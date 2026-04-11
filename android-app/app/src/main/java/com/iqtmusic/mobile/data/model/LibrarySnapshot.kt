package com.iqtmusic.mobile.data.model

import kotlinx.serialization.Serializable

@Serializable
data class ListeningStats(
    val totalMinutes: Int,
    val weeklyMinutes: Int,
    val streakDays: Int,
    val topArtist: String,
)

@Serializable
data class CollabSessionState(
    val isActive: Boolean,
    val roleLabel: String,
    val roomCode: String?,
    val participants: Int,
    val status: String,
)

@Serializable
data class LibrarySnapshot(
    val tracks: List<Track>,
    val playlists: List<Playlist>,
    val favoriteTrackIds: List<String>,
    val recentTrackIds: List<String>,
    val queueTrackIds: List<String>,
    val stats: ListeningStats,
    val collab: CollabSessionState,
    val currentTrackId: String?,
    val isPlaying: Boolean,
) {
    companion object {
        val EMPTY = LibrarySnapshot(
            tracks = emptyList(),
            playlists = emptyList(),
            favoriteTrackIds = emptyList(),
            recentTrackIds = emptyList(),
            queueTrackIds = emptyList(),
            stats = ListeningStats(0, 0, 0, "-"),
            collab = CollabSessionState(
                isActive = false,
                roleLabel = "Hazir",
                roomCode = null,
                participants = 1,
                status = "Bagli degil",
            ),
            currentTrackId = null,
            isPlaying = false,
        )
    }
}
