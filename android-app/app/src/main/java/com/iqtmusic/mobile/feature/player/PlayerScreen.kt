package com.iqtmusic.mobile.feature.player

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.gestures.detectHorizontalDragGestures
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.KeyboardArrowDown
import androidx.compose.material.icons.rounded.Pause
import androidx.compose.material.icons.rounded.PlayArrow
import androidx.compose.material.icons.rounded.QueueMusic
import androidx.compose.material.icons.rounded.Repeat
import androidx.compose.material.icons.rounded.RepeatOne
import androidx.compose.material.icons.rounded.Shuffle
import androidx.compose.material.icons.rounded.SkipNext
import androidx.compose.material.icons.rounded.SkipPrevious
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil.compose.AsyncImage
import com.iqtmusic.mobile.MainUiState
import com.iqtmusic.mobile.data.model.RepeatMode
import com.iqtmusic.mobile.playback.PlayerProgress
import com.iqtmusic.mobile.ui.components.IqtRoundIconButton
import com.iqtmusic.mobile.ui.theme.IqtNightBlack
import com.iqtmusic.mobile.ui.theme.iqtPalette

@Composable
fun PlayerScreen(
    uiState: MainUiState,
    playerProgress: PlayerProgress,
    onBack: () -> Unit,
    onTogglePlayback: () -> Unit,
    onSkipPrevious: () -> Unit,
    onSkipNext: () -> Unit,
    onSeek: (Float) -> Unit,
    onToggleShuffle: () -> Unit,
    onCycleRepeatMode: () -> Unit,
    onOpenQueue: () -> Unit = {},
) {
    val snapshot = uiState.snapshot
    val currentTrack = snapshot.tracks.find { it.id == snapshot.currentTrackId }
    val queue = snapshot.queueTrackIds
    val currentIdx = queue.indexOf(snapshot.currentTrackId)
    val hasPrevious = currentIdx > 0
    val hasNext = currentIdx >= 0 && currentIdx < queue.lastIndex

    var isDragging by remember { mutableStateOf(false) }
    var dragFraction by remember { mutableFloatStateOf(0f) }
    val displayFraction = if (isDragging) dragFraction else playerProgress.fraction

    val palette = MaterialTheme.iqtPalette
    val primary = MaterialTheme.colorScheme.primary

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(
                Brush.verticalGradient(
                    colorStops = arrayOf(
                        0.0f to palette.backgroundAlt,
                        1.0f to IqtNightBlack,
                    ),
                ),
            ),
    ) {
        // Soft accent glow behind cover
        Box(
            modifier = Modifier
                .size(360.dp)
                .align(Alignment.TopCenter)
                .background(
                    Brush.radialGradient(
                        colors = listOf(
                            primary.copy(alpha = 0.08f),
                            Color.Transparent,
                        ),
                    ),
                ),
        )

        Column(
            modifier = Modifier
                .fillMaxSize()
                .statusBarsPadding()
                .navigationBarsPadding()
                .padding(horizontal = 24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            // ── Top bar ─────────────────────────────
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 16.dp, bottom = 8.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                IqtRoundIconButton(
                    icon = Icons.Rounded.KeyboardArrowDown,
                    contentDescription = "Kapat",
                    onClick = onBack,
                )
                Text(
                    text = "SIMDI CALIYOR",
                    style = MaterialTheme.typography.labelSmall,
                    color = primary,
                    letterSpacing = 2.sp,
                )
                IqtRoundIconButton(
                    icon = Icons.Rounded.QueueMusic,
                    contentDescription = "Kuyruk",
                    onClick = onOpenQueue,
                )
            }

            Spacer(Modifier.height(16.dp))

            // ── Cover art ───────────────────────────
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .aspectRatio(1f)
                    .shadow(
                        elevation = 40.dp,
                        shape = RoundedCornerShape(20.dp),
                        ambientColor = primary.copy(alpha = 0.25f),
                        spotColor = Color.Black.copy(alpha = 0.6f),
                    )
                    .clip(RoundedCornerShape(20.dp))
                    .background(palette.cardHover),
            ) {
                if (!currentTrack?.coverUrl.isNullOrBlank()) {
                    AsyncImage(
                        model = currentTrack?.coverUrl,
                        contentDescription = "Kapak",
                        modifier = Modifier.fillMaxSize(),
                        contentScale = ContentScale.Crop,
                    )
                } else {
                    Box(
                        modifier = Modifier
                            .fillMaxSize()
                            .background(
                                Brush.linearGradient(
                                    colors = listOf(palette.cardHover, palette.elevated),
                                    start = Offset(0f, 0f),
                                    end = Offset(400f, 400f),
                                ),
                            ),
                    )
                }
            }

            Spacer(Modifier.height(28.dp))

            // ── Title + Artist ───────────────────────
            Column(
                modifier = Modifier.fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                Text(
                    text = currentTrack?.title ?: "-",
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.Bold,
                    color = palette.textPrimary,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    text = currentTrack?.artist ?: "-",
                    style = MaterialTheme.typography.bodyMedium,
                    color = palette.textSecondary,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }

            Spacer(Modifier.height(24.dp))

            // ── Seek bar ─────────────────────────────
            PlayerSeekBar(
                fraction = displayFraction,
                positionMs = if (isDragging) (dragFraction * playerProgress.durationMs).toLong() else playerProgress.positionMs,
                durationMs = playerProgress.durationMs,
                primaryColor = primary,
                onSeekStart = { f ->
                    isDragging = true
                    dragFraction = f
                },
                onSeekUpdate = { f -> dragFraction = f },
                onSeekEnd = { f ->
                    isDragging = false
                    onSeek(f)
                },
            )

            Spacer(Modifier.height(28.dp))

            // ── Controls ─────────────────────────────
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceEvenly,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                // Shuffle
                IconButton(onClick = onToggleShuffle) {
                    Icon(
                        imageVector = Icons.Rounded.Shuffle,
                        contentDescription = "Karistir",
                        tint = if (snapshot.shuffleEnabled) primary else palette.textMuted,
                        modifier = Modifier.size(22.dp),
                    )
                }

                // Skip previous
                IconButton(onClick = onSkipPrevious, enabled = hasPrevious) {
                    Icon(
                        imageVector = Icons.Rounded.SkipPrevious,
                        contentDescription = "Onceki",
                        tint = if (hasPrevious) palette.textPrimary else palette.textMuted,
                        modifier = Modifier.size(36.dp),
                    )
                }

                // Play / Pause — big
                Box(
                    modifier = Modifier
                        .shadow(
                            elevation = 12.dp,
                            shape = CircleShape,
                            spotColor = primary.copy(alpha = 0.5f),
                            ambientColor = primary.copy(alpha = 0.3f),
                        )
                        .size(68.dp)
                        .clip(CircleShape)
                        .background(primary),
                    contentAlignment = Alignment.Center,
                ) {
                    IconButton(
                        onClick = onTogglePlayback,
                        modifier = Modifier.fillMaxSize(),
                    ) {
                        Icon(
                            imageVector = if (snapshot.isPlaying) Icons.Rounded.Pause else Icons.Rounded.PlayArrow,
                            contentDescription = if (snapshot.isPlaying) "Duraklat" else "Cal",
                            tint = IqtNightBlack,
                            modifier = Modifier.size(32.dp),
                        )
                    }
                }

                // Skip next
                IconButton(onClick = onSkipNext, enabled = hasNext) {
                    Icon(
                        imageVector = Icons.Rounded.SkipNext,
                        contentDescription = "Sonraki",
                        tint = if (hasNext) palette.textPrimary else palette.textMuted,
                        modifier = Modifier.size(36.dp),
                    )
                }

                // Repeat
                IconButton(onClick = onCycleRepeatMode) {
                    Icon(
                        imageVector = when (snapshot.repeatMode) {
                            RepeatMode.ONE -> Icons.Rounded.RepeatOne
                            else -> Icons.Rounded.Repeat
                        },
                        contentDescription = "Tekrar",
                        tint = if (snapshot.repeatMode != RepeatMode.NONE) primary else palette.textMuted,
                        modifier = Modifier.size(22.dp),
                    )
                }
            }

            Spacer(Modifier.height(16.dp))
        }
    }
}

@Composable
private fun PlayerSeekBar(
    fraction: Float,
    positionMs: Long,
    durationMs: Long,
    primaryColor: Color,
    onSeekStart: (Float) -> Unit,
    onSeekUpdate: (Float) -> Unit,
    onSeekEnd: (Float) -> Unit,
) {
    var trackWidthPx by remember { mutableFloatStateOf(1f) }

    Column(
        modifier = Modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        // Track
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(36.dp)
                .onSizeChanged { trackWidthPx = it.width.toFloat() }
                .pointerInput(Unit) {
                    detectTapGestures { offset ->
                        val f = (offset.x / trackWidthPx).coerceIn(0f, 1f)
                        onSeekStart(f)
                        onSeekEnd(f)
                    }
                }
                .pointerInput(Unit) {
                    detectHorizontalDragGestures(
                        onDragStart = { offset ->
                            onSeekStart((offset.x / trackWidthPx).coerceIn(0f, 1f))
                        },
                        onHorizontalDrag = { _, dragAmount ->
                            val delta = dragAmount / trackWidthPx
                            onSeekUpdate((fraction + delta).coerceIn(0f, 1f))
                        },
                        onDragEnd = { onSeekEnd(fraction) },
                    )
                },
            contentAlignment = Alignment.Center,
        ) {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(4.dp)
                    .clip(RoundedCornerShape(2.dp))
                    .background(primaryColor.copy(alpha = 0.18f)),
            )
            Box(
                modifier = Modifier
                    .fillMaxWidth(fraction.coerceIn(0f, 1f))
                    .height(4.dp)
                    .clip(RoundedCornerShape(2.dp))
                    .background(primaryColor)
                    .align(Alignment.CenterStart),
            )
            // Thumb
            Box(
                modifier = Modifier
                    .align(Alignment.CenterStart)
                    .padding(start = (fraction.coerceIn(0f, 1f) * 0.98f * 300).dp.coerceAtLeast(0.dp))
                    .size(14.dp)
                    .clip(CircleShape)
                    .background(primaryColor),
            )
        }

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Text(
                text = formatMs(positionMs),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.iqtPalette.textMuted,
            )
            Text(
                text = formatMs(durationMs),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.iqtPalette.textMuted,
            )
        }
    }
}

private fun formatMs(ms: Long): String {
    if (ms <= 0L) return "0:00"
    val totalSeconds = ms / 1000
    val minutes = totalSeconds / 60
    val seconds = totalSeconds % 60
    return "$minutes:${seconds.toString().padStart(2, '0')}"
}
