"""Sanatçılar genel bakış sayfası."""
import logging
log = logging.getLogger("iqtMusic")

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QLineEdit, QGridLayout
)
from PySide6.QtCore import QObject, Signal as _Signal
from PySide6.QtCore import Qt, QSize, QRectF
from PySide6.QtGui import (
    QColor, QPainter, QPainterPath, QPixmap, QRadialGradient,
    QLinearGradient, QBrush, QPen
)

from core.constants import (
    BG_BLACK, BG_CARD, BG_CARD_HOVER, BG_ELEVATED, BORDER_COLOR,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED
)
from core.theme import get_accent, get_accent_hover
from utils.helpers import create_icon
from ui.widgets import ClickableFrame
from pages.common import _build_page_header, _scrollable


def _fmt_artist_metric(value: int) -> str:
    n = int(value or 0)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


class _ArtistAvatarWidget(QWidget):
    """Dairesel sanatçı fotoğrafı — glow halkası + vignette overlay ile.

    Fotoğraf yoksa harfli gradient placeholder gösterir.
    Hover'da glow yoğunlaşır ve hafif scale efekti uygulanır.
    """
    def __init__(self, size: int, accent: str, initials: str = "?", parent=None):
        super().__init__(parent)
        self._size    = size
        self._accent  = accent
        self._initials = (initials or "?")[:2].upper()
        self._px: QPixmap | None = None
        self._hovered = False
        self.setFixedSize(size + 12, size + 12)
        self.setAttribute(Qt.WA_StyledBackground, False)
        self.setStyleSheet("background:transparent; border:none;")
        self.setCursor(Qt.PointingHandCursor)

    def setPixmap(self, px: QPixmap):
        self._px = px
        self.update()

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        cx = self.width()  // 2
        cy = self.height() // 2
        r  = self._size    // 2
        glow_r = r + (5 if self._hovered else 3)
        corner = max(14, self._size // 7)
        photo_rect = QRectF(cx - r, cy - r, r * 2, r * 2)

        # ── 1. Dış glow halkası ──────────────────────────────────────────────
        glow = QRadialGradient(cx, cy, glow_r)
        acc_color = QColor(self._accent)
        alpha_outer = 80 if self._hovered else 45
        alpha_mid   = 35 if self._hovered else 18
        glow.setColorAt(0.70, QColor(acc_color.red(), acc_color.green(), acc_color.blue(), alpha_outer))
        glow.setColorAt(0.88, QColor(acc_color.red(), acc_color.green(), acc_color.blue(), alpha_mid))
        glow.setColorAt(1.00, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(glow))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(
            QRectF(cx - glow_r, cy - glow_r, glow_r * 2, glow_r * 2),
            corner + 4,
            corner + 4,
        )

        # ── 2. Dairesel clip path ────────────────────────────────────────────
        clip = QPainterPath()
        clip.addRoundedRect(photo_rect, corner, corner)
        painter.setClipPath(clip)

        if self._px and not self._px.isNull():
            # Fotoğrafı daire içine scale et (cover gibi)
            scaled = self._px.scaled(
                r * 2, r * 2,
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation,
            )
            ox = (scaled.width()  - r * 2) // 2
            oy = (scaled.height() - r * 2) // 2
            painter.drawPixmap(cx - r, cy - r, scaled, ox, oy, r * 2, r * 2)

            # Vignette — alt kenardan kararan radyal gradient
            vign = QRadialGradient(cx, cy + r * 0.35, r * 1.1)
            vign.setColorAt(0.0, QColor(0, 0, 0, 0))
            vign.setColorAt(0.6, QColor(0, 0, 0, 0))
            vign.setColorAt(1.0, QColor(0, 0, 0, 145))
            painter.setBrush(QBrush(vign))
            painter.drawRoundedRect(photo_rect, corner, corner)

        else:
            # Placeholder: accent→koyu diagonal gradient + baş harfler
            grad = QLinearGradient(cx - r, cy - r, cx + r, cy + r)
            acc  = QColor(self._accent)
            dark = QColor(
                max(0, acc.red()   - 60),
                max(0, acc.green() - 60),
                max(0, acc.blue()  - 60),
            )
            grad.setColorAt(0.0, acc)
            grad.setColorAt(1.0, dark)
            painter.setBrush(QBrush(grad))
            painter.drawRoundedRect(photo_rect, corner, corner)

            painter.setClipping(False)
            font = painter.font()
            font.setPixelSize(max(14, r // 2))
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(QColor(0, 0, 0, 160))
            painter.drawText(cx - r + 2, cy - r + 2, r * 2, r * 2,
                             Qt.AlignCenter, self._initials)
            painter.setPen(QColor(255, 255, 255, 220))
            painter.drawText(cx - r, cy - r, r * 2, r * 2,
                             Qt.AlignCenter, self._initials)
            painter.setClipping(True)

        painter.setClipping(False)

        # ── 3. İnce parlak halka (accent rengi) ─────────────────────────────
        ring_width = 2.0 if not self._hovered else 2.5
        pen = QPen(QColor(
            acc_color.red(), acc_color.green(), acc_color.blue(),
            200 if self._hovered else 130
        ))
        pen.setWidthF(ring_width)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        margin = ring_width / 2
        painter.drawRoundedRect(
            QRectF(cx - r + margin, cy - r + margin, r * 2 - ring_width, r * 2 - ring_width),
            corner,
            corner,
        )

        painter.end()


def _artist_overview_card(app, artist_data: dict):
    acc = get_accent()
    t = app._tr
    name = str(artist_data.get("name", "") or "").strip() or t("artist.unknown")
    meta = artist_data.get("artist_meta") or {}
    browse_id = str(meta.get("browseId") or meta.get("channelId") or "").strip()
    image_url = str(artist_data.get("image_url", "") or "").strip()
    sample_track = artist_data.get("sample_track") or {}

    card = ClickableFrame()
    card.setObjectName("ArtistOverviewCard")
    card.setAttribute(Qt.WA_StyledBackground, True)
    card.setStyleSheet(f"""
        QFrame#ArtistOverviewCard {{
            background:qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 rgba(255,255,255,0.022), stop:0.26 {acc}10,
                stop:0.72 {BG_CARD}, stop:1 {BG_ELEVATED});
            border-radius:20px;
            border:1px solid {acc}22;
        }}
        QFrame#ArtistOverviewCard:hover {{
            border:1px solid {acc}58;
            background:qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 rgba(255,255,255,0.03), stop:0.24 {acc}16,
                stop:0.72 {BG_CARD_HOVER}, stop:1 {BG_ELEVATED});
        }}
        QFrame#ArtistOverviewCard QLabel {{
            background:transparent;
            border:none;
        }}
    """)
    try:
        app._add_soft_shadow(card, 22, QColor(0, 0, 0, 82), 0, 8)
    except Exception as _e:
        log.debug("Sessiz hata: %s", _e)

    outer = QVBoxLayout(card)
    outer.setContentsMargins(16, 16, 16, 16)
    outer.setSpacing(12)

    top = QHBoxLayout()
    top.setSpacing(10)

    initials = (name or "?")[:2]
    avatar = _ArtistAvatarWidget(116, acc, initials)

    # Fotoğrafı yükle — _load_image QLabel bekliyor, wrapper kullanıyoruz
    _img_proxy = QLabel()
    _img_proxy.setFixedSize(1, 1)   # gizli proxy
    _img_proxy.hide()

    def _on_avatar_loaded(px_label):
        """Proxy label'a yüklenen pixmap'i avatar widget'a aktar."""
        px = px_label.pixmap()
        if px and not px.isNull():
            avatar.setPixmap(px)

    # Pixmap gelince avatar'a aktar
    _orig_set = _img_proxy.setPixmap
    def _intercept(px, _lbl=_img_proxy, _av=avatar):
        _orig_set(px)
        if px and not px.isNull():
            _av.setPixmap(px)
    _img_proxy.setPixmap = _intercept

    if image_url:
        app._load_image(image_url, _img_proxy, (232, 232))
    else:
        thumb = app._thumb(sample_track, big=True)
        if thumb:
            app._load_image(thumb, _img_proxy, (232, 232))

    top.addWidget(avatar, 0, Qt.AlignVCenter)

    text_col = QVBoxLayout()
    text_col.setSpacing(4)
    title = QLabel(name)
    title.setWordWrap(True)
    title.setStyleSheet(f"font-size:18px; font-weight:900; color:{TEXT_PRIMARY};")
    sub_bits = []
    if artist_data.get("plays"):
        sub_bits.append(t("artists.metric.plays", count=artist_data["plays"]))
    if meta.get("listeners"):
        sub_bits.append(t("artists.metric.listeners", count=_fmt_artist_metric(meta["listeners"])))
    subtitle = QLabel("  ·  ".join(sub_bits) if sub_bits else t("artists.card.local_profile"))
    subtitle.setWordWrap(True)
    subtitle.setStyleSheet(f"font-size:12px; color:{TEXT_SECONDARY};")
    text_col.addWidget(title)
    text_col.addWidget(subtitle)

    top_track = str(artist_data.get("top_track", "") or "").strip()
    if top_track:
        top_track_lbl = QLabel(t("artists.card.top_track", track=top_track))
        top_track_lbl.setWordWrap(True)
        top_track_lbl.setStyleSheet(f"font-size:11px; color:{TEXT_MUTED};")
        text_col.addWidget(top_track_lbl)

    counts = []
    if artist_data.get("favorite_hits"):
        counts.append(t("artists.metric.favorites", count=artist_data["favorite_hits"]))
    if artist_data.get("download_hits"):
        counts.append(t("artists.metric.downloads", count=artist_data["download_hits"]))
    if counts:
        counts_lbl = QLabel("  ·  ".join(counts))
        counts_lbl.setStyleSheet(f"font-size:11px; color:{TEXT_MUTED};")
        text_col.addWidget(counts_lbl)

    text_col.addStretch()
    top.addLayout(text_col, 1)
    outer.addLayout(top)

    tags = [str(tag).strip() for tag in list(artist_data.get("tags") or [])[:3] if str(tag).strip()]
    if tags:
        tags_row = QHBoxLayout()
        tags_row.setSpacing(8)
        for tag in tags:
            pill = QLabel(tag)
            pill.setStyleSheet(
                f"background:rgba(255,255,255,0.045); color:{TEXT_PRIMARY}; "
                f"border:1px solid {acc}20; border-radius:12px; padding:5px 10px; "
                "font-size:11px; font-weight:700;")
            tags_row.addWidget(pill)
        tags_row.addStretch()
        outer.addLayout(tags_row)

    actions = QHBoxLayout()
    actions.setSpacing(8)

    open_btn = QPushButton(t("artists.open_profile"))
    open_btn.setCursor(Qt.PointingHandCursor)
    open_btn.setStyleSheet(f"""
        QPushButton {{
            background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 {acc}, stop:1 {get_accent_hover()});
            color:#06110A;
            border:none;
            border-radius:13px;
            padding:9px 14px;
            font-size:12px;
            font-weight:800;
        }}
        QPushButton:hover {{
            background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 {get_accent_hover()}, stop:1 {acc});
        }}
    """)
    open_btn.clicked.connect(lambda: app._open_artist_name(name, browse_id))
    actions.addWidget(open_btn)

    is_liked = app._is_artist_liked(name)
    like_btn = QPushButton()
    like_btn.setFixedSize(34, 34)
    like_btn.setCursor(Qt.PointingHandCursor)
    like_btn.setFocusPolicy(Qt.NoFocus)
    like_btn.setIcon(create_icon("heart_on" if is_liked else "heart_off", acc if is_liked else TEXT_MUTED, 17))
    like_btn.setIconSize(QSize(17, 17))
    like_btn.setToolTip(t("artist.unlike" if is_liked else "artist.like"))
    like_btn.setStyleSheet(f"""
        QPushButton {{
            background:rgba(255,255,255,0.04);
            border:1px solid {acc}24;
            border-radius:13px;
        }}
        QPushButton:hover {{
            background:{acc}16;
            border-color:{acc}58;
        }}
    """)
    like_btn.clicked.connect(lambda: app._toggle_artist_like(name, browse_id, meta, like_btn))
    actions.addWidget(like_btn)

    if meta.get("url"):
        source_lbl = QLabel(t("artists.profile_badge"))
        source_lbl.setAlignment(Qt.AlignCenter)
        source_lbl.setFixedHeight(34)
        source_lbl.setStyleSheet(
            f"background:rgba(255,255,255,0.04); color:{TEXT_MUTED}; "
            f"border:1px solid {acc}18; border-radius:13px; padding:0 12px; "
            "font-size:11px; font-weight:700;")
        actions.addWidget(source_lbl)

    actions.addStretch()
    outer.addLayout(actions)

    card.clicked.connect(lambda: app._open_artist_name(name, browse_id))
    return card


def build_artists_page(app, payload=None, loading=False):
    app.current_page = "artists"
    data = payload or {}
    t = app._tr
    featured = list(data.get("featured") or [])
    similar = list(data.get("similar") or [])
    summary = data.get("summary") or {}
    top_artist = str(summary.get("top_artist", "") or "").strip()
    artist_count = int(summary.get("artist_count", 0) or 0)
    top_tags = [str(tag).strip() for tag in list(summary.get("top_tags") or []) if str(tag).strip()]

    if loading and not featured:
        subtitle = t("artists.subtitle.loading")
    elif top_artist:
        subtitle = t("artists.subtitle.focused", count=artist_count, artist=top_artist)
    else:
        subtitle = t("artists.subtitle.empty")

    refresh_btn = QPushButton(t("artists.refresh"))
    refresh_btn.setCursor(Qt.PointingHandCursor)
    refresh_btn.setStyleSheet(f"""
        QPushButton {{
            background:rgba(255,255,255,0.04);
            color:{TEXT_PRIMARY};
            border:1px solid {get_accent()}32;
            border-radius:13px;
            padding:9px 14px;
            font-size:12px;
            font-weight:800;
        }}
        QPushButton:hover {{
            background:{get_accent()}16;
            border-color:{get_accent()}72;
            color:{get_accent()};
        }}
    """)
    refresh_btn.clicked.connect(lambda: app._net_pool.submit(app._fetch_artists_overview))

    pg = QWidget()
    pg.setStyleSheet(f"background:{BG_BLACK};")
    outer = QVBoxLayout(pg)
    outer.setContentsMargins(36, 36, 36, 0)
    outer.setSpacing(0)
    outer.addWidget(_build_page_header(
        app,
        t("artists.page_title"),
        subtitle,
        eyebrow=t("artists.page_eyebrow"),
        right_widget=refresh_btn,
    ))
    outer.addSpacing(24)

    sc, ct, cl = _scrollable()
    outer.addWidget(sc)
    cl.setSpacing(18)

    hero = QFrame()
    hero.setObjectName("ArtistsHero")
    hero.setAttribute(Qt.WA_StyledBackground, True)
    hero.setStyleSheet(f"""
        QFrame#ArtistsHero {{
            background:qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 rgba(255,255,255,0.025), stop:0.22 {get_accent()}16,
                stop:0.72 {BG_CARD}, stop:1 {BG_ELEVATED});
            border-radius:24px;
            border:1px solid {get_accent()}2A;
        }}
        QFrame#ArtistsHero QLabel {{
            background:transparent;
            border:none;
        }}
    """)
    try:
        app._add_soft_shadow(hero, 26, QColor(0, 0, 0, 85), 0, 8)
    except Exception as _e:
        log.debug("Sessiz hata: %s", _e)
    hl = QVBoxLayout(hero)
    hl.setContentsMargins(22, 20, 22, 20)
    hl.setSpacing(14)

    top_row = QHBoxLayout()
    top_row.setSpacing(12)
    accent_line = QFrame()
    accent_line.setFixedSize(4, 54)
    accent_line.setStyleSheet(
        f"background:qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 {get_accent()}, stop:1 {get_accent_hover()}); "
        "border:none; border-radius:2px;")
    top_row.addWidget(accent_line, 0, Qt.AlignTop)

    text_col = QVBoxLayout()
    text_col.setSpacing(6)
    eyebrow = QLabel(t("artists.hero.eyebrow"))
    eyebrow.setStyleSheet(f"font-size:10px; font-weight:900; letter-spacing:2px; color:{get_accent()};")
    title = QLabel(top_artist or t("artists.hero.preparing"))
    title.setWordWrap(True)
    title.setStyleSheet(f"font-size:24px; font-weight:900; color:{TEXT_PRIMARY};")
    desc = QLabel(t("artists.hero.desc"))
    desc.setWordWrap(True)
    desc.setStyleSheet(f"font-size:13px; color:{TEXT_SECONDARY};")
    text_col.addWidget(eyebrow)
    text_col.addWidget(title)
    text_col.addWidget(desc)
    top_row.addLayout(text_col, 1)
    hl.addLayout(top_row)

    if top_tags:
        tags_row = QHBoxLayout()
        tags_row.setSpacing(8)
        for tag in top_tags[:6]:
            pill = QLabel(tag)
            pill.setStyleSheet(
                f"background:rgba(255,255,255,0.04); color:{TEXT_PRIMARY}; "
                f"border:1px solid {get_accent()}24; border-radius:13px; padding:6px 10px; "
                "font-size:11px; font-weight:700;")
            tags_row.addWidget(pill)
        tags_row.addStretch()
        hl.addLayout(tags_row)

    if similar:
        sim_lbl = QLabel(t("artists.hero.similar"))
        sim_lbl.setStyleSheet(f"font-size:12px; font-weight:800; color:{TEXT_MUTED};")
        hl.addWidget(sim_lbl)
        sim_row = QHBoxLayout()
        sim_row.setSpacing(8)
        for item in similar[:6]:
            artist_name = str(item.get("name", "") or "").strip()
            if not artist_name:
                continue
            artist_meta = item.get("artist_meta") or {}
            browse_id = str(
                item.get("browseId")
                or item.get("channelId")
                or artist_meta.get("browseId")
                or artist_meta.get("channelId")
                or ""
            ).strip()
            btn = QPushButton(artist_name)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background:rgba(255,255,255,0.04);
                    color:{TEXT_PRIMARY};
                    border:1px solid rgba(255,255,255,0.06);
                    border-radius:13px;
                    padding:8px 12px;
                    font-size:12px;
                    font-weight:700;
                }}
                QPushButton:hover {{
                    background:{get_accent()}16;
                    border-color:{get_accent()}50;
                    color:{get_accent()};
                }}
            """)
            btn.clicked.connect(lambda _, artist=artist_name, bid=browse_id: app._open_artist_name(artist, bid))
            sim_row.addWidget(btn)
        sim_row.addStretch()
        hl.addLayout(sim_row)

    cl.addWidget(hero)

    # ── Sanatçı arama kutusu (YouTube Music / Last.fm'den gerçek arama) ───────
    from PySide6.QtCore import QTimer
    acc = get_accent()

    search_box = QLineEdit()
    search_box.setPlaceholderText(t("artists.search_placeholder"))
    search_box.setFixedHeight(48)
    search_box.setClearButtonEnabled(True)
    search_box.setStyleSheet(f"""
        QLineEdit {{
            background:{BG_ELEVATED};
            color:{TEXT_PRIMARY};
            border:1.5px solid {BORDER_COLOR};
            border-radius:14px;
            padding:0 16px;
            font-size:14px;
        }}
        QLineEdit:focus {{
            border-color:{acc};
            background:{BG_CARD};
        }}
    """)
    cl.addWidget(search_box)

    # Sonuç paneli — başlangıçta gizli
    results_panel = QFrame()
    results_panel.setObjectName("ArtistSearchResults")
    results_panel.setAttribute(Qt.WA_StyledBackground, True)
    results_panel.setStyleSheet(f"""
        QFrame#ArtistSearchResults {{
            background:{BG_CARD};
            border:1px solid {acc}30;
            border-radius:14px;
        }}
        QFrame#ArtistSearchResults QLabel {{
            background:transparent;
            border:none;
        }}
    """)
    results_layout = QVBoxLayout(results_panel)
    results_layout.setContentsMargins(8, 8, 8, 8)
    results_layout.setSpacing(4)
    results_panel.setVisible(False)
    cl.addWidget(results_panel)

    # Thread → UI köprüsü (QTimer.singleShot worker thread'den çalışmaz)
    class _SearchBridge(QObject):
        results_ready = _Signal(list)

    _bridge = _SearchBridge()

    # Debounce zamanlayıcısı
    _timer = QTimer()
    _timer.setSingleShot(True)
    _timer.setInterval(380)

    def _clear_results():
        while results_layout.count():
            item = results_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

    def _show_results(names: list):
        _clear_results()
        if not names:
            results_panel.setVisible(False)
            return
        for artist_name in names[:8]:
            row = ClickableFrame()
            row.setAttribute(Qt.WA_StyledBackground, True)
            row.setStyleSheet(f"""
                QFrame {{
                    background:transparent;
                    border-radius:10px;
                    border:none;
                }}
                QFrame:hover {{
                    background:{acc}18;
                }}
            """)
            row_l = QHBoxLayout(row)
            row_l.setContentsMargins(10, 8, 10, 8)
            row_l.setSpacing(10)

            lbl = QLabel(artist_name)
            lbl.setStyleSheet(f"font-size:14px; color:{TEXT_PRIMARY}; font-weight:600;")
            row_l.addWidget(lbl, 1)

            arrow = QLabel("→")
            arrow.setStyleSheet(f"font-size:13px; color:{TEXT_MUTED};")
            row_l.addWidget(arrow)

            _name = artist_name
            row.clicked.connect(lambda _n=_name: (
                search_box.clear(),
                results_panel.setVisible(False),
                app._open_artist_name(_n),
            ))
            results_layout.addWidget(row)

        results_panel.setVisible(True)

    # Signal → slot bağlantısı (main thread'de çalışır, thread-safe)
    _bridge.results_ready.connect(_show_results)

    def _do_search():
        query = search_box.text().strip()
        if not query:
            _clear_results()
            results_panel.setVisible(False)
            return

        # Yükleniyor göstergesi
        _clear_results()
        loading_row = QLabel(f"   {t('artists.search_loading')}")
        loading_row.setStyleSheet(f"font-size:13px; color:{TEXT_MUTED}; padding:8px 10px;")
        results_layout.addWidget(loading_row)
        results_panel.setVisible(True)

        def _worker(_q=query):
            names = []
            try:
                results = app._yt_search(_q, filter="artists", limit=8, fallback_on_empty=False)
                for r in results or []:
                    if not isinstance(r, dict):
                        continue
                    n = (
                        r.get("artist")
                        or r.get("name")
                        or (r.get("artists") or [{}])[0].get("name", "")
                    )
                    n = str(n or "").strip()
                    if n and n not in names:
                        names.append(n)
            except Exception as _e:
                log.debug("Sanatçı arama hatası: %s", _e)
            # Last.fm fallback
            if False and not names and getattr(app, "_lastfm", None):
                try:
                    meta = app._lastfm.get_artist_profile(_q)
                    if meta and meta.get("name"):
                        names.append(str(meta["name"]).strip())
                except Exception:
                    pass
            # Hiçbir sonuç yoksa aranan kelimeyi göster
            if not names:
                names = [_q]
            # Signal ile main thread'e gönder (thread-safe)
            _bridge.results_ready.emit(names)

        app._net_pool.submit(_worker)

    search_box.textChanged.connect(lambda _: (
        _clear_results(),
        results_panel.setVisible(False),
        _timer.start(),
    ))
    _timer.timeout.connect(_do_search)

    def _on_enter():
        _timer.stop()
        _do_search()

    search_box.returnPressed.connect(_on_enter)

    if loading and not featured:
        loading_lbl = QLabel(t("artists.loading"))
        loading_lbl.setAlignment(Qt.AlignCenter)
        loading_lbl.setStyleSheet(
            f"font-size:14px; color:{TEXT_MUTED}; background:transparent; padding:28px 0;")
        cl.addWidget(loading_lbl)
        return pg

    if not featured:
        empty = QLabel(t("artists.empty"))
        empty.setAlignment(Qt.AlignCenter)
        empty.setStyleSheet(
            f"font-size:15px; color:{TEXT_MUTED}; background:transparent; padding:28px 0;")
        cl.addWidget(empty)
        return pg

    # ── Öne çıkan sanatçılar grid ─────────────────────────────────────────────
    sec_lbl = QLabel(t("artists.section.featured"))
    sec_lbl.setStyleSheet(f"font-size:13px; font-weight:800; color:{TEXT_MUTED}; background:transparent;")
    cl.addWidget(sec_lbl)

    grid_wrap = QWidget()
    grid_wrap.setStyleSheet("background:transparent;")
    grid = QGridLayout(grid_wrap)
    grid.setContentsMargins(0, 0, 0, 12)
    grid.setHorizontalSpacing(16)
    grid.setVerticalSpacing(16)

    max_cols = 3
    row = 0
    col = 0
    for artist_data in featured:
        card = _artist_overview_card(app, artist_data)
        grid.addWidget(card, row, col)
        col += 1
        if col >= max_cols:
            col = 0
            row += 1

    for idx in range(max_cols):
        grid.setColumnStretch(idx, 1)
    cl.addWidget(grid_wrap)
    return pg
