"""Entry point: python -m karaoke_blast"""

import argparse
import sys
from pathlib import Path

from karaoke_blast.app import run


def main() -> None:
    parser = argparse.ArgumentParser(description="Karaoke Blast — full-screen video player")
    parser.add_argument(
        "--folder",
        type=Path,
        default=None,
        help="Path to a folder of video files to open on startup",
    )
    args = parser.parse_args()
    sys.exit(run(initial_folder=args.folder))


if __name__ == "__main__":
    main()
