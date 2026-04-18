package com.iqtmusic.mobile.navigation

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.BarChart
import androidx.compose.material.icons.rounded.Groups
import androidx.compose.material.icons.rounded.Home
import androidx.compose.material.icons.rounded.PlaylistPlay
import androidx.compose.material.icons.rounded.QueueMusic
import androidx.compose.material.icons.rounded.Search
import androidx.compose.material.icons.rounded.Settings
import androidx.compose.ui.graphics.vector.ImageVector

sealed class IqtMusicDestination(
    val route: String,
    val label: String,
    val icon: ImageVector,
) {
    data object Home : IqtMusicDestination("home", "Ana Sayfa", Icons.Rounded.Home)
    data object Search : IqtMusicDestination("search", "Ara", Icons.Rounded.Search)
    data object Playlists : IqtMusicDestination("playlists", "Listeler", Icons.Rounded.QueueMusic)
    data object PlaylistDetail : IqtMusicDestination("playlist/{playlistId}", "Liste", Icons.Rounded.QueueMusic) {
        fun createRoute(playlistId: String): String = "playlist/$playlistId"
        const val playlistIdArg = "playlistId"
    }
    data object Queue : IqtMusicDestination("queue", "Kuyruk", Icons.Rounded.PlaylistPlay)
    data object Collab : IqtMusicDestination("collab", "Beraber", Icons.Rounded.Groups)
    data object Stats : IqtMusicDestination("stats", "Istatistik", Icons.Rounded.BarChart)
    data object Settings : IqtMusicDestination("settings", "Ayarlar", Icons.Rounded.Settings)
    data object Artist : IqtMusicDestination("artist/{artistName}", "Sanatci", Icons.Rounded.Home) {
        fun createRoute(artistName: String): String =
            "artist/${java.net.URLEncoder.encode(artistName, "UTF-8")}"
        const val artistNameArg = "artistName"
    }
    data object Player : IqtMusicDestination("player", "Calici", Icons.Rounded.Home)

    companion object {
        val topLevel = listOf(Home, Search, Playlists, Stats, Settings)
    }
}
