"""Lyrics dialog."""
from PySide6.QtCore import QEvent, QObject, QPoint, Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMenu,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from core.constants import BG_BLACK, BORDER_COLOR, TEXT_MUTED, TEXT_SECONDARY
from core.theme import get_accent
from ui.lyrics_delegate import LyricsDelegate
from ui.titlebar import TitleBar
from ui.widgets import TrackCoverWidget
from utils.helpers import qt_is_valid


class _LyricsResizeFilter(QObject):
    def __init__(self, dialog, on_resize=None):
        super().__init__(dialog)
        self._dialog = dialog
        self._on_resize = on_resize
        self._margin = 6
        self._active = False
        self._start = QPoint()
        self._geom = dialog.frameGeometry()
        self._edges = (False, False, False, False)

    def bind(self):
        dialog = self._dialog
        if dialog is None or not qt_is_valid(dialog):
            return
        dialog.installEventFilter(self)
        for widget in [dialog, *dialog.findChildren(QWidget)]:
            try:
                widget.installEventFilter(self)
                widget.setMouseTracking(True)
            except Exception:
                pass

    def eventFilter(self, obj, event):
        dialog = self._dialog
        if dialog is None or not qt_is_valid(dialog):
            return False

        event_type = event.type()
        if obj is dialog and event_type == QEvent.Resize:
            if callable(self._on_resize):
                self._on_resize()
            return False

        if event_type == QEvent.Leave and not self._active:
            self._clear_cursor()
            return False

        if event_type not in (QEvent.MouseButtonPress, QEvent.MouseMove, QEvent.MouseButtonRelease):
            return False

        if dialog.isMaximized() or dialog.isFullScreen():
            self._clear_cursor()
            return False

        global_pos = event.globalPosition().toPoint()
        left, right, top, bottom = self._resize_edges(global_pos)
        near_edge = any((left, right, top, bottom))

        if event_type == QEvent.MouseButtonPress:
            if event.button() == Qt.LeftButton and near_edge:
                self._active = True
                self._start = global_pos
                self._geom = dialog.frameGeometry()
                self._edges = (left, right, top, bottom)
                self._apply_cursor(obj, left, right, top, bottom)
                return True
            return False

        if event_type == QEvent.MouseMove:
            if self._active and (event.buttons() & Qt.LeftButton):
                self._resize_to(global_pos)
                self._apply_cursor(obj, *self._edges)
                return True
            if near_edge:
                self._apply_cursor(obj, left, right, top, bottom)
            else:
                self._clear_cursor()
            return False

        if event.button() == Qt.LeftButton and self._active:
            self._active = False
            if near_edge:
                self._apply_cursor(obj, left, right, top, bottom)
            else:
                self._clear_cursor()
            return True
        return False

    def _resize_edges(self, global_pos):
        pos = self._dialog.mapFromGlobal(global_pos)
        rect = self._dialog.rect()
        margin = self._margin
        left = pos.x() <= margin
        right = pos.x() >= rect.width() - margin
        top = pos.y() <= margin
        bottom = pos.y() >= rect.height() - margin
        return left, right, top, bottom

    def _cursor_shape(self, left, right, top, bottom):
        if (top and left) or (bottom and right):
            return Qt.SizeFDiagCursor
        if (top and right) or (bottom and left):
            return Qt.SizeBDiagCursor
        if left or right:
            return Qt.SizeHorCursor
        if top or bottom:
            return Qt.SizeVerCursor
        return Qt.ArrowCursor

    def _apply_cursor(self, owner, left, right, top, bottom):
        shape = self._cursor_shape(left, right, top, bottom)
        try:
            self._dialog.setCursor(shape)
        except Exception:
            pass

    def _clear_cursor(self):
        try:
            self._dialog.unsetCursor()
        except Exception:
            pass

    def _resize_to(self, global_pos):
        delta = global_pos - self._start
        geom = self._geom
        left, right, top, bottom = self._edges
        nx, ny, nw, nh = geom.x(), geom.y(), geom.width(), geom.height()
        min_w = max(460, self._dialog.minimumWidth())
        min_h = max(560, self._dialog.minimumHeight())

        if right:
            nw = max(min_w, geom.width() + delta.x())
        if bottom:
            nh = max(min_h, geom.height() + delta.y())
        if left:
            nw = max(min_w, geom.width() - delta.x())
            nx = geom.x() + (geom.width() - nw)
        if top:
            nh = max(min_h, geom.height() - delta.y())
            ny = geom.y() + (geom.height() - nh)

        self._dialog.setGeometry(nx, ny, nw, nh)


def open_lyrics_dialog(app):
    if not (app.queue and app.queue_index != -1):
        return

    track = app.queue[app.queue_index]
    t = app._tr
    existing = getattr(app, "_lyr_win", None)
    if existing is not None and qt_is_valid(existing):
        current_vid = str(track.get("videoId", "") or "")
        if current_vid and current_vid != str(getattr(app, "_lyr_bound_vid", "") or ""):
            app._lyrics_refresh_for_track(track)
        existing.show()
        existing.raise_()
        existing.activateWindow()
        return
    if existing is not None and not qt_is_valid(existing):
        app._cleanup_lyrics_dialog_refs()

    from PySide6.QtWidgets import QApplication as _QApp
    dialog = QDialog(None)
    dialog.setAttribute(Qt.WA_DeleteOnClose, True)
    dialog.setAttribute(Qt.WA_QuitOnClose, False)   # ana pencere minimize'yken kapanması uygulamayı kapatmasın
    dialog.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
    try:
        dialog.setWindowIcon(app.windowIcon())
    except Exception:
        pass
    _QApp.instance().aboutToQuit.connect(
        lambda: (qt_is_valid(dialog) and dialog.close())
    )
    dialog.setMinimumSize(460, 560)
    initial_size = getattr(app, "_lyr_window_size", (560, 760)) or (560, 760)
    try:
        init_w, init_h = int(initial_size[0]), int(initial_size[1])
    except Exception:
        init_w, init_h = 560, 760
    dialog.resize(max(460, init_w), max(560, init_h))
    dialog.setStyleSheet(f"background:{BG_BLACK}; color:white;")

    outer = QVBoxLayout(dialog)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(0)

    titlebar = TitleBar(dialog, title=track.get("title", ""))
    outer.addWidget(titlebar)

    content = QWidget(dialog)
    content.setStyleSheet(f"background:{BG_BLACK}; color:white;")
    outer.addWidget(content, 1)

    root = QVBoxLayout(content)
    root.setContentsMargins(16, 12, 16, 12)
    root.setSpacing(12)

    def _rgba(hex_color: str, alpha: float) -> str:
        value = (hex_color or "#000000").lstrip("#")
        if len(value) != 6:
            value = "000000"
        r = int(value[0:2], 16)
        g = int(value[2:4], 16)
        b = int(value[4:6], 16)
        return f"rgba({r},{g},{b},{max(0.0, min(1.0, float(alpha))):.3f})"

    accent = get_accent()
    panel_border = _rgba(accent, 0.26)
    panel_glow = _rgba(accent, 0.14)
    panel_fill = _rgba(accent, 0.10)

    hero_card = QFrame()
    hero_card.setStyleSheet(
        f"""
        QFrame {{
            background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 rgba(14,22,38,0.98),
                stop:0.58 rgba(16,24,42,0.98),
                stop:1 {panel_fill});
            border: 1px solid {panel_border};
            border-radius: 18px;
        }}
        QLabel {{
            background: transparent;
            border: none;
        }}
        """
    )
    root.addWidget(hero_card)

    hero_layout = QVBoxLayout(hero_card)
    hero_layout.setContentsMargins(14, 14, 14, 12)
    hero_layout.setSpacing(10)

    header = QHBoxLayout()
    header.setSpacing(12)
    header.setContentsMargins(0, 0, 0, 0)

    cover = TrackCoverWidget(64, 64, radius=12)
    thumb = app._thumb(track, big=True)
    if thumb:
        app._load_image(thumb, cover, (64, 64))
    header.addWidget(cover, 0, Qt.AlignVCenter)

    meta = QVBoxLayout()
    meta.setSpacing(4)
    meta.setContentsMargins(0, 0, 0, 0)
    title = QLabel(track.get("title", ""))
    title.setWordWrap(True)
    title.setStyleSheet("font-size:19px; font-weight:900; background:transparent; color:white;")
    artist = QLabel(app._artist_str(track))
    artist.setWordWrap(True)
    artist.setStyleSheet(f"color:{TEXT_SECONDARY}; font-size:13px; background:transparent;")
    meta.addWidget(title)
    meta.addWidget(artist)

    meta_hint = QLabel(t("lyrics.hint"))
    meta_hint.setWordWrap(True)
    meta_hint.setStyleSheet("color: rgba(236,243,255,0.58); font-size:11px; background:transparent;")
    meta.addWidget(meta_hint)
    header.addLayout(meta, 1)

    actions = QHBoxLayout()
    actions.setSpacing(8)

    def _button_style(active: bool) -> str:
        if active:
            return f"""
                QPushButton {{
                    background: {_rgba(accent, 0.18)};
                    border: 1px solid {_rgba(accent, 0.30)};
                    border-radius: 10px;
                    color: white;
                    padding: 0 10px;
                    font-size: 10px;
                    font-weight: 700;
                }}
                QPushButton:hover {{
                    background: {_rgba(accent, 0.24)};
                    border: 1px solid {_rgba(accent, 0.46)};
                }}
                QPushButton:pressed {{
                    background: {_rgba(accent, 0.14)};
                }}
            """
        return f"""
            QPushButton {{
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 10px;
                color: #A9B8D5;
                padding: 0 10px;
                font-size: 10px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background: rgba(255,255,255,0.08);
                color: white;
            }}
        """

    sync_btn = QPushButton(t("lyrics.sync"))
    sync_btn.setFixedHeight(26)
    sync_btn.setCursor(Qt.PointingHandCursor)
    sync_btn.setStyleSheet(_button_style(True))
    actions.addWidget(sync_btn)

    effect_btn = QPushButton(t("lyrics.effect_on"))
    effect_btn.setFixedHeight(26)
    effect_btn.setCursor(Qt.PointingHandCursor)
    effect_btn.setStyleSheet(_button_style(True))
    actions.addWidget(effect_btn)

    more_btn = QPushButton(t("lyrics.more_show"))
    more_btn.setFixedHeight(26)
    more_btn.setCursor(Qt.PointingHandCursor)
    more_btn.setStyleSheet(_button_style(False))
    actions.addWidget(more_btn)

    actions.addStretch(1)
    hero_layout.addLayout(header)
    hero_layout.addLayout(actions)

    offset_wrap = QFrame()
    offset_wrap.setStyleSheet(
        f"background: rgba(255,255,255,0.03); border-radius: 14px; border:1px solid rgba(255,255,255,0.06);"
    )
    offset_wrap.hide()
    offset_row = QHBoxLayout(offset_wrap)
    offset_row.setContentsMargins(10, 8, 10, 8)
    offset_row.setSpacing(10)

    def _format_offset(ms: int) -> str:
        sign = "+" if ms > 0 else ""
        return f"{sign}{ms / 1000:.2f}s"

    offset_label = QLabel(t("lyrics.offset"))
    offset_label.setStyleSheet(
        f"color:{TEXT_SECONDARY}; font-size:11px; font-weight:700; background:transparent;"
    )
    offset_value = QLabel(_format_offset(int(getattr(app, "_lyr_offset_ms", 0) or 0)))
    offset_value.setStyleSheet(
        f"color:{accent}; font-size:11px; font-weight:800; background:transparent;"
    )
    offset_slider = QSlider(Qt.Horizontal)
    offset_slider.setRange(-5000, 5000)
    offset_slider.setSingleStep(50)
    offset_slider.setPageStep(250)
    offset_slider.setValue(int(getattr(app, "_lyr_offset_ms", 0) or 0))
    offset_slider.setStyleSheet(
        f"""
        QSlider::groove:horizontal {{
            height: 4px;
            background: rgba(255,255,255,0.10);
            border-radius: 2px;
        }}
        QSlider::sub-page:horizontal {{
            background: {accent};
            border-radius: 2px;
        }}
        QSlider::handle:horizontal {{
            width: 14px;
            margin: -5px 0;
            background: white;
            border: 2px solid {accent};
            border-radius: 7px;
        }}
        """
    )
    offset_reset = QPushButton(t("lyrics.reset"))
    offset_reset.setFixedHeight(26)
    offset_reset.setCursor(Qt.PointingHandCursor)
    offset_reset.setStyleSheet(_button_style(False))

    offset_row.addWidget(offset_label)
    offset_row.addWidget(offset_slider, 1)
    offset_row.addWidget(offset_value)
    offset_row.addWidget(offset_reset)
    hero_layout.addWidget(offset_wrap)

    preview_wrap = QFrame()
    preview_wrap.setObjectName("LyricsPreviewWrap")
    preview_wrap.setStyleSheet(
        """
        QFrame#LyricsPreviewWrap {
            background: rgba(7,12,20,0.55);
            border: 1px solid rgba(255,255,255,0.05);
            border-radius: 14px;
        }
        """
    )
    preview_wrap.hide()
    preview_layout = QVBoxLayout(preview_wrap)
    preview_layout.setContentsMargins(12, 10, 12, 10)
    preview_layout.setSpacing(6)
    preview_caption = QLabel(t("lyrics.preview_caption"))
    preview_caption.setStyleSheet(
        f"color:{TEXT_SECONDARY}; font-size:10px; font-weight:800; letter-spacing:0.8px; background:transparent; border:none;"
    )
    preview_label = QLabel(t("lyrics.loading"))
    preview_label.setWordWrap(True)
    preview_label.setStyleSheet("color:white; font-size:13px; font-weight:700; background:transparent; border:none;")
    preview_layout.addWidget(preview_caption)
    preview_layout.addWidget(preview_label)
    hero_layout.addWidget(preview_wrap)

    utility_shell = QFrame()
    utility_shell.setStyleSheet(
        "background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.05); border-radius: 14px;"
    )
    utility_shell.hide()
    hero_layout.addWidget(utility_shell)

    utility = QHBoxLayout(utility_shell)
    utility.setContentsMargins(10, 8, 10, 8)
    utility.setSpacing(8)

    offset_btn = QPushButton(t("lyrics.offset"))
    offset_btn.setFixedHeight(24)
    offset_btn.setCursor(Qt.PointingHandCursor)
    offset_btn.setStyleSheet(_button_style(False))
    utility.addWidget(offset_btn)

    preview_btn = QPushButton(t("lyrics.preview_button"))
    preview_btn.setFixedHeight(24)
    preview_btn.setCursor(Qt.PointingHandCursor)
    preview_btn.setStyleSheet(_button_style(False))
    utility.addWidget(preview_btn)

    font_down = QPushButton("A-")
    font_down.setFixedHeight(24)
    font_down.setCursor(Qt.PointingHandCursor)
    font_down.setStyleSheet(_button_style(False))
    utility.addWidget(font_down)

    font_label = QLabel()
    font_label.setAlignment(Qt.AlignCenter)
    font_label.setMinimumWidth(48)
    font_label.setStyleSheet(f"color:{TEXT_SECONDARY}; font-size:10px; font-weight:700;")
    utility.addWidget(font_label)

    font_up = QPushButton("A+")
    font_up.setFixedHeight(24)
    font_up.setCursor(Qt.PointingHandCursor)
    font_up.setStyleSheet(_button_style(False))
    utility.addWidget(font_up)

    utility.addStretch(1)

    lyrics_list = QListWidget()
    lyrics_list.setStyleSheet(
        f"""
        QListWidget {{
            background: transparent;
            border: none;
            color: {TEXT_MUTED};
            outline: none;
        }}
        QListWidget::item {{
            background: transparent;
        }}
        """
    )
    lyrics_list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
    lyrics_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    lyrics_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    lyrics_list.setSelectionMode(QListWidget.NoSelection)
    lyrics_list.setUniformItemSizes(False)
    lyrics_list.setWordWrap(True)
    lyrics_list.viewport().setCursor(Qt.PointingHandCursor)
    delegate = LyricsDelegate(app)
    lyrics_list.setItemDelegate(delegate)
    root.addWidget(lyrics_list, 1)

    app._lyr_win = dialog
    app._lyr_tb = titlebar
    app._lyr_cover = cover
    app._lyr_title_lbl = title
    app._lyr_artist_lbl = artist
    app._lyr_sync_button = sync_btn
    app._lyr_effect_button = effect_btn
    app._lyr_more_toggle = more_btn
    app._lyr_offset_slider = offset_slider
    app._lyr_offset_label = offset_value
    app._lyr_offset_toggle = offset_btn
    app._lyr_preview_toggle = preview_btn
    app._lyr_font_down = font_down
    app._lyr_font_up = font_up
    app._lyr_font_label = font_label
    app._lyr_next_preview_label = preview_label
    app._lyr_list = lyrics_list
    app._lyr_auto_sync = bool(getattr(app, "_lyr_auto_sync", True))
    app._lyr_effect_enabled = bool(getattr(app, "_lyr_effect_enabled", True))
    app._lyr_advanced_visible = bool(getattr(app, "_lyr_advanced_visible", False))

    def _toggle_sync():
        if not bool(getattr(app, "_lyr_has_real_timestamps", False)):
            return
        app._lyr_auto_sync = not bool(getattr(app, "_lyr_auto_sync", True))
        app._lyrics_update_sync_button()
        if app._lyr_auto_sync and int(getattr(app, "_lyr_current_idx", -1) or -1) >= 0:
            item = lyrics_list.item(app._lyr_current_idx)
            if item is not None:
                lyrics_list.scrollToItem(item, QAbstractItemView.PositionAtCenter)

    def _refresh_effect_text():
        effect_btn.setText(
            t("lyrics.effect_on") if app._lyr_effect_enabled else t("lyrics.effect_off")
        )

    def _apply_sync_capabilities():
        has_lines = bool(getattr(app, "lyrics_data", None))
        has_real = bool(getattr(app, "_lyr_has_real_timestamps", False))
        interactive = has_real and has_lines
        sync_btn.setVisible(interactive)
        effect_btn.setVisible(interactive)
        more_btn.setVisible(interactive)
        utility_shell.setVisible(interactive and bool(getattr(app, "_lyr_advanced_visible", False)))
        if not interactive:
            offset_wrap.hide()
            preview_wrap.hide()
        meta_hint.setText(t("lyrics.hint") if interactive or not has_lines else t("lyrics.hint_static"))
        lyrics_list.viewport().setCursor(Qt.PointingHandCursor if interactive else Qt.ArrowCursor)

    def _toggle_effect():
        app._lyr_effect_enabled = not bool(getattr(app, "_lyr_effect_enabled", True))
        _refresh_effect_text()
        effect_btn.setStyleSheet(_button_style(app._lyr_effect_enabled))
        if hasattr(delegate, "clear_cache"):
            delegate.clear_cache()
        lyrics_list.viewport().update()

    def _refresh_offset_ui():
        current = int(getattr(app, "_lyr_offset_ms", 0) or 0)
        base_label = t("lyrics.offset")
        offset_value.setText(_format_offset(current))
        offset_label.setText(base_label)
        offset_btn.setText(base_label if not current else f"{base_label} {_format_offset(current)}")
        offset_btn.setStyleSheet(_button_style(offset_wrap.isVisible()))
        offset_reset.setEnabled(bool(current))
        offset_reset.setStyleSheet(_button_style(bool(current)))

    def _toggle_offset_panel():
        if not bool(getattr(app, "_lyr_advanced_visible", False)):
            return
        offset_wrap.setVisible(not offset_wrap.isVisible())
        _refresh_offset_ui()

    def _refresh_preview_toggle():
        preview_btn.setStyleSheet(_button_style(preview_wrap.isVisible()))

    def _toggle_preview_panel():
        if not bool(getattr(app, "_lyr_advanced_visible", False)):
            return
        preview_wrap.setVisible(not preview_wrap.isVisible())
        _refresh_preview_toggle()

    def _refresh_advanced_ui():
        advanced_visible = bool(getattr(app, "_lyr_advanced_visible", False))
        utility_shell.setVisible(advanced_visible and bool(getattr(app, "_lyr_has_real_timestamps", False)))
        if not advanced_visible:
            offset_wrap.hide()
            preview_wrap.hide()
        more_btn.setText(t("lyrics.more_hide") if advanced_visible else t("lyrics.more_show"))
        more_btn.setStyleSheet(_button_style(advanced_visible))
        _refresh_offset_ui()
        _refresh_preview_toggle()
        _apply_sync_capabilities()

    def _toggle_advanced_ui():
        app._lyr_advanced_visible = not bool(getattr(app, "_lyr_advanced_visible", False))
        _refresh_advanced_ui()

    def _offset_changed(value: int):
        app._lyr_offset_ms = int(value)
        _refresh_offset_ui()
        if hasattr(delegate, "clear_cache"):
            delegate.clear_cache()
        lyrics_list.scheduleDelayedItemsLayout()
        lyrics_list.viewport().update()

    def _show_context_menu(pos):
        item = lyrics_list.itemAt(pos)
        menu = QMenu(lyrics_list)
        copy_action = menu.addAction(t("lyrics.copy_line"))
        selected = menu.exec(lyrics_list.viewport().mapToGlobal(pos))
        if selected == copy_action:
            if item is None:
                app._lyrics_copy_line()
            else:
                app._lyrics_copy_line(idx=lyrics_list.row(item), text=item.text())

    def _refresh_ui_texts():
        meta_hint.setText(t("lyrics.hint"))
        offset_label.setText(t("lyrics.offset"))
        offset_reset.setText(t("lyrics.reset"))
        preview_caption.setText(t("lyrics.preview_caption"))
        preview_btn.setText(t("lyrics.preview_button"))
        _refresh_effect_text()
        app._lyrics_update_sync_button()
        _refresh_advanced_ui()
        app._lyrics_update_preview()

    def _on_lyric_click(item):
        idx = lyrics_list.row(item)
        lines = getattr(app, "lyrics_data", []) or []
        if 0 <= idx < len(lines) and int(lines[idx][0]) >= 0:
            offset = int(getattr(app, "_lyr_offset_ms", 0) or 0)
            app._seek_commit(max(0, int(lines[idx][0]) - offset))

    sync_btn.clicked.connect(_toggle_sync)
    effect_btn.clicked.connect(_toggle_effect)
    more_btn.clicked.connect(_toggle_advanced_ui)
    offset_btn.clicked.connect(_toggle_offset_panel)
    preview_btn.clicked.connect(_toggle_preview_panel)
    offset_slider.valueChanged.connect(_offset_changed)
    offset_reset.clicked.connect(lambda: offset_slider.setValue(0))
    font_down.clicked.connect(lambda: app._lyrics_set_font_size(int(getattr(app, "_lyr_font_size", 15) or 15) - 1))
    font_up.clicked.connect(lambda: app._lyrics_set_font_size(int(getattr(app, "_lyr_font_size", 15) or 15) + 1))
    lyrics_list.itemClicked.connect(_on_lyric_click)
    lyrics_list.setContextMenuPolicy(Qt.CustomContextMenu)
    lyrics_list.customContextMenuRequested.connect(_show_context_menu)

    sync_timer = QTimer(dialog)
    sync_timer.timeout.connect(app._sync_lyrics)
    sync_timer.start(33)
    app._lyr_sync = sync_timer

    resize_filter = _LyricsResizeFilter(
        dialog,
        on_resize=lambda: (
            not dialog.isFullScreen() and setattr(app, "_lyr_window_size", (dialog.width(), dialog.height())),
            hasattr(delegate, "clear_cache") and delegate.clear_cache(),
            lyrics_list.scheduleDelayedItemsLayout(),
            lyrics_list.viewport().update(),
        ),
    )
    resize_filter.bind()
    dialog._lyr_resize_filter = resize_filter

    dialog.destroyed.connect(lambda *_: app._cleanup_lyrics_dialog_refs())
    app._lyrics_refresh_ui_texts = _refresh_ui_texts
    app._lyrics_apply_sync_capabilities = _apply_sync_capabilities

    app._lyrics_update_font_label()
    _refresh_ui_texts()
    effect_btn.setStyleSheet(_button_style(app._lyr_effect_enabled))
    _apply_sync_capabilities()
    app._lyrics_apply_window_flags()
    app._lyrics_refresh_for_track(track)

    dialog.show()
    dialog.raise_()
    dialog.activateWindow()
