package com.iqtmusic.mobile.feature.home

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Delete
import androidx.compose.material.icons.rounded.Download
import androidx.compose.material.icons.rounded.DownloadDone
import androidx.compose.material.icons.rounded.Favorite
import androidx.compose.material.icons.rounded.FavoriteBorder
import androidx.compose.material.icons.rounded.MoreVert
import androidx.compose.material.icons.rounded.PlayArrow
import androidx.compose.material.icons.rounded.QueueMusic
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.iqtmusic.mobile.MainUiState
import com.iqtmusic.mobile.data.model.Track
import com.iqtmusic.mobile.ui.components.IqtEmptyState
import com.iqtmusic.mobile.ui.components.IqtInfoPill
import com.iqtmusic.mobile.ui.components.IqtRoundIconButton
import com.iqtmusic.mobile.ui.components.IqtScreenHeader
import com.iqtmusic.mobile.ui.components.IqtSectionHeader
import com.iqtmusic.mobile.ui.components.IqtTrackRow

@Composable
fun HomeScreen(
    uiState: MainUiState,
    onPlayTrack: (String) -> Unit,
    onToggleFavorite: (String) -> Unit,
    onRemoveTrack: (String) -> Unit,
    onDownloadTrack: (String) -> Unit = {},
    onDeleteDownload: (String) -> Unit = {},
    onOpenArtist: (String) -> Unit = {},
) {
    val downloadedCount = uiState.snapshot.tracks.count { it.isDownloaded }
    val currentTrackId = uiState.snapshot.currentTrackId
    val hasLibrary = uiState.snapshot.tracks.isNotEmpty()

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(horizontal = 20.dp, vertical = 20.dp),
        verticalArrangement = Arrangement.spacedBy(18.dp),
    ) {
        item {
            IqtScreenHeader(
                kicker = "IQTMusic",
                title = "Ana sayfa",
            )
        }

        item {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                IqtInfoPill(
                    label = "${uiState.snapshot.playlists.size} liste",
                    icon = Icons.Rounded.QueueMusic,
                    active = uiState.snapshot.playlists.isNotEmpty(),
                )
                IqtInfoPill(
                    label = "$downloadedCount indirilen",
                    icon = Icons.Rounded.DownloadDone,
                    active = downloadedCount > 0,
                )
                IqtInfoPill(
                    label = "${uiState.favoriteTracks.size} favori",
                    icon = Icons.Rounded.Favorite,
                    active = uiState.favoriteTracks.isNotEmpty(),
                )
            }
        }

        if (!hasLibrary) {
            item {
                IqtEmptyState(
                    title = "Kutuphane bos",
                    body = "Ara ekranindan sarki ekle.",
                )
            }
        } else {
            if (uiState.recentTracks.isNotEmpty()) {
                item {
                    IqtSectionHeader(title = "Son calinanlar")
                }
                items(uiState.recentTracks, key = { "recent-${it.id}" }) { track ->
                    HomeTrackRow(
                        track = track,
                        isActive = track.id == currentTrackId,
                        downloadingProgress = uiState.downloadProgress[track.id],
                        onPlayTrack = onPlayTrack,
                        onToggleFavorite = onToggleFavorite,
                        onRemoveTrack = onRemoveTrack,
                        onDownloadTrack = onDownloadTrack,
                        onDeleteDownload = onDeleteDownload,
                        onOpenArtist = onOpenArtist,
                    )
                }
            }

            if (uiState.favoriteTracks.isNotEmpty()) {
                item {
                    IqtSectionHeader(title = "Favoriler")
                }
                items(uiState.favoriteTracks.take(4), key = { "favorite-${it.id}" }) { track ->
                    HomeTrackRow(
                        track = track,
                        isActive = track.id == currentTrackId,
                        downloadingProgress = uiState.downloadProgress[track.id],
                        onPlayTrack = onPlayTrack,
                        onToggleFavorite = onToggleFavorite,
                        onRemoveTrack = onRemoveTrack,
                        onDownloadTrack = onDownloadTrack,
                        onDeleteDownload = onDeleteDownload,
                        onOpenArtist = onOpenArtist,
                    )
                }
            }

        }
    }
}

@Composable
private fun HomeTrackRow(
    track: Track,
    isActive: Boolean,
    downloadingProgress: Float?,
    onPlayTrack: (String) -> Unit,
    onToggleFavorite: (String) -> Unit,
    onRemoveTrack: (String) -> Unit,
    onDownloadTrack: (String) -> Unit,
    onDeleteDownload: (String) -> Unit,
    onOpenArtist: (String) -> Unit,
) {
    val subtitle = buildString {
        append(track.artist)
        append(" - ")
        append(track.album.ifBlank { track.durationLabel })
    }

    var menuExpanded by remember { mutableStateOf(false) }

    IqtTrackRow(
        title = track.title,
        subtitle = subtitle,
        onSubtitleClick = if (track.artist.isNotBlank()) {
            { onOpenArtist(track.artist) }
        } else null,
        coverUrl = track.coverUrl,
        isActive = isActive,
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
            Box {
                IqtRoundIconButton(
                    icon = Icons.Rounded.MoreVert,
                    contentDescription = "Daha fazla",
                    onClick = { menuExpanded = true },
                )
                DropdownMenu(
                    expanded = menuExpanded,
                    onDismissRequest = { menuExpanded = false },
                ) {
                    when {
                        downloadingProgress != null -> {
                            DropdownMenuItem(
                                text = { Text("İndiriliyor...") },
                                onClick = { menuExpanded = false },
                                leadingIcon = {
                                    androidx.compose.material3.CircularProgressIndicator(
                                        progress = { downloadingProgress },
                                        modifier = Modifier.size(18.dp),
                                        strokeWidth = 2.dp,
                                    )
                                },
                            )
                        }
                        track.isDownloaded -> {
                            DropdownMenuItem(
                                text = { Text("İndirmeyi sil") },
                                onClick = { onDeleteDownload(track.id); menuExpanded = false },
                                leadingIcon = {
                                    androidx.compose.material3.Icon(Icons.Rounded.DownloadDone, null)
                                },
                            )
                        }
                        track.videoId != null -> {
                            DropdownMenuItem(
                                text = { Text("İndir") },
                                onClick = { onDownloadTrack(track.id); menuExpanded = false },
                                leadingIcon = {
                                    androidx.compose.material3.Icon(Icons.Rounded.Download, null)
                                },
                            )
                        }
                    }
                    DropdownMenuItem(
                        text = { Text("Kütüphaneden kaldır") },
                        onClick = { onRemoveTrack(track.id); menuExpanded = false },
                        leadingIcon = {
                            androidx.compose.material3.Icon(Icons.Rounded.Delete, null)
                        },
                    )
                }
            }
        },
    )
}
