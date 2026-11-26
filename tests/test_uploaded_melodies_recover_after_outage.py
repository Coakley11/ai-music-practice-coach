"""A reference saved while the cloud was down is uploaded when it is saved again (Slice 4 Stage 1, 2026-11-25)."""
import pytest

import media_persistence
import media_storage
import song_document_catalog as sdc

LOCAL = {"sha256": "x", "storage_status": "local_only", "local_path": "media/a.pdf", "storage_ref": None}
CLOUD = {"sha256": "x", "storage_status": "cloud", "local_path": "media/b.pdf", "storage_ref": "supabase://b/k"}


@pytest.mark.parametrize("rows, cloud_on, want", [
    ([LOCAL], True, {}),
    ([LOCAL], False, {"storage_ref": "", "local_path": "media/a.pdf"}),
    ([LOCAL, CLOUD], True, {"storage_ref": "supabase://b/k", "local_path": "media/b.pdf"}),
    ([CLOUD], True, {"storage_ref": "supabase://b/k", "local_path": "media/b.pdf"}),
])
def test_a_local_only_copy_is_reused_only_while_the_cloud_is_off(monkeypatch, rows, cloud_on, want):
    monkeypatch.setattr(media_persistence, "list_song_documents", lambda **_k: rows)
    monkeypatch.setattr(media_storage, "_cloud_storage_enabled", lambda: cloud_on)
    assert sdc._existing_blob_for_hash("x") == want
