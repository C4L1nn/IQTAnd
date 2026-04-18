"""Mixin classes for IqtMusic application."""

from core.mixins.player import PlayerMixin
from core.mixins.queue import QueueMixin
from core.mixins.ytmusic import YtmusicMixin
from core.mixins.feed import FeedMixin
from core.mixins.navigation import NavigationMixin
from core.mixins.discord import DiscordMixin
from core.mixins.stats import StatsMixin
from core.mixins.playlist import PlaylistMixin
from core.mixins.lyrics import LyricsMixin
from core.mixins.mini_player import MiniPlayerMixin
from core.mixins.artist import ArtistMixin
from core.mixins.context_menu import ContextMenuMixin
from core.mixins.ui_config import UiConfigMixin
from core.mixins.resize import ResizeMixin
from core.mixins.persistence import PersistenceMixin
from core.mixins.collab import CollabMixin

__all__ = [
    'PlayerMixin',
    'QueueMixin',
    'YtmusicMixin',
    'FeedMixin',
    'NavigationMixin',
    'DiscordMixin',
    'StatsMixin',
    'PlaylistMixin',
    'LyricsMixin',
    'MiniPlayerMixin',
    'ArtistMixin',
    'ContextMenuMixin',
    'UiConfigMixin',
    'ResizeMixin',
    'PersistenceMixin',
    'CollabMixin',
]
