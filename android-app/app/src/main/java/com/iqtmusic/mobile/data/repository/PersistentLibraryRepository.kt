package com.iqtmusic.mobile.data.repository

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import com.iqtmusic.mobile.data.model.LibrarySnapshot
import com.iqtmusic.mobile.data.model.Track
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.serialization.decodeFromString
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json

private val Context.libraryDataStore by preferencesDataStore(name = "iqtmusic_library")

class PersistentLibraryRepository(
    private val context: Context,
    private val scope: CoroutineScope = CoroutineScope(SupervisorJob() + Dispatchers.IO),
) : LibraryRepository {
    private val state = MutableStateFlow(LibrarySnapshot.EMPTY)
    private val mutex = Mutex()
    private val json = Json {
        ignoreUnknownKeys = true
        prettyPrint = false
        explicitNulls = false
    }
    private val snapshotKey = stringPreferencesKey("library_snapshot_json")

    override val snapshot: StateFlow<LibrarySnapshot> = state.asStateFlow()

    init {
        scope.launch {
            loadInitialSnapshot()
        }
    }

    override suspend fun toggleFavorite(trackId: String) {
        mutate { current ->
            val currentlyFavorite = trackId in current.favoriteTrackIds
            val favorites = if (currentlyFavorite) {
                current.favoriteTrackIds.filterNot { it == trackId }
            } else {
                listOf(trackId) + current.favoriteTrackIds
            }

            current.copy(
                favoriteTrackIds = favorites.distinct(),
                tracks = current.tracks.map { track ->
                    if (track.id == trackId) {
                        track.copy(isFavorite = !currentlyFavorite)
                    } else {
                        track
                    }
                },
            )
        }
    }

    override suspend fun addAndPlayTrack(track: Track) {
        mutate { current ->
            val tracks = if (current.tracks.any { it.id == track.id }) current.tracks
                         else current.tracks + listOf(track)
            val recentIds = listOf(track.id) + current.recentTrackIds.filterNot { it == track.id }
            current.copy(
                tracks = tracks,
                currentTrackId = track.id,
                isPlaying = true,
                recentTrackIds = recentIds.take(12),
                queueTrackIds = listOf(track.id),
            )
        }
    }

    override suspend fun playTrack(trackId: String) {
        mutate { current ->
            val baseQueue = current.queueTrackIds.ifEmpty { current.tracks.map { it.id } }
            val queue = if (trackId in baseQueue) baseQueue else listOf(trackId) + baseQueue.filterNot { it == trackId }
            val recentIds = listOf(trackId) + current.recentTrackIds.filterNot { it == trackId }
            current.copy(
                currentTrackId = trackId,
                isPlaying = true,
                recentTrackIds = recentIds.take(12),
                queueTrackIds = queue,
            )
        }
    }

    override suspend fun playPlaylist(playlistId: String, startTrackId: String?) {
        mutate { current ->
            val playlist = current.playlists.find { it.id == playlistId } ?: return@mutate current
            val queue = playlist.trackIds.filter { id -> current.tracks.any { it.id == id } }
            if (queue.isEmpty()) return@mutate current

            val currentTrackId = when {
                startTrackId != null && startTrackId in queue -> startTrackId
                current.currentTrackId in queue -> current.currentTrackId
                else -> queue.first()
            }

            val recentIds = listOfNotNull(currentTrackId) + current.recentTrackIds.filterNot { it == currentTrackId }
            current.copy(
                currentTrackId = currentTrackId,
                isPlaying = true,
                queueTrackIds = queue,
                recentTrackIds = recentIds.take(12),
            )
        }
    }

    override suspend fun togglePlayback() {
        mutate { current ->
            if (current.currentTrackId == null) current else current.copy(isPlaying = !current.isPlaying)
        }
    }

    override suspend fun createPlaylist(name: String) {
        val clean = name.trim()
        if (clean.isBlank()) return

        mutate { current ->
            if (current.playlists.any { it.name.equals(clean, ignoreCase = true) }) {
                current
            } else {
                current.copy(
                    playlists = listOf(
                        com.iqtmusic.mobile.data.model.Playlist(
                            id = "pl-${clean.lowercase().replace(" ", "-")}-${current.playlists.size + 1}",
                            name = clean,
                            trackIds = current.recentTrackIds.take(3),
                        ),
                    ) + current.playlists,
                )
            }
        }
    }

    override suspend fun addTrackToPlaylist(playlistId: String, trackId: String) {
        mutate { current ->
            if (current.tracks.none { it.id == trackId }) return@mutate current

            current.copy(
                playlists = current.playlists.map { playlist ->
                    if (playlist.id != playlistId || trackId in playlist.trackIds) {
                        playlist
                    } else {
                        playlist.copy(trackIds = playlist.trackIds + trackId)
                    }
                },
            )
        }
    }

    override suspend fun removeTrackFromPlaylist(playlistId: String, trackId: String) {
        mutate { current ->
            current.copy(
                playlists = current.playlists.map { playlist ->
                    if (playlist.id != playlistId || trackId !in playlist.trackIds) {
                        playlist
                    } else {
                        playlist.copy(trackIds = playlist.trackIds.filterNot { it == trackId })
                    }
                },
            )
        }
    }

    override suspend fun startCollabHost() {
        mutate { current ->
            current.copy(
                collab = current.collab.copy(
                    isActive = true,
                    roleLabel = "Host",
                    roomCode = "IQT8MUSIC",
                    participants = 2,
                    status = "Oda aktif, davet bekleniyor",
                ),
            )
        }
    }

    private suspend fun loadInitialSnapshot() {
        val stored = context.libraryDataStore.data.first()[snapshotKey]
        val snapshot = if (stored.isNullOrBlank()) {
            seedLibrarySnapshot()
        } else {
            runCatching { json.decodeFromString<LibrarySnapshot>(stored) }
                .getOrElse { seedLibrarySnapshot() }
        }
        state.value = snapshot
        persist(snapshot)
    }

    private suspend fun mutate(transform: (LibrarySnapshot) -> LibrarySnapshot) {
        mutex.withLock {
            val updated = transform(state.value)
            state.update { updated }
            persist(updated)
        }
    }

    private suspend fun persist(snapshot: LibrarySnapshot) {
        val encoded = json.encodeToString(snapshot)
        context.libraryDataStore.edit { prefs ->
            prefs[snapshotKey] = encoded
        }
    }
}
