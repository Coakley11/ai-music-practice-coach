"""R10 — an explicit Mission-type pick must win over the saved workflow blob.

Changing the Mission worked from a clean slate but not after an example had been
generated: the deferred blob -> legacy projection re-asserted the blob's
``mission_type`` over both ``improv_active_mission`` and the
``improv_mission_pick`` widget key, so the selector snapped back to the Mission
that was active when the blob was written. The next switch then appeared to
work, because the blob had caught up — hence "does not reliably change".

The canonical mission config is the authority for Mission type
(``authoritative_mission_type`` reads it). These tests pin that a fresh pick
beats a stale blob, and that an ordinary rehydrate with no fresh pick still
follows the blob.
"""

from __future__ import annotations

import pytest

from creative_mission_config_persistence import (
    CREATIVE_MISSION_USER_EVENT_KEY,
    SAVE_REASON_MISSION_PICK,
    SAVE_REASON_MISSION_TARGET,
    mission_pick_user_event_is_current,
)

MISSION_A = "Improvise using only chord tones"
MISSION_B = "Target only guide tones (3rds & 7ths)"


def _pick_event(run_seq, *, field="improv_mission_pick", save_reason=SAVE_REASON_MISSION_PICK):
    return {
        "field": field,
        "save_reason": save_reason,
        "run_seq": run_seq,
        "interaction": "mission_pick_on_change",
    }


# -------------------------------------------------------------------------
# The run window. The selector's on_change callback records the event one run
# before the body that performs the projection, so "this run" means the current
# run or the one immediately before it — and nothing older.
# -------------------------------------------------------------------------


@pytest.mark.parametrize(
    "event_run,now,expected",
    [
        (11, 11, True),   # same run
        (11, 12, True),   # callback at 11, projection in the body of 12
        (11, 13, False),  # two runs later is stale
        (11, 10, False),  # cannot be from the future
    ],
)
def test_pick_event_run_window(event_run, now, expected):
    session = {"_script_run_seq": now, CREATIVE_MISSION_USER_EVENT_KEY: _pick_event(event_run)}
    assert mission_pick_user_event_is_current(session) is expected


def test_only_a_mission_pick_event_counts():
    """A target or metrics edit must not be mistaken for a Mission-type pick."""
    base = {"_script_run_seq": 5}
    assert mission_pick_user_event_is_current(dict(base)) is False
    assert (
        mission_pick_user_event_is_current(
            dict(base, **{CREATIVE_MISSION_USER_EVENT_KEY: _pick_event(5, field="improv_mission_target")})
        )
        is False
    )
    assert (
        mission_pick_user_event_is_current(
            dict(base, **{CREATIVE_MISSION_USER_EVENT_KEY: _pick_event(5, save_reason=SAVE_REASON_MISSION_TARGET)})
        )
        is False
    )
    assert (
        mission_pick_user_event_is_current(
            dict(base, **{CREATIVE_MISSION_USER_EVENT_KEY: "not-a-dict"})
        )
        is False
    )


# -------------------------------------------------------------------------
# The projection itself.
# -------------------------------------------------------------------------


def _mission_jam_blob(mission_type):
    from music_workflow_state_store import WorkflowStateBlob

    return WorkflowStateBlob(
        workflow_owner="mission_jam",
        workflow_session_id="r10-session",
        source_type="catalog_song",
        song_title="All of Me",
        mission_type=mission_type,
    )


def _session_with_fresh_pick(picked):
    """Session as it stands mid-rerun: canonical config already holds the pick."""
    from creative_mission_config_persistence import commit_mission_config_to_canonical

    session = {
        "_script_run_seq": 12,
        "studio_page": "creative",
        "improv_intelligence_tab": "Missions",
        "improv_mission_pick": picked,
        "improv_active_mission": picked,
        CREATIVE_MISSION_USER_EVENT_KEY: _pick_event(11),
    }
    commit_mission_config_to_canonical(
        session,
        reason=SAVE_REASON_MISSION_PICK,
        values={"improv_mission_pick": picked, "improv_active_mission": picked},
        project_widget_keys=False,
        interaction="mission_pick_on_change",
    )
    return session


def test_fresh_pick_survives_a_stale_blob_projection():
    """The blob still names Mission A; the user just picked B, so B must stand."""
    from music_workflow_legacy_projection import restore_workflow_blob_to_session

    session = _session_with_fresh_pick(MISSION_B)
    restore_workflow_blob_to_session(session, _mission_jam_blob(MISSION_A))
    assert session.get("improv_active_mission") == MISSION_B
    assert session.get("improv_mission_pick") == MISSION_B, "the selector must not snap back"


def test_rehydrate_without_a_fresh_pick_still_follows_the_blob():
    """No user pick this run: an ordinary restore/reboot keeps the blob's Mission."""
    from music_workflow_legacy_projection import restore_workflow_blob_to_session

    session = {
        "_script_run_seq": 12,
        "studio_page": "creative",
        "improv_intelligence_tab": "Missions",
    }
    restore_workflow_blob_to_session(session, _mission_jam_blob(MISSION_A))
    assert session.get("improv_active_mission") == MISSION_A
    assert session.get("improv_mission_pick") == MISSION_A


def test_stale_pick_event_does_not_pin_the_selector():
    """An old pick event (two runs back) must not override a genuine restore."""
    from music_workflow_legacy_projection import restore_workflow_blob_to_session

    session = _session_with_fresh_pick(MISSION_B)
    session["_script_run_seq"] = 20  # the pick event is now ancient
    restore_workflow_blob_to_session(session, _mission_jam_blob(MISSION_A))
    assert session.get("improv_active_mission") == MISSION_A
