"""Disposable whole-workspace acceptance through the actual JSON envelope.

No browser, application entrypoint, cloud connection, or real musician data.
"""
from copy import deepcopy
import json
from types import SimpleNamespace
from unittest.mock import patch

from custom_progression_lab import default_active_progression
from composition_document import new_composition_document, ensure_workflow
from home_practice_resume import restore_recent_practice
from music_persistent_state import build_music_disk_state, apply_music_disk_state
from song_catalog import format_pick_key
from studio_nav_history import navigate_studio_page


def test_reopen_then_home_and_recent_backing_preserves_entire_saved_workspace():
    trial = default_active_progression()
    trial.update(id="acceptance-trial", name="Trial Song", original_key_center="Eb")
    trial["original_sections"]["Verse"] = [{"chord": "Ebmaj7", "bars": 2}]
    other = deepcopy(trial)
    other.update(id="acceptance-other", name="Other Custom song")
    composition = new_composition_document(title="Acceptance composition")
    ensure_workflow(composition)
    catalog = {"Jazz": {"All the Things You Are": {
        "title": "All the Things You Are", "artist": "Kern", "key": "Ab",
        "sections": {"A": ["Fm7", "Bbm7"]},
    }}}
    pick = format_pick_key("Jazz", "All the Things You Are")
    initial = {
        "workspace_id": "guest", "studio_page": "multitrack",
        "instrument": "Piano", "level": "Advanced", "focus": "Improvisation",
        "practice_minutes": 45, "display_key": "Bb",
        "cpl_saved_progressions": {"Trial Song": trial, "Other": other},
        "cpl_active_progression": trial, "cpl_last_display_key": "Bb",
        "composer_saved_compositions": {composition["id"]: composition},
        "composer_active_document": composition,
        "mt_tracks": {"A": b"fixture-recording", "B": None},
        "mt_track_filenames": {"A": "disposable-take.wav"},
        "mixed_track_wav": b"fixture-mix", "multitrack_bpm": 132,
    }
    # A real serialize/deserialize boundary catches bytes and nested-project loss
    # that an in-memory navigation-only fixture cannot reveal.
    envelope = json.loads(json.dumps(build_music_disk_state(SimpleNamespace(session_state=deepcopy(initial)))))
    fresh = {}
    apply_music_disk_state(SimpleNamespace(session_state=fresh), envelope,
                           song_picker_catalog=catalog, song_library={}, authoritative_restore=True)
    assert fresh["instrument"] == "Piano" and fresh["level"] == "Advanced"
    protected = ["cpl_saved_progressions", "cpl_active_progression", "cpl_last_display_key",
                 "composer_saved_compositions", "composer_active_document", "mt_tracks",
                 "mt_track_filenames", "mixed_track_wav", "practice_minutes"]
    assert fresh["cpl_saved_progressions"]["Trial Song"]["original_sections"] == trial["original_sections"]
    assert fresh["composer_saved_compositions"][composition["id"]]["title"] == composition["title"]
    assert fresh["mt_tracks"]["A"] == initial["mt_tracks"]["A"]
    assert fresh["mixed_track_wav"] == initial["mixed_track_wav"]
    baseline = {k: deepcopy(fresh[k]) for k in protected}
    fresh["workspace_id"] = "guest"
    fresh["_music_workspace_blob_hydrated"] = True
    for page in ("home", "custom", "composer", "multitrack", "home"):
        navigate_studio_page(fresh, page)
        assert {k: fresh[k] for k in protected} == baseline
    record = {"session_id": "acceptance-backing", "practice_type": "backing track",
              "song_id": pick, "practice_concert_key": "Ab", "instrument": "Tenor Saxophone",
              "workspace_id": "guest", "resume_payload": {"workspace_id": "guest", "pick_key": pick,
              "backing_track_bpm": 108}}
    with patch("songs.state.persist_music_local_state"), patch("suite_activity_client.record_activity"):
        ok, why = restore_recent_practice(fresh, record, catalog)
    assert ok, why
    assert fresh["studio_page"] == "backing" and fresh["display_key"] == "Ab"
    assert not fresh.get("_backing_autoplay")
    assert {k: fresh[k] for k in protected} == baseline
    reopened = {}
    second_envelope = json.loads(json.dumps(build_music_disk_state(SimpleNamespace(session_state=fresh))))
    apply_music_disk_state(SimpleNamespace(session_state=reopened), second_envelope,
                           song_picker_catalog=catalog, song_library={}, authoritative_restore=True)
    assert {k: reopened[k] for k in protected} == baseline
