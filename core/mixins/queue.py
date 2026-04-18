"""Mixin for Queue functionality."""
import logging

log = logging.getLogger("iqtMusic")

from core.constants import TEXT_MUTED
from core.theme import get_accent
from utils.helpers import create_icon


class QueueMixin:

    def _set_queue_view_state(self, active: bool):
        self.in_queue_view = bool(active)
        try:
            if hasattr(self, "btn_queue") and self.btn_queue:
                self.btn_queue.setIcon(create_icon("queue", get_accent() if active else TEXT_MUTED, 18))
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)


    def _manual_queue_insert_index(self) -> int:
        if not self.queue:
            return 0
        start = len(self.queue)
        if 0 <= self.queue_index < len(self.queue):
            start = self.queue_index + 1
        for idx in range(start, len(self.queue)):
            vid = self.queue[idx].get("videoId", "")
            if vid and vid in self._radio_queue_vids:
                return idx
        return len(self.queue)


    def _add_to_queue(self, track):
        # Kapak fotoğrafı eksikse fallback URL'leri ekle
        try:
            _ = self._thumb(track)
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
        vid = track.get("videoId", "")
        if vid:
            self._radio_queue_vids.discard(vid)
        insert_at = self._manual_queue_insert_index()
        self.queue.insert(insert_at, track)
        self.sig.notify.emit("≣ Sıraya eklendi")
        if getattr(self, "current_page", "") == "queue":
            self.page_queue(live=True)


    def _add_next(self, track):
        if not self.queue:
            self.force_play(track)
        else:
            # Eksik küçük resim bilgilerini doldur
            try:
                _ = self._thumb(track)
            except Exception as _e:
                log.debug("Sessiz hata: %s", _e)
            vid = track.get("videoId", "")
            if vid:
                self._radio_queue_vids.discard(vid)
            self.queue.insert(self.queue_index + 1, track)
            self.sig.notify.emit("➕ Sıradaki olarak ayarlandı")
            if getattr(self, "current_page", "") == "queue":
                self.page_queue(live=True)


    def _remove_from_queue_at(self, idx: int):
        if not (0 <= idx < len(self.queue)):
            return

        removed = self.queue.pop(idx)
        removed_vid = removed.get("videoId", "")
        if removed_vid and not any(
            t.get("videoId", "") == removed_vid for t in self.queue
        ):
            self._radio_queue_vids.discard(removed_vid)

        removed_current = idx == self.queue_index
        if idx < self.queue_index:
            self.queue_index -= 1

        if not self.queue:
            self.queue_index = -1
            self.target_vid = ""
            try:
                self.player.stop()
            except Exception as _e:
                log.debug("Sessiz hata: %s", _e)
            self._set_main_play_icon(False)
        elif removed_current:
            if idx >= len(self.queue):
                self.queue_index = len(self.queue) - 1
            else:
                self.queue_index = idx
            self._play(self.queue[self.queue_index], force_radio=False)

        self._queue_refresh_state = None
        self.sig.notify.emit("✕ Sıradan çıkarıldı")
        if getattr(self, "current_page", "") == "queue":
            self.page_queue(live=True)
        else:
            try:
                self.sig.player_ui_update.emit()
            except Exception as _e:
                log.debug("Sessiz hata: %s", _e)


    def _q_move(self, idx: int, delta: int):
        new = idx + delta
        if 0 <= new < len(self.queue):
            self.queue[idx], self.queue[new] = self.queue[new], self.queue[idx]
            if   self.queue_index == idx: self.queue_index = new
            elif self.queue_index == new: self.queue_index = idx
            self.page_queue(live=True)


    def toggle_queue_view(self):
        if self.in_queue_view:
            self._set_queue_view_state(False)
            self._restore_prev_page()
        else:
            self._save_prev_page()
            self._set_queue_view_state(True)
            self.page_queue()


    def _save_prev_page(self):
        # _current_nav_payload tüm sayfa türlerini (category, artist,
        # artist_album, artists, search, …) eksiksiz taşır.
        # Eski string-tabanlı yaklaşım cat_, artist vb. için home'a düşüyordu.
        self._queue_return_payload = (
            dict(self._current_nav_payload)
            if self._current_nav_payload else None
        )


    def _restore_prev_page(self):
        payload = getattr(self, "_queue_return_payload", None)
        if payload:
            # from_history=True → _nav_history'e tekrar eklenmez,
            # _nav_restoring aktifken _remember_current_page çalışmaz.
            self._open_nav_payload(payload, from_history=True)
        else:
            self.page_home()

    # ══════════════════════════════════════════════════════════════════════════
    # PLAYLİST
    # ══════════════════════════════════════════════════════════════════════════
