"""Mixin for Ytmusic functionality."""
import logging

from yt_dlp import YoutubeDL

log = logging.getLogger("iqtMusic")


class YtmusicMixin:

    def _yt_search(
        self,
        query: str,
        filter: str = "songs",
        limit: int = 20,
        gl: str | None = None,
        hl: str | None = None,
        fallback_on_empty: bool = True,
    ) -> list:
        """ytmusicapi search — hesap gerekmez, anonim modda da çalışır."""
        if not self.yt:
            if fallback_on_empty:
                return self._yt_dlp_search(query, limit)
            return []
        kwargs = {"filter": filter, "limit": limit}
        if gl:
            kwargs["gl"] = gl
        if hl:
            kwargs["hl"] = hl
        try:
            try:
                results = self.yt.search(query, **kwargs)
            except TypeError:
                kwargs.pop("gl", None)
                kwargs.pop("hl", None)
                results = self.yt.search(query, **kwargs)
            if isinstance(results, list) and results:
                return results
            # Boş gelirse yt-dlp fallback
            if fallback_on_empty:
                return self._yt_dlp_search(query, limit)
            return []
        except Exception as e:
            log.warning("yt.search başarısız (%s): %s — yt-dlp fallback", query, e)
            return self._yt_dlp_search(query, limit)


    def _yt_get_charts(self, country: str = "TR") -> list:
        """
        YouTube Music Charts — login gerektirir.
        Anonim modda ya boş döner ya da exception fırlatır.
        Her iki durumda da yt-dlp tabanlı arama fallback'ine düşer.
        """
        if not self.yt:
            return []
        try:
            charts = self.yt.get_charts(country=country)
            raw = []
            for key in ("songs", "videos"):
                try:
                    raw = charts.get("results", {}).get(key, []) or []
                except Exception as _e:
                    log.debug("Sessiz hata: %s", _e)
                if raw:
                    break
            return raw if raw else []
        except Exception as e:
            log.debug("get_charts erişilemedi (%s): %s", country, e)
            return []


    def _yt_get_home(self, limit: int = 8) -> list:
        """YouTube Music ana sayfa raflari."""
        if not self.yt:
            return []
        try:
            try:
                rows = self.yt.get_home(limit=limit)
            except TypeError:
                rows = self.yt.get_home()
            if isinstance(rows, list):
                return rows[:limit]
            return []
        except Exception as e:
            log.debug("get_home hatasi: %s", e)
            return []


    def _yt_get_mood_categories(self) -> dict:
        """YouTube Music mood/category gruplari."""
        if not self.yt:
            return {}
        try:
            data = self.yt.get_mood_categories() or {}
            return data if isinstance(data, dict) else {}
        except Exception as e:
            log.debug("get_mood_categories hatasi: %s", e)
            return {}


    def _yt_get_mood_playlists(self, params: str) -> list:
        """Belirli mood kategorisinin playlistleri."""
        if not self.yt or not params:
            return []
        try:
            data = self.yt.get_mood_playlists(params) or []
            return data if isinstance(data, list) else []
        except Exception as e:
            log.debug("get_mood_playlists hatasi (%s): %s", params, e)
            return []


    def _yt_get_playlist(self, playlist_id: str, limit=40) -> dict:
        """YT Music playlist detaylari. limit=None tüm şarkıları getirir."""
        if not self.yt or not playlist_id:
            return {}
        try:
            data = self.yt.get_playlist(playlist_id, limit=limit) or {}
            return data if isinstance(data, dict) else {}
        except Exception as e:
            log.debug("get_playlist hatasi (%s): %s", playlist_id, e)
            return {}


    def _yt_get_album(self, browse_id: str) -> dict:
        """YT Music album detaylari."""
        if not self.yt or not browse_id:
            return {}
        try:
            data = self.yt.get_album(browse_id) or {}
            return data if isinstance(data, dict) else {}
        except Exception as e:
            log.debug("get_album hatasi (%s): %s", browse_id, e)
            return {}


    def _yt_get_song(self, video_id: str) -> dict:
        """YT Music song/video detaylari."""
        if not self.yt or not video_id:
            return {}
        try:
            data = self.yt.get_song(video_id) or {}
            return data if isinstance(data, dict) else {}
        except Exception as e:
            log.debug("get_song hatasi (%s): %s", video_id, e)
            return {}


    def _yt_get_artist(self, channel_id: str) -> dict:
        """YT Music sanatçı detayları (tam şarkı + albüm listesi)."""
        if not self.yt or not channel_id:
            return {}
        try:
            data = self.yt.get_artist(channel_id) or {}
            return data if isinstance(data, dict) else {}
        except Exception as e:
            log.debug("get_artist hatasi (%s): %s", channel_id, e)
            return {}


    def _yt_get_artist_albums(self, channel_id: str, params: str) -> list:
        """YT Music sanatçı tüm albümleri (get_artist'taki params ile)."""
        if not self.yt or not channel_id or not params:
            return []
        try:
            data = self.yt.get_artist_albums(channel_id, params=params) or []
            return data if isinstance(data, list) else []
        except Exception as e:
            log.debug("get_artist_albums hatasi (%s): %s", channel_id, e)
            return []


    def _ytm_title_is_blocked(self, title: str) -> bool:
        hay = self._normalize_feed_text(title)
        if not hay:
            return True
        blocked_tokens = (
            "quick picks",
            "top music videos",
            "music videos",
            "recommended music videos",
            "community playlists",
            "trending in shorts",
            "shorts",
            "video",
            "videos",
            "podcast",
            "episodes",
            "for children",
            "kids",
            "from your library",
            "listen again",
            "forgotten favorites",
            "radios for you",
            "mixes for you",
        )
        return any(token in hay for token in blocked_tokens)


    def _ytm_curated_mood_catalog(self):
        return (
            ("Dans & elektronik", ("dance electronic", "dance & electronic", "dance")),
            ("Türkçe hip-hop", ("turkish hip hop", "turkish hip-hop")),
            ("Türkçe pop", ("turkish pop",)),
            ("Türkçe indie", ("turkish indie",)),
            ("Türkçe rock", ("turkish rock",)),
            ("Chill", ("chill", "chill out")),
            ("İyi hisset", ("feel good",)),
            ("Odak", ("focus", "deep focus")),
            ("Enerji", ("energy",)),
            ("Parti", ("party",)),
            ("Antrenman", ("workout",)),
            ("Uyku", ("sleep",)),
            ("Yolculuk", ("commute",)),
        )


    def _ytm_section_title_score(self, title: str) -> int:
        hay = self._normalize_feed_text(title)
        if self._ytm_title_is_blocked(hay):
            return -100
        score = 0
        positive_tokens = (
            ("albums", 12),
            ("album", 10),
            ("singles", 10),
            ("songs", 9),
            ("hits", 8),
            ("trending songs", 12),
            ("popular", 7),
            ("recommended", 6),
            ("released", 6),
            ("new", 5),
            ("fresh", 5),
        )
        for token, weight in positive_tokens:
            if token in hay:
                score += weight
        return score


    def _ytm_localize_label(self, title: str) -> str:
        norm = self._normalize_feed_text(title)
        localized_map = (
            ("dance electronic", "Dans & elektronik"),
            ("dance & electronic", "Dans & elektronik"),
            ("turkish hip hop", "Türkçe hip-hop"),
            ("turkish hip-hop", "Türkçe hip-hop"),
            ("turkish pop", "Türkçe pop"),
            ("turkish indie", "Türkçe indie"),
            ("turkish rock", "Türkçe rock"),
            ("feel good", "İyi hisset"),
            ("focus", "Odak"),
            ("chill", "Chill"),
            ("workout", "Antrenman"),
            ("energy", "Enerji"),
            ("party", "Parti"),
            ("commute", "Yolculuk"),
            ("sleep", "Uyku"),
            ("deep focus", "Derin odak"),
            ("indie", "Indie"),
            ("rock", "Rock"),
            ("pop", "Pop"),
            ("hip hop", "Hip-hop"),
            ("rap", "Rap"),
            ("new albums & singles", "Yeni albümler ve tekliler"),
            ("new albums", "Yeni albümler"),
            ("new singles", "Yeni tekliler"),
            ("trending songs", "Trend şarkılar"),
            ("recommended songs", "Önerilen şarkılar"),
            ("popular songs", "Popüler şarkılar"),
            ("fresh songs", "Taze seçimler"),
        )
        for token, label in localized_map:
            if token == norm:
                return label
        return str(title or "").strip() or "Müzik"


    def _ytm_track_is_good(self, track: dict) -> bool:
        if not isinstance(track, dict):
            return False
        title = self._normalize_feed_text(track.get("title", ""))
        if not title:
            return False
        artist = self._normalize_feed_text(self._artist_str(track))
        if not artist:
            return False
        blocked_tokens = (
            "cover", "karaoke", "sped up", "slowed", "reverb",
            "remix", "lyric", "lyrics", "fan made", "fanmade",
            "shorts", "video edit", "live loop", "nightcore",
            "edit audio", "clip audio", "mashup", "mix", "instrumental",
        )
        if any(token in title for token in blocked_tokens):
            return False
        duration = track.get("duration_seconds")
        if duration is not None and (duration < 75 or duration > 420):
            return False
        return True


    def _ytm_section_has_quality(self, tracks: list, min_tracks: int = 4) -> bool:
        if not isinstance(tracks, list) or len(tracks) < min_tracks:
            return False
        artists = []
        for track in tracks:
            artist = self._normalize_feed_text(self._artist_str(track))
            if artist:
                artists.append(artist)
        unique_artists = set(artists)
        if len(unique_artists) < max(4, min_tracks - 1):
            return False
        if artists:
            dominant_share = max(artists.count(name) for name in unique_artists) / max(1, len(artists))
            if dominant_share > 0.34:
                return False
        return True


    def _yt_get_watch_playlist(self, videoId: str, limit: int = 30) -> dict:
        """Radyo/öneri listesi — anonim modda genellikle çalışır."""
        if not self.yt:
            return {}
        try:
            return self.yt.get_watch_playlist(videoId=videoId, limit=limit) or {}
        except Exception as e:
            log.debug("get_watch_playlist hatası (%s): %s", videoId, e)
            return {}


    def _yt_get_lyrics(self, browseId: str, timestamps: bool = False):
        """Şarkı sözleri — anonim modda çoğunlukla erişilebilir."""
        if not self.yt:
            return None
        try:
            return self.yt.get_lyrics(browseId=browseId, timestamps=timestamps)
        except Exception as e:
            log.debug("get_lyrics hatası (%s): %s", browseId, e)
            return None


    def _yt_dlp_search(self, query: str, limit: int = 20) -> list:
        """
        yt-dlp ytsearch ile arama yapar. ytmusicapi tamamen başarısız
        olduğunda son çare fallback. Hesap gerekmez, cookie gerekmez.
        Döndürülen dict yapısı ytmusicapi formatına normalize edilir.
        """
        try:
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "extract_flat": "in_playlist",
                "skip_download": True,
                "default_search": f"ytsearch{limit}",
            }
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(query, download=False)
            entries = (info or {}).get("entries") or []
            results = []
            for e in entries:
                if not e or not e.get("id"):
                    continue
                duration = e.get("duration") or 0
                thumbnails = []
                thumb_url = e.get("thumbnail") or e.get("url") or ""
                if thumb_url and not thumb_url.startswith("http"):
                    thumb_url = ""
                if thumb_url:
                    thumbnails = [{"url": thumb_url, "width": 226, "height": 226}]
                results.append({
                    "videoId":          e["id"],
                    "title":            e.get("title", "?"),
                    "artists":          [{"name": e.get("uploader") or e.get("channel") or "?"}],
                    "thumbnails":       thumbnails,
                    "duration_seconds": int(duration),
                    "resultType":       "song",
                })
            return results
        except Exception as e:
            log.warning("yt-dlp arama başarısız (%s): %s", query, e)
            return []

    # ─────────────────────────────────────────────────────────────────────────
