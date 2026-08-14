"""Detect VLC and ffmpeg on the system and configure runtime paths."""

from __future__ import annotations

import logging
import os
import shutil
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_MAC_FFMPEG_SEARCH_DIRS = (
    "/opt/homebrew/bin",
    "/usr/local/bin",
)

_WIN_VLC_REGISTRY_KEYS = (
    r"HKLM\SOFTWARE\VideoLAN\VLC",
    r"HKLM\SOFTWARE\WOW6432Node\VideoLAN\VLC",
)

_WIN_VLC_DEFAULT_DIRS = (
    Path(r"C:\Program Files\VideoLAN\VLC"),
    Path(r"C:\Program Files (x86)\VideoLAN\VLC"),
)

_MAC_VLC_PATHS = (
    Path("/Applications/VLC.app/Contents/MacOS/lib/libvlc.dylib"),
    Path("/Applications/VLC.app/Contents/MacOS/lib/libvlc.5.dylib"),
)

_MAC_VLC_BREW_PREFIXES = (
    Path("/opt/homebrew/opt/vlc"),
    Path("/usr/local/opt/vlc"),
)


def packaged_app_root() -> Path | None:
    """Return the install root when running from a packaged app layout."""
    if sys.platform == "darwin":
        exe = Path(sys.executable).resolve()
        # .../Karaoke Blast.app/Contents/Resources/venv/bin/python
        parts = exe.parts
        if "Contents" in parts:
            contents_idx = parts.index("Contents")
            return Path(*parts[:contents_idx + 1])
        return None

    if sys.platform == "win32":
        exe = Path(sys.executable).resolve()
        # .../Karaoke Blast/venv/Scripts/python.exe
        if exe.parent.name.lower() == "scripts" and exe.parent.parent.name.lower() == "venv":
            return exe.parent.parent.parent
        local = os.environ.get("LOCALAPPDATA", "")
        if local:
            candidate = Path(local) / "Programs" / "Karaoke Blast"
            if candidate.is_dir():
                return candidate
    return None


def bundled_ffmpeg_dir() -> Path | None:
    """Directory that may contain a bundled ffmpeg binary from the installer."""
    root = packaged_app_root()
    if root is None:
        return None

    if sys.platform == "darwin":
        candidate = root / "Contents" / "Resources" / "ffmpeg"
    else:
        candidate = root / "ffmpeg"

    return candidate if candidate.is_dir() else None


def _ffmpeg_binary_names() -> tuple[str, ...]:
    return ("ffmpeg.exe", "ffmpeg") if sys.platform == "win32" else ("ffmpeg",)


def _ffmpeg_search_dirs() -> list[str]:
    dirs: list[str] = []

    bundled = bundled_ffmpeg_dir()
    if bundled is not None:
        dirs.append(str(bundled))

    if sys.platform == "darwin":
        dirs.extend(_MAC_FFMPEG_SEARCH_DIRS)
    elif sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA", "")
        if local:
            winget_links = Path(local) / "Microsoft" / "WinGet" / "Links"
            if winget_links.is_dir():
                dirs.append(str(winget_links))
            winget_packages = Path(local) / "Microsoft" / "WinGet" / "Packages"
            if winget_packages.is_dir():
                for package_dir in winget_packages.iterdir():
                    if not package_dir.is_dir() or "ffmpeg" not in package_dir.name.lower():
                        continue
                    for candidate in package_dir.glob("*/bin"):
                        if candidate.is_dir():
                            dirs.append(str(candidate))

    return [d for d in dirs if os.path.isdir(d)]


def resolve_ffmpeg_location() -> str | None:
    """Return an ffmpeg binary path, including bundled and common install locations."""
    for name in _ffmpeg_binary_names():
        found = shutil.which(name)
        if found:
            return found

    extra_dirs = _ffmpeg_search_dirs()
    if extra_dirs:
        for name in _ffmpeg_binary_names():
            found = shutil.which(name, path=os.pathsep.join(extra_dirs))
            if found:
                return found

    for directory in extra_dirs:
        for name in _ffmpeg_binary_names():
            candidate = Path(directory) / name
            if candidate.is_file():
                return str(candidate)

    return None


def _win_vlc_dir_from_registry() -> Path | None:
    if sys.platform != "win32":
        return None

    import winreg

    for key_path in _WIN_VLC_REGISTRY_KEYS:
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path.replace("HKLM\\", "")) as key:
                install_dir, _ = winreg.QueryValueEx(key, "InstallDir")
                if install_dir:
                    path = Path(str(install_dir))
                    if path.is_dir():
                        return path
        except OSError:
            continue
    return None


def _win_vlc_lib_path() -> Path | None:
    install_dir = _win_vlc_dir_from_registry()
    if install_dir is not None:
        candidate = install_dir / "libvlc.dll"
        if candidate.is_file():
            return candidate

    for directory in _WIN_VLC_DEFAULT_DIRS:
        candidate = directory / "libvlc.dll"
        if candidate.is_file():
            return candidate
    return None


def _mac_vlc_lib_path() -> Path | None:
    for candidate in _MAC_VLC_PATHS:
        if candidate.is_file():
            return candidate

    for prefix in _MAC_VLC_BREW_PREFIXES:
        for name in ("lib/libvlc.dylib", "lib/libvlc.5.dylib"):
            candidate = prefix / name
            if candidate.is_file():
                return candidate
    return None


def _linux_vlc_lib_path() -> Path | None:
    found = shutil.which("vlc")
    if found:
        # python-vlc usually finds libvlc via ldconfig when VLC is installed.
        return None

    for name in ("libvlc.so", "libvlc.so.5"):
        lib = shutil.which(name)
        if lib:
            return Path(lib)
    return None


def resolve_vlc_lib_path() -> Path | None:
    """Return the path to libvlc if VLC is installed on the system."""
    if sys.platform == "win32":
        return _win_vlc_lib_path()
    if sys.platform == "darwin":
        return _mac_vlc_lib_path()
    return _linux_vlc_lib_path()


def is_vlc_available() -> bool:
    return resolve_vlc_lib_path() is not None


def is_ffmpeg_available() -> bool:
    return resolve_ffmpeg_location() is not None


def configure_vlc_environment() -> bool:
    """Set PYTHON_VLC_LIB_PATH when VLC is installed. Returns True if configured."""
    if os.environ.get("PYTHON_VLC_LIB_PATH"):
        return True

    lib_path = resolve_vlc_lib_path()
    if lib_path is None:
        return False

    os.environ["PYTHON_VLC_LIB_PATH"] = str(lib_path)
    if sys.platform == "win32":
        vlc_dir = lib_path.parent
        os.environ.setdefault("PATH", "")
        if str(vlc_dir) not in os.environ["PATH"]:
            os.environ["PATH"] = f"{vlc_dir}{os.pathsep}{os.environ['PATH']}"
    elif sys.platform == "darwin":
        vlc_dir = lib_path.parent
        os.environ.setdefault("DYLD_LIBRARY_PATH", "")
        if str(vlc_dir) not in os.environ["DYLD_LIBRARY_PATH"]:
            os.environ["DYLD_LIBRARY_PATH"] = (
                f"{vlc_dir}{os.pathsep}{os.environ['DYLD_LIBRARY_PATH']}"
            )

    logger.debug("Configured VLC library path: %s", lib_path)
    return True


def configure_runtime_dependencies() -> None:
    """Configure VLC and ffmpeg paths before the app loads media backends."""
    configure_vlc_environment()

    ffmpeg = resolve_ffmpeg_location()
    if ffmpeg is None:
        logger.debug("ffmpeg not found on PATH or in bundled locations")
        return

    ffmpeg_dir = str(Path(ffmpeg).parent)
    os.environ.setdefault("PATH", "")
    if ffmpeg_dir not in os.environ["PATH"]:
        os.environ["PATH"] = f"{ffmpeg_dir}{os.pathsep}{os.environ['PATH']}"
    logger.debug("Configured ffmpeg path: %s", ffmpeg)
