<p align="center">
  <img src="src/karaoke_blast/assets/logo.png" alt="Karaoke Blast logo" width="240">
</p>

# Karaoke Blast

Full-screen karaoke video player and manager. Open a local folder of videos and play them in alphabetical order, or search YouTube for karaoke tracks and play them in an embedded player.

## Requirements

### Install manually (system)

These must be installed on the machine before running the app:

| Dependency | Why | macOS | Windows | Linux |
|---|---|---|---|---|
| Python 3.11+ | Runs the app | `brew install python@3.12` (or any 3.11+) | [python.org](https://www.python.org/downloads/) | Distro package manager |
| [VLC](https://www.videolan.org/vlc/) | Local file playback (`python-vlc`) | `brew install vlc` | Download from [videolan.org](https://www.videolan.org/vlc/) | `sudo apt install vlc` (or your distro's package manager) |
| [ffmpeg](https://ffmpeg.org/) on PATH | Merge YouTube video + audio when downloading | `brew install ffmpeg` | Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH | `sudo apt install ffmpeg` (or your distro's package manager) |

### Python packages (`pip install -e .`)

These are installed automatically into your virtualenv when you run Quick Start below:

| Package | Purpose |
|---|---|
| PyQt6 | Desktop UI |
| PyQt6-WebEngine | Embedded YouTube player |
| python-vlc | Local playback (requires VLC installed on the system) |
| yt-dlp | YouTube search and download |
| mutagen | Read/write media tags and metadata song-list labels |

If you already have a virtualenv from an older checkout, re-run `pip install -e .` so newer dependencies (such as mutagen) are installed.

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
python -m karaoke_blast
```

Open a folder containing video or audio files (`.mp4`, `.mkv`, `.avi`, `.mov`, `.webm`, `.m4v`, `.mp3`, `.m4a`, `.aac`, `.flac`, `.wav`, `.ogg`, `.opus`, `.wma`) — including folders that only have media in subfolders — and the player opens in full screen. Recently opened folders appear on the startup screen for quick access. Right-click a recent folder and choose **Remove from List** to hide it from the list.

You can also click **Search YouTube** on the startup screen to find and play karaoke videos online without downloading them first.

### CLI

```bash
python -m karaoke_blast --folder /path/to/videos
```

## Keyboard Shortcuts

| Key | Action |
|---|---|
| `Space` | Play / pause (local files) |
| `S` | Stop |
| `→` or `N` | Next song / next queued YouTube video |
| `←` or `P` | Previous song |
| `,` or `[` | Rewind 10 seconds |
| `.` or `]` | Fast forward 10 seconds |
| `M` | Mute / unmute (local and YouTube) |
| `+` / `↑` | Volume up (local and YouTube) |
| `-` / `↓` | Volume down (local and YouTube) |
| `O` | Open a different folder |
| `Y` | Open YouTube search (or focus search when in YouTube mode) |
| `L` | Toggle song list / YouTube panel |
| `⌂` (Start menu button) | Return to the start screen |
| `F` or `F11` | Toggle full screen |
| `Esc` | Exit full screen (or quit if already windowed) |
| `Q` | Quit |

Move the mouse during playback to reveal the on-screen control bar. Use the play/pause toggle on the control bar, or press `Space`, to play and pause local files.

## Song List

When a folder is loaded, a song list panel appears on the left. Subfolders that contain videos are listed with a trailing `/` — click one to drill down, or use **‥ Up** to go back (within the folder you opened). Click a song once to select it, then click it again to start playback. Use the **⋯** menu for **Play all under this folder** or **Queue all under this folder** (includes nested subfolders). After Play all, use **←** or **Back to folders** to return to hierarchical browsing. Use the sort dropdown to reorder by:

- Name (A → Z / Z → A)
- Date modified (oldest / newest first)

Toggle **Metadata** to show embedded title, artist, and comments instead of file names (songs without a title still show the file name). Use **⚙** next to it to set the field order and separators. Search matches metadata first, then the file name. The same display mode applies to the queue, **Current + queue**, and History.

Press `L` or click **☰** on the control bar to show or hide the song list. You can also click **×** at the top of the song list panel.

Right-click any song and choose **Play Next** to queue it after the current song finishes. Queued songs appear in the **Queue** panel above the list — click **×** on a song to remove it, or **Clear** to empty the queue. You can also right-click a queued song and choose **Remove from Queue**. Toggle **Current + queue** to show only the playing song and queued songs; the filter turns off automatically when the queue is empty. Right-click a song in the list, queue, **Current + queue**, or History and choose **Edit Metadata…** to change Song Title, Artist Name, and Comments (supported formats only).

Use the **History** tab to see recently played songs from any folder. Double-click to play, or right-click for **Play Now**, **Play Next**, **Edit Metadata…**, or **Remove from History**. Click **Clear** to empty the history list. History is saved across sessions.

## Batch Rename

Use **Rename Downloads** on the startup screen (or right-click a song in the song list) to rename video files with a configurable format.

The format uses **four reorderable slots** with a separator between each position:

- **Song Name** (required at rename time)
- **Artist Name** (optional)
- Two **additional** slots (optional, customizable labels)

By default the pattern is `{Song Name} - {Artist Name} - {Karaoke}` with a fourth slot disabled. Use **↑** / **↓** in the format editor to change slot order, checkboxes to enable or disable slots, and separator fields between rows to customize spacing. For additional slots, set **Hint or default value** and check **Fixed** to pre-fill that value when renaming (like the old Karaoke suffix); you can still change it per file. Only **Song Name** must be filled when renaming; empty optional slots are omitted from the filename.

Settings are saved in `settings.json` under `filename_rename`. Legacy two-slot + suffix settings are migrated automatically on load.

## Tag Metadata

Use **Tag Metadata** on the startup screen to write embedded **Title**, **Artist**, and optional **Comment** tags from filename slots — without renaming files.

1. Choose a folder and the same four-slot filename format used for Batch Rename.
2. Check which slots should be copied into the **Comments** property (for example a fixed **Karaoke** slot).
3. Optionally auto-fill slots from the filename and skip files that already have Title and Artist.
4. Review each file one at a time with the same part-chip UI as rename, then **Apply Metadata & Next** or **Skip**.

Supported containers: MP3, MP4/M4A/M4V, FLAC, OGG/Opus, and WAV. Unsupported types (for example some MKV/WebM/AVI files) are skipped and counted in the summary. Preferences are saved in `settings.json` (`metadata_comment_slot_indices`, `metadata_auto_fill_slots`, `metadata_skip_tagged`); the slot layout reuses `filename_rename`.

## YouTube Streaming

Click **Search YouTube** on the startup screen, or press `Y`, to enter YouTube mode.

### Search

1. Enter a **song** name (required) and optionally an **artist / band**.
2. Leave **Append "karaoke" to search** checked to add `karaoke` to the query when it is not already present, or uncheck it to search for any YouTube video.
3. Click **Search**. Double-click a result to play it, or right-click and choose **Play Next** to queue it.
4. Click **Search more** to load the next 15 results and append them to the list (up to 60 total). A new **Search** clears the list and starts over.

### Paste URL

Switch to the **Paste URL** tab to play a video when you already have a YouTube link or video ID.

### Queue

Queued YouTube videos appear in the **Queue** section at the top of the search panel. When the current video ends, the next queued video plays automatically. Press `N` or click **Next** on the control bar to skip ahead manually. Press `S` or **Stop** to end playback; the queue is kept.

Volume and mute on the control bar work in YouTube mode and share the same saved settings as local playback.

The **History** tab lists recently played YouTube videos with the same play, queue, and remove actions as search results. History persists across sessions and can be cleared with the **Clear** button.

Opening a local folder switches back to local playback and clears the YouTube queue.

### Downloads

Download YouTube videos for offline playback in the local VLC player:

- Right-click a search result, history entry, or queue item and choose **Download**
- Or use the **Download** button on the **Paste URL** tab

Downloads run in the background — you can keep playing and searching YouTube while a download is in progress. Progress, success, and failure are shown in the status area below the queue panel. Only one download runs at a time.

Videos are saved as VLC-compatible **MP4** files (H.264 video + AAC audio when available). By default they go to the app's **YouTube Downloads** folder:

- macOS: `~/Library/Application Support/Karaoke Blast/youtube-downloads`
- Linux: `~/.config/karaoke-blast/youtube-downloads`
- Windows: `%APPDATA%\Karaoke Blast\youtube-downloads`

Use **Change…** on the startup screen or in the YouTube panel (below the download status) to pick a different folder. The choice is saved across sessions. Changing the folder does not move existing downloads.

You can also set the path manually in `settings.json`:

```json
{
  "youtube_downloads_dir": "D:\\Karaoke\\YouTube"
}
```

Omit `youtube_downloads_dir` or set it to `null` to use the default folder above.

**YouTube Downloads** appears as a pinned folder on the startup screen. Click it to open your downloads in the local player. When the folder is empty, the player opens with a message prompting you to download videos from YouTube mode.

After a successful download, you are prompted to **Open Downloads** in the local player or dismiss the dialog.

### Search backends

By default, searches use **yt-dlp** (no API key required). To use the official **YouTube Data API** instead, edit your settings file:

- macOS: `~/Library/Application Support/Karaoke Blast/settings.json`
- Linux: `~/.config/karaoke-blast/settings.json`
- Windows: `%APPDATA%\Karaoke Blast\settings.json`

```json
{
  "youtube_search_backend": "api",
  "youtube_api_key": "YOUR_GOOGLE_API_KEY"
}
```

Set `youtube_search_backend` to `"yt-dlp"` to switch back. If the API key is missing while `"api"` is selected, the app falls back to yt-dlp and shows a notice.

## Manual Test Checklist

- [ ] Local folder opens and plays as before
- [ ] Parent folder with videos only in subfolders can be opened
- [ ] Song list shows subfolders; drill down and Up stay within the opened root
- [ ] Play all / Queue all include nested videos; Back to folders restores hierarchy
- [ ] **Search YouTube** opens player in YouTube mode with search panel visible
- [ ] **Append "karaoke" to search** is checked by default; unchecking searches without adding `karaoke`
- [ ] Checkbox state persists after restart
- [ ] **Search more** appends additional results; new **Search** clears the list
- [ ] Double-click result plays video in embedded player
- [ ] Right-click **Play Next** queues video; queue shows in panel
- [ ] Video end auto-advances to next queued item
- [ ] **Next** skips to next queued video; **Stop** stops playback but keeps queue
- [ ] **Paste URL** tab plays a direct link
- [ ] `Y` focuses search; `L` toggles YouTube panel
- [ ] Opening a local folder switches back to VLC and clears YouTube queue
- [ ] Fullscreen works in both local and YouTube modes
- [ ] Right-click **Download** on a search result; progress appears in the sidebar
- [ ] Download completes and shows success; **Open Downloads** opens the local player
- [ ] **YouTube Downloads** appears on the startup screen (even when empty)
- [ ] Can play and search YouTube while a download is in progress
- [ ] Second download while one is active shows a notice
- [ ] Re-downloading an existing video reports it is already downloaded
- [ ] **Change…** on startup screen and YouTube panel opens a folder picker
- [ ] Custom download folder persists after restart and is used for new downloads
- [ ] Right-click **Remove from List** on a recent folder removes it from the startup list after restart

## Roadmap

- Custom playlists and sort order
- Per-song properties and custom graphics
- Persistent storage for playlists and settings
- Song manager panel
