from PySide6.QtCore import QObject, Signal


class Signals(QObject):
    image_loaded = Signal(object, object)
    search_done = Signal(str, list)
    lyrics_done = Signal(str, int, list)
    home_section_done = Signal(list, object, object)
    artists_overview_done = Signal(object)
    player_ui_update = Signal()
    notify = Signal(object)
    artist_songs_done = Signal(list, str, object)
    artist_album_done = Signal(list, str, str, object)
    stats_updated = Signal(dict)
    auto_next_ready = Signal(int, bool)
    audio_url_ready = Signal(object, str, int)
    crossfade_start = Signal(str)
    rate_apply_deferred = Signal(float, int)
    audio_output_apply_deferred = Signal(int, int)
    restore_pos_deferred = Signal(str, int)
    media_key_action = Signal(str)
    collab_sync = Signal(object)
    collab_control = Signal(object)
    collab_status = Signal(str, str)
    collab_join_request = Signal()  # Host'a Discord katılma isteği geldiğinde
    play_all_tracks = Signal(list)
    history_updated = Signal()
