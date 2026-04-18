"""Last.fm API istemcisi ve önbellekli yardımcılar."""
import html
import logging
import os
import re
import time
import threading
from collections import OrderedDict
from hashlib import sha1
from urllib.parse import quote
import requests

from core.i18n import normalize_language
from utils.helpers import safe_load_json, safe_save_json

log = logging.getLogger("iqtMusic")


class LastFMClient:
    API_URL = "https://ws.audioscrobbler.com/2.0/"
    CACHE_VERSION = "v4"

    def __init__(
        self,
        base_dir: str,
        api_key: str = "",
        session=None,
        ttl_seconds: int = 604800,
        preferred_language: str = "tr",
    ):
        self.api_key = str(api_key or "").strip()
        self.ttl_seconds = max(900, int(ttl_seconds or 86400))
        self._session = session or requests.Session()
        self._cache_dir = os.path.join(base_dir, "cache", "lastfm")
        self._preferred_language = "en" if normalize_language(preferred_language) == "en" else "tr"
        self._mem: OrderedDict[str, object] = OrderedDict()
        self._mem_lock = threading.Lock()
        self._mem_items = 256
        os.makedirs(self._cache_dir, exist_ok=True)

    def set_language(self, language: str):
        self._preferred_language = "en" if normalize_language(language) == "en" else "tr"

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def _cache_key(self, method: str, params: dict) -> str:
        parts = [self.CACHE_VERSION, method]
        for key in sorted(params):
            if key == "api_key":
                continue
            parts.append(f"{key}={params[key]}")
        return sha1("|".join(parts).encode("utf-8")).hexdigest()

    def _cache_path(self, method: str, params: dict) -> str:
        return os.path.join(self._cache_dir, f"{self._cache_key(method, params)}.json")

    def _mem_get(self, cache_key: str):
        with self._mem_lock:
            data = self._mem.get(cache_key)
            if data is not None:
                self._mem.move_to_end(cache_key)
            return data

    def _mem_set(self, cache_key: str, data):
        with self._mem_lock:
            self._mem[cache_key] = data
            self._mem.move_to_end(cache_key)
            while len(self._mem) > self._mem_items:
                self._mem.popitem(last=False)

    def _read_cache(self, path: str, allow_stale: bool = False):
        cached = safe_load_json(path, {})
        if not isinstance(cached, dict):
            return None
        fetched_at = float(cached.get("_fetched_at", 0) or 0)
        if fetched_at and (time.time() - fetched_at) < self.ttl_seconds:
            return cached.get("data")
        if allow_stale and "data" in cached:
            return cached.get("data")
        return None

    def _write_cache(self, path: str, data):
        safe_save_json(path, {"_fetched_at": time.time(), "data": data})

    def call(self, method: str, **params):
        if not self.enabled:
            return {}
        payload = dict(params)
        payload.update({
            "method": method,
            "api_key": self.api_key,
            "format": "json",
        })
        cache_key = self._cache_key(method, payload)
        mem_cached = self._mem_get(cache_key)
        if mem_cached is not None:
            return mem_cached
        cache_path = self._cache_path(method, payload)
        cached = self._read_cache(cache_path)
        if cached is not None:
            self._mem_set(cache_key, cached)
            return cached
        try:
            resp = self._session.get(self.API_URL, params=payload, timeout=8)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, dict) and data.get("error"):
                log.warning("Last.fm API hatasi (%s): %s", method, data.get("message"))
                stale = self._read_cache(cache_path, allow_stale=True)
                if stale is not None:
                    self._mem_set(cache_key, stale)
                return stale if stale is not None else {}
            self._write_cache(cache_path, data)
            self._mem_set(cache_key, data)
            return data
        except Exception as exc:
            log.warning("Last.fm istegi basarisiz (%s): %s", method, exc)
            stale = self._read_cache(cache_path, allow_stale=True)
            if stale is not None:
                self._mem_set(cache_key, stale)
            return stale if stale is not None else {}

    def _request(self, method: str, **params):
        return self.call(method, **params)

    def artist_info(self, artist: str, lang: str = "tr"):
        return self.call("artist.getinfo", artist=artist, lang=lang, autocorrect=1)

    def artist_similar(self, artist: str, limit: int = 12):
        return self.call("artist.getsimilar", artist=artist, limit=limit, autocorrect=1)

    def artist_top_albums(self, artist: str, limit: int = 12):
        return self.call("artist.gettopalbums", artist=artist, limit=limit, autocorrect=1)

    def artist_top_tracks(self, artist: str, limit: int = 12):
        return self.call("artist.gettoptracks", artist=artist, limit=limit, autocorrect=1)

    def artist_top_tags(self, artist: str):
        return self.call("artist.gettoptags", artist=artist, autocorrect=1)

    def artist_user_tags(self, artist: str, user: str):
        return self.call("artist.gettags", artist=artist, user=user, autocorrect=1)

    def track_info(self, artist: str, track: str, username: str | None = None):
        params = {"artist": artist, "track": track, "autocorrect": 1}
        if username:
            params["username"] = username
        return self.call("track.getinfo", **params)

    def track_similar(self, artist: str, track: str, limit: int = 20):
        return self.call("track.getsimilar", artist=artist, track=track, limit=limit, autocorrect=1)

    def track_top_tags(self, artist: str, track: str):
        return self.call("track.gettoptags", artist=artist, track=track)

    def track_user_tags(self, artist: str, track: str, user: str):
        return self.call("track.gettags", artist=artist, track=track, user=user, autocorrect=1)

    def album_info(self, artist: str, album: str, username: str | None = None):
        params = {"artist": artist, "album": album, "autocorrect": 1}
        if username:
            params["username"] = username
        return self.call("album.getinfo", **params)

    def album_search(self, album: str, limit: int = 20, page: int = 1):
        return self.call("album.search", album=album, limit=limit, page=page)

    def album_top_tags(self, artist: str, album: str):
        return self.call("album.gettoptags", artist=artist, album=album, autocorrect=1)

    def tag_top_tracks(self, tag: str, limit: int = 30, page: int = 1):
        return self.call("tag.gettoptracks", tag=tag, limit=limit, page=page)

    def tag_top_artists(self, tag: str, limit: int = 30, page: int = 1):
        return self.call("tag.gettopartists", tag=tag, limit=limit, page=page)

    def global_top_tags(self):
        return self.call("tag.gettoptags")

    def chart_top_tracks(self, limit: int = 20, page: int = 1):
        return self.call("chart.gettoptracks", limit=limit, page=page)

    def chart_top_artists(self, limit: int = 20, page: int = 1):
        return self.call("chart.gettopartists", limit=limit, page=page)

    def geo_top_tracks(self, country: str, limit: int = 20, page: int = 1):
        return self.call("geo.gettoptracks", country=country, limit=limit, page=page)

    def geo_top_artists(self, country: str, limit: int = 20, page: int = 1):
        return self.call("geo.gettopartists", country=country, limit=limit, page=page)

    def user_recent_tracks(self, user: str, limit: int = 20, page: int = 1):
        return self.call("user.getrecenttracks", user=user, limit=limit, page=page)

    def user_top_tracks(self, user: str, period: str = "overall", limit: int = 20, page: int = 1):
        return self.call("user.gettoptracks", user=user, period=period, limit=limit, page=page)

    def user_top_artists(self, user: str, period: str = "overall", limit: int = 20, page: int = 1):
        return self.call("user.gettopartists", user=user, period=period, limit=limit, page=page)

    def user_top_albums(self, user: str, period: str = "overall", limit: int = 20, page: int = 1):
        return self.call("user.gettopalbums", user=user, period=period, limit=limit, page=page)

    def user_library_artists(self, user: str, limit: int = 50, page: int = 1):
        return self.call("library.getartists", user=user, limit=limit, page=page)

    @staticmethod
    def _to_int(value, default: int = 0) -> int:
        try:
            return int(str(value).replace(",", "").strip())
        except Exception:
            return default

    @staticmethod
    def _clean_bio(text: str) -> str:
        raw = html.unescape(str(text or ""))
        raw = re.sub(r"<[^>]+>", " ", raw)
        raw = re.sub(r"\s+", " ", raw).strip()
        raw = re.sub(r"Read more on Last\.fm.*$", "", raw, flags=re.I).strip()
        return raw

    @staticmethod
    def _best_image(images) -> str:
        best = ""
        if not isinstance(images, list):
            return best
        for item in images:
            if not isinstance(item, dict):
                continue
            url = str(item.get("#text", "") or "").strip()
            if url:
                best = url
        if best.startswith("http://"):
            best = "https://" + best[len("http://"):]
        return best

    @staticmethod
    def _is_placeholder_image(url: str) -> bool:
        value = str(url or "").strip().lower()
        if not value:
            return True
        return (
            "2a96cbd8b46e442fc41c2b86b821562f" in value
            or "avatar170s" in value
            or "noimage" in value
            or value.endswith("/2a96cbd8b46e442fc41c2b86b821562f.png")
        )

    @staticmethod
    def _normalize_text(value: str) -> str:
        return re.sub(r"\s+", " ", str(value or "").strip().lower())

    def _artist_search_image(self, name: str) -> str:
        data = self._request("artist.search", artist=name, limit=5)
        matches = (((data or {}).get("results") or {}).get("artistmatches") or {}).get("artist", [])
        if isinstance(matches, dict):
            matches = [matches]
        target = self._normalize_text(name)
        for item in matches:
            if not isinstance(item, dict):
                continue
            candidate_name = self._normalize_text(item.get("name", ""))
            if candidate_name and candidate_name != target and target not in candidate_name:
                continue
            image_block = item.get("image", [])
            image = ""
            if isinstance(image_block, list):
                image = self._best_image(image_block)
            elif isinstance(image_block, dict):
                image = str(image_block.get("#text", "") or "").strip()
            elif isinstance(image_block, str):
                image = str(image_block or "").strip()
            if not image:
                image = str(item.get("image_medium", "") or item.get("image_small", "") or "").strip()
            if image and not self._is_placeholder_image(image):
                return image.replace("http://", "https://")
        return ""

    def _request_page(self, url: str) -> str:
        page_url = str(url or "").strip()
        if not page_url:
            return ""
        cache_key = self._cache_key("page.fetch", {"url": page_url})
        # Başarısız istek önbelleği: 1 saat içinde tekrar deneme
        _fail_key = "fail:" + cache_key
        _fail_cache = getattr(self, "_page_fail_cache", {})
        _fail_ts = _fail_cache.get(_fail_key, 0)
        if _fail_ts and (time.time() - _fail_ts) < 3600:
            return ""
        mem_cached = self._mem_get(cache_key)
        if isinstance(mem_cached, str):
            return mem_cached
        cache_path = self._cache_path("page.fetch", {"url": page_url})
        cached = self._read_cache(cache_path)
        if isinstance(cached, str) and cached:
            self._mem_set(cache_key, cached)
            return cached
        try:
            _headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "tr,en;q=0.9",
            }
            resp = self._session.get(page_url, timeout=8, headers=_headers)
            resp.raise_for_status()
            text = str(resp.text or "")
            self._write_cache(cache_path, text)
            self._mem_set(cache_key, text)
            return text
        except Exception as exc:
            log.warning("Last.fm sayfa istegi basarisiz: %s", exc)
            stale = self._read_cache(cache_path, allow_stale=True)
            if isinstance(stale, str) and stale:
                self._mem_set(cache_key, stale)
                return stale
            # Başarısız istekleri 1 saat süreyle belleğe al (tekrarlayan 406 hatalarını önle)
            _fail_key = "fail:" + cache_key
            _fail_cache = getattr(self, "_page_fail_cache", None)
            if _fail_cache is None:
                self._page_fail_cache = {}
                _fail_cache = self._page_fail_cache
            _fail_cache[_fail_key] = time.time()
            return ""

    def _artist_page_image(self, page_url: str, artist_name: str = "") -> str:
        if not page_url:
            fallback_name = str(artist_name or "").strip()
            if not fallback_name:
                return ""
            page_url = f"https://www.last.fm/music/{quote(fallback_name)}"
        html_text = self._request_page(page_url)
        if not html_text:
            return ""

        patterns = [
            r'<meta\s+property="og:image"\s+content="([^"]+)"',
            r'<meta\s+name="twitter:image"\s+content="([^"]+)"',
            r'background-image:\s*url\((?:&quot;|")?([^"\')]+)',
            r'"image"\s*:\s*"([^"]+)"',
        ]
        for pattern in patterns:
            match = re.search(pattern, html_text, flags=re.I)
            if not match:
                continue
            url = html.unescape(str(match.group(1) or "").strip())
            if not url:
                continue
            if url.startswith("//"):
                url = "https:" + url
            if url.startswith("http://"):
                url = "https://" + url[len("http://"):]
            if self._is_placeholder_image(url):
                continue
            return url
        return ""

    @staticmethod
    def _public_artist_url(name: str) -> str:
        clean = str(name or "").strip()
        if not clean:
            return ""
        return f"https://www.last.fm/music/{quote(clean)}"

    def _album_track_count(self, artist_name: str, album_name: str) -> int:
        if not artist_name or not album_name:
            return 0
        info = self.album_info(artist_name, album_name)
        album_info = info.get("album", {}) if isinstance(info, dict) else {}
        tracks = ((album_info.get("tracks") or {}).get("track")) if isinstance(album_info, dict) else None
        if isinstance(tracks, list):
            return len([t for t in tracks if isinstance(t, dict)])
        if isinstance(tracks, dict):
            return 1
        return 0

    def _track_image(self, artist_name: str, track_name: str) -> str:
        info = self.track_info(artist_name, track_name)
        track_info = info.get("track", {}) if isinstance(info, dict) else {}
        album_info = track_info.get("album", {}) if isinstance(track_info, dict) else {}
        image = self._best_image(album_info.get("image", []))
        if image:
            return image

        search = self.call("track.search", track=track_name, limit=6)
        matches = (((search or {}).get("results") or {}).get("trackmatches") or {}).get("track", [])
        if isinstance(matches, dict):
            matches = [matches]
        target_artist = self._normalize_text(artist_name)
        target_track = self._normalize_text(track_name)
        for item in matches:
            if not isinstance(item, dict):
                continue
            item_artist = self._normalize_text(item.get("artist", ""))
            item_track = self._normalize_text(item.get("name", ""))
            if item_track and target_track and item_track != target_track and target_track not in item_track:
                continue
            if item_artist and target_artist and item_artist != target_artist and target_artist not in item_artist:
                continue
            image = self._best_image(item.get("image", []))
            if image:
                return image
        return ""

    def get_artist_profile(self, name: str) -> dict:
        clean_name = str(name or "").strip()
        if not clean_name:
            return {}

        canonical_name = clean_name
        artist_info = {}
        top_block = {}
        top_albums_block = {}
        similar_block = {}
        tags_block = {}
        bio = ""

        if self.enabled:
            correction = self.call("artist.getcorrection", artist=clean_name)
            try:
                correction_artist = (((correction or {}).get("corrections") or {}).get("correction") or {}).get("artist") or {}
                canonical_name = str(correction_artist.get("name", "") or clean_name).strip() or clean_name
            except Exception:
                canonical_name = clean_name

            preferred_lang = "en" if self._preferred_language == "en" else "tr"
            fallback_lang = "tr" if preferred_lang == "en" else "en"

            info = self.artist_info(canonical_name, lang=preferred_lang)
            artist_info = info.get("artist", {}) if isinstance(info, dict) else {}
            bio = self._clean_bio(((artist_info.get("bio") or {}).get("summary", "")))
            if not bio:
                info_en = self.artist_info(canonical_name, lang=fallback_lang)
                artist_info_en = info_en.get("artist", {}) if isinstance(info_en, dict) else {}
                if artist_info_en:
                    bio = self._clean_bio(((artist_info_en.get("bio") or {}).get("summary", "")))
                    if not artist_info:
                        artist_info = artist_info_en
            top_tracks = self.artist_top_tracks(canonical_name, limit=10)
            top_albums = self.artist_top_albums(canonical_name, limit=10)
            similar = self.artist_similar(canonical_name, limit=8)
            top_tags = self.artist_top_tags(canonical_name)
            top_block = top_tracks.get("toptracks", {}) if isinstance(top_tracks, dict) else {}
            top_albums_block = top_albums.get("topalbums", {}) if isinstance(top_albums, dict) else {}
            similar_block = similar.get("similarartists", {}) if isinstance(similar, dict) else {}
            tags_block = top_tags.get("toptags", {}) if isinstance(top_tags, dict) else {}

        if not tags_block and isinstance(artist_info, dict):
            tags_block = artist_info.get("tags", {}) or {}

        tags_raw = []
        if isinstance(tags_block, dict):
            tags_raw = tags_block.get("tag", []) or []
        if isinstance(tags_raw, dict):
            tags_raw = [tags_raw]

        tracks_raw = top_block.get("track", []) if isinstance(top_block, dict) else []
        if isinstance(tracks_raw, dict):
            tracks_raw = [tracks_raw]

        albums_raw = top_albums_block.get("album", []) if isinstance(top_albums_block, dict) else []
        if isinstance(albums_raw, dict):
            albums_raw = [albums_raw]

        similar_raw = similar_block.get("artist", []) if isinstance(similar_block, dict) else []
        if isinstance(similar_raw, dict):
            similar_raw = [similar_raw]

        artist_url = str(artist_info.get("url", "") or "").strip() or self._public_artist_url(canonical_name)
        top_tracks_payload = []
        for track in tracks_raw:
            if not isinstance(track, dict):
                continue
            track_name = str(track.get("name", "") or "").strip()
            if not track_name:
                continue
            track_image = self._best_image(track.get("image", []))
            if not track_image:
                track_image = self._track_image(canonical_name, track_name)
            top_tracks_payload.append({
                "name": track_name,
                "playcount": self._to_int(track.get("playcount")),
                "listeners": self._to_int(track.get("listeners")),
                "image_url": track_image,
            })
            if len(top_tracks_payload) >= 8:
                break

        top_albums_payload = []
        for album in albums_raw:
            if not isinstance(album, dict):
                continue
            album_name = str(album.get("name", "") or "").strip()
            if not album_name:
                continue
            track_count = self._album_track_count(canonical_name, album_name)
            album_img = self._best_image(album.get("image", []))
            if self._is_placeholder_image(album_img):
                album_img = ""
            top_albums_payload.append({
                "name": album_name,
                "playcount": self._to_int(album.get("playcount")),
                "url": str(album.get("url", "") or "").strip(),
                "image_url": album_img,
                "track_count": track_count,
            })
            if len(top_albums_payload) >= 8:
                break

        image_url = self._best_image(artist_info.get("image", []))
        if self._is_placeholder_image(image_url):
            image_url = ""
        if not image_url:
            image_url = self._artist_search_image(canonical_name)
        if not image_url:
            image_url = self._artist_page_image(artist_url, canonical_name)

        # Benzer sanatçı resimleri — placeholder ise artist.search ile dene
        similar_artists_payload = []
        for artist in similar_raw:
            if not isinstance(artist, dict):
                continue
            sim_name = str(artist.get("name", "") or "").strip()
            if not sim_name:
                continue
            sim_img = self._best_image(artist.get("image", []))
            if self._is_placeholder_image(sim_img):
                sim_img = self._artist_search_image(sim_name)
            similar_artists_payload.append({
                "name": sim_name,
                "match": float(artist.get("match", 0) or 0),
                "url": str(artist.get("url", "") or "").strip(),
                "image_url": sim_img,
            })
            if len(similar_artists_payload) >= 8:
                break

        return {
            "name": artist_info.get("name") or canonical_name,
            "url": artist_url,
            "bio": bio,
            "image_url": image_url,
            "listeners": self._to_int(artist_info.get("stats", {}).get("listeners")),
            "playcount": self._to_int(artist_info.get("stats", {}).get("playcount")),
            "tags": [
                str(tag.get("name", "") or "").strip()
                for tag in tags_raw
                if isinstance(tag, dict) and str(tag.get("name", "") or "").strip()
            ][:8],
            "top_tracks": top_tracks_payload,
            "top_albums": top_albums_payload,
            "similar_artists": similar_artists_payload,
        }

    def get_artist_seed_terms(self, name: str) -> dict:
        profile = self.get_artist_profile(name)
        if not profile:
            return {"similar": [], "tags": []}
        return {
            "similar": [item["name"] for item in profile.get("similar_artists", [])[:5] if item.get("name")],
            "tags": [tag for tag in profile.get("tags", [])[:5] if tag],
        }

    def get_album_profile(self, artist: str, album: str) -> dict:
        clean_artist = str(artist or "").strip()
        clean_album = str(album or "").strip()
        if not clean_artist or not clean_album or not self.enabled:
            return {}

        data = self.album_info(clean_artist, clean_album)
        album_info = data.get("album", {}) if isinstance(data, dict) else {}
        tracks_raw = ((album_info.get("tracks") or {}).get("track")) if isinstance(album_info, dict) else []
        if isinstance(tracks_raw, dict):
            tracks_raw = [tracks_raw]

        image_url = self._best_image(album_info.get("image", []))
        wiki = self._clean_bio(((album_info.get("wiki") or {}).get("summary", "")))

        track_items = []
        for index, item in enumerate(tracks_raw or [], start=1):
            if not isinstance(item, dict):
                continue
            title = str(item.get("name", "") or "").strip()
            if not title:
                continue
            duration = self._to_int(item.get("duration"))
            rank = item.get("@attr", {}) if isinstance(item.get("@attr"), dict) else {}
            track_items.append({
                "name": title,
                "rank": self._to_int(rank.get("rank"), index),
                "duration_seconds": duration,
            })

        return {
            "name": str(album_info.get("name", "") or clean_album).strip() or clean_album,
            "artist": str(album_info.get("artist", "") or clean_artist).strip() or clean_artist,
            "url": str(album_info.get("url", "") or "").strip(),
            "image_url": image_url,
            "listeners": self._to_int(album_info.get("listeners")),
            "playcount": self._to_int(album_info.get("playcount")),
            "wiki": wiki,
            "track_count": len(track_items),
            "tracks": track_items,
        }
