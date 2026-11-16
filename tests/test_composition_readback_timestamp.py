"""Composition save verification must not fail because a document's bookkeeping timestamp moved.

Observed against the isolated QA project under Python 3.14.10 (the version Streamlit Cloud runs): the cloud copy was
written at 04:29:31 and the copy it was compared against carried 04:29:37 - the document had been touched again after the
write, before the read-back. Nothing in the composition differed, but the content fingerprint included the document's own
``updated_at``, so every such save reported "the stored copy did not match" (and the local-copy check, which uses the same
fingerprint, could report the local copy as unverified too). Real content changes must still be detected.
"""
from __future__ import annotations

import contextlib
import copy
import io
import unittest
from unittest import mock

import composition_save_verification as csv


def _doc(doc_id="doc-1", updated="2026-11-16T04:29:31+00:00", **over):
    doc = {
        "id": doc_id, "title": "Lighthouse", "updated_at": updated, "status": "draft",
        "metadata": {"description": "A gentle folk song"},
        "global": {"bpm": 96, "time_signature": "4/4", "original_key_label": "C major", "original_key_center": "C"},
        "form": {"sections": {
            "s1": {"id": "s1", "label": "Verse", "bars": 8, "chords": [{"bars": 1, "chord": "Am"}, {"bars": 1, "chord": "F"}],
                   "melody": {"events": [{"pitch": 60, "beats": 1.0}, {"pitch": 62, "beats": 1.0}]},
                   "lyrics": {"raw_text": "The lamp keeps watch tonight", "lines": ["The lamp keeps watch tonight"]}},
            "s2": {"id": "s2", "label": "Chorus", "bars": 8, "chords": [], "melody": {"events": []}, "lyrics": {"raw_text": "", "lines": []}},
        }, "order": ["s1", "s2"]},
    }
    doc.update(over)
    return doc


def _blob(doc=None, **over):
    doc = doc or _doc()
    blob = {"active_document": doc, "library": {doc["id"]: copy.deepcopy(doc)}, "deleted_document_ids": [],
            "library_initialized": True, "needs_seed": False, "active_section_id": "s1", "focus_lane": "lyrics",
            "workflow_phase": "lyrics"}
    blob.update(over)
    return blob


class TestFingerprintIgnoresOnlyTheTimestamp(unittest.TestCase):
    def test_a_later_updated_at_alone_is_not_a_difference(self):
        saved = _blob(_doc(updated="2026-11-16T04:29:31.029556+00:00"))
        compared = _blob(_doc(updated="2026-11-16T04:29:37.906600+00:00"))        # the QA-observed pair
        self.assertEqual(csv.content_fingerprint(saved), csv.content_fingerprint(compared))

    def test_updated_at_is_ignored_in_the_library_copies_too(self):
        a, b = _blob(), _blob()
        for doc in b["library"].values():
            doc["updated_at"] = "2030-01-01T00:00:00+00:00"
        self.assertEqual(csv.content_fingerprint(a), csv.content_fingerprint(b))

    def test_a_missing_updated_at_is_equivalent_to_a_present_one(self):
        a, b = _blob(), _blob()
        b["active_document"].pop("updated_at"); [d.pop("updated_at") for d in b["library"].values()]
        self.assertEqual(csv.content_fingerprint(a), csv.content_fingerprint(b))

    def test_every_real_change_is_still_detected(self):
        base = csv.content_fingerprint(_blob())
        changes = {
            "title": lambda d: d.update(title="Another title"),
            "tempo": lambda d: d["global"].update(bpm=97),
            "meter": lambda d: d["global"].update(time_signature="3/4"),
            "key": lambda d: d["global"].update(original_key_label="G major", original_key_center="G"),
            "lyrics": lambda d: d["form"]["sections"]["s1"]["lyrics"].update(raw_text="Waves sing the ships back home"),
            "chords": lambda d: d["form"]["sections"]["s1"]["chords"].append({"bars": 1, "chord": "G"}),
            "melody": lambda d: d["form"]["sections"]["s1"]["melody"]["events"].append({"pitch": 64, "beats": 1.0}),
            "section label": lambda d: d["form"]["sections"]["s2"].update(label="Bridge"),
            "section order": lambda d: d["form"].update(order=["s2", "s1"]),
            "description": lambda d: d["metadata"].update(description="A different idea"),
        }
        for name, mutate in changes.items():
            doc = _doc(); mutate(doc)
            self.assertNotEqual(csv.content_fingerprint(_blob(doc)), base, name)

    def test_workspace_level_changes_are_still_detected(self):
        base = csv.content_fingerprint(_blob())
        self.assertNotEqual(csv.content_fingerprint(_blob(active_section_id="s2")), base)
        self.assertNotEqual(csv.content_fingerprint(_blob(deleted_document_ids=["gone"])), base)
        extra = _blob(); extra["library"]["doc-2"] = _doc("doc-2")
        self.assertNotEqual(csv.content_fingerprint(extra), base)

    def test_a_changed_timestamp_together_with_a_real_change_is_a_difference(self):
        doc = _doc(updated="2030-01-01T00:00:00+00:00"); doc["form"]["sections"]["s1"]["lyrics"]["raw_text"] = "edited"
        self.assertNotEqual(csv.content_fingerprint(_blob(doc)), csv.content_fingerprint(_blob()))

    def test_workspace_content_does_not_modify_its_input(self):
        blob = _blob(); before = copy.deepcopy(blob)
        csv.workspace_content(blob)
        self.assertEqual(blob, before)

    def test_doc_hash_and_fingerprint_agree_on_the_timestamp_rule(self):
        self.assertEqual(csv.doc_hash(_doc(updated="a")), csv.doc_hash(_doc(updated="b")))


class TestVerifyCheckpointEndToEnd(unittest.TestCase):
    """Drive verify_checkpoint with the disk and the cloud both holding the SAME content but an older document timestamp."""

    def _run(self, saved_doc, current_doc, *, disk=True, cloud=True):
        saved, expected = _blob(saved_doc), _blob(current_doc)
        session = {"_suite_persist_last_save_disk": disk, "_suite_persist_last_save_cloud": cloud}
        with mock.patch.object(csv, "_read_disk_state", return_value={}) as _d, \
                mock.patch.object(csv, "_matching_workspace", side_effect=lambda state, exp: csv.content_fingerprint(state) == csv.content_fingerprint(exp)), \
                mock.patch("suite_storage_config.cloud_storage_enabled", return_value=True), \
                mock.patch("suite_user.account_mode", return_value="cloud"), \
                mock.patch("suite_cloud_state.load_cloud_full_session", return_value=(saved, "ts")):
            _d.return_value = saved
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                result = csv.verify_checkpoint(session, expected, force_ok=True)
        return result, buf.getvalue()

    def test_same_content_with_a_newer_timestamp_verifies_on_disk_and_in_the_cloud(self):
        result, _ = self._run(_doc(updated="2026-11-16T04:29:31+00:00"), _doc(updated="2026-11-16T04:29:37+00:00"))
        self.assertTrue(result["disk_verified"])
        self.assertTrue(result["cloud_verified"])
        self.assertEqual(result["failure_code"], "")
        self.assertEqual(csv.save_feedback(result)[0], "success")

    def test_a_real_difference_is_still_reported_as_a_readback_mismatch(self):
        other = _doc(); other["form"]["sections"]["s1"]["lyrics"]["raw_text"] = "something else"
        result, _ = self._run(other, _doc())
        self.assertFalse(result["cloud_verified"])
        self.assertEqual(result["failure_code"], "readback_mismatch")


class TestFailureIsLogged(unittest.TestCase):
    def test_an_unverified_save_leaves_one_diagnosable_line(self):
        session = {"_suite_persist_last_save_disk": False, "_suite_persist_last_save_cloud": False,
                   "_music_force_save_blocked_reason": "cloud_save_unconfirmed",
                   "_suite_last_cloud_save_failure_stage": "supabase_not_configured",
                   "_suite_last_cloud_save_exception": "HTTPSConnectionPool(host='abcdefghijklmnop.supabase.co'): "
                                                       "Max retries exceeded with url: /rest/v1/x?apikey=eyJhbGciOiJIUzI1NiJ9.abcdefghijklmnopqrstuvwxyz0123456789"}
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), mock.patch("suite_storage_config.cloud_storage_enabled", return_value=True), \
                mock.patch("suite_user.account_mode", return_value="cloud"):
            result = csv.verify_checkpoint(session, _blob(), force_ok=True)
        lines = [l for l in buf.getvalue().splitlines() if l.startswith("[composition_save]")]
        self.assertEqual(len(lines), 1)
        line = lines[0]
        for token in ("status=", "failure_code=", "disk_verified=False", "cloud_verified=False", "last_save_cloud=False",
                      "cloud_stage=supabase_not_configured", "blocked_reason=cloud_save_unconfirmed"):
            self.assertIn(token, line)
        self.assertNotIn("eyJ", line)                                       # no token
        self.assertNotIn("supabase.co", line)                               # no project host / URL
        self.assertNotIn("Lighthouse", line); self.assertNotIn("lamp", line)  # no composition content
        self.assertNotEqual(result["failure_code"], "")

    def test_logging_never_breaks_a_save(self):
        class Boom(dict):
            def get(self, *a, **k):
                raise RuntimeError("session unavailable")
        csv.log_save_outcome(Boom(), {"status": "x"})                       # must not raise

    def test_a_failed_cloud_write_is_logged_without_secrets(self):
        import suite_cloud_state as scs
        result = scs.CloudSaveResult(success=False, save_cloud_full_session_return_value=False, account_resolution_attempted=True,
                                     account_id_resolved=True, account_id="00000000-0000-4000-8000-000000000000",
                                     workspace_id_resolved="daniel", cloud_document_path="music", cloud_auth_available=True,
                                     cloud_payload_built=True, cloud_payload_revision=3, failure_stage="cloud_upsert_failed",
                                     exception="boom https://x.supabase.co/rest/v1/t?k=" + "A" * 40)
        buf = io.StringIO(); session = {}
        with contextlib.redirect_stdout(buf):
            scs._record_cloud_save_result(session, result)
        out = buf.getvalue()
        self.assertIn("[music_cloud_save] FAILED stage=cloud_upsert_failed", out)
        self.assertNotIn("supabase.co", out); self.assertNotIn("A" * 40, out); self.assertNotIn("00000000-0000", out)
        ok = scs.CloudSaveResult(success=True, save_cloud_full_session_return_value=True, account_resolution_attempted=True,
                                 account_id_resolved=True, account_id="x", workspace_id_resolved="daniel", cloud_document_path="music",
                                 cloud_auth_available=True, cloud_payload_built=True, cloud_payload_revision=3)
        buf2 = io.StringIO()
        with contextlib.redirect_stdout(buf2):
            scs._record_cloud_save_result({}, ok)
        self.assertEqual(buf2.getvalue(), "")                               # successes stay silent


if __name__ == "__main__":
    unittest.main()
