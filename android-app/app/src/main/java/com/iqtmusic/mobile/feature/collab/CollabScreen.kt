package com.iqtmusic.mobile.feature.collab

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.iqtmusic.mobile.MainUiState

@Composable
fun CollabScreen(
    uiState: MainUiState,
    onStartCollabHost: () -> Unit,
) {
    val collab = uiState.snapshot.collab

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Text("Beraber Dinle", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)

        Card {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(18.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Text("Durum", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                Text("Rol: ${collab.roleLabel}")
                Text("Baglanti: ${collab.status}")
                Text("Katilimci: ${collab.participants}")
                Text("Oda kodu: ${collab.roomCode ?: "-"}")
                Button(onClick = onStartCollabHost) {
                    Text(if (collab.isActive) "Odayi yenile" else "Host olarak baslat")
                }
            }
        }

        Card {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(18.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Text("Android notu", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                Text(
                    text = "Bu asamada sadece collab akisinin UI ve state kabugu kuruldu. Sonraki adimda desktop tarafindaki MQTT tabanli protokol Android service katmanina tasinacak.",
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

