# Building and publishing installers

This guide is for **maintainers** who need to build `KaraokeBlast-Setup.exe` and `Karaoke Blast.dmg` and publish them on GitHub.

**End users** do not need this document. See the [Install section in the main README](../README.md#install-windows-and-macos).

## Important: do not commit installer binaries to git

Installer files are large and change often. They are **not** stored in the repository.

| Commit to git | Do not commit |
|---|---|
| Source code, `packaging/` scripts, workflow files | `KaraokeBlast-Setup.exe`, `Karaoke Blast.dmg` |
| Version bumps in `pyproject.toml` | `packaging/**/staging/`, `packaging/**/dist/` (gitignored) |

Publish installers as **GitHub Release assets** (download links on the Releases page). That is how end users get them.

---

## Publishing installers to GitHub (recommended)

This is the easiest path from any machine (including a Mac). GitHub Actions builds both installers on Microsoft and Apple runners — you do not need Inno Setup on your own PC.

### 1. Commit and push your changes

Commit packaging scripts and app code only:

```bash
git add .
git commit -m "Prepare release 0.1.0"
git push origin main
```

**After a packaging fix:** the release tag must point at the commit that contains the fix. CI builds the **tag**, not “latest main”. If you already published `v0.1.0` on an older commit, move the tag before republishing:

```bash
git tag -f v0.1.0
git push origin v0.1.0 --force
```

Then delete and republish the GitHub release (or publish a new tag such as `v0.1.1`). Do **not** use “Re-run failed jobs” on an old workflow run — that rebuilds the old commit.

### 2. Create a GitHub Release

1. Open [Karaoke Blast Releases](https://github.com/edbecnel/Karaoke-Blast/releases).
2. Click **Draft a new release**.
3. Choose a tag (for example `v0.1.0`) — create the tag if it does not exist.
4. Set the release title (for example `v0.1.0`) and add release notes.
5. Click **Publish release**.

Publishing triggers [`.github/workflows/release.yml`](../../.github/workflows/release.yml), which:

- Builds `Karaoke Blast.dmg` on `macos-latest`
- Builds `KaraokeBlast-Setup.exe` on `windows-latest` (Inno Setup installed via Chocolatey)
- Uploads both files to the release automatically

Wait for the **Release** workflow to finish (Actions tab). The `.exe` and `.dmg` appear under **Assets** on the release page.

### 3. Verify the release

Download each asset and smoke-test on Windows and macOS before announcing the release.

### Alternative: run the workflow without publishing

To build installers without creating a public release yet:

1. Go to **Actions** → **Release** → **Run workflow**.
2. Download artifacts from the completed `build-macos` and `build-windows` jobs (artifact names: `macos-dmg`, `windows-installer`).
3. When ready, create/publish a release and attach those files manually, or publish a release to trigger automatic upload.

### Alternative: upload a locally built installer to a release

If you built `KaraokeBlast-Setup.exe` on your Windows machine (see below):

1. Create or edit a release on GitHub.
2. Drag `packaging\windows\dist\KaraokeBlast-Setup.exe` into the release asset upload area.
3. Do the same for `packaging/macos/dist/Karaoke Blast.dmg` if you built it locally.

---

## Building on your Windows machine

### Option A — Full installer (requires Inno Setup 6)

Best when you want the same `KaraokeBlast-Setup.exe` that CI produces.

**Prerequisites**

- Windows 10 or later (64-bit)
- [Python 3.11+](https://www.python.org/downloads/) (for the build scripts only)
- [Inno Setup 6](https://jrsoftware.org/isinfo.php) (free) — adds `ISCC.exe`, usually at `C:\Program Files (x86)\Inno Setup 6\ISCC.exe`

**Build**

Open PowerShell in the repo root:

```powershell
powershell -ExecutionPolicy Bypass -File packaging\windows\build-installer.ps1
```

**Output:** `packaging\windows\dist\KaraokeBlast-Setup.exe`

This script:

1. Runs `prepare-staging.ps1` (downloads private Python, creates venv, bundles ffmpeg)
2. Compiles the Inno Setup script into the setup `.exe`

If Inno Setup is missing, the script stops with:

> Inno Setup compiler (iscc) not found. Install from https://jrsoftware.org/isinfo.php

---

### Option B — Use GitHub Actions (no Inno Setup on your PC)

Use this when you do not want to install Inno Setup locally.

1. Push your branch to GitHub.
2. **Actions** → **Release** → **Run workflow** (or publish a release as above).
3. Download `windows-installer` from the completed workflow run.

CI installs Inno Setup automatically with `choco install innosetup -y`.

---

### Option C — Staging folder only (no installer, no Inno Setup)

Use this to run or test the packaged app without building `KaraokeBlast-Setup.exe`.

```powershell
powershell -ExecutionPolicy Bypass -File packaging\windows\prepare-staging.ps1
```

**Output:** `packaging\windows\staging\` containing:

- `python\` — private CPython runtime
- `venv\` — app and dependencies
- `ffmpeg\` — bundled ffmpeg fallback
- `launcher.bat` — starts the app
- `detect-deps.ps1` — optional VLC check

**Run the app:**

```powershell
packaging\windows\staging\launcher.bat
```

Or double-click `launcher.bat` in File Explorer.

There is no Start Menu shortcut, no uninstaller, and no single-file setup — this is for development and testing only.

---

## Building on macOS

```bash
./packaging/macos/build-dmg.sh
```

**Output:** `packaging/macos/dist/Karaoke Blast.dmg`

Requires network access (downloads Python standalone and ffmpeg). On Apple Silicon, builds an arm64 app; on Intel, x86_64.

---

## What each installer does

| Platform | Install location | Launcher |
|---|---|---|
| Windows | `%LOCALAPPDATA%\Programs\Karaoke Blast` | Start Menu → **Karaoke Blast** (runs `launcher.bat`) |
| macOS | `/Applications/Karaoke Blast.app` | Double-click the app in Finder |

Both bundles include a private Python runtime. **VLC** and **ffmpeg** are used from the system when present; otherwise:

- **Windows:** installer can install VLC via winget; ffmpeg is bundled in the app folder.
- **macOS:** first launch may run `brew install --cask vlc`; ffmpeg is bundled in the app.

---

## Troubleshooting

| Problem | What to try |
|---|---|
| `iscc` not found | Install Inno Setup 6, or use Option B (GitHub Actions) |
| `tar` not found on Windows | Use Windows 10+ (built-in `tar`), or run the build on CI |
| macOS build fails moving `python` into `.app` | Fixed in `build-dmg.sh` — ensure `Contents/Resources` exists before `mv` |
| macOS build fails at app icon / `venv/bin/python` | Fixed in `build-dmg.sh` — create venv inside `Resources/` with `--copies` |
| SmartScreen / Gatekeeper warning | Expected for unsigned builds; see README |
| winget VLC install fails | Install VLC manually from [videolan.org](https://www.videolan.org/vlc/) |
| Build fails downloading Python/ffmpeg | Check network; URLs are in `packaging/common/versions.env` |

---

## File reference

| Path | Purpose |
|---|---|
| `packaging/windows/build-installer.ps1` | Full Windows build (staging + Inno Setup) |
| `packaging/windows/prepare-staging.ps1` | Staging only (Option C) |
| `packaging/windows/karaoke-blast.iss` | Inno Setup script |
| `packaging/windows/detect-deps.ps1` | Post-install VLC/ffmpeg check |
| `packaging/macos/build-dmg.sh` | macOS `.app` + `.dmg` |
| `packaging/macos/install-optional-deps.sh` | First-run VLC/ffmpeg on macOS |
| `packaging/common/versions.env` | Python standalone and ffmpeg download versions |
| `.github/workflows/release.yml` | CI release builds |
