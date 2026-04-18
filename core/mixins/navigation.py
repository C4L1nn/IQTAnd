"""Mixin for Navigation functionality."""
import logging
import time

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, Property, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QColor, QPainter

from core.constants import BG_BLACK
from pages.home_clean import build_home_page
from pages.search import build_search_page
from pages.category import build_category_page
from pages.favorites import build_favs_page
from pages.downloads import build_downloads_page
from pages.playlist import build_playlist_page
from pages.playlists_overview import build_playlists_overview_page
from pages.queue import build_queue_page, _rebuild_queue_list, _refresh_queue_list_rows, _queue_current_video_id
from pages.artist import build_artist_page, build_artist_album_page
from pages.artists import build_artists_page
from pages.settings import build_settings_page
from pages.stats import build_stats_page
from utils.helpers import qt_is_valid

log = logging.getLogger("iqtMusic")


class _PageFadeOverlay(QWidget):
    """Lightweight painted overlay for page transitions."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self._alpha = 0
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.hide()

    def _get_alpha(self) -> int:
        return self._alpha

    def _set_alpha(self, value: int):
        self._alpha = max(0, min(255, int(value)))
        self.update()

    alpha = Property(int, _get_alpha, _set_alpha)

    def paintEvent(self, _event):
        if self._alpha <= 0:
            return
        painter = QPainter(self)
        color = QColor(BG_BLACK)
        color.setAlpha(self._alpha)
        painter.fillRect(self.rect(), color)


class NavigationMixin:

    def _ensure_page_transition_overlay(self):
        overlay = self._page_transition_overlay
        if overlay is None or not qt_is_valid(overlay):
            overlay = _PageFadeOverlay(self.pages)
            self._page_transition_overlay = overlay
            self._page_transition_overlay.hide()
        overlay.setGeometry(self.pages.rect())
        overlay.raise_()
        return overlay


    def _ensure_page_fade_anim(self):
        overlay = self._ensure_page_transition_overlay()
        anim = getattr(self, "_page_fade_in_anim", None)
        if anim is None or anim.targetObject() is not overlay:
            anim = QPropertyAnimation(overlay, b"alpha", self)
            anim.setDuration(140)
            anim.setEasingCurve(QEasingCurve.InOutQuad)
            anim.finished.connect(self._on_page_fade_finished)
            self._page_fade_in_anim = anim
        return anim


    def _is_page_fade_running(self) -> bool:
        anim = getattr(self, "_page_fade_in_anim", None)
        return bool(anim and anim.state() == QPropertyAnimation.Running)


    def _dispose_unshown_page(self, widget):
        if widget is None:
            return
        if widget is getattr(self, "_home_page_cache", None):
            self._rescue_home_cache()
            return
        try:
            if qt_is_valid(widget):
                widget.hide()
                widget.deleteLater()
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)


    def _start_page_fade(self, end_alpha: int):
        overlay = self._ensure_page_transition_overlay()
        overlay.setGeometry(self.pages.rect())
        overlay.raise_()
        overlay.show()

        anim = self._ensure_page_fade_anim()
        if anim.state() == QPropertyAnimation.Running:
            anim.stop()
        anim.setStartValue(overlay.alpha)
        anim.setEndValue(end_alpha)
        anim.start()


    def _ensure_home_park(self) -> QWidget:
        """
        Home sayfası cache'ini tutmak için gizli park widget'ı.

        _clear() stack'teki her widget'a deleteLater() çağırır. Home page
        cache'ini korumak için navigasyon sırasında onu stack'ten çıkarıp
        bu gizli parent'a taşıyoruz; _clear() onu bulamaz ve silmez.
        """
        park = getattr(self, "_home_park_widget", None)
        if park is None or not qt_is_valid(park):
            park = QWidget()        # parent yok = bağımsız, gizli
            park.setFixedSize(0, 0)
            park.hide()
            self._home_park_widget = park
        return park

    def _rescue_home_cache(self):
        """Home page widget'ını stack'ten çekip park'a taşı (silinmemesi için)."""
        cached = getattr(self, "_home_page_cache", None)
        if cached is None:
            return
        try:
            if qt_is_valid(cached):
                cached.setParent(self._ensure_home_park())
                cached.hide()
        except Exception as _e:
            log.debug("Home cache rescue hatası: %s", _e)
            self._home_page_cache = None

    def _swap_page_widget(self, widget):
        # Home cache'ini _clear()'dan önce kurtarmak zorunlu;
        # aksi hâlde deleteLater() onu yok eder.
        self._rescue_home_cache()
        self._clear()
        self.pages.addWidget(widget)
        self.pages.setCurrentWidget(widget)


    def _show_page(self, widget):
        if self.pages.count() == 0:
            self._swap_page_widget(widget)
            self._hide_page_transition_overlay()
            return

        pending = getattr(self, "_page_pending_widget", None)
        if pending is not None and pending is not widget:
            self._dispose_unshown_page(pending)
        self._page_pending_widget = widget

        if self._is_page_fade_running():
            phase = getattr(self, "_page_transition_phase", None)
            if phase == "fade_in":
                self._page_transition_phase = "fade_out"
                self._start_page_fade(205)
            return

        self._page_transition_phase = "fade_out"
        self._start_page_fade(205)


    def _on_page_fade_finished(self):
        phase = getattr(self, "_page_transition_phase", None)
        overlay = self._ensure_page_transition_overlay()

        if phase == "fade_out":
            widget = getattr(self, "_page_pending_widget", None)
            self._page_pending_widget = None
            if widget is not None:
                self._swap_page_widget(widget)
            overlay.setGeometry(self.pages.rect())
            overlay.raise_()
            overlay.show()
            self._page_transition_phase = "fade_in"
            self._start_page_fade(0)
            return

        self._page_transition_phase = None
        overlay.alpha = 0
        overlay.hide()

        widget = getattr(self, "_page_pending_widget", None)
        if widget is not None:
            self._page_pending_widget = None
            self._show_page(widget)


    def _hide_page_transition_overlay(self):
        try:
            anim = getattr(self, "_page_fade_in_anim", None)
            if anim and anim.state() == QPropertyAnimation.Running:
                anim.stop()
            self._page_transition_phase = None
            if self._page_transition_overlay and qt_is_valid(self._page_transition_overlay):
                if hasattr(self._page_transition_overlay, "alpha"):
                    self._page_transition_overlay.alpha = 0
                self._page_transition_overlay.hide()
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)


    def _refresh_queue_page_state(self, force: bool = False):
        refs = getattr(self, "_queue_page_refs", None) or {}
        queue_list = refs.get("list_widget")
        title_label = refs.get("title_label")
        if queue_list is None or not qt_is_valid(queue_list):
            return

        fav_vids = {fav.get("videoId", "") for fav in self.favorites}
        current_vid = _queue_current_video_id(self)
        state = (
            len(self.queue),
            self.queue_index,
            current_vid,
            tuple(track.get("videoId", "") for track in self.queue),
            tuple(sorted(fav_vids)),
        )
        if not force and state == self._queue_refresh_state:
            return
        track_changed = current_vid != getattr(self, "_queue_last_current_vid", None)
        self._queue_refresh_state = state
        self._queue_last_current_vid = current_vid

        if title_label and qt_is_valid(title_label):
            title_label.setText(self._tr("queue.header_state", count=len(self.queue)))
        try:
            scroll_value = 0
            try:
                scroll_value = int(queue_list.verticalScrollBar().value())
            except Exception:
                scroll_value = 0
            if track_changed or queue_list.count() != len(self.queue) or not _refresh_queue_list_rows(self, queue_list):
                _rebuild_queue_list(self, queue_list)
            try:
                queue_list.viewport().update()
            except Exception:
                pass
            QTimer.singleShot(
                0,
                lambda value=scroll_value, widget=queue_list: (
                    widget.verticalScrollBar().setValue(
                        min(value, widget.verticalScrollBar().maximum())
                    )
                    if qt_is_valid(widget) else None
                ),
            )
        except Exception:
            self._queue_refresh_state = None
            self.page_queue(live=True, reveal_current=False)


    def _set_active_nav(self, key: str):
        """Sidebar'daki aktif nav butonunu güncelle."""
        nav = getattr(self, "_nav_buttons", {})
        for k, btn in nav.items():
            try:
                btn.set_active(k == key, force=True)
            except Exception as _e:
                log.debug("Sessiz hata: %s", _e)


    def _remember_current_page(self, target_payload=None):
        if self._nav_restoring:
            return
        payload = self._current_nav_payload
        if not payload:
            return
        if target_payload and payload == target_payload:
            return
        if self._nav_history and self._nav_history[-1] == payload:
            return
        self._nav_history.append(dict(payload))
        if len(self._nav_history) > 40:
            self._nav_history = self._nav_history[-40:]


    def _open_nav_payload(self, payload, from_history=False):
        if not payload:
            self.page_home()
            return

        prev_restoring = self._nav_restoring
        self._nav_restoring = from_history
        try:
            pt = payload.get("type")
            if pt == "home":
                self.page_home()
            elif pt == "search":
                self.page_search()
            elif pt == "artists":
                payload_data = payload.get("data")
                if payload_data:
                    self._artists_overview_payload = payload_data
                self.page_artists()
            elif pt == "category":
                self.page_category(
                    payload.get("title", "Kategori"),
                    payload.get("query", ""),
                    payload.get("ftype", "songs"),
                )
            elif pt == "favorites":
                self.page_favs()
            elif pt == "downloads":
                self.page_downloads()
            elif pt == "playlists":
                self.page_playlists()
            elif pt == "playlist":
                self.page_playlist(payload.get("name", ""))
            elif pt == "stats":
                self.page_stats()
            elif pt == "settings":
                self.page_settings(payload.get("tab", "general"))
            elif pt == "artist":
                self._set_active_nav("artists")
                self._show_page(build_artist_page(
                    self,
                    payload.get("tracks", []),
                    payload.get("name", ""),
                    payload.get("artist_meta", {}) or {},
                ))
                self._current_nav_payload = dict(payload)
            elif pt == "artist_album":
                self._set_active_nav("artists")
                self._show_page(build_artist_album_page(
                    self,
                    payload.get("artist_name", ""),
                    payload.get("album_name", ""),
                    payload.get("tracks", []),
                    payload.get("album_meta", {}) or {},
                ))
                self._current_nav_payload = dict(payload)
            else:
                self.page_home()
        finally:
            self._nav_restoring = prev_restoring


    def _go_back(self):
        while self._nav_history:
            payload = self._nav_history.pop()
            if payload and payload != self._current_nav_payload:
                self._open_nav_payload(payload, from_history=True)
                return
        self.page_home()


    def _leave_queue_view(self):
        if getattr(self, "in_queue_view", False):
            try:
                self._set_queue_view_state(False)
            except Exception as _e:
                log.debug("Sessiz hata: %s", _e)


    def _invalidate_home_cache(self):
        """
        Home page cache'ini geçersiz kıl.
        Feed yenileme, tema değişimi veya geçmiş/favori güncellemelerinde
        çağrılmalı; bir sonraki page_home() çağrısı sayfayı yeniden oluşturur.
        """
        self._home_page_cache = None

    def page_home(self):
        self._leave_queue_view()
        target_payload = {"type": "home"}
        self._remember_current_page(target_payload)
        self._current_nav_payload = target_payload
        self._set_active_nav("home")
        self.current_page = "home"

        # PERFORMANS: Home sayfası cache'i.
        # İlk açılışta build_home_page() çağrılır (ağır işlem).
        # Sonraki gezinmelerde aynı widget yeniden kullanılır; rebuild yok.
        # Cache sadece _invalidate_home_cache() veya _refresh_home_feed()
        # çağrıldığında sıfırlanır.
        cached = getattr(self, "_home_page_cache", None)
        if cached is not None and qt_is_valid(cached):
            self._show_page(cached)
        else:
            pg = build_home_page(self)
            self._home_page_cache = pg
            self._show_page(pg)


    def page_search(self):
        self._leave_queue_view()
        target_payload = {"type": "search"}
        self._remember_current_page(target_payload)
        self._current_nav_payload = target_payload
        self._set_active_nav("search")
        if not str(self._search_cache.get("q") or "").strip():
            self._search_cache["q"] = ""
            self._search_cache["results"] = []
        self._show_page(build_search_page(self))


    def page_artists(self):
        self._leave_queue_view()
        payload = getattr(self, "_artists_overview_payload", None)
        target_payload = {"type": "artists", "data": payload or {}}
        self._remember_current_page(target_payload)
        self._current_nav_payload = target_payload
        self._set_active_nav("artists")

        loading = not bool(payload and payload.get("featured"))
        self._show_page(build_artists_page(self, payload=payload, loading=loading))

        last_update = float(getattr(self, "_artists_overview_updated_at", 0) or 0)
        if loading or (time.time() - last_update) > 1800:
            self._net_pool.submit(self._fetch_artists_overview)


    def page_category(self, title, query, ftype="songs"):
        self._leave_queue_view()
        target_payload = {
            "type": "category",
            "title": title,
            "query": query,
            "ftype": ftype,
        }
        self._remember_current_page(target_payload)
        self._current_nav_payload = target_payload
        self._set_active_nav("search")
        self._show_page(build_category_page(self, title, query, ftype))


    def page_favs(self):
        self._leave_queue_view()
        target_payload = {"type": "favorites"}
        self._remember_current_page(target_payload)
        self._current_nav_payload = target_payload
        self._set_active_nav("favs")
        self._show_page(build_favs_page(self))


    def page_downloads(self):
        self._leave_queue_view()
        target_payload = {"type": "downloads"}
        self._remember_current_page(target_payload)
        self._current_nav_payload = target_payload
        self._set_active_nav("downloads")
        self._show_page(build_downloads_page(self))


    def page_playlists(self):
        self._leave_queue_view()
        target_payload = {"type": "playlists"}
        self._remember_current_page(target_payload)
        self._current_nav_payload = target_payload
        self._set_active_nav("playlists")
        self._show_page(build_playlists_overview_page(self))


    def page_playlist(self, name: str):
        self._leave_queue_view()
        target_payload = {"type": "playlist", "name": name}
        self._remember_current_page(target_payload)
        self._current_nav_payload = target_payload
        self._set_active_nav("playlists")
        self._show_page(build_playlist_page(self, name))


    def page_queue(self, live=False, reveal_current=None):
        if reveal_current is None:
            reveal_current = not bool(live)
        prev_scroll = None
        if live:
            try:
                refs = getattr(self, "_queue_page_refs", None) or {}
                queue_list = refs.get("list_widget")
                if queue_list is not None and qt_is_valid(queue_list):
                    prev_scroll = queue_list.verticalScrollBar().value()
            except Exception as _e:
                log.debug("Sessiz hata: %s", _e)
        self._set_queue_view_state(True)
        self.current_page = "queue"
        widget = build_queue_page(self)
        if live and self.pages.count():
            self._swap_page_widget(widget)
        else:
            self._show_page(widget)
        # Sayfa yenilendikten sonra aktif şarkıya scroll yap
        if live and prev_scroll is not None:
            QTimer.singleShot(0, lambda value=prev_scroll: self._restore_queue_scroll(value))
        elif reveal_current and self.queue_index >= 0:
            QTimer.singleShot(50, self._scroll_queue_to_current)


    def _scroll_queue_to_current(self):
        """Queue sayfasında çalan şarkıyı görünür hale getir."""
        try:
            refs = getattr(self, "_queue_page_refs", None) or {}
            queue_list = refs.get("list_widget")
            if queue_list is None or not qt_is_valid(queue_list):
                return
            idx = self.queue_index
            if 0 <= idx < queue_list.count():
                item = queue_list.item(idx)
                if item:
                    queue_list.scrollToItem(item)
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)


    def _restore_queue_scroll(self, value: int):
        try:
            refs = getattr(self, "_queue_page_refs", None) or {}
            queue_list = refs.get("list_widget")
            if queue_list is None or not qt_is_valid(queue_list):
                return
            bar = queue_list.verticalScrollBar()
            bar.setValue(min(max(0, int(value)), bar.maximum()))
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)


    def page_stats(self):
        self._leave_queue_view()
        target_payload = {"type": "stats"}
        self._remember_current_page(target_payload)
        self._current_nav_payload = target_payload
        self._set_active_nav("stats")
        self._show_page(build_stats_page(self))


    def page_settings(self, initial_tab: str = "general"):
        self._leave_queue_view()
        tab = str(initial_tab or "general").strip().lower()
        target_payload = {"type": "settings", "tab": tab}
        self._remember_current_page(target_payload)
        self._current_nav_payload = target_payload
        self._set_active_nav("settings")
        self._show_page(build_settings_page(self, tab))


    def _on_artist_songs(self, tracks, name, artist_meta=None):
        self._leave_queue_view()
        target_payload = {
            "type": "artist",
            "name": name,
            "tracks": tracks,
            "artist_meta": artist_meta or {},
        }
        self._remember_current_page(target_payload)
        self._current_nav_payload = target_payload
        self._set_active_nav("artists")
        self._show_page(build_artist_page(self, tracks, name, artist_meta or {}))


    def _on_artist_album(self, tracks, artist_name, album_name, album_meta=None):
        self._leave_queue_view()
        target_payload = {
            "type": "artist_album",
            "artist_name": artist_name,
            "album_name": album_name,
            "tracks": tracks,
            "album_meta": album_meta or {},
        }
        self._remember_current_page(target_payload)
        self._current_nav_payload = target_payload
        self._set_active_nav("artists")
        self._show_page(build_artist_album_page(
            self,
            artist_name,
            album_name,
            tracks,
            album_meta or {},
        ))


    def _fetch_artists_overview(self):
        payload = self._build_artists_overview_payload()
        self.sig.artists_overview_done.emit(payload)


    def _on_artists_overview(self, payload):
        data = payload or {}
        self._artists_overview_payload = data
        self._artists_overview_updated_at = time.time()
        if self.current_page == "artists":
            target_payload = {"type": "artists", "data": data}
            self._current_nav_payload = target_payload
            self._show_page(build_artists_page(self, payload=data, loading=False))


    def _refresh_home_feed(self):
        # Cache'i sıfırla; page_home() yeni widget oluşturur
        self._invalidate_home_cache()
        self._home_force_curated_cover_refresh = True
        self._home_pool_session = None
        self._home_visit_seed   = int(time.time() * 1000) % 100000
        self.page_home()

    # ══════════════════════════════════════════════════════════════════════════
    # YARDIMCI FONKSİYONLAR
    # ══════════════════════════════════════════════════════════════════════════
