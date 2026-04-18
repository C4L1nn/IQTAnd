import os
import time
import logging
import threading
import hashlib
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor

import requests
from yt_dlp import YoutubeDL
from PySide6.QtGui import QImage
from PySide6.QtCore import Qt

from utils.helpers import safe_load_json, safe_save_json

log = logging.getLogger("iqtMusic")


class DiskImageCache:
    def __init__(self, base_dir: str, max_mb: int = 200,
                 ttl_days: int = 7, mem_items: int = 256):
        self.max_bytes = max_mb * 1024 * 1024
        self.ttl_sec   = ttl_days * 86_400
        self.mem_items = max(32, mem_items)
        self.img_dir   = os.path.join(base_dir, "cache", "images")
        os.makedirs(self.img_dir, exist_ok=True)
        self._mem: OrderedDict = OrderedDict()
        self._inflight: set    = set()
        self._lock              = threading.Lock()
        self._last_evict        = 0.0
        self._evict_old()

    def _key_path(self, url: str, size: tuple) -> str:
        h = hashlib.sha1(f"{url}|{size[0]}x{size[1]}|v3".encode()).hexdigest()
        return os.path.join(self.img_dir, f"{h}.jpg")

    def _mem_get(self, url: str, size: tuple):
        k = (url, size)
        with self._lock:
            img = self._mem.get(k)
            if img is not None:
                self._mem.move_to_end(k)
            return img

    def _mem_set(self, url: str, size: tuple, img: QImage):
        k = (url, size)
        with self._lock:
            self._mem[k] = img
            self._mem.move_to_end(k)
            while len(self._mem) > self.mem_items:
                self._mem.popitem(last=False)

    def _scale_mode(self, size: tuple) -> Qt.AspectRatioMode:
        """Her zaman tam doldur (Discord gibi)."""
        return Qt.KeepAspectRatioByExpanding

    def get_or_load(self, url: str, size: tuple,
                    session: requests.Session) -> QImage | None:
        # 1. Bellek önbelleği — en hızlı yol, lock altında O(1)
        img = self._mem_get(url, size)
        if img is not None:
            return img

        local_path = str(url or "").strip()
        if local_path and os.path.isfile(local_path):
            img = QImage(local_path)
            if not img.isNull():
                mode = self._scale_mode(size)
                img = img.scaled(size[0], size[1], mode, Qt.SmoothTransformation)
                self._mem_set(url, size, img)
                return img

        # 2. Disk önbelleği — PERFORMANS İYİLEŞTİRMESİ:
        #    _key_path() URL + boyutu birlikte hash'ler, yani disk'teki dosya
        #    zaten o boyut için kaydedilmiştir. Artık diskten okurken
        #    SmoothTransformation uygulamıyoruz; dosyayı olduğu gibi yükleyip
        #    mem cache'e atıyoruz. Çok sayıda kart gösteriminde bu maliyeti
        #    tamamen sıfırlar.
        fp  = self._key_path(url, size)
        now = time.time()
        k   = (url, size)
        try:
            if os.path.exists(fp):
                if now - os.stat(fp).st_mtime <= self.ttl_sec:
                    img = QImage(fp)
                    if not img.isNull():
                        try:
                            os.utime(fp, None)
                        except Exception as _e:
                            log.debug("Sessiz hata: %s", _e)
                        # Disk'teki dosya zaten doğru boyutta — direkt kullan
                        self._mem_set(url, size, img)
                        return img
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)

        # 3. Ağdan indir; scale et; SCALED versiyonu diske kaydet.
        #    Bir sonraki çalıştırmada disk okuma (adım 2) anında hazır olur.
        with self._lock:
            if k in self._inflight:
                return None
            self._inflight.add(k)
        try:
            resp = session.get(url, timeout=6)
            resp.raise_for_status()
            img = QImage()
            img.loadFromData(resp.content)
            if img.isNull():
                return None
            mode = self._scale_mode(size)
            img = img.scaled(size[0], size[1], mode, Qt.SmoothTransformation)
            # Scaled versiyonu diske kaydet (ham veriyi değil!)
            img.save(fp, "JPG", 85)
            try:
                os.utime(fp, None)
            except Exception as _e:
                log.debug("Sessiz hata: %s", _e)
            self._mem_set(url, size, img)
            self._maybe_evict_old()
            return img
        except Exception as e:
            log.debug("Resim yüklenemedi: %s — %s", url, e)
            return None
        finally:
            with self._lock:
                self._inflight.discard(k)

    def _evict_old(self):
        try:
            self._last_evict = time.time()
            now   = time.time()
            files = []
            total = 0
            for fn in os.listdir(self.img_dir):
                fp = os.path.join(self.img_dir, fn)
                try:
                    st  = os.stat(fp)
                    age = now - st.st_mtime
                    if age > self.ttl_sec:
                        os.remove(fp)
                        continue
                    files.append((st.st_mtime, st.st_size, fp))
                    total += st.st_size
                except Exception as _e:
                    log.debug("Sessiz hata: %s", _e)
            files.sort()
            for mtime, size, fp in files:
                if total <= self.max_bytes:
                    break
                try:
                    os.remove(fp)
                    total -= size
                except Exception as _e:
                    log.debug("Sessiz hata: %s", _e)
        except Exception as e:
            log.debug("Önbellek temizleme hatası: %s", e)

    def _maybe_evict_old(self, min_interval_sec: int = 30):
        if time.time() - self._last_evict >= min_interval_sec:
            self._evict_old()


class LRUTTLCache:
    def __init__(self, max_items: int = 200, ttl_sec: int = 18000):
        self.max_items = max(10, max_items)
        self.ttl_sec   = max(10, ttl_sec)
        self._store: OrderedDict = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str):
        with self._lock:
            item = self._store.get(key)
            if not item:
                return None
            ts, val = item
            if time.time() - ts > self.ttl_sec:
                del self._store[key]
                return None
            self._store.move_to_end(key)
            return val

    def set(self, key: str, val):
        with self._lock:
            self._store[key] = (time.time(), val)
            self._store.move_to_end(key)
            while len(self._store) > self.max_items:
                self._store.popitem(last=False)

    def delete(self, key: str):
        with self._lock:
            self._store.pop(key, None)


class DiskMediaCache:
    def __init__(self, base_dir: str, max_mb: int = 500, workers: int = 1):
        self.max_bytes = max(64, max_mb) * 1024 * 1024
        self.media_dir = os.path.join(base_dir, "cache", "media")
        self.meta_file = os.path.join(self.media_dir, "media_cache.json")
        os.makedirs(self.media_dir, exist_ok=True)
        self._meta = safe_load_json(self.meta_file, {})
        self._lock = threading.RLock()
        self._active: set[str] = set()
        self._executor = ThreadPoolExecutor(max_workers=max(1, workers))
        self._last_evict = 0.0
        self._last_save = 0.0
        self._evict_old()

    def _save(self, force: bool = False):
        if not force and (time.time() - self._last_save) < 1.5:
            return
        os.makedirs(self.media_dir, exist_ok=True)
        with self._lock:
            snapshot = dict(self._meta)
        if safe_save_json(self.meta_file, snapshot):
            self._last_save = time.time()

    def _find_existing_path(self, vid: str) -> str | None:
        prefix = f"{vid}."
        try:
            for fn in os.listdir(self.media_dir):
                if not fn.startswith(prefix):
                    continue
                if fn.endswith((".part", ".tmp", ".ytdl")):
                    continue
                fp = os.path.join(self.media_dir, fn)
                if os.path.isfile(fp):
                    return fp
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
        return None

    def _record(self, vid: str, path: str, track: dict | None = None):
        if not path or not os.path.exists(path):
            return
        now = time.time()
        try:
            os.utime(path, None)
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
        size = 0
        try:
            size = os.path.getsize(path)
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
        with self._lock:
            old_title = self._meta.get(vid, {}).get("title", "")
            self._meta[vid] = {
                "path": path,
                "size": size,
                "last_access": now,
                "title": (track or {}).get("title", old_title),
            }
        self._save(force=track is not None)
        if track is not None:
            self._evict_old()
        else:
            self._maybe_evict_old()

    def touch(self, vid: str, path: str | None = None):
        path = path or self.get_path(vid, touch=False)
        if not path:
            return
        self._record(vid, path)

    def get_path(self, vid: str, touch: bool = True) -> str | None:
        if not vid:
            return None
        with self._lock:
            meta = dict(self._meta.get(vid, {}))
        path = meta.get("path", "")
        if not path or not os.path.exists(path):
            path = self._find_existing_path(vid)
            if not path:
                with self._lock:
                    self._meta.pop(vid, None)
                self._save(force=True)
                return None
            self._record(vid, path)
            return path
        if touch:
            self._record(vid, path)
        return path

    def has(self, vid: str) -> bool:
        return bool(self.get_path(vid, touch=False))

    def queue(self, track: dict, ydl_base_opts: dict | None = None):
        vid = (track or {}).get("videoId", "")
        if not vid or self.has(vid):
            return False
        with self._lock:
            if vid in self._active:
                return False
            self._active.add(vid)
        self._executor.submit(self._worker, dict(track), dict(ydl_base_opts or {}))
        return True

    def _worker(self, track: dict, ydl_base_opts: dict):
        vid = track.get("videoId", "")
        os.makedirs(self.media_dir, exist_ok=True)
        opts = {
            "outtmpl": os.path.join(self.media_dir, f"{vid}.%(ext)s"),
            "format": ydl_base_opts.get("format", "bestaudio[ext=m4a]/bestaudio/best"),
            "quiet": True,
            "no_warnings": True,
            "nocheckcertificate": True,
            "geo_bypass": True,
            "socket_timeout": ydl_base_opts.get("socket_timeout", 15),
            "cachedir": ydl_base_opts.get("cachedir"),
            "noplaylist": True,
            "retries": 2,
        }
        for key in ("extractor_args", "cookiesfrombrowser", "ffmpeg_location"):
            if ydl_base_opts.get(key):
                opts[key] = ydl_base_opts[key]
        try:
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(
                    f"https://www.youtube.com/watch?v={vid}",
                    download=True,
                )
                path = ydl.prepare_filename(info)
            if path and os.path.exists(path):
                self._record(vid, path, track)
        except Exception as e:
            log.debug("Medya cache indirilemedi (%s): %s", vid, e)
        finally:
            with self._lock:
                self._active.discard(vid)

    def _evict_old(self):
        self._last_evict = time.time()
        stale_vids = []
        valid = []
        total = 0
        with self._lock:
            snapshot = dict(self._meta)
            active = set(self._active)
        for vid, meta in snapshot.items():
            path = meta.get("path", "")
            if not path or not os.path.exists(path):
                stale_vids.append(vid)
                continue
            try:
                size = os.path.getsize(path)
            except Exception as _e:
                log.debug("Sessiz hata: %s", _e)
                size = meta.get("size", 0)
            last_access = meta.get("last_access", 0) or 0
            total += size
            valid.append((last_access, size, vid, path))
        valid.sort(key=lambda item: item[0])
        for _, size, vid, path in valid:
            if total <= self.max_bytes:
                break
            if vid in active:
                continue
            try:
                os.remove(path)
            except Exception as _e:
                log.debug("Sessiz hata: %s", _e)
            total -= size
            stale_vids.append(vid)
        if stale_vids:
            with self._lock:
                for vid in stale_vids:
                    self._meta.pop(vid, None)
            self._save(force=True)

    def _maybe_evict_old(self, min_interval_sec: int = 45):
        if time.time() - self._last_evict >= min_interval_sec:
            self._evict_old()

    def shutdown(self):
        try:
            self._save(force=True)
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
        try:
            self._executor.shutdown(wait=False, cancel_futures=True)
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
