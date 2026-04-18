"""Mixin for Artist functionality."""
import html
import logging
import re
import time

from core.constants import TEXT_MUTED
from core.theme import get_accent
from utils.helpers import qt_is_valid as _qt_is_valid

log = logging.getLogger("iqtMusic")


class ArtistMixin:

    @staticmethod
    def _split_compound_artist_text(text: str) -> list:
        clean = str(text or "").strip()
        if not clean:
            return []
        parts = re.split(
            r"\s(?:-|&|x|,)\s|\s(?:feat\.?|ft\.?|featuring|with)\s",
            clean,
            flags=re.IGNORECASE,
        )
        names = []
        seen = set()
        for part in parts:
            piece = str(part or "").strip()
            if not piece:
                continue
            key = piece.casefold()
            if key in seen:
                continue
            seen.add(key)
            names.append(piece)
        return names or ([clean] if clean else [])

    def _track_artist_entries(self, track: dict) -> list:
        entries = []
        seen = set()
        artists = (track or {}).get("artists")
        if isinstance(artists, list):
            for artist in artists:
                if isinstance(artist, dict):
                    raw_name = str(artist.get("name") or "").strip()
                    browse_id = str(
                        artist.get("browseId") or artist.get("channelId") or artist.get("id") or ""
                    ).strip()
                else:
                    raw_name = str(artist or "").strip()
                    browse_id = ""
                if not raw_name:
                    continue
                split_names = [raw_name]
                entry_browse_id = browse_id
                if len(artists) == 1:
                    split_names = self._split_compound_artist_text(raw_name)
                    if len(split_names) > 1:
                        entry_browse_id = ""
                for name in split_names:
                    key = name.casefold()
                    if key in seen:
                        continue
                    seen.add(key)
                    entries.append({"name": name, "browseId": entry_browse_id})
        if entries:
            return entries

        author = (track or {}).get("author")
        if isinstance(author, dict):
            author = author.get("name")
        fallback = str(
            (track or {}).get("artist")
            or author
            or self._artist_str(track or {})
            or ""
        ).strip()
        return [{"name": name, "browseId": ""} for name in self._split_compound_artist_text(fallback)]

    def _open_artist_entry(self, entry: dict):
        if not isinstance(entry, dict):
            return
        self._open_artist_name(
            str(entry.get("name") or "").strip(),
            str(entry.get("browseId") or "").strip(),
        )

    def _set_player_artist_label(self, track: dict | None):
        label = getattr(self, "lbl_artist", None)
        if label is None or not _qt_is_valid(label):
            return
        entries = self._track_artist_entries(track or {})
        label._artist_entries = list(entries)
        if not entries:
            label.setText(self._artist_str(track or {}))
            return
        sep = f'<span style="color:{TEXT_MUTED};"> - </span>'
        parts = []
        for idx, entry in enumerate(entries):
            name = html.escape(str(entry.get("name") or "").strip())
            if not name:
                continue
            if parts:
                parts.append(sep)
            parts.append(
                f'<a href="{idx}" style="color:{TEXT_MUTED}; text-decoration:none;">{name}</a>'
            )
        label.setText("".join(parts) if parts else self._artist_str(track or {}))

    def _player_artist_link_activated(self, link: str):
        label = getattr(self, "lbl_artist", None)
        entries = list(getattr(label, "_artist_entries", []) or [])
        try:
            idx = int(str(link or "").strip())
        except Exception:
            idx = -1
        if 0 <= idx < len(entries):
            self._open_artist_entry(entries[idx])
            return
        if self.queue and 0 <= self.queue_index < len(self.queue):
            self._open_artist(self.queue[self.queue_index])

    @staticmethod
    def _split_artist_names(track: dict) -> list:
        """Track'ten sanatçı isimlerini ayrı ayrı döndürür.
        YTM bazen tek objede 'Joker & Zagos' döndürdüğü için ' & ' ile de böler."""
        artists = track.get("artists")
        names = []
        if isinstance(artists, list):
            for a in artists:
                if isinstance(a, dict) and a.get("name"):
                    # Tek objede birleşik isim varsa böl
                    for part in str(a["name"]).split(" & "):
                        part = part.strip()
                        if part:
                            names.append(part)
        return names

    @staticmethod
    def _split_artist_names(track: dict) -> list:
        artists = (track or {}).get("artists")
        names = []
        seen = set()
        if isinstance(artists, list):
            for a in artists:
                raw_name = str(a.get("name") or "").strip() if isinstance(a, dict) else str(a or "").strip()
                if not raw_name:
                    continue
                for part in ArtistMixin._split_compound_artist_text(raw_name):
                    key = part.casefold()
                    if key in seen:
                        continue
                    seen.add(key)
                    names.append(part)
        return names

    def _show_artist_menu(self, entries: list):
        from PySide6.QtWidgets import QMenu
        from PySide6.QtGui import QCursor
        menu = QMenu()
        menu.setStyleSheet(
            "QMenu{background:#131b2a; border:1px solid rgba(255,255,255,0.12); border-radius:8px; padding:4px;}"
            "QMenu::item{color:#e8eaf0; padding:6px 18px; font-size:13px; border-radius:6px;}"
            "QMenu::item:selected{background:rgba(255,255,255,0.10);}"
        )
        for entry in list(entries or []):
            name = str(entry.get("name") or "").strip()
            if not name:
                continue
            action = menu.addAction(name)
            action.triggered.connect(lambda _, artist_entry=dict(entry): self._open_artist_entry(artist_entry))
        menu.exec(QCursor.pos())

    def _artist_clicked(self, event):
        if not (self.queue and self.queue_index != -1):
            return
        track = self.queue[self.queue_index]
        entries = self._track_artist_entries(track)
        if len(entries) <= 1:
            self._open_artist(track)
            return
        self._show_artist_menu(entries)

    def _artist_clicked_for(self, track: dict):
        """Verilen track için sanatçı tıklama — birden fazlaysa popup menü gösterir."""
        entries = self._track_artist_entries(track)
        if len(entries) <= 1:
            self._open_artist(track)
            return
        self._show_artist_menu(entries)

    def _open_artist(self, track: dict):
        entries = self._track_artist_entries(track)
        if entries:
            self._open_artist_entry(entries[0])
            return
        name = self._artist_str(track)
        self._open_artist_name(name)


    def _open_artist_name(self, name: str, browse_id: str = ""):
        if not name or name == "?":
            return
        self.sig.notify.emit(self._tr("artist.loading", name=name))
        self._net_pool.submit(self._fetch_artist, name, browse_id)


    def _fetch_artist_lastfm(self, name: str) -> dict:
        """Last.fm'den sanatçı profili çek (bio, tags, benzer sanatçılar)."""
        try:
            if getattr(self, "_lastfm", None):
                return self._lastfm.get_artist_profile(name) or {}
        except Exception as e:
            log.warning("Last.fm sanatci verisi alinamadi: %s", e)
        return {}

    def _ytm_best_thumbnail_url(self, thumbnails, target: int = 512) -> str:
        """YTMusic thumbnail listesinden en yüksek kaliteli sanatçı görselini seç."""
        if isinstance(thumbnails, dict):
            nested = thumbnails.get("thumbnails")
            thumbnails = nested if isinstance(nested, list) else [thumbnails]
        if not isinstance(thumbnails, list):
            return ""

        best_url = ""
        best_score = -1
        for item in thumbnails:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            if not url:
                continue
            try:
                score = int(item.get("width") or 0) * int(item.get("height") or 0)
            except Exception:
                score = 0
            if score >= best_score:
                best_score = score
                best_url = url

        if not best_url:
            return ""
        try:
            return re.sub(r"=w\d+-h\d+", f"=w{int(target)}-h{int(target)}", best_url)
        except Exception:
            return best_url

    def _ytm_artist_result_name(self, item: dict) -> str:
        if not isinstance(item, dict):
            return ""
        raw = (
            item.get("artist")
            or item.get("name")
            or item.get("title")
            or (item.get("artists") or [{}])[0].get("name", "")
        )
        return str(raw or "").strip()

    def _ytm_artist_summary(self, name: str, browse_id: str = "", target: int = 512) -> dict:
        """Hızlı YTMusic artist araması; overview kartları için Last.fm'siz özet."""
        clean_name = str(name or "").strip()
        clean_browse = str(browse_id or "").strip()
        if not clean_name and not clean_browse:
            return {}

        cache_key = f"__ytm_artist_summary::{clean_browse or clean_name.casefold()}::{target}"
        cached = getattr(self, "_home_cache", {}).get(cache_key)
        if cached:
            try:
                return dict(cached[1] or {})
            except Exception:
                pass

        try:
            results = self._yt_search(clean_name or clean_browse, filter="artists", limit=5, fallback_on_empty=False)
        except Exception as e:
            log.debug("YTMusic sanatçı özeti alınamadı (%s): %s", clean_name or clean_browse, e)
            results = []

        target_norm = self._normalize_feed_text(clean_name)
        picked = None
        for item in results or []:
            if not isinstance(item, dict):
                continue
            item_name = self._ytm_artist_result_name(item)
            item_norm = self._normalize_feed_text(item_name)
            item_browse = str(item.get("browseId") or item.get("channelId") or "").strip()
            if clean_browse and item_browse == clean_browse:
                picked = item
                break
            if target_norm and item_norm == target_norm:
                picked = item
                break
        if picked is None and results:
            picked = next((item for item in results if isinstance(item, dict)), None)
        if not picked:
            return {}

        item_name = self._ytm_artist_result_name(picked) or clean_name
        summary = {
            "name": item_name,
            "browseId": str(picked.get("browseId") or picked.get("channelId") or "").strip(),
            "channelId": str(picked.get("channelId") or picked.get("browseId") or "").strip(),
            "image_url": self._ytm_best_thumbnail_url(
                picked.get("thumbnails") or picked.get("thumbnail") or [],
                target=target,
            ),
            "subscribers": str(picked.get("subscribers") or "").strip(),
            "source": "ytmusic",
        }
        try:
            self._home_cache[cache_key] = (time.time(), summary)
        except Exception:
            pass
        return summary

    def _fetch_artist_ytm(self, name: str, browse_id: str = "") -> dict:
        """YTMusic'ten sanatçı kanalını ara ve tam veriyi çek."""
        if not self.yt:
            return {}
        try:
            if browse_id:
                direct = self._yt_get_artist(browse_id)
                if direct:
                    direct.setdefault("channelId", browse_id)
                    direct.setdefault("browseId", browse_id)
                    return direct
            results = self.yt.search(name, filter="artists", limit=5)
            if not results:
                return {}
            name_lower = name.lower().strip()
            channel_id = None
            for r in results:
                r_name = str(r.get("artist") or r.get("name") or "").lower().strip()
                r_id = r.get("browseId") or r.get("channelId")
                if r_name == name_lower and r_id:
                    channel_id = r_id
                    break
            if not channel_id and results:
                channel_id = (results[0].get("browseId") or results[0].get("channelId"))
            if not channel_id:
                return {}
            data = self._yt_get_artist(channel_id)
            if data:
                data.setdefault("channelId", channel_id)
                data.setdefault("browseId", channel_id)
            return data
        except Exception as e:
            log.warning("YTMusic sanatci aranamadi (%s): %s", name, e)
            return {}

    def _fetch_artist(self, name: str, browse_id: str = ""):
        artist_meta = {}
        yt_artist   = {}
        res         = []

        # YTMusic artık birincil kaynak: Last.fm beklenmediği için sayfa çok daha
        # hızlı açılır ve Last.fm rate-limit/API riskine bağımlılık azalır.
        yt_artist = self._fetch_artist_ytm(name, browse_id)
        if not yt_artist:
            artist_meta = self._fetch_artist_lastfm(name)

        # ── YTMusic verisi ile artist_meta'yı zenginleştir ─────────────────
        if yt_artist:
            artist_meta.setdefault("source", "ytmusic")
            ytm_browse_id = str(
                yt_artist.get("browseId") or yt_artist.get("channelId") or browse_id or ""
            ).strip()
            if ytm_browse_id:
                artist_meta.setdefault("browseId", ytm_browse_id)
            if not artist_meta.get("name"):
                artist_meta["name"] = yt_artist.get("name", name)
            # En iyi thumbnail
            thumbs = yt_artist.get("thumbnails") or []
            if thumbs and not artist_meta.get("image_url"):
                img_url = self._ytm_best_thumbnail_url(thumbs, target=1600)
                if img_url:
                    artist_meta["image_url"] = img_url
            if yt_artist.get("subscribers") and not artist_meta.get("subscribers"):
                artist_meta["subscribers"] = yt_artist["subscribers"]
            # Albümler (browseId ile)
            yt_albums_data = yt_artist.get("albums") or {}
            yt_albums      = []
            if isinstance(yt_albums_data, dict):
                yt_albums = list(yt_albums_data.get("results") or [])
                params    = yt_albums_data.get("params")
                cid       = yt_artist.get("channelId", "")
                if params and cid and len(yt_albums) < 8:
                    try:
                        extra = self._yt_get_artist_albums(cid, params)
                        seen  = {a.get("browseId") for a in yt_albums}
                        for a in (extra or []):
                            if a.get("browseId") not in seen:
                                yt_albums.append(a)
                                seen.add(a.get("browseId"))
                    except Exception as _e:
                        log.debug("Sessiz hata: %s", _e)
            if yt_albums:
                artist_meta["yt_albums"] = yt_albums
            # Singles
            yt_singles_data = yt_artist.get("singles") or {}
            if isinstance(yt_singles_data, dict):
                singles = list(yt_singles_data.get("results") or [])
                params = yt_singles_data.get("params")
                cid = yt_artist.get("channelId", "")
                if params and cid and len(singles) < 12:
                    try:
                        extra = self._yt_get_artist_albums(cid, params)
                        seen = {
                            str(a.get("browseId") or a.get("title") or "").strip().lower()
                            for a in singles
                            if isinstance(a, dict)
                        }
                        for item in extra or []:
                            if not isinstance(item, dict):
                                continue
                            key = str(item.get("browseId") or item.get("title") or "").strip().lower()
                            if key and key not in seen:
                                singles.append(item)
                                seen.add(key)
                    except Exception as _e:
                        log.debug("Sessiz hata: %s", _e)
                if singles:
                    artist_meta["yt_singles"] = singles
            # Bio: YTMusic description'ı Last.fm bio yoksa kullan
            yt_desc = str(yt_artist.get("description") or "").strip()
            if yt_desc and not artist_meta.get("bio"):
                artist_meta["bio"] = yt_desc
            # Benzer sanatçılar: YTMusic related.results'ı Last.fm yoksa kullan
            if not artist_meta.get("similar_artists"):
                related_data = yt_artist.get("related") or {}
                related_items = list(
                    related_data.get("results") or []
                    if isinstance(related_data, dict) else []
                )
                similar = []
                for r in related_items:
                    r_name = str(r.get("title") or r.get("name") or "").strip()
                    if not r_name:
                        continue
                    r_browse_id = str(r.get("browseId") or r.get("channelId") or "").strip()
                    img_url = self._ytm_best_thumbnail_url(
                        r.get("thumbnails") or r.get("thumbnail") or [],
                        target=300,
                    )
                    similar.append({
                        "name": r_name,
                        "image_url": img_url,
                        "browseId": r_browse_id,
                        "source": "ytmusic",
                    })
                if similar:
                    artist_meta["similar_artists"] = similar

        # ── Şarkı listesi: YTMusic get_artist songs + arama ────────────────
        yt_songs = []
        songs_data = yt_artist.get("songs") or {}
        if isinstance(songs_data, dict):
            yt_songs = list(songs_data.get("results") or [])

        if yt_songs and not artist_meta.get("top_tracks"):
            top_tracks = []
            for item in yt_songs[:12]:
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title") or item.get("name") or "").strip()
                if not title:
                    continue
                top_tracks.append({
                    "name": title,
                    "image_url": self._thumb(item, big=True) or "",
                    "playcount": 0,
                    "listeners": 0,
                })
            if top_tracks:
                artist_meta["top_tracks"] = top_tracks

        if yt_songs:
            filtered = self._filter_tracks(yt_songs)
            res = self._rank_artist_tracks_for_page(name, filtered, artist_meta)

        # YTMusic aramasıyla tamamla (daha fazla şarkı)
        try:
            raw = self._yt_search(name, filter="songs", limit=50, fallback_on_empty=False)
            if raw:
                extra_filtered = self._rank_artist_tracks_for_page(
                    name, self._filter_tracks(raw), artist_meta
                )
                if not res:
                    res = extra_filtered
                else:
                    # Mevcut listede olmayan videoId'leri ekle
                    seen_vids = {t.get("videoId") for t in res if t.get("videoId")}
                    for t in extra_filtered:
                        if t.get("videoId") and t["videoId"] not in seen_vids:
                            res.append(t)
                            seen_vids.add(t["videoId"])
        except Exception as e:
            log.debug("Ek arama basarisiz: %s", e)

        # Hiç sonuç yoksa Last.fm top track adlarıyla ara
        if not res:
            try:
                top_tracks = [
                    item.get("name", "")
                    for item in (artist_meta or {}).get("top_tracks", [])
                    if isinstance(item, dict) and item.get("name")
                ]
                query = f"{name} {' '.join(top_tracks[:3])}" if top_tracks else name
                raw = self._yt_search(query, filter="songs", limit=40, fallback_on_empty=True)
                res = self._rank_artist_tracks_for_page(name, self._filter_tracks(raw), artist_meta)
            except Exception as e:
                log.warning("Fallback arama basarisiz: %s", e)

        if not res:
            fallback = self._yt_dlp_search(name, 30)
            res = self._rank_artist_tracks_for_page(
                name, self._filter_tracks(fallback), artist_meta
            )

        self.sig.artist_songs_done.emit(res, name, artist_meta)

    # ══════════════════════════════════════════════════════════════════════════
    # BANNER CAROUSEL
    # ══════════════════════════════════════════════════════════════════════════


    def _rank_artist_tracks_for_page(self, artist_name: str, tracks: list, artist_meta: dict | None = None) -> list:
        if not tracks:
            return []
        meta = artist_meta or {}
        top_track_names = {
            self._normalize_feed_text(item.get("name", ""))
            for item in meta.get("top_tracks", [])
            if isinstance(item, dict) and item.get("name")
        }
        artist_norm = self._normalize_feed_text(artist_name)
        scored = []
        for idx, track in enumerate(tracks):
            norm_track = self._normalize_feed_track(track)
            if not norm_track:
                continue
            haystack, artist_hay = self._feed_text_blobs(norm_track)
            score = 100.0 - idx
            if artist_norm and artist_norm in artist_hay:
                score += 45
            elif artist_norm and artist_norm in haystack:
                score += 20
            title_norm = self._normalize_feed_text(norm_track.get("title", ""))
            for top_name in top_track_names:
                if not top_name:
                    continue
                if title_norm == top_name:
                    score += 40
                    break
                if top_name in title_norm or title_norm in top_name:
                    score += 22
                    break
            scored.append((score, idx, norm_track))
        scored.sort(key=lambda item: (-item[0], item[1]))
        all_ranked = [track for _, _, track in scored]
        # Sanatçı adı hiç geçmeyen şarkıları filtrele (yeterli eşleşme varsa)
        if artist_norm:
            matching = []
            for t in all_ranked:
                _, artist_hay = self._feed_text_blobs(t)
                if artist_norm in artist_hay:
                    matching.append(t)
            if len(matching) >= 5:
                return matching
        return all_ranked


    def _open_artist_album(self, artist_name: str, album_name: str, browse_id: str = ""):
        clean_artist = str(artist_name or "").strip()
        clean_album  = str(album_name  or "").strip()
        if not clean_artist or not clean_album:
            return
        self.sig.notify.emit(self._tr("artist.album_loading", name=clean_album))
        self._net_pool.submit(self._fetch_artist_album, clean_artist, clean_album, browse_id)


    def _play_artist_release(self, artist_name: str, album_name: str, browse_id: str = ""):
        clean_artist = str(artist_name or "").strip()
        clean_album = str(album_name or "").strip()
        if not clean_artist or not clean_album:
            return
        self.sig.notify.emit(self._tr("artist.album_loading", name=clean_album))
        self._net_pool.submit(self._fetch_artist_release_for_play, clean_artist, clean_album, browse_id)


    def _fetch_artist_release_for_play(self, artist_name: str, album_name: str, browse_id: str = ""):
        resolved_tracks = []
        album_thumb_url = ""
        if browse_id:
            try:
                album_data = self._yt_get_album(browse_id)
                if album_data and album_data.get("tracks"):
                    album_thumbs = album_data.get("thumbnails") or []
                    if album_thumbs:
                        best = max(
                            album_thumbs,
                            key=lambda t: t.get("width", 0) * t.get("height", 0),
                            default=None,
                        )
                        if best:
                            album_thumb_url = best.get("url", "")
                    for track in album_data["tracks"]:
                        if not isinstance(track, dict) or not track.get("videoId"):
                            continue
                        item = dict(track)
                        if not (item.get("thumbnails") or []) and album_thumb_url:
                            item["thumbnails"] = [{"url": album_thumb_url}]
                        item.setdefault("album", {"name": album_data.get("title", album_name)})
                        if not item.get("artists"):
                            item["artists"] = album_data.get("artists") or [{"name": artist_name}]
                        resolved_tracks.append(item)
            except Exception as e:
                log.warning("YTMusic single/EP oynatilamadi (%s): %s", browse_id, e)

        if not resolved_tracks:
            try:
                raw = self._yt_search(
                    f"{artist_name} {album_name}",
                    filter="songs",
                    limit=8,
                    fallback_on_empty=False,
                )
                ranked = self._rank_album_tracks_for_page(
                    artist_name,
                    album_name,
                    album_name,
                    self._filter_tracks(raw),
                )
                resolved_tracks = ranked[:4]
            except Exception as e:
                log.warning("Single/EP arama ile oynatilamadi (%s / %s): %s", artist_name, album_name, e)

        if resolved_tracks:
            self.sig.play_all_tracks.emit(resolved_tracks)
        else:
            self.sig.notify.emit(self._tr("artist.no_tracks"))


    def _fetch_artist_album(self, artist_name: str, album_name: str, browse_id: str = ""):
        resolved_tracks = []
        album_meta      = {}

        # ── Yol 1: YTMusic browseId ile direkt albüm yükle ─────────────────
        if browse_id:
            try:
                album_data = self._yt_get_album(browse_id)
                if album_data and album_data.get("tracks"):
                    # Albüm thumbnail'ini her parçaya koy (parça thumbnail yoksa)
                    album_thumbs = album_data.get("thumbnails") or []
                    album_thumb_url = ""
                    if album_thumbs:
                        best = max(album_thumbs,
                                   key=lambda t: t.get("width", 0) * t.get("height", 0),
                                   default=None)
                        if best:
                            album_thumb_url = best.get("url", "")

                    for track in album_data["tracks"]:
                        if not isinstance(track, dict):
                            continue
                        if not track.get("videoId"):
                            continue
                        t = dict(track)
                        # Thumbnail yoksa albümden al
                        if not (t.get("thumbnails") or []):
                            if album_thumb_url:
                                t["thumbnails"] = [{"url": album_thumb_url}]
                        t.setdefault("album", {"name": album_data.get("title", album_name)})
                        if not t.get("artists"):
                            t["artists"] = album_data.get("artists") or [{"name": artist_name}]
                        resolved_tracks.append(t)

                    album_meta = {
                        "name":       album_data.get("title", album_name),
                        "artist":     artist_name,
                        "year":       str(album_data.get("year") or ""),
                        "image_url":  album_thumb_url,
                        "tracks":     resolved_tracks,
                        "track_count": len(resolved_tracks),
                        "description": album_data.get("description", ""),
                        "type":       album_data.get("type", "Album"),
                    }
                    self.sig.artist_album_done.emit(resolved_tracks, artist_name, album_name, album_meta)
                    return
            except Exception as e:
                log.warning("YTMusic album yuklenemedi (%s): %s — Last.fm fallback", browse_id, e)

        # ── Yol 2: Last.fm + per-track YTMusic araması (eski yöntem) ───────
        try:
            if getattr(self, "_lastfm", None):
                album_meta = self._lastfm.get_album_profile(artist_name, album_name) or {}
        except Exception as e:
            log.warning("Album Last.fm verisi alinamadi: %s", e)
            album_meta = {}

        track_rows = list(album_meta.get("tracks") or [])
        for row in track_rows:
            if not isinstance(row, dict):
                continue
            track_name = str(row.get("name", "") or "").strip()
            if not track_name:
                continue

            query = f"{artist_name} {track_name} {album_name}"
            try:
                raw = self._yt_search(query, filter="songs", limit=10, fallback_on_empty=False)
                ranked = self._rank_album_tracks_for_page(
                    artist_name, album_name, track_name, self._filter_tracks(raw)
                )
                if not ranked:
                    ranked = self._rank_album_tracks_for_page(
                        artist_name, album_name, track_name,
                        self._filter_tracks(self._yt_dlp_search(query, 8)),
                    )
                if not ranked:
                    continue
                chosen = dict(ranked[0])
                chosen["album"] = {"name": album_name}
                if not chosen.get("duration_seconds"):
                    chosen["duration_seconds"] = int(row.get("duration_seconds") or 0)
                resolved_tracks.append(chosen)
            except Exception as e:
                log.warning("Album parcasi cozumlenemedi (%s / %s): %s", artist_name, track_name, e)

        self.sig.artist_album_done.emit(resolved_tracks, artist_name, album_name, album_meta)


    def _rank_album_tracks_for_page(self, artist_name: str, album_name: str, track_name: str, tracks: list) -> list:
        if not tracks:
            return []

        artist_norm = self._normalize_feed_text(artist_name)
        album_norm = self._normalize_feed_text(album_name)
        track_norm = self._normalize_feed_text(track_name)
        scored = []

        for idx, track in enumerate(tracks):
            norm_track = self._normalize_feed_track(track)
            if not norm_track:
                continue

            haystack, artist_hay = self._feed_text_blobs(norm_track)
            score = 100.0 - idx
            title_norm = self._normalize_feed_text(norm_track.get("title", ""))

            album_obj = norm_track.get("album")
            candidate_album = ""
            if isinstance(album_obj, dict):
                candidate_album = self._normalize_feed_text(album_obj.get("name", ""))
            elif isinstance(album_obj, str):
                candidate_album = self._normalize_feed_text(album_obj)

            if title_norm == track_norm:
                score += 60
            elif track_norm and (track_norm in title_norm or title_norm in track_norm):
                score += 28

            if artist_norm and artist_norm in artist_hay:
                score += 35
            elif artist_norm and artist_norm in haystack:
                score += 12

            if candidate_album and album_norm:
                if candidate_album == album_norm:
                    score += 32
                elif album_norm in candidate_album or candidate_album in album_norm:
                    score += 16
            elif album_norm and album_norm in haystack:
                score += 8

            scored.append((score, idx, norm_track))

        scored.sort(key=lambda item: (-item[0], item[1]))
        return [track for _, _, track in scored]


    def _home_rotate_banner(self):
        stack = getattr(self, "_home_banner_stack", None)
        dots  = getattr(self, "_home_banner_dots",  None)
        if not stack or not _qt_is_valid(stack) or stack.count() < 2:
            return
        idx = (stack.currentIndex() + 1) % stack.count()
        stack.setCurrentIndex(idx)
        if dots:
            for i, d in enumerate(dots):
                if not _qt_is_valid(d):
                    continue
                d.setStyleSheet(
                    f"color:{get_accent() if i == idx else TEXT_MUTED}; "
                    f"font-size:10px; background:transparent;")

    # ══════════════════════════════════════════════════════════════════════════
    # BOYUTLANDIRMA — Çerçevesiz pencere için kenar tutamağı
    # ══════════════════════════════════════════════════════════════════════════

    _RESIZE_MARGIN = 6   # kenar algılama px
