"""Focused Backing Key Cycling UI contracts."""

from __future__ import annotations

from pathlib import Path

from backing_key_cycle import (
    ENHARMONIC_SPELLING_PAIRS,
    advance_key_cycle_now,
    current_backing_owner_practice_key,
    default_spelling_prefs,
    get_owner_cycle_session,
    is_cycle_active,
    note_key_cycle_arrangement_settings_changed,
    reproject_key_cycle_display,
    render_backing_key_cycle_controls,
    should_honor_cycle_off_request,
    start_key_cycle,
    stop_key_cycle,
    temporary_playback_key,
)
from music_feature_icons import feature_label, semantic_field_icon


class _Ctx:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class _ControlsSt:
    def __init__(self, session: dict, *, cycling: str):
        self.session = session
        self.cycling = cycling
        self.expanders: list[tuple[str, bool]] = []
        self.radio_labels: list[str] = []

    def radio(self, label, *, options, key, **_kwargs):
        self.radio_labels.append(str(label or ""))
        if str(label or "").endswith("Key cycling") or str(label or "") == "Key cycling":
            self.session[key] = self.cycling
            return self.cycling
        value = self.session.get(key)
        if value not in options:
            value = options[0]
            self.session[key] = value
        return value

    def columns(self, count):
        return [_Ctx() for _ in range(count)]

    def expander(self, label, *, expanded=False):
        self.expanders.append((label, expanded))
        return _Ctx()


def _session() -> dict:
    pick = "Pop|UI Contract"
    return {
        "studio_page": "backing",
        "active_catalog_pick_key": pick,
        "practice_key_by_source": {pick: "C"},
        "display_key": "C",
        "concert_key": "C",
        "backing_key_spelling_prefs": default_spelling_prefs(),
    }


def test_cycling_can_turn_on_before_play_and_starts_at_saved_key() -> None:
    session = _session()
    ui = _ControlsSt(session, cycling="On")

    render_backing_key_cycle_controls(ui, session)

    assert is_cycle_active(session)
    assert temporary_playback_key(session) == "C"
    assert session["practice_key_by_source"]["Pop|UI Contract"] == "C"
    assert "Interval" in ui.radio_labels
    assert "Direction" in ui.radio_labels
    assert ("Key Spelling", True) in ui.expanders


def test_subcontrols_hidden_while_cycling_off() -> None:
    session = _session()
    ui = _ControlsSt(session, cycling="Off")

    render_backing_key_cycle_controls(ui, session)

    assert not is_cycle_active(session)
    assert any(lbl.endswith("Key cycling") for lbl in ui.radio_labels)
    assert "Interval" not in ui.radio_labels
    assert "Direction" not in ui.radio_labels
    assert ("Key Spelling", True) not in ui.expanders
    assert not any(label == "Key Spelling" for label, _ in ui.expanders)


def test_subcontrols_appear_when_cycling_on() -> None:
    session = _session()
    ui = _ControlsSt(session, cycling="On")

    render_backing_key_cycle_controls(ui, session)

    assert is_cycle_active(session)
    assert "Interval" in ui.radio_labels
    assert "Direction" in ui.radio_labels
    assert ("Key Spelling", True) in ui.expanders


def test_main_off_control_stops_cycle_and_preserves_saved_key() -> None:
    session = _session()
    start_key_cycle(session, start_key="C")
    advance_key_cycle_now(session)
    advance_key_cycle_now(session)
    assert temporary_playback_key(session) == "D"
    saved = current_backing_owner_practice_key(session)

    session["backing_key_cycle_enabled_ui"] = "Off"
    session["_kc_cycle_user_toggled"] = True
    ui = _ControlsSt(session, cycling="Off")
    render_backing_key_cycle_controls(ui, session)

    assert not is_cycle_active(session)
    assert current_backing_owner_practice_key(session) == saved
    assert temporary_playback_key(session) in {"", saved, "C"}
    data = get_owner_cycle_session(session) or {}
    assert data.get("enabled") is False
    assert int(data.get("offset_semitones") or 0) == 0
    assert "Interval" not in ui.radio_labels
    assert ("Key Spelling", True) not in ui.expanders


def test_turn_off_button_path_stops_cycle_and_preserves_saved_key() -> None:
    session = _session()
    start_key_cycle(session, start_key="C")
    advance_key_cycle_now(session)
    advance_key_cycle_now(session)
    assert temporary_playback_key(session) == "D"
    saved = current_backing_owner_practice_key(session)

    # Same path as the playbar "Turn off cycling" button.
    stop_key_cycle(session)
    assert session.get("_key_cycle_force_ui_off") is True
    assert not is_cycle_active(session)

    ui = _ControlsSt(session, cycling="Off")
    render_backing_key_cycle_controls(ui, session)

    assert not is_cycle_active(session)
    assert session.get("backing_key_cycle_enabled_ui") == "Off"
    assert current_backing_owner_practice_key(session) == saved
    data = get_owner_cycle_session(session) or {}
    assert data.get("enabled") is False
    assert int(data.get("offset_semitones") or 0) == 0
    assert "Interval" not in ui.radio_labels


def test_reenable_cycling_starts_from_saved_practice_key() -> None:
    session = _session()
    start_key_cycle(session, start_key="C")
    advance_key_cycle_now(session)
    assert temporary_playback_key(session) == "Db"
    stop_key_cycle(session)

    session["_kc_cycle_user_toggled"] = True
    ui = _ControlsSt(session, cycling="On")
    render_backing_key_cycle_controls(ui, session)

    assert is_cycle_active(session)
    assert temporary_playback_key(session) == "C"
    assert current_backing_owner_practice_key(session) == "C"
    assert "Interval" in ui.radio_labels
    assert ("Key Spelling", True) in ui.expanders


def test_advanced_icon_labels_still_registered() -> None:
    assert semantic_field_icon("style") == "✨"
    assert semantic_field_icon("meter") == "🥁"
    assert feature_label("key_cycle", "Key cycling").startswith("🔄 ")


def test_receiver_component_has_no_user_facing_handoff_word() -> None:
    component = (
        Path(__file__).resolve().parents[1] / "kc_handoff_component" / "index.html"
    ).read_text(encoding="utf-8")
    visible_markup = component.split("<script", 1)[0].lower()
    assert ">handoff<" not in visible_markup
    assert "<title>kc-handoff</title>" not in visible_markup


def test_scope_feel_and_loops_edits_each_preserve_current_cycle_position() -> None:
    for setting in ("Scope", "Feel", "Loops"):
        session = _session()
        start_key_cycle(session, start_key="C")
        advance_key_cycle_now(session)
        before = dict(get_owner_cycle_session(session) or {})

        note_key_cycle_arrangement_settings_changed(session)

        after = get_owner_cycle_session(session) or {}
        assert temporary_playback_key(session) == "Db", setting
        assert after.get("offset_semitones") == before.get("offset_semitones"), setting
        assert after.get("cycle_id") == before.get("cycle_id"), setting


def test_written_key_display_edit_preserves_current_cycle_position() -> None:
    session = _session()
    session["instrument"] = "Clarinet"
    session["show_chart_in_instrument_key"] = False
    start_key_cycle(session, start_key="C")
    advance_key_cycle_now(session)
    before = dict(get_owner_cycle_session(session) or {})

    session["show_chart_in_instrument_key"] = True
    assert reproject_key_cycle_display(session)

    after = get_owner_cycle_session(session) or {}
    assert temporary_playback_key(session) == "Db"
    assert after.get("offset_semitones") == before.get("offset_semitones")
    assert after.get("cycle_id") == before.get("cycle_id")


def test_spurious_cycle_off_from_sidebar_remount_is_ignored() -> None:
    assert should_honor_cycle_off_request(
        user_toggled=True, force_off=False, suppress_spurious=True
    ) is False
    assert should_honor_cycle_off_request(
        user_toggled=True, force_off=False, suppress_spurious=False
    ) is True
    assert should_honor_cycle_off_request(
        user_toggled=False, force_off=True, suppress_spurious=True
    ) is True


def test_written_reproject_sticky_suppress_survives_multiple_off_remounts() -> None:
    """Instrument→Alto→Written remounts must not restart the mid-cycle key."""
    session = _session()
    session["instrument"] = "Saxophone"
    session["selected_transposing_instrument"] = "Alto saxophone (Eb)"
    start_key_cycle(session, start_key="C")
    advance_key_cycle_now(session)
    mid = temporary_playback_key(session)
    assert mid == "Db"
    # Seed spelling widget keys so the mock radios do not look like a prefs edit.
    prefs = default_spelling_prefs()
    for sharp, flat in ENHARMONIC_SPELLING_PAIRS:
        pair = f"{sharp}/{flat}"
        session[f"backing_key_spell__{pair}"] = prefs[pair]
    data = get_owner_cycle_session(session) or {}
    session["_kc_cycle_settings_applied"] = (
        int(data.get("interval") or 1),
        str(data.get("direction") or "up"),
        str(data.get("cycle_id") or ""),
    )
    session["show_chart_in_instrument_key"] = True
    assert reproject_key_cycle_display(session, force=True)
    assert int(session.get("_kc_suppress_spurious_cycle_off_runs") or 0) >= 4
    before_id = str((get_owner_cycle_session(session) or {}).get("cycle_id") or "")

    for _ in range(3):
        session["backing_key_cycle_enabled_ui"] = "Off"
        session["_kc_cycle_user_toggled"] = True
        ui = _ControlsSt(session, cycling="Off")
        render_backing_key_cycle_controls(ui, session)
        assert is_cycle_active(session)
        assert temporary_playback_key(session) == mid
        assert str((get_owner_cycle_session(session) or {}).get("cycle_id") or "") == before_id
        assert session.get("backing_key_cycle_enabled_ui") == "On"


def test_forced_written_reproject_always_remounts_cmd_bridge() -> None:
    session = _session()
    session["instrument"] = "Saxophone"
    session["selected_transposing_instrument"] = "Alto saxophone (Eb)"
    session["show_chart_in_instrument_key"] = True
    start_key_cycle(session, start_key="C")
    advance_key_cycle_now(session)
    # First reproject establishes the written signature.
    assert reproject_key_cycle_display(session)
    epoch = int(session.get("_kc_player_cmd_epoch") or 0)
    # Same display signature again — force=True must still bump epoch so a
    # mid-cycle Written widget click cannot be dropped as a no-op.
    assert reproject_key_cycle_display(session, force=True)
    assert int(session.get("_kc_player_cmd_epoch") or 0) == epoch + 1
    assert session.get("_kc_display_reproject") is True
    assert temporary_playback_key(session) == "Db"
