"""Mixin for Lyrics functionality."""
import logging
import re
from bisect import bisect_right

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QAbstractItemView, QListWidgetItem

from core.constants import TEXT_MUTED
from core.theme import get_accent
from ui.dialogs import open_lyrics_dialog
from utils.helpers import qt_is_valid

log = logging.getLogger("iqtMusic")


class LyricsMixin:

    def open_lyrics(self):
        open_lyrics_dialog(self)

    def _lyrics_cache_get(self, vid: str):
        cache = getattr(self, "_lyrics_cache", None)
        if not isinstance(cache, dict):
            self._lyrics_cache = {}
            cache = self._lyrics_cache
        lines = cache.get(vid)
        return list(lines) if isinstance(lines, list) else None

    def _lyrics_cache_set(self, vid: str, lines: list):
        if not vid or not self._lyrics_result_is_cacheable(lines):
            return
        cache = getattr(self, "_lyrics_cache", None)
        if not isinstance(cache, dict):
            self._lyrics_cache = {}
            cache = self._lyrics_cache
        cache[vid] = list(lines)

    def _lyrics_result_is_cacheable(self, lines: list) -> bool:
        if not isinstance(lines, list) or not lines:
            return False
        ignored = {
            self._tr("lyrics.not_found").strip().lower(),
            self._tr("lyrics.error").strip().lower(),
        }
        for entry in lines:
            try:
                text = str(entry[2] or "").strip().lower()
            except Exception:
                continue
            if text and text not in ignored:
                return True
        return False

    def _next_lyrics_request_id(self) -> int:
        rid = int(getattr(self, "_lyrics_request_id", 0) or 0) + 1
        self._lyrics_request_id = rid
        return rid

    def _request_lyrics(self, vid: str, track: dict | None = None, *, force: bool = False) -> int:
        if not vid:
            self._lyr_pending_vid = ""
            self._lyr_pending_request_id = 0
            return 0

        request_id = self._next_lyrics_request_id()
        self._lyr_pending_vid = vid
        self._lyr_pending_request_id = request_id

        cached = None if force else self._lyrics_cache_get(vid)
        if cached is not None:
            self.sig.lyrics_done.emit(vid, request_id, cached)
            return request_id

        self._net_pool.submit(self._fetch_lyrics, vid, request_id, dict(track or {}))
        return request_id

    def _lyrics_extract_track_meta(self, track: dict | None = None) -> dict:
        track = track or {}
        title = str(track.get("title", "") or "").strip()
        artist = str(self._artist_str(track) or "").strip()
        album = ""
        album_data = track.get("album")
        if isinstance(album_data, dict):
            album = str(album_data.get("name", "") or album_data.get("title", "") or "").strip()
        elif isinstance(album_data, str):
            album = album_data.strip()
        duration = track.get("duration_seconds")
        try:
            duration = int(duration) if duration is not None else None
        except Exception:
            duration = None
        return {
            "title": title,
            "artist": artist,
            "album": album,
            "duration": duration,
        }

    def _lyrics_clean_title(self, title: str) -> str:
        value = str(title or "").strip()
        if not value:
            return ""
        patterns = (
            r"\s*[\(\[]\s*(official|audio|video|music video|lyric video|lyrics|visualizer|performance|live|remaster(?:ed)?|sped up|slowed(?:\s*\+\s*reverb)?|karaoke|cover)[^)\]]*[\)\]]",
            r"\s*-\s*(official|audio|video|music video|lyric video|lyrics|visualizer|live|remaster(?:ed)?).*$",
            r"\s+(feat\.?|ft\.?|featuring)\s+.+$",
        )
        for pattern in patterns:
            value = re.sub(pattern, "", value, flags=re.IGNORECASE).strip()
        value = re.sub(r"\s{2,}", " ", value).strip(" -_")
        return value

    def _lyrics_title_variants(self, title: str) -> list[str]:
        base = str(title or "").strip()
        cleaned = self._lyrics_clean_title(base)
        variants = []
        for candidate in (
            base,
            cleaned,
            re.sub(r"\s*[\(\[].*?[\)\]]", "", cleaned).strip(),
            re.sub(r"\s+-\s+.*$", "", cleaned).strip(),
        ):
            candidate = re.sub(r"\s{2,}", " ", str(candidate or "").strip()).strip(" -_")
            if candidate and candidate not in variants:
                variants.append(candidate)
        return variants

    def _lyrics_artist_variants(self, artist: str) -> list[str]:
        base = str(artist or "").strip()
        variants = []
        split_tokens = (",", "&", " x ", " X ", " feat. ", " ft. ", " featuring ")
        if base:
            variants.append(base)
        for token in split_tokens:
            if token in base:
                candidate = base.split(token, 1)[0].strip()
                if candidate and candidate not in variants:
                    variants.append(candidate)
        return variants

    def _lyrics_parse_text_blob(self, raw: str) -> list:
        parsed = []
        if not raw:
            return parsed
        lines = str(raw).splitlines()
        is_lrc = any(re.match(r"\[\d+:\d+", line) for line in lines)
        if is_lrc:
            for line in lines:
                match = re.match(r"\[(\d+):(\d+)(?:\.(\d+))?\](.*)", line)
                if not match:
                    continue
                frac = str(match.group(3) or "0")
                ms = int((frac + "00")[:3])
                total = (int(match.group(1)) * 60 + int(match.group(2))) * 1000 + ms
                text = str(match.group(4) or "").strip()
                if text:
                    parsed.append((total, -1, text))
            return parsed

        for line in lines:
            text = str(line or "").strip()
            if text:
                parsed.append((-1, -1, text))
        return parsed

    def _lyrics_parse_lrclib_payload(self, payload: dict) -> list:
        if not isinstance(payload, dict):
            return []
        for key in ("syncedLyrics", "synced_lyrics", "plainLyrics", "plain_lyrics"):
            parsed = self._lyrics_parse_text_blob(payload.get(key, ""))
            if parsed:
                return parsed
        return []

    def _lyrics_lrclib_get(self, title: str, artist: str, album: str = "", duration: int | None = None):
        session = getattr(self, "_http", None)
        if session is None or not title or not artist:
            return None
        params = {"track_name": title, "artist_name": artist}
        if album:
            params["album_name"] = album
        if duration:
            params["duration"] = int(duration)
        try:
            resp = session.get("https://lrclib.net/api/get", params=params, timeout=8)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, dict) else None
        except Exception as e:
            log.debug("LRCLIB get hatası (%s / %s): %s", artist, title, e)
            return None

    def _lyrics_lrclib_search(self, title: str, artist: str, duration: int | None = None) -> list:
        session = getattr(self, "_http", None)
        if session is None or not title:
            return []
        params = {"track_name": title}
        if artist:
            params["artist_name"] = artist
        if duration:
            params["duration"] = int(duration)
        try:
            resp = session.get("https://lrclib.net/api/search", params=params, timeout=8)
            if resp.status_code == 404:
                return []
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, list) else []
        except Exception as e:
            log.debug("LRCLIB search hatası (%s / %s): %s", artist, title, e)
            return []

    def _lyrics_fetch_fallback_sources(self, track: dict | None = None) -> list:
        meta = self._lyrics_extract_track_meta(track)
        titles = self._lyrics_title_variants(meta.get("title", ""))
        artists = self._lyrics_artist_variants(meta.get("artist", ""))
        duration = meta.get("duration")
        album = meta.get("album", "")
        if not titles or not artists:
            return []

        seen_keys = set()
        for title in titles[:4]:
            for artist in artists[:3]:
                key = (title.lower(), artist.lower())
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                parsed = self._lyrics_parse_lrclib_payload(
                    self._lyrics_lrclib_get(title, artist, album=album, duration=duration)
                )
                if parsed:
                    return parsed

        for title in titles[:4]:
            for artist in artists[:3]:
                candidates = self._lyrics_lrclib_search(title, artist, duration=duration)
                if not candidates:
                    continue
                for item in candidates[:5]:
                    parsed = self._lyrics_parse_lrclib_payload(item)
                    if parsed:
                        return parsed
        return []

    def _lyrics_fetch_ovh(self, artist: str, title: str) -> list:
        """lyrics.ovh ücretsiz API ile şarkı sözü çeker."""
        session = getattr(self, "_http", None)
        if session is None or not artist or not title:
            return []
        from urllib.parse import quote as _quote
        try:
            url = f"https://api.lyrics.ovh/v1/{_quote(artist)}/{_quote(title)}"
            resp = session.get(url, timeout=8)
            if resp.status_code != 200:
                return []
            data = resp.json()
            raw = str(data.get("lyrics", "") or "").strip()
            if not raw:
                return []
            return self._lyrics_parse_text_blob(raw)
        except Exception as e:
            log.debug("lyrics.ovh hatası (%s / %s): %s", artist, title, e)
            return []

    def _lyrics_fetch_yt_description(self, vid: str) -> list:
        """YouTube video açıklamasından şarkı sözlerini çekmeye çalışır."""
        if not vid:
            return []
        try:
            import yt_dlp
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "extract_flat": False,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(
                    f"https://www.youtube.com/watch?v={vid}",
                    download=False,
                )
            desc = str((info or {}).get("description", "") or "").strip()
            if not desc:
                return []

            lines = [l.strip() for l in desc.splitlines()]

            # Açıklamada sözler bölümü işaretleyicisi varsa yalnızca o kısımdan al
            _marker_pat = re.compile(
                r"(şarkı\s*sözler|lyrics?\s*:|sözler?\s*:|\bsözleriyle\b)",
                re.IGNORECASE,
            )
            marker_idx = None
            for i, line in enumerate(lines):
                if _marker_pat.search(line):
                    marker_idx = i + 1  # işaretleyiciden sonraki satırdan başla
                    break
            if marker_idx is not None:
                lines = lines[marker_idx:]

            # Kredi/meta satırlarını ve genel spam'i filtrele
            _skip_pats = re.compile(
                r"(https?://|www\.|@\w|#\w|"
                r"\bfollow\b|\bsubscribe\b|\bstream\b|\bdownload\b|\bout now\b|"
                r"\bSpotify\b|\bApple Music\b|\binstagram\b|\btwitter\b|\bfacebook\b|"
                r"\bYouTube\b|\bYouTubeMusic\b|\bDistrokid\b|\bSoundCloud\b|"
                r"\bTikTok\b|\bBeatport\b|\bLinktree\b|"
                r"\bDirected by\b|\bProduced by\b|\bMixed by\b|\bMastered by\b|"
                r"\bRecorded by\b|\bVideo by\b|\bFilmed by\b|\bEdited by\b|"
                r"\bLabel\b|\bPublishing\b|\bDistribution\b|\bManagement\b|"
                r"\bBooking\b|\bPR\b|\bA&R\b)"
                r"|\b(AC|DP|DOP|Gaffer|Colorist|Cast|Crew)\b.*:",
                re.IGNORECASE,
            )
            # "Anahtar: Değer" kredileri: kısa ön ek + iki nokta (örn. "1st AC: X")
            _credit_pat = re.compile(r"^[^:]{1,30}:\s+\S")

            text_lines = []
            for line in lines:
                if not line:
                    continue
                if _skip_pats.search(line):
                    continue
                if _credit_pat.match(line):
                    continue
                # Tamamen büyük harf ve kısa satırlar → şirket/prodüksiyon adı
                stripped = re.sub(r"[^A-Za-z]", "", line)
                if stripped and stripped == stripped.upper() and len(line) < 40:
                    continue
                text_lines.append(line)

            # Sözler bölümü işaretçisi bulunamadıysa ek kalite kontrolü yap
            if marker_idx is None:
                if len(text_lines) < 8:
                    return []
                avg_len = sum(len(l) for l in text_lines) / len(text_lines)
                if avg_len > 75:
                    return []

            if len(text_lines) < 4:
                return []

            return [(-1, -1, l) for l in text_lines]
        except Exception as e:
            log.debug("YT açıklama sözleri hatası (%s): %s", vid, e)
            return []

    def _fetch_lyrics(self, vid: str, request_id: int = 0, track: dict | None = None):
        try:
            wp = self._yt_get_watch_playlist(vid)
            raw = None
            timed = []
            if wp and "lyrics" in wp:
                ld = self._yt_get_lyrics(browseId=wp["lyrics"], timestamps=True)
                if ld and ld.get("hasTimestamps") and "lyrics" in ld:
                    for line in ld["lyrics"]:
                        text = getattr(line, "text", None)
                        start_time = getattr(line, "start_time", None)
                        end_time = getattr(line, "end_time", None)
                        if isinstance(line, dict):
                            text = line.get("text", text)
                            start_time = line.get("start_time", start_time)
                            end_time = line.get("end_time", end_time)
                        if text and start_time is not None:
                            timed.append((
                                int(start_time),
                                int(end_time) if end_time is not None else -1,
                                text.strip(),
                            ))
                    if timed:
                        self._lyrics_cache_set(vid, timed)
                        self.sig.lyrics_done.emit(vid, int(request_id or 0), timed)
                        return
                ld = self._yt_get_lyrics(browseId=wp["lyrics"])
                if ld and "lyrics" in ld:
                    raw = ld["lyrics"]

            parsed = self._lyrics_parse_text_blob(raw)

            # lrclib.net
            if not parsed:
                parsed = self._lyrics_fetch_fallback_sources(track)

            # lyrics.ovh
            if not parsed:
                meta = self._lyrics_extract_track_meta(track)
                titles = self._lyrics_title_variants(meta.get("title", ""))
                artists = self._lyrics_artist_variants(meta.get("artist", ""))
                for title in titles[:2]:
                    for artist in artists[:2]:
                        parsed = self._lyrics_fetch_ovh(artist, title)
                        if parsed:
                            break
                    if parsed:
                        break

            # YouTube video açıklaması
            if not parsed and vid:
                parsed = self._lyrics_fetch_yt_description(vid)

            if not parsed:
                parsed = [(-1, -1, self._tr("lyrics.not_found"))]
            self._lyrics_cache_set(vid, parsed)
            self.sig.lyrics_done.emit(vid, int(request_id or 0), parsed)
        except Exception as e:
            log.warning("Lyrics hatası: %s", e)
            self.sig.lyrics_done.emit(vid, int(request_id or 0), [(-1, -1, self._tr("lyrics.error"))])

    def _lyrics_placeholder(self, text: str):
        lyr_list = getattr(self, "_lyr_list", None)
        if lyr_list is None or not qt_is_valid(lyr_list):
            return
        delegate = lyr_list.itemDelegate()
        if hasattr(delegate, "clear_cache"):
            delegate.clear_cache()
        lyr_list.clear()
        item = QListWidgetItem(text)
        item.setTextAlignment(Qt.AlignCenter)
        lyr_list.addItem(item)
        lyr_list.scheduleDelayedItemsLayout()
        lyr_list.viewport().update()

    def _lyrics_update_sync_button(self):
        button = getattr(self, "_lyr_sync_button", None)
        if button is None or not qt_is_valid(button):
            helper = getattr(self, "_lyrics_apply_sync_capabilities", None)
            if callable(helper):
                try:
                    helper()
                except Exception:
                    pass
            return

        has_real = bool(getattr(self, "_lyr_has_real_timestamps", False))
        auto_sync = bool(getattr(self, "_lyr_auto_sync", True))
        has_lines = bool(getattr(self, "lyrics_data", None))
        if not has_real:
            button.setText(
                self._tr("lyrics.sync_estimated") if has_lines else self._tr("lyrics.sync_unavailable")
            )
            button.setStyleSheet(
                f"""
                QPushButton {{
                    background: rgba(255,255,255,0.06);
                    border: 1px solid rgba(255,255,255,0.12);
                    border-radius: 12px;
                    color: {TEXT_MUTED};
                    padding: 0 14px;
                    font-size: 11px;
                    font-weight: 700;
                }}
                """
            )
            helper = getattr(self, "_lyrics_apply_sync_capabilities", None)
            if callable(helper):
                try:
                    helper()
                except Exception:
                    pass
            return

        button.setText(self._tr("lyrics.sync") if auto_sync else self._tr("lyrics.manual"))
        if auto_sync:
            button.setStyleSheet(
                f"""
                QPushButton {{
                    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                        stop:0 {get_accent()}DD, stop:1 {get_accent()}88);
                    border: none;
                    border-radius: 12px;
                    color: white;
                    padding: 0 14px;
                    font-size: 11px;
                    font-weight: 700;
                }}
                """
            )
        else:
            button.setStyleSheet(
                f"""
                QPushButton {{
                    background: rgba(255,255,255,0.06);
                    border: 1px solid rgba(255,255,255,0.12);
                    border-radius: 12px;
                    color: {TEXT_MUTED};
                    padding: 0 14px;
                    font-size: 11px;
                    font-weight: 700;
                }}
                """
            )
        helper = getattr(self, "_lyrics_apply_sync_capabilities", None)
        if callable(helper):
            try:
                helper()
            except Exception:
                pass

    def _lyrics_update_font_label(self):
        label = getattr(self, "_lyr_font_label", None)
        if label is None or not qt_is_valid(label):
            return
        size = int(getattr(self, "_lyr_font_size", 15) or 15)
        label.setText(f"{size} pt")

    def _lyrics_set_font_size(self, size: int):
        self._lyr_font_size = max(12, min(int(size), 24))
        self._lyrics_update_font_label()
        lyr_list = getattr(self, "_lyr_list", None)
        if lyr_list is not None and qt_is_valid(lyr_list):
            delegate = lyr_list.itemDelegate()
            if hasattr(delegate, "clear_cache"):
                delegate.clear_cache()
            lyr_list.scheduleDelayedItemsLayout()
            lyr_list.viewport().update()

    def _lyrics_toggle_always_on_top(self):
        self._lyr_always_on_top = not bool(getattr(self, "_lyr_always_on_top", False))
        self._lyrics_apply_window_flags()

    def _lyrics_toggle_cinema_mode(self):
        win = getattr(self, "_lyr_win", None)
        button = getattr(self, "_lyr_cinema_button", None)
        if win is None or not qt_is_valid(win):
            return
        if win.isFullScreen():
            win.showNormal()
            if button is not None and qt_is_valid(button):
                button.setText(self._tr("lyrics.cinema"))
        else:
            win.showFullScreen()
            if button is not None and qt_is_valid(button):
                button.setText(self._tr("lyrics.window"))

    def _lyrics_apply_window_flags(self):
        win = getattr(self, "_lyr_win", None)
        if win is None or not qt_is_valid(win):
            return
        on_top = bool(getattr(self, "_lyr_always_on_top", False))
        flags = win.windowFlags() | Qt.Window | Qt.FramelessWindowHint
        if on_top:
            flags |= Qt.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowStaysOnTopHint
        was_visible = win.isVisible()
        win.setWindowFlags(flags)
        if was_visible:
            win.show()
            win.raise_()
            win.activateWindow()

        button = getattr(self, "_lyr_pin_button", None)
        if button is not None and qt_is_valid(button):
            button.setText(self._tr("lyrics.pin") if not on_top else self._tr("lyrics.always_on_top"))

    def _lyrics_copy_line(self, idx: int | None = None, text: str | None = None):
        copied = text or ""
        if not copied:
            if idx is None:
                idx = int(getattr(self, "_lyr_current_idx", -1) or -1)
            lines = getattr(self, "lyrics_data", []) or []
            if idx is None or idx < 0:
                idx = 0 if lines else -1
            if 0 <= idx < len(lines):
                copied = str(lines[idx][2] or "")
        copied = copied.strip()
        if not copied:
            self.sig.notify.emit(self._tr("lyrics.no_line_to_copy"))
            return
        QApplication.clipboard().setText(copied)
        self.sig.notify.emit(self._tr("lyrics.line_copied"))

    def _lyrics_update_preview(self, idx: int | None = None):
        label = getattr(self, "_lyr_next_preview_label", None)
        if label is None or not qt_is_valid(label):
            return

        lines = getattr(self, "lyrics_data", []) or []
        has_real = bool(getattr(self, "_lyr_has_real_timestamps", False))
        if not lines:
            label.setText(self._tr("lyrics.loading"))
            return
        if not has_real:
            label.setText(self._tr("lyrics.preview_requires_timestamps"))
            return

        if idx is None:
            idx = int(getattr(self, "_lyr_current_idx", -1) or -1)
        next_idx = max(0, idx + 1)
        if next_idx >= len(lines):
            label.setText(self._tr("lyrics.last_line"))
            return
        text = str(lines[next_idx][2] or "").strip()
        if len(text) > 120:
            text = text[:117].rstrip() + "..."
        label.setText(text or self._tr("lyrics.next_line_not_ready"))

    def _lyrics_refresh_for_track(self, track: dict, *, force_request: bool = False):
        win = getattr(self, "_lyr_win", None)
        if win is None or not qt_is_valid(win):
            self._cleanup_lyrics_dialog_refs()
            return

        title = track.get("title", "") or ""
        artist = self._artist_str(track)
        vid = str(track.get("videoId", "") or "")

        tb = getattr(self, "_lyr_tb", None)
        if tb is not None and qt_is_valid(tb):
            tb.setTitle(title)
        title_lbl = getattr(self, "_lyr_title_lbl", None)
        if title_lbl is not None and qt_is_valid(title_lbl):
            title_lbl.setText(title)
        artist_lbl = getattr(self, "_lyr_artist_lbl", None)
        if artist_lbl is not None and qt_is_valid(artist_lbl):
            artist_lbl.setText(artist)
        cover = getattr(self, "_lyr_cover", None)
        if cover is not None and qt_is_valid(cover):
            thumb = self._thumb(track, big=True)
            if thumb:
                self._load_image(thumb, cover, (56, 56))
            else:
                cover.clear()

        self._lyr_bound_vid = vid
        self._lyr_current_idx = -1
        self._lyr_progress = 0.0
        self._lyr_progress_target = 0.0
        self._lyr_has_real_timestamps = False
        self._lyrics_start_times = []
        self.lyrics_data = []
        self._lyrics_update_sync_button()
        self._lyrics_update_preview(-1)
        self._lyrics_placeholder(self._tr("lyrics.loading"))
        self._request_lyrics(vid, track, force=force_request)

    def _cleanup_lyrics_dialog_refs(self):
        sync_timer = getattr(self, "_lyr_sync", None)
        if sync_timer is not None and qt_is_valid(sync_timer):
            try:
                sync_timer.stop()
            except Exception:
                pass

        self._lyr_pending_vid = ""
        self._lyr_pending_request_id = 0
        self._lyr_bound_vid = ""
        self._lyrics_start_times = []
        self.lyrics_data = []
        self._lyr_current_idx = -1
        self._lyr_progress = 0.0
        self._lyr_progress_target = 0.0
        self._lyr_has_real_timestamps = False

        for name in (
            "_lyr_win",
            "_lyr_tb",
            "_lyr_cover",
            "_lyr_title_lbl",
            "_lyr_artist_lbl",
            "_lyr_sync_button",
            "_lyr_effect_button",
            "_lyr_more_toggle",
            "_lyr_offset_slider",
            "_lyr_offset_label",
            "_lyr_offset_toggle",
            "_lyr_preview_toggle",
            "_lyr_size_down",
            "_lyr_size_up",
            "_lyr_size_label",
            "_lyr_font_label",
            "_lyr_font_down",
            "_lyr_font_up",
            "_lyr_pin_button",
            "_lyr_copy_button",
            "_lyr_cinema_button",
            "_lyr_list",
            "_lyr_sync",
            "_lyr_next_preview_label",
            "_lyrics_refresh_ui_texts",
            "_lyrics_apply_sync_capabilities",
        ):
            setattr(self, name, None)

    def _on_lyrics(self, vid: str, request_id: int, lines: list):
        if self._lyrics_result_is_cacheable(lines):
            self._lyrics_cache_set(vid, lines)
        if (
            str(vid or "") != str(getattr(self, "_lyr_pending_vid", "") or "")
            or int(request_id or 0) != int(getattr(self, "_lyr_pending_request_id", 0) or 0)
        ):
            return

        lyr_list = getattr(self, "_lyr_list", None)
        if lyr_list is None or not qt_is_valid(lyr_list):
            if getattr(self, "_lyr_win", None) is not None and not qt_is_valid(getattr(self, "_lyr_win", None)):
                self._cleanup_lyrics_dialog_refs()
            return

        self.lyrics_data = list(lines or [])
        self._lyr_bound_vid = str(vid or "")
        self._lyr_has_real_timestamps = any(int(ts) >= 0 for ts, _end, _text in self.lyrics_data)
        self._lyrics_start_times = [int(ts) for ts, _end, _text in self.lyrics_data] if self._lyr_has_real_timestamps else []
        self._lyr_current_idx = -1
        self._lyr_progress = 0.0
        self._lyr_progress_target = 0.0

        delegate = lyr_list.itemDelegate()
        if hasattr(delegate, "clear_cache"):
            delegate.clear_cache()

        lyr_list.clear()
        for _ts, _end, text in self.lyrics_data:
            item = QListWidgetItem(text)
            item.setTextAlignment(Qt.AlignCenter)
            lyr_list.addItem(item)
        lyr_list.scheduleDelayedItemsLayout()
        lyr_list.viewport().update()

        self._lyrics_update_sync_button()
        self._lyrics_update_preview(-1)

    def _lyrics_find_index(self, cur_ms: int) -> int:
        starts = getattr(self, "_lyrics_start_times", []) or []
        if not starts:
            return -1

        prev_idx = int(getattr(self, "_lyr_current_idx", -1) or -1)
        if 0 <= prev_idx < len(starts):
            next_ts = starts[prev_idx + 1] if prev_idx + 1 < len(starts) else None
            if cur_ms >= starts[prev_idx] and (next_ts is None or cur_ms < next_ts):
                return prev_idx
            if next_ts is not None and cur_ms >= next_ts:
                idx = prev_idx + 1
                while idx + 1 < len(starts) and cur_ms >= starts[idx + 1]:
                    idx += 1
                return idx

        idx = bisect_right(starts, cur_ms) - 1
        return idx if idx >= 0 else -1

    def _sync_lyrics(self):
        lyr_list = getattr(self, "_lyr_list", None)
        if (
            lyr_list is None or not qt_is_valid(lyr_list)
            or not getattr(self, "lyrics_data", None)
        ):
            return
        try:
            if not self.player.is_playing():
                return
            cur = max(0, int(self.player.get_time()) + int(getattr(self, "_lyr_offset_ms", 0) or 0))
        except Exception:
            return

        if getattr(self, "_lyr_has_real_timestamps", False):
            idx = self._lyrics_find_index(cur)
            prev_idx = int(getattr(self, "_lyr_current_idx", -1) or -1)
            auto_sync = bool(getattr(self, "_lyr_auto_sync", True))

            if idx != -1:
                if auto_sync:
                    lyr_list.setCurrentRow(idx)
                    if idx != prev_idx:
                        item = lyr_list.item(idx)
                        if item is not None:
                            lyr_list.scrollToItem(item, QAbstractItemView.PositionAtCenter)

                start_ts = int(self.lyrics_data[idx][0] or 0)
                explicit_end = int(self.lyrics_data[idx][1] or -1)
                next_ts = (
                    int(self.lyrics_data[idx + 1][0])
                    if idx + 1 < len(self.lyrics_data)
                    else int(self.player.get_length() or start_ts)
                )
                end_ts = explicit_end if explicit_end > start_ts else next_ts
                progress = 0.0 if end_ts <= start_ts else (cur - start_ts) / (end_ts - start_ts)
                target = max(0.0, min(progress, 1.0))
                if idx != prev_idx:
                    self._lyr_progress = target
                else:
                    current = float(getattr(self, "_lyr_progress", 0.0) or 0.0)
                    self._lyr_progress = current + (target - current) * 0.28
                self._lyr_progress_target = target
                self._lyr_current_idx = idx
                if idx != prev_idx:
                    self._lyrics_update_preview(idx)
                lyr_list.viewport().update()
                return

        # Tahmini senkron: gerçek zaman damgası yoksa şarkı süresine göre kayan satır
        self._lyr_current_idx = -1
        self._lyr_progress = 0.0
        self._lyr_progress_target = 0.0
        lyr_list.viewport().update()
