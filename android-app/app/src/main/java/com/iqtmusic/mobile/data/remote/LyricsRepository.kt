package com.iqtmusic.mobile.data.remote

import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder

private const val TAG = "LyricsRepository"

class LyricsRepository {
    private val json = Json { ignoreUnknownKeys = true }
    private val cache = mutableMapOf<String, String?>()

    suspend fun getLyrics(title: String, artist: String, durationMs: Long): String? =
        withContext(Dispatchers.IO) {
            val key = "$artist|$title"
            if (cache.containsKey(key)) return@withContext cache[key]

            val result = runCatching {
                val t = URLEncoder.encode(title.take(100), "UTF-8")
                val a = URLEncoder.encode(artist.take(100), "UTF-8")
                val dSec = durationMs / 1000
                val url = "https://lrclib.net/api/get?artist_name=$a&track_name=$t" +
                    if (dSec > 0) "&duration=$dSec" else ""

                val conn = URL(url).openConnection() as HttpURLConnection
                conn.connectTimeout = 8_000
                conn.readTimeout = 10_000
                conn.setRequestProperty("User-Agent", "iqtMusic/1.0 (github.com/C4L1nn/iqtMusic)")

                try {
                    if (conn.responseCode != 200) {
                        Log.d(TAG, "lrclib HTTP ${conn.responseCode} for $artist - $title")
                        return@runCatching null
                    }
                    val body = conn.inputStream.bufferedReader().readText()
                    val response = json.decodeFromString<LrclibResponse>(body)
                    response.plainLyrics?.takeIf { it.isNotBlank() }
                        ?: response.syncedLyrics?.let { parseSyncedLyrics(it) }
                } finally {
                    conn.disconnect()
                }
            }.getOrElse { e ->
                Log.e(TAG, "Lyrics fetch error: ${e.message}")
                null
            }

            cache[key] = result
            result
        }

    /** "[mm:ss.xx] line" formatından saf metni çıkar */
    private fun parseSyncedLyrics(synced: String): String =
        synced.lines()
            .map { it.replace(Regex("^\\[\\d+:\\d+\\.\\d+]\\s*"), "").trim() }
            .filter { it.isNotBlank() }
            .joinToString("\n")
}

@Serializable
private data class LrclibResponse(
    val plainLyrics: String? = null,
    val syncedLyrics: String? = null,
)
