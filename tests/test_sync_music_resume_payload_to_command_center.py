"""Drift check: Command Center's vendored music_resume_payload.py must equal Music's.

Music is authoritative. This test never writes; on drift it tells the developer
to run the sync script. Set COMMAND_CENTER_REPO to point at a non-sibling checkout.
"""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "sync_music_resume_payload_to_command_center",
    ROOT / "scripts" / "sync_music_resume_payload_to_command_center.py",
)
sync_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sync_mod)


def _write(path, data):
    path.write_bytes(data)
    return path


def test_vendored_copy_matches_music_authoritative_file():
    cc = sync_mod.resolve_command_center()
    if not sync_mod.destination_path(cc).is_file():
        pytest.skip(f"Command Center checkout not found at {cc} (set COMMAND_CENTER_REPO)")
    assert sync_mod.is_in_sync(cc), (
        "Command Center's music_resume_payload.py has drifted from Music's. Run: "
        "python scripts/sync_music_resume_payload_to_command_center.py"
    )


def test_sync_copies_only_the_one_file_and_verifies(tmp_path, monkeypatch):
    cc = tmp_path / "cc"
    cc.mkdir()
    other = _write(cc / "suite_deep_links.py", b"keep me")
    monkeypatch.setattr(sync_mod, "ROOT", tmp_path / "music")
    (tmp_path / "music").mkdir()
    _write(tmp_path / "music" / sync_mod.FILENAME, b"x = 1\r\n")
    _write(cc / sync_mod.FILENAME, b"stale")
    assert sync_mod.check(cc) == 1
    assert sync_mod.sync(cc) == 0
    assert (cc / sync_mod.FILENAME).read_bytes() == b"x = 1\r\n"
    assert other.read_bytes() == b"keep me"
    assert sync_mod.check(cc) == 0


def test_check_never_writes_and_missing_paths_exit_nonzero(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sync_mod, "ROOT", tmp_path / "music")
    (tmp_path / "music").mkdir()
    _write(tmp_path / "music" / sync_mod.FILENAME, b"new")
    cc = tmp_path / "cc"
    cc.mkdir()
    _write(cc / sync_mod.FILENAME, b"old")
    assert sync_mod.check(cc) == 1
    assert (cc / sync_mod.FILENAME).read_bytes() == b"old"  # --check is read-only
    assert "sync_music_resume_payload_to_command_center.py" in capsys.readouterr().err
    assert sync_mod.sync(tmp_path / "missing") == 2
    (tmp_path / "music" / sync_mod.FILENAME).unlink()
    assert sync_mod.sync(cc) == 2
