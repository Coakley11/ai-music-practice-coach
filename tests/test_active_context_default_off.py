"""Default-off gate: with MUSIC_ACTIVE_CONTEXT unset the feature is a complete no-op.

No store, no file, no snapshot, no session keys, no network. The local/mock feature is opt-in only.
"""
from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

import music_active_context as ac
from songs import music_source as ms

SAY = "Pop\x1fSay — John Mayer"


@pytest.fixture(autouse=True)
def _feature_unset(monkeypatch, tmp_path):
    for name in ("MUSIC_ACTIVE_CONTEXT", "MUSIC_ACTIVE_CONTEXT_DIR"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("MUSIC_APP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.chdir(tmp_path)


def _session():
    return {"studio_page": "practice", "active_catalog_pick_key": SAY, "instrument": "Guitar", "display_key": "G"}


def test_feature_is_disabled_and_has_no_store():
    assert ac.active_context_enabled() is False
    assert ac.get_store() is None


@pytest.mark.parametrize("value", ["", "0", "off", "false", "cloud", "supabase", "1", "true"])
def test_only_the_exact_local_opt_in_enables_anything(monkeypatch, value):
    monkeypatch.setenv("MUSIC_ACTIVE_CONTEXT", value)
    assert ac.get_store() is None  # cloud is not implemented; nothing else enables the feature


def test_mark_intent_is_a_complete_no_op(monkeypatch):
    def boom(_session):
        raise AssertionError("snapshot must not be built while the feature is off")

    monkeypatch.setattr(ac, "snapshot_from_session", boom)
    s = _session()
    before = dict(s)
    for cause in ("song_selected", "select", "workflow_selected", "page", "instrument", "key", "resume"):
        ac.mark_intent(s, cause)
    assert s == before  # no `_music_ctx_*` key was written


def test_flush_without_a_store_attempts_nothing():
    s = _session()
    assert ac.flush_intent(s, ac.get_store(), account_id="a", workspace_id="w", device_id="d") == "no_intent"


def test_source_hooks_leave_no_trace_and_create_no_files(tmp_path):
    s = _session()
    st = SimpleNamespace(session_state=s)
    ms.begin_explicit_custom_selection(s)
    ms.queue_custom_active_song_activation(st, {"id": "c1", "name": "Trial", "original_key_center": "D",
                                                "original_sections": {"Verse": [{"chord": "D", "bars": 1}]}})
    ms.mark_explicit_catalog_selection(s) if hasattr(ms, "mark_explicit_catalog_selection") else None
    assert not [k for k in s if k.startswith("_music_ctx")]
    created = [p for p in Path(tmp_path).rglob("*") if p.is_file()]
    assert created == []  # no active-context file, directory content or lock anywhere


def test_module_has_no_cloud_client():
    src = Path(ac.__file__).read_text(encoding="utf-8").lower()
    for word in ("supabase", "requests", "httpx", "urllib", "postgrest"):
        assert word not in src


def test_unset_env_is_really_unset():
    assert "MUSIC_ACTIVE_CONTEXT" not in os.environ
