package com.iqtmusic.mobile.feature.artist

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.ArrowBack
import androidx.compose.material.icons.rounded.Favorite
import androidx.compose.material.icons.rounded.FavoriteBorder
import androidx.compose.material.icons.rounded.PlayArrow
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.iqtmusic.mobile.MainUiState
import com.iqtmusic.mobile.ui.components.IqtEmptyState
import com.iqtmusic.mobile.ui.components.IqtRoundIconButton
import com.iqtmusic.mobile.ui.components.IqtScreenHeader
import com.iqtmusic.mobile.ui.components.IqtTrackRow

@Composable
fun ArtistScreen(
    uiState: MainUiState,
    artistName: String,
    onBack: () -> Unit,
    onPlayTrack: (String) -> Unit,
    onToggleFavorite: (String) -> Unit,
) {
    val tracks = uiState.snapshot.tracks.filter { it.artist == artistName }
    val currentTrackId = uiState.snapshot.currentTrackId

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
            }
        }

        item {
            IqtScreenHeader(
                kicker = "sanatci",
                title = artistName,
            )
        }

        if (tracks.isEmpty()) {
            item {
                IqtEmptyState(
                    title = "Sarki yok",
                    body = "Bu sanatcinin sarkilari kutuphanende gorunur.",
                )
            }
        } else {
            items(tracks, key = { it.id }) { track ->
                IqtTrackRow(
                    title = track.title,
                    subtitle = "${track.album.ifBlank { "Album bilgisi yok" }} - ${track.durationLabel}",
                    coverUrl = track.coverUrl,
                    badge = track.durationLabel,
                    isActive = track.id == currentTrackId,
                    onClick = { onPlayTrack(track.id) },
                    trailing = {
                        IqtRoundIconButton(
                            icon = if (track.isFavorite) Icons.Rounded.Favorite else Icons.Rounded.FavoriteBorder,
                            contentDescription = "Favori",
                            onClick = { onToggleFavorite(track.id) },
                            active = track.isFavorite,
                        )
                        IqtRoundIconButton(
                            icon = Icons.Rounded.PlayArrow,
                            contentDescription = "Cal",
                            onClick = { onPlayTrack(track.id) },
                            emphasize = true,
                        )
                    },
                )
            }
        }
    }
}
