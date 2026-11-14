"""QA cloud pass: the cloud-write pre-flight must read Streamlit's real session state.

``st.session_state`` is a MutableMapping but not a ``dict``. The pre-flight used ``isinstance(session,
dict)`` and therefore saw an empty session in the real app: the device never looked hydrated, so every
save to an existing cloud workspace was refused as a stale conflict (and the hydrated revision was
invisible). These tests use a non-dict mapping, like Streamlit does.
"""
from __future__ import annotations

import unittest
from collections.abc import MutableMapping
from unittest import mock

import music_workspace_conditional_cloud_write as w
from music_session_mapping import as_session_mapping


class Proxy(MutableMapping):  # stands in for st.session_state: a mapping, not a dict
    def __init__(self, data=None):
        self._d = dict(data or {})
    def __getitem__(self, k): return self._d[k]
    def __setitem__(self, k, v): self._d[k] = v
    def __delitem__(self, k): del self._d[k]
    def __iter__(self): return iter(self._d)
    def __len__(self): return len(self._d)


ROW = {"song": "Say", "full_session": {"workspace_revision": 3}, "workspace_revision": 3}


def _prep(session):
    with mock.patch.object(w, "_authoritative_stored_metrics", return_value=(True, 3, dict(ROW))):
        return w.prepare_music_conditional_write(session, {"workspace_revision": 4})


class TestMappingHelper(unittest.TestCase):
    def test_accepts_dict_and_proxy_rejects_junk(self):
        p = Proxy({"a": 1})
        self.assertIs(as_session_mapping(p), p)
        d = {"a": 1}
        self.assertIs(as_session_mapping(d), d)
        self.assertEqual(as_session_mapping(None), {})
        self.assertEqual(as_session_mapping(42), {})


class TestPreflightReadsRealSession(unittest.TestCase):
    def _hydrated(self):
        from workspace_revision import APPLIED_REVISION_KEY
        return Proxy({APPLIED_REVISION_KEY: 3, "_music_authoritative_hydrated_revision": 3,
                      "_music_device_applied_revision_source": "authoritative_network_hydrate",
                      "_music_workspace_blob_hydrated": True})

    def test_hydrated_proxy_session_gets_expected_revision_and_is_not_blocked(self):
        prep = _prep(self._hydrated())
        self.assertEqual(prep["expected_revision"], 3)
        self.assertFalse(prep["blocked_precheck"])
        self.assertNotIn(w.VIOLATION_DEVICE_APPLIED_NOT_INITIALIZED, prep["violations_precheck"])

    def test_unhydrated_proxy_session_cannot_overwrite_an_existing_workspace(self):
        prep = _prep(Proxy())
        self.assertTrue(prep["blocked_precheck"])
        self.assertIn(w.VIOLATION_DEVICE_APPLIED_NOT_INITIALIZED, prep["violations_precheck"])

    def test_dict_and_proxy_behave_identically(self):
        h = self._hydrated()
        a, b = _prep(h), _prep(dict(h))
        for k in ("expected_revision", "blocked_precheck", "violations_precheck"):
            self.assertEqual(a[k], b[k], k)


if __name__ == "__main__":
    unittest.main()
