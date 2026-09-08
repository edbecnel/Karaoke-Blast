"""Tests for the global preferences dialog."""

from karaoke_blast.ui.preferences_dialog import PreferencesValues, build_preferences_values


def test_build_preferences_values_round_trip() -> None:
    values = build_preferences_values(
        hide_appledouble_files=True,
        library_flat_browse=False,
        controls_auto_hide=True,
        filename_rename_skip_canonical=True,
        filename_rename_auto_fill_slots=False,
        metadata_skip_tagged=True,
        metadata_auto_fill_slots=False,
    )

    assert values == PreferencesValues(
        hide_appledouble_files=True,
        library_flat_browse=False,
        controls_auto_hide=True,
        filename_rename_skip_canonical=True,
        filename_rename_auto_fill_slots=False,
        metadata_skip_tagged=True,
        metadata_auto_fill_slots=False,
    )


def test_build_preferences_values_reflects_toggled_values() -> None:
    values = build_preferences_values(
        hide_appledouble_files=False,
        library_flat_browse=True,
        controls_auto_hide=False,
        filename_rename_skip_canonical=False,
        filename_rename_auto_fill_slots=True,
        metadata_skip_tagged=False,
        metadata_auto_fill_slots=True,
    )

    assert values == PreferencesValues(
        hide_appledouble_files=False,
        library_flat_browse=True,
        controls_auto_hide=False,
        filename_rename_skip_canonical=False,
        filename_rename_auto_fill_slots=True,
        metadata_skip_tagged=False,
        metadata_auto_fill_slots=True,
    )
