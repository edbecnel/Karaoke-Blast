"""Tests for filename stem parsing."""

from karaoke_blast.utils.filename_rename import split_title


def test_split_title_contraction_underscores() -> None:
    assert split_title("Don_t Cry Out Loud - Artist") == [
        "Don't Cry Out Loud",
        "Artist",
    ]
    assert split_title("It_s A Wonderful Life - Artist") == [
        "It's A Wonderful Life",
        "Artist",
    ]
    assert split_title("I_D_DIE_FOR_YOU") == ["I'D", "DIE", "FOR", "YOU"]
    assert split_title("I_D_DIE_FOR_YOU - Artist") == [
        "I'D",
        "DIE",
        "FOR",
        "YOU",
        "Artist",
    ]
    assert split_title("DON_T CRY OUT LOUD - Artist") == [
        "DON'T CRY OUT LOUD",
        "Artist",
    ]
    assert split_title("IT_S A WONDERFUL LIFE - Artist") == [
        "IT'S A WONDERFUL LIFE",
        "Artist",
    ]


def test_split_title_preserves_real_apostrophes() -> None:
    assert split_title("Don't Cry Out Loud - Artist") == [
        "Don't Cry Out Loud",
        "Artist",
    ]
    assert split_title("It's A Wonderful Life - Artist") == [
        "It's A Wonderful Life",
        "Artist",
    ]


def test_split_title_avoids_false_positive_underscore_merges() -> None:
    assert split_title("word_data - Artist") == ["word", "data", "Artist"]
    assert split_title("Rock_n_Roll - Artist") == ["Rock", "n", "Roll", "Artist"]
