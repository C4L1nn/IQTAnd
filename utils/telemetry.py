"""Anonymous install count telemetry — one ping per UTC day."""
from __future__ import annotations

import datetime
import os
import platform
import sys
import threading
import uuid

import requests

from utils.helpers import safe_load_json, safe_save_json

TELEMETRY_URL = os.environ.get(
    "IQTMUSIC_TELEMETRY_URL", "https://iqtmusic-server.onrender.com/telemetry"
).strip()


def _screen_resolution() -> str:
    try:
        import ctypes
        u = ctypes.windll.user32
        return f"{u.GetSystemMetrics(0)}x{u.GetSystemMetrics(1)}"
    except Exception:
        pass
    try:
        from PySide6.QtWidgets import QApplication
        s = QApplication.primaryScreen()
        if s:
            g = s.geometry()
            return f"{g.width()}x{g.height()}"
    except Exception:
        pass
    return ""


def maybe_send_startup_telemetry(
    *,
    base_dir: str,
    app_version: str,
    language: str,
    enabled: bool,
    url: str = TELEMETRY_URL,
) -> bool:
    """Send one anonymous startup ping per UTC day in a background thread."""
    if not enabled or not url:
        return False

    path = os.path.join(base_dir, "telemetry_state.json")
    state = safe_load_json(path, {})
    if not isinstance(state, dict):
        state = {}

    today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    if state.get("last_ping") == today:
        return False

    install_id = str(state.get("install_id") or "").strip()
    first_seen = str(state.get("first_seen") or "").strip()

    if not (16 <= len(install_id) <= 64):
        install_id = uuid.uuid4().hex
        first_seen = today
        state["install_id"] = install_id
        state["first_seen"] = first_seen
        safe_save_json(path, state)
    elif not first_seen:
        first_seen = today
        state["first_seen"] = first_seen
        safe_save_json(path, state)

    payload = {
        "event": "app_start",
        "install_id": install_id,
        "app_version": str(app_version or ""),
        "language": str(language or ""),
        "os": platform.system(),
        "os_version": platform.release(),
        "screen": _screen_resolution(),
        "packaged": bool(getattr(sys, "frozen", False)),
        "first_seen": first_seen,
    }

    def _send() -> None:
        try:
            r = requests.post(
                url,
                json=payload,
                headers={"User-Agent": f"iqtMusic/{app_version}"},
                timeout=3,
            )
            if 200 <= r.status_code < 300:
                s = safe_load_json(path, {})
                if not isinstance(s, dict):
                    s = {}
                s["install_id"] = install_id
                s["last_ping"] = today
                s["first_seen"] = first_seen
                safe_save_json(path, s)
        except Exception:
            pass

    threading.Thread(target=_send, name="iqtmusic-telemetry", daemon=True).start()
    return True
