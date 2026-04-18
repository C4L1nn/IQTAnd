package com.iqtmusic.mobile.feature.settings

import android.webkit.CookieManager
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.AccountCircle
import androidx.compose.material.icons.rounded.Check
import androidx.compose.material.icons.rounded.Close
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import com.iqtmusic.mobile.MainUiState
import com.iqtmusic.mobile.ServerStatus
import com.iqtmusic.mobile.ui.components.IqtInfoPill
import com.iqtmusic.mobile.ui.components.IqtPanel
import com.iqtmusic.mobile.ui.components.IqtScreenHeader
import com.iqtmusic.mobile.ui.components.IqtSectionHeader
import com.iqtmusic.mobile.ui.components.iqtOutlinedTextFieldColors
import com.iqtmusic.mobile.ui.components.iqtPrimaryButtonColors
import com.iqtmusic.mobile.ui.components.iqtSecondaryButtonColors
import com.iqtmusic.mobile.ui.theme.iqtPalette

@Composable
fun SettingsScreen(
    uiState: MainUiState,
    onSaveServerUrl: (String) -> Unit,
    onCheckConnection: () -> Unit,
) {
    var urlInput by rememberSaveable(uiState.serverUrl) { mutableStateOf(uiState.serverUrl) }
    val isDirty = urlInput.trim() != uiState.serverUrl
    var showYouTubeLogin by rememberSaveable { mutableStateOf(false) }
    var isYouTubeLoggedIn by remember {
        mutableStateOf(
            (CookieManager.getInstance().getCookie("https://www.youtube.com") ?: "").contains("SAPISID"),
        )
    }

    if (showYouTubeLogin) {
        Dialog(
            onDismissRequest = {
                showYouTubeLogin = false
                CookieManager.getInstance().flush()
                isYouTubeLoggedIn =
                    (CookieManager.getInstance().getCookie("https://www.youtube.com") ?: "").contains("SAPISID")
            },
            properties = DialogProperties(usePlatformDefaultWidth = false),
        ) {
            AndroidView(
                modifier = Modifier.fillMaxSize(),
                factory = { ctx ->
                    WebView(ctx).apply {
                        settings.javaScriptEnabled = true
                        settings.domStorageEnabled = true
                        CookieManager.getInstance().setAcceptCookie(true)
                        CookieManager.getInstance().setAcceptThirdPartyCookies(this, true)
                        webViewClient = WebViewClient()
                        loadUrl("https://accounts.google.com/signin/v2/identifier?service=youtube&hl=tr")
                    }
                },
            )
        }
    }

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(horizontal = 20.dp, vertical = 20.dp),
        verticalArrangement = Arrangement.spacedBy(18.dp),
    ) {
        item {
            IqtScreenHeader(
                kicker = "ayarlar",
                title = "Ayarlar",
            )
        }

        item {
            IqtPanel(
                modifier = Modifier.fillMaxWidth(),
                accentAmount = if (uiState.serverStatus == ServerStatus.ONLINE) 0.14f else 0f,
            ) {
                IqtSectionHeader(title = "Baglanti adresi")
                OutlinedTextField(
                    value = urlInput,
                    onValueChange = { urlInput = it },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("localhost:5001 veya https://...") },
                    singleLine = true,
                    colors = iqtOutlinedTextFieldColors(),
                )
                Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    Button(
                        onClick = { onSaveServerUrl(urlInput.trim()) },
                        enabled = isDirty,
                        colors = iqtPrimaryButtonColors(),
                    ) {
                        Text("Kaydet")
                    }
                    OutlinedButton(
                        onClick = onCheckConnection,
                        enabled = uiState.serverUrl.isNotBlank() && uiState.serverStatus != ServerStatus.CHECKING,
                        colors = iqtSecondaryButtonColors(),
                    ) {
                        Text("Baglantiyi test et")
                    }
                }
                ConnectionStatus(uiState.serverStatus)
            }
        }

        item {
            IqtPanel(modifier = Modifier.fillMaxWidth()) {
                IqtSectionHeader(title = "YouTube oturumu")
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    IqtInfoPill(
                        label = if (isYouTubeLoggedIn) "Oturum hazir" else "Oturum kapali",
                        icon = Icons.Rounded.AccountCircle,
                        active = isYouTubeLoggedIn,
                    )
                }
                if (isYouTubeLoggedIn) {
                    OutlinedButton(
                        onClick = { showYouTubeLogin = true },
                        colors = iqtSecondaryButtonColors(),
                    ) {
                        Text("Oturumu yenile")
                    }
                } else {
                    Button(
                        onClick = { showYouTubeLogin = true },
                        colors = iqtPrimaryButtonColors(),
                    ) {
                        Text("Giris yap")
                    }
                }
            }
        }

    }
}

@Composable
private fun ConnectionStatus(status: ServerStatus) {
    when (status) {
        ServerStatus.UNCHECKED -> Unit
        ServerStatus.CHECKING -> Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            CircularProgressIndicator(strokeWidth = 2.dp, modifier = Modifier.size(16.dp))
            Text(
                text = "Kontrol ediliyor...",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.iqtPalette.textSecondary,
            )
        }
        ServerStatus.ONLINE -> IqtInfoPill(
            label = "Sunucu cevrimici",
            icon = Icons.Rounded.Check,
            active = true,
        )
        ServerStatus.OFFLINE -> IqtInfoPill(
            label = "Sunucuya ulasilamiyor",
            icon = Icons.Rounded.Close,
        )
    }
}
