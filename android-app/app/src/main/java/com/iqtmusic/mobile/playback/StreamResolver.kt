package com.iqtmusic.mobile.playback

import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.schabi.newpipe.extractor.NewPipe
import org.schabi.newpipe.extractor.ServiceList

/**
 * YouTube stream URL'sini doğrudan cihazdan çözer (NewPipeExtractor).
 * Sunucu IP'si yerine cihazın kendi (residential) IP'sini kullanır —
 * YouTube'un datacenter engelinden etkilenmez.
 */
class StreamResolver {

    init {
        runCatching { NewPipe.init(NewPipeDownloader) }
    }

    suspend fun getAudioUrl(videoId: String): String? = withContext(Dispatchers.IO) {
        try {
            val url = "https://www.youtube.com/watch?v=$videoId"
            val extractor = ServiceList.YouTube.getStreamExtractor(url)
            extractor.fetchPage()

            val audioStreams = extractor.audioStreams
            if (audioStreams.isEmpty()) {
                Log.e(TAG, "No audio streams for $videoId")
                return@withContext null
            }

            val best = audioStreams.maxByOrNull { it.averageBitrate }
            val streamUrl = best?.content

            if (streamUrl != null) Log.d(TAG, "OK: ${streamUrl.take(80)}...")
            else Log.e(TAG, "Stream URL null for $videoId")

            streamUrl
        } catch (e: Exception) {
            Log.e(TAG, "Error: $videoId — ${e.message}")
            null
        }
    }

    private companion object {
        const val TAG = "StreamResolver"
    }
}
