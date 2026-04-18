import os
import re
import sys
import shutil
import logging
import threading
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import QObject, Signal
from yt_dlp import YoutubeDL

from utils.helpers import safe_load_json, safe_save_json
from core.constants import YDL_FORMAT

log = logging.getLogger("iqtMusic")


def _find_ffmpeg() -> str:
    """
    FFmpeg yürütülebilir dosyasını otomatik olarak bul.
    Önce PATH'e, sonra yt-dlp paket dizinine ve yaygın Windows konumlarına bakılır.
    Bulunamazsa boş string döndürür.
    """
    # 1) Sistem PATH'inde var mı?
    if shutil.which("ffmpeg"):
        return ""  # boş = yt-dlp PATH'i kullanır (zaten bulacak)

    # 2) Uygulama klasörü içindeki bin/ klasörü (kullanıcının eklediği FFmpeg)
    try:
        # sys.argv[0] = ana betik; exe haline getirince sys.executable kullan
        exe_path = sys.executable if getattr(sys, "frozen", False) else os.path.abspath(sys.argv[0])
        candidates_dirs = [
            os.path.join(os.path.dirname(exe_path), "bin"),
            # PyInstaller 6+: data dosyaları _internal/ (sys._MEIPASS) altına kopyalanır
            os.path.join(getattr(sys, "_MEIPASS", ""), "bin"),
            os.path.join(os.getcwd(), "bin"),
        ]
        for app_bin in candidates_dirs:
            if not app_bin:
                continue
            for cand in ("ffmpeg.exe", "ffmpeg"):
                if os.path.isfile(os.path.join(app_bin, cand)):
                    return app_bin
    except Exception as _e:
        log.debug("Sessiz hata: %s", _e)

    # 3) yt-dlp paket dizininde bundled ffmpeg var mı?
    try:
        import yt_dlp as _ydlp
        # Frozen modda sys._MEIPASS altındaki yt_dlp dizinine bak
        if getattr(sys, "frozen", False):
            pkg_dir = getattr(sys, "_MEIPASS", "")
        else:
            pkg_dir = os.path.dirname(_ydlp.__file__)
        if pkg_dir:
            for cand in ("ffmpeg.exe", "ffmpeg", os.path.join("bin", "ffmpeg.exe"),
                         os.path.join("bin", "ffmpeg")):
                full = os.path.join(pkg_dir, cand)
                if os.path.isfile(full):
                    return os.path.dirname(full)
    except Exception as _e:
        log.debug("Sessiz hata: %s", _e)

    # 4) Windows yaygın konumlar
    common = [
        r"C:\ffmpeg\bin", r"C:\Program Files\ffmpeg\bin",
        r"C:\Program Files (x86)\ffmpeg\bin",
        os.path.expanduser(r"~\ffmpeg\bin"),
    ]
    for d in common:
        if os.path.isfile(os.path.join(d, "ffmpeg.exe")):
            return d

    return ""  # bulunamadı


class DownloadManager(QObject):
    progress_signal = Signal(str, int)
    finished_signal = Signal(dict)
    error_signal    = Signal(str, str)

    def __init__(self, base_dir: str):
        super().__init__()
        self.dl_dir    = os.path.join(base_dir, "downloads")
        self.meta_file = os.path.join(self.dl_dir, "downloads.json")
        os.makedirs(self.dl_dir, exist_ok=True)
        self._meta: dict       = safe_load_json(self.meta_file, {})
        self._executor         = ThreadPoolExecutor(max_workers=2)
        self._active: set[str] = set()
        self._futures: set     = set()
        self._lock             = threading.RLock()
        # İndirme formatı ve kalitesi (değiştirilebilir)
        self.dl_format  = "m4a"   # "m4a" | "mp3" | "flac" | "wav"
        self.dl_quality = "best"  # "128" | "192" | "320" | "best"

    def _track_future(self, future):
        with self._lock:
            self._futures.add(future)
        future.add_done_callback(self._discard_future)
        return future

    def _discard_future(self, future):
        with self._lock:
            self._futures.discard(future)

    def _save(self):
        with self._lock:
            snapshot = dict(self._meta)
        safe_save_json(self.meta_file, snapshot)

    def is_downloaded(self, vid: str) -> bool:
        with self._lock:
            known = vid in self._meta
        return known and os.path.exists(self.get_path(vid))

    def set_quality(self, fmt: str, quality: str):
        """İndirme formatı ve kalitesini ayarla (thread-safe)."""
        with self._lock:
            self.dl_format  = fmt
            self.dl_quality = quality

    @staticmethod
    def _safe_fname(s: str) -> str:
        """Dosya adında geçersiz karakterleri temizle."""
        return re.sub(r'[\\/*?:"<>|]', "", s).strip()

    def _track_fname(self, track: dict) -> str:
        """Şarkı için 'Sanatçı - Başlık' formatında dosya adı üret."""
        title  = self._safe_fname(track.get("title", "") or "")
        arts   = track.get("artists") or []
        if arts:
            art = arts[0].get("name", "") if isinstance(arts[0], dict) else str(arts[0])
        else:
            art = ""
        art = self._safe_fname(art)
        if art and title:
            return f"{art} - {title}"
        return title or track.get("videoId", "track")

    def get_path(self, vid: str) -> str:
        with self._lock:
            meta = self._meta.get(vid, {})
        fname = meta.get("_filename", "")
        # Önce meta'daki dosya adıyla ara
        if fname:
            for ext in ("m4a", "mp3", "flac", "wav", "webm", "opus"):
                p = os.path.join(self.dl_dir, f"{fname}.{ext}")
                if os.path.exists(p):
                    return p
        # Yedek: eski vid tabanlı isimle ara
        for ext in ("m4a", "mp3", "flac", "wav", "webm", "opus"):
            p = os.path.join(self.dl_dir, f"{vid}.{ext}")
            if os.path.exists(p):
                return p
        return os.path.join(self.dl_dir, f"{fname or vid}.m4a")

    def start(self, track: dict):
        vid = track.get("videoId", "")
        if not vid:
            return
        with self._lock:
            if vid in self._active:
                return
            # Meta'da kayıtlı ama dosya silinmişse kaydı temizle, tekrar indir
            if vid in self._meta and not os.path.exists(self.get_path(vid)):
                log.info("İndirilen dosya bulunamadı, tekrar indiriliyor: %s", vid)
                del self._meta[vid]
            elif vid in self._meta:
                return
            self._active.add(vid)
        self._track_future(self._executor.submit(self._worker, track))

    def _worker(self, track: dict):
        vid  = track["videoId"]
        with self._lock:
            fmt  = self.dl_format
            qual = self.dl_quality

        def _hook(d):
            if d["status"] == "downloading":
                pct_str = d.get("_percent_str", "0%").strip().replace("%", "")
                try:
                    pct = int(float(pct_str))
                    self.progress_signal.emit(vid, pct)
                except Exception as _e:
                    log.debug("Sessiz hata: %s", _e)

        ffmpeg_loc = _find_ffmpeg()

        # Sanatçı - Başlık formatında dosya adı
        fname = self._track_fname(track)

        _base_opts = {
            "outtmpl":            os.path.join(self.dl_dir, f"{fname}.%(ext)s"),
            "quiet":              True,
            "no_warnings":        True,
            "nocheckcertificate": True,
            "geo_bypass":         True,
            "retries":            3,
            "progress_hooks":     [_hook],
            # Streaming ile aynı istemci: giriş gerektirmeyen tv_embedded →
            # android → web fallback zinciri. Bot tespitini atlar.
            "extractor_args":     {"youtube": {"player_client": ["tv_embedded", "android", "web"]}},
        }
        if ffmpeg_loc:
            _base_opts["ffmpeg_location"] = ffmpeg_loc

        if fmt in ("mp3", "flac", "wav"):
            bitrate = qual if (fmt == "mp3" and qual != "best") else "0"
            pp: dict = {"key": "FFmpegExtractAudio", "preferredcodec": fmt}
            if fmt == "mp3":
                pp["preferredquality"] = bitrate
            opts = {
                **_base_opts,
                "format": YDL_FORMAT,
                "postprocessors": [pp],
            }
        else:  # m4a (varsayılan)
            opts = {
                **_base_opts,
                "format": f"bestaudio[ext=m4a]/{YDL_FORMAT}",
            }
        try:
            with YoutubeDL(opts) as ydl:
                ydl.download([f"https://www.youtube.com/watch?v={vid}"])
            with self._lock:
                self._meta[vid] = {**track, "_filename": fname}
            self._save()
            self.progress_signal.emit(vid, 100)
            self.finished_signal.emit(track)
        except Exception as e:
            log.error("İndirme hatası (%s): %s", vid, e)
            self.error_signal.emit(vid, str(e))
        finally:
            with self._lock:
                self._active.discard(vid)

    def delete(self, vid: str) -> bool:
        with self._lock:
            if vid not in self._meta or vid in self._active:
                return False
        p = self.get_path(vid)
        try:
            if os.path.exists(p):
                os.remove(p)
        except Exception as e:
            log.warning("Dosya silinirken hata: %s", e)
        with self._lock:
            self._meta.pop(vid, None)
        self._save()
        return True

    def all_tracks(self) -> list:
        with self._lock:
            return list(self._meta.values())

    def reorder_tracks(self, ordered_tracks: list):
        with self._lock:
            remaining = dict(self._meta)
            reordered = {}
            for track in ordered_tracks:
                vid = str(track.get("videoId", "") or "").strip()
                if not vid or vid not in remaining:
                    continue
                reordered[vid] = remaining.pop(vid)
            for vid, meta in remaining.items():
                reordered[vid] = meta
            self._meta = reordered
        self._save()

    def shutdown(self):
        """Aktif indirmeleri bekleyerek temiz kapat (dosya bozulmasını önle)."""
        import concurrent.futures
        with self._lock:
            pending = [f for f in self._futures if not f.done()]
        # Önce yeni görev kabulünü durdur
        self._executor.shutdown(wait=False, cancel_futures=False)
        # Çalışan worker'ların en fazla 10 saniye içinde bitmesini bekle
        try:
            concurrent.futures.wait(pending, timeout=10)
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
