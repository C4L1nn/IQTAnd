package com.iqtmusic.mobile

import android.content.Intent
import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.viewModels
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.lifecycle.lifecycleScope
import com.iqtmusic.mobile.playback.IqtMusicPlayerService
import com.iqtmusic.mobile.ui.IqtMusicRoot
import com.iqtmusic.mobile.ui.theme.IqtMusicAndroidTheme
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {
    private val viewModel by viewModels<MainViewModel> {
        val container = (application as IqtMusicApp).container
        MainViewModel.Factory(container.libraryRepository, container.remoteApi, container)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        // Müzik servisini başlat.
        // MIUI / Android 12+ arka plan kısıtlaması: startService patlayabilir,
        // startForegroundService ile aşıyoruz; service onStartCommand'da foreground'a alıyor.
        try {
            startForegroundService(Intent(this, IqtMusicPlayerService::class.java))
        } catch (e: Exception) {
            android.util.Log.w("MainActivity", "Service start deferred: ${e.message}")
        }

        lifecycleScope.launch {
            viewModel.streamErrorFlow.collect { msg ->
                Toast.makeText(this@MainActivity, msg, Toast.LENGTH_SHORT).show()
            }
        }

        setContent {
            val uiState by viewModel.uiState.collectAsState()
            val playerProgress by viewModel.playerProgress.collectAsState()

            IqtMusicAndroidTheme {
                IqtMusicRoot(
                    modifier = Modifier,
                    uiState = uiState,
                    playerProgress = playerProgress,
                    onSearchQueryChange = viewModel::updateSearchQuery,
                    onToggleFavorite = viewModel::toggleFavorite,
                    onPlayTrack = viewModel::playTrack,
                    onAddAndPlayTrack = viewModel::addAndPlayTrack,
                    onPlayPlaylist = viewModel::playPlaylist,
                    onTogglePlayback = viewModel::togglePlayback,
                    onCreatePlaylist = viewModel::createPlaylist,
                    onAddTrackToPlaylist = viewModel::addTrackToPlaylist,
                    onRemoveTrackFromPlaylist = viewModel::removeTrackFromPlaylist,
                    onStartCollabHost = viewModel::startCollabHost,
                    onSaveServerUrl = viewModel::saveServerUrl,
                    onCheckConnection = viewModel::checkServerConnection,
                    onSkipPrevious = viewModel::skipPrevious,
                    onSkipNext = viewModel::skipNext,
                    onRemoveTrack = viewModel::removeTrack,
                    onToggleShuffle = viewModel::toggleShuffle,
                    onCycleRepeatMode = viewModel::cycleRepeatMode,
                    onSeek = viewModel::seekTo,
                    onDownloadTrack = viewModel::downloadTrack,
                    onDeleteDownload = viewModel::deleteDownload,
                    viewModel = viewModel,
                )
            }
        }
    }
}
