package com.iqtmusic.mobile.playback

data class PlayerProgress(
    val positionMs: Long = 0L,
    val durationMs: Long = 0L,
) {
    val fraction: Float
        get() = if (durationMs > 0L) (positionMs.toFloat() / durationMs).coerceIn(0f, 1f) else 0f
}
