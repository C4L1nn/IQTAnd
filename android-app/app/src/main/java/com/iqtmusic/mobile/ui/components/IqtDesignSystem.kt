package com.iqtmusic.mobile.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.MusicNote
import androidx.compose.material.icons.rounded.Pause
import androidx.compose.material.icons.rounded.PlayArrow
import androidx.compose.material.icons.rounded.SkipNext
import androidx.compose.material.icons.rounded.SkipPrevious
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import com.iqtmusic.mobile.ui.theme.IqtAccent
import com.iqtmusic.mobile.ui.theme.IqtNightBlack
import com.iqtmusic.mobile.ui.theme.iqtPalette

private val IqtPanelShape = RoundedCornerShape(24.dp)
private val IqtRowShape = RoundedCornerShape(20.dp)
private val IqtPillShape = RoundedCornerShape(999.dp)

@Composable
fun IqtBackdrop(
    modifier: Modifier = Modifier,
    content: @Composable BoxScope.() -> Unit,
) {
    val palette = MaterialTheme.iqtPalette

    Box(
        modifier = modifier
            .fillMaxSize()
            .background(
                Brush.verticalGradient(
                    colors = listOf(palette.backgroundAlt, palette.background),
                ),
            ),
    ) {
        Box(
            modifier = Modifier
                .matchParentSize()
                .background(
                    Brush.linearGradient(
                        colors = listOf(
                            MaterialTheme.colorScheme.primary.copy(alpha = 0.16f),
                            Color.Transparent,
                        ),
                        start = Offset(0f, 0f),
                        end = Offset(540f, 760f),
                    ),
                ),
        )
        Box(
            modifier = Modifier
                .matchParentSize()
                .background(
                    Brush.linearGradient(
                        colors = listOf(
                            MaterialTheme.colorScheme.tertiary.copy(alpha = 0.12f),
                            Color.Transparent,
                        ),
                        start = Offset(1200f, 0f),
                        end = Offset(280f, 900f),
                    ),
                ),
        )
        content()
    }
}

@Composable
fun IqtPanel(
    modifier: Modifier = Modifier,
    shape: Shape = IqtPanelShape,
    contentPadding: PaddingValues = PaddingValues(18.dp),
    accentAmount: Float = 0f,
    content: @Composable ColumnScope.() -> Unit,
) {
    val palette = MaterialTheme.iqtPalette
    val borderColor = if (accentAmount > 0f) {
        MaterialTheme.colorScheme.primary.copy(alpha = 0.32f)
    } else {
        palette.border
    }

    Box(
        modifier = modifier
            .clip(shape)
            .background(
                Brush.linearGradient(
                    colors = listOf(palette.card, palette.elevated),
                ),
            )
            .border(1.dp, borderColor, shape),
    ) {
        if (accentAmount > 0f) {
            Box(
                modifier = Modifier
                    .matchParentSize()
                    .background(
                        Brush.linearGradient(
                            colors = listOf(
                                MaterialTheme.colorScheme.primary.copy(alpha = accentAmount),
                                Color.Transparent,
                            ),
                            start = Offset(0f, 0f),
                            end = Offset(700f, 700f),
                        ),
                    ),
            )
        }
        Column(
            modifier = Modifier.padding(contentPadding),
            verticalArrangement = Arrangement.spacedBy(12.dp),
            content = content,
        )
    }
}

@Composable
fun IqtScreenHeader(
    kicker: String,
    title: String,
    subtitle: String = "",
    modifier: Modifier = Modifier,
) {
    val palette = MaterialTheme.iqtPalette

    Column(
        modifier = modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        IqtEyebrow(kicker)
        Text(
            text = title,
            style = MaterialTheme.typography.displaySmall,
            color = palette.textPrimary,
        )
        if (subtitle.isNotEmpty()) {
            Text(
                text = subtitle,
                style = MaterialTheme.typography.bodyLarge,
                color = palette.textSecondary,
            )
        }
        Box(
            modifier = Modifier
                .width(84.dp)
                .height(4.dp)
                .clip(IqtPillShape)
                .background(
                    Brush.horizontalGradient(
                        colors = listOf(
                            MaterialTheme.colorScheme.primary,
                            MaterialTheme.colorScheme.tertiary,
                        ),
                    ),
                ),
        )
    }
}

@Composable
fun IqtSectionHeader(
    title: String,
    subtitle: String? = null,
    modifier: Modifier = Modifier,
    trailing: (@Composable () -> Unit)? = null,
) {
    val palette = MaterialTheme.iqtPalette

    Row(
        modifier = modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(
            modifier = Modifier.weight(1f),
            verticalArrangement = Arrangement.spacedBy(2.dp),
        ) {
            Text(
                text = title,
                style = MaterialTheme.typography.titleLarge,
                color = palette.textPrimary,
            )
            if (subtitle != null) {
                Text(
                    text = subtitle,
                    style = MaterialTheme.typography.bodySmall,
                    color = palette.textMuted,
                )
            }
        }
        if (trailing != null) {
            Spacer(Modifier.width(12.dp))
            trailing()
        }
    }
}

@Composable
fun IqtEyebrow(
    text: String,
    modifier: Modifier = Modifier,
) {
    Text(
        text = text.uppercase(),
        modifier = modifier,
        style = MaterialTheme.typography.labelSmall,
        color = MaterialTheme.colorScheme.primary,
    )
}

@Composable
fun IqtInfoPill(
    label: String,
    icon: ImageVector? = null,
    modifier: Modifier = Modifier,
    active: Boolean = false,
) {
    val palette = MaterialTheme.iqtPalette
    val background = if (active) {
        MaterialTheme.colorScheme.primary.copy(alpha = 0.16f)
    } else {
        palette.backgroundAlt.copy(alpha = 0.78f)
    }
    val borderColor = if (active) {
        MaterialTheme.colorScheme.primary.copy(alpha = 0.42f)
    } else {
        palette.border
    }
    val contentColor = if (active) {
        MaterialTheme.colorScheme.primary
    } else {
        palette.textSecondary
    }

    Row(
        modifier = modifier
            .clip(IqtPillShape)
            .background(background)
            .border(1.dp, borderColor, IqtPillShape)
            .padding(horizontal = 12.dp, vertical = 8.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (icon != null) {
            Icon(
                imageVector = icon,
                contentDescription = null,
                tint = contentColor,
                modifier = Modifier.size(14.dp),
            )
        }
        Text(
            text = label,
            style = MaterialTheme.typography.labelMedium,
            color = contentColor,
        )
    }
}

@Composable
fun IqtRoundIconButton(
    icon: ImageVector,
    contentDescription: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    active: Boolean = false,
    emphasize: Boolean = false,
    enabled: Boolean = true,
) {
    val palette = MaterialTheme.iqtPalette
    val background = when {
        !enabled -> palette.cardHover.copy(alpha = 0.42f)
        emphasize -> MaterialTheme.colorScheme.primary
        active -> MaterialTheme.colorScheme.primary.copy(alpha = 0.18f)
        else -> palette.backgroundAlt.copy(alpha = 0.92f)
    }
    val border = when {
        !enabled -> palette.border.copy(alpha = 0.5f)
        emphasize -> MaterialTheme.colorScheme.primary
        active -> MaterialTheme.colorScheme.primary.copy(alpha = 0.52f)
        else -> palette.border
    }
    val tint = when {
        !enabled -> palette.textMuted.copy(alpha = 0.6f)
        emphasize -> IqtNightBlack
        active -> MaterialTheme.colorScheme.primary
        else -> palette.textSecondary
    }
    val size = if (emphasize) 44.dp else 40.dp

    Box(
        modifier = modifier
            .size(size)
            .clip(CircleShape)
            .background(background)
            .border(1.dp, border, CircleShape)
            .then(
                if (enabled) Modifier.clickable(onClick = onClick) else Modifier,
            ),
        contentAlignment = Alignment.Center,
    ) {
        Icon(
            imageVector = icon,
            contentDescription = contentDescription,
            tint = tint,
            modifier = Modifier.size(if (emphasize) 20.dp else 18.dp),
        )
    }
}

@Composable
fun IqtTrackArtwork(
    coverUrl: String?,
    modifier: Modifier = Modifier,
    size: Dp = 56.dp,
) {
    val palette = MaterialTheme.iqtPalette
    val shape = RoundedCornerShape(16.dp)

    Box(
        modifier = modifier
            .size(size)
            .clip(shape)
            .background(
                Brush.linearGradient(
                    colors = listOf(palette.cardHover, palette.elevated),
                ),
            )
            .border(1.dp, palette.border, shape),
        contentAlignment = Alignment.Center,
    ) {
        if (coverUrl.isNullOrBlank()) {
            Icon(
                imageVector = Icons.Rounded.MusicNote,
                contentDescription = null,
                tint = palette.textMuted,
                modifier = Modifier.size(size * 0.42f),
            )
        } else {
            AsyncImage(
                model = coverUrl,
                contentDescription = "Track artwork",
                modifier = Modifier.fillMaxSize(),
                contentScale = ContentScale.Crop,
            )
        }
    }
}

@Composable
fun IqtTrackRow(
    title: String,
    subtitle: String,
    coverUrl: String?,
    modifier: Modifier = Modifier,
    leadingLabel: String? = null,
    badge: String? = null,
    isActive: Boolean = false,
    onClick: (() -> Unit)? = null,
    onSubtitleClick: (() -> Unit)? = null,
    trailing: @Composable RowScope.() -> Unit = {},
) {
    val palette = MaterialTheme.iqtPalette
    val shape = IqtRowShape
    val borderColor = if (isActive) {
        MaterialTheme.colorScheme.primary.copy(alpha = 0.44f)
    } else {
        palette.border
    }

    Row(
        modifier = modifier
            .clip(shape)
            .background(
                Brush.linearGradient(
                    colors = listOf(
                        if (isActive) palette.cardHover else palette.card,
                        palette.elevated,
                    ),
                ),
            )
            .border(1.dp, borderColor, shape)
            .then(if (onClick != null) Modifier.clickable(onClick = onClick) else Modifier)
            .padding(horizontal = 14.dp, vertical = 12.dp),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (leadingLabel != null) {
            Text(
                text = leadingLabel,
                style = MaterialTheme.typography.labelLarge,
                color = palette.textMuted,
                modifier = Modifier.width(18.dp),
                maxLines = 1,
            )
        }

        IqtTrackArtwork(coverUrl = coverUrl)

        Column(
            modifier = Modifier.weight(1f),
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            Text(
                text = title,
                style = MaterialTheme.typography.titleMedium,
                color = palette.textPrimary,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                text = subtitle,
                style = MaterialTheme.typography.bodyMedium,
                color = if (onSubtitleClick != null) MaterialTheme.colorScheme.primary.copy(alpha = 0.8f)
                        else palette.textSecondary,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                modifier = if (onSubtitleClick != null) Modifier.clickable(onClick = onSubtitleClick) else Modifier,
            )
        }

        if (badge != null) {
            IqtInfoPill(label = badge)
        }

        Row(
            horizontalArrangement = Arrangement.spacedBy(6.dp),
            verticalAlignment = Alignment.CenterVertically,
            content = trailing,
        )
    }
}

@Composable
fun IqtStatTile(
    title: String,
    value: String,
    modifier: Modifier = Modifier,
) {
    val palette = MaterialTheme.iqtPalette

    IqtPanel(
        modifier = modifier,
        accentAmount = 0.1f,
    ) {
        Text(
            text = title,
            style = MaterialTheme.typography.labelMedium,
            color = palette.textMuted,
        )
        Text(
            text = value,
            style = MaterialTheme.typography.headlineMedium,
            color = palette.textPrimary,
            fontWeight = FontWeight.ExtraBold,
        )
    }
}

@Composable
fun IqtEmptyState(
    title: String,
    body: String,
    modifier: Modifier = Modifier,
) {
    val palette = MaterialTheme.iqtPalette

    IqtPanel(
        modifier = modifier,
        accentAmount = 0.08f,
    ) {
        Text(
            text = title,
            style = MaterialTheme.typography.titleLarge,
            color = palette.textPrimary,
        )
        Text(
            text = body,
            style = MaterialTheme.typography.bodyMedium,
            color = palette.textSecondary,
        )
    }
}

@Composable
fun iqtOutlinedTextFieldColors() = OutlinedTextFieldDefaults.colors(
    focusedTextColor = MaterialTheme.iqtPalette.textPrimary,
    unfocusedTextColor = MaterialTheme.iqtPalette.textPrimary,
    disabledTextColor = MaterialTheme.iqtPalette.textMuted,
    focusedContainerColor = MaterialTheme.iqtPalette.elevated.copy(alpha = 0.82f),
    unfocusedContainerColor = MaterialTheme.iqtPalette.elevated.copy(alpha = 0.82f),
    disabledContainerColor = MaterialTheme.iqtPalette.elevated.copy(alpha = 0.4f),
    focusedBorderColor = MaterialTheme.colorScheme.primary,
    unfocusedBorderColor = MaterialTheme.iqtPalette.border,
    disabledBorderColor = MaterialTheme.iqtPalette.border.copy(alpha = 0.45f),
    cursorColor = MaterialTheme.colorScheme.primary,
    focusedLabelColor = MaterialTheme.colorScheme.primary,
    unfocusedLabelColor = MaterialTheme.iqtPalette.textMuted,
    focusedPlaceholderColor = MaterialTheme.iqtPalette.textMuted,
    unfocusedPlaceholderColor = MaterialTheme.iqtPalette.textMuted,
)

@Composable
fun iqtPrimaryButtonColors() = ButtonDefaults.buttonColors(
    containerColor = MaterialTheme.colorScheme.primary,
    contentColor = IqtNightBlack,
    disabledContainerColor = MaterialTheme.iqtPalette.cardHover,
    disabledContentColor = MaterialTheme.iqtPalette.textMuted,
)

@Composable
fun iqtSecondaryButtonColors() = ButtonDefaults.outlinedButtonColors(
    contentColor = MaterialTheme.iqtPalette.textSecondary,
    disabledContentColor = MaterialTheme.iqtPalette.textMuted,
)

@Composable
fun IqtNavigationDock(
    items: List<IqtNavItemModel>,
    selectedRoute: String?,
    modifier: Modifier = Modifier,
    onNavigate: (String) -> Unit,
) {
    val palette = MaterialTheme.iqtPalette
    val topShape = RoundedCornerShape(topStart = 28.dp, topEnd = 28.dp)

    Box(
        modifier = modifier
            .fillMaxWidth()
            .clip(topShape)
            .background(palette.card)
            .border(1.dp, palette.border, topShape),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 8.dp, vertical = 10.dp),
            horizontalArrangement = Arrangement.SpaceEvenly,
        ) {
            items.forEach { item ->
                val selected = selectedRoute == item.route
                IqtNavItem(
                    item = item,
                    selected = selected,
                    onClick = { onNavigate(item.route) },
                )
            }
        }
    }
}

@Composable
private fun IqtNavItem(
    item: IqtNavItemModel,
    selected: Boolean,
    onClick: () -> Unit,
) {
    val primary = MaterialTheme.colorScheme.primary
    val palette = MaterialTheme.iqtPalette

    Column(
        modifier = Modifier
            .clip(RoundedCornerShape(16.dp))
            .clickable(onClick = onClick)
            .padding(horizontal = 14.dp, vertical = 6.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Box(
            modifier = Modifier
                .size(44.dp, 30.dp)
                .clip(RoundedCornerShape(15.dp))
                .background(
                    if (selected) primary.copy(alpha = 0.15f) else Color.Transparent,
                ),
            contentAlignment = Alignment.Center,
        ) {
            Icon(
                imageVector = item.icon,
                contentDescription = item.label,
                tint = if (selected) primary else palette.textMuted,
                modifier = Modifier.size(22.dp),
            )
        }
        Text(
            text = item.label,
            style = MaterialTheme.typography.labelSmall,
            color = if (selected) primary else palette.textMuted,
            maxLines = 1,
        )
    }
}

@Composable
fun IqtNowPlayingCard(
    title: String,
    subtitle: String,
    coverUrl: String?,
    isPlaying: Boolean,
    modifier: Modifier = Modifier,
    hasPrevious: Boolean = false,
    hasNext: Boolean = false,
    isLoading: Boolean = false,
    progress: Float = 0f,
    onClick: () -> Unit,
    onTogglePlayback: () -> Unit,
    onSkipPrevious: () -> Unit = {},
    onSkipNext: () -> Unit = {},
    onSeek: ((Float) -> Unit)? = null,
) {
    val palette = MaterialTheme.iqtPalette
    val shape = IqtPanelShape

    Column(
        modifier = modifier
            .clip(shape)
            .background(
                Brush.linearGradient(
                    colors = listOf(
                        palette.cardHover,
                        palette.elevated,
                    ),
                ),
            )
            .border(
                1.dp,
                MaterialTheme.colorScheme.primary.copy(alpha = 0.3f),
                shape,
            )
            .clickable(onClick = onClick),
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 14.dp, vertical = 12.dp),
            horizontalArrangement = Arrangement.spacedBy(12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            IqtTrackArtwork(
                coverUrl = coverUrl,
                size = 52.dp,
            )
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                IqtEyebrow("simdi caliyor")
                Text(
                    text = title,
                    style = MaterialTheme.typography.titleMedium,
                    color = palette.textPrimary,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    text = subtitle,
                    style = MaterialTheme.typography.bodySmall,
                    color = palette.textSecondary,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
            IqtRoundIconButton(
                icon = Icons.Rounded.SkipPrevious,
                contentDescription = "Onceki",
                onClick = onSkipPrevious,
                enabled = hasPrevious && !isLoading,
            )
            if (isLoading) {
                Box(
                    modifier = Modifier.size(40.dp),
                    contentAlignment = Alignment.Center,
                ) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(24.dp),
                        strokeWidth = 2.dp,
                        color = MaterialTheme.colorScheme.primary,
                    )
                }
            } else {
                IqtRoundIconButton(
                    icon = if (isPlaying) Icons.Rounded.Pause else Icons.Rounded.PlayArrow,
                    contentDescription = if (isPlaying) "Duraklat" else "Cal",
                    onClick = onTogglePlayback,
                    emphasize = true,
                )
            }
            IqtRoundIconButton(
                icon = Icons.Rounded.SkipNext,
                contentDescription = "Sonraki",
                onClick = onSkipNext,
                enabled = hasNext && !isLoading,
            )
        }
        if (progress > 0f) {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(16.dp)
                    .then(
                        if (onSeek != null) {
                            Modifier.pointerInput(Unit) {
                                detectTapGestures { offset ->
                                    onSeek((offset.x / size.width).coerceIn(0f, 1f))
                                }
                            }
                        } else Modifier,
                    ),
                contentAlignment = Alignment.Center,
            ) {
                LinearProgressIndicator(
                    progress = { progress },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(2.dp),
                    color = MaterialTheme.colorScheme.primary,
                    trackColor = MaterialTheme.colorScheme.primary.copy(alpha = 0.15f),
                )
            }
        }
    }
}

data class IqtNavItemModel(
    val route: String,
    val label: String,
    val icon: ImageVector,
)
