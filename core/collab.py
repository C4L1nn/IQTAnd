"""
iqtMusic - Beraber Dinleme (Collab Session)
===========================================

MQTT tabanli gercek zamanli muzik senkronizasyonu.
"""

from __future__ import annotations

import json
import logging
import random
import secrets
import string
import threading
import time
from typing import Callable

from core.i18n import DEFAULT_LANGUAGE, translate

log = logging.getLogger("iqtMusic.collab")

try:
    import paho.mqtt.client as mqtt  # type: ignore
    _MQTT_OK = True
except ImportError:
    mqtt = None  # type: ignore
    _MQTT_OK = False
    log.warning("paho-mqtt kurulu değil - 'pip install paho-mqtt' ile kurun")

_BROKER_HOST = "broker.hivemq.com"
_BROKER_PORT = 8883
_KEEPALIVE = 60
_TOPIC_PREFIX = "iqtmusic/v1"
_QOS = 1
_PRESENCE_QOS = 1
_PRESENCE_INTERVAL = 4.0
_PRESENCE_STALE_AFTER = 12.0
_RECONNECT_DELAYS = [3, 6, 12, 24, 30]  # saniye cinsinden exponential backoff
_REQUEST_STATE_DELAY_MIN = 0.3
_REQUEST_STATE_DELAY_MAX = 2.0


def _gen_room_code() -> str:
    chars = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(chars) for _ in range(8))


def fmt_room_code(raw: str) -> str:
    room = raw.upper().replace("-", "")[:8]
    return f"{room[:4]}-{room[4:]}" if len(room) == 8 else room


def parse_room_code(text: str) -> str:
    return text.upper().replace("-", "").replace(" ", "")[:8]


class CollabSession:
    ST_DISCONNECTED = "disconnected"
    ST_CONNECTING = "connecting"
    ST_CONNECTED = "connected"
    ST_ERROR = "error"

    def __init__(
        self,
        on_sync: Callable[[dict], None] | None = None,
        on_control: Callable[[dict], None] | None = None,
        on_status: Callable[[str, str], None] | None = None,
        translator: Callable[..., str] | None = None,
    ):
        self._on_sync = on_sync
        self._on_control = on_control
        self._on_status = on_status
        self._translator = translator
        self._client = None
        self._room_code = ""
        self._is_host = False
        self._state = self.ST_DISCONNECTED
        self._lock = threading.RLock()
        self._client_id = ""
        self._participants: dict[str, dict] = {}
        self._presence_stop = threading.Event()
        self._presence_thread: threading.Thread | None = None
        self._last_presence_signature: tuple[int, bool] | None = None
        self._last_status_message = ""
        self._intentional_leave = False
        self._reconnect_attempt = 0

    def _tr(self, key: str, **kwargs) -> str:
        if self._translator is not None:
            try:
                return str(self._translator(key, **kwargs))
            except Exception:
                pass
        return translate(DEFAULT_LANGUAGE, key, **kwargs)

    def _now_ms(self) -> int:
        return int(time.time() * 1000)

    def _transport_payload(
        self,
        event_type: str,
        position_ms: int,
        *,
        state: str,
        anchor_host_ms: int | None = None,
        session_epoch: int = 0,
        track_version: int = 0,
    ) -> dict:
        return {
            "t": event_type,
            "pos": int(position_ms),
            "state": str(state or "paused"),
            "anchor_pos_ms": int(position_ms),
            "anchor_host_ms": int(anchor_host_ms or self._now_ms()),
            "session_epoch": int(session_epoch or 0),
            "track_version": int(track_version or 0),
        }

    @property
    def room_code(self) -> str:
        return self._room_code

    @property
    def formatted_room_code(self) -> str:
        return fmt_room_code(self._room_code)

    @property
    def is_host(self) -> bool:
        return self._is_host

    @property
    def state(self) -> str:
        return self._state

    @property
    def is_connected(self) -> bool:
        return self._state == self.ST_CONNECTED

    @property
    def role_label(self) -> str:
        return self._tr("collab.role.host") if self._is_host else self._tr("collab.role.guest")

    @property
    def participant_count(self) -> int:
        now = time.time()
        with self._lock:
            active = [
                item
                for item in self._participants.values()
                if now - float(item.get("last_seen", 0.0)) <= _PRESENCE_STALE_AFTER
            ]
            count = len(active)
        return max(1 if self._room_code else 0, count)

    @property
    def participant_label(self) -> str:
        count = self.participant_count
        if count <= 0:
            return self._tr("collab.participants.disconnected")
        return self._tr("collab.participants.connected", count=count)

    @property
    def peer_connected(self) -> bool:
        return self.participant_count >= 2

    @property
    def connection_label(self) -> str:
        if self._state == self.ST_CONNECTING:
            return self._tr("collab.connection.connecting")
        if self._state == self.ST_ERROR:
            return self._tr("collab.connection.error")
        if self._state != self.ST_CONNECTED:
            return self._tr("collab.connection.disconnected")
        return self._tr("collab.connection.active") if self.peer_connected else self._tr("collab.connection.waiting")

    def create(self) -> str:
        if not _MQTT_OK:
            self._emit_status(self.ST_ERROR, self._tr("collab.error.mqtt_missing"))
            return ""
        self._reconnect_attempt = 0
        self._intentional_leave = False
        self._room_code = _gen_room_code()
        self._is_host = True
        self._connect()
        return self._room_code

    def join(self, room_code: str, from_discord: bool = False) -> bool:
        if not _MQTT_OK:
            self._emit_status(self.ST_ERROR, self._tr("collab.error.mqtt_missing"))
            return False
        self._room_code = parse_room_code(room_code)
        if len(self._room_code) != 8:
            self._emit_status(self.ST_ERROR, self._tr("collab.error.invalid_room"))
            return False
        self._reconnect_attempt = 0
        self._intentional_leave = False
        self._is_host = False
        self._from_discord = from_discord  # Discord deep-link ile mi katılıyor?
        self._connect()
        return True

    def leave(self):
        """Oturumu kapatır. Bloklamaz — arka planda çalışır."""
        self._intentional_leave = True
        threading.Thread(target=self._leave_blocking, daemon=True, name="collab-leave").start()

    def _leave_blocking(self):
        try:
            info = self._publish_presence(kind="bye")
            if info is not None:
                try:
                    info.wait_for_publish(timeout=1.5)
                except Exception:
                    pass
        except Exception:
            pass
        time.sleep(0.3)
        with self._lock:
            client = self._client
            self._client = None
            self._room_code = ""
            self._is_host = False
            self._participants.clear()
            self._client_id = ""
        self._stop_presence_loop()
        if client is not None:
            try:
                client.disconnect()
            except Exception:
                pass
            try:
                client.loop_stop()
            except Exception:
                pass
        self._emit_status(self.ST_DISCONNECTED, self._tr("collab.status.left"))
        log.info("Collab oturumu kapatıldı")

    def send_track(
        self,
        track: dict,
        position_ms: int = 0,
        artist_str: str = "",
        upcoming: list | None = None,
        playing: bool = True,
        *,
        state: str | None = None,
        anchor_host_ms: int | None = None,
        session_epoch: int = 0,
        track_version: int = 0,
    ):
        payload = self._transport_payload(
            "track",
            position_ms,
            state=state or ("playing" if playing else "paused"),
            anchor_host_ms=anchor_host_ms,
            session_epoch=session_epoch,
            track_version=track_version,
        )
        payload.update({
            "vid": track.get("videoId", ""),
            "title": track.get("title", ""),
            "artist": artist_str or "",
            "thumbs": track.get("thumbnails", []),
            "upcoming": upcoming or [],
            "playing": bool(playing),
        })
        self._publish(payload)

    def send_play(
        self,
        position_ms: int,
        *,
        anchor_host_ms: int | None = None,
        session_epoch: int = 0,
        track_version: int = 0,
    ):
        self._publish(
            self._transport_payload(
                "play",
                position_ms,
                state="playing",
                anchor_host_ms=anchor_host_ms,
                session_epoch=session_epoch,
                track_version=track_version,
            )
        )

    def send_pause(
        self,
        position_ms: int,
        *,
        anchor_host_ms: int | None = None,
        session_epoch: int = 0,
        track_version: int = 0,
    ):
        self._publish(
            self._transport_payload(
                "pause",
                position_ms,
                state="paused",
                anchor_host_ms=anchor_host_ms,
                session_epoch=session_epoch,
                track_version=track_version,
            )
        )

    def send_seek(
        self,
        position_ms: int,
        *,
        state: str = "playing",
        anchor_host_ms: int | None = None,
        session_epoch: int = 0,
        track_version: int = 0,
    ):
        self._publish(
            self._transport_payload(
                "seek",
                position_ms,
                state=state,
                anchor_host_ms=anchor_host_ms,
                session_epoch=session_epoch,
                track_version=track_version,
            )
        )

    def send_upcoming(self, current_vid: str, tracks: list | None = None):
        self._publish({
            "t": "upcoming",
            "current_vid": current_vid or "",
            "tracks": tracks or [],
        })

    def send_control(self, payload: dict):
        if not isinstance(payload, dict):
            return
        body = dict(payload)
        body.setdefault("client_id", self._client_id)
        body.setdefault("role", "host" if self._is_host else "guest")
        self._publish_control(body)

    def send_request_state(self):
        """Guest bağlandıktan sonra host'tan mevcut şarkı ve pozisyonu talep eder."""
        self.send_control({"t": "request_state"})

    def send_join_request(self):
        """Discord deep-link ile katılan guest, host'tan onay ister."""
        self.send_control({"t": "join_request"})

    def send_join_response(self, approved: bool):
        """Host tarafından onay veya red gönderilir."""
        self.send_control({"t": "join_approved" if approved else "join_denied"})

    def send_clock_ping(self, ping_id: str, client_time_ms: int):
        self.send_control({
            "t": "clock_ping",
            "ping_id": str(ping_id),
            "client_time_ms": int(client_time_ms),
        })

    def send_clock_pong(self, ping_id: str, client_time_ms: int, host_recv_ms: int):
        self.send_control({
            "t": "clock_pong",
            "ping_id": str(ping_id),
            "client_time_ms": int(client_time_ms),
            "host_recv_ms": int(host_recv_ms),
            "host_send_ms": self._now_ms(),
        })

    def _summary_message_legacy(self) -> str:
        if self._state == self.ST_CONNECTING:
            return self._tr("collab.summary.connecting")
        if self._state == self.ST_ERROR:
            return self._last_status_message or self._tr("collab.summary.connection_error")
        if self._state == self.ST_DISCONNECTED:
            return self._last_status_message or self._tr("collab.summary.disconnected")
        if self._is_host:
            return self._tr("collab.summary.host_active", participants=self.participant_label) if self.peer_connected else self._tr("collab.summary.host_waiting")
        return self._tr("collab.summary.guest_active", participants=self.participant_label) if self.peer_connected else self._tr("collab.summary.guest_waiting")

    def _topic_state(self) -> str:
        return f"{_TOPIC_PREFIX}/{self._room_code}/state"

    def _topic_control(self) -> str:
        return f"{_TOPIC_PREFIX}/{self._room_code}/control"

    def _topic_presence(self) -> str:
        return f"{_TOPIC_PREFIX}/{self._room_code}/presence"

    def _publish(self, payload: dict):
        if not self._is_host:
            return
        with self._lock:
            client = self._client
            ok = self._state == self.ST_CONNECTED
        if client is None or not ok:
            return
        try:
            client.publish(self._topic_state(), json.dumps(payload, ensure_ascii=False), qos=_QOS, retain=False)
        except Exception as e:
            log.debug("MQTT publish hatası: %s", e)

    def _publish_control(self, payload: dict):
        with self._lock:
            client = self._client
            ok = self._state == self.ST_CONNECTED
        if client is None or not ok:
            return
        try:
            client.publish(self._topic_control(), json.dumps(payload, ensure_ascii=False), qos=_QOS, retain=False)
        except Exception as e:
            log.debug("MQTT control publish hatası: %s", e)

    def _publish_presence(self, kind: str = "ping", force: bool = False):
        with self._lock:
            client = self._client
            ok = self._state == self.ST_CONNECTED
            client_id = self._client_id
            room_code = self._room_code
            is_host = self._is_host
        if client is None or (not ok and not force) or not room_code or not client_id:
            return None
        payload = {
            "t": "presence",
            "kind": kind,
            "client_id": client_id,
            "role": "host" if is_host else "guest",
            "room": room_code,
            "ts": time.time(),
        }
        try:
            return client.publish(
                self._topic_presence(),
                json.dumps(payload, ensure_ascii=False),
                qos=_PRESENCE_QOS,
                retain=False,
            )
        except Exception as e:
            log.debug("MQTT presence publish hatası: %s", e)
            return None

    def _start_presence_loop(self):
        self._stop_presence_loop()
        self._presence_stop.clear()

        def _loop():
            while not self._presence_stop.wait(_PRESENCE_INTERVAL):
                try:
                    self._publish_presence("ping")
                    self._prune_presence()
                except Exception as e:
                    log.debug("Presence döngü hatası: %s", e)

        thread = threading.Thread(target=_loop, daemon=True, name="collab-presence")
        self._presence_thread = thread
        thread.start()

    def _stop_presence_loop(self):
        self._presence_stop.set()
        self._presence_thread = None

    def _connect(self):
        role = "host" if self._is_host else "guest"
        client_id = f"iqtm-{role}-{secrets.token_hex(5)}"
        self._client_id = client_id
        self._participants.clear()
        self._last_presence_signature = None
        self._emit_status(self.ST_CONNECTING, self._tr("collab.summary.connecting"))

        try:
            client = mqtt.Client(
                mqtt.CallbackAPIVersion.VERSION1,
                client_id=client_id,
                protocol=mqtt.MQTTv311,
            )
        except AttributeError:
            client = mqtt.Client(client_id=client_id, protocol=mqtt.MQTTv311)

        try:
            client.tls_set()
        except Exception as e:
            log.warning("TLS ayarlanamadı, düz TCP deneniyor: %s", e)

        lwt_payload = json.dumps({
            "t": "presence",
            "kind": "bye",
            "client_id": client_id,
            "role": role,
            "room": self._room_code,
            "ts": 0,
        }, ensure_ascii=False)
        try:
            client.will_set(self._topic_presence(), lwt_payload, qos=_PRESENCE_QOS, retain=False)
        except Exception as e:
            log.debug("LWT ayarlanamadı: %s", e)

        client.on_connect = self._cb_connect
        client.on_disconnect = self._cb_disconnect
        client.on_message = self._cb_message

        with self._lock:
            self._client = client

        def _do_connect():
            try:
                client.connect(_BROKER_HOST, _BROKER_PORT, _KEEPALIVE)
                client.loop_start()
            except Exception as e:
                log.warning("MQTT bağlantı hatası: %s", e)
                self._emit_status(self.ST_ERROR, self._tr("collab.error.connect_failed", error=e))

        threading.Thread(target=_do_connect, daemon=True, name="collab-connect").start()

    def _cb_connect(self, client, userdata, flags, rc, *args):
        code = rc if isinstance(rc, int) else (rc.value if hasattr(rc, "value") else 0)
        if code == 0:
            self._reconnect_attempt = 0
            log.info("Collab MQTT bağlandı (oda=%s, host=%s)", self._room_code, self._is_host)
            client.subscribe(self._topic_presence(), qos=_PRESENCE_QOS)
            client.subscribe(self._topic_control(), qos=_QOS)
            if not self._is_host:
                client.subscribe(self._topic_state(), qos=_QOS)
                if getattr(self, "_from_discord", False):
                    # Discord deep-link ile katılıyorsa önce join_request gönder,
                    # host onaylayana kadar request_state gönderme.
                    delay = random.uniform(_REQUEST_STATE_DELAY_MIN, _REQUEST_STATE_DELAY_MAX)
                    timer = threading.Timer(delay, self.send_join_request)
                    timer.daemon = True
                    timer.start()
                else:
                    # Normal katılım: doğrudan mevcut state'i talep et.
                    delay = random.uniform(_REQUEST_STATE_DELAY_MIN, _REQUEST_STATE_DELAY_MAX)
                    timer = threading.Timer(delay, self.send_request_state)
                    timer.daemon = True
                    timer.start()
            self._register_self_presence()
            self._start_presence_loop()
            self._emit_status(self.ST_CONNECTED, self.summary_message())
            self._publish_presence("hello")
            threading.Timer(2.0, lambda: self._publish_presence("hello")).start()
        else:
            msg = self._tr("collab.error.rejected", code=code)
            log.warning("Collab: %s", msg)
            self._emit_status(self.ST_ERROR, msg)

    def _cb_disconnect(self, client, userdata, rc, *args):
        code = rc if isinstance(rc, int) else (rc.value if hasattr(rc, "value") else rc)
        log.info("Collab MQTT bağlantısı kesildi (rc=%s)", code)
        self._stop_presence_loop()
        with self._lock:
            still_active = self._client is client
            if still_active:
                self._participants.clear()
        if not still_active:
            return
        if self._intentional_leave:
            # leave() zaten _leave_blocking içinde status emit ediyor
            return
        attempt = self._reconnect_attempt
        if attempt >= len(_RECONNECT_DELAYS):
            self._emit_status(self.ST_ERROR, self._tr("collab.error.reconnect_failed"))
            return
        delay = _RECONNECT_DELAYS[attempt]
        self._reconnect_attempt += 1
        self._emit_status(
            self.ST_CONNECTING,
            self._tr(
                "collab.status.reconnecting",
                delay=delay,
                attempt=attempt + 1,
                max_attempts=len(_RECONNECT_DELAYS),
            ),
        )
        log.info("Collab reconnect denemesi %d/%d, %ds sonra", attempt + 1, len(_RECONNECT_DELAYS), delay)
        threading.Timer(delay, self._reconnect).start()

    def _reconnect(self):
        with self._lock:
            room_code = self._room_code
        if not room_code or self._intentional_leave:
            return
        log.info("Collab yeniden bağlanılıyor (oda=%s)", room_code)
        self._connect()

    def _cb_message(self, client, userdata, msg):
        topic = getattr(msg, "topic", "") or ""
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except Exception as e:
            log.debug("Collab mesaj parse hatası: %s", e)
            return

        if topic == self._topic_presence():
            self._handle_presence(payload)
            return

        if topic == self._topic_control():
            if str(payload.get("client_id", "") or "") == self._client_id:
                return
            callback = self._on_control
            if callback:
                try:
                    callback(payload)
                except Exception as e:
                    log.debug("Collab control callback hatası: %s", e)
            return

        if self._is_host:
            return
        callback = self._on_sync
        if callback:
            try:
                callback(payload)
            except Exception as e:
                log.debug("Collab sync callback hatası: %s", e)

    def _register_self_presence(self):
        now = time.time()
        with self._lock:
            if self._client_id:
                self._participants[self._client_id] = {
                    "client_id": self._client_id,
                    "role": "host" if self._is_host else "guest",
                    "last_seen": now,
                }

    def _handle_presence(self, payload: dict):
        if payload.get("t") != "presence":
            return
        client_id = str(payload.get("client_id", "") or "")
        if not client_id:
            return
        kind = str(payload.get("kind", "ping") or "ping")
        if payload.get("room") and str(payload.get("room")) != self._room_code:
            return
        role = str(payload.get("role", "guest") or "guest")
        now = time.time()
        with self._lock:
            if kind == "bye":
                self._participants.pop(client_id, None)
            else:
                self._participants[client_id] = {
                    "client_id": client_id,
                    "role": role,
                    "last_seen": now,
                }
        self._prune_presence()

    def _prune_presence(self):
        now = time.time()
        changed = False
        with self._lock:
            stale = [
                cid
                for cid, item in self._participants.items()
                if now - float(item.get("last_seen", 0.0)) > _PRESENCE_STALE_AFTER
            ]
            for cid in stale:
                self._participants.pop(cid, None)
                changed = True
            signature = (self.participant_count, self.peer_connected)
            should_emit = signature != self._last_presence_signature
            self._last_presence_signature = signature
        if changed or should_emit:
            if self._state == self.ST_CONNECTED:
                self._emit_status(self.ST_CONNECTED, self.summary_message())

    def summary_message(self) -> str:
        if self._state == self.ST_CONNECTING:
            return self._tr("collab.summary.connecting")
        if self._state == self.ST_ERROR:
            return self._last_status_message or self._tr("collab.summary.connection_error")
        if self._state == self.ST_DISCONNECTED:
            return self._last_status_message or self._tr("collab.summary.disconnected")
        if self._is_host:
            return self._tr("collab.summary.host_active", participants=self.participant_label) if self.peer_connected else self._tr("collab.summary.host_waiting")
        return self._tr("collab.summary.guest_active", participants=self.participant_label) if self.peer_connected else self._tr("collab.summary.guest_waiting")

    def _emit_status(self, state: str, msg: str = ""):
        self._state = state
        self._last_status_message = msg or self._last_status_message
        callback = self._on_status
        if callback:
            try:
                callback(state, msg)
            except Exception as e:
                log.debug("Collab status callback hatası: %s", e)
