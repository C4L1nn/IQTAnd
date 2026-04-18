# pages paketi

from pages.common import _build_page_header, _scrollable, _back_btn
from pages.search import build_search_page
from pages.category import build_category_page
from pages.favorites import build_favs_page
from pages.downloads import build_downloads_page
from pages.playlist import build_playlist_page, _populate_playlist_tracks
from pages.playlists_overview import build_playlists_overview_page
from pages.queue import build_queue_page, _rebuild_queue_list
from pages.artist import build_artist_page, build_artist_album_page
from pages.artists import build_artists_page
from pages.stats import build_stats_page

__all__ = [
    "build_search_page",
    "build_category_page",
    "build_favs_page",
    "build_downloads_page",
    "build_playlist_page",
    "build_queue_page",
    "build_artist_page",
    "build_artist_album_page",
    "build_artists_page",
    "build_stats_page",
    "build_playlists_overview_page",
    "_build_page_header",
    "_scrollable",
    "_back_btn",
    "_populate_playlist_tracks",
    "_rebuild_queue_list",
]
