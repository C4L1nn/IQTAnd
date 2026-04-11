package com.iqtmusic.mobile.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Pause
import androidx.compose.material.icons.rounded.PlayArrow
import androidx.compose.material3.Card
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.iqtmusic.mobile.MainUiState
import com.iqtmusic.mobile.data.model.Track
import com.iqtmusic.mobile.navigation.IqtMusicDestination
import com.iqtmusic.mobile.navigation.IqtMusicNavGraph

@Composable
@Suppress("LongParameterList")
fun IqtMusicRoot(
    modifier: Modifier = Modifier,
    uiState: MainUiState,
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
) {
    val navController = rememberNavController()
    val destinations = IqtMusicDestination.topLevel
    val navBackStackEntry by navController.currentBackStackEntryAsState()
    val currentRoute = navBackStackEntry?.destination?.route

    Scaffold(
        modifier = modifier,
        bottomBar = {
            Column {
                NowPlayingBar(
                    uiState = uiState,
                    onOpenCurrentTrack = {
                        uiState.snapshot.currentTrackId?.let(onPlayTrack)
                    },
                    onTogglePlayback = onTogglePlayback,
                )
                NavigationBar {
                    destinations.forEach { destination ->
                        NavigationBarItem(
                            selected = currentRoute == destination.route,
                            onClick = {
                                if (currentRoute != destination.route) {
                                    navController.navigate(destination.route) {
                                        launchSingleTop = true
                                        restoreState = true
                                        popUpTo(navController.graph.startDestinationId) {
                                            saveState = true
                                        }
                                    }
                                }
                            },
                            icon = { Icon(destination.icon, contentDescription = destination.label) },
                            label = { Text(destination.label) },
                        )
                    }
                }
            }
        },
    ) { innerPadding ->
        IqtMusicNavGraph(
            navController = navController,
            modifier = Modifier.padding(innerPadding),
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
        )
    }
}

@Composable
private fun NowPlayingBar(
    uiState: MainUiState,
    onOpenCurrentTrack: () -> Unit,
    onTogglePlayback: () -> Unit,
) {
    val currentTrack = uiState.snapshot.tracks.find { it.id == uiState.snapshot.currentTrackId } ?: return

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp, vertical = 8.dp)
            .clickable(onClick = onOpenCurrentTrack),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 14.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(2.dp),
            ) {
                Text(
                    text = currentTrack.title,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                )
                Text(
                    text = "${currentTrack.artist} - ${currentTrack.durationLabel} - ${uiState.queueTracks.size} kuyruk",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            IconButton(onClick = onTogglePlayback) {
                Icon(
                    imageVector = if (uiState.snapshot.isPlaying) Icons.Rounded.Pause else Icons.Rounded.PlayArrow,
                    contentDescription = if (uiState.snapshot.isPlaying) "Duraklat" else "Oynat",
                )
            }
        }
    }
}
