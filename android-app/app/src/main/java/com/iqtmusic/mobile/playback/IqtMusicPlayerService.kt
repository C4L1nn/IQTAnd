package com.iqtmusic.mobile.playback

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Intent
import android.content.pm.ServiceInfo
import android.net.Uri
import android.os.Build
import android.util.Log
import androidx.media3.common.MediaItem
import androidx.media3.common.MediaMetadata
import androidx.media3.common.Player
import androidx.media3.common.util.UnstableApi
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.session.MediaSession
import androidx.media3.session.MediaSessionService
import com.iqtmusic.mobile.IqtMusicApp
import com.iqtmusic.mobile.data.model.LibrarySnapshot
import com.iqtmusic.mobile.data.model.RepeatMode
import com.iqtmusic.mobile.data.model.Track
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
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

    private lateinit var container: com.iqtmusic.mobile.AppContainer
    private var currentVideoId: String? = null
    private var resolveJob: Job? = null
    private var lastPrefetchSignature: String? = null

    override fun onCreate() {
        super.onCreate()
        container = (application as IqtMusicApp).container
        streamResolver = container.streamResolver

        val exo = ExoPlayer.Builder(this).build()
        exo.addListener(object : Player.Listener {
            override fun onPlaybackStateChanged(playbackState: Int) {
                // Sadece gercekten bir sarki calarken STATE_ENDED'e gececek durumda tetikle
                if (playbackState == Player.STATE_ENDED && currentVideoId != null) {
                    val snapshot = container.libraryRepository.snapshot.value
                    if (snapshot.repeatMode == RepeatMode.ONE) {
                        exo.seekTo(0)
                        exo.play()
                    } else {
                        scope.launch { container.libraryRepository.handlePlaybackEnded() }
                    }
                }
            }
        })
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

        // ExoPlayer pozisyonunu her 500ms'de container'a yaz
        scope.launch {
            while (isActive) {
                val exo = player
                if (exo != null) {
                    val pos = exo.currentPosition
                    val dur = exo.duration.takeIf { it > 0L } ?: 0L
                    container.playerProgress.value = PlayerProgress(pos, dur)
                }
                delay(500)
            }
        }

        // UI'dan gelen seek isteklerini uygula
        scope.launch {
            container.seekRequestFlow.collect { positionMs ->
                player?.seekTo(positionMs)
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
                exo.clearMediaItems()
                currentVideoId = null
                maybePrefetch(snapshot, currentVideoId = null)
            }

            videoId == currentVideoId -> {
                Log.d(TAG, "Same track, updating playWhenReady=${snapshot.isPlaying}")
                // STATE_ENDED'deyse (sarki bitti) tekrar calinmak isteniyor: seek(0) olmadan calmiyor
                if (snapshot.isPlaying && exo.playbackState == Player.STATE_ENDED) {
                    exo.seekTo(0)
                }
                exo.playWhenReady = snapshot.isPlaying
                maybePrefetch(snapshot, currentVideoId = videoId)
            }

            else -> {
                resolveJob?.cancel()
                val wantPlaying = snapshot.isPlaying

                // İndirilmiş dosya varsa stream resolve etme
                val localFile = track.localPath
                if (localFile != null) {
                    Log.d(TAG, "Playing local file for $videoId: $localFile")
                    currentVideoId = videoId
                    val mediaItem = buildMediaItem("file://$localFile", track)
                    exo.setMediaItem(mediaItem)
                    exo.prepare()
                    exo.playWhenReady = wantPlaying
                    maybePrefetch(snapshot, currentVideoId = videoId)
                    return
                }

                Log.d(TAG, "New track, resolving stream for videoId=$videoId")
                container.streamLoading.value = true
                resolveJob = scope.launch {
                    val url = streamResolver.getAudioUrl(videoId)
                    Log.d(TAG, "Stream URL for $videoId: ${if (url != null) "OK (${url.take(60)}...)" else "NULL"}")
                    if (url != null && isActive) {
                        currentVideoId = videoId
                        container.streamLoading.value = false
                        val mediaItem = buildMediaItem(url, track)
                        exo.setMediaItem(mediaItem)
                        exo.prepare()
                        exo.playWhenReady = wantPlaying
                        maybePrefetch(snapshot, currentVideoId = videoId)
                    } else if (isActive) {
                        Log.e(TAG, "Unable to resolve stream for $videoId")
                        container.streamLoading.value = false
                        container.streamErrorFlow.tryEmit("Şarkı yüklenemedi")
                        currentVideoId = null
                        exo.stop()
                        exo.clearMediaItems()
                    }
                }
            }
        }
    }

    private fun maybePrefetch(snapshot: LibrarySnapshot, currentVideoId: String?) {
        val candidates = buildPrefetchCandidates(snapshot, currentVideoId)
        val signature = candidates.joinToString("|")
        if (signature == lastPrefetchSignature) return
        lastPrefetchSignature = signature
        if (candidates.isEmpty()) return

        scope.launch(Dispatchers.IO) {
            runCatching {
                streamResolver.prefetchAudioUrls(candidates)
            }.onFailure { error ->
                Log.d(TAG, "Prefetch skipped: ${error.message}")
            }
        }
    }

    private fun buildPrefetchCandidates(
        snapshot: LibrarySnapshot,
        currentVideoId: String?,
    ): List<String> {
        val queueCandidates = if (currentVideoId != null && snapshot.queueTrackIds.isNotEmpty()) {
            val currentIndex = snapshot.queueTrackIds.indexOf(currentVideoId)
            if (currentIndex >= 0) {
                snapshot.queueTrackIds.drop(currentIndex + 1)
            } else {
                snapshot.queueTrackIds
            }
        } else {
            emptyList()
        }

        val fallbackCandidates = snapshot.tracks.mapNotNull { it.videoId }
        val merged = (queueCandidates + fallbackCandidates)
            .filterNot { it == currentVideoId }
            .distinct()

        return if (currentVideoId == null) {
            merged.take(3)
        } else {
            merged.take(2)
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
        promoteForeground()
        super.onStartCommand(intent, flags, startId)
        return START_STICKY
    }

    private fun promoteForeground() {
        val channelId = "iqtmusic_bg"
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val nm = getSystemService(NotificationManager::class.java)
            if (nm.getNotificationChannel(channelId) == null) {
                nm.createNotificationChannel(
                    NotificationChannel(channelId, "IQTMusic", NotificationManager.IMPORTANCE_LOW).apply {
                        setSound(null, null)
                        setShowBadge(false)
                    },
                )
            }
            val notification = Notification.Builder(this, channelId)
                .setSmallIcon(android.R.drawable.ic_media_play)
                .setContentTitle("IQTMusic")
                .setContentText("Calma hazir")
                .build()
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                startForeground(1001, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PLAYBACK)
            } else {
                startForeground(1001, notification)
            }
        }
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
