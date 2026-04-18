package com.iqtmusic.mobile.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Scaffold
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.iqtmusic.mobile.MainUiState
import com.iqtmusic.mobile.data.model.Track
import com.iqtmusic.mobile.navigation.IqtMusicDestination
import com.iqtmusic.mobile.navigation.IqtMusicNavGraph
import com.iqtmusic.mobile.playback.PlayerProgress
import com.iqtmusic.mobile.ui.components.IqtBackdrop
import com.iqtmusic.mobile.ui.components.IqtNavItemModel
import com.iqtmusic.mobile.ui.components.IqtNavigationDock
import com.iqtmusic.mobile.ui.components.IqtNowPlayingCard

@Composable
@Suppress("LongParameterList")
fun IqtMusicRoot(
    modifier: Modifier = Modifier,
    uiState: MainUiState,
    playerProgress: PlayerProgress = PlayerProgress(),
    onSearchQueryChange: (String) -> Unit,
    onToggleFavorite: (String) -> Unit,
    onPlayTrack: (String) -> Unit,
    onAddAndPlayTrack: (Track) -> Unit,
    onPlayPlaylist: (String, String?) -> Unit,
    onTogglePlayback: () -> Unit,
    onCreatePlaylist: (String) -> Unit,
    onAddTrackToPlaylist: (String, String) -> Unit,
    onRemoveTrackFromPlaylist: (String, String) -> Unit,
    onStartCollabHost: () -> Unit,
    onSaveServerUrl: (String) -> Unit,
    onCheckConnection: () -> Unit,
    onSkipPrevious: () -> Unit,
    onSkipNext: () -> Unit,
    onRemoveTrack: (String) -> Unit,
    onToggleShuffle: () -> Unit,
    onCycleRepeatMode: () -> Unit,
    onSeek: (Float) -> Unit = {},
    onDownloadTrack: (String) -> Unit = {},
    onDeleteDownload: (String) -> Unit = {},
    viewModel: com.iqtmusic.mobile.MainViewModel? = null,
) {
    val navController = rememberNavController()
    val navBackStackEntry by navController.currentBackStackEntryAsState()
    val currentRoute = navBackStackEntry?.destination?.route
    val isPlayerScreen = currentRoute == IqtMusicDestination.Player.route
    val selectedRoute = when {
        currentRoute?.startsWith("playlist/") == true -> IqtMusicDestination.Playlists.route
        currentRoute?.startsWith("artist/") == true -> null
        else -> currentRoute
    }
    val destinations = IqtMusicDestination.topLevel.map {
        IqtNavItemModel(
            route = it.route,
            label = it.label,
            icon = it.icon,
        )
    }
    val currentTrack = uiState.snapshot.tracks.find { it.id == uiState.snapshot.currentTrackId }
    val queue = uiState.snapshot.queueTrackIds
    val currentIdx = queue.indexOf(uiState.snapshot.currentTrackId)

    IqtBackdrop(modifier = modifier.fillMaxSize()) {
        Scaffold(
            modifier = Modifier.fillMaxSize(),
            containerColor = Color.Transparent,
            bottomBar = {
                if (isPlayerScreen) return@Scaffold
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .navigationBarsPadding(),
                    verticalArrangement = Arrangement.spacedBy(0.dp),
                ) {
                    if (currentTrack != null) {
                        IqtNowPlayingCard(
                            modifier = Modifier.padding(horizontal = 14.dp, vertical = 8.dp),
                            title = currentTrack.title,
                            subtitle = buildString {
                                append(currentTrack.artist)
                                append(" - ")
                                append(currentTrack.durationLabel)
                                if (uiState.queueTracks.size > 1) {
                                    append(" - ")
                                    append("${uiState.queueTracks.size} sarki sirada")
                                }
                            },
                            coverUrl = currentTrack.coverUrl,
                            isPlaying = uiState.snapshot.isPlaying,
                            hasPrevious = currentIdx > 0,
                            hasNext = currentIdx >= 0 && currentIdx < queue.lastIndex,
                            isLoading = uiState.isStreamLoading,
                            progress = playerProgress.fraction,
                            onSeek = onSeek,
                            onClick = {
                                navController.navigate(IqtMusicDestination.Player.route) {
                                    launchSingleTop = true
                                }
                            },
                            onTogglePlayback = onTogglePlayback,
                            onSkipPrevious = onSkipPrevious,
                            onSkipNext = onSkipNext,
                        )
                    }
                    IqtNavigationDock(
                        modifier = Modifier.fillMaxWidth(),
                        items = destinations,
                        selectedRoute = selectedRoute,
                        onNavigate = { route ->
                            if (selectedRoute != route) {
                                navController.navigate(route) {
                                    launchSingleTop = true
                                    restoreState = true
                                    popUpTo(navController.graph.startDestinationId) {
                                        saveState = true
                                    }
                                }
                            }
                        },
                    )
                }
            },
        ) { innerPadding ->
            IqtMusicNavGraph(
                navController = navController,
                modifier = Modifier
                    .fillMaxSize()
                    .padding(innerPadding),
                uiState = uiState,
                onSearchQueryChange = onSearchQueryChange,
                onToggleFavorite = onToggleFavorite,
                onPlayTrack = onPlayTrack,
                onAddAndPlayTrack = onAddAndPlayTrack,
                onPlayPlaylist = onPlayPlaylist,
                onCreatePlaylist = onCreatePlaylist,
                onAddTrackToPlaylist = onAddTrackToPlaylist,
                onRemoveTrackFromPlaylist = onRemoveTrackFromPlaylist,
                onStartCollabHost = onStartCollabHost,
                onSaveServerUrl = onSaveServerUrl,
                onCheckConnection = onCheckConnection,
                onRemoveTrack = onRemoveTrack,
                onTogglePlayback = onTogglePlayback,
                onSkipPrevious = onSkipPrevious,
                onSkipNext = onSkipNext,
                onToggleShuffle = onToggleShuffle,
                onCycleRepeatMode = onCycleRepeatMode,
                onDownloadTrack = onDownloadTrack,
                onDeleteDownload = onDeleteDownload,
                playerProgress = playerProgress,
                onSeekFromPlayer = onSeek,
                viewModel = viewModel,
            )
        }
    }
}
