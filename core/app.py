"""Ana uygulama sınıfı — IqtMusic."""
import os
import sys
import time
import logging
import threading
import gettext
from collections import deque, OrderedDict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import requests
import vlc
from ytmusicapi import YTMusic
from yt_dlp import YoutubeDL

try:
    from pypresence import Presence
    DISCORD_AVAILABLE = True
except ImportError:
    DISCORD_AVAILABLE = False

try:
    from pynput import keyboard as pynput_keyboard
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False

try:
    import ctypes
    from ctypes import wintypes
except Exception:
    ctypes = None
    wintypes = None

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QSystemTrayIcon, QMenu, QLabel, QPushButton,
    QApplication, QGraphicsDropShadowEffect,
)
from PySide6.QtCore import Qt, QSize, QTimer, QPoint, QEvent
from PySide6.QtGui import (
    QIcon, QPixmap, QColor, QAction, QFont, QKeySequence, QCursor,
    QBitmap, QPainter, QPainterPath
)

import core.constants as _C
from core.constants import (
    THEMES, BG_BLACK, BG_CARD, BG_CARD_HOVER, BG_ELEVATED, BORDER_COLOR,
    TEXT_PRIMARY, TEXT_MUTED, FONT_MAIN, YDL_FORMAT, APP_VERSION
)
from core.theme import get_accent
from core.cache import DiskImageCache, LRUTTLCache, DiskMediaCache
from core.downloader import DownloadManager
from core.i18n import DEFAULT_LANGUAGE, normalize_language, translate
from core.lastfm import LastFMClient
from core.signals import Signals
from core.geo import detect_content_region, region_display_name
from utils.helpers import (
    get_app_dir, safe_load_json, safe_save_json, open_folder,
    create_icon, ICON_PATH, VLC_PLUGINS, VLC_DIR, qt_is_valid
)
from utils.telemetry import maybe_send_startup_telemetry, send_event
from ui.widgets import ClickableFrame, TrackCoverWidget
from ui.titlebar import TitleBar
from ui.styles import get_main_stylesheet
from ui.sidebar import build_sidebar
from ui.player_bar import build_player_bar
from ui.dialogs import (
    open_eq_dialog, open_lyrics_dialog, open_sleep_dialog, show_toast
)
from pages.common import _scrollable

log = logging.getLogger("iqtMusic")

# gettext güvenli sarmalayıcı
_orig_trans = gettext.translation
def _safe_trans(domain, localedir=None, languages=None, fallback=False):
    try:
        return _orig_trans(domain, localedir=localedir, languages=languages, fallback=True)
    except Exception:
        return gettext.NullTranslations()
gettext.translation = _safe_trans


from core.mixins import (
    PlayerMixin, QueueMixin, YtmusicMixin, FeedMixin, NavigationMixin,
    DiscordMixin, StatsMixin, PlaylistMixin, LyricsMixin, MiniPlayerMixin,
    ArtistMixin, ContextMenuMixin, UiConfigMixin, ResizeMixin, PersistenceMixin,
    CollabMixin
)


class IqtMusic(
    NavigationMixin,
    PlayerMixin,
    QueueMixin,
    YtmusicMixin,
    FeedMixin,
    DiscordMixin,
    StatsMixin,
    PlaylistMixin,
    LyricsMixin,
    MiniPlayerMixin,
    ArtistMixin,
    ContextMenuMixin,
    UiConfigMixin,
    ResizeMixin,
    PersistenceMixin,
    CollabMixin,
    QMainWindow
):

    def __init__(self, progress_cb=None):
        super().__init__()

        # ── İlerleme bildirimi yardımcısı ────────────────────────────────────
        # Splash screen'e her aşama bildirmek için.  progress_cb(value, msg)
        # formatında çağrılır; None geçilirse sessizce çalışır.
        def _prog(val: int, msg: str = ""):
            if progress_cb is not None:
                try:
                    progress_cb(val, msg)
                except Exception:
                    pass

        self._resize_active = False
        self._resize_start = QPoint()
        self._resize_geom = self.frameGeometry()
        self._resize_edges_s = (False, False, False, False)
        self._resize_cursor_owner = None
        self._resize_cursor_backup = None
        self._windowed_geometry = None
        self._maximized_active = False
        self._fullscreen_active = False

        # Enable a borderless window. The native title bar is hidden
        # when using Qt.FramelessWindowHint. A custom title bar is
        # provided via ui.titlebar.TitleBar.
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self._window_corner_radius = 12
        # Custom title bar: replaces the native menu bar area, handles
        # minimise/maximise/close and window dragging.
        self._titlebar = TitleBar(self, title="")
        self._titlebar.setObjectName("MainTitleBar")
        self._titlebar.setAttribute(Qt.WA_StyledBackground, True)
        self.setMenuWidget(self._titlebar)
        global _C

        # ── Ayarlar ──────────────────────────────────────────────────────────
        self.base_dir        = get_app_dir("iqtMusicElite")
        self._settings_file  = os.path.join(self.base_dir, "settings.json")
        settings             = safe_load_json(self._settings_file, {})
        self._language       = normalize_language(settings.get("language", DEFAULT_LANGUAGE))
        self._titlebar.refresh_texts()
        _prog(8, self._tr("startup.settings_loading"))

        loaded_theme = settings.get("theme", "Yeşil")
        if loaded_theme not in THEMES:
            loaded_theme = "Yeşil"
        _C.CURRENT_THEME = loaded_theme
        self._playlist_covers: dict = settings.get("playlist_covers", {})
        self._playlist_overview_sort_mode = str(
            settings.get("playlist_overview_sort_mode", "added") or "added"
        ).strip().lower()
        self._playlist_manual_order: list = list(
            settings.get("playlist_manual_order", None) or []
        )
        # İçerik bölgesi arayüz dilinden ayrı tutulur.
        # Örn: Türkçe arayüz + Almanya/ABD listeleri.
        self._content_region_mode = str(settings.get("content_region_mode", "auto") or "auto").strip().lower()
        self._content_region = str(settings.get("content_region", "") or "").strip().upper()
        self._telemetry_enabled = bool(settings.get("telemetry_enabled", True))
        self._shortcut_map = dict(settings.get("shortcuts", {}) or {})
        self._lastfm_api_key = (
            os.environ.get("IQTMUSIC_LASTFM_API_KEY")
            or os.environ.get("LASTFM_API_KEY")
            or "ac802fa149a6b9afa6f2d6d485fdee94"
        )

        _prog(18, self._tr("startup.network_pools"))
        # ── HTTP & Thread havuzları ───────────────────────────────────────────
        self._seek_cooldown_until = 0.0
        self._last_vol_upd        = 0.0
        self._pending_seek_ms     = None
        self._http = requests.Session()
        self._http.headers["User-Agent"] = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/122 Safari/537.36"
        )
        try:
            self._content_region = detect_content_region(settings, session=self._http, base_dir=self.base_dir)
            log.info("İçerik bölgesi: %s (%s)", self._content_region, region_display_name(self._content_region, self._language))
        except Exception as _geo_err:
            log.debug("İçerik bölgesi algılanamadı: %s", _geo_err)
            self._content_region = self._content_region or "TR"
        self._img_pool = ThreadPoolExecutor(max_workers=4)
        self._net_pool = ThreadPoolExecutor(max_workers=6)
        self._stream_pool = ThreadPoolExecutor(max_workers=3)
        self._stream_prefetch_pool = ThreadPoolExecutor(max_workers=2)

        _prog(28, self._tr("startup.cache"))
        # ── Önbellek ─────────────────────────────────────────────────────────
        self._img_cache       = DiskImageCache(self.base_dir, 320, 14, 384)
        self._media_cache     = DiskMediaCache(self.base_dir, 3000)
        self._lastfm          = LastFMClient(
            self.base_dir,
            self._lastfm_api_key,
            session=self._http,
            preferred_language=self._language,
        )
        self._url_cache       = LRUTTLCache(400, 18000)
        self._track_info_cache = LRUTTLCache(200, 21600)
        self._home_cache      = {}
        self._home_cache_ttl  = 1800
        self._retry_guard: dict = {}
        self._shuffle_buf     = deque(maxlen=15)
        self._radio_queue_vids: set[str] = set()
        self._state_lock      = threading.RLock()
        self._queue_lock      = threading.RLock()
        self._stream_url_lock = threading.RLock()
        self._stream_waiters: dict = {}
        self._stream_prefetching: set[str] = set()
        self._search_history: list = safe_load_json(
            os.path.join(self.base_dir, "search_history.json"), [])
        self._main_play_icon_state = None
        self._main_play_icon = create_icon("play", "#FFFFFF", 15)
        self._main_pause_icon = create_icon("pause", "#FFFFFF", 14)
        self._vis_last_blur = 0
        self._sidebar_bootstrap_done = False
        self._startup_geometry_checked = False

        self._ydl_cache_dir = os.path.join(self.base_dir, "cache", "ydl")
        os.makedirs(self._ydl_cache_dir, exist_ok=True)
        self._ydl_opts = {
            # Geniş format seçici: mevcut en iyi ses; format yoksa herhangi bir ses al
            "format":             YDL_FORMAT,
            "quiet":              True,
            "cachedir":           self._ydl_cache_dir,
            "no_warnings":        True,
            "geo_bypass":         True,
            "socket_timeout":     15,
            "retries":            3,
            "fragment_retries":   3,
            # tv_embedded ve android istemcileri giriş yapmadan çalışır;
            # web istemcisiyle aynı format ID'lerini (140/251) kullandığından
            # bestaudio seçici bozulmaz.
            "extractor_args":     {"youtube": {"player_client": ["tv_embedded", "android", "web"]}},
        }
        # Tarayıcıdan çerez alarak bot tespitini ek güvence olarak ekle.
        # NOT: cookiesfrombrowser kasıtlı olarak devre dışı bırakıldı.
        # tv_embedded ve android player client'ları giriş gerektirmeden
        # çalıştığından tarayıcı çerezi gerekli değildir. Windows'ta
        # Chrome/Edge çerezleri DPAPI ile şifrelendiğinden yt-dlp
        # "Failed to decrypt with DPAPI" hatası verir. Bu yüzden çerez
        # okuma özelliği kullanılmıyor.

        # ── Sinyaller ────────────────────────────────────────────────────────
        self.sig = Signals()
        self.sig.image_loaded.connect(self._on_image)
        self.sig.notify.connect(self._show_toast)
        self.sig.home_section_done.connect(self._on_home_section)
        self.sig.search_done.connect(self._on_search)
        self.sig.lyrics_done.connect(self._on_lyrics)
        self.sig.player_ui_update.connect(self._sync_player_ui)
        self.sig.audio_url_ready.connect(self._start_resolved_audio)
        self.sig.artists_overview_done.connect(self._on_artists_overview)
        self.sig.artist_songs_done.connect(self._on_artist_songs)
        self.sig.artist_album_done.connect(self._on_artist_album)
        self.sig.auto_next_ready.connect(self._on_auto_next_ready)
        self.sig.crossfade_start.connect(self._start_crossfade)
        self.sig.rate_apply_deferred.connect(self._deferred_rate_apply)
        self.sig.audio_output_apply_deferred.connect(self._deferred_audio_output_apply)
        self.sig.restore_pos_deferred.connect(self._deferred_restore_pos)
        self.sig.media_key_action.connect(self._handle_media_key_action, Qt.QueuedConnection)
        self.sig.collab_sync.connect(self._collab_on_sync)
        self.sig.collab_control.connect(self._collab_on_control)
        self.sig.collab_status.connect(self._collab_on_status)
        self.sig.collab_join_request.connect(self._collab_show_join_approval)
        self.sig.play_all_tracks.connect(self._play_all)
        self.sig.history_updated.connect(self._on_history_updated)

        # ── İndirme yöneticisi ───────────────────────────────────────────────
        self.dl = DownloadManager(self.base_dir)
        self.dl.dl_format  = settings.get("dl_format",  "m4a")
        self.dl.dl_quality = settings.get("dl_quality", "best")
        saved_dir = settings.get("dl_dir", "")
        if saved_dir and os.path.isdir(saved_dir):
            self.dl.dl_dir = saved_dir
        self.dl.progress_signal.connect(self._on_dl_progress)
        self.dl.finished_signal.connect(self._on_dl_done)
        self.dl.error_signal.connect(self._on_dl_error)
        self._dl_progress: dict = {}

        _prog(40, self._tr("startup.ytmusic"))
        # ── YouTube Music API ────────────────────────────────────────────────
        # Hesap girişi zorunlu değil. Önce kayıtlı browser.json ile dene,
        # yoksa anonim modda başlat.
        #
        # PERFORMANS / SPLASH: YTMusic() ağa bağlanıp header dosyaları
        # oluşturduğundan 500ms-3s sürebilir. Arka plan thread'inde
        # çalıştırarak ana thread'i serbest bırakıyoruz; bu sayede splash
        # aurora animasyonu donmuyor.
        _yt_auth   = os.path.join(self.base_dir, "browser.json")
        _yt_box    = [None]   # [yt_instance]
        _yt_event  = threading.Event()

        def _yt_worker():
            try:
                _yt_box[0] = (YTMusic(_yt_auth) if os.path.isfile(_yt_auth)
                              else YTMusic())
                log.info("YTMusic başlatıldı (%s)",
                         "giriş yapılmış" if os.path.isfile(_yt_auth)
                         else "anonim mod")
            except Exception as _yt_err:
                log.warning("YTMusic başlatılamadı (%s), anonim moda geçiliyor",
                            _yt_err)
                try:
                    _yt_box[0] = YTMusic()
                except Exception:
                    _yt_box[0] = None
            finally:
                _yt_event.set()

        threading.Thread(target=_yt_worker, daemon=True,
                         name="iqt-yt-init").start()

        # Ana thread: 20ms'de bir event loop'u çalıştır → splash canlı kalır
        while not _yt_event.wait(timeout=0.020):
            _prog(40, self._tr("startup.ytmusic"))

        self.yt = _yt_box[0]

        # Ana sayfa verisi için ön yükleme başlat (YTMusic hazır, VLC init'iyle paralel)
        # Hem curated cards hem de bundle (hero/sections) önceden yüklenir; bu
        # sayede pencere açıldığında tüm cache'ler sıcak olur ve home sayfası
        # skeleton flash'ı olmadan anında render edilir.
        _home_prefetch_event = threading.Event()
        def _home_prefetch():
            try:
                from pages.home_clean import (
                    _TABS as _HOME_TABS,
                    _bundle as _pb,
                    _cache_get as _home_cache_get,
                    _cache_set as _home_cache_set,
                    _curated_home_cards as _phc,
                    _prepare_curated_playlist_covers as _prepare_curated_covers,
                    _personal as _home_personal,
                )
                curated_cards = _phc(self)
                _prepare_curated_covers(self, curated_cards, force_refresh=False)
                _pb(self)
                _home_personal(self)
                active_query = getattr(self, "_home_active_tab_query", "") or (
                    _HOME_TABS[0][1] if _HOME_TABS else "feed:charts.tr"
                )
                tab_cache_key = f"__home_bundle::tab::{active_query}"
                if _home_cache_get(self, tab_cache_key, ttl=900) is None:
                    tab_results = list(self._fetch_feed_results(active_query, limit=20) or [])
                    _home_cache_set(self, tab_cache_key, tab_results)
            except Exception as _pe:
                log.debug("Ana sayfa ön yükleme hatası: %s", _pe)
            finally:
                _home_prefetch_event.set()
        threading.Thread(target=_home_prefetch, daemon=True, name="iqt-home-prefetch").start()

        _prog(54, self._tr("startup.audio"))
        # ── VLC ──────────────────────────────────────────────────────────────
        # scaletempo filtresi: set_rate() ile hızlandırırken pitch korunur.
        #
        # PERFORMANS / SPLASH: vlc.Instance() libvlc.dll'yi yükleyip
        # eklenti dizinini taradığından 200ms-1s sürebilir. Arka plan
        # thread'inde başlatıp ana thread'i event loop için serbest bırakıyoruz.
        vlc_args = ["--no-video", "--quiet",
                    "--file-caching=500", "--network-caching=100",
                    "--audio-filter=equalizer:scaletempo"]

        _vlc_box   = [None, None, None, None]  # [inst, player, player2, eq]
        _vlc_event = threading.Event()
        _vlc_args  = list(vlc_args)            # kapanım için kopyala

        def _vlc_worker():
            try:
                inst        = vlc.Instance(*_vlc_args)
                _vlc_box[0] = inst
                _vlc_box[1] = inst.media_player_new()
                _vlc_box[2] = inst.media_player_new()
                _vlc_box[3] = vlc.AudioEqualizer()
            except Exception as _ve:
                log.error("VLC başlatılamadı: %s", _ve)
            finally:
                _vlc_event.set()

        threading.Thread(target=_vlc_worker, daemon=True,
                         name="iqt-vlc-init").start()

        while not _vlc_event.wait(timeout=0.020):
            _prog(54, self._tr("startup.audio"))

        self.vlc_inst = _vlc_box[0]
        self.player   = _vlc_box[1]
        self._player2 = _vlc_box[2]
        self.eq_inst  = _vlc_box[3]
        self._eq_vals = list(settings.get("eq_vals", [0]*10))
        if self.eq_inst is not None:
            for i, v in enumerate(self._eq_vals):
                self.eq_inst.set_amp_at_index(v, i)

        # ── Discord ──────────────────────────────────────────────────────────
        self._discord_id        = "1441852339521851482"
        self._discord_rpc       = None
        self._discord_connected = False
        self._discord_presence_enabled = bool(settings.get("discord_presence_enabled", True))
        self._discord_display_mode = str(settings.get("discord_display_mode", "song") or "song").strip().lower()
        if self._discord_display_mode not in {"song", "artist"}:
            self._discord_display_mode = "song"
        if DISCORD_AVAILABLE and self._discord_presence_enabled:
            self._net_pool.submit(self._discord_connect)

        # ── Durum değişkenleri ───────────────────────────────────────────────
        self.queue:              list  = []
        self.queue_index:        int   = -1
        self.target_vid:         str   = ""
        self._play_request_id:   int   = 0
        self._auto_next_token:   int   = 0
        self._cleanup_done:      bool  = False
        self.total_dur:          int   = 0
        self.is_dragging:        bool  = False
        self.current_page:       str   = ""
        self.prev_page:          dict  = None
        self._current_nav_payload       = None
        self._nav_history: list[dict]   = []
        self._nav_restoring: bool       = False
        self.in_queue_view:      bool  = False
        self._queue_page_refs:   dict  = {}
        self._queue_refresh_state       = None
        self._queue_last_current_vid    = None
        self._page_transition_overlay   = None
        self._page_opacity_fx          = None
        self._page_fade_out_anim       = None
        self._page_fade_in_anim        = None
        self._startup_home_light: bool = True
        self.repeat_mode:        int   = 0
        self.shuffle_on:         bool  = False
        self._last_vlc_chk:      float = 0
        self.lyrics_data:        list  = []
        self._lyrics_cache:      dict  = {}
        self._lyrics_request_id: int   = 0
        self._lyr_bound_vid:     str   = ""
        self._lyr_pending_vid:   str   = ""
        self._lyr_pending_request_id: int = 0
        self._lyr_window_size:   tuple = (560, 760)
        self._lyr_font_size:     int   = 15
        self._lyr_always_on_top: bool  = False
        self._lyr_offset_ms:     int   = 0

        _prog(64, self._tr("startup.user_data"))
        # ── Kalıcı dosyalar ──────────────────────────────────────────────────
        self.fav_file          = os.path.join(self.base_dir, "favoriler.json")
        self.liked_artists_file = os.path.join(self.base_dir, "liked_artists.json")
        self.playlist_file     = os.path.join(self.base_dir, "playlists.json")
        self.hist_file           = os.path.join(self.base_dir, "history.json")
        self.last_file           = os.path.join(self.base_dir, "last.json")
        self.stats_file          = os.path.join(self.base_dir, "stats.json")
        self._search_hist_file   = os.path.join(self.base_dir, "search_history.json")
        self._artists_cache_file = os.path.join(self.base_dir, "artists_cache.json")

        self.favorites  = safe_load_json(self.fav_file,      [])
        self.liked_artists = safe_load_json(self.liked_artists_file, [])
        self.playlists  = safe_load_json(self.playlist_file, {})
        history_raw     = safe_load_json(self.hist_file,     [])
        self.history    = history_raw if isinstance(history_raw, list) else history_raw.get("items", [])
        self.last_state = safe_load_json(self.last_file,     {})
        self.stats      = safe_load_json(self.stats_file,    {"play_count": {}, "total_ms": 0})

        # Sanatçı önbelleği — varsa diskten yükle (arka plan yenileme yine yapılır)
        _artists_disk = safe_load_json(self._artists_cache_file, {})
        if isinstance(_artists_disk, dict) and _artists_disk.get("payload"):
            self._artists_overview_payload    = _artists_disk["payload"]
            self._artists_overview_updated_at = float(_artists_disk.get("updated_at", 0) or 0)
        else:
            self._artists_overview_payload    = None
            self._artists_overview_updated_at = 0
        if not isinstance(self.stats, dict):
            self.stats = {"play_count": {}, "total_ms": 0}
        if not isinstance(self.liked_artists, list):
            self.liked_artists = []
        self.stats.setdefault("play_count", {})
        self.stats.setdefault("total_ms", 0)
        if not isinstance(self.stats.get("daily_ms"), dict):
            self.stats["daily_ms"] = {}
        if not isinstance(self.stats.get("listen_events"), list):
            self.stats["listen_events"] = []
        if not self.stats.get("period_start"):
            self.stats["period_start"] = datetime.now().isoformat(timespec="seconds")
            safe_save_json(self.stats_file, self.stats)
        self._listen_track = None
        self._listen_vid = ""
        self._listen_elapsed_ms = 0
        self._listen_counted = False
        self._listen_last_tick = None
        self._listen_last_state = None
        self._pending_restore_pos = None
        self._pending_restore_vid = ""

        self._volume        = settings.get("volume", 80)
        self._search_cache       = {"q": "", "results": []}
        self._search_filter      = "songs"
        self._search_filter_btns: dict = {}
        self._pixmap_mem: OrderedDict = OrderedDict()
        self._pixmap_mem_max = 200
        self._pixmap_waiters: dict = {}
        self._pixmap_pending: set = set()
        self._pixmap_lock = threading.RLock()

        # ── Oynatma davranışı / ses ayarları ─────────────────────────────────
        self._crossfade_duration = 0.0
        self._gapless_on         = False
        self._playback_rate      = float(settings.get("playback_rate", 1.0))
        self._loudness_mode      = str(settings.get("loudness_mode", "light") or "light").strip().lower()
        if self._loudness_mode not in {"off", "light", "strong"}:
            self._loudness_mode = "light"
        self._audio_output_device = str(settings.get("audio_output_device", "") or "")
        self._audio_output_name   = str(settings.get("audio_output_name", "") or "")
        self._next_preload_on     = bool(settings.get("next_preload_on", True))
        self._volume_step         = max(1, int(settings.get("volume_step", 5) or 5))
        self._seek_step_sec       = max(1, int(settings.get("seek_step_sec", 5) or 5))
        self._media_keys_enabled  = bool(settings.get("media_keys_enabled", True))
        self._media_key_listener  = None
        self._muted               = False
        self._audio_output_cache  = []
        self._cf_active          = False
        self._cf_triggered       = False
        self._cf_elapsed         = 0
        self._cf_interval        = 60
        self._cf_duration_ms     = 0
        self._cf_target_vol      = self._volume
        self._ended_transition_active = False
        self._collab_clock_offset_ms = 0.0
        self._collab_clock_rtt_ms = None
        self._collab_clock_best_rtt_ms = None
        self._collab_clock_ping_seq = 0
        self._collab_clock_pings: dict[str, int] = {}
        self._collab_session_epoch = 0
        self._collab_track_version = 0
        self._collab_epoch_track_vid = ""
        self._collab_anchor_host_ms = 0
        self._collab_anchor_pos_ms = 0
        self._collab_transport_state = "paused"
        self._collab_pending_host_broadcast_rid = 0
        self._collab_soft_rate_applied = None

        # ── Uyku zamanlayıcısı ───────────────────────────────────────────────
        self._sleep_timer = QTimer(self)
        self._sleep_timer.setSingleShot(True)
        self._sleep_timer.timeout.connect(self._sleep_stop)
        self._sleep_remaining = 0

        _prog(74, self._tr("startup.ui"))
        # ── Ana pencere ──────────────────────────────────────────────────────
        self.setWindowTitle("IQTMusic")
        self._fit_window_to_available_geometry(initial=True)
        app_font = QFont(FONT_MAIN, 10)
        app_font.setHintingPreference(QFont.PreferFullHinting)
        QApplication.instance().setFont(app_font)
        if os.path.exists(ICON_PATH):
            self.setWindowIcon(QIcon(ICON_PATH))

        self._setup_ui()
        _prog(82, self._tr("startup.styles"))
        QApplication.instance().installEventFilter(self)
        self._apply_styles()
        self._setup_shortcuts()
        self._setup_tray()
        self._setup_media_keys()

        _prog(88, self._tr("startup.timers"))
        # ── Timer'lar ────────────────────────────────────────────────────────
        self._seek_timer = QTimer(self)
        self._seek_timer.timeout.connect(self._update_seek)
        self._seek_timer.start(200)

        self._state_timer = QTimer(self)
        self._state_timer.timeout.connect(self._check_state)
        self._state_timer.start(1000)

        self._discord_timer = QTimer(self)
        self._discord_timer.timeout.connect(self._discord_loop)
        self._discord_timer.start(2000)

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(400)
        self._search_timer.timeout.connect(self._do_search)

        self._sleep_display_timer = QTimer(self)
        self._sleep_display_timer.timeout.connect(self._update_sleep_display)
        self._sleep_display_timer.start(1000)

        self._vis_timer = QTimer(self)
        self._vis_timer.timeout.connect(self._update_visualizer)
        self._vis_timer.start(33)
        self._vis_phase = 0.0

        # Crossfade timer (ana thread'de oluşturulmalı)
        self._cf_timer = QTimer(self)
        self._cf_timer.timeout.connect(self._cf_tick)
        QTimer.singleShot(5000, lambda: setattr(self, "_startup_home_light", False))

        QApplication.instance().aboutToQuit.connect(self._cleanup)

        _prog(94, self._tr("startup.home"))
        # ── Başlangıç sayfası & son durum ────────────────────────────────────
        # Ön yükleme thread'inin bitmesini bekle (en fazla 6 saniye).
        # Bu sayede anasayfa açıldığında veriler önbellekte hazır olur.
        _home_prefetch_event.wait(timeout=6.0)
        self.page_home()

        if self.last_state.get("track"):
            try:
                t = self.last_state["track"]
                self.queue       = [t]
                self.queue_index = 0
                self.target_vid  = t.get("videoId", "")
                self.lbl_title.setText(t.get("title", "")[:32])
                self._set_player_artist_label(t)
                if t.get("thumbnails"):
                    self._load_image(t["thumbnails"][-1]["url"],
                                     self.img_cover, (60, 60))
                self.player_bar.show()
                pos = self.last_state.get("position")
                if pos is not None:
                    self._pending_restore_pos = int(pos)
                    self._pending_restore_vid = t.get("videoId", "")
            except Exception as e:
                log.warning("Son durum yüklenemedi: %s", e)


        self._session_start = time.monotonic()
        self._send_startup_telemetry()


    def _send_startup_telemetry(self):
        try:
            maybe_send_startup_telemetry(
                base_dir=self.base_dir,
                app_version=APP_VERSION,
                language=getattr(self, "_language", "tr"),
                enabled=bool(getattr(self, "_telemetry_enabled", True)),
            )
        except Exception as e:
            log.debug("Telemetry skipped: %s", e)


    def showEvent(self, event):
        super().showEvent(event)
        self._update_window_rounding()
        if not self._startup_geometry_checked:
            self._startup_geometry_checked = True
            QTimer.singleShot(0, self._fit_window_to_available_geometry)
        if self._sidebar_bootstrap_done:
            return
        self._sidebar_bootstrap_done = True

        def _stabilize_sidebar():
            try:
                self._set_active_nav("home")
                if getattr(self, "sidebar", None):
                    self.sidebar.updateGeometry()
                    self.sidebar.update()
            except Exception as _e:
                log.debug("Sessiz hata: %s", _e)

        QTimer.singleShot(0, _stabilize_sidebar)
        QTimer.singleShot(160, _stabilize_sidebar)

    # ══════════════════════════════════════════════════════════════════════════
    # UI KURULUM
    # ══════════════════════════════════════════════════════════════════════════


    def _tr(self, key: str, **kwargs) -> str:
        return translate(getattr(self, "_language", DEFAULT_LANGUAGE), key, **kwargs)

    def _language_label(self, language: str | None = None) -> str:
        code = normalize_language(language or getattr(self, "_language", DEFAULT_LANGUAGE))
        return self._tr(f"language.name.{code}")

    def _set_language(self, language: str, save: bool = True, refresh_ui: bool = True) -> bool:
        code = normalize_language(language)
        changed = code != getattr(self, "_language", DEFAULT_LANGUAGE)
        self._language = code
        try:
            if getattr(self, "_lastfm", None) is not None:
                self._lastfm.set_language(code)
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
        if save:
            self._save_settings()
        if changed and refresh_ui and hasattr(self, "pages"):
            self._refresh_language()
            self.sig.notify.emit(
                self._tr("language.changed", language=self._language_label(code))
            )
        return changed

    def _rebuild_sidebar(self):
        old_sidebar = getattr(self, "sidebar", None)
        host = self.centralWidget()
        layout = host.layout() if host is not None else None
        if old_sidebar is None or layout is None:
            return
        idx = layout.indexOf(old_sidebar)
        if idx < 0:
            return
        layout.removeWidget(old_sidebar)
        old_sidebar.hide()
        old_sidebar.deleteLater()
        self.sidebar = build_sidebar(self)
        layout.insertWidget(idx, self.sidebar)

    def _refresh_language(self):
        try:
            self._invalidate_home_cache()
        except Exception:
            pass
        try:
            self._rebuild_sidebar()
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
        try:
            self._setup_tray()
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
        try:
            if hasattr(self, "_refresh_player_bar_texts"):
                self._refresh_player_bar_texts()
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
        try:
            if hasattr(self, "_update_mini"):
                self._update_mini()
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
        try:
            if hasattr(self, "_mini_win") and self._mini_win is not None:
                self._mini_win.setWindowTitle(self._tr("mini_player.window_title"))
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
        try:
            if hasattr(self, "_update_home_now_playing"):
                self._update_home_now_playing()
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
        try:
            if hasattr(self, "_lyrics_refresh_ui_texts"):
                self._lyrics_refresh_ui_texts()
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
        try:
            if hasattr(self, "_titlebar") and self._titlebar is not None:
                self._titlebar.refresh_texts()
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
        try:
            if hasattr(self, "_collab_update_ui"):
                self._collab_update_ui()
            if hasattr(self, "_collab_refresh_dialog"):
                self._collab_refresh_dialog()
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
        current_payload = getattr(self, "_current_nav_payload", None)
        if current_payload:
            try:
                self._open_nav_payload(dict(current_payload), from_history=True)
            except Exception as _e:
                log.debug("Sessiz hata: %s", _e)
        else:
            try:
                refreshers = {
                    "home": "page_home",
                    "search": "page_search",
                    "artists": "page_artists",
                    "favorites": "page_favs",
                    "downloads": "page_downloads",
                    "queue": "page_queue",
                    "stats": "page_stats",
                }
                refresher_name = refreshers.get(str(getattr(self, "current_page", "") or ""))
                refresher = getattr(self, refresher_name, None) if refresher_name else None
                if callable(refresher):
                    refresher()
            except Exception as _e:
                log.debug("Sessiz hata: %s", _e)

    def _setup_ui(self):
        cw = QWidget()
        cw.setObjectName("AppShell")
        cw.setAttribute(Qt.WA_StyledBackground, True)
        self._app_shell = cw
        self.setCentralWidget(cw)
        ml = QHBoxLayout(cw)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(0)

        self.sidebar = build_sidebar(self)
        ml.addWidget(self.sidebar)

        rf = QWidget()
        rf.setObjectName("ContentFrame")
        rf.setAttribute(Qt.WA_StyledBackground, True)
        self._content_frame = rf
        rl = QVBoxLayout(rf)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)
        self.pages = QStackedWidget()
        rl.addWidget(self.pages)

        self.player_bar = build_player_bar(self)
        rl.addWidget(self.player_bar)
        ml.addWidget(rf)


    def _apply_styles(self):
        self.setStyleSheet(get_main_stylesheet())
        self._update_window_rounding()


    def _refresh_rounded_shell_style(self, flat: bool):
        radius = 0 if flat else int(getattr(self, "_window_corner_radius", 24) or 24)
        titlebar = getattr(self, "_titlebar", None)
        if titlebar is not None:
            titlebar.setStyleSheet(f"""
                QWidget#MainTitleBar {{
                    background-color: {BG_BLACK};
                    color: #e0e0e0;
                    border-top-left-radius: {radius}px;
                    border-top-right-radius: {radius}px;
                }}
            """)
        for widget in (
            getattr(self, "_app_shell", None),
            getattr(self, "_content_frame", None),
            getattr(self, "sidebar", None),
            getattr(self, "player_bar", None),
        ):
            if widget is None:
                continue
            try:
                widget.setProperty("flatWindow", flat)
                widget.style().unpolish(widget)
                widget.style().polish(widget)
                widget.update()
            except Exception as _e:
                log.debug("Sessiz hata: %s", _e)


    def _set_native_corner_preference(self, rounded: bool):
        if not sys.platform.startswith("win") or ctypes is None:
            return
        try:
            DWMWA_WINDOW_CORNER_PREFERENCE = 33
            DWMWCP_DONOTROUND = 1
            DWMWCP_ROUND = 2
            value = ctypes.c_int(DWMWCP_ROUND if rounded else DWMWCP_DONOTROUND)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                int(self.winId()),
                DWMWA_WINDOW_CORNER_PREFERENCE,
                ctypes.byref(value),
                ctypes.sizeof(value),
            )
        except Exception as _e:
            log.debug("Native pencere köşesi uygulanamadı: %s", _e)


    def _set_fullscreen_topmost(self, enabled: bool, geom=None):
        if not sys.platform.startswith("win") or ctypes is None:
            return
        try:
            hwnd = int(self.winId())
            HWND_TOPMOST = -1
            HWND_NOTOPMOST = -2
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_NOACTIVATE = 0x0010
            SWP_SHOWWINDOW = 0x0040
            x = y = w = h = 0
            flags = SWP_NOACTIVATE | SWP_SHOWWINDOW
            if enabled and geom is not None:
                x, y, w, h = geom.x(), geom.y(), geom.width(), geom.height()
            else:
                flags |= SWP_NOMOVE | SWP_NOSIZE
            ctypes.windll.user32.SetWindowPos(
                hwnd,
                HWND_TOPMOST if enabled else HWND_NOTOPMOST,
                x,
                y,
                w,
                h,
                flags,
            )
        except Exception as _e:
            log.debug("Fullscreen topmost uygulanamadı: %s", _e)


    def _enable_native_rounded_corners(self):
        self._set_native_corner_preference(True)


    def _update_window_rounding(self):
        fullscreen = self._is_effective_fullscreen() if hasattr(self, "_is_effective_fullscreen") else self.isFullScreen()
        maximized = self._is_effective_maximized() if hasattr(self, "_is_effective_maximized") else self.isMaximized()
        flat = bool(maximized or fullscreen)
        self._refresh_rounded_shell_style(flat)
        if flat:
            try:
                self.clearMask()
            except Exception as _e:
                log.debug("Sessiz hata: %s", _e)
            # Qt keeps the real fullscreen/maximized bounds; changing geometry
            # here can silently drop the native fullscreen/maximized state.
            self._set_native_corner_preference(False)
            return
        self._enable_native_rounded_corners()
        try:
            size = self.size()
            if size.width() <= 0 or size.height() <= 0:
                return
            radius = int(getattr(self, "_window_corner_radius", 24) or 24)
            mask = QBitmap(size.width(), size.height())
            mask.fill(Qt.GlobalColor.color0)
            painter = QPainter(mask)
            try:
                painter.setRenderHint(QPainter.Antialiasing)
                painter.setPen(Qt.NoPen)
                painter.setBrush(Qt.GlobalColor.color1)
                path = QPainterPath()
                path.addRoundedRect(0, 0, size.width(), size.height(), radius, radius)
                painter.drawPath(path)
            finally:
                painter.end()
            self.setMask(mask)
        except Exception as _e:
            log.debug("Rounded pencere maskesi uygulanamadı: %s", _e)


    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.WindowStateChange:
            QTimer.singleShot(0, self._update_window_rounding)


    def _setup_shortcuts(self):
        from PySide6.QtGui import QShortcut

        previous = list(getattr(self, "_shortcuts", []) or [])
        for shortcut in previous:
            try:
                shortcut.setParent(None)
                shortcut.deleteLater()
            except Exception:
                pass

        definitions = [
            ("play_pause", "shortcut.play_pause", "Space", self.toggle_play),
            ("search", "shortcut.search", "Ctrl+F", self.page_search),
            ("queue", "shortcut.queue", "Ctrl+Q", self.toggle_queue_view),
            ("lyrics", "shortcut.lyrics", "Ctrl+L", self.open_lyrics),
            ("next", "shortcut.next", "Ctrl+Right", self.next_song),
            ("previous", "shortcut.previous", "Ctrl+Left", self.prev_song),
            ("volume_up", "shortcut.volume_up", "Ctrl+Up", lambda: self._change_volume(getattr(self, "_volume_step", 5))),
            ("volume_down", "shortcut.volume_down", "Ctrl+Down", lambda: self._change_volume(-getattr(self, "_volume_step", 5))),
            ("seek_forward", "shortcut.seek_forward", "Alt+Right", lambda: self._seek_relative(getattr(self, "_seek_step_sec", 5))),
            ("seek_backward", "shortcut.seek_backward", "Alt+Left", lambda: self._seek_relative(-getattr(self, "_seek_step_sec", 5))),
            ("mute", "shortcut.mute", "M", self.toggle_mute),
            ("fullscreen", "shortcut.fullscreen", "F11", self.toggle_fullscreen),
            ("exit_fullscreen", "shortcut.exit_fullscreen", "Escape", lambda: self.exit_fullscreen() if self.isFullScreen() else None),
        ]
        self._shortcut_definitions = [
            {"id": sid, "label_key": label_key, "default": default}
            for sid, label_key, default, _callback in definitions
        ]
        configured = dict(getattr(self, "_shortcut_map", {}) or {})
        self._shortcut_map = {
            sid: str(configured.get(sid) or default)
            for sid, _label_key, default, _callback in definitions
        }

        def _add_shortcut(seq: str, callback):
            key = QKeySequence(str(seq or "").strip())
            if key.isEmpty():
                return None
            sc = QShortcut(QKeySequence(seq), self)
            sc.setContext(Qt.ApplicationShortcut)
            sc.activated.connect(callback)
            self._shortcuts.append(sc)
            return sc

        self._shortcuts = []
        for sid, _label_key, _default, callback in definitions:
            _add_shortcut(self._shortcut_map.get(sid, ""), callback)

    def _set_shortcut_sequence(self, shortcut_id: str, sequence: str):
        shortcut_id = str(shortcut_id or "").strip()
        valid_ids = {item.get("id") for item in getattr(self, "_shortcut_definitions", [])}
        if shortcut_id not in valid_ids:
            return
        self._shortcut_map[shortcut_id] = str(sequence or "").strip()
        self._save_settings()
        self._setup_shortcuts()

    def _reset_shortcut_sequence(self, shortcut_id: str):
        for item in getattr(self, "_shortcut_definitions", []) or []:
            if item.get("id") == shortcut_id:
                self._set_shortcut_sequence(shortcut_id, item.get("default", ""))
                return


    def _setup_tray(self):
        self._tray_available = bool(QSystemTrayIcon.isSystemTrayAvailable())
        if not self._tray_available:
            self.tray = None
            log.warning("Sistem tray kullanilamiyor; pencere kapatilinca uygulama cikacak.")
            return
        if getattr(self, "tray", None) is None:
            self.tray = QSystemTrayIcon(self)
            self.tray.activated.connect(
                lambda r: self._show_window() if r == QSystemTrayIcon.DoubleClick else None
            )
        if os.path.exists(ICON_PATH):
            self.tray.setIcon(QIcon(ICON_PATH))
        else:
            pix = QPixmap(64, 64)
            pix.fill(QColor(get_accent()))
            self.tray.setIcon(QIcon(pix))
        m = QMenu()
        m.addAction(QAction(self._tr("tray.show"),       self, triggered=self._show_window))
        m.addAction(QAction(self._tr("tray.previous"),   self, triggered=self.prev_song))
        m.addAction(QAction(self._tr("tray.play_pause"), self, triggered=self.toggle_play))
        m.addAction(QAction(self._tr("tray.next"),       self, triggered=self.next_song))
        m.addSeparator()
        m.addAction(QAction(self._tr("tray.quit"),       self, triggered=self._quit))
        self.tray.setContextMenu(m)
        self.tray.show()


    def _show_window(self):
        """Pencereyi öne getirir; minimize/gizli durumdaysa açar."""
        mode = self._window_display_mode()
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
        if mode == "fullscreen":
            self._fullscreen_active = True
            self._maximized_active = False
            self.showFullScreen()
            self._force_fullscreen_bounds()
        elif mode == "maximized":
            self._fullscreen_active = False
            self._maximized_active = True
            self.showNormal()
            self._force_maximized_bounds()
        else:
            self._fullscreen_active = False
            self._maximized_active = False
            self.showNormal()
            self._fit_window_to_available_geometry()
        self._sync_titlebar_window_state()
        self.raise_()
        self.activateWindow()

    def _quit(self):
        """Uygulamayı tamamen kapatır."""
        self._send_close_telemetry()
        QApplication.quit()

    def _send_close_telemetry(self):
        try:
            if not getattr(self, "_telemetry_enabled", True):
                return
            sec = int(time.monotonic() - getattr(self, "_session_start", time.monotonic()))
            send_event(
                base_dir=self.base_dir,
                event="app_close",
                app_version=APP_VERSION,
                session_sec=sec,
            )
        except Exception as e:
            log.debug("Close telemetry skipped: %s", e)

    def closeEvent(self, event):
        """Kapat düğmesine basılınca pencereyi gizle, uygulamayı kapatma."""
        if getattr(self, "_tray_available", False) and self.tray is not None:
            event.ignore()
            self.hide()
        else:
            self._send_close_telemetry()
            event.accept()

    def _handle_media_key_action(self, action: str):
        if not getattr(self, "_media_keys_enabled", True):
            return
        action = str(action or "").strip().lower()
        if action == "play_pause":
            self.toggle_play()
        elif action == "next":
            self.next_song()
        elif action == "prev":
            self.prev_song()
        elif action == "vol_up":
            self._change_volume(getattr(self, "_volume_step", 5))
        elif action == "vol_down":
            self._change_volume(-getattr(self, "_volume_step", 5))
        elif action == "mute":
            self.toggle_mute()


    def _dispatch_media_key(self, action: str):
        if not getattr(self, "_media_keys_enabled", True):
            return
        action = str(action or "").strip().lower()
        if not action:
            return
        now = time.time()
        last_action = getattr(self, "_last_media_action", "")
        last_at = float(getattr(self, "_last_media_action_at", 0.0) or 0.0)
        if action == last_action and (now - last_at) < 0.18:
            return
        self._last_media_action = action
        self._last_media_action_at = now
        try:
            self.sig.media_key_action.emit(action)
        except Exception as _e:
            log.debug("Media key dispatch hatasi: %s", _e)


    def _setup_media_keys(self):
        if not getattr(self, "_media_keys_enabled", True):
            return
        if not PYNPUT_AVAILABLE:
            return

        key_type = getattr(pynput_keyboard, "Key", None)
        special_map = {}
        for attr, action in (
            ("media_play_pause", "play_pause"),
            ("media_next", "next"),
            ("media_previous", "prev"),
            ("media_volume_up", "vol_up"),
            ("media_volume_down", "vol_down"),
            ("media_volume_mute", "mute"),
        ):
            special = getattr(key_type, attr, None) if key_type else None
            if special is not None:
                special_map[special] = action

        vk_map = {
            0xB3: "play_pause",
            0xB0: "next",
            0xB1: "prev",
            0xAF: "vol_up",
            0xAE: "vol_down",
            0xAD: "mute",
        }

        def _on_key(key):
            try:
                action = special_map.get(key)
                if not action:
                    vk = getattr(key, "vk", None)
                    if vk is not None:
                        action = vk_map.get(int(vk))
                if not action:
                    name = str(getattr(key, "name", "") or str(key) or "").lower()
                    text_map = {
                        "media_play_pause": "play_pause",
                        "media_next": "next",
                        "media_previous": "prev",
                        "media_volume_up": "vol_up",
                        "media_volume_down": "vol_down",
                        "media_volume_mute": "mute",
                    }
                    for token, mapped in text_map.items():
                        if token in name:
                            action = mapped
                            break
                if action:
                    self._dispatch_media_key(action)
            except Exception as _e:
                log.debug("Media key listener hatasi: %s", _e)

        try:
            listener = pynput_keyboard.Listener(on_press=_on_key)
            listener.daemon = True
            listener.start()
            self._media_key_listener = listener
        except Exception as _e:
            log.debug("Media key listener baslatilamadi: %s", _e)


    def nativeEvent(self, eventType, message):
        if sys.platform.startswith("win") and ctypes is not None and wintypes is not None:
            try:
                msg = wintypes.MSG.from_address(int(message))
                if msg.message == 0x0319:  # WM_APPCOMMAND
                    cmd = (int(msg.lParam) >> 16) & 0xFFF
                    mapping = {
                        14: "play_pause",
                        11: "next",
                        12: "prev",
                        10: "vol_up",
                        9:  "vol_down",
                        8:  "mute",
                    }
                    action = mapping.get(cmd)
                    if action:
                        self._dispatch_media_key(action)
                        return True, 0
            except Exception as _e:
                log.debug("nativeEvent media key hatasi: %s", _e)
        return super().nativeEvent(eventType, message)

    # ══════════════════════════════════════════════════════════════════════════
    # SAYFA NAVİGASYONU
    # ══════════════════════════════════════════════════════════════════════════


    def _clear(self):
        self._queue_refresh_state = None
        self._queue_last_current_vid = None
        if self._page_transition_overlay:
            self._page_transition_overlay.hide()
        while self.pages.count():
            w = self.pages.widget(0)
            self.pages.removeWidget(w)
            w.deleteLater()


    def _add_soft_shadow(self, widget, blur=24, color=None, dx=0, dy=8):
        eff = QGraphicsDropShadowEffect(widget)
        eff.setBlurRadius(blur)
        eff.setOffset(dx, dy)
        eff.setColor(color or QColor(0, 0, 0, 120))
        # Delay attachment until the target widget is shown. Attaching the
        # effect too early can trigger Qt's point-size warning on some pages.
        if widget.isVisible():
            widget.setGraphicsEffect(eff)
        else:
            pending = getattr(self, "_pending_soft_shadows", None)
            if pending is None:
                pending = {}
                self._pending_soft_shadows = pending
            pending[id(widget)] = (widget, eff)
        return eff


    def _set_main_play_icon(self, playing: bool):
        state = "pause" if playing else "play"
        if self._main_play_icon_state == state:
            return
        self._main_play_icon_state = state
        if playing:
            self.btn_play.setIcon(self._main_pause_icon)
            self.btn_play.setIconSize(QSize(14, 14))
            if hasattr(self.btn_play, "setIconOffset"):
                self.btn_play.setIconOffset(0, 0)
            self.btn_play.setToolTip(self._tr("player.tooltip.pause"))
        else:
            self.btn_play.setIcon(self._main_play_icon)
            self.btn_play.setIconSize(QSize(15, 15))
            if hasattr(self.btn_play, "setIconOffset"):
                self.btn_play.setIconOffset(1, 0)
            self.btn_play.setToolTip(self._tr("player.tooltip.play"))


    def _extract_stream_url(self, vid: str, bypass_cache=False):
        if not vid:
            return None
        if self.dl.is_downloaded(vid):
            return self.dl.get_path(vid)
        if not bypass_cache:
            cached = self._url_cache.get(vid)
            if cached:
                return cached
        with YoutubeDL(self._ydl_opts) as ydl:
            info = ydl.extract_info(
                f"https://www.youtube.com/watch?v={vid}",
                download=False,
            )
            url = info.get("url")
        if url:
            self._url_cache.set(vid, url)
        return url


    def _resolve_stream_url(self, vid: str, bypass_cache=False):
        if not vid:
            return None
        if self.dl.is_downloaded(vid):
            return self.dl.get_path(vid)
        cached_media = self._media_cache.get_path(vid)
        if cached_media:
            return cached_media
        if bypass_cache:
            self._url_cache.delete(vid)
        else:
            cached = self._url_cache.get(vid)
            if cached:
                return cached

        owner = False
        with self._stream_url_lock:
            waiter = self._stream_waiters.get(vid)
            if waiter is None:
                waiter = {
                    "event": threading.Event(),
                    "url": None,
                    "error": None,
                    "bypass_cache": bool(bypass_cache),
                }
                self._stream_waiters[vid] = waiter
                owner = True
            elif bypass_cache:
                waiter["bypass_cache"] = True

        if owner:
            try:
                url = self._extract_stream_url(
                    vid,
                    bypass_cache=waiter.get("bypass_cache", False),
                )
                waiter["url"] = url
                return url
            except Exception as exc:
                waiter["error"] = exc
                raise
            finally:
                waiter["event"].set()
                with self._stream_url_lock:
                    self._stream_waiters.pop(vid, None)

        waiter["event"].wait(25)
        if waiter.get("url"):
            return waiter["url"]
        if waiter.get("error"):
            raise waiter["error"]
        return None


    def _prefetch_stream(self, track_or_vid):
        if isinstance(track_or_vid, dict):
            vid = track_or_vid.get("videoId", "")
        else:
            vid = str(track_or_vid or "")
        if not vid or self.dl.is_downloaded(vid) or self._url_cache.get(vid):
            return

        with self._stream_url_lock:
            if vid in self._stream_prefetching or vid in self._stream_waiters:
                return
            self._stream_prefetching.add(vid)

        def _task():
            try:
                self._resolve_stream_url(vid)
            except Exception as _e:
                log.debug("Sessiz hata: %s", _e)
            finally:
                with self._stream_url_lock:
                    self._stream_prefetching.discard(vid)

        self._stream_prefetch_pool.submit(_task)


    def _prime_stream_urls(self, tracks, limit=3):
        if not tracks:
            return
        seen = set()
        primed = 0
        for track in tracks:
            if not isinstance(track, dict):
                continue
            vid = track.get("videoId", "")
            if not vid or vid in seen:
                continue
            seen.add(vid)
            self._prefetch_stream(track)
            primed += 1
            if primed >= limit:
                break


    def _scrollable(self):
        return _scrollable()


    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()


    def _thumb(self, track: dict, big: bool = False) -> str | None:
        """Return a thumbnail URL for a track.

        The YouTube Music API occasionally omits ``thumbnails`` or ``thumbnail``
        fields for tracks, which leads to blank album covers in the UI (e.g.
        for radio and queue entries). To ensure we always have a cover to
        display, this helper first attempts to use any provided thumbnail
        fields and then falls back to the standard YouTube default based on
        the ``videoId``. When a fallback URL is used, it is appended to the
        track's ``thumbnails`` list so subsequent calls can reuse the URL
        without re‑entering the fallback branch.

        Args:
            track: Metadata dictionary for the track.
            big: When ``True``, prefer a higher resolution image (``hqdefault``);
                 otherwise use a medium quality image (``mqdefault``).

        Returns:
            The URL string of a suitable thumbnail if available, or ``None``.
        """
        if not isinstance(track, dict):
            return None
        key = "thumbnails"
        alt = "thumbnail"
        # Try the explicit list of thumbnails first
        thumbs = track.get(key)
        if isinstance(thumbs, list) and thumbs:
            # Bazı parçalar için "thumbnails" listesinde farklı boyut ve oranlarda
            # görseller bulunur. Kare kapaklar 16:9 resimlere göre küçük
            # boyutta olabilir; bu nedenle oranı yüksekliği ve genişliği
            # birbirine yakın olan (kareye yakın) görselleri tercih ediyoruz.
            square_candidates = []
            for t in thumbs:
                try:
                    w, h = t.get("width"), t.get("height")
                    if w and h:
                        # En boy oranı kareye yakınsa aday olarak ekle
                        if abs(w - h) / max(w, h) < 0.2:
                            square_candidates.append(t)
                except Exception as _e:
                    log.debug("Sessiz hata: %s", _e)
            if square_candidates:
                # Mevcut kare adayları küçükten büyüğe sırala
                square_candidates.sort(key=lambda d: d.get("width", 0))
                # Büyük olanı mı küçük olanı mı istiyoruz? `big=True`
                chosen = square_candidates[-1] if big else square_candidates[0]
                url = chosen.get("url")
                if url:
                    return url
            # Kare aday bulunamazsa önceki yaklaşımı kullan
            try:
                return thumbs[-1]["url"] if big else thumbs[0]["url"]
            except Exception as _e:
                log.debug("Sessiz hata: %s", _e)
        # Fall back to alternate field if present
        if alt in track:
            v = track[alt]
            if isinstance(v, list) and v:
                try:
                    return v[-1]["url"] if big else v[0]["url"]
                except Exception as _e:
                    log.debug("Sessiz hata: %s", _e)
            if isinstance(v, str) and v:
                return v
        # Finally, construct a default thumbnail from the videoId
        vid = track.get("videoId") or track.get("video_id")
        if vid:
            quality = "hqdefault" if big else "mqdefault"
            url = f"https://i.ytimg.com/vi/{vid}/{quality}.jpg"
            try:
                # NOTE: Bu blok kasıtlı olarak track dict'ini mutasyona uğratır.
                # Fallback URL'yi thumbnails listesine ekleyerek sonraki
                # çağrılarda tekrar hesaplama yapılmasını önleriz. Bu davranış
                # bilinçlidir; track dict'leri uygulama boyunca paylaşılan
                # referanslardır, dolayısıyla bu güncelleme tüm görünümlere
                # otomatik olarak yansır.
                thumbs_list = track.get(key)
                if not isinstance(thumbs_list, list):
                    track[key] = []
                    thumbs_list = track[key]
                # Aynı URL'yi iki kez eklememek için kontrol et
                if not any(
                    isinstance(t, dict) and t.get("url") == url
                    for t in thumbs_list
                ):
                    thumbs_list.append({"url": url})
            except (TypeError, AttributeError) as _e:
                log.debug("Sessiz hata (_thumb fallback): %s", _e)
            return url
        return None


    def _artist_str(self, track: dict) -> str:
        a = track.get("artists")
        if a and isinstance(a, list):
            names = [x.get("name", "") for x in a if isinstance(x, dict) and x.get("name")]
            if names:
                return " & ".join(names)
        if isinstance(a, str):
            return a
        return (track.get("author", {}).get("name", "?")
                if isinstance(track.get("author"), dict)
                else track.get("author", "?"))


    def _fmt(self, ms: int) -> str:
        s    = ms // 1000
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


    def _search_history_matches(self, query: str, limit: int = 8) -> list[str]:
        q = str(query or "").strip().lower()
        if not self._search_history:
            return []
        if not q:
            return list(self._search_history[:limit])
        ranked = []
        for item in self._search_history:
            text = str(item or "").strip()
            norm = text.lower()
            if not norm or norm == q:
                continue
            if norm.startswith(q):
                score = 0
            elif q in norm:
                score = 1
            else:
                continue
            ranked.append((score, len(text), text))
        ranked.sort(key=lambda row: (row[0], row[1], row[2]))
        return [text for *_meta, text in ranked[:limit]]


    def _hide_search_suggestions(self):
        widget = getattr(self, "_search_suggest", None)
        if widget is None or not qt_is_valid(widget):
            self._search_suggest = None
            return
        widget.clear()
        widget.hide()


    def _update_search_suggestions(self, text: str | None = None):
        widget = getattr(self, "_search_suggest", None)
        if widget is None or not qt_is_valid(widget):
            self._search_suggest = None
            return
        search_box = getattr(self, "_search_box", None)
        if text is None and search_box is not None and qt_is_valid(search_box):
            query = str(search_box.text() or "").strip()
        else:
            query = str(text or "").strip()
        suggestions = self._search_history_matches(query)
        if not suggestions:
            self._hide_search_suggestions()
            return
        widget.blockSignals(True)
        widget.clear()
        for item in suggestions:
            widget.addItem(item)
        widget.blockSignals(False)
        widget.show()


    def _apply_search_suggestion(self, text: str):
        suggestion = str(text or "").strip()
        search_box = getattr(self, "_search_box", None)
        if not suggestion or search_box is None or not qt_is_valid(search_box):
            self._search_box = None
            return
        search_box.setText(suggestion)
        self._hide_search_suggestions()
        self._do_search()


    def _on_search_text_changed(self, text: str):
        q = str(text or "").strip()
        self._search_cache["q"] = q
        self._search_timer.stop()
        self._update_search_suggestions(q)
        if q:
            return

        self._search_cache["results"] = []
        self._search_fav_buttons = {}
        self._hide_search_suggestions()
        try:
            if hasattr(self, "_res_layout") and qt_is_valid(self._res_layout):
                self._clear_layout(self._res_layout)
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)


    def _do_search(self):
        search_box = getattr(self, "_search_box", None)
        res_layout = getattr(self, "_res_layout", None)
        if search_box is None or not qt_is_valid(search_box):
            self._search_box = None
            return
        if res_layout is None or not qt_is_valid(res_layout):
            self._res_layout = None
            return
        q = search_box.text().strip()
        if not q:
            self._search_cache["q"] = ""
            self._search_cache["results"] = []
            self._clear_layout(res_layout)
            self._hide_search_suggestions()
            return
        self._search_cache["q"] = q
        if q not in self._search_history:
            self._search_history.insert(0, q)
            self._search_history = self._search_history[:20]
            safe_save_json(self._search_hist_file, self._search_history)
        self._hide_search_suggestions()
        self._clear_layout(res_layout)
        lbl = QLabel(self._tr("search.loading"))
        lbl.setStyleSheet(f"color:{get_accent()}; font-size:14px; background:transparent;")
        res_layout.addWidget(lbl)
        self._net_pool.submit(self._search_worker, q)
        if getattr(self, "_telemetry_enabled", True):
            send_event(base_dir=self.base_dir, event="feature_use", feature="search")


    def _rank_search(self, results: list, query: str) -> list:
        """Arama sonuçlarını alaka düzeyine göre sırala.

        Tam eşleşmeler (başlık veya sanatçı + başlık) en üste çıkar,
        kısmi eşleşmeler ortaya, geri kalanlar YouTube'un sırasını korur.
        """
        q_l = query.lower().strip()
        q_words = q_l.split()

        def _score(track):
            title  = (track.get("title") or "").lower()
            arts   = " ".join(
                a.get("name", "") for a in (track.get("artists") or [])
            ).lower()
            full   = f"{arts} {title}"
            # Başlıkta tam sorgu eşleşmesi
            if q_l in title:
                return 0
            # Sanatçı + başlık içinde tam eşleşme
            if q_l in full:
                return 1
            # Başlık sorgunun başında
            if title.startswith(q_l[:max(3, len(q_l)//2)]):
                return 2
            # Tüm sorgu kelimeleri tam metinde var
            if q_words and all(w in full for w in q_words):
                return 3
            # Sorgu kelimelerinin çoğu var
            if q_words:
                matched = sum(1 for w in q_words if w in full)
                if matched >= max(1, len(q_words) - 1):
                    return 4
            return 5

        try:
            return sorted(results, key=_score)
        except Exception:
            return results


    def _search_worker(self, q: str):
        flt = self._search_filter
        try:
            if flt == "songs":
                res = self._yt_search(q, filter="songs", limit=30)
                res = self._rank_search(res, q)
                # Alaka puanı 5 (hiç eşleşme yok) olanları filtrele
                # eğer daha alakalı sonuç varsa
                q_l = q.lower().strip()
                q_words = q_l.split()
                def _score_check(track):
                    title = (track.get("title") or "").lower()
                    arts = " ".join(
                        a.get("name", "") for a in (track.get("artists") or [])
                    ).lower()
                    full = f"{arts} {title}"
                    if q_l in title or q_l in full:
                        return True
                    if title.startswith(q_l[:max(3, len(q_l)//2)]):
                        return True
                    if q_words and all(w in full for w in q_words):
                        return True
                    if q_words:
                        matched = sum(1 for w in q_words if w in full)
                        if matched >= max(1, len(q_words) - 1):
                            return True
                    return False
                relevant = [r for r in res if _score_check(r)]
                if len(relevant) >= 5:
                    res = relevant
                elif relevant:
                    res = relevant + [r for r in res if r not in relevant][:10]
            else:
                res = self._yt_search(q, filter=flt, limit=30)
            self.sig.search_done.emit(q, res)
        except Exception as e:
            log.warning("Arama hatası: %s", e)
            self.sig.search_done.emit(q, [])


    def _on_search(self, q, results):
        if self.current_page != "search":
            return
        if q != self._search_cache.get("q"):
            return
        try:
            search_box = getattr(self, "_search_box", None)
            res_ct = getattr(self, "_res_ct", None)
            res_layout = getattr(self, "_res_layout", None)
            if (
                search_box is None or not qt_is_valid(search_box)
                or res_ct is None or not qt_is_valid(res_ct)
                or res_layout is None or not qt_is_valid(res_layout)
            ):
                return
            live_q = search_box.text().strip()
            _ = res_ct.objectName()
        except RuntimeError:
            return
        if q != live_q:
            return
        self._search_cache["results"] = results
        flt = self._search_filter
        if flt == "albums":
            self._list_albums(results, res_ct, res_layout)
        elif flt == "artists":
            self._list_artists(results, res_ct, res_layout)
        elif flt == "playlists":
            self._list_playlists(results, res_ct, res_layout)
        else:
            self._list_tracks(results, res_ct, res_layout)


    def _quick_search(self, q: str):
        self.page_search()
        search_box = getattr(self, "_search_box", None)
        if search_box is None or not qt_is_valid(search_box):
            return
        search_box.setText(q)
        self._hide_search_suggestions()
        self._do_search()


    def _switch_search_filter(self, key: str):
        if self._search_filter == key:
            return
        self._search_filter = key
        # Chip stillerini güncelle
        from core.theme import get_accent
        from pages.search import _chip_ss
        acc = get_accent()
        for k, btn in self._search_filter_btns.items():
            try:
                if qt_is_valid(btn):
                    btn.setStyleSheet(_chip_ss(k == key, acc))
            except RuntimeError:
                pass
        # Sonuç listesini temizle ve yeniden ara
        q = getattr(self, "_search_box", None)
        q = q.text().strip() if q and qt_is_valid(q) else ""
        if not q:
            return
        res_layout = getattr(self, "_res_layout", None)
        if res_layout and qt_is_valid(res_layout):
            self._clear_layout(res_layout)
            lbl = QLabel(self._tr("search.loading"))
            lbl.setStyleSheet(f"color:{get_accent()}; font-size:14px; background:transparent;")
            res_layout.addWidget(lbl)
        self._net_pool.submit(self._search_worker, q)


    def _fetch_cat(self, q, ft, ct, ld):
        try:
            if ft == "songs":
                res = self._fetch_feed_results(q, limit=80)
            else:
                res = self._yt_search(q, filter=ft, limit=50)
            self.sig.home_section_done.emit(res, ct, ld)
        except Exception as e:
            log.warning("Kategori yüklenemedi: %s", e)
            self.sig.home_section_done.emit([], ct, ld)

    # ══════════════════════════════════════════════════════════════════════════
    # ARAMA SONUÇ RENDER (albüm / sanatçı / playlist)
    # ══════════════════════════════════════════════════════════════════════════

    def _list_albums(self, items, container, layout):
        self._clear_layout(layout)
        if not items:
            empty = QLabel(self._tr("search.empty.albums"))
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet(f"color:{TEXT_MUTED}; font-size:14px; background:transparent;")
            layout.addWidget(empty)
            return
        acc = get_accent()
        for i, item in enumerate(items):
            row = ClickableFrame()
            row.setObjectName("TrackRow")
            row.setFixedHeight(76)
            row.setFocusPolicy(Qt.NoFocus)
            row.setStyleSheet(
                f"QFrame#TrackRow{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0, "
                f"stop:0 {BG_CARD}, stop:1 {BG_ELEVATED}); border-radius:16px; "
                f"border:1px solid {BORDER_COLOR};}}"
                f"QFrame#TrackRow:hover{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0, "
                f"stop:0 {BG_CARD_HOVER}, stop:1 {BG_ELEVATED}); border-color:{acc}44;}}")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(12, 10, 12, 10)
            rl.setSpacing(12)

            num_lbl = QLabel(str(i + 1))
            num_lbl.setFixedWidth(28)
            num_lbl.setAlignment(Qt.AlignCenter)
            num_lbl.setStyleSheet(f"color:{TEXT_MUTED}; font-size:12px; background:transparent;")
            num_lbl.setFocusPolicy(Qt.NoFocus)

            img = TrackCoverWidget(52, 52, radius=6)
            img.setFocusPolicy(Qt.NoFocus)
            thumb = self._thumb(item, big=True)
            if thumb:
                self._load_image(thumb, img, (52, 52))
            else:
                try:
                    img.setPixmap(create_icon("album", TEXT_MUTED, 32).pixmap(32, 32))
                except Exception as _e:
                    log.debug("Sessiz hata: %s", _e)

            inf = QWidget()
            inf.setStyleSheet("background:transparent;")
            inf.setFocusPolicy(Qt.NoFocus)
            il = QVBoxLayout(inf)
            il.setContentsMargins(0, 0, 0, 0)
            il.setSpacing(3)
            tl = QLabel(item.get("title") or self._tr("common.unknown_title"))
            tl.setStyleSheet(
                f"font-weight:800; color:{TEXT_PRIMARY}; font-size:14px; background:transparent;")
            tl.setFocusPolicy(Qt.NoFocus)
            artists = item.get("artists") or []
            artist_str = ", ".join(
                a.get("name", "") for a in artists if a.get("name")
            ) if isinstance(artists, list) else str(artists)
            year = item.get("year") or ""
            sub = f"{artist_str}  •  {year}" if year else artist_str
            al = QLabel(sub or self._tr("common.unknown_artist"))
            al.setStyleSheet(f"color:{TEXT_MUTED}; font-size:11px; background:transparent;")
            al.setFocusPolicy(Qt.NoFocus)
            il.addWidget(tl)
            il.addWidget(al)

            type_badge = QLabel(self._tr("search.result.album"))
            type_badge.setStyleSheet(
                f"color:{acc}; font-size:10px; font-weight:700; background:transparent;")
            type_badge.setFocusPolicy(Qt.NoFocus)

            rl.addWidget(num_lbl)
            rl.addWidget(img)
            rl.addWidget(inf, 1)
            rl.addWidget(type_badge)

            browse_id = item.get("browseId", "")
            artist_name = artist_str.split(",")[0].strip() if artist_str else ""
            title = item.get("title") or ""
            row.clicked.connect(
                lambda _b=browse_id, _a=artist_name, _t=title:
                self._open_artist_album(_a, _t, _b)
            )
            row.setContextMenuPolicy(Qt.CustomContextMenu)
            layout.addWidget(row)
        layout.addStretch()

    def _list_artists(self, items, container, layout):
        self._clear_layout(layout)
        if not items:
            empty = QLabel(self._tr("search.empty.artists"))
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet(f"color:{TEXT_MUTED}; font-size:14px; background:transparent;")
            layout.addWidget(empty)
            return
        acc = get_accent()
        for i, item in enumerate(items):
            row = ClickableFrame()
            row.setObjectName("TrackRow")
            row.setFixedHeight(76)
            row.setFocusPolicy(Qt.NoFocus)
            row.setStyleSheet(
                f"QFrame#TrackRow{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0, "
                f"stop:0 {BG_CARD}, stop:1 {BG_ELEVATED}); border-radius:16px; "
                f"border:1px solid {BORDER_COLOR};}}"
                f"QFrame#TrackRow:hover{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0, "
                f"stop:0 {BG_CARD_HOVER}, stop:1 {BG_ELEVATED}); border-color:{acc}44;}}")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(12, 10, 12, 10)
            rl.setSpacing(12)

            num_lbl = QLabel(str(i + 1))
            num_lbl.setFixedWidth(28)
            num_lbl.setAlignment(Qt.AlignCenter)
            num_lbl.setStyleSheet(f"color:{TEXT_MUTED}; font-size:12px; background:transparent;")
            num_lbl.setFocusPolicy(Qt.NoFocus)

            img = TrackCoverWidget(52, 52, radius=26)  # yuvarlak sanatçı fotoğrafı
            img.setFocusPolicy(Qt.NoFocus)
            thumb = self._thumb(item, big=True)
            if thumb:
                self._load_image(thumb, img, (52, 52))
            else:
                try:
                    img.setPixmap(create_icon("person", TEXT_MUTED, 32).pixmap(32, 32))
                except Exception as _e:
                    log.debug("Sessiz hata: %s", _e)

            inf = QWidget()
            inf.setStyleSheet("background:transparent;")
            inf.setFocusPolicy(Qt.NoFocus)
            il = QVBoxLayout(inf)
            il.setContentsMargins(0, 0, 0, 0)
            il.setSpacing(3)
            artist_name = item.get("artist") or item.get("title") or self._tr("common.unknown_title")
            tl = QLabel(artist_name)
            tl.setStyleSheet(
                f"font-weight:800; color:{TEXT_PRIMARY}; font-size:14px; background:transparent;")
            tl.setFocusPolicy(Qt.NoFocus)
            subs = item.get("subscribers") or ""
            al = QLabel(str(subs) if subs else self._tr("search.result.artist"))
            al.setStyleSheet(f"color:{TEXT_MUTED}; font-size:11px; background:transparent;")
            al.setFocusPolicy(Qt.NoFocus)
            il.addWidget(tl)
            il.addWidget(al)

            rl.addWidget(num_lbl)
            rl.addWidget(img)
            rl.addWidget(inf, 1)

            name = artist_name
            row.clicked.connect(lambda _n=name: self._open_artist_name(_n))
            row.setContextMenuPolicy(Qt.CustomContextMenu)
            layout.addWidget(row)
        layout.addStretch()

    def _list_playlists(self, items, container, layout):
        self._clear_layout(layout)
        if not items:
            empty = QLabel(self._tr("search.empty.playlists"))
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet(f"color:{TEXT_MUTED}; font-size:14px; background:transparent;")
            layout.addWidget(empty)
            return
        acc = get_accent()
        for i, item in enumerate(items):
            row = ClickableFrame()
            row.setObjectName("TrackRow")
            row.setFixedHeight(76)
            row.setFocusPolicy(Qt.NoFocus)
            row.setStyleSheet(
                f"QFrame#TrackRow{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0, "
                f"stop:0 {BG_CARD}, stop:1 {BG_ELEVATED}); border-radius:16px; "
                f"border:1px solid {BORDER_COLOR};}}"
                f"QFrame#TrackRow:hover{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0, "
                f"stop:0 {BG_CARD_HOVER}, stop:1 {BG_ELEVATED}); border-color:{acc}44;}}")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(12, 10, 12, 10)
            rl.setSpacing(12)

            num_lbl = QLabel(str(i + 1))
            num_lbl.setFixedWidth(28)
            num_lbl.setAlignment(Qt.AlignCenter)
            num_lbl.setStyleSheet(f"color:{TEXT_MUTED}; font-size:12px; background:transparent;")
            num_lbl.setFocusPolicy(Qt.NoFocus)

            img = TrackCoverWidget(52, 52, radius=6)
            img.setFocusPolicy(Qt.NoFocus)
            thumb = self._thumb(item, big=True)
            if thumb:
                self._load_image(thumb, img, (52, 52))
            else:
                try:
                    img.setPixmap(create_icon("queue_music", TEXT_MUTED, 32).pixmap(32, 32))
                except Exception as _e:
                    log.debug("Sessiz hata: %s", _e)

            inf = QWidget()
            inf.setStyleSheet("background:transparent;")
            inf.setFocusPolicy(Qt.NoFocus)
            il = QVBoxLayout(inf)
            il.setContentsMargins(0, 0, 0, 0)
            il.setSpacing(3)
            tl = QLabel(item.get("title") or self._tr("common.unknown_title"))
            tl.setStyleSheet(
                f"font-weight:800; color:{TEXT_PRIMARY}; font-size:14px; background:transparent;")
            tl.setFocusPolicy(Qt.NoFocus)
            author = item.get("author") or {}
            author_name = author.get("name", "") if isinstance(author, dict) else str(author)
            item_count = item.get("itemCount") or ""
            count_text = self._tr("search.result.tracks", count=item_count) if item_count else ""
            sub = self._tr("search.result.playlist_tracks", author=author_name, count=item_count) if author_name and item_count else (count_text or author_name)
            al = QLabel(sub or "Playlist")
            al.setStyleSheet(f"color:{TEXT_MUTED}; font-size:11px; background:transparent;")
            al.setFocusPolicy(Qt.NoFocus)
            il.addWidget(tl)
            il.addWidget(al)

            play_btn = QPushButton()
            play_btn.setFixedSize(34, 34)
            play_btn.setIcon(create_icon("play", acc, 18))
            play_btn.setIconSize(QSize(18, 18))
            play_btn.setFocusPolicy(Qt.NoFocus)
            play_btn.setCursor(Qt.PointingHandCursor)
            play_btn.setStyleSheet(
                f"QPushButton{{background:transparent; border:none; border-radius:17px;}}"
                f"QPushButton:hover{{background:{acc}22;}}")
            browse_id = item.get("browseId", "")
            play_btn.clicked.connect(
                lambda _b=browse_id: self._net_pool.submit(self._open_playlist_search, _b))

            rl.addWidget(num_lbl)
            rl.addWidget(img)
            rl.addWidget(inf, 1)
            rl.addWidget(play_btn)

            row.clicked.connect(
                lambda _b=browse_id: self._net_pool.submit(self._open_playlist_search, _b))
            row.setContextMenuPolicy(Qt.CustomContextMenu)
            layout.addWidget(row)
        layout.addStretch()

    def _open_playlist_search(self, browse_id: str):
        """Playlist'i aç ve tüm şarkıları kuyruğa ekle."""
        if not browse_id:
            return
        try:
            data = self._yt_get_playlist(browse_id, limit=50)
            raw_tracks = list(data.get("tracks") or [])
            tracks = [t for t in (self._normalize_feed_track(r) for r in raw_tracks) if t]
            if not tracks:
                return
            self.sig.play_all_tracks.emit(tracks)
        except Exception as e:
            log.warning("Playlist açma hatası: %s", e)

    # ══════════════════════════════════════════════════════════════════════════
    # ŞARKI LİSTESİ
    # ══════════════════════════════════════════════════════════════════════════


    def _list_tracks(self, tracks, container, layout, queue_mode=False):
        self._clear_layout(layout)
        if not tracks:
            empty = QLabel(self._tr("search.empty.tracks"))
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet(f"color:{TEXT_MUTED}; font-size:14px; background:transparent;")
            layout.addWidget(empty)
            return

        acc = get_accent()
        fav_vids = {f.get("videoId", "") for f in self.favorites}
        self._prime_stream_urls(tracks, limit=4)
        for i, track in enumerate(tracks):
            row = ClickableFrame()
            row.setObjectName("TrackRow")
            row.setFixedHeight(76)
            # Odak çizgilerini gizlemek için odak politikasını kaldır
            row.setFocusPolicy(Qt.NoFocus)
            row.setStyleSheet(
                f"QFrame#TrackRow{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0, "
                f"stop:0 {BG_CARD}, stop:1 {BG_ELEVATED}); border-radius:16px; "
                f"border:1px solid {BORDER_COLOR};}}"
                f"QFrame#TrackRow:hover{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0, "
                f"stop:0 {BG_CARD_HOVER}, stop:1 {BG_ELEVATED}); border-color:{acc}44;}}")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(12, 10, 12, 10)
            rl.setSpacing(12)

            num_lbl = QLabel(str(i+1))
            num_lbl.setFixedWidth(28)
            num_lbl.setAlignment(Qt.AlignCenter)
            num_lbl.setStyleSheet(
                f"color:{TEXT_MUTED}; font-size:12px; background:transparent;")
            num_lbl.setFocusPolicy(Qt.NoFocus)

            img = TrackCoverWidget(52, 52, radius=6)
            img.setFocusPolicy(Qt.NoFocus)
            # Daha yüksek çözünürlüklü kare kapak tercih etmek için big=True
            thumb = self._thumb(track, big=True)
            if thumb:
                self._load_image(thumb, img, (52, 52))
            else:
                try:
                    fall_pix = create_icon("music", TEXT_MUTED, 32)
                    img.setPixmap(fall_pix.pixmap(32, 32))
                except Exception as _e:
                    log.debug("Sessiz hata: %s", _e)

            inf = QWidget()
            inf.setStyleSheet("background:transparent;")
            inf.setFocusPolicy(Qt.NoFocus)
            il  = QVBoxLayout(inf)
            il.setContentsMargins(0, 0, 0, 0)
            il.setSpacing(3)
            tl = QLabel(track.get("title", self._tr("common.unknown_title")))
            tl.setStyleSheet(
                f"font-weight:800; color:{TEXT_PRIMARY}; font-size:14px; background:transparent;")
            tl.setFocusPolicy(Qt.NoFocus)
            al = QLabel(self._artist_str(track))
            al.setStyleSheet(
                f"color:{TEXT_MUTED}; font-size:11px; background:transparent;")
            al.setFocusPolicy(Qt.NoFocus)
            il.addWidget(tl)
            il.addWidget(al)

            vid = track.get("videoId", "")
            if self.dl.is_downloaded(vid):
                dl_badge = QLabel("offline")
                dl_badge.setStyleSheet(
                    f"color:{acc}; font-size:11px; font-weight:700; background:transparent;")
                il.addWidget(dl_badge)

            bf  = QWidget()
            bf.setStyleSheet("background:transparent;")
            bf.setFocusPolicy(Qt.NoFocus)
            bl  = QHBoxLayout(bf)
            bl.setSpacing(4)
            bl.setContentsMargins(0, 0, 0, 0)

            is_fav = vid in fav_vids
            bh = QPushButton()
            bh.setFixedSize(34, 34)
            bh.setIcon(create_icon(
                "heart_on" if is_fav else "heart_off",
                acc if is_fav else TEXT_MUTED, 18))
            bh.setStyleSheet(
                f"QPushButton{{border:1px solid transparent; background:transparent; border-radius:15px;}}"
                f"QPushButton:hover{{background:{BG_CARD_HOVER}; border-color:{acc}22;}}")
            bh.setFocusPolicy(Qt.NoFocus)
            bh.clicked.connect(lambda _, t=track, b=bh: self._toggle_fav(t, b))
            # Ara sayfası kalp senkronu için kaydet
            if not hasattr(self, "_search_fav_buttons"):
                self._search_fav_buttons = {}
            self._search_fav_buttons.setdefault(vid, []).append(bh)

            pct = self._dl_progress.get(vid)
            if pct is not None and pct < 100:
                from PySide6.QtWidgets import QProgressBar
                pb = QProgressBar()
                pb.setRange(0, 100)
                pb.setValue(pct)
                pb.setFixedSize(64, 8)
                pb.setFocusPolicy(Qt.NoFocus)
                bl.addWidget(pb)
            else:
                bp = QPushButton()
                bp.setFixedSize(26, 26)
                acc_now = get_accent()
                bp.setIcon(create_icon("play", acc_now, 18))
                bp.setIconSize(QSize(18, 18))
                bp.setFocusPolicy(Qt.NoFocus)
                bp.setCursor(Qt.PointingHandCursor)
                # Şeffaf arka plan: sadece yeşil ikon görünür, hover'da çok hafif tint
                bp.setStyleSheet(
                    f"QPushButton{{background:transparent; border:none; border-radius:13px;}}"
                    f"QPushButton:hover{{background:{acc_now}22;}}"
                )
                bp.clicked.connect(lambda _, t=track: self.force_play(t))
                bl.addWidget(bp)

            bl.addWidget(bh)

            # queue_mode: ↑↓ butonlar kaldırıldı — queue sayfasında drag & drop var

            rl.addWidget(num_lbl)
            rl.addWidget(img)
            rl.addWidget(inf, 1)
            rl.addWidget(bf)

            row.clicked.connect(lambda t=track: self.force_play(t))
            row.setContextMenuPolicy(Qt.CustomContextMenu)
            row.customContextMenuRequested.connect(
                lambda _, t=track: self._ctx_menu(QCursor.pos(), t))
            layout.addWidget(row)
        layout.addStretch()

    # ══════════════════════════════════════════════════════════════════════════
    # MÜZİK ÇALMA MOTORU
    # ══════════════════════════════════════════════════════════════════════════


    def force_play(self, track: dict):
        # Geçerli parçanın küçük resmi eksik olabilir; queue'ya eklemeden önce
        # `_thumb` çağrısı yaparak `thumbnails` alanını doldurun.
        try:
            _ = self._thumb(track)
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
        # Yarış koşulu koruması: VLC Ended geldiğinde otomatik ileri geçişi engelle
        try:
            import time as _t
            self._manual_play_ts = _t.monotonic()
        except Exception:
            pass
        # Şarkı zaten kuyrukta varsa sadece o pozisyona geç, radyo yeniden başlatma
        vid = track.get("videoId", "")
        for i, qt in enumerate(self.queue):
            if qt.get("videoId") == vid:
                self.queue_index = i
                self._play(track, force_radio=False)
                try:
                    self.sig.player_ui_update.emit()
                except Exception as _e:
                    log.debug("Sessiz hata: %s", _e)
                return
        # Kuyrukta yoksa yeni tek şarkılık kuyruk oluştur ve radyo başlat
        self.queue       = [track]
        self.queue_index = 0
        self._radio_queue_vids.clear()
        # Start playback immediately
        self._play(track, force_radio=True)
        # Emit UI update so that home page and mini player reflect the new state
        try:
            self.sig.player_ui_update.emit()
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)


    def play(self, track: dict):
        """Kuyruğa ekleyip çal (force_play gibi ama radyo açmaz)."""
        # Eksik küçük resim bilgilerini doldur
        try:
            _ = self._thumb(track)
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)
        if track not in self.queue:
            self.queue.append(track)
            self.queue_index = len(self.queue) - 1
        vid = track.get("videoId", "")
        if vid:
            self._radio_queue_vids.discard(vid)
        self._play(track)
        # Trigger an immediate UI refresh to update play/pause icons and cover
        try:
            self.sig.player_ui_update.emit()
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)

    def _pixmap_cache_get(self, key):
        with self._pixmap_lock:
            pixmap = self._pixmap_mem.get(key)
            if pixmap is not None:
                self._pixmap_mem.move_to_end(key)
            return pixmap


    def _pixmap_cache_set(self, key, pixmap):
        if pixmap is None:
            return
        with self._pixmap_lock:
            self._pixmap_mem[key] = pixmap
            self._pixmap_mem.move_to_end(key)
            while len(self._pixmap_mem) > self._pixmap_mem_max:
                self._pixmap_mem.popitem(last=False)


    def _load_image(self, url: str, label, size: tuple):
        key = (str(url or ""), int(size[0]), int(size[1]))
        cached = self._pixmap_cache_get(key)
        if cached is not None:
            try:
                if label and qt_is_valid(label):
                    label.setPixmap(cached)
            except Exception as _e:
                log.debug("Sessiz hata: %s", _e)
            return

        with self._pixmap_lock:
            waiters = self._pixmap_waiters.setdefault(key, [])
            if label is not None:
                waiters.append(label)
            if key in self._pixmap_pending:
                return
            self._pixmap_pending.add(key)

        def _task():
            img = self._img_cache.get_or_load(url, size, self._http)
            self.sig.image_loaded.emit(key, img)
        self._img_pool.submit(_task)


    def _on_image(self, target, qimage):
        try:
            from PySide6.QtGui import QPixmap
            if isinstance(target, tuple) and len(target) == 3:
                with self._pixmap_lock:
                    labels = list(self._pixmap_waiters.pop(target, []))
                    self._pixmap_pending.discard(target)
                if qimage is None or getattr(qimage, "isNull", lambda: True)():
                    return
                pixmap = QPixmap.fromImage(qimage)
                self._pixmap_cache_set(target, pixmap)
                for label in labels:
                    try:
                        if label and qt_is_valid(label):
                            label.setPixmap(pixmap)
                    except Exception as _e:
                        log.debug("Sessiz hata: %s", _e)
                return
            if target:
                target.setPixmap(QPixmap.fromImage(qimage))
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)

    # ══════════════════════════════════════════════════════════════════════════
    # RADYO
    # ══════════════════════════════════════════════════════════════════════════


    def _is_stale_radio_request(self, expected_request_id: int | None = None) -> bool:
        if expected_request_id is None:
            return False
        return expected_request_id != getattr(self, "_play_request_id", -1)


    def _fetch_radio(self, vid: str, expected_request_id: int | None = None) -> int:
        if not vid:
            return 0
        if self._is_stale_radio_request(expected_request_id):
            return 0
        try:
            w = self._yt_get_watch_playlist(vid, limit=30)
            if self._is_stale_radio_request(expected_request_id):
                return 0
            if "tracks" in w:
                new = []
                with self._queue_lock:
                    if self._is_stale_radio_request(expected_request_id):
                        return 0
                    existing_vids = {t.get("videoId") for t in self.queue}
                    for t in w["tracks"]:
                        tid = t.get("videoId", "")
                        if tid and tid not in existing_vids:
                            # Oluşturulan sözlük, eksik kapak fotoğrafı durumunda
                            # fallback URL'leri içerecek şekilde _thumb ile
                            # zenginleştirilecek. Bu, radyo listesinden gelen
                            # şarkılarda kapak fotoğraflarının boş kalmasını
                            # engeller.
                            arts = t.get("artists") or [{"name": "?"}]
                            t_dict = {
                                "videoId":    tid,
                                "title":      t.get("title", "?"),
                                "artists":    arts,
                                "thumbnails": t.get("thumbnails", []),
                            }
                            # Eksik küçük resim bilgilerini doldur.
                            try:
                                _ = self._thumb(t_dict)
                            except Exception as _e:
                                log.debug("Sessiz hata: %s", _e)
                            new.append(t_dict)
                            existing_vids.add(tid)
                    if new:
                        radio_tail = new
                        self.queue.extend(radio_tail)
                        self._radio_queue_vids.update(
                            t.get("videoId", "")
                            for t in radio_tail
                            if t.get("videoId", "")
                        )
                if new:
                    try:
                        self._collab_emit_upcoming()
                    except Exception as e:
                        log.debug("Collab upcoming yayini hatasi: %s", e)
                    self.sig.notify.emit(self._tr("player.radio_added", count=len(new) - 1))
                    return len(new)
        except Exception as e:
            log.debug("Radyo hatası: %s", e)
        return 0


    def _request_auto_next_from_radio(self, token: int, vid: str, request_id: int):
        added = self._fetch_radio(vid, expected_request_id=request_id) > 0
        self.sig.auto_next_ready.emit(token, added)


    def _on_auto_next_ready(self, token: int, added: bool):
        if token != self._auto_next_token or not added:
            return
        if not self.queue:
            return
        if 0 <= self.queue_index < len(self.queue) - 1:
            self.queue_index += 1
            if 0 <= self.queue_index < len(self.queue):
                self._play(self.queue[self.queue_index])

    def _on_history_updated(self):
        try:
            from pages import home_clean
            cache = getattr(self, "_home_cache", None)
            if cache is not None:
                cache.pop("__home_bundle::personal", None)
            refs = getattr(self, "_home_refs", None)
            if refs and getattr(self, "current_page", None) == "home":
                personal = refs.get("personal")
                if personal is not None and qt_is_valid(personal):
                    home_clean._render_personal(self)
        except Exception as _e:
            log.debug("Sessiz hata: %s", _e)

    # ══════════════════════════════════════════════════════════════════════════
    # ŞARKI SÖZLERİ
    # ══════════════════════════════════════════════════════════════════════════
