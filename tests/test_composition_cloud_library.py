"""Cluster D (P8/P9): fake-cloud durability + Composition Library. No network, no real account."""
from __future__ import annotations

import copy
from contextlib import contextmanager
from unittest.mock import patch

from workspace_revision import APPLIED_REVISION_KEY, stamp_applied_workspace_revision
from composition_document import (apply_section_chords, apply_structure_template, bootstrap_from_vision,
                                  ordered_sections, parse_chord_paste)
from composition_library import (library_rows, load_cloud_and_keep_edits, retry_cloud_save,
                                 status_badges, switch_to_composition)
from composition_save_verification import save_feedback
from composition_session_state import (COMPOSER_LIBRARY_KEY, get_active_document, save_document_to_library,
                                       set_active_document)
from composition_workspace_state_persistence import (apply_composition_workspace_from_payload,
                                                     checkpoint_composition_workspace)


def make_doc(title, chords="Cmaj7 Am7 Dm7 G7", key="C major"):
    doc = bootstrap_from_vision(genre="Jazz", song_idea=title, title=title, key=key, bpm=100, meter="4/4")
    apply_structure_template(doc, "simple")
    apply_section_chords(doc, ordered_sections(doc)[0]["id"], parse_chord_paste(chords))
    return doc


class FakeCloud:
    """Account-scoped single-row workspace with a revision CAS, like the real CAS write path."""

    def __init__(self):
        self.row: dict = {}
        self.rev = 0
        self.offline = False
        self.writes = 0

    def persist(self, st, **kw):
        ss = st.session_state
        ss["_suite_persist_last_save_disk"] = True
        ss["_suite_persist_last_save_cloud"] = False
        if self.offline:
            ss["_music_force_save_blocked_reason"] = "save_cloud_full_session:supabase_http_error"
            return False
        if int(ss.get(APPLIED_REVISION_KEY) or 0) != self.rev:
            ss["_music_force_save_blocked_reason"] = "stale_revision_conflict"
            ss["_music_stale_write_blocked"] = True
            return False
        self.rev += 1
        self.writes += 1
        self.row = {"composition_workspace_state": copy.deepcopy(ss["composition_workspace_state"]),
                    "workspace_revision": self.rev}
        stamp_applied_workspace_revision(ss, self.row)
        ss.pop("_music_force_save_blocked_reason", None)
        ss["_suite_persist_last_save_cloud"] = True
        return True

    def load(self, app, force=False):
        return copy.deepcopy(self.row), "now"

    def external_write(self, blob):
        """Another device wrote a newer revision."""
        self.rev += 1
        self.row = {"composition_workspace_state": copy.deepcopy(blob), "workspace_revision": self.rev}


@contextmanager
def wired(cloud, ss, *, mode="cloud", configured=True):
    import composition_save_verification as v

    def disk():
        return {"composition_workspace_state": copy.deepcopy(ss["composition_workspace_state"])}

    with patch("music_persistent_state.force_save_music_state", side_effect=cloud.persist), \
         patch("suite_storage_config.cloud_storage_enabled", return_value=configured), \
         patch("suite_user.account_mode", return_value=mode), \
         patch("suite_cloud_state.load_cloud_full_session", side_effect=cloud.load), \
         patch.object(v, "_read_disk_state", side_effect=disk):
        yield


def new_session(*docs):
    ss = {"workspace_id": "guest"}
    for d in docs:
        set_active_document(ss, d, checkpoint=False)
        save_document_to_library(ss, force_disk=False)
    return ss


def save(ss, cloud, **kw):
    with wired(cloud, ss, **kw):
        return checkpoint_composition_workspace(ss, reason="explicit_library_save", force_disk=True)


def test_write_readback_reload_reopen_and_edit():
    cloud = FakeCloud()
    a, b = make_doc("Earlier Tune"), make_doc("Jazz Tune", "Dm7 G7 Cmaj7")
    ss = new_session(a, b)
    r = save(ss, cloud)
    assert r["cloud_verified"] and r["failure_code"] == ""
    assert save_feedback(r)[0] == "success"
    assert not ss.get("composition_workspace_state_dirty")
    # New session / device: only the cloud row is available.
    fresh = {"workspace_id": "guest"}
    assert apply_composition_workspace_from_payload(fresh, cloud.row, authoritative=True)
    assert {row["title"] for row in library_rows(fresh)} == {"Earlier Tune", "Jazz Tune"}
    ok, _ = switch_to_composition(fresh, a["id"])
    assert ok and get_active_document(fresh)["id"] == a["id"]          # stable id
    doc = get_active_document(fresh)
    apply_section_chords(doc, ordered_sections(doc)[0]["id"], parse_chord_paste("Em7 A7 Dmaj7 Bm7"))
    save_document_to_library(fresh, doc, force_disk=False)
    stamp_applied_workspace_revision(fresh, cloud.row)
    r2 = save(fresh, cloud)
    assert r2["cloud_verified"] and cloud.writes == 2
    stored = cloud.row["composition_workspace_state"]["library"]
    assert set(stored) == {a["id"], b["id"]} and stored[a["id"]] != a


def test_cloud_failure_keeps_local_edits_and_retry_succeeds():
    cloud = FakeCloud()
    ss = new_session(make_doc("Offline Tune"))
    cloud.offline = True
    r = save(ss, cloud)
    assert not r["cloud_verified"] and r["failure_code"] == "cloud_write_failed" and r["retryable"]
    level, text = save_feedback(r)
    assert level == "warning" and "Retry cloud save" in text and "edits are kept" in text
    assert ss["composition_workspace_state_dirty"]
    assert len(ss[COMPOSER_LIBRARY_KEY]) == 1 and get_active_document(ss)["title"] == "Offline Tune"
    cloud.offline = False
    with wired(cloud, ss):
        level, text = retry_cloud_save(ss)
    assert level == "success" and not ss.get("composition_workspace_state_dirty")
    assert len(cloud.row["composition_workspace_state"]["library"]) == 1


def test_not_signed_in_and_not_configured_are_explained_never_success():
    for kw, code, hint in (({"mode": "local"}, "not_signed_in", "Sign in"),
                           ({"configured": False}, "cloud_not_configured", "not configured")):
        cloud = FakeCloud()
        cloud.offline = "configured" in kw          # an unconfigured backend cannot write
        ss = new_session(make_doc("T"))
        r = save(ss, cloud, **kw)
        assert not r["cloud_verified"] and r["failure_code"] == code
        level, text = save_feedback(r)
        assert level != "success" and hint in text
        if code == "not_signed_in":
            assert ss["composition_workspace_state_dirty"]


def test_stale_revision_conflict_does_not_overwrite_and_merge_keeps_both():
    cloud = FakeCloud()
    ss = new_session(make_doc("Shared Tune"))
    assert save(ss, cloud)["cloud_verified"]
    other = copy.deepcopy(cloud.row["composition_workspace_state"])
    theirs = make_doc("Other Device Tune")
    other["library"][theirs["id"]] = theirs
    cloud.external_write(other)
    mine = get_active_document(ss)
    apply_section_chords(mine, ordered_sections(mine)[0]["id"], parse_chord_paste("F6 G7 Cmaj7 A7"))
    save_document_to_library(ss, mine, force_disk=False)
    before = copy.deepcopy(cloud.row)
    r = save(ss, cloud)
    assert r["failure_code"] == "stale_revision_conflict" and not r["cloud_verified"]
    assert cloud.row == before                                          # nothing overwritten
    assert ss["composition_workspace_state_dirty"]
    assert "Load cloud version" in save_feedback(r)[1]
    with wired(cloud, ss):
        ok, _msg = load_cloud_and_keep_edits(ss)
    assert ok
    assert save(ss, cloud)["cloud_verified"]
    assert {x["title"] for x in library_rows(ss)} == {"Shared Tune", "Other Device Tune"}
    final = cloud.row["composition_workspace_state"]["library"]
    assert theirs["id"] in final and final[mine["id"]]["form"] == mine["form"]   # both sides kept


def test_same_id_conflict_preserves_both_versions_as_copies():
    cloud = FakeCloud()
    ss = new_session(make_doc("Shared Tune"))
    assert save(ss, cloud)["cloud_verified"]
    mine = get_active_document(ss)
    remote = copy.deepcopy(cloud.row["composition_workspace_state"])
    rdoc = remote["library"][mine["id"]]
    apply_section_chords(rdoc, ordered_sections(rdoc)[0]["id"], parse_chord_paste("Gm7 C7 Fmaj7 Bbmaj7"))
    rdoc["updated_at"] = "9999-01-01T00:00:00+00:00"
    cloud.external_write(remote)
    apply_section_chords(mine, ordered_sections(mine)[0]["id"], parse_chord_paste("F6 G7 Cmaj7 A7"))
    save_document_to_library(ss, mine, force_disk=False)
    with wired(cloud, ss):
        ok, _ = load_cloud_and_keep_edits(ss)
    assert ok
    titles = sorted(x["title"] for x in library_rows(ss))
    assert titles == ["Shared Tune", "Shared Tune (my edits)"]
    assert ss[COMPOSER_LIBRARY_KEY][mine["id"]]["form"] == rdoc["form"]   # cloud keeps the id


def test_library_lists_all_and_separates_now_editing_from_active_song():
    a, b, c = make_doc("A"), make_doc("B"), make_doc("C")
    ss = new_session(a, b, c)
    set_active_document(ss, b, checkpoint=False)
    rows = {r["title"]: r for r in library_rows(ss, active_song_id=a["id"])}
    assert set(rows) == {"A", "B", "C"}
    assert status_badges(rows["B"]) == ["Now Editing"] and status_badges(rows["A"]) == ["Active Song"]
    assert status_badges(rows["C"]) == []
    both = {r["title"]: r for r in library_rows(ss, active_song_id=b["id"])}
    assert status_badges(both["B"]) == ["Now Editing", "Active Song"]


def test_draft_not_in_library_is_listed_and_switch_preserves_edits():
    a, b = make_doc("Saved"), make_doc("Draft")
    ss = new_session(a)
    set_active_document(ss, b, checkpoint=False)                       # never upserted
    rows = library_rows(ss)
    assert {r["title"] for r in rows} == {"Saved", "Draft"}
    assert [r for r in rows if r["title"] == "Draft"][0]["in_library"] is False
    ok, _ = switch_to_composition(ss, a["id"])
    assert ok and b["id"] in ss[COMPOSER_LIBRARY_KEY] and get_active_document(ss)["id"] == a["id"]


def test_switch_rejects_unknown_and_deleted_ids():
    ss = new_session(make_doc("A"))
    ss["composer_deleted_document_ids"] = ["gone"]
    assert not switch_to_composition(ss, "gone")[0] and not switch_to_composition(ss, "nope")[0]


def test_dirty_session_hydration_merges_earlier_compositions_without_overwrite():
    earlier = make_doc("Earlier Tune")
    remote = {"composition_workspace_state": {"schema_version": 2, "library": {earlier["id"]: earlier},
              "active_document": earlier, "library_initialized": True, "deleted_document_ids": []}}
    ss = new_session(make_doc("Jazz Tune"))
    ss["composition_workspace_state_dirty"] = True
    local_active = get_active_document(ss)["id"]
    assert apply_composition_workspace_from_payload(ss, remote) is False
    assert {r["title"] for r in library_rows(ss)} == {"Jazz Tune", "Earlier Tune"}
    assert get_active_document(ss)["id"] == local_active


def test_tombstoned_remote_documents_are_not_resurrected_by_merge():
    gone = make_doc("Deleted Tune")
    ss = new_session(make_doc("Jazz Tune"))
    ss["composition_workspace_state_dirty"] = True
    ss["composer_deleted_document_ids"] = [gone["id"]]
    remote = {"composition_workspace_state": {"schema_version": 2, "library": {gone["id"]: gone},
              "library_initialized": True, "deleted_document_ids": []}}
    apply_composition_workspace_from_payload(ss, remote)
    assert {r["title"] for r in library_rows(ss)} == {"Jazz Tune"}


def test_start_new_song_from_songs_keeps_previous_draft():
    from composition_songs_bridge import PENDING_COMPOSER_NEW_SONG_KEY, apply_pending_composer_new_song

    draft = make_doc("Unsaved Draft")
    ss = {"workspace_id": "guest"}
    set_active_document(ss, draft, checkpoint=False)
    ss[PENDING_COMPOSER_NEW_SONG_KEY] = True
    assert apply_pending_composer_new_song(ss)
    assert draft["id"] in ss[COMPOSER_LIBRARY_KEY] and get_active_document(ss) is None
