"""Mixin for Discord functionality."""
import logging
import time

try:
    from pypresence import Presence
    DISCORD_AVAILABLE = True
except ImportError:
    DISCORD_AVAILABLE = False

log = logging.getLogger("iqtMusic")

# Discord IPC rate limit: saniyede en fazla 1 güncelleme, her 15 saniyede bir.
# https://discord.com/developers/docs/topics/rate-limits
_DISCORD_RATE_LIMIT = 15.0


class DiscordMixin:

    def _discord_connect(self):
        if not getattr(self, "_discord_presence_enabled", True):
            return
        try:
            if getattr(self, "_discord_rpc", None):
                try:
                    self._discord_rpc.close()
                except Exception:
                    pass
            self._discord_rpc = Presence(self._discord_id)
            self._discord_rpc.connect()
            self._discord_connected = True
            self._discord_last_update: float = 0.0
            self._discord_pending_track = None
            log.info("Discord RPC baglandi.")
            # Bağlanır bağlanmaz mevcut şarkıyı gönder
            try:
                if self.queue and self.queue_index != -1:
                    self._discord_do_update(self.queue[self.queue_index])
            except Exception:
                pass
        except Exception as e:
            self._discord_connected = False
            log.debug("Discord RPC baglanamadi: %s", e)

    def _discord_reconnect(self):
        """Arka planda yeniden bağlanmayı dene (bağlantı koptuğunda çağrılır)."""
        if not DISCORD_AVAILABLE or not getattr(self, "_discord_presence_enabled", True):
            return
        self._discord_connected = False
        self._net_pool.submit(self._discord_connect)

    def _discord_update(self, track):
        """
        Şarkı değişince çağrılır. Hemen göndermeyi dener; rate-limit nedeniyle
        başarısız olursa pending'e alır — loop iki saniyede bir tekrar dener.
        """
        if not (
            DISCORD_AVAILABLE
            and getattr(self, "_discord_presence_enabled", True)
            and getattr(self, "_discord_connected", False)
        ):
            return
        # Her track değişiminde pending güncelle (başarısız olursa loop yakalar)
        self._discord_pending_track = track
        self._discord_do_update(track)

    def _discord_do_update(self, track):
        """Fiilen Discord IPC'ye yazma işini yapan iç metod."""
        if not (
            DISCORD_AVAILABLE
            and getattr(self, "_discord_presence_enabled", True)
            and getattr(self, "_discord_connected", False)
        ):
            return
        try:
            from pypresence.types import ActivityType, StatusDisplayType

            vid = track.get("videoId", "") or ""
            title = track.get("title", "?")
            artist = self._artist_str(track) or "?"
            now_ts = int(time.time())

            cover_url = None
            try:
                cover_url = self._thumb(track, big=True)
            except Exception:
                cover_url = None

            try:
                is_playing = bool(self.player.is_playing())
            except Exception:
                is_playing = True
            if not is_playing:
                try:
                    self._discord_rpc.clear()
                except Exception as _e:
                    log.debug("Sessiz hata: %s", _e)
                return
            small_image_key = "play"
            small_text = "Caliyor"

            buttons = []
            if vid:
                buttons.append({"label": "YouTube", "url": f"https://www.youtube.com/watch?v={vid}"})

            collab = getattr(self, "_collab_session", None)
            is_collab = (
                collab is not None
                and collab.is_connected
                and collab.peer_connected
            )
            # Collab oturumu aktifse, host ise ve henüz kimse bağlı değilse butonu göster.
            # Birisi zaten odadaysa kodu gizle (gereksiz maruziyeti önler).
            if (
                collab is not None
                and collab.is_host
                and collab.is_connected
                and collab.room_code
                and not collab.peer_connected
            ):
                buttons.append({
                    "label": "Beraber Dinle",
                    "url": f"iqtmusic://join/{collab.room_code}",
                })

            display_mode = str(getattr(self, "_discord_display_mode", "song") or "song").strip().lower()
            if display_mode == "artist":
                details = artist
                state = title
            else:
                details = title
                state = artist

            large_img = cover_url or "iqticon"
            large_txt = "Beraber Dinliyor" if is_collab else "IQTMusic"

            update_kwargs = {
                "activity_type": ActivityType.LISTENING,
                "details": details,
                "state": state,
                "large_image": large_img,
                "large_text": large_txt,
                "small_image": small_image_key,
                "small_text": small_text,
                "buttons": buttons,
                "status_display_type": StatusDisplayType.DETAILS,
            }

            try:
                length_ms = 0
                current_ms = 0
                try:
                    dur_sec = track.get("duration_seconds")
                    if dur_sec:
                        length_ms = int(float(dur_sec) * 1000)
                except Exception:
                    length_ms = 0
                if length_ms <= 0:
                    try:
                        length_ms = int(self.player.get_length() or 0)
                    except Exception:
                        length_ms = 0
                if length_ms <= 0:
                    try:
                        length_ms = int(self.total_dur or 0)
                    except Exception:
                        length_ms = 0

                try:
                    current_ms = int(self.player.get_time() or 0)
                except Exception:
                    current_ms = 0

                if length_ms > 0:
                    start_ts = now_ts - (current_ms // 1000)
                    end_ts = start_ts + (length_ms // 1000)
                    update_kwargs["start"] = start_ts
                    update_kwargs["end"] = end_ts
            except Exception as _e:
                log.debug("Sessiz hata: %s", _e)

            self._discord_rpc.update(**update_kwargs)
            self._discord_last_update = time.time()
            self._discord_pending_track = None
        except Exception as _e:
            err = str(_e).lower()
            # Bağlantı tamamen kopmuşsa (socket hatası) yeniden bağlan
            if "send" in err or "pipe" in err or "closed" in err or "connect" in err:
                log.debug("Discord bağlantısı koptu, yeniden bağlanılıyor: %s", _e)
                self._discord_reconnect()

    def _discord_loop(self):
        """Discord Presence'i periyodik olarak gunceller.

        - Bağlı değilse her 30 saniyede bir yeniden bağlanmayı dener
          (program açıkken Discord açılma senaryosu).
        - Pending track varsa önce onu gönderir (şarkı değişimi gecikmeli).
        - Normal periyodik güncelleme (elapsed time senkronizasyonu).
        """
        if not DISCORD_AVAILABLE:
            return
        if not getattr(self, "_discord_presence_enabled", True):
            if getattr(self, "_discord_connected", False):
                try:
                    if getattr(self, "_discord_rpc", None):
                        self._discord_rpc.clear()
                        self._discord_rpc.close()
                except Exception as _e:
                    log.debug("Sessiz hata: %s", _e)
                self._discord_connected = False
            return

        if not getattr(self, "_discord_connected", False):
            # Her 30 saniyede bir yeniden bağlanmayı dene
            now = time.time()
            last_try = getattr(self, "_discord_last_connect_try", 0.0)
            if now - last_try >= 30.0:
                self._discord_last_connect_try = now
                self._net_pool.submit(self._discord_connect)
            return

        # Pending track varsa onu gönder (şarkı değişimi yakalanmış olur)
        pending = getattr(self, "_discord_pending_track", None)
        if pending is not None:
            self._discord_do_update(pending)
            return

        # Normal periyodik güncelleme (elapsed time senkronizasyonu)
        if not self.queue or self.queue_index == -1:
            return
        self._discord_do_update(self.queue[self.queue_index])

    def _set_discord_presence_enabled(self, enabled: bool):
        self._discord_presence_enabled = bool(enabled)
        self._save_settings()
        if not self._discord_presence_enabled:
            self._discord_pending_track = None
            try:
                if getattr(self, "_discord_rpc", None):
                    self._discord_rpc.clear()
                    self._discord_rpc.close()
            except Exception as _e:
                log.debug("Sessiz hata: %s", _e)
            self._discord_connected = False
            return
        if DISCORD_AVAILABLE:
            self._net_pool.submit(self._discord_connect)

    def _set_discord_display_mode(self, mode: str):
        clean = str(mode or "song").strip().lower()
        if clean not in {"song", "artist"}:
            clean = "song"
        self._discord_display_mode = clean
        self._save_settings()
        if self.queue and self.queue_index != -1:
            self._discord_update(self.queue[self.queue_index])
