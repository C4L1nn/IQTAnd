"""Sinematik splash screen — iqtMusic.

Animasyonlu aurora arka plan, smooth progress bar, fade-in logo.
"""

from __future__ import annotations
import math

from PySide6.QtCore import Qt, QRect, QTimer, QRectF
from PySide6.QtGui import (
    QPixmap, QPainter, QColor, QFont, QLinearGradient,
    QRadialGradient, QBrush, QPen, QPainterPath
)
from PySide6.QtWidgets import QWidget, QApplication


class SplashScreen(QWidget):

    W, H = 760, 440

    def __init__(
        self,
        image_path: str = "",
        parent=None,
        accent=None,
        accent_color=None,
        subtitle: str = "",
    ) -> None:
        super().__init__(parent)

        self._pixmap = QPixmap(image_path) if image_path else QPixmap()
        self._progress: float = 0.0
        self._display_progress: float = 0.0
        self._message: str = ""
        self._phase: float = 0.0
        self._logo_opacity: float = 0.0

        self._subtitle = subtitle or ""
        colour_value = accent_color if accent_color is not None else accent
        if colour_value is None:
            colour_value = "#1DB954"
        if isinstance(colour_value, QColor):
            self._accent = colour_value
        elif isinstance(colour_value, str):
            self._accent = QColor(colour_value)
        else:
            self._accent = QColor(*colour_value)

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedSize(self.W, self.H)

        screen = QApplication.primaryScreen()
        if screen:
            sg = screen.geometry()
            self.move(sg.center().x() - self.W // 2, sg.center().y() - self.H // 2)

        self._timer = QTimer(self)
        self._timer.setInterval(30)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def _tick(self):
        self._phase = (self._phase + 0.018) % (2 * math.pi)
        if self._logo_opacity < 1.0:
            self._logo_opacity = min(1.0, self._logo_opacity + 0.04)

        gap = self._progress - self._display_progress
        if gap > 0.05:
            # Fark büyükse hızlı yaklaş, küçükse smooth animasyon.
            # Bu, hem ani progress güncellemelerini hissettirmez hem de
            # küçük adımları akıcı gösterir.
            # gap=30 → step≈4.5, gap=10 → step≈1.5, gap=2 → step≈0.8
            step = max(0.8, min(gap * 0.15, 4.5))
            self._display_progress = min(self._progress, self._display_progress + step)

        self.update()

    def set_progress(self, value: int, message=None) -> None:
        self._progress = float(max(0, min(100, int(value))))
        if message is not None:
            self._message = message
        self.update()

    def finish(self, widget=None) -> None:
        self._timer.stop()
        self.hide()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)

        W, H = self.W, self.H
        phase = self._phase
        acc = self._accent
        ar, ag, ab = acc.red(), acc.green(), acc.blue()

        # Rounded clip
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(0, 0, W, H), 20, 20)
        p.setClipPath(clip)
        p.fillRect(0, 0, W, H, QColor(6, 9, 16))

        # Aurora 1
        cx1 = W * (0.30 + 0.12 * math.sin(phase))
        cy1 = H * (0.50 + 0.10 * math.cos(phase * 0.7))
        g1 = QRadialGradient(cx1, cy1, W * 0.55)
        g1.setColorAt(0.0, QColor(ar, ag, ab, 60))
        g1.setColorAt(0.5, QColor(ar, ag, ab, 20))
        g1.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.fillRect(0, 0, W, H, QBrush(g1))

        # Aurora 2
        cx2 = W * (0.72 + 0.08 * math.cos(phase * 1.2))
        cy2 = H * (0.38 + 0.09 * math.sin(phase * 0.8))
        g2 = QRadialGradient(cx2, cy2, W * 0.40)
        g2.setColorAt(0.0, QColor(45, 136, 255, 35))
        g2.setColorAt(0.6, QColor(45, 136, 255, 8))
        g2.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.fillRect(0, 0, W, H, QBrush(g2))

        # Arka plan fotoğrafı (çok hafif)
        if not self._pixmap.isNull():
            scaled = self._pixmap.scaled(W, H, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            ox = (scaled.width() - W) // 2
            oy = (scaled.height() - H) // 2
            p.setOpacity(0.12)
            p.drawPixmap(0, 0, scaled, ox, oy, W, H)
            p.setOpacity(1.0)

        # Üst karartma
        tg = QLinearGradient(0, 0, 0, H * 0.5)
        tg.setColorAt(0.0, QColor(6, 9, 16, 190))
        tg.setColorAt(1.0, QColor(6, 9, 16, 0))
        p.fillRect(0, 0, W, H, QBrush(tg))

        # Alt karartma
        bg = QLinearGradient(0, H * 0.45, 0, H)
        bg.setColorAt(0.0, QColor(6, 9, 16, 0))
        bg.setColorAt(1.0, QColor(6, 9, 16, 230))
        p.fillRect(0, 0, W, H, QBrush(bg))

        # ── Logo ─────────────────────────────────────────────────────────────
        p.setOpacity(self._logo_opacity)

        # Üçgen play ikonu
        ix = W // 2 - 116
        iy = H // 2 - 50
        tri = QPainterPath()
        tri.moveTo(ix, iy)
        tri.lineTo(ix, iy + 30)
        tri.lineTo(ix + 24, iy + 15)
        tri.closeSubpath()
        p.setBrush(QBrush(acc))
        p.setPen(Qt.NoPen)
        p.drawPath(tri)

        # iqtMusic yazısı
        f_logo = QFont("Segoe UI Variable", 34, QFont.Black)
        p.setFont(f_logo)
        p.setPen(QColor(255, 255, 255))
        p.drawText(QRect(ix + 34, iy - 6, 320, 44), Qt.AlignLeft | Qt.AlignVCenter, "IQTMusic")

        # Alt başlık
        f_sub = QFont("Segoe UI", 10)
        p.setFont(f_sub)
        p.setPen(QColor(255, 255, 255, 90))
        p.drawText(QRect(ix + 36, iy + 40, 320, 22), Qt.AlignLeft, self._subtitle)

        p.setOpacity(1.0)

        # ── Progress bar ─────────────────────────────────────────────────────
        BAR_H = 3
        BAR_M = 50
        BAR_Y = H - 44
        bar_w = W - BAR_M * 2
        prog_w = int(bar_w * self._display_progress / 100.0)

        # Arka iz
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 20))
        p.drawRoundedRect(BAR_M, BAR_Y, bar_w, BAR_H, BAR_H / 2, BAR_H / 2)

        # Dolum
        if prog_w > 0:
            bar_grad = QLinearGradient(BAR_M, 0, BAR_M + bar_w, 0)
            bar_grad.setColorAt(0.0, QColor(ar, ag, ab, 180))
            bar_grad.setColorAt(1.0, QColor(ar, ag, ab, 255))
            p.setBrush(QBrush(bar_grad))
            p.drawRoundedRect(BAR_M, BAR_Y, prog_w, BAR_H, BAR_H / 2, BAR_H / 2)

            # Uç glow
            gr = 12
            glow = QRadialGradient(BAR_M + prog_w, BAR_Y + BAR_H // 2, gr)
            glow.setColorAt(0.0, QColor(ar, ag, ab, 140))
            glow.setColorAt(1.0, QColor(ar, ag, ab, 0))
            p.setBrush(QBrush(glow))
            p.drawEllipse(int(BAR_M + prog_w - gr), int(BAR_Y + BAR_H // 2 - gr), gr * 2, gr * 2)

        # Mesaj
        if self._message:
            f_msg = QFont("Segoe UI", 9)
            p.setFont(f_msg)
            p.setPen(QColor(255, 255, 255, 120))
            p.drawText(QRect(BAR_M, BAR_Y - 22, bar_w, 18), Qt.AlignLeft | Qt.AlignVCenter, self._message)
            p.setPen(QColor(ar, ag, ab, 210))
            p.drawText(QRect(BAR_M, BAR_Y - 22, bar_w, 18), Qt.AlignRight | Qt.AlignVCenter, f"%{int(self._display_progress)}")

        # Border
        pen = QPen(QColor(255, 255, 255, 15))
        pen.setWidthF(1.0)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(0.5, 0.5, W - 1, H - 1), 20, 20)

        p.end()


MusicSplashScreen = SplashScreen
