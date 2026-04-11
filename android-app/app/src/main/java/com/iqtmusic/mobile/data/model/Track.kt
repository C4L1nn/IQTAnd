package com.iqtmusic.mobile.data.model

import kotlinx.serialization.Serializable

@Serializable
data class Track(
    val id: String,
    val title: String,
    val artist: String,
    val durationLabel: String,
    val album: String = "",
    val coverUrl: String? = null,
    val isDownloaded: Boolean = false,
    val isFavorite: Boolean = false,
    /** YouTube video ID — ExoPlayer bu ID üzerinden stream URL'si çözer. */
    val videoId: String? = null,
)
