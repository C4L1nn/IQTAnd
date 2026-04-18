package com.iqtmusic.mobile.feature.playlists

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.ChevronRight
import androidx.compose.material.icons.rounded.PlayArrow
import androidx.compose.material.icons.rounded.QueueMusic
import androidx.compose.material3.Button
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
import com.iqtmusic.mobile.ui.components.IqtEmptyState
import com.iqtmusic.mobile.ui.components.IqtInfoPill
import com.iqtmusic.mobile.ui.components.IqtPanel
import com.iqtmusic.mobile.ui.components.IqtRoundIconButton
import com.iqtmusic.mobile.ui.components.IqtScreenHeader
import com.iqtmusic.mobile.ui.components.IqtSectionHeader
import com.iqtmusic.mobile.ui.components.iqtOutlinedTextFieldColors
import com.iqtmusic.mobile.ui.components.iqtPrimaryButtonColors
import com.iqtmusic.mobile.ui.theme.iqtPalette

@Composable
fun PlaylistsScreen(
    uiState: MainUiState,
    onCreatePlaylist: (String) -> Unit,
    onPlayPlaylist: (String, String?) -> Unit,
    onOpenPlaylist: (String) -> Unit,
) {
    var playlistName by rememberSaveable { mutableStateOf("") }

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(horizontal = 20.dp, vertical = 20.dp),
        verticalArrangement = Arrangement.spacedBy(18.dp),
    ) {
        item {
            IqtScreenHeader(
                kicker = "koleksiyon",
                title = "Listelerim",
            )
        }

        item {
            IqtPanel(
                modifier = Modifier.fillMaxWidth(),
                accentAmount = 0.12f,
            ) {
                IqtSectionHeader(title = "Yeni liste olustur")
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    OutlinedTextField(
                        value = playlistName,
                        onValueChange = { playlistName = it },
                        modifier = Modifier.weight(1f),
                        singleLine = true,
                        label = { Text("Liste adi") },
                        placeholder = { Text("Gece surusu, Fokus, Favoriler...") },
                        colors = iqtOutlinedTextFieldColors(),
                    )
                    Button(
                        onClick = {
                            onCreatePlaylist(playlistName)
                            playlistName = ""
                        },
                        enabled = playlistName.isNotBlank(),
                        colors = iqtPrimaryButtonColors(),
                    ) {
                        Text("Olustur")
                    }
                }
            }
        }

        item {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                IqtInfoPill(
                    label = "${uiState.snapshot.playlists.size} liste",
                    icon = Icons.Rounded.QueueMusic,
                    active = uiState.snapshot.playlists.isNotEmpty(),
                )
                IqtInfoPill(
                    label = "${uiState.snapshot.tracks.size} sarki",
                    icon = Icons.Rounded.PlayArrow,
                )
            }
        }

        if (uiState.snapshot.playlists.isEmpty()) {
            item {
                IqtEmptyState(
                    title = "Liste yok",
                    body = "Yukardaki alandan yeni liste olustur.",
                )
            }
        } else {
            items(uiState.snapshot.playlists, key = { it.id }) { playlist ->
                val firstTrackId = playlist.trackIds.firstOrNull()
                val firstTrack = uiState.snapshot.tracks.find { it.id == firstTrackId }

                IqtPanel(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable { onOpenPlaylist(playlist.id) },
                    accentAmount = if (firstTrackId != null) 0.1f else 0f,
                ) {
                    Text(
                        text = playlist.name,
                        style = MaterialTheme.typography.headlineMedium,
                        color = MaterialTheme.iqtPalette.textPrimary,
                    )
                    Text(
                        text = if (firstTrack != null) firstTrack.title else "Bos liste",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.iqtPalette.textSecondary,
                    )
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        IqtInfoPill(
                            label = "${playlist.trackIds.size} sarki",
                            icon = Icons.Rounded.QueueMusic,
                        )
                        if (firstTrack != null) {
                            IqtInfoPill(
                                label = firstTrack.artist,
                                icon = Icons.Rounded.PlayArrow,
                            )
                        }
                    }
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        IqtRoundIconButton(
                            icon = Icons.Rounded.PlayArrow,
                            contentDescription = "Listeyi cal",
                            onClick = { onPlayPlaylist(playlist.id, firstTrackId) },
                            emphasize = true,
                            enabled = firstTrackId != null,
                        )
                        IqtRoundIconButton(
                            icon = Icons.Rounded.ChevronRight,
                            contentDescription = "Liste detayi",
                            onClick = { onOpenPlaylist(playlist.id) },
                        )
                    }
                }
            }
        }
    }
}
