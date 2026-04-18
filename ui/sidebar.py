"""Sol kenar çubuğu — Spotify benzeri gerçek baloncuk/pill nav."""
import logging
log = logging.getLogger("iqtMusic")

from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget, QSizePolicy,
    QMenu
)
from PySide6.QtCore import Qt, QSize, QTimer, QPropertyAnimation, QEasingCurve, QPoint, QAbstractAnimation, QUrl
from PySide6.QtGui import QDesktopServices

from core.constants import (
    BG_CARD_HOVER, TEXT_PRIMARY
)
from core.theme import get_accent
from utils.helpers import create_icon


_SECTION_MAP = {
    "home":      ("nav.home",      "home"),
    "search":    ("nav.search",    "search"),
    "artists":   ("nav.artists",   "artist"),
    "favs":      ("nav.favs",      "heart_on"),
    "downloads": ("nav.downloads", "download"),
    "mix":       ("nav.mix",       "mix"),
    "stats":     ("nav.stats",     "stats"),
    "settings":  ("nav.settings",  "settings"),
    "playlists": ("nav.playlists", "queue"),
}

# Spotify-tarzı baloncuk renkleri (koyu arka plan üstünde beyaz şeffaflık)
_BUBBLE_ACTIVE  = "rgba(255,255,255,0.15)"  # aktif: beyaz şeffaf bubble
_BUBBLE_HOVER   = "rgba(255,255,255,0.07)"  # hover: çok hafif beyaz
_ICON_ACTIVE    = "#FFFFFF"                  # aktif ikon rengi: beyaz
_TEXT_ACTIVE    = "#FFFFFF"                  # aktif yazı rengi: beyaz
_ICON_INACTIVE  = "#8A9AB5"                  # inaktif ikon: soluk gri-mavi
_TEXT_INACTIVE  = "#8A9AB5"                  # inaktif yazı: soluk gri-mavi
_BTN_W          = 232


def _rgba(hex_color: str, alpha: float) -> str:
    value = str(hex_color or "#000000").lstrip("#")
    if len(value) != 6:
        value = "000000"
    r = int(value[0:2], 16)
    g = int(value[2:4], 16)
    b = int(value[4:6], 16)
    try:
        alpha_value = float(alpha)
    except Exception:
        alpha_value = 1.0
    if alpha_value <= 1.0:
        alpha_int = int(round(max(0.0, min(1.0, alpha_value)) * 255.0))
    else:
        alpha_int = int(round(max(0.0, min(255.0, alpha_value))))
    return f"rgba({r},{g},{b},{alpha_int})"


class _BrandHeader(QFrame):
    _REST_SEGMENT_POS = QPoint(20, 0)
    _HOVER_SEGMENT_POS = QPoint(60, 0)
    _REST_SHADOW_POS = QPoint(1, 1)
    _HOVER_SHADOW_POS = QPoint(2, 2)

    def __init__(self, app, accent: str):
        super().__init__()
        self._app = app
        brand_accent = "#5EA2FF"
        self._accent = brand_accent
        self._brand_hovered = False
        self.setObjectName("SidebarBrand")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedWidth(_BTN_W)
        self.setFixedHeight(78)
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)

        self._content_wrap = QWidget(self)
        self._content_wrap.setObjectName("SidebarBrandInner")
        self._content_wrap.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        content_layout = QHBoxLayout(self._content_wrap)
        content_layout.setContentsMargins(14, 12, 14, 12)
        content_layout.setSpacing(12)

        badge_icon = QLabel()
        badge_icon.setFixedSize(36, 36)
        badge_icon.setAlignment(Qt.AlignCenter)
        badge_icon.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        app_icon = app.windowIcon() if hasattr(app, "windowIcon") else None
        badge_icon.setPixmap(
            app_icon.pixmap(34, 34)
            if app_icon is not None and not app_icon.isNull()
            else create_icon("play", brand_accent, 34).pixmap(34, 34)
        )
        content_layout.addWidget(badge_icon, 0, Qt.AlignTop)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(4)

        title_wrap = QWidget()
        title_wrap.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        title_wrap.setStyleSheet("background:transparent; border:none;")
        title_shadow = QLabel("IQTMusic", title_wrap)
        title_shadow.setStyleSheet(
            f"font-family:'Bahnschrift SemiCondensed','Bahnschrift SemiBold','Arial Black','Segoe UI Variable Display','Segoe UI'; "
            f"font-size:24px; font-weight:900; color:{_rgba('#203B67', 0.78)}; "
            f"letter-spacing:-0.3px; background:transparent;"
        )
        title_shadow.adjustSize()
        title_main = QLabel("IQTMusic", title_wrap)
        title_main.setStyleSheet(
            f"font-family:'Bahnschrift SemiCondensed','Bahnschrift SemiBold','Arial Black','Segoe UI Variable Display','Segoe UI'; "
            f"font-size:24px; font-weight:900; color:{TEXT_PRIMARY}; "
            f"letter-spacing:-0.3px; background:transparent;"
        )
        title_main.adjustSize()
        title_wrap.setFixedSize(title_main.sizeHint().width() + 6, title_main.sizeHint().height() + 6)
        title_main.move(0, 0)
        title_shadow.move(self._REST_SHADOW_POS)
        self._title_shadow = title_shadow
        text_col.addWidget(title_wrap)

        subtitle = QLabel(app._tr("sidebar.brand_subtitle"))
        subtitle.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._subtitle = subtitle
        text_col.addWidget(subtitle)

        accent_track = QFrame()
        accent_track.setFixedSize(92, 4)
        accent_track.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        accent_track.setStyleSheet(
            "background: rgba(255,255,255,0.07); border-radius: 2px;"
        )
        accent_glow = QFrame(accent_track)
        accent_glow.setGeometry(0, 0, 32, 4)
        accent_glow.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        accent_glow.setStyleSheet(
            f"""
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 rgba(255,255,255,0.18),
                stop:0.35 {_rgba(brand_accent, 0.98)},
                stop:1 rgba(255,255,255,0.18));
            border-radius: 2px;
            """
        )
        self._accent_glow = accent_glow
        text_col.addWidget(accent_track, 0, Qt.AlignLeft)
        content_layout.addLayout(text_col, 1)

        pulse = QLabel()
        pulse.setFixedSize(7, 7)
        pulse.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        pulse.setStyleSheet(
            f"background:{_rgba(brand_accent, 0.95)}; border-radius: 3px; border:none;"
        )
        self._pulse = pulse
        content_layout.addWidget(pulse, 0, Qt.AlignVCenter | Qt.AlignRight)

        self._line_anim = QPropertyAnimation(accent_glow, b"pos", self)
        self._line_anim.setStartValue(self._REST_SEGMENT_POS)
        self._line_anim.setKeyValueAt(0.5, self._HOVER_SEGMENT_POS)
        self._line_anim.setEndValue(self._REST_SEGMENT_POS)
        self._line_anim.setDuration(2400)
        self._line_anim.setLoopCount(-1)
        self._line_anim.setEasingCurve(QEasingCurve.InOutCubic)

        self._content_anim = QPropertyAnimation(self._content_wrap, b"pos", self)
        self._content_anim.setDuration(170)
        self._content_anim.setEasingCurve(QEasingCurve.OutCubic)

        self._shadow_pos_anim = QPropertyAnimation(self._title_shadow, b"pos", self)
        self._shadow_pos_anim.setDuration(170)
        self._shadow_pos_anim.setEasingCurve(QEasingCurve.OutCubic)

        self._apply_brand_frame_style(False)
        self._apply_subtitle_style(False)
        self._content_wrap.move(0, 0)
        self._accent_glow.move(self._REST_SEGMENT_POS)
        self._set_brand_motion(False)

    def _apply_brand_frame_style(self, hovered: bool):
        border_alpha = 0.26 if hovered else 0.18
        self.setStyleSheet(
            f"""
            QFrame#SidebarBrand {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 #09111B,
                    stop:0.55 #08111C,
                    stop:1 #070B12);
                border: 1px solid {_rgba(self._accent, border_alpha)};
                border-radius: 18px;
            }}
            QFrame#SidebarBrand:hover {{
                border: 1px solid {_rgba(self._accent, border_alpha + 0.06)};
            }}
            QLabel {{
                background: transparent;
                border: none;
            }}
            """
        )
        self._content_wrap.setStyleSheet(
            f"""
            QWidget#SidebarBrandInner {{
                background: transparent;
                border: none;
            }}
            """
        )

    def _apply_subtitle_style(self, hovered: bool):
        alpha = 0.98 if hovered else 0.82
        self._subtitle.setStyleSheet(
            f"font-size:11px; font-weight:700; color:{_rgba(self._accent, alpha)}; "
            f"letter-spacing:0.5px; background:transparent;"
        )

    def _apply_shadow_style(self, hovered: bool):
        alpha = 0.68 if hovered else 0.42
        self._title_shadow.setStyleSheet(
            f"font-family:'Bahnschrift SemiCondensed','Bahnschrift SemiBold','Arial Black','Segoe UI Variable Display','Segoe UI'; "
            f"font-size:24px; font-weight:900; color:{_rgba('#203B67', alpha)}; "
            f"letter-spacing:-0.3px; background:transparent;"
        )

    def _apply_pulse_style(self, hovered: bool):
        alpha = 1.0 if hovered else 0.62
        self._pulse.setStyleSheet(
            f"background:{_rgba(self._accent, alpha)}; border-radius: 3px; border:none;"
        )

    def _set_brand_motion(self, active: bool):
        self._brand_hovered = bool(active)
        self._apply_brand_frame_style(self._brand_hovered)
        self._apply_subtitle_style(self._brand_hovered)
        self._apply_shadow_style(self._brand_hovered)
        self._apply_pulse_style(self._brand_hovered)

        for anim in (self._content_anim, self._shadow_pos_anim):
            try:
                anim.stop()
            except Exception:
                pass

        self._content_anim.setStartValue(self._content_wrap.pos())
        self._content_anim.setEndValue(QPoint(0, -1) if self._brand_hovered else QPoint(0, 0))
        self._content_anim.start()

        self._shadow_pos_anim.setStartValue(self._title_shadow.pos())
        self._shadow_pos_anim.setEndValue(self._HOVER_SHADOW_POS if self._brand_hovered else self._REST_SHADOW_POS)
        self._shadow_pos_anim.start()

        if self._brand_hovered:
            if self._line_anim.state() != QAbstractAnimation.Running:
                self._line_anim.start()
            return

        try:
            self._line_anim.stop()
        except Exception:
            pass
        try:
            self._accent_glow.move(self._REST_SEGMENT_POS)
        except Exception:
            pass

    def enterEvent(self, event):
        self._set_brand_motion(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._set_brand_motion(False)
        super().leaveEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._content_wrap.resize(self.width(), self.height() + 2)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton and hasattr(self._app, "toggle_fullscreen"):
            self._app.toggle_fullscreen()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


class _SidebarFrame(QFrame):
    def __init__(self, app):
        super().__init__()
        self._app = app

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton and hasattr(self._app, "toggle_fullscreen"):
            self._app.toggle_fullscreen()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


class _SideNavBtn(QPushButton):
    """
    Spotify tarzı gerçek baloncuk/pill nav butonu.

    - Aktif : beyaz şeffaf yuvarlak baloncuk, beyaz ikon+yazı, bold
    - Hover : çok hafif beyaz tint, ikon renklenir
    - Normal: saydam arka plan, muted gri ikon+yazı
    """

    _BASE_H  = 44
    _HOVER_H = 44

    def __init__(self, text: str, icon_name: str, page_key: str):
        super().__init__(text)
        self._icon_name = icon_name
        self._page_key  = page_key
        self._active    = False

        self.setFocusPolicy(Qt.NoFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.setIconSize(QSize(20, 20))
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setAutoDefault(False)
        self.setDefault(False)
        self.setFlat(True)
        self.setFixedWidth(_BTN_W)
        self.setFixedHeight(self._BASE_H)
        self._apply_style()

    @property
    def page_key(self) -> str:
        return self._page_key

    def set_active(self, active: bool, force: bool = False):
        if self._active == active and not force:
            return
        self._active = active
        self._apply_style()
        try:
            self.style().unpolish(self)
            self.style().polish(self)
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
        self.updateGeometry()
        self.update()

    def enterEvent(self, event):
        super().enterEvent(event)

    def leaveEvent(self, event):
        super().leaveEvent(event)

    def _apply_style(self):
        if self._active:
            self.setIcon(create_icon(self._icon_name, _ICON_ACTIVE, 20))
            self.setStyleSheet(f"""
                QPushButton {{
                    text-align:    left;
                    padding-left:  16px;
                    padding-right: 16px;
                    border:        none;
                    border-radius: 14px;
                    background:    {_BUBBLE_ACTIVE};
                    color:         {_TEXT_ACTIVE};
                    font-size:     13px;
                    font-weight:   800;
                }}
            """)
        else:
            self.setIcon(create_icon(self._icon_name, _ICON_INACTIVE, 20))
            self.setStyleSheet(f"""
                QPushButton {{
                    text-align:    left;
                    padding-left:  16px;
                    padding-right: 16px;
                    border:        none;
                    border-radius: 14px;
                    background:    transparent;
                    color:         {_TEXT_INACTIVE};
                    font-size:     13px;
                    font-weight:   600;
                }}
                QPushButton:hover {{
                    background: {_BUBBLE_HOVER};
                    color:      {TEXT_PRIMARY};
                }}
            """)
        self.setMinimumHeight(self._BASE_H)
        self.setMaximumHeight(self._BASE_H)
        self.setFixedHeight(self._BASE_H)

    def _animate_h(self, target: int):
        self.setFixedHeight(self._BASE_H)


# ── build_sidebar ──────────────────────────────────────────────────────────

def build_sidebar(app) -> QFrame:
    acc = get_accent()

    sidebar = _SidebarFrame(app)
    sidebar.setObjectName("Sidebar")
    sidebar.setAttribute(Qt.WA_StyledBackground, True)
    sidebar.setFixedWidth(248)
    sl = QVBoxLayout(sidebar)
    sl.setContentsMargins(0, 20, 0, 20)
    sl.setSpacing(4)

    # Logo ─────────────────────────────────────────────────────────────────
    brand = _BrandHeader(app, acc)
    sl.addWidget(brand, 0, Qt.AlignHCenter)
    sl.addSpacing(18)

    # "KEŞFET" bölüm etiketi ────────────────────────────────────────────────
    sl.addSpacing(6)

    # Nav butonları ────────────────────────────────────────────────────────
    nav_buttons: dict[str, _SideNavBtn] = {}

    def _add(key: str, cmd):
        label_key, icon = _SECTION_MAP[key]
        btn = _SideNavBtn(app._tr(label_key), icon, key)
        btn.clicked.connect(cmd)
        sl.addWidget(btn, 0, Qt.AlignHCenter)
        nav_buttons[key] = btn

    _add("home",      app.page_home)
    _add("search",    app.page_search)
    _add("artists",   app.page_artists)
    _add("favs",      app.page_favs)
    _add("downloads", app.page_downloads)
    _add("mix",       app._build_mix)
    _add("stats",     app.page_stats)
    _add("settings",  lambda: app.page_settings())

    sl.addSpacing(16)

    # "KİTAPLIĞIM" bölüm etiketi ────────────────────────────────────────────
    _section_lbl(sl, app._tr("sidebar.section.library"))
    sl.addSpacing(4)

    # "Listelerim" nav butonu
    _add("playlists", app.page_playlists)

    sl.addSpacing(4)
    # Yeni liste oluştur butonu
    _mk_action_btn(app._tr("sidebar.create_playlist"), "add", app._dlg_new_playlist, sl)

    sl.addStretch()

    # "Beraber Dinle" butonu ─────────────────────────────────────────────────
    sl.addSpacing(6)
    collab_btn = QPushButton(app._tr("sidebar.listen_together"))
    collab_btn.setIcon(create_icon("link", _ICON_INACTIVE, 18))
    collab_btn.setIconSize(QSize(18, 18))
    collab_btn.setFocusPolicy(Qt.NoFocus)
    collab_btn.setCursor(Qt.PointingHandCursor)
    collab_btn.setAutoDefault(False)
    collab_btn.setDefault(False)
    collab_btn.setFlat(True)
    collab_btn.setFixedWidth(_BTN_W)
    collab_btn.setFixedHeight(40)
    collab_btn.setStyleSheet(f"""
        QPushButton {{
            text-align:    left;
            padding-left:  16px;
            padding-right: 16px;
            border:        none;
            border-radius: 14px;
            background:    transparent;
            color:         {_TEXT_INACTIVE};
            font-size:     13px;
            font-weight:   600;
        }}
        QPushButton:hover {{
            background: {_BUBBLE_HOVER};
            color:      {TEXT_PRIMARY};
        }}
    """)
    collab_btn.clicked.connect(app._collab_open_dialog)
    sl.addWidget(collab_btn, 0, Qt.AlignHCenter)
    sl.addSpacing(6)
    app._collab_btn = collab_btn
    # Oturum kapandığında geri dönülecek orijinal stili sakla
    collab_btn._default_stylesheet = collab_btn.styleSheet()

    # "Destek Ol" butonu ─────────────────────────────────────────────────────
    _PATREON_COLOR  = "#FF424D"
    _PATREON_HOVER  = "rgba(255,66,77,0.12)"
    support_btn = QPushButton(app._tr("sidebar.support_us"))
    support_btn.setIcon(create_icon("heart_on", _PATREON_COLOR, 18))
    support_btn.setIconSize(QSize(18, 18))
    support_btn.setFocusPolicy(Qt.NoFocus)
    support_btn.setCursor(Qt.PointingHandCursor)
    support_btn.setAutoDefault(False)
    support_btn.setDefault(False)
    support_btn.setFlat(True)
    support_btn.setFixedWidth(_BTN_W)
    support_btn.setFixedHeight(40)
    support_btn.setStyleSheet(f"""
        QPushButton {{
            text-align:    left;
            padding-left:  16px;
            padding-right: 16px;
            border:        none;
            border-radius: 14px;
            background:    transparent;
            color:         {_PATREON_COLOR};
            font-size:     13px;
            font-weight:   700;
        }}
        QPushButton:hover {{
            background: {_PATREON_HOVER};
            color:      #FF6B74;
        }}
    """)
    def _open_support_menu():
        menu = QMenu(support_btn)
        menu.setStyleSheet(f"""
            QMenu {{
                background: #0E1B31;
                border: 1px solid #1A2B49;
                border-radius: 8px;
                padding: 4px;
                color: #ECF3FF;
                font-size: 12px;
                font-weight: 600;
            }}
            QMenu::item {{
                padding: 8px 16px;
                border-radius: 6px;
            }}
            QMenu::item:selected {{
                background: {_PATREON_HOVER};
                color: {_PATREON_COLOR};
            }}
        """)
        menu.addAction("Üye Ol", lambda: QDesktopServices.openUrl(
            QUrl("https://www.patreon.com/c/iqtmusic/membership")))
        menu.addAction("Destek Ol", lambda: QDesktopServices.openUrl(
            QUrl("https://www.patreon.com/cw/IQTMusic/shop")))
        pos = support_btn.mapToGlobal(support_btn.rect().topLeft())
        menu.exec(pos)

    def _open_support_menu_localized():
        menu = QMenu(support_btn)
        menu.setStyleSheet(f"""
            QMenu {{
                background: #0E1B31;
                border: 1px solid #1A2B49;
                border-radius: 8px;
                padding: 4px;
                color: #ECF3FF;
                font-size: 12px;
                font-weight: 600;
            }}
            QMenu::item {{
                padding: 8px 16px;
                border-radius: 6px;
            }}
            QMenu::item:selected {{
                background: {_PATREON_HOVER};
                color: {_PATREON_COLOR};
            }}
        """)
        menu.addAction(app._tr("sidebar.support_menu.join"), lambda: QDesktopServices.openUrl(
            QUrl("https://www.patreon.com/c/iqtmusic/membership")))
        menu.addAction(app._tr("sidebar.support_menu.support"), lambda: QDesktopServices.openUrl(
            QUrl("https://www.patreon.com/cw/IQTMusic/shop")))
        pos = support_btn.mapToGlobal(support_btn.rect().topLeft())
        menu.exec(pos)

    support_btn.clicked.connect(_open_support_menu_localized)
    sl.addWidget(support_btn, 0, Qt.AlignHCenter)
    sl.addSpacing(4)

    lang_wrap = QFrame()
    lang_wrap.setObjectName("SidebarLangToggle")
    lang_wrap.setFixedSize(68, 30)
    lang_wrap.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    lang_wrap.setStyleSheet(f"""
        QFrame#SidebarLangToggle {{
            background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 rgba(255,255,255,0.03),
                stop:1 rgba(255,255,255,0.06));
            border: 1px solid {_rgba(acc, 0.18)};
            border-radius: 9px;
        }}
    """)
    lang_layout = QHBoxLayout(lang_wrap)
    lang_layout.setContentsMargins(3, 3, 3, 3)
    lang_layout.setSpacing(2)
    current_lang = str(getattr(app, "_language", "tr") or "tr")

    def _mk_lang_btn(label: str, code: str) -> QPushButton:
        btn = QPushButton(label)
        btn.setCheckable(True)
        btn.setAutoExclusive(True)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFocusPolicy(Qt.NoFocus)
        btn.setFixedSize(29, 22)
        btn.setStyleSheet(f"""
            QPushButton {{
                padding: 0;
                border: 1px solid transparent;
                border-radius: 6px;
                background: transparent;
                color: {_TEXT_INACTIVE};
                font-size: 10px;
                font-weight: 800;
            }}
            QPushButton:hover {{
                background: rgba(255,255,255,0.05);
                color: {TEXT_PRIMARY};
            }}
            QPushButton:checked {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 {_rgba(acc, 0.42)},
                    stop:1 {_rgba(acc, 0.24)});
                border-color: {_rgba(acc, 0.52)};
                color: #FFFFFF;
            }}
        """)
        btn.setChecked(code == current_lang)
        btn.clicked.connect(
            lambda _checked=False, c=code:
            app._set_language(c)
            if c != str(getattr(app, "_language", "tr") or "tr")
            else None
        )
        return btn

    tr_btn = _mk_lang_btn("TR", "tr")
    en_btn = _mk_lang_btn("EN", "en")
    lang_layout.addWidget(tr_btn)
    lang_layout.addWidget(en_btn)
    sl.addWidget(lang_wrap, 0, Qt.AlignHCenter)
    sl.addSpacing(8)
    app._sidebar_lang_toggle = lang_wrap

    # Versiyon etiketi ─────────────────────────────────────────────────────
    from core.constants import APP_VERSION
    ver_lbl = QLabel(f"v{APP_VERSION}")
    ver_lbl.setStyleSheet(
        "font-size:9px; font-weight:600; color:#2E3A4A; "
        "background:transparent; border:none;"
    )
    ver_lbl.setAlignment(Qt.AlignHCenter)
    sl.addWidget(ver_lbl, 0, Qt.AlignHCenter)
    sl.addSpacing(2)

    # App referansları ─────────────────────────────────────────────────────
    pl_container = QWidget()
    pl_container.setObjectName("TC")
    pl_layout = QVBoxLayout(pl_container)
    pl_layout.setContentsMargins(0, 0, 0, 0)
    pl_container.hide()

    app._pl_container   = pl_container
    app._pl_layout      = pl_layout
    app._nav_buttons    = nav_buttons

    def _stabilize_sidebar_buttons():
        for key, btn in nav_buttons.items():
            try:
                btn.set_active(key == "home", force=True)
                btn.setFixedHeight(btn._BASE_H)
                btn.setMinimumHeight(btn._BASE_H)
                btn.setMaximumHeight(btn._BASE_H)
                btn.style().unpolish(btn)
                btn.style().polish(btn)
                btn.updateGeometry()
                btn.update()
            except Exception as _e:
                log.debug("Sessiz hata: %s", _e)

    _stabilize_sidebar_buttons()
    QTimer.singleShot(0, _stabilize_sidebar_buttons)
    QTimer.singleShot(140, _stabilize_sidebar_buttons)

    return sidebar


# ── Yardımcı fonksiyonlar ──────────────────────────────────────────────────

def _section_lbl(layout, text: str):
    """Bölüm etiketi — açık gri, okunabilir."""
    lbl = QLabel(text)
    lbl.setStyleSheet(
        "font-size:10px; font-weight:700; color:#5A6880; "
        "padding-left:20px; letter-spacing:2px; "
        "background:transparent;")
    layout.addWidget(lbl)


def _mk_action_btn(text: str, icon_name: str, cmd, layout):
    """Sidebar action button."""
    btn = QPushButton(text)
    btn.setIcon(create_icon(icon_name, _ICON_INACTIVE, 18))
    btn.setIconSize(QSize(18, 18))
    btn.setFocusPolicy(Qt.NoFocus)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setAutoDefault(False)
    btn.setDefault(False)
    btn.setFlat(True)
    btn.setFixedWidth(_BTN_W)
    btn.setFixedHeight(40)
    btn.setStyleSheet(f"""
        QPushButton {{
            text-align:    left;
            padding-left:  16px;
            padding-right: 16px;
            border:        none;
            border-radius: 10px;
            background:    transparent;
            color:         {_TEXT_INACTIVE};
            font-size:     13px;
            font-weight:   600;
        }}
        QPushButton:hover {{
            background: {_BUBBLE_HOVER};
            color:      {TEXT_PRIMARY};
        }}
    """)
    btn.clicked.connect(cmd)
    layout.addWidget(btn, 0, Qt.AlignHCenter)


def _mk_lib_btn(text: str, cmd, layout):
    _mk_action_btn(text, "add", cmd, layout)
