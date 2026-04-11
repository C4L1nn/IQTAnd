package com.iqtmusic.mobile.feature.search

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
import androidx.compose.material.icons.rounded.Favorite
import androidx.compose.material.icons.rounded.MusicNote
import androidx.compose.material.icons.rounded.PlayArrow
import androidx.compose.material.icons.rounded.PlaylistAdd
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
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
fun SearchScreen(
    uiState: MainUiState,
    onQueryChange: (String) -> Unit,
    onPlayTrack: (String) -> Unit,
    onAddAndPlayTrack: (Track) -> Unit,
    onToggleFavorite: (String) -> Unit,
    onAddTrackToPlaylist: (String, String) -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Text("Ara", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)

        OutlinedTextField(
            value = uiState.searchQuery,
            onValueChange = onQueryChange,
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
            label = { Text("Sarki, sanatci veya album") },
        )

        if (uiState.searchQuery.isBlank()) {
            Text(
                text = "Lokal kutuphanende veya YouTube Music'te ara.",
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        } else {
            LazyColumn(
                modifier = Modifier.fillMaxSize(),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                // Lokal sonuçlar
                if (uiState.searchResults.isNotEmpty()) {
                    item {
                        Text(
                            "Kutuphane",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.SemiBold,
                            color = MaterialTheme.colorScheme.primary,
                        )
                    }
                    items(uiState.searchResults, key = { "local-${it.id}" }) { track ->
                        LocalTrackRow(
                            track = track,
                            uiState = uiState,
                            onPlayTrack = onPlayTrack,
                            onToggleFavorite = onToggleFavorite,
                            onAddTrackToPlaylist = onAddTrackToPlaylist,
                        )
                    }
                }

                // YouTube Music sonuçlar
                item {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        Text(
                            "YouTube Music",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.SemiBold,
                            color = MaterialTheme.colorScheme.primary,
                        )
                        if (uiState.isRemoteSearching) {
                            CircularProgressIndicator(
                                modifier = Modifier.size(16.dp),
                                strokeWidth = 2.dp,
                            )
                        }
                    }
                }

                if (!uiState.isRemoteSearching && uiState.remoteSearchResults.isEmpty()) {
                    item {
                        Text(
                            "Sonuc bulunamadi. PC sunucusunun acik oldugunu ve ADB tunnel'in kurulu oldugunu kontrol et.",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }

                items(uiState.remoteSearchResults, key = { "remote-${it.id}" }) { track ->
                    RemoteTrackRow(
                        track = track,
                        onAddAndPlayTrack = onAddAndPlayTrack,
                    )
                }
            }
        }
    }
}

@Composable
private fun LocalTrackRow(
    track: Track,
    uiState: MainUiState,
    onPlayTrack: (String) -> Unit,
    onToggleFavorite: (String) -> Unit,
    onAddTrackToPlaylist: (String, String) -> Unit,
) {
    Card {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 12.dp, vertical = 10.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            TrackArtwork(coverUrl = track.coverUrl)
            Spacer(Modifier.width(12.dp))
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(2.dp),
            ) {
                Text(track.title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold, maxLines = 1)
                Text(
                    text = "${track.artist} · ${track.album}",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1,
                )
            }
            Row {
                AddToPlaylistButton(uiState = uiState, trackId = track.id, onAddTrackToPlaylist = onAddTrackToPlaylist)
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

@Composable
private fun RemoteTrackRow(
    track: Track,
    onAddAndPlayTrack: (Track) -> Unit,
) {
    Card {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 12.dp, vertical = 10.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            TrackArtwork(coverUrl = track.coverUrl)
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
            IconButton(onClick = { onAddAndPlayTrack(track) }) {
                Icon(Icons.Rounded.PlayArrow, contentDescription = "Ekle ve Cal")
            }
        }
    }
}

@Composable
private fun TrackArtwork(coverUrl: String?) {
    if (coverUrl != null) {
        AsyncImage(
            model = coverUrl,
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
}

@Composable
private fun AddToPlaylistButton(
    uiState: MainUiState,
    trackId: String,
    onAddTrackToPlaylist: (String, String) -> Unit,
) {
    var expanded by rememberSaveable(trackId) { mutableStateOf(false) }
    val playlists = uiState.snapshot.playlists

    Box {
        IconButton(onClick = { expanded = true }, enabled = playlists.isNotEmpty()) {
            Icon(Icons.Rounded.PlaylistAdd, contentDescription = "Listeye ekle")
        }
        DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            playlists.forEach { playlist ->
                val alreadyAdded = trackId in playlist.trackIds
                DropdownMenuItem(
                    text = { Text(if (alreadyAdded) "${playlist.name} (ekli)" else playlist.name) },
                    enabled = !alreadyAdded,
                    onClick = {
                        onAddTrackToPlaylist(playlist.id, trackId)
                        expanded = false
                    },
                )
            }
        }
    }
}
