"""Mixin for Persistence functionality."""
import logging

log = logging.getLogger("iqtMusic")

from core.constants import BG_CARD, BG_CARD_HOVER
from core.theme import get_accent
from utils.helpers import safe_load_json, safe_save_json

from PySide6.QtWidgets import QApplication, QSystemTrayIcon
from PySide6.QtCore import QEvent, QRect, QSize, Qt
import core.constants as _C


class PersistenceMixin:
    _DEFAULT_WINDOW_WIDTH = 1440
    _DEFAULT_WINDOW_HEIGHT = 960
    _DEFAULT_MIN_WINDOW_WIDTH = 900
    _DEFAULT_MIN_WINDOW_HEIGHT = 600
    _WINDOW_SCREEN_PADDING = 48

    def _available_window_geometry(self):
        screen = None
        try:
            handle = self.windowHandle()
            if handle is not None:
                screen = handle.screen()
        except Exception:
            screen = None
        if screen is None:
            try:
                screen = self.screen()
            except Exception:
                screen = None
        if screen is None:
            app = QApplication.instance()
            if app is not None:
                screen = app.primaryScreen()
        return screen.availableGeometry() if screen is not None else None

    def _fit_window_to_available_geometry(self, initial: bool = False):
        if self.isMaximized() or self.isFullScreen():
            return

        geom = self._available_window_geometry()
        if geom is None:
            if initial:
                self.setMinimumSize(
                    self._DEFAULT_MIN_WINDOW_WIDTH,
                    self._DEFAULT_MIN_WINDOW_HEIGHT,
                )
                self.resize(
                    self._DEFAULT_WINDOW_WIDTH,
                    self._DEFAULT_WINDOW_HEIGHT,
                )
            return

        avail_w = max(1, geom.width() - self._WINDOW_SCREEN_PADDING)
        avail_h = max(1, geom.height() - self._WINDOW_SCREEN_PADDING)
        min_w = min(self._DEFAULT_MIN_WINDOW_WIDTH, avail_w)
        min_h = min(self._DEFAULT_MIN_WINDOW_HEIGHT, avail_h)

        self.setMinimumSize(min_w, min_h)

        if initial:
            target_w = min(self._DEFAULT_WINDOW_WIDTH, avail_w)
            target_h = min(self._DEFAULT_WINDOW_HEIGHT, avail_h)
        else:
            target_w = min(max(self.width(), min_w), avail_w)
            target_h = min(max(self.height(), min_h), avail_h)

        new_w = max(min_w, target_w)
        new_h = max(min_h, target_h)
        if self.width() != new_w or self.height() != new_h:
            self.resize(new_w, new_h)

        max_x = geom.x() + max(0, geom.width() - new_w)
        max_y = geom.y() + max(0, geom.height() - new_h)
        if initial:
            new_x = geom.x() + max(0, (geom.width() - new_w) // 2)
            new_y = geom.y() + max(0, (geom.height() - new_h) // 2)
        else:
            new_x = min(max(self.x(), geom.x()), max_x)
            new_y = min(max(self.y(), geom.y()), max_y)

        if self.x() != new_x or self.y() != new_y:
            self.move(new_x, new_y)

    def _window_display_mode(self) -> str:
        state = self.windowState()
        if state & Qt.WindowFullScreen:
            return "fullscreen"
        if state & Qt.WindowMaximized:
            return "maximized"
        return "windowed"

    def _sync_titlebar_window_state(self):
        titlebar = getattr(self, "_titlebar", None)
        if titlebar is None or not hasattr(titlebar, "sync_window_state"):
            return
        try:
            titlebar.sync_window_state()
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)

    def _remember_windowed_geometry(self):
        if self.isMaximized() or self.isFullScreen():
            return
        try:
            geom = self.geometry()
            if geom.isValid() and geom.width() > 0 and geom.height() > 0:
                self._windowed_geometry = QRect(geom)
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)

    def _restore_windowed_geometry(self):
        geom = getattr(self, "_windowed_geometry", None)
        self.showNormal()
        try:
            if geom is not None and geom.isValid():
                self.setGeometry(QRect(geom))
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
        self._fit_window_to_available_geometry()
        self._remember_windowed_geometry()
        self._sync_titlebar_window_state()

    def toggle_maximize_restore(self):
        if self.isFullScreen():
            self._restore_windowed_geometry()
            return
        if self.isMaximized():
            self._restore_windowed_geometry()
            return
        self._remember_windowed_geometry()
        self.showMaximized()
        self._sync_titlebar_window_state()

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self._restore_windowed_geometry()
            return
        self._remember_windowed_geometry()
        self.showFullScreen()
        self._sync_titlebar_window_state()

    def exit_fullscreen(self):
        if self.isFullScreen():
            self._restore_windowed_geometry()

    def _refresh_playerbar_layout(self):
        if not hasattr(self, "player_bar"):
            return
        w       = max(640, self.width())
        compact = w < 1180
        tiny    = w < 980

        self.player_bar.setFixedHeight(92 if tiny else 98)
        if hasattr(self, "img_cover"):
            cover = 56 if tiny else 64
            self.img_cover.setFixedSize(cover, cover)
        if hasattr(self, "btn_play"):
            btn  = 28 if tiny else 30
            icon = 10 if tiny else 11
            self.btn_play.setFixedSize(btn, btn)
            self.btn_play.setIconSize(QSize(icon, icon))
        for name in ("btn_shuffle", "btn_prev", "btn_next", "btn_repeat"):
            b = getattr(self, name, None)
            if b:
                s = 28 if tiny else 30
                b.setFixedSize(s, s)
                b.setStyleSheet(
                    f"QPushButton{{border:1px solid transparent; background:transparent; border-radius:{s//2}px;}}"
                    f"QPushButton:hover{{background:{BG_CARD_HOVER}; border-color:{get_accent()}22;}}")
        for b in getattr(self, "_player_tool_buttons", []):
            s    = 26 if tiny else 30
            icon = 15 if tiny else 17
            b.setFixedSize(s, s)
            b.setIconSize(QSize(icon, icon))
            b.setStyleSheet(
                f"QPushButton{{border:1px solid transparent; background:transparent; border-radius:{s//2}px;}}"
                f"QPushButton:hover{{background:{BG_CARD}; border-color:{get_accent()}22; color:white;}}")
        if hasattr(self, "vol_slider"):
            self.vol_slider.setFixedWidth(72 if tiny else 84 if compact else 92)
        if hasattr(self, "lbl_cur"):
            self.lbl_cur.setMinimumWidth(32 if tiny else 34)
        if hasattr(self, "lbl_end"):
            self.lbl_end.setMinimumWidth(32 if tiny else 34)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        state = self.windowState()
        if not (state & Qt.WindowMinimized) and not self.isMaximized() and not self.isFullScreen():
            self._remember_windowed_geometry()
        self._sync_titlebar_window_state()

    def moveEvent(self, event):
        super().moveEvent(event)
        state = self.windowState()
        if not (state & Qt.WindowMinimized) and not self.isMaximized() and not self.isFullScreen():
            self._remember_windowed_geometry()
        self._sync_titlebar_window_state()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.WindowStateChange:
            state = self.windowState()
            if state & Qt.WindowMinimized:
                self._sync_titlebar_window_state()
                return
            if not self.isMaximized() and not self.isFullScreen():
                self._fit_window_to_available_geometry()
                self._remember_windowed_geometry()
            self._sync_titlebar_window_state()
            if hasattr(self, "_update_window_rounding"):
                self._update_window_rounding()

    # ══════════════════════════════════════════════════════════════════════════
    # KAYDETME / YÜKLEME
    # ══════════════════════════════════════════════════════════════════════════


    def _save_state(self):
        if self.queue and self.queue_index != -1:
            safe_save_json(self.last_file, {
                "track":    self.queue[self.queue_index],
                "position": self.player.get_time(),
            })
        safe_save_json(self.hist_file,     self.history)
        safe_save_json(self.playlist_file, self.playlists)
        safe_save_json(self.stats_file,    self.stats)
        # Sanatçı önbelleğini diske yaz
        payload = getattr(self, "_artists_overview_payload", None)
        updated_at = float(getattr(self, "_artists_overview_updated_at", 0) or 0)
        if payload and updated_at:
            import os
            cache_file = os.path.join(self.base_dir, "artists_cache.json")
            safe_save_json(cache_file, {"payload": payload, "updated_at": updated_at})


    def _save_settings(self):
        payload = {
            "language":            getattr(self, "_language", "tr"),
            "theme":               _C.CURRENT_THEME,
            "volume":              self._volume,
            "eq_vals":             self._eq_vals,
            "dl_format":           getattr(self.dl, "dl_format",  "m4a"),
            "dl_quality":          getattr(self.dl, "dl_quality", "best"),
            "dl_dir":              getattr(self.dl, "dl_dir",     ""),
            "playlist_covers":     getattr(self, "_playlist_covers", {}),
            "playlist_overview_sort_mode": str(
                getattr(self, "_playlist_overview_sort_mode", "added") or "added"
            ).strip().lower(),
            "playlist_manual_order":       list(
                getattr(self, "_playlist_manual_order", None) or []
            ),
            "content_region_mode": getattr(self, "_content_region_mode", "auto"),
            "content_region":      getattr(self, "_content_region", "TR"),
            "playback_rate":       getattr(self, "_playback_rate", 1.0),
            "loudness_mode":       getattr(self, "_loudness_mode", "light"),
            "audio_output_device": getattr(self, "_audio_output_device", ""),
            "audio_output_name":   getattr(self, "_audio_output_name", ""),
            "next_preload_on":     bool(getattr(self, "_next_preload_on", True)),
            "volume_step":         int(getattr(self, "_volume_step", 5) or 5),
            "seek_step_sec":       int(getattr(self, "_seek_step_sec", 5) or 5),
            "media_keys_enabled":  bool(getattr(self, "_media_keys_enabled", True)),
            "shortcuts":           dict(getattr(self, "_shortcut_map", {}) or {}),
            "discord_presence_enabled": bool(getattr(self, "_discord_presence_enabled", True)),
            "discord_display_mode": str(getattr(self, "_discord_display_mode", "song") or "song"),
            "crossfade_duration":  0,
            "gapless_on":          False,
        }
        safe_save_json(self._settings_file, payload)


    def _set_lastfm_api_key(self, api_key: str):
        self._lastfm_api_key = str(api_key or "").strip()
        self._save_settings()


    def _save_dl_settings(self):
        """İndirme ayarlarını kaydet ve downloads sayfasını yenile."""
        self._save_settings()
        if self.current_page == "downloads":
            self.page_downloads()


    def _restore_pos(self, expected_vid=None, request_id=None):
        if request_id is not None and request_id != self._play_request_id:
            return

        if expected_vid:
            current_vid = ""
            if self.queue and 0 <= self.queue_index < len(self.queue):
                current_vid = self.queue[self.queue_index].get("videoId", "")
            if current_vid != expected_vid:
                return

        # _pending_restore_pos, __init__'te last_state["position"] değeriyle
        # doldurulur. Buraya gelindiyse sadece bu değeri kullanmak yeterlidir;
        # last_state'e tekrar bakmaya gerek yoktur.
        pos = self._pending_restore_pos
        if pos is not None:
            try:
                self.player.set_time(int(pos))
            except Exception as _e:
                log.debug("Sessiz hata: %s", _e)

        if expected_vid and expected_vid == self._pending_restore_vid:
            self._pending_restore_pos = None
            self._pending_restore_vid = ""

        self.sig.player_ui_update.emit()

    # ══════════════════════════════════════════════════════════════════════════
    # PENCERE OLAYLARI
    # ══════════════════════════════════════════════════════════════════════════


    def _show_window(self):
        self._fit_window_to_available_geometry()
        self.show()
        self.setWindowState(
            self.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
        self.raise_()
        self.activateWindow()


    def closeEvent(self, event):
        self._save_state()
        self._save_settings()
        if not getattr(self, "_tray_available", False) or getattr(self, "tray", None) is None:
            # Tamamen çıkış — tüm yüzen pencereleri kapat, player'ı durdur
            for attr in ("_lyr_win", "_collab_dialog"):
                win = getattr(self, attr, None)
                if win is not None:
                    try:
                        win.close()
                    except Exception as _e:
                        log.debug("Sessiz hata: %s", _e)
            try:
                self.player.stop()
            except Exception as _e:
                log.debug("Sessiz hata: %s", _e)
            event.accept()
            from PySide6.QtCore import QTimer
            from PySide6.QtWidgets import QApplication
            QTimer.singleShot(0, QApplication.quit)
            return
        # Tray modu — sadece gizle
        try:
            lyr_win = getattr(self, "_lyr_win", None)
            if lyr_win is not None:
                lyr_win.hide()
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
        try:
            collab_dlg = getattr(self, "_collab_dialog", None)
            if collab_dlg is not None:
                collab_dlg.hide()
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
        try:
            collab_session = getattr(self, "_collab_session", None)
            if collab_session is not None and getattr(collab_session, "room_code", ""):
                self.collab_leave()
                self.player.stop()
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
        event.ignore()
        self.hide()
        try:
            if self.tray.supportsMessages():
                self.tray.showMessage(
                    "iqtMusic",
                    "Arka planda calismaya devam ediyor.",
                    QSystemTrayIcon.Information,
                    2000,
                )
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)


    def _cleanup(self):
        if self._cleanup_done:
            return
        self._cleanup_done = True
        self._save_state()
        self._save_settings()
        try:
            lyr_win = getattr(self, "_lyr_win", None)
            if lyr_win is not None:
                lyr_win.hide()
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
        try:
            collab_dlg = getattr(self, "_collab_dialog", None)
            if collab_dlg is not None:
                collab_dlg.hide()
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
        try:
            if hasattr(self, "collab_leave"):
                self.collab_leave()
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
        try:
            if hasattr(self, "_discord_shutdown"):
                self._discord_shutdown()
            self._img_pool.shutdown(wait=False, cancel_futures=True)
            self._net_pool.shutdown(wait=False, cancel_futures=True)
            self._stream_pool.shutdown(wait=False, cancel_futures=True)
            self._stream_prefetch_pool.shutdown(wait=False, cancel_futures=True)
            if getattr(self, '_media_key_listener', None):
                try:
                    self._media_key_listener.stop()
                except Exception:
                    pass
            self._media_cache.shutdown()
            self.dl.shutdown()
            self._http.close()
            self.player.stop()
            self.vlc_inst.release()
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)


    def _quit(self):
        if getattr(self, "tray", None) is not None:
            self.tray.hide()
        QApplication.quit()
