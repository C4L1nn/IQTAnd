package com.iqtmusic.mobile.playback

import android.content.Intent
import android.net.Uri
import android.util.Log
import androidx.media3.common.MediaItem
import androidx.media3.common.MediaMetadata
import androidx.media3.common.util.UnstableApi
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.session.MediaSession
import androidx.media3.session.MediaSessionService
import com.iqtmusic.mobile.IqtMusicApp
import com.iqtmusic.mobile.data.model.LibrarySnapshot
import com.iqtmusic.mobile.data.model.Track
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

private const val TAG = "IqtMusicPlayer"

/**
 * Arka plan müzik servisi — MediaSessionService kullanır.
 *
 * - ExoPlayer üzerinde MediaSession kurar → lock screen kontrolleri + bildirim otomatik gelir
 * - Repository'deki snapshot'ı dinler; currentTrackId değişince stream URL çözer
 * - Track metadata'sını (başlık, sanatçı, kapak) MediaItem'e ekler → bildirimde görünür
 */
@UnstableApi
class IqtMusicPlayerService : MediaSessionService() {

    private var player: ExoPlayer? = null
    private var mediaSession: MediaSession? = null
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
    private lateinit var streamResolver: StreamResolver

    private var currentVideoId: String? = null
    private var resolveJob: Job? = null

    override fun onCreate() {
        super.onCreate()
        val container = (application as IqtMusicApp).container
        streamResolver = StreamResolver()

        val exo = ExoPlayer.Builder(this).build()
        player = exo

        mediaSession = MediaSession.Builder(this, exo)
            .setId("iqtmusic_session")
            .build()

        val repository = container.libraryRepository
        scope.launch {
            repository.snapshot.collect { snapshot ->
                handleSnapshot(snapshot)
            }
        }
    }

    override fun onGetSession(controllerInfo: MediaSession.ControllerInfo): MediaSession? = mediaSession

    private fun handleSnapshot(snapshot: LibrarySnapshot) {
        val exo = player ?: return
        val track = snapshot.tracks.find { it.id == snapshot.currentTrackId }
        val videoId = track?.videoId
        Log.d(TAG, "handleSnapshot: currentTrackId=${snapshot.currentTrackId} videoId=$videoId isPlaying=${snapshot.isPlaying}")

        when {
            videoId == null -> {
                resolveJob?.cancel()
                exo.stop()
                currentVideoId = null
            }

            videoId == currentVideoId -> {
                Log.d(TAG, "Same track, updating playWhenReady=${snapshot.isPlaying}")
                exo.playWhenReady = snapshot.isPlaying
            }

            else -> {
                resolveJob?.cancel()
                val wantPlaying = snapshot.isPlaying
                Log.d(TAG, "New track, resolving stream for videoId=$videoId")
                resolveJob = scope.launch {
                    val url = streamResolver.getAudioUrl(videoId)
                    Log.d(TAG, "Stream URL for $videoId: ${if (url != null) "OK (${url.take(60)}...)" else "NULL"}")
                    if (url != null && isActive) {
                        currentVideoId = videoId
                        val mediaItem = buildMediaItem(url, track)
                        exo.setMediaItem(mediaItem)
                        exo.prepare()
                        exo.playWhenReady = wantPlaying
                    }
                }
            }
        }
    }

    private fun buildMediaItem(url: String, track: Track): MediaItem {
        val metadata = MediaMetadata.Builder()
            .setTitle(track.title)
            .setArtist(track.artist)
            .setAlbumTitle(track.album)
            .apply {
                track.coverUrl?.let { setArtworkUri(Uri.parse(it)) }
            }
            .build()

        return MediaItem.Builder()
            .setUri(url)
            .setMediaMetadata(metadata)
            .build()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        super.onStartCommand(intent, flags, startId)
        return START_STICKY
    }

    override fun onDestroy() {
        scope.cancel()
        mediaSession?.run {
            player.release()
            release()
        }
        player = null
        mediaSession = null
        super.onDestroy()
    }
}
