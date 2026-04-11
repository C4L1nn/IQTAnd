package com.iqtmusic.mobile.data.remote

import android.util.Log
import com.iqtmusic.mobile.data.model.Track
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder

/**
 * Sunucu üzerinden YouTube Music arama yapar.
 * [getServerUrl] lambda'sı her çağrıda güncel sunucu adresini döner.
 *
 * Endpoint: GET /search?q=SORGU → [{id, title, artist, album, durationLabel, coverUrl, videoId}]
 */
class RemoteApi(private val getServerUrl: () -> String = { "" }) {

    private val json = Json { ignoreUnknownKeys = true }

    suspend fun search(query: String): List<Track> = withContext(Dispatchers.IO) {
        val server = getServerUrl()
        if (server.isBlank()) return@withContext emptyList()

        runCatching {
            val encoded = URLEncoder.encode(query, "UTF-8")
            val conn = URL("$server/search?q=$encoded").openConnection() as HttpURLConnection
            conn.connectTimeout = 5_000
            conn.readTimeout = 20_000

            if (conn.responseCode != 200) {
                Log.w(TAG, "Search HTTP ${conn.responseCode}")
                conn.disconnect()
                return@runCatching emptyList()
            }

            val body = conn.inputStream.bufferedReader().readText().also { conn.disconnect() }
            val results = json.decodeFromString<List<RemoteTrack>>(body).map { it.toTrack() }
            Log.d(TAG, "Search '$query': ${results.size} results")
            results
        }.getOrElse { e ->
            Log.e(TAG, "Search error: ${e.message}")
            emptyList()
        }
    }

    private companion object {
        const val TAG = "RemoteApi"
    }
}

@Serializable
private data class RemoteTrack(
    val id: String = "",
    val title: String = "",
    val artist: String = "",
    val album: String = "",
    val durationLabel: String = "",
    val coverUrl: String? = null,
    val videoId: String? = null,
) {
    fun toTrack(): Track = Track(
        id = id.ifBlank { "yt-${videoId.orEmpty()}" },
        title = title,
        artist = artist,
        album = album,
        durationLabel = durationLabel,
        coverUrl = coverUrl?.takeIf { it.isNotBlank() },
        videoId = videoId ?: id.removePrefix("yt-"),
    )
}
