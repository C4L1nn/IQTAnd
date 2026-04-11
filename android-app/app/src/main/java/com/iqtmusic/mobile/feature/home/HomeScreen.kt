package com.iqtmusic.mobile.feature.home

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.DownloadDone
import androidx.compose.material.icons.rounded.Favorite
import androidx.compose.material.icons.rounded.MusicNote

import androidx.compose.material.icons.rounded.PlayArrow
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Card
import androidx.compose.material3.ElevatedCard
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import com.iqtmusic.mobile.MainUiState
import com.iqtmusic.mobile.data.model.Track

@Composable
fun HomeScreen(
    uiState: MainUiState,
    onPlayTrack: (String) -> Unit,
    onToggleFavorite: (String) -> Unit,
) {
    val downloadedCount = uiState.snapshot.tracks.count { it.isDownloaded }

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = androidx.compose.foundation.layout.PaddingValues(20.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        item {
            ElevatedCard {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(20.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    Text("iqtMusic Android", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
                    Text(
                        text = "Desktop'teki playlist, favori, gecmis ve collab mantigini mobile uygun bir katmana tasiyoruz.",
                        style = MaterialTheme.typography.bodyLarge,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        AssistChip(
                            onClick = {},
                            label = { Text("${uiState.snapshot.playlists.size} liste") },
                            leadingIcon = { Icon(Icons.Rounded.Favorite, contentDescription = null) },
                        )
                        AssistChip(
                            onClick = {},
                            label = { Text("$downloadedCount indirilen") },
                            leadingIcon = { Icon(Icons.Rounded.DownloadDone, contentDescription = null) },
                        )
                    }
                }
            }
        }

        if (uiState.recentTracks.isNotEmpty()) {
            item { SectionTitle("Son calinanlar") }
            items(uiState.recentTracks, key = { "recent-${it.id}" }) { track ->
                TrackRow(track, onPlayTrack, onToggleFavorite)
            }
        }

        if (uiState.favoriteTracks.isNotEmpty()) {
            item { SectionTitle("Favoriler") }
            items(uiState.favoriteTracks.take(3), key = { "fav-${it.id}" }) { track ->
                TrackRow(track, onPlayTrack, onToggleFavorite)
            }
        }

        item { SectionTitle("Tum Sarkilar") }

        items(uiState.snapshot.tracks, key = { "all-${it.id}" }) { track ->
            TrackRow(track, onPlayTrack, onToggleFavorite)
        }
    }
}

@Composable
private fun SectionTitle(text: String) {
    Text(text, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
}

@Composable
private fun TrackRow(
    track: Track,
    onPlayTrack: (String) -> Unit,
    onToggleFavorite: (String) -> Unit,
) {
    Card {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 12.dp, vertical = 10.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            if (track.coverUrl != null) {
                AsyncImage(
                    model = track.coverUrl,
                    contentDescription = "Album kapaği",
                    modifier = Modifier
                        .size(48.dp)
                        .clip(RoundedCornerShape(6.dp)),
                    contentScale = ContentScale.Crop,
                )
            } else {
                Box(
                    modifier = Modifier
                        .size(48.dp)
                        .clip(RoundedCornerShape(6.dp)),
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(
                        Icons.Rounded.MusicNote,
                        contentDescription = null,
                        modifier = Modifier.size(24.dp),
                        tint = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
            Spacer(Modifier.width(12.dp))
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(2.dp),
            ) {
                Text(track.title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold, maxLines = 1)
                Text(
                    text = "${track.artist} · ${track.durationLabel}",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1,
                )
            }

            Row {
                IconButton(onClick = { onToggleFavorite(track.id) }) {
                    Icon(Icons.Rounded.Favorite, contentDescription = "Favori")
                }
                IconButton(onClick = { onPlayTrack(track.id) }) {
                    Icon(Icons.Rounded.PlayArrow, contentDescription = "Cal")
                }
            }
        }
    }
}
