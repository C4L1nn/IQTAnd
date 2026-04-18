package com.iqtmusic.mobile.feature.playlists

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.ArrowBack
import androidx.compose.material.icons.rounded.DeleteOutline
import androidx.compose.material.icons.rounded.PlayArrow
import androidx.compose.material.icons.rounded.QueueMusic
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.iqtmusic.mobile.MainUiState
import com.iqtmusic.mobile.ui.components.IqtEmptyState
import com.iqtmusic.mobile.ui.components.IqtInfoPill
import com.iqtmusic.mobile.ui.components.IqtPanel
import com.iqtmusic.mobile.ui.components.IqtRoundIconButton
import com.iqtmusic.mobile.ui.components.IqtScreenHeader
import com.iqtmusic.mobile.ui.components.IqtSectionHeader
import com.iqtmusic.mobile.ui.components.IqtTrackRow
import com.iqtmusic.mobile.ui.theme.iqtPalette

@Composable
fun PlaylistDetailScreen(
    uiState: MainUiState,
    playlistId: String,
    onBack: () -> Unit,
    onPlayPlaylist: (String, String?) -> Unit,
    onRemoveTrackFromPlaylist: (String, String) -> Unit,
) {
    val playlist = uiState.snapshot.playlists.find { it.id == playlistId }
    val tracks = playlist?.trackIds?.mapNotNull { id ->
        uiState.snapshot.tracks.find { it.id == id }
    }.orEmpty()

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(horizontal = 20.dp, vertical = 20.dp),
        verticalArrangement = Arrangement.spacedBy(18.dp),
    ) {
        item {
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                IqtRoundIconButton(
                    icon = Icons.Rounded.ArrowBack,
                    contentDescription = "Geri",
                    onClick = onBack,
                )
                IqtInfoPill(
                    label = "Liste",
                    icon = Icons.Rounded.QueueMusic,
                    active = true,
                )
            }
        }

        if (playlist == null) {
            item {
                IqtEmptyState(
                    title = "Liste bulunamadi",
                    body = "Geri donup listelerim ekranindan tekrar secmeyi deneyebilirsin.",
                )
            }
            return@LazyColumn
        }

        item {
            IqtScreenHeader(
                kicker = "liste",
                title = playlist.name,
            )
        }

        item {
            IqtPanel(
                modifier = Modifier.fillMaxWidth(),
                accentAmount = if (tracks.isNotEmpty()) 0.12f else 0f,
            ) {
                Text(
                    text = "${tracks.size} sarki",
                    style = MaterialTheme.typography.headlineMedium,
                    color = MaterialTheme.iqtPalette.textPrimary,
                )
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    IqtInfoPill(
                        label = "${tracks.size} sarki",
                        icon = Icons.Rounded.QueueMusic,
                    )
                    if (tracks.isNotEmpty()) {
                        IqtInfoPill(
                            label = tracks.first().artist,
                            icon = Icons.Rounded.PlayArrow,
                        )
                    }
                }
                IqtRoundIconButton(
                    icon = Icons.Rounded.PlayArrow,
                    contentDescription = "Tumunu cal",
                    onClick = { onPlayPlaylist(playlist.id, tracks.firstOrNull()?.id) },
                    emphasize = true,
                    enabled = tracks.isNotEmpty(),
                )
            }
        }

        if (tracks.isEmpty()) {
            item {
                IqtEmptyState(
                    title = "Liste bos",
                    body = "Aramadan sarki ekle.",
                )
            }
        } else {
            item {
                IqtSectionHeader(title = "Parcalar")
            }

            itemsIndexed(tracks, key = { _, track -> track.id }) { index, track ->
                IqtTrackRow(
                    title = track.title,
                    subtitle = "${track.artist} - ${track.durationLabel}",
                    coverUrl = track.coverUrl,
                    leadingLabel = "${index + 1}",
                    badge = track.durationLabel,
                    isActive = track.id == uiState.snapshot.currentTrackId,
                    onClick = { onPlayPlaylist(playlist.id, track.id) },
                    trailing = {
                        IqtRoundIconButton(
                            icon = Icons.Rounded.DeleteOutline,
                            contentDescription = "Listeden cikar",
                            onClick = { onRemoveTrackFromPlaylist(playlist.id, track.id) },
                        )
                        IqtRoundIconButton(
                            icon = Icons.Rounded.PlayArrow,
                            contentDescription = "Cal",
                            onClick = { onPlayPlaylist(playlist.id, track.id) },
                            emphasize = true,
                        )
                    },
                )
            }
        }
    }
}
