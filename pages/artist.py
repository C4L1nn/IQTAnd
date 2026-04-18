"""Sanatçı detay ve albüm sayfaları."""

import logging
import hashlib
import math

log = logging.getLogger("iqtMusic")
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QSizePolicy, QGridLayout, QMenu,
    QGraphicsBlurEffect, QGraphicsOpacityEffect, QDialog
)
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QPointF, QRectF, QSize
from PySide6.QtGui import (
    QColor, QPainter, QPainterPath, QFont, QCursor,
    QPixmap, QRadialGradient, QLinearGradient, QBrush, QPen,
    QConicalGradient
)

from core.constants import (
    BG_BLACK, BG_CARD, BG_CARD_HOVER, BG_ELEVATED, BORDER_COLOR,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED
)
from core.theme import get_accent, get_accent_hover
from utils.helpers import create_icon
from ui.widgets import ClickableFrame
from pages.common import _build_page_header, _scrollable


def _make_artist_row(app, track, album_name=""):
    """Birden fazla sanatçıyı ayrı ayrı tıklanabilir label olarak oluşturur."""
    from PySide6.QtCore import Qt
    entries = list(app._track_artist_entries(track) or [])
    if not entries:
        raw = app._artist_str(track)
        if raw:
            entries = [{"name": raw, "browseId": ""}]

    row_w = QWidget()
    row_w.setStyleSheet("background:transparent;")
    row_l = QHBoxLayout(row_w)
    row_l.setContentsMargins(0, 0, 0, 0)
    row_l.setSpacing(3)

    for i, entry in enumerate(entries):
        name = str(entry.get("name") or "").strip()
        if not name:
            continue
        lbl = QLabel(name)
        lbl.setAttribute(Qt.WA_Hover, True)
        lbl.setStyleSheet(
            f"QLabel{{font-size:11px; color:{TEXT_MUTED}; background:transparent;}}"
            f"QLabel:hover{{color:{TEXT_SECONDARY};}}"
        )
        lbl.setCursor(Qt.PointingHandCursor)
        lbl.mousePressEvent = lambda _, artist_entry=dict(entry): app._open_artist_entry(artist_entry)
        row_l.addWidget(lbl)
        if i < len(entries) - 1:
            sep = QLabel("·")
            sep.setStyleSheet(f"font-size:11px; color:{TEXT_MUTED}; background:transparent;")
            row_l.addWidget(sep)

    if album_name:
        dot = QLabel("  ·  " + album_name)
        dot.setStyleSheet(f"font-size:11px; color:{TEXT_MUTED}; background:transparent;")
        row_l.addWidget(dot)

    row_l.addStretch()
    return row_w


def _fmt_artist_metric(value: int) -> str:
    n = int(value or 0)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def _artist_metric_text(app, key: str, value) -> str:
    return app._tr(f"artist.metric.{key}", count=value)


def _artist_album_meta_text(app, track_count: int = 0, playcount: int = 0) -> str:
    if track_count:
        return _artist_metric_text(app, "tracks", track_count)
    if playcount:
        return _artist_metric_text(app, "playcount", _fmt_artist_metric(playcount))
    return app._tr("artist.album_default_label")


def _artist_album_sort_options(app) -> list[tuple[str, str]]:
    return [
        ("featured", app._tr("artist.album_sort.featured")),
        ("name", app._tr("artist.album_sort.name_asc")),
        ("year", app._tr("artist.album_sort.year_desc")),
        ("popularity", app._tr("artist.album_sort.popularity_desc")),
    ]


def _artist_album_sort_mode(app) -> str:
    mode = str(getattr(app, "_artist_album_sort_mode", "featured") or "featured").strip().lower()
    valid = {key for key, _ in _artist_album_sort_options(app)}
    return mode if mode in valid else "featured"


def _artist_album_sort_label(app) -> str:
    mode = _artist_album_sort_mode(app)
    for key, label in _artist_album_sort_options(app):
        if key == mode:
            return label
    return app._tr("artist.album_sort.featured")


def _artist_album_year_int(value) -> int:
    try:
        return int(str(value or "").strip()[:4])
    except Exception:
        return 0


def _sort_artist_album_items(app, items: list[dict]) -> list[dict]:
    albums = list(items or [])
    mode = _artist_album_sort_mode(app)
    if mode == "name":
        albums.sort(
            key=lambda item: (
                str(item.get("name", "") or "").casefold(),
                int(item.get("sort_index", 0) or 0),
            )
        )
    elif mode == "year":
        albums.sort(
            key=lambda item: (
                0 if int(item.get("year_int", 0) or 0) > 0 else 1,
                -(int(item.get("year_int", 0) or 0)),
                str(item.get("name", "") or "").casefold(),
            )
        )
    elif mode == "popularity":
        albums.sort(
            key=lambda item: (
                -(int(item.get("playcount", 0) or 0)),
                str(item.get("name", "") or "").casefold(),
                int(item.get("sort_index", 0) or 0),
            )
        )
    else:
        albums.sort(key=lambda item: int(item.get("sort_index", 0) or 0))
    return albums


def _apply_artist_album_sort(app, mode: str):
    clean_mode = str(mode or "featured").strip().lower() or "featured"
    if clean_mode == _artist_album_sort_mode(app):
        return
    app._artist_album_sort_mode = clean_mode
    payload = dict(getattr(app, "_current_nav_payload", {}) or {})
    if payload.get("type") != "artist":
        return
    app._set_active_nav("artists")
    app._show_page(
        build_artist_page(
            app,
            payload.get("tracks", []),
            payload.get("name", ""),
            payload.get("artist_meta", {}) or {},
        )
    )
    app._current_nav_payload = payload


def _find_artist_track_by_name(tracks: list, target_name: str):
    norm_target = str(target_name or "").strip().lower()
    if not norm_target:
        return None
    loose_match = None
    for track in tracks or []:
        if not isinstance(track, dict):
            continue
        title = str(track.get("title", "") or "").strip().lower()
        if not title:
            continue
        if title == norm_target:
            return track
        if loose_match is None and (norm_target in title or title in norm_target):
            loose_match = track
    return loose_match


def _lbl(text: str, style: str) -> QLabel:
    """Hızlı yardımcı QLabel oluşturucu."""
    w = QLabel(text)
    w.setStyleSheet(style)
    return w


def _name_color(name: str) -> str:
    """Sanatçı adından deterministik bir hex renk döndür."""
    _palette = [
        "#1DB954", "#E91E63", "#9C27B0", "#2196F3", "#FF5722",
        "#009688", "#FF9800", "#607D8B", "#3F51B5", "#00BCD4",
    ]
    h = int(hashlib.md5((name or "?").lower().encode()).hexdigest()[:8], 16)
    return _palette[h % len(_palette)]


class _HeroBg(QWidget):
    """Sanatçı hero arka plan — sinematik + animasyonlu.

    Düşük kaliteli fotoğrafları sinematik efektlerle maskeler:
    - Animated gradient aurora (fotoğraf yokken veya yüklenirken)
    - Akıllı blur+sharpen layering: arka plan blurlu, öne çıkan keskin
    - Yüksek opaklıkta renk overlay (renk bozukluklarını gizler)
    - Nefes alan parçacık/aura animasyonu
    - Smooth fade-in (fotoğraf yüklenince)
    - Çok katmanlı gradient vignette
    """
    def __init__(self, artist_name: str = "", accent: str = "#1DB954", parent=None):
        super().__init__(parent)
        self._px = None
        self._opacity = 0.0          # fade-in için
        self._aura_phase = 0.0       # animasyon fazı
        self._accent = QColor(accent)
        self._artist_name = artist_name

        # Sanatçı adından deterministik ikincil renk
        _palette = [
            "#E91E63", "#9C27B0", "#2196F3", "#FF5722",
            "#009688", "#FF9800", "#3F51B5", "#00BCD4",
        ]
        h = int(hashlib.md5((artist_name or "?").lower().encode()).hexdigest()[:8], 16)
        self._accent2 = QColor(_palette[h % len(_palette)])

        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background:#070B12; border:none;")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Aura animasyon timer'ı
        self._aura_timer = QTimer(self)
        self._aura_timer.setInterval(30)   # ~33fps
        self._aura_timer.timeout.connect(self._tick_aura)
        self._aura_timer.start()

    def _tick_aura(self):
        self._aura_phase = (self._aura_phase + 0.012) % (2 * math.pi)
        self.update()

    def setPixmap(self, px):
        if isinstance(px, QPixmap) and not px.isNull():
            self._px = px
            # Fade-in animasyonu: opacity 0 → 1 (800ms)
            self._fade_timer = QTimer(self)
            self._fade_timer.setInterval(16)
            self._fade_in_start = 0.0
            def _fade_step():
                self._opacity = min(1.0, self._opacity + 0.035)
                self.update()
                if self._opacity >= 1.0:
                    self._fade_timer.stop()
            self._fade_timer.timeout.connect(_fade_step)
            self._fade_timer.start()
        else:
            self._px = None
            self._opacity = 0.0
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)

        w, h = self.width(), self.height()
        phase = self._aura_phase
        acc  = self._accent
        acc2 = self._accent2

        # ── 1. Animated aurora base (fotoğraf yokken canlı arka plan) ────────
        cx1 = w * (0.65 + 0.08 * math.sin(phase))
        cy1 = h * (0.35 + 0.06 * math.cos(phase * 0.7))
        aurora1 = QRadialGradient(cx1, cy1, max(w, h) * 0.7)
        aurora1.setColorAt(0.0, QColor(acc.red(), acc.green(), acc.blue(), 45))
        aurora1.setColorAt(0.4, QColor(acc.red(), acc.green(), acc.blue(), 15))
        aurora1.setColorAt(1.0, QColor(7, 11, 18, 0))
        p.fillRect(0, 0, w, h, QBrush(aurora1))

        cx2 = w * (0.82 + 0.06 * math.cos(phase * 1.3))
        cy2 = h * (0.62 + 0.08 * math.sin(phase * 0.9))
        aurora2 = QRadialGradient(cx2, cy2, max(w, h) * 0.5)
        aurora2.setColorAt(0.0, QColor(acc2.red(), acc2.green(), acc2.blue(), 30))
        aurora2.setColorAt(0.5, QColor(acc2.red(), acc2.green(), acc2.blue(), 8))
        aurora2.setColorAt(1.0, QColor(7, 11, 18, 0))
        p.fillRect(0, 0, w, h, QBrush(aurora2))

        # ── 2. Fotoğraf — genişliği doldur, üstten hizala (yüz odaklı) ─────────
        if self._px is not None and not self._px.isNull() and self._opacity > 0:
            scaled = self._px.scaled(
                w, h,
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation,
            )
            draw_x = (w - scaled.width()) // 2
            draw_y = int((h - scaled.height()) * 0.12)

            p.setOpacity(self._opacity)
            p.drawPixmap(draw_x, draw_y, scaled)
            p.setOpacity(1.0)

            # ── 3. Hafif genel karartma (YouTube Music tarzı) ────────────────
            p.fillRect(0, 0, w, h, QColor(0, 0, 0, 60))

            # ── 4. Sol kenar fade (sadece kenar yumuşatma) ───────────────────
            grad_reveal = QLinearGradient(0, 0, max(1, int(w * 0.18)), 0)
            grad_reveal.setColorAt(0.00, QColor(7, 11, 18, 200))
            grad_reveal.setColorAt(1.00, QColor(7, 11, 18, 0))
            p.fillRect(0, 0, w, h, QBrush(grad_reveal))

            # ── 5. Sağ kenar fade (sadece kenar yumuşatma) ──────────────────
            grad_right = QLinearGradient(w, 0, max(0, int(w * 0.82)), 0)
            grad_right.setColorAt(0.00, QColor(7, 11, 18, 160))
            grad_right.setColorAt(1.00, QColor(7, 11, 18, 0))
            p.fillRect(0, 0, w, h, QBrush(grad_right))

        else:
            # Fotoğraf yok — sadece arka plan gradientini koru
            pass

        # ── 6. Alt vignette (metadata alanı için) ────────────────────────────
        grad_bt = QLinearGradient(0, h * 0.45, 0, h)
        grad_bt.setColorAt(0.00, QColor(7, 11, 18, 0))
        grad_bt.setColorAt(0.55, QColor(7, 11, 18, 150))
        grad_bt.setColorAt(1.00, QColor(7, 11, 18, 252))
        p.fillRect(0, 0, w, h, QBrush(grad_bt))

        # ── 7. Üst vignette (başlık çubuğu geçişi) ───────────────────────────
        grad_top = QLinearGradient(0, 0, 0, h * 0.20)
        grad_top.setColorAt(0.00, QColor(7, 11, 18, 140))
        grad_top.setColorAt(1.00, QColor(7, 11, 18, 0))
        p.fillRect(0, 0, w, h, QBrush(grad_top))

        p.end()


def _artist_visual_widget(app, tracks: list, artist_meta: dict):
    """Sanatçı detay sayfasının sağ köşesindeki fotoğraf widget'ı.

    Dairesel kırpma + parlayan halka + alt vignette ile şık bir önizleme sunar.
    """
    meta = artist_meta or {}
    hero_img = str(meta.get("image_url", "") or "").strip()
    acc = get_accent()

    CARD_W, CARD_H = 280, 280   # kare alan
    AVATAR_R = 118               # yarıçap (px)

    shell = QFrame()
    shell.setFixedSize(CARD_W, CARD_H)
    shell.setAttribute(Qt.WA_StyledBackground, True)
    shell.setStyleSheet("background:transparent; border:none;")

    class _CircularPhoto(QWidget):
        """Dairesel sanatçı fotoğrafı — glow halkası + vignette."""
        def __init__(self, radius: int, accent: str, parent=None):
            super().__init__(parent)
            self._r   = radius
            self._acc = accent
            self._px: QPixmap | None = None
            self.setFixedSize(radius * 2 + 20, radius * 2 + 20)
            self.setAttribute(Qt.WA_StyledBackground, False)
            self.setStyleSheet("background:transparent; border:none;")

        def setPixmap(self, px):
            self._px = px if isinstance(px, QPixmap) else None
            self.update()

        def paintEvent(self, ev):
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing)
            p.setRenderHint(QPainter.SmoothPixmapTransform)

            cx = self.width()  // 2
            cy = self.height() // 2
            r  = self._r
            ac = QColor(self._acc)

            # Glow halkası
            for glow_r, alpha in [(r + 14, 30), (r + 8, 55), (r + 4, 80)]:
                glow = QRadialGradient(cx, cy, glow_r)
                glow.setColorAt(0.72, QColor(ac.red(), ac.green(), ac.blue(), alpha))
                glow.setColorAt(1.00, QColor(0, 0, 0, 0))
                p.setBrush(QBrush(glow))
                p.setPen(Qt.NoPen)
                p.drawEllipse(cx - glow_r, cy - glow_r, glow_r * 2, glow_r * 2)

            # Dairesel clip
            clip = QPainterPath()
            clip.addEllipse(cx - r, cy - r, r * 2, r * 2)
            p.setClipPath(clip)

            if self._px and not self._px.isNull():
                scaled = self._px.scaled(r * 2, r * 2,
                    Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                ox = (scaled.width()  - r * 2) // 2
                oy = (scaled.height() - r * 2) // 2
                p.drawPixmap(cx - r, cy - r, scaled, ox, oy, r * 2, r * 2)

                # Alt vignette
                vign = QLinearGradient(0, cy, 0, cy + r)
                vign.setColorAt(0.0, QColor(0, 0, 0, 0))
                vign.setColorAt(0.6, QColor(0, 0, 0, 80))
                vign.setColorAt(1.0, QColor(0, 0, 0, 200))
                p.fillRect(cx - r, cy - r, r * 2, r * 2, QBrush(vign))
            else:
                # Placeholder gradient
                grad = QLinearGradient(cx - r, cy - r, cx + r, cy + r)
                grad.setColorAt(0.0, QColor(ac.red(), ac.green(), ac.blue(), 180))
                grad.setColorAt(1.0, QColor(
                    max(0, ac.red() - 60),
                    max(0, ac.green() - 60),
                    max(0, ac.blue() - 60), 220))
                p.setBrush(QBrush(grad))
                p.drawEllipse(cx - r, cy - r, r * 2, r * 2)

            p.setClipping(False)

            # Parlak ince halka
            pen = QPen(QColor(ac.red(), ac.green(), ac.blue(), 180))
            pen.setWidthF(2.5)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(cx - r + 1, cy - r + 1, r * 2 - 2, r * 2 - 2)

            p.end()

    photo = _CircularPhoto(AVATAR_R, acc, shell)
    photo.move(
        (CARD_W - photo.width())  // 2,
        (CARD_H - photo.height()) // 2,
    )

    if hero_img:
        # proxy label aracılığıyla yükle
        _proxy = QLabel(shell)
        _proxy.hide()
        _orig = _proxy.setPixmap
        def _fwd(px, _p=photo, _o=_orig):
            _o(px)
            if px and not px.isNull():
                _p.setPixmap(px)
        _proxy.setPixmap = _fwd
        app._load_image(hero_img, _proxy, (AVATAR_R * 2 + 20, AVATAR_R * 2 + 20))

    try:
        app._add_soft_shadow(shell, 40, QColor(0, 0, 0, 100), 0, 12)
    except Exception as _e:
        log.debug("Sessiz hata: %s", _e)

    return shell


def _artist_profile_hero(app, name: str, tracks: list, artist_meta: dict, subtitle: str) -> QWidget:
    """
    Sinematik sanatçı hero — düşük kaliteli fotoğrafı şık efektlerle maskeler.
    - Animated aurora arka plan (fotoğraf yüklenene kadar & altında)
    - Akıllı blur+sharp layering
    - Fade-in fotoğraf geçişi
    - Animasyonlu başlık opacity
    - Accent rengiyle dinamik istatistik pilleri
    """
    meta = artist_meta or {}
    acc  = get_accent()
    t = app._tr
    image_url = str(meta.get("image_url", "") or "").strip()

    hero = QFrame()
    hero.setObjectName("ArtistProfileHero")
    hero.setAttribute(Qt.WA_StyledBackground, True)
    hero.setFixedHeight(520)
    hero.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    hero.setStyleSheet("""
        QFrame#ArtistProfileHero {
            background: #070B12;
            border-radius: 28px;
            border: none;
        }
    """)

    gl = QGridLayout(hero)
    gl.setContentsMargins(0, 0, 0, 0)
    gl.setSpacing(0)

    # Animated hero background — sanatçı adı & accent rengiyle
    photo_bg = _HeroBg(artist_name=name, accent=acc)
    photo_bg.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    photo_bg.setStyleSheet("background:transparent; border:none;")
    if image_url:
        app._load_image(image_url, photo_bg, (900, 520))
    gl.addWidget(photo_bg, 0, 0)

    # İçerik katmanı
    content = QWidget()
    content.setAttribute(Qt.WA_TranslucentBackground, True)
    content.setStyleSheet("background: transparent; border: none;")
    content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    cl = QVBoxLayout(content)
    cl.setContentsMargins(44, 32, 44, 36)
    cl.setSpacing(10)
    cl.addStretch()

    # ── Sanatçı adı — fade-in animasyonlu ────────────────────────────────────
    title = QLabel(name)
    title.setWordWrap(True)
    title.setStyleSheet(
        "font-size:66px; font-weight:950; color:#FFFFFF; "
        "background:transparent; border:none; "
        "letter-spacing:0px;"
    )

    title_opacity_fx = QGraphicsOpacityEffect(title)
    title_opacity_fx.setOpacity(0.0)
    title.setGraphicsEffect(title_opacity_fx)
    _title_op_val = [0.0]

    def _fade_title():
        _title_op_val[0] = min(1.0, _title_op_val[0] + 0.045)
        title_opacity_fx.setOpacity(_title_op_val[0])
        if _title_op_val[0] >= 1.0:
            _title_fade_timer.stop()
            title.setGraphicsEffect(None)

    _title_fade_timer = QTimer(hero)
    _title_fade_timer.setInterval(20)
    _title_fade_timer.timeout.connect(_fade_title)
    QTimer.singleShot(80, _title_fade_timer.start)
    cl.addWidget(title)

    if subtitle:
        sub_lbl = QLabel(subtitle)
        sub_lbl.setWordWrap(True)
        sub_lbl.setStyleSheet(
            "font-size:14px; color:rgba(255,255,255,0.60); "
            "background:transparent; border:none;"
        )
        cl.addWidget(sub_lbl)

    # ── İstatistik pilleri — accent renkli ───────────────────────────────────
    stats = []
    if meta.get("listeners"):
        stats.append(_artist_metric_text(app, "listeners", _fmt_artist_metric(meta["listeners"])))
    if meta.get("subscribers"):
        stats.append(_artist_metric_text(app, "subscribers", meta["subscribers"]))
    if meta.get("playcount"):
        stats.append(_artist_metric_text(app, "playcount", _fmt_artist_metric(meta["playcount"])))
    yt_album_count = len(meta.get("yt_albums") or []) + len(meta.get("yt_singles") or [])
    lastfm_album_count = len(meta.get("top_albums") or [])
    album_count = yt_album_count or lastfm_album_count
    if album_count:
        stats.append(_artist_metric_text(app, "albums", album_count))
    if stats:
        sr = QHBoxLayout()
        sr.setSpacing(8)
        for i, text in enumerate(stats[:4]):
            pill = QLabel(text)
            if i == 0:
                pill.setStyleSheet(
                    f"background:{acc}28; color:{acc}; "
                    f"border:1px solid {acc}55; "
                    "border-radius:14px; padding:6px 14px; "
                    "font-size:11px; font-weight:800;"
                )
            else:
                pill.setStyleSheet(
                    "background:rgba(255,255,255,0.09); color:#FFFFFF; "
                    "border:1px solid rgba(255,255,255,0.16); "
                    "border-radius:14px; padding:6px 14px; "
                    "font-size:11px; font-weight:700;"
                )
            sr.addWidget(pill)
        sr.addStretch()
        cl.addLayout(sr)

    # ── Tür etiketleri ───────────────────────────────────────────────────────
    tags = [str(t).strip() for t in (meta.get("tags") or []) if str(t).strip()]
    if tags:
        tr = QHBoxLayout()
        tr.setSpacing(8)
        for tag in tags[:5]:
            pill = QLabel(tag.capitalize())
            pill.setStyleSheet(
                f"background:{acc}18; color:rgba(255,255,255,0.80); "
                f"border:1px solid {acc}30; "
                "border-radius:13px; padding:5px 11px; "
                "font-size:11px; font-weight:800;"
            )
            tr.addWidget(pill)
        tr.addStretch()
        cl.addLayout(tr)

    # ── Aksiyon butonları ─────────────────────────────────────────────────────
    actions = QHBoxLayout()
    actions.setSpacing(10)

    play_btn = QPushButton(t("artist.play"))
    play_btn.setCursor(Qt.PointingHandCursor)
    play_btn.setEnabled(bool(tracks))
    play_btn.setStyleSheet(f"""
        QPushButton {{
            background: {acc};
            color: #061008;
            border: none;
            border-radius: 22px;
            padding: 13px 28px;
            font-size: 14px;
            font-weight: 900;
        }}
        QPushButton:hover {{ background: {get_accent_hover()}; }}
        QPushButton:disabled {{
            background: rgba(255,255,255,0.06);
            color: rgba(255,255,255,0.28);
        }}
    """)
    play_btn.clicked.connect(lambda: app._play_artist_only(list(tracks)) if tracks else None)
    actions.addWidget(play_btn)

    def _shuffle_artist():
        if not tracks:
            return
        import random
        shuffled = list(tracks)
        random.shuffle(shuffled)
        app._play_artist_only(shuffled)

    shuffle_btn = QPushButton(t("artist.shuffle"))
    shuffle_btn.setCursor(Qt.PointingHandCursor)
    shuffle_btn.setEnabled(bool(tracks))
    shuffle_btn.setStyleSheet(f"""
        QPushButton {{
            background: rgba(255,255,255,0.08);
            color: #FFFFFF;
            border: 1px solid rgba(255,255,255,0.18);
            border-radius: 22px;
            padding: 13px 22px;
            font-size: 14px;
            font-weight: 800;
        }}
        QPushButton:hover {{
            background: rgba(255,255,255,0.16);
            border-color: rgba(255,255,255,0.32);
        }}
        QPushButton:disabled {{ color: rgba(255,255,255,0.24); }}
    """)
    shuffle_btn.clicked.connect(_shuffle_artist)
    actions.addWidget(shuffle_btn)

    is_liked = app._is_artist_liked(name)
    like_btn = QPushButton()
    like_btn.setFixedSize(46, 46)
    like_btn.setCursor(Qt.PointingHandCursor)
    like_btn.setFocusPolicy(Qt.NoFocus)
    like_btn.setIcon(create_icon("heart_on" if is_liked else "heart_off", acc if is_liked else "#FFFFFF", 20))
    like_btn.setIconSize(QSize(20, 20))
    like_btn.setToolTip(t("artist.unlike" if is_liked else "artist.like"))
    like_btn.setStyleSheet(f"""
        QPushButton {{
            background: rgba(255,255,255,0.08);
            color: #FFFFFF;
            border: 1px solid rgba(255,255,255,0.18);
            border-radius: 23px;
        }}
        QPushButton:hover {{
            background: {acc}20;
            border-color: {acc}66;
        }}
    """)
    like_btn.clicked.connect(lambda: app._toggle_artist_like(name, str(meta.get("browseId") or meta.get("channelId") or ""), meta, like_btn))
    actions.addWidget(like_btn)
    actions.addStretch()
    cl.addLayout(actions)

    gl.addWidget(content, 0, 0)
    return hero


def _artist_popular_panel(
    app,
    tracks: list,
    artist_meta: dict,
    title_key: str = "artist.popular",
    limit: int | None = 10,
    show_all_button: bool = False,
) -> QWidget:
    acc = get_accent()
    t = app._tr
    panel = QFrame()
    panel.setObjectName("ArtistPopularPanel")
    panel.setAttribute(Qt.WA_StyledBackground, True)
    panel.setStyleSheet(f"""
        QFrame#ArtistPopularPanel {{
            background:qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 rgba(255,255,255,0.02), stop:1 {BG_CARD});
            border-radius:24px;
            border:1px solid {BORDER_COLOR};
        }}
        QFrame#ArtistPopularPanel QLabel {{
            background:transparent;
            border:none;
        }}
    """)

    outer = QVBoxLayout(panel)
    outer.setContentsMargins(20, 18, 20, 18)
    outer.setSpacing(10)

    head = QHBoxLayout()
    head.setContentsMargins(0, 0, 0, 0)
    head.setSpacing(10)
    title = QLabel(t(title_key))
    title.setStyleSheet(f"font-size:26px; font-weight:900; color:{TEXT_PRIMARY};")
    head.addWidget(title)
    head.addStretch()
    has_more = show_all_button and limit is not None and len(tracks or []) > int(limit)
    see_all_btn = None
    if has_more:
        see_all_btn = QPushButton(t("artist.show_all_tracks"))
        see_all_btn.setCursor(Qt.PointingHandCursor)
        see_all_btn.setStyleSheet(f"""
            QPushButton {{
                background:rgba(255,255,255,0.05);
                color:{TEXT_PRIMARY};
                border:1px solid rgba(255,255,255,0.10);
                border-radius:15px;
                padding:8px 14px;
                font-size:12px;
                font-weight:850;
            }}
            QPushButton:hover {{
                color:{acc};
                border-color:{acc}55;
                background:{acc}14;
            }}
        """)
        head.addWidget(see_all_btn)
    outer.addLayout(head)

    meta_tracks = {}
    for item in list((artist_meta or {}).get("top_tracks") or []):
        if not isinstance(item, dict):
            continue
        norm = str(item.get("name", "") or "").strip().lower()
        if norm:
            meta_tracks[norm] = item

    if not tracks:
        empty = QLabel(t("artist.no_tracks"))
        empty.setStyleSheet(f"font-size:13px; color:{TEXT_MUTED};")
        outer.addWidget(empty)
        return panel

    visible_tracks = list(tracks or [])
    if limit is not None:
        visible_tracks = visible_tracks[:max(1, int(limit))]
    extra_tracks = list(tracks or [])[len(visible_tracks):] if has_more else []

    for index, track in enumerate(visible_tracks, start=1):
        row = ClickableFrame()
        row.setObjectName("ArtistPopularRow")
        row.setFixedHeight(74)
        row.setStyleSheet(f"""
            QFrame#ArtistPopularRow {{
                background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {BG_CARD}, stop:1 {BG_ELEVATED});
                border-radius:16px;
                border:1px solid {BORDER_COLOR};
            }}
            QFrame#ArtistPopularRow:hover {{
                background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {BG_CARD_HOVER}, stop:1 {BG_ELEVATED});
                border-color:{acc}44;
            }}
        """)
        rl = QHBoxLayout(row)
        rl.setContentsMargins(14, 10, 14, 10)
        rl.setSpacing(12)

        idx_lbl = QLabel(str(index))
        idx_lbl.setFixedWidth(24)
        idx_lbl.setAlignment(Qt.AlignCenter)
        idx_lbl.setStyleSheet(f"color:{TEXT_MUTED}; font-size:16px; font-weight:700;")

        img = QLabel()
        img.setFixedSize(50, 50)
        img.setAlignment(Qt.AlignCenter)
        img.setStyleSheet("background:#121926; border-radius:10px;")
        track_title_norm = str(track.get("title", "") or "").strip().lower()
        top_meta = meta_tracks.get(track_title_norm, {})
        if not top_meta and track_title_norm:
            for candidate_name, candidate_meta in meta_tracks.items():
                if track_title_norm in candidate_name or candidate_name in track_title_norm:
                    top_meta = candidate_meta
                    break
        thumb = app._thumb(track, big=True)
        if not thumb:
            thumb = str(top_meta.get("image_url", "") or "").strip()
        if thumb:
            app._load_image(thumb, img, (50, 50))
        else:
            try:
                img.setPixmap(create_icon("music", TEXT_MUTED, 26).pixmap(26, 26))
            except Exception as _e:
                log.debug("Sessiz hata: %s", _e)

        info = QVBoxLayout()
        info.setContentsMargins(0, 0, 0, 0)
        info.setSpacing(3)
        title_lbl = QLabel(track.get("title", t("artist.unknown")))
        title_lbl.setStyleSheet(f"font-size:14px; font-weight:850; color:{TEXT_PRIMARY};")
        album_name = ""
        album_obj = track.get("album")
        if isinstance(album_obj, dict):
            album_name = str(album_obj.get("name", "") or "").strip()
        elif isinstance(album_obj, str):
            album_name = str(album_obj or "").strip()
        info.addWidget(title_lbl)
        info.addWidget(_make_artist_row(app, track, album_name))

        right = QHBoxLayout()
        right.setSpacing(14)

        playcount = int(top_meta.get("playcount", 0) or 0)
        listeners = int(top_meta.get("listeners", 0) or 0)
        if playcount:
            count_lbl = QLabel(_fmt_artist_metric(playcount))
            count_lbl.setFixedWidth(72)
            count_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            count_lbl.setStyleSheet(f"font-size:12px; font-weight:700; color:{TEXT_SECONDARY};")
            right.addWidget(count_lbl)
        elif listeners:
            count_lbl = QLabel(_artist_metric_text(app, "listeners", _fmt_artist_metric(listeners)))
            count_lbl.setFixedWidth(96)
            count_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            count_lbl.setStyleSheet(f"font-size:12px; font-weight:700; color:{TEXT_SECONDARY};")
            right.addWidget(count_lbl)

        duration_text = ""
        try:
            duration_sec = int(track.get("duration_seconds") or 0)
            if duration_sec > 0:
                duration_text = app._fmt(duration_sec * 1000)
        except Exception:
            duration_text = ""
        dur_lbl = QLabel(duration_text or "--:--")
        dur_lbl.setFixedWidth(44)
        dur_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        dur_lbl.setStyleSheet(f"font-size:12px; color:{TEXT_MUTED};")
        right.addWidget(dur_lbl)

        play_btn = QPushButton()
        play_btn.setFixedSize(30, 30)
        play_btn.setCursor(Qt.PointingHandCursor)
        play_btn.setIcon(create_icon("play", acc, 16))
        from PySide6.QtCore import QSize
        play_btn.setIconSize(QSize(16, 16))
        play_btn.setStyleSheet(
            f"QPushButton{{background:transparent; border:none; border-radius:15px;}}"
            f"QPushButton:hover{{background:{acc}18;}}"
        )
        play_btn.clicked.connect(lambda _, t=track: app.force_play(t))
        right.addWidget(play_btn)

        rl.addWidget(idx_lbl)
        rl.addWidget(img)
        rl.addLayout(info, 1)
        rl.addLayout(right)

        row.clicked.connect(lambda t=track: app.force_play(t))
        row.setContextMenuPolicy(Qt.CustomContextMenu)
        row.customContextMenuRequested.connect(lambda _, t=track: app._ctx_menu(QCursor.pos(), t))
        outer.addWidget(row)

    if extra_tracks:
        extra_wrap = QWidget()
        extra_wrap.setStyleSheet("background:transparent; border:none;")
        extra_wrap.hide()
        extra_vl = QVBoxLayout(extra_wrap)
        extra_vl.setContentsMargins(0, 0, 0, 0)
        extra_vl.setSpacing(10)
        base_offset = len(visible_tracks)
        for idx2, track2 in enumerate(extra_tracks, start=base_offset + 1):
            row2 = ClickableFrame()
            row2.setObjectName("ArtistPopularRow")
            row2.setFixedHeight(74)
            row2.setStyleSheet(f"""
                QFrame#ArtistPopularRow {{
                    background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
                        stop:0 {BG_CARD}, stop:1 {BG_ELEVATED});
                    border-radius:16px;
                    border:1px solid {BORDER_COLOR};
                }}
                QFrame#ArtistPopularRow:hover {{
                    background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
                        stop:0 {BG_CARD_HOVER}, stop:1 {BG_ELEVATED});
                    border-color:{acc}44;
                }}
            """)
            rl2 = QHBoxLayout(row2)
            rl2.setContentsMargins(14, 10, 14, 10)
            rl2.setSpacing(12)
            idx_lbl2 = QLabel(str(idx2))
            idx_lbl2.setFixedWidth(24)
            idx_lbl2.setAlignment(Qt.AlignCenter)
            idx_lbl2.setStyleSheet(f"color:{TEXT_MUTED}; font-size:16px; font-weight:700;")
            img2 = QLabel()
            img2.setFixedSize(50, 50)
            img2.setAlignment(Qt.AlignCenter)
            img2.setStyleSheet("background:#121926; border-radius:10px;")
            thumb2 = app._thumb(track2, big=True)
            if thumb2:
                app._load_image(thumb2, img2, (50, 50))
            else:
                try:
                    img2.setPixmap(create_icon("music", TEXT_MUTED, 26).pixmap(26, 26))
                except Exception:
                    pass
            info2 = QVBoxLayout()
            info2.setContentsMargins(0, 0, 0, 0)
            info2.setSpacing(3)
            title_lbl2 = QLabel(track2.get("title", t("artist.unknown")))
            title_lbl2.setStyleSheet(f"font-size:14px; font-weight:850; color:{TEXT_PRIMARY};")
            album_obj2 = track2.get("album")
            album_name2 = ""
            if isinstance(album_obj2, dict):
                album_name2 = str(album_obj2.get("name", "") or "").strip()
            elif isinstance(album_obj2, str):
                album_name2 = str(album_obj2 or "").strip()
            info2.addWidget(title_lbl2)
            info2.addWidget(_make_artist_row(app, track2, album_name2))
            right2 = QHBoxLayout()
            right2.setSpacing(14)
            dur_sec2 = int(track2.get("duration_seconds") or 0)
            dur_text2 = app._fmt(dur_sec2 * 1000) if dur_sec2 > 0 else "--:--"
            dur_lbl2 = QLabel(dur_text2)
            dur_lbl2.setFixedWidth(44)
            dur_lbl2.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            dur_lbl2.setStyleSheet(f"font-size:12px; color:{TEXT_MUTED};")
            right2.addWidget(dur_lbl2)
            play_btn2 = QPushButton()
            play_btn2.setFixedSize(30, 30)
            play_btn2.setCursor(Qt.PointingHandCursor)
            play_btn2.setIcon(create_icon("play", acc, 16))
            from PySide6.QtCore import QSize as _QSize
            play_btn2.setIconSize(_QSize(16, 16))
            play_btn2.setStyleSheet(
                f"QPushButton{{background:transparent; border:none; border-radius:15px;}}"
                f"QPushButton:hover{{background:{acc}18;}}"
            )
            play_btn2.clicked.connect(lambda _, tr=track2: app.force_play(tr))
            right2.addWidget(play_btn2)
            rl2.addWidget(idx_lbl2)
            rl2.addWidget(img2)
            rl2.addLayout(info2, 1)
            rl2.addLayout(right2)
            row2.clicked.connect(lambda tr=track2: app.force_play(tr))
            row2.setContextMenuPolicy(Qt.CustomContextMenu)
            row2.customContextMenuRequested.connect(lambda _, tr=track2: app._ctx_menu(QCursor.pos(), tr))
            extra_vl.addWidget(row2)
        outer.addWidget(extra_wrap)

        def _toggle_extra():
            if extra_wrap.isHidden():
                extra_wrap.show()
                see_all_btn.setText(t("artist.show_less_tracks"))
            else:
                extra_wrap.hide()
                see_all_btn.setText(t("artist.show_all_tracks"))
        see_all_btn.clicked.connect(_toggle_extra)

    return panel


def _open_artist_all_tracks_dialog(app, tracks: list, artist_meta: dict):
    if not tracks:
        return
    dlg = QDialog(app)
    dlg.setWindowTitle(app._tr("artist.all_tracks"))
    dlg.resize(900, 720)
    dlg.setStyleSheet(f"""
        QDialog {{
            background:{BG_BLACK};
            color:{TEXT_PRIMARY};
        }}
    """)
    root = QVBoxLayout(dlg)
    root.setContentsMargins(18, 18, 18, 18)
    root.setSpacing(14)

    header = QHBoxLayout()
    title = QLabel(app._tr("artist.all_tracks"))
    title.setStyleSheet(f"font-size:26px; font-weight:950; color:{TEXT_PRIMARY};")
    close_btn = QPushButton("X")
    close_btn.setFixedSize(36, 36)
    close_btn.setCursor(Qt.PointingHandCursor)
    close_btn.setStyleSheet(f"""
        QPushButton {{
            background:rgba(255,255,255,0.05);
            color:{TEXT_SECONDARY};
            border:1px solid rgba(255,255,255,0.10);
            border-radius:18px;
            font-size:13px;
            font-weight:900;
        }}
        QPushButton:hover {{
            color:{get_accent()};
            border-color:{get_accent()}55;
        }}
    """)
    close_btn.clicked.connect(dlg.close)
    header.addWidget(title)
    header.addStretch()
    header.addWidget(close_btn)
    root.addLayout(header)

    sc = QScrollArea()
    sc.setWidgetResizable(True)
    sc.setFrameShape(QFrame.NoFrame)
    sc.setStyleSheet("background:transparent; border:none;")
    holder = QWidget()
    holder.setStyleSheet("background:transparent;")
    holder_l = QVBoxLayout(holder)
    holder_l.setContentsMargins(0, 0, 0, 0)
    holder_l.setSpacing(0)
    holder_l.addWidget(_artist_popular_panel(app, tracks, artist_meta, "artist.all_tracks", None, False))
    sc.setWidget(holder)
    root.addWidget(sc, 1)
    dlg.exec()


def _artist_album_items(app, tracks: list, artist_meta: dict) -> list[dict]:
    items = []
    seen  = set()
    artist_name = str((artist_meta or {}).get("name", "") or "").strip()
    sort_index = 0

    # ── Önce YTMusic albümleri (browseId ile — direkt ve hızlı) ─────────────
    for album in (artist_meta or {}).get("yt_albums") or []:
        if not isinstance(album, dict):
            continue
        name = str(album.get("title", "") or "").strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        album_type  = str(album.get("type", "Album") or "Album")
        browse_id   = str(album.get("browseId", "") or "").strip()
        year        = str(album.get("year", "") or "").strip()
        thumbs      = album.get("thumbnails") or []
        image_url   = ""
        if thumbs:
            best = max(thumbs, key=lambda t: t.get("width", 0) * t.get("height", 0), default=None)
            if best:
                image_url = best.get("url", "")
        seen.add(key)
        meta_parts = []
        if year:
            meta_parts.append(year)
        meta_parts.append(album_type)
        items.append({
            "name":        name,
            "artist_name": artist_name,
            "image_url":   image_url,
            "browse_id":   browse_id,
            "album_type":  album_type,
            "group":       "album",
            "year":        year,
            "year_int":    _artist_album_year_int(year),
            "playcount":   0,
            "track_count": 0,
            "sort_index":  sort_index,
            "meta":        " · ".join(meta_parts),
        })
        sort_index += 1

    # ── YTMusic single ve EP'leri de diskografiye ekle ─────────────────────
    for album in (artist_meta or {}).get("yt_singles") or []:
        if not isinstance(album, dict):
            continue
        name = str(album.get("title", "") or "").strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        album_type = str(album.get("type") or app._tr("artist.single_label"))
        browse_id = str(album.get("browseId", "") or "").strip()
        year = str(album.get("year", "") or "").strip()
        thumbs = album.get("thumbnails") or []
        image_url = ""
        if thumbs:
            best = max(thumbs, key=lambda t: t.get("width", 0) * t.get("height", 0), default=None)
            if best:
                image_url = best.get("url", "")
        seen.add(key)
        meta_parts = []
        if year:
            meta_parts.append(year)
        meta_parts.append(album_type)
        try:
            track_count = int(album.get("trackCount") or album.get("track_count") or 1)
        except Exception:
            track_count = 1
        items.append({
            "name":        name,
            "artist_name": artist_name,
            "image_url":   image_url,
            "browse_id":   browse_id,
            "album_type":  album_type,
            "group":       "single",
            "year":        year,
            "year_int":    _artist_album_year_int(year),
            "playcount":   0,
            "track_count": track_count,
            "sort_index":  sort_index,
            "meta":        " · ".join(meta_parts),
        })
        sort_index += 1

    # ── Sonra Last.fm albümleri (YTMusic'te olmayan varsa ekle) ─────────────
    for album in (artist_meta or {}).get("top_albums") or []:
        if not isinstance(album, dict):
            continue
        name = str(album.get("name", "") or "").strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        track_count = int(album.get("track_count", 0) or 0)
        if track_count == 1:
            continue
        playcount = int(album.get("playcount", 0) or 0)
        seen.add(key)
        items.append({
            "name":        name,
            "artist_name": artist_name,
            "image_url":   str(album.get("image_url", "") or "").strip(),
            "browse_id":   "",
            "album_type":  app._tr("artist.album_default_label"),
            "group":       "album",
            "year":        "",
            "year_int":    0,
            "playcount":   playcount,
            "track_count": track_count,
            "sort_index":  sort_index,
            "meta": _artist_album_meta_text(app, track_count, playcount),
        })
        sort_index += 1
    return items


def _artist_albums_strip(app, tracks: list, artist_meta: dict) -> QWidget | None:
    albums = _sort_artist_album_items(app, _artist_album_items(app, tracks, artist_meta))
    if not albums:
        return None

    acc = get_accent()
    t = app._tr
    panel = QFrame()
    panel.setObjectName("ArtistAlbumsPanelV2")
    panel.setAttribute(Qt.WA_StyledBackground, True)
    panel.setStyleSheet(f"""
        QFrame#ArtistAlbumsPanelV2 {{
            background:qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 rgba(255,255,255,0.022), stop:1 {BG_CARD});
            border-radius:24px;
            border:1px solid {BORDER_COLOR};
        }}
        QFrame#ArtistAlbumsPanelV2 QLabel {{
            background:transparent;
            border:none;
        }}
        QScrollArea {{
            background:transparent;
            border:none;
        }}
        QScrollBar:horizontal {{
            background:transparent;
            height:10px;
            margin:4px 0 0 0;
        }}
        QScrollBar::handle:horizontal {{
            background:{acc}55;
            min-width:44px;
            border-radius:5px;
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
            background:transparent;
            border:none;
        }}
    """)

    outer = QVBoxLayout(panel)
    outer.setContentsMargins(20, 18, 20, 16)
    outer.setSpacing(12)

    head = QHBoxLayout()
    head.setSpacing(10)
    has_yt = bool((artist_meta or {}).get("yt_albums") or (artist_meta or {}).get("yt_singles"))
    title = QLabel(t("artist.discography") if has_yt else t("artist.albums"))
    title.setStyleSheet(f"font-size:26px; font-weight:900; color:{TEXT_PRIMARY};")
    sub = QLabel(
        t("artist.albums_with_singles") if has_yt
        else t("artist.albums_desc")
    )
    sub.setStyleSheet(f"font-size:12px; color:{TEXT_MUTED};")
    head_text = QVBoxLayout()
    head_text.setContentsMargins(0, 0, 0, 0)
    head_text.setSpacing(2)
    head_text.addWidget(title)
    head_text.addWidget(sub)
    head.addLayout(head_text)
    head.addStretch()

    sort_wrap = QHBoxLayout()
    sort_wrap.setContentsMargins(0, 0, 0, 0)
    sort_wrap.setSpacing(8)

    sort_lbl = QLabel(t("artist.album_sort.label"))
    sort_lbl.setStyleSheet(f"font-size:11px; font-weight:700; color:{TEXT_MUTED};")
    sort_wrap.addWidget(sort_lbl)

    sort_btn = QPushButton(_artist_album_sort_label(app))
    sort_btn.setCursor(Qt.PointingHandCursor)
    sort_btn.setStyleSheet(f"""
        QPushButton {{
            background:rgba(255,255,255,0.04);
            color:{TEXT_PRIMARY};
            border:1px solid rgba(255,255,255,0.08);
            border-radius:14px;
            padding:8px 14px;
            font-size:12px;
            font-weight:800;
            text-align:left;
        }}
        QPushButton:hover {{
            border-color:{acc}44;
            color:{acc};
        }}
    """)
    sort_menu = QMenu(sort_btn)
    sort_menu.setStyleSheet(f"""
        QMenu {{
            background:#0E1B31;
            border:1px solid #1A2B49;
            border-radius:10px;
            padding:5px;
            color:#ECF3FF;
            font-size:12px;
            font-weight:700;
        }}
        QMenu::item {{
            padding:8px 16px;
            border-radius:7px;
        }}
        QMenu::item:selected {{
            background:{acc}22;
            color:{acc};
        }}
    """)
    current_mode = _artist_album_sort_mode(app)
    for mode, label in _artist_album_sort_options(app):
        action = sort_menu.addAction(label)
        action.setCheckable(True)
        action.setChecked(mode == current_mode)
        action.triggered.connect(lambda _checked=False, m=mode: _apply_artist_album_sort(app, m))
    sort_btn.setMenu(sort_menu)
    sort_wrap.addWidget(sort_btn)
    head.addLayout(sort_wrap)
    outer.addLayout(head)

    def _album_card(album: dict) -> QWidget:
        artist_name = str(album.get("artist_name", "") or "").strip()
        album_name = str(album.get("name", "") or "").strip()

        card = ClickableFrame()
        card.setFixedSize(188, 246)
        card.setCursor(Qt.PointingHandCursor)
        card.setAttribute(Qt.WA_StyledBackground, True)
        card.setStyleSheet(f"""
            QFrame {{
                background:qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 {BG_CARD}, stop:1 {BG_ELEVATED});
                border-radius:18px;
                border:1px solid rgba(255,255,255,0.06);
            }}
            QFrame:hover {{
                border-color:{acc}44;
                background:qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 {BG_CARD_HOVER}, stop:1 {BG_ELEVATED});
            }}
            QLabel {{
                background:transparent;
                border:none;
            }}
        """)
        try:
            app._add_soft_shadow(card, 18, QColor(0, 0, 0, 60), 0, 6)
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)

        cl = QVBoxLayout(card)
        cl.setContentsMargins(12, 12, 12, 12)
        cl.setSpacing(10)

        img = QLabel()
        img.setFixedSize(164, 164)
        img.setAlignment(Qt.AlignCenter)
        img.setStyleSheet("background:#0B1420; border-radius:14px;")
        img_url = str(album.get("image_url", "") or "").strip()
        if img_url:
            app._load_image(img_url, img, (164, 164))
        else:
            try:
                img.setPixmap(create_icon("music", TEXT_MUTED, 28).pixmap(28, 28))
            except Exception as _e:
                log.debug("Sessiz hata: %s", _e)
        cl.addWidget(img)

        name_lbl = QLabel(album_name)
        name_lbl.setWordWrap(True)
        name_lbl.setStyleSheet(f"font-size:14px; font-weight:850; color:{TEXT_PRIMARY};")
        cl.addWidget(name_lbl)

        meta_text = str(album.get("meta", "") or "").strip() or t("artist.album_default_label")
        meta_lbl = QLabel(meta_text)
        meta_lbl.setStyleSheet(f"font-size:11px; color:{TEXT_SECONDARY};")
        cl.addWidget(meta_lbl)
        cl.addStretch()

        if artist_name and album_name:
            bid = str(album.get("browse_id", "") or "")
            if album.get("group") == "single" and callable(getattr(app, "_play_artist_release", None)):
                card.clicked.connect(
                    lambda a=artist_name, n=album_name, b=bid: app._play_artist_release(a, n, b)
                )
            else:
                card.clicked.connect(
                    lambda a=artist_name, n=album_name, b=bid: app._open_artist_album(a, n, b)
                )
        return card

    def _album_strip(title_text: str, group_items: list[dict]):
        if not group_items:
            return
        group_title = QLabel(title_text)
        group_title.setStyleSheet(f"font-size:15px; font-weight:900; color:{TEXT_SECONDARY};")
        outer.addWidget(group_title)

        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        sc.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        sc.setFrameShape(QFrame.NoFrame)
        sc.setFixedHeight(290)

        holder = QWidget()
        hl = QHBoxLayout(holder)
        hl.setContentsMargins(2, 2, 2, 2)
        hl.setSpacing(14)
        for album in group_items[:12]:
            hl.addWidget(_album_card(album))
        hl.addStretch()
        sc.setWidget(holder)
        outer.addWidget(sc)

    album_items = [item for item in albums if item.get("group") != "single"]
    single_items = [item for item in albums if item.get("group") == "single"]
    _album_strip(t("artist.albums"), album_items)
    _album_strip(t("artist.singles_eps"), single_items)
    return panel


def _artist_similar_strip(app, artist_meta: dict) -> "QWidget | None":
    """Last.fm similar_artists verisinden yatay kaydırmalı sanatçı kartları."""

    similar = [
        item for item in (artist_meta or {}).get("similar_artists") or []
        if isinstance(item, dict) and str(item.get("name", "") or "").strip()
    ]
    if not similar:
        return None

    acc = get_accent()
    t = app._tr
    panel = QFrame()
    panel.setObjectName("ArtistSimilarPanel")
    panel.setAttribute(Qt.WA_StyledBackground, True)
    panel.setStyleSheet(f"""
        QFrame#ArtistSimilarPanel {{
            background:qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 rgba(255,255,255,0.022), stop:1 {BG_CARD});
            border-radius:24px;
            border:1px solid {BORDER_COLOR};
        }}
        QFrame#ArtistSimilarPanel QLabel {{
            background:transparent;
            border:none;
        }}
        QScrollArea {{ background:transparent; border:none; }}
        QScrollBar:horizontal {{
            background:transparent; height:10px; margin:4px 0 0 0;
        }}
        QScrollBar::handle:horizontal {{
            background:{acc}55; min-width:44px; border-radius:5px;
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
            background:transparent; border:none;
        }}
    """)

    outer = QVBoxLayout(panel)
    outer.setContentsMargins(20, 18, 20, 16)
    outer.setSpacing(12)

    head = QHBoxLayout()
    head_text = QVBoxLayout()
    head_text.setContentsMargins(0, 0, 0, 0)
    head_text.setSpacing(2)
    head_text.addWidget(_lbl(t("artist.similar"),
        f"font-size:26px; font-weight:900; color:{TEXT_PRIMARY};"))
    head.addLayout(head_text)
    head.addStretch()
    outer.addLayout(head)

    sc = QScrollArea()
    sc.setWidgetResizable(True)
    sc.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    sc.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    sc.setFrameShape(QFrame.NoFrame)
    sc.setFixedHeight(200)

    holder = QWidget()
    hl = QHBoxLayout(holder)
    hl.setContentsMargins(2, 2, 2, 2)
    hl.setSpacing(14)

    for item in similar[:12]:
        artist_name = str(item.get("name", "") or "").strip()
        img_url     = str(item.get("image_url", "") or "").strip()
        browse_id   = str(item.get("browseId") or item.get("channelId") or "").strip()

        card = ClickableFrame()
        card.setFixedSize(152, 164)
        card.setCursor(Qt.PointingHandCursor)
        card.setAttribute(Qt.WA_StyledBackground, True)
        card.setStyleSheet(f"""
            QFrame {{
                background:{BG_CARD};
                border-radius:18px;
                border:1px solid rgba(255,255,255,0.06);
            }}
            QFrame:hover {{
                border-color:{acc}50;
                background:{BG_CARD_HOVER};
            }}
            QLabel {{ background:transparent; border:none; }}
        """)
        try:
            app._add_soft_shadow(card, 18, QColor(0, 0, 0, 55), 0, 5)
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)

        cl2 = QVBoxLayout(card)
        cl2.setContentsMargins(12, 12, 12, 10)
        cl2.setSpacing(8)

        avatar_color = _name_color(artist_name)
        initials = "".join(w[0].upper() for w in artist_name.split()[:2]) or "?"

        img = QLabel(initials)
        img.setFixedSize(100, 100)
        img.setAlignment(Qt.AlignCenter)
        img.setStyleSheet(
            f"background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            f"stop:0 {avatar_color}, stop:1 {avatar_color}88);"
            "border-radius:50px;"
            f"color:#FFFFFF; font-size:28px; font-weight:900;"
        )

        def _fetch_yt_artist_img(an=artist_name, lbl=img, lfm_url=img_url):
            try:
                if lfm_url:
                    app._load_image(lfm_url, lbl, (100, 100))
                    return
                results = app._yt_search(an, filter="artists", limit=3, fallback_on_empty=False)
                for r in (results or []):
                    if not isinstance(r, dict):
                        continue
                    thumbs = r.get("thumbnails") or r.get("thumbnail") or []
                    if isinstance(thumbs, dict):
                        thumbs = [thumbs]
                    best = ""
                    for t in thumbs:
                        if isinstance(t, dict):
                            u = str(t.get("url", "") or "").strip()
                            if u:
                                best = u
                    if best:
                        import re as _re
                        best = _re.sub(r'=w\d+-h\d+', '=w300-h300', best)
                        app._load_image(best, lbl, (100, 100))
                        return
            except Exception as _e:
                log.debug("YT sanatçı görseli başarısız (%s): %s", an, _e)

        app._img_pool.submit(_fetch_yt_artist_img)

        cl2.addWidget(img, 0, Qt.AlignHCenter)

        name_lbl = QLabel(artist_name)
        name_lbl.setAlignment(Qt.AlignCenter)
        name_lbl.setWordWrap(True)
        name_lbl.setStyleSheet(
            f"font-size:13px; font-weight:800; color:{TEXT_PRIMARY};"
        )
        cl2.addWidget(name_lbl)
        cl2.addStretch()

        card.clicked.connect(lambda an=artist_name, bid=browse_id: app._open_artist_name(an, bid))
        hl.addWidget(card)

    hl.addStretch()
    sc.setWidget(holder)
    outer.addWidget(sc)
    return panel


def _artist_about_card(app, name: str, artist_meta: dict) -> "QWidget | None":
    """Tam biyografi + tür etiketleri + Last.fm bağlantısı."""

    meta = artist_meta or {}
    bio  = str(meta.get("bio", "") or "").strip()
    tags = [str(t).strip() for t in (meta.get("tags") or []) if str(t).strip()]
    url  = str(meta.get("url", "") or "").strip()

    if not bio and not tags:
        return None

    acc = get_accent()
    t = app._tr
    card = QFrame()
    card.setObjectName("ArtistAboutCard")
    card.setAttribute(Qt.WA_StyledBackground, True)
    card.setStyleSheet(f"""
        QFrame#ArtistAboutCard {{
            background:qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 rgba(255,255,255,0.022), stop:1 {BG_CARD});
            border-radius:24px;
            border:1px solid {BORDER_COLOR};
        }}
        QFrame#ArtistAboutCard QLabel {{ background:transparent; border:none; }}
    """)
    try:
        app._add_soft_shadow(card, 24, QColor(0, 0, 0, 70), 0, 8)
    except Exception as _e:
        log.debug("Sessiz hata: %s", _e)

    outer = QVBoxLayout(card)
    outer.setContentsMargins(24, 20, 24, 20)
    outer.setSpacing(14)

    head = QHBoxLayout()
    accent_line = QFrame()
    accent_line.setFixedSize(4, 40)
    accent_line.setStyleSheet(
        f"background:qlineargradient(x1:0,y1:0,x2:0,y2:1,"
        f"stop:0 {acc},stop:1 {get_accent_hover()});"
        "border:none; border-radius:2px;")
    head.addWidget(accent_line, 0, Qt.AlignVCenter)
    head.addSpacing(10)
    head_lbl = QLabel(t("artist.about"))
    head_lbl.setStyleSheet(f"font-size:22px; font-weight:900; color:{TEXT_PRIMARY};")
    head.addWidget(head_lbl)
    head.addStretch()
    outer.addLayout(head)

    if bio:
        bio_lbl = QLabel(bio)
        bio_lbl.setWordWrap(True)
        bio_lbl.setStyleSheet(
            f"font-size:13px; line-height:1.6; color:{TEXT_SECONDARY};"
        )
        outer.addWidget(bio_lbl)

    if tags:
        tags_row = QHBoxLayout()
        tags_row.setSpacing(8)
        for tag in tags[:8]:
            pill = QLabel(tag.capitalize())
            pill.setStyleSheet(f"""
                background:{acc}14;
                color:{TEXT_PRIMARY};
                border:1px solid {acc}2A;
                border-radius:13px;
                padding:6px 12px;
                font-size:11px;
                font-weight:800;
            """)
            tags_row.addWidget(pill)
        tags_row.addStretch()
        outer.addLayout(tags_row)

    return card


def _build_artist_profile_page(app, tracks, name: str, artist_meta: dict, subtitle: str):
    """Spotify tarzı tam sanatçı sayfası.
    Akış: Hero → Popüler → Albümler → Benzer Sanatçılar → Hakkında
    """
    meta = artist_meta or {}
    pg = QWidget()
    pg.setStyleSheet(f"background:{BG_BLACK};")
    vl = QVBoxLayout(pg)
    vl.setContentsMargins(36, 36, 36, 0)
    vl.setSpacing(0)
    vl.addWidget(_build_page_header(
        app,
        name,
        subtitle,
        eyebrow=app._tr("artist.page_eyebrow"),
        back=True,
    ))
    vl.addSpacing(24)

    sc, ct, cl = _scrollable()
    vl.addWidget(sc)
    cl.setSpacing(22)

    cl.addWidget(_artist_profile_hero(app, name, tracks, meta, subtitle))
    cl.addWidget(_artist_popular_panel(app, tracks, meta, "artist.popular", 10, True))

    albums_strip = _artist_albums_strip(app, tracks, meta)
    if albums_strip is not None:
        cl.addWidget(albums_strip)

    similar_strip = _artist_similar_strip(app, meta)
    if similar_strip is not None:
        cl.addWidget(similar_strip)

    about_card = _artist_about_card(app, name, meta)
    if about_card is not None:
        cl.addWidget(about_card)

    cl.addSpacing(32)
    return pg


def build_artist_page(app, tracks, name, artist_meta=None):
    app.current_page = f"artist_{name}"
    meta = artist_meta or {}
    subtitle_bits = []
    if meta.get("listeners"):
        subtitle_bits.append(_artist_metric_text(app, "listeners", _fmt_artist_metric(meta["listeners"])))
    if meta.get("subscribers"):
        subtitle_bits.append(_artist_metric_text(app, "subscribers", meta["subscribers"]))
    if meta.get("playcount"):
        subtitle_bits.append(_artist_metric_text(app, "playcount", _fmt_artist_metric(meta["playcount"])))
    subtitle = " · ".join(subtitle_bits) if subtitle_bits else app._tr("artist.subtitle.fallback")
    return _build_artist_profile_page(app, tracks, name, meta, subtitle)


def build_artist_album_page(app, artist_name: str, album_name: str, tracks: list, album_meta=None):
    meta = album_meta or {}
    app.current_page = f"artist_album_{artist_name}_{album_name}"
    t = app._tr

    subtitle_bits = [artist_name]
    if meta.get("year"):
        subtitle_bits.append(str(meta["year"]))
    if meta.get("type") and meta.get("type") != "Album":
        subtitle_bits.append(str(meta["type"]))
    track_count = int(meta.get("track_count", 0) or len(tracks or []) or 0)
    if track_count:
        subtitle_bits.append(_artist_metric_text(app, "tracks", track_count))
    if meta.get("playcount"):
        subtitle_bits.append(_artist_metric_text(app, "listens", _fmt_artist_metric(meta.get("playcount", 0))))
    subtitle = "  ·  ".join([bit for bit in subtitle_bits if bit])

    pg = QWidget()
    pg.setStyleSheet(f"background:{BG_BLACK};")
    vl = QVBoxLayout(pg)
    vl.setContentsMargins(36, 36, 36, 0)
    vl.setSpacing(0)

    vl.addWidget(_build_page_header(
        app,
        album_name,
        subtitle,
        eyebrow=t("artist.album_eyebrow"),
        back=True,
    ))
    vl.addSpacing(24)

    sc, ct, cl = _scrollable()
    vl.addWidget(sc)
    cl.setSpacing(18)

    acc = get_accent()
    hero = QFrame()
    hero.setObjectName("ArtistAlbumHero")
    hero.setAttribute(Qt.WA_StyledBackground, True)
    hero.setMinimumHeight(276)
    hero.setStyleSheet(f"""
        QFrame#ArtistAlbumHero {{
            background:qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 rgba(255,255,255,0.024), stop:0.18 {acc}14,
                stop:0.58 rgba(8,18,28,0.94), stop:1 {BG_ELEVATED});
            border-radius:28px;
            border:1px solid {acc}34;
        }}
        QFrame#ArtistAlbumHero QLabel {{
            background:transparent;
            border:none;
        }}
    """)
    try:
        app._add_soft_shadow(hero, 28, QColor(0, 0, 0, 86), 0, 12)
    except Exception as _e:
        log.debug("Sessiz hata: %s", _e)

    hero_l = QHBoxLayout(hero)
    hero_l.setContentsMargins(28, 28, 28, 28)
    hero_l.setSpacing(22)

    cover = QLabel()
    cover.setFixedSize(196, 196)
    cover.setAlignment(Qt.AlignCenter)
    cover.setStyleSheet("background:#0B1420; border-radius:24px;")
    cover_url = str(meta.get("image_url", "") or "").strip()
    if cover_url:
        app._load_image(cover_url, cover, (196, 196))
    else:
        try:
            cover.setPixmap(create_icon("music", TEXT_MUTED, 48).pixmap(48, 48))
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
    hero_l.addWidget(cover, 0, Qt.AlignTop)

    info = QVBoxLayout()
    info.setContentsMargins(0, 0, 0, 0)
    info.setSpacing(10)

    eyebrow = QLabel(t("artist.album_eyebrow"))
    eyebrow.setStyleSheet(f"font-size:11px; font-weight:900; letter-spacing:2px; color:{acc};")
    title = QLabel(album_name)
    title.setWordWrap(True)
    title.setStyleSheet(f"font-size:40px; font-weight:950; color:{TEXT_PRIMARY};")
    artist_lbl = QLabel(artist_name)
    artist_lbl.setStyleSheet(f"font-size:16px; font-weight:700; color:{TEXT_SECONDARY};")
    info.addWidget(eyebrow)
    info.addWidget(title)
    info.addWidget(artist_lbl)

    wiki = str(meta.get("wiki", "") or "").strip()
    if wiki:
        wiki_lbl = QLabel((wiki[:360] + "...") if len(wiki) > 360 else wiki)
        wiki_lbl.setWordWrap(True)
        wiki_lbl.setStyleSheet(f"font-size:13px; line-height:1.45; color:{TEXT_SECONDARY};")
        info.addWidget(wiki_lbl)

    stats_row = QHBoxLayout()
    stats_row.setSpacing(10)
    stat_texts = []
    if track_count:
        stat_texts.append(_artist_metric_text(app, "tracks", track_count))
    if meta.get("listeners"):
        stat_texts.append(_artist_metric_text(app, "listeners", _fmt_artist_metric(meta.get("listeners", 0))))
    if meta.get("playcount"):
        stat_texts.append(_artist_metric_text(app, "followers", _fmt_artist_metric(meta.get("playcount", 0))))
    for text in stat_texts[:3]:
        pill = QLabel(text)
        pill.setStyleSheet(
            f"background:rgba(255,255,255,0.05); color:{TEXT_PRIMARY}; "
            f"border:1px solid {acc}20; border-radius:14px; padding:7px 12px; "
            "font-size:11px; font-weight:700;")
        stats_row.addWidget(pill)
    stats_row.addStretch()
    info.addLayout(stats_row)

    actions = QHBoxLayout()
    actions.setSpacing(10)

    play_btn = QPushButton(t("artist.play"))
    play_btn.setCursor(Qt.PointingHandCursor)
    play_btn.setEnabled(bool(tracks))
    play_btn.setStyleSheet(f"""
        QPushButton {{
            background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 {acc}, stop:1 {get_accent_hover()});
            color:#081108;
            border:none;
            border-radius:16px;
            padding:12px 20px;
            font-size:13px;
            font-weight:900;
        }}
        QPushButton:disabled {{
            background:{BG_CARD};
            color:{TEXT_MUTED};
        }}
    """)
    play_btn.clicked.connect(lambda: app._play_artist_only(list(tracks)) if tracks else None)
    actions.addWidget(play_btn)

    def _shuffle_album():
        if not tracks:
            return
        import random
        shuffled = list(tracks)
        random.shuffle(shuffled)
        app._play_artist_only(shuffled)

    shuffle_btn = QPushButton(t("artist.shuffle"))
    shuffle_btn.setCursor(Qt.PointingHandCursor)
    shuffle_btn.setEnabled(bool(tracks))
    shuffle_btn.setStyleSheet(f"""
        QPushButton {{
            background:rgba(255,255,255,0.04);
            color:{TEXT_PRIMARY};
            border:1px solid rgba(255,255,255,0.08);
            border-radius:16px;
            padding:12px 18px;
            font-size:13px;
            font-weight:800;
        }}
        QPushButton:hover {{
            border-color:{acc}44;
            color:{acc};
        }}
        QPushButton:disabled {{
            color:{TEXT_MUTED};
        }}
    """)
    shuffle_btn.clicked.connect(_shuffle_album)
    actions.addWidget(shuffle_btn)
    actions.addStretch()
    info.addLayout(actions)
    info.addStretch()

    hero_l.addLayout(info, 1)
    cl.addWidget(hero)

    tracks_panel = QFrame()
    tracks_panel.setObjectName("ArtistAlbumTracksPanel")
    tracks_panel.setAttribute(Qt.WA_StyledBackground, True)
    tracks_panel.setStyleSheet(f"""
        QFrame#ArtistAlbumTracksPanel {{
            background:qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 rgba(255,255,255,0.02), stop:1 {BG_CARD});
            border-radius:24px;
            border:1px solid {BORDER_COLOR};
        }}
        QFrame#ArtistAlbumTracksPanel QLabel {{
            background:transparent;
            border:none;
        }}
    """)
    tp_l = QVBoxLayout(tracks_panel)
    tp_l.setContentsMargins(20, 18, 20, 18)
    tp_l.setSpacing(10)

    tracks_title = QLabel(t("artist.section_tracks"))
    tracks_title.setStyleSheet(f"font-size:26px; font-weight:900; color:{TEXT_PRIMARY};")
    tp_l.addWidget(tracks_title)

    if tracks:
        tracks_holder = QWidget()
        tracks_layout = QVBoxLayout(tracks_holder)
        tracks_layout.setContentsMargins(0, 0, 0, 0)
        tracks_layout.setSpacing(8)
        app._list_tracks(tracks, tracks_holder, tracks_layout)
        tp_l.addWidget(tracks_holder)
    else:
        empty = QLabel(t("artist.no_album_tracks"))
        empty.setStyleSheet(f"font-size:13px; color:{TEXT_MUTED};")
        tp_l.addWidget(empty)

    cl.addWidget(tracks_panel)
    return pg
