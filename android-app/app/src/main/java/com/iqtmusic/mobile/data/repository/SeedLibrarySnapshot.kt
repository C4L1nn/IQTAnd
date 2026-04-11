package com.iqtmusic.mobile.data.repository

import com.iqtmusic.mobile.data.model.CollabSessionState
import com.iqtmusic.mobile.data.model.LibrarySnapshot
import com.iqtmusic.mobile.data.model.ListeningStats
import com.iqtmusic.mobile.data.model.Playlist
import com.iqtmusic.mobile.data.model.Track

/**
 * Uygulama ilk kurulduğunda yüklenen örnek kütüphane.
 * videoId alanları YouTube video ID'leridir — istersen kendi seçtiklerini ekleyebilirsin.
 * YouTube URL'sinden ID almak için: youtube.com/watch?v=<BURASI>
 */
fun seedLibrarySnapshot(): LibrarySnapshot {
    val tracks = listOf(
        Track("trk-1", "Blinding Lights", "The Weeknd", "3:20", "After Hours",
            isFavorite = true, videoId = "4NRXx6U8ABQ"),
        Track("trk-2", "Shape of You", "Ed Sheeran", "3:53", "Divide",
            videoId = "JGwWNGJdvx8"),
        Track("trk-3", "Señorita", "Shawn Mendes & Camila Cabello", "3:11", "Señorita",
            isDownloaded = false, videoId = "Pkh8UtuejGw"),
        Track("trk-4", "Bad Guy", "Billie Eilish", "3:14", "When We All Fall Asleep",
            isFavorite = true, videoId = "DyDfgMOUjCI"),
        Track("trk-5", "Dance Monkey", "Tones and I", "3:29", "The Kids Are Coming",
            videoId = "q0hyYWKXF0Q"),
        Track("trk-6", "Watermelon Sugar", "Harry Styles", "2:54", "Fine Line",
            videoId = "E07s5ZYygMg"),
    )

    return LibrarySnapshot(
        tracks = tracks,
        playlists = listOf(
            Playlist("pl-1", "Pop Hits", listOf("trk-1", "trk-4", "trk-6")),
            Playlist("pl-2", "Chill Vibes", listOf("trk-2", "trk-3", "trk-5")),
        ),
        favoriteTrackIds = tracks.filter { it.isFavorite }.map { it.id },
        recentTrackIds = emptyList(),
        queueTrackIds = emptyList(),
        stats = ListeningStats(0, 0, 0, "-"),
        collab = CollabSessionState(false, "Hazir", null, 1, "Bagli degil"),
        currentTrackId = null,
        isPlaying = false,
    )
}

