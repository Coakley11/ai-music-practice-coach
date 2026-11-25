"""The media catalog (recordings, Multitrack sessions, tone takes, exports, song documents) is one cloud record.

Found by Uploaded Melodies Slice 4 Stage 1 (2026-11-25): with the cloud READ failing, the next save wrote the local
catalog over the cloud record. A fresh server disk has no local copy, so every row saved before was lost.
"""
from __future__ import annotations

import copy

import pytest

import media_persistence as mp


@pytest.fixture
def store(monkeypatch):
    state = {"cloud": {}, "local": {}, "read_error": None, "enabled": True, "writes": 0, "write_error": ""}

    def load_cloud(**_k):
        if not state["enabled"]:
            return {}, None
        return ({}, state["read_error"]) if state["read_error"] else (copy.deepcopy(state["cloud"]), None)

    def save_cloud(catalog, **_k):
        if not state["enabled"]:
            return False, "cloud_disabled"
        if state["write_error"]:
            return False, state["write_error"]
        state["cloud"] = copy.deepcopy(catalog); state["writes"] += 1
        return True, ""

    def save_local(catalog, **_k):
        state["local"] = copy.deepcopy(catalog)
        return True, ""

    monkeypatch.setattr(mp, "_resolve_workspace_id", lambda **_k: "daniel")
    monkeypatch.setattr(mp, "_load_local_catalog", lambda **_k: copy.deepcopy(state["local"]) or mp._empty_catalog(workspace_id="daniel"))
    monkeypatch.setattr(mp, "_save_local_catalog", save_local)
    monkeypatch.setattr(mp, "_load_cloud_catalog", load_cloud)
    monkeypatch.setattr(mp, "_save_cloud_catalog", save_cloud)
    monkeypatch.setattr(mp, "_cloud_authoritative", lambda: state["enabled"])
    return state


def _add(i):
    return mp.add_song_document(None, {"document_id": f"doc-{i}", "source_type": "catalog", "source_id": "s", "title": f"T{i}"})


def _cloud_docs(state):
    return {r["document_id"] for r in state["cloud"].get("song_documents") or [] if not r.get("deleted")}


def _fresh_disk(state):
    state["local"] = {}


def test_a_failed_cloud_read_never_lets_a_save_drop_the_cloud_rows(store):
    for i in (1, 2, 3):
        assert _add(i)["ok"]
    _fresh_disk(store)
    store["read_error"] = "503 simulated outage"
    result = _add(4)
    assert {"doc-1", "doc-2", "doc-3"} <= _cloud_docs(store)
    assert result["ok"] is False and result["error"]  # the cloud does not have it: never "saved"
    store["read_error"] = None
    assert _add(5)["ok"]
    assert _cloud_docs(store) == {"doc-1", "doc-2", "doc-3", "doc-4", "doc-5"}  # doc-4 was kept locally and arrives


@pytest.mark.parametrize("kind, add, key", [
    ("uploaded_recordings", mp.add_uploaded_recording, "recording_id"),
    ("multitrack_sessions", mp.add_multitrack_session, "multitrack_id"),
    ("tone_takes", mp.add_tone_take, "tone_take_id"),
])
def test_recordings_multitrack_sessions_and_tone_takes_are_protected_too(store, kind, add, key):
    add(None, {key: "one", "title": "one"})
    before = [r.get(key) for r in store["cloud"].get(kind) or []]
    assert before
    _fresh_disk(store)
    store["read_error"] = "timeout"
    add(None, {key: "two", "title": "two"})
    assert [r.get(key) for r in store["cloud"].get(kind) or []] == before


def test_a_device_that_loaded_early_does_not_overwrite_rows_saved_since(store):
    _add(1)
    stale = mp.load_media_catalog()
    _add(2)
    _fresh_disk(store)
    mp.save_media_catalog(stale)
    assert _cloud_docs(store) == {"doc-1", "doc-2"}


def test_a_deletion_still_wins_over_an_older_cloud_copy(store):
    _add(1); _add(2)
    assert mp.delete_song_document(None, "doc-1")["ok"]
    _fresh_disk(store)
    _add(3)
    assert _cloud_docs(store) == {"doc-2", "doc-3"}


def test_a_stale_device_does_not_bring_back_a_deleted_row(store):
    _add(1); _add(2)
    stale_local = copy.deepcopy(store["local"])
    mp.delete_song_document(None, "doc-1")
    store["local"] = stale_local
    _add(3)
    assert _cloud_docs(store) == {"doc-2", "doc-3"}


def test_a_failed_write_is_reported_and_kept_locally(store):
    _add(1)
    store["write_error"] = "503"
    r = _add(2)
    assert r["ok"] is False and "503" in r["error"]
    assert {d["document_id"] for d in store["local"]["song_documents"]} >= {"doc-1", "doc-2"}


def test_with_the_cloud_off_saving_is_local_as_before(store):
    store["enabled"] = False
    assert _add(1)["ok"] is True
    assert store["writes"] == 0 and store["local"]["song_documents"]
