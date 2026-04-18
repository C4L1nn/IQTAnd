"""Editorial home page renderer."""
import logging
import os
import re
import time
from datetime import datetime

from PySide6.QtCore import QObject, QEvent, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor, QBrush, QCursor, QLinearGradient, QPainter, QPainterPath,
    QPen, QPixmap, QRadialGradient, QImage, QFont,
)
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QMenu, QPushButton, QScrollArea,
    QStackedWidget, QVBoxLayout, QWidget,
)

import core.constants as _C
import pages.home as _H
from core.geo import normalize_region, region_display_name
from pages.common import _build_page_header
from ui.widgets import SkeletonWidget
from utils.helpers import qt_is_valid, repair_mojibake_text

log = logging.getLogger("iqtMusic")

_HOME_CACHE_VERSION = 18
_HOME_DEFAULT_HOST_MIN_WIDTH = 1344
_HOME_CURATED_HOST_MIN_WIDTH = 920
_HOME_CURATED_REFLOW_DELAY_MS = 140
_HOME_CURATED_COVER_TTL_SEC = 6 * 60 * 60
_HOME_CURATED_COVER_MAX_EDGE = 960
_HOME_CURATED_COVER_JPEG_QUALITY = 94
_TABS = (
    ("home.tab.trends_tr", "feed:charts.tr", ""),
    ("home.tab.global", "feed:charts.global", ""),
    ("home.tab.new_releases", "feed:new.music", ""),
    ("home.tab.rap", "feed:tr.rap", ""),
    ("home.tab.pop", "feed:tr.pop", ""),
    ("home.tab.chill", "feed:chill", ""),
)
_HERO_FEEDS = (
    ("home.feed.charts_tr.title", "feed:charts.tr", "home.feed.charts_tr.hero_desc"),
    ("home.feed.new_trending.title", "feed:new.music", "home.feed.new_trending.hero_desc"),
    ("home.feed.global_top.title", "feed:charts.global", "home.feed.global_top.hero_desc"),
)
_LIVE_FEEDS = (
    ("home.feed.charts_tr.title", "feed:charts.tr", "home.feed.charts_tr.live_desc"),
    ("home.feed.new_trending.title", "feed:new.music", "home.feed.new_trending.live_desc"),
)
_SPOTLIGHT_FEEDS = (
    ("home.feed.charts_tr.title", "feed:charts.tr", "home.feed.charts_tr.spotlight_desc"),
    ("home.feed.new_trending.title", "feed:new.music", "home.feed.new_trending.spotlight_desc"),
    ("home.feed.tr_pop.title", "feed:tr.pop", "home.feed.tr_pop.spotlight_desc"),
    ("home.feed.tr_rap.title", "feed:tr.rap", "home.feed.tr_rap.spotlight_desc"),
)
_TR_UPPER_MAP = str.maketrans({
    "i": "İ",
    "ı": "I",
    "ğ": "Ğ",
    "ü": "Ü",
    "ö": "Ö",
    "ş": "Ş",
    "ç": "Ç",
})


def _content_region(app) -> str:
    return normalize_region(getattr(app, "_content_region", "TR") or "TR")


def _content_region_name(app) -> str:
    return region_display_name(_content_region(app), getattr(app, "_language", "tr"))


def _region_cache_suffix(app) -> str:
    return f"{getattr(app, '_language', 'tr')}::{_content_region(app)}"


def _regional_title(app, label_key: str, query: str = "") -> str:
    region = _content_region(app)
    name = _content_region_name(app)
    lang = str(getattr(app, "_language", "tr") or "tr").lower()
    if query == "feed:charts.tr":
        return f"{name} Trend" if lang.startswith("tr") else f"{name} Trends"
    if query == "feed:new.music" and region != "TR":
        return f"{name} Yeni Çıkanlar" if lang.startswith("tr") else f"New in {name}"
    if query == "feed:tr.pop" and region != "TR":
        return f"{name} Pop"
    if query == "feed:tr.rap" and region != "TR":
        return f"{name} Rap"
    return app._tr(label_key)


def _regional_desc(app, desc_key: str, query: str = "") -> str:
    region = _content_region(app)
    name = _content_region_name(app)
    lang = str(getattr(app, "_language", "tr") or "tr").lower()
    if region != "TR":
        if query == "feed:charts.tr":
            return f"{name} bölgesinde şu an öne çıkan şarkılar." if lang.startswith("tr") else f"Songs trending in {name} right now."
        if query == "feed:new.music":
            return f"{name} için yeni çıkan şarkılar ve taze hitler." if lang.startswith("tr") else f"Fresh releases and new hits for {name}."
        if query in {"feed:tr.pop", "feed:tr.rap"}:
            genre = "rap" if query.endswith("rap") else "pop"
            return f"{name} için öne çıkan {genre} şarkıları." if lang.startswith("tr") else f"Standout {genre} tracks for {name}."
    return app._tr(desc_key)


def _cache_get(app, key, ttl=None):
    item = getattr(app, "_home_cache", {}).get(key)
    if not item:
        return None
    ts, val = item
    if (time.time() - float(ts or 0)) > int(ttl or getattr(app, "_home_cache_ttl", 1800)):
        return None
    return val


def _cache_set(app, key, val):
    app._home_cache[key] = (time.time(), val)


def _clear(layout):
    while layout and layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().hide()
            item.widget().deleteLater()
        elif item.layout():
            _clear(item.layout())


def _curated_home_cards_cache_key(app):
    return f"__home_curated_cards_v6::{_region_cache_suffix(app)}"


def _curated_grid_available_width(app):
    refs = getattr(app, "_home_refs", {})
    box = refs.get("playlist_grid_box")
    if box is not None and qt_is_valid(box):
        width = int(box.width() or 0)
        if width >= 320:
            return width
    scroll = refs.get("scroll_area")
    if scroll is not None and qt_is_valid(scroll):
        try:
            width = int(scroll.viewport().width() or 0) - 72
            if width >= 320:
                return width
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
    host = refs.get("scroll_host")
    if host is not None and qt_is_valid(host):
        width = int(host.width() or 0) - 72
        if width >= 320:
            return width
    return 1200


def _curated_grid_metrics(app):
    available = max(320, _curated_grid_available_width(app))
    spacing = 16
    min_card_width = 220
    max_columns = 5
    columns = max(1, min(max_columns, (available + spacing) // (min_card_width + spacing)))
    raw_card_width = max(208, int((available - ((columns - 1) * spacing)) / max(1, columns)))
    width_step = 32
    card_width = max(208, int(raw_card_width / width_step) * width_step)
    art_height = max(138, min(196, int(card_width * 0.68)))
    card_height = art_height + (110 if card_width >= 240 else 102)
    metrics = {
        "available": available,
        "spacing": spacing,
        "columns": int(columns),
        "card_width": int(card_width),
        "card_height": int(card_height),
        "card_radius": 26 if card_width >= 280 else 24,
        "card_padding": 14 if card_width >= 260 else 12,
        "art_width": int(card_width - (28 if card_width >= 260 else 24)),
        "art_height": int(art_height),
        "art_radius": 22 if card_width >= 280 else 18,
        "title_px": 16 if card_width >= 280 else 15,
        "subtitle_px": 12 if card_width >= 240 else 11,
        "meta_px": 11,
        "badge_px": 10 if card_width < 240 else 11,
        "play_size": 40 if card_width >= 280 else 36,
    }
    metrics["signature"] = (
        metrics["columns"],
        metrics["card_width"],
    )
    return metrics


def _set_curated_host_min_width(app, minimum):
    host = getattr(app, "_home_refs", {}).get("scroll_host")
    if host is None or not qt_is_valid(host):
        return
    try:
        host.setMinimumWidth(int(minimum))
    except Exception as _e:
        log.debug("Sessiz hata: %s", _e)


def _schedule_curated_grid_reflow(app):
    refs = getattr(app, "_home_refs", {})
    items = list(refs.get("playlist_grid_items") or [])
    if not items or getattr(app, "current_page", None) != "home":
        return
    box = refs.get("playlist_grid_box")
    if box is None or not qt_is_valid(box) or not box.isVisible():
        return
    seq = int(getattr(app, "_home_curated_grid_reflow_seq", 0) or 0) + 1
    app._home_curated_grid_reflow_seq = seq

    def _apply(expected_seq=seq):
        if expected_seq != getattr(app, "_home_curated_grid_reflow_seq", 0):
            return
        current_refs = getattr(app, "_home_refs", {})
        current_box = current_refs.get("playlist_grid_box")
        if current_box is None or not qt_is_valid(current_box) or not current_box.isVisible():
            return
        metrics = _curated_grid_metrics(app)
        if metrics["signature"] == current_refs.get("playlist_grid_metrics"):
            return
        _render_curated_playlist_grid(app, current_refs.get("playlist_grid_items") or [])

    QTimer.singleShot(_HOME_CURATED_REFLOW_DELAY_MS, _apply)


def _home_track_cover_urls(app, tracks, limit=1):
    urls = []
    seen = set()
    for track in list(tracks or []):
        if not isinstance(track, dict):
            continue
        thumb = app._thumb(track, big=True) or app._thumb(track, big=False)
        thumb = str(thumb or "").strip()
        if not thumb or thumb in seen:
            continue
        seen.add(thumb)
        urls.append(thumb)
        if len(urls) >= max(1, int(limit or 1)):
            break
    return urls


class _CuratedGridResizeFilter(QObject):
    def __init__(self, app):
        super().__init__(app)
        self.app = app

    def eventFilter(self, watched, event):
        try:
            if event is not None and event.type() in {QEvent.Resize, QEvent.Show}:
                _schedule_curated_grid_reflow(self.app)
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
        return super().eventFilter(watched, event)


def _next_ui_token(app):
    token = int(getattr(app, "_home_ui_token_seq", 0) or 0) + 1
    if token > 1000000000:
        token = 1
    app._home_ui_token_seq = token
    return token


def _tr_upper(text):
    return str(text or "").translate(_TR_UPPER_MAP).upper()


def _header(text):
    acc = _H.get_accent()
    wrap = QFrame()
    row = QHBoxLayout(wrap)
    row.setContentsMargins(0, 8, 0, 8)
    row.setSpacing(10)
    bar = QFrame()
    bar.setFixedSize(4, 18)
    bar.setStyleSheet(
        f"background:qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 {acc}, stop:1 {_H.get_accent_hover()});"
        "border:none; border-radius:2px;"
    )
    lbl = QLabel(_H._clean_section_title(text))
    lbl.setStyleSheet(f"font-size:20px; font-weight:900; color:{_H.TEXT_PRIMARY}; background:transparent;")
    row.addWidget(bar, 0, Qt.AlignVCenter)
    row.addWidget(lbl, 0, Qt.AlignVCenter)
    row.addStretch()
    return wrap


def _solid_btn():
    return f"""
        QPushButton {{
            background:{_H.get_accent()}; color:#081208; border:none; border-radius:14px;
            padding:0 18px; font-size:13px; font-weight:900;
        }}
        QPushButton:hover {{ background:{_H.get_accent_hover()}; }}
    """


def _ghost_btn():
    return f"""
        QPushButton {{
            background:rgba(255,255,255,0.04); color:{_H.TEXT_PRIMARY};
            border:1px solid rgba(255,255,255,0.08); border-radius:14px;
            padding:0 16px; font-size:13px; font-weight:800;
        }}
        QPushButton:hover {{ color:{_H.get_accent()}; border-color:{_H.get_accent()}55; }}
    """


def _tab_btn(active):
    if active:
        return f"""
            QPushButton {{
                background:{_H.get_accent()}; color:#081208; border:none; border-radius:16px;
                padding:0 16px; font-size:12px; font-weight:900;
            }}
        """
    return f"""
        QPushButton {{
            background:qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {_H.BG_ELEVATED}, stop:1 {_H.BG_CARD});
            color:{_H.TEXT_PRIMARY}; border:1px solid {_H.BORDER_COLOR}; border-radius:16px;
            padding:0 16px; font-size:12px; font-weight:800;
        }}
        QPushButton:hover {{ background:{_H.BG_CARD_HOVER}; border-color:{_H.get_accent()}55; color:{_H.get_accent()}; }}
    """


def _intro(app):
    t = app._tr
    hour = datetime.now().hour
    if 5 <= hour < 12:
        greet = t("home.intro.morning")
    elif 12 <= hour < 18:
        greet = t("home.intro.day")
    elif 18 <= hour < 22:
        greet = t("home.intro.evening")
    else:
        greet = t("home.intro.night")
    counts = {}
    for tr in list(app.history[:36]):
        artist = app._artist_str(tr)
        if artist and artist != "?":
            counts[artist] = counts.get(artist, 0) + 1
    top_artist = max(counts, key=counts.get) if counts else ""
    sub = t("home.intro.subtitle")
    if top_artist:
        sub += t("home.intro.top_artist", artist=top_artist)
    return greet, sub


def _guess_query(title):
    title = str(title or "").strip()
    if not title:
        return "feed:new.music"
    if title in _C.SMART_FEED_ALIASES:
        return _C.SMART_FEED_ALIASES[title]
    norm = " ".join(title.lower().split())
    if "global" in norm:
        return "feed:charts.global"
    if "trend" in norm or "turkiye" in norm or "türkiye" in norm or "turkey" in norm:
        return "feed:charts.tr"
    if "biggest hits" in norm or "top hits" in norm or "viral" in norm:
        return "feed:charts.global"
    if "new" in norm or "fresh" in norm or "yeni" in norm:
        return "feed:new.music"
    if "rap" in norm:
        return "feed:tr.rap"
    if "rock" in norm:
        return "feed:tr.rock"
    if "pop" in norm:
        return "feed:tr.pop"
    if "chill" in norm or "acoustic" in norm:
        return "feed:chill"
    return "feed:new.music"


def _buttons(app, limit=8):
    key = f"__home_bundle::buttons::{_region_cache_suffix(app)}::{limit}"
    cached = _cache_get(app, key)
    if cached:
        return list(cached)
    items = []
    try:
        items = list(app._get_ytm_mood_buttons(limit=limit) or [])
    except Exception as _e:
        log.debug("Sessiz hata: %s", _e)
    seen = {str(q).strip().lower() for _, q, _ in items}
    for label, query, ftype in list(_H.CATEGORY_BUTTONS):
        norm = str(query).strip().lower()
        if norm in seen:
            continue
        items.append((label, query, ftype))
        seen.add(norm)
        if len(items) >= limit:
            break
    _cache_set(app, key, items[:limit])
    return list(items[:limit])


def _personal(app, limit=8):
    key = "__home_bundle::personal"
    cached = _cache_get(app, key, ttl=300)
    if cached is not None:
        return list(cached)
    items, seen = [], set()
    mix_name = app._resolve_mix_playlist_name() if hasattr(app, "_resolve_mix_playlist_name") else app._tr("nav.mix")
    pools = (
        ("DEVAM ET", list(app.history[:4])),
        ("FAVORİ", list(app.favorites[:3])),
        ("OFFLINE", list(app.dl.all_tracks()[:3])),
        ("MIX", list(app.playlists.get(mix_name, [])[:2])),
    )
    for badge, tracks in pools:
        for tr in tracks:
            vid = str(tr.get("videoId", "") or "").strip()
            if not vid or vid in seen:
                continue
            seen.add(vid)
            items.append((badge, tr))
            if len(items) >= limit:
                _cache_set(app, key, items)
                return list(items)
    _cache_set(app, key, items)
    return list(items)


def _hero(app, sections):
    cached = _cache_get(app, f"__home_bundle::hero::{_region_cache_suffix(app)}")
    if cached:
        return dict(cached)
    for label_key, query, desc_key in _HERO_FEEDS:
        label = _regional_title(app, label_key, query)
        desc = _regional_desc(app, desc_key, query)
        results = list(app._fetch_feed_results(query, limit=8) or [])
        if results:
            hero = {"track": results[0], "source": label, "query": query, "desc": desc, "support": results[1:4]}
            _cache_set(app, f"__home_bundle::hero::{_region_cache_suffix(app)}", hero)
            return hero
    if sections and sections[0][1]:
        title, tracks = sections[0][0], sections[0][1]
        hero = {
            "track": tracks[0],
            "source": app._tr("home.hero.loading.source"),
            "query": _guess_query(title),
            "desc": app._tr("home.live_picked"),
            "support": list(tracks[1:4]),
        }
        _cache_set(app, f"__home_bundle::hero::{_region_cache_suffix(app)}", hero)
        return hero
    return {
        "track": {},
        "source": app._tr("home.hero.loading.title"),
        "query": "feed:new.music",
        "desc": app._tr("home.hero.loading.artist"),
        "support": [],
    }


def _live_sections(app, limit=2, per_section=8):
    key = f"__home_bundle::live_sections::{_region_cache_suffix(app)}::{limit}::{per_section}"
    cached = _cache_get(app, key, ttl=900)
    if cached is not None:
        return list(cached)

    sections = []
    for title_key, query, desc_key in list(_LIVE_FEEDS)[: max(1, int(limit or 2))]:
        title = _regional_title(app, title_key, query)
        desc = _regional_desc(app, desc_key, query)
        try:
            tracks = list(app._fetch_feed_results(query, limit=per_section) or [])
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
            tracks = []
        if not tracks:
            continue
        sections.append((title, tracks, desc))
    _cache_set(app, key, sections)
    return list(sections)


def _bundle(app):
    sections = _live_sections(app, limit=2, per_section=8)
    return {
        "buttons": _buttons(app),
        "hero": _hero(app, sections),
        "sections": list(sections[:2]),
        "spotlights": _spotlight_entries(app, limit=4),
    }


def _rebind(button, fn):
    prev = getattr(button, "_home_click_handler", None)
    if prev is not None:
        try:
            button.clicked.disconnect(prev)
        except (TypeError, RuntimeError):
            pass
    button._home_click_handler = None
    button.setEnabled(fn is not None)
    if fn:
        button.clicked.connect(fn)
        button._home_click_handler = fn


def _apply_home_image(app, target, url: str, size: tuple):
    path = str(url or "").strip()
    if not path or target is None:
        return
    if os.path.isfile(path):
        try:
            px = QPixmap(path)
            if not px.isNull():
                target.setPixmap(px)
                return
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
    app._load_image(path, target, size)


def _strip(app, parent_layout, tracks):
    hs = QScrollArea()
    hs.setFixedHeight(108)
    hs.setWidgetResizable(False)
    hs.setStyleSheet("background:transparent; border:none;")
    hs.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    hs.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    host = QWidget()
    host.setObjectName("TC")
    row = QHBoxLayout(host)
    row.setContentsMargins(0, 4, 0, 4)
    row.setSpacing(10)
    for tr in list(tracks or [])[:8]:
        row.addWidget(_H._make_home_compact_card(app, tr, "normal"))
    row.addStretch()
    host.adjustSize()
    hs.setWidget(host)
    parent_layout.addWidget(hs)


def _dedupe_tracks(app, tracks, limit=8):
    items = []
    seen = set()
    for tr in list(tracks or []):
        vid = str(tr.get("videoId", "") or "").strip()
        artist = str(app._artist_str(tr) or "").strip().lower()
        title = str(tr.get("title", "") or "").strip().lower()
        key = vid or f"{title}|{artist}"
        if not key or key in seen:
            continue
        seen.add(key)
        items.append(tr)
        if len(items) >= max(1, int(limit or 8)):
            break
    return items


def _make_editorial_track_card(app, track, mode="poster"):
    mode = str(mode or "poster").lower()
    if mode == "mini":
        card_w, card_h = 220, 74
        art_w, art_h = 54, 54
    elif mode == "wide":
        card_w, card_h = 274, 118
        art_w, art_h = 88, 88
    else:
        card_w, card_h = 228, 322
        art_w, art_h = 200, 200

    obj_name = f"HomeTrackCard{mode.title()}"
    card = _H.AnimatedCard()
    card.setObjectName(obj_name)
    card.setFixedSize(card_w, card_h)
    card.setStyleSheet(
        f"""
        QFrame#{obj_name} {{
            background:qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 rgba(255,255,255,0.025), stop:0.15 {_H.get_accent()}12,
                stop:0.68 {_H.BG_CARD}, stop:1 {_H.BG_ELEVATED});
            border:1px solid {_H.BORDER_COLOR};
            border-radius:{22 if mode == "poster" else 18}px;
        }}
        QFrame#{obj_name}:hover {{
            border:1px solid {_H.get_accent()}55;
            background:qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 {_H.get_accent()}16, stop:0.55 {_H.BG_CARD_HOVER}, stop:1 {_H.BG_ELEVATED});
        }}
        """
    )

    title_text = str(track.get("title") or app._tr("common.unknown_title"))
    artist_text = str(app._artist_str(track) or app._tr("common.unknown_artist"))
    thumb = app._thumb(track, big=True)

    if mode == "poster":
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)
        art = QLabel()
        art.setFixedSize(art_w, art_h)
        art.setAlignment(Qt.AlignCenter)
        art.setStyleSheet(f"background:{_H.BG_BLACK}; border:none; border-radius:18px;")
        if thumb:
            app._load_image(thumb, art, (art_w, art_h))
        else:
            try:
                ico = _H.create_icon("music", _H.TEXT_MUTED, 56)
                art.setPixmap(ico.pixmap(56, 56))
            except Exception:
                pass
        lay.addWidget(art, 0, Qt.AlignHCenter)

        kicker = QLabel(app._tr("home.editorial.kicker"))
        kicker.setStyleSheet(
            f"color:{_H.get_accent()}; font-size:11px; font-weight:900; letter-spacing:1px; background:transparent;"
        )
        title = QLabel(title_text)
        title.setWordWrap(True)
        title.setFixedHeight(52)
        title.setStyleSheet(
            f"color:{_H.TEXT_PRIMARY}; font-size:22px; font-weight:900; background:transparent;"
        )
        artist = QLabel(artist_text)
        artist.setWordWrap(True)
        artist.setFixedHeight(34)
        artist.setStyleSheet(
            f"color:{_H.TEXT_SECONDARY}; font-size:13px; font-weight:700; background:transparent;"
        )
        lay.addWidget(kicker)
        lay.addWidget(title)
        lay.addWidget(artist)
        lay.addStretch()
    else:
        lay = QHBoxLayout(card)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(12)
        art = QLabel()
        art.setFixedSize(art_w, art_h)
        art.setAlignment(Qt.AlignCenter)
        art.setStyleSheet(f"background:{_H.BG_BLACK}; border:none; border-radius:14px;")
        if thumb:
            app._load_image(thumb, art, (art_w, art_h))
        else:
            try:
                ico = _H.create_icon("music", _H.TEXT_MUTED, 30)
                art.setPixmap(ico.pixmap(30, 30))
            except Exception:
                pass
        lay.addWidget(art)
        text_l = QVBoxLayout()
        text_l.setSpacing(4)
        if mode == "wide":
            badge = QLabel(app._tr("home.editorial.badge"))
            badge.setStyleSheet(
                f"color:{_H.get_accent()}; font-size:10px; font-weight:900; letter-spacing:1px; background:transparent;"
            )
            text_l.addWidget(badge)
        title = QLabel(title_text)
        title.setWordWrap(True)
        title.setStyleSheet(
            f"color:{_H.TEXT_PRIMARY}; font-size:{14 if mode == 'mini' else 18}px; font-weight:900; background:transparent;"
        )
        artist = QLabel(artist_text)
        artist.setWordWrap(True)
        artist.setStyleSheet(
            f"color:{_H.TEXT_SECONDARY}; font-size:{11 if mode == 'mini' else 12}px; font-weight:700; background:transparent;"
        )
        text_l.addWidget(title)
        text_l.addWidget(artist)
        text_l.addStretch()
        lay.addLayout(text_l, 1)

    if ("browseId" in track and track.get("resultType") not in ("song", "video")):
        card.clicked.connect(lambda b=track.get("browseId"): app._fetch_radio(b))
    else:
        card.clicked.connect(lambda t=track: app.force_play(t))
        card.setContextMenuPolicy(Qt.CustomContextMenu)
        card.customContextMenuRequested.connect(lambda _, t=track: app._ctx_menu(QCursor.pos(), t))
    return card


def _render_editorial_strip(app, parent_layout, tracks, mode="poster", limit=8):
    hs = QScrollArea()
    hs.setFixedHeight(352 if str(mode or "").lower() == "poster" else 146)
    hs.setWidgetResizable(False)
    hs.setStyleSheet("background:transparent; border:none;")
    hs.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    hs.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    host = QWidget()
    host.setObjectName("TC")
    row = QHBoxLayout(host)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(16 if str(mode or "").lower() == "poster" else 12)
    for tr in _dedupe_tracks(app, tracks, limit=limit):
        row.addWidget(_make_editorial_track_card(app, tr, mode=mode))
    row.addStretch()
    host.adjustSize()
    hs.setWidget(host)
    parent_layout.addWidget(hs)


def _base_spotlight_entries(app, limit=4):
    key = f"__home_bundle::spotlights::{_region_cache_suffix(app)}::{limit}"
    cached = _cache_get(app, key, ttl=900)
    if cached is not None:
        return list(cached)

    entries = []
    for label_key, query, desc_key in list(_SPOTLIGHT_FEEDS)[: max(1, int(limit or 4))]:
        label = _regional_title(app, label_key, query)
        desc = _regional_desc(app, desc_key, query)
        try:
            tracks = list(app._fetch_feed_results(query, limit=4) or [])
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
            tracks = []
        if not tracks:
            continue
        lead = tracks[0]
        entries.append({
            "label": label,
            "query": query,
            "desc": desc,
            "track": lead,
            "headline": str(lead.get("title") or label),
            "subline": str(app._artist_str(lead) or ""),
        })
    _cache_set(app, key, entries)
    return list(entries)


def _make_spotlight_card(app, entry):
    card = _H.AnimatedCard()
    card.setObjectName("HomeSpotlightCard")
    card.setFixedSize(276, 204)
    card.setStyleSheet(
        f"""
        QFrame#HomeSpotlightCard {{
            background:qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {_H.BG_ELEVATED}, stop:1 {_H.BG_CARD});
            border:1px solid {_H.BORDER_COLOR};
            border-radius:22px;
        }}
        QFrame#HomeSpotlightCard:hover {{
            border:1px solid {_H.get_accent()}55;
            background:qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {_H.get_accent()}14, stop:1 {_H.BG_CARD_HOVER});
        }}
        """
    )
    lay = QVBoxLayout(card)
    lay.setContentsMargins(12, 12, 12, 12)
    lay.setSpacing(10)

    art = QLabel()
    art.setFixedHeight(122)
    art.setAlignment(Qt.AlignCenter)
    art.setStyleSheet(f"background:{_H.BG_CARD}; border:none; border-radius:16px;")
    thumb = app._thumb(entry.get("track") or {}, big=True)
    if thumb:
        app._load_image(thumb, art, (252, 122))
    else:
        try:
            ico = _H.create_icon("music", _H.TEXT_MUTED, 34)
            art.setPixmap(ico.pixmap(34, 34))
        except Exception:
            pass
    lay.addWidget(art)

    kicker = QLabel(str(entry.get("label") or app._tr("home.spotlight.default")))
    kicker.setStyleSheet(f"color:{_H.get_accent()}; font-size:10px; font-weight:900; letter-spacing:1px; background:transparent;")
    kicker.setWordWrap(True)
    title = QLabel(str(entry.get("headline") or ""))
    title.setStyleSheet(f"color:{_H.TEXT_PRIMARY}; font-size:22px; font-weight:900; background:transparent;")
    title.setWordWrap(True)
    meta = QLabel(str(entry.get("subline") or entry.get("desc") or ""))
    meta.setStyleSheet(f"color:{_H.TEXT_SECONDARY}; font-size:12px; font-weight:700; background:transparent;")
    meta.setWordWrap(True)
    lay.addWidget(kicker)
    lay.addWidget(title)
    lay.addWidget(meta)
    lay.addStretch()

    card.clicked.connect(
        lambda q=entry.get("query") or "", t=entry.get("label") or app._tr("home.spotlight.default"):
        app.page_category(t, q, "songs")
    )
    return card


def _legacy_render_spotlights(app, entries):
    layout = app._home_refs["spotlights"]
    _clear(layout)
    for entry in list(entries or [])[:4]:
        layout.addWidget(_make_spotlight_card(app, entry))
    layout.addStretch()
    try:
        w = layout.parentWidget()
        if w is not None:
            w.adjustSize()
    except Exception:
        pass


def _legacy_set_hero_loading(app):
    refs = getattr(app, "_home_refs", {})
    if not refs:
        return
    refs["source"].setText(_tr_upper(app._tr("home.hero.loading.source")))
    refs["title"].setText(app._tr("home.hero.loading.title"))
    refs["artist"].setText(app._tr("home.hero.loading.artist"))
    refs["desc"].setText(app._tr("home.hero.loading.desc"))
    refs["cover"].clear()
    _rebind(refs["play"], None)
    _rebind(refs["open"], lambda: app.page_category(app._tr("home.new_songs.title"), "feed:new.music", "songs"))
    _rebind(refs["refresh"], getattr(app, "_home_reload_current", app._refresh_home_feed))
    _clear(refs["spotlights"])


def _render_buttons(app, buttons):
    refs = getattr(app, "_home_refs", {})
    wrap = refs.get("chips_wrap")
    if wrap is not None:
        wrap.hide()
    layout = refs["chips"]
    _clear(layout)
    return


def _obsolete_early_apply_bundle(app, bundle):
    refs = getattr(app, "_home_refs", {})
    if not refs:
        return
    hero = bundle.get("hero") or {}
    tr = hero.get("track") or {}
    refs["source"].setText(_tr_upper(hero.get("source") or app._tr("home.hero.loading.source")))
    refs["title"].setText(str(tr.get("title") or app._tr("home.hero.ready")))
    refs["artist"].setText(str(app._artist_str(tr) or app._tr("home.hero.live_selections")))
    refs["desc"].setText(str(hero.get("desc") or ""))
    thumb = app._thumb(tr, big=True)
    if thumb:
        try:
            ico = _H.create_icon("music", _H.TEXT_MUTED, 56)
            refs["cover"].setPixmap(ico.pixmap(56, 56))
        except Exception:
            refs["cover"].clear()
        app._load_image(thumb, refs["cover"], (220, 220))
    _rebind(refs["play"], lambda: app.force_play(tr) if tr else None)
    _rebind(refs["open"], lambda q=hero.get("query") or "feed:new.music", s=hero.get("source") or app._tr("home.hero.loading.source"): app.page_category(s, q, "songs"))
    _rebind(refs["refresh"], getattr(app, "_home_reload_current", app._refresh_home_feed))
    _render_buttons(app, bundle.get("buttons") or [])
    _render_spotlights(app, bundle.get("spotlights") or [])

    live = refs["live"]
    live.setVisible(bool(bundle.get("sections")))
    _clear(live.layout())
    if bundle.get("sections"):
        live.layout().addWidget(_header(app._tr("home.live_streams")))
        for title, tracks, desc in list(bundle["sections"])[:2]:
            lbl = QLabel(str(title))
            lbl.setStyleSheet(f"color:{_H.TEXT_PRIMARY}; font-size:15px; font-weight:850; background:transparent;")
            sub = QLabel(str(desc or app._tr("home.live_curated_desc")))
            sub.setStyleSheet(f"color:{_H.TEXT_MUTED}; font-size:11px; background:transparent;")
            live.layout().addWidget(lbl)
            live.layout().addWidget(sub)
            _strip(app, live.layout(), tracks)


def _legacy_apply_tab(app, query, results):
    info = app._home_state["tabs"].get(query)
    if not info or not qt_is_valid(info["frame"]):
        return
    _clear(info["frame"].layout())
    if results:
        app._fill_h_grid(results, info["frame"], None)
    else:
        box = QFrame()
        box.setStyleSheet(f"background:{_H.BG_CARD}; border:1px solid {_H.BORDER_COLOR}; border-radius:18px;")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(20, 18, 20, 18)
        t = QLabel(app._tr("home.tab.empty.title"))
        t.setStyleSheet(f"color:{_H.TEXT_PRIMARY}; font-size:14px; font-weight:850; background:transparent;")
        s = QLabel(app._tr("home.tab.empty.subtitle"))
        s.setStyleSheet(f"color:{_H.TEXT_MUTED}; font-size:12px; background:transparent;")
        lay.addWidget(t); lay.addWidget(s)
        info["frame"].layout().addWidget(box); info["frame"].layout().addStretch()
    info["loaded"] = True
    info["loading"] = False


class _Bridge(QObject):
    bundle_ready = Signal(object, object)
    tab_ready = Signal(object, str, object)
    curated_ready = Signal(object, object)

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.bundle_ready.connect(self._on_bundle, Qt.QueuedConnection)
        self.tab_ready.connect(self._on_tab, Qt.QueuedConnection)
        self.curated_ready.connect(self._on_curated, Qt.QueuedConnection)

    def _ok(self, token):
        return token == getattr(self.app, "_home_ui_token", None) and qt_is_valid(self.app._home_refs.get("page"))

    def _on_bundle(self, token, bundle):
        if self._ok(token):
            _apply_bundle(self.app, bundle)

    def _on_tab(self, token, query, results):
        if self._ok(token):
            _apply_tab(self.app, query, results or [])

    def _on_curated(self, token, items):
        if not self._ok(token):
            return
        refs = getattr(self.app, "_home_refs", {})
        refs["playlist_grid_items"] = list(items or [])
        cache_key = _curated_home_cards_cache_key(self.app)
        _cache_set(self.app, cache_key, list(items or []))
        _render_curated_playlist_grid(self.app, refs["playlist_grid_items"])


def _load_bundle_async(app, token):
    bridge = getattr(app, "_home_bridge", None)
    if bridge is None:
        return
    def _work():
        try:
            data = _bundle(app)
        except Exception as e:
            log.warning("Home bundle yüklenemedi: %s", e)
            data = {"buttons": _buttons(app), "hero": {}, "sections": []}
        bridge.bundle_ready.emit(token, data)
    app._net_pool.submit(_work)


def _load_curated_playlist_previews_async(app, items):
    bridge = getattr(app, "_home_bridge", None)
    token = getattr(app, "_home_ui_token", None)
    if bridge is None or token is None:
        return
    rows = [dict(item) for item in list(items or [])]
    if not rows:
        return
    force_cover_refresh = bool(getattr(app, "_home_force_curated_cover_refresh", False))
    pending = []
    for row in rows:
        slug = str(row.get("slug") or _home_cover_slug(row.get("title") or "")).strip()
        has_source = bool(str(row.get("playlist_query") or row.get("query") or row.get("fallback_query") or "").strip())
        has_fresh_real_cover = bool(_curated_cached_cover_path(app, slug, allow_stale=False))
        if has_source and (force_cover_refresh or not has_fresh_real_cover):
            pending.append(row)
    if not pending:
        return
    if getattr(app, "_home_curated_preview_token", None) == token:
        return
    app._home_curated_preview_token = token

    def _work():
        enriched = _prepare_curated_playlist_covers(app, rows, force_refresh=force_cover_refresh)
        if force_cover_refresh:
            try:
                app._home_force_curated_cover_refresh = False
            except Exception:
                pass
        bridge.curated_ready.emit(token, enriched)

    app._net_pool.submit(_work)


def _legacy_load_tab_async(app, query, force=False):
    info = app._home_state["tabs"].get(query)
    if not info or (info["loading"] and not force):
        return
    info["loading"] = True
    info["loaded"] = False
    _clear(info["frame"].layout())
    for _ in range(6):
        info["frame"].layout().addWidget(SkeletonWidget(width=198, height=292, radius=18))
    info["frame"].layout().addStretch()
    bridge = getattr(app, "_home_bridge", None)
    token = getattr(app, "_home_ui_token", None)
    key = f"__home_bundle::tab::{_region_cache_suffix(app)}::{query}"
    cached = None if force else _cache_get(app, key)
    if cached is not None and bridge is not None:
        bridge.tab_ready.emit(token, query, list(cached))
        return
    def _work():
        try:
            results = list(app._fetch_feed_results(query, limit=20) or [])
        except Exception as e:
            log.warning("Home tab yüklenemedi (%s): %s", query, e)
            results = []
        _cache_set(app, key, results)
        if bridge is not None:
            bridge.tab_ready.emit(token, query, results)
    app._net_pool.submit(_work)


def _activate_tab(app, query, force=False):
    if query not in app._home_state["tabs"]:
        return
    app._home_state["active"] = query
    app._home_active_tab_query = query
    app._home_refs["stack"].setCurrentIndex(app._home_state["tabs"][query]["index"])
    for key, info in app._home_state["tabs"].items():
        info["btn"].setStyleSheet(_tab_btn(key == query))
    if force or not app._home_state["tabs"][query]["loaded"]:
        _load_tab_async(app, query, force=force)


def _render_personal(app):
    host = app._home_refs["personal"]
    data = _personal(app)
    host.setVisible(bool(data))
    _clear(host.layout())
    if not data:
        return
    host.layout().addWidget(_header(app._tr("home.recently_played")))
    _strip(app, host.layout(), [track for _badge, track in data])


def _reload(app):
    if not qt_is_valid(app._home_refs.get("page")):
        app._invalidate_home_cache()
        app.page_home()
        return
    try:
        app._home_cache.clear()
    except Exception as _e:
        log.debug("Sessiz hata: %s", _e)
    app._home_pool_session = None
    app._home_visit_seed = int(time.time() * 1000) % 100000
    app._home_ui_token = _next_ui_token(app)
    app._home_force_curated_cover_refresh = True
    for info in app._home_state["tabs"].values():
        info["loaded"] = False
        info["loading"] = False
    _set_curated_grid_loading(app)
    _render_buttons(app, list(_H.CATEGORY_BUTTONS[:6]))
    app._home_refs["live"].setVisible(False)
    _clear(app._home_refs["live"].layout())
    app._home_refs["personal"].setVisible(False)
    _clear(app._home_refs["personal"].layout())
    QTimer.singleShot(120, lambda token=app._home_ui_token: token == app._home_ui_token and _render_personal(app))
    _load_bundle_async(app, app._home_ui_token)
    _activate_tab(app, app._home_state.get("active") or _TABS[0][1], force=True)


def _refresh_entry(app):
    page = getattr(app, "_home_refs", {}).get("page")
    if getattr(app, "current_page", None) == "home" and qt_is_valid(page):
        _reload(app)
        return
    legacy = getattr(app, "_legacy_refresh_home_feed", None)
    if callable(legacy):
        legacy()
        return
    app._invalidate_home_cache()
    app.page_home()


def _set_hero_loading(app):
    refs = getattr(app, "_home_refs", {})
    if not refs:
        return
    refs["source"].setText(_tr_upper(app._tr("home.hero.loading.source")))
    refs["title"].setText(app._tr("home.hero.loading.title"))
    refs["artist"].setText(app._tr("home.hero.loading.artist"))
    refs["desc"].setText(app._tr("home.hero.loading.desc"))
    refs["cover"].clear()
    _rebind(refs["play"], None)
    _rebind(refs["open"], lambda: app.page_category(app._tr("home.new_songs.title"), "feed:new.music", "songs"))
    _rebind(refs["refresh"], getattr(app, "_home_reload_current", app._refresh_home_feed))
    _clear(refs["spotlights"])
    support = refs.get("support")
    if support is not None:
        _clear(support)


def _legacy_render_hero_support(app, tracks):
    layout = getattr(app, "_home_refs", {}).get("support")
    if layout is None:
        return
    _clear(layout)
    for tr in _dedupe_tracks(app, tracks, limit=3):
        layout.addWidget(_make_editorial_track_card(app, tr, mode="mini"))
    layout.addStretch()


def _apply_bundle(app, bundle):
    refs = getattr(app, "_home_refs", {})
    if not refs:
        return
    hero = bundle.get("hero") or {}
    tr = hero.get("track") or {}
    refs["source"].setText(_tr_upper(hero.get("source") or app._tr("home.hero.loading.source")))
    refs["title"].setText(str(tr.get("title") or app._tr("home.hero.ready")))
    refs["artist"].setText(str(app._artist_str(tr) or app._tr("home.hero.live_selections")))
    refs["desc"].setText(str(hero.get("desc") or ""))
    thumb = app._thumb(tr, big=True)
    if thumb:
        try:
            ico = _H.create_icon("music", _H.TEXT_MUTED, 56)
            refs["cover"].setPixmap(ico.pixmap(56, 56))
        except Exception:
            refs["cover"].clear()
        app._load_image(thumb, refs["cover"], (220, 220))
    else:
        refs["cover"].clear()
    _rebind(refs["play"], lambda: app.force_play(tr) if tr else None)
    _rebind(
        refs["open"],
        lambda q=hero.get("query") or "feed:new.music", s=hero.get("source") or app._tr("home.hero.loading.source"): app.page_category(s, q, "songs"),
    )
    _rebind(refs["refresh"], getattr(app, "_home_reload_current", app._refresh_home_feed))
    _render_buttons(app, bundle.get("buttons") or [])
    _render_spotlights(app, bundle.get("spotlights") or [])
    _render_hero_support(app, hero.get("support") or [])

    live = refs["live"]
    live.setVisible(bool(bundle.get("sections")))
    _clear(live.layout())
    if bundle.get("sections"):
        live.layout().addWidget(_header(app._tr("home.live_streams")))
        for title, tracks, desc in list(bundle["sections"])[:2]:
            lbl = QLabel(str(title))
            lbl.setStyleSheet(f"color:{_H.TEXT_PRIMARY}; font-size:15px; font-weight:850; background:transparent;")
            sub = QLabel(str(desc or app._tr("home.live_curated_desc")))
            sub.setStyleSheet(f"color:{_H.TEXT_MUTED}; font-size:11px; background:transparent;")
            live.layout().addWidget(lbl)
            live.layout().addWidget(sub)
            _render_editorial_strip(app, live.layout(), tracks, mode="wide", limit=8)


_FINAL_HOME_SPOTLIGHT_ENTRIES = _base_spotlight_entries
_FINAL_HOME_HERO = _hero
_FINAL_HOME_BUNDLE = _bundle
_FINAL_HOME_APPLY_BUNDLE = _apply_bundle


def _spotlight_entries(app, limit=4):
    curated = _curated_home_cards(app)
    if curated:
        return list(curated[: max(1, int(limit or 4))])
    return _FINAL_HOME_SPOTLIGHT_ENTRIES(app, limit=limit)


def _legacy_curated_hero(app, sections):
    curated = _curated_home_cards(app)
    if curated:
        lead = dict(curated[0])
        return {
            "item": lead,
            "tracks": list(lead.get("track_preview") or []),
            "source": "Öne Çıkan Liste",
            "query": lead.get("query") or "feed:new.music",
            "desc": str(lead.get("subtitle") or "Her hafta güncellenen listeler ."),
            "support": list(curated[4:7]),
        }
    return _FINAL_HOME_HERO(app, sections)


def _legacy_curated_bundle(app):
    curated = _curated_home_cards(app)
    if curated:
        return {
            "buttons": _buttons(app),
            "hero": _hero(app, []),
            "sections": [],
            "spotlights": _spotlight_entries(app, limit=4),
            "playlist_mode": True,
            "curated_mode": True,
        }
    bundle = _FINAL_HOME_BUNDLE(app)
    bundle["curated_mode"] = False
    return bundle


def _legacy_curated_apply_bundle(app, bundle):
    refs = getattr(app, "_home_refs", {})
    if not refs:
        return

    if not bundle.get("curated_mode"):
        _set_curated_host_min_width(app, _HOME_DEFAULT_HOST_MIN_WIDTH)
        grid_box = refs.get("playlist_grid_box")
        if grid_box is not None:
            grid_box.hide()
        hero_frame = refs.get("hero_frame")
        if hero_frame is not None:
            hero_frame.show()
        _FINAL_HOME_APPLY_BUNDLE(app, bundle)
        return

    cards = list(_curated_home_cards(app) or [])
    _set_curated_host_min_width(app, _HOME_CURATED_HOST_MIN_WIDTH)
    grid_box = refs.get("playlist_grid_box")
    if grid_box is not None:
        grid_box.show()
    hero_frame = refs.get("hero_frame")
    if hero_frame is not None:
        hero_frame.hide()

    grid_title = refs.get("playlist_grid_title")
    if grid_title is not None:
        grid_title.setText(app._tr("home.grid.title"))
    grid_desc = refs.get("playlist_grid_desc")
    if grid_desc is not None:
        grid_desc.setText(app._tr("home.grid.desc"))
    grid_refresh = refs.get("playlist_grid_refresh")
    if grid_refresh is not None:
        _rebind(grid_refresh, getattr(app, "_home_reload_current", app._refresh_home_feed))

    _render_curated_playlist_grid(app, cards)
    _load_curated_playlist_previews_async(app, cards)

    rail = refs.get("rail")
    if rail is not None:
        rail.setVisible(False)

    live = refs["live"]
    live.setVisible(False)
    _clear(live.layout())


_CURATED_HOME_SPOTLIGHT_ENTRIES_IMPL = _spotlight_entries
_CURATED_HOME_HERO_IMPL = _legacy_curated_hero
_CURATED_HOME_BUNDLE_IMPL = _legacy_curated_bundle
_CURATED_HOME_APPLY_BUNDLE_IMPL = _legacy_curated_apply_bundle


def _obsolete_default_hero(app, sections):
    curated = _curated_home_cards(app)
    if curated:
        lead = dict(curated[0])
        return {
            "item": lead,
            "tracks": list(lead.get("track_preview") or []),
            "source": app._tr("home.new_songs.source"),
            "query": lead.get("query") or "feed:new.music",
            "desc": str(lead.get("subtitle") or "Her hafta güncellenen müzik seçimleri."),
            "support": list(curated[4:7]),
        }
    return _LEGACY_HOME_HERO(app, sections)


def _obsolete_default_bundle(app):
    curated = _curated_home_cards(app)
    if curated:
        return {
            "buttons": _buttons(app),
            "hero": _hero(app, []),
            "sections": [],
            "spotlights": _spotlight_entries(app, limit=4),
            "playlist_mode": True,
            "curated_mode": True,
        }
    bundle = _LEGACY_HOME_BUNDLE(app)
    bundle["curated_mode"] = False
    return bundle


def _obsolete_default_apply_bundle(app, bundle):
    if not bundle.get("curated_mode"):
        _LEGACY_HOME_APPLY_BUNDLE(app, bundle)
        return

    refs = getattr(app, "_home_refs", {})
    if not refs:
        return

    hero = bundle.get("hero") or {}
    item = hero.get("item") or {}
    preview_tracks = list(hero.get("tracks") or [])

    refs["source"].setText(_tr_upper(hero.get("source") or app._tr("home.new_songs.source")))
    refs["title"].setText(str(item.get("title") or app._tr("home.new_songs.title")))
    refs["artist"].setText(str(item.get("subtitle") or app._tr("home.new_songs.subtitle")))
    refs["desc"].setText(app._tr("home.new_songs.desc"))
    refs["cover"].clear()
    art_url = str(item.get("art_url") or "").strip()
    if art_url:
        app._load_image(art_url, refs["cover"], (220, 220))

    lead_track = preview_tracks[0] if preview_tracks else None
    _rebind(
        refs["play"],
        lambda tr=lead_track, q=item.get("query") or "", t=item.get("title") or "Liste": app.force_play(tr) if tr else app.page_category(t, q, "songs"),
    )
    _rebind(
        refs["open"],
        lambda q=item.get("query") or "", t=item.get("title") or "Liste": app.page_category(t, q, "songs"),
    )
    _rebind(refs["refresh"], getattr(app, "_home_reload_current", app._refresh_home_feed))
    _render_buttons(app, bundle.get("buttons") or [])
    _render_spotlights(app, bundle.get("spotlights") or [])
    _render_hero_support(app, hero.get("support") or [])

    spotlight_label = refs.get("spotlight_label")
    if spotlight_label is not None:
        spotlight_label.setText(app._tr("home.new_songs.title"))
    support_label = refs.get("support_label")
    if support_label is not None:
        support_label.setText(app._tr("home.hero.support"))

    rail = refs.get("rail")
    if rail is not None:
        rail.setVisible(False)

    live = refs["live"]
    live.setVisible(False)
    _clear(live.layout())


_CURATED_HOME_PLAYLISTS = (
    {
        "title": "Yeni Çıkanlar",
        "description": "Her cuma haftanın en yeni şarkıları.",
        "url": "https://www.youtube.com/watch?v=ApvPVUgAbEk&list=RDCLAK5uy_ncwbM766_rhOk_JllLnAXmv_5v21_b2bc&index=2",
        "fallback_query": "feed:new.music",
        "slug": "yeni-cikanlar",
    },
    {
        "title": "TÃ¼rkiye Trendler",
        "description": "TÃ¼rkiye'de Åu an Ã¶ne Ã§Ä±kan ÅarkÄ±lar.",
        "url": "https://www.youtube.com/watch?v=vso1LpaQRbo&list=RDCLAK5uy_n7OdwqgA4C6ewA6dD-YAXJEqUC0lPHqUA&index=2",
        "fallback_query": "feed:charts.tr",
        "slug": "turkiye-trendler",
    },
    {
        "title": "Yeni Türkçe Pop",
        "description": "Her hafta yenilenen Türkçe pop şarkıları.",
        "url": "https://www.youtube.com/watch?v=aPFeLf3qZ3M&list=RDCLAK5uy_k31GPZp_nSsHeJEniR4MqtqFBRJatI-JI&index=2",
        "fallback_query": "feed:tr.pop",
        "slug": "yeni-turkce-pop",
    },
    {
        "title": "Yeni Türkçe Rap",
        "description": "Her hafta yenilenen Türkçe rap şarkıları.",
        "url": "https://www.youtube.com/watch?v=sNZW_GxwSu0&list=RDCLAK5uy_n2YZ2tg_cPKwwuyYdZJwHHRG6pjc6DpTA&index=2",
        "fallback_query": "feed:tr.rap",
        "slug": "yeni-turkce-rap",
    },
    {
        "title": "Yeni Nesil Türkçe Rap",
        "description": "Türkiye'den yeni nesil Türkçe rap seçimleri.",
        "url": "https://www.youtube.com/watch?v=zGvNdWZIFiY&list=RDCLAK5uy_m4Nf66w53gEgzlYDl8qywtm_jOAIXvnrM&index=2",
        "fallback_query": "feed:tr.rap",
        "slug": "yeni-nesil-turkce-rap",
    },
    {
        "title": "Yeni Türküler",
        "description": "Her hafta yenilenen yeni türkü seçimleri.",
        "url": "https://www.youtube.com/watch?v=xPO3i09ek1U&list=RDCLAK5uy_kY5-Mk6p1h2nPp1Q94av5A_bzL7pByeMI&index=2",
        "fallback_query": "feed:tr.slow",
        "slug": "yeni-turkuler",
    },
    {
        "title": "Yeni Arabesk",
        "description": "Güncel arabesk şarkılarından taze seçimleri.",
        "url": "https://www.youtube.com/watch?v=2UPBTDVkLGo&list=RDCLAK5uy_n8UNNIBTs0TrIvaiuOcn6yXQSqWHHAsZ4&index=2",
        "fallback_query": "feed:tr.arabesk",
        "slug": "yeni-arabesk",
    },
    {
        "title": "Güncel Pop Şarkıları",
        "description": "Şu an öne çıkan güncel pop şarkıları.",
        "url": "https://www.youtube.com/watch?v=7iQlT-EI_Rk&list=RDCLAK5uy_nOwL35BM_GUTEbdbw_9FmvQhPWWdd3sAg&index=2",
        "fallback_query": "feed:tr.pop",
        "slug": "guncel-pop-sarkilari",
    },
    {
        "title": "Sakin Türkçe İndie",
        "description": "Sakin ve içten Türkçe indie şarkılar.",
        "url": "https://www.youtube.com/watch?v=TaUuYrpvMS0&list=RDCLAK5uy_l2Y9mrA559EY5tfe8kK8YxdUVR0rADYBI&index=2",
        "fallback_query": "feed:tr.indie",
        "slug": "sakin-turkce-indie",
    },
    {
        "title": "Güncel Türkçe Rock",
        "description": "Türkiye'den güncel rock ve alternatif şarkılar.",
        "url": "https://www.youtube.com/watch?v=ItISVW3o0X0&list=RDCLAK5uy_m5iRJRUhtLWAf7JWYFNb3ANZkuxMK9yrw&index=2",
        "fallback_query": "feed:tr.rock",
        "slug": "guncel-turkce-rock",
    },
    {
        "title": "Elektronik Müzik Türkiye",
        "description": "Türkiye'den elektronik ve dans müziği listesi.",
        "url": "https://www.youtube.com/watch?v=oO2N2kak064&list=RDCLAK5uy_kB1PM1GFKy0KLYd3C5oZ59KHN-q2JcRRg&index=2",
        "fallback_query": "feed:global.edm",
        "slug": "elektronik-muzik-turkiye",
    },
    {
        "title": "Çalışırken Dinlemelik",
        "description": "Odaklanmayı kolaylaştıran sakin müzikler.",
        "url": "https://www.youtube.com/watch?v=ew4FWW1q200&list=RDCLAK5uy_ny_3fjH20gPvg3ZFCc4ITAoiJHRCF1F_8&index=2",
        "fallback_query": "feed:focus",
        "slug": "calisirken-dinlemelik",
    },
    {
        "title": "Yumuşak Piyano",
        "description": "Dinlendirici ve duygusal piyano melodileri.",
        "url": "https://www.youtube.com/watch?v=kn1zbCPPgLg&list=RDCLAK5uy_ldooV6iHaoPy6VKyVuHDq0DT4lh-3tRqQ&index=2",
        "fallback_query": "feed:focus",
        "slug": "yumusak-piyano",
    },
    {
        "title": "Caz Gecesi",
        "description": "Gece için seçilmiş caz ve smooth şarkılar.",
        "url": "https://www.youtube.com/watch?v=TAMP9zGjvYI&list=RDCLAK5uy_n2cq0PxECLzVblC6NOorWjaCtF5NwXJT4&index=2",
        "fallback_query": "feed:chill",
        "slug": "caz-gecesi",
    },
    {
        "title": "Yabancı Pop Klasikleri",
        "description": "Dünyanın dört bir yanından pop klasikleri.",
        "url": "https://www.youtube.com/watch?v=lp-EO5I60KA&list=RDCLAK5uy_nDL8KeBrUagwyISwNmyEiSfYgz1gVCesg&index=2",
        "fallback_query": "feed:global.pop",
        "slug": "yabanci-pop-klasikleri",
    },
    {
        "title": "Lo-Fi Müzikler",
        "description": "Rahatlatıcı lo-fi beats ve chillhop seçimleri.",
        "url": "https://www.youtube.com/watch?v=Z20dQqE1u0E&list=RDCLAK5uy_kb7EBi6y3GrtJri4_ZH56Ms786DFEimbM&index=2",
        "fallback_query": "feed:chill",
        "slug": "lofi-muzikler",
    },
)


def _region_curated_home_playlists(app):
    """Return homepage playlist cards for the current content region."""
    region = _content_region(app)
    if region == "TR":
        return _CURATED_HOME_PLAYLISTS

    name = _content_region_name(app)
    lang = str(getattr(app, "_language", "tr") or "tr").lower()
    tr_ui = lang.startswith("tr")
    code = region.lower()

    def title(tr_text, en_text):
        return tr_text if tr_ui else en_text

    return (
        {
            "title": title(f"{name} Yeni Çıkanlar", f"New in {name}"),
            "description": title(
                f"{name} için haftanın yeni şarkıları ve taze hitleri.",
                f"Fresh releases and new hits for {name}.",
            ),
            "fallback_query": "feed:new.music",
            "slug": f"{code}-new-songs",
        },
        {
            "title": title(f"{name} Trendler", f"{name} Trends"),
            "description": title(
                f"{name} bölgesinde şu an öne çıkan şarkılar.",
                f"Songs trending in {name} right now.",
            ),
            "fallback_query": "feed:charts.tr",
            "slug": f"{code}-trends",
        },
        {
            "title": title(f"{name} Pop", f"{name} Pop"),
            "description": title(
                f"{name} için pop hitleri ve yeni pop şarkıları.",
                f"Pop hits and fresh pop songs for {name}.",
            ),
            "fallback_query": "feed:tr.pop",
            "slug": f"{code}-pop",
        },
        {
            "title": title(f"{name} Rap / Hip-Hop", f"{name} Rap / Hip-Hop"),
            "description": title(
                f"{name} için güncel rap ve hip-hop parçaları.",
                f"Current rap and hip-hop picks for {name}.",
            ),
            "fallback_query": "feed:tr.rap",
            "slug": f"{code}-rap",
        },
        {
            "title": title(f"{name} Rock", f"{name} Rock"),
            "description": title(
                f"{name} için rock ve alternatif şarkılar.",
                f"Rock and alternative songs for {name}.",
            ),
            "fallback_query": "feed:tr.rock",
            "slug": f"{code}-rock",
        },
        {
            "title": title(f"{name} Indie", f"{name} Indie"),
            "description": title(
                f"{name} için indie ve alternatif pop seçimleri.",
                f"Indie and alternative pop picks for {name}.",
            ),
            "fallback_query": "feed:tr.indie",
            "slug": f"{code}-indie",
        },
        {
            "title": title("Global Pop", "Global Pop"),
            "description": title(
                "Dünya genelinde öne çıkan pop şarkıları.",
                "Pop songs breaking out worldwide.",
            ),
            "fallback_query": "feed:global.pop",
            "slug": f"{code}-global-pop",
        },
        {
            "title": title("Çalışırken Dinlemelik", "Focus While Working"),
            "description": title(
                "Odaklanmayı kolaylaştıran sakin müzikler.",
                "Calm tracks that make it easier to focus.",
            ),
            "fallback_query": "feed:focus",
            "slug": f"{code}-focus",
        },
        {
            "title": title("Lo-Fi Müzikler", "Lo-Fi Music"),
            "description": title(
                "Rahatlatıcı lo-fi beat'ler ve chillhop seçimleri.",
                "Relaxing lo-fi beats and chillhop picks.",
            ),
            "fallback_query": "feed:chill",
            "slug": f"{code}-lofi",
        },
    )


_CURATED_HOME_COPY = {
    "yeni-cikanlar": {
        "title": {"tr": "Yeni Çıkanlar", "en": "New Songs"},
        "description": {
            "tr": "Her cuma haftanın en yeni şarkıları.",
            "en": "The newest songs of the week, refreshed every Friday.",
        },
        "badge": {"tr": "Her Cuma", "en": "Every Friday"},
    },
    "turkiye-trendler": {
        "title": {"tr": "TÃ¼rkiye Trendler", "en": "Turkey Trends"},
        "description": {
            "tr": "TÃ¼rkiye'de Åu an Ã¶ne Ã§Ä±kan ÅarkÄ±lar.",
            "en": "The songs trending in Turkey right now.",
        },
        "badge": {"tr": "Trend", "en": "Trending"},
    },
    "yeni-turkce-pop": {
        "title": {"tr": "Yeni Türkçe Pop", "en": "New Turkish Pop"},
        "description": {
            "tr": "Her hafta yenilenen Türkçe pop şarkıları.",
            "en": "Turkish pop songs refreshed every week.",
        },
        "badge": {"tr": "Pop Taze", "en": "Fresh Pop"},
    },
    "yeni-turkce-rap": {
        "title": {"tr": "Yeni Türkçe Rap", "en": "New Turkish Rap"},
        "description": {
            "tr": "Her hafta yenilenen Türkçe rap şarkıları.",
            "en": "Turkish rap songs refreshed every week.",
        },
        "badge": {"tr": "Rap Taze", "en": "Fresh Rap"},
    },
    "yeni-nesil-turkce-rap": {
        "title": {"tr": "Yeni Nesil Türkçe Rap", "en": "Next Gen Turkish Rap"},
        "description": {
            "tr": "Türkiye'den yeni nesil Türkçe rap seçimleri.",
            "en": "Next generation Turkish rap picks from Turkey.",
        },
        "badge": {"tr": "Yeni Nesil", "en": "Next Gen"},
    },
    "yeni-turkuler": {
        "title": {"tr": "Yeni Türküler", "en": "New Folk Songs"},
        "description": {
            "tr": "Her hafta yenilenen yeni türkü seçimleri.",
            "en": "Fresh folk picks refreshed every week.",
        },
        "badge": {"tr": "Anadolu", "en": "Anatolia"},
    },
    "yeni-arabesk": {
        "title": {"tr": "Yeni Arabesk", "en": "New Arabesque"},
        "description": {
            "tr": "Güncel arabesk şarkılarından taze seçimler.",
            "en": "Fresh picks from current arabesque songs.",
        },
        "badge": {"tr": "Arabesk", "en": "Arabesque"},
    },
    "guncel-pop-sarkilari": {
        "title": {"tr": "Güncel Pop Şarkıları", "en": "Current Pop Songs"},
        "description": {
            "tr": "Şu an öne çıkan güncel pop şarkıları.",
            "en": "Current pop songs breaking out right now.",
        },
        "badge": {"tr": "Şimdi Pop", "en": "Pop Now"},
    },
    "sakin-turkce-indie": {
        "title": {"tr": "Sakin Türkçe Indie", "en": "Calm Turkish Indie"},
        "description": {
            "tr": "Sakin ve içten Türkçe indie şarkılar.",
            "en": "Calm and intimate Turkish indie songs.",
        },
        "badge": {"tr": "Indie", "en": "Indie"},
    },
    "guncel-turkce-rock": {
        "title": {"tr": "Güncel Türkçe Rock", "en": "Current Turkish Rock"},
        "description": {
            "tr": "Türkiye'den güncel rock ve alternatif şarkılar.",
            "en": "Current rock and alternative songs from Turkey.",
        },
        "badge": {"tr": "Rock", "en": "Rock"},
    },
    "elektronik-muzik-turkiye": {
        "title": {"tr": "Elektronik Müzik Türkiye", "en": "Turkey Electronic"},
        "description": {
            "tr": "Türkiye'den elektronik ve dans müziği listesi.",
            "en": "Electronic and dance music from Turkey.",
        },
        "badge": {"tr": "Elektronik", "en": "Electronic"},
    },
    "calisirken-dinlemelik": {
        "title": {"tr": "Çalışırken Dinlemelik", "en": "Focus While Working"},
        "description": {
            "tr": "Odaklanmayı kolaylaştıran sakin müzikler.",
            "en": "Calm tracks that make it easier to focus.",
        },
        "badge": {"tr": "Odak", "en": "Focus"},
    },
    "yumusak-piyano": {
        "title": {"tr": "Yumuşak Piyano", "en": "Soft Piano"},
        "description": {
            "tr": "Dinlendirici ve duygusal piyano melodileri.",
            "en": "Relaxing and emotional piano melodies.",
        },
        "badge": {"tr": "Piyano", "en": "Piano"},
    },
    "caz-gecesi": {
        "title": {"tr": "Caz Gecesi", "en": "Jazz Night"},
        "description": {
            "tr": "Gece için seçilmiş caz ve smooth şarkılar.",
            "en": "Jazz and smooth picks for late hours.",
        },
        "badge": {"tr": "Caz", "en": "Jazz"},
    },
    "yabanci-pop-klasikleri": {
        "title": {"tr": "Yabancı Pop Klasikleri", "en": "International Pop Classics"},
        "description": {
            "tr": "Dünyanın dört bir yanından pop klasikleri.",
            "en": "Pop classics from around the world.",
        },
        "badge": {"tr": "Klasikler", "en": "Classics"},
    },
    "lofi-muzikler": {
        "title": {"tr": "Lo-Fi Müzikler", "en": "Lo-Fi Music"},
        "description": {
            "tr": "Rahatlatıcı lo-fi beat'ler ve chillhop seçimleri.",
            "en": "Relaxing lo-fi beats and chillhop picks.",
        },
        "badge": {"tr": "Lo-Fi", "en": "Lo-Fi"},
    },
}

_CURATED_HOME_COPY["turkiye-trendler"] = {
    "title": {"tr": "T\u00fcrkiye Trendler", "en": "Turkey Trends"},
    "description": {
        "tr": "T\u00fcrkiye'de \u015fu an \u00f6ne \u00e7\u0131kan \u015fark\u0131lar.",
        "en": "The songs trending in Turkey right now.",
    },
    "badge": {"tr": "Trend", "en": "Trending"},
}


def _curated_copy(app, spec: dict, field: str, fallback: str = "") -> str:
    slug = str(spec.get("slug") or "").strip()
    lang = str(getattr(app, "_language", "tr") or "tr")
    entry = _CURATED_HOME_COPY.get(slug) or {}
    value = repair_mojibake_text((entry.get(field) or {}).get(lang) or "")
    raw = repair_mojibake_text(spec.get(field) or "")
    fallback_text = repair_mojibake_text(fallback or "")
    if value:
        return str(value).strip()
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return str(fallback_text or "")

_CURATED_HOME_THEMES = {
    "_default": {
        "accent": "#6EA8FF",
        "accent_soft": "#82C6FF",
        "surface": "#151a28",
        "surface_alt": "#0d1320",
        "badge": "",
        "style": "poster",
    },
    "yeni-cikanlar": {
        "accent": "#ff4f70",
        "accent_soft": "#ff9d76",
        "surface": "#23151d",
        "surface_alt": "#111827",
        "badge": "Her Cuma",
        "style": "poster",
    },
    "turkiye-trendler": {
        "accent": "#4da3ff",
        "accent_soft": "#89c7ff",
        "surface": "#121c2b",
        "surface_alt": "#0d1420",
        "badge": "Trend",
        "style": "band",
    },
    "yeni-turkce-pop": {
        "accent": "#ff8c54",
        "accent_soft": "#ffc76b",
        "surface": "#23171a",
        "surface_alt": "#101726",
        "badge": "Pop Taze",
        "style": "split",
    },
    "yeni-turkce-rap": {
        "accent": "#ff3b3b",
        "accent_soft": "#ff7b54",
        "surface": "#211215",
        "surface_alt": "#12131d",
        "badge": "Rap Taze",
        "style": "band",
    },
    "yeni-nesil-turkce-rap": {
        "accent": "#b15cff",
        "accent_soft": "#ff5fb2",
        "surface": "#1a1324",
        "surface_alt": "#10131f",
        "badge": "Yeni Nesil",
        "style": "split",
    },
    "yeni-turkuler": {
        "accent": "#f0b74d",
        "accent_soft": "#ffe08c",
        "surface": "#241c10",
        "surface_alt": "#111725",
        "badge": "Anadolu",
        "style": "poster",
    },
    "yeni-arabesk": {
        "accent": "#64dfdf",
        "accent_soft": "#80ffdb",
        "surface": "#11211e",
        "surface_alt": "#0d1622",
        "badge": "Arabesk",
        "style": "band",
    },
    "guncel-pop-sarkilari": {
        "accent": "#ff71ce",
        "accent_soft": "#b8ff6a",
        "surface": "#221328",
        "surface_alt": "#0f1624",
        "badge": "Şimdi Pop",
        "style": "poster",
    },
    "sakin-turkce-indie": {
        "accent": "#5ec4ff",
        "accent_soft": "#a0e4ff",
        "surface": "#0f1e2e",
        "surface_alt": "#0a1422",
        "badge": "İndie",
        "style": "poster",
    },
    "guncel-turkce-rock": {
        "accent": "#ff6b35",
        "accent_soft": "#ffab76",
        "surface": "#221410",
        "surface_alt": "#120e0a",
        "badge": "Rock",
        "style": "band",
    },
    "elektronik-muzik-turkiye": {
        "accent": "#00d4ff",
        "accent_soft": "#80eeff",
        "surface": "#071828",
        "surface_alt": "#040f1a",
        "badge": "Elektronik",
        "style": "split",
    },
    "calisirken-dinlemelik": {
        "accent": "#43e97b",
        "accent_soft": "#9fffc8",
        "surface": "#0d1f18",
        "surface_alt": "#081410",
        "badge": "Odak",
        "style": "poster",
    },
    "yumusak-piyano": {
        "accent": "#e0c3fc",
        "accent_soft": "#f5e6ff",
        "surface": "#1a1428",
        "surface_alt": "#100d1c",
        "badge": "Piyano",
        "style": "poster",
    },
    "caz-gecesi": {
        "accent": "#ffd166",
        "accent_soft": "#ffe9a0",
        "surface": "#1e1a0a",
        "surface_alt": "#121006",
        "badge": "Caz",
        "style": "split",
    },
    "yabanci-pop-klasikleri": {
        "accent": "#f72585",
        "accent_soft": "#ff85b3",
        "surface": "#21101c",
        "surface_alt": "#130a12",
        "badge": "Klasikler",
        "style": "poster",
    },
    "lofi-muzikler": {
        "accent": "#9b8bf4",
        "accent_soft": "#c8beff",
        "surface": "#13112a",
        "surface_alt": "#0c0a1c",
        "badge": "Lo-Fi",
        "style": "band",
    },
}


def _home_url_params(url: str):
    from urllib.parse import parse_qs, urlparse

    parsed = urlparse(str(url or "").strip())
    query = parse_qs(parsed.query or "")
    return {
        "video_id": str((query.get("v") or [""])[0] or "").strip(),
        "playlist_id": str((query.get("list") or [""])[0] or "").strip(),
    }


def _home_cover_slug(value: str):
    text = app_norm = _H._clean_section_title(value or "").lower()
    for src, dst in (("ç", "c"), ("ğ", "g"), ("ı", "i"), ("ö", "o"), ("ş", "s"), ("ü", "u")):
        text = text.replace(src, dst)
    cleaned = []
    prev_dash = False
    for ch in text:
        if ch.isalnum():
            cleaned.append(ch)
            prev_dash = False
        elif not prev_dash:
            cleaned.append("-")
            prev_dash = True
    return "".join(cleaned).strip("-")


def _home_rgba(color: str, alpha: int) -> str:
    fallback = str(color or _H.get_accent() or "#6EA8FF")
    qcolor = QColor(fallback)
    if not qcolor.isValid():
        qcolor = QColor("#6EA8FF")
    return f"rgba({qcolor.red()}, {qcolor.green()}, {qcolor.blue()}, {max(0, min(255, int(alpha)))})"


def _home_playlist_theme(item=None):
    item = item or {}
    slug = str(item.get("slug") or _home_cover_slug(item.get("title") or "")).strip()
    base = dict(_CURATED_HOME_THEMES.get("_default", {}))
    base.update(_CURATED_HOME_THEMES.get(slug, {}))
    item_badge = str(item.get("badge") or "").strip()
    if item_badge:
        base["badge"] = item_badge
    # Curated kartlar uygulamanin aktif accent rengini izlesin; boylece
    # ana tema koyu mavi cizgiden kopmadan tutarli kalir.
    base["accent"] = _H.get_accent()
    base["accent_soft"] = _H.get_accent_hover()
    base["surface"] = _H.BG_CARD
    base["surface_alt"] = _H.BG_ELEVATED
    base["slug"] = slug
    return base


def _home_local_cover_path(spec: dict, playlist_id: str):
    from pathlib import Path

    from utils.helpers import BASE_PATH
    cover_dir = Path(BASE_PATH) / "assets" / "home_covers"
    candidates = [
        str(spec.get("slug") or "").strip(),
        _home_cover_slug(spec.get("title") or ""),
        str(playlist_id or "").strip(),
    ]
    for stem in candidates:
        if not stem:
            continue
        for ext in (".png", ".jpg", ".jpeg", ".webp"):
            path = cover_dir / f"{stem}{ext}"
            if path.is_file():
                return str(path)
    return ""


def _curated_cover_cache_dir(app):
    path = os.path.join(app.base_dir, "cache", "home_curated_covers")
    os.makedirs(path, exist_ok=True)
    return path


def _curated_cover_cache_path(app, slug: str):
    clean_slug = re.sub(r"[^a-z0-9_-]+", "-", str(slug or "").strip().lower()).strip("-") or "cover"
    return os.path.join(_curated_cover_cache_dir(app), f"{clean_slug}.jpg")


def _curated_placeholder_cover_dir(app):
    path = os.path.join(app.base_dir, "cache", "home_curated_placeholders")
    os.makedirs(path, exist_ok=True)
    return path


def _curated_placeholder_cover_path(app, slug: str):
    clean_slug = re.sub(r"[^a-z0-9_-]+", "-", str(slug or "").strip().lower()).strip("-") or "cover"
    return os.path.join(_curated_placeholder_cover_dir(app), f"{clean_slug}.png")


def _draw_curated_placeholder_cover(app, row: dict, slug: str) -> str:
    """Generate a local cover image while the live playlist artwork loads."""
    target = _curated_placeholder_cover_path(app, slug)
    try:
        if os.path.isfile(target) and os.path.getsize(target) > 1024:
            return target
    except Exception:
        pass

    try:
        w, h = 960, 600
        title = repair_mojibake_text(str(row.get("title") or app._tr("home.playlist") or "Playlist"))
        badge = repair_mojibake_text(str(row.get("badge") or row.get("section_title") or app._tr("home.new_songs.source") or "Fresh List"))
        region = repair_mojibake_text(_content_region_name(app))
        theme = _home_playlist_theme(row)
        accent = QColor(str(theme.get("accent") or _H.get_accent() or "#22c55e"))
        accent_soft = QColor(str(theme.get("accent_soft") or _H.get_accent_hover() or "#63e6be"))
        if not accent.isValid():
            accent = QColor("#22c55e")
        if not accent_soft.isValid():
            accent_soft = QColor("#63e6be")

        img = QImage(w, h, QImage.Format_ARGB32)
        img.fill(QColor("#0b1019"))
        painter = QPainter(img)
        try:
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setRenderHint(QPainter.TextAntialiasing)
            bg = QLinearGradient(0, 0, w, h)
            bg.setColorAt(0.0, QColor(14, 22, 35))
            bg.setColorAt(0.48, QColor(10, 15, 25))
            bg.setColorAt(1.0, QColor(3, 7, 13))
            painter.fillRect(0, 0, w, h, QBrush(bg))
            glow = QRadialGradient(int(w * 0.22), int(h * 0.22), int(w * 0.62))
            glow.setColorAt(0.0, QColor(accent.red(), accent.green(), accent.blue(), 125))
            glow.setColorAt(0.42, QColor(accent.red(), accent.green(), accent.blue(), 34))
            glow.setColorAt(1.0, QColor(accent.red(), accent.green(), accent.blue(), 0))
            painter.fillRect(0, 0, w, h, QBrush(glow))
            glow2 = QRadialGradient(int(w * 0.88), int(h * 0.78), int(w * 0.55))
            glow2.setColorAt(0.0, QColor(accent_soft.red(), accent_soft.green(), accent_soft.blue(), 82))
            glow2.setColorAt(0.52, QColor(accent_soft.red(), accent_soft.green(), accent_soft.blue(), 22))
            glow2.setColorAt(1.0, QColor(accent_soft.red(), accent_soft.green(), accent_soft.blue(), 0))
            painter.fillRect(0, 0, w, h, QBrush(glow2))
            painter.setPen(Qt.NoPen)
            for x, y, size, alpha in ((650, 80, 210, 48), (585, 220, 260, 64), (720, 350, 180, 42)):
                rect = QRectF(x, y, size, size)
                card_grad = QLinearGradient(rect.left(), rect.top(), rect.right(), rect.bottom())
                card_grad.setColorAt(0.0, QColor(accent_soft.red(), accent_soft.green(), accent_soft.blue(), alpha))
                card_grad.setColorAt(1.0, QColor(255, 255, 255, 10))
                painter.setBrush(QBrush(card_grad))
                painter.drawRoundedRect(rect, 34, 34)
                painter.setPen(QPen(QColor(255, 255, 255, 26), 2))
                painter.setBrush(Qt.NoBrush)
                painter.drawRoundedRect(rect.adjusted(2, 2, -2, -2), 32, 32)
                painter.setPen(Qt.NoPen)
            bar_x = 72
            bar_bottom = 505
            bars = [44, 88, 132, 74, 170, 108, 58, 146, 92, 120, 66, 154]
            for i, bh in enumerate(bars):
                color = QColor(accent.red(), accent.green(), accent.blue(), 115 if i % 2 else 170)
                painter.setBrush(color)
                painter.drawRoundedRect(QRectF(bar_x + i * 23, bar_bottom - bh, 12, bh), 6, 6)
            painter.setFont(QFont("Segoe UI", 22, QFont.Black))
            badge_text = (badge or "Fresh List")[:28]
            fm = painter.fontMetrics()
            pill_w = min(360, max(150, fm.horizontalAdvance(badge_text) + 48))
            pill_rect = QRectF(58, 54, pill_w, 54)
            painter.setBrush(QColor(7, 18, 33, 210))
            painter.setPen(QPen(QColor(accent_soft.red(), accent_soft.green(), accent_soft.blue(), 90), 2))
            painter.drawRoundedRect(pill_rect, 27, 27)
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(pill_rect, Qt.AlignCenter, badge_text)
            painter.setPen(QColor(255, 255, 255))
            painter.setFont(QFont("Segoe UI", 58, QFont.Black))
            painter.drawText(QRectF(58, 150, 570, 165), Qt.AlignLeft | Qt.AlignVCenter | Qt.TextWordWrap, title)
            painter.setFont(QFont("Segoe UI", 24, QFont.DemiBold))
            painter.setPen(QColor(203, 213, 225))
            subtitle = f"{region} • IQTMusic" if region else "IQTMusic"
            painter.drawText(QRectF(62, 326, 520, 44), Qt.AlignLeft | Qt.AlignVCenter, subtitle)
            painter.setFont(QFont("Segoe UI Symbol", 132, QFont.Bold))
            painter.setPen(QColor(accent_soft.red(), accent_soft.green(), accent_soft.blue(), 138))
            painter.drawText(QRectF(690, 150, 190, 190), Qt.AlignCenter, "♫")
            vignette = QLinearGradient(0, int(h * 0.55), 0, h)
            vignette.setColorAt(0.0, QColor(0, 0, 0, 0))
            vignette.setColorAt(1.0, QColor(0, 0, 0, 145))
            painter.fillRect(0, 0, w, h, QBrush(vignette))
        finally:
            painter.end()
        if img.save(target, "PNG"):
            return target
    except Exception as _e:
        log.debug("Curated placeholder kapak oluşturulamadı (%s): %s", slug, _e)
    return ""


def _curated_cover_is_fresh(path: str) -> bool:
    try:
        return bool(path) and os.path.isfile(path) and (time.time() - os.path.getmtime(path)) <= _HOME_CURATED_COVER_TTL_SEC
    except Exception as _e:
        log.debug("Sessiz hata: %s", _e)
        return False


def _curated_cached_cover_path(app, slug: str, allow_stale: bool = True):
    path = _curated_cover_cache_path(app, slug)
    if not os.path.isfile(path):
        return ""
    if allow_stale or _curated_cover_is_fresh(path):
        return path
    return ""


def _home_cover_url_candidates(url: str) -> list[str]:
    raw = str(url or "").strip()
    if not raw:
        return []
    candidates = []

    def _push(value):
        value = str(value or "").strip()
        if value and value not in candidates:
            candidates.append(value)

    if os.path.isfile(raw):
        _push(raw)
        return candidates

    if "i.ytimg.com/vi/" in raw:
        _push(raw.replace("/hqdefault.", "/maxresdefault."))
        _push(raw.replace("/hqdefault.", "/sddefault."))
        _push(raw)
        return candidates

    if "googleusercontent.com" in raw or "yt3.ggpht.com" in raw:
        base = raw.split("=", 1)[0]
        _push(f"{base}=w1200-h1200-l90-rj")
        _push(f"{base}=w900-h900-l90-rj")
        _push(f"{base}=w720-h720-l90-rj")
        _push(raw)
        return candidates

    _push(raw)
    return candidates


def _save_curated_cover_image(app, source_url: str, slug: str):
    target_path = _curated_cover_cache_path(app, slug)
    tmp_path = f"{target_path}.tmp"
    try:
        for candidate in _home_cover_url_candidates(source_url):
            try:
                if os.path.isfile(candidate):
                    img = QImage(candidate)
                else:
                    resp = app._http.get(candidate, timeout=8)
                    resp.raise_for_status()
                    img = QImage()
                    img.loadFromData(resp.content)
                if img.isNull():
                    continue
                if max(img.width(), img.height()) > _HOME_CURATED_COVER_MAX_EDGE:
                    img = img.scaled(
                        _HOME_CURATED_COVER_MAX_EDGE,
                        _HOME_CURATED_COVER_MAX_EDGE,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation,
                    )
                if not img.save(tmp_path, "JPG", _HOME_CURATED_COVER_JPEG_QUALITY):
                    continue
                os.replace(tmp_path, target_path)
                return target_path
            except Exception as _e:
                log.debug("Curated cover kaydedilemedi (%s): %s", candidate, _e)
        return ""
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception as _e:
                log.debug("Sessiz hata: %s", _e)


def _resolve_curated_cover_source(app, card: dict) -> str:
    playlist_query = str(card.get("playlist_query") or "").strip()
    query = str(card.get("query") or card.get("fallback_query") or "").strip()
    source_query = playlist_query or query
    tracks = []
    try:
        if source_query.startswith("ytm:playlist:"):
            playlist_id = source_query.split("ytm:playlist:", 1)[1]
            tracks = list(app._ytm_playlist_tracks(playlist_id, limit=6) or [])
        elif source_query:
            tracks = list(app._fetch_feed_results(source_query, limit=6) or [])
    except Exception as _e:
        log.debug("Curated cover kaynagi alinmadi (%s): %s", source_query, _e)
    covers = _home_track_cover_urls(app, tracks, limit=1)
    if covers:
        return covers[0]
    video_id = str(card.get("video_id") or "").strip()
    if video_id:
        return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
    return ""


def _prepare_curated_playlist_covers(app, items=None, force_refresh: bool = False):
    rows = [dict(item) for item in list(items or _curated_home_cards(app) or [])]
    enriched = []
    for row in rows:
        slug = str(row.get("slug") or _home_cover_slug(row.get("title") or "")).strip()
        fresh_local = _curated_cached_cover_path(app, slug, allow_stale=False)
        stale_local = fresh_local or _curated_cached_cover_path(app, slug, allow_stale=True)
        art_path = fresh_local
        if force_refresh or not fresh_local:
            source_url = _resolve_curated_cover_source(app, row)
            if source_url:
                saved_path = _save_curated_cover_image(app, source_url, slug)
                if saved_path:
                    art_path = saved_path
                    stale_local = saved_path
        placeholder = ""
        if not (art_path or stale_local):
            placeholder = _draw_curated_placeholder_cover(app, row, slug)
        row["art_url"] = art_path or stale_local or placeholder or ""
        row["cover_urls"] = []
        row["preview_loaded"] = bool(art_path or stale_local)
        row["placeholder_cover"] = bool(placeholder and not (art_path or stale_local))
        enriched.append(row)

    _cache_set(app, _curated_home_cards_cache_key(app), enriched)
    return enriched


def _curated_home_cards(app):
    cache_key = _curated_home_cards_cache_key(app)
    cached = _cache_get(app, cache_key, ttl=1800)
    if cached is not None:
        return list(cached)

    cards = []
    for spec in _region_curated_home_playlists(app):
        params = _home_url_params(spec.get("url") or "")
        playlist_id = params.get("playlist_id") or ""
        video_id = params.get("video_id") or ""
        playlist_query = f"ytm:playlist:{playlist_id}" if playlist_id else ""
        fallback_query = str(spec.get("fallback_query") or "feed:new.music").strip()
        resolved_query = playlist_query or fallback_query
        slug = str(spec.get("slug") or "")
        cached_cover_path = _curated_cached_cover_path(app, slug, allow_stale=True)
        base_row = {
            "title": _curated_copy(app, spec, "title", app._tr("home.playlist")),
            "subtitle": _curated_copy(app, spec, "description", ""),
            "badge": _curated_copy(app, spec, "badge", ""),
            "query": resolved_query or "feed:new.music",
            "playlist_query": playlist_query,
            "fallback_query": fallback_query,
            "count": "",
            "slug": slug,
            "section_title": app._tr("home.new_songs.source"),
            "track_preview": [],
            "cover_urls": [],
            "video_id": video_id,
        }
        placeholder_cover_path = "" if cached_cover_path else _draw_curated_placeholder_cover(app, base_row, slug)
        base_row.update({
            "art_url": cached_cover_path or placeholder_cover_path,
            "preview_loaded": bool(cached_cover_path),
            "placeholder_cover": bool(placeholder_cover_path and not cached_cover_path),
        })
        cards.append(base_row)

    _cache_set(app, cache_key, cards)
    return list(cards)


def _obsolete_wrong_spotlight_entries(app, limit=4):
    curated = _curated_home_cards(app)
    if curated:
        return list(curated[: max(1, int(limit or 4))])
    return _DEFAULT_SPOTLIGHT_ENTRIES(app, limit=limit)


def _obsolete_wrong_hero(app, sections):
    curated = _curated_home_cards(app)
    if curated:
        lead = dict(curated[0])
        return {
            "item": lead,
            "tracks": list(lead.get("track_preview") or []),
            "source": app._tr("home.new_songs.source"),
            "query": lead.get("query") or "feed:new.music",
            "desc": str(lead.get("subtitle") or "Her hafta güncellenen çalma listesi."),
            "support": list(curated[4:7]),
        }
    return _DEFAULT_HERO(app, sections)


def _obsolete_wrong_bundle(app):
    curated = _curated_home_cards(app)
    if curated:
        return {
            "buttons": _buttons(app),
            "hero": _hero(app, []),
            "sections": [],
            "spotlights": _spotlight_entries(app, limit=4),
            "playlist_mode": True,
            "curated_mode": True,
        }
    bundle = _DEFAULT_BUNDLE(app)
    bundle["curated_mode"] = False
    return bundle


def _obsolete_wrong_apply_bundle(app, bundle):
    if not bundle.get("curated_mode"):
        _DEFAULT_APPLY_BUNDLE(app, bundle)
        return

    refs = getattr(app, "_home_refs", {})
    if not refs:
        return

    hero = bundle.get("hero") or {}
    item = hero.get("item") or {}
    preview_tracks = list(hero.get("tracks") or [])

    refs["source"].setText(_tr_upper(hero.get("source") or app._tr("home.new_songs.source")))
    refs["title"].setText(str(item.get("title") or app._tr("home.new_songs.title")))
    refs["artist"].setText(str(item.get("subtitle") or app._tr("home.new_songs.subtitle")))
    refs["desc"].setText(app._tr("home.new_songs.desc"))
    refs["cover"].clear()
    art_url = str(item.get("art_url") or "").strip()
    if art_url:
        app._load_image(art_url, refs["cover"], (220, 220))

    lead_track = preview_tracks[0] if preview_tracks else None
    _rebind(
        refs["play"],
        lambda tr=lead_track, q=item.get("query") or "", t=item.get("title") or "Liste": app.force_play(tr) if tr else app.page_category(t, q, "songs"),
    )
    _rebind(
        refs["open"],
        lambda q=item.get("query") or "", t=item.get("title") or "Liste": app.page_category(t, q, "songs"),
    )
    _rebind(refs["refresh"], getattr(app, "_home_reload_current", app._refresh_home_feed))
    _render_buttons(app, bundle.get("buttons") or [])
    _render_spotlights(app, bundle.get("spotlights") or [])
    _render_hero_support(app, hero.get("support") or [])

    spotlight_label = refs.get("spotlight_label")
    if spotlight_label is not None:
        spotlight_label.setText(app._tr("home.new_songs.title"))
    support_label = refs.get("support_label")
    if support_label is not None:
        support_label.setText(app._tr("home.hero.support"))

    rail = refs.get("rail")
    if rail is not None:
        rail.setVisible(False)

    live = refs["live"]
    live.setVisible(False)
    _clear(live.layout())


def _apply_tab(app, query, results):
    info = app._home_state["tabs"].get(query)
    if not info or not qt_is_valid(info["frame"]):
        return
    _clear(info["frame"].layout())
    if results:
        _render_editorial_strip(app, info["frame"].layout(), results, mode="poster", limit=10)
    else:
        box = QFrame()
        box.setStyleSheet(f"background:{_H.BG_CARD}; border:1px solid {_H.BORDER_COLOR}; border-radius:18px;")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(20, 18, 20, 18)
        t = QLabel(app._tr("home.tab.empty.title"))
        t.setStyleSheet(f"color:{_H.TEXT_PRIMARY}; font-size:14px; font-weight:850; background:transparent;")
        s = QLabel(app._tr("home.tab.empty.subtitle"))
        s.setStyleSheet(f"color:{_H.TEXT_MUTED}; font-size:12px; background:transparent;")
        lay.addWidget(t)
        lay.addWidget(s)
        info["frame"].layout().addWidget(box)
        info["frame"].layout().addStretch()
    info["loaded"] = True
    info["loading"] = False


def _load_tab_async(app, query, force=False):
    info = app._home_state["tabs"].get(query)
    if not info or (info["loading"] and not force):
        return
    key = f"__home_bundle::tab::{_region_cache_suffix(app)}::{query}"
    cached = None if force else _cache_get(app, key)
    if cached is not None:
        _apply_tab(app, query, list(cached))
        return
    info["loading"] = True
    info["loaded"] = False
    _clear(info["frame"].layout())
    for _ in range(5):
        info["frame"].layout().addWidget(SkeletonWidget(width=228, height=322, radius=22))
    info["frame"].layout().addStretch()
    bridge = getattr(app, "_home_bridge", None)
    token = getattr(app, "_home_ui_token", None)

    def _work():
        try:
            results = list(app._fetch_feed_results(query, limit=20) or [])
        except Exception as e:
            log.warning("Home tab yüklenemedi (%s): %s", query, e)
            results = []
        _cache_set(app, key, results)
        if bridge is not None:
            bridge.tab_ready.emit(token, query, results)

    app._net_pool.submit(_work)


def build_home_page(app):
    curated_spotlights = globals().get("_CURATED_HOME_SPOTLIGHT_ENTRIES_IMPL")
    curated_hero = globals().get("_CURATED_HOME_HERO_IMPL")
    curated_bundle = globals().get("_CURATED_HOME_BUNDLE_IMPL")
    curated_apply_bundle = globals().get("_CURATED_HOME_APPLY_BUNDLE_IMPL")
    if callable(curated_spotlights):
        globals()["_spotlight_entries"] = curated_spotlights
    if callable(curated_hero):
        globals()["_hero"] = curated_hero
    if callable(curated_bundle):
        globals()["_bundle"] = curated_bundle
    if callable(curated_apply_bundle):
        globals()["_apply_bundle"] = curated_apply_bundle

    _H._make_section_header = _header
    app.current_page = "home"
    app.prev_page = None
    if getattr(app, "_home_feed_cache_version", None) != _HOME_CACHE_VERSION:
        try:
            app._home_cache.clear()
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
        app._home_feed_cache_version = _HOME_CACHE_VERSION
    app._home_ui_token = _next_ui_token(app)
    app._home_state = {"active": getattr(app, "_home_active_tab_query", _TABS[0][1]), "tabs": {}}
    app._home_refs = {}

    page = QWidget()
    root = QVBoxLayout(page)
    root.setContentsMargins(0, 0, 0, 0)
    page.setStyleSheet(f"background:{_H.BG_BLACK};")
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setStyleSheet("background:transparent; border:none;")
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    root.addWidget(scroll)

    host = QWidget()
    host.setObjectName("TC")
    host.setMinimumWidth(_HOME_DEFAULT_HOST_MIN_WIDTH)
    layout = QVBoxLayout(host)
    layout.setContentsMargins(36, 28, 36, 32)
    layout.setSpacing(0)
    scroll.setWidget(host)
    app._home_refs["page"] = page
    app._home_refs["scroll_area"] = scroll
    app._home_refs["scroll_host"] = host

    greet, sub = _intro(app)
    layout.addWidget(
        _build_page_header(
            app,
            greet,
            sub,
            eyebrow="",
        )
    )
    layout.addSpacing(18)

    personal = QWidget(); personal.setStyleSheet("background:transparent; border:none;"); per_l = QVBoxLayout(personal); per_l.setContentsMargins(0, 0, 0, 0); per_l.setSpacing(8); personal.hide()
    app._home_refs["personal"] = personal
    layout.addWidget(personal)
    layout.addSpacing(18)

    playlist_grid_box = QWidget()
    playlist_grid_box.setStyleSheet("background:transparent; border:none;")
    playlist_grid_box.hide()
    playlist_grid_v = QVBoxLayout(playlist_grid_box)
    playlist_grid_v.setContentsMargins(0, 0, 0, 0)
    playlist_grid_v.setSpacing(14)

    grid_head = QHBoxLayout()
    grid_head.setSpacing(16)
    grid_text = QVBoxLayout()
    grid_text.setSpacing(4)
    playlist_grid_title = QLabel(app._tr("home.grid.title"))
    playlist_grid_title.setStyleSheet(f"color:{_H.TEXT_PRIMARY}; font-size:28px; font-weight:900; background:transparent;")
    playlist_grid_desc = QLabel(app._tr("home.grid.desc"))
    playlist_grid_desc.setWordWrap(True)
    playlist_grid_desc.setStyleSheet(f"color:{_H.TEXT_SECONDARY}; font-size:13px; background:transparent;")
    grid_text.addWidget(playlist_grid_title)
    grid_text.addWidget(playlist_grid_desc)
    grid_head.addLayout(grid_text, 1)
    playlist_grid_refresh = QPushButton(app._tr("home.hero.refresh"))
    playlist_grid_refresh.setFixedHeight(38)
    playlist_grid_refresh.setCursor(Qt.PointingHandCursor)
    playlist_grid_refresh.setStyleSheet(_ghost_btn())
    grid_head.addWidget(playlist_grid_refresh, 0, Qt.AlignTop)
    playlist_grid_v.addLayout(grid_head)

    playlist_grid = QGridLayout()
    playlist_grid.setContentsMargins(0, 0, 0, 0)
    playlist_grid.setHorizontalSpacing(16)
    playlist_grid.setVerticalSpacing(16)
    playlist_grid_v.addLayout(playlist_grid)
    layout.addWidget(playlist_grid_box)
    layout.addSpacing(18)

    hero = QFrame()
    hero.setObjectName("HomeHero")
    hero.setStyleSheet(
        f"""
        QFrame#HomeHero {{
            background:qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 rgba(255,255,255,0.02), stop:0.18 {_H.get_accent()}16, stop:0.62 {_H.BG_CARD}, stop:1 {_H.BG_ELEVATED});
            border-radius:26px;
            border:1px solid {_H.get_accent()}24;
        }}
        QFrame#HomeHero QLabel {{
            background:transparent;
            border:none;
        }}
        QFrame#HomeHero QWidget {{
            background:transparent;
        }}
        """
    )
    hero_l = QVBoxLayout(hero)
    hero_l.setContentsMargins(28, 28, 28, 24)
    hero_l.setSpacing(18)
    top = QHBoxLayout(); top.setSpacing(28); hero_l.addLayout(top)
    left = QVBoxLayout(); left.setSpacing(8); top.addLayout(left, 1)
    source = QLabel(); source.setStyleSheet(f"color:{_H.get_accent()}; font-size:11px; font-weight:900; letter-spacing:2px;")
    title = QLabel(); title.setWordWrap(True); title.setStyleSheet(f"color:{_H.TEXT_PRIMARY}; font-size:34px; font-weight:900;")
    artist = QLabel(); artist.setStyleSheet(f"color:{_H.TEXT_SECONDARY}; font-size:16px; font-weight:700;")
    desc = QLabel(); desc.setWordWrap(True); desc.setStyleSheet(f"color:{_H.TEXT_MUTED}; font-size:13px;")
    left.addWidget(source); left.addWidget(title); left.addWidget(artist); left.addWidget(desc)
    btns = QHBoxLayout(); btns.setSpacing(10)
    play = QPushButton(app._tr("home.hero.play")); play.setFixedHeight(42); play.setCursor(Qt.PointingHandCursor); play.setStyleSheet(_solid_btn())
    open_btn = QPushButton(app._tr("home.hero.open")); open_btn.setFixedHeight(42); open_btn.setCursor(Qt.PointingHandCursor); open_btn.setStyleSheet(_ghost_btn())
    refresh = QPushButton(app._tr("home.hero.refresh")); refresh.setFixedHeight(42); refresh.setCursor(Qt.PointingHandCursor); refresh.setStyleSheet(_ghost_btn())
    btns.addWidget(play); btns.addWidget(open_btn); btns.addWidget(refresh); btns.addStretch()
    left.addLayout(btns)
    spotlight_wrap = QWidget(); spotlight_wrap.setStyleSheet("background:transparent; border:none;")
    spotlight_v = QVBoxLayout(spotlight_wrap); spotlight_v.setContentsMargins(0, 8, 0, 0); spotlight_v.setSpacing(10)
    spotlight_lbl = QLabel(app._tr("home.hero.spotlight"))
    spotlight_lbl.setStyleSheet(f"color:{_H.TEXT_PRIMARY}; font-size:13px; font-weight:850; background:transparent;")
    spotlight_v.addWidget(spotlight_lbl)
    spotlight_scroll = QScrollArea(); spotlight_scroll.setFixedHeight(312); spotlight_scroll.setWidgetResizable(False); spotlight_scroll.setStyleSheet("background:transparent; border:none;")
    spotlight_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff); spotlight_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    spotlight_host = QWidget(); spotlight_host.setObjectName("TC")
    spotlights = QHBoxLayout(spotlight_host); spotlights.setContentsMargins(0, 0, 0, 0); spotlights.setSpacing(12)
    spotlight_scroll.setWidget(spotlight_host)
    spotlight_v.addWidget(spotlight_scroll)
    left.addWidget(spotlight_wrap)
    left.addStretch()
    right = QVBoxLayout(); right.setSpacing(12); top.addLayout(right, 0)
    cover = QLabel(); cover.setFixedSize(332, 224); cover.setAlignment(Qt.AlignCenter)
    cover.setStyleSheet(f"background:{_H.BG_CARD}; border:1px solid {_H.BORDER_COLOR}; border-radius:28px;")
    right.addWidget(cover, 0, Qt.AlignRight)
    support_lbl = QLabel(app._tr("home.hero.support"))
    support_lbl.setWordWrap(True); support_lbl.setAlignment(Qt.AlignRight | Qt.AlignTop)
    support_lbl.setStyleSheet(f"color:{_H.TEXT_PRIMARY}; font-size:12px; font-weight:850; background:transparent;")
    right.addWidget(support_lbl)
    support_wrap = QWidget(); support_wrap.setStyleSheet("background:transparent; border:none;")
    support_wrap.setMinimumWidth(332)
    support_v = QVBoxLayout(support_wrap); support_v.setContentsMargins(0, 0, 0, 0); support_v.setSpacing(10)
    right.addWidget(support_wrap); right.addStretch()
    chips_wrap = QWidget(); chips_wrap.setStyleSheet("background:transparent; border:none;")
    chips_wrap.hide()
    chips_v = QVBoxLayout(chips_wrap); chips_v.setContentsMargins(0, 0, 0, 0); chips_v.setSpacing(8)
    chips_lbl = QLabel(app._tr("home.hero.quick")); chips_lbl.setStyleSheet(f"color:{_H.TEXT_PRIMARY}; font-size:13px; font-weight:850; background:transparent;")
    chips_v.addWidget(chips_lbl)
    chip_scroll = QScrollArea(); chip_scroll.setFixedHeight(48); chip_scroll.setWidgetResizable(True); chip_scroll.setStyleSheet("background:transparent; border:none;")
    chip_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff); chip_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    chip_host = QWidget(); chip_host.setObjectName("TC")
    chips = QHBoxLayout(chip_host); chips.setContentsMargins(0, 0, 0, 0); chips.setSpacing(8)
    chip_scroll.setWidget(chip_host); chips_v.addWidget(chip_scroll); hero_l.addWidget(chips_wrap)
    app._home_refs.update({
        "playlist_grid_box": playlist_grid_box,
        "playlist_grid": playlist_grid,
        "playlist_grid_title": playlist_grid_title,
        "playlist_grid_desc": playlist_grid_desc,
        "playlist_grid_refresh": playlist_grid_refresh,
        "hero_frame": hero,
        "chips_wrap": chips_wrap,
        "source": source,
        "title": title,
        "artist": artist,
        "desc": desc,
        "play": play,
        "open": open_btn,
        "refresh": refresh,
        "cover": cover,
        "spotlights": spotlights,
        "chips": chips,
        "support": support_v,
        "spotlight_label": spotlight_lbl,
        "support_label": support_lbl,
    })
    layout.addWidget(hero); layout.addSpacing(18)

    rail = QFrame()
    rail_l = QVBoxLayout(rail); rail_l.setContentsMargins(0, 0, 0, 0); rail_l.setSpacing(10)
    rail_l.addWidget(_header(app._tr("home.hero.loading.source")))
    rail_sub = QLabel(app._tr("home.rail.subtitle"))
    rail_sub.setStyleSheet(f"color:{_H.TEXT_MUTED}; font-size:12px; background:transparent;")
    rail_l.addWidget(rail_sub)
    tab_row = QHBoxLayout(); tab_row.setSpacing(8); rail_l.addLayout(tab_row)
    stack = QStackedWidget(); rail_l.addWidget(stack); app._home_refs["stack"] = stack; app._home_refs["rail"] = rail
    for idx, (label_key, query, _desc) in enumerate(_TABS):
        btn = QPushButton(_regional_title(app, label_key, query)); btn.setFixedHeight(34); btn.setCursor(Qt.PointingHandCursor); btn.setStyleSheet(_tab_btn(False))
        btn.clicked.connect(lambda _, q=query: _activate_tab(app, q)); tab_row.addWidget(btn)
        page_sc = _H._mk_hscroll(); page_sc.setFixedHeight(352); frame = page_sc.widget(); frame.setProperty("dedupe_across_home", False); frame.setProperty("home_section_key", f"tab::{query}")
        stack.addWidget(page_sc); app._home_state["tabs"][query] = {"btn": btn, "frame": frame, "index": idx, "loaded": False, "loading": False}
    tab_row.addStretch()
    layout.addWidget(rail); layout.addSpacing(18)

    live = QWidget(); live.setStyleSheet("background:transparent; border:none;"); live_l = QVBoxLayout(live); live_l.setContentsMargins(0, 0, 0, 0); live_l.setSpacing(14); live.hide()
    app._home_refs["live"] = live
    layout.addWidget(live); layout.addStretch()

    bridge = _Bridge(app)
    page._home_bridge = bridge
    app._home_bridge = bridge
    curated_resize_filter = _CuratedGridResizeFilter(app)
    page._home_curated_resize_filter = curated_resize_filter
    scroll.viewport().installEventFilter(curated_resize_filter)
    playlist_grid_box.installEventFilter(curated_resize_filter)
    if not callable(getattr(app, "_legacy_refresh_home_feed", None)):
        app._legacy_refresh_home_feed = app._refresh_home_feed
    app._home_reload_current = lambda: _reload(app)
    app._refresh_home_feed = lambda: _refresh_entry(app)
    _render_buttons(app, list(_H.CATEGORY_BUTTONS[:6]))
    _render_personal(app)

    # Cache sıcaksa (splash'ta önyüklendi) skeleton göstermeden doğrudan render et.
    # Cache soğuksa skeleton göster ve async yükle.
    if _curated_home_cards(app):
        try:
            _apply_bundle(app, _bundle(app))
        except Exception as _e:
            log.debug("Senkron bundle hatası, skeleton'a düşülüyor: %s", _e)
            _set_curated_grid_loading(app)
            _load_bundle_async(app, app._home_ui_token)
    else:
        _set_curated_grid_loading(app)
        _load_bundle_async(app, app._home_ui_token)
    active = app._home_state["active"] if app._home_state["active"] in app._home_state["tabs"] else _TABS[0][1]
    _activate_tab(app, active)
    return page


def _home_text(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("text", "name", "title", "label"):
            text = _home_text(value.get(key))
            if text:
                return text
        return ""
    if isinstance(value, (list, tuple)):
        parts = [_home_text(item) for item in value]
        return " • ".join(part for part in parts if part)
    return str(value).strip()


def _home_collection_thumb(item):
    thumbs = item.get("thumbnails") or item.get("thumbnail") or []
    if isinstance(thumbs, dict):
        thumbs = thumbs.get("thumbnails") or [thumbs]
    if isinstance(thumbs, str):
        return thumbs
    best_url = ""
    best_area = -1
    for thumb in list(thumbs or []):
        if not isinstance(thumb, dict):
            continue
        url = str(thumb.get("url") or "").strip()
        area = int(thumb.get("width") or 0) * int(thumb.get("height") or 0)
        if url and area >= best_area:
            best_area = area
            best_url = url
    return best_url


def _home_collection_query(item):
    playlist_id = str(item.get("playlistId") or "").strip()
    browse_id = str(item.get("browseId") or "").strip()
    result_type = str(item.get("resultType") or "").lower()
    if playlist_id:
        return f"ytm:playlist:{playlist_id}"
    if browse_id and result_type == "album":
        return f"ytm:album:{browse_id}"
    return ""


def _home_collection_subtitle(app, item):
    for key in ("subtitle", "strapline", "description", "author"):
        text = _home_text(item.get(key))
        if text:
            return text
    artists = item.get("artists") or []
    if isinstance(artists, list):
        names = []
        for artist in artists:
            name = _home_text(artist.get("name") if isinstance(artist, dict) else artist)
            if name:
                names.append(name)
        if names:
            return " • ".join(names[:2])
    artist = _home_text(item.get("artist"))
    if artist:
        return artist
    return _H._clean_section_title(item.get("section_title") or "")


def _normalize_home_collection_item(app, item, section_title=""):
    if not isinstance(item, dict):
        return None
    title = _home_text(item.get("title"))
    query = _home_collection_query(item)
    if not title or not query:
        return None
    subtitle = _home_collection_subtitle(app, item)
    art_url = _home_collection_thumb(item)
    count = _home_text(item.get("count") or item.get("videoCount") or item.get("songCount"))
    result_type = str(item.get("resultType") or "").lower()
    return {
        "title": title,
        "subtitle": subtitle,
        "query": query,
        "art_url": art_url,
        "count": count,
        "result_type": result_type,
        "section_title": _H._clean_section_title(section_title or ""),
    }


def _ytm_playlist_home_sections(app, limit=4, items_per_section=6):
    cache_key = f"__ytm_playlist_home_sections::{limit}::{items_per_section}"
    cached = _cache_get(app, cache_key, ttl=900)
    if cached is not None:
        return list(cached)

    rows = app._yt_get_home(limit=max(limit * 4, 12))
    sections = []
    seen_titles = set()
    for row in list(rows or []):
        if not isinstance(row, dict):
            continue
        raw_title = _home_text(row.get("title") or row.get("header"))
        if not raw_title or app._ytm_title_is_blocked(raw_title):
            continue
        title = app._ytm_localize_label(raw_title)
        norm_title = app._normalize_feed_text(title)
        if not norm_title or norm_title in seen_titles:
            continue

        items = []
        seen_queries = set()
        contents = row.get("contents") or row.get("items") or row.get("results") or []
        for item in list(contents or [])[: max(items_per_section * 3, 12)]:
            normalized = _normalize_home_collection_item(app, item, section_title=title)
            if not normalized:
                continue
            query = normalized.get("query") or ""
            if not query or query in seen_queries:
                continue
            seen_queries.add(query)
            items.append(normalized)
            if len(items) >= items_per_section:
                break

        if len(items) < 3:
            continue

        sections.append(
            (
                title,
                items,
                app._tr("home.youtube_music.shelf_live", title=title),
            )
        )
        seen_titles.add(norm_title)
        if len(sections) >= limit:
            break

    _cache_set(app, cache_key, sections)
    return list(sections)


def _home_count_badge(app, count_text):
    text = str(count_text or "").strip()
    if not text:
        return ""
    if text.isdigit():
        return app._tr("home.track_count", count=text)
    lowered = text.lower()
    if "şarkı" in lowered or "parça" in lowered:
        return text
    return text


class _CoverPixmapSink(QObject):
    def __init__(self, owner, index: int):
        super().__init__(owner)
        self._owner = owner
        self._index = int(index)

    def setPixmap(self, px):
        if self._owner is None or not qt_is_valid(self._owner):
            return
        self._owner.setTilePixmap(self._index, px)


class _HomeCoverWidget(QWidget):
    def __init__(self, width: int, height: int, accent: str, parent=None):
        super().__init__(parent)
        self._accent = str(accent or _H.get_accent() or "#6EA8FF")
        self._px = None
        self._tile_pixmaps = {}
        self._tile_targets = {}
        self.setFixedSize(width, height)
        self.setAttribute(Qt.WA_StyledBackground, False)
        self.setStyleSheet("background:transparent; border:none;")

    def setPixmap(self, px):
        self._px = px if isinstance(px, QPixmap) else None
        self.update()

    def setTilePixmap(self, index: int, px):
        if isinstance(px, QPixmap) and not px.isNull():
            self._tile_pixmaps[int(index)] = px
        else:
            self._tile_pixmaps.pop(int(index), None)
        self.update()

    def tileTarget(self, index: int):
        sink = self._tile_targets.get(int(index))
        if sink is None or not qt_is_valid(sink):
            sink = _CoverPixmapSink(self, int(index))
            self._tile_targets[int(index)] = sink
        return sink

    def _draw_pixmap_rect(self, painter, target, pixmap, radius):
        if pixmap is None or pixmap.isNull():
            return
        path = QPainterPath()
        path.addRoundedRect(QRectF(target), radius, radius)
        painter.save()
        painter.setClipPath(path)
        scaled = pixmap.scaled(target.size().toSize(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        ox = max(0, (scaled.width() - int(target.width())) // 2)
        oy = max(0, (scaled.height() - int(target.height())) // 2)
        painter.drawPixmap(
            int(target.left()),
            int(target.top()),
            scaled,
            ox,
            oy,
            int(target.width()),
            int(target.height()),
        )
        painter.restore()
        outline_pen = QPen(QColor(255, 255, 255, 24))
        outline_pen.setWidthF(1.0)
        painter.setPen(outline_pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(QRectF(target), radius, radius)

    def _draw_collage(self, painter, rect):
        pixmaps = [self._tile_pixmaps[idx] for idx in sorted(self._tile_pixmaps) if isinstance(self._tile_pixmaps[idx], QPixmap)]
        if not pixmaps:
            return False
        if len(pixmaps) == 1:
            self._draw_pixmap_rect(painter, QRectF(rect), pixmaps[0], 18)
            return True

        gap = 6
        radius = 16
        rect_f = QRectF(rect)
        if len(pixmaps) == 2:
            half_w = (rect_f.width() - gap) / 2.0
            slots = [
                QRectF(rect_f.left(), rect_f.top(), half_w, rect_f.height()),
                QRectF(rect_f.left() + half_w + gap, rect_f.top(), half_w, rect_f.height()),
            ]
        elif len(pixmaps) == 3:
            lead_w = (rect_f.width() * 0.56) - (gap * 0.5)
            side_w = rect_f.width() - lead_w - gap
            half_h = (rect_f.height() - gap) / 2.0
            slots = [
                QRectF(rect_f.left(), rect_f.top(), lead_w, rect_f.height()),
                QRectF(rect_f.left() + lead_w + gap, rect_f.top(), side_w, half_h),
                QRectF(rect_f.left() + lead_w + gap, rect_f.top() + half_h + gap, side_w, half_h),
            ]
        else:
            cell_w = (rect_f.width() - gap) / 2.0
            cell_h = (rect_f.height() - gap) / 2.0
            slots = [
                QRectF(rect_f.left(), rect_f.top(), cell_w, cell_h),
                QRectF(rect_f.left() + cell_w + gap, rect_f.top(), cell_w, cell_h),
                QRectF(rect_f.left(), rect_f.top() + cell_h + gap, cell_w, cell_h),
                QRectF(rect_f.left() + cell_w + gap, rect_f.top() + cell_h + gap, cell_w, cell_h),
            ]
        for slot, pixmap in zip(slots, pixmaps[: len(slots)]):
            self._draw_pixmap_rect(painter, slot, pixmap, radius)
        return True

    def paintEvent(self, event):
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.Antialiasing)
            p.setRenderHint(QPainter.SmoothPixmapTransform)

            rect = self.rect().adjusted(2, 2, -2, -2)
            radius = 22
            shell = QPainterPath()
            shell.addRoundedRect(rect, radius, radius)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(10, 15, 24, 220))
            p.drawPath(shell)

            clip = QPainterPath()
            clip.addRoundedRect(rect, radius, radius)
            p.setClipPath(clip)

            drew_image = self._draw_collage(p, rect)
            if not drew_image and self._px and not self._px.isNull():
                scaled = self._px.scaled(rect.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                ox = (scaled.width() - rect.width()) // 2
                oy = (scaled.height() - rect.height()) // 2
                p.drawPixmap(rect.left(), rect.top(), scaled, ox, oy, rect.width(), rect.height())
                drew_image = True

            if drew_image:
                grad_lr = QLinearGradient(rect.left(), 0, rect.right(), 0)
                grad_lr.setColorAt(0.0, QColor(7, 11, 18, 118))
                grad_lr.setColorAt(0.22, QColor(7, 11, 18, 18))
                grad_lr.setColorAt(0.78, QColor(7, 11, 18, 18))
                grad_lr.setColorAt(1.0, QColor(7, 11, 18, 132))
                p.fillRect(rect, QBrush(grad_lr))

                grad_bt = QLinearGradient(0, rect.top(), 0, rect.bottom())
                grad_bt.setColorAt(0.0, QColor(7, 11, 18, 12))
                grad_bt.setColorAt(0.58, QColor(7, 11, 18, 0))
                grad_bt.setColorAt(1.0, QColor(7, 11, 18, 178))
                p.fillRect(rect, QBrush(grad_bt))
            else:
                base = QLinearGradient(rect.left(), rect.top(), rect.right(), rect.bottom())
                base.setColorAt(0.0, QColor(28, 34, 46, 255))
                base.setColorAt(1.0, QColor(17, 22, 31, 255))
                p.fillRect(rect, QBrush(base))

            p.setClipping(False)
            outer_pen = QPen(QColor(255, 255, 255, 18))
            outer_pen.setWidthF(1.0)
            p.setPen(outer_pen)
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(rect, radius, radius)

            inner_pen = QPen(QColor(255, 255, 255, 10))
            inner_pen.setWidthF(1.0)
            p.setPen(inner_pen)
            p.drawRoundedRect(rect.adjusted(0, 0, 0, 0), radius, radius)
        finally:
            p.end()


def _render_curated_playlist_grid(app, items):
    refs = getattr(app, "_home_refs", {})
    layout = refs.get("playlist_grid")
    if layout is None:
        return
    _clear(layout)
    cards = list(items or [])
    metrics = _curated_grid_metrics(app)
    refs["playlist_grid_items"] = cards
    refs["playlist_grid_metrics"] = metrics["signature"]
    layout.setHorizontalSpacing(metrics["spacing"])
    layout.setVerticalSpacing(metrics["spacing"])
    columns = metrics["columns"]
    for idx, item in enumerate(cards):
        row = idx // columns
        col = idx % columns
        layout.addWidget(_make_curated_collection_card(app, item, mode="grid", metrics=metrics), row, col)
    for col in range(5):
        layout.setColumnStretch(col, 1 if col < columns else 0)
    for row in range(max(1, (len(cards) + columns - 1) // columns)):
        layout.setRowStretch(row, 0)


def _set_curated_grid_loading(app):
    refs = getattr(app, "_home_refs", {})
    if not refs:
        return
    _set_curated_host_min_width(app, _HOME_CURATED_HOST_MIN_WIDTH)

    cards = list(_curated_home_cards(app) or [])
    if cards:
        try:
            _render_curated_playlist_grid(app, cards)
            _load_curated_playlist_previews_async(app, cards)
            grid_box = refs.get("playlist_grid_box")
            if grid_box is not None:
                grid_box.show()
            hero_frame = refs.get("hero_frame")
            if hero_frame is not None:
                hero_frame.hide()
            rail = refs.get("rail")
            if rail is not None:
                rail.hide()
            live = refs.get("live")
            if live is not None:
                live.hide()
                try:
                    _clear(live.layout())
                except Exception as _e:
                    log.debug("Sessiz hata: %s", _e)
            grid_title = refs.get("playlist_grid_title")
            if grid_title is not None:
                grid_title.setText(app._tr("home.youtube_music.title"))
            grid_desc = refs.get("playlist_grid_desc")
            if grid_desc is not None:
                grid_desc.setText(app._tr("home.youtube_music.ready_desc"))
            grid_refresh = refs.get("playlist_grid_refresh")
            if grid_refresh is not None:
                _rebind(grid_refresh, getattr(app, "_home_reload_current", app._refresh_home_feed))
            return
        except Exception as _e:
            log.debug("Hafif curated grid hatası: %s", _e)

    grid_box = refs.get("playlist_grid_box")
    if grid_box is not None:
        grid_box.show()
    hero_frame = refs.get("hero_frame")
    if hero_frame is not None:
        hero_frame.hide()
    rail = refs.get("rail")
    if rail is not None:
        rail.hide()
    live = refs.get("live")
    if live is not None:
        live.hide()
        try:
            _clear(live.layout())
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)

    grid_title = refs.get("playlist_grid_title")
    if grid_title is not None:
        grid_title.setText(app._tr("home.youtube_music.title"))
    grid_desc = refs.get("playlist_grid_desc")
    if grid_desc is not None:
        grid_desc.setText(app._tr("home.youtube_music.loading_desc"))
    grid_refresh = refs.get("playlist_grid_refresh")
    if grid_refresh is not None:
        _rebind(grid_refresh, getattr(app, "_home_reload_current", app._refresh_home_feed))

    layout = refs.get("playlist_grid")
    if layout is None:
        return
    _clear(layout)
    skel_count = len(_region_curated_home_playlists(app))
    metrics = _curated_grid_metrics(app)
    columns = metrics["columns"]
    for idx in range(skel_count):
        row = idx // columns
        col = idx % columns
        layout.addWidget(
            SkeletonWidget(
                width=metrics["card_width"],
                height=metrics["card_height"],
                radius=metrics["card_radius"],
            ),
            row,
            col,
        )


def _make_curated_collection_card(app, item, mode="spotlight", metrics=None):
    mode = str(mode or "spotlight").lower()
    theme = _home_playlist_theme(item)
    accent = theme.get("accent") or _H.get_accent() or "#6EA8FF"
    accent_soft = theme.get("accent_soft") or accent
    surface = theme.get("surface") or _H.BG_CARD
    surface_alt = theme.get("surface_alt") or _H.BG_ELEVATED
    variant = str(theme.get("style") or "poster").lower()
    badge_text = str(theme.get("badge") or app._tr("home.curated.badge"))

    title_text = str(item.get("title") or app._tr("home.playlist"))
    subtitle_text = str(item.get("subtitle") or "")
    count_badge = _home_count_badge(app, item.get("count"))
    art_url = str(item.get("art_url") or "").strip()
    cover_urls = [str(url or "").strip() for url in list(item.get("cover_urls") or []) if str(url or "").strip()]
    section_text = str(item.get("section_title") or app._tr("home.playlist"))

    if mode == "grid":
        metrics = metrics or _curated_grid_metrics(app)
        card_w = metrics["card_width"]
        card_h = metrics["card_height"]
        art_w = metrics["art_width"]
        art_h = metrics["art_height"]
        card_radius = metrics["card_radius"]
        card_padding = metrics["card_padding"]
        title_px = metrics["title_px"]
        subtitle_px = metrics["subtitle_px"]
        meta_px = metrics["meta_px"]
        badge_px = metrics["badge_px"]
        play_size = metrics["play_size"]
        obj_name = f"CuratedHomeCardGrid{theme.get('slug', 'Default').title().replace('-', '')}"
        card = _H.AnimatedCard()
        card.setObjectName(obj_name)
        card.setFixedSize(card_w, card_h)
        card.setStyleSheet(
            f"""
            QFrame#{obj_name} {{
                background:qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 {surface_alt},
                    stop:0.55 {surface},
                    stop:1 {_H.BG_BLACK});
                border:1px solid {_H.BORDER_COLOR};
                border-radius:{card_radius}px;
            }}
            QFrame#{obj_name}:hover {{
                background:qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 {_H.BG_CARD_HOVER},
                    stop:0.55 {surface},
                    stop:1 {_H.BG_BLACK});
                border:1px solid {_home_rgba(accent_soft, 58)};
            }}
            """
        )
        try:
            app._add_soft_shadow(card, 14, QColor(0, 0, 0, 80), 0, 5)
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)

        lay = QVBoxLayout(card)
        lay.setContentsMargins(card_padding, card_padding, card_padding, card_padding)
        lay.setSpacing(8)

        # Art widget — badge pill'i üzerine overlay olarak konumlandırıyoruz
        art = _HomeCoverWidget(art_w, art_h, accent_soft, card)
        if cover_urls:
            _apply_home_image(app, art, cover_urls[0], (art_w, art_h))
        elif art_url:
            _apply_home_image(app, art, art_url, (art_w, art_h))
        lay.addWidget(art)

        # Badge pill: art widget'ının sol üst köşesine overlay
        accent_tag = QLabel(badge_text, art)
        accent_tag.setStyleSheet(
            f"color:#fff; font-size:{badge_px}px; font-weight:900;"
            f" font-family:'Segoe UI Variable Display','Segoe UI Black','Segoe UI';"
            f" background:#0d1f35; border:1px solid #1e3d5c;"
            f" border-radius:11px; padding:4px 10px;"
        )
        accent_tag.adjustSize()
        accent_tag.move(12, 12)
        accent_tag.raise_()

        title = QLabel(title_text)
        title.setWordWrap(True)
        title.setMinimumHeight(20)
        title.setMaximumHeight(44 if card_w < 240 else 48)
        title.setStyleSheet(f"color:{_H.TEXT_PRIMARY}; font-size:{title_px}px; font-weight:900; font-family:'Segoe UI Variable Display','Segoe UI Black','Segoe UI'; background:transparent;")

        sub = QLabel(subtitle_text or section_text)
        sub.setWordWrap(True)
        sub.setMinimumHeight(16)
        sub.setMaximumHeight(34)
        sub.setStyleSheet(f"color:{_H.TEXT_SECONDARY}; font-size:{subtitle_px}px; font-weight:600; font-family:'Segoe UI Variable Display','Segoe UI'; background:transparent;")

        meta_row = QHBoxLayout()
        meta_row.setContentsMargins(0, 0, 0, 0)
        meta_row.setSpacing(8)
        section_lbl = QLabel(section_text)
        section_lbl.setStyleSheet(f"color:{_H.TEXT_MUTED}; font-size:{meta_px}px; font-weight:800; font-family:'Segoe UI Variable Display','Segoe UI'; letter-spacing:0.5px; background:transparent;")
        meta_row.addWidget(section_lbl, 1)
        if count_badge:
            count_lbl = QLabel(count_badge)
            count_lbl.setStyleSheet(
                f"color:{_H.TEXT_PRIMARY}; font-size:{meta_px}px; font-weight:900;"
                f" background:{_home_rgba(accent, 14)}; border:1px solid {_home_rgba(accent_soft, 36)};"
                f" border-radius:10px; padding:3px 8px;"
            )
            meta_row.addWidget(count_lbl, 0, Qt.AlignRight)

        lay.addWidget(title)
        lay.addWidget(sub)
        lay.addLayout(meta_row)
        lay.addStretch()

        # ── Play butonu: art widget'ının sağ alt köşesinde overlay ──────────
        _query = item.get("query") or ""
        _title = item.get("title") or "Liste"

        play_btn = QPushButton("▶", art)
        play_btn.setFixedSize(play_size, play_size)
        play_btn.setCursor(Qt.PointingHandCursor)
        play_btn.setStyleSheet(
            f"QPushButton{{"
            f"  background:{accent}; color:#fff; font-size:14px; font-weight:900;"
            f"  border:none; border-radius:{play_size // 2}px;"
            f"}}"
            f"QPushButton:hover{{"
            f"  background:{accent_soft};"
            f"}}"
            f"QPushButton:pressed{{"
            f"  background:{_home_rgba(accent, 200)};"
            f"}}"
        )
        # Sanat alanının sağ-altına yerleştir (14px iç boşluk)
        inset = 12
        play_btn.move(art.width() - play_size - inset, art.height() - play_size - inset)
        play_btn.raise_()

        def _play_list(q=_query):
            if not q:
                return
            import threading as _threading
            def _bg():
                try:
                    tracks = app._fetch_feed_results(q, limit=80)
                    if tracks:
                        app.sig.play_all_tracks.emit(list(tracks))
                except Exception as _e:
                    log.debug("Sessiz hata: %s", _e)
            _threading.Thread(target=_bg, daemon=True, name="iqt-play-list").start()

        play_btn.clicked.connect(lambda: _play_list())

        # ── Sağ tık bağlam menüsü ────────────────────────────────────────────
        card.setContextMenuPolicy(Qt.CustomContextMenu)

        def _ctx_menu(pos, q=_query, t=_title):
            menu = QMenu(card)
            menu.setStyleSheet(
                f"QMenu{{background:#1a1f2e; border:1px solid {_home_rgba(accent, 60)};"
                f" border-radius:10px; padding:4px;}}"
                f"QMenu::item{{color:#e0e0e0; padding:8px 16px; font-size:13px; border-radius:6px;}}"
                f"QMenu::item:selected{{background:{_home_rgba(accent, 40)}; color:#fff;}}"
            )
            act_play = menu.addAction(f"▶  {app._tr('home.hero.play')}")
            act_open = menu.addAction(f"↗  {app._tr('home.hero.open')}")
            chosen = menu.exec(QCursor.pos())
            if chosen == act_play:
                _play_list(q)
            elif chosen == act_open:
                app.page_category(t, q, "songs")

        card.customContextMenuRequested.connect(_ctx_menu)

        card.clicked.connect(
            lambda q=_query, t=_title: app.page_category(t, q, "songs")
        )
        return card

    if mode == "mini":
        card_w, card_h = 332, 102
        art_w, art_h = 112, 74
    else:
        card_w, card_h = 336, 286
        art_w, art_h = 302, 188

    obj_name = f"CuratedHomeCard{mode.title()}{theme.get('slug', 'Default').title().replace('-', '')}"
    card = _H.AnimatedCard()
    card.setObjectName(obj_name)
    card.setFixedSize(card_w, card_h)
    card.setStyleSheet(
        f"""
        QFrame#{obj_name} {{
            background:qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 {_home_rgba(accent, 28)},
                stop:0.2 {_home_rgba(accent_soft, 18)},
                stop:0.62 {surface},
                stop:1 {surface_alt});
            border:1px solid {_home_rgba(accent, 88)};
            border-radius:{24 if mode != 'mini' else 22}px;
        }}
        QFrame#{obj_name}:hover {{
            background:qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 {_home_rgba(accent, 42)},
                stop:0.2 {_home_rgba(accent_soft, 24)},
                stop:0.62 {_H.BG_CARD_HOVER},
                stop:1 {surface_alt});
            border:1px solid {_home_rgba(accent_soft, 128)};
        }}
        """
    )

    if mode == "mini":
        lay = QHBoxLayout(card)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(12)

        stripe = QFrame()
        stripe.setFixedWidth(5)
        stripe.setStyleSheet(
            f"background:qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 {accent}, stop:1 {accent_soft}); border:none; border-radius:2px;"
        )
        lay.addWidget(stripe)

        art = QLabel()
        art.setFixedSize(art_w, art_h)
        art.setAlignment(Qt.AlignCenter)
        art.setStyleSheet(
            f"background:{_home_rgba(accent, 18)}; border:none; border-radius:18px;"
        )
        if art_url:
            app._load_image(art_url, art, (art_w, art_h))
        lay.addWidget(art)

        text_l = QVBoxLayout()
        text_l.setSpacing(4)
        badge = QLabel(badge_text)
        badge.setStyleSheet(
            f"color:#fff; font-size:10px; font-weight:900; font-family:'Segoe UI Variable Display','Segoe UI Black','Segoe UI'; background:#0d1f35; border:1px solid #1e3d5c; border-radius:11px; padding:3px 8px;"
        )
        title = QLabel(title_text)
        title.setWordWrap(True)
        title.setFixedHeight(34)
        title.setStyleSheet(f"color:{_H.TEXT_PRIMARY}; font-size:15px; font-weight:900; font-family:'Segoe UI Variable Display','Segoe UI Black','Segoe UI'; background:transparent;")
        sub = QLabel(subtitle_text or section_text)
        sub.setWordWrap(True)
        sub.setFixedHeight(30)
        sub.setStyleSheet(f"color:{_H.TEXT_SECONDARY}; font-size:11px; font-weight:700; font-family:'Segoe UI Variable Display','Segoe UI'; background:transparent;")
        text_l.addWidget(badge, 0, Qt.AlignLeft)
        text_l.addWidget(title)
        text_l.addWidget(sub)
        if count_badge:
            count_lbl = QLabel(count_badge)
            count_lbl.setStyleSheet(f"color:{_H.TEXT_MUTED}; font-size:10px; font-weight:800; background:transparent;")
            text_l.addWidget(count_lbl)
        lay.addLayout(text_l, 1)
    else:
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        if variant == "split":
            hero_row = QHBoxLayout()
            hero_row.setSpacing(12)
            meta_l = QVBoxLayout()
            meta_l.setSpacing(8)
            kicker = QLabel(badge_text)
            kicker.setStyleSheet(
                f"color:#fff; font-size:11px; font-weight:900; font-family:'Segoe UI Variable Display','Segoe UI Black','Segoe UI'; background:#0d1f35; border:1px solid #1e3d5c; border-radius:12px; padding:4px 10px;"
            )
            title = QLabel(title_text)
            title.setWordWrap(True)
            title.setFixedHeight(74)
            title.setStyleSheet(f"color:{_H.TEXT_PRIMARY}; font-size:20px; font-weight:900; font-family:'Segoe UI Variable Display','Segoe UI Black','Segoe UI'; background:transparent;")
            sub = QLabel(subtitle_text or section_text)
            sub.setWordWrap(True)
            sub.setFixedHeight(60)
            sub.setStyleSheet(f"color:{_H.TEXT_SECONDARY}; font-size:12px; font-weight:700; font-family:'Segoe UI Variable Display','Segoe UI'; background:transparent;")
            meta_l.addWidget(kicker, 0, Qt.AlignLeft)
            meta_l.addWidget(title)
            meta_l.addWidget(sub)
            if count_badge:
                count_lbl = QLabel(count_badge)
                count_lbl.setStyleSheet(f"color:{_H.TEXT_MUTED}; font-size:11px; font-weight:800; background:transparent;")
                meta_l.addWidget(count_lbl)
            meta_l.addStretch()
            hero_row.addLayout(meta_l, 1)

            art = QLabel()
            art.setFixedSize(154, 188)
            art.setAlignment(Qt.AlignCenter)
            art.setStyleSheet(
                f"background:{_home_rgba(accent, 18)}; border:1px solid {_home_rgba(accent_soft, 72)}; border-radius:22px;"
            )
            if art_url:
                app._load_image(art_url, art, (154, 188))
            hero_row.addWidget(art, 0, Qt.AlignRight)
            lay.addLayout(hero_row)
        else:
            art = QLabel()
            art.setFixedSize(art_w, art_h)
            art.setAlignment(Qt.AlignCenter)
            art.setStyleSheet(
                f"background:{_home_rgba(accent, 18)}; border:1px solid {_home_rgba(accent_soft, 72)}; border-radius:24px;"
            )
            if art_url:
                app._load_image(art_url, art, (art_w, art_h))
            lay.addWidget(art, 0, Qt.AlignHCenter)

            if variant == "band":
                band = QLabel(badge_text)
                band.setAlignment(Qt.AlignCenter)
                band.setStyleSheet(
                    f"color:{_H.BG_BLACK}; font-size:10px; font-weight:900; background:qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {accent_soft}, stop:1 {accent}); border:none; border-radius:10px; padding:4px 10px;"
                )
                lay.addWidget(band, 0, Qt.AlignLeft)
            else:
                kicker = QLabel(badge_text)
                kicker.setStyleSheet(
                    f"color:#fff; font-size:11px; font-weight:900; font-family:'Segoe UI Variable Display','Segoe UI Black','Segoe UI'; background:#0d1f35; border:1px solid #1e3d5c; border-radius:12px; padding:4px 10px;"
                )
                lay.addWidget(kicker, 0, Qt.AlignLeft)

            title = QLabel(title_text)
            title.setWordWrap(True)
            title.setFixedHeight(58)
            title.setStyleSheet(f"color:{_H.TEXT_PRIMARY}; font-size:18px; font-weight:900; font-family:'Segoe UI Variable Display','Segoe UI Black','Segoe UI'; background:transparent;")
            sub = QLabel(subtitle_text or section_text)
            sub.setWordWrap(True)
            sub.setFixedHeight(38)
            sub.setStyleSheet(f"color:{_H.TEXT_SECONDARY}; font-size:12px; font-weight:700; font-family:'Segoe UI Variable Display','Segoe UI'; background:transparent;")
            lay.addWidget(title)
            lay.addWidget(sub)
            if count_badge:
                count_lbl = QLabel(count_badge)
                count_lbl.setStyleSheet(f"color:{_H.TEXT_MUTED}; font-size:11px; font-weight:800; background:transparent;")
                lay.addWidget(count_lbl)
            lay.addStretch()

    card.clicked.connect(
        lambda q=item.get("query") or "", t=item.get("title") or "Liste": app.page_category(t, q, "songs")
    )
    return card


def _make_collection_card(app, item, mode="shelf"):
    mode = str(mode or "shelf").lower()
    if isinstance(item, dict) and item.get("slug") and mode in {"spotlight", "mini", "shelf"}:
        return _make_curated_collection_card(app, item, mode=("spotlight" if mode == "shelf" else mode))
    if mode == "mini":
        card_w, card_h = 220, 74
        art_w, art_h = 54, 54
    elif mode == "spotlight":
        card_w, card_h = 276, 214
        art_w, art_h = 244, 122
    else:
        card_w, card_h = 306, 262
        art_w, art_h = 274, 172

    obj_name = f"HomeCollectionCard{mode.title()}"
    card = _H.AnimatedCard()
    card.setObjectName(obj_name)
    card.setFixedSize(card_w, card_h)
    card.setStyleSheet(
        f"""
        QFrame#{obj_name} {{
            background:qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 rgba(255,255,255,0.02), stop:0.15 {_H.get_accent()}10,
                stop:0.7 {_H.BG_CARD}, stop:1 {_H.BG_ELEVATED});
            border:1px solid {_H.BORDER_COLOR};
            border-radius:{22 if mode != 'mini' else 18}px;
        }}
        QFrame#{obj_name}:hover {{
            border:1px solid {_H.get_accent()}55;
            background:qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 {_H.get_accent()}14, stop:0.58 {_H.BG_CARD_HOVER}, stop:1 {_H.BG_ELEVATED});
        }}
        """
    )

    art_url = str(item.get("art_url") or "").strip()
    title_text = str(item.get("title") or "Liste")
    subtitle_text = str(item.get("subtitle") or "")
    count_text = str(item.get("count") or "")
    section_text = str(item.get("section_title") or "")

    if mode == "mini":
        lay = QHBoxLayout(card)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(10)
        art = QLabel()
        art.setFixedSize(art_w, art_h)
        art.setAlignment(Qt.AlignCenter)
        art.setStyleSheet(f"background:{_H.BG_BLACK}; border:none; border-radius:12px;")
        if art_url:
            app._load_image(art_url, art, (art_w, art_h))
        lay.addWidget(art)
        text_l = QVBoxLayout()
        text_l.setSpacing(3)
        title = QLabel(title_text)
        title.setWordWrap(True)
        title.setStyleSheet(f"color:{_H.TEXT_PRIMARY}; font-size:13px; font-weight:850; background:transparent;")
        sub = QLabel(subtitle_text)
        sub.setWordWrap(True)
        sub.setStyleSheet(f"color:{_H.TEXT_SECONDARY}; font-size:11px; font-weight:700; background:transparent;")
        text_l.addWidget(title)
        text_l.addWidget(sub)
        text_l.addStretch()
        lay.addLayout(text_l, 1)
    else:
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)
        art = QLabel()
        art.setFixedSize(art_w, art_h)
        art.setAlignment(Qt.AlignCenter)
        art.setStyleSheet(f"background:{_H.BG_BLACK}; border:none; border-radius:18px;")
        if art_url:
            app._load_image(art_url, art, (art_w, art_h))
        lay.addWidget(art, 0, Qt.AlignHCenter)
        kicker = QLabel(section_text or app._tr("home.playlist"))
        kicker.setStyleSheet(
            f"color:{_H.get_accent()}; font-size:11px; font-weight:900; letter-spacing:1px; background:transparent;"
        )
        title = QLabel(title_text)
        title.setWordWrap(True)
        title.setFixedHeight(60 if mode == "shelf" else 52)
        title.setStyleSheet(f"color:{_H.TEXT_PRIMARY}; font-size:{17 if mode == 'shelf' else 15}px; font-weight:900; background:transparent;")
        sub = QLabel(subtitle_text)
        sub.setWordWrap(True)
        sub.setFixedHeight(34)
        sub.setStyleSheet(f"color:{_H.TEXT_SECONDARY}; font-size:12px; font-weight:700; background:transparent;")
        lay.addWidget(kicker)
        lay.addWidget(title)
        lay.addWidget(sub)
        if count_text:
            count_lbl = QLabel(count_text)
            count_lbl.setStyleSheet(f"color:{_H.TEXT_MUTED}; font-size:11px; font-weight:700; background:transparent;")
            lay.addWidget(count_lbl)
        lay.addStretch()

    card.clicked.connect(
        lambda q=item.get("query") or "", t=item.get("title") or "Liste": app.page_category(t, q, "songs")
    )
    return card


def _render_collection_strip(app, parent_layout, items, mode="shelf", limit=6):
    hs = QScrollArea()
    hs.setFixedHeight(286 if str(mode or "").lower() == "shelf" else 232)
    hs.setWidgetResizable(False)
    hs.setStyleSheet("background:transparent; border:none;")
    hs.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    hs.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    host = QWidget()
    host.setObjectName("TC")
    row = QHBoxLayout(host)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(16)
    for item in list(items or [])[: max(1, int(limit or 6))]:
        row.addWidget(_make_collection_card(app, item, mode=mode))
    row.addStretch()
    host.adjustSize()
    hs.setWidget(host)
    parent_layout.addWidget(hs)


def _render_spotlights(app, entries):
    layout = app._home_refs["spotlights"]
    _clear(layout)
    for entry in list(entries or [])[:4]:
        layout.addWidget(_make_collection_card(app, entry, mode="spotlight"))
    layout.addStretch()
    try:
        w = layout.parentWidget()
        if w is not None:
            w.adjustSize()
    except Exception:
        pass


def _render_hero_support(app, items):
    layout = getattr(app, "_home_refs", {}).get("support")
    if layout is None:
        return
    _clear(layout)
    for item in list(items or [])[:3]:
        if isinstance(item, dict) and item.get("query"):
            layout.addWidget(_make_collection_card(app, item, mode="mini"))
        else:
            layout.addWidget(_make_editorial_track_card(app, item, mode="mini"))
    layout.addStretch()


def _obsolete_final_spotlight_entries(app, limit=4):
    sections = _ytm_playlist_home_sections(app, limit=3, items_per_section=6)
    entries = []
    seen = set()
    for section_title, items, _desc in sections:
        for item in list(items or []):
            query = str(item.get("query") or "").strip()
            if not query or query in seen:
                continue
            seen.add(query)
            entry = dict(item)
            entry["section_title"] = section_title
            entries.append(entry)
            if len(entries) >= limit:
                return entries
    return entries


def _obsolete_final_hero(app, sections):
    cached = _cache_get(app, f"__home_bundle::hero::{_region_cache_suffix(app)}")
    if cached:
        return dict(cached)

    if sections and sections[0][1]:
        source_title, items, desc = sections[0]
        if items and isinstance(items[0], dict) and items[0].get("query"):
            lead = dict(items[0])
            preview_tracks = list(app._fetch_feed_results(lead.get("query") or "", limit=4) or [])
            hero = {
                "item": lead,
                "tracks": preview_tracks,
                "source": source_title,
                "query": lead.get("query") or "feed:new.music",
                "desc": desc or app._tr("home.youtube_music.shelf_selected", title=source_title),
                "support": list(items[1:4]),
            }
            _cache_set(app, f"__home_bundle::hero::{_region_cache_suffix(app)}", hero)
            return hero
        if items:
            hero = {
                "track": items[0],
                "tracks": list(items[:4]),
                "source": source_title,
                "query": _guess_query(source_title),
                "desc": desc or app._tr("home.live_picked"),
                "support": list(items[1:4]),
            }
            _cache_set(app, f"__home_bundle::hero::{_region_cache_suffix(app)}", hero)
            return hero

    return {
        "item": {},
        "tracks": [],
        "source": app._tr("home.youtube_music.source"),
        "query": "feed:new.music",
        "desc": app._tr("home.youtube_music.loading_desc"),
        "support": [],
    }


def _obsolete_final_bundle(app):
    playlist_sections = _ytm_playlist_home_sections(app, limit=4, items_per_section=6)
    if playlist_sections:
        return {
            "buttons": _buttons(app),
            "hero": _hero(app, playlist_sections),
            "sections": list(playlist_sections[:3]),
            "spotlights": _spotlight_entries(app, limit=4),
            "playlist_mode": True,
        }

    sections = _live_sections(app, limit=2, per_section=8)
    return {
        "buttons": _buttons(app),
        "hero": _hero(app, sections),
        "sections": list(sections[:2]),
        "spotlights": _spotlight_entries(app, limit=4),
        "playlist_mode": False,
    }


def _obsolete_final_apply_bundle(app, bundle):
    refs = getattr(app, "_home_refs", {})
    if not refs:
        return

    if bundle.get("playlist_mode"):
        hero = bundle.get("hero") or {}
        item = hero.get("item") or {}
        preview_tracks = list(hero.get("tracks") or [])
        refs["source"].setText(_tr_upper(hero.get("source") or app._tr("home.youtube_music.source")))
        refs["title"].setText(str(item.get("title") or app._tr("home.youtube_music.source")))
        refs["artist"].setText(str(item.get("subtitle") or hero.get("source") or app._tr("home.youtube_music.live_rail")))
        refs["desc"].setText(str(hero.get("desc") or ""))

        art_url = str(item.get("art_url") or "").strip()
        refs["cover"].clear()
        if art_url:
            app._load_image(art_url, refs["cover"], (220, 220))
        elif preview_tracks:
            thumb = app._thumb(preview_tracks[0], big=True)
            if thumb:
                app._load_image(thumb, refs["cover"], (220, 220))

        lead_track = preview_tracks[0] if preview_tracks else None
        _rebind(refs["play"], lambda tr=lead_track, q=item.get("query") or "", t=item.get("title") or "Liste": app.force_play(tr) if tr else app.page_category(t, q, "songs"))
        _rebind(refs["open"], lambda q=item.get("query") or "", t=item.get("title") or "Liste": app.page_category(t, q, "songs"))
        _rebind(refs["refresh"], getattr(app, "_home_reload_current", app._refresh_home_feed))
        _render_buttons(app, bundle.get("buttons") or [])
        _render_spotlights(app, bundle.get("spotlights") or [])
        _render_hero_support(app, hero.get("support") or [])

        rail = refs.get("rail")
        if rail is not None:
            rail.setVisible(False)

        live = refs["live"]
        live.setVisible(bool(bundle.get("sections")))
        _clear(live.layout())
        if bundle.get("sections"):
            live.layout().addWidget(_header(app._tr("home.youtube_music.live")))
            for title, items, desc in list(bundle["sections"])[:3]:
                lbl = QLabel(str(title))
                lbl.setStyleSheet(f"color:{_H.TEXT_PRIMARY}; font-size:18px; font-weight:900; background:transparent;")
                sub = QLabel(str(desc or app._tr("home.youtube_music.live_desc")))
                sub.setStyleSheet(f"color:{_H.TEXT_MUTED}; font-size:12px; background:transparent;")
                live.layout().addWidget(lbl)
                live.layout().addWidget(sub)
                _render_collection_strip(app, live.layout(), items, mode="shelf", limit=6)
        return

    rail = refs.get("rail")
    if rail is not None:
        rail.setVisible(True)

    hero = bundle.get("hero") or {}
    tr = hero.get("track") or {}
    refs["source"].setText(_tr_upper(hero.get("source") or app._tr("home.hero.loading.source")))
    refs["title"].setText(str(tr.get("title") or app._tr("home.hero.ready")))
    refs["artist"].setText(str(app._artist_str(tr) or app._tr("home.hero.live_selection_single")))
    refs["desc"].setText(str(hero.get("desc") or ""))
    thumb = app._thumb(tr, big=True)
    refs["cover"].clear()
    if thumb:
        app._load_image(thumb, refs["cover"], (220, 220))
    _rebind(refs["play"], lambda: app.force_play(tr) if tr else None)
    _rebind(
        refs["open"],
        lambda q=hero.get("query") or "feed:new.music", s=hero.get("source") or app._tr("home.spotlight.default"):
        app.page_category(s, q, "songs"),
    )
    _rebind(refs["refresh"], getattr(app, "_home_reload_current", app._refresh_home_feed))
    _render_buttons(app, bundle.get("buttons") or [])
    _render_spotlights(app, bundle.get("spotlights") or [])
    _render_hero_support(app, hero.get("support") or [])

    live = refs["live"]
    live.setVisible(bool(bundle.get("sections")))
    _clear(live.layout())
    if bundle.get("sections"):
        live.layout().addWidget(_header(app._tr("home.live_streams")))
        for title, tracks, desc in list(bundle["sections"])[:2]:
            lbl = QLabel(str(title))
            lbl.setStyleSheet(f"color:{_H.TEXT_PRIMARY}; font-size:15px; font-weight:850; background:transparent;")
            sub = QLabel(str(desc or app._tr("home.live_curated_desc")))
            sub.setStyleSheet(f"color:{_H.TEXT_MUTED}; font-size:11px; background:transparent;")
            live.layout().addWidget(lbl)
            live.layout().addWidget(sub)
            _render_editorial_strip(app, live.layout(), tracks, mode="wide", limit=8)
