"""Geriye dönük uyumluluk — tüm dialog bileşenlerini alt modüllerden dışa aktarır."""
from ui.lyrics_delegate import LyricsDelegate
from ui.equalizer import open_eq_dialog
from ui.lyrics import open_lyrics_dialog
from ui.sleep_timer import open_sleep_dialog
from ui.toast import show_toast
from ui.download_settings import open_download_settings_dialog

__all__ = [
    "LyricsDelegate",
    "open_eq_dialog",
    "open_lyrics_dialog",
    "open_sleep_dialog",
    "show_toast",
    "open_download_settings_dialog",
]
