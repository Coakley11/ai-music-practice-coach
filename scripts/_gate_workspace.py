"""Isolated suite workspace helpers for identity gates (no shared daniel residue)."""
from __future__ import annotations

import json
import os
import shutil
import time
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
WORKSPACES = DATA / "workspaces"
DEFAULT_BASE_URL = "http://localhost:8501"


def unique_workspace_id(prefix: str) -> str:
    stamp = time.strftime("%Y%m%d%H%M%S")
    return f"{prefix}_{stamp}_{uuid.uuid4().hex[:8]}"


def workspace_url(base: str, workspace_id: str, *, dev: bool = True) -> str:
    q = f"suite_workspace={workspace_id}"
    if dev:
        q += "&dev=1"
    sep = "&" if "?" in base else "?"
    return f"{base.rstrip('/')}{sep}{q}"


def ensure_empty_workspace(workspace_id: str) -> Path:
    """Create a clean workspace dir with a picker-page envelope (no song residue)."""
    path = WORKSPACES / workspace_id
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)
    # Empty dirs alone can resume onto Practice; seed a Songs/picker page so gates
    # can reach Music Source without reload recovery.
    state_path = path / "music_user_state.json"
    envelope = {
        "version": 1,
        "app": "music",
        "saved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "state": {
            "studio_page": "picker",
            "session": {"studio_page": "picker"},
            "music_workspace_state": {
                "schema_version": 1,
                "workspace_id": workspace_id,
                "page": "picker",
                "studio_page": "picker",
            },
        },
    }
    state_path.write_text(json.dumps(envelope, indent=2), encoding="utf-8")
    return path


def seed_catalog_disk_state(
    workspace_id: str,
    *,
    pick_key: str = "Pop\x1fSay — John Mayer",
    title: str = "Say",
    artist: str = "John Mayer",
    key: str = "Bb",
) -> Path:
    """Write a Catalog-owned music envelope so cold start restores Catalog + USER_CATALOG."""
    ensure_empty_workspace(workspace_id)
    path = WORKSPACES / workspace_id / "music_user_state.json"
    session: dict[str, Any] = {
        "studio_page": "picker",
        "explicit_music_source_choice": "catalog_song",
        "active_music_source": "catalog_song",
        "_user_chose_catalog_music_source": True,
        "song_picker_active_source": "Song Selection (catalog song)",
        "active_catalog_pick_key": pick_key,
        "_last_catalog_state": {
            "pick_key": pick_key,
            "selected_song": {
                "title": title,
                "artist": artist,
                "key": key,
                "pick_key": pick_key,
            },
            "original_key": key,
            "display_key": key,
        },
        "_last_catalog_song_state": {
            "pick_key": pick_key,
            "selected_song": {
                "title": title,
                "artist": artist,
                "key": key,
                "pick_key": pick_key,
            },
            "original_key": key,
            "display_key": key,
        },
    }
    envelope = {
        "version": 1,
        "app": "music",
        "saved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "state": {
            "studio_page": "picker",
            "session": session,
            "active_song_state": {
                "pick_key": pick_key,
                "music_source": "catalog_song",
                "title": title,
                "artist": artist,
                "original_key": key,
                "display_key": key,
            },
            "music_workspace_state": {
                "schema_version": 1,
                "workspace_id": workspace_id,
                "page": "picker",
                "studio_page": "picker",
                "pick_key": pick_key,
            },
        },
    }
    path.write_text(json.dumps(envelope, indent=2), encoding="utf-8")
    return path


def point_active_workspace_file(workspace_id: str) -> None:
    """Persist suite_active_workspace.json so resolve_workspace_id finds this profile."""
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "suite_active_workspace.json").write_text(
        json.dumps({"workspace_id": workspace_id}, indent=2),
        encoding="utf-8",
    )


def land_songs_with_source_radio(page, v, *, timeout_ms: int = 45000) -> None:
    """Reach Songs picker with a live Catalog/Custom/Composition Music Source radio.

    Empty workspaces may briefly restore onto Practice; do not page.reload here.
    """
    deadline = time.time() + timeout_ms / 1000.0
    last_err: Exception | None = None
    while time.time() < deadline:
        try:
            if v._studio_page_id(page) != "picker":
                try:
                    nav = page.locator(".ui-nav-art-cell.nav-picker button")
                    if nav.count() and nav.first.is_visible():
                        nav.first.click(timeout=5000, no_wait_after=True)
                    else:
                        v.click_nav(page, "Songs")
                except Exception as exc:
                    last_err = exc
                v.wait_streamlit(page, 1500)
            v.wait_streamlit_idle(page, timeout_ms=5000)
            radios = page.locator("[data-testid='stRadio']")
            try:
                total = radios.count()
            except Exception:
                total = 0
            for i in range(total):
                block = radios.nth(i)
                try:
                    if not v._marker_is_live(block) or not block.is_visible():
                        continue
                    txt = block.inner_text(timeout=1500)
                except Exception:
                    continue
                if "Composition" in txt and (
                    "Custom" in txt or "catalog" in txt.lower() or "Song Selection" in txt
                ):
                    return
        except Exception as exc:
            last_err = exc
        page.wait_for_timeout(400)
    detail = f" ({last_err})" if last_err else ""
    raise RuntimeError("Songs Music Source radio never became live" + detail)


def prepare_isolated_workspace(
    prefix: str,
    *,
    seed: str = "empty",
    base_url: str | None = None,
) -> tuple[str, str]:
    """Create a unique workspace, point the active file, return (workspace_id, start_url).

    seed:
      - empty: no music_user_state.json (true fresh)
      - catalog: Catalog-owned envelope for cold-start Custom tests
    Honors GATE_WORKSPACE when set (reuses that id; still re-seeds/empties).
    """
    ws = (os.environ.get("GATE_WORKSPACE") or "").strip() or unique_workspace_id(prefix)
    if seed == "catalog":
        seed_catalog_disk_state(ws)
    else:
        ensure_empty_workspace(ws)
    point_active_workspace_file(ws)
    base = (base_url or os.environ.get("GATE_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
    url = workspace_url(base, ws)
    print(f"[workspace] isolated id={ws} seed={seed} url={url}", flush=True)
    return ws, url
