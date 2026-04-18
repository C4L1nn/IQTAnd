"""Geriye dönük uyumluluk modülü — tüm sayfa oluşturucuları alt modüllerden yeniden dışa aktarır."""

from pages.common import _build_page_header, _scrollable, _back_btn
from pages.search import build_search_page
from pages.category import build_category_page
from pages.favorites import build_favs_page
from pages.downloads import build_downloads_page
from pages.playlist import build_playlist_page, _populate_playlist_tracks
from pages.playlists_overview import build_playlists_overview_page
from pages.queue import build_queue_page, _rebuild_queue_list, _QueueTrackRow, _DragQueueList
from pages.artist import (
    build_artist_page, build_artist_album_page,
    _fmt_artist_metric, _find_artist_track_by_name,
    _artist_visual_widget, _artist_profile_hero, _artist_popular_panel,
    _artist_album_items, _artist_albums_strip,
    _artist_similar_strip, _artist_about_card, _lbl, _name_color, _HeroBg
)
from pages.artists import build_artists_page, _artist_overview_card
from pages.stats import build_stats_page, _MiniBarChart, _make_animated_stat_card, _stats_period_text

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
    "_QueueTrackRow",
    "_DragQueueList",
    "_artist_overview_card",
    "_MiniBarChart",
    "_make_animated_stat_card",
    "_stats_period_text",
    "_fmt_artist_metric",
    "_find_artist_track_by_name",
    "_artist_visual_widget",
    "_artist_profile_hero",
    "_artist_popular_panel",
    "_artist_album_items",
    "_artist_albums_strip",
    "_artist_similar_strip",
    "_artist_about_card",
    "_lbl",
    "_name_color",
    "_HeroBg",
]
