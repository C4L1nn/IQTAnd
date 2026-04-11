package com.iqtmusic.mobile.playback

import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import java.net.HttpURLConnection
import java.net.URL

/**
 * Sunucudan ses stream URL'si çözer.
 * [getServerUrl] lambda'sı her çağrıda güncel sunucu adresini döner.
 *
 * Sunucu: stream_server.py (local ADB tüneli VEYA Render.com cloud)
 * Endpoint: GET /stream?videoId=XXX → {"url": "..."}
 */
class StreamResolver(private val getServerUrl: () -> String = { "" }) {

    private val json = Json { ignoreUnknownKeys = true }

    suspend fun getAudioUrl(videoId: String): String? = withContext(Dispatchers.IO) {
        val server = getServerUrl()
        if (server.isBlank()) {
            Log.e(TAG, "Sunucu URL'si ayarlanmamis. Ayarlar ekranindan gir.")
            return@withContext null
        }

        Log.d(TAG, "Requesting stream for $videoId from $server")
        val result = runCatching {
            val conn = URL("$server/stream?videoId=$videoId").openConnection() as HttpURLConnection
            conn.connectTimeout = 5_000
            conn.readTimeout = 30_000  // yt-dlp biraz zaman alabilir
            conn.setRequestProperty("User-Agent", "iqtMusic-Android/1.0")

            if (conn.responseCode != 200) {
                Log.w(TAG, "HTTP ${conn.responseCode} for $videoId")
                conn.disconnect()
                return@runCatching null
            }

            val body = conn.inputStream.bufferedReader().readText().also { conn.disconnect() }
            json.decodeFromString<StreamResponse>(body).url.takeIf { it.isNotBlank() }
        }.getOrElse { e ->
            Log.e(TAG, "Stream error for $videoId: ${e.message}")
            null
        }

        if (result != null) Log.d(TAG, "OK: ${result.take(80)}...")
        else Log.e(TAG, "Failed: $videoId")
        result
    }

    private companion object {
        const val TAG = "StreamResolver"
    }
}

@Serializable
private data class StreamResponse(val url: String = "")
