"""Mini Player penceresi."""
import logging
log = logging.getLogger("iqtMusic")

from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider, QWidget
)
from PySide6.QtCore import Qt, QSize, QTimer

from core.constants import BG_CARD, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED
from core.theme import get_accent
from utils.helpers import create_icon
from ui.widgets import (
    ClickableLabel, DraggableFramelessWidget, ClickableSlider, TrackCoverWidget,
    SmoothCircleIconButton,
)

_COVER = 64


def open_mini_player(app):
    """Mini player penceresini acar veya one getirir."""
    if hasattr(app, "_mini_win") and app._mini_win is not None:
        try:
            state = app._mini_win.windowState()
            if state & Qt.WindowMinimized:
                app._mini_win.setWindowState(state & ~Qt.WindowMinimized | Qt.WindowNoState)
            app._mini_win.show()
            app._mini_win.raise_()
            app._mini_win.activateWindow()
            try:
                if hasattr(app, "_mini_timer") and app._mini_timer is not None:
                    app._mini_timer.start(700)
            except Exception as _e:
                log.debug("Sessiz hata: %s", _e)
            try:
                app._update_mini()
            except Exception as _e:
                log.debug("Sessiz hata: %s", _e)
            return
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)

    acc = get_accent()

    app._mini_is_dragging = False
    app._mini_win = DraggableFramelessWidget()
    app._mini_win.setWindowTitle(app._tr("mini_player.window_title"))
    app._mini_win.resize(340, 148)
    app._mini_win.setMinimumSize(230, 130)
    app._mini_win.setWindowFlags(
        Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool
    )
    app._mini_win.setAttribute(Qt.WA_TranslucentBackground, True)
    app._mini_win.setStyleSheet("background:transparent;")
    app._mini_win.setContentsMargins(0, 0, 0, 0)
    try:
        app._mini_win._resize_margin = 6
    except Exception as _e:
        log.debug("Sessiz hata: %s", _e)

    host_layout = QVBoxLayout(app._mini_win)
    host_layout.setContentsMargins(0, 0, 0, 0)
    host_layout.setSpacing(0)

    shell = QFrame()
    shell.setObjectName("MiniShell")
    shell.setStyleSheet(f"""
        QFrame#MiniShell {{
            background:qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 rgba(8,14,24,0.995),
                stop:1 rgba(8,11,19,0.998));
            border:1px solid {acc}30;
            border-radius:16px;
        }}
    """)
    outer = QVBoxLayout(shell)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(0)

    def _shell_hit_edges(pos):
        rect = shell.rect()
        margin = getattr(app._mini_win, "_resize_margin", 6)
        edges = set()
        if pos.x() <= margin:
            edges.add("left")
        elif pos.x() >= rect.width() - margin:
            edges.add("right")
        if pos.y() <= margin:
            edges.add("top")
        elif pos.y() >= rect.height() - margin:
            edges.add("bottom")
        return edges

    def _shell_apply_cursor(edges):
        if edges == {"left"} or edges == {"right"}:
            shell.setCursor(Qt.SizeHorCursor)
        elif edges == {"top"} or edges == {"bottom"}:
            shell.setCursor(Qt.SizeVerCursor)
        elif edges == {"left", "top"} or edges == {"right", "bottom"}:
            shell.setCursor(Qt.SizeFDiagCursor)
        elif edges == {"right", "top"} or edges == {"left", "bottom"}:
            shell.setCursor(Qt.SizeBDiagCursor)
        else:
            shell.setCursor(Qt.ArrowCursor)

    def _drag_press(e):
        if e.button() == Qt.LeftButton:
            edges = _shell_hit_edges(e.position().toPoint())
            if edges:
                _shell_apply_cursor(edges)
                edge_flags = Qt.Edges()
                if "left" in edges:
                    edge_flags |= Qt.LeftEdge
                if "right" in edges:
                    edge_flags |= Qt.RightEdge
                if "top" in edges:
                    edge_flags |= Qt.TopEdge
                if "bottom" in edges:
                    edge_flags |= Qt.BottomEdge
                try:
                    wh = app._mini_win.windowHandle()
                    if wh:
                        wh.startSystemResize(edge_flags)
                except Exception as _e:
                    log.debug("Sessiz hata: %s", _e)
                e.accept()
                return
            try:
                wh = app._mini_win.windowHandle()
                if wh:
                    wh.startSystemMove()
            except Exception as _e:
                log.debug("Sessiz hata: %s", _e)
            e.accept()

    def _drag_move(e):
        _shell_apply_cursor(_shell_hit_edges(e.position().toPoint()))

    def _drag_release(e):
        _shell_apply_cursor(_shell_hit_edges(e.position().toPoint()))
        e.accept()

    shell.mousePressEvent = _drag_press
    shell.mouseMoveEvent = _drag_move
    shell.mouseReleaseEvent = _drag_release
    shell.setCursor(Qt.ArrowCursor)
    shell.setMouseTracking(True)

    body = QVBoxLayout()
    body.setContentsMargins(10, 14, 10, 6)
    body.setSpacing(8)

    top_row = QHBoxLayout()
    top_row.setContentsMargins(0, 4, 0, 0)
    top_row.setSpacing(14)
    top_row.setAlignment(Qt.AlignVCenter)

    cover_cont = QWidget()
    cover_cont.setFixedSize(_COVER, _COVER)
    cover_cont.setStyleSheet("background:transparent;")
    cover_cont.setAttribute(Qt.WA_TransparentForMouseEvents, False)

    app._mini_img = TrackCoverWidget(_COVER, _COVER, radius=10, parent=cover_cont)
    app._mini_img.move(0, 0)
    top_row.addWidget(cover_cont, 0, Qt.AlignVCenter)

    right = QVBoxLayout()
    right.setContentsMargins(4, 2, 0, 0)
    right.setSpacing(0)

    _wbtn_ss = (
        "QPushButton{border:none; border-radius:8px; background:rgba(255,255,255,0.06);}"
        "QPushButton:hover{background:rgba(255,255,255,0.16);}"
    )

    min_btn = QPushButton()
    min_btn.setFixedSize(18, 18)
    min_btn.setIcon(create_icon("minus", TEXT_MUTED, 9))
    min_btn.setIconSize(QSize(9, 9))
    min_btn.setStyleSheet(_wbtn_ss)
    min_btn.setCursor(Qt.PointingHandCursor)
    min_btn.setFocusPolicy(Qt.NoFocus)
    min_btn.clicked.connect(app._mini_win.showMinimized)

    close_btn = QPushButton()
    close_btn.setFixedSize(18, 18)
    close_btn.setIcon(create_icon("close", TEXT_MUTED, 9))
    close_btn.setIconSize(QSize(9, 9))
    close_btn.setStyleSheet(_wbtn_ss)
    close_btn.setCursor(Qt.PointingHandCursor)
    close_btn.setFocusPolicy(Qt.NoFocus)
    close_btn.clicked.connect(app._hide_mini_player)

    wbtn_row = QHBoxLayout()
    wbtn_row.setContentsMargins(0, 0, 0, 0)
    wbtn_row.setSpacing(3)
    wbtn_row.addStretch()
    wbtn_row.addWidget(min_btn)
    wbtn_row.addWidget(close_btn)
    right.addLayout(wbtn_row)
    right.addSpacing(10)

    app._mini_title = QLabel(app._tr("mini_player.no_track"))
    app._mini_title.setWordWrap(True)
    app._mini_title.setMaximumHeight(34)
    app._mini_title.setStyleSheet(
        f"font-size:11px; font-weight:700; color:{TEXT_PRIMARY}; background:transparent;"
    )
    right.addWidget(app._mini_title)

    app._mini_artist = QLabel(app._tr("mini_player.ready"))
    app._mini_artist.setWordWrap(False)
    app._mini_artist.setStyleSheet(
        f"font-size:10px; color:{TEXT_SECONDARY}; background:transparent;"
    )
    right.addWidget(app._mini_artist)
    right.addSpacing(4)

    app._mini_status = QLabel(app._tr("mini_player.controls"))
    app._mini_status.setStyleSheet(
        f"font-size:10px; color:{TEXT_MUTED}; background:transparent;"
    )

    top_row.addLayout(right, 1)
    body.addLayout(top_row)

    def mini_btn(icon_name, cmd, size=24, icon_px=12, object_name=None, icon_color="#FFFFFF"):
        b = SmoothCircleIconButton() if object_name == "PlayButton" else QPushButton()
        b.setCursor(Qt.PointingHandCursor)
        b.setFixedSize(size, size)
        if object_name:
            b.setObjectName(object_name)
        else:
            b.setStyleSheet(
                f"QPushButton{{background:rgba(255,255,255,0.06); border:none; "
                f"border-radius:{size // 2}px;}}"
                "QPushButton:hover{background:rgba(255,255,255,0.14);}"
            )
        b.setIcon(create_icon(icon_name, icon_color, icon_px))
        b.setIconSize(QSize(icon_px, icon_px))
        if object_name == "PlayButton" and hasattr(b, "setIconOffset"):
            b.setIconOffset(1, 0)
        b.clicked.connect(cmd)
        b.setFocusPolicy(Qt.NoFocus)
        return b

    ctl = QHBoxLayout()
    ctl.setContentsMargins(0, 2, 0, 0)
    ctl.setSpacing(6)
    ctl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

    app._mini_prev_btn = mini_btn("skip_prev", app.prev_song, size=24, icon_px=12)
    app._mini_play_btn = mini_btn(
        "play", app.toggle_play, size=28, icon_px=12, object_name="PlayButton"
    )
    app._mini_next_btn = mini_btn("skip_next", app.next_song, size=24, icon_px=12)
    app._mini_lyrics_btn = mini_btn("mic", app.open_lyrics, size=24, icon_px=12)
    app._mini_fav_btn = mini_btn(
        "heart_off",
        app._toggle_fav_current,
        size=24,
        icon_px=14,
        icon_color=TEXT_MUTED,
    )

    ctl.addWidget(app._mini_prev_btn)
    ctl.addWidget(app._mini_play_btn)
    ctl.addWidget(app._mini_next_btn)
    ctl.addWidget(app._mini_lyrics_btn)
    ctl.addWidget(app._mini_fav_btn)
    ctl.addSpacing(6)

    app._mini_vol_icon = ClickableLabel()
    app._mini_vol_icon.setFixedSize(10, 10)
    app._mini_vol_icon.setStyleSheet("background:transparent;")
    app._mini_vol_icon.clicked.connect(app.toggle_mute)
    ctl.addWidget(app._mini_vol_icon)

    app._mini_vol = QSlider(Qt.Horizontal)
    app._mini_vol.setObjectName("MiniVolSlider")
    app._mini_vol.setRange(0, 100)
    app._mini_vol.setValue(getattr(app, "_volume", 60))
    app._mini_vol.setFixedWidth(72)
    app._mini_vol.valueChanged.connect(app._set_volume)
    app._mini_vol.setFocusPolicy(Qt.NoFocus)
    ctl.addWidget(app._mini_vol)
    ctl.addStretch()

    body.addLayout(ctl)
    outer.addLayout(body)

    seek_row = QHBoxLayout()
    seek_row.setContentsMargins(10, 0, 10, 10)
    seek_row.setSpacing(0)

    app._mini_seek = ClickableSlider(Qt.Horizontal)
    app._mini_seek.setRange(0, 0)
    app._mini_seek.setObjectName("MiniSeekBar")
    app._mini_seek.setFixedHeight(12)
    app._mini_seek.sliderPressed.connect(app._mini_seek_start)
    app._mini_seek.sliderReleased.connect(app._mini_seek_end)
    app._mini_seek.sliderMoved.connect(app._mini_seek_move)
    app._mini_seek.seekRequested.connect(app._mini_seek_commit)
    app._mini_seek.setFocusPolicy(Qt.NoFocus)
    seek_row.addWidget(app._mini_seek)
    outer.addLayout(seek_row)

    host_layout.addWidget(shell)
    app._mini_win.show()

    app._mini_win._resize_callback = app._layout_mini_player

    app._mini_timer = QTimer(app._mini_win)
    app._mini_timer.timeout.connect(app._update_mini)
    app._mini_timer.start(700)
    app._layout_mini_player()
    app._update_mini()
    try:
        app._refresh_volume_ui()
    except Exception:
        pass
