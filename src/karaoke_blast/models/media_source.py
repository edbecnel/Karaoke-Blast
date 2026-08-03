"""Media source mode for local vs YouTube playback."""

from enum import Enum


class MediaSourceMode(Enum):
    LOCAL = "local"
    YOUTUBE = "youtube"
