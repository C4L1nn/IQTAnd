"""
iqtMusic Android Stream Server
================================
Android telefon bu sunucuya USB ADB tüneli üzerinden bağlanır:
    adb reverse tcp:5001 tcp:5001

Endpoints:
    GET /stream?videoId=XXX   → {"url": "..."}
    GET /search?q=SORGU        → [{"id","title","artist","album","durationLabel","coverUrl","videoId"}, ...]

Çalıştır:
    python stream_server.py

Durdurmak için: Ctrl+C
"""
import json
import os
import re
import shutil
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote_plus

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from yt_dlp import YoutubeDL
    print("[OK] yt-dlp bulundu")
except ImportError:
    print("[HATA] yt-dlp bulunamadi. 'pip install yt-dlp' calistir.")
    sys.exit(1)

try:
    from ytmusicapi import YTMusic
    _yt = YTMusic()
    print("[OK] ytmusicapi bulundu")
except Exception as e:
    _yt = None
    print(f"[UYARI] ytmusicapi kullanilamiyor: {e} — arama devre disi")

PORT = int(os.environ.get("PORT", 5001))
SERVER_TOKEN = os.environ.get("IQTMUSIC_SERVER_TOKEN", "").strip()
ENABLE_DEBUG = os.environ.get("IQTMUSIC_ENABLE_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}
VERBOSE_ERRORS = os.environ.get("IQTMUSIC_VERBOSE_ERRORS", "").strip().lower() in {"1", "true", "yes", "on"}
RATE_LIMIT_MAX = int(os.environ.get("IQTMUSIC_RATE_LIMIT_MAX", "120"))
RATE_LIMIT_WINDOW = int(os.environ.get("IQTMUSIC_RATE_LIMIT_WINDOW", "60"))
TELEMETRY_ENABLED = os.environ.get("IQTMUSIC_TELEMETRY_ENABLED", "1").strip().lower() not in {"0", "false", "no", "off"}
UPSTASH_URL   = os.environ.get("UPSTASH_REDIS_REST_URL", "").strip()
UPSTASH_TOKEN = os.environ.get("UPSTASH_REDIS_REST_TOKEN", "").strip()
VIDEO_ID_RE   = re.compile(r"^[A-Za-z0-9_-]{6,20}$")
INSTALL_ID_RE = re.compile(r"^[A-Za-z0-9_-]{16,64}$")

# YouTube cookie dosyası — Render Secret File olarak yüklenir
# /etc/secrets/ read-only olduğu için /tmp/'a kopyalanır
_SECRET_COOKIES = "/etc/secrets/cookies.txt"
_LOCAL_COOKIES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookies.txt")
_TMP_COOKIES = "/tmp/yt_cookies.txt"

def _find_cookies_file() -> str | None:
    source = None
    if os.path.isfile(_SECRET_COOKIES):
        source = _SECRET_COOKIES
    elif os.path.isfile(_LOCAL_COOKIES):
        source = _LOCAL_COOKIES

    if source is None:
        print("[UYARI] cookies.txt bulunamadi — stream'ler basarisiz olabilir")
        return None

    try:
        shutil.copy2(source, _TMP_COOKIES)
        os.chmod(_TMP_COOKIES, 0o600)
        print(f"[OK] Cookies kopyalandi: {source} -> {_TMP_COOKIES}")
        return _TMP_COOKIES
    except Exception as e:
        print(f"[HATA] Cookies kopyalanamadi: {e}")
        return None

_COOKIES_FILE = _find_cookies_file()

YDL_OPTS: dict = {
    "format": "bestaudio/best",
    "quiet": True,
    "no_warnings": True,
    "noplaylist": True,
    "extract_flat": False,
    "extractor_args": {
        "youtube": {
            # Web tabanli client'lar artik sikca PO token gerektiriyor.
            # Stream server'da audio odakli ve daha dayanikli client'lari tercih ediyoruz.
            "player_client": ["ios", "android_vr", "tv"],
        }
    },
}
if _COOKIES_FILE:
    YDL_OPTS["cookiefile"] = _COOKIES_FILE

# Basit in-memory cache — aynı videoId için tekrar tekrar istek atmayı önler
_url_cache: dict[str, str] = {}
_cache_lock = threading.Lock()
_stream_waiters: dict[str, dict] = {}
_stream_waiters_lock = threading.Lock()
_prefetching: set[str] = set()
_prefetch_lock = threading.Lock()
_prefetch_pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix="iqt-stream-prefetch")
_rate_lock = threading.Lock()
_rate_hits: dict[str, list[float]] = {}


def _public_error(exc: Exception | str) -> str:
    if VERBOSE_ERRORS:
        return str(exc)
    return "Stream service unavailable"


def _valid_video_id(video_id: str) -> bool:
    return bool(VIDEO_ID_RE.match(str(video_id or "").strip()))


def _safe_url_label(raw_url: str) -> str:
    try:
        parsed = urlparse(raw_url)
        path = parsed.path or ""
        if len(path) > 28:
            path = path[:28] + "..."
        return f"{parsed.netloc}{path}"
    except Exception:
        return "<stream-url>"


def _clean_str(value, max_len: int) -> str:
    text = "".join(ch for ch in str(value or "").strip() if ch.isprintable())
    return text[:max_len]


def _upstash(cmd: list) -> None:
    if not UPSTASH_URL:
        return
    try:
        import requests as _req
        _req.post(
            UPSTASH_URL,
            headers={"Authorization": f"Bearer {UPSTASH_TOKEN}"},
            json=cmd,
            timeout=3,
        )
    except Exception:
        pass


def _record_ping(install_id: str) -> None:
    today = datetime.now(timezone.utc).date().isoformat()
    _upstash(["SADD", "iqt:all", install_id])
    _upstash(["SADD", f"iqt:day:{today}", install_id])
    _upstash(["EXPIRE", f"iqt:day:{today}", 86400 * 35])


def _extract_stream_url(video_id: str) -> str | None:
    with _cache_lock:
        if video_id in _url_cache:
            return _url_cache[video_id]
    try:
        with YoutubeDL(YDL_OPTS) as ydl:
            info = ydl.extract_info(
                f"https://www.youtube.com/watch?v={video_id}",
                download=False,
            )

        # Direkt URL'yi bul
        url = info.get("url")

        # Yoksa requested_formats içinde ara
        if not url and info.get("requested_formats"):
            for fmt in info["requested_formats"]:
                if fmt.get("url"):
                    url = fmt["url"]
                    break

        # Yoksa formats listesinde en iyi audio'yu bul
        if not url and info.get("formats"):
            audio_fmts = [
                f for f in info["formats"]
                if f.get("url") and f.get("vcodec") in ("none", None)
            ]
            if audio_fmts:
                best = max(audio_fmts, key=lambda x: x.get("abr") or x.get("tbr") or 0)
                url = best["url"]

        if url:
            with _cache_lock:
                _url_cache[video_id] = url
        else:
            print(f"[HATA] stream {video_id}: URL bulunamadi, mevcut formatlar: "
                  f"{[f.get('format_id') for f in info.get('formats', [])][:5]}")
        return url
    except Exception as e:
        print(f"[HATA] stream {video_id}: {e}")
        raise  # caller'a ilet


def get_stream_url(video_id: str) -> str | None:
    if not video_id:
        return None

    with _cache_lock:
        cached = _url_cache.get(video_id)
    if cached:
        return cached

    owner = False
    with _stream_waiters_lock:
        waiter = _stream_waiters.get(video_id)
        if waiter is None:
            waiter = {"event": threading.Event(), "url": None, "error": None}
            _stream_waiters[video_id] = waiter
            owner = True

    if owner:
        try:
            waiter["url"] = _extract_stream_url(video_id)
            return waiter["url"]
        except Exception as e:
            waiter["error"] = e
            raise
        finally:
            waiter["event"].set()
            with _stream_waiters_lock:
                _stream_waiters.pop(video_id, None)

    waiter["event"].wait(25)
    if waiter.get("url"):
        return waiter["url"]
    if waiter.get("error"):
        raise waiter["error"]
    return None


def schedule_prefetch(video_ids: list[str], limit: int = 3) -> list[str]:
    scheduled: list[str] = []

    for raw_id in video_ids:
        video_id = str(raw_id or "").strip()
        if not video_id:
            continue

        with _cache_lock:
            if video_id in _url_cache:
                continue
        with _stream_waiters_lock:
            if video_id in _stream_waiters:
                continue
        with _prefetch_lock:
            if video_id in _prefetching:
                continue
            _prefetching.add(video_id)

        def _task(vid=video_id):
            try:
                get_stream_url(vid)
            except Exception as e:
                print(f"[UYARI] prefetch {vid}: {e}")
            finally:
                with _prefetch_lock:
                    _prefetching.discard(vid)

        _prefetch_pool.submit(_task)
        scheduled.append(video_id)
        if len(scheduled) >= limit:
            break

    return scheduled


def _fmt_duration(seconds) -> str:
    try:
        s = int(seconds)
        return f"{s // 60}:{s % 60:02d}"
    except Exception:
        return "0:00"


def search_youtube_music(query: str, limit: int = 20) -> list[dict]:
    if _yt is None:
        return []
    try:
        results = _yt.search(query, filter="songs", limit=limit)
        tracks = []
        for r in results:
            vid = r.get("videoId") or ""
            if not vid:
                continue
            artists = r.get("artists") or []
            artist = artists[0].get("name", "") if artists else ""
            album_obj = r.get("album") or {}
            album = album_obj.get("name", "") if album_obj else ""
            thumbnails = r.get("thumbnails") or []
            cover = thumbnails[-1].get("url", "") if thumbnails else ""
            duration_s = r.get("duration_seconds") or 0
            tracks.append({
                "id": f"yt-{vid}",
                "title": r.get("title", ""),
                "artist": artist,
                "album": album,
                "durationLabel": _fmt_duration(duration_s),
                "coverUrl": cover,
                "videoId": vid,
            })
        return tracks
    except Exception as e:
        print(f"[HATA] search '{query}': {e}")
        return []


class StreamHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path != "/telemetry":
            self._send_json(404, {"error": "Not found"})
            return
        if self._is_rate_limited():
            self._send_json(429, {"error": "Too many requests"})
            return
        self._handle_telemetry()

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if parsed.path == "/health":
            self._send_json(200, {"status": "ok", "v": 2, "cookies_loaded": bool(_COOKIES_FILE)})
            return

        if not self._check_access():
            return

        if self._is_rate_limited():
            self._send_json(429, {"error": "Too many requests"})
            return

        if parsed.path == "/debug":
            if not ENABLE_DEBUG:
                self._send_json(404, {"error": "Not found"})
                return
            self._handle_debug(params)
            return
        if parsed.path == "/prefetch":
            self._handle_prefetch(params)
            return
        if parsed.path == "/stream":
            self._handle_stream(params)
            return
        if parsed.path == "/search":
            self._handle_search(params)
            return
        self._send_json(404, {"error": "Not found"})

    def _client_ip(self) -> str:
        forwarded = self.headers.get("X-Forwarded-For", "")
        if forwarded:
            return forwarded.split(",", 1)[0].strip()
        return self.client_address[0] if self.client_address else "unknown"

    def _check_access(self) -> bool:
        if not SERVER_TOKEN:
            return True
        if self._auth_token() == SERVER_TOKEN:
            return True
        self._send_json(401, {"error": "Unauthorized"})
        return False

    def _auth_token(self) -> str:
        auth = self.headers.get("Authorization", "")
        token = ""
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()
        return token or self.headers.get("X-IQTMusic-Token", "").strip()

    def _is_rate_limited(self) -> bool:
        if RATE_LIMIT_MAX <= 0 or RATE_LIMIT_WINDOW <= 0:
            return False
        now = time.monotonic()
        cutoff = now - RATE_LIMIT_WINDOW
        ip = self._client_ip()
        with _rate_lock:
            hits = [ts for ts in _rate_hits.get(ip, []) if ts >= cutoff]
            limited = len(hits) >= RATE_LIMIT_MAX
            if not limited:
                hits.append(now)
            _rate_hits[ip] = hits
            for key in list(_rate_hits.keys()):
                if key != ip and not [ts for ts in _rate_hits[key] if ts >= cutoff]:
                    _rate_hits.pop(key, None)
        return limited

    def _handle_debug(self, params):
        video_id = params.get("videoId", ["4NRXx6U8ABQ"])[0]
        if not _valid_video_id(video_id):
            self._send_json(400, {"error": "Invalid videoId"})
            return
        opts = {**YDL_OPTS, "format": None, "listformats": True, "quiet": False}
        try:
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
            fmts = [
                {"id": f.get("format_id"), "ext": f.get("ext"), "abr": f.get("abr"), "vcodec": f.get("vcodec")}
                for f in (info.get("formats") or [])
            ]
            self._send_json(200, {"cookies_loaded": bool(_COOKIES_FILE), "format_count": len(fmts), "formats": fmts[:20]})
        except Exception as e:
            self._send_json(503, {"cookies_loaded": bool(_COOKIES_FILE), "error": _public_error(e)})

    def _handle_stream(self, params):
        video_id = params.get("videoId", [None])[0]
        if not video_id:
            self._send_json(400, {"error": "videoId parameter required"})
            return
        if not _valid_video_id(video_id):
            self._send_json(400, {"error": "Invalid videoId"})
            return
        print(f"[>] Stream: {video_id}")
        try:
            url = get_stream_url(video_id)
        except Exception as e:
            print(f"[FAIL] {video_id}: {e}")
            self._send_json(503, {"error": _public_error(e)})
            return
        if url:
            print(f"[OK] {video_id[:12]} -> {_safe_url_label(url)}")
            self._send_json(200, {"url": url})
        else:
            print(f"[FAIL] {video_id}: URL None")
            self._send_json(503, {"error": "URL could not be extracted"})

    def _handle_prefetch(self, params):
        raw_ids = list(params.get("videoId", []))
        raw_ids.extend(
            item.strip()
            for group in params.get("videoIds", [])
            for item in group.split(",")
        )
        raw_ids = [video_id for video_id in raw_ids if _valid_video_id(video_id)]
        queued = schedule_prefetch(raw_ids)
        self._send_json(202, {"queued": queued, "count": len(queued)})

    def _handle_search(self, params):
        q = unquote_plus(params.get("q", [""])[0]).strip()
        if not q:
            self._send_json(400, {"error": "q parameter required"})
            return
        if len(q) > 120:
            self._send_json(400, {"error": "q parameter too long"})
            return
        print(f"[>] Search: {q!r}")
        results = search_youtube_music(q)
        schedule_prefetch([item.get("videoId", "") for item in results[:3]], limit=3)
        print(f"[OK] {len(results)} sonuc")
        self._send_json(200, results)

    def _handle_telemetry(self):
        if not TELEMETRY_ENABLED:
            self._send_json(404, {"error": "Not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(min(length, 4096))
            payload = json.loads(raw.decode("utf-8"))
        except Exception:
            self._send_json(400, {"error": "Invalid request"})
            return
        install_id = _clean_str(payload.get("install_id"), 64)
        if not INSTALL_ID_RE.match(install_id):
            self._send_json(400, {"error": "Invalid install_id"})
            return
        threading.Thread(target=_record_ping, args=(install_id,), daemon=True).start()
        self._send_json(202, {"ok": True})

    def _send_json(self, code: int, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print(f"[HTTP] {self.address_string()} - {fmt % args}")


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", PORT), StreamHandler)
    print(f"\n[iqtMusic Stream Server] http://0.0.0.0:{PORT}")
    print(f"[iqtMusic Stream Server] ADB tunnel: adb reverse tcp:5001 tcp:5001")
    print("[iqtMusic Stream Server] Ctrl+C ile durdur\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[Durduruldu]")
else:
    # Gunicorn / WSGI desteği yok; sadece doğrudan çalıştırma desteklenir.
    pass
