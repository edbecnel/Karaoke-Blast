# Karaoke Blast

Full-screen karaoke video player and manager. Open a local folder of videos and play them in alphabetical order.

## Requirements

- Python 3.11+
- [VLC media player](https://www.videolan.org/vlc/) installed on your system

### Install VLC

| Platform | Command |
|---|---|
| macOS | `brew install vlc` |
| Windows | Download from [videolan.org](https://www.videolan.org/vlc/) |
| Linux | `sudo apt install vlc` (or your distro's package manager) |

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
python -m karaoke_blast
```

Open a folder containing video files (`.mp4`, `.mkv`, `.avi`, `.mov`, `.webm`, `.m4v`) and playback starts automatically in full screen. Recently opened folders appear on the startup screen for quick access.

### CLI

```bash
python -m karaoke_blast --folder /path/to/videos
```

## Keyboard Shortcuts

| Key | Action |
|---|---|
| `Space` | Play / pause |
| `S` | Stop |
| `→` or `N` | Next song |
| `←` or `P` | Previous song |
| `,` or `[` | Rewind 10 seconds |
| `.` or `]` | Fast forward 10 seconds |
| `M` | Mute / unmute |
| `+` / `↑` | Volume up |
| `-` / `↓` | Volume down |
| `O` | Open a different folder |
| `L` | Toggle song list |
| `F` or `F11` | Toggle full screen |
| `Esc` | Exit full screen (or quit if already windowed) |
| `Q` | Quit |

Move the mouse during playback to reveal the on-screen control bar. Use the play/pause toggle on the control bar, or press `Space`, to play and pause.

## Song List

When a folder is loaded, a song list panel appears on the left. Click a song once to select it, then click it again to start playback. Use the sort dropdown to reorder by:

- Name (A → Z / Z → A)
- Date modified (oldest / newest first)

Press `L` or click **☰** on the control bar to show or hide the song list. You can also click **×** at the top of the song list panel.

Right-click any song and choose **Play Next** to queue it after the current song finishes. Queued songs appear in the **Queue** panel above the list — click **×** on a song to remove it, or **Clear** to empty the queue. You can also right-click a queued song and choose **Remove from Queue**. Toggle **Current + queue** to show only the playing song and queued songs; the filter turns off automatically when the queue is empty.

## Roadmap

- Custom playlists and sort order
- Per-song properties and custom graphics
- Persistent storage for playlists and settings
- Recursive subfolder scanning
- Song manager panel
