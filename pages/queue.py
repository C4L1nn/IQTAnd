import logging
log = logging.getLogger("iqtMusic")
"""Kuyruk sayfası."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QListWidget, QListWidgetItem, QFrame, QHBoxLayout,
    QLabel, QPushButton, QAbstractItemView
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor

from core.constants import (
    BG_BLACK, BG_CARD, BG_CARD_HOVER, BG_ELEVATED, BORDER_COLOR,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED
)
from core.theme import get_accent, get_accent_hover
from utils.helpers import create_icon
from pages.common import _build_page_header
from ui.widgets import TrackCoverWidget


class _QueueTrackRow(QFrame):
    def __init__(self, app, track, position: int, is_current: bool, is_favorite: bool, parent=None):
        super().__init__(parent)
        self._app = app
        self._track = track
        self._accent = get_accent()
        self._accent_hover = get_accent_hover()
        self.setObjectName("QueueTrackRow")
        self.setAttribute(Qt.WA_StyledBackground, True)

        rl = QHBoxLayout(self)
        rl.setContentsMargins(14, 8, 14, 8)
        rl.setSpacing(10)

        self.glow_line = QFrame()
        self.glow_line.setFixedSize(4, 40)

        self.drag_lbl = QWidget()
        self.drag_lbl.setFixedWidth(0)
        self.drag_lbl.hide()

        self.num_lbl = QLabel()
        self.num_lbl.setFixedWidth(0)
        self.num_lbl.hide()

        self.cover_frame = QFrame()
        self.cover_frame.setFixedSize(48, 48)
        cover_l = QVBoxLayout(self.cover_frame)
        cover_l.setContentsMargins(2, 2, 2, 2)
        cover_l.setSpacing(0)
        self.img = TrackCoverWidget(44, 44, radius=8)
        cover_l.addWidget(self.img)

        title = track.get("title", app._tr("common.unknown_title"))
        artist = ""
        arts = track.get("artists") or []
        if arts:
            artist = arts[0].get("name", "") if isinstance(arts[0], dict) else str(arts[0])

        inf = QVBoxLayout()
        inf.setSpacing(2)
        inf.setContentsMargins(0, 0, 0, 0)
        self.t_lbl = QLabel(title)
        self.t_lbl.setMaximumWidth(360)
        self.a_lbl = QLabel(artist)
        inf.addWidget(self.t_lbl)
        inf.addWidget(self.a_lbl)

        self.btn_frame = QWidget()
        self.btn_frame.setStyleSheet("background:transparent;")
        btn_l = QHBoxLayout(self.btn_frame)
        btn_l.setContentsMargins(0, 0, 0, 0)
        btn_l.setSpacing(6)

        self.play_btn = QPushButton()
        self.play_btn.setFixedSize(30, 30)
        self.play_btn.setIconSize(QSize(16, 16))
        self.play_btn.setCursor(Qt.PointingHandCursor)
        self.play_btn.setFocusPolicy(Qt.NoFocus)
        self.play_btn.clicked.connect(self._play_track)
        btn_l.addWidget(self.play_btn)

        self.remove_btn = QPushButton()
        self.remove_btn.setFixedSize(30, 30)
        self.remove_btn.setIconSize(QSize(14, 14))
        self.remove_btn.setCursor(Qt.PointingHandCursor)
        self.remove_btn.setFocusPolicy(Qt.NoFocus)
        self.remove_btn.clicked.connect(self._remove_track)
        btn_l.addWidget(self.remove_btn)

        self.heart_btn = QPushButton()
        self.heart_btn.setFixedSize(30, 30)
        self.heart_btn.setIconSize(QSize(15, 15))
        self.heart_btn.setCursor(Qt.PointingHandCursor)
        self.heart_btn.setFocusPolicy(Qt.NoFocus)
        self.heart_btn.clicked.connect(self._toggle_favorite)
        btn_l.addWidget(self.heart_btn)

        rl.addWidget(self.glow_line, 0, Qt.AlignVCenter)
        rl.addWidget(self.drag_lbl, 0, Qt.AlignVCenter)
        rl.addWidget(self.num_lbl, 0, Qt.AlignVCenter)
        rl.addWidget(self.cover_frame, 0, Qt.AlignVCenter)
        rl.addLayout(inf, 1)
        rl.addWidget(self.btn_frame, 0, Qt.AlignVCenter)

        thumb = app._thumb(track)
        if thumb:
            app._load_image(thumb, self.img, (44, 44))

        self.update_state(position, is_current, is_favorite)

    def refresh_content(self, track):
        self._track = track

        title = track.get("title", self._app._tr("common.unknown_title"))
        artist = ""
        arts = track.get("artists") or []
        if arts:
            artist = arts[0].get("name", "") if isinstance(arts[0], dict) else str(arts[0])

        if self.t_lbl.text() != title:
            self.t_lbl.setText(title)
        if self.a_lbl.text() != artist:
            self.a_lbl.setText(artist)

        thumb = self._app._thumb(track)
        if thumb:
            self._app._load_image(thumb, self.img, (44, 44))

    def _play_track(self):
        self._app.force_play(self._track)
        try:
            self._app._refresh_queue_page_state()
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)

    def _toggle_favorite(self):
        self._app._toggle_fav(self._track, self.heart_btn)
        try:
            self._app._refresh_queue_page_state()
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)

    def _remove_track(self):
        self._app._remove_from_queue_at(getattr(self, "_queue_pos", -1))

    def update_state(self, position: int, is_current: bool, is_favorite: bool):
        self._accent = get_accent()
        self._accent_hover = get_accent_hover()
        self._queue_pos = max(0, position - 1)
        base_bg = f"{self._accent}16" if is_current else BG_CARD
        base_mid = BG_CARD_HOVER if is_current else BG_ELEVATED
        border = f"{self._accent}54" if is_current else BORDER_COLOR
        glow_start = self._accent if is_current else f"{self._accent}55"
        glow_end = self._accent_hover if is_current else f"{self._accent_hover}33"

        self.setStyleSheet(f"""
            QFrame#QueueTrackRow {{
                background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {base_bg}, stop:0.68 {base_mid}, stop:1 {BG_CARD});
                border-radius:16px;
                border:1px solid {border};
            }}
            QFrame#QueueTrackRow:hover {{
                background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {self._accent}16, stop:0.68 {BG_CARD_HOVER}, stop:1 {BG_ELEVATED});
                border:1px solid {self._accent}72;
            }}
            QFrame#QueueTrackRow QLabel {{
                border:none;
                background:transparent;
            }}
        """)

        self.glow_line.setStyleSheet(
            f"background:qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 {glow_start}, stop:1 {glow_end}); "
            "border-radius:2px; border:none;")

        if is_current:
            self.num_lbl.setText("▶")
            self.num_lbl.setStyleSheet(
                f"color:{self._accent}; font-size:12px; font-weight:800; background:transparent;")
        else:
            self.num_lbl.setText(str(position))
            self.num_lbl.setStyleSheet(
                f"color:{TEXT_MUTED}; font-size:12px; font-weight:600; background:transparent;")

        cover_border = f"{self._accent}40" if is_current else BORDER_COLOR
        self.cover_frame.setStyleSheet(
            f"background:#101826; border-radius:10px; border:1px solid {cover_border};")
        self.img.setStyleSheet("background:#121926; border-radius:8px;")

        self.t_lbl.setStyleSheet(
            f"font-size:13px; font-weight:{'800' if is_current else '650'}; "
            f"color:{self._accent if is_current else TEXT_PRIMARY}; background:transparent;")
        self.a_lbl.setStyleSheet(
            f"font-size:11px; color:{TEXT_MUTED}; background:transparent;")

        self.play_btn.setIcon(create_icon("play", self._accent, 16))
        self.play_btn.setStyleSheet(f"""
            QPushButton {{
                background:transparent;
                border:none;
                border-radius:15px;
            }}
            QPushButton:hover {{
                background:{self._accent}20;
            }}
        """)

        self.remove_btn.setIcon(create_icon("close", TEXT_MUTED, 14))
        self.remove_btn.setStyleSheet(f"""
            QPushButton {{
                background:transparent;
                border:none;
                border-radius:15px;
            }}
            QPushButton:hover {{
                background:rgba(255,107,107,0.14);
            }}
        """)

        self.heart_btn.setIcon(create_icon(
            "heart_on" if is_favorite else "heart_off",
            self._accent if is_favorite else TEXT_MUTED, 15))
        self.heart_btn.setStyleSheet(f"""
            QPushButton {{
                background:transparent;
                border:none;
                border-radius:15px;
            }}
            QPushButton:hover {{
                background:{self._accent}14;
            }}
        """)


class _DragQueueList(QListWidget):
    """
    Sürükle-bırak ile yeniden sıralama destekli kuyruk listesi.
    Sıralama değişince app.queue güncellenir.
    """
    def __init__(self, app):
        super().__init__()
        self._app = app
        acc = get_accent()
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setSpacing(6)
        self.setStyleSheet(f"""
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
                min-height: 48px;
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
        """)
        self.model().rowsMoved.connect(self._sync_queue)

    def _sync_queue(self):
        current_vid = ""
        if self._app.queue and 0 <= self._app.queue_index < len(self._app.queue):
            current_vid = self._app.queue[self._app.queue_index].get("videoId", "")

        new_queue = []
        for i in range(self.count()):
            item = self.item(i)
            if item:
                track = item.data(Qt.UserRole)
                if track:
                    new_queue.append(track)
        self._app.queue = new_queue
        if current_vid:
            for i, track in enumerate(self._app.queue):
                if track.get("videoId") == current_vid:
                    self._app.queue_index = i
                    break
        self._app._queue_refresh_state = None
        try:
            self._app._refresh_queue_page_state()
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)


def _queue_current_video_id(app) -> str:
    target_vid = str(getattr(app, "target_vid", "") or "").strip()
    if target_vid:
        return target_vid
    try:
        if app.queue and 0 <= app.queue_index < len(app.queue):
            return str(app.queue[app.queue_index].get("videoId", "") or "").strip()
    except Exception:
        pass
    return ""


def _queue_row_is_current(app, track: dict, index: int, current_vid: str) -> bool:
    vid = str((track or {}).get("videoId", "") or "").strip()
    if current_vid and vid:
        return vid == current_vid
    return index == getattr(app, "queue_index", -1)


def _rebuild_queue_list(app, queue_list):
    if queue_list is None:
        return

    scroll_value = queue_list.verticalScrollBar().value()
    queue_list.setUpdatesEnabled(False)
    queue_list.clear()

    fav_vids = {fav.get("videoId", "") for fav in app.favorites}
    current_vid = _queue_current_video_id(app)
    for i, track in enumerate(app.queue):
        item = QListWidgetItem()
        item.setData(Qt.UserRole, track)
        item.setSizeHint(QSize(0, 76))

        holder = QWidget()
        holder.setStyleSheet("background:transparent;")
        holder_l = QVBoxLayout(holder)
        holder_l.setContentsMargins(0, 3, 0, 3)
        holder_l.setSpacing(0)

        row = _QueueTrackRow(
            app,
            track,
            i + 1,
            _queue_row_is_current(app, track, i, current_vid),
            track.get("videoId", "") in fav_vids,
        )
        holder._queue_row = row
        holder_l.addWidget(row)

        queue_list.addItem(item)
        queue_list.setItemWidget(item, holder)

    queue_list.setUpdatesEnabled(True)
    queue_list.verticalScrollBar().setValue(
        min(scroll_value, queue_list.verticalScrollBar().maximum())
    )


def _refresh_queue_list_rows(app, queue_list) -> bool:
    if queue_list is None or queue_list.count() != len(app.queue):
        return False

    fav_vids = {fav.get("videoId", "") for fav in app.favorites}
    current_vid = _queue_current_video_id(app)
    for i, track in enumerate(app.queue):
        item = queue_list.item(i)
        if item is None:
            return False

        item_track = item.data(Qt.UserRole) or {}
        if item_track.get("videoId", "") != track.get("videoId", ""):
            return False

        holder = queue_list.itemWidget(item)
        row = getattr(holder, "_queue_row", None) if holder is not None else None
        if row is None:
            return False

        item.setData(Qt.UserRole, track)
        row.refresh_content(track)
        row.update_state(
            i + 1,
            _queue_row_is_current(app, track, i, current_vid),
            track.get("videoId", "") in fav_vids,
        )

    return True


def build_queue_page(app):
    pg = QWidget()
    pg.setStyleSheet(f"background:{BG_BLACK};")
    vl = QVBoxLayout(pg)
    vl.setContentsMargins(36, 36, 36, 20)
    vl.setSpacing(0)

    vl.addWidget(_build_page_header(
        app,
        app._tr("queue.title"),
        app._tr("queue.subtitle", count=len(app.queue)),
        eyebrow=app._tr("queue.eyebrow"),
    ))
    vl.addSpacing(18)

    queue_list = _DragQueueList(app)
    app._queue_list_widget = queue_list
    _rebuild_queue_list(app, queue_list)

    app._queue_page_refs = {
        "title_label": None,
        "hint_label": None,
        "list_widget": queue_list,
    }
    vl.addWidget(queue_list)
    return pg
