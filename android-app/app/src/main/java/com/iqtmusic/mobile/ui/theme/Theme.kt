package com.iqtmusic.mobile.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp

private val DarkColors = darkColorScheme(
    primary = IqtAccent,
    onPrimary = IqtNightBlack,
    secondary = IqtTextSecondary,
    onSecondary = IqtNightBlack,
    tertiary = IqtBrandBlue,
    background = IqtNightBlack,
    onBackground = IqtTextPrimary,
    surface = IqtNightDark,
    onSurface = IqtTextPrimary,
    surfaceVariant = IqtCard,
    onSurfaceVariant = IqtTextSecondary,
    outline = IqtBorder,
    outlineVariant = IqtBorder.copy(alpha = 0.72f),
    error = IqtDanger,
    onError = IqtNightBlack,
)

private val IqtShapes = Shapes(
    extraSmall = androidx.compose.foundation.shape.RoundedCornerShape(10.dp),
    small = androidx.compose.foundation.shape.RoundedCornerShape(14.dp),
    medium = androidx.compose.foundation.shape.RoundedCornerShape(20.dp),
    large = androidx.compose.foundation.shape.RoundedCornerShape(26.dp),
    extraLarge = androidx.compose.foundation.shape.RoundedCornerShape(30.dp),
)

@Immutable
data class IqtPalette(
    val background: Color,
    val backgroundAlt: Color,
    val card: Color,
    val cardHover: Color,
    val elevated: Color,
    val border: Color,
    val textPrimary: Color,
    val textSecondary: Color,
    val textMuted: Color,
)

private val LocalIqtPalette = staticCompositionLocalOf {
    IqtPalette(
        background = IqtNightBlack,
        backgroundAlt = IqtNightDark,
        card = IqtCard,
        cardHover = IqtCardHover,
        elevated = IqtElevated,
        border = IqtBorder,
        textPrimary = IqtTextPrimary,
        textSecondary = IqtTextSecondary,
        textMuted = IqtTextMuted,
    )
}

val MaterialTheme.iqtPalette: IqtPalette
    @Composable
    get() = LocalIqtPalette.current

@Composable
fun IqtMusicAndroidTheme(
    darkTheme: Boolean = true,
    content: @Composable () -> Unit,
) {
    val palette = IqtPalette(
        background = IqtNightBlack,
        backgroundAlt = IqtNightDark,
        card = IqtCard,
        cardHover = IqtCardHover,
        elevated = IqtElevated,
        border = IqtBorder,
        textPrimary = IqtTextPrimary,
        textSecondary = IqtTextSecondary,
        textMuted = IqtTextMuted,
    )

    CompositionLocalProvider(LocalIqtPalette provides palette) {
        MaterialTheme(
            colorScheme = DarkColors,
            typography = IqtTypography,
            shapes = IqtShapes,
            content = content,
        )
    }
}
