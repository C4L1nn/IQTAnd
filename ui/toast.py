import logging
log = logging.getLogger("iqtMusic")
"""Toast bildirim sistemi."""
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout, QLabel, QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint, QParallelAnimationGroup
from PySide6.QtGui import QColor

from core.constants import TEXT_PRIMARY, TEXT_SECONDARY
from core.theme import get_accent
from utils.helpers import create_icon


# Global state for toast queue and management
_toast_queue: list = []
_toast_active: bool = False
_toast_current = None


def show_toast(app, msg):
    """Bildirimi kuyruğa ekle; mevcut toast yoksa hemen göster."""
    global _toast_active, _toast_queue, _toast_current
    msg = _normalize_toast_payload(msg)
    _toast_queue.clear()
    _toast_queue.append(msg)
    if _toast_current is not None:
        try:
            if hasattr(_toast_current, "_dismiss_timer"):
                _toast_current._dismiss_timer.stop()
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
        try:
            _toast_current.hide()
            _toast_current.deleteLater()
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
        _toast_current = None
        _toast_active = False
    _show_next_toast(app)


def _clean_toast_message(msg: str) -> str:
    text = str(msg or "").strip()
    prefixes = (
        "✅ ", "⚠️ ", "❌ ", "⬇️ ", "🗑️ ", "≣ ", "➕ ", "⏱  ", "⏱ ",
        "📂 ", "🎵 ", "🔗 ",
    )
    changed = True
    while changed and text:
        changed = False
        for prefix in prefixes:
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
                changed = True
    return text


def _normalize_toast_payload(payload) -> dict:
    if isinstance(payload, dict):
        title = _clean_toast_message(payload.get("title") or payload.get("message") or "")
        message = _clean_toast_message(payload.get("message") or "")
        return {
            "title": title,
            "message": "" if message == title else message,
            "icon": str(payload.get("icon") or _toast_profile(title or message)[1] or "music"),
            "cover_url": str(payload.get("cover_url") or "").strip(),
        }

    text = _clean_toast_message(str(payload or ""))
    return {
        "title": text,
        "message": "",
        "icon": _toast_profile(text)[1],
        "cover_url": "",
    }


def _toast_profile(msg: str) -> tuple[str, str]:
    lower = (msg or "").lower()
    if "radyo" in lower:
        return "RADYO", "radio"
    if "indir" in lower:
        return "İNDİRME", "download"
    if "başarısız" in lower or "hata" in lower or "silindi" in lower:
        return "UYARI", "download"
    if "eklendi" in lower or "hazır" in lower or "oluşturuldu" in lower:
        return "GÜNCELLEME", "download_done"
    if "şarkı sözü" in lower or "sanatçı" in lower:
        return "MÜZİK", "mic"
    return "BİLDİRİM", "music"


def _toast_anchor_rect(app):
    if hasattr(app, "player_bar") and app.player_bar and app.player_bar.isVisible():
        top_left = app.player_bar.mapTo(app, QPoint(0, 0))
        return top_left.x(), top_left.y(), app.player_bar.width(), app.player_bar.height()
    if hasattr(app, "sidebar") and app.sidebar:
        left = app.sidebar.width()
        return left, 0, max(320, app.width() - left), app.height()
    return 0, 0, app.width(), app.height()


def _legacy_show_next_toast(app):
    """Kuyruktaki bir sonraki bildirimi göster."""
    global _toast_active, _toast_queue
    if not _toast_queue:
        _toast_active = False
        return
    _toast_active = True
    msg = _toast_queue.pop(0)

    acc = get_accent()

    # ── Çerçeve ─────────────────────────────────────────────────────────────
    toast = QFrame(app)
    toast.setObjectName("ToastFrame")
    toast.setAttribute(Qt.WA_TranslucentBackground, False)
    toast.setStyleSheet(f"""
        QFrame#ToastFrame {{
            background: #1C2333;
            border: 1px solid {acc}55;
            border-radius: 14px;
            border-left: 4px solid {acc};
        }}
    """)

    # Gölge
    shadow = QGraphicsDropShadowEffect(toast)
    shadow.setBlurRadius(28)
    shadow.setOffset(0, 6)
    shadow.setColor(QColor(0, 0, 0, 140))
    toast.setGraphicsEffect(shadow)

    # İç düzen: accent nokta + metin
    inner = QHBoxLayout(toast)
    inner.setContentsMargins(16, 12, 20, 12)
    inner.setSpacing(10)

    dot = QLabel()
    dot.setFixedSize(8, 8)
    dot.setStyleSheet(f"background:{acc}; border-radius:4px;")
    inner.addWidget(dot, 0, Qt.AlignVCenter)

    tl = QLabel(msg)
    tl.setStyleSheet(
        f"color:#EAEEFF; font-weight:700; font-size:13px; background:transparent;")
    tl.setMaximumWidth(320)
    tl.setWordWrap(True)
    inner.addWidget(tl, 1)

    # Boyutlandır ve konumlandır
    toast.adjustSize()
    toast.setMinimumWidth(260)
    r = app.rect()
    tw = max(toast.width(), 260)
    toast.resize(tw, toast.height())
    cx = (r.width() - tw) // 2
    y_show  = r.height() - 110
    y_start = r.height() - 60   # aşağıdan kayarak gelir

    toast.move(cx, y_start)
    toast.setWindowOpacity(0.0)
    toast.show()
    toast.raise_()

    # ── Slide-up + fade-in animasyonu ───────────────────────────────────────
    slide_in = QPropertyAnimation(toast, b"pos")
    slide_in.setDuration(220)
    slide_in.setEasingCurve(QEasingCurve.OutCubic)
    slide_in.setStartValue(toast.pos())
    slide_in.setEndValue(toast.pos().__class__(cx, y_show))

    fade_in = QPropertyAnimation(toast, b"windowOpacity")
    fade_in.setDuration(200)
    fade_in.setStartValue(0.0)
    fade_in.setEndValue(1.0)

    slide_in.start()
    fade_in.start()
    toast._anims = [slide_in, fade_in]

    # ── Fade-out + destroy ───────────────────────────────────────────────────
    def _fade_out():
        fade2 = QPropertyAnimation(toast, b"windowOpacity")
        fade2.setDuration(280)
        fade2.setStartValue(1.0)
        fade2.setEndValue(0.0)
        slide2 = QPropertyAnimation(toast, b"pos")
        slide2.setDuration(280)
        slide2.setEasingCurve(QEasingCurve.InCubic)
        slide2.setStartValue(toast.pos())
        slide2.setEndValue(toast.pos().__class__(cx, y_show + 20))

        def _done():
            toast.deleteLater()
            _show_next_toast(app)

        fade2.finished.connect(_done)
        fade2.start()
        slide2.start()
        toast._anims2 = [fade2, slide2]

    QTimer.singleShot(2800, _fade_out)


def _show_next_toast(app):
    """Kuyruktaki bir sonraki bildirimi goster."""
    global _toast_active, _toast_queue, _toast_current
    if not _toast_queue:
        _toast_active = False
        _toast_current = None
        return

    _toast_active = True
    payload = _toast_queue.pop(0)
    acc = get_accent()
    title = str(payload.get("title") or "").strip()
    message = str(payload.get("message") or "").strip()
    icon_name = str(payload.get("icon") or "music")
    cover_url = str(payload.get("cover_url") or "").strip()

    toast = QFrame(app)
    toast.setObjectName("ToastFrame")
    toast.setAttribute(Qt.WA_TransparentForMouseEvents, True)
    toast.setStyleSheet(f"""
        QFrame#ToastFrame {{
            background:qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 rgba(20,28,43,246),
                stop:0.62 rgba(17,24,39,250),
                stop:1 rgba(13,19,32,252));
            border:1px solid {acc}2C;
            border-radius:15px;
        }}
    """)

    shadow = QGraphicsDropShadowEffect(toast)
    shadow.setBlurRadius(16)
    shadow.setOffset(0, 8)
    glow_color = QColor(acc)
    glow_color.setAlpha(88)
    shadow.setColor(glow_color)
    toast.setGraphicsEffect(shadow)

    inner = QHBoxLayout(toast)
    inner.setContentsMargins(10, 8, 12, 8)
    inner.setSpacing(8)

    if cover_url:
        cover_chip = QFrame()
        cover_chip.setFixedSize(42, 42)
        cover_chip.setStyleSheet(f"""
            background: rgba(255,255,255,0.04);
            border: 1px solid {acc}38;
            border-radius: 12px;
        """)
        cover_l = QVBoxLayout(cover_chip)
        cover_l.setContentsMargins(0, 0, 0, 0)
        cover_lbl = QLabel()
        cover_lbl.setAlignment(Qt.AlignCenter)
        cover_lbl.setStyleSheet("background:transparent; border:none; border-radius:12px;")
        cover_l.addWidget(cover_lbl)
        inner.addWidget(cover_chip, 0, Qt.AlignVCenter)
        try:
            app._load_image(cover_url, cover_lbl, (42, 42))
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
    else:
        icon_chip = QFrame()
        icon_chip.setFixedSize(30, 30)
        icon_chip.setStyleSheet(f"""
            background:qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 {acc}30, stop:1 rgba(255,255,255,0.03));
            border:1px solid {acc}40;
            border-radius:10px;
        """)
        icon_l = QVBoxLayout(icon_chip)
        icon_l.setContentsMargins(0, 0, 0, 0)
        icon_lbl = QLabel()
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet("background:transparent; border:none;")
        icon_lbl.setPixmap(create_icon(icon_name, "#F5FAFF", 13).pixmap(13, 13))
        icon_l.addWidget(icon_lbl)
        inner.addWidget(icon_chip, 0, Qt.AlignVCenter)

    text_wrap = QVBoxLayout()
    text_wrap.setContentsMargins(0, 0, 0, 0)
    text_wrap.setSpacing(0)

    title_lbl = QLabel(title)
    title_lbl.setWordWrap(True)
    title_lbl.setStyleSheet(
        f"color:{TEXT_PRIMARY}; font-weight:800; font-size:12px; "
        "background:transparent; border:none;")
    text_wrap.addWidget(title_lbl)
    if message:
        body_lbl = QLabel(message)
        body_lbl.setWordWrap(True)
        body_lbl.setStyleSheet(
            f"color:{TEXT_SECONDARY}; font-weight:600; font-size:11px; "
            "background:transparent; border:none; margin-top:1px;")
        text_wrap.addWidget(body_lbl)
    inner.addLayout(text_wrap, 1)

    anchor_x, anchor_y, anchor_w, _anchor_h = _toast_anchor_rect(app)
    max_width = min(360, max(220, anchor_w - 28))
    min_width = min(max_width, 280)
    title_lbl.setMaximumWidth(max_width - 86)
    toast.setMinimumWidth(min_width)
    toast.setMaximumWidth(max_width)
    toast.adjustSize()

    tw = min(max(toast.width(), min_width), max_width)
    toast.resize(tw, toast.height())
    cx = anchor_x + max(8, (anchor_w - tw) // 2)
    if hasattr(app, "player_bar") and app.player_bar and app.player_bar.isVisible():
        y_show = max(18, anchor_y - toast.height() - 16)
        y_start = y_show + 12
    else:
        y_show = max(18, app.height() - toast.height() - 28)
        y_start = y_show + 10

    toast.move(cx, y_start)
    toast.setWindowOpacity(0.0)
    toast.show()
    toast.raise_()
    _toast_current = toast

    slide_in = QPropertyAnimation(toast, b"pos")
    slide_in.setDuration(190)
    slide_in.setEasingCurve(QEasingCurve.OutCubic)
    slide_in.setStartValue(toast.pos())
    slide_in.setEndValue(QPoint(cx, y_show))

    fade_in = QPropertyAnimation(toast, b"windowOpacity")
    fade_in.setDuration(150)
    fade_in.setStartValue(0.0)
    fade_in.setEndValue(1.0)

    blur_in = QPropertyAnimation(shadow, b"blurRadius")
    blur_in.setDuration(190)
    blur_in.setStartValue(8.0)
    blur_in.setEndValue(16.0)

    offset_in = QPropertyAnimation(shadow, b"yOffset")
    offset_in.setDuration(190)
    offset_in.setStartValue(10.0)
    offset_in.setEndValue(6.0)

    group_in = QParallelAnimationGroup(toast)
    group_in.addAnimation(slide_in)
    group_in.addAnimation(fade_in)
    group_in.addAnimation(blur_in)
    group_in.addAnimation(offset_in)
    group_in.start()
    toast._anims = [group_in, slide_in, fade_in, blur_in, offset_in]

    def _fade_out():
        fade2 = QPropertyAnimation(toast, b"windowOpacity")
        fade2.setDuration(180)
        fade2.setStartValue(1.0)
        fade2.setEndValue(0.0)

        slide2 = QPropertyAnimation(toast, b"pos")
        slide2.setDuration(180)
        slide2.setEasingCurve(QEasingCurve.InOutCubic)
        slide2.setStartValue(toast.pos())
        slide2.setEndValue(QPoint(cx, y_show - 4))

        blur2 = QPropertyAnimation(shadow, b"blurRadius")
        blur2.setDuration(180)
        blur2.setStartValue(shadow.blurRadius())
        blur2.setEndValue(6.0)

        def _done():
            global _toast_current, _toast_active
            _toast_current = None
            _toast_active = False
            toast.deleteLater()
            _show_next_toast(app)

        group_out = QParallelAnimationGroup(toast)
        group_out.addAnimation(fade2)
        group_out.addAnimation(slide2)
        group_out.addAnimation(blur2)
        group_out.finished.connect(_done)
        group_out.start()
        toast._anims2 = [group_out, fade2, slide2, blur2]

    toast._dismiss_timer = QTimer(toast)
    toast._dismiss_timer.setSingleShot(True)
    toast._dismiss_timer.timeout.connect(_fade_out)
    toast._dismiss_timer.start(2200)
