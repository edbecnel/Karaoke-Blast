from karaoke_blast.player.controls_bar import ControlsBar
from karaoke_blast.player.video_widget import VideoWidget

__all__ = ["ControlsBar", "VideoWidget"]

def __getattr__(name: str):
    if name == "VlcPlayer":
        from karaoke_blast.player.vlc_player import VlcPlayer

        return VlcPlayer
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
