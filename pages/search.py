import logging
log = logging.getLogger("iqtMusic")
"""Arama sayfası."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QGridLayout, QLineEdit, QListWidget, QAbstractItemView
)
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor

from core.constants import (
    BG_BLACK, BG_CARD, BG_CARD_HOVER, BG_ELEVATED, BORDER_COLOR,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED
)
from core.theme import get_accent, get_accent_hover
from utils.helpers import create_icon, safe_save_json
from ui.widgets import ClickableFrame
from pages.common import _build_page_header


_FILTER_TABS = [
    ("search.filter.songs", "songs"),
    ("search.filter.albums", "albums"),
    ("search.filter.artists", "artists"),
    ("search.filter.playlists", "playlists"),
]


def _chip_ss(active: bool, acc: str) -> str:
    if active:
        return (
            f"QPushButton{{background:{acc}; color:#081208; border:none; "
            f"border-radius:17px; padding:0 18px; font-size:12px; font-weight:900;}}"
        )
    return (
        f"QPushButton{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
        f"stop:0 {BG_ELEVATED},stop:1 {BG_CARD}); color:{TEXT_PRIMARY};"
        f"border:1px solid {BORDER_COLOR}; border-radius:17px;"
        f"padding:0 18px; font-size:12px; font-weight:700;}}"
        f"QPushButton:hover{{background:{BG_CARD_HOVER}; border-color:{acc}55; color:{acc};}}"
    )


def build_search_page(app):
    app.current_page = "search"
    t = app._tr

    pg = QWidget()
    pg.setStyleSheet(f"background:{BG_BLACK};")
    vl = QVBoxLayout(pg)
    vl.setContentsMargins(36, 36, 36, 0)
    vl.setSpacing(0)

    vl.addWidget(_build_page_header(
        app,
        t("search.title"),
        t("search.subtitle"),
        eyebrow=t("search.eyebrow"),
    ))
    vl.addSpacing(18)

    sb_frame = QFrame()
    sb_frame.setFixedHeight(52)
    sb_frame.setStyleSheet(
        f"background:qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {BG_ELEVATED}, stop:1 {BG_CARD}); "
        f"border-radius:26px; border:1px solid {BORDER_COLOR};"
    )
    sb_inner = QHBoxLayout(sb_frame)
    sb_inner.setContentsMargins(0, 0, 8, 0)
    sb_inner.setSpacing(6)

    icon_lbl = QLabel()
    icon_lbl.setPixmap(create_icon("search", TEXT_MUTED, 20).pixmap(20, 20))
    icon_lbl.setStyleSheet("background:transparent; padding:0 14px;")
    icon_lbl.setFixedSize(50, 52)

    app._search_box = QLineEdit()
    app._search_box.setPlaceholderText(t("search.placeholder"))
    app._search_box.setFixedHeight(52)
    app._search_box.setStyleSheet(
        f"background:transparent; color:{TEXT_PRIMARY}; border:none; "
        f"border-radius:0; padding-left:0; font-size:15px; font-weight:500;"
    )
    app._search_box.textChanged.connect(app._on_search_text_changed)
    app._search_box.returnPressed.connect(app._do_search)
    if app._search_cache.get("q"):
        app._search_box.setText(app._search_cache["q"])

    search_btn = QPushButton(t("search.button"))
    search_btn.setFixedSize(88, 38)
    search_btn.setCursor(Qt.PointingHandCursor)
    search_btn.setIcon(create_icon("search", BG_BLACK, 16))
    search_btn.setStyleSheet(f"""
        QPushButton {{
            background: {get_accent()};
            color: {BG_BLACK};
            border: none;
            border-radius: 19px;
            padding: 0 14px;
            font-size: 12px;
            font-weight: 800;
        }}
        QPushButton:hover {{
            background: {get_accent_hover()};
        }}
        QPushButton:pressed {{
            background: {get_accent()}CC;
        }}
    """)
    search_btn.clicked.connect(app._do_search)

    clear_btn = QPushButton()
    clear_btn.setFixedSize(38, 38)
    clear_btn.setCursor(Qt.PointingHandCursor)
    clear_btn.setToolTip(t("search.clear_tooltip"))
    clear_btn.setIcon(create_icon("close", TEXT_MUTED, 14))
    clear_btn.setIconSize(QSize(14, 14))
    clear_btn.setStyleSheet(f"""
        QPushButton {{
            background: transparent;
            border: 1px solid {BORDER_COLOR};
            border-radius: 19px;
        }}
        QPushButton:hover {{
            background: {BG_CARD_HOVER};
            border-color: {get_accent()}55;
        }}
        QPushButton:disabled {{
            border-color: {BORDER_COLOR};
            opacity: 0.55;
        }}
    """)

    def _clear_query():
        app._search_box.clear()
        app._hide_search_suggestions()
        try:
            app._clear_layout(app._res_layout)
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
        app._search_box.setFocus()

    def _sync_clear_button_state(text: str):
        clear_btn.setEnabled(bool(str(text or "").strip()))

    clear_btn.clicked.connect(_clear_query)
    app._search_box.textChanged.connect(_sync_clear_button_state)

    sb_inner.addWidget(icon_lbl)
    sb_inner.addWidget(app._search_box)
    sb_inner.addWidget(search_btn, 0, Qt.AlignVCenter)
    sb_inner.addWidget(clear_btn, 0, Qt.AlignVCenter)
    vl.addWidget(sb_frame)
    _sync_clear_button_state(app._search_box.text())

    # ── Filtre chip'leri ────────────────────────────────────────────────────
    chip_bar = QFrame()
    chip_bar.setStyleSheet("background:transparent; border:none;")
    chip_row = QHBoxLayout(chip_bar)
    chip_row.setContentsMargins(0, 10, 0, 0)
    chip_row.setSpacing(8)

    acc = get_accent()
    current_filter = getattr(app, "_search_filter", "songs")
    app._search_filter_btns = {}

    for label_key, key in _FILTER_TABS:
        btn = QPushButton(t(label_key))
        btn.setFixedHeight(34)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFocusPolicy(Qt.NoFocus)
        btn.setStyleSheet(_chip_ss(key == current_filter, acc))
        btn.clicked.connect(lambda _, k=key: app._switch_search_filter(k))
        chip_row.addWidget(btn)
        app._search_filter_btns[key] = btn

    chip_row.addStretch()
    vl.addWidget(chip_bar)
    # ───────────────────────────────────────────────────────────────────────

    app._search_suggest = QListWidget()
    app._search_suggest.hide()
    app._search_suggest.setMaximumHeight(176)
    app._search_suggest.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    app._search_suggest.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
    app._search_suggest.setSpacing(2)
    app._search_suggest.setStyleSheet(f"""
        QListWidget {{
            background: {BG_CARD};
            border: 1px solid {BORDER_COLOR};
            border-radius: 14px;
            color: {TEXT_PRIMARY};
            padding: 4px;
            outline: none;
        }}
        QListWidget::item {{
            background: transparent;
            border-radius: 9px;
            padding: 7px 10px;
            font-size: 12px;
            font-weight: 600;
        }}
        QListWidget::item:selected {{
            background: {get_accent()}22;
            color: {get_accent()};
        }}
        QListWidget::item:hover {{
            background: {BG_CARD_HOVER};
        }}
    """)
    app._search_suggest.itemClicked.connect(
        lambda item: app._apply_search_suggestion(item.text())
    )
    vl.addWidget(app._search_suggest)
    vl.addSpacing(12)

    if app._search_history:
        hist_frame = QFrame()
        hist_frame.setStyleSheet("background:transparent;")
        hist_v = QVBoxLayout(hist_frame)
        hist_v.setContentsMargins(0, 0, 0, 0)
        hist_v.setSpacing(8)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)
        hist_lbl = QLabel(t("search.recent_searches"))
        hist_lbl.setStyleSheet(
            f"color:{TEXT_MUTED}; font-size:14px; font-weight:600; background:transparent;"
        )
        top_row.addWidget(hist_lbl)
        top_row.addStretch()

        def _clear_history():
            app._search_history.clear()
            try:
                safe_save_json(app._search_hist_file, [])
            except Exception as _e:
                log.debug("Sessiz hata: %s", _e)
            app.page_search()

        clear_btn = QPushButton(t("search.clear_history"))
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {TEXT_MUTED};
                border: 1px solid {BORDER_COLOR};
                border-radius: 14px; padding: 5px 12px;
                font-size: 11px; font-weight: 600;
            }}
            QPushButton:hover {{
                color: {get_accent()}; border-color: {get_accent()}66;
                background: {get_accent()}10;
            }}
        """)
        clear_btn.clicked.connect(_clear_history)
        top_row.addWidget(clear_btn)
        hist_v.addLayout(top_row)

        chip_row = QHBoxLayout()
        chip_row.setContentsMargins(0, 0, 0, 0)
        chip_row.setSpacing(8)
        chip_ss = f"""
            QPushButton {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {BG_ELEVATED}, stop:1 {BG_CARD});
                color: {TEXT_PRIMARY}; border: 1px solid {BORDER_COLOR};
                border-radius: 14px; padding: 6px 14px;
                font-size: 12px; font-weight: 650;
                max-width: 160px;
            }}
            QPushButton:hover {{ background: {BG_CARD_HOVER}; border-color: {get_accent()}55; }}
        """
        for q in app._search_history[:8]:
            display = q if len(q) <= 18 else q[:16] + "..."
            btn = QPushButton(display)
            btn.setToolTip(q)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(chip_ss)
            btn.clicked.connect(lambda _, x=q: app._quick_search(x))
            chip_row.addWidget(btn)

        chip_row.addStretch()
        hist_v.addLayout(chip_row)
        vl.addWidget(hist_frame)
        vl.addSpacing(12)

    app._res_scroll = QScrollArea()
    app._res_scroll.setWidgetResizable(True)
    app._res_scroll.setStyleSheet("background:transparent; border:none;")
    app._res_ct = QWidget()
    app._res_ct.setObjectName("TC")
    app._res_layout = QVBoxLayout(app._res_ct)
    app._res_layout.setContentsMargins(0, 0, 0, 24)
    app._res_layout.setSpacing(8)
    app._res_scroll.setWidget(app._res_ct)
    vl.addWidget(app._res_scroll)

    if app._search_cache.get("results"):
        _flt = getattr(app, "_search_filter", "songs")
        if _flt == "albums":
            app._list_albums(app._search_cache["results"], app._res_ct, app._res_layout)
        elif _flt == "artists":
            app._list_artists(app._search_cache["results"], app._res_ct, app._res_layout)
        elif _flt == "playlists":
            app._list_playlists(app._search_cache["results"], app._res_ct, app._res_layout)
        else:
            app._list_tracks(app._search_cache["results"], app._res_ct, app._res_layout)
    elif app._search_cache.get("q"):
        app._update_search_suggestions(app._search_cache["q"])

    app._search_box.setFocus()
    return pg
