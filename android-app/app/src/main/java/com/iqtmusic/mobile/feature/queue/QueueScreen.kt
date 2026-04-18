package com.iqtmusic.mobile.feature.queue

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Lyrics
import androidx.compose.material.icons.rounded.PlayArrow
import androidx.compose.material.icons.rounded.Repeat
import androidx.compose.material.icons.rounded.RepeatOne
import androidx.compose.material.icons.rounded.Shuffle
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.iqtmusic.mobile.MainUiState
import com.iqtmusic.mobile.MainViewModel
import com.iqtmusic.mobile.data.model.RepeatMode
import com.iqtmusic.mobile.ui.components.IqtEmptyState
import com.iqtmusic.mobile.ui.components.IqtInfoPill
import com.iqtmusic.mobile.ui.components.IqtPanel
import com.iqtmusic.mobile.ui.components.IqtRoundIconButton
import com.iqtmusic.mobile.ui.components.IqtScreenHeader
import com.iqtmusic.mobile.ui.components.IqtSectionHeader
import com.iqtmusic.mobile.ui.components.IqtTrackRow
import com.iqtmusic.mobile.ui.theme.iqtPalette

@Composable
fun QueueScreen(
    uiState: MainUiState,
    onPlayTrack: (String) -> Unit,
    onToggleShuffle: () -> Unit,
    onCycleRepeatMode: () -> Unit,
    viewModel: MainViewModel? = null,
) {
    val snapshot = uiState.snapshot
    val queue = uiState.queueTracks
    val currentTrackId = snapshot.currentTrackId
    val lyricsState by (viewModel?.lyricsState?.collectAsState() ?: androidx.compose.runtime.remember {
        androidx.compose.runtime.mutableStateOf(false to null)
    })

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(horizontal = 20.dp, vertical = 20.dp),
        verticalArrangement = Arrangement.spacedBy(18.dp),
    ) {
        item {
            IqtScreenHeader(
                kicker = "oynatma",
                title = "Kuyruk",
            )
        }

        item {
            IqtPanel(
                modifier = Modifier.fillMaxWidth(),
                accentAmount = if (snapshot.shuffleEnabled || snapshot.repeatMode != RepeatMode.NONE) 0.12f else 0f,
            ) {
                IqtSectionHeader(
                    title = "Oynatma modu",
                    subtitle = "${queue.size} sarki",
                )
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    IqtRoundIconButton(
                        icon = Icons.Rounded.Shuffle,
                        contentDescription = "Karistir",
                        onClick = onToggleShuffle,
                        active = snapshot.shuffleEnabled,
                    )
                    IqtRoundIconButton(
                        icon = when (snapshot.repeatMode) {
                            RepeatMode.ONE -> Icons.Rounded.RepeatOne
                            else -> Icons.Rounded.Repeat
                        },
                        contentDescription = "Tekrar",
                        onClick = onCycleRepeatMode,
                        active = snapshot.repeatMode != RepeatMode.NONE,
                    )
                    IqtInfoPill(
                        label = when (snapshot.repeatMode) {
                            RepeatMode.NONE -> "Tekrar yok"
                            RepeatMode.ALL -> "Hepsini tekrar et"
                            RepeatMode.ONE -> "Bu sarkiyi tekrar et"
                        },
                        icon = Icons.Rounded.PlayArrow,
                        active = snapshot.repeatMode != RepeatMode.NONE,
                    )
                }
            }
        }

        if (currentTrackId != null) {
            item {
                IqtPanel(modifier = Modifier.fillMaxWidth()) {
                    val (isLoading, lyrics) = lyricsState
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        IqtRoundIconButton(
                            icon = Icons.Rounded.Lyrics,
                            contentDescription = "Sozleri getir",
                            onClick = { viewModel?.loadLyrics(currentTrackId) },
                            active = lyrics != null,
                        )
                        IqtSectionHeader(
                            title = "Sarki sozleri",
                            subtitle = if (lyrics != null) "Hazir" else "Getir",
                        )
                        if (isLoading) {
                            CircularProgressIndicator(
                                modifier = Modifier.size(20.dp),
                                strokeWidth = 2.dp,
                            )
                        }
                    }
                    if (lyrics != null) {
                        Text(
                            text = lyrics,
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.iqtPalette.textSecondary,
                        )
                    }
                }
            }
        }

        if (queue.isEmpty()) {
            item {
                IqtEmptyState(
                    title = "Kuyruk bos",
                    body = "Bir sarki cal.",
                )
            }
        } else {
            item {
                IqtSectionHeader(title = "Siradaki sarkilar")
            }
            items(queue, key = { "q-${it.id}" }) { track ->
                IqtTrackRow(
                    title = track.title,
                    subtitle = "${track.artist} - ${track.durationLabel}",
                    coverUrl = track.coverUrl,
                    badge = if (track.id == currentTrackId) "caliyor" else null,
                    isActive = track.id == currentTrackId,
                    onClick = { onPlayTrack(track.id) },
                )
            }
        }
    }
}
