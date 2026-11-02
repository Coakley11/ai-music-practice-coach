#!/usr/bin/env python3
"""One-way sync: Music's music_resume_payload.py -> Command Center's vendored copy.

Music is the authoritative source. This script copies exactly one file, never
the reverse direction, and never touches Command Center's own sync script
(``scripts/sync_suite_cloud_modules.py`` copies the opposite way).

    python scripts/sync_music_resume_payload_to_command_center.py            # copy + verify
    python scripts/sync_music_resume_payload_to_command_center.py --check    # verify only, never writes

Command Center is located via ``--command-center`` or ``COMMAND_CENTER_REPO``,
else the sibling ``daniel-ai-command-center`` directory.
Exit status: 0 ok, 1 drift (--check) or failed verification, 2 missing path.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILENAME = "music_resume_payload.py"
COMMAND_CENTER_ENV = "COMMAND_CENTER_REPO"
DEFAULT_COMMAND_CENTER = ROOT.parent / "daniel-ai-command-center"


def resolve_command_center(explicit: str | None = None) -> Path:
    return Path(explicit or os.environ.get(COMMAND_CENTER_ENV) or DEFAULT_COMMAND_CENTER)


def source_path() -> Path:
    return ROOT / FILENAME


def destination_path(command_center: Path) -> Path:
    return command_center / FILENAME


def is_in_sync(command_center: Path) -> bool:
    """True when the vendored copy is byte-for-byte identical. Never writes."""
    src, dest = source_path(), destination_path(command_center)
    return src.is_file() and dest.is_file() and src.read_bytes() == dest.read_bytes()


def sync(command_center: Path) -> int:
    src, dest = source_path(), destination_path(command_center)
    if not src.is_file():
        print(f"error: Music source missing: {src}", file=sys.stderr)
        return 2
    if not command_center.is_dir() or not dest.parent.is_dir():
        print(f"error: Command Center repo not found: {command_center}", file=sys.stderr)
        return 2
    shutil.copyfile(src, dest)
    if src.read_bytes() != dest.read_bytes():
        print(f"error: verification failed, {dest} differs from {src}", file=sys.stderr)
        return 1
    print(f"synced {FILENAME} -> {dest} (verified byte-for-byte)")
    return 0


def check(command_center: Path) -> int:
    src, dest = source_path(), destination_path(command_center)
    if not src.is_file() or not dest.is_file():
        print(f"error: missing {src if not src.is_file() else dest}", file=sys.stderr)
        return 2
    if src.read_bytes() != dest.read_bytes():
        print(f"DRIFT: {dest} differs from Music's {FILENAME}. "
              f"Run: python scripts/sync_music_resume_payload_to_command_center.py", file=sys.stderr)
        return 1
    print(f"{FILENAME} is in sync")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--command-center", help="Command Center repo root")
    parser.add_argument("--check", action="store_true", help="verify only; never writes")
    args = parser.parse_args(argv)
    cc = resolve_command_center(args.command_center)
    return check(cc) if args.check else sync(cc)


if __name__ == "__main__":
    raise SystemExit(main())
