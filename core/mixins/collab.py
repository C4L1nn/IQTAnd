"""Mixin for Collab (Beraber Dinleme) functionality."""
from __future__ import annotations

import logging
import time

from PySide6.QtCore import QTimer

log = logging.getLogger("iqtMusic.collab")

# ──────────────────────────────────────────────────────────────────────────────
# Senkron mantığı hakkında notlar:
#
#  • time.time() tabanlı "latency compensation" KULLANILMAZ.
#    İki bilgisayarın saatleri birbirinden saniyeler farklı olabilir;
#    bu fark compensation hesabına eklenince tam tersine sapma yaratır.
#
#  • Bunun yerine "raw pozisyon" yaklaşımı kullanılır:
#    - Host her 2 saniyede seek event'i yayınlar (mevcut pozisyon)
#    - Guest, kendi pozisyonuyla karşılaştırır; 1200ms+ farklıysa seek eder
#    - İlk yükleme gecikmesi için 20 saniyelik hızlı resync timer çalışır
#
#  • QTimer'lar YALNIZCA main thread'den oluşturulup başlatılır.
#    MQTT callback'lerinden signal emit edilir; slotlar main thread'de çalışır.
# ──────────────────────────────────────────────────────────────────────────────

# Misafir hangi farkta seek yapılacağını anlar (ms)
_SEEK_THRESHOLD_MS = 1200
_SEEK_THRESHOLD_STARTUP_MS = 2400
_SOFT_SYNC_IGNORE_MS = 160
_SOFT_SYNC_RATE_START_MS = 260
_SOFT_SYNC_RATE_MAX = 0.025
_SOFT_SYNC_HOLD_MS = 1800
_EMERGENCY_SEEK_THRESHOLD_MS = 2600
_EMERGENCY_SEEK_COOLDOWN_MS = 12000
_ACTIVE_SYNC_WINDOW_MS = 14000
# İlk yükleme resync timer aralığı (ms) ve toplam tick sayısı (~20 saniye)
_FAST_RESYNC_INTERVAL_MS = 800
_FAST_RESYNC_TICKS = 25
# Host'un periyodik seek timer aralığı (ms)
_PERIODIC_SYNC_INTERVAL_MS = 2000
_DRIFT_SYNC_INTERVAL_MS = 900
_STATE_BROADCAST_BATCH_MS = 250
_STATE_BROADCAST_DEBOUNCE_MS = 2000


class CollabMixin:
    # ──────────── oturum yönetimi ────────────

    def collab_create(self) -> str:
        from core.collab import CollabSession, fmt_room_code

        existing = getattr(self, "_collab_session", None)
        if existing is not None and existing.is_host and existing.room_code:
            log.info("Mevcut host oturumu kullanılıyor: %s", fmt_room_code(existing.room_code))
            self._collab_update_ui()
            self._collab_refresh_dialog()
            return existing.room_code

        self._collab_reset_state_broadcast_gate()
        self._collab_session = CollabSession(
            on_sync=self._collab_raw_sync,
            on_control=self._collab_raw_control,
            on_status=self._collab_raw_status,
            translator=self._tr,
        )
        code = self._collab_session.create()
        log.info("Collab oturum oluşturuldu: %s", fmt_room_code(code))
        self._collab_update_ui()
        self._collab_refresh_dialog()
        return code

    def collab_join(self, room_code: str, from_discord: bool = False) -> bool:
        from core.collab import CollabSession, parse_room_code

        normalized = parse_room_code(room_code)
        existing = getattr(self, "_collab_session", None)
        if (
            existing is not None
            and not existing.is_host
            and existing.room_code == normalized
            and existing.state in {existing.ST_CONNECTED, existing.ST_CONNECTING}
        ):
            self._collab_update_ui()
            self._collab_refresh_dialog()
            return True

        self._collab_reset_state_broadcast_gate()
        self._collab_discord_join_pending = from_discord  # Onay bekleyen Discord join
        self._collab_session = CollabSession(
            on_sync=self._collab_raw_sync,
            on_control=self._collab_raw_control,
            on_status=self._collab_raw_status,
            translator=self._tr,
        )
        ok = self._collab_session.join(normalized, from_discord=from_discord)
        self._collab_update_ui()
        self._collab_refresh_dialog()
        return ok

    def collab_leave(self):
        s = getattr(self, "_collab_session", None)
        if s is not None:
            s.leave()
        self._collab_session = None
        self._collab_reset_state_broadcast_gate()
        self._stop_collab_resync_timer()
        self._stop_collab_fast_resync_timer()
        self._stop_collab_drift_timer()
        self._collab_reset_soft_rate()
        # Guest olarak ayrılınca radyo kilidini kaldır
        self._queue_artist_lock = False
        self._collab_update_ui()
        self._collab_refresh_dialog()

    @property
    def _collab(self):
        return getattr(self, "_collab_session", None)

    def _collab_is_guest_active(self) -> bool:
        s = self._collab
        if s is None:
            return False
        try:
            return (not s.is_host) and s.state in {s.ST_CONNECTED, s.ST_CONNECTING}
        except Exception:
            return False

    def _collab_local_now_ms(self) -> int:
        return int(time.time() * 1000)

    def _collab_host_now_ms(self) -> int:
        return int(self._collab_local_now_ms() + float(getattr(self, "_collab_clock_offset_ms", 0.0) or 0.0))

    def _collab_reset_soft_rate(self):
        current = getattr(self, "_collab_soft_rate_applied", None)
        base_rate = float(getattr(self, "_playback_rate", 1.0) or 1.0)
        if current is None or abs(float(current) - base_rate) <= 0.001:
            self._collab_soft_rate_applied = base_rate
            self._collab_soft_rate_hold_until_ms = 0
            return
        try:
            self.player.set_rate(base_rate)
        except Exception as e:
            log.debug("collab rate sifirlama hatasi: %s", e)
            return
        self._collab_soft_rate_applied = base_rate
        self._collab_soft_rate_hold_until_ms = 0

    def _collab_apply_soft_sync(self, target_pos_ms: int, *, allow_seek: bool = True) -> int:
        try:
            current = max(0, int(self.player.get_time()))
        except Exception:
            return 0
        now_ms = self._collab_local_now_ms()
        diff = current - max(0, int(target_pos_ms))
        abs_diff = abs(diff)
        hold_until_ms = int(getattr(self, "_collab_soft_rate_hold_until_ms", 0) or 0)
        last_change_ms = int(getattr(self, "_collab_last_soft_rate_change_ms", 0) or 0)
        if abs_diff <= _SOFT_SYNC_IGNORE_MS:
            if hold_until_ms <= now_ms:
                self._collab_reset_soft_rate()
            return diff

        seek_threshold = (
            _SEEK_THRESHOLD_STARTUP_MS
            if current < 30000 or target_pos_ms < 30000
            else _SEEK_THRESHOLD_MS
        )
        emergency_seek_ms = seek_threshold if allow_seek else _EMERGENCY_SEEK_THRESHOLD_MS
        if abs_diff >= emergency_seek_ms:
            self._collab_reset_soft_rate()
            try:
                self.player.set_time(max(0, int(target_pos_ms)))
            except Exception as e:
                log.debug("collab soft seek hatasi: %s", e)
            return diff

        if abs_diff < _SOFT_SYNC_RATE_START_MS:
            if hold_until_ms <= now_ms:
                self._collab_reset_soft_rate()
            return diff

        base_rate = float(getattr(self, "_playback_rate", 1.0) or 1.0)
        ratio = min(1.0, abs_diff / max(1.0, float(seek_threshold)))
        delta = max(0.008, min(_SOFT_SYNC_RATE_MAX, ratio * _SOFT_SYNC_RATE_MAX))
        nudged_rate = base_rate * (1.0 - delta if diff > 0 else 1.0 + delta)
        nudged_rate = max(0.5, min(2.0, nudged_rate))
        last_rate = getattr(self, "_collab_soft_rate_applied", None)
        should_update = (
            last_rate is None
            or abs(float(last_rate) - nudged_rate) > 0.008
            or now_ms - last_change_ms >= 900
        )
        if should_update:
            try:
                self.player.set_rate(nudged_rate)
                self._collab_soft_rate_applied = nudged_rate
                self._collab_soft_rate_hold_until_ms = now_ms + _SOFT_SYNC_HOLD_MS
                self._collab_last_soft_rate_change_ms = now_ms
            except Exception as e:
                log.debug("collab soft rate hatasi: %s", e)
        return diff

    def _collab_extract_transport(self, event: dict, default_state: str = "paused") -> dict:
        state = str(event.get("state") or default_state or "paused").strip().lower()
        if state not in {"playing", "paused", "loading"}:
            state = default_state or "paused"
        anchor_pos_ms = max(0, int(event.get("anchor_pos_ms", event.get("pos", 0)) or 0))
        anchor_host_ms = int(event.get("anchor_host_ms", 0) or 0)
        if anchor_host_ms <= 0:
            anchor_host_ms = self._collab_host_now_ms()
        return {
            "state": state,
            "anchor_pos_ms": anchor_pos_ms,
            "anchor_host_ms": anchor_host_ms,
            "session_epoch": int(event.get("session_epoch", 0) or 0),
            "track_version": int(event.get("track_version", 0) or 0),
        }

    def _collab_store_transport(self, event: dict, default_state: str = "paused") -> dict:
        transport = self._collab_extract_transport(event, default_state=default_state)
        self._collab_anchor_pos_ms = transport["anchor_pos_ms"]
        self._collab_anchor_host_ms = transport["anchor_host_ms"]
        self._collab_transport_state = transport["state"]
        self._collab_host_playing = transport["state"] == "playing"
        if transport["session_epoch"] > 0:
            self._collab_session_epoch = transport["session_epoch"]
        if transport["track_version"] >= 0:
            self._collab_track_version = transport["track_version"]
        self._collab_update_drift_timer()
        return transport

    def _collab_target_position_ms(self, transport: dict | None = None) -> int:
        info = transport or {
            "state": getattr(self, "_collab_transport_state", "paused"),
            "anchor_pos_ms": int(getattr(self, "_collab_anchor_pos_ms", 0) or 0),
            "anchor_host_ms": int(getattr(self, "_collab_anchor_host_ms", 0) or 0),
        }
        anchor_pos_ms = max(0, int(info.get("anchor_pos_ms", 0) or 0))
        anchor_host_ms = max(0, int(info.get("anchor_host_ms", 0) or 0))
        if str(info.get("state") or "paused") != "playing" or anchor_host_ms <= 0:
            return anchor_pos_ms
        return max(0, anchor_pos_ms + max(0, self._collab_host_now_ms() - anchor_host_ms))

    def _collab_mark_active_sync_window(self, duration_ms: int = _ACTIVE_SYNC_WINDOW_MS):
        self._collab_active_sync_until_ms = self._collab_local_now_ms() + max(0, int(duration_ms))
        self._collab_update_drift_timer()

    def _collab_in_active_sync_window(self) -> bool:
        return int(getattr(self, "_collab_active_sync_until_ms", 0) or 0) > self._collab_local_now_ms()

    def _collab_host_bump_epoch(self, track: dict | None = None):
        vid = str((track or {}).get("videoId", "") or "")
        if vid and vid != getattr(self, "_collab_epoch_track_vid", ""):
            self._collab_session_epoch = int(getattr(self, "_collab_session_epoch", 0) or 0) + 1
            self._collab_epoch_track_vid = vid
        self._collab_track_version = 0

    def _collab_host_bump_version(self) -> int:
        self._collab_track_version = int(getattr(self, "_collab_track_version", 0) or 0) + 1
        return self._collab_track_version

    def _collab_host_transport_kwargs(self, position_ms: int, state: str, *, bump_version: bool = True) -> dict:
        anchor_host_ms = self._collab_local_now_ms()
        self._collab_anchor_pos_ms = max(0, int(position_ms))
        self._collab_anchor_host_ms = anchor_host_ms
        self._collab_transport_state = state
        self._collab_host_playing = state == "playing"
        version = self._collab_host_bump_version() if bump_version else int(getattr(self, "_collab_track_version", 0) or 0)
        return {
            "anchor_host_ms": anchor_host_ms,
            "session_epoch": int(getattr(self, "_collab_session_epoch", 0) or 0),
            "track_version": version,
            "state": state,
        }

    def _collab_queue_clock_sync(self):
        if not self._collab_is_guest_active():
            return
        now_ms = self._collab_local_now_ms()
        last_req = int(getattr(self, "_collab_last_clock_sync_ms", 0) or 0)
        if now_ms - last_req < 5000:
            return
        self._collab_last_clock_sync_ms = now_ms
        for delay in (0, 220, 700, 1600):
            QTimer.singleShot(delay, self._collab_send_clock_ping)

    def _collab_send_clock_ping(self):
        if not self._collab_is_guest_active():
            return
        session = self._collab
        if session is None or not session.is_connected:
            return
        self._collab_clock_ping_seq = int(getattr(self, "_collab_clock_ping_seq", 0) or 0) + 1
        now_ms = self._collab_local_now_ms()
        ping_id = f"{now_ms}-{self._collab_clock_ping_seq}"
        self._collab_clock_pings[ping_id] = now_ms
        try:
            session.send_clock_ping(ping_id, now_ms)
        except Exception as e:
            log.debug("collab clock ping hatasi: %s", e)

    def _collab_handle_clock_pong(self, event: dict):
        ping_id = str(event.get("ping_id", "") or "")
        if not ping_id:
            return
        sent_ms = self._collab_clock_pings.pop(ping_id, None)
        if sent_ms is None:
            return
        recv_ms = self._collab_local_now_ms()
        host_recv_ms = int(event.get("host_recv_ms", 0) or 0)
        host_send_ms = int(event.get("host_send_ms", 0) or 0)
        if host_recv_ms <= 0 or host_send_ms <= 0:
            return
        host_processing_ms = max(0, host_send_ms - host_recv_ms)
        rtt_ms = max(0, recv_ms - int(sent_ms) - host_processing_ms)
        offset_ms = ((host_recv_ms - int(sent_ms)) + (host_send_ms - recv_ms)) / 2.0
        current_offset = float(getattr(self, "_collab_clock_offset_ms", 0.0) or 0.0)
        best_rtt = getattr(self, "_collab_clock_best_rtt_ms", None)
        if best_rtt is None or rtt_ms <= best_rtt + 25:
            self._collab_clock_offset_ms = offset_ms if abs(current_offset) <= 0.01 else ((current_offset * 0.35) + (offset_ms * 0.65))
            self._collab_clock_rtt_ms = rtt_ms
            if best_rtt is None or rtt_ms < best_rtt:
                self._collab_clock_best_rtt_ms = rtt_ms
        log.debug("collab clock sync: offset=%.1fms rtt=%dms", float(getattr(self, "_collab_clock_offset_ms", 0.0) or 0.0), int(rtt_ms))

    def _collab_emit_host_loaded_play(self, request_id: int):
        if request_id != int(getattr(self, "_collab_pending_host_broadcast_rid", 0) or 0):
            return
        session = self._collab
        if session is None or not session.is_host or not session.is_connected:
            self._collab_pending_host_broadcast_rid = 0
            return
        try:
            if not self.player.is_playing():
                QTimer.singleShot(260, lambda rid=request_id: self._collab_emit_host_loaded_play(rid))
                return
            pos_ms = max(0, int(self.player.get_time()))
        except Exception:
            QTimer.singleShot(260, lambda rid=request_id: self._collab_emit_host_loaded_play(rid))
            return
        self._collab_pending_host_broadcast_rid = 0
        self._collab_emit_play(pos_override=pos_ms)

    def _collab_raw_control(self, event: dict):
        try:
            self.sig.collab_control.emit(event)
        except Exception as e:
            log.debug("collab_raw_control emit hatasi: %s", e)

    def _collab_on_control(self, event: dict):
        if not event or not isinstance(event, dict):
            return
        event_type = str(event.get("t", "") or "")
        session = self._collab
        if session is None:
            return
        # join_request: host reconnect sırasında da gelmeli — is_connected kontrolü atlanır.
        if event_type == "join_request":
            if not session.is_host:
                return
            log.info("collab: Discord join isteği alındı")
            try:
                self.sig.collab_join_request.emit()
            except Exception as e:
                log.debug("collab_join_request emit hatası: %s", e)
            return
        if not session.is_connected:
            return
        if event_type == "clock_ping":
            if not session.is_host:
                return
            try:
                session.send_clock_pong(
                    str(event.get("ping_id", "") or ""),
                    int(event.get("client_time_ms", 0) or 0),
                    self._collab_local_now_ms(),
                )
            except Exception as e:
                log.debug("collab clock pong hatasi: %s", e)
        elif event_type == "clock_pong":
            if session.is_host:
                return
            self._collab_handle_clock_pong(event)
        elif event_type == "request_state":
            # Guest bağlandı ve mevcut state'i talep ediyor — presence tespitini bekleme.
            if not session.is_host:
                return
            log.debug("collab: guest state talebi alindi, mevcut sarki gonderiliyor")
            # Debounce / aktif timer'ı bypass et — guest açıkça state istedi, hemen gönder.
            _sb_timer = self._ensure_collab_state_broadcast_timer()
            _sb_timer.stop()
            self._collab_last_state_broadcast_ms = 0
            self._collab_schedule_state_broadcast()
        elif event_type == "join_approved":
            # Host onayladı — sync başlatılabilir.
            if session.is_host:
                return
            if not getattr(self, "_collab_discord_join_pending", False):
                return
            log.info("collab: Discord join onaylandı, sync başlıyor")
            self._collab_discord_join_pending = False
            try:
                session.send_request_state()
            except Exception as e:
                log.debug("collab send_request_state hatası: %s", e)
            from ui.toast import show_toast
            show_toast(self, "Odaya katıldın! Beraber dinleniyor.")
        elif event_type == "join_denied":
            # Host reddetti.
            if session.is_host:
                return
            log.info("collab: Discord join reddedildi")
            self._collab_discord_join_pending = False
            self.collab_leave()
            from ui.toast import show_toast
            show_toast(self, "Oda sahibi isteğini reddetti.")

    def _collab_build_track(self, raw: dict) -> dict | None:
        if not isinstance(raw, dict):
            return None
        vid = str(raw.get("videoId") or raw.get("vid") or "").strip()
        if not vid:
            return None
        raw_artists = raw.get("artists")
        artists = []
        if isinstance(raw_artists, list):
            for artist in raw_artists:
                if isinstance(artist, dict):
                    name = str(artist.get("name") or "").strip()
                else:
                    name = str(artist or "").strip()
                if name:
                    artists.append({"name": name})
        if not artists:
            artist_name = str(raw.get("artist") or "").strip()
            if artist_name:
                artists.append({"name": artist_name})
        if not artists:
            artists = [{"name": "?"}]
        thumbs = raw.get("thumbnails")
        if not isinstance(thumbs, list):
            thumbs = raw.get("thumbs")
        if not isinstance(thumbs, list):
            thumbs = []
        track = {
            "videoId": vid,
            "title": str(raw.get("title") or "?"),
            "artists": artists,
            "thumbnails": thumbs,
        }
        try:
            _ = self._thumb(track)
        except Exception as e:
            log.debug("collab track thumb hazirlanamadi: %s", e)
        return track

    def _collab_collect_upcoming(self, limit: int = 3) -> list[dict]:
        queue = getattr(self, "queue", []) or []
        idx = int(getattr(self, "queue_index", -1))
        if not (0 <= idx < len(queue)):
            return []
        current_vid = str((queue[idx] or {}).get("videoId", "") or "")
        seen = {current_vid} if current_vid else set()
        upcoming = []
        for raw in queue[idx + 1:]:
            track = self._collab_build_track(raw)
            if track is None:
                continue
            vid = track.get("videoId", "")
            if not vid or vid in seen:
                continue
            upcoming.append(track)
            seen.add(vid)
            if len(upcoming) >= limit:
                break
        return upcoming

    def _collab_replace_guest_queue(self, current_track: dict, upcoming_items: list | None = None) -> list[dict]:
        current_vid = str((current_track or {}).get("videoId", "") or "")
        seen = {current_vid} if current_vid else set()
        upcoming = []
        for raw in upcoming_items or []:
            track = self._collab_build_track(raw)
            if track is None:
                continue
            vid = track.get("videoId", "")
            if not vid or vid in seen:
                continue
            upcoming.append(track)
            seen.add(vid)
        self.queue = [current_track, *upcoming]
        self.queue_index = 0
        return upcoming

    # ──────────── host → MQTT emit ────────────

    def _collab_emit_track(self, track: dict):
        s = self._collab
        if s is None or not s.is_host or not s.is_connected:
            return
        # YENİ şarkı geçişinde pos=0 gönder.
        # _play() çağrısı sırasında _load_audio henüz thread pool'da bekliyordur;
        # player.get_time() eski şarkının pozisyonunu döndürür (örn. 45000ms).
        # Guest bu değeri alır ve fast resync yeni şarkıya set_time(45000) yapar —
        # VLC buffer henüz o noktaya ulaşmamış olduğundan yükleme durur.
        # pos=0 ile gönderip periyodik seek ile hizalama yapılır.
        try:
            # Sıradaki 3 şarkıyı guest'e gönder (prefetch için)
            self._collab_host_bump_epoch(track)
            transport = self._collab_host_transport_kwargs(0, "loading", bump_version=False)
            upcoming = self._collab_collect_upcoming(limit=3)
            s.send_track(
                track,
                0,
                self._artist_str(track),
                upcoming=upcoming,
                playing=False,
                state="loading",
                anchor_host_ms=transport["anchor_host_ms"],
                session_epoch=transport["session_epoch"],
                track_version=transport["track_version"],
            )
            self._collab_refresh_dialog()
        except Exception as e:
            log.debug("collab send_track hatası: %s", e)

    def _collab_emit_upcoming(self):
        s = self._collab
        if s is None or not s.is_host or not s.is_connected:
            return
        try:
            queue = getattr(self, "queue", []) or []
            idx = int(getattr(self, "queue_index", -1))
            if not (0 <= idx < len(queue)):
                return
            current_vid = str((queue[idx] or {}).get("videoId", "") or "")
            if not current_vid:
                return
            s.send_upcoming(current_vid, self._collab_collect_upcoming(limit=3))
        except Exception as e:
            log.debug("collab send_upcoming hatası: %s", e)

    def _collab_emit_play(self, pos_override: int | None = None):
        s = self._collab
        if s is None or not s.is_host or not s.is_connected:
            return
        try:
            pos_ms = max(0, int(self.player.get_time() if pos_override is None else pos_override))
            transport = self._collab_host_transport_kwargs(pos_ms, "playing", bump_version=True)
            s.send_play(
                pos_ms,
                anchor_host_ms=transport["anchor_host_ms"],
                session_epoch=transport["session_epoch"],
                track_version=transport["track_version"],
            )
            self._collab_refresh_dialog()
        except Exception as e:
            log.debug("collab send_play hatası: %s", e)

    def _collab_emit_pause(self):
        s = self._collab
        if s is None or not s.is_host or not s.is_connected:
            return
        try:
            pos_ms = max(0, int(self.player.get_time()))
            transport = self._collab_host_transport_kwargs(pos_ms, "paused", bump_version=True)
            s.send_pause(
                pos_ms,
                anchor_host_ms=transport["anchor_host_ms"],
                session_epoch=transport["session_epoch"],
                track_version=transport["track_version"],
            )
            self._collab_refresh_dialog()
        except Exception as e:
            log.debug("collab send_pause hatası: %s", e)

    def _collab_emit_seek(self, position_ms: int, *, bump_version: bool = True):
        s = self._collab
        if s is None or not s.is_host or not s.is_connected:
            return
        try:
            state = "playing"
            try:
                if not self.player.is_playing():
                    state = "paused"
            except Exception:
                pass
            transport = self._collab_host_transport_kwargs(position_ms, state, bump_version=bump_version)
            s.send_seek(
                position_ms,
                state=transport["state"],
                anchor_host_ms=transport["anchor_host_ms"],
                session_epoch=transport["session_epoch"],
                track_version=transport["track_version"],
            )
            self._collab_refresh_dialog()
        except Exception as e:
            log.debug("collab send_seek hatası: %s", e)

    # ──────────── MQTT → main thread ────────────

    def _collab_raw_sync(self, event: dict):
        """MQTT thread'inden çağrılır — signal ile main thread'e iletir."""
        try:
            self.sig.collab_sync.emit(event)
        except Exception as e:
            log.debug("collab_raw_sync emit hatası: %s", e)

    def _collab_raw_status(self, state: str, msg: str):
        """MQTT thread'inden çağrılır — signal ile main thread'e iletir."""
        try:
            self.sig.collab_status.emit(state, msg)
        except Exception as e:
            log.debug("collab_raw_status emit hatası: %s", e)

    # ──────────── main thread: sync event'leri ────────────

    def _collab_on_sync(self, event: dict):
        """Main thread'de çalışır (queued signal)."""
        if not event or not isinstance(event, dict):
            return
        # Discord deep-link ile katılındıysa host onaylayana kadar sync yok
        if getattr(self, "_collab_discord_join_pending", False):
            return

        t = event.get("t", "")
        s = self._collab

        if t == "track":
            self._collab_sync_track(event, s)
        elif t == "upcoming":
            self._collab_sync_upcoming(event, s)
        elif t == "play":
            self._collab_sync_play(event, s)
        elif t == "pause":
            self._collab_sync_pause(event, s)
        elif t == "seek":
            self._collab_sync_seek(event, s)
        self._collab_refresh_dialog()

    def _collab_sync_track(self, event: dict, s):
        """Yeni şarkı event'i: şarkıyı başlat, hızlı resync timer'ı devreye al."""
        vid = event.get("vid", "")
        if not vid:
            return
        track = self._collab_build_track({
            "vid": vid,
            "title": event.get("title", ""),
            "artist": event.get("artist", ""),
            "thumbs": event.get("thumbs", []),
        })
        if track is None:
            return
        # Raw pozisyon — time.time() compensation YOK (saat farkı sapma yaratır)
        transport = self._collab_store_transport(
            event,
            default_state="playing" if bool(event.get("playing", True)) else "paused",
        )
        should_play = transport["state"] == "playing"
        if should_play:
            self._collab_mark_active_sync_window()
        start_ms = self._collab_target_position_ms(transport) if should_play else transport["anchor_pos_ms"]
        track["_collab_autoplay"] = should_play

        current_vid = ""
        try:
            queue = getattr(self, "queue", []) or []
            idx = int(getattr(self, "queue_index", -1))
            if 0 <= idx < len(queue):
                current_vid = str((queue[idx] or {}).get("videoId", "") or "")
        except Exception:
            current_vid = ""

        upcoming = self._collab_replace_guest_queue(track, event.get("upcoming", []))
        try:
            if upcoming:
                self._prime_stream_urls(upcoming, limit=1)
            self._prefetch_next()
        except Exception as e:
            log.debug("collab upcoming prefetch hatası: %s", e)
        self.target_vid = vid
        self._collab_pending_seek_ms = start_ms
        self._collab_queue_clock_sync()
        # Son bilinen host pozisyonunu kaydet (fast resync bunu kullanır)
        self._collab_last_host_pos_ms = start_ms

        if current_vid == vid:
            try:
                if should_play and not self.player.is_playing():
                    self.player.play()
                elif not should_play and self.player.is_playing():
                    self.player.pause()
                if should_play:
                    self._collab_apply_soft_sync(start_ms, allow_seek=False)
                else:
                    self._collab_reset_soft_rate()
            except Exception as e:
                log.debug("collab mevcut parca devam ettirilemedi: %s", e)
            try:
                self.sig.player_ui_update.emit()
            except Exception:
                pass
            if should_play:
                self._collab_start_fast_resync(ticks=_FAST_RESYNC_TICKS)
            else:
                self._stop_collab_fast_resync_timer()
            return

        try:
            self._play(track)
        except Exception as e:
            log.debug("collab _play hatası: %s", e)

        # Yükleme gecikmesini telafi etmek için hızlı resync başlat (tam 25 tick)
        if should_play:
            self._collab_start_fast_resync(ticks=_FAST_RESYNC_TICKS)
        else:
            self._stop_collab_fast_resync_timer()

    def _collab_sync_upcoming(self, event: dict, s):
        """Host kuyruÄŸundaki sonraki parçaları guest tarafında günceller."""
        if not self._collab_is_guest_active():
            return
        queue = getattr(self, "queue", []) or []
        idx = int(getattr(self, "queue_index", -1))
        if not (0 <= idx < len(queue)):
            return
        current_track = queue[idx]
        current_vid = str((current_track or {}).get("videoId", "") or "")
        event_vid = str(event.get("current_vid", "") or "")
        if event_vid and current_vid and event_vid != current_vid:
            return
        upcoming = self._collab_replace_guest_queue(current_track, event.get("tracks", []))
        try:
            if upcoming:
                self._prime_stream_urls(upcoming, limit=1)
            self._prefetch_next()
        except Exception as e:
            log.debug("collab upcoming sync prefetch hatası: %s", e)

    # ──────────── hızlı resync (şarkı yükleme gecikmesi için) ────────────

    def _collab_start_fast_resync(self, ticks: int = _FAST_RESYNC_TICKS):
        """
        Yeni şarkı yüklenirken veya resume sonrası pozisyonu hızla hizalar.
        Main thread'de çağrılır — QTimer güvenli.
        ticks: kaç tick çalışacak (varsayılan 25 = ~20 saniye)
        """
        self._collab_fast_resync_ticks = 0
        self._collab_fast_resync_max_ticks = ticks
        timer = getattr(self, "_collab_fast_resync_timer", None)
        if timer is None:
            timer = QTimer(self)
            timer.setInterval(_FAST_RESYNC_INTERVAL_MS)
            timer.timeout.connect(self._collab_fast_resync_tick)
            self._collab_fast_resync_timer = timer
        timer.start()
        log.debug("collab fast resync başladı (max_ticks=%d)", ticks)

    def _stop_collab_fast_resync_timer(self):
        timer = getattr(self, "_collab_fast_resync_timer", None)
        if timer is not None:
            timer.stop()

    # ──────────── periyodik resync (host tarafı) ────────────

    def _ensure_collab_resync_timer(self):
        """Host'un periyodik seek timer'ı — sadece main thread'den çağrılır."""
        timer = getattr(self, "_collab_resync_timer", None)
        if timer is None:
            timer = QTimer(self)
            timer.setInterval(_PERIODIC_SYNC_INTERVAL_MS)
            timer.timeout.connect(self._collab_periodic_sync_tick)
            self._collab_resync_timer = timer
        return timer

    def _stop_collab_resync_timer(self):
        timer = getattr(self, "_collab_resync_timer", None)
        if timer is not None:
            timer.stop()

    def _ensure_collab_state_broadcast_timer(self):
        timer = getattr(self, "_collab_state_broadcast_timer", None)
        if timer is None:
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(self._collab_flush_state_broadcast)
            self._collab_state_broadcast_timer = timer
        return timer

    def _collab_schedule_state_broadcast(self):
        session = self._collab
        if session is None or not session.is_host or not session.is_connected:
            return
        timer = self._ensure_collab_state_broadcast_timer()
        if timer.isActive():
            return
        now_ms = self._collab_local_now_ms()
        last_sent_ms = int(getattr(self, "_collab_last_state_broadcast_ms", 0) or 0)
        if last_sent_ms <= 0:
            delay_ms = _STATE_BROADCAST_BATCH_MS
        else:
            elapsed_ms = now_ms - last_sent_ms
            delay_ms = (
                _STATE_BROADCAST_BATCH_MS
                if elapsed_ms >= _STATE_BROADCAST_DEBOUNCE_MS
                else (_STATE_BROADCAST_DEBOUNCE_MS - elapsed_ms)
            )
        timer.start(max(0, int(delay_ms)))

    def _collab_flush_state_broadcast(self):
        if self._collab_send_current_track_to_peer():
            self._collab_last_state_broadcast_ms = self._collab_local_now_ms()

    def _collab_reset_state_broadcast_gate(self):
        self._collab_last_state_broadcast_ms = 0
        timer = getattr(self, "_collab_state_broadcast_timer", None)
        if timer is not None:
            timer.stop()

    # ──────────── UI yardımcıları ────────────

    def _ensure_collab_drift_timer(self):
        timer = getattr(self, "_collab_drift_timer", None)
        if timer is None:
            timer = QTimer(self)
            timer.setInterval(_DRIFT_SYNC_INTERVAL_MS)
            timer.timeout.connect(self._collab_drift_tick)
            self._collab_drift_timer = timer
        return timer

    def _stop_collab_drift_timer(self):
        timer = getattr(self, "_collab_drift_timer", None)
        if timer is not None:
            timer.stop()

    def _collab_update_drift_timer(self):
        if (
            self._collab_is_guest_active()
            and getattr(self, "_collab_host_playing", False)
            and self._collab_in_active_sync_window()
        ):
            self._ensure_collab_drift_timer().start()
        else:
            self._stop_collab_drift_timer()
            self._collab_reset_soft_rate()

    def _collab_drift_tick(self):
        if not self._collab_is_guest_active():
            self._stop_collab_drift_timer()
            self._collab_reset_soft_rate()
            return
        if getattr(self, "_collab_host_playing", False) is False:
            self._stop_collab_drift_timer()
            self._collab_reset_soft_rate()
            return
        if not self._collab_in_active_sync_window():
            self._stop_collab_drift_timer()
            self._collab_reset_soft_rate()
            return
        try:
            if not self.player.is_playing():
                return
        except Exception:
            return
        target_pos = self._collab_target_position_ms()
        self._collab_last_host_pos_ms = target_pos
        self._collab_apply_soft_sync(target_pos, allow_seek=False)

    def _collab_sync_play(self, event: dict, s):
        transport = self._collab_store_transport(event, default_state="playing")
        self._collab_mark_active_sync_window()
        target_pos = self._collab_target_position_ms(transport)
        self._collab_last_host_pos_ms = target_pos
        try:
            if not self.player.is_playing():
                self.player.play()
            self._collab_apply_soft_sync(target_pos, allow_seek=True)
        except Exception as e:
            log.debug("collab play sync hatasi: %s", e)
        self._collab_start_fast_resync(ticks=10)

    def _collab_sync_pause(self, event: dict, s):
        transport = self._collab_store_transport(event, default_state="paused")
        pos = transport["anchor_pos_ms"]
        self._collab_last_host_pos_ms = pos
        try:
            if self.player.is_playing():
                self.player.pause()
            self.player.set_time(pos)
        except Exception as e:
            log.debug("collab pause sync hatasi: %s", e)
        self._collab_active_sync_until_ms = 0
        self._stop_collab_fast_resync_timer()
        self._stop_collab_drift_timer()
        self._collab_reset_soft_rate()

    def _collab_sync_seek(self, event: dict, s):
        prev_version = int(getattr(self, "_collab_track_version", 0) or 0)
        transport = self._collab_store_transport(
            event,
            default_state="playing" if getattr(self, "_collab_host_playing", True) else "paused",
        )
        target_pos = self._collab_target_position_ms(transport)
        self._collab_last_host_pos_ms = target_pos
        explicit_seek = int(transport.get("track_version", 0) or 0) != prev_version
        try:
            current = max(0, int(self.player.get_time()))
            if target_pos < 2000 and current < 2000:
                return
            if explicit_seek:
                self._collab_mark_active_sync_window()
                self._collab_apply_soft_sync(target_pos, allow_seek=True)
                return
            if not self._collab_in_active_sync_window():
                self._collab_reset_soft_rate()
                diff = current - target_pos
                last_emergency_ms = int(getattr(self, "_collab_last_emergency_seek_ms", 0) or 0)
                now_ms = self._collab_local_now_ms()
                if abs(diff) >= _EMERGENCY_SEEK_THRESHOLD_MS and (now_ms - last_emergency_ms) >= _EMERGENCY_SEEK_COOLDOWN_MS:
                    try:
                        self.player.set_time(max(0, int(target_pos)))
                        self._collab_last_emergency_seek_ms = now_ms
                    except Exception as seek_error:
                        log.debug("collab emergency seek hatasi: %s", seek_error)
                return
            self._collab_apply_soft_sync(target_pos, allow_seek=False)
        except Exception as e:
            log.debug("collab seek sync hatasi: %s", e)

    def _collab_fast_resync_tick(self):
        ticks = int(getattr(self, "_collab_fast_resync_ticks", 0) or 0)
        self._collab_fast_resync_ticks = ticks + 1
        max_ticks = int(getattr(self, "_collab_fast_resync_max_ticks", _FAST_RESYNC_TICKS) or _FAST_RESYNC_TICKS)
        if ticks >= max_ticks:
            self._stop_collab_fast_resync_timer()
            self._collab_update_drift_timer()
            log.debug("collab fast resync tamamlandi")
            return

        target_pos = self._collab_target_position_ms()
        self._collab_last_host_pos_ms = target_pos
        if getattr(self, "_collab_host_playing", True) is False:
            self._stop_collab_fast_resync_timer()
            self._collab_update_drift_timer()
            return
        try:
            playing = bool(self.player.is_playing())
        except Exception:
            return
        if not playing:
            try:
                self.player.play()
            except Exception as e:
                log.debug("collab fast resync play hatasi: %s", e)
            return
        try:
            current = max(0, int(self.player.get_time()))
        except Exception:
            return
        if target_pos < 2500 and current < 2500:
            return
        diff = self._collab_apply_soft_sync(target_pos, allow_seek=True)
        if abs(diff) >= _SEEK_THRESHOLD_MS:
            log.debug(
                "collab fast resync duzeltme: tick=%d current=%d host=%d fark=%d",
                ticks,
                current,
                target_pos,
                diff,
            )

    def _collab_periodic_sync_tick(self):
        session = self._collab
        if session is None or not session.is_host or not session.is_connected or not session.peer_connected:
            self._stop_collab_resync_timer()
            return
        try:
            if not self.player.is_playing():
                return
            pos_ms = max(0, int(self.player.get_time()))
            self._collab_emit_seek(pos_ms, bump_version=False)
        except Exception as e:
            log.debug("collab periodic sync hatasi: %s", e)

    def _collab_on_status(self, state: str, msg: str):
        log.info("Collab durum: %s - %s", state, msg)
        self._collab_update_ui()
        session = self._collab
        timer = self._ensure_collab_resync_timer()
        was_active = timer.isActive()
        if session is not None and session.is_host and session.is_connected and session.peer_connected:
            if not was_active:
                timer.start()
            # Yeni guest bağlandığında her zaman state broadcast'i zorla başlat.
            _sb = self._ensure_collab_state_broadcast_timer()
            _sb.stop()
            self._collab_last_state_broadcast_ms = 0
            self._collab_schedule_state_broadcast()
        else:
            self._stop_collab_resync_timer()
        if self._collab_is_guest_active() and session is not None and session.peer_connected:
            self._collab_queue_clock_sync()
        self._collab_update_drift_timer()
        self._collab_refresh_dialog(state, msg)

    def _collab_send_current_track_to_peer(self):
        session = self._collab
        if session is None or not session.is_host or not session.is_connected:
            return False
        try:
            queue = getattr(self, "queue", []) or []
            idx = int(getattr(self, "queue_index", -1))
            if not (0 <= idx < len(queue)):
                return False
            track = queue[idx]
            try:
                playing = bool(self.player.is_playing())
            except Exception:
                playing = False
            try:
                media = self.player.get_media()
            except Exception:
                media = None
            if not playing and media is None:
                return False
            try:
                pos_ms = max(0, int(self.player.get_time()))
            except Exception:
                pos_ms = 0
            state_name = "playing" if playing else "paused"
            transport = self._collab_host_transport_kwargs(pos_ms, state_name, bump_version=False)
            log.info("Collab: peer baglandi, mevcut sarki gonderiliyor pos=%d", pos_ms)
            session.send_track(
                track,
                pos_ms,
                self._artist_str(track),
                upcoming=self._collab_collect_upcoming(limit=3),
                playing=playing,
                state=state_name,
                anchor_host_ms=transport["anchor_host_ms"],
                session_epoch=transport["session_epoch"],
                track_version=transport["track_version"],
            )
            if not playing:
                session.send_pause(
                    pos_ms,
                    anchor_host_ms=transport["anchor_host_ms"],
                    session_epoch=transport["session_epoch"],
                    track_version=transport["track_version"],
                )
            return True
        except Exception as e:
            log.debug("collab_send_current_track_to_peer hatasi: %s", e)
            return False

    def _collab_update_ui(self):
        try:
            btn = getattr(self, "_collab_btn", None)
            if btn is None:
                return
            s = self._collab
            if s is not None and s.room_code and s.state in {s.ST_CONNECTED, s.ST_CONNECTING}:
                from core.theme import get_accent
                acc = get_accent()
                btn.setStyleSheet(
                    f"QPushButton {{ background:{acc}22; color:{acc}; border:1px solid {acc}; border-radius:10px; padding:6px 14px; font-size:12px; font-weight:700; }}"
                    f"QPushButton:hover {{ background:{acc}44; }}"
                )
                role = self._tr("collab.role.host_short") if s.is_host else self._tr("collab.role.guest_short")
                btn.setText(self._tr("collab.button.active", role=role))
            else:
                # Orijinal stili geri yükle (text-align:left korunur)
                default_ss = getattr(btn, "_default_stylesheet", "")
                btn.setStyleSheet(default_ss)
                btn.setText(self._tr("collab.button.title"))
        except Exception as e:
            log.debug("collab_update_ui hatası: %s", e)

    def _collab_show_join_approval(self):
        """Discord'dan katılma isteği geldiğinde host'a collab dialog içinde onay banner'ı göster."""
        session = self._collab
        if session is None or not session.is_host or not session.is_connected:
            return

        def _on_accept():
            s = self._collab
            if s and s.is_host and s.is_connected:
                s.send_join_response(True)
                log.info("collab: Discord join isteği onaylandı")

        def _on_deny():
            s = self._collab
            if s and s.is_host and s.is_connected:
                s.send_join_response(False)
                log.info("collab: Discord join isteği reddedildi")

        # Collab dialog'u aç ve banner'ı içine yerleştir
        self._collab_open_dialog()
        dlg = getattr(self, "_collab_dialog", None)
        if dlg is not None and hasattr(dlg, "show_join_banner"):
            dlg.show_join_banner(_on_accept, _on_deny)
        # Odak çalmadan görev çubuğu ikonunu yanıp söndür
        try:
            from PySide6.QtWidgets import QApplication as _QApp
            _QApp.alert(self, 0)
        except Exception:
            pass

    def _collab_refresh_dialog(self, state: str | None = None, msg: str | None = None):
        dlg = getattr(self, "_collab_dialog", None)
        if dlg is None:
            return
        try:
            if state is not None:
                if hasattr(dlg, "queue_status"):
                    dlg.queue_status(state, msg or "")
                else:
                    dlg.on_status(state, msg or "")
            if hasattr(dlg, "queue_refresh"):
                dlg.queue_refresh()
            else:
                dlg.refresh_now()
        except Exception as e:
            log.debug("collab_refresh_dialog hatası: %s", e)

    def _collab_open_dialog(self):
        from ui.collab_dialog import CollabDialog

        dlg = getattr(self, "_collab_dialog", None)
        if dlg is None:
            dlg = CollabDialog(self)
            dlg.destroyed.connect(lambda *_: setattr(self, "_collab_dialog", None))
            self._collab_dialog = dlg

        try:
            if hasattr(dlg, "queue_refresh"):
                dlg.queue_refresh()
            else:
                dlg.refresh_now()
            dlg.show()
            dlg.raise_()
            dlg.activateWindow()
        except Exception as e:
            log.debug("collab dialog açılamadı: %s", e)
