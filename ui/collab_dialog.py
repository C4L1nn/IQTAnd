from __future__ import annotations
import logging
from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, Qt, Signal, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QProgressBar,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from core.collab import fmt_room_code, parse_room_code
from core.i18n import DEFAULT_LANGUAGE, translate
from core.theme import get_accent
from utils.helpers import create_icon
from ui.widgets import TrackCoverWidget

log = logging.getLogger("iqtMusic.collab")

_BG     = "#08111E"
_SHELL  = "#0B1628"
_CARD   = "#0E1B31"
_CARD_ALT = "#0B1830"
_BORDER = "#1A2B49"
_TEXT   = "#ECF3FF"
_MUTED  = "#9AAACE"
_WARN   = "#F5B942"
_ERR    = "#FF6B7D"


def _rgba(hex_color: str, alpha: float) -> str:
    s = (hex_color or "#000000").lstrip("#")
    if len(s) != 6:
        s = "000000"
    r, g, b = int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
    return f"rgba({r},{g},{b},{max(0.0, min(1.0, float(alpha))):.3f})"


class CollabDialog(QDialog):
    refresh_requested = Signal()
    status_requested  = Signal(str, str)

    def __init__(self, app):
        super().__init__(app)
        self._app = app
        self._mode = "host"
        self._drag_offset: QPoint | None = None
        self._status_state   = "idle"
        self._status_message = self._tr("collab.status.ready_hint")
        self._did_intro_anim = False
        self._stat_title_labels: dict[str, QLabel] = {}

        self.setObjectName("CollabDialog")
        self.setWindowTitle(self._tr("collab.window_title"))
        self.setModal(False)
        self.setWindowFlags(
            Qt.Window | Qt.FramelessWindowHint |
            Qt.WindowSystemMenuHint | Qt.WindowMinimizeButtonHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setStyleSheet(self._stylesheet())
        self._apply_responsive_geometry(initial=True)

        self._live_timer = QTimer(self)
        self._live_timer.setInterval(400)
        self._live_timer.timeout.connect(self.refresh_now)
        self.refresh_requested.connect(self.refresh_now)
        self.status_requested.connect(self._handle_status_signal)
        if hasattr(self._app, "sig") and hasattr(self._app.sig, "player_ui_update"):
            try:
                self._app.sig.player_ui_update.connect(self.queue_refresh)
            except Exception:
                pass

        # ── shell ──
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self._shell = QFrame(self)
        self._shell.setObjectName("CollabShell")
        root.addWidget(self._shell)

        shell_layout = QVBoxLayout(self._shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)
        shell_layout.addWidget(self._build_titlebar())

        body = QWidget(self._shell)
        body.setObjectName("CollabBody")
        shell_layout.addWidget(body, 1)

        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(14, 10, 14, 12)
        body_layout.setSpacing(8)
        self._body_layout = body_layout
        self._join_banner: QFrame | None = None

        # badge + title inline
        top_row = QHBoxLayout()
        top_row.setSpacing(10)
        self._badge = QLabel("", body)
        self._badge.setObjectName("StateBadge")
        self._badge.setAlignment(Qt.AlignCenter)
        self._badge.setFixedHeight(24)
        self._badge.setMinimumWidth(90)
        self._badge.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        top_row.addWidget(self._badge)
        self._hero_title = QLabel(body)
        self._hero_title.setObjectName("HeroTitle")
        self._hero_title.setWordWrap(False)
        top_row.addWidget(self._hero_title, 1)
        body_layout.addLayout(top_row)

        self._page_stack = QStackedWidget(body)
        self._page_stack.setObjectName("PageStack")
        body_layout.addWidget(self._page_stack, 1)

        self._idle_page = self._build_idle_page()
        self._live_page = self._build_live_page()
        self._page_stack.addWidget(self._idle_page)
        self._page_stack.addWidget(self._live_page)

        body_layout.addWidget(self._build_status_bar())

        self._refresh_texts()
        self._switch_mode("host")
        self.refresh_now()

    # ── join approval banner ────────────────────────────────────────

    def show_join_banner(self, on_accept_cb, on_deny_cb):
        """Show an in-dialog approval banner above the page stack."""
        from PySide6.QtWidgets import QGraphicsDropShadowEffect
        from PySide6.QtGui import QColor
        from core.theme import get_accent

        self.hide_join_banner()

        acc = get_accent()
        banner = QFrame(self)
        banner.setObjectName("JoinApprovalBanner")
        banner.setStyleSheet(f"""
            QFrame#JoinApprovalBanner {{
                background: #131E35;
                border: 1px solid {acc};
                border-radius: 10px;
            }}
        """)
        shadow = QGraphicsDropShadowEffect(banner)
        shadow.setBlurRadius(18)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor(0, 0, 0, 140))
        banner.setGraphicsEffect(shadow)

        row = QHBoxLayout(banner)
        row.setContentsMargins(14, 10, 14, 10)
        row.setSpacing(10)

        dot = QLabel()
        dot.setFixedSize(8, 8)
        dot.setStyleSheet(f"background:{acc};border-radius:4px;")
        row.addWidget(dot, 0, Qt.AlignVCenter)

        lbl = QLabel("Biri Discord üzerinden odana katılmak istiyor")
        lbl.setStyleSheet(
            "color:#ECF3FF;font-weight:700;font-size:12px;background:transparent;border:none;"
        )
        row.addWidget(lbl, 1)

        def _make_btn(text, color, bg):
            btn = QPushButton(text)
            btn.setFixedHeight(28)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background:{bg}; color:{color};
                    border:none; border-radius:6px;
                    padding:0 12px; font-weight:700; font-size:11px;
                }}
                QPushButton:hover {{ background:{color}; color:#fff; }}
            """)
            return btn

        accept_btn = _make_btn("Kabul Et", acc, f"{acc}33")
        deny_btn   = _make_btn("Reddet", "#FF6B7D", "#FF6B7D22")
        row.addWidget(accept_btn)
        row.addWidget(deny_btn)

        auto_deny_timer = QTimer(banner)
        auto_deny_timer.setSingleShot(True)
        auto_deny_timer.setInterval(60_000)

        def _close():
            self.hide_join_banner()

        def _on_accept():
            auto_deny_timer.stop()
            on_accept_cb()
            _close()

        def _on_deny():
            auto_deny_timer.stop()
            on_deny_cb()
            _close()

        accept_btn.clicked.connect(_on_accept)
        deny_btn.clicked.connect(_on_deny)
        auto_deny_timer.timeout.connect(_on_deny)
        auto_deny_timer.start()

        # Insert after top_row (index 0), before _page_stack (index 1)
        self._body_layout.insertWidget(1, banner)
        self._join_banner = banner

    def hide_join_banner(self):
        old = self._join_banner
        if old is not None:
            try:
                self._body_layout.removeWidget(old)
                old.hide()
                old.deleteLater()
            except Exception:
                pass
            self._join_banner = None

    # ── public helpers ──────────────────────────────────────────────

    def queue_refresh(self):
        try:
            self.refresh_requested.emit()
        except Exception:
            self.refresh_now()

    def queue_status(self, state: str, msg: str):
        try:
            self.status_requested.emit(state or "", msg or "")
        except Exception:
            self.on_status(state, msg)

    def _tr(self, key: str, **kwargs) -> str:
        try:
            return self._app._tr(key, **kwargs)
        except Exception:
            return translate(DEFAULT_LANGUAGE, key, **kwargs)

    def _refresh_texts(self):
        self.setWindowTitle(self._tr("collab.window_title"))
        if hasattr(self, "_title_label"):
            self._title_label.setText(self._tr("collab.window_title"))
        ready_messages = {
            translate("tr", "collab.status.ready"),
            translate("tr", "collab.status.ready_hint"),
            translate("en", "collab.status.ready"),
            translate("en", "collab.status.ready_hint"),
        }
        if self._status_state == "idle" and (not self._status_message or self._status_message in ready_messages):
            self._status_message = self._tr("collab.status.ready_hint")
        host_title = self._tr("collab.tab.host.title")
        host_subtitle = self._tr("collab.tab.host.subtitle")
        join_title = self._tr("collab.tab.join.title")
        join_subtitle = self._tr("collab.tab.join.subtitle")
        self._mode_host_btn.setText(f"{host_title}\n{host_subtitle}")
        self._mode_join_btn.setText(f"{join_title}\n{join_subtitle}")
        self._host_section.setText(self._tr("collab.host.section"))
        self._host_desc.setText(self._tr("collab.host.desc"))
        self._start_btn.setText(self._tr("collab.host.start"))
        self._join_section.setText(self._tr("collab.join.section"))
        self._join_code.setPlaceholderText(self._tr("collab.join.placeholder"))
        self._paste_btn.setText(self._tr("collab.join.paste"))
        self._join_btn.setText(self._tr("collab.join.join"))
        self._normalize_join_code(self._join_code.text())
        for key, label in self._stat_title_labels.items():
            label.setText(self._tr(key))
        self._room_label.setText(self._tr("collab.live.room_code"))
        self._copy_btn.setText(self._tr("collab.live.copy"))
        self._invite_btn.setText(self._tr("collab.live.share"))
        self._track_label.setText(self._tr("collab.live.track"))
        self._copy_invite_btn.setText(self._tr("collab.live.invite"))
        self._leave_btn.setText(self._tr("collab.live.leave"))
        self._reconnect_btn.setText(self._tr("collab.live.refresh"))

    # ── build ───────────────────────────────────────────────────────

    def _build_titlebar(self) -> QWidget:
        bar = QFrame(self._shell)
        bar.setObjectName("TitleBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        icon = QLabel(bar)
        pix = create_icon("headphone", color=get_accent(), size=16).pixmap(16, 16)
        if isinstance(pix, QPixmap) and not pix.isNull():
            icon.setPixmap(pix)
        else:
            icon.setText("♪")
        icon.setObjectName("TitleIcon")
        layout.addWidget(icon)

        self._title_label = QLabel("", bar)
        self._title_label.setObjectName("TitleText")
        layout.addWidget(self._title_label)
        layout.addStretch(1)

        self._min_btn = self._make_titlebar_button("minus")
        self._min_btn.clicked.connect(self.hide)
        layout.addWidget(self._min_btn)

        self._close_btn = self._make_titlebar_button("close", danger=True)
        self._close_btn.clicked.connect(self.hide)
        layout.addWidget(self._close_btn)
        return bar

    def _build_idle_page(self) -> QWidget:
        page = QWidget()
        root = QVBoxLayout(page)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        tabs = QHBoxLayout()
        tabs.setSpacing(8)
        self._mode_host_btn = self._make_tab_button("", "")
        self._mode_join_btn = self._make_tab_button("", "")
        self._mode_host_btn.clicked.connect(lambda: self._switch_mode("host"))
        self._mode_join_btn.clicked.connect(lambda: self._switch_mode("join"))
        tabs.addWidget(self._mode_host_btn)
        tabs.addWidget(self._mode_join_btn)
        root.addLayout(tabs)

        self._idle_stack = QStackedWidget(page)
        self._idle_stack.setObjectName("IdleStack")
        self._idle_stack.addWidget(self._build_host_form())
        self._idle_stack.addWidget(self._build_join_form())
        root.addWidget(self._idle_stack, 1)
        return page

    def _build_host_form(self) -> QWidget:
        card = self._card_frame()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        self._host_section = QLabel("", card)
        self._host_section.setObjectName("SectionLabel")
        layout.addWidget(self._host_section)

        self._host_desc = QLabel("", card)
        self._host_desc.setObjectName("SectionText")
        self._host_desc.setWordWrap(True)
        layout.addWidget(self._host_desc)

        layout.addStretch(1)

        self._start_btn = self._make_primary_button("")
        self._start_btn.clicked.connect(self._start_session)
        layout.addWidget(self._start_btn)
        return card

    def _build_join_form(self) -> QWidget:
        card = self._card_frame()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        self._join_section = QLabel("", card)
        self._join_section.setObjectName("SectionLabel")
        layout.addWidget(self._join_section)

        row = QHBoxLayout()
        row.setSpacing(8)
        self._join_code = QLineEdit(card)
        self._join_code.setObjectName("CodeInput")
        self._join_code.setMaxLength(9)
        self._join_code.setAlignment(Qt.AlignCenter)
        self._join_code.textEdited.connect(self._normalize_join_code)
        row.addWidget(self._join_code, 1)
        self._paste_btn = self._make_secondary_button("", icon_name="link")
        self._paste_btn.setFixedWidth(110)
        self._paste_btn.clicked.connect(self._paste_code)
        row.addWidget(self._paste_btn)
        layout.addLayout(row)

        self._join_hint = QLabel("", card)
        self._join_hint.setObjectName("HintLabel")
        self._join_hint.setWordWrap(True)
        layout.addWidget(self._join_hint)

        layout.addStretch(1)

        self._join_btn = self._make_primary_button("")
        self._join_btn.clicked.connect(self._join_session)
        layout.addWidget(self._join_btn)
        return card

    def _build_live_page(self) -> QWidget:
        page = QWidget()
        root = QVBoxLayout(page)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        # ── compact inline status row ──
        status_card = self._card_frame()
        status_row = QHBoxLayout(status_card)
        status_row.setContentsMargins(14, 10, 14, 10)
        status_row.setSpacing(0)

        self._role_value   = QLabel()
        self._role_sub     = QLabel()
        self._conn_value   = QLabel()
        self._conn_sub     = QLabel()
        self._members_value = QLabel()
        self._members_sub  = QLabel()

        status_row.addLayout(self._stat_col("collab.live.role", self._role_value), 1)
        status_row.addWidget(self._vdivider())
        status_row.addLayout(self._stat_col("collab.live.connection", self._conn_value), 1)
        status_row.addWidget(self._vdivider())
        status_row.addLayout(self._stat_col("collab.live.participants", self._members_value), 1)
        root.addWidget(status_card)

        # ── room code card ──
        room_card = self._card_frame()
        room_layout = QVBoxLayout(room_card)
        room_layout.setContentsMargins(14, 12, 14, 12)
        room_layout.setSpacing(8)

        self._room_label = QLabel("", room_card)
        self._room_label.setObjectName("SectionLabel")
        room_layout.addWidget(self._room_label)

        self._room_code_lbl = QLabel("---- ----", room_card)
        self._room_code_lbl.setObjectName("RoomCodeLabel")
        self._room_code_lbl.setAlignment(Qt.AlignCenter)
        self._room_code_lbl.setFixedHeight(52)
        room_layout.addWidget(self._room_code_lbl)

        room_actions = QHBoxLayout()
        room_actions.setSpacing(8)
        self._copy_btn = self._make_secondary_button("", icon_name="copy")
        self._copy_btn.clicked.connect(self._copy_room_code)
        room_actions.addWidget(self._copy_btn)
        self._invite_btn = self._make_secondary_button("", icon_name="share")
        self._invite_btn.clicked.connect(self._share_room_code)
        room_actions.addWidget(self._invite_btn)
        room_layout.addLayout(room_actions)
        root.addWidget(room_card)

        # ── track card ──
        track_card = self._card_frame()
        track_layout = QVBoxLayout(track_card)
        track_layout.setContentsMargins(14, 12, 14, 12)
        track_layout.setSpacing(8)

        self._track_label = QLabel("", track_card)
        self._track_label.setObjectName("SectionLabel")
        track_layout.addWidget(self._track_label)

        info_row = QHBoxLayout()
        info_row.setSpacing(10)
        info_row.setAlignment(Qt.AlignVCenter)

        self._track_art = TrackCoverWidget(52, 52, radius=10, parent=track_card)
        info_row.addWidget(self._track_art, 0, Qt.AlignVCenter)

        text_col = QVBoxLayout()
        text_col.setSpacing(3)
        text_col.setContentsMargins(0, 0, 0, 0)
        self._track_title = QLabel("", track_card)
        self._track_title.setObjectName("TrackTitle")
        self._track_title.setWordWrap(False)
        self._track_title.setMaximumWidth(220)
        text_col.addWidget(self._track_title)
        self._track_artist = QLabel("", track_card)
        self._track_artist.setObjectName("TrackArtist")
        self._track_artist.setWordWrap(False)
        self._track_artist.setMaximumWidth(220)
        text_col.addWidget(self._track_artist)
        info_row.addLayout(text_col, 1)
        track_layout.addLayout(info_row)

        time_row = QHBoxLayout()
        self._time_left = QLabel("0:00", track_card)
        self._time_left.setObjectName("MiniLabel")
        time_row.addWidget(self._time_left)
        time_row.addStretch(1)
        self._time_right = QLabel("0:00", track_card)
        self._time_right.setObjectName("MiniLabel")
        time_row.addWidget(self._time_right)
        track_layout.addLayout(time_row)

        self._progress = QProgressBar(track_card)
        self._progress.setTextVisible(False)
        self._progress.setRange(0, 1000)
        self._progress.setValue(0)
        self._progress.setFixedHeight(4)
        track_layout.addWidget(self._progress)
        root.addWidget(track_card)

        # ── actions ──
        act_row = QHBoxLayout()
        act_row.setSpacing(8)
        self._copy_invite_btn = self._make_secondary_button("", icon_name="share")
        self._copy_invite_btn.clicked.connect(self._share_room_code)
        act_row.addWidget(self._copy_invite_btn)
        self._leave_btn = self._make_danger_button("")
        self._leave_btn.clicked.connect(self._leave_session)
        act_row.addWidget(self._leave_btn)
        root.addLayout(act_row)

        # compat reference (hidden, not shown)
        self._reconnect_btn = self._make_secondary_button("", icon_name="repeat")
        self._reconnect_btn.clicked.connect(self.queue_refresh)
        self._reconnect_btn.hide()

        return page

    def _build_status_bar(self) -> QWidget:
        bar = QFrame(self._shell)
        bar.setObjectName("StatusBar")
        row = QHBoxLayout(bar)
        row.setContentsMargins(12, 7, 12, 7)
        row.setSpacing(8)
        self._status_dot = QLabel("●", bar)
        self._status_dot.setObjectName("StatusDot")
        row.addWidget(self._status_dot)
        self._status_label = QLabel(self._tr("collab.status.ready"), bar)
        self._status_label.setObjectName("StatusLabel")
        self._status_label.setWordWrap(False)
        row.addWidget(self._status_label, 1)
        return bar

    # ── style helpers ───────────────────────────────────────────────

    def _stylesheet(self) -> str:
        acc = get_accent()
        return f"""
        QDialog#CollabDialog {{ background: transparent; border: none; }}
        QFrame#CollabShell {{
            background: {_SHELL};
            border: 1px solid {_BORDER};
            border-radius: 16px;
        }}
        QWidget {{ background: {_SHELL}; border: none; }}
        QWidget#CollabBody, QStackedWidget#PageStack, QStackedWidget#IdleStack {{
            background: {_SHELL}; border: none;
        }}
        QFrame#TitleBar {{
            background: {_BG};
            border-bottom: 1px solid {_BORDER};
            border-top-left-radius: 16px;
            border-top-right-radius: 16px;
        }}
        QLabel#TitleText {{ color: {_TEXT}; font-size: 14px; font-weight: 800; }}
        QLabel#TitleIcon {{ min-width: 16px; min-height: 16px; }}
        QLabel#StateBadge {{
            color: {_BG};
            background: {acc};
            border-radius: 12px;
            padding: 0 10px;
            font-size: 11px;
            font-weight: 800;
        }}
        QLabel#HeroTitle {{ color: {_TEXT}; font-size: 13px; font-weight: 700; }}
        QFrame#CardFrame {{
            background: {_CARD};
            border: 1px solid {_BORDER};
            border-radius: 14px;
        }}
        QFrame#CardFrame[alt='true'] {{ background: {_CARD_ALT}; }}
        QLabel#SectionLabel {{
            color: {acc};
            font-size: 10px;
            font-weight: 800;
            letter-spacing: 1px;
            background: transparent;
        }}
        QLabel#SectionText {{ color: {_TEXT}; font-size: 12px; background: transparent; }}
        QLabel#HintLabel, QLabel#MiniLabel, QLabel#TrackArtist {{
            color: {_MUTED}; font-size: 11px; background: transparent;
        }}
        QLabel#StatValue {{
            color: {_TEXT}; font-size: 13px; font-weight: 700; background: transparent;
        }}
        QLabel#TrackTitle {{
            color: {_TEXT}; font-size: 13px; font-weight: 700; background: transparent;
        }}
        QLabel#RoomCodeLabel {{
            background: {_CARD_ALT};
            border: 1px solid {_BORDER};
            border-radius: 12px;
            color: {acc};
            font-size: 22px;
            font-weight: 900;
            letter-spacing: 4px;
            padding: 4px 8px;
        }}
        QLineEdit#CodeInput {{
            min-height: 44px;
            background: {_CARD_ALT};
            color: {_TEXT};
            border: 1px solid {_BORDER};
            border-radius: 12px;
            padding: 0 14px;
            font-size: 17px;
            font-weight: 700;
            selection-background-color: {acc};
        }}
        QLineEdit#CodeInput:focus {{ border-color: {acc}; }}
        QFrame#StatusBar {{
            background: {_BG};
            border: 1px solid {_BORDER};
            border-radius: 12px;
        }}
        QLabel#StatusLabel {{ color: {_MUTED}; font-size: 11px; }}
        QLabel#StatusDot  {{ color: {acc}; font-size: 12px; }}
        QProgressBar {{
            background: {_CARD_ALT};
            border: none;
            border-radius: 2px;
        }}
        QProgressBar::chunk {{ background: {acc}; border-radius: 2px; }}
        """

    def _vdivider(self) -> QFrame:
        div = QFrame()
        div.setFixedWidth(1)
        div.setStyleSheet(f"background:{_BORDER}; border:none;")
        return div

    def _stat_col(self, title_key: str, value_label: QLabel) -> QVBoxLayout:
        col = QVBoxLayout()
        col.setContentsMargins(10, 0, 10, 0)
        col.setSpacing(2)
        t = QLabel(self._tr(title_key))
        t.setObjectName("MiniLabel")
        self._stat_title_labels[title_key] = t
        col.addWidget(t)
        value_label.setObjectName("StatValue")
        col.addWidget(value_label)
        return col

    def _card_frame(self, alt: bool = False) -> QFrame:
        frame = QFrame(self)
        frame.setObjectName("CardFrame")
        frame.setProperty("alt", bool(alt))
        return frame

    def _make_titlebar_button(self, icon_name: str, danger: bool = False) -> QPushButton:
        btn = QPushButton(self)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedSize(28, 28)
        color = _ERR if danger else get_accent()
        hover = _rgba(_ERR if danger else get_accent(), 0.18)
        btn.setIcon(create_icon(icon_name, color=color, size=14))
        btn.setIconSize(btn.icon().actualSize(btn.size()))
        btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none; border-radius: 14px; }}"
            f"QPushButton:hover {{ background: {hover}; }}"
        )
        return btn

    def _make_tab_button(self, title: str, subtitle: str) -> QPushButton:
        btn = QPushButton(f"{title}\n{subtitle}", self)
        btn.setCheckable(True)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setMinimumHeight(56)
        btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        btn.setStyleSheet(self._tab_style(False))
        return btn

    def _tab_style(self, active: bool) -> str:
        acc = get_accent()
        if active:
            return (
                f"QPushButton {{ background:{_rgba(acc,0.14)}; color:{_TEXT}; border:1px solid {acc};"
                f" border-radius:12px; padding:10px 12px; text-align:left; font-size:12px; font-weight:700; }}"
                f"QPushButton:hover {{ background:{_rgba(acc,0.20)}; }}"
            )
        return (
            f"QPushButton {{ background:{_CARD}; color:{_TEXT}; border:1px solid {_BORDER};"
            f" border-radius:12px; padding:10px 12px; text-align:left; font-size:12px; font-weight:700; }}"
            f"QPushButton:hover {{ background:{_CARD_ALT}; }}"
        )

    def _apply_button_style(self, btn: QPushButton, bg: str, fg: str, border: str, hover: str):
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedHeight(38)
        btn.setStyleSheet(
            f"QPushButton {{ background:{bg}; color:{fg}; border:1px solid {border};"
            f" border-radius:12px; font-size:12px; font-weight:800; padding:0 12px; text-align:center; }}"
            f"QPushButton:hover {{ background:{hover}; }}"
            f"QPushButton:disabled {{ background:{_CARD_ALT}; color:{_MUTED}; border:1px solid {_BORDER}; }}"
        )

    def _make_primary_button(self, text: str) -> QPushButton:
        btn = QPushButton(text, self)
        acc = get_accent()
        self._apply_button_style(btn, acc, _BG, acc, acc)
        return btn

    def _make_secondary_button(self, text: str, icon_name: str | None = None) -> QPushButton:
        btn = QPushButton(text, self)
        if icon_name:
            btn.setIcon(create_icon(icon_name, color=_TEXT, size=13))
            btn.setIconSize(btn.icon().actualSize(btn.size()))
        self._apply_button_style(btn, _CARD_ALT, _TEXT, _BORDER, "#12203a")
        return btn

    def _make_danger_button(self, text: str) -> QPushButton:
        btn = QPushButton(text, self)
        self._apply_button_style(btn, _CARD_ALT, _ERR, _rgba(_ERR, 0.55), _rgba(_ERR, 0.12))
        return btn

    # ── geometry ────────────────────────────────────────────────────

    def _available_geometry(self):
        screen = None
        try:
            handle = self.windowHandle()
            if handle is not None:
                screen = handle.screen()
        except Exception:
            pass
        if screen is None:
            try:
                screen = self.screen()
            except Exception:
                pass
        if screen is None:
            screen = QApplication.primaryScreen()
        return screen.availableGeometry() if screen is not None else None

    def _apply_responsive_geometry(self, initial: bool = False):
        geom = self._available_geometry()
        if geom is None:
            if initial:
                self.setMinimumSize(360, 440)
                self.resize(420, 540)
            return
        avail_w = max(1, geom.width() - 48)
        avail_h = max(1, geom.height() - 48)
        min_w = min(360, avail_w)
        min_h = min(440, avail_h)
        max_w = max(min_w, avail_w)
        max_h = max(min_h, avail_h)
        target_w = min(440, max_w)
        target_h = min(580, max_h)
        self.setMinimumSize(min_w, min_h)
        self.setMaximumSize(max_w, max_h)
        if initial:
            self.resize(max(min_w, target_w), max(min_h, target_h))
            return
        new_w = max(min_w, min(self.width(), max_w))
        new_h = max(min_h, min(self.height(), max_h))
        if new_w != self.width() or new_h != self.height():
            self.resize(new_w, new_h)

    # ── events ──────────────────────────────────────────────────────

    def showEvent(self, event):
        super().showEvent(event)
        if not self._live_timer.isActive():
            self._live_timer.start()
        self._apply_responsive_geometry()
        self.queue_refresh()
        if not self._did_intro_anim:
            self._did_intro_anim = True
            self.setWindowOpacity(0.0)
            end   = self.pos()
            start = end + QPoint(0, 10)
            self.move(start)
            fade = QPropertyAnimation(self, b"windowOpacity", self)
            fade.setDuration(150)
            fade.setStartValue(0.0)
            fade.setEndValue(1.0)
            slide = QPropertyAnimation(self, b"pos", self)
            slide.setDuration(150)
            slide.setEasingCurve(QEasingCurve.OutCubic)
            slide.setStartValue(start)
            slide.setEndValue(end)
            fade.start()
            slide.start()
            self._intro_anim_refs = [fade, slide]

    def hideEvent(self, event):
        if self._live_timer.isActive():
            self._live_timer.stop()
        super().hideEvent(event)

    def closeEvent(self, event):
        if self._live_timer.isActive():
            self._live_timer.stop()
        event.ignore()
        self.hide()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and event.position().y() <= 48:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_offset = None
        super().mouseReleaseEvent(event)

    # ── data / state ────────────────────────────────────────────────

    def _handle_status_signal(self, state: str, msg: str):
        self.on_status(state, msg)

    def refresh_now(self):
        self._refresh_texts()
        session = getattr(self._app, "_collab_session", None)
        has_live = bool(
            session and session.room_code
            and session.state in {session.ST_CONNECTED, session.ST_CONNECTING}
        )
        self._page_stack.setCurrentWidget(self._live_page if has_live else self._idle_page)
        if has_live:
            self._sync_live_page(session)
        else:
            self._sync_idle_page()
        state = self._status_state
        msg   = self._status_message
        if has_live and state in {"idle", session.ST_CONNECTED, session.ST_CONNECTING, session.ST_ERROR, session.ST_DISCONNECTED}:
            state = session.state if state == "idle" else state
            msg = session.summary_message() or msg
        self._apply_status_line(state or "idle", msg or self._tr("collab.status.ready"))
        if self.isVisible():
            self._apply_responsive_geometry()

    def on_status(self, state: str, msg: str):
        self._status_state   = state or "idle"
        self._status_message = msg or self._tr("collab.status.ready")
        self.refresh_now()

    def _sync_idle_page(self):
        self._update_badge(self._tr("collab.badge.new"), get_accent())
        self._hero_title.setText(self._tr("collab.hero.idle"))
        self._start_btn.setEnabled(True)
        self._start_btn.setText(self._tr("collab.host.start"))
        self._join_btn.setEnabled(True)
        self._join_btn.setText(self._tr("collab.join.join"))
        self._switch_mode(self._mode)

    def _sync_live_page(self, session):
        if session.peer_connected:
            self._update_badge(self._tr("collab.badge.active"), get_accent())
        elif session.is_host:
            self._update_badge(self._tr("collab.badge.waiting_friend"), _WARN)
        else:
            self._update_badge(self._tr("collab.badge.waiting_host"), _WARN)
        self._hero_title.setText(self._tr("collab.hero.live"))
        self._role_value.setText(session.role_label)
        self._conn_value.setText(session.connection_label)
        self._members_value.setText(session.participant_label)
        self._room_code_lbl.setText(session.formatted_room_code or "---- ----")
        title, artist, thumb, pos_ms, len_ms = self._current_track_snapshot()
        self._track_title.setText(title)
        self._track_artist.setText(artist)
        if thumb:
            try:
                self._app._load_image(thumb, self._track_art, (52, 52))
            except Exception as _e:
                log.debug("Collab kapak yüklenemedi: %s", _e)
        else:
            self._track_art.clear()
        self._time_left.setText(self._fmt_ms(pos_ms))
        self._time_right.setText(self._fmt_ms(len_ms))
        self._progress.setValue(
            max(0, min(1000, int((pos_ms / max(1, len_ms)) * 1000))) if len_ms > 0 else 0
        )

    def _current_track_snapshot(self) -> tuple[str, str, str, int, int]:
        title  = self._tr("collab.live.no_track")
        artist = self._tr("collab.live.no_track_hint")
        thumb  = ""
        pos_ms = len_ms = 0
        try:
            queue = getattr(self._app, "queue", []) or []
            idx   = int(getattr(self._app, "queue_index", -1))
            if 0 <= idx < len(queue):
                track  = queue[idx]
                title  = str(track.get("title") or self._tr("collab.track.unknown_title"))
                try:
                    artist = self._app._artist_str(track) or self._tr("collab.track.unknown_artist")
                except Exception:
                    artist = self._tr("collab.track.unknown_artist")
                try:
                    thumb = self._app._thumb(track, big=True) or ""
                except Exception:
                    thumb = ""
        except Exception as e:
            log.debug("Track snapshot okunamadı: %s", e)
        try:
            pos_ms = max(0, int(self._app.player.get_time()))
        except Exception:
            pass
        try:
            len_ms = max(0, int(self._app.player.get_length()))
        except Exception:
            pass
        return title, artist, thumb, pos_ms, len_ms

    def _switch_mode(self, mode: str):
        self._mode = mode if mode in {"host", "join"} else "host"
        is_host = self._mode == "host"
        self._mode_host_btn.setChecked(is_host)
        self._mode_join_btn.setChecked(not is_host)
        self._mode_host_btn.setStyleSheet(self._tab_style(is_host))
        self._mode_join_btn.setStyleSheet(self._tab_style(not is_host))
        self._idle_stack.setCurrentIndex(0 if is_host else 1)

    def _normalize_join_code(self, text: str):
        clean = parse_room_code(text)
        formatted = fmt_room_code(clean) if clean else ""
        self._join_code.blockSignals(True)
        self._join_code.setText(formatted)
        self._join_code.blockSignals(False)
        self._join_hint.setText(
            self._tr("collab.join.hint_ready") if len(clean) == 8
            else self._tr("collab.join.hint")
        )

    # ── actions ─────────────────────────────────────────────────────

    def _paste_code(self):
        text    = QApplication.clipboard().text() or ""
        cleaned = parse_room_code(text)
        self._join_code.setText(fmt_room_code(cleaned))
        self._normalize_join_code(self._join_code.text())
        if cleaned:
            self._toast_or_status(self._tr("collab.toast.code_pasted"))

    def _start_session(self):
        self._start_btn.setEnabled(False)
        self._start_btn.setText(self._tr("collab.host.starting"))
        code = self._app.collab_create()
        if not code:
            self._start_btn.setEnabled(True)
            self._start_btn.setText(self._tr("collab.host.start"))
            self._apply_status_line("error", self._tr("collab.host.start_failed"))
            return
        self.queue_refresh()

    def _join_session(self):
        code = parse_room_code(self._join_code.text())
        if len(code) != 8:
            self._apply_status_line("error", self._tr("collab.join.invalid"))
            return
        self._join_btn.setEnabled(False)
        self._join_btn.setText(self._tr("collab.join.connecting"))
        ok = self._app.collab_join(code)
        if not ok:
            self._join_btn.setEnabled(True)
            self._join_btn.setText(self._tr("collab.join.join"))
            self._apply_status_line("error", self._tr("collab.join.failed"))
            return
        self.queue_refresh()

    def _leave_session(self):
        self._app.collab_leave()
        self._status_state   = "idle"
        self._status_message = self._tr("collab.toast.session_closed")
        self.queue_refresh()

    def _copy_room_code(self):
        session = getattr(self._app, "_collab_session", None)
        if not session or not session.room_code:
            return
        QApplication.clipboard().setText(session.formatted_room_code)
        self._toast_or_status(self._tr("collab.toast.room_code_copied"))

    def _share_room_code(self):
        session = getattr(self._app, "_collab_session", None)
        if not session or not session.room_code:
            return
        invite = self._tr("collab.invite_message", code=session.formatted_room_code)
        QApplication.clipboard().setText(invite)
        self._toast_or_status(self._tr("collab.toast.invite_copied"))

    # ── ui helpers ──────────────────────────────────────────────────

    def _apply_status_line(self, state: str, message: str):
        acc = get_accent()
        color = {
            "connected":    acc,
            "idle":         acc,
            "connecting":   _WARN,
            "error":        _ERR,
            "disconnected": _MUTED,
        }.get(state, _MUTED)
        self._status_dot.setStyleSheet(f"color:{color}; font-size:12px;")
        self._status_label.setText(message or self._tr("collab.status.ready"))

    def _update_badge(self, text: str, color: str):
        safe = color or get_accent()
        self._badge.setText(text)
        self._badge.setStyleSheet(
            f"background:{safe}; color:{_BG}; border-radius:12px;"
            f" padding:0 10px; font-size:11px; font-weight:800;"
        )

    def _toast_or_status(self, message: str):
        try:
            from ui.toast import show_toast
            show_toast(self._app, message)
        except Exception:
            self._apply_status_line("idle", message)

    def _fmt_ms(self, ms: int) -> str:
        try:
            return self._app._fmt(int(ms))
        except Exception:
            ms      = max(0, int(ms or 0))
            seconds = ms // 1000
            minutes, seconds = divmod(seconds, 60)
            hours, minutes   = divmod(minutes, 60)
            return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes}:{seconds:02d}"
