package com.iqtmusic.mobile.playback

import android.annotation.SuppressLint
import android.content.Context
import android.util.Log
import android.webkit.CookieManager
import android.webkit.JavascriptInterface
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.webkit.WebViewCompat
import androidx.webkit.WebViewFeature
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.launch
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import kotlin.coroutines.resume

/**
 * Once stream_server.py uzerinden /stream endpoint'ini dener.
 * Sunucu kullanilamiyorsa cihazdaki WebView interception fallback'ine gecer.
 * Basit bir memory cache ve request dedup ile ilk acilisi haric sonraki calislari hizlandirir.
 */
class StreamResolver(
    private val context: Context,
    private val getServerUrl: () -> String = { "" },
) {
    private val json = Json { ignoreUnknownKeys = true }
    private val cacheLock = Any()
    private val urlCache = LinkedHashMap<String, CachedUrl>()
    private val pendingRequests = mutableMapOf<String, CompletableDeferred<String?>>()

    suspend fun getAudioUrl(videoId: String): String? =
        resolveAudioUrl(videoId, allowFallback = true)

    suspend fun prefetchAudioUrls(videoIds: List<String>, limit: Int = 3) {
        val candidates = videoIds
            .asSequence()
            .map { it.trim() }
            .filter { it.isNotEmpty() }
            .distinct()
            .take(limit)
            .toList()
        if (candidates.isEmpty()) return

        scheduleServerPrefetch(candidates)

        coroutineScope {
            candidates.forEach { videoId ->
                launch {
                    runCatching {
                        resolveAudioUrl(videoId, allowFallback = false)
                    }
                }
            }
        }
    }

    private suspend fun resolveAudioUrl(videoId: String, allowFallback: Boolean): String? {
        getCachedUrl(videoId)?.let { return it }

        val (owner, request) = synchronized(cacheLock) {
            getCachedUrlLocked(videoId)?.let { cached ->
                return@synchronized false to CompletableDeferred<String?>().apply { complete(cached) }
            }
            pendingRequests[videoId]?.let { existing ->
                return@synchronized false to existing
            }
            val created = CompletableDeferred<String?>()
            pendingRequests[videoId] = created
            true to created
        }

        if (!owner) {
            return request.await()
        }

        return try {
            Log.d(TAG, "Resolving: $videoId")

            val resolved = resolveFromServer(videoId) ?: if (allowFallback) {
                Log.w(TAG, "Server stream unavailable, falling back to WebView for $videoId")
                withTimeoutOrNull(40_000) { intercept(videoId) }
            } else {
                null
            }

            if (resolved != null) {
                putCachedUrl(videoId, resolved)
                Log.d(TAG, "Resolved OK: ${resolved.take(100)}...")
            } else {
                Log.e(TAG, "Failed to resolve: $videoId")
            }
            request.complete(resolved)
            resolved
        } catch (error: Exception) {
            request.completeExceptionally(error)
            throw error
        } finally {
            synchronized(cacheLock) {
                pendingRequests.remove(videoId)
            }
        }
    }

    private suspend fun scheduleServerPrefetch(videoIds: List<String>) =
        withContext(Dispatchers.IO) {
            val serverUrl = getServerUrl().trim()
            if (serverUrl.isBlank() || videoIds.isEmpty()) return@withContext

            runCatching {
                val query = videoIds.joinToString("&") { videoId ->
                    "videoId=${URLEncoder.encode(videoId, "UTF-8")}"
                }
                val connection = URL("$serverUrl/prefetch?$query").openConnection() as HttpURLConnection
                connection.connectTimeout = 3_000
                connection.readTimeout = 5_000
                try {
                    connection.responseCode
                } finally {
                    connection.disconnect()
                }
            }.onFailure { error ->
                Log.d(TAG, "Server prefetch skipped: ${error.message}")
            }
        }

    private suspend fun resolveFromServer(videoId: String): String? =
        withContext(Dispatchers.IO) {
            val serverUrl = getServerUrl().trim()
            if (serverUrl.isBlank()) return@withContext null

            runCatching {
                val encodedVideoId = URLEncoder.encode(videoId, "UTF-8")
                val connection = URL("$serverUrl/stream?videoId=$encodedVideoId")
                    .openConnection() as HttpURLConnection
                connection.connectTimeout = 5_000
                connection.readTimeout = 60_000

                try {
                    if (connection.responseCode != 200) {
                        val errorBody = connection.errorStream
                            ?.bufferedReader()
                            ?.use { it.readText() }
                            .orEmpty()
                        Log.w(
                            TAG,
                            "Stream HTTP ${connection.responseCode} for $videoId: ${errorBody.take(120)}",
                        )
                        return@runCatching null
                    }

                    val body = connection.inputStream.bufferedReader().use { it.readText() }
                    json.decodeFromString<StreamResponse>(body).url.takeIf { it.isNotBlank() }
                } finally {
                    connection.disconnect()
                }
            }.getOrElse { error ->
                Log.e(TAG, "Server stream error for $videoId: ${error.message}")
                null
            }
        }

    @SuppressLint("SetJavaScriptEnabled", "RequiresFeature")
    private suspend fun intercept(videoId: String): String? =
        withContext(Dispatchers.Main) {
            suspendCancellableCoroutine { cont ->
                val webView = WebView(context)
                var delivered = false

                fun deliver(result: String?) {
                    if (!delivered) {
                        delivered = true
                        webView.stopLoading()
                        webView.destroy()
                        cont.resume(result)
                    }
                }

                // JavaScript köprüsü — JS kodundan URL'yi al
                webView.addJavascriptInterface(object {
                    @JavascriptInterface
                    fun onUrl(url: String) {
                        if (url.isBlank()) return
                        val clean = stripRange(url)
                        Log.d(TAG, "JS intercept: ${clean.take(100)}")
                        deliver(clean)
                    }
                }, "AndroidBridge")

                webView.settings.apply {
                    javaScriptEnabled = true
                    domStorageEnabled = true
                    mediaPlaybackRequiresUserGesture = false
                }
                CookieManager.getInstance().apply {
                    setAcceptCookie(true)
                    setAcceptThirdPartyCookies(webView, true)
                }

                // XHR/fetch'i sayfa script'lerinden ÖNCE yakala
                if (WebViewFeature.isFeatureSupported(WebViewFeature.DOCUMENT_START_SCRIPT)) {
                    WebViewCompat.addDocumentStartJavaScript(webView, XHR_INTERCEPT_JS, setOf("*"))
                }

                webView.webViewClient = object : WebViewClient() {
                    override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest) = false

                    override fun onPageFinished(view: WebView, url: String) {
                        // Fallback: autoplay tetikle, sayfa scriptleri zaten interceptor'ı kurdu
                        view.evaluateJavascript(AUTO_PLAY_JS, null)
                    }
                }

                cont.invokeOnCancellation { deliver(null) }
                webView.loadUrl("https://www.youtube.com/watch?v=$videoId&hl=en")
            }
        }

    private fun getCachedUrl(videoId: String): String? =
        synchronized(cacheLock) { getCachedUrlLocked(videoId) }

    private fun getCachedUrlLocked(videoId: String): String? {
        val cached = urlCache[videoId] ?: return null
        if ((System.currentTimeMillis() - cached.savedAtMs) > URL_CACHE_TTL_MS) {
            urlCache.remove(videoId)
            return null
        }
        return cached.url
    }

    private fun putCachedUrl(videoId: String, url: String) {
        synchronized(cacheLock) {
            urlCache[videoId] = CachedUrl(url = url, savedAtMs = System.currentTimeMillis())
            while (urlCache.size > MAX_CACHE_SIZE) {
                val oldestKey = urlCache.entries.firstOrNull()?.key ?: break
                urlCache.remove(oldestKey)
            }
        }
    }

    private companion object {
        const val TAG = "StreamResolver"
        const val URL_CACHE_TTL_MS = 10 * 60 * 1000L
        const val MAX_CACHE_SIZE = 48

        private val AUDIO_ITAGS = setOf("140", "141", "249", "250", "251", "256", "258")

        fun isAudioItag(url: String): Boolean =
            AUDIO_ITAGS.any { url.contains("itag=$it&") || url.contains("itag=$it") }

        fun stripRange(url: String): String =
            url.replace(Regex("[?&]range=[0-9]+-[0-9]+"), "")
                .trimEnd('?', '&')

        // Sayfa yüklenmeden önce enjekte edilir — XHR ve fetch'i yakalar
        val XHR_INTERCEPT_JS = """
            (function() {
                var AUDIO_ITAGS = /itag=(140|141|249|250|251|256|258)[^0-9]/;
                function isAudio(url) { return url && url.indexOf('googlevideo.com') !== -1 && AUDIO_ITAGS.test(url + '&'); }
                function notify(url) { try { AndroidBridge.onUrl(url); } catch(e) {} }

                // XHR intercept
                var _open = XMLHttpRequest.prototype.open;
                XMLHttpRequest.prototype.open = function(m, url) {
                    if (isAudio(url)) notify(url);
                    return _open.apply(this, arguments);
                };

                // fetch intercept
                var _fetch = window.fetch;
                window.fetch = function(input, opts) {
                    var url = (typeof input === 'string') ? input : (input && input.url) || '';
                    if (isAudio(url)) notify(url);
                    return _fetch.apply(this, arguments);
                };
            })();
        """.trimIndent()

        val AUTO_PLAY_JS = """
            (function() {
                try {
                    var v = document.querySelector('video');
                    if (v) { v.muted = true; v.volume = 0; v.play(); }
                } catch(e) {}
            })();
        """.trimIndent()
    }
}

private data class CachedUrl(
    val url: String,
    val savedAtMs: Long,
)

@Serializable
private data class StreamResponse(
    val url: String = "",
)
