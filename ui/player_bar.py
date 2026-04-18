"""Alt oynatıcı çubuğu — polished spacing & alignment."""
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QSlider, QSizePolicy
)
from PySide6.QtCore import Qt, QSize

from core.constants import (
    BG_CARD, BG_CARD_HOVER, BORDER_COLOR,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED
)
from core.theme import get_accent
from utils.helpers import create_icon
from ui.widgets import (
    ClickableLabel, ClickableSlider, TrackCoverWidget, HoverScaleButton,
    SmoothCircleIconButton,
)


def build_player_bar(app) -> QFrame:
    """Player bar frame'ini oluşturur, app'e gerekli widget ref'lerini bağlar."""
    player_bar = QFrame()
    player_bar.setObjectName("PlayerBar")
    player_bar.setFixedHeight(92)
    player_bar.hide()

    root = QHBoxLayout(player_bar)
    root.setContentsMargins(18, 0, 18, 0)
    root.setSpacing(0)

    # ── Sol: kapak + şarkı bilgisi ──────────────────────────────────────────
    left = QFrame()
    left.setStyleSheet("background:transparent;")
    left_l = QHBoxLayout(left)
    left_l.setContentsMargins(0, 0, 0, 0)
    left_l.setSpacing(14)
    left_l.setAlignment(Qt.AlignVCenter)

    app.img_cover = TrackCoverWidget(60, 60, radius=10)
    app.img_cover.setCursor(Qt.PointingHandCursor)
    app.img_cover.mousePressEvent = lambda _: app._player_ctx_menu()

    info = QVBoxLayout()
    info.setSpacing(2)
    info.setAlignment(Qt.AlignVCenter)

    app.lbl_title = QLabel(app._tr("player.choose_song"))
    app.lbl_title.setStyleSheet(
        f"font-size:13px; font-weight:800; color:{TEXT_PRIMARY}; background:transparent;")
    app.lbl_title.setMaximumWidth(200)

    app.lbl_artist = QLabel("")
    app.lbl_artist.setStyleSheet(
        f"font-size:12px; color:{TEXT_SECONDARY}; background:transparent;")
    app.lbl_artist.setMaximumWidth(200)
    app.lbl_artist.setTextFormat(Qt.RichText)
    app.lbl_artist.setTextInteractionFlags(Qt.LinksAccessibleByMouse)
    app.lbl_artist.setOpenExternalLinks(False)
    app.lbl_artist.setCursor(Qt.PointingHandCursor)
    app.lbl_artist.linkActivated.connect(app._player_artist_link_activated)

    info.addWidget(app.lbl_title)
    info.addWidget(app.lbl_artist)

    left_l.addWidget(app.img_cover)
    left_l.addLayout(info)
    left_l.addStretch()
    root.addWidget(left, 2)

    # ── Orta: kontroller + seek bar ────────────────────────────────────────
    mid = QFrame()
    mid.setStyleSheet("background:transparent;")
    mid_l = QVBoxLayout(mid)
    mid_l.setContentsMargins(0, 10, 0, 8)
    mid_l.setSpacing(4)
    mid_l.setAlignment(Qt.AlignHCenter)

    # Kontrol butonları satırı
    ctrl = QFrame()
    ctrl.setStyleSheet("background:transparent;")
    ctrl_l = QHBoxLayout(ctrl)
    ctrl_l.setContentsMargins(0, 0, 0, 0)
    ctrl_l.setSpacing(0)
    ctrl_l.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)

    acc = get_accent()

    def _ctrl_btn(icon_name, size=30, icon_px=17, is_play=False):
        b = SmoothCircleIconButton() if is_play else HoverScaleButton()
        b.setFocusPolicy(Qt.NoFocus)
        b.setVisualSize(size)          # PAD otomatik eklenir
        b.setCursor(Qt.PointingHandCursor)
        if is_play:
            b.setObjectName("PlayButton")
        else:
            b.setStyleSheet(
                f"QPushButton{{border:none; background:transparent; border-radius:{size//2}px;}}"
                f"QPushButton:hover{{background:{BG_CARD_HOVER};}}")
        b.setIcon(create_icon(icon_name, TEXT_PRIMARY, icon_px))
        b.setIconSize(QSize(icon_px, icon_px))
        return b

    # Shuffle
    app.btn_shuffle = _ctrl_btn("shuffle", 30, 16)
    app.btn_shuffle.setIcon(create_icon("shuffle", TEXT_MUTED, 16))
    app.btn_shuffle.setIconSize(QSize(16, 16))
    app.btn_shuffle.setToolTip(app._tr("player.tooltip.shuffle"))

    # Previous
    app.btn_prev = _ctrl_btn("skip_prev", 34, 18)
    app.btn_prev.setToolTip(app._tr("player.tooltip.previous"))

    # Play / Pause  (merkez, biraz daha büyük)
    app.btn_play = _ctrl_btn("play", 36, 15, is_play=True)
    app.btn_play.setIcon(create_icon("play", "#FFFFFF", 15))
    app.btn_play.setIconSize(QSize(15, 15))
    app.btn_play.setIconOffset(1, 0)
    app.btn_play.setToolTip(app._tr("player.tooltip.play"))

    # Next
    app.btn_next = _ctrl_btn("skip_next", 34, 18)
    app.btn_next.setToolTip(app._tr("player.tooltip.next"))

    # Repeat
    app.btn_repeat = _ctrl_btn("repeat", 30, 16)
    app.btn_repeat.setIcon(create_icon("repeat", TEXT_MUTED, 16))
    app.btn_repeat.setIconSize(QSize(16, 16))
    app.btn_repeat.setToolTip(app._tr("player.tooltip.repeat"))

    app.btn_shuffle.clicked.connect(app._toggle_shuffle)
    app.btn_prev.clicked.connect(app.prev_song)
    app.btn_play.clicked.connect(app.toggle_play)
    app.btn_next.clicked.connect(app.next_song)
    app.btn_repeat.clicked.connect(app._toggle_repeat)

    ctrl_l.addWidget(app.btn_shuffle)
    ctrl_l.addSpacing(16)
    ctrl_l.addWidget(app.btn_prev)
    ctrl_l.addSpacing(8)
    ctrl_l.addWidget(app.btn_play)
    ctrl_l.addSpacing(8)
    ctrl_l.addWidget(app.btn_next)
    ctrl_l.addSpacing(16)
    ctrl_l.addWidget(app.btn_repeat)

    # Seek bar satırı
    seek_row = QFrame()
    seek_row.setStyleSheet("background:transparent;")
    seek_l = QHBoxLayout(seek_row)
    seek_l.setContentsMargins(0, 0, 0, 0)
    seek_l.setSpacing(8)

    app.lbl_cur = QLabel("0:00")
    app.lbl_cur.setStyleSheet(
        f"color:{TEXT_MUTED}; font-size:11px; min-width:34px; background:transparent;")
    app.lbl_cur.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

    app.seek_bar = ClickableSlider(Qt.Horizontal)
    app.seek_bar.setRange(0, 0)
    app.seek_bar.setObjectName("SeekBar")
    app.seek_bar.sliderPressed.connect(app._seek_start)
    app.seek_bar.sliderReleased.connect(app._seek_end)
    app.seek_bar.sliderMoved.connect(app._seek_move)
    app.seek_bar.seekRequested.connect(app._seek_commit)

    app.lbl_end = QLabel("0:00")
    app.lbl_end.setStyleSheet(
        f"color:{TEXT_MUTED}; font-size:11px; min-width:34px; background:transparent;")

    seek_l.addWidget(app.lbl_cur)
    seek_l.addWidget(app.seek_bar, 1)
    seek_l.addWidget(app.lbl_end)

    mid_l.addWidget(ctrl)
    mid_l.addWidget(seek_row)
    root.addWidget(mid, 3)

    # ── Sağ: araç butonları + ses ───────────────────────────────────────────
    right = QFrame()
    right.setStyleSheet("background:transparent;")
    right_l = QHBoxLayout(right)
    right_l.setContentsMargins(0, 0, 0, 0)
    right_l.setSpacing(2)
    right_l.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

    app._player_tool_buttons = []

    def _tool_btn(icon_name, cmd, tooltip_key=None, size=28):
        b = HoverScaleButton()
        b.setFocusPolicy(Qt.NoFocus)
        b.setVisualSize(size)
        b.setIcon(create_icon(icon_name, TEXT_MUTED, 16))
        b.setIconSize(QSize(16, 16))
        b.setCursor(Qt.PointingHandCursor)
        if tooltip_key:
            b.setToolTip(app._tr(tooltip_key))
        b.setStyleSheet(
            f"QPushButton{{border:none; background:transparent; border-radius:{size//2}px;}}"
            f"QPushButton:hover{{background:{BG_CARD}; color:white;}}")
        b.clicked.connect(cmd)
        app._player_tool_buttons.append(b)
        return b

    # Uyku zamanlayıcı etiketi (görünmez başlangıçta)
    app.lbl_sleep = QLabel("")
    app.lbl_sleep.setStyleSheet(
        f"color:{acc}; font-size:11px; font-weight:700; background:transparent;")
    app.lbl_sleep.hide()
    right_l.addWidget(app.lbl_sleep)

    app.btn_sleep = _tool_btn("timer", app._dlg_sleep, "player.tooltip.sleep_timer")
    right_l.addWidget(app.btn_sleep)
    app.btn_mini = _tool_btn("miniplayer", app._open_mini, "player.tooltip.mini_player")
    right_l.addWidget(app.btn_mini)
    app.btn_lyrics = _tool_btn("mic", app.open_lyrics, "player.tooltip.lyrics")
    right_l.addWidget(app.btn_lyrics)

    # Oynatma ayarlari butonu — sadece cark ikonu
    speed_btn = HoverScaleButton()
    speed_btn.setObjectName("SpeedBtn")
    speed_btn.setVisualSize(28)
    speed_btn.setCursor(Qt.PointingHandCursor)
    speed_btn.setFocusPolicy(Qt.NoFocus)
    speed_btn.setIcon(create_icon("settings", TEXT_MUTED, 16))
    speed_btn.setIconSize(QSize(16, 16))
    speed_btn.setToolTip(app._tr("player.playback_settings_tooltip"))
    speed_btn.setStyleSheet(
        f"QPushButton{{border:none;background:transparent;border-radius:14px;color:{TEXT_MUTED};}}"
        f"QPushButton:hover{{background:{BG_CARD};color:white;}}"
    )
    speed_btn.clicked.connect(app._open_playback_settings)
    app._speed_btn = speed_btn
    app._player_tool_buttons.append(speed_btn)
    right_l.addWidget(speed_btn)

    app.btn_fav_bar = _tool_btn("heart_off", app._toggle_fav_current)
    right_l.addWidget(app.btn_fav_bar)

    app.btn_dl_bar = _tool_btn("download", app._dl_current)
    right_l.addWidget(app.btn_dl_bar)

    app.btn_queue = _tool_btn("queue", app.toggle_queue_view)
    right_l.addWidget(app.btn_queue)

    app.btn_eq = _tool_btn("eq", app._open_eq)
    right_l.addWidget(app.btn_eq)

    # Ses kontrolü
    right_l.addSpacing(6)
    app.vol_icon = ClickableLabel()
    app.vol_icon.setFixedSize(16, 16)
    app.vol_icon.setStyleSheet("background:transparent;")
    app.vol_icon.clicked.connect(app.toggle_mute)

    app.vol_slider = QSlider(Qt.Horizontal)
    app.vol_slider.setFixedWidth(88)
    app.vol_slider.setObjectName("VolSlider")
    app.vol_slider.setRange(0, 100)
    app.vol_slider.setValue(app._volume)
    app.vol_slider.setFocusPolicy(Qt.NoFocus)
    app.vol_slider.setToolTip(app._tr("player.tooltip.volume"))
    app.vol_slider.valueChanged.connect(app._set_volume)

    right_l.addWidget(app.vol_icon)
    right_l.addWidget(app.vol_slider)
    try:
        app._refresh_volume_ui()
    except Exception:
        pass

    def _set_player_bar_tooltips():
        app.btn_shuffle.setToolTip(app._tr("player.tooltip.shuffle"))
        app.btn_prev.setToolTip(app._tr("player.tooltip.previous"))
        app.btn_play.setToolTip(
            app._tr("player.tooltip.pause")
            if getattr(app, "_main_play_icon_state", None) == "pause"
            else app._tr("player.tooltip.play")
        )
        app.btn_next.setToolTip(app._tr("player.tooltip.next"))
        app.btn_repeat.setToolTip(app._tr("player.tooltip.repeat"))
        app.btn_sleep.setToolTip(app._tr("player.tooltip.sleep_timer"))
        app.btn_mini.setToolTip(app._tr("player.tooltip.mini_player"))
        app.btn_lyrics.setToolTip(app._tr("player.tooltip.lyrics"))
        speed_btn.setToolTip(app._tr("player.playback_settings_tooltip"))
        current = None
        if getattr(app, "queue", None) and 0 <= getattr(app, "queue_index", -1) < len(app.queue):
            current = app.queue[app.queue_index]
        vid = str((current or {}).get("videoId", "") or "")
        is_fav = bool(vid and any(f.get("videoId") == vid for f in getattr(app, "favorites", [])))
        app.btn_fav_bar.setToolTip(
            app._tr("player.tooltip.unfavorite" if is_fav else "player.tooltip.favorite")
        )
        app.btn_dl_bar.setToolTip(app._tr("player.tooltip.download"))
        app.btn_queue.setToolTip(app._tr("player.tooltip.queue"))
        app.btn_eq.setToolTip(app._tr("player.tooltip.equalizer"))
        app.vol_slider.setToolTip(app._tr("player.tooltip.volume"))

    def _refresh_player_bar_texts():
        if not getattr(app, "queue", None) or getattr(app, "queue_index", -1) < 0:
            app.lbl_title.setText(app._tr("player.choose_song"))
            app.lbl_artist.setText("")
        _set_player_bar_tooltips()
        try:
            app._refresh_volume_ui()
        except Exception:
            pass

    app._set_player_bar_tooltips = _set_player_bar_tooltips
    app._refresh_player_bar_texts = _refresh_player_bar_texts
    _set_player_bar_tooltips()

    root.addWidget(right, 2)
    return player_bar
