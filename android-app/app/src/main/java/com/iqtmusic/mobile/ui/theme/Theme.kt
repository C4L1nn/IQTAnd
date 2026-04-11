package com.iqtmusic.mobile.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable

private val DarkColors = darkColorScheme(
    primary = BrandGreen,
    onPrimary = Midnight,
    secondary = BrandGreenSoft,
    background = Midnight,
    surface = SurfaceNight,
    surfaceVariant = SurfaceCard,
    onSurfaceVariant = TextSoft,
)

@Composable
fun IqtMusicAndroidTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    val colors = DarkColors
    MaterialTheme(
        colorScheme = colors,
        typography = IqtTypography,
        content = content,
    )
}

