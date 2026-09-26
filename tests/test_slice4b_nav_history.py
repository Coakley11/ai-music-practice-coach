"""Slice 4B — Back/Forward history contract (units).

History remembers destinations/workspaces; it does not undo musical settings.
"""

from __future__ import annotations

from unittest.mock import patch

from studio_nav_history import (
    NAV_BACK_STACK,
    NAV_FORWARD_STACK,
    _HISTORY_NAV_PENDING_SAVE,
    _apply_history_nav_transition,
    can_go_forward,
    go_back,
    go_forward,
    history_destination_id,
    init_nav_history,
    navigate_studio_page,
    record_creative_workspace_change,
    sync_live_creative_history_dest,
)


def _nav(ss: dict, page: str) -> None:
    with patch("music_persistent_state.after_studio_page_change"):
        navigate_studio_page(ss, page)


def _back(ss: dict) -> None:
    assert go_back(ss) is True
    _apply_history_nav_transition(ss, source="history_back")


def _forward(ss: dict) -> None:
    assert go_forward(ss) is True
    _apply_history_nav_transition(ss, source="history_forward")


def _dest_stack(ss: dict, key: str) -> list[str]:
    return [history_destination_id(entry=e) for e in (ss.get(key) or [])]


@patch("music_persistent_state.after_studio_page_change")
def test_forward_survives_pending_target_remount(_mock):
    ss = {"studio_page": "practice"}
    init_nav_history(ss)
    _nav(ss, "picker")
    _nav(ss, "backing")
    _nav(ss, "creative")
    _back(ss)
    assert ss["studio_page"] == "backing"
    assert can_go_forward(ss)
    ss.pop("_studio_nav_from_history", None)
    assert ss.get(_HISTORY_NAV_PENDING_SAVE) == "backing"
    ss["studio_page"] = "practice"
    assert navigate_studio_page(ss, "backing") is True
    assert can_go_forward(ss)
    assert _dest_stack(ss, NAV_FORWARD_STACK)[-1] == "creative"


@patch("music_persistent_state.after_studio_page_change")
def test_new_nav_after_back_clears_forward(_mock):
    """A→B→C → Back to B → navigate D discards Forward(C)."""
    ss = {"studio_page": "practice"}
    init_nav_history(ss)
    _nav(ss, "picker")  # A-ish
    _nav(ss, "practice")  # B
    _nav(ss, "analysis")  # C
    _back(ss)  # → practice, forward=analysis
    assert ss["studio_page"] == "practice"
    assert can_go_forward(ss)
    # End of Back run: deferred history save flushes pending seal.
    ss.pop(_HISTORY_NAV_PENDING_SAVE, None)
    ss.pop("_studio_nav_from_history", None)
    _nav(ss, "custom")  # D
    assert ss["studio_page"] == "custom"
    assert not can_go_forward(ss)
    assert _dest_stack(ss, NAV_FORWARD_STACK) == []


@patch("music_persistent_state.after_studio_page_change")
def test_settings_changes_do_not_create_history(_mock):
    ss = {
        "studio_page": "practice",
        "display_key": "C",
        "instrument": "Piano",
        "active_catalog_pick_key": "pk::Pop::Perfect",
    }
    init_nav_history(ss)
    _nav(ss, "picker")
    before = list(ss.get(NAV_BACK_STACK) or [])
    ss["display_key"] = "E"
    ss["instrument"] = "Clarinet"
    ss["active_catalog_pick_key"] = "pk::Pop::Photograph"
    # Same-page remount / settings — no history push.
    assert navigate_studio_page(ss, "picker") is False
    assert list(ss.get(NAV_BACK_STACK) or []) == before
    assert ss["display_key"] == "E"
    assert ss["instrument"] == "Clarinet"


@patch("music_persistent_state.after_studio_page_change")
def test_adjacent_rerun_duplicates_suppressed_but_aba_kept(_mock):
    ss = {"studio_page": "practice"}
    init_nav_history(ss)
    _nav(ss, "picker")
    _nav(ss, "practice")
    _nav(ss, "picker")
    # Songs → Practice → Songs: three real visits; back stack has practice then earlier picker leave.
    dests = _dest_stack(ss, NAV_BACK_STACK)
    assert dests.count("practice") >= 1
    assert dests[-1] == "practice"
    # Rerun noise: leaving picker again when already pushed picker as current leave —
    # navigate same page is noop; forcing append path via leave practice→picker again
    # after being on picker would push practice only once adjacent.
    _back(ss)
    assert ss["studio_page"] == "practice"
    _back(ss)
    assert ss["studio_page"] == "picker"


@patch("music_persistent_state.after_studio_page_change")
def test_creative_workspaces_are_separate_destinations(_mock):
    ss = {
        "studio_page": "creative",
        "improv_intelligence_tab": "Missions",
        "creative_improv_intelligence_tab": "Missions",
        "improv_entry_mode": "Song-Based Improvisation",
    }
    init_nav_history(ss)
    sync_live_creative_history_dest(ss)
    assert history_destination_id(ss) == "creative::Missions"

    # Widget advances first (Streamlit on_change order), then history records leave.
    ss["improv_intelligence_tab"] = "Phrase / Motif"
    assert record_creative_workspace_change(
        ss,
        previous_tab="Missions",
        previous_entry_mode="Song-Based Improvisation",
        previous_destination="creative::Missions",
    )
    ss["creative_improv_intelligence_tab"] = "Phrase / Motif"
    sync_live_creative_history_dest(ss)

    ss["improv_intelligence_tab"] = "Entry & Jam"
    ss["improv_entry_mode"] = "Song-Based Improvisation"
    assert record_creative_workspace_change(
        ss,
        previous_tab="Phrase / Motif",
        previous_destination="creative::Phrase / Motif",
    )
    ss["creative_improv_intelligence_tab"] = "Entry & Jam"
    sync_live_creative_history_dest(ss)

    ss["improv_entry_mode"] = "Jam Session Generator"
    assert record_creative_workspace_change(
        ss,
        previous_tab="Entry & Jam",
        previous_entry_mode="Song-Based Improvisation",
        previous_destination="creative::SBI",
    )
    sync_live_creative_history_dest(ss)

    dests = _dest_stack(ss, NAV_BACK_STACK)
    assert "creative::Missions" in dests
    assert "creative::Phrase / Motif" in dests
    assert "creative::SBI" in dests
    assert history_destination_id(ss) == "creative::Entry Mode"

    _back(ss)
    assert history_destination_id(ss) == "creative::SBI"
    _back(ss)
    assert history_destination_id(ss) == "creative::Phrase / Motif"
    _forward(ss)
    assert history_destination_id(ss) == "creative::SBI"


@patch("music_persistent_state.after_studio_page_change")
def test_history_back_preserves_live_musical_globals(_mock):
    ss = {
        "studio_page": "practice",
        "display_key": "C",
        "instrument": "Piano",
        "active_catalog_pick_key": "pk::Pop::Perfect",
    }
    init_nav_history(ss)
    _nav(ss, "creative")
    ss["display_key"] = "F#"
    ss["instrument"] = "Clarinet"
    ss["active_catalog_pick_key"] = "pk::Pop::Photograph"
    _back(ss)
    assert ss["studio_page"] == "practice"
    assert ss["display_key"] == "F#"
    assert ss["instrument"] == "Clarinet"
    assert ss["active_catalog_pick_key"] == "pk::Pop::Photograph"


@patch("music_persistent_state.after_studio_page_change")
def test_backing_envelope_survives_back_forward(_mock):
    from backing_owner_envelope import (
        OWNER_CATALOG,
        get_backing_owner_envelope,
        stamp_backing_owner_envelope,
    )

    ss = {"studio_page": "picker", "display_key": "C"}
    init_nav_history(ss)
    stamp_backing_owner_envelope(
        ss,
        source=OWNER_CATALOG,
        identity="Pop\x1fPerfect — Ed Sheeran",
        title="Perfect",
        original_key="G",
        practice_key="C",
        sounding_key="C",
        return_destination=OWNER_CATALOG,
    )
    _nav(ss, "backing")
    _nav(ss, "creative")
    _back(ss)
    env = get_backing_owner_envelope(ss)
    assert env is not None
    assert env.source == OWNER_CATALOG
    _forward(ss)
    env2 = get_backing_owner_envelope(ss)
    assert env2 is not None
    assert env2.source == OWNER_CATALOG
    assert env2.practice_key == "C"
