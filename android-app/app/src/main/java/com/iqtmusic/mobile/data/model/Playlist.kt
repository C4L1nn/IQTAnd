package com.iqtmusic.mobile.data.model

import kotlinx.serialization.Serializable

@Serializable
data class Playlist(
    val id: String,
    val name: String,
    val trackIds: List<String>,
    val customCoverUrl: String? = null,
)
