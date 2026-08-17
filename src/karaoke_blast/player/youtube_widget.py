"""Embedded YouTube iframe player."""

import json

from PyQt6.QtCore import QObject, QUrl, pyqtSignal, pyqtSlot
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QWidget


class _YouTubeBridge(QObject):
    video_ended = pyqtSignal()

    @pyqtSlot()
    def videoEnded(self) -> None:
        self.video_ended.emit()


class YouTubeWidget(QWebEngineView):
    """QWebEngineView that renders a borderless YouTube iframe player."""

    playback_ended = pyqtSignal()
    playback_error = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet("background-color: black;")
        self.page().setBackgroundColor(self.palette().color(self.backgroundRole()))
        self._bridge = _YouTubeBridge(self)
        self._bridge.video_ended.connect(self.playback_ended)
        self._channel = QWebChannel(self.page())
        self._channel.registerObject("bridge", self._bridge)
        self.page().setWebChannel(self._channel)
        self._current_video_id: str | None = None
        self._volume = 80
        self._muted = False
        self.page().loadFinished.connect(self._on_load_finished)

    def load_video(self, video_id: str, *, volume: int = 80, muted: bool = False) -> None:
        self._current_video_id = video_id
        self._volume = max(0, min(100, volume))
        self._muted = muted
        self.setHtml(
            _player_html(video_id, volume=self._volume, muted=self._muted),
            QUrl("https://karaoke-blast.local/"),
        )

    def clear(self) -> None:
        if self._current_video_id is not None:
            self.page().runJavaScript(
                "if (window.player && window.player.stopVideo) {"
                " window.player.stopVideo(); }"
            )
        self._current_video_id = None
        self.setHtml(_blank_html(), QUrl("about:blank"))

    def set_volume(self, volume: int) -> None:
        self._volume = max(0, min(100, volume))
        self._run_player_js(f"window.setPlayerVolume({self._volume});")

    def set_mute(self, muted: bool) -> None:
        self._muted = muted
        self._run_player_js("window.setPlayerMuted(true);" if muted else "window.setPlayerMuted(false);")

    def _run_player_js(self, script: str) -> None:
        if self._current_video_id is None:
            return
        self.page().runJavaScript(script)

    def _on_load_finished(self, ok: bool) -> None:
        if not ok and self._current_video_id is not None:
            self.playback_error.emit("Could not load the YouTube player.")


def _player_html(video_id: str, *, volume: int, muted: bool) -> str:
    origin = "https://karaoke-blast.local"
    config = json.dumps(
        {
            "videoId": video_id,
            "volume": volume,
            "muted": muted,
            "playerVars": {
                "autoplay": 1,
                "rel": 0,
                "modestbranding": 1,
                "enablejsapi": 1,
                "playsinline": 1,
                "origin": origin,
            },
        }
    )
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    html, body {{
      margin: 0;
      padding: 0;
      width: 100%;
      height: 100%;
      background: #000;
      overflow: hidden;
    }}
    #player {{
      width: 100%;
      height: 100%;
    }}
  </style>
  <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
  <script src="https://www.youtube.com/iframe_api"></script>
</head>
<body>
  <div id="player"></div>
  <script>
    const playerConfig = {config};
    let bridge = null;
    window.player = null;

    window.setPlayerVolume = function(volume) {{
      if (window.player && window.player.setVolume) {{
        window.player.setVolume(volume);
      }}
    }};

    window.setPlayerMuted = function(muted) {{
      if (!window.player) return;
      if (muted && window.player.mute) window.player.mute();
      else if (!muted && window.player.unMute) window.player.unMute();
    }};

    window.applyPlayerAudio = function() {{
      window.setPlayerVolume(playerConfig.volume);
      window.setPlayerMuted(playerConfig.muted);
    }};

    new QWebChannel(qt.webChannelTransport, function(channel) {{
      bridge = channel.objects.bridge;
    }});

    function onYouTubeIframeAPIReady() {{
      window.player = new YT.Player("player", {{
        videoId: playerConfig.videoId,
        playerVars: playerConfig.playerVars,
        events: {{
          onReady: function() {{
            window.applyPlayerAudio();
          }},
          onStateChange: function(event) {{
            if (event.data === YT.PlayerState.ENDED && bridge) {{
              bridge.videoEnded();
            }}
          }}
        }}
      }});
    }}
  </script>
</body>
</html>"""


def _blank_html() -> str:
    return """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    html, body { margin: 0; padding: 0; background: #000; }
  </style>
</head>
<body></body>
</html>"""
