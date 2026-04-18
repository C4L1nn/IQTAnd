package com.iqtmusic.mobile.feature.search

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.PlaylistAdd
import androidx.compose.material.icons.rounded.Favorite
import androidx.compose.material.icons.rounded.FavoriteBorder
import androidx.compose.material.icons.rounded.Link
import androidx.compose.material.icons.rounded.PlayArrow
import androidx.compose.material.icons.rounded.QueueMusic
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.iqtmusic.mobile.MainUiState
import com.iqtmusic.mobile.data.model.Track
import com.iqtmusic.mobile.ui.components.IqtEmptyState
import com.iqtmusic.mobile.ui.components.IqtInfoPill
import com.iqtmusic.mobile.ui.components.IqtPanel
import com.iqtmusic.mobile.ui.components.IqtRoundIconButton
import com.iqtmusic.mobile.ui.components.IqtScreenHeader
import com.iqtmusic.mobile.ui.components.IqtSectionHeader
import com.iqtmusic.mobile.ui.components.IqtTrackRow
import com.iqtmusic.mobile.ui.components.iqtOutlinedTextFieldColors

@Composable
fun SearchScreen(
    uiState: MainUiState,
    onQueryChange: (String) -> Unit,
    onPlayTrack: (String) -> Unit,
    onAddAndPlayTrack: (Track) -> Unit,
    onToggleFavorite: (String) -> Unit,
    onAddTrackToPlaylist: (String, String) -> Unit,
) {
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(horizontal = 20.dp, vertical = 20.dp),
        verticalArrangement = Arrangement.spacedBy(18.dp),
    ) {
        item {
            IqtScreenHeader(
                kicker = "kesfet",
                title = "Ara",
                subtitle = "Sarki, sanatci ve album ara.",
            )
        }

        item {
            IqtPanel(
                modifier = Modifier.fillMaxWidth(),
                accentAmount = if (uiState.searchQuery.isNotBlank()) 0.1f else 0f,
            ) {
                OutlinedTextField(
                    value = uiState.searchQuery,
                    onValueChange = onQueryChange,
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                    label = { Text("Sarki, sanatci veya album") },
                    placeholder = { Text("Ornek: The Weeknd, Duman, Motive") },
                    colors = iqtOutlinedTextFieldColors(),
                )
            }
        }

        if (uiState.searchQuery.isBlank()) {
            item {
                IqtEmptyState(
                    title = "Aramaya hazir",
                    body = "Aramaya basla; kutuphanendeki sarkilar ve cevrimici sonuclar burada birlikte gorunur.",
                )
            }
        } else {
            if (uiState.searchResults.isNotEmpty()) {
                item {
                    IqtSectionHeader(
                        title = "Kutuphanen",
                        subtitle = "Cihazindaki ve kayitli sarkilar.",
                        trailing = {
                            IqtInfoPill(
                                label = "${uiState.searchResults.size} sonuc",
                                icon = Icons.Rounded.QueueMusic,
                            )
                        },
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

            item {
                IqtSectionHeader(
                    title = "Cevrimici sonuclar",
                    subtitle = "Daha fazlasini kesfet.",
                    trailing = {
                        if (uiState.isRemoteSearching) {
                            CircularProgressIndicator(
                                modifier = Modifier.size(18.dp),
                                strokeWidth = 2.dp,
                            )
                        } else {
                            IqtInfoPill(
                                label = "${uiState.remoteSearchResults.size} sonuc",
                                icon = Icons.Rounded.Link,
                                active = uiState.remoteSearchResults.isNotEmpty(),
                            )
                        }
                    },
                )
            }

            if (!uiState.isRemoteSearching && uiState.remoteSearchResults.isEmpty()) {
                item {
                    IqtEmptyState(
                        title = "Sonuc bulunamadi",
                        body = "Bir sonuc bulamadik. Yazimi kontrol et veya farkli bir arama dene. Cevrimici sonuclar gelmiyorsa Ayarlar ekranindan baglanti adresini kontrol edebilirsin.",
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

@Composable
private fun LocalTrackRow(
    track: Track,
    uiState: MainUiState,
    onPlayTrack: (String) -> Unit,
    onToggleFavorite: (String) -> Unit,
    onAddTrackToPlaylist: (String, String) -> Unit,
) {
    val subtitle = buildString {
        append(track.artist)
        if (track.album.isNotBlank()) {
            append(" - ")
            append(track.album)
        }
    }

    IqtTrackRow(
        title = track.title,
        subtitle = subtitle,
        coverUrl = track.coverUrl,
        badge = track.durationLabel,
        onClick = { onPlayTrack(track.id) },
        trailing = {
            AddToPlaylistButton(
                uiState = uiState,
                trackId = track.id,
                onAddTrackToPlaylist = onAddTrackToPlaylist,
            )
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

@Composable
private fun RemoteTrackRow(
    track: Track,
    onAddAndPlayTrack: (Track) -> Unit,
) {
    IqtTrackRow(
        title = track.title,
        subtitle = "${track.artist} - ${track.durationLabel}",
        coverUrl = track.coverUrl,
        badge = "ekle",
        onClick = { onAddAndPlayTrack(track) },
        trailing = {
            IqtRoundIconButton(
                icon = Icons.Rounded.PlayArrow,
                contentDescription = "Ekle ve cal",
                onClick = { onAddAndPlayTrack(track) },
                emphasize = true,
            )
        },
    )
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
        IqtRoundIconButton(
            icon = Icons.AutoMirrored.Rounded.PlaylistAdd,
            contentDescription = "Listeye ekle",
            onClick = { expanded = true },
            enabled = playlists.isNotEmpty(),
        )
        DropdownMenu(
            expanded = expanded,
            onDismissRequest = { expanded = false },
        ) {
            playlists.forEach { playlist ->
                val alreadyAdded = trackId in playlist.trackIds
                DropdownMenuItem(
                    text = {
                        Text(
                            text = if (alreadyAdded) "${playlist.name} (ekli)" else playlist.name,
                            color = if (alreadyAdded) {
                                MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f)
                            } else {
                                MaterialTheme.colorScheme.onSurface
                            },
                        )
                    },
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
