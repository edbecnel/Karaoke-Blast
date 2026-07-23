"""Application config directory paths."""

import os
import sys
from pathlib import Path


def config_dir() -> Path:
    if sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / "Karaoke Blast"
    elif sys.platform == "win32":
        path = Path(os.environ.get("APPDATA", Path.home())) / "Karaoke Blast"
    else:
        path = Path.home() / ".config" / "karaoke-blast"
    path.mkdir(parents=True, exist_ok=True)
    return path
