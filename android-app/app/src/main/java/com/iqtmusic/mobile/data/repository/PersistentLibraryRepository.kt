package com.iqtmusic.mobile.data.repository

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import com.iqtmusic.mobile.data.model.LibrarySnapshot
import com.iqtmusic.mobile.data.model.ListeningStats
import com.iqtmusic.mobile.data.model.RepeatMode
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
import java.util.Calendar

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
            val track = current.tracks.find { it.id == trackId }
            val today = todayKey()
            val newPlayDates = (listOf(today) + current.playDates).distinct().take(90)
            val newArtistCounts = current.artistPlayCounts.toMutableMap().also { map ->
                track?.artist?.takeIf { it.isNotBlank() }?.let { artist ->
                    map[artist] = (map[artist] ?: 0) + 1
                }
            }
            val topArtist = newArtistCounts.maxByOrNull { it.value }?.key ?: current.stats.topArtist
            current.copy(
                currentTrackId = trackId,
                isPlaying = true,
                recentTrackIds = recentIds.take(12),
                queueTrackIds = queue,
                playDates = newPlayDates,
                artistPlayCounts = newArtistCounts,
                stats = current.stats.copy(
                    topArtist = topArtist,
                    streakDays = calculateStreak(newPlayDates),
                ),
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

    override suspend fun skipNext() {
        mutate { current ->
            val queue = current.queueTrackIds.ifEmpty { return@mutate current }
            val idx = queue.indexOf(current.currentTrackId)
            val nextId = if (idx >= 0 && idx < queue.lastIndex) queue[idx + 1] else return@mutate current
            val recentIds = listOf(nextId) + current.recentTrackIds.filterNot { it == nextId }
            current.copy(currentTrackId = nextId, isPlaying = true, recentTrackIds = recentIds.take(12))
        }
    }

    override suspend fun skipPrevious() {
        mutate { current ->
            val queue = current.queueTrackIds.ifEmpty { return@mutate current }
            val idx = queue.indexOf(current.currentTrackId)
            val prevId = if (idx > 0) queue[idx - 1] else return@mutate current
            val recentIds = listOf(prevId) + current.recentTrackIds.filterNot { it == prevId }
            current.copy(currentTrackId = prevId, isPlaying = true, recentTrackIds = recentIds.take(12))
        }
    }

    override suspend fun removeTrack(trackId: String) {
        mutate { current ->
            val newQueue = current.queueTrackIds.filterNot { it == trackId }
            val newCurrentId = if (current.currentTrackId == trackId) newQueue.firstOrNull() else current.currentTrackId
            current.copy(
                tracks = current.tracks.filterNot { it.id == trackId },
                queueTrackIds = newQueue,
                recentTrackIds = current.recentTrackIds.filterNot { it == trackId },
                favoriteTrackIds = current.favoriteTrackIds.filterNot { it == trackId },
                currentTrackId = newCurrentId,
                isPlaying = if (current.currentTrackId == trackId) newCurrentId != null else current.isPlaying,
                playlists = current.playlists.map { pl ->
                    pl.copy(trackIds = pl.trackIds.filterNot { it == trackId })
                },
            )
        }
    }

    override suspend fun toggleShuffle() {
        mutate { current ->
            if (current.shuffleEnabled) {
                current.copy(shuffleEnabled = false)
            } else {
                val idx = current.queueTrackIds.indexOf(current.currentTrackId)
                val rest = current.queueTrackIds.toMutableList()
                val current2 = if (idx >= 0) rest.removeAt(idx) else null
                val shuffled = rest.shuffled()
                val newQueue = if (current2 != null) listOf(current2) + shuffled else shuffled
                current.copy(shuffleEnabled = true, queueTrackIds = newQueue)
            }
        }
    }

    override suspend fun cycleRepeatMode() {
        mutate { current ->
            val next = when (current.repeatMode) {
                RepeatMode.NONE -> RepeatMode.ALL
                RepeatMode.ALL -> RepeatMode.ONE
                RepeatMode.ONE -> RepeatMode.NONE
            }
            current.copy(repeatMode = next)
        }
    }

    override suspend fun handlePlaybackEnded() {
        mutate { current ->
            val queue = current.queueTrackIds.ifEmpty { return@mutate current.copy(isPlaying = false) }
            val idx = queue.indexOf(current.currentTrackId)

            // Biten şarkının süresini istatistiklere ekle
            val finishedTrack = current.tracks.find { it.id == current.currentTrackId }
            val addedMinutes = finishedTrack?.durationMs?.div(60_000L)?.toInt() ?: 0
            val today = todayKey()
            val newTotal = current.totalPlayedMinutes + addedMinutes
            val newDayMap = current.dayPlayMinutes.toMutableMap().also {
                it[today] = (it[today] ?: 0) + addedMinutes
            }
            val weeklyMinutes = last7DaysMinutes(newDayMap)
            val updatedStats = current.stats.copy(
                totalMinutes = newTotal,
                weeklyMinutes = weeklyMinutes,
            )

            fun advance(nextId: String, cur: LibrarySnapshot): LibrarySnapshot {
                val recentIds = listOf(nextId) + cur.recentTrackIds.filterNot { it == nextId }
                return cur.copy(
                    currentTrackId = nextId,
                    isPlaying = true,
                    recentTrackIds = recentIds.take(12),
                    totalPlayedMinutes = newTotal,
                    dayPlayMinutes = newDayMap,
                    stats = updatedStats,
                )
            }

            when (current.repeatMode) {
                RepeatMode.ONE -> current.copy(
                    totalPlayedMinutes = newTotal,
                    dayPlayMinutes = newDayMap,
                    stats = updatedStats,
                )
                RepeatMode.ALL -> {
                    val nextId = if (idx >= 0 && idx < queue.lastIndex) queue[idx + 1] else queue.first()
                    advance(nextId, current)
                }
                RepeatMode.NONE -> {
                    if (idx >= 0 && idx < queue.lastIndex) {
                        advance(queue[idx + 1], current)
                    } else {
                        current.copy(
                            isPlaying = false,
                            totalPlayedMinutes = newTotal,
                            dayPlayMinutes = newDayMap,
                            stats = updatedStats,
                        )
                    }
                }
            }
        }
    }

    override suspend fun markTrackDownloaded(trackId: String, localPath: String) {
        mutate { current ->
            current.copy(
                tracks = current.tracks.map { t ->
                    if (t.id == trackId) t.copy(isDownloaded = true, localPath = localPath) else t
                },
            )
        }
    }

    override suspend fun clearTrackDownload(trackId: String) {
        mutate { current ->
            current.copy(
                tracks = current.tracks.map { t ->
                    if (t.id == trackId) t.copy(isDownloaded = false, localPath = null) else t
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

    private fun todayKey(): String {
        val c = Calendar.getInstance()
        val y = c.get(Calendar.YEAR)
        val m = (c.get(Calendar.MONTH) + 1).toString().padStart(2, '0')
        val d = c.get(Calendar.DAY_OF_MONTH).toString().padStart(2, '0')
        return "$y$m$d"
    }

    private fun calculateStreak(playDates: List<String>): Int {
        if (playDates.isEmpty()) return 0
        val sorted = playDates.sortedDescending()
        val today = todayKey()
        var streak = 0
        var expected = today
        for (date in sorted) {
            if (date == expected) {
                streak++
                expected = previousDay(date)
            } else {
                break
            }
        }
        return streak
    }

    private fun previousDay(dateKey: String): String {
        val c = Calendar.getInstance().also {
            it.set(
                dateKey.substring(0, 4).toInt(),
                dateKey.substring(4, 6).toInt() - 1,
                dateKey.substring(6, 8).toInt(),
            )
            it.add(Calendar.DAY_OF_MONTH, -1)
        }
        val y = c.get(Calendar.YEAR)
        val m = (c.get(Calendar.MONTH) + 1).toString().padStart(2, '0')
        val d = c.get(Calendar.DAY_OF_MONTH).toString().padStart(2, '0')
        return "$y$m$d"
    }

    private fun last7DaysMinutes(dayMap: Map<String, Int>): Int {
        val c = Calendar.getInstance()
        var total = 0
        repeat(7) {
            val y = c.get(Calendar.YEAR)
            val m = (c.get(Calendar.MONTH) + 1).toString().padStart(2, '0')
            val d = c.get(Calendar.DAY_OF_MONTH).toString().padStart(2, '0')
            total += dayMap["$y$m$d"] ?: 0
            c.add(Calendar.DAY_OF_MONTH, -1)
        }
        return total
    }

    private suspend fun loadInitialSnapshot() {
        val stored = context.libraryDataStore.data.first()[snapshotKey]
        val snapshot = if (stored.isNullOrBlank()) {
            seedLibrarySnapshot()
        } else {
            runCatching { json.decodeFromString<LibrarySnapshot>(stored) }
                .getOrElse { seedLibrarySnapshot() }
        }
        val normalized = normalizeLoadedSnapshot(snapshot)
        state.value = normalized
        persist(normalized)
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

    private fun normalizeLoadedSnapshot(snapshot: LibrarySnapshot): LibrarySnapshot {
        return if (isLegacySeedSnapshot(snapshot)) {
            LibrarySnapshot.EMPTY
        } else {
            snapshot.copy(isPlaying = false)
        }
    }

    private fun isLegacySeedSnapshot(snapshot: LibrarySnapshot): Boolean {
        val legacyTrackIds = setOf("trk-1", "trk-2", "trk-3", "trk-4", "trk-5", "trk-6")
        val legacyPlaylistIds = setOf("pl-1", "pl-2")
        return snapshot.tracks.isNotEmpty() &&
            snapshot.tracks.all { it.id in legacyTrackIds } &&
            snapshot.playlists.all { it.id in legacyPlaylistIds }
    }
}
