"""Favorites page."""

from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.constants import BG_BLACK, BG_CARD, BG_CARD_HOVER, BG_ELEVATED, BORDER_COLOR, TEXT_MUTED, TEXT_PRIMARY
from core.theme import get_accent
from pages.common import _build_page_header
from pages.reorderable_tracks import build_reorderable_track_panel
from ui.widgets import ClickableFrame
from utils.helpers import create_icon


def _tab_button(app, text: str, checked: bool = False) -> QPushButton:
    acc = get_accent()
    btn = QPushButton(text)
    btn.setCheckable(True)
    btn.setChecked(checked)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setFixedHeight(38)
    btn.setStyleSheet(f"""
        QPushButton {{
            background:{acc}18;
            color:{TEXT_PRIMARY};
            border:1px solid {acc}44;
            border-radius:14px;
            padding:0 16px;
            font-size:12px;
            font-weight:800;
        }}
        QPushButton:!checked {{
            background:{BG_CARD};
            color:{TEXT_MUTED};
            border-color:{BORDER_COLOR};
        }}
        QPushButton:hover {{
            background:{BG_CARD_HOVER};
            border-color:{acc}66;
            color:{TEXT_PRIMARY};
        }}
    """)
    return btn


def _artist_card(app, artist: dict) -> QWidget:
    acc = get_accent()
    name = str(artist.get("name", "") or "").strip() or app._tr("artist.unknown")
    browse_id = str(artist.get("browseId", "") or "").strip()
    meta = artist.get("artist_meta") if isinstance(artist.get("artist_meta"), dict) else {}
    image_url = str(artist.get("image_url") or meta.get("image_url") or "").strip()
    is_liked = app._is_artist_liked(name)

    card = ClickableFrame()
    card.setObjectName("LikedArtistCard")
    card.setAttribute(Qt.WA_StyledBackground, True)
    card.setCursor(Qt.PointingHandCursor)
    card.setStyleSheet(f"""
        QFrame#LikedArtistCard {{
            background:qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 {BG_CARD}, stop:1 {BG_ELEVATED});
            border-radius:16px;
            border:1px solid {BORDER_COLOR};
        }}
        QFrame#LikedArtistCard:hover {{
            background:qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 {BG_CARD_HOVER}, stop:1 {BG_ELEVATED});
            border-color:{acc}66;
        }}
        QFrame#LikedArtistCard QLabel {{
            background:transparent;
            border:none;
        }}
    """)

    row = QHBoxLayout(card)
    row.setContentsMargins(14, 12, 14, 12)
    row.setSpacing(12)

    avatar = QLabel()
    avatar.setFixedSize(52, 52)
    avatar.setAlignment(Qt.AlignCenter)
    avatar.setStyleSheet(f"background:{BG_BLACK}; border-radius:26px; color:{TEXT_MUTED}; font-weight:900;")
    if image_url:
        app._load_image(image_url, avatar, (52, 52))
    else:
        avatar.setPixmap(create_icon("music", TEXT_MUTED, 24).pixmap(24, 24))
    row.addWidget(avatar, 0, Qt.AlignVCenter)

    text_col = QVBoxLayout()
    text_col.setContentsMargins(0, 0, 0, 0)
    text_col.setSpacing(4)
    title = QLabel(name)
    title.setStyleSheet(f"color:{TEXT_PRIMARY}; font-size:14px; font-weight:850;")
    sub = QLabel(app._tr("favorites.artist_open"))
    sub.setStyleSheet(f"color:{TEXT_MUTED}; font-size:11px;")
    text_col.addWidget(title)
    text_col.addWidget(sub)
    row.addLayout(text_col, 1)

    like_btn = QPushButton()
    like_btn.setFixedSize(32, 32)
    like_btn.setFocusPolicy(Qt.NoFocus)
    like_btn.setCursor(Qt.PointingHandCursor)
    like_btn.setIcon(create_icon("heart_on" if is_liked else "heart_off", acc if is_liked else TEXT_MUTED, 17))
    like_btn.setIconSize(QSize(17, 17))
    like_btn.setToolTip(app._tr("artist.unlike" if is_liked else "artist.like"))
    like_btn.setStyleSheet(
        f"QPushButton{{background:transparent; border:none; border-radius:16px;}}"
        f"QPushButton:hover{{background:{acc}18;}}"
    )
    like_btn.clicked.connect(lambda: app._toggle_artist_like(name, browse_id, meta, like_btn))
    row.addWidget(like_btn, 0, Qt.AlignVCenter)

    card.clicked.connect(lambda: app._open_artist_name(name, browse_id))
    return card


def _build_artists_panel(app) -> QWidget:
    artists = [
        item for item in list(getattr(app, "liked_artists", []) or [])
        if isinstance(item, dict) and str(item.get("name", "") or "").strip()
    ]
    if not artists:
        empty = QLabel(app._tr("favorites.artists_empty"))
        empty.setAlignment(Qt.AlignCenter)
        empty.setStyleSheet(f"background:{BG_BLACK}; color:{TEXT_MUTED}; font-size:14px;")
        return empty

    sc = QScrollArea()
    sc.setWidgetResizable(True)
    sc.setFrameShape(QFrame.NoFrame)
    sc.setStyleSheet("background:transparent; border:none;")

    host = QWidget()
    host.setStyleSheet("background:transparent;")
    layout = QVBoxLayout(host)
    layout.setContentsMargins(0, 0, 6, 10)
    layout.setSpacing(8)
    for artist in artists:
        layout.addWidget(_artist_card(app, artist))
    layout.addStretch()
    sc.setWidget(host)
    return sc


def build_favs_page(app):
    app.current_page = "favorites"
    t = app._tr
    artist_count = len([item for item in getattr(app, "liked_artists", []) if isinstance(item, dict)])

    pg = QWidget()
    pg.setStyleSheet(f"background:{BG_BLACK};")
    vl = QVBoxLayout(pg)
    vl.setContentsMargins(36, 36, 36, 0)
    vl.setSpacing(0)
    vl.addWidget(
        _build_page_header(
            app,
            t("favorites.title"),
            t("favorites.subtitle_mixed", tracks=len(app.favorites), artists=artist_count),
            eyebrow=t("favorites.eyebrow"),
        )
    )
    vl.addSpacing(18)

    tabs = QWidget()
    tabs.setStyleSheet("background:transparent;")
    tabs_l = QHBoxLayout(tabs)
    tabs_l.setContentsMargins(0, 0, 0, 0)
    tabs_l.setSpacing(10)
    songs_btn = _tab_button(app, t("favorites.tab.songs"), checked=True)
    artists_btn = _tab_button(app, t("favorites.tab.artists"))
    tabs_l.addWidget(songs_btn)
    tabs_l.addWidget(artists_btn)
    tabs_l.addStretch()
    vl.addWidget(tabs)
    vl.addSpacing(14)

    stack = QStackedWidget()
    stack.addWidget(
        build_reorderable_track_panel(
            app,
            list(app.favorites),
            "favorites",
            t("favorites.empty"),
        )
    )
    stack.addWidget(_build_artists_panel(app))
    vl.addWidget(stack, 1)

    def _select(index: int):
        stack.setCurrentIndex(index)
        songs_btn.setChecked(index == 0)
        artists_btn.setChecked(index == 1)

    songs_btn.clicked.connect(lambda: _select(0))
    artists_btn.clicked.connect(lambda: _select(1))
    return pg
