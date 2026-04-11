package com.iqtmusic.mobile

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.iqtmusic.mobile.AppContainer
import com.iqtmusic.mobile.data.model.LibrarySnapshot
import com.iqtmusic.mobile.data.model.Track
import com.iqtmusic.mobile.data.remote.RemoteApi
import com.iqtmusic.mobile.data.repository.LibraryRepository
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

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

    val uiState: StateFlow<MainUiState> = combine(
        repository.snapshot,
        searchQuery,
        remoteResults,
        isRemoteSearching,
        combine(serverUrl, serverStatus) { url, status -> url to status },
    ) { snapshot, query, remote, searching, (url, status) ->
        val normalized = query.trim()
        val recentTracks = snapshot.recentTrackIds.mapNotNull { id ->
            snapshot.tracks.find { it.id == id }
        }
        val favoriteTracks = snapshot.tracks.filter { it.id in snapshot.favoriteTrackIds }
        val queueTracks = snapshot.queueTrackIds.mapNotNull { id ->
            snapshot.tracks.find { it.id == id }
        }
        val localResults = if (normalized.isBlank()) emptyList() else {
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

    fun saveServerUrl(url: String) {
        appContainer.setServerUrl(url)
        serverUrl.value = url
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
