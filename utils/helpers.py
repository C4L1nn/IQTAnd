import os
import sys
import json
import time
import logging
import hashlib
import platform
import tempfile
import subprocess
import threading
from collections import OrderedDict

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QByteArray
from PySide6.QtGui import QIcon, QPixmap, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

from core.constants import ICON_PATHS

log = logging.getLogger("iqtMusic")
_JSON_SAVE_LOCKS: dict[str, threading.Lock] = {}
_JSON_SAVE_LOCKS_GUARD = threading.Lock()


def _get_json_save_lock(path: str) -> threading.Lock:
    norm = os.path.normcase(os.path.abspath(path))
    with _JSON_SAVE_LOCKS_GUARD:
        lock = _JSON_SAVE_LOCKS.get(norm)
        if lock is None:
            lock = threading.Lock()
            _JSON_SAVE_LOCKS[norm] = lock
        return lock


# Path helpers
if getattr(sys, "frozen", False):
    BASE_PATH = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
else:
    BASE_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _resolve_vlc_dir(base_path: str) -> str:
    for candidate in (os.path.join(base_path, "vlc"), base_path):
        if os.path.isfile(os.path.join(candidate, "libvlc.dll")):
            return candidate
    return os.path.join(base_path, "vlc")


ICON_PATH = os.path.join(BASE_PATH, "iqticon.ico")
VLC_DIR = _resolve_vlc_dir(BASE_PATH)
VLC_PLUGINS = os.path.join(VLC_DIR, "plugins")
if os.path.isfile(os.path.join(VLC_DIR, "libvlc.dll")):
    os.environ["PATH"] = VLC_DIR + os.pathsep + os.environ.get("PATH", "")
if os.path.isdir(VLC_PLUGINS):
    os.environ["VLC_PLUGIN_PATH"] = VLC_PLUGINS


def get_app_dir(name: str) -> str:
    """Return the platform-specific app data directory."""
    system = platform.system()
    if system == "Windows":
        base = (
            os.environ.get("LOCALAPPDATA")
            or os.environ.get("APPDATA")
            or os.path.expanduser("~")
        )
    elif system == "Darwin":
        base = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(
            os.path.expanduser("~"), ".config"
        )
    path = os.path.join(base, name)
    os.makedirs(path, exist_ok=True)
    return path


def safe_load_json(path: str, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                return json.load(f)
        except Exception as e:
            log.warning("JSON okuma hatasi (%s): %s", path, e)
            # Bozuk dosyayı .bak olarak yedekle (veri kaybını önle)
            bak_path = path + ".bak"
            try:
                import shutil
                shutil.copy2(path, bak_path)
                log.info("Bozuk JSON yedeklendi: %s", bak_path)
            except Exception as bak_e:
                log.warning("JSON yedekleme basarisiz (%s): %s", bak_path, bak_e)
    return default


def safe_save_json(path: str, data) -> bool:
    tmp_path = ""
    try:
        dname = os.path.dirname(path)
        os.makedirs(dname, exist_ok=True)
        lock = _get_json_save_lock(path)
        with lock:
            fd, tmp_path = tempfile.mkstemp(dir=dname, suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as tmp:
                json.dump(data, tmp, ensure_ascii=False, indent=2)
                tmp.flush()
                try:
                    os.fsync(tmp.fileno())
                except Exception as _e:
                    log.debug("Sessiz hata: %s", _e)
            for attempt in range(4):
                try:
                    os.makedirs(dname, exist_ok=True)
                    os.replace(tmp_path, path)
                    tmp_path = ""
                    return True
                except PermissionError:
                    if attempt >= 3:
                        raise
                    time.sleep(0.05 * (attempt + 1))
                except FileNotFoundError:
                    if attempt >= 3:
                        raise
                    os.makedirs(dname, exist_ok=True)
                    time.sleep(0.03 * (attempt + 1))
    except Exception as e:
        log.error("JSON kaydetme hatasi (%s): %s", path, e)
        return False
    finally:
        if tmp_path:
            try:
                os.remove(tmp_path)
            except Exception as _e:
                log.debug("Sessiz hata: %s", _e)


def open_folder(path: str):
    """Cross-platform open folder."""
    try:
        system = platform.system()
        if system == "Windows":
            os.startfile(path)
        elif system == "Darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception as e:
        log.warning("Klasor acilamadi: %s", e)


def create_icon(name: str, color: str = "white", size: int = 24) -> QIcon:
    data = ICON_PATHS.get(name, "")
    if not data:
        return QIcon()
    if isinstance(data, dict):
        view_box = data.get("viewBox", "0 0 24 24")
        body = str(data.get("body", "") or "").format(color=color)
    else:
        view_box = "0 0 24 24"
        body = f'<path d="{data}" fill="{color}"/>'
    svg = (
        f'<svg viewBox="{view_box}" width="{size}" height="{size}" '
        f'xmlns="http://www.w3.org/2000/svg">'
        f"{body}</svg>"
    )
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    renderer.render(p)
    p.end()
    return QIcon(pix)


try:
    from shiboken6 import isValid as _shiboken_is_valid
except ImportError:
    _shiboken_is_valid = None


def qt_is_valid(obj) -> bool:
    """Return True if obj is a live Qt object (not deleted/destroyed).

    Uses shiboken6.isValid when available for an accurate C++ wrapper check.
    Falls back to a simple None check when shiboken6 is not installed.
    """
    if obj is None:
        return False
    if _shiboken_is_valid is not None:
        try:
            return _shiboken_is_valid(obj)
        except Exception:
            return False
    return True


_MOJIBAKE_MARKERS = ("Ã", "Â", "Ä", "Å", "Æ", "Ð", "Ñ", "â€", "â€“", "â€”", "â€¢")


def repair_mojibake_text(value: str) -> str:
    """Best-effort repair for common UTF-8/Latin-1 mojibake sequences.

    This is intentionally conservative: if the text does not contain the usual
    mojibake markers, it is returned unchanged.
    """
    text = str(value or "")
    if not text or not any(marker in text for marker in _MOJIBAKE_MARKERS):
        return text

    repaired = text
    for _ in range(2):
        if not any(marker in repaired for marker in _MOJIBAKE_MARKERS):
            break
        next_text = None
        for source_encoding in ("latin-1", "cp1252"):
            try:
                candidate = repaired.encode(source_encoding).decode("utf-8")
            except Exception:
                continue
            if candidate and candidate != repaired:
                next_text = candidate
                break
        if not next_text:
            break
        repaired = next_text
    return repaired
