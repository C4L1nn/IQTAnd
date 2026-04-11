package com.iqtmusic.mobile.data.repository

import com.iqtmusic.mobile.data.model.LibrarySnapshot
import com.iqtmusic.mobile.data.model.Playlist
import com.iqtmusic.mobile.data.model.Track
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update

class FakeLibraryRepository : LibraryRepository {
    private val state = MutableStateFlow(seedSnapshot())

    override val snapshot: StateFlow<LibrarySnapshot> = state.asStateFlow()

    override suspend fun toggleFavorite(trackId: String) {
        state.update { current ->
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
        state.update { current ->
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
        state.update { current ->
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
        state.update { current ->
            val playlist = current.playlists.find { it.id == playlistId } ?: return@update current
            val queue = playlist.trackIds.filter { id -> current.tracks.any { it.id == id } }
            if (queue.isEmpty()) return@update current

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
        state.update { current ->
            if (current.currentTrackId == null) current else current.copy(isPlaying = !current.isPlaying)
        }
    }

    override suspend fun createPlaylist(name: String) {
        val clean = name.trim()
        if (clean.isBlank()) return

        state.update { current ->
            if (current.playlists.any { it.name.equals(clean, ignoreCase = true) }) {
                current
            } else {
                val newPlaylist = Playlist(
                    id = "pl-${clean.lowercase().replace(" ", "-")}-${current.playlists.size + 1}",
                    name = clean,
                    trackIds = current.recentTrackIds.take(3),
                )
                current.copy(playlists = listOf(newPlaylist) + current.playlists)
            }
        }
    }

    override suspend fun addTrackToPlaylist(playlistId: String, trackId: String) {
        state.update { current ->
            if (current.tracks.none { it.id == trackId }) return@update current

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
        state.update { current ->
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
        state.update { current ->
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

    private fun seedSnapshot(): LibrarySnapshot = seedLibrarySnapshot()
}
