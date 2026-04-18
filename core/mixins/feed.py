"""Mixin for Feed functionality."""
import logging
import re
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

log = logging.getLogger("iqtMusic")

from core.constants import BG_CARD, BG_CARD_HOVER, BG_ELEVATED, BORDER_COLOR, TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY
from core.theme import get_accent
from utils.helpers import create_icon

from PySide6.QtGui import QColor, QCursor
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout
)
from PySide6.QtCore import Qt
import core.constants as _C
from core.geo import build_region_feed_spec
from ui.widgets import AnimatedCard, TrackCoverWidget, ClickableFrame

class FeedMixin:

    @property
    def _feed_pool(self) -> ThreadPoolExecutor:
        """
        PERFORMANS: Feed sorguları için kalıcı thread havuzu.

        Önceki tasarımda her çağrıda `with ThreadPoolExecutor(max_workers=6)`
        bloğu açılıp kapanıyordu; bu 6 thread'i her seferinde oluşturup yok
        etmek demek. Kalıcı havuz bu overhead'i tamamen ortadan kaldırır.
        max_workers=3 yeterli: YTMusic istekleri I/O bound ama çok fazla
        thread ağ bant genişliğini değil sadece CPU ve belleği tüketir.
        """
        pool = getattr(self, "_feed_pool_instance", None)
        if pool is None:
            pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix="feed")
            self._feed_pool_instance = pool
        return pool

    def _home_pool_tracks(self) -> list:
        pool = []
        if self.history:
            pool.extend(self.history[:5])
        if self.favorites:
            pool.extend(self.favorites[:5])
        if self.dl.all_tracks():
            pool.extend(self.dl.all_tracks()[:5])
        seen, uniq = set(), []
        for t in pool:
            vid = t.get("videoId", "")
            if vid and vid not in seen:
                seen.add(vid)
                t["artist"] = self._artist_str(t)
                uniq.append(t)
        return uniq

    # ══════════════════════════════════════════════════════════════════════════
    # TREND SORGULARI VE FİLTRELEME
    # ══════════════════════════════════════════════════════════════════════════

    def _filter_tracks(self, tracks: list) -> list:
        """
        Home sayfasındaki trend bölümler için gelen sonuçları filtrele.
        Bazı arama sorguları 2 saatlik videolar, yapay zeka şarkıları veya
        'mix' gibi uzun çalma listeleri içerebiliyor. Bu fonksiyon, şarkı
        olmayan veya aşırı uzun olan sonuçları filtreler. Özellikle şunları
        eler:

        - Süresi 10 dakikadan (600 saniye) uzun videolar
        - Başlıkta "remix", "mix", "medley", "hour", "video" veya "AI"
          gibi kelimeler içeren sonuçlar (küçük harfe dönüştürülmüş olarak)

        Args:
            tracks: YTM arama sonuç listesi

        Returns:
            Filtrelenmiş sonuç listesi
        """
        filtered = []
        for t in tracks:
            title = t.get("title", "").lower()
            dur   = t.get("duration_seconds")
            result_type = str(t.get("resultType", "") or "").lower()
            if result_type in {"playlist", "album", "artist", "station", "podcast", "episode", "profile"}:
                continue
            # Şarkı süresi tanımlı ise çok kısa ve çok uzun sonuçları ele
            if dur is not None and (dur < 60 or dur > 600):
                continue
            # İstenmeyen anahtar kelimelerden herhangi biri varsa atla
            unwanted = (
                "remix", "mix", "medley", "hour", " video", "ai",
                "sped up", "slowed", "reverb", "karaoke", "cover",
                "lyrics", "lyric video", "8d", "bass boosted",
                "fan made", "fanmade", "playlist", "full album",
            )
            if any(u in title for u in unwanted):
                continue
            filtered.append(t)
        return filtered

    def _looks_turkish_text(self, text: str) -> bool:
        if not text:
            return False
        hay = f" {text.lower()} "
        if any(ch in hay for ch in "çğıöşü"):
            return True
        hints = (
            " bir ", " sen ", " ben ", " gece ", " bana ", " beni ",
            " gibi ", " ask ", " aşk ", " yol ", " yine ", " hadi ",
            " sev ", " yok ", " var ", " kalb", " göz",
        )
        return sum(1 for token in hints if token in hay) >= 2

    def _normalize_feed_text(self, text: str) -> str:
        if not text:
            return ""
        table = str.maketrans({
            "ç": "c", "Ç": "c",
            "ğ": "g", "Ğ": "g",
            "ı": "i", "İ": "i",
            "ö": "o", "Ö": "o",
            "ş": "s", "Ş": "s",
            "ü": "u", "Ü": "u",
        })
        return " ".join(str(text).translate(table).lower().split())

    def _feed_text_blobs(self, track: dict) -> tuple[str, str]:
        title = str(track.get("title", "") or "")
        artist = self._artist_str(track) or ""
        album = ""
        album_obj = track.get("album")
        if isinstance(album_obj, dict):
            album = album_obj.get("name", "") or ""
        elif isinstance(album_obj, str):
            album = album_obj
        category = str(track.get("category", "") or "")
        combined = " ".join(part for part in (title, artist, album, category) if part)
        return self._normalize_feed_text(combined), self._normalize_feed_text(artist)

    def _match_feed_tokens(self, haystack: str, tokens) -> list[str]:
        hits = []
        for token in list(tokens or ()):
            norm = self._normalize_feed_text(token)
            if norm and norm in haystack:
                hits.append(norm)
        return hits

    def _feed_int(self, value) -> int:
        try:
            if isinstance(value, bool):
                return int(value)
            return int(str(value).strip())
        except Exception:
            pass
        digits = re.sub(r"\D+", "", str(value or ""))
        try:
            return int(digits) if digits else 0
        except Exception:
            return 0

    def _extract_feed_year(self, value) -> int:
        if value is None:
            return 0
        if isinstance(value, int):
            year = int(value)
            return year if 1900 <= year <= (datetime.now().year + 1) else 0
        text = str(value or "").strip()
        if not text:
            return 0
        match = re.search(r"(19|20)\d{2}", text)
        if not match:
            return 0
        year = self._feed_int(match.group(0))
        return year if 1900 <= year <= (datetime.now().year + 1) else 0

    def _track_live_meta(self, track: dict) -> dict:
        vid = str((track or {}).get("videoId") or "").strip()
        if not vid:
            return {}
        cache_key = f"__feed_track_meta::{vid}"
        cached = self._home_cache.get(cache_key)
        now = time.time()
        if cached and (now - cached[0]) < max(self._home_cache_ttl, 21600):
            return dict(cached[1] or {})

        payload = self._yt_get_song(vid)
        video = payload.get("videoDetails") or {}
        micro = (payload.get("microformat") or {}).get("microformatDataRenderer", {})
        date_text = str(micro.get("publishDate") or micro.get("uploadDate") or "").strip()
        meta = {
            "year": self._extract_feed_year(date_text),
            "view_count": self._feed_int(video.get("viewCount")),
            "author": str(video.get("author") or "").strip(),
        }
        self._home_cache[cache_key] = (now, meta)
        return meta

    def _track_release_year(self, track: dict, live_meta=None) -> int:
        live_meta = live_meta or {}
        album = track.get("album") if isinstance(track, dict) else {}
        candidates = [
            live_meta.get("year"),
            (track or {}).get("year"),
            album.get("year") if isinstance(album, dict) else 0,
        ]
        for candidate in candidates:
            year = self._extract_feed_year(candidate)
            if year:
                return year
        return 0

    def _freshness_score(self, track: dict, live_meta: dict, spec: dict) -> float:
        score = 0.0
        current_year = datetime.now().year
        release_year = self._track_release_year(track, live_meta)
        strict_recent = bool(spec.get("strict_recent"))
        recent_years = max(0, self._feed_int(spec.get("recent_years")))
        max_age_years = max(0, self._feed_int(spec.get("max_age_years")))

        if release_year:
            age = current_year - release_year
            if age <= 0:
                score += 24 if strict_recent else 14
            elif age == 1:
                score += 16 if strict_recent else 10
            elif recent_years and age <= recent_years:
                score += max(2, 10 - (age * 2))
            elif strict_recent:
                score -= min(28, 10 + (age * 4))
            elif max_age_years and age > max_age_years:
                score -= min(20, 4 + ((age - max_age_years) * 3))
        elif strict_recent:
            score -= 12
        elif recent_years:
            score -= 4

        views = self._feed_int((live_meta or {}).get("view_count"))
        if views >= 500000000:
            score += 12
        elif views >= 100000000:
            score += 9
        elif views >= 25000000:
            score += 6
        elif views >= 5000000:
            score += 3

        author_hay = self._normalize_feed_text((live_meta or {}).get("author", ""))
        artist_hay = self._normalize_feed_text(self._artist_str(track))
        if author_hay and artist_hay and (artist_hay in author_hay or author_hay in artist_hay):
            score += 4

        return score

    def _refine_scored_tracks(self, scored_tracks, spec: dict, limit: int = 20):
        needs_live_meta = bool(
            spec.get("strict_recent")
            or spec.get("recent_years")
            or spec.get("max_age_years")
        )
        if not scored_tracks or not needs_live_meta:
            return scored_tracks

        default_probe = self._feed_int(spec.get("meta_probe_limit")) or 14
        probe_limit = min(len(scored_tracks), max(10, min(default_probe, limit * 2)))
        ranked = sorted(
            scored_tracks,
            key=lambda item: (-item[0], item[1], item[2], item[3].get("title", "").lower()),
        )[:probe_limit]

        meta_map = {}
        futures = {}
        for _score, _source_index, _position, track in ranked:
            vid = str(track.get("videoId") or "").strip()
            if not vid or vid in futures:
                continue
            futures[vid] = self._feed_pool.submit(self._track_live_meta, track)

        for vid, fut in futures.items():
            try:
                meta_map[vid] = fut.result(timeout=8)
            except Exception as e:
                log.debug("Feed meta alınamadı (%s): %s", vid, e)
                meta_map[vid] = {}

        refined = []
        for score, source_index, position, track in scored_tracks:
            live_meta = meta_map.get(str(track.get("videoId") or "").strip(), {})
            boosted = score + self._freshness_score(track, live_meta, spec)
            if live_meta:
                year = self._track_release_year(track, live_meta)
                if year and not track.get("year"):
                    track = dict(track)
                    track["year"] = year
            refined.append((boosted, source_index, position, track))
        return refined

    def _track_matches_feed_profile(self, track: dict, spec: dict) -> bool:
        if not spec:
            return True
        haystack, artist_haystack = self._feed_text_blobs(track)
        hard_reject = spec.get("hard_reject_tokens") or ()
        if hard_reject and self._match_feed_tokens(haystack, hard_reject):
            return False
        title_reject = spec.get("title_reject_tokens") or ()
        if title_reject and self._match_feed_tokens(self._normalize_feed_text(track.get("title", "")), title_reject):
            return False
        required_any = spec.get("required_any_tokens") or ()
        if spec.get("strict_profile") and required_any:
            hay_hits = self._match_feed_tokens(haystack, required_any)
            artist_hints = spec.get("artist_boost_tokens") or ()
            artist_hits = self._match_feed_tokens(artist_haystack, artist_hints)
            if not hay_hits and not artist_hits:
                return False
        return True

    def _normalize_feed_track(self, track: dict):
        if not isinstance(track, dict):
            return None
        item = dict(track)
        result_type = str(item.get("resultType", "") or "").lower()
        if result_type in {"playlist", "album", "artist", "station", "podcast", "episode", "profile"}:
            return None
        vid = item.get("videoId") or item.get("id")
        if not vid:
            return None
        item["videoId"] = vid
        title = str(item.get("title", "") or "")
        if "playlist" in title.lower():
            return None
        if "artists" not in item:
            artist = item.get("artist")
            if isinstance(artist, str) and artist.strip():
                item["artists"] = [{"name": artist.strip()}]
        if not item.get("artist"):
            try:
                item["artist"] = self._artist_str(item)
            except Exception as _e:
                log.debug("Sessiz hata: %s", _e)
        return item

    # ── YTMusic null-safe sarmalayıcılar ─────────────────────────────────────
    # self.yt None olabilir (başlatma hatası) ya da anonim modda bazı
    # endpoint'ler çalışmayabilir. Tüm yt çağrıları bu metodlar üzerinden
    # yapılırsa uygulama hiçbir zaman çökmez; sadece boş liste döner.

    def _resolve_feed_spec(self, query):
        alias = _C.SMART_FEED_ALIASES.get(query, query)
        region = str(getattr(self, "_content_region", "TR") or "TR").upper()
        dynamic_spec = build_region_feed_spec(alias, region)
        if dynamic_spec:
            return alias, dynamic_spec
        return alias, _C.SMART_FEEDS.get(alias)

    def _expand_feed_query(self, query: str) -> str:
        if not query:
            return ""
        year = datetime.now().year
        try:
            return str(query).format(year=year, prev_year=year - 1, next_year=year + 1)
        except Exception:
            return str(query)

    def _ordered_feed_queries(self, feed_key: str, queries) -> list[str]:
        prepared = []
        seen = set()
        for query in list(queries or []):
            expanded = self._expand_feed_query(query).strip()
            norm = expanded.lower()
            if not expanded or norm in seen:
                continue
            seen.add(norm)
            prepared.append(expanded)
        if len(prepared) <= 1:
            return prepared
        seed = getattr(self, "_feed_rotation_seed", None)
        if seed is None:
            seed = int(time.time() * 1000)
            self._feed_rotation_seed = seed
        offset = (seed + sum(ord(ch) for ch in str(feed_key))) % len(prepared)
        return prepared[offset:] + prepared[:offset]

    def _build_listener_feed_queries(self, feed_key: str, spec: dict) -> list[str]:
        profile = self._get_listener_seed_profile()
        artists = [str(item).strip() for item in list(profile.get("artists") or [])[:2] if str(item).strip()]
        similar_artists = [
            str(item).strip() for item in list(profile.get("similar_artists") or [])[:3] if str(item).strip()
        ]
        tags = [str(item).strip() for item in list(profile.get("tags") or [])[:4] if str(item).strip()]
        if not artists and not similar_artists and not tags:
            return []

        hay = self._normalize_feed_text(
            " ".join(
                [
                    str(feed_key or ""),
                    " ".join(spec.get("queries") or []),
                    " ".join(spec.get("prefer_tokens") or []),
                    " ".join(spec.get("required_any_tokens") or []),
                    " ".join(spec.get("artist_boost_tokens") or []),
                ]
            )
        )
        prefer_tr = spec.get("prefer_turkish") is True

        genre_hint = ""
        if any(token in hay for token in ("rap", "hip hop", "hiphop", "trap", "drill")):
            genre_hint = "turkce rap" if prefer_tr else "rap"
        elif any(token in hay for token in ("rock", "alternative", "indie", "anadolu")):
            genre_hint = "turkce rock" if prefer_tr else "rock"
        elif any(token in hay for token in ("arabesk", "damar")):
            genre_hint = "arabesk"
        elif any(token in hay for token in ("acoustic", "akustik", "slow", "night", "chill", "focus")):
            genre_hint = "turkce slow chill" if prefer_tr else "slow chill"
        elif any(token in hay for token in ("edm", "dance", "electronic", "house", "party")):
            genre_hint = "turkce dance pop" if prefer_tr else "dance pop"
        else:
            genre_hint = "turkce pop" if prefer_tr else "pop"

        preferred_tags = []
        for tag in tags:
            norm_tag = self._normalize_feed_text(tag)
            if not norm_tag:
                continue
            if genre_hint == "arabesk" and any(token in norm_tag for token in ("arabesk", "damar")):
                preferred_tags.append(tag)
            elif "rap" in genre_hint and any(token in norm_tag for token in ("rap", "trap", "drill", "hip hop")):
                preferred_tags.append(tag)
            elif "rock" in genre_hint and any(token in norm_tag for token in ("rock", "alternative", "indie")):
                preferred_tags.append(tag)
            elif any(token in genre_hint for token in ("slow", "chill")) and any(
                token in norm_tag for token in ("chill", "acoustic", "ambient", "slow")
            ):
                preferred_tags.append(tag)
            elif "pop" in genre_hint and "pop" in norm_tag:
                preferred_tags.append(tag)
        if not preferred_tags:
            preferred_tags = tags[:2]

        queries = []
        for artist in artists + similar_artists:
            if genre_hint:
                queries.append(f"{artist} {genre_hint}")
            for tag in preferred_tags[:2]:
                queries.append(f"{artist} {tag}")

        for tag in preferred_tags[:2]:
            if genre_hint and self._normalize_feed_text(tag) not in self._normalize_feed_text(genre_hint):
                queries.append(f"{tag} {genre_hint}")
            else:
                queries.append(tag)

        deduped = []
        seen = set()
        for query in queries:
            expanded = self._expand_feed_query(query).strip()
            norm = self._normalize_feed_text(expanded)
            if not expanded or not norm or norm in seen:
                continue
            seen.add(norm)
            deduped.append(expanded)
        return deduped[:6]

    def _get_listener_seed_profile(self):
        cached = getattr(self, "_listener_seed_profile_cache", None)
        if isinstance(cached, tuple) and len(cached) == 2:
            if (time.time() - float(cached[0] or 0)) < 1800:
                return cached[1]

        profile = {"artists": [], "similar_artists": [], "tags": []}
        if not getattr(self, "_lastfm", None) or not self._lastfm.enabled:
            self._listener_seed_profile_cache = (time.time(), profile)
            return profile

        counts = {}
        sample = []
        try:
            sample.extend(list(self.history[:30]))
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
        try:
            sample.extend(list(self.favorites[:20]))
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
        try:
            sample.extend(list(self.dl.all_tracks()[:10]))
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)

        for track in sample:
            if not isinstance(track, dict):
                continue
            artist = (self._artist_str(track) or "").strip()
            if not artist or artist == "?":
                continue
            counts[artist] = counts.get(artist, 0) + 1

        top_artists = [
            artist
            for artist, _ in sorted(counts.items(), key=lambda item: (-item[1], item[0].lower()))[:3]
        ]

        similar_artists = []
        tags = []
        seen_similar = set()
        seen_tags = set()
        for artist in top_artists:
            try:
                seeds = self._lastfm.get_artist_seed_terms(artist)
            except Exception as _e:
                log.debug("Sessiz hata: %s", _e)
                continue
            for similar in list(seeds.get("similar") or [])[:4]:
                norm = self._normalize_feed_text(similar)
                if not norm or norm in seen_similar:
                    continue
                seen_similar.add(norm)
                similar_artists.append(similar)
            for tag in list(seeds.get("tags") or [])[:4]:
                norm = self._normalize_feed_text(tag)
                if not norm or norm in seen_tags:
                    continue
                seen_tags.add(norm)
                tags.append(tag)

        profile = {
            "artists": top_artists,
            "similar_artists": similar_artists,
            "tags": tags,
        }
        self._listener_seed_profile_cache = (time.time(), profile)
        return profile

    def _build_artists_overview_payload(self):
        buckets = []
        try:
            buckets.append(("history", list(self.history[:50]), 1.0))
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
        try:
            buckets.append(("favorites", list(self.favorites[:30]), 1.8))
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
        try:
            buckets.append(("downloads", list(self.dl.all_tracks()[:25]), 1.2))
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)

        artists = {}
        for source_name, tracks, weight in buckets:
            for idx, track in enumerate(tracks):
                if not isinstance(track, dict):
                    continue
                artist_entries = []
                try:
                    artist_entries = list(self._track_artist_entries(track) or [])
                except Exception:
                    artist_entries = []
                if len(artist_entries) != 1:
                    continue
                artist_name = str(artist_entries[0].get("name") or "").strip()
                if not artist_name or artist_name == "?":
                    continue
                data = artists.setdefault(artist_name, {
                    "name": artist_name,
                    "score": 0.0,
                    "plays": 0,
                    "favorite_hits": 0,
                    "download_hits": 0,
                    "sample_track": track,
                })
                data["score"] += max(0.2, weight - (idx * 0.015))
                data["plays"] += 1
                if source_name == "favorites":
                    data["favorite_hits"] += 1
                if source_name == "downloads":
                    data["download_hits"] += 1

        ranked_artists = sorted(
            artists.values(),
            key=lambda item: (-item["score"], -item["plays"], item["name"].lower()),
        )

        # ── Featured sanatçılar: Last.fm çağrıları paralel ───────────────────
        top_artists_data = ranked_artists[:12]

        def _fetch_featured(artist_data):
            artist_name = artist_data["name"]
            summary = self._ytm_artist_summary(artist_name, target=512)
            sample_track = artist_data.get("sample_track") or {}
            image_url = summary.get("image_url") or self._thumb(sample_track, big=True) or ""
            artist_meta = {
                "name": summary.get("name") or artist_name,
                "image_url": image_url,
                "subscribers": summary.get("subscribers", ""),
                "browseId": summary.get("browseId") or summary.get("channelId") or "",
                "source": "ytmusic" if summary else "library",
            }
            return {
                "name": artist_meta["name"],
                "score": round(float(artist_data["score"]), 2),
                "plays": int(artist_data["plays"]),
                "favorite_hits": int(artist_data["favorite_hits"]),
                "download_hits": int(artist_data["download_hits"]),
                "sample_track": sample_track,
                "image_url": image_url,
                "artist_meta": artist_meta,
                "tags": [],
                "top_track": str(sample_track.get("title") or "").strip(),
            }
            artist_meta = {}
            if self._lastfm.enabled:
                try:
                    artist_meta = self._lastfm.get_artist_profile(artist_name)
                except Exception as e:
                    log.warning("Sanatçı özeti alınamadı (%s): %s", artist_name, e)
            sample_track = artist_data.get("sample_track") or {}
            image_url = artist_meta.get("image_url") or self._thumb(sample_track, big=True) or ""
            return {
                "name": artist_name,
                "score": round(float(artist_data["score"]), 2),
                "plays": int(artist_data["plays"]),
                "favorite_hits": int(artist_data["favorite_hits"]),
                "download_hits": int(artist_data["download_hits"]),
                "sample_track": sample_track,
                "image_url": image_url,
                "artist_meta": artist_meta,
                "tags": list((artist_meta.get("tags") or [])[:3]),
                "top_track": ((artist_meta.get("top_tracks") or [{}])[0].get("name", "")
                              if artist_meta.get("top_tracks") else ""),
            }

        featured_map = {}
        futs = {self._feed_pool.submit(_fetch_featured, ad): ad["name"] for ad in top_artists_data}
        for fut in as_completed(futs, timeout=30):
            try:
                result = fut.result()
                featured_map[futs[fut]] = result
            except Exception as e:
                log.debug("Featured sanatçı hatası: %s", e)

        # Orijinal sıralamayı koru
        featured = []
        seen_featured = set()
        for ad in top_artists_data:
            item = featured_map.get(ad["name"])
            if not item:
                continue
            norm = self._normalize_feed_text(item.get("name") or ad["name"])
            browse = str((item.get("artist_meta") or {}).get("browseId") or "").strip().lower()
            key = browse or norm
            if not key or key in seen_featured:
                continue
            seen_featured.add(key)
            featured.append(item)
        similar = []
        if featured:
            lead = featured[0]
            lead_meta = lead.get("artist_meta") or {}
            try:
                yt_artist = self._fetch_artist_ytm(
                    lead.get("name") or "",
                    lead_meta.get("browseId") or "",
                )
                related_data = yt_artist.get("related") or {}
                related_items = (
                    list(related_data.get("results") or [])
                    if isinstance(related_data, dict) else []
                )
                seen_related = {
                    self._normalize_feed_text(item.get("name") or "")
                    for item in featured
                }
                for item in related_items:
                    if not isinstance(item, dict):
                        continue
                    artist_name = str(item.get("title") or item.get("name") or "").strip()
                    if not artist_name:
                        continue
                    norm = self._normalize_feed_text(artist_name)
                    if not norm or norm in seen_related:
                        continue
                    seen_related.add(norm)
                    browse_id = str(item.get("browseId") or item.get("channelId") or "").strip()
                    image_url = self._ytm_best_thumbnail_url(
                        item.get("thumbnails") or item.get("thumbnail") or [],
                        target=512,
                    )
                    similar.append({
                        "name": artist_name,
                        "image_url": image_url,
                        "artist_meta": {
                            "name": artist_name,
                            "image_url": image_url,
                            "browseId": browse_id,
                            "source": "ytmusic",
                        },
                        "tags": [],
                    })
                    if len(similar) >= 8:
                        break
            except Exception as e:
                log.debug("YTMusic benzer sanatci hatasi: %s", e)

        # ── Benzer sanatçılar: paralel ────────────────────────────────────────
        seed_profile = {"tags": []}
        similar_names = []

        def _fetch_similar(artist_name):
            profile = {}
            if self._lastfm.enabled:
                try:
                    profile = self._lastfm.get_artist_profile(artist_name)
                except Exception:
                    pass
            return {
                "name": artist_name,
                "image_url": profile.get("image_url", ""),
                "artist_meta": profile,
                "tags": list((profile.get("tags") or [])[:2]),
            }

        similar_map = {}
        futs = {self._feed_pool.submit(_fetch_similar, n): n for n in similar_names}
        for fut in as_completed(futs, timeout=30):
            try:
                result = fut.result()
                similar_map[result["name"]] = result
            except Exception as e:
                log.debug("Benzer sanatçı hatası: %s", e)

        similar = similar or [similar_map[n] for n in similar_names if n in similar_map]

        summary = {
            "artist_count": len(ranked_artists),
            "top_artist": featured[0]["name"] if featured else "",
            "top_tags": list(seed_profile.get("tags") or [])[:6],
        }
        return {
            "featured": featured,
            "similar": similar,
            "summary": summary,
        }

    def _score_feed_track(self, track: dict, spec: dict, source_index=0, position=0):
        raw_hay = f"{track.get('title', '') or ''} {self._artist_str(track) or ''}".strip()
        hay, artist_hay = self._feed_text_blobs(track)
        score = 100 - (position * 2.0) - (source_index * 7.0)

        duration = track.get("duration_seconds")
        if duration is not None:
            if 110 <= duration <= 320:
                score += 5
            elif duration > 420:
                score -= 6

        avoid_tokens = spec.get("avoid_tokens") or ()
        if self._match_feed_tokens(hay, avoid_tokens):
            score -= 18

        prefer_tokens = spec.get("prefer_tokens") or ()
        score += min(12, len(self._match_feed_tokens(hay, prefer_tokens)) * 4)

        artist_boost_tokens = spec.get("artist_boost_tokens") or ()
        score += min(18, len(self._match_feed_tokens(artist_hay, artist_boost_tokens)) * 6)

        if spec.get("use_listener_profile"):
            listener_profile = self._get_listener_seed_profile()
            seed_artist_tokens = tuple(listener_profile.get("artists") or ()) + tuple(
                listener_profile.get("similar_artists") or ()
            )
            if seed_artist_tokens:
                score += min(14, len(self._match_feed_tokens(artist_hay, seed_artist_tokens)) * 4)

            seed_tag_tokens = listener_profile.get("tags") or ()
            if seed_tag_tokens:
                score += min(10, len(self._match_feed_tokens(hay, seed_tag_tokens)) * 2)

        required_any = spec.get("required_any_tokens") or ()
        if required_any:
            required_hits = self._match_feed_tokens(hay, required_any)
            score += min(12, len(required_hits) * 3) if required_hits else -8

        prefer_turkish = spec.get("prefer_turkish")
        if prefer_turkish is True:
            score += 6 if self._looks_turkish_text(raw_hay) else -10
        elif prefer_turkish is False:
            score += 3 if not self._looks_turkish_text(raw_hay) else -5

        return score

    def _finalize_feed_tracks(self, scored_tracks, limit=20, max_per_artist=2):
        if not scored_tracks:
            return []

        ranked = sorted(
            scored_tracks,
            key=lambda item: (-item[0], item[1], item[2], item[3].get("title", "").lower()),
        )
        artist_caps = {}
        picked = []
        deferred = []
        seen = set()

        for score, source_index, position, track in ranked:
            key = track.get("videoId") or f"{track.get('title', '')}|{self._artist_str(track)}"
            if key in seen:
                continue
            seen.add(key)
            artist_key = (self._artist_str(track) or "").strip().lower()
            if artist_key and artist_caps.get(artist_key, 0) >= max(1, int(max_per_artist or 1)):
                deferred.append(track)
                continue
            picked.append(track)
            if artist_key:
                artist_caps[artist_key] = artist_caps.get(artist_key, 0) + 1
            if len(picked) >= limit:
                return picked

        for track in deferred:
            picked.append(track)
            if len(picked) >= limit:
                break
        return picked[:limit]

    def _ytm_playlist_tracks(self, playlist_id: str, limit=20):
        playlist_id = str(playlist_id or "").strip()
        if not playlist_id:
            return []
        try:
            requested_limit = int(limit) if limit is not None else 80
        except Exception:
            requested_limit = 80
        requested_limit = max(1, requested_limit)
        # Eski limit>=500 davranışı YTMusic API'nin tüm playlisti sayfa sayfa
        # çekmesine neden olabiliyordu; sınırsız mod artık sadece limit=None.
        full_mode = limit is None
        cache_key = f"__ytm_playlist::{playlist_id}::{'full' if full_mode else requested_limit}"
        cached = self._home_cache.get(cache_key)
        now = time.time()
        if cached and (now - cached[0]) < self._home_cache_ttl:
            return list(cached[1] or [])

        api_limit = None if full_mode else max(requested_limit, 24)
        payload = self._yt_get_playlist(playlist_id, limit=api_limit)
        tracks = []
        for position, item in enumerate(list(payload.get("tracks") or [])):
            track = self._normalize_feed_track(item)
            if not track:
                continue
            if not self._ytm_track_is_good(track):
                continue
            tracks.append((100 - (position * 2.0), 0, position, track))

        if full_mode:
            # Playlist sırası korunsun, sanatçı başına sınır uygulanmasın
            final = [t for _, _, _, t in sorted(tracks, key=lambda x: x[2])]
        else:
            final = self._finalize_feed_tracks(tracks, requested_limit, max_per_artist=1)
        self._home_cache[cache_key] = (now, final)
        return final

    def _ytm_album_tracks(self, browse_id: str, limit=20):
        browse_id = str(browse_id or "").strip()
        if not browse_id:
            return []
        cache_key = f"__ytm_album::{browse_id}::{limit}"
        cached = self._home_cache.get(cache_key)
        now = time.time()
        if cached and (now - cached[0]) < self._home_cache_ttl:
            return list(cached[1] or [])

        payload = self._yt_get_album(browse_id)
        tracks = []
        for position, item in enumerate(list(payload.get("tracks") or [])):
            track = self._normalize_feed_track(item)
            if not track:
                continue
            if not self._ytm_track_is_good(track):
                continue
            tracks.append((100 - (position * 2.0), 0, position, track))
        final = self._finalize_feed_tracks(tracks, limit, max_per_artist=1)
        self._home_cache[cache_key] = (now, final)
        return final

    def _ytm_mood_feed(self, params: str, limit=20):
        params = str(params or "").strip()
        if not params:
            return []
        cache_key = f"__ytm_mood::{params}::{limit}"
        cached = self._home_cache.get(cache_key)
        now = time.time()
        if cached and (now - cached[0]) < self._home_cache_ttl:
            return list(cached[1] or [])

        playlists = self._yt_get_mood_playlists(params)
        scored = []
        for source_index, item in enumerate(playlists[:2]):
            playlist_id = str(item.get("playlistId", "") or "").strip()
            if not playlist_id:
                continue
            for position, track in enumerate(self._ytm_playlist_tracks(playlist_id, limit=max(limit, 12))):
                scored.append((100 - (source_index * 5.0) - (position * 2.0), source_index, position, track))
        final = self._finalize_feed_tracks(scored, limit, max_per_artist=1)
        self._home_cache[cache_key] = (now, final)
        return final

    def _get_ytm_mood_buttons(self, limit=8):
        cache_key = f"__ytm_mood_buttons::{limit}"
        cached = self._home_cache.get(cache_key)
        now = time.time()
        if cached and (now - cached[0]) < self._home_cache_ttl:
            return list(cached[1] or [])

        groups = self._yt_get_mood_categories()
        if not isinstance(groups, dict) or not groups:
            return []

        catalog = self._ytm_curated_mood_catalog()
        ranked = []
        for group_name, items in groups.items():
            if not isinstance(items, list):
                continue
            for position, item in enumerate(items):
                title = str(item.get("title", "") or "").strip()
                params = str(item.get("params", "") or "").strip()
                if not title or not params:
                    continue
                norm = self._normalize_feed_text(title)
                score = 0
                label = ""
                for catalog_index, (catalog_label, aliases) in enumerate(catalog):
                    if any(alias == norm for alias in aliases):
                        label = catalog_label
                        score = 100 - catalog_index
                        break
                if not label:
                    continue
                if "mood" in str(group_name).lower() or "genre" in str(group_name).lower():
                    score += 3
                ranked.append((score, position, label, params, norm))

        if not ranked:
            return []

        ranked.sort(key=lambda item: (-item[0], item[1], item[2].lower()))
        seen = set()
        buttons = []
        for _, _, label, params, norm in ranked:
            if not norm or norm in seen:
                continue
            seen.add(norm)
            buttons.append((label, f"ytm:mood:{params}", "songs"))
            if len(buttons) >= limit:
                break

        self._home_cache[cache_key] = (now, buttons)
        return buttons

    def _get_ytm_home_sections(self, limit=4, tracks_per_section=8):
        cache_key = f"__ytm_home_sections::{limit}::{tracks_per_section}"
        cached = self._home_cache.get(cache_key)
        now = time.time()
        if cached and (now - cached[0]) < self._home_cache_ttl:
            return list(cached[1] or [])

        rows = self._yt_get_home(limit=max(limit * 3, 10))
        sections = []
        seen_titles = set()

        for row in rows:
            if not isinstance(row, dict):
                continue
            title = str(row.get("title", "") or row.get("header", "") or "").strip()
            if not title:
                continue
            if self._ytm_title_is_blocked(title):
                continue
            norm_title = self._normalize_feed_text(title)
            if not norm_title or norm_title in seen_titles:
                continue
            if self._ytm_section_title_score(title) < 8:
                continue

            contents = row.get("contents") or row.get("items") or row.get("results") or []
            if not isinstance(contents, list) or not contents:
                continue

            scored = []
            for source_index, item in enumerate(contents[:10]):
                track = self._normalize_feed_track(item)
                if track:
                    if not self._ytm_track_is_good(track):
                        continue
                    scored.append((100 - (source_index * 2.0), 0, source_index, track))
                    continue

                result_type = str(item.get("resultType", "") or "").lower()
                playlist_id = str(item.get("playlistId", "") or "").strip()
                browse_id = str(item.get("browseId", "") or "").strip()

                nested_tracks = []
                if playlist_id:
                    nested_tracks = self._ytm_playlist_tracks(playlist_id, limit=4)
                elif browse_id and result_type == "album":
                    nested_tracks = self._ytm_album_tracks(browse_id, limit=4)

                for position, nested_track in enumerate(nested_tracks):
                    scored.append((92 - (source_index * 4.0) - (position * 2.0), source_index, position, nested_track))

            final = self._finalize_feed_tracks(scored, tracks_per_section, max_per_artist=1)
            if not self._ytm_section_has_quality(final, min_tracks=5):
                continue

            seen_titles.add(norm_title)
            sections.append((self._ytm_localize_label(title), final))
            if len(sections) >= limit:
                break

        self._home_cache[cache_key] = (now, sections)
        return sections

    def _playlist_id_from_search_item(self, item: dict) -> str:
        if not isinstance(item, dict):
            return ""
        playlist_id = str(item.get("playlistId") or item.get("playlist_id") or "").strip()
        browse_id = str(item.get("browseId") or item.get("browse_id") or "").strip()
        if not playlist_id and browse_id:
            playlist_id = browse_id[2:] if browse_id.startswith("VL") else browse_id
        if playlist_id.startswith("VL"):
            playlist_id = playlist_id[2:]
        return playlist_id

    def _score_playlist_candidate(self, item: dict, spec: dict, query: str, position: int) -> float:
        title = self._normalize_feed_text(str(item.get("title", "") or ""))
        author = self._normalize_feed_text(str(item.get("author", "") or item.get("artists", "") or ""))
        haystack = f"{title} {author} {self._normalize_feed_text(query)}".strip()
        if not title:
            return -999.0

        score = 100.0 - (position * 3.0)
        prefer_tokens = spec.get("playlist_prefer_tokens") or spec.get("prefer_tokens") or ()
        reject_tokens = spec.get("playlist_reject_tokens") or ()
        for token in prefer_tokens:
            norm = self._normalize_feed_text(token)
            if norm and norm in haystack:
                score += 18.0
        for token in reject_tokens:
            norm = self._normalize_feed_text(token)
            if norm and norm in haystack:
                score -= 45.0

        if any(token in title for token in ("top 100", "top 50", "best songs", "greatest hits")):
            score -= 15.0
        if "playlist" in title:
            score += 2.0
        return score

    def _playlist_search_feed(self, feed_key: str, spec: dict, limit=20):
        """Build a feed from real YouTube Music playlists first."""
        queries = self._ordered_feed_queries(feed_key, spec.get("playlist_queries") or [])
        if not queries:
            return self._search_feed(feed_key, spec, limit=limit)

        cache_key = f"__playlist_search::{feed_key}::{limit}::{hash(tuple(queries[:6]))}"
        cached = self._home_cache.get(cache_key)
        now = time.time()
        if cached and (now - cached[0]) < self._home_cache_ttl:
            return list(cached[1] or [])

        gl = spec.get("gl")
        hl = spec.get("hl")
        search_limit = max(4, min(int(spec.get("playlist_search_limit", 8)), 12))
        max_sources = max(1, min(len(queries), int(spec.get("playlist_max_sources", 3))))

        ranked_playlists = []
        seen_playlists = set()
        for source_index, query in enumerate(queries[:max_sources]):
            raw = self._yt_search(
                query,
                filter="playlists",
                limit=search_limit,
                gl=gl,
                hl=hl,
                fallback_on_empty=False,
            )
            for position, item in enumerate(list(raw or [])):
                playlist_id = self._playlist_id_from_search_item(item)
                if not playlist_id or playlist_id in seen_playlists:
                    continue
                score = self._score_playlist_candidate(item, spec, query, position) - (source_index * 5.0)
                if score < 40:
                    continue
                seen_playlists.add(playlist_id)
                ranked_playlists.append((score, source_index, position, playlist_id, item, query))

        ranked_playlists.sort(key=lambda row: (-row[0], row[1], row[2]))

        scored_tracks = []
        for playlist_rank, (pl_score, source_index, _pos, playlist_id, _item, _query) in enumerate(ranked_playlists[:3]):
            tracks = self._ytm_playlist_tracks(playlist_id, limit=max(limit, 18))
            for position, track in enumerate(tracks):
                if not track or not self._ytm_track_is_good(track):
                    continue
                score = pl_score - (playlist_rank * 4.0) - (position * 1.5)
                scored_tracks.append((score, source_index, position, track))
            if len(scored_tracks) >= max(limit * 2, 24):
                break

        if scored_tracks:
            final = self._finalize_feed_tracks(
                scored_tracks,
                limit,
                max_per_artist=max(1, int(spec.get("max_artist_repeat", 2))),
            )
            self._home_cache[cache_key] = (now, final)
            return final

        final = self._search_feed(feed_key, spec, limit=limit)
        self._home_cache[cache_key] = (now, final)
        return final

    def _search_feed(self, feed_key: str, spec: dict, limit=20):
        queries = self._ordered_feed_queries(feed_key, spec.get("queries") or [])
        listener_queries = []
        if spec.get("use_listener_profile"):
            listener_queries = self._ordered_feed_queries(
                f"{feed_key}:listener",
                self._build_listener_feed_queries(feed_key, spec),
            )
        if listener_queries:
            merged_queries = []
            seen_queries = set()
            for query in list(listener_queries[:3]) + list(queries):
                norm_query = self._normalize_feed_text(query)
                if not norm_query or norm_query in seen_queries:
                    continue
                seen_queries.add(norm_query)
                merged_queries.append(query)
            queries = merged_queries
        if not queries:
            return []
        search_limit = max(int(spec.get("search_limit", 14)), min(max(limit * 2, 18), 30))
        max_sources = max(1, min(len(queries), int(spec.get("max_sources", 3))))
        gl = spec.get("gl")
        hl = spec.get("hl")
        scored = []
        for source_index, query in enumerate(queries[:max_sources]):
            raw = self._yt_search(
                query,
                filter="songs",
                limit=search_limit,
                gl=gl,
                hl=hl,
                fallback_on_empty=False,
            )
            filtered = self._filter_tracks(raw)
            for position, item in enumerate(filtered):
                track = self._normalize_feed_track(item)
                if not track:
                    continue
                if not self._track_matches_feed_profile(track, spec):
                    continue
                score = self._score_feed_track(track, spec, source_index, position)
                scored.append((score, source_index, position, track))
            if len(scored) >= max(limit * 2, search_limit * 2):
                break
        if not scored and queries:
            raw = self._yt_dlp_search(queries[0], search_limit)
            filtered = self._filter_tracks(raw)
            for position, item in enumerate(filtered):
                track = self._normalize_feed_track(item)
                if not track:
                    continue
                if not self._track_matches_feed_profile(track, spec):
                    continue
                score = self._score_feed_track(track, spec, 99, position)
                scored.append((score, 99, position, track))
        scored = self._refine_scored_tracks(scored, spec, limit=limit)
        return self._finalize_feed_tracks(
            scored,
            limit,
            max_per_artist=max(1, int(spec.get("max_artist_repeat", 1))),
        )

    def _chart_feed(self, spec: dict, limit=20):
        country = spec.get("country", "US")
        scored = []

        # _yt_get_charts: hesap yoksa / anonim modda boş liste döner, exception fırlatmaz
        raw = self._yt_get_charts(country)
        for position, item in enumerate(raw):
            track = self._normalize_feed_track(item)
            if not track:
                continue
            if not self._track_matches_feed_profile(track, spec):
                continue
            score = self._score_feed_track(track, spec, 0, position) + 10
            scored.append((score, 0, position, track))

        scored = self._refine_scored_tracks(scored, spec, limit=limit)
        results = self._finalize_feed_tracks(scored, limit, max_per_artist=1)
        if results:
            return results

        # get_charts boş döndüyse (anonim mod veya API sorunu) → arama fallback
        fallback_queries = spec.get("fallback_queries") or []
        if not fallback_queries:
            return []
        log.debug("Charts boş (%s) → fallback arama kullanılıyor", country)
        fallback_spec = {
            "queries": fallback_queries,
            "search_limit": max(limit, 14),
            "prefer_turkish": spec.get("prefer_turkish"),
            "prefer_tokens": spec.get("prefer_tokens", ()),
            "avoid_tokens": spec.get("avoid_tokens", ()),
            "strict_recent": spec.get("strict_recent"),
            "recent_years": spec.get("recent_years"),
            "max_age_years": spec.get("max_age_years"),
            "title_reject_tokens": spec.get("title_reject_tokens", ()),
            "gl": spec.get("gl"),
            "hl": spec.get("hl"),
            "max_sources": spec.get("max_sources", 3),
        }
        if spec.get("playlist_queries"):
            fallback_spec.update({
                "kind": "playlist_search",
                "playlist_queries": spec.get("playlist_queries") or (),
                "playlist_prefer_tokens": spec.get("playlist_prefer_tokens") or spec.get("prefer_tokens", ()),
                "playlist_reject_tokens": spec.get("playlist_reject_tokens", ()),
                "playlist_search_limit": spec.get("playlist_search_limit", 8),
                "playlist_max_sources": spec.get("playlist_max_sources", 3),
            })
            return self._playlist_search_feed(f"{country.lower()}:fallback", fallback_spec, limit=limit)
        return self._search_feed(f"{country.lower()}:fallback", fallback_spec, limit=limit)

    def _fetch_feed_results(self, query, limit=20):
        query = str(query or "").strip()
        if query.startswith("ytm:mood:"):
            return self._ytm_mood_feed(query.split("ytm:mood:", 1)[1], limit=limit)
        if query.startswith("ytm:playlist:"):
            return self._ytm_playlist_tracks(query.split("ytm:playlist:", 1)[1], limit=limit)
        if query.startswith("ytm:album:"):
            return self._ytm_album_tracks(query.split("ytm:album:", 1)[1], limit=limit)

        alias, spec = self._resolve_feed_spec(query)
        if not spec:
            raw = self._yt_search(query, filter="songs", limit=max(limit, 20))
            filtered = self._filter_tracks(raw)
            scored = []
            for position, item in enumerate(filtered):
                track = self._normalize_feed_track(item)
                if not track:
                    continue
                scored.append((100 - (position * 2.0), 0, position, track))
            return self._finalize_feed_tracks(scored, limit)

        if spec.get("kind") == "charts":
            return self._chart_feed(spec, limit=limit)
        if spec.get("kind") == "playlist_search":
            return self._playlist_search_feed(alias, spec, limit=limit)
        return self._search_feed(alias, spec, limit=limit)

    def _fetch_charts(self, country: str, frame, loading):
        """
        YouTube Music Charts API'sinden trend şarkıları getirir.
        Hesap yoksa veya API erişilemezse _chart_feed otomatik olarak
        fallback arama kullanır. Sonuç boş olsa bile sinyal emit edilir;
        bu sayede skeleton kartlar asla ekranda takılı kalmaz.
        """
        feed_key = "feed:charts.tr" if country == "TR" else "feed:charts.global"
        results = []
        try:
            results = self._fetch_feed_results(feed_key, limit=20)
            if results:
                self._home_cache[f"__charts_{country}"] = (time.time(), results)
        except Exception as e:
            log.warning("Charts yüklenemedi (%s): %s", country, e)
        # Boş olsa bile emit et → skeleton kapanır, boş bölüm gösterilmez
        self.sig.home_section_done.emit(results, frame, loading)

    def _fetch_home_trending_sec(self, query, frame, loading):
        """
        Ana sayfa trend bölümleri için özelleştirilmiş veri getirme.
        Bu metod, standard arama yerine daha yüksek limitli arama yapar ve
        sonrasında filtreleme uygular. Arama sonuçlarının yüksek limitli
        olması, filtreleme sonrası yeterli öğe kalmasını sağlar.

        Args:
            query: Arama sorgusu
            frame: Bölüm çerçevesi
            loading: Yükleme etiketi
        """
        try:
            res = self._fetch_feed_results(query, limit=20)
            self._home_cache[query] = (time.time(), res)
            self.sig.home_section_done.emit(res, frame, loading)
        except Exception as e:
            log.warning("Trend bölüm yüklenemedi (%s): %s", query, e)

    # ══════════════════════════════════════════════════════════════════════════
    # HOME BÖLÜM YÜKLEMESİ
    # ══════════════════════════════════════════════════════════════════════════

    def _fetch_home_sec(self, query, frame, loading):
        try:
            res = self._fetch_feed_results(query, limit=20)
            self._home_cache[query] = (time.time(), res)
            self.sig.home_section_done.emit(res, frame, loading)
        except Exception as e:
            log.warning("Bölüm yüklenemedi (%s): %s", query, e)

    def _on_home_section(self, results, frame, loading):
        try:
            _ = frame.objectName()
        except RuntimeError:
            return
        # loading None olabilir (skeleton modunda)
        try:
            self._fill_h_grid(results, frame, loading if loading is not None else None)
            if self.current_page != "home":
                self._prime_stream_urls(results, limit=4)
        except RuntimeError:
            pass

    def _fill_h_grid(self, tracks, frame, loading):

        # loading; QLabel veya None (skeleton kullanımı) olabilir
        if loading is not None:
            try:
                loading.deleteLater()
            except Exception as _e:
                log.debug("Sessiz hata: %s", _e)
        # Mevcut skeleton widget'larını temizle
        try:
            lay = frame.layout()
            if lay:
                for i in reversed(range(lay.count())):
                    item = lay.itemAt(i)
                    if item:
                        w = item.widget()
                        if w and w.__class__.__name__ == "SkeletonWidget":
                            lay.removeWidget(w)
                            w.stop()
                            w.deleteLater()
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
        layout   = frame.layout()
        is_grid  = isinstance(layout, QGridLayout)
        row = col = 0
        if is_grid and self.current_page != "home":
            available_width = max(int(frame.width() or 0), 1180)
            MAX_COLS = max(5, min(8, available_width // 202))
            try:
                layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
                layout.setHorizontalSpacing(10)
                layout.setVerticalSpacing(10)
            except Exception as _e:
                log.debug("Sessiz hata: %s", _e)
        else:
            MAX_COLS = 4
        acc      = get_accent()
        render_tracks = []
        seen_render_keys = set()
        blocked_types = {"playlist", "album", "artist", "station", "podcast", "episode", "profile"}
        for track in list(tracks or []):
            if not isinstance(track, dict):
                continue
            result_type = str(track.get("resultType", "") or "").lower()
            title = str(track.get("title", "") or "").strip()
            if result_type in blocked_types or "playlist" in title.lower():
                continue
            vid = str(track.get("videoId", "") or "").strip()
            artist = (self._artist_str(track) or "").strip().lower()
            key = vid or f"{title.lower()}|{artist}"
            if key and key in seen_render_keys:
                continue
            if key:
                seen_render_keys.add(key)
            render_tracks.append(track)
        if (
            self.current_page == "home"
            and bool(frame.property("dedupe_across_home"))
        ):
            seen_home = getattr(self, "_home_feed_seen_keys", None)
            if seen_home is None:
                seen_home = set()
                self._home_feed_seen_keys = seen_home
            artist_counts = getattr(self, "_home_feed_artist_counts", None)
            if artist_counts is None:
                artist_counts = {}
                self._home_feed_artist_counts = artist_counts
            unique_tracks = []
            deferred_tracks = []
            for track in render_tracks:
                vid = str(track.get("videoId", "") or "").strip()
                artist = (self._artist_str(track) or "").strip().lower()
                title = str(track.get("title", "") or "").strip().lower()
                key = vid or f"{title}|{artist}"
                if not key or key in seen_home:
                    continue
                if artist and artist_counts.get(artist, 0) >= 2:
                    deferred_tracks.append((key, artist, track))
                    continue
                seen_home.add(key)
                if artist:
                    artist_counts[artist] = artist_counts.get(artist, 0) + 1
                unique_tracks.append(track)
            if len(unique_tracks) < min(4, len(render_tracks)):
                for key, artist, track in deferred_tracks:
                    if key in seen_home:
                        continue
                    seen_home.add(key)
                    if artist:
                        artist_counts[artist] = artist_counts.get(artist, 0) + 1
                    unique_tracks.append(track)
                    if len(unique_tracks) >= min(4, len(render_tracks)):
                        break
            render_tracks = unique_tracks

        # ── Kategori sayfası: satır tabanlı liste görünümü ───────────────────
        if getattr(frame, "objectName", lambda: "")() == "CatListContainer":
            self._fill_cat_list(render_tracks, frame, layout)
            return

        for track in render_tracks:
            card = AnimatedCard()
            card.setObjectName("HomeTrackCard")
            card.setFixedSize(186, 268)
            card.setStyleSheet(f"""
                QFrame#HomeTrackCard {{
                    background:qlineargradient(x1:0,y1:1,x2:0,y2:0,
                        stop:0 {BG_ELEVATED}, stop:0.55 {BG_CARD}, stop:1 rgba(255,255,255,0.022));
                    border-radius:20px;
                    border: 1px solid {BORDER_COLOR};
                }}
                QFrame#HomeTrackCard:hover {{
                    background:qlineargradient(x1:0,y1:1,x2:0,y2:0,
                        stop:0 {BG_ELEVATED}, stop:0.5 {BG_CARD_HOVER}, stop:1 {acc}12);
                    border-color: {acc}44;
                }}
            """)
            try:
                self._add_soft_shadow(card, 16, QColor(0, 0, 0, 80), 0, 5)
            except Exception as _e:
                log.debug("Sessiz hata: %s", _e)
            cl = QVBoxLayout(card)
            cl.setContentsMargins(12, 12, 12, 14)
            cl.setSpacing(0)

            # Kare kapak görseli — TrackCoverWidget ile KeepAspectRatioByExpanding
            img_lbl = TrackCoverWidget(162, 162, radius=14)
            thumb = self._thumb(track, big=True)
            if thumb:
                self._load_image(thumb, img_lbl, (320, 320))
            else:
                try:
                    from PySide6.QtGui import QPixmap as _QP
                    fall_pix = create_icon("music", TEXT_MUTED, 48)
                    img_lbl.setPixmap(fall_pix.pixmap(48, 48))
                except Exception as _e:
                    log.debug("Sessiz hata: %s", _e)

            cl.addWidget(img_lbl)
            cl.addSpacing(10)

            title = track.get("title", "Bilinmiyor")
            lt = QLabel(title)
            lt.setWordWrap(True)
            lt.setFixedHeight(44)
            lt.setStyleSheet(
                f"font-weight:900; color:{TEXT_PRIMARY}; font-size:13px;"
                f" font-family:'Segoe UI Variable Display','Segoe UI Black','Segoe UI';"
                f" background:transparent;"
            )

            sub = self._artist_str(track)
            la = QLabel(sub)
            la.setStyleSheet(
                f"color:{TEXT_MUTED}; font-size:11px; font-weight:600; background:transparent;"
            )
            la.setFixedHeight(18)
            la.setCursor(Qt.PointingHandCursor)
            la.mousePressEvent = lambda _, t=track: self._artist_clicked_for(t)

            cl.addWidget(lt)
            cl.addSpacing(2)
            cl.addWidget(la)
            cl.addStretch()

            if ("browseId" in track and
                    track.get("resultType") not in ("song", "video")):
                card.clicked.connect(lambda t=track: self._fetch_radio(t["browseId"]))
            else:
                card.clicked.connect(lambda t=track: self.force_play(t))
                card.setContextMenuPolicy(Qt.CustomContextMenu)
                card.customContextMenuRequested.connect(
                    lambda _, t=track: self._ctx_menu(QCursor.pos(), t))

            if is_grid:
                layout.addWidget(card, row, col, Qt.AlignTop | Qt.AlignLeft)
                col += 1
                if col >= MAX_COLS:
                    col = 0
                    row += 1
            else:
                layout.addWidget(card)

        if not is_grid:
            layout.addStretch()
            frame.adjustSize()

    def _fill_cat_list(self, tracks, frame, layout):
        """Kategori sayfası için şık satır tabanlı liste render'ı."""
        import random as _random
        from PySide6.QtCore import QSize

        acc = get_accent()
        fav_vids = {f.get("videoId", "") for f in self.favorites}
        self._prime_stream_urls(tracks, limit=4)

        # ── Hero bileşenlerini güncelle ───────────────────────────────────────
        count = len(tracks)
        try:
            frame._hero_count_lbl.setText(self._tr("home.track_count", count=count))
        except Exception:
            pass
        try:
            slots = getattr(frame, "_hero_cover_slots", [])
            for i, track in enumerate(tracks[:4]):
                thumb = self._thumb(track, big=True)
                if thumb and i < len(slots):
                    self._load_image(thumb, slots[i], (160, 160))
        except Exception:
            pass
        try:
            play_btn = getattr(frame, "_play_btn", None)
            if play_btn:
                play_btn.setEnabled(bool(tracks))
                play_btn.clicked.connect(
                    lambda _=None, tr=list(tracks): self._play_all(tr)
                )
            shuf_btn = getattr(frame, "_shuffle_btn", None)
            if shuf_btn:
                shuf_btn.setEnabled(bool(tracks))
                def _shuffle_and_play(_checked=None, tr=list(tracks)):
                    shuffled = list(tr)
                    _random.shuffle(shuffled)
                    self._play_all(shuffled)
                shuf_btn.clicked.connect(_shuffle_and_play)
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)

        # ── Satırları oluştur ─────────────────────────────────────────────────
        if not tracks:
            empty = QLabel(self._tr("search.empty.tracks"))
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet(
                f"color:{TEXT_MUTED}; font-size:14px; background:transparent;"
            )
            layout.addWidget(empty)
            layout.addStretch()
            return

        for i, track in enumerate(tracks):
            row = ClickableFrame()
            row.setObjectName("CatTrackRow")
            row.setFixedHeight(68)
            row.setFocusPolicy(Qt.NoFocus)
            row.setStyleSheet(f"""
                QFrame#CatTrackRow {{
                    background: transparent;
                    border-radius: 12px;
                    border: 1px solid transparent;
                }}
                QFrame#CatTrackRow:hover {{
                    background: rgba(255,255,255,0.04);
                    border: 1px solid {acc}28;
                }}
                QFrame#CatTrackRow QLabel {{
                    background: transparent; border: none;
                }}
            """)
            rl = QHBoxLayout(row)
            rl.setContentsMargins(8, 8, 12, 8)
            rl.setSpacing(12)

            # Sıra numarası
            num_lbl = QLabel(str(i + 1))
            num_lbl.setFixedWidth(28)
            num_lbl.setAlignment(Qt.AlignCenter)
            num_lbl.setStyleSheet(
                f"color:{TEXT_MUTED}; font-size:12px; font-weight:600;"
            )
            num_lbl.setFocusPolicy(Qt.NoFocus)

            # Kapak
            img = TrackCoverWidget(46, 46, radius=8)
            thumb = self._thumb(track, big=True)
            if thumb:
                self._load_image(thumb, img, (46, 46))

            # Başlık + sanatçı
            inf = QFrame()
            inf.setStyleSheet("background:transparent; border:none;")
            inf.setFocusPolicy(Qt.NoFocus)
            il = QVBoxLayout(inf)
            il.setContentsMargins(0, 0, 0, 0)
            il.setSpacing(3)
            tl = QLabel(track.get("title", "Bilinmiyor"))
            tl.setStyleSheet(
                f"font-weight:750; color:{TEXT_PRIMARY}; font-size:13px;"
            )
            tl.setFocusPolicy(Qt.NoFocus)
            al = QLabel(self._artist_str(track))
            al.setStyleSheet(f"color:{TEXT_MUTED}; font-size:11px;")
            al.setFocusPolicy(Qt.NoFocus)
            il.addWidget(tl)
            il.addWidget(al)

            # Favori butonu
            vid = track.get("videoId", "")
            is_fav = vid in fav_vids
            bh = QPushButton()
            bh.setFixedSize(32, 32)
            bh.setIcon(create_icon(
                "heart_on" if is_fav else "heart_off",
                acc if is_fav else TEXT_MUTED, 16))
            bh.setIconSize(QSize(16, 16))
            bh.setCursor(Qt.PointingHandCursor)
            bh.setFocusPolicy(Qt.NoFocus)
            bh.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; border: none; border-radius: 16px;
                }}
                QPushButton:hover {{ background: {acc}18; }}
            """)
            bh.clicked.connect(lambda _, t=track, b=bh: self._toggle_fav(t, b))

            # Oynat butonu
            bp = QPushButton()
            bp.setFixedSize(32, 32)
            bp.setIcon(create_icon("play", acc, 14))
            bp.setIconSize(QSize(14, 14))
            bp.setCursor(Qt.PointingHandCursor)
            bp.setFocusPolicy(Qt.NoFocus)
            bp.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; border: none; border-radius: 16px;
                }}
                QPushButton:hover {{ background: {acc}22; }}
            """)
            bp.clicked.connect(lambda _, t=track: self.force_play(t))

            rl.addWidget(num_lbl)
            rl.addWidget(img, 0, Qt.AlignVCenter)
            rl.addWidget(inf, 1)
            rl.addWidget(bp)
            rl.addWidget(bh)

            row.clicked.connect(lambda t=track: self.force_play(t))
            row.setContextMenuPolicy(Qt.CustomContextMenu)
            row.customContextMenuRequested.connect(
                lambda _, t=track: self._ctx_menu(QCursor.pos(), t)
            )
            layout.addWidget(row)

        layout.addStretch()

    # ══════════════════════════════════════════════════════════════════════════
    # ARAMA
    # ══════════════════════════════════════════════════════════════════════════
