import logging
import weakref
log = logging.getLogger("iqtMusic")

from PySide6.QtWidgets import (
    QLabel, QFrame, QSlider, QPushButton, QWidget, QGraphicsDropShadowEffect,
    QGraphicsEffect
)
from PySide6.QtCore import (
    Qt, QPoint, QRect, QRectF, QPropertyAnimation, QEasingCurve, Signal, QTimer, QSize, Property
)
from PySide6.QtGui import QColor, QPainter, QLinearGradient, QBrush, QPen, QPainterPath, QPixmap

from core.theme import get_accent, get_accent_hover


# ─────────────────────────────────────────────────────────────────────────────
# GLOBAL SKELETON TIMER — Tüm SkeletonWidget'lar tek bir QTimer paylaşır.
# Önceki tasarımda her widget kendi 22ms timer'ını açıyordu; sayfada 20+
# skeleton varsa 20+ ayrı timer, 20x CPU yükü demek. Singleton timer ile
# tüm shimmer animasyonları tek bir tick'te güncellenir.
# ─────────────────────────────────────────────────────────────────────────────

_skeleton_timer: QTimer | None = None          # singleton QTimer
_skeleton_refs: list[weakref.ref] = []         # yaşayan skeleton'lara zayıf referanslar


def _skeleton_tick():
    """Global tick — tüm aktif skeleton widget'larını günceller."""
    alive: list[weakref.ref] = []
    for ref in _skeleton_refs:
        w = ref()
        if w is None:
            continue  # widget silinmiş, referansı at
        try:
            if not w._stopped:
                w._offset = (w._offset + 0.022) % 1.2
                w.update()
            alive.append(ref)
        except RuntimeError:
            pass  # C++ tarafı silinmiş
    _skeleton_refs[:] = alive
    # Hiç canlı skeleton kalmadıysa timer'ı durdur (CPU sıfırlanır)
    if not alive and _skeleton_timer is not None:
        _skeleton_timer.stop()


def _register_skeleton(widget: "SkeletonWidget"):
    """Yeni skeleton'u global timer'a kaydeder; gerekirse timer'ı başlatır."""
    global _skeleton_timer
    _skeleton_refs.append(weakref.ref(widget))
    if _skeleton_timer is None:
        _skeleton_timer = QTimer()
        _skeleton_timer.timeout.connect(_skeleton_tick)
    if not _skeleton_timer.isActive():
        _skeleton_timer.start(22)   # ~45 fps


class ClickableLabel(QLabel):
    clicked = Signal()
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setAttribute(Qt.WA_StyledBackground, True)
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(e)


class ClickableFrame(QFrame):
    clicked = Signal()
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setAttribute(Qt.WA_StyledBackground, True)
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(e)


class ClickableSlider(QSlider):
    seekRequested = Signal(int)

    def _value_from_pos(self, pos_x: float) -> int:
        usable = max(1, self.width() - 16)
        pos_x = max(0.0, min(float(pos_x) - 8.0, float(usable)))
        ratio = pos_x / usable
        return int(self.minimum() + ratio * (self.maximum() - self.minimum()))

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            val = self._value_from_pos(e.position().x())
            self.setSliderDown(True)
            self.setValue(val)
            self.sliderPressed.emit()
            self.sliderMoved.emit(val)
            e.accept()
            return
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.LeftButton:
            val = self._value_from_pos(e.position().x())
            self.setValue(val)
            self.sliderMoved.emit(val)
            e.accept()
            return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            val = self._value_from_pos(e.position().x())
            self.setValue(val)
            self.sliderMoved.emit(val)
            self.setSliderDown(False)
            self.sliderReleased.emit()
            self.seekRequested.emit(val)
            e.accept()
            return
        super().mouseReleaseEvent(e)


class DraggableFramelessWidget(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._drag_active = False
        self._drag_offset = QPoint()
        self._resize_active = False
        self._resize_edges = set()
        self._resize_start_geom = QRect()
        self._resize_start_pos = QPoint()
        # Kenardan pencere boyutlandırmayı kolaylaştırmak için margin değerini
        # arttırıyoruz. Önceden 8 piksel olan margin, pencereyi tutmayı
        # zorlaştırıyordu; bu değeri 12'ye çıkarmak kullanıcı deneyimini
        # iyileştirir.
        self._resize_margin = 12
        self._resize_callback = None
        self.setMouseTracking(True)
        self.setMinimumSize(230, 130)

    def _hit_edges(self, pos):
        r = self.rect()
        m = self._resize_margin
        edges = set()
        if pos.x() <= m:
            edges.add("left")
        elif pos.x() >= r.width() - m:
            edges.add("right")
        if pos.y() <= m:
            edges.add("top")
        elif pos.y() >= r.height() - m:
            edges.add("bottom")
        return edges

    def _apply_cursor(self, edges):
        if edges == {"left"} or edges == {"right"}:
            self.setCursor(Qt.SizeHorCursor)
        elif edges == {"top"} or edges == {"bottom"}:
            self.setCursor(Qt.SizeVerCursor)
        elif edges == {"left", "top"} or edges == {"right", "bottom"}:
            self.setCursor(Qt.SizeFDiagCursor)
        elif edges == {"right", "top"} or edges == {"left", "bottom"}:
            self.setCursor(Qt.SizeBDiagCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            edges = self._hit_edges(e.position().toPoint())
            if edges:
                self._resize_active = True
                self._resize_edges = edges
                self._resize_start_geom = self.geometry()
                self._resize_start_pos = e.globalPosition().toPoint()
                e.accept()
                return
            self._drag_active = True
            self._drag_offset = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            e.accept()
            return
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        pos = e.position().toPoint()
        if self._resize_active and (e.buttons() & Qt.LeftButton):
            delta = e.globalPosition().toPoint() - self._resize_start_pos
            g = QRect(self._resize_start_geom)
            min_w = max(self.minimumWidth(), 230)
            min_h = max(self.minimumHeight(), 130)
            if "left" in self._resize_edges:
                new_left = min(g.right() - min_w + 1, g.left() + delta.x())
                g.setLeft(new_left)
            if "right" in self._resize_edges:
                g.setWidth(max(min_w, self._resize_start_geom.width() + delta.x()))
            if "top" in self._resize_edges:
                new_top = min(g.bottom() - min_h + 1, g.top() + delta.y())
                g.setTop(new_top)
            if "bottom" in self._resize_edges:
                g.setHeight(max(min_h, self._resize_start_geom.height() + delta.y()))
            self.setGeometry(g.normalized())
            e.accept()
            return
        if self._drag_active and (e.buttons() & Qt.LeftButton):
            self.move(e.globalPosition().toPoint() - self._drag_offset)
            e.accept()
            return
        self._apply_cursor(self._hit_edges(pos))
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_active = False
            self._resize_active = False
            self._resize_edges = set()
            self._apply_cursor(self._hit_edges(e.position().toPoint()))
            e.accept()
            return
        super().mouseReleaseEvent(e)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        cb = getattr(self, "_resize_callback", None)
        if cb:
            try:
                cb()
            except Exception as _e:
                log.debug("Sessiz hata: %s", _e)


class _ScaleEffect(QGraphicsEffect):
    """
    QGraphicsEffect tabanlı scale animasyonu.
    sourcePixmap() ile widget'ı olduğu gibi yakalar, sonra ölçeklenmiş
    olarak çizer — CSS/stylesheet tamamen korunur.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.sv = 1.0          # public, no name-mangling

    def get_sv(self) -> float:
        return self.sv

    def set_sv(self, v: float):
        self.sv = v
        self.update()

    anim_scale = Property(float, get_sv, set_sv)

    def boundingRectFor(self, src: QRectF) -> QRectF:
        extra = max(src.width(), src.height()) * 0.15
        return src.adjusted(-extra, -extra, extra, extra)

    def draw(self, painter: QPainter):
        # offset = pixmap'in painter koordinatındaki pozisyonu (genellikle negatif, padding yüzünden)
        # Widget içeriği pixmap içinde (-offset.x, -offset.y) noktasından başlar.
        offset = QPoint()
        pm = self.sourcePixmap(Qt.LogicalCoordinates, offset)
        if pm.isNull():
            return
        s = self.sv
        src = self.sourceBoundingRect(Qt.LogicalCoordinates)
        w, h = src.width(), src.height()
        # Widget içeriğinin pixmap içindeki rect'i
        src_rect = QRectF(-offset.x(), -offset.y(), w, h)
        # Widget merkezinin painter koordinatındaki konumu
        cx = src.x() + w * 0.5
        cy = src.y() + h * 0.5
        sw, sh = w * s, h * s
        dst_rect = QRectF(cx - sw * 0.5, cy - sh * 0.5, sw, sh)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.drawPixmap(dst_rect, pm, src_rect)


class HoverScaleButton(QPushButton):
    """
    Hover'da widget içeriği smooth olarak büyür.
    CSS tamamen korunur — QGraphicsEffect kaynak widget'ı olduğu gibi render
    eder, sadece ölçeklenmiş pixmap çizer. PAD gerekmez.
    """
    _SCALE_MAX = 1.18
    _DURATION = 160

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__eff = _ScaleEffect()
        self.setGraphicsEffect(self.__eff)
        self.__anim = QPropertyAnimation(self.__eff, b"anim_scale")
        self.__anim.setDuration(self._DURATION)
        self.__anim.setEasingCurve(QEasingCurve.OutCubic)

    def enterEvent(self, event):
        super().enterEvent(event)
        self.raise_()
        self.__anim.stop()
        self.__anim.setStartValue(self.__eff.sv)
        self.__anim.setEndValue(self._SCALE_MAX)
        self.__anim.start()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.__anim.stop()
        self.__anim.setStartValue(self.__eff.sv)
        self.__anim.setEndValue(1.0)
        self.__anim.start()

    def setVisualSize(self, w: int, h: int | None = None):
        h = h if h is not None else w
        self.setFixedSize(w, h)


class SmoothCircleIconButton(HoverScaleButton):
    """Antialiased circular icon button for controls that must stay round."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._icon_offset = QPoint(0, 0)
        self.setAttribute(Qt.WA_StyledBackground, False)
        self.setStyleSheet("background:transparent; border:none; padding:0;")
        self.setFocusPolicy(Qt.NoFocus)

    def setIconOffset(self, x: int = 0, y: int = 0):
        self._icon_offset = QPoint(int(x), int(y))
        self.update()

    def enterEvent(self, event):
        super().enterEvent(event)
        self.update()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.update()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.update()

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self.update()

    def paintEvent(self, _):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        rect = QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)
        acc = QColor(get_accent())
        acc2 = QColor(get_accent_hover())
        if not acc.isValid():
            acc = QColor("#6EA8FF")
        if not acc2.isValid():
            acc2 = QColor("#9BCBFF")

        hover = self.underMouse()
        down = self.isDown()
        fill_alpha = 18
        ring_alpha = 76
        if hover:
            fill_alpha = 34
            ring_alpha = 130
        if down:
            fill_alpha = 52
            ring_alpha = 170

        fill = QColor(acc)
        fill.setAlpha(fill_alpha)
        ring = QColor(255, 255, 255, ring_alpha)
        if hover or down:
            ring = QColor(acc2)
            ring.setAlpha(ring_alpha)

        painter.setBrush(QBrush(fill))
        painter.setPen(QPen(ring, 1.25))
        painter.drawEllipse(rect)

        icon = self.icon()
        if not icon.isNull():
            icon_size = self.iconSize()
            offset = getattr(self, "_icon_offset", QPoint(0, 0))
            icon_rect = QRect(
                int((self.width() - icon_size.width()) / 2) + offset.x(),
                int((self.height() - icon_size.height()) / 2) + offset.y(),
                icon_size.width(),
                icon_size.height(),
            )
            icon.paint(painter, icon_rect, Qt.AlignCenter)


class GlowButton(QPushButton):
    """Hover'da glow efekti olan buton.

    PERFORMANS: Effect ve animasyon nesneleri artık ilk hover'da (lazy)
    oluşturuluyor. Daha önce her buton başlatılırken QGraphicsDropShadowEffect
    + QPropertyAnimation açılıyordu; bu GPU compositing katmanı demekti.
    Ekranda hiç hover yapılmayan butonlar için bu maliyet tamamen sıfıra iner.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._glow: QGraphicsDropShadowEffect | None = None
        self._anim: QPropertyAnimation | None = None

    def _ensure_glow(self):
        if self._glow is None:
            self._glow = QGraphicsDropShadowEffect(self)
            self._glow.setBlurRadius(0)
            self._glow.setOffset(0, 0)
            self._glow.setColor(QColor(get_accent()))
            self.setGraphicsEffect(self._glow)
            self._anim = QPropertyAnimation(self._glow, b"blurRadius")
            self._anim.setDuration(200)

    def enterEvent(self, e):
        self._ensure_glow()
        self._glow.setColor(QColor(get_accent()))
        self._anim.setStartValue(self._glow.blurRadius())
        self._anim.setEndValue(20)
        self._anim.start()
        super().enterEvent(e)

    def leaveEvent(self, e):
        if self._glow is not None:
            self._anim.setStartValue(self._glow.blurRadius())
            self._anim.setEndValue(0)
            self._anim.start()
        super().leaveEvent(e)


class SkeletonWidget(QWidget):
    """
    Animasyonlu shimmer (iskelet) yükleme göstergesi.

    Belirli bir genişlik/yükseklikte sabit tutulur; soldan sağa kayan
    bir ışık gradient'i ile Spotify/YouTube tarzı yükleme efekti verir.

    PERFORMANs: Artık her widget kendi QTimer'ını açmıyor.
    Tüm skeleton'lar modül seviyesindeki singleton _skeleton_timer'ı
    paylaşır; bu sayede n kart = 1 timer (önceden n timer).
    """

    def __init__(self, width: int = 180, height: int = 220,
                 radius: int = 14, parent=None):
        super().__init__(parent)
        self._radius  = radius
        self._offset  = 0.0      # shimmer pozisyonu
        self._stopped = False

        self.setFixedSize(QSize(width, height))
        _register_skeleton(self)  # global timer'a kaydol

    def paintEvent(self, _):
        if self._stopped:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        r     = self._radius

        # Zemin rengi
        base_col = QColor("#111827")
        p.setBrush(QBrush(base_col))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(0, 0, w, h, r, r)

        # Shimmer gradient: şeffaf → beyaz → şeffaf, sağa kayıyor
        shimmer_w = w * 0.55
        x0 = (self._offset - 0.4) * (w + shimmer_w) - shimmer_w
        x1 = x0 + shimmer_w

        grad = QLinearGradient(x0, 0, x1, 0)
        grad.setColorAt(0.0, QColor(255, 255, 255, 0))
        grad.setColorAt(0.4, QColor(255, 255, 255, 18))
        grad.setColorAt(0.5, QColor(255, 255, 255, 32))
        grad.setColorAt(0.6, QColor(255, 255, 255, 18))
        grad.setColorAt(1.0, QColor(255, 255, 255, 0))

        p.setBrush(QBrush(grad))
        p.drawRoundedRect(0, 0, w, h, r, r)
        p.end()

    def stop(self):
        """İçerik yüklenince animasyonu durdur (global tick'ten düşer)."""
        self._stopped = True
        self.update()  # son frame'i temizle


class AnimatedCard(ClickableFrame):
    """Hover'da gölge animasyonlu kart.

    PERFORMANS: QGraphicsDropShadowEffect artık constructor'da değil, ilk
    hover'da (lazy) oluşturuluyor. Her kart için baştan GPU compositing
    katmanı açmak çok pahalıydı; kullanıcı hover yapmadan geçtiği kartlar
    için bu maliyet artık sıfır.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._pos_anim = None
        self._shadow: QGraphicsDropShadowEffect | None = None  # lazy init

    def _ensure_shadow(self):
        if self._shadow is None:
            self._shadow = QGraphicsDropShadowEffect(self)
            self._shadow.setBlurRadius(0)
            self._shadow.setOffset(0, 4)
            self._shadow.setColor(QColor(0, 0, 0, 80))
            self.setGraphicsEffect(self._shadow)

    def enterEvent(self, e):
        """Hover üzerine geldiğinde kartın gölgesini ve rengini artır."""
        self._ensure_shadow()
        self._shadow.setBlurRadius(30)
        lighter = QColor(get_accent()).lighter(140)
        self._shadow.setColor(lighter)
        super().enterEvent(e)

    def leaveEvent(self, e):
        """Hover dışına çıkıldığında gölgeyi normal hâle getir."""
        if self._shadow is not None:
            self._shadow.setBlurRadius(0)
            self._shadow.setColor(QColor(0, 0, 0, 80))
        super().leaveEvent(e)


class TrackCoverWidget(QWidget):
    """Şarkı kapak görseli: KeepAspectRatio + merkez hizalama +
    yuvarlatılmış köşe + alt vinyette degradesi.

    Albüm kapağının tamamı görünür; kırpma yapılmaz.
    """

    def __init__(self, w: int, h: int, radius: int = 14, parent=None):
        super().__init__(parent)
        self._px: QPixmap | None = None
        self._radius = radius
        self.setFixedSize(w, h)
        self.setAttribute(Qt.WA_StyledBackground, False)
        self.setStyleSheet("background:transparent; border:none;")

    def setPixmap(self, px):  # noqa: N802 — QLabel API ile uyumlu
        self._px = px if isinstance(px, QPixmap) else None
        self.update()

    def clear(self):  # noqa: N802 — QLabel API ile uyumlu
        self._px = None
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)

        rect = self.rect().adjusted(1, 1, -1, -1)
        r = self._radius

        # Yuvarlatılmış kırpma maskesi
        clip = QPainterPath()
        clip.addRoundedRect(rect, r, r)
        p.setClipPath(clip)

        # Arka plan dolgusu
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(20, 24, 36))
        p.drawRoundedRect(rect, r, r)

        if self._px and not self._px.isNull():
            # KeepAspectRatioByExpanding + merkez kırpma — Discord gibi tam doldur
            from PySide6.QtCore import QSize as _QS
            scaled = self._px.scaled(
                _QS(rect.width(), rect.height()),
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation,
            )
            ox = (scaled.width() - rect.width()) // 2
            oy = (scaled.height() - rect.height()) // 2
            p.drawPixmap(rect.left(), rect.top(), scaled, ox, oy, rect.width(), rect.height())

            # Alt vinyette degradesi
            vign = QLinearGradient(0, float(rect.top()), 0, float(rect.bottom()))
            vign.setColorAt(0.0,  QColor(0, 0, 0, 0))
            vign.setColorAt(0.55, QColor(0, 0, 0, 0))
            vign.setColorAt(1.0,  QColor(0, 0, 0, 150))
            p.fillRect(rect, QBrush(vign))

        p.end()
