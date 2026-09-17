"""VLC local path / MRL handling."""

from pathlib import Path

from karaoke_blast.player.vlc_player import path_to_vlc_media_mrl


def test_path_with_square_brackets_uses_encoded_file_uri(tmp_path: Path) -> None:
    video = tmp_path / "Song [Karaoke] [rumble:abc].mp4"
    video.write_bytes(b"x")
    mrl = path_to_vlc_media_mrl(video)
    assert mrl.startswith("file://")
    assert "[" not in mrl
    assert "%5B" in mrl
