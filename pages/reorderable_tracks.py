"""Reusable drag-and-drop track lists for library pages."""

import logging

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.constants import (
    BG_BLACK,
    BG_CARD,
    BG_CARD_HOVER,
    BG_ELEVATED,
    BORDER_COLOR,
    TEXT_MUTED,
    TEXT_PRIMARY,
)
from core.theme import get_accent
from utils.helpers import create_icon, safe_save_json
from ui.widgets import TrackCoverWidget

log = logging.getLogger("iqtMusic")


class _LibraryTrackRow(QFrame):
    def __init__(self, app, track: dict, position: int, source_kind: str, parent=None):
        super().__init__(parent)
        self._app = app
        self._track = track
        self._source_kind = source_kind
        self._accent = get_accent()
        self.setObjectName("LibraryTrackRow")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(
            f"""
            QFrame#LibraryTrackRow {{
                background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {BG_CARD}, stop:1 {BG_ELEVATED});
                border-radius:16px;
                border:1px solid {BORDER_COLOR};
            }}
            QFrame#LibraryTrackRow:hover {{
                background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {BG_CARD_HOVER}, stop:1 {BG_ELEVATED});
                border-color:{self._accent}55;
            }}
            QFrame#LibraryTrackRow QLabel {{
                background:transparent;
                border:none;
            }}
            """
        )

        row_l = QHBoxLayout(self)
        row_l.setContentsMargins(12, 10, 12, 10)
        row_l.setSpacing(12)

        drag_lbl = QLabel("::")
        drag_lbl.setFixedWidth(14)
        drag_lbl.setAlignment(Qt.AlignCenter)
        drag_lbl.setToolTip("Surukle birak")
        drag_lbl.setStyleSheet(
            f"color:{TEXT_MUTED}; font-size:15px; font-weight:700;"
        )

        pos_lbl = QLabel(str(position))
        pos_lbl.setFixedWidth(28)
        pos_lbl.setAlignment(Qt.AlignCenter)
        pos_lbl.setStyleSheet(
            f"color:{TEXT_MUTED}; font-size:12px; font-weight:600;"
        )

        img = TrackCoverWidget(52, 52, radius=8)

        thumb = app._thumb(track, big=True)
        if thumb:
            app._load_image(thumb, img, (52, 52))
        else:
            try:
                fallback = create_icon("music", TEXT_MUTED, 32)
                img.setPixmap(fallback.pixmap(32, 32))
            except Exception as _e:
                log.debug("Sessiz hata: %s", _e)

        info = QVBoxLayout()
        info.setContentsMargins(0, 0, 0, 0)
        info.setSpacing(3)

        title_lbl = QLabel(track.get("title", "Bilinmiyor"))
        title_lbl.setStyleSheet(
            f"color:{TEXT_PRIMARY}; font-size:14px; font-weight:800;"
        )

        artist_lbl = QLabel(app._artist_str(track))
        artist_lbl.setStyleSheet(
            f"color:{TEXT_MUTED}; font-size:11px;"
        )

        info.addWidget(title_lbl)
        info.addWidget(artist_lbl)

        tags = []
        vid = track.get("videoId", "")
        if (
            source_kind != "favorites"
            and vid
            and any(fav.get("videoId") == vid for fav in app.favorites)
        ):
            tags.append("Favori")
        if source_kind != "downloads" and app.dl.is_downloaded(vid):
            tags.append("Offline")
        if tags:
            tag_lbl = QLabel(" | ".join(tags))
            tag_lbl.setStyleSheet(
                f"color:{self._accent}; font-size:10px; font-weight:700;"
            )
            info.addWidget(tag_lbl)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(6)

        play_btn = QPushButton()
        play_btn.setFixedSize(30, 30)
        play_btn.setCursor(Qt.PointingHandCursor)
        play_btn.setFocusPolicy(Qt.NoFocus)
        play_btn.setIcon(create_icon("play", self._accent, 16))
        play_btn.setIconSize(QSize(16, 16))
        play_btn.setStyleSheet(
            f"QPushButton{{background:transparent; border:none; border-radius:15px;}}"
            f"QPushButton:hover{{background:{self._accent}22;}}"
        )
        play_btn.clicked.connect(lambda: app.force_play(track))

        heart_on = any(fav.get("videoId") == vid for fav in app.favorites)
        self._heart_btn = QPushButton()
        self._heart_btn.setFixedSize(30, 30)
        self._heart_btn.setCursor(Qt.PointingHandCursor)
        self._heart_btn.setFocusPolicy(Qt.NoFocus)
        self._heart_btn.setIcon(
            create_icon(
                "heart_on" if heart_on else "heart_off",
                self._accent if heart_on else TEXT_MUTED,
                16,
            )
        )
        self._heart_btn.setIconSize(QSize(16, 16))
        self._heart_btn.setStyleSheet(
            f"QPushButton{{background:transparent; border:none; border-radius:15px;}}"
            f"QPushButton:hover{{background:{self._accent}18;}}"
        )
        self._heart_btn.clicked.connect(self._toggle_favorite)

        actions.addWidget(play_btn)
        actions.addWidget(self._heart_btn)

        row_l.addWidget(drag_lbl, 0, Qt.AlignVCenter)
        row_l.addWidget(pos_lbl, 0, Qt.AlignVCenter)
        row_l.addWidget(img, 0, Qt.AlignVCenter)
        row_l.addLayout(info, 1)
        row_l.addLayout(actions, 0)

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(
            lambda _pos: app._ctx_menu(QCursor.pos(), track)
        )

    def _toggle_favorite(self):
        self._app._toggle_fav(self._track, self._heart_btn)


class _ReorderableTrackList(QListWidget):
    def __init__(self, app, source_kind: str):
        super().__init__()
        self._app = app
        self._source_kind = source_kind
        acc = get_accent()
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setSpacing(6)
        self.setStyleSheet(
            f"""
            QListWidget {{
                background: transparent;
                border: none;
                outline: none;
                padding-right: 6px;
            }}
            QListWidget::item {{
                background: transparent;
                border: none;
                margin: 0;
                padding: 0;
            }}
            QListWidget::item:selected {{
                background: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 10px;
                margin: 6px 0;
            }}
            QScrollBar::handle:vertical {{
                background: {BORDER_COLOR};
                border-radius: 5px;
                min-height: 40px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {acc}88;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: transparent;
                border: none;
                height: 0;
            }}
            """
        )

    def dropEvent(self, event):
        super().dropEvent(event)
        self._sync_collection()
        QTimer.singleShot(0, self._reinstall_widgets)
        event.accept()

    def _ordered_tracks(self) -> list:
        ordered = []
        for index in range(self.count()):
            item = self.item(index)
            if item is None:
                continue
            track = item.data(Qt.UserRole)
            if track:
                ordered.append(track)
        return ordered

    def _sync_collection(self):
        ordered = self._ordered_tracks()
        if self._source_kind == "favorites":
            self._app.favorites = ordered
            safe_save_json(self._app.fav_file, self._app.favorites)
            return
        if self._source_kind == "downloads":
            self._app.dl.reorder_tracks(ordered)

    def _reinstall_widgets(self):
        for index in range(self.count()):
            item = self.item(index)
            if item is None:
                continue
            track = item.data(Qt.UserRole)
            if not track:
                continue
            holder = _make_holder(self._app, track, index + 1, self._source_kind)
            self.setItemWidget(item, holder)


def _make_holder(app, track: dict, position: int, source_kind: str) -> QWidget:
    holder = QWidget()
    holder.setStyleSheet("background:transparent;")
    holder_l = QVBoxLayout(holder)
    holder_l.setContentsMargins(0, 3, 0, 3)
    holder_l.setSpacing(0)
    holder_l.addWidget(_LibraryTrackRow(app, track, position, source_kind))
    return holder


def _populate_list(lst: _ReorderableTrackList, app, tracks: list, source_kind: str):
    for index, track in enumerate(tracks):
        item = QListWidgetItem()
        item.setData(Qt.UserRole, track)
        item.setSizeHint(QSize(0, 82))
        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDragEnabled)
        lst.addItem(item)
        lst.setItemWidget(item, _make_holder(app, track, index + 1, source_kind))


def build_reorderable_track_panel(app, tracks: list, source_kind: str, empty_text: str) -> QWidget:
    if not tracks:
        empty = QLabel(empty_text)
        empty.setAlignment(Qt.AlignCenter)
        empty.setStyleSheet(
            f"background:{BG_BLACK}; color:{TEXT_MUTED}; font-size:14px;"
        )
        return empty

    app._prime_stream_urls(tracks, limit=4)
    lst = _ReorderableTrackList(app, source_kind)
    _populate_list(lst, app, tracks, source_kind)
    return lst
