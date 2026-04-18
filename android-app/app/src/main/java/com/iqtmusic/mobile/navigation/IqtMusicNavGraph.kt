package com.iqtmusic.mobile.navigation

import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.navigation.NavType
import androidx.navigation.NavHostController
import androidx.navigation.navArgument
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import com.iqtmusic.mobile.MainUiState
import com.iqtmusic.mobile.feature.artist.ArtistScreen
import com.iqtmusic.mobile.feature.collab.CollabScreen
import com.iqtmusic.mobile.feature.home.HomeScreen
import com.iqtmusic.mobile.feature.playlists.PlaylistDetailScreen
import com.iqtmusic.mobile.feature.playlists.PlaylistsScreen
import com.iqtmusic.mobile.data.model.Track
import com.iqtmusic.mobile.feature.player.PlayerScreen
import com.iqtmusic.mobile.feature.queue.QueueScreen
import com.iqtmusic.mobile.feature.search.SearchScreen
import com.iqtmusic.mobile.feature.settings.SettingsScreen
import com.iqtmusic.mobile.feature.stats.StatsScreen
import com.iqtmusic.mobile.playback.PlayerProgress

@Composable
@Suppress("LongParameterList")
fun IqtMusicNavGraph(
    navController: NavHostController,
    modifier: Modifier,
    uiState: MainUiState,
    onSearchQueryChange: (String) -> Unit,
    onToggleFavorite: (String) -> Unit,
    onPlayTrack: (String) -> Unit,
    onAddAndPlayTrack: (Track) -> Unit,
    onPlayPlaylist: (String, String?) -> Unit,
    onCreatePlaylist: (String) -> Unit,
    onAddTrackToPlaylist: (String, String) -> Unit,
    onRemoveTrackFromPlaylist: (String, String) -> Unit,
    onStartCollabHost: () -> Unit,
    onSaveServerUrl: (String) -> Unit,
    onCheckConnection: () -> Unit,
    onRemoveTrack: (String) -> Unit,
    onTogglePlayback: () -> Unit = {},
    onSkipPrevious: () -> Unit = {},
    onSkipNext: () -> Unit = {},
    onToggleShuffle: () -> Unit,
    onCycleRepeatMode: () -> Unit,
    onDownloadTrack: (String) -> Unit = {},
    onDeleteDownload: (String) -> Unit = {},
    playerProgress: PlayerProgress = PlayerProgress(),
    onSeekFromPlayer: (Float) -> Unit = {},
    viewModel: com.iqtmusic.mobile.MainViewModel? = null,
) {
    NavHost(
        navController = navController,
        startDestination = IqtMusicDestination.Home.route,
        modifier = modifier,
    ) {
        composable(IqtMusicDestination.Home.route) {
            HomeScreen(
                uiState = uiState,
                onPlayTrack = onPlayTrack,
                onToggleFavorite = onToggleFavorite,
                onRemoveTrack = onRemoveTrack,
                onDownloadTrack = onDownloadTrack,
                onDeleteDownload = onDeleteDownload,
                onOpenArtist = { artistName ->
                    navController.navigate(IqtMusicDestination.Artist.createRoute(artistName))
                },
            )
        }
        composable(IqtMusicDestination.Search.route) {
            SearchScreen(
                uiState = uiState,
                onQueryChange = onSearchQueryChange,
                onPlayTrack = onPlayTrack,
                onAddAndPlayTrack = onAddAndPlayTrack,
                onToggleFavorite = onToggleFavorite,
                onAddTrackToPlaylist = onAddTrackToPlaylist,
            )
        }
        composable(IqtMusicDestination.Playlists.route) {
            PlaylistsScreen(
                uiState = uiState,
                onCreatePlaylist = onCreatePlaylist,
                onPlayPlaylist = onPlayPlaylist,
                onOpenPlaylist = { playlistId ->
                    navController.navigate(IqtMusicDestination.PlaylistDetail.createRoute(playlistId))
                },
            )
        }
        composable(
            route = IqtMusicDestination.PlaylistDetail.route,
            arguments = listOf(
                navArgument(IqtMusicDestination.PlaylistDetail.playlistIdArg) {
                    type = NavType.StringType
                },
            ),
        ) { backStackEntry ->
            val playlistId = backStackEntry.arguments?.getString(IqtMusicDestination.PlaylistDetail.playlistIdArg).orEmpty()
            PlaylistDetailScreen(
                uiState = uiState,
                playlistId = playlistId,
                onBack = navController::popBackStack,
                onPlayPlaylist = onPlayPlaylist,
                onRemoveTrackFromPlaylist = onRemoveTrackFromPlaylist,
            )
        }
        composable(IqtMusicDestination.Queue.route) {
            QueueScreen(
                uiState = uiState,
                onPlayTrack = onPlayTrack,
                onToggleShuffle = onToggleShuffle,
                onCycleRepeatMode = onCycleRepeatMode,
                viewModel = viewModel,
            )
        }
        composable(IqtMusicDestination.Collab.route) {
            CollabScreen(uiState, onStartCollabHost)
        }
        composable(IqtMusicDestination.Stats.route) {
            StatsScreen(uiState)
        }
        composable(IqtMusicDestination.Settings.route) {
            SettingsScreen(
                uiState = uiState,
                onSaveServerUrl = onSaveServerUrl,
                onCheckConnection = onCheckConnection,
            )
        }
        composable(IqtMusicDestination.Player.route) {
            PlayerScreen(
                uiState = uiState,
                playerProgress = playerProgress,
                onBack = navController::popBackStack,
                onTogglePlayback = onTogglePlayback,
                onSkipPrevious = onSkipPrevious,
                onSkipNext = onSkipNext,
                onSeek = onSeekFromPlayer,
                onToggleShuffle = onToggleShuffle,
                onCycleRepeatMode = onCycleRepeatMode,
                onOpenQueue = {
                    navController.navigate(IqtMusicDestination.Queue.route) {
                        launchSingleTop = true
                    }
                },
            )
        }
        composable(
            route = IqtMusicDestination.Artist.route,
            arguments = listOf(
                navArgument(IqtMusicDestination.Artist.artistNameArg) {
                    type = NavType.StringType
                },
            ),
        ) { backStackEntry ->
            val encoded = backStackEntry.arguments?.getString(IqtMusicDestination.Artist.artistNameArg).orEmpty()
            val artistName = java.net.URLDecoder.decode(encoded, "UTF-8")
            ArtistScreen(
                uiState = uiState,
                artistName = artistName,
                onBack = navController::popBackStack,
                onPlayTrack = onPlayTrack,
                onToggleFavorite = onToggleFavorite,
            )
        }
    }
}
