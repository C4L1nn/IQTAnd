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
import sys
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
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

YDL_OPTS = {
    "format": "bestaudio/best",
    "quiet": True,
    "no_warnings": True,
    "extract_flat": False,
}

# Basit in-memory cache — aynı videoId için tekrar tekrar istek atmayı önler
_url_cache: dict[str, str] = {}
_cache_lock = threading.Lock()


def get_stream_url(video_id: str) -> str | None:
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
    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if parsed.path == "/health":
            self._send_json(200, {"status": "ok"})
        elif parsed.path == "/stream":
            self._handle_stream(params)
        elif parsed.path == "/search":
            self._handle_search(params)
        else:
            self._send_json(404, {"error": "Not found"})

    def _handle_stream(self, params):
        video_id = params.get("videoId", [None])[0]
        if not video_id:
            self._send_json(400, {"error": "videoId parameter required"})
            return
        print(f"[>] Stream: {video_id}")
        try:
            url = get_stream_url(video_id)
        except Exception as e:
            print(f"[FAIL] {video_id}: {e}")
            self._send_json(503, {"error": str(e)})
            return
        if url:
            print(f"[OK] {video_id[:12]} → {url[:60]}...")
            self._send_json(200, {"url": url})
        else:
            print(f"[FAIL] {video_id}: URL None")
            self._send_json(503, {"error": "URL could not be extracted"})

    def _handle_search(self, params):
        q = unquote_plus(params.get("q", [""])[0]).strip()
        if not q:
            self._send_json(400, {"error": "q parameter required"})
            return
        print(f"[>] Search: {q!r}")
        results = search_youtube_music(q)
        print(f"[OK] {len(results)} sonuc")
        self._send_json(200, results)

    def _send_json(self, code: int, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), StreamHandler)
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
