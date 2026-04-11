package com.iqtmusic.mobile

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.viewModels
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import com.iqtmusic.mobile.playback.IqtMusicPlayerService
import com.iqtmusic.mobile.ui.IqtMusicRoot
import com.iqtmusic.mobile.ui.theme.IqtMusicAndroidTheme

class MainActivity : ComponentActivity() {
    private val viewModel by viewModels<MainViewModel> {
        val container = (application as IqtMusicApp).container
        MainViewModel.Factory(container.libraryRepository, container.remoteApi, container)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        // Müzik servisini başlat — repository değişikliklerini dinleyip ExoPlayer'ı yönetir
        startService(Intent(this, IqtMusicPlayerService::class.java))

        setContent {
            val uiState by viewModel.uiState.collectAsState()

            IqtMusicAndroidTheme {
                IqtMusicRoot(
                    modifier = Modifier,
                    uiState = uiState,
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
                )
            }
        }
    }
}
