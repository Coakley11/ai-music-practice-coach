"""Active-context sync x Mobile QA (Custom/Composition identity, per-song Practice Key, explicit Backing switch).

Local mock store only; no cloud. Sessions are built with the real Custom loaders so the QA branch's
per-song Practice Key and Original Key behaviour is what the sync layer observes.
"""
from __future__ import annotations

import copy
from types import SimpleNamespace
from unittest import mock

import pytest

import music_active_context as ac
from custom_progression_lab import CPL_ACTIVE_KEY
from songs import music_source as ms
from songs.music_source import custom_pick_key_for
from songs.practice_key_state import get_practice_concert_key
from tests.test_custom_practice_key_per_song import _choose, _load, _store

ACC, WS = "acct-1", "daniel"
SAY = "Pop\x1fSay — John Mayer"
COMP = "composition::comp-1"


def device(pick, page="backing", inst="Guitar", key="D"):
    return {"_suite_active_workspace_id": WS, "studio_page": page, "active_catalog_pick_key": pick,
            "instrument": inst, "display_key": key}


def custom_device(songs, name, page="backing", inst="Guitar"):
    ss = {"_suite_active_workspace_id": WS, "studio_page": page, "instrument": inst}
    _load(ss, songs, name)
    ss["active_catalog_pick_key"] = custom_pick_key_for(ss[CPL_ACTIVE_KEY])
    ss["display_key"] = get_practice_concert_key(ss, ss["active_catalog_pick_key"])
    return ss


def flush(s, store, dev):
    return ac.flush_intent(s, store, account_id=ACC, workspace_id=WS, device_id=dev)


@pytest.fixture
def store(tmp_path):
    return ac.LocalFileActiveContextStore(tmp_path)


def test_custom_identity_is_the_stable_custom_pick_key_and_source_type(store):
    songs = _store()
    a = custom_device(songs, "Trial Song")
    snap = ac.snapshot_from_session(a)
    assert snap["source_type"] == "custom" and snap["resource_id"] == "custom::trial-1"
    assert snap["practice_key"] == "D"  # Original Key until a Practice Key is chosen
    b = custom_device(songs, "Blues in F minor")
    assert ac.snapshot_from_session(b)["resource_id"] == "custom::blues-1"


def test_composition_identity_and_catalog_identity_are_distinct_source_types():
    assert ac.snapshot_from_session(device(COMP))["source_type"] == "composition"
    assert ac.snapshot_from_session(device(SAY))["source_type"] == "catalog"


def test_stale_device_cannot_apply_one_songs_practice_key_to_another_custom_song(store):
    songs = _store()
    phone = custom_device(songs, "Trial Song")
    ac.mark_intent(phone, "song_selected")
    assert flush(phone, store, "phone") == "published"
    stale_dell = custom_device(songs, "Trial Song")  # hydrated before the phone changed song
    # phone moves on to Blues (explicit pick)
    _load(phone, songs, "Blues in F minor")
    phone["active_catalog_pick_key"] = "custom::blues-1"
    phone["display_key"] = "Fm"
    ac.mark_intent(phone, "song_selected")
    assert flush(phone, store, "phone") == "published"
    _choose(stale_dell, "E")
    stale_dell["display_key"] = "E"
    ac.mark_intent(stale_dell, "practice_key_changed")
    assert flush(stale_dell, store, "dell") == "discarded"
    rec = store.read(ACC, WS)
    assert (rec.resource_id, rec.practice_key, rec.revision) == ("custom::blues-1", "Fm", 2)


def test_stale_practice_key_survives_neither_a_source_change_nor_a_catalog_switch(store):
    songs = _store()
    phone = custom_device(songs, "Trial Song")
    ac.mark_intent(phone, "song_selected")
    flush(phone, store, "phone")
    stale = custom_device(songs, "Trial Song")
    # Backing source changes on the phone: Custom -> Catalog (Say) -> Composition, each explicit.
    for pick, key in ((SAY, "G"), (COMP, "Bb")):
        phone.update(active_catalog_pick_key=pick, display_key=key)
        ac.mark_intent(phone, "song_selected")
        assert flush(phone, store, "phone") == "published"
    _choose(stale, "A")
    stale["display_key"] = "A"
    ac.mark_intent(stale, "practice_key_changed")
    assert flush(stale, store, "dell") == "discarded"
    rec = store.read(ACC, WS)
    assert (rec.source_type, rec.resource_id, rec.practice_key) == ("composition", COMP, "Bb")


def test_same_song_practice_key_from_another_device_merges_without_touching_the_song(store):
    songs = _store()
    phone = custom_device(songs, "Trial Song")
    ac.mark_intent(phone, "song_selected")
    flush(phone, store, "phone")
    dell = custom_device(songs, "Trial Song")
    _choose(dell, "E")
    dell["display_key"] = "E"
    ac.mark_intent(dell, "practice_key_changed")
    assert flush(dell, store, "dell") == "published"
    rec = store.read(ACC, WS)
    assert (rec.resource_id, rec.practice_key, rec.revision) == ("custom::trial-1", "E", 2)
    assert songs["Trial Song"]["original_key_center"] == "D"  # Original Key is never rewritten


def test_explicit_backing_switch_to_custom_reports_a_song_selected_intent(store):
    songs = _store()
    phone = device(SAY, key="G")
    ac.mark_intent(phone, "song_selected")
    flush(phone, store, "phone")
    st = SimpleNamespace(session_state=phone, rerun=lambda: None)
    phone["cpl_saved_progressions"] = songs
    phone[ms.LAST_CUSTOM_STATE_KEY] = {"active": {"id": "blues-1", "name": "Blues in F minor"}}

    def fake_source_change(st_, **_kw):  # the real handler installs the Custom song
        _load(st_.session_state, songs, "Blues in F minor")
        st_.session_state["active_catalog_pick_key"] = "custom::blues-1"
        st_.session_state["display_key"] = "Fm"

    with mock.patch.object(ms, "on_song_picker_source_change", side_effect=fake_source_change):
        assert ms.switch_backing_source_to_custom(st, invalidate_backing=lambda *a, **k: None) == "switched"
    assert flush(phone, store, "phone") == "published"
    rec = store.read(ACC, WS)
    assert (rec.source_type, rec.resource_id, rec.practice_key, rec.revision) == ("custom", "custom::blues-1", "Fm", 2)


def test_failed_backing_switch_publishes_nothing(store):
    phone = device(SAY, key="G")
    ac.mark_intent(phone, "song_selected")
    flush(phone, store, "phone")
    st = SimpleNamespace(session_state=phone, rerun=lambda: None)
    before = copy.deepcopy(phone)
    assert ms.switch_backing_source_to_custom(st, invalidate_backing=lambda *a, **k: None) == "no_custom"
    assert flush(phone, store, "phone") == "no_intent"
    phone.pop("_music_ctx_last_status", None)
    before.pop("_music_ctx_last_status", None)
    assert store.read(ACC, WS).revision == 1 and phone == before


def test_loading_a_custom_song_passively_never_publishes(store):
    songs = _store()
    s = custom_device(songs, "Trial Song")  # hydration / reload: no mark_intent
    for _ in range(3):
        assert flush(s, store, "dell") == "no_intent"
    assert store.read(ACC, WS) is None


def test_custom_resume_payload_round_trips_for_adoption(store):
    songs = _store()
    phone = custom_device(songs, "Blues in F minor")
    ac.mark_intent(phone, "song_selected")
    flush(phone, store, "phone")
    payload = ac.payload_for_adoption(store.read(ACC, WS))
    assert payload["pick_key"] == "custom::blues-1" and payload["display_key"] == "Fm"
    assert payload["studio_page"] == "backing"


def test_set_as_active_song_reports_a_custom_selection_intent(store):
    songs = _store()
    phone = device(SAY, key="G")
    ac.mark_intent(phone, "song_selected")
    flush(phone, store, "phone")
    st = SimpleNamespace(session_state=phone)
    ms.queue_custom_active_song_activation(st, copy.deepcopy(songs["Trial Song"]))
    # the next run commits the queued Custom song; the end-of-run flush publishes it
    phone["active_catalog_pick_key"] = "custom::trial-1"
    phone["display_key"] = "D"
    assert flush(phone, store, "phone") == "published"
    assert store.read(ACC, WS).resource_id == "custom::trial-1"
