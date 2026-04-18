"""Mixin for Stats functionality."""
import logging
import time
from datetime import datetime
from typing import Optional

log = logging.getLogger("iqtMusic")

from core.constants import BG_CARD, BG_CARD_HOVER, BG_ELEVATED, BORDER_COLOR, TEXT_PRIMARY, TEXT_SECONDARY
from core.theme import get_accent, get_accent_hover
from utils.helpers import create_icon, safe_save_json
from ui.titlebar import TitleBar

from PySide6.QtCore import Qt
import vlc
from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

class StatsMixin:

    _MAX_LISTEN_EVENTS = 5000
    _MAX_DAILY_MS_DAYS = 400

    def _played_at_now(self) -> str:
        return datetime.now().isoformat(timespec="seconds")

    def _stamp_played_track(self, track, played_at: Optional[str] = None) -> dict:
        if not isinstance(track, dict):
            return {}
        stamped = dict(track)
        stamped["played_at"] = str(
            played_at
            or stamped.get("played_at")
            or stamped.get("added_at")
            or self._played_at_now()
        )
        return stamped

    def _prune_daily_ms(self):
        daily_ms = self.stats.get("daily_ms", {})
        if not isinstance(daily_ms, dict):
            self.stats["daily_ms"] = {}
            return
        if len(daily_ms) <= self._MAX_DAILY_MS_DAYS:
            return
        keep_keys = sorted(daily_ms.keys())[-self._MAX_DAILY_MS_DAYS:]
        self.stats["daily_ms"] = {
            key: int(daily_ms.get(key, 0) or 0)
            for key in keep_keys
        }

    def _append_listen_event(self, track: dict, played_at: str):
        events = self.stats.get("listen_events", [])
        if not isinstance(events, list):
            events = []
            self.stats["listen_events"] = events
        event = self._stamp_played_track(track, played_at)
        events.insert(0, event)
        del events[self._MAX_LISTEN_EVENTS:]

    def _add_history(self, track, played_at: Optional[str] = None):
        item = self._stamp_played_track(track, played_at)
        vid = item.get("videoId", "")
        self.history = [t for t in self.history if t.get("videoId") != vid]
        self.history.insert(0, item)
        self.history = self.history[:500]
        safe_save_json(self.hist_file, self.history)
        try:
            self.sig.history_updated.emit()
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)

    def _reset_listen_session(self, track):
        self._listen_track = dict(track) if isinstance(track, dict) else None
        self._listen_vid = str(track.get("videoId", "")) if isinstance(track, dict) else ""
        self._listen_elapsed_ms = 0
        self._listen_counted = False
        self._listen_last_tick = time.monotonic()
        self._listen_last_state = None

    def _listen_threshold_ms(self, track=None):
        track = track or getattr(self, "_listen_track", None) or {}
        dur_ms = 0
        try:
            dur_ms = int(track.get("duration_seconds") or 0) * 1000
        except (ValueError, TypeError, AttributeError):
            dur_ms = 0
        if dur_ms <= 0:
            try:
                dur_ms = max(int(self.player.get_length() or 0), int(self.total_dur or 0))
            except Exception:
                dur_ms = int(self.total_dur or 0)
        if dur_ms > 0:
            return dur_ms // 2
        return 30_000

    def _apply_listen_time(self, delta_ms: int):
        if delta_ms <= 0:
            return
        delta_ms = int(delta_ms)
        self.stats["total_ms"] = self.stats.get("total_ms", 0) + delta_ms
        day_key = datetime.now().date().isoformat()
        daily_ms = self.stats.get("daily_ms", {})
        if not isinstance(daily_ms, dict):
            daily_ms = {}
            self.stats["daily_ms"] = daily_ms
        daily_ms[day_key] = int(daily_ms.get(day_key, 0) or 0) + delta_ms
        self._prune_daily_ms()

    def _maybe_commit_listen(self):
        if self._listen_counted or not self._listen_vid or not self._listen_track:
            return
        threshold_ms = self._listen_threshold_ms(self._listen_track)
        if self._listen_elapsed_ms < threshold_ms:
            return
        self._listen_counted = True
        played_at = self._played_at_now()
        self._listen_track = self._stamp_played_track(self._listen_track, played_at)
        self._add_history(self._listen_track, played_at)
        self._update_stats(self._listen_track, played_at)
        self._media_cache.queue(self._listen_track, self._ydl_opts)

    def _tick_listen_stats(self, state):
        now = time.monotonic()
        last_tick = getattr(self, "_listen_last_tick", None)
        prev_state = getattr(self, "_listen_last_state", None)

        if (
            last_tick is not None
            and prev_state == vlc.State.Playing
            and self._listen_vid
        ):
            delta_ms = int((now - last_tick) * 1000)
            if 0 < delta_ms < 5_000:
                self._listen_elapsed_ms += delta_ms
                self._apply_listen_time(delta_ms)
                self._maybe_commit_listen()

        self._listen_last_tick = now
        self._listen_last_state = state

    def _update_stats(self, track, played_at: Optional[str] = None):
        stamped = self._stamp_played_track(track, played_at)
        vid = stamped.get("videoId", "")
        if not vid:
            return
        pc = self.stats.setdefault("play_count", {})
        pc[vid] = pc.get(vid, 0) + 1
        self._append_listen_event(stamped, stamped["played_at"])
        safe_save_json(self.stats_file, self.stats)
        try:
            self.sig.stats_updated.emit(self.stats)
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)

    def _update_stats_duration(self, vid: str):
        try:
            length = self.player.get_length()
            if length > 0:
                self.stats["total_ms"] = self.stats.get("total_ms", 0) + length
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)

    def _confirm_stats_reset_dialog(self):

        acc = get_accent()
        dlg = QDialog(self)
        dlg.setWindowFlags(dlg.windowFlags() | Qt.FramelessWindowHint)
        dlg.setAttribute(Qt.WA_TranslucentBackground, True)
        dlg.setModal(True)
        dlg.setFixedSize(430, 190)

        outer = QVBoxLayout(dlg)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        shell = QFrame()
        shell.setObjectName("StatsResetDialog")
        shell.setStyleSheet(f"""
            QFrame#StatsResetDialog {{
                background: {BG_CARD};
                border: 1px solid {acc}66;
                border-radius: 18px;
            }}
            QFrame#StatsResetDialog QLabel {{
                background: transparent;
                border: none;
            }}
        """)
        outer.addWidget(shell)

        shell_l = QVBoxLayout(shell)
        shell_l.setContentsMargins(0, 0, 0, 0)
        shell_l.setSpacing(0)

        tb = TitleBar(dlg, title=self._tr("stats.reset.titlebar"))
        tb.setStyleSheet(f"background:{BG_CARD}; color:{TEXT_PRIMARY};")
        shell_l.addWidget(tb)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{acc}55; border:none;")
        shell_l.addWidget(sep)

        content = QWidget()
        content.setStyleSheet("background:transparent;")
        shell_l.addWidget(content, 1)

        content_l = QVBoxLayout(content)
        content_l.setContentsMargins(24, 20, 24, 22)
        content_l.setSpacing(18)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(14)

        icon = QLabel()
        icon.setPixmap(create_icon("delete", acc, 26).pixmap(26, 26))
        icon.setFixedSize(30, 30)
        top.addWidget(icon, 0, Qt.AlignTop)

        text_v = QVBoxLayout()
        text_v.setContentsMargins(0, 0, 0, 0)
        text_v.setSpacing(6)

        title = QLabel(self._tr("stats.reset.question"))
        title.setWordWrap(True)
        title.setStyleSheet(
            f"font-size:15px; font-weight:800; color:{TEXT_PRIMARY}; background:transparent;")
        desc = QLabel(self._tr("stats.reset.desc"))
        desc.setWordWrap(True)
        desc.setStyleSheet(
            f"font-size:12px; color:{TEXT_SECONDARY}; background:transparent;")
        text_v.addWidget(title)
        text_v.addWidget(desc)
        top.addLayout(text_v, 1)
        content_l.addLayout(top)

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(10)
        btn_row.addStretch()

        no_btn = QPushButton(self._tr("stats.reset.no"))
        no_btn.setFixedHeight(36)
        no_btn.setCursor(Qt.PointingHandCursor)
        no_btn.setFocusPolicy(Qt.NoFocus)
        no_btn.setStyleSheet(
            f"QPushButton{{background:{BG_ELEVATED}; color:{TEXT_SECONDARY}; "
            f"border:1px solid {BORDER_COLOR}; border-radius:12px; padding:0 18px; font-weight:700;}}"
            f"QPushButton:hover{{background:{BG_CARD_HOVER}; color:{TEXT_PRIMARY}; border-color:{acc}44;}}"
        )
        no_btn.clicked.connect(dlg.reject)

        yes_btn = QPushButton(self._tr("stats.reset.yes"))
        yes_btn.setFixedHeight(36)
        yes_btn.setCursor(Qt.PointingHandCursor)
        yes_btn.setFocusPolicy(Qt.NoFocus)
        yes_btn.setStyleSheet(
            f"QPushButton{{background:{acc}; color:#081018; "
            f"border:1px solid {acc}; border-radius:12px; padding:0 20px; font-weight:800;}}"
            f"QPushButton:hover{{background:{get_accent_hover()}; border-color:{get_accent_hover()};}}"
        )
        yes_btn.clicked.connect(dlg.accept)

        btn_row.addWidget(no_btn)
        btn_row.addWidget(yes_btn)
        content_l.addLayout(btn_row)

        return dlg.exec() == QDialog.Accepted

    def _reset_stats(self):
        if not self._confirm_stats_reset_dialog():
            return

        self.stats = {
            "play_count": {},
            "total_ms": 0,
            "daily_ms": {},
            "listen_events": [],
            "period_start": datetime.now().isoformat(timespec="seconds"),
        }
        safe_save_json(self.stats_file, self.stats)

        current_track = None
        if self.queue and 0 <= self.queue_index < len(self.queue):
            current_track = self.queue[self.queue_index]
        if current_track:
            self._reset_listen_session(current_track)
        else:
            self._listen_track = None
            self._listen_vid = ""
            self._listen_elapsed_ms = 0
            self._listen_counted = False
            self._listen_last_tick = None
            self._listen_last_state = None

        try:
            self.sig.stats_updated.emit(self.stats)
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
        self.sig.notify.emit("İstatistikler sıfırlandı")
        if self.current_page == "stats":
            self.page_stats()

    # ══════════════════════════════════════════════════════════════════════════
    # RESİM YÜKLEMESİ
    # ══════════════════════════════════════════════════════════════════════════
