package com.iqtmusic.mobile.playback

import android.content.Context
import android.os.Environment
import android.util.Log
import android.webkit.CookieManager
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.withContext
import java.io.File
import java.net.HttpURLConnection
import java.net.URL

private const val TAG = "DownloadManager"

/**
 * Track'i local depolamaya indirir.
 * Progress 0f–1f arası; tamamlanınca map'ten çıkar.
 * Hata durumunda null döner, map'ten çıkarılır.
 */
class DownloadManager(
    private val context: Context,
    private val streamResolver: StreamResolver,
) {
    private val _progress = MutableStateFlow<Map<String, Float>>(emptyMap())
    val progress: StateFlow<Map<String, Float>> = _progress.asStateFlow()

    /** videoId → absolute local path, null if failed */
    suspend fun download(trackId: String, videoId: String): String? = withContext(Dispatchers.IO) {
        if (_progress.value.containsKey(trackId)) {
            Log.d(TAG, "Already downloading $trackId")
            return@withContext null
        }
        _progress.value = _progress.value + (trackId to 0f)

        try {
            val url = streamResolver.getAudioUrl(videoId)
            if (url == null) {
                Log.e(TAG, "Could not resolve stream for $videoId")
                return@withContext null
            }

            val dir = context.getExternalFilesDir(Environment.DIRECTORY_MUSIC)
                ?: context.filesDir
            dir.mkdirs()
            val file = File(dir, "$trackId.m4a")

            val conn = URL(url).openConnection() as HttpURLConnection
            conn.connectTimeout = 10_000
            conn.readTimeout = 120_000
            conn.setRequestProperty("User-Agent", "Mozilla/5.0")
            conn.setRequestProperty("Referer", "https://www.youtube.com/")
            // YouTube signed URL'leri için cookie gerekiyor
            val cookie = CookieManager.getInstance().getCookie("https://www.youtube.com")
            if (!cookie.isNullOrBlank()) {
                conn.setRequestProperty("Cookie", cookie)
            }

            try {
                val total = conn.contentLengthLong
                var downloaded = 0L
                conn.inputStream.use { input ->
                    file.outputStream().use { output ->
                        val buf = ByteArray(512 * 1024) // 8KB → 512KB, ~64x hızlanma
                        while (true) {
                            val n = input.read(buf)
                            if (n < 0) break
                            output.write(buf, 0, n)
                            downloaded += n
                            if (total > 0) {
                                _progress.value = _progress.value +
                                    (trackId to (downloaded.toFloat() / total).coerceIn(0f, 0.99f))
                            }
                        }
                    }
                }
            } finally {
                conn.disconnect()
            }

            Log.d(TAG, "Downloaded $trackId → ${file.absolutePath}")
            file.absolutePath
        } catch (e: Exception) {
            Log.e(TAG, "Download failed for $trackId: ${e.message}")
            null
        } finally {
            _progress.value = _progress.value - trackId
        }
    }

    fun deleteLocal(trackId: String) {
        val dir = context.getExternalFilesDir(Environment.DIRECTORY_MUSIC) ?: context.filesDir
        File(dir, "$trackId.m4a").delete()
    }
}
