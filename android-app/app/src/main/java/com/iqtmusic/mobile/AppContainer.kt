package com.iqtmusic.mobile

import android.content.Context
import com.iqtmusic.mobile.data.remote.LyricsRepository
import com.iqtmusic.mobile.data.remote.RemoteApi
import com.iqtmusic.mobile.data.repository.LibraryRepository
import com.iqtmusic.mobile.data.repository.PersistentLibraryRepository
import com.iqtmusic.mobile.playback.DownloadManager
import com.iqtmusic.mobile.playback.PlayerProgress
import com.iqtmusic.mobile.playback.StreamResolver
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow

class AppContainer(private val context: Context) {
    private val prefs = context.getSharedPreferences("iqtmusic_settings", Context.MODE_PRIVATE)

    val libraryRepository: LibraryRepository = PersistentLibraryRepository(context.applicationContext)
    val remoteApi: RemoteApi = RemoteApi { getServerUrl() }

    val streamResolver = StreamResolver(context.applicationContext) { getServerUrl() }
    val downloadManager = DownloadManager(context.applicationContext, streamResolver)
    val lyricsRepository = LyricsRepository()

    /** Service tarafından set edilir; ViewModel UI'a yansıtır. */
    val streamLoading = MutableStateFlow(false)

    /** Stream çözülemediyinde tek seferlik hata eventi. */
    val streamErrorFlow = MutableSharedFlow<String>(replay = 0, extraBufferCapacity = 1)

    /** ExoPlayer'dan her 500ms'de güncellenen pozisyon/süre. */
    val playerProgress = MutableStateFlow(PlayerProgress())

    /** UI'dan gelen seek isteği (ms cinsinden pozisyon). Service dinler. */
    val seekRequestFlow = MutableSharedFlow<Long>(extraBufferCapacity = 1)

    fun getServerUrl(): String = normalizeServerUrl(
        prefs.getString("server_url", "http://localhost:5001").orEmpty(),
    )

    fun setServerUrl(url: String) {
        prefs.edit().putString("server_url", normalizeServerUrl(url)).apply()
    }

    private fun normalizeServerUrl(url: String): String {
        val trimmed = url.trim().trimEnd('/')
        if (trimmed.isBlank()) return ""
        return if (trimmed.startsWith("http://") || trimmed.startsWith("https://")) {
            trimmed
        } else {
            "http://$trimmed"
        }
    }
}
