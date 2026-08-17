<p align="center">
  <img src="src/karaoke_blast/assets/logo.png" alt="Karaoke Blast logo" width="240">
</p>

# Karaoke Blast

Full-screen karaoke video player and manager. Open a local folder of videos and audio files, browse subfolders, queue songs, and search YouTube for karaoke tracks — all in one session.

## Install (Windows and macOS)

Download the latest installers from [GitHub Releases](https://github.com/edbecnel/Karaoke-Blast/releases). You do **not** need Python, Inno Setup, or any developer tools.

### Windows

1. Download `KaraokeBlast-Setup.exe` from the latest release.
2. Run the installer. If Windows SmartScreen appears (“Windows protected your PC”), click **More info** → **Run anyway** (unsigned builds show this until the app is code-signed).
3. Follow the setup wizard:
   - Karaoke Blast is installed to `%LOCALAPPDATA%\Programs\Karaoke Blast`.
   - Leave **Install VLC if it is not already on this computer** checked if you want local file playback and you do not already have VLC.
   - Optionally check **Create a desktop shortcut**.
4. After install, open **Karaoke Blast** from the Start Menu (or the desktop shortcut).
5. To uninstall: **Settings** → **Apps** → **Karaoke Blast** → **Uninstall**, or use **Karaoke Blast** in the Start Menu uninstall entry.

**What you need separately**

| Component | Required for | Installed by setup? |
|---|---|---|
| Karaoke Blast + Python | Running the app | Yes (always) |
| VLC | Local videos and downloaded YouTube files | Only if missing (optional winget step) |
| ffmpeg | YouTube downloads | Bundled in app folder if not on PATH |

YouTube streaming in the embedded player works without VLC.

### macOS

1. Download `Karaoke Blast.dmg` from the latest release.
2. Open the DMG and drag **Karaoke Blast** to **Applications**.
3. Open **Karaoke Blast** from Applications or Spotlight.
4. If Gatekeeper blocks the app (“cannot be opened because the developer cannot be verified”), open **System Settings** → **Privacy & Security** and click **Open Anyway**, or right-click the app → **Open** → **Open** (unsigned builds show this until the app is notarized).
5. On first launch, the app may offer to install **VLC** via Homebrew if VLC is not installed (`brew install --cask vlc`). Local playback needs VLC; YouTube streaming does not.

**What you need separately**

| Component | Required for | Installed automatically? |
|---|---|---|
| Karaoke Blast + Python | Running the app | Yes (inside the app) |
| VLC | Local videos and downloaded YouTube files | Attempted via Homebrew on first launch if missing |
| ffmpeg | YouTube downloads | Bundled in app if not on PATH |

### Dependencies (all platforms)

The installers always ship Karaoke Blast and Python. **VLC** and **ffmpeg** are installed or bundled only when they are not already on your computer:

- **VLC** — required for local file playback. The Windows installer can install it via winget when missing. On macOS, first launch tries Homebrew (`brew install --cask vlc`) if VLC is not found.
- **ffmpeg** — required for YouTube downloads. If ffmpeg is not on PATH, the installer bundles a copy inside the app directory.

YouTube streaming works without VLC. Local folder playback and downloaded YouTube videos need VLC.

### Unsigned builds

Release installers are not code-signed yet. Windows SmartScreen and macOS Gatekeeper may warn on first launch. You can still run the app after confirming the prompt. For public distribution, Apple Developer ID notarization and Windows Authenticode signing are recommended.

### Building and publishing installers (maintainers)

See **[packaging/README.md](packaging/README.md)** for:

- How to publish installers on **GitHub Releases** (recommended — no Inno Setup on your PC)
- Building `KaraokeBlast-Setup.exe` on your **Windows machine** (with Inno Setup)
- **Three options** if you do not have Inno Setup locally (GitHub Actions, staging-only test build, manual release upload)
- Why installer binaries should **not** be committed to git

Quick local build commands:

**macOS DMG**

```bash
./packaging/macos/build-dmg.sh
# Output: packaging/macos/dist/Karaoke Blast.dmg
```

**Windows installer** (requires [Inno Setup 6](https://jrsoftware.org/isinfo.php), or use GitHub Actions instead)

```powershell
powershell -ExecutionPolicy Bypass -File packaging\windows\build-installer.ps1
# Output: packaging\windows\dist\KaraokeBlast-Setup.exe
```

## Run from source (developers)


### Requirements

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

Open a folder containing video or audio files (`.mp4`, `.mkv`, `.avi`, `.mov`, `.webm`, `.m4v`, `.mp3`, `.m4a`, `.aac`, `.flac`, `.wav`, `.ogg`, `.opus`, `.wma`) — including folders that only have media in subfolders — and the player opens in full screen. Recently opened folders appear on the startup screen for quick access. Right-click a recent folder for **Browse folder** (open in Finder or Explorer) or **Remove from List**.

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
| `Y` | Focus library search on the YouTube tab |
| `L` | Toggle library panel |
| `⌂` (Start menu button) | Return to the start screen |
| `F` or `F11` | Toggle full screen |
| `Esc` | Exit full screen (or quit if already windowed) |
| `Q` | Quit |

Move the mouse during playback to reveal the on-screen control bar. Use the play/pause toggle on the control bar, or press `Space`, to play and pause local files.

## Library Panel

During playback, press `L` or click **☰** on the control bar to show the **library panel** on the left. One search box at the top filters the active tab:

- **Local** — live search across the opened folder and all subfolders (empty search shows normal folder browse)
- **YouTube** — press Enter or click **Search** (with optional **Append "karaoke"** and **Search more**)

The panel has three tabs:

### Local

When a folder is loaded, subfolders that contain videos are listed with a trailing `/` — click one to drill down, or use **‥ Up** to go back (within the folder you opened). Click a song once to select it, then click it again to start playback. Use the folder header menu for **Browse folder** (open the current folder in Finder or Explorer), **Play all under this folder**, or **Queue all under this folder** (includes nested subfolders). After Play all, use **← Back to folders** to return to hierarchical browsing. Use the sort dropdown to reorder by:

- Name (A → Z / Z → A)
- Date modified (oldest / newest first)

Toggle **Metadata** to show embedded title, artist, and comments instead of file names (songs without a title still show the file name). Use **⚙** next to it to set the field order and separators. Search matches metadata first, then the file name.

Right-click any song and choose **Play Next** to queue it, **Reveal in Finder** / **Show in Explorer** to locate the file, or **Edit Metadata…** to change Song Title, Artist Name, and Comments (supported formats only).

### YouTube

1. Switch to the **YouTube** tab and enter a search query.
2. Leave **Append "karaoke" to search** checked to add `karaoke` to the query when it is not already present, or uncheck it to search for any YouTube video.
3. Click **Search** or press Enter. Double-click a result to play it, or right-click and choose **Play Next** to queue it.
4. Click **Search more** to load the next 15 results and append them to the list (up to 60 total).

Use the **Paste URL** sub-tab to play a video when you already have a YouTube link or video ID.

### Queue

Queued local files and YouTube videos share one **Queue** section at the top of the library panel. When the current item ends, the next queued item plays automatically (switching between VLC and the embedded YouTube player as needed). Press `N` or click **Next** on the control bar to skip ahead manually. Press `S` or **Stop** to end playback; the queue is kept.

### History

The **History** tab lists recently played local files and YouTube videos in one list (newest first). Double-click to play, or right-click for **Play Now**, **Play Next**, **Edit Metadata…** (local), **Download** (YouTube), or **Remove from History**. Click **Clear** to empty history. History is saved across sessions in `play_history.json` (legacy local/YouTube history files are migrated on first launch).

Volume and mute on the control bar work in both local and YouTube playback and share the same saved settings.

You can open a local folder or search YouTube mid-session without returning to the start screen. Opening a folder while a YouTube video is playing updates the local library without interrupting playback.

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

Click **Search YouTube** on the startup screen, or press `Y`, to open the player with the YouTube tab focused.

Download YouTube videos for offline playback in the local VLC player:

- Right-click a search result, history entry, or queue item and choose **Download**
- Or use the **Download** button on the **Paste URL** tab

Downloads run in the background — you can keep playing and searching YouTube while a download is in progress. Progress, success, and failure are shown in the status area below the queue panel. Only one download runs at a time.

Videos are saved as VLC-compatible **MP4** files (H.264 video + AAC audio when available). By default they go to the app's **YouTube Downloads** folder:

- macOS: `~/Library/Application Support/Karaoke Blast/youtube-downloads`
- Linux: `~/.config/karaoke-blast/youtube-downloads`
- Windows: `%APPDATA%\Karaoke Blast\youtube-downloads`

Use **Change…** on the startup screen or in the library panel (below the download status) to pick a different folder. The choice is saved across sessions. Changing the folder does not move existing downloads.

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
- [ ] Library panel: Local tab browse + recursive search; YouTube tab search and Paste URL
- [ ] Mixed queue plays local files and YouTube videos in order
- [ ] **History** tab shows local and YouTube plays together
- [ ] **Search YouTube** opens player with YouTube tab focused
- [ ] **Append "karaoke" to search** is checked by default; unchecking searches without adding `karaoke`
- [ ] Checkbox state persists after restart
- [ ] **Search more** appends additional results; new **Search** clears the list
- [ ] Double-click result plays video in embedded player
- [ ] Right-click **Play Next** queues item; queue shows in panel
- [ ] Video end auto-advances to next queued item (local or YouTube)
- [ ] **Next** skips to next queued item; **Stop** stops playback but keeps queue
- [ ] **Paste URL** sub-tab plays a direct link
- [ ] `Y` focuses YouTube search; `L` toggles library panel
- [ ] Opening a folder mid-session does not interrupt YouTube or clear the queue
- [ ] Fullscreen works in both local and YouTube modes
- [ ] Right-click **Download** on a search result; progress appears in the sidebar
- [ ] Download completes and shows success; **Open Downloads** opens the local player
- [ ] **YouTube Downloads** appears on the startup screen (even when empty)
- [ ] Can play and search YouTube while a download is in progress
- [ ] Second download while one is active shows a notice
- [ ] Re-downloading an existing video reports it is already downloaded
- [ ] **Change…** on startup screen and library panel opens a folder picker
- [ ] Custom download folder persists after restart and is used for new downloads
- [ ] Right-click **Remove from List** on a recent folder removes it from the startup list after restart
- [ ] Right-click **Browse folder** on a recent folder opens it in Finder or Explorer
- [ ] Right-click a local song shows **Reveal in Finder** / **Show in Explorer**

## Roadmap

- Custom playlists and sort order
- Per-song properties and custom graphics
- Persistent storage for playlists and settings
- Song manager panel
