"""Chart editor save/load and collect_draft_from_widgets regressions."""

from __future__ import annotations

from song_catalog import user_overrides as uo
from song_chart_editor import (
    chart_override_bar_preview,
    chart_save_preview_lines,
    collect_draft_from_widgets,
)


class _FakeSessionState(dict):
    """Minimal stand-in for Streamlit session_state."""


def test_chart_override_bar_preview():
    entry = {
        "sections": {"Verse": ["G", "D"]},
        "chart_versions": {"Intermediate": {"Verse": ["Gmaj7", "D"]}},
        "edited_level": "Intermediate",
    }
    assert chart_override_bar_preview(entry, section="Verse") == "Verse bar 1 = Gmaj7"


def test_chart_save_preview_shows_edited_bars_first():
    saved = {"Verse": ["Gmaj7", "D", "Em"], "Chorus": ["C", "G", "Am", "F"]}
    before = {"Verse": ["G", "D", "Em"], "Chorus": ["C", "G", "Am", "F"]}
    lines = chart_save_preview_lines(saved, before=before)
    assert lines == ["Verse bar 1: Gmaj7"]


def test_chart_save_preview_fallback_to_first_bars_when_no_diff():
    saved = {"Verse": ["G", "D"], "Chorus": ["C", "G"]}
    before = {"Verse": ["G", "D"], "Chorus": ["C", "G"]}
    lines = chart_save_preview_lines(saved, before=before, max_fallback_sections=2)
    assert lines == ["Verse bar 1: G", "Chorus bar 1: C"]


def test_collect_draft_uses_bar_widgets_not_stale_quick_edit(monkeypatch):
    """Bar-box edits must win over the quick-edit line (always contains ``|``)."""
    title, artist = "Test Song", "Test Artist"
    draft = {"Verse": ["C", "G", "Am", "F"]}
    state = _FakeSessionState(
        {
            f"chart_edit_quick::{title}::{artist}::Verse": "C | G | Am | F",
            f"chart_edit_cell::{title}::{artist}::Verse::0": "Dm",
            f"chart_edit_cell::{title}::{artist}::Verse::1": "G",
            f"chart_edit_cell::{title}::{artist}::Verse::2": "Am",
            f"chart_edit_cell::{title}::{artist}::Verse::3": "F",
        }
    )

    class _St:
        session_state = state

    collected = collect_draft_from_widgets(
        _St(),
        title=title,
        artist=artist,
        draft=draft,
    )
    assert collected["Verse"][0] == "Dm"
    assert collected["Verse"] == ["Dm", "G", "Am", "F"]


def test_save_and_reload_user_verified_override(tmp_path, monkeypatch):
    """Save as user verified writes disk and applies on catalog reload."""
    overrides_file = tmp_path / "user_chart_overrides.json"
    monkeypatch.setattr(uo, "overrides_path", lambda workspace_id=None: overrides_file)

    sections = {"Verse": ["Dm", "G", "Am", "F"], "Chorus": ["F", "C", "G", "Am"]}
    uo.save_user_override(
        title="Override Test",
        artist="QA Artist",
        genre="Pop",
        key="C",
        sections=sections,
        chart_versions={
            "Beginner": sections,
            "Intermediate": sections,
            "Advanced": sections,
        },
        section_order=["Verse", "Chorus"],
        override_status=uo.USER_VERIFIED,
        edited_level="Intermediate",
        catalog_snapshot={
            "key": "C",
            "chart_status": "practice_simplified",
            "sections": {"Verse": ["C", "G", "Am", "F"], "Chorus": ["F", "C", "G", "Am"]},
            "chart_versions": {},
        },
    )

    assert overrides_file.is_file()
    on_disk = uo.get_user_override("Override Test", "QA Artist")
    assert on_disk is not None
    assert on_disk["override_status"] == uo.USER_VERIFIED
    assert on_disk["sections"]["Verse"][0] == "Dm"

    record = {
        "title": "Override Test",
        "artist": "QA Artist",
        "genre": "Pop",
        "key": "C",
        "sections": {"Verse": ["C", "G", "Am", "F"], "Chorus": ["F", "C", "G", "Am"]},
        "chart_versions": {},
        "chart_status": "practice_simplified",
    }
    merged = uo.apply_user_override_to_record(record)
    assert merged["sections"]["Verse"][0] == "Dm"
    assert merged["user_override"]["status"] == uo.USER_VERIFIED
    assert merged["chart_versions"]["Intermediate"]["Verse"][0] == "Dm"


def test_user_verified_and_corrected_share_same_storage(tmp_path, monkeypatch):
    """Both save buttons persist the same way; only override_status differs."""
    overrides_file = tmp_path / "user_chart_overrides.json"
    monkeypatch.setattr(uo, "overrides_path", lambda workspace_id=None: overrides_file)

    uo.save_user_override(
        title="Status Test",
        artist="Artist",
        genre="Rock",
        key="G",
        sections={"Chorus": ["G", "D", "Em", "C"]},
        chart_versions={"Intermediate": {"Chorus": ["G", "D", "Em", "C"]}},
        override_status=uo.USER_CORRECTED,
        edited_level="Intermediate",
    )
    corrected = uo.get_user_override("Status Test", "Artist")
    assert corrected["override_status"] == uo.USER_CORRECTED

    uo.save_user_override(
        title="Status Test",
        artist="Artist",
        genre="Rock",
        key="G",
        sections={"Chorus": ["G7", "D", "Em", "C"]},
        chart_versions={"Intermediate": {"Chorus": ["G7", "D", "Em", "C"]}},
        override_status=uo.USER_VERIFIED,
        edited_level="Intermediate",
        catalog_snapshot=corrected.get("catalog_snapshot"),
    )
    verified = uo.get_user_override("Status Test", "Artist")
    assert verified["override_status"] == uo.USER_VERIFIED
    assert verified["sections"]["Chorus"][0] == "G7"
