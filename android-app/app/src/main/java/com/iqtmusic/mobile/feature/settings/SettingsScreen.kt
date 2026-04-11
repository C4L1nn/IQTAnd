package com.iqtmusic.mobile.feature.settings

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Check
import androidx.compose.material.icons.rounded.Close
import androidx.compose.material.icons.rounded.HelpOutline
import androidx.compose.material.icons.rounded.Wifi
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ElevatedCard
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.iqtmusic.mobile.MainUiState
import com.iqtmusic.mobile.ServerStatus

@Composable
fun SettingsScreen(
    uiState: MainUiState,
    onSaveServerUrl: (String) -> Unit,
    onCheckConnection: () -> Unit,
) {
    var urlInput by rememberSaveable(uiState.serverUrl) { mutableStateOf(uiState.serverUrl) }
    val isDirty = urlInput.trim() != uiState.serverUrl

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(20.dp),
    ) {
        Text("Ayarlar", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)

        // Server URL card
        ElevatedCard {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(20.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Text("Sunucu Adresi", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                Text(
                    "stream_server.py'nin çalıştığı adres. " +
                        "Render.com'a deploy edersen oradan aldığın URL'yi gir.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )

                OutlinedTextField(
                    value = urlInput,
                    onValueChange = { urlInput = it },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("https://iqtmusic-xxxx.onrender.com") },
                    singleLine = true,
                )

                Row(
                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Button(
                        onClick = {
                            onSaveServerUrl(urlInput.trim())
                        },
                        enabled = isDirty,
                    ) {
                        Text("Kaydet")
                    }
                    OutlinedButton(
                        onClick = onCheckConnection,
                        enabled = uiState.serverUrl.isNotBlank() && uiState.serverStatus != ServerStatus.CHECKING,
                    ) {
                        Text("Bağlantıyı Test Et")
                    }
                }

                // Connection status
                ConnectionStatus(uiState.serverStatus)
            }
        }

        // How-to card
        ElevatedCard {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(20.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Icon(Icons.Rounded.HelpOutline, contentDescription = null)
                    Text("Render.com'a Nasıl Deploy Edilir?", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                }

                Spacer(Modifier.height(4.dp))

                listOf(
                    "1. render.com'da ücretsiz hesap oluştur",
                    "2. GitHub'a iqtMusic projesini push et",
                    "3. New → Web Service → GitHub repo'nu seç",
                    "4. Build Command: pip install -r requirements_server.txt",
                    "5. Start Command: python stream_server.py",
                    "6. Deploy et → URL'yi buraya yapıştır",
                ).forEach { step ->
                    Text(
                        step,
                        style = MaterialTheme.typography.bodyMedium,
                        modifier = Modifier.padding(start = 4.dp),
                    )
                }

                Spacer(Modifier.height(4.dp))

                Text(
                    "Yerel kullanım için: python stream_server.py çalıştır, " +
                        "adb reverse tcp:5001 tcp:5001 komutunu ver ve " +
                        "adres olarak http://localhost:5001 gir.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

@Composable
private fun ConnectionStatus(status: ServerStatus) {
    when (status) {
        ServerStatus.UNCHECKED -> Unit
        ServerStatus.CHECKING -> Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            CircularProgressIndicator(modifier = Modifier.size(16.dp), strokeWidth = 2.dp)
            Text("Kontrol ediliyor...", style = MaterialTheme.typography.bodySmall)
        }
        ServerStatus.ONLINE -> Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Icon(Icons.Rounded.Check, contentDescription = null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(18.dp))
            Text("Sunucu çevrimiçi", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.primary)
        }
        ServerStatus.OFFLINE -> Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Icon(Icons.Rounded.Close, contentDescription = null, tint = MaterialTheme.colorScheme.error, modifier = Modifier.size(18.dp))
            Text("Sunucuya ulaşılamıyor", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
        }
    }
}
