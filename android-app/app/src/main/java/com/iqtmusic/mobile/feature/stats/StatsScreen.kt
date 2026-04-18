package com.iqtmusic.mobile.feature.stats

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.iqtmusic.mobile.MainUiState
import com.iqtmusic.mobile.ui.components.IqtEmptyState
import com.iqtmusic.mobile.ui.components.IqtPanel
import com.iqtmusic.mobile.ui.components.IqtScreenHeader
import com.iqtmusic.mobile.ui.components.IqtSectionHeader
import com.iqtmusic.mobile.ui.components.IqtStatTile
import com.iqtmusic.mobile.ui.theme.iqtPalette

@Composable
fun StatsScreen(
    uiState: MainUiState,
) {
    val snapshot = uiState.snapshot
    val stats = snapshot.stats
    val topArtists = snapshot.artistPlayCounts
        .entries
        .sortedByDescending { it.value }
        .take(5)
    val totalPlays = snapshot.artistPlayCounts.values.sum()

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(horizontal = 20.dp, vertical = 20.dp),
        verticalArrangement = Arrangement.spacedBy(18.dp),
    ) {
        item {
            IqtScreenHeader(
                kicker = "ozet",
                title = "Istatistik",
            )
        }

        if (totalPlays <= 0) {
            item {
                IqtEmptyState(
                    title = "Henuz dinleme yok",
                    body = "Sarki cal, istatistiklerin burada gorunur.",
                )
            }
        } else {
            item {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    IqtStatTile(
                        title = "Toplam sure",
                        value = formatMinutes(stats.totalMinutes),
                        modifier = Modifier.weight(1f),
                    )
                    IqtStatTile(
                        title = "Bu hafta",
                        value = formatMinutes(stats.weeklyMinutes),
                        modifier = Modifier.weight(1f),
                    )
                }
            }

            item {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    IqtStatTile(
                        title = "Seri",
                        value = if (stats.streakDays > 0) "${stats.streakDays} gun" else "-",
                        modifier = Modifier.weight(1f),
                    )
                    IqtStatTile(
                        title = "En cok dinlenen",
                        value = stats.topArtist,
                        modifier = Modifier.weight(1f),
                    )
                }
            }

            if (topArtists.isNotEmpty()) {
                item {
                    IqtSectionHeader(title = "En cok dinlenen")
                }
                items(topArtists, key = { it.key }) { (artist, count) ->
                    IqtPanel(modifier = Modifier.fillMaxWidth(), accentAmount = 0.06f) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                        ) {
                            Text(
                                text = artist,
                                style = MaterialTheme.typography.titleSmall,
                                color = MaterialTheme.iqtPalette.textPrimary,
                            )
                            Text(
                                text = "$count dinleme",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.iqtPalette.textSecondary,
                            )
                        }
                    }
                }
            }
        }
    }
}

private fun formatMinutes(minutes: Int): String = when {
    minutes <= 0 -> "-"
    minutes < 60 -> "$minutes dk"
    else -> "${minutes / 60} sa ${minutes % 60} dk"
}
