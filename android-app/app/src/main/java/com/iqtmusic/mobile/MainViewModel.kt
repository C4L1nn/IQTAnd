package com.iqtmusic.mobile

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.iqtmusic.mobile.AppContainer
import com.iqtmusic.mobile.data.model.LibrarySnapshot
import com.iqtmusic.mobile.data.model.Track
import com.iqtmusic.mobile.data.remote.RemoteApi
import com.iqtmusic.mobile.data.repository.LibraryRepository
import com.iqtmusic.mobile.playback.PlayerProgress
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.coroutines.Dispatchers

data class MainUiState(
    val snapshot: LibrarySnapshot = LibrarySnapshot.EMPTY,
    val searchQuery: String = "",
    val recentTracks: List<Track> = emptyList(),
    val favoriteTracks: List<Track> = emptyList(),
    val searchResults: List<Track> = emptyList(),
    val queueTracks: List<Track> = emptyList(),
    val remoteSearchResults: List<Track> = emptyList(),
    val isRemoteSearching: Boolean = false,
    val serverUrl: String = "",
    val serverStatus: ServerStatus = ServerStatus.UNCHECKED,
    val isStreamLoading: Boolean = false,
    val downloadProgress: Map<String, Float> = emptyMap(),
    val currentLyrics: String? = null,
    val isLyricsLoading: Boolean = false,
)

enum class ServerStatus { UNCHECKED, CHECKING, ONLINE, OFFLINE }

class MainViewModel(
    private val repository: LibraryRepository,
    private val remoteApi: RemoteApi,
    private val appContainer: AppContainer,
) : ViewModel() {
    private val searchQuery = MutableStateFlow("")
    private val remoteResults = MutableStateFlow<List<Track>>(emptyList())
    private val isRemoteSearching = MutableStateFlow(false)
    private val serverUrl = MutableStateFlow(appContainer.getServerUrl())
    private val serverStatus = MutableStateFlow(ServerStatus.UNCHECKED)
    private var searchJob: Job? = null
    private var statusCheckJob: Job? = null

    val streamErrorFlow: SharedFlow<String> = appContainer.streamErrorFlow

    val playerProgress: StateFlow<PlayerProgress> = appContainer.playerProgress
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), PlayerProgress())

    val downloadProgress: StateFlow<Map<String, Float>> = appContainer.downloadManager.progress
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyMap())

    private val _lyricsState = MutableStateFlow<Pair<Boolean, String?>>(false to null)
    val lyricsState: StateFlow<Pair<Boolean, String?>> = _lyricsState

    val uiState: StateFlow<MainUiState> = combine(
        repository.snapshot,
        searchQuery,
        combine(remoteResults, isRemoteSearching) { r, s -> r to s },
        combine(serverUrl, serverStatus, appContainer.streamLoading) { url, status, loading ->
            Triple(url, status, loading)
        },
        combine(appContainer.downloadManager.progress) { arr -> arr[0] },
    ) { snapshot, query, (remote, searching), (url, status, streamLoading), dlProgress ->
        val normalized = query.trim()
        val recentTracks = snapshot.recentTrackIds.mapNotNull { id ->
            snapshot.tracks.find { it.id == id }
        }
        val favoriteTracks = snapshot.tracks.filter { it.id in snapshot.favoriteTrackIds }
        val queueTracks = snapshot.queueTrackIds.mapNotNull { id ->
            snapshot.tracks.find { it.id == id }
        }
        val localResults = if (normalized.isBlank()) emptyList<com.iqtmusic.mobile.data.model.Track>() else {
            snapshot.tracks.filter { track ->
                track.title.contains(normalized, ignoreCase = true) ||
                    track.artist.contains(normalized, ignoreCase = true) ||
                    track.album.contains(normalized, ignoreCase = true)
            }
        }
        MainUiState(
            snapshot = snapshot,
            searchQuery = normalized,
            recentTracks = recentTracks,
            favoriteTracks = favoriteTracks,
            searchResults = localResults,
            queueTracks = queueTracks,
            remoteSearchResults = remote,
            isRemoteSearching = searching,
            serverUrl = url,
            serverStatus = status,
            isStreamLoading = streamLoading,
            downloadProgress = dlProgress,
        )
    }.stateIn(
        scope = viewModelScope,
        started = SharingStarted.WhileSubscribed(5_000),
        initialValue = MainUiState(),
    )

    fun updateSearchQuery(value: String) {
        searchQuery.update { value }
        searchJob?.cancel()
        if (value.isBlank()) {
            remoteResults.value = emptyList()
            isRemoteSearching.value = false
            return
        }
        searchJob = viewModelScope.launch {
            delay(600) // debounce
            isRemoteSearching.value = true
            remoteResults.value = remoteApi.search(value)
            isRemoteSearching.value = false
        }
    }

    fun toggleFavorite(trackId: String) {
        viewModelScope.launch { repository.toggleFavorite(trackId) }
    }

    fun playTrack(trackId: String) {
        viewModelScope.launch { repository.playTrack(trackId) }
    }

    /** Arama sonucundan gelen track'i kütüphaneye ekle ve çal. */
    fun addAndPlayTrack(track: Track) {
        viewModelScope.launch { repository.addAndPlayTrack(track) }
    }

    fun playPlaylist(playlistId: String, startTrackId: String? = null) {
        viewModelScope.launch { repository.playPlaylist(playlistId, startTrackId) }
    }

    fun togglePlayback() {
        viewModelScope.launch { repository.togglePlayback() }
    }

    fun createPlaylist(name: String) {
        viewModelScope.launch { repository.createPlaylist(name) }
    }

    fun addTrackToPlaylist(playlistId: String, trackId: String) {
        viewModelScope.launch { repository.addTrackToPlaylist(playlistId, trackId) }
    }

    fun removeTrackFromPlaylist(playlistId: String, trackId: String) {
        viewModelScope.launch { repository.removeTrackFromPlaylist(playlistId, trackId) }
    }

    fun startCollabHost() {
        viewModelScope.launch { repository.startCollabHost() }
    }

    fun skipNext() {
        viewModelScope.launch { repository.skipNext() }
    }

    fun skipPrevious() {
        viewModelScope.launch { repository.skipPrevious() }
    }

    fun removeTrack(trackId: String) {
        viewModelScope.launch { repository.removeTrack(trackId) }
    }

    fun toggleShuffle() {
        viewModelScope.launch { repository.toggleShuffle() }
    }

    fun cycleRepeatMode() {
        viewModelScope.launch { repository.cycleRepeatMode() }
    }

    fun seekTo(fraction: Float) {
        val durationMs = appContainer.playerProgress.value.durationMs
        if (durationMs <= 0L) return
        val positionMs = (durationMs * fraction.coerceIn(0f, 1f)).toLong()
        viewModelScope.launch { appContainer.seekRequestFlow.emit(positionMs) }
    }

    fun downloadTrack(trackId: String) {
        val track = repository.snapshot.value.tracks.find { it.id == trackId } ?: return
        val videoId = track.videoId ?: return
        if (track.isDownloaded) return
        viewModelScope.launch {
            val path = appContainer.downloadManager.download(trackId, videoId)
            if (path != null) {
                repository.markTrackDownloaded(trackId, path)
            }
        }
    }

    fun deleteDownload(trackId: String) {
        val track = repository.snapshot.value.tracks.find { it.id == trackId } ?: return
        appContainer.downloadManager.deleteLocal(trackId)
        viewModelScope.launch { repository.clearTrackDownload(trackId) }
        track.localPath // consumed
    }

    fun loadLyrics(trackId: String) {
        val track = repository.snapshot.value.tracks.find { it.id == trackId } ?: return
        _lyricsState.value = true to null
        viewModelScope.launch {
            val text = withContext(Dispatchers.IO) {
                appContainer.lyricsRepository.getLyrics(track.title, track.artist, track.durationMs)
            }
            _lyricsState.value = false to text
        }
    }

    fun saveServerUrl(url: String) {
        appContainer.setServerUrl(url)
        serverUrl.value = appContainer.getServerUrl()
        serverStatus.value = ServerStatus.UNCHECKED
    }

    fun checkServerConnection() {
        val url = serverUrl.value
        if (url.isBlank()) { serverStatus.value = ServerStatus.OFFLINE; return }
        statusCheckJob?.cancel()
        statusCheckJob = viewModelScope.launch {
            serverStatus.value = ServerStatus.CHECKING
            serverStatus.value = kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.IO) {
                runCatching {
                    val conn = java.net.URL("$url/health").openConnection() as java.net.HttpURLConnection
                    conn.connectTimeout = 5_000
                    conn.readTimeout = 5_000
                    val code = conn.responseCode
                    conn.disconnect()
                    if (code == 200) ServerStatus.ONLINE else ServerStatus.OFFLINE
                }.getOrElse { ServerStatus.OFFLINE }
            }
        }
    }

    class Factory(
        private val repository: LibraryRepository,
        private val remoteApi: RemoteApi,
        private val appContainer: AppContainer,
    ) : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T =
            MainViewModel(repository, remoteApi, appContainer) as T
    }
}
