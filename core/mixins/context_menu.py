"""Mixin for ContextMenu functionality."""
import logging
import re
from datetime import datetime

log = logging.getLogger("iqtMusic")

from core.theme import get_accent
from utils.helpers import create_icon, open_folder, safe_save_json
from core.constants import (
    BG_BLACK, BG_DARK, BG_CARD, BG_ELEVATED, BORDER_COLOR,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED
)
from ui.titlebar import TitleBar

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QMenu, QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QFrame, QPushButton, QWidget
)
from PySide6.QtGui import QCursor


class ContextMenuMixin:

    def _artist_like_key(self, name: str) -> str:
        return " ".join(str(name or "").strip().casefold().split())

    def _is_artist_liked(self, name: str) -> bool:
        key = self._artist_like_key(name)
        if not key:
            return False
        return any(
            self._artist_like_key(item.get("name", "")) == key
            for item in getattr(self, "liked_artists", [])
            if isinstance(item, dict)
        )

    def _artist_like_payload(self, name: str, browse_id: str = "", artist_meta: dict | None = None) -> dict:
        meta = dict(artist_meta or {})
        clean_name = str(name or meta.get("name") or "").strip()
        image_url = str(meta.get("image_url") or meta.get("thumbnail") or "").strip()
        return {
            "name": clean_name,
            "browseId": str(browse_id or meta.get("browseId") or meta.get("channelId") or "").strip(),
            "image_url": image_url,
            "artist_meta": meta,
            "liked_at": datetime.now().isoformat(timespec="seconds"),
        }

    def _toggle_artist_like(self, name: str, browse_id: str = "", artist_meta: dict | None = None, btn=None):
        clean_name = str(name or "").strip()
        key = self._artist_like_key(clean_name)
        if not key:
            return
        liked = list(getattr(self, "liked_artists", []) or [])
        target = next(
            (
                item for item in liked
                if isinstance(item, dict) and self._artist_like_key(item.get("name", "")) == key
            ),
            None,
        )
        if target:
            liked.remove(target)
            is_liked = False
            msg = self._tr("artist.like_removed", name=clean_name)
        else:
            liked.insert(0, self._artist_like_payload(clean_name, browse_id, artist_meta))
            is_liked = True
            msg = self._tr("artist.like_added", name=clean_name)
        self.liked_artists = liked[:500]
        safe_save_json(self.liked_artists_file, self.liked_artists)
        if btn is not None:
            btn.setIcon(create_icon("heart_on" if is_liked else "heart_off", get_accent() if is_liked else TEXT_MUTED, 18))
            btn.setToolTip(self._tr("artist.unlike" if is_liked else "artist.like"))
        self.sig.notify.emit(msg)
        if getattr(self, "current_page", "") == "favorites":
            self.page_favs()

    def _ctx_menu(self, pos, track):
        acc = get_accent()
        t = self._tr
        m = QMenu(self)
        m.setStyleSheet(f"""
            QMenu {{
                background: #1A1A2E;
                border: 1px solid {acc}33;
                border-radius: 12px;
                padding: 6px 0;
                color: white;
            }}
            QMenu::item {{
                padding: 9px 16px 9px 12px;
                font-size: 13px;
                font-weight: 600;
                border-radius: 8px;
                margin: 1px 4px;
            }}
            QMenu::item:selected {{
                background: {acc}28;
                color: {acc};
            }}
            QMenu::separator {{
                height: 1px;
                background: rgba(255,255,255,0.07);
                margin: 4px 12px;
            }}
        """)

        def _act(label, icon_name, fn, color=None):
            a = m.addAction(label, fn)
            a.setIcon(create_icon(icon_name, color or acc, 16))
            return a

        def _start_radio():
            self._fetch_radio(track["videoId"])
            self.sig.notify.emit(t("context_menu.radio_started", title=track["title"]))

        _act(t("context_menu.play_now"),      "play",         lambda: self.force_play(track))
        _act(t("context_menu.add_to_queue"),  "queue",        lambda: self._add_to_queue(track))
        _act(t("context_menu.play_next"),     "skip_next",    lambda: self._add_next(track))
        _act(t("context_menu.start_radio"),   "radio",        _start_radio)
        _act(t("context_menu.track_details"), "music",        lambda: self._open_track_details(track))
        _act(t("context_menu.copy_link"),     "link",         lambda: self._copy_link(track),
             color="#7CB8FF")
        m.addSeparator()

        vid = track.get("videoId", "")
        if self.dl.is_downloaded(vid):
            _act(t("context_menu.remove_downloaded"), "delete", lambda: self._del_dl(track),
                 color="#FF6B6B")
        else:
            _act(t("context_menu.download"), "download", lambda: self._dl_track(track))

        pl = m.addMenu(t("context_menu.add_to_playlist"))
        pl.setIcon(create_icon("playlist_add", acc, 16))
        if not self.playlists:
            pl.addAction(t("context_menu.no_playlist")).setEnabled(False)
        else:
            for pn in self.playlists:
                pl.addAction(pn, lambda n=pn: self._add_to_pl(n, track))
        m.exec(pos)


    def _player_ctx_menu(self):
        if self.queue and self.queue_index != -1:
            self._ctx_menu(QCursor.pos(), self.queue[self.queue_index])


    def _copy_link(self, track):
        vid = track.get("videoId", "")
        if vid:
            QApplication.clipboard().setText(f"https://www.youtube.com/watch?v={vid}")
            self.sig.notify.emit(self._tr("context_menu.link_copied"))

    # ══════════════════════════════════════════════════════════════════════════
    # FAVORİ / İNDİRME / GEÇMİŞ / İSTATİSTİK
    # ══════════════════════════════════════════════════════════════════════════


    def _safe_int(self, value) -> int:
        if value in (None, ""):
            return 0
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, str):
            cleaned = re.sub(r"[^\d-]", "", value.strip())
            if not cleaned or cleaned == "-":
                return 0
            value = cleaned
        try:
            return int(value)
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
            return 0


    def _fmt_track_metric(self, value: int) -> str:
        value = max(0, self._safe_int(value))
        if not value:
            return self._tr("track_details.unknown")
        return f"{value:,}".replace(",", ".")


    def _extract_track_details(self, track: dict) -> dict:
        t = self._tr
        track = track if isinstance(track, dict) else {}
        vid = str(track.get("videoId") or track.get("video_id") or "").strip()
        cache_key = f"track-info::{vid}" if vid else ""
        if cache_key:
            cached = self._track_info_cache.get(cache_key)
            if cached:
                return dict(cached)

        title = str(track.get("title") or "?").strip() or "?"
        artist = str(self._artist_str(track) or "?").strip() or "?"
        album = ""
        album_browse_id = ""
        album_data = track.get("album")
        if isinstance(album_data, dict):
            album = str(album_data.get("name") or album_data.get("title") or "").strip()
            album_browse_id = str(
                album_data.get("id") or album_data.get("browseId") or ""
            ).strip()
        elif isinstance(album_data, str):
            album = album_data.strip()

        duration_sec = self._safe_int(track.get("duration_seconds"))
        if not duration_sec:
            duration_text = str(track.get("duration") or "").strip()
            if duration_text and ":" in duration_text:
                try:
                    parts = [int(p) for p in duration_text.split(":") if p.isdigit()]
                    if 1 < len(parts) <= 3:
                        total = 0
                        for part in parts:
                            total = total * 60 + part
                        duration_sec = total
                except Exception as _e:
                    log.debug("Sessiz hata: %s", _e)

        cover_url = str(self._thumb(track, big=True) or "").strip()
        year = str(track.get("year") or "").strip()
        popularity = 0

        if album_browse_id:
            try:
                album_payload = self._yt_get_album(album_browse_id)
                if isinstance(album_payload, dict) and album_payload:
                    album = str(album_payload.get("title") or album or "").strip()
                    if not year:
                        year = str(album_payload.get("year") or "").strip()
                    if not cover_url:
                        thumbs = album_payload.get("thumbnails") or []
                        if isinstance(thumbs, list) and thumbs:
                            cover_url = str(thumbs[-1].get("url") or "").strip()
            except Exception as _e:
                log.debug("Sessiz hata: %s", _e)

        if vid:
            try:
                song_payload = self._yt_get_song(vid)
                video_details = song_payload.get("videoDetails") or {}
                micro = (
                    song_payload.get("microformat", {})
                    .get("microformatDataRenderer", {})
                )
                if not duration_sec:
                    duration_sec = self._safe_int(video_details.get("lengthSeconds"))
                if artist in {"", "?"}:
                    artist = str(video_details.get("author") or artist or "?").strip()
                popularity = self._safe_int(video_details.get("viewCount"))
                if not year:
                    date_text = str(
                        micro.get("publishDate") or micro.get("uploadDate") or ""
                    ).strip()
                    match = re.search(r"(19|20)\d{2}", date_text)
                    if match and match.group(0) != "1969":
                        year = match.group(0)
                if not cover_url:
                    thumb_root = micro.get("thumbnail") or {}
                    thumbs = thumb_root.get("thumbnails") if isinstance(thumb_root, dict) else []
                    if isinstance(thumbs, list) and thumbs:
                        cover_url = str(thumbs[-1].get("url") or "").strip()
            except Exception as _e:
                log.debug("Sessiz hata: %s", _e)

        details = {
            "title": title,
            "artist": artist or "?",
            "album": album or t("track_details.default_album"),
            "year": year or t("track_details.unknown"),
            "duration": self._fmt(duration_sec * 1000) if duration_sec else t("track_details.unknown"),
            "duration_seconds": duration_sec,
            "popularity": (
                t("track_details.views", count=self._fmt_track_metric(popularity))
                if popularity else t("track_details.unknown")
            ),
            "popularity_value": popularity,
            "video_id": vid or "-",
            "cover_url": cover_url,
        }
        if cache_key:
            self._track_info_cache.set(cache_key, details)
        return details


    def _open_track_details(self, track: dict):
        details = self._extract_track_details(track)
        acc = get_accent()
        t = self._tr

        dlg = QDialog(self)
        dlg.setModal(True)
        dlg.setWindowFlags(dlg.windowFlags() | Qt.FramelessWindowHint)
        dlg.setWindowTitle(t("track_details.title"))
        dlg.resize(520, 400)
        dlg.setStyleSheet(f"""
            QDialog {{
                background: {BG_DARK};
                color: {TEXT_PRIMARY};
            }}
            QFrame#TrackInfoCard {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 rgba(22,31,49,250),
                    stop:1 rgba(13,19,32,252));
                border: 1px solid {acc}30;
                border-radius: 18px;
            }}
            QFrame#TrackInfoHero {{
                background: {BG_CARD};
                border: 1px solid {BORDER_COLOR};
                border-radius: 14px;
            }}
            QFrame#TrackInfoRow {{
                background: {BG_ELEVATED};
                border: 1px solid {BORDER_COLOR};
                border-radius: 12px;
            }}
            QLabel#TrackInfoTitle {{
                color: {TEXT_PRIMARY};
                font-size: 17px;
                font-weight: 800;
                background: transparent;
            }}
            QLabel#TrackInfoArtist {{
                color: {TEXT_SECONDARY};
                font-size: 12px;
                font-weight: 600;
                background: transparent;
            }}
            QLabel#TrackInfoKey {{
                color: {TEXT_MUTED};
                font-size: 11px;
                font-weight: 700;
                background: transparent;
            }}
            QLabel#TrackInfoValue {{
                color: {TEXT_PRIMARY};
                font-size: 12px;
                font-weight: 700;
                background: transparent;
            }}
            QPushButton {{
                background: {acc};
                color: {BG_BLACK};
                border: none;
                border-radius: 12px;
                padding: 10px 16px;
                font-weight: 800;
            }}
            QPushButton:hover {{
                background: {acc}DD;
            }}
        """)

        host_l = QVBoxLayout(dlg)
        host_l.setContentsMargins(0, 0, 0, 0)
        host_l.setSpacing(0)

        tb = TitleBar(dlg, title=t("track_details.title"))
        tb.setStyleSheet(f"background:{BG_DARK}; color:white;")
        host_l.addWidget(tb)

        sep_top = QFrame()
        sep_top.setFixedHeight(1)
        sep_top.setStyleSheet(f"background:{acc}44;")
        host_l.addWidget(sep_top)

        content = QWidget()
        content.setStyleSheet(f"background:{BG_DARK};")
        host_l.addWidget(content, 1)

        root = QVBoxLayout(content)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        card = QFrame()
        card.setObjectName("TrackInfoCard")
        card_l = QVBoxLayout(card)
        card_l.setContentsMargins(16, 16, 16, 16)
        card_l.setSpacing(12)
        root.addWidget(card)

        hero = QFrame()
        hero.setObjectName("TrackInfoHero")
        hero_l = QHBoxLayout(hero)
        hero_l.setContentsMargins(12, 12, 12, 12)
        hero_l.setSpacing(12)
        card_l.addWidget(hero)

        cover = QLabel()
        cover.setFixedSize(88, 88)
        cover.setAlignment(Qt.AlignCenter)
        cover.setStyleSheet(
            f"background: rgba(255,255,255,0.04); border: 1px solid {acc}33; "
            "border-radius: 14px;"
        )
        hero_l.addWidget(cover, 0, Qt.AlignTop)
        if details["cover_url"]:
            try:
                self._load_image(details["cover_url"], cover, (88, 88))
            except Exception as _e:
                log.debug("Sessiz hata: %s", _e)

        meta_wrap = QVBoxLayout()
        meta_wrap.setContentsMargins(0, 0, 0, 0)
        meta_wrap.setSpacing(5)
        hero_l.addLayout(meta_wrap, 1)

        title_lbl = QLabel(details["title"])
        title_lbl.setObjectName("TrackInfoTitle")
        title_lbl.setWordWrap(True)
        meta_wrap.addWidget(title_lbl)

        artist_lbl = QLabel(details["artist"])
        artist_lbl.setObjectName("TrackInfoArtist")
        artist_lbl.setWordWrap(True)
        meta_wrap.addWidget(artist_lbl)

        vid_lbl = QLabel(t("track_details.video_id", video_id=details["video_id"]))
        vid_lbl.setObjectName("TrackInfoArtist")
        vid_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        meta_wrap.addWidget(vid_lbl)
        meta_wrap.addStretch(1)

        def _meta_row(label: str, value: str):
            row = QFrame()
            row.setObjectName("TrackInfoRow")
            row_l = QHBoxLayout(row)
            row_l.setContentsMargins(12, 8, 12, 8)
            row_l.setSpacing(10)

            key_lbl = QLabel(label)
            key_lbl.setObjectName("TrackInfoKey")
            key_lbl.setFixedWidth(96)
            row_l.addWidget(key_lbl, 0, Qt.AlignTop)

            value_lbl = QLabel(value)
            value_lbl.setObjectName("TrackInfoValue")
            value_lbl.setWordWrap(True)
            value_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
            row_l.addWidget(value_lbl, 1)
            card_l.addWidget(row)

        _meta_row(t("track_details.album"), details["album"])
        _meta_row(t("track_details.release_year"), details["year"])
        _meta_row(t("track_details.duration"), details["duration"])
        _meta_row(t("track_details.popularity"), details["popularity"])

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color: {BORDER_COLOR};")
        card_l.addWidget(sep)

        close_btn = QPushButton(t("track_details.close"))
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(dlg.accept)

        foot = QHBoxLayout()
        foot.setContentsMargins(0, 0, 0, 0)
        foot.addStretch(1)
        foot.addWidget(close_btn)
        root.addLayout(foot)

        dlg.exec()


    def _toggle_fav(self, track, btn=None):
        vid    = track.get("videoId", "")
        target = next((f for f in self.favorites if f.get("videoId") == vid), None)
        if target:
            self.favorites.remove(target)
            msg = self._tr("context_menu.likes_removed")
            if btn: btn.setIcon(create_icon("heart_off", TEXT_MUTED, 18))
        else:
            self.favorites.insert(0, track)
            msg = self._tr("context_menu.likes_added")
            if btn: btn.setIcon(create_icon("heart_on", get_accent(), 18))
        safe_save_json(self.fav_file, self.favorites)
        self.sig.notify.emit(msg)
        # Çalma barındaki kalp ikonunu senkronize et
        if self.queue and self.queue_index != -1:
            cur_vid = self.queue[self.queue_index].get("videoId", "")
            if cur_vid == vid:
                self._update_fav_btn(track)
        # Ara sayfasındaki kalp ikonlarını senkronize et
        is_fav_now = target is None  # target was None means we just added
        search_btns = getattr(self, "_search_fav_buttons", {})
        for b in list(search_btns.get(vid, [])):
            try:
                from utils.helpers import qt_is_valid as _qv
                if not _qv(b):
                    continue
                b.setIcon(create_icon(
                    "heart_on" if is_fav_now else "heart_off",
                    get_accent() if is_fav_now else TEXT_MUTED, 18))
            except Exception:
                pass
        if self.current_page == "favorites":
            self.page_favs()


    def _toggle_fav_current(self):
        if self.queue and self.queue_index != -1:
            self._toggle_fav(self.queue[self.queue_index], self.btn_fav_bar)


    def _update_fav_btn(self, track):
        vid    = track.get("videoId", "")
        is_fav = any(f.get("videoId") == vid for f in self.favorites)
        self.btn_fav_bar.setIcon(create_icon(
            "heart_on" if is_fav else "heart_off",
            get_accent() if is_fav else TEXT_MUTED, 18))
        self.btn_fav_bar.setToolTip(
            self._tr("player.tooltip.unfavorite" if is_fav else "player.tooltip.favorite")
        )


    def _dl_current(self):
        if self.queue and self.queue_index != -1:
            self._dl_track(self.queue[self.queue_index])


    def _dl_track(self, track):
        self.dl.start(track)
        self.sig.notify.emit(self._tr("context_menu.download_starting", title=track.get("title", "?")))


    def _del_dl(self, track):
        vid = track.get("videoId", "")
        if self.dl.delete(vid):
            self.sig.notify.emit(self._tr("context_menu.download_deleted"))
            if self.current_page == "downloads":
                self.page_downloads()


    def _on_dl_progress(self, vid: str, pct: int):
        self._dl_progress[vid] = pct


    def _on_dl_done(self, track):
        vid = track.get("videoId", "")
        self._dl_progress.pop(vid, None)
        self.sig.notify.emit(self._tr("context_menu.download_done", title=track.get("title", "?")))
        if self.current_page == "downloads":
            self.page_downloads()


    def _on_dl_error(self, vid: str, msg: str):
        self._dl_progress.pop(vid, None)
        self.sig.notify.emit(self._tr("context_menu.download_failed"))
        log.error("İndirme hatası (%s): %s", vid, msg)


    def _open_dl_folder(self):
        open_folder(self.dl.dl_dir)
