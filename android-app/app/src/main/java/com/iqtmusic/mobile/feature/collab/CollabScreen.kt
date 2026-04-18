package com.iqtmusic.mobile.feature.collab

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Groups
import androidx.compose.material.icons.rounded.Hub
import androidx.compose.material.icons.rounded.Link
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.iqtmusic.mobile.MainUiState
import com.iqtmusic.mobile.ui.components.IqtInfoPill
import com.iqtmusic.mobile.ui.components.IqtPanel
import com.iqtmusic.mobile.ui.components.IqtScreenHeader
import com.iqtmusic.mobile.ui.components.IqtSectionHeader
import com.iqtmusic.mobile.ui.components.iqtPrimaryButtonColors
import com.iqtmusic.mobile.ui.theme.iqtPalette

@Composable
fun CollabScreen(
    uiState: MainUiState,
    onStartCollabHost: () -> Unit,
) {
    val collab = uiState.snapshot.collab

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(horizontal = 20.dp, vertical = 20.dp),
        verticalArrangement = Arrangement.spacedBy(18.dp),
    ) {
        item {
            IqtScreenHeader(
                kicker = "beraber",
                title = "Beraber dinle",
            )
        }

        item {
            IqtPanel(
                modifier = Modifier.fillMaxWidth(),
                accentAmount = if (collab.isActive) 0.14f else 0f,
            ) {
                IqtSectionHeader(title = "Oturum durumu")
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    IqtInfoPill(
                        label = collab.roleLabel,
                        icon = Icons.Rounded.Groups,
                        active = collab.isActive,
                    )
                    IqtInfoPill(
                        label = collab.status,
                        icon = Icons.Rounded.Link,
                    )
                    IqtInfoPill(
                        label = "${collab.participants} kisi",
                        icon = Icons.Rounded.Hub,
                    )
                }
                Text(
                    text = "Oda kodu: ${collab.roomCode ?: "-"}",
                    style = MaterialTheme.typography.headlineMedium,
                    color = MaterialTheme.iqtPalette.textPrimary,
                )
                Button(
                    onClick = onStartCollabHost,
                    colors = iqtPrimaryButtonColors(),
                ) {
                    Text(if (collab.isActive) "Odayi yenile" else "Oda olustur")
                }
            }
        }

    }
}
