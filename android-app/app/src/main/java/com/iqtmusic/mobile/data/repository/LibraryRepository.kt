package com.iqtmusic.mobile.data.repository

import com.iqtmusic.mobile.data.model.LibrarySnapshot
import com.iqtmusic.mobile.data.model.Track
import kotlinx.coroutines.flow.StateFlow

interface LibraryRepository {
    val snapshot: StateFlow<LibrarySnapshot>

    suspend fun toggleFavorite(trackId: String)
    suspend fun playTrack(trackId: String)
    /** Arama sonucunu kütüphaneye ekler ve hemen çalar. */
    suspend fun addAndPlayTrack(track: Track)
    suspend fun playPlaylist(playlistId: String, startTrackId: String? = null)
    suspend fun togglePlayback()
    suspend fun createPlaylist(name: String)
    suspend fun addTrackToPlaylist(playlistId: String, trackId: String)
    suspend fun removeTrackFromPlaylist(playlistId: String, trackId: String)
    suspend fun startCollabHost()
    suspend fun skipNext()
    suspend fun skipPrevious()
    suspend fun removeTrack(trackId: String)
    suspend fun toggleShuffle()
    suspend fun cycleRepeatMode()
    suspend fun handlePlaybackEnded()
    suspend fun markTrackDownloaded(trackId: String, localPath: String)
    suspend fun clearTrackDownload(trackId: String)
}
