package com.iqtmusic.mobile

import android.content.Context
import com.iqtmusic.mobile.data.remote.RemoteApi
import com.iqtmusic.mobile.data.repository.LibraryRepository
import com.iqtmusic.mobile.data.repository.PersistentLibraryRepository

class AppContainer(private val context: Context) {
    private val prefs = context.getSharedPreferences("iqtmusic_settings", Context.MODE_PRIVATE)

    val libraryRepository: LibraryRepository = PersistentLibraryRepository(context.applicationContext)
    val remoteApi: RemoteApi = RemoteApi { getServerUrl() }

    fun getServerUrl(): String = prefs.getString("server_url", "").orEmpty().trim()
    fun setServerUrl(url: String) { prefs.edit().putString("server_url", url.trim()).apply() }
}
