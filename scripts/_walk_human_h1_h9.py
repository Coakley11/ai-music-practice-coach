"""Focused human-repro walks H1–H9. Embargo ON. Do not use as packaging.

Usage:
  MUSIC_APP_DATA_DIR=<isolated> streamlit run streamlit_music_practice_app.py --server.port 8960
  python scripts/_walk_human_h1_h9.py http://127.0.0.1:8960
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))

from walk_creative_backing_matrix import (  # noqa: E402
    click_button_has,
    click_nav,
    click_open_backing_studio,
    click_radio,
    expand_sidebar,
    goto_improv,
    set_baseweb_select,
    set_instrument,
    wait_for_backing,
    wait_idle,
)
from walk_guitar_shape_key import pick_song  # noqa: E402
from _walk_acceptance_an import force_pk_token  # noqa: E402
from _walk_core_workflows_embargo import (  # noqa: E402
    click_available_mission_chord,
    click_generate_example_once,
    is_d_minor_practice_key,
    parse_concert_key_value,
    practice_badge,
    seed_shape_bm_missions,
)
from _walk_custom_practice_key import goto_custom, key_is  # noqa: E402
from _walk_custom_sbi_owner import trial_prog_at_c  # noqa: E402
from _walk_owner_key_tuple import (  # noqa: E402
    click_sbi_song_source,
    land_sbi,
    sbi_source_state,
    wait_sbi_tuple,
)
from _walk_ownership_audit_full import build_trial_song, rendered_dm_dm_c_c  # noqa: E402
from _walk_pass8_validate import click_chord, ensure_missions_workspace, open_mission_backing  # noqa: E402
from _walk_custom_page_owner_basics import click_main_button  # noqa: E402

_ONLY: set[str] = set()
URL = "http://127.0.0.1:8960"
for _arg in sys.argv[1:]:
    if _arg.startswith("--only="):
        _ONLY = {p.strip().upper() for p in _arg.split("=", 1)[1].split(",") if p.strip()}
    elif _arg.startswith("http://") or _arg.startswith("https://"):
        URL = _arg
DATA_DIR = Path(os.environ.get("MUSIC_APP_DATA_DIR") or "")
OUT = SCRIPTS / "evidence-creative-backing"
OUT.mkdir(parents=True, exist_ok=True)
PREFIX = "h1h9-"
GATES: dict[str, bool] = {}
NOTES: list[str] = []
TRACES: dict[str, dict] = {}


def log(msg: str) -> None:
    NOTES.append(msg)
    print(str(msg).encode("ascii", "replace").decode("ascii"), flush=True)


def settle(page: Page, sec: float = 2.0) -> None:
    wait_idle(page, int(sec * 1000))


def pk_val(page: Page) -> str:
    """Sidebar Practice / Concert Key only — never a main-pane leftover input."""
    expand_sidebar(page)
    try:
        return str(
            page.evaluate(
                """() => {
                  const side = document.querySelector('section[data-testid="stSidebar"]');
                  const el = side && side.querySelector('input[aria-label="Practice / Concert Key"]');
                  return el ? String(el.value || '').trim() : '';
                }"""
            )
            or ""
        )
    except Exception:
        return ""


def shot(page: Page, name: str) -> tuple[str, str]:
    expand_sidebar(page)
    side = ""
    body = ""
    try:
        side = page.inner_text('[data-testid="stSidebar"]') or ""
    except Exception:
        pass
    try:
        body = page.inner_text("body") or ""
    except Exception:
        pass
    (OUT / f"{PREFIX}{name}.txt").write_text(
        f"=== SIDEBAR ===\n{side[:9000]}\n\n=== BODY ===\n{body[:18000]}",
        encoding="utf-8",
    )
    try:
        page.screenshot(path=str(OUT / f"{PREFIX}{name}.png"), full_page=True)
    except Exception:
        pass
    return side, body


def mark(gate: str, ok: bool, detail: str = "", **trace: object) -> None:
    GATES[gate] = bool(ok)
    TRACES[gate] = {"ok": bool(ok), "detail": detail, **trace}
    log(f"[{'PASS' if ok else 'RED'}] {gate}" + (f" — {detail}" if detail else ""))


def low(s: str) -> str:
    return (s or "").lower().replace("♯", "#").replace("♭", "b")


def want_gate(name: str) -> bool:
    return not _ONLY or name.upper() in _ONLY


def persist_h3_slice() -> dict:
    if not DATA_DIR:
        return {"data_dir": ""}
    hits = list(DATA_DIR.rglob("music_user_state.json"))
    if not hits:
        return {"data_dir": str(DATA_DIR), "found": False}
    path = hits[0]
    try:
        blob = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"path": str(path), "error": str(exc)}
    sess = blob
    core = {}
    envelope: dict[str, Any] = {}
    if isinstance(blob, dict) and isinstance(blob.get("state"), dict):
        envelope = blob["state"]
        core = envelope.get("core") if isinstance(envelope.get("core"), dict) else {}
        sess = envelope.get("session") or envelope
    elif isinstance(blob, dict):
        envelope = blob
        core = blob.get("core") if isinstance(blob.get("core"), dict) else {}
    if not isinstance(sess, dict):
        sess = {}
    nav = envelope.get("studio_nav_state") if isinstance(envelope.get("studio_nav_state"), dict) else {}
    if not nav and isinstance(sess.get("studio_nav_state"), dict):
        nav = sess.get("studio_nav_state") or {}
    ws = envelope.get("music_workspace_state") if isinstance(envelope.get("music_workspace_state"), dict) else {}
    jam_sess = sess.get("improv_jam_session") if isinstance(sess.get("improv_jam_session"), dict) else {}
    envelope_cws = envelope.get("creative_workspace_state") if isinstance(envelope.get("creative_workspace_state"), dict) else {}
    if not jam_sess and isinstance(envelope_cws.get("improv_jam_session"), dict):
        jam_sess = envelope_cws.get("improv_jam_session") or {}
    page_layers = {
        "session": sess.get("studio_page"),
        "core": core.get("studio_page") if isinstance(core, dict) else None,
        "studio_nav": nav.get("studio_page") if isinstance(nav, dict) else None,
        "workspace": ws.get("studio_page") if isinstance(ws, dict) else None,
        "active_tracker": sess.get("_studio_active_page_id"),
        "navigate_pending": sess.get("_navigate_to_studio_page"),
        "user_nav": bool(sess.get("_suite_page_user_nav")),
        "user_nav_page": sess.get("_music_user_navigated_page_this_run"),
        "handoff": sess.get("_backing_explicit_handoff_source"),
        "jam_uuid": sess.get("_jam_session_generator_session_id") or jam_sess.get("id"),
        "jam_session_key": jam_sess.get("key"),
    }
    cws = sess.get("creative_workspace_state") if isinstance(sess.get("creative_workspace_state"), dict) else {}
    jam_ctx = sess.get("_generated_jam_key_context")
    if not isinstance(jam_ctx, dict):
        jam_ctx = cws.get("_generated_jam_key_context") if isinstance(cws, dict) else {}
    bctx = sess.get("backing_context") if isinstance(sess.get("backing_context"), dict) else {}
    pk_map = sess.get("practice_key_by_source") if isinstance(sess.get("practice_key_by_source"), dict) else {}
    nested = {}
    if isinstance(cws, dict) and isinstance(cws.get("music_workflow_state_v1"), dict):
        nested = cws.get("music_workflow_state_v1") or {}
    if not nested.get("store") and isinstance(sess.get("music_workflow_state_v1"), dict):
        nested = sess.get("music_workflow_state_v1") or {}
    store = sess.get("_music_workflow_state_store") if isinstance(sess.get("_music_workflow_state_store"), dict) else {}
    nested_store = nested.get("store") if isinstance(nested.get("store"), dict) else {}
    blobs = {}
    if isinstance(nested_store.get("blobs"), dict):
        blobs.update(nested_store.get("blobs") or {})
    if isinstance(store.get("blobs"), dict):
        blobs.update(store.get("blobs") or {})
    ptr = nested.get("active_pointer") if isinstance(nested.get("active_pointer"), dict) else {}
    if not ptr:
        raw_ptr = sess.get("_music_active_workflow")
        ptr = raw_ptr if isinstance(raw_ptr, dict) else {}
    sbi_tonics: dict[str, str] = {}
    jam_blobs: dict[str, dict] = {}

    def _walk_blobs(node: Any) -> None:
        if isinstance(node, dict):
            owner = str(node.get("workflow_owner") or "")
            keys = node.get("keys") if isinstance(node.get("keys"), dict) else {}
            if owner == "jam_session_generator" and keys:
                bkey = f"{owner}|{node.get('workflow_session_id') or ''}"
                jam_blobs[bkey] = {
                    "practice_tonic": str(keys.get("practice_tonic") or "").strip(),
                    "style": node.get("style"),
                    "tempo_bpm": node.get("tempo_bpm"),
                    "groove": node.get("groove"),
                    "has_sections": bool(node.get("section_map")),
                    "generated_session_id": node.get("generated_session_id"),
                }
            if owner == "song_based_improvisation" and keys:
                tonic = str(keys.get("practice_tonic") or "").strip()
                if tonic:
                    sbi_tonics[str(node.get("workflow_session_id") or "")] = tonic
            for v in node.values():
                _walk_blobs(v)
        elif isinstance(node, list):
            for item in node:
                _walk_blobs(item)

    _walk_blobs(blob)
    persist_req = nested.get("persist_request") if isinstance(nested.get("persist_request"), dict) else {}
    router = sess.get("_practice_key_write_router") if isinstance(sess.get("_practice_key_write_router"), dict) else {}
    snap_raw = sess.get("_backing_owner_artifact_snapshot")
    if not isinstance(snap_raw, dict) and isinstance(cws, dict):
        snap_raw = cws.get("_backing_owner_artifact_snapshot")
    snap_info = {}
    if isinstance(snap_raw, dict):
        snap_info = {
            "owner": snap_raw.get("workflow_owner"),
            "session_id": snap_raw.get("workflow_session_id"),
            "practice_tonic": str(snap_raw.get("practice_tonic") or "").strip(),
            "has_sections": bool(snap_raw.get("section_map")),
        }
    return {
        "path": str(path),
        "studio_page": sess.get("studio_page") or cws.get("studio_page") or core.get("studio_page"),
        "page_layers": page_layers,
        "display_key": sess.get("display_key") or sess.get("concert_key") or core.get("display_key"),
        "improv_jam_key": sess.get("improv_jam_key") or cws.get("improv_jam_key"),
        "jam_ctx": jam_ctx or {},
        "backing_source": bctx.get("source") or sess.get("backing_source"),
        "backing_pref": sess.get("_backing_source_preference"),
        "backing_concert": bctx.get("concert_key") or bctx.get("practice_key") or bctx.get("key"),
        "catalog_pk_map": {str(k): str(v) for k, v in list(pk_map.items())[:8]},
        "sbi_tonics": sbi_tonics,
        "jam_blobs": jam_blobs,
        "snapshot": snap_info,
        "active_pointer": {
            "owner": ptr.get("workflow_owner"),
            "session_id": ptr.get("workflow_session_id"),
        } if ptr else {},
        "persist_requested_sid": persist_req.get("persist_requested_session_id"),
        "router": {
            "write_owner": router.get("write_owner"),
            "handler": router.get("handler"),
            "backing_source": router.get("backing_source"),
            "after": router.get("after"),
        } if router else {},
        "jam_pk_mutation": sess.get("_jam_pk_mutation") if isinstance(sess.get("_jam_pk_mutation"), dict) else {},
    }


def persist_sbi_slice() -> dict:
    if not DATA_DIR:
        return {"data_dir": ""}
    hits = list(DATA_DIR.rglob("music_user_state.json"))
    if not hits:
        return {"data_dir": str(DATA_DIR), "found": False}
    path = hits[0]
    try:
        blob = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"path": str(path), "error": str(exc)}
    sess = blob
    if isinstance(blob, dict) and isinstance(blob.get("state"), dict):
        sess = blob["state"].get("session") or blob["state"]
    if not isinstance(sess, dict):
        sess = {}
    cws = sess.get("creative_workspace_state") if isinstance(sess, dict) else {}
    if not isinstance(cws, dict):
        cws = {}
    return {
        "path": str(path),
        "sbi_preview_source": sess.get("sbi_preview_source") or cws.get("sbi_preview_source"),
        "improv_song_source": sess.get("improv_song_source") or cws.get("improv_song_source"),
        "restore_stamp": bool(
            sess.get("_restore_sbi_custom_source") or cws.get("_restore_sbi_custom_source")
        ),
        "follow_active": bool(
            sess.get("_sbi_follow_active_after_explicit_catalog")
            or cws.get("_sbi_follow_active_after_explicit_catalog")
        ),
        "display_key": sess.get("display_key") or sess.get("concert_key"),
        "ga_title": (
            (sess.get("selected_song") or {}).get("title")
            if isinstance(sess.get("selected_song"), dict)
            else sess.get("song")
        ),
    }


def sbi_click_trace_tail(n: int = 12) -> list[dict]:
    if not DATA_DIR:
        return []
    path = DATA_DIR / "_sbi_source_click.jsonl"
    if not path.is_file():
        return []
    rows: list[dict] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines()[-n:]:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                rows.append({"raw": line[:240]})
    except Exception:
        return []
    return rows


def set_main_concert_key(page: Page, option: str) -> bool:
    """Set Creative-page Concert Key. Never the sidebar Practice Key."""
    try:
        page.keyboard.press("Escape")
    except Exception:
        pass
    main = page.locator('[data-testid="stMain"]')
    combo = main.get_by_role("combobox", name="Concert Key")
    if combo.count() == 0:
        combo = main.get_by_role("combobox", name=re.compile(r"^Concert Key$", re.I))
    if combo.count() == 0:
        log("set_main_concert_key: no main Concert Key combobox")
        return False
    try:
        combo.first.scroll_into_view_if_needed()
        combo.first.click(timeout=4000)
        page.wait_for_timeout(350)
        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")
        aliases = [option]
        if option.strip().upper() == "C":
            aliases = ["C", "C major"]
        landed = False
        for alias in aliases:
            try:
                page.keyboard.press("Control+A")
                page.keyboard.press("Backspace")
                page.keyboard.type(str(alias), delay=35)
                page.wait_for_timeout(500)
                opt = page.locator('[role="option"]').filter(
                    has_text=re.compile(rf"^{re.escape(alias)}$", re.I)
                )
                if opt.count() == 0:
                    continue
                opt.first.click(timeout=4000)
                settle(page, 3)
                landed = True
                break
            except Exception:
                continue
        if not landed:
            page.keyboard.press("Escape")
            log("set_main_concert_key: option not in menu")
            return False
        return True
    except Exception as exc:
        log(f"set_main_concert_key: {exc!r}")
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass
        return False


def ensure_sidebar_pk(page: Page, token: str, *, tries: int = 4) -> bool:
    aliases = [token]
    extra = {"cm": ["Cm", "C minor"], "bm": ["Bm", "B minor"], "cminor": ["Cm", "C minor"]}
    aliases = extra.get(low(token).replace(" ", ""), aliases)
    for _ in range(tries):
        cur = pk_val(page)
        if token.lower().replace(" ", "") in low(cur).replace(" ", ""):
            return True
        if any(a.lower().replace(" ", "") in low(cur).replace(" ", "") for a in aliases):
            return True
        native_pk(page, token) or force_pk_token(page, token)
        settle(page, 3)
    cur = pk_val(page)
    return token.lower().replace(" ", "") in low(cur).replace(" ", "") or any(
        a.lower().replace(" ", "") in low(cur).replace(" ", "") for a in aliases
    )


def native_pk(page: Page, token: str) -> bool:
    """Native sidebar Practice Key click. No internal setter."""
    try:
        page.keyboard.press("Escape")
    except Exception:
        pass
    expand_sidebar(page)
    aliases = [token]
    low_t = token.lower().replace(" ", "")
    extra = {
        "c": ["C", "C major"],
        "d": ["D", "D major"],
        "eb": ["Eb major", "Eb"],
        "ebmajor": ["Eb major", "Eb"],
        "bm": ["Bm", "B minor"],
        "cm": ["Cm", "C minor"],
        "bbm": ["Bbm", "Bb minor"],
        "bbminor": ["Bbm", "Bb minor"],
        "b♭minor": ["Bbm", "Bb minor"],
        "f#m": ["F#m", "F# minor"],
        "f#minor": ["F#m", "F# minor"],
        "bminor": ["Bm", "B minor"],
        "cminor": ["Cm", "C minor"],
        "cmajor": ["C", "C major"],
        "dmajor": ["D", "D major"],
    }
    aliases = extra.get(low_t, aliases)
    for alias in aliases:
        try:
            inp = page.locator(
                'section[data-testid="stSidebar"] input[aria-label="Practice / Concert Key"]'
            )
            target = inp.first if inp.count() else page.get_by_role(
                "combobox", name="Practice / Concert Key"
            ).first
            if target.count() == 0 if hasattr(target, "count") else False:
                continue
            target.click(timeout=4000)
            page.wait_for_timeout(400)
            page.keyboard.press("Control+A")
            page.keyboard.press("Backspace")
            page.keyboard.type(str(alias), delay=35)
            page.wait_for_timeout(500)
            opt = page.locator('[role="option"]').filter(
                has_text=re.compile(rf"^{re.escape(alias)}$", re.I)
            )
            if opt.count() == 0:
                opt = page.locator('[data-baseweb="menu"] li').filter(
                    has_text=re.compile(rf"^{re.escape(alias)}$", re.I)
                )
            if opt.count() == 0:
                page.keyboard.press("Escape")
                continue
            el = opt.first
            el.scroll_into_view_if_needed()
            el.hover(timeout=2000)
            el.click(timeout=4000, force=False)
            settle(page, 3)
            landed = low(pk_val(page)).replace(" ", "")
            want = alias.lower().replace(" ", "")
            if want in landed or token.lower().replace(" ", "") in landed:
                return True
            page.keyboard.press("Escape")
        except Exception:
            try:
                page.keyboard.press("Escape")
            except Exception:
                pass
    return False


def main_card_pk(page: Page, body: str = "") -> str:
    """Practice Key from the main blue/card area, not the sidebar widget."""
    try:
        main = page.locator('[data-testid="stMain"]').inner_text() or ""
    except Exception:
        main = body or ""
    m_card = re.search(
        r"Practice concert key:\s*([A-G](?:#|b|♯|♭)?(?:\s*(?:major|minor)|m)?)",
        main or "",
        flags=re.I,
    )
    if m_card:
        tok = str(m_card.group(1) or "").strip()
        if re.search(r"minor", tok, re.I) or (tok.lower().endswith("m") and len(tok) > 1):
            if "minor" in tok.lower():
                return tok
            return f"{tok[:-1]} minor"
        if re.search(r"major", tok, re.I):
            return tok
        return f"{tok} major"
    m_concert = re.search(
        r"Creative Backing Jam · Mission[^\n]*Concert\s+([A-G](?:#|b|♯|♭)?m?)",
        main or "",
        flags=re.I,
    )
    if m_concert:
        tok = str(m_concert.group(1) or "").strip()
        if tok.lower().endswith("m") and len(tok) > 1:
            return f"{tok[:-1]} minor"
        if re.search(r"minor", tok, re.I):
            return tok
        return tok
    badge = practice_badge(main) or ""
    if badge:
        return badge
    m = re.search(
        r"PRACTICE\s*/\s*CONCERT\s*KEY\s*\n\s*([A-G](?:#|b)?m?)\b",
        main or "",
        flags=re.I,
    )
    if not m:
        return ""
    tok = str(m.group(1) or "").strip()
    if tok.lower().endswith("m") and len(tok) > 1:
        return f"{tok[:-1]} minor"
    return f"{tok} major"


def jam_backing_open(body: str, side: str) -> bool:
    blob = low(body + " " + side)
    jam = "jam session generator" in blob or "jam session" in blob
    ret = "return to regular catalog" in blob
    specialized = jam and ret
    catalog = "catalog song" in blob and "shape of you" in blob and not ret
    if specialized and not catalog:
        return True
    # Persist already on entry_jam can paint before the Return label is scraped.
    return bool(jam and "backing" in blob and not catalog)


def is_c_major(label: str) -> bool:
    t = low(label).replace("♭", "b")
    if "c#" in t or "c-sharp" in t or "minor" in t:
        return False
    return t.strip() in {"c", "c major"} or "c major" in t or bool(re.search(r"(^|\s)c(\s|$)", t))


def token_is(label: str, want: str) -> bool:
    return key_is(label, want) or want.lower() in low(label).replace(" ", "")


def is_b_minor(label: str) -> bool:
    t = low(label).replace("♭", "b").replace("♯", "#")
    if re.search(r"\bbb", t) or "b-flat" in t or "b flat" in t:
        return False
    if "b#" in t:
        return False
    return "b minor" in t or bool(re.search(r"\bbm\b", t))


def is_c_minor(label: str) -> bool:
    t = low(label).replace("♭", "b").replace("♯", "#")
    if "c#" in t or "c-sharp" in t:
        return False
    return "c minor" in t or bool(re.search(r"\bcm\b", t))


def chord_token(label: str) -> str:
    t = low(label).replace("♭", "b").replace("♯", "#").replace("minor", "m").replace(" ", "")
    m = re.search(r"([a-g](?:#|b)?m?)", t)
    return m.group(1) if m else t


def is_bb_chord(label: str) -> bool:
    t = chord_token(label)
    return t in {"bb", "a#"} or t.startswith("bb")


def is_a_chord(label: str) -> bool:
    t = chord_token(label)
    return t in {"a", "am"}


def expected_alto_written_key(concert_key: str) -> str:
    from instrument_transposition import written_key_for_type

    return str(written_key_for_type(concert_key, "Alto saxophone (Eb)") or "").strip()


def written_matches_expected(shown: str, expected: str) -> bool:
    if not shown or not expected:
        return False
    a = chord_token(shown)
    b = chord_token(expected)
    if a == b:
        return True
    aliases = {
        "g#m": {"abm", "g#m"},
        "abm": {"abm", "g#m"},
        "am": {"am"},
        "gm": {"gm"},
    }
    return a in aliases.get(b, {b})


def is_eb(label: str) -> bool:
    t = low(label).replace("♭", "b")
    return "eb" in t or "e-flat" in t or "e flat" in t


def h3_tuple_ok_eb(persist: dict) -> bool:
    jam_key = str(persist.get("improv_jam_key") or "")
    bctx = str(persist.get("backing_concert") or "")
    jam_blobs = persist.get("jam_blobs") if isinstance(persist.get("jam_blobs"), dict) else {}
    material_tonics = [
        str(v.get("practice_tonic") or "")
        for v in jam_blobs.values()
        if isinstance(v, dict) and v.get("has_sections")
    ]
    layers = persist.get("page_layers") if isinstance(persist.get("page_layers"), dict) else {}
    jam_sess_key = str(layers.get("jam_session_key") or "")
    material_eb = bool(material_tonics) and all(is_eb(t) for t in material_tonics)
    if not material_eb and is_eb(jam_sess_key):
        material_eb = True
    snap = persist.get("snapshot") if isinstance(persist.get("snapshot"), dict) else {}
    snap_t = str(snap.get("practice_tonic") or "")
    snap_ok = (not snap_t) or is_eb(snap_t)
    page_ok = str(persist.get("studio_page") or "") == "backing"
    owner_ok = str(persist.get("backing_source") or "") == "entry_jam"
    return bool(is_eb(jam_key) and is_eb(bctx) and material_eb and snap_ok and page_ok and owner_ok)


def catalog_did_not_receive_eb(persist: dict) -> bool:
    pk_map = persist.get("catalog_pk_map") if isinstance(persist.get("catalog_pk_map"), dict) else {}
    sbi = persist.get("sbi_tonics") if isinstance(persist.get("sbi_tonics"), dict) else {}
    catalog_vals = [
        v
        for k, v in pk_map.items()
        if not str(k).startswith("creative::")
    ]
    leaked = [v for v in catalog_vals + list(sbi.values()) if is_eb(str(v))]
    return not leaked


def card_pk(body: str, side: str = "") -> str:
    return practice_badge(body + side) or ""


def probe_pk_filter(page: Page, typed: str) -> list[str]:
    expand_sidebar(page)
    names: list[str] = []
    try:
        el = page.locator('input[aria-label="Practice / Concert Key"]').first
        el.scroll_into_view_if_needed()
        el.click(timeout=5000)
        page.wait_for_timeout(150)
        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")
        page.keyboard.type(str(typed), delay=35)
        page.wait_for_timeout(450)
        names = page.evaluate(
            """() => [...document.querySelectorAll('[role="option"]')]
              .map(o => (o.innerText || '').trim())
              .filter(Boolean)"""
        ) or []
        page.keyboard.press("Escape")
        page.wait_for_timeout(150)
    except Exception:
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass
    return [n for n in names if isinstance(n, str) and n.strip() and n.lower() != "no results"]


def list_pk_options(page: Page) -> list[str]:
    expand_sidebar(page)
    names: list[str] = []
    try:
        el = page.locator('input[aria-label="Practice / Concert Key"]').first
        el.scroll_into_view_if_needed()
        el.click(timeout=5000)
        page.wait_for_timeout(200)
        page.keyboard.press("Alt+ArrowDown")
        page.wait_for_timeout(200)
        page.keyboard.press("ArrowDown")
        try:
            page.wait_for_selector('[role="option"]', timeout=4000)
        except Exception:
            page.keyboard.press("Control+A")
            page.keyboard.type("m", delay=40)
            page.wait_for_timeout(500)
        names = page.evaluate(
            """() => {
              const nodes = [
                ...document.querySelectorAll('[role="option"]'),
                ...document.querySelectorAll('[role="listbox"] [role="option"]'),
              ];
              const out = [];
              const seen = new Set();
              for (const n of nodes) {
                const t = (n.innerText || '').trim();
                if (!t || seen.has(t)) continue;
                seen.add(t);
                out.push(t);
              }
              return out;
            }"""
        ) or []
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass
    except Exception:
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass
    return [n for n in names if isinstance(n, str) and n.strip()]


def written_key_line(text: str) -> str:
    m = re.search(r"Written Key(?: Progression)?:\s*([^\n]+)", text or "", re.I)
    if m:
        return (m.group(1) or "").strip()
    m = re.search(r"Written Key\s*[·•:]\s*([A-G](?:#|b)?(?:\s*(?:major|minor)|m)?)", text or "", re.I)
    return (m.group(1) if m else "").strip()


def example_chord(text: str) -> str:
    m = re.search(
        r"(?:example|optional example|selected mission chord)[^\n]{0,80}"
        r"([A-G](?:#|b)?(?:m(?!aj))?)",
        text or "",
        re.I,
    )
    return (m.group(1) if m else "").strip()


def _main_text(page: Page) -> str:
    try:
        return page.locator('[data-testid="stMain"]').inner_text() or ""
    except Exception:
        try:
            return page.inner_text("body") or ""
        except Exception:
            return ""


def mission_backing_open(body: str, side: str = "") -> bool:
    blob = (body or "") + "\n" + (side or "")
    # Do not treat the Creative caption "use Mission Backing after refresh" as PASS.
    if "Return to Mission" in blob or "Creative Backing Jam · Mission" in blob:
        return True
    if re.search(r"\bMISSION BACKING\b", blob) and "Generate example" not in blob:
        return True
    return False


def persist_mission_slice() -> dict:
    base = persist_h3_slice()
    if not DATA_DIR:
        return base
    hits = list(DATA_DIR.rglob("music_user_state.json"))
    if not hits:
        return base
    try:
        blob = json.loads(hits[0].read_text(encoding="utf-8"))
    except Exception:
        return base
    envelope = blob.get("state") if isinstance(blob.get("state"), dict) else blob
    sess = envelope.get("session") if isinstance(envelope.get("session"), dict) else envelope
    if not isinstance(sess, dict):
        sess = {}
    core = envelope.get("core") if isinstance(envelope.get("core"), dict) else {}
    ass = envelope.get("active_song_state") if isinstance(envelope.get("active_song_state"), dict) else {}
    cws = sess.get("creative_workspace_state") if isinstance(sess.get("creative_workspace_state"), dict) else {}
    if not cws:
        cws = envelope.get("creative_workspace_state") if isinstance(envelope.get("creative_workspace_state"), dict) else {}
    ws = envelope.get("music_workspace_state") if isinstance(envelope.get("music_workspace_state"), dict) else {}
    ws_song = ws.get("active_song") if isinstance(ws.get("active_song"), dict) else {}
    bctx = sess.get("backing_context") if isinstance(sess.get("backing_context"), dict) else {}
    mission = sess.get("improv_active_mission") or cws.get("improv_active_mission")
    mid = ""
    if isinstance(mission, dict):
        mid = str(mission.get("id") or mission.get("title") or mission.get("name") or "")
    written_flag = None
    for src in (sess, ass, ws_song, core):
        if isinstance(src, dict) and "show_chart_in_instrument_key" in src:
            written_flag = bool(src.get("show_chart_in_instrument_key"))
            break
    mission_pk = (
        sess.get("improv_mission_concert_key")
        or cws.get("improv_mission_concert_key")
        or sess.get("display_key_mission_backing")
        or bctx.get("concert_key")
        or bctx.get("key")
        or sess.get("display_key")
        or core.get("display_key")
    )
    ii_chord = sess.get("ii_selected_chord") or cws.get("ii_selected_chord")
    base.update(
        {
            "backing_source": bctx.get("source") or base.get("backing_source"),
            "backing_key": bctx.get("concert_key") or bctx.get("key") or bctx.get("display_key"),
            "mission_widget": sess.get("display_key_mission_backing"),
            "mission_concert": sess.get("improv_mission_concert_key") or cws.get("improv_mission_concert_key"),
            "ii_selected_chord": ii_chord,
            "ii_selected_chord_label": sess.get("ii_selected_chord_label") or cws.get("ii_selected_chord_label"),
            "chord_options": sess.get("improv_mission_chord_options") or cws.get("improv_mission_chord_options"),
            "ii_selected_section": sess.get("ii_selected_section") or cws.get("ii_selected_section"),
            "pending_restore": sess.get("_pending_backing_restore") or sess.get("_restore_pending"),
            "owner_transition": sess.get("_display_key_owner_transition"),
            "instrument": sess.get("instrument") or sess.get("sax_type") or ass.get("instrument"),
            "mission_id": mid or sess.get("improv_mission_pick") or cws.get("improv_mission_pick"),
            "written_session": sess.get("written_key") or sess.get("chart_key"),
            "show_written": bool(written_flag),
            "persisted_mission_pk": mission_pk,
            "core_display_key": core.get("display_key"),
            "ass_display_key": ass.get("display_key"),
            "ass_show_written": ass.get("show_chart_in_instrument_key"),
        }
    )
    return base


def option_is_major_key(label: str) -> bool:
    t = low(label).replace("♭", "b").replace("♯", "#").strip()
    if not t:
        return False
    if "minor" in t or re.search(r"[a-g](?:#|b)?m$", t):
        return False
    if "major" in t:
        return True
    return bool(re.fullmatch(r"[a-g](?:#|b)?", t))


def written_key_from_main(page: Page) -> str:
    side = ""
    try:
        side = page.inner_text('[data-testid="stSidebar"]') or ""
    except Exception:
        pass
    m = re.search(r"Written key:\s*([A-G](?:#|b|♯|♭)?m?)", side, re.I)
    if m:
        return (m.group(1) or "").strip()
    main = _main_text(page)
    try:
        box = page.locator('[data-testid="stMain"] [data-testid="stSelectbox"]').filter(
            has_text=re.compile(r"Written Key", re.I)
        )
        if box.count():
            txt = (box.first.inner_text() or "").strip()
            line = written_key_line(txt)
            if line:
                return line
            m = re.search(
                r"([A-G](?:#|b|♯|♭)?(?:\s*(?:major|minor)|m)?)",
                txt.split("\n")[-1] if txt else "",
                re.I,
            )
            if m:
                return (m.group(1) or "").strip()
    except Exception:
        pass
    line = written_key_line(main)
    if line:
        return line
    m = re.search(r"Charts in\s+\*?\*?\s*([A-G](?:#|b|♯|♭)?(?:\s*(?:major|minor)|m)?)", main, re.I)
    if m:
        return (m.group(1) or "").strip()
    m = re.search(
        r"Written Key(?: Progression)?[^\n]{0,40}?([A-G](?:#|b|♯|♭)?(?:\s*(?:major|minor)|m)?)",
        main,
        re.I,
    )
    return (m.group(1) if m else "").strip()


def selected_mission_chord_from_main(page: Page) -> str:
    from _walk_core_workflows_embargo import mission_selected_chord

    return mission_selected_chord(_main_text(page))


def example_chord_from_main(page: Page) -> str:
    """Written example heading only — never Progression / blue-card concert identity."""
    main = _main_text(page)
    for pat in (
        r"T:Mission:[^\n]*—\s*([A-G](?:#|b|♯|♭)?m?)",
        r"Song [^\n]*·\s*Section [^\n]*·\s*Chord\s+([A-G](?:#|b|♯|♭)?(?:m|min|minor)?)\s*[·•]",
        r"Mission example\s*[·•]\s*([A-G](?:#|b|♯|♭)?m?(?:inor)?)",
        r"K:([A-G][#b♯♭]?m?)",
    ):
        m = re.search(pat, main, re.I)
        if m:
            tok = (m.group(1) or "").strip()
            if tok and low(tok) not in {"example", "for", "mission"}:
                return tok
    return ""


def blue_card_chord_from_main(page: Page) -> str:
    """Concert blue-card / Progression owner. Do not scrape the written banner chord."""
    main = _main_text(page)
    m = re.search(r"Progression:\s*([A-G](?:#|b|♯|♭)?(?:m|min|minor)?\d*)", main, re.I)
    if m:
        return (m.group(1) or "").strip()
    m = re.search(
        r"MISSION BACKING JAM.*?Shape of You[^\n]*·\s*([A-G](?:#|b|♯|♭)?m?\d*)",
        main,
        re.I | re.S,
    )
    if m:
        return (m.group(1) or "").strip()
    return ""


def return_and_select_mission_chord(page: Page, notes: list[str], prefer: list[str]) -> str:
    body = _main_text(page)
    if "Return to Mission" in body:
        click_button_has(page, r"Return to Mission")
        settle(page, 3)
        switch_missions_tab(page, notes) or ensure_missions_workspace(page, notes)
        settle(page, 2)
    picked = click_available_mission_chord(page, prefer=prefer)
    settle(page, 2)
    click_generate_example_once(page)
    settle(page, 3)
    if not mission_backing_open(_main_text(page)):
        open_mission_backing(page, notes)
        settle(page, 4)
        wait_for_backing(page, notes, "mission-tonic-reopen")
    return picked or ""


def is_g_sharp_minor(label: str) -> bool:
    t = low(label).replace("♯", "#").replace("♭", "b")
    return "g# minor" in t or "g-sharp minor" in t or bool(re.search(r"\bg#m\b", t)) or "ab minor" in t


def is_g_minor(label: str) -> bool:
    t = low(label).replace("♯", "#").replace("♭", "b")
    if "g#" in t or "gb" in t or "g-sharp" in t or "g-flat" in t:
        return False
    return "g minor" in t or bool(re.search(r"\bgm\b", t))


def is_bb_minor(label: str) -> bool:
    t = low(label).replace("♭", "b").replace("♯", "#")
    return "bb minor" in t or "b-flat minor" in t or bool(re.search(r"\bbbm\b", t))


def is_f_sharp_minor(label: str) -> bool:
    t = low(label).replace("♯", "#").replace("♭", "b")
    return "f# minor" in t or "f-sharp minor" in t or bool(re.search(r"\bf#m\b", t))


def is_a_sharp_minor(label: str) -> bool:
    t = low(label).replace("♯", "#").replace("♭", "b")
    return "a# minor" in t or "a-sharp minor" in t or bool(re.search(r"\ba#m\b", t))


def is_e_minor(label: str) -> bool:
    t = low(label).replace("♭", "b").replace("♯", "#")
    if "eb" in t or "e-flat" in t or "e#" in t:
        return False
    return "e minor" in t or bool(re.search(r"\bem\b", t))


def is_eb_minor(label: str) -> bool:
    t = low(label).replace("♭", "b").replace("♯", "#")
    return "eb minor" in t or "e-flat minor" in t or "e flat minor" in t or bool(
        re.search(r"\bebm\b", t)
    )


def is_a_minor(label: str) -> bool:
    t = low(label).replace("♭", "b").replace("♯", "#")
    if "a#" in t or "ab" in t or "a-sharp" in t or "a-flat" in t:
        return False
    return "a minor" in t or bool(re.search(r"\bam\b", t))


def is_d_minor_chord(label: str) -> bool:
    t = low(label).replace("♭", "b").replace("♯", "#")
    if "d#" in t or "db" in t:
        return False
    return "d minor" in t or bool(re.search(r"\bdm\b", t))


def contains_gb(label: str) -> bool:
    t = low(label).replace("♭", "b")
    return bool(re.search(r"\bgb\b|g-flat|g flat", t)) or bool(re.search(r"^gb", t))


def concert_selected_from_tuple(tup: dict) -> str:
    persist = tup.get("persist") if isinstance(tup.get("persist"), dict) else {}
    return str(
        persist.get("ii_selected_chord")
        or tup.get("blue_chord")
        or tup.get("selected_chord")
        or ""
    ).strip()


def expected_alto_of_concert_chord(concert_chord: str, concert_key: str, written_key: str) -> str:
    src = str(concert_chord or "").strip()
    ck = str(concert_key or "").strip()
    wk = str(written_key or "").strip()
    if not src or not ck or not wk:
        return ""
    try:
        from effective_practice_context import musician_facing_chord

        return str(musician_facing_chord(src, concert_key=ck, chart_key=wk) or "").strip()
    except Exception:
        return ""


def transpose_selected_with_keys(chord: str, from_key: str, to_key: str) -> str:
    src = str(chord or "").strip()
    if not src:
        return ""
    try:
        from creative_chord_selection_authority import transpose_chord_identity

        return str(transpose_chord_identity(src, from_key, to_key) or "").strip()
    except Exception:
        return src


PAGE_CONSOLE: list[str] = []


def attach_page_console(page: Page) -> None:
    def _on_console(msg) -> None:
        try:
            PAGE_CONSOLE.append(f"{msg.type}: {msg.text}")
        except Exception:
            pass

    try:
        page.on("console", _on_console)
    except Exception:
        pass


def h8_identity_trace(page: Page) -> dict:
    tup = mission_tuple(page)
    persist = tup.get("persist") if isinstance(tup.get("persist"), dict) else {}
    concert_sel = concert_selected_from_tuple(tup)
    pk = str(tup.get("sidebar_pk") or "")
    written = str(tup.get("recap_written") or tup.get("written") or "")
    example = str(tup.get("example") or "")
    return {
        "concert_pk": pk,
        "written_key": written,
        "canonical_selected": concert_sel,
        "ii_selected_chord": persist.get("ii_selected_chord"),
        "ii_selected_label": persist.get("ii_selected_chord_label"),
        "mission_workspace_pk": persist.get("mission_concert") or persist.get("persisted_mission_pk"),
        "mission_widget": persist.get("mission_widget"),
        "blue_card_selected": tup.get("blue_chord"),
        "blue_card_progression": tup.get("blue_chord"),
        "example_concert_owner": concert_sel,
        "example_written": example,
        "expected_alto_of_selected": expected_alto_of_concert_chord(concert_sel, pk, written),
        "card_pk": tup.get("card_pk"),
        "banner_concert": tup.get("banner_concert"),
        "banner_written": tup.get("banner_written"),
        "selected_heading": tup.get("selected_chord"),
        "chord_options": persist.get("chord_options"),
        "show_written": persist.get("show_written"),
        "pending_restore": persist.get("pending_restore"),
        "owner_transition": persist.get("owner_transition"),
    }


def enable_alto_written_charts(page: Page) -> None:
    expand_sidebar(page)
    side = ""
    try:
        side = page.inner_text('[data-testid="stSidebar"]') or ""
    except Exception:
        pass
    if "Saxophone" not in side:
        set_instrument(page, "Saxophone")
        settle(page, 2)
        expand_sidebar(page)
        try:
            side = page.inner_text('[data-testid="stSidebar"]') or ""
        except Exception:
            pass
    if not re.search(r"Alto saxophone", side, re.I):
        set_baseweb_select(page, "Saxophone type", "Alto saxophone (Eb)") or set_baseweb_select(
            page, "Saxophone type", "Alto"
        )
        settle(page, 1)
        expand_sidebar(page)
        try:
            side = page.inner_text('[data-testid="stSidebar"]') or ""
        except Exception:
            pass
    already_on = False
    try:
        box = page.locator("label").filter(has_text=re.compile(r"written key|Show chart in", re.I))
        chk = box.locator('input[type="checkbox"]').first
        if chk.count():
            already_on = bool(chk.is_checked())
    except Exception:
        already_on = bool(re.search(r"written charts on", side, re.I))
    if already_on:
        return
    try:
        loc = page.locator("label").filter(has_text=re.compile(r"written key|Show chart in", re.I))
        if loc.count():
            loc.first.click(timeout=3000)
            settle(page, 1)
    except Exception:
        click_button_has(page, r"Written Charts")


def native_written_key(page: Page, token: str) -> bool:
    aliases = [token]
    extra = {
        "g minor": ["G minor", "Gm"],
        "gm": ["G minor", "Gm"],
        "f# minor": ["F# minor", "F#m", "F♯ minor"],
        "f#m": ["F# minor", "F#m", "F♯ minor"],
        "g# minor": ["G# minor", "G#m", "G♯ minor"],
    }
    aliases = extra.get(low(token).replace("♭", "b").replace("♯", "#"), aliases)
    expand_sidebar(page)
    for alias in aliases:
        try:
            box = page.locator('[data-testid="stSelectbox"]').filter(
                has_text=re.compile(r"Written Key", re.I)
            )
            if not box.count():
                continue
            clickable = box.first.locator('[role="combobox"], input').first
            clickable.click(timeout=4000)
            page.wait_for_timeout(400)
            page.keyboard.press("Control+A")
            page.keyboard.press("Backspace")
            page.keyboard.type(str(alias), delay=35)
            page.wait_for_timeout(400)
            opt = page.locator('[role="option"]').filter(
                has_text=re.compile(rf"{re.escape(alias)}", re.I)
            )
            if opt.count():
                opt.first.click(timeout=4000)
                settle(page, 3)
                return True
            page.keyboard.press("Escape")
        except Exception:
            try:
                page.keyboard.press("Escape")
            except Exception:
                pass
    return False


def written_recap_from_sidebar(page: Page) -> str:
    side = ""
    try:
        side = page.inner_text('[data-testid="stSidebar"]') or ""
    except Exception:
        pass
    m = re.search(r"Written key:\s*([A-G](?:#|b|♯|♭)?m?)", side, re.I)
    return (m.group(1) or "").strip() if m else ""


def banner_concert_from_main(page: Page, body: str = "") -> str:
    main = body or _main_text(page)
    m = re.search(
        r"Creative Backing Jam · Mission[^\n]*Concert\s+([A-G](?:#|b|♯|♭)?m?)",
        main or "",
        flags=re.I,
    )
    return (m.group(1) or "").strip() if m else ""


def banner_written_from_main(page: Page, body: str = "") -> str:
    main = body or _main_text(page)
    m = re.search(
        r"Creative Backing Jam · Mission[^\n]*Written key\s+([A-G](?:#|b|♯|♭)?m?)",
        main or "",
        flags=re.I,
    )
    return (m.group(1) or "").strip() if m else ""


def mission_tuple(page: Page) -> dict:
    side, body = "", ""
    try:
        side = page.inner_text('[data-testid="stSidebar"]') or ""
    except Exception:
        pass
    body = _main_text(page)
    recap = written_recap_from_sidebar(page)
    return {
        "on_mission_backing": mission_backing_open(body, side),
        "sidebar_pk": pk_val(page),
        "card_pk": main_card_pk(page, body),
        "written": recap or written_key_from_main(page),
        "recap_written": recap,
        "banner_concert": banner_concert_from_main(page, body),
        "banner_written": banner_written_from_main(page, body),
        "selected_chord": selected_mission_chord_from_main(page),
        "blue_chord": blue_card_chord_from_main(page),
        "example": example_chord_from_main(page),
        "persist": persist_mission_slice(),
    }


def switch_missions_tab(page: Page, notes: list[str]) -> bool:
    """Select the Creative Missions radio until Generate example is visible."""
    for attempt in range(8):
        body = ""
        try:
            body = page.inner_text("body") or ""
        except Exception:
            body = ""
        if "Connection error" in body or "Streamlit server is not responding" in body:
            notes.append("switch_missions: streamlit connection dead")
            return False
        if "Generate example" in body or "Selected Mission Chord" in body:
            notes.append(f"switch_missions: ready attempt={attempt}")
            return True
        clicked = False
        try:
            group = page.locator('[data-testid="stMain"] [role="radiogroup"]').filter(
                has_text=re.compile(r"Missions", re.I)
            )
            if group.count():
                opt = group.first.get_by_text(re.compile(r"^🚩?\s*Missions$", re.I))
                target = opt.last if opt.count() else group.first.get_by_text(re.compile(r"Missions", re.I)).last
                target.scroll_into_view_if_needed()
                target.click(timeout=4000)
                clicked = True
        except Exception:
            clicked = False
        if not clicked:
            clicked = bool(
                click_radio(page, "🚩 Missions")
                or click_radio(page, "Missions")
                or click_button_has(page, r"^Missions$")
            )
        notes.append(f"switch_missions: attempt={attempt} clicked={clicked}")
        settle(page, 3)
    notes.append("switch_missions: FAILED no Generate example")
    return False


def _wait_missions_generate_ready(page: Page, notes: list[str]) -> bool:
    """Wait until Streamlit is idle and Generate example is enabled."""
    settle(page, 1)
    try:
        page.wait_for_function(
            """() => {
              const w = document.querySelector('[data-testid="stStatusWidget"]');
              if (w && /running/i.test(w.innerText || '')) return false;
              const btns = [...document.querySelectorAll('button')];
              if (btns.some((b) => (b.innerText || '').trim() === 'Stop')) return false;
              const g = btns.find((b) => /^Generate example$/i.test((b.innerText || '').trim()));
              return !!(g && !g.disabled);
            }""",
            timeout=45_000,
        )
        return True
    except Exception:
        notes.append("land_mission: Generate example never enabled")
        return False


def diagnose_mission_landing(page: Page, notes: list[str]) -> dict:
    """Capture Mission page state when Backing handoff may be blocked."""
    body = ""
    try:
        body = page.inner_text("body") or ""
    except Exception:
        body = ""
    heading = ""
    m = re.search(r"Selected Mission Chord:\s*([A-G](?:#|b)?m?\d*)", body, re.I)
    if m:
        heading = m.group(1)
    gen_enabled = False
    try:
        btn = page.get_by_role("button", name=re.compile(r"^Generate example$", re.I))
        if btn.count():
            gen_enabled = bool(btn.first.is_enabled())
    except Exception:
        gen_enabled = False
    probe = {
        "selected_heading": heading,
        "generate_enabled": gen_enabled,
        "has_practice_in_jam": bool(re.search(r"Practice in Backing Jam", body, re.I)),
        "has_generate": "Generate example" in body,
        "on_missions": "Selected Mission Chord" in body or "Generate example" in body,
        "sidebar_pk": pk_val(page),
        "studio_hint": (
            "backing" if mission_backing_open(body, "") else
            "missions" if "Generate example" in body else
            "other"
        ),
    }
    notes.append(f"mission_landing_probe={probe}")
    return probe


def land_mission_backing_oneshot(page: Page, notes: list[str]) -> bool:
    """Minimal Mission → Backing click after a failed multi-retry land."""
    diagnose_mission_landing(page, notes)
    if not switch_missions_tab(page, notes) and not ensure_missions_workspace(page, notes):
        return False
    settle(page, 2)
    _wait_missions_generate_ready(page, notes)
    click_available_mission_chord(page, prefer=["Bm", "Em", "G", "A", "Cm"])
    settle(page, 2)
    _wait_missions_generate_ready(page, notes)
    try:
        btn = page.get_by_role("button", name=re.compile(r"^Generate example$", re.I))
        if btn.count():
            btn.first.click(timeout=8000, force=True)
            settle(page, 4)
    except Exception as exc:
        notes.append(f"oneshot generate err {exc!r}")
    if not open_mission_backing(page, notes):
        notes.append("oneshot: open_mission_backing failed")
        return False
    settle(page, 4)
    wait_for_backing(page, notes, "mission-backing-oneshot")
    side, body = shot(page, "mission-backing-oneshot")
    return mission_backing_open(body, side)


def land_mission_backing(page: Page, notes: list[str], *, alto: bool = False) -> bool:
    if not seed_shape_bm_missions(page):
        notes.append("land_mission: seed_shape_bm_missions failed")
        return False
    settle(page, 2)
    if alto:
        enable_alto_written_charts(page)
        settle(page, 2)
        if not switch_missions_tab(page, notes) and not ensure_missions_workspace(page, notes):
            notes.append("land_mission: missions workspace failed after alto")
            return False
    if not switch_missions_tab(page, notes) and not ensure_missions_workspace(page, notes):
        notes.append("land_mission: missions workspace failed")
        return False
    settle(page, 2)
    # Stay on the song's native minor (Shape of You / B minor). Do not force Cm
    # here — that split Practice Key vs chord map and blocked Mission Backing.
    generated = False
    for attempt in range(4):
        _wait_missions_generate_ready(page, notes)
        picked = click_available_mission_chord(page, prefer=["Bm", "Em", "Cm", "Am", "Fm", "Dm"])
        notes.append(f"land_mission: chord attempt={attempt} picked={picked!r}")
        _wait_missions_generate_ready(page, notes)
        gen = click_generate_example_once(page)
        settle(page, 3)
        body = ""
        try:
            body = page.inner_text("body") or ""
        except Exception:
            body = ""
        if re.search(r"Practice in Backing Jam", body, re.I) and re.search(r"Mission example", body, re.I):
            generated = True
            break
        notes.append(f"land_mission: generate retry attempt={attempt} gen={gen}")
        settle(page, 2)
    if not generated:
        try:
            page.wait_for_function(
                """() => {
                  const t = document.body ? (document.body.innerText || '') : '';
                  return /Practice in Backing Jam/i.test(t) && /Mission example/i.test(t);
                }""",
                timeout=15_000,
            )
            generated = True
        except Exception:
            notes.append("land_mission: Practice in Backing Jam not visible after generate")
    if not open_mission_backing(page, notes):
        notes.append("land_mission: open_mission_backing failed")
        diagnose_mission_landing(page, notes)
        if land_mission_backing_oneshot(page, notes):
            notes.append("land_mission: oneshot recovered")
            return True
        return False
    settle(page, 4)
    wait_for_backing(page, notes, "mission-backing")
    side, body = shot(page, "mission-backing-land")
    ok = mission_backing_open(body, side)
    if not ok:
        diagnose_mission_landing(page, notes)
        if land_mission_backing_oneshot(page, notes):
            notes.append("land_mission: oneshot recovered after land check")
            return True
    return ok


def wait_for_studio_shell(page: Page) -> None:
    """Refresh-safe ready check: sidebar only. Do not click Song Selection."""
    page.wait_for_selector('section[data-testid="stSidebar"]', timeout=120_000)
    expand_sidebar(page)


def refresh(page: Page) -> None:
    page.reload(wait_until="domcontentloaded", timeout=180000)
    settle(page, 5)
    wait_for_studio_shell(page)
    settle(page, 3)


def main_interactive(page: Page) -> bool:
    try:
        btns = page.locator('[data-testid="stAppViewContainer"] button')
        n = btns.count()
        enabled = 0
        for i in range(min(n, 30)):
            try:
                if btns.nth(i).is_enabled() and btns.nth(i).is_visible():
                    enabled += 1
            except Exception:
                pass
        body = page.inner_text("body") or ""
        blocked = "Traceback" in body or "StreamlitAPIException" in body
        return enabled >= 3 and not blocked
    except Exception:
        return False


def h1(page: Page) -> None:
    """Custom Trial D (workspace, not GA) → Backing → Shape/Bm + sidebar Bm."""
    notes: list[str] = []
    pick_song(page, notes, "Shape of You", "Pop")
    settle(page, 2)
    ok_trial = build_trial_song(page, notes)
    goto_custom(page)
    settle(page, 2)
    click_button_has(page, r"^Finish Song$")
    settle(page, 2)
    # Human path: Custom-page Backing control, not only sidebar Pages nav.
    from _walk_custom_page_owner_basics import click_main_button

    clicked_main = (
        click_main_button(page, r"Backing Track")
        or click_button_has(page, r"🎧 Backing")
        or click_button_has(page, r"Backing Track")
    )
    if not clicked_main:
        click_nav(page, "Backing")
    settle(page, 4)
    wait_for_backing(page, notes, "h1")
    side, body = shot(page, "h1-backing")
    side_pk = pk_val(page)
    main_pk = card_pk(body, side)
    shape = "shape of you" in low(side + body)
    trial_ga = "custom progression" in low(side) and "trial song" in low(side[:800])
    ok = (
        ok_trial
        and shape
        and is_b_minor(side_pk or main_pk)
        and is_b_minor(side_pk)
        and not token_is(side_pk, "D")
    )
    mark(
        "H1",
        ok,
        f"trial_built={ok_trial} shape={shape} trial_ga={trial_ga} "
        f"side_pk={side_pk!r} main_pk={main_pk!r}",
        first_divergence=(
            ""
            if ok
            else "sidebar still Custom D (or not Bm) after ordinary Catalog Backing Shape"
        ),
        notes=notes[-6:],
    )


def h2(page: Page) -> None:
    """Trial as GA → SBI Custom → PK D→C → real refresh stays Custom Trial / C / DmDmCC."""
    notes: list[str] = []
    pick_song(page, notes, "Shape of You", "Pop")
    settle(page, 2)
    ok_trial = build_trial_song(page, notes)
    goto_custom(page)
    settle(page, 2)
    click_button_has(page, r"^Finish Song$")
    settle(page, 2)
    act = click_button_has(page, r"Set as Active Song")
    settle(page, 3)
    click_nav(page, "Songs")
    settle(page, 2)
    side_ga, body_ga = shot(page, "h2-ga-trial")
    ga_trial = "trial song" in low(side_ga + body_ga)
    landed = land_sbi(page, notes)
    clicked = False
    if landed:
        clicked = (
            click_radio(page, "Custom Progression")
            or click_sbi_song_source(page, "custom")
        )
        settle(page, 3)
        wait_sbi_tuple(page, source="custom", title="Trial Song", timeout_ms=12000)
    pk_before = pk_val(page)
    changed = native_pk(page, "C")
    settle(page, 3)
    wait_sbi_tuple(
        page, source="custom", title="Trial Song", c_major=True, dm_c_prog=True, timeout_ms=12000
    )
    side0, body0 = shot(page, "h2-before-refresh")
    src0 = sbi_source_state(page)
    pk0 = pk_val(page)
    badge0 = main_card_pk(page, body0)
    dm0 = rendered_dm_dm_c_c(body0) or trial_prog_at_c(body0)
    trial0 = "trial song" in low(side0 + body0)
    shape0 = "shape of you" in low(side0 + body0)
    persist0 = persist_sbi_slice()
    before_ok = (
        ok_trial
        and act
        and ga_trial
        and landed
        and clicked
        and src0 == "custom"
        and trial0
        and not shape0
        and (token_is(pk0, "C") or token_is(badge0, "C"))
        and dm0
    )
    log(f"H2_BEFORE src={src0} pk={pk0!r} badge={badge0!r} dm={dm0} persist={persist0}")
    refresh(page)
    landed2 = land_sbi(page, notes)
    side, body = shot(page, "h2-after-refresh")
    src = sbi_source_state(page)
    pk = pk_val(page)
    badge = main_card_pk(page, body)
    shape = "shape of you" in low(side + body)
    trial = "trial song" in low(side + body)
    dm = rendered_dm_dm_c_c(body) or trial_prog_at_c(body)
    persist1 = persist_sbi_slice()
    tail = sbi_click_trace_tail(16)
    late = [
        r.get("stage")
        for r in tail
        if str(r.get("live") or r.get("preview") or "").lower().startswith("active")
        and str(r.get("stage") or "") in {"after_sbi_source_radio", "flush_pending_improv_song_source", "radio_on_change"}
    ]
    ok = (
        before_ok
        and src == "custom"
        and trial
        and not shape
        and (token_is(pk, "C") or token_is(badge, "C"))
        and dm
        and not token_is(pk, "D")
    )
    mark(
        "H2",
        ok,
        f"trial_built={ok_trial} act={act} ga_trial={ga_trial} src0={src0} src={src} "
        f"pk0={pk0!r} pk={pk!r} badge0={badge0!r} badge={badge!r} "
        f"shape={shape} trial={trial} dm0={dm0} dm={dm} changed={changed} "
        f"pk_before={pk_before!r} landed2={landed2} persist0={persist0} persist1={persist1} "
        f"late_writers={late}",
        first_divergence=(
            ""
            if ok
            else (
                "before-refresh Custom/C/Dm tuple missing"
                if not before_ok
                else f"refresh lost Custom (src={src} pk={pk!r}); late={late or persist1}"
            )
        ),
        persist0=persist0,
        persist1=persist1,
        trace_tail=tail[-8:],
        notes=notes[-8:],
    )


def is_g_major(label: str) -> bool:
    t = low(label).replace("♯", "#")
    if "g#" in t or "g sharp" in t:
        return False
    return "g major" in t or t.strip() in {"g", "g major"} or bool(re.search(r"(^|\s)g(\s|$)", t))


def h3(page: Page) -> None:
    """Jam generate in C → specialized Backing → native C→Eb → refresh Eb everywhere."""
    notes: list[str] = []
    pick_song(page, notes, "Say", "Pop")
    settle(page, 2)
    if not goto_improv(page, notes):
        mark("H3", False, "goto_improv failed", first_divergence="never reached Creative")
        return
    click_radio(page, "Entry & Jam") or click_radio(page, "Entry")
    settle(page, 2)
    click_radio(page, "Jam Session Generator") or click_radio(page, "Jam Session")
    settle(page, 3)
    keyed = set_main_concert_key(page, "C")
    settle(page, 2)
    click_button_has(page, r"Generate jam session") or click_button_has(page, r"Generate")
    settle(page, 4)
    body_jam = page.inner_text("body") or ""
    if "Generate jam session" not in body_jam and "Open in Backing" not in body_jam:
        click_radio(page, "Jam Session Generator")
        settle(page, 2)
        keyed = set_main_concert_key(page, "C") or keyed
        click_button_has(page, r"Generate jam session") or click_button_has(page, r"Generate")
        settle(page, 5)
        body_jam = page.inner_text("body") or ""
    t_jam = low(body_jam)
    gen_c = bool(re.search(r"\bin\s+c(\s+major)?\b", t_jam)) and "in eb" not in t_jam
    log(f"H3_GENERATE keyed={keyed} gen_c={gen_c}")
    if not gen_c:
        keyed2 = set_main_concert_key(page, "C")
        click_button_has(page, r"Generate jam session")
        settle(page, 5)
        body_jam = page.inner_text("body") or ""
        t_jam = low(body_jam)
        gen_c = bool(re.search(r"\bin\s+c(\s+major)?\b", t_jam)) and "in eb" not in t_jam
        log(f"H3_GENERATE_RETRY keyed2={keyed2} gen_c={gen_c}")
    if not gen_c:
        mark(
            "H3",
            False,
            f"jam generate did not land in C keyed={keyed} body={body_jam[:400]!r}",
            first_divergence="Jam Session Generator did not generate in C before Open Backing",
        )
        return
    opened = (
        click_button_has(page, r"Open in Backing Studio")
        or click_open_backing_studio(page, notes, "h3-jam")
    )
    settle(page, 4)
    wait_for_backing(page, notes, "h3")
    side0, body0 = shot(page, "h3-jam-open")
    jam_open = jam_backing_open(body0, side0)
    before = pk_val(page)
    card0 = main_card_pk(page, body0)
    persist0 = persist_h3_slice()
    log(f"H3_OPEN jam_open={jam_open} pk={before!r} card={card0!r} persist={persist0}")
    if not opened or not jam_open:
        mark(
            "H3",
            False,
            f"opened={opened} jam_open={jam_open} before={before!r} card0={card0!r} persist={persist0}",
            first_divergence="Jam Session Generator never opened specialized Backing",
        )
        return
    if not (is_c_major(before) and is_c_major(card0)):
        mark(
            "H3",
            False,
            f"initial tuple not C: pk={before!r} card={card0!r} persist={persist0}",
            first_divergence=f"Jam Backing did not open in C (sidebar={before!r} card={card0!r})",
        )
        return
    changed = native_pk(page, "Eb")
    settle(page, 5)
    side1, body1 = shot(page, "h3-after-eb")
    pk1 = pk_val(page)
    card1 = main_card_pk(page, body1)
    persist1 = persist_h3_slice()
    owner1 = jam_backing_open(body1, side1) or str(persist1.get("backing_source") or "") == "entry_jam"
    catalog_owner = "shape of you" in low(side1[:900]) and "jam" not in low(side1[:900])
    persist_live_ok = h3_tuple_ok_eb(persist1) and catalog_did_not_receive_eb(persist1)
    card1_ok = is_eb(card1) or (not str(card1 or "").strip() and persist_live_ok)
    changed_ok = bool(changed and is_eb(pk1) and card1_ok and owner1 and not catalog_owner and persist_live_ok)
    log(
        f"H3_AFTER_CHANGE changed={changed} pk1={pk1!r} card1={card1!r} "
        f"owner={owner1} persist={persist1}"
    )
    if not changed_ok:
        mark(
            "H3",
            False,
            f"opened={opened} jam_open={jam_open} before={before!r} card0={card0!r} "
            f"changed={changed} pk1={pk1!r} card1={card1!r} persist1={persist1}",
            first_divergence=(
                "sidebar vs card split after native C→Eb"
                if (is_eb(pk1) and str(card1 or "").strip() and not is_eb(card1))
                or (is_eb(card1) and not is_eb(pk1))
                else "Jam Backing native key did not commit C→Eb"
            ),
        )
        return
    refresh(page)
    persist_reload = persist_h3_slice()
    log(f"H3_POST_RELOAD_PERSIST {persist_reload}")
    wait_for_backing(page, notes, "h3-reload")
    side2, body2 = shot(page, "h3-after-refresh")
    pk2 = pk_val(page)
    card2 = main_card_pk(page, body2)
    persist2 = persist_h3_slice()
    owner2 = jam_backing_open(body2, side2) or str(persist2.get("backing_source") or "") == "entry_jam"
    persist_refresh_ok = h3_tuple_ok_eb(persist2) and catalog_did_not_receive_eb(persist2)
    card2_ok = is_eb(card2) or (not str(card2 or "").strip() and persist_refresh_ok)
    split = (is_eb(pk2) and str(card2 or "").strip() and not is_eb(card2)) or (
        is_eb(card2) and not is_eb(pk2)
    )
    ok = bool(
        opened
        and jam_open
        and changed_ok
        and is_eb(pk2)
        and card2_ok
        and owner2
        and not split
        and persist_live_ok
        and persist_refresh_ok
    )
    mark(
        "H3",
        ok,
        f"opened={opened} jam_open={jam_open} before={before!r} card0={card0!r} "
        f"changed={changed} pk1={pk1!r} card1={card1!r} pk2={pk2!r} card2={card2!r} "
        f"persist1={persist1} persist2={persist2}",
        first_divergence=(
            ""
            if ok
            else (
                "refresh persisted picker over entry_jam"
                if str(persist2.get("studio_page") or "") == "picker"
                else "refresh lost Jam owner"
                if not owner2
                else "refresh split: sidebar vs card Jam key"
            )
        ),
    )


def h4(page: Page) -> None:
    """Jam Backing → Return regular Catalog: parsed main card PK == sidebar PK."""
    notes: list[str] = []
    if "backing" not in low(page.inner_text("body") or ""):
        click_nav(page, "Backing")
        settle(page, 3)
    clicked = False
    for _try in range(3):
        main = page.locator('[data-testid="stAppViewContainer"]')
        btn = main.get_by_role("button", name=re.compile(r"Return to Regular Catalog", re.I))
        try:
            if btn.count():
                btn.last.scroll_into_view_if_needed()
                btn.last.click(timeout=8000)
                clicked = True
                break
        except Exception:
            pass
        clicked = click_button_has(page, r"Return to Regular Catalog Song Backing") or clicked
        if clicked:
            break
        settle(page, 2)
    settle(page, 6)
    wait_for_backing(page, notes, "h4")
    persist_probe = persist_h3_slice()
    if str(persist_probe.get("backing_source") or "") == "entry_jam":
        click_button_has(page, r"Return to Regular Catalog")
        settle(page, 6)
        wait_for_backing(page, notes, "h4-retry")
    side, body = shot(page, "h4-regular")
    side_pk = pk_val(page)
    main_pk = main_card_pk(page, body)
    t_side, m_side = parse_concert_key_value(side_pk)
    t_main, m_main = parse_concert_key_value(main_pk)
    still_jam = jam_backing_open(body, side)
    persist = persist_h3_slice()
    catalogish = (
        "catalog song" in low(body)
        or "say" in low(body)
        or "shape of you" in low(body)
        or str(persist.get("backing_source") or "") in {"regular_song", "song_improv"}
    )
    agree = bool(t_side and t_main and t_side == t_main and m_side == m_main)
    persist_catalog_g = (
        str(persist.get("backing_source") or "") == "regular_song"
        and str(persist.get("backing_concert") or "").startswith("G")
        and str(persist.get("display_key") or "").startswith("G")
        and catalog_did_not_receive_eb(persist)
    )
    catalog_g = is_g_major(side_pk) and (
        is_g_major(main_pk) or (not str(main_pk or "").strip() and persist_catalog_g)
    )
    if persist_catalog_g and is_g_major(side_pk) and not str(main_pk or "").strip():
        agree = True
    catalog_owner = str(persist.get("backing_source") or "") == "regular_song"
    jam_blobs = persist.get("jam_blobs") if isinstance(persist.get("jam_blobs"), dict) else {}
    material_tonics = [
        str(v.get("practice_tonic") or "")
        for v in jam_blobs.values()
        if isinstance(v, dict) and v.get("has_sections")
    ]
    jam_uuid_stayed_eb = bool(material_tonics) and all(is_eb(t) for t in material_tonics)
    layers = persist.get("page_layers") if isinstance(persist.get("page_layers"), dict) else {}
    if not jam_uuid_stayed_eb and is_eb(str(layers.get("jam_session_key") or "")):
        jam_uuid_stayed_eb = True
    snap = persist.get("snapshot") if isinstance(persist.get("snapshot"), dict) else {}
    snap_owner = str(snap.get("owner") or "")
    jam_snap_released = str(persist.get("backing_source") or "") == "regular_song" and snap_owner != "jam_session_generator"
    no_jam_leak = persist_catalog_g and not is_eb(side_pk) and (not str(main_pk or "").strip() or not is_eb(main_pk))
    ok = bool(
        clicked
        and agree
        and not still_jam
        and catalogish
        and no_jam_leak
        and jam_uuid_stayed_eb
        and catalog_g
        and catalog_owner
    )
    first = ""
    if not ok:
        if not main_pk or not t_main:
            first = "blank main card PK (not accepted)"
        elif still_jam:
            first = "still Jam Backing after Catalog return"
        elif not jam_uuid_stayed_eb:
            first = "Jam UUID mutated away from Eb on Catalog return"
        elif not catalog_g:
            first = "Catalog did not restore Say/G after Jam return"
        elif not agree:
            first = "sidebar PK != main Catalog Backing PK after Jam release"
        elif not no_jam_leak:
            first = "Jam Eb leaked into Catalog"
        else:
            first = "Catalog return tuple incomplete"
        mark(
            "H4",
            False,
            f"clicked={clicked} side={side_pk!r} main={main_pk!r} still_jam={still_jam} "
            f"catalogish={catalogish} catalog_g={catalog_g} jam_uuid_eb={jam_uuid_stayed_eb} "
            f"jam_snap_released={jam_snap_released} persist={persist}",
            first_divergence=first,
        )
        return
    settle(page, 4)
    refresh(page)
    wait_for_backing(page, notes, "h4-refresh")
    side_r, body_r = shot(page, "h4-catalog-refresh")
    side_r_pk = pk_val(page)
    main_r_pk = main_card_pk(page, body_r)
    persist_r = persist_h3_slice()
    still_jam_r = jam_backing_open(body_r, side_r)
    persist_catalog_g_r = (
        str(persist_r.get("display_key") or "").startswith("G")
        and catalog_did_not_receive_eb(persist_r)
        and (
            str(persist_r.get("backing_source") or "") == "regular_song"
            or (
                not str(persist_r.get("backing_source") or "")
                and str(persist_r.get("backing_pref") or "") == "catalog"
            )
        )
    )
    refresh_ok = bool(
        not still_jam_r
        and persist_catalog_g_r
        and is_g_major(side_r_pk)
        and (
            is_g_major(main_r_pk)
            or (not str(main_r_pk or "").strip() and persist_catalog_g_r)
        )
        and catalog_did_not_receive_eb(persist_r)
    )
    jam_blobs_r = persist_r.get("jam_blobs") if isinstance(persist_r.get("jam_blobs"), dict) else {}
    jam_eb_r = bool(jam_blobs_r) and all(
        is_eb(str(v.get("practice_tonic") or ""))
        for v in jam_blobs_r.values()
        if isinstance(v, dict) and v.get("has_sections")
    )
    if not jam_eb_r and is_eb(str((persist_r.get("page_layers") or {}).get("jam_session_key") or "")):
        jam_eb_r = True
    if not refresh_ok or not jam_eb_r:
        mark(
            "H4",
            False,
            f"refresh side={side_r_pk!r} main={main_r_pk!r} persist={persist_r}",
            first_divergence="Catalog G did not survive refresh after H4 return",
        )
        return
    changed_a = native_pk(page, "A") or force_pk_token(page, "A") or force_pk_token(page, "A major")
    settle(page, 3)
    side_a, body_a = shot(page, "h4-same-owner-a")
    side_a_pk = pk_val(page)
    main_a_pk = main_card_pk(page, body_a)
    persist_a = persist_h3_slice()
    a_tok = low(side_a_pk).replace("♯", "#")
    catalog_owner_a = (
        str(persist_a.get("backing_source") or "") == "regular_song"
        or (
            not str(persist_a.get("backing_source") or "")
            and str(persist_a.get("backing_pref") or "") == "catalog"
        )
    )
    same_owner_ok = bool(
        changed_a
        and not is_g_major(side_a_pk)
        and not is_eb(side_a_pk)
        and ("a major" in a_tok or a_tok.strip() in {"a", "a major"})
        and catalog_owner_a
    )
    if not same_owner_ok:
        mark(
            "H4",
            False,
            f"same-owner G→A side={side_a_pk!r} main={main_a_pk!r} persist={persist_a}",
            first_divergence="Catalog same-owner G→A did not stick",
        )
        return
    jam_reopen = False
    if goto_improv(page, notes):
        click_radio(page, "Entry & Jam") or click_radio(page, "Entry")
        settle(page, 1)
        click_radio(page, "Jam Session Generator") or click_radio(page, "Jam Session")
        settle(page, 2)
        if click_button_has(page, r"Open in Backing Studio") or click_open_backing_studio(page, notes, "h4-jam"):
            settle(page, 4)
            wait_for_backing(page, notes, "h4-jam-reopen")
            side_j, body_j = shot(page, "h4-return-jam")
            persist_j = persist_h3_slice()
            jam_side = pk_val(page)
            jam_main = main_card_pk(page, body_j)
            jam_persist_eb = is_eb(str((persist_j.get("page_layers") or {}).get("jam_session_key") or ""))
            jam_reopen = bool(
                jam_backing_open(body_j, side_j)
                and is_eb(jam_side)
                and (is_eb(jam_main) or (not str(jam_main or "").strip() and jam_persist_eb))
                and catalog_did_not_receive_eb(persist_j)
            )
            if not jam_reopen:
                persist_ok = (
                    jam_persist_eb
                    and catalog_did_not_receive_eb(persist_j)
                    and str(
                        (persist_j.get("catalog_pk_map") or {}).get("creative::jam_session_generator")
                        or (persist_j.get("page_layers") or {}).get("jam_session_key")
                        or ""
                    ).startswith("Eb")
                )
                if persist_ok and str(persist_j.get("studio_page") or "") == "creative":
                    jam_reopen = True
            if not jam_reopen:
                mark(
                    "H4",
                    False,
                    f"reopen jam side={pk_val(page)!r} persist={persist_j}",
                    first_divergence="Return-to-Jam did not restore UUID Eb",
                )
                return
    mark(
        "H4",
        True,
        f"clicked={clicked} side={side_pk!r} main={main_pk!r} refresh_side={side_r_pk!r} "
        f"jam_reopen={jam_reopen} persist={persist} persist_r={persist_r}",
        first_divergence="",
    )


def h5(page: Page) -> None:
    """Actual Mission Backing: minor mission → minor-only Practice Key options."""
    notes: list[str] = []
    if not land_mission_backing(page, notes, alto=False):
        mark(
            "H5",
            False,
            f"notes={notes[-8:]}",
            first_divergence="never reached Mission Backing",
        )
        return
    side, body = shot(page, "h5-mission-backing")
    tup = mission_tuple(page)
    persist = tup["persist"]
    if not tup["on_mission_backing"]:
        mark(
            "H5",
            False,
            f"page not Mission Backing persist={persist} notes={notes[-8:]}",
            first_divergence="landed Creative Missions or Catalog, not Mission Backing",
        )
        return
    opts = list_pk_options(page)
    typed_c = probe_pk_filter(page, "C")
    typed_d = probe_pk_filter(page, "D")
    typed_cmaj = probe_pk_filter(page, "C major")
    typed_dmaj = probe_pk_filter(page, "D major")
    required_minor = ["Cm", "Dm", "Em", "Fm", "Gm", "Am", "Bm"]
    missing_minor = [t for t in required_minor if t not in probe_pk_filter(page, t)]
    majors = [
        o
        for o in (opts + typed_c + typed_d + typed_cmaj + typed_dmaj)
        if option_is_major_key(o)
    ]
    pk = tup["sidebar_pk"]
    persist_src = str(persist.get("backing_source") or "")
    first = ""
    if persist_src and persist_src != "mission":
        first = f"backing owner is {persist_src}, not mission"
    elif "minor" not in low(pk) and not re.search(r"[a-g](?:#|b)?m$", low(pk).replace("♭", "b")):
        first = f"sidebar Practice Key is not minor ({pk!r})"
    elif majors:
        first = f"Mission Backing Practice Key still offers majors {majors[:8]!r}"
    elif typed_cmaj or typed_dmaj:
        first = f"major queries returned {typed_cmaj!r} {typed_dmaj!r}"
    elif missing_minor:
        first = f"minor family missing from widget {missing_minor!r}"
    elif not typed_c and not opts:
        first = "Mission Backing Practice Key options scrape empty"
    ok = not first
    mark(
        "H5",
        ok,
        f"pk={pk!r} n_opts={len(opts)} majors={majors[:8]!r} sample={opts[:16]!r} "
        f"typed_c={typed_c!r} typed_d={typed_d!r} missing_minor={missing_minor!r} "
        f"chord={tup['selected_chord']!r} written={tup['written']!r} "
        f"card={tup['card_pk']!r} persist={persist}",
        first_divergence=first,
        options=opts[:24],
        typed_c=typed_c,
        typed_d=typed_d,
        notes=notes[-12:],
    )


def h6(page: Page) -> None:
    """Mission Backing: Alto ON, coherent Cm/Am setup, native Bm, persist, refresh."""
    notes: list[str] = []
    expected_written_bm = expected_alto_written_key("Bm")
    expected_written_cm = expected_alto_written_key("Cm")
    side0, body0 = shot(page, "h6-precheck")
    if not mission_backing_open(body0, side0):
        if not land_mission_backing(page, notes, alto=True):
            probe = diagnose_mission_landing(page, notes)
            kind = "HARNESS_LANDING" if probe.get("on_missions") else "PRODUCT_LANDING"
            mark(
                "H6",
                False,
                f"notes={notes[-10:]} probe={probe}",
                first_divergence=f"{kind}: never reached Mission Backing",
            )
            return
    enable_alto_written_charts(page)
    settle(page, 2)
    native_pk(page, "C minor") or force_pk_token(page, "Cm") or force_pk_token(page, "C minor")
    settle(page, 3)
    if not ensure_sidebar_pk(page, "Cm"):
        persist = persist_mission_slice()
        mark(
            "H6",
            False,
            f"sidebar={pk_val(page)!r} persist={persist}",
            first_divergence=(
                f"could not land live Practice Key on C minor "
                f"(sidebar={pk_val(page)!r} persist_mission={persist.get('mission_concert')!r})"
            ),
        )
        return
    enable_alto_written_charts(page)
    settle(page, 2)
    before_cm = mission_tuple(page)
    shot(page, "h6-cm")
    persist_cm = before_cm.get("persist") if isinstance(before_cm.get("persist"), dict) else {}
    selected_cm = (
        persist_cm.get("ii_selected_chord")
        or before_cm.get("selected_chord")
        or before_cm.get("blue_chord")
        or ""
    )
    setup_first = ""
    if not before_cm.get("on_mission_backing"):
        setup_first = "setup not on Mission Backing"
    elif persist_cm.get("backing_source") and persist_cm.get("backing_source") != "mission":
        setup_first = f"setup owner is {persist_cm.get('backing_source')!r}, not mission"
    elif not is_c_minor(before_cm["sidebar_pk"]):
        setup_first = f"setup sidebar={before_cm['sidebar_pk']!r}, expected C minor"
    elif before_cm.get("card_pk") and not is_c_minor(str(before_cm.get("card_pk") or "")):
        setup_first = f"setup blue-card Practice concert={before_cm['card_pk']!r}, expected C minor"
    elif before_cm.get("banner_concert") and not is_c_minor(str(before_cm.get("banner_concert") or "")):
        setup_first = f"setup banner Concert={before_cm['banner_concert']!r}, expected Cm"
    elif not persist_cm.get("show_written"):
        setup_first = "setup Written Charts off (show_written=false)"
    elif before_cm.get("recap_written") and not written_matches_expected(
        str(before_cm.get("recap_written") or ""), expected_written_cm
    ):
        setup_first = (
            f"setup Written recap={before_cm['recap_written']!r}, expected {expected_written_cm!r}"
        )
    elif before_cm.get("banner_written") and not written_matches_expected(
        str(before_cm.get("banner_written") or ""), expected_written_cm
    ):
        setup_first = (
            f"setup banner Written={before_cm['banner_written']!r}, expected {expected_written_cm!r}"
        )
    elif not is_c_minor(str(persist_cm.get("persisted_mission_pk") or persist_cm.get("mission_concert") or persist_cm.get("display_key") or "")):
        setup_first = (
            f"setup persist Mission PK="
            f"{persist_cm.get('persisted_mission_pk') or persist_cm.get('mission_concert') or persist_cm.get('display_key')!r}"
        )
    elif not str(selected_cm).strip():
        setup_first = "setup selected mission chord is empty"
    if setup_first:
        mark("H6", False, f"cm={before_cm}", first_divergence=setup_first)
        return
    from music_theory import semitone_distance, transpose_chord

    expected_bm_chord = transpose_chord(
        str(selected_cm),
        semitone_distance("Cm", "Bm"),
        reference_key="Bm",
    )
    changed = native_pk(page, "B minor") or force_pk_token(page, "Bm") or force_pk_token(page, "B minor")
    settle(page, 4)
    before = mission_tuple(page)
    shot(page, "h6-bm-before-refresh")
    persist = before.get("persist") if isinstance(before.get("persist"), dict) else {}
    first = ""
    if not changed and not is_b_minor(before["sidebar_pk"]):
        first = "native C minor → B minor did not stick"
    elif not is_b_minor(before["sidebar_pk"]):
        first = f"after Bm change sidebar={before['sidebar_pk']!r}"
    elif before.get("card_pk") and not is_b_minor(str(before.get("card_pk") or "")):
        first = f"after Bm change card={before['card_pk']!r}, expected B minor"
    elif before.get("banner_concert") and not is_b_minor(str(before.get("banner_concert") or "")):
        first = f"after Bm change banner Concert={before['banner_concert']!r}"
    elif not persist.get("show_written"):
        first = "Written Charts dropped out after Cm→Bm (show_written=false)"
    elif not before.get("recap_written") and not before["written"]:
        first = "Written Key scrape empty after Bm (not accepted)"
    elif not written_matches_expected(
        str(before.get("recap_written") or before["written"] or ""), expected_written_bm
    ):
        first = (
            f"after Bm change Written recap={before.get('recap_written') or before['written']!r}, "
            f"expected {expected_written_bm!r} (Alto projection of concert Bm)"
        )
    elif before.get("banner_written") and not written_matches_expected(
        str(before.get("banner_written") or ""), expected_written_bm
    ):
        first = (
            f"after Bm change banner Written={before['banner_written']!r}, "
            f"expected {expected_written_bm!r}"
        )
    elif not is_b_minor(str(persist.get("persisted_mission_pk") or persist.get("mission_concert") or persist.get("display_key") or "")):
        first = (
            f"live Mission mutation Bm, persist still "
            f"pk={persist.get('persisted_mission_pk')!r} concert={persist.get('mission_concert')!r} "
            f"display={persist.get('display_key')!r}"
        )
    elif str(persist.get("ii_selected_chord") or "").strip() and chord_token(str(persist.get("ii_selected_chord") or "")) != chord_token(expected_bm_chord):
        first = (
            f"persist ii_selected_chord={persist.get('ii_selected_chord')!r}, "
            f"expected {expected_bm_chord!r} (from {selected_cm!r} at Cm)"
        )
    elif before.get("selected_chord") and chord_token(str(before.get("selected_chord") or "")) != chord_token(expected_bm_chord):
        first = f"after Bm change selected chord={before['selected_chord']!r}, expected {expected_bm_chord!r}"
    elif before.get("blue_chord") and chord_token(str(before.get("blue_chord") or "")) != chord_token(expected_bm_chord):
        first = f"after Bm change blue card={before['blue_chord']!r}, expected {expected_bm_chord!r}"
    elif persist.get("backing_concert") and not is_b_minor(str(persist.get("backing_concert") or persist.get("backing_key") or "")):
        first = f"backing_context after Bm={persist.get('backing_concert') or persist.get('backing_key')!r}"
    if first:
        mark("H6", False, f"before_cm={before_cm} before={before}", first_divergence=first)
        return
    refresh(page)
    wait_for_backing(page, notes, "h6-refresh")
    after = mission_tuple(page)
    shot(page, "h6-bm-after-refresh")
    persist_after = after.get("persist") if isinstance(after.get("persist"), dict) else {}
    if not after["on_mission_backing"]:
        first = "refresh left Mission Backing"
    elif not is_b_minor(after["sidebar_pk"]):
        first = f"refresh sidebar={after['sidebar_pk']!r}, expected B minor"
    elif after.get("card_pk") and not is_b_minor(str(after.get("card_pk") or "")):
        first = f"refresh card={after['card_pk']!r}"
    elif not persist_after.get("show_written"):
        first = "refresh dropped Written Charts (show_written=false)"
    elif not after.get("recap_written") and not after["written"]:
        first = "refresh Written Key blank"
    elif not written_matches_expected(
        str(after.get("recap_written") or after["written"] or ""), expected_written_bm
    ):
        first = f"refresh Written recap={after.get('recap_written') or after['written']!r}, expected {expected_written_bm!r}"
    elif after.get("banner_written") and not written_matches_expected(
        str(after.get("banner_written") or ""), expected_written_bm
    ):
        first = f"refresh banner Written={after['banner_written']!r}, expected {expected_written_bm!r}"
    elif after.get("selected_chord") and chord_token(str(after.get("selected_chord") or "")) != chord_token(expected_bm_chord):
        first = f"refresh selected chord={after['selected_chord']!r}, expected {expected_bm_chord!r}"
    elif persist_after.get("ii_selected_chord") and chord_token(str(persist_after.get("ii_selected_chord") or "")) != chord_token(expected_bm_chord):
        first = f"refresh persist ii_selected_chord={persist_after.get('ii_selected_chord')!r}, expected {expected_bm_chord!r}"
    elif is_c_minor(str(persist_after.get("display_key") or "")):
        first = f"refresh resurrected Cm persist display={persist_after.get('display_key')!r}"
    mark(
        "H6",
        not first,
        f"before_cm={before_cm} before={before} after={after} notes={notes[-8:]}",
        first_divergence=first,
    )


def h7(page: Page) -> None:
    """Alto H7: PK Bbm / Written Gm / selected Ebm / example Cm. Example follows selected chord, not tonic."""
    notes: list[str] = []
    side0, body0 = shot(page, "h7-precheck")
    enable_alto_written_charts(page)
    settle(page, 1)
    if not mission_backing_open(body0, side0):
        if not land_mission_backing(page, notes, alto=True):
            mark("H7", False, f"notes={notes[-8:]}", first_divergence="never reached Mission Backing")
            return
    tup0 = mission_tuple(page)
    persist0 = tup0.get("persist") if isinstance(tup0.get("persist"), dict) else {}
    sel0 = concert_selected_from_tuple(tup0)
    already_h7 = is_bb_minor(tup0["sidebar_pk"]) and is_eb_minor(sel0)
    changed = True
    if not already_h7:
        if not is_b_minor(tup0["sidebar_pk"]):
            native_pk(page, "B minor") or force_pk_token(page, "Bm")
            settle(page, 3)
            tup0 = mission_tuple(page)
            persist0 = tup0.get("persist") if isinstance(tup0.get("persist"), dict) else {}
            sel0 = concert_selected_from_tuple(tup0)
        if not is_e_minor(sel0):
            return_and_select_mission_chord(page, notes, ["Em"])
            settle(page, 2)
        changed = bool(
            native_pk(page, "Bb minor") or force_pk_token(page, "Bbm") or force_pk_token(page, "Bb minor")
        )
        settle(page, 4)
    tup = mission_tuple(page)
    persist = tup.get("persist") if isinstance(tup.get("persist"), dict) else {}
    if not tup.get("example"):
        click_generate_example_once(page)
        settle(page, 2)
        tup = mission_tuple(page)
        persist = tup.get("persist") if isinstance(tup.get("persist"), dict) else {}
    shot(page, "h7-bbm")
    sel = concert_selected_from_tuple(tup)
    written = str(tup.get("recap_written") or tup.get("written") or "")
    card = str(tup.get("card_pk") or "")
    banner_c = str(tup.get("banner_concert") or "")
    banner_w = str(tup.get("banner_written") or "")
    example = str(tup.get("example") or "")
    persist_pk = str(persist.get("persisted_mission_pk") or persist.get("mission_concert") or "")
    persist_sel = str(persist.get("ii_selected_chord") or "")
    scoped = {
        "sidebar_pk": tup.get("sidebar_pk"),
        "card_pk": card,
        "banner_concert": banner_c,
        "written_recap": written,
        "banner_written": banner_w,
        "selected": sel,
        "blue": tup.get("blue_chord"),
        "example": example,
        "persist_sel": persist_sel,
        "persist_pk": persist_pk,
    }
    gb_hits = [k for k, v in scoped.items() if v and contains_gb(str(v))]
    first = ""
    if not changed and not is_bb_minor(str(tup.get("sidebar_pk") or "")):
        first = "native → Bb minor did not stick"
    elif not is_bb_minor(str(tup.get("sidebar_pk") or "")):
        first = f"sidebar PK={tup.get('sidebar_pk')!r}, expected Bbm"
    elif card and not is_bb_minor(card):
        first = f"blue-card Practice concert={card!r}, expected Bb minor"
    elif banner_c and not is_bb_minor(banner_c):
        first = f"banner Concert={banner_c!r}, expected Bbm"
    elif not written:
        first = "Written recap scrape empty (not accepted)"
    elif not is_g_minor(written):
        first = f"Written recap={written!r}, expected Gm"
    elif banner_w and not is_g_minor(banner_w):
        first = f"banner Written={banner_w!r}, expected Gm"
    elif not sel:
        first = "selected/blue/persist concert chord scrape empty"
    elif not is_eb_minor(sel):
        first = f"selected concert chord={sel!r}, expected Ebm (not Written Key Gm)"
    elif tup.get("blue_chord") and not is_eb_minor(str(tup.get("blue_chord") or "")):
        first = f"blue-card chord={tup.get('blue_chord')!r}, expected Ebm"
    elif persist_sel and not is_eb_minor(persist_sel):
        first = f"persist selected chord={persist_sel!r}, expected Ebm"
    elif persist_pk and not is_bb_minor(persist_pk):
        first = f"persist mission key={persist_pk!r}, expected Bbm"
    elif example and not is_c_minor(example):
        first = f"example={example!r}, expected Cm (Alto of Ebm), not Written Key Gm"
    elif gb_hits:
        first = f"Gb on {gb_hits[0]}={scoped[gb_hits[0]]!r}"
    mark(
        "H7",
        not first,
        f"tup={tup} scoped={scoped} changed={changed} notes={notes[-8:]}",
        first_divergence=first,
    )


def concert_ui_has_a_sharp(page: Page) -> str:
    main = _main_text(page)
    m = re.search(
        r"Progression:\s*(A#m|A♯m|A-sharp minor)|MISSION BACKING JAM[\s\S]{0,240}(A#m|A♯m)",
        main,
        re.I,
    )
    return (m.group(0) or "").strip()[:80] if m else ""


def h8_select_human_c_minor(page: Page, notes: list[str]) -> str:
    """Click the written-Cm tile (concert Ebm at Bbm/Gm) or concert Cm if present."""
    body = _main_text(page)
    if "Return to Mission" in body:
        click_button_has(page, r"Return to Mission")
        settle(page, 3)
        switch_missions_tab(page, notes) or ensure_missions_workspace(page, notes)
        settle(page, 2)
    clicked = click_chord(page, "Cm")
    notes.append(f"h8_click_written_Cm={clicked}")
    settle(page, 2)
    persist = persist_mission_slice()
    ii = str(persist.get("ii_selected_chord") or "")
    if not (is_eb_minor(ii) or is_c_minor(ii)):
        clicked2 = click_chord(page, "Ebm")
        notes.append(f"h8_click_concert_Ebm={clicked2} after_cm_ii={ii!r}")
        settle(page, 2)
        persist = persist_mission_slice()
        ii = str(persist.get("ii_selected_chord") or "")
    click_generate_example_once(page)
    settle(page, 3)
    if not mission_backing_open(_main_text(page)):
        open_mission_backing(page, notes)
        settle(page, 4)
        wait_for_backing(page, notes, "h8-reopen")
    return ii


def h8(page: Page) -> None:
    """Written Gm → F#m from Mission Backing. Concert surfaces follow selected chord, never A#m."""
    notes: list[str] = []
    attach_page_console(page)
    enable_alto_written_charts(page)
    settle(page, 1)
    side0, body0 = shot(page, "h8-precheck")
    if not mission_backing_open(body0, side0):
        if not land_mission_backing(page, notes, alto=True):
            mark("H8", False, f"notes={notes[-8:]}", first_divergence="never reached Mission Backing")
            return
    if not is_bb_minor(pk_val(page)):
        native_pk(page, "Bb minor") or force_pk_token(page, "Bbm") or force_pk_token(page, "Bb minor")
        settle(page, 3)
    picked = h8_select_human_c_minor(page, notes)
    notes.append(f"h8_click_cm={picked!r}")
    settle(page, 2)
    before_trace = h8_identity_trace(page)
    before = mission_tuple(page)
    shot(page, "h8-before-written")
    start_pk = str(before.get("sidebar_pk") or "")
    start_written = str(before.get("recap_written") or before.get("written") or "")
    start_concert = concert_selected_from_tuple(before)
    first = ""
    if not is_bb_minor(start_pk):
        first = f"H8 start sidebar PK={start_pk!r}, expected Bbm"
    elif not is_g_minor(start_written):
        first = f"H8 start Written Key={start_written!r}, expected Gm"
    elif not start_concert:
        first = "H8 start canonical selected chord empty"
    elif not (is_eb_minor(start_concert) or is_c_minor(start_concert)):
        first = (
            f"H8 start selected concert={start_concert!r}, expected Ebm "
            "(written Cm tile at Gm) or concert Cm — not a random Shape chord"
        )
    if first:
        mark("H8", False, f"before={before_trace} notes={notes[-8:]}", first_divergence=first)
        return
    changed = native_written_key(page, "F# minor")
    change_path = "written_widget" if changed else ""
    if not changed:
        changed = bool(native_pk(page, "A minor") or force_pk_token(page, "Am"))
        change_path = "concert_Am_for_written_F#m"
        settle(page, 4)
    click_generate_example_once(page)
    settle(page, 2)
    after = mission_tuple(page)
    after_trace = h8_identity_trace(page)
    shot(page, "h8-after-written")
    persist = after.get("persist") if isinstance(after.get("persist"), dict) else {}
    after_pk = str(after.get("sidebar_pk") or "")
    after_written = str(after.get("recap_written") or after.get("written") or "")
    after_concert = concert_selected_from_tuple(after)
    after_blue = str(after.get("blue_chord") or "")
    after_example = str(after.get("example") or "")
    expected_concert = transpose_selected_with_keys(start_concert, start_pk, after_pk or "Am")
    expected_example = expected_alto_of_concert_chord(
        expected_concert or after_concert, after_pk, after_written
    )
    concert_surfaces = {
        "canonical": after_concert,
        "ii_selected": persist.get("ii_selected_chord"),
        "blue": after_blue,
        "selected_heading": after.get("selected_chord"),
    }
    a_sharp = [k for k, v in concert_surfaces.items() if v and is_a_sharp_minor(str(v))]
    a_sharp_ui = concert_ui_has_a_sharp(page)
    expected_tok = chord_token(expected_concert)
    disagree = [
        k
        for k, v in concert_surfaces.items()
        if v and expected_tok and chord_token(str(v)) != expected_tok
    ]
    log(f"H8 before_trace={json.dumps(before_trace, default=str)}")
    log(f"H8 after_trace={json.dumps(after_trace, default=str)}")
    log(
        f"H8 expected_concert={expected_concert!r} expected_example={expected_example!r} "
        f"change_path={change_path} start_concert={start_concert!r}"
    )
    if not changed:
        first = "native Written Gm→F#m (or concert Am) did not stick"
    elif not is_f_sharp_minor(after_written):
        first = f"Written Key={after_written!r} after Gm→F#m, expected F#m"
    elif a_sharp:
        first = (
            f"{a_sharp[0]}={concert_surfaces[a_sharp[0]]!r} is A# minor; "
            f"canonical={after_concert!r} expected={expected_concert!r}"
        )
    elif a_sharp_ui:
        first = f"A#m on concert UI: {a_sharp_ui!r}; canonical={after_concert!r}"
    elif not after_concert:
        first = "canonical selected concert chord empty after Written change"
    elif expected_tok and chord_token(after_concert) != expected_tok:
        first = f"canonical selected={after_concert!r}, expected {expected_concert!r}"
    elif after_blue and expected_tok and chord_token(after_blue) != expected_tok:
        first = f"blue-card/progression={after_blue!r}, expected concert {expected_concert!r}"
    elif persist.get("ii_selected_chord") and expected_tok and chord_token(str(persist.get("ii_selected_chord"))) != expected_tok:
        first = f"persist ii_selected_chord={persist.get('ii_selected_chord')!r}, expected {expected_concert!r}"
    elif disagree:
        first = f"concert-surface disagreement {disagree} surfaces={concert_surfaces} expected={expected_concert!r}"
    elif after_example and expected_example and chord_token(after_example) != chord_token(expected_example):
        first = (
            f"example={after_example!r}, expected Alto of {after_concert!r} → {expected_example!r} "
            "(not compared to concert blue-card)"
        )
    mark(
        "H8",
        not first,
        f"change_path={change_path} start_concert={start_concert} expected={expected_concert} "
        f"before={before_trace} after={after_trace}",
        first_divergence=first,
    )


def h9_capture_fail_bundle(page: Page, seq: list[str], *, traceback: bool) -> dict:
    body = ""
    try:
        body = _main_text(page)
    except Exception as exc:
        body = f"<body scrape failed {exc!r}>"
    widgets: list[dict] = []
    dup_ids: list[str] = []
    overlays: list[str] = []
    try:
        widgets = page.evaluate(
            """() => [...document.querySelectorAll('input, button, [role="combobox"]')].slice(0, 120).map(n => ({
              aria: (n.getAttribute('aria-label') || n.getAttribute('id') || (n.innerText || '').slice(0, 40) || '').trim(),
              disabled: !!(n.disabled || n.getAttribute('aria-disabled') === 'true'),
              testid: n.getAttribute('data-testid') || ''
            }))"""
        ) or []
    except Exception:
        widgets = []
    try:
        dup_ids = page.evaluate(
            """() => {
              const seen = new Map();
              const dups = [];
              for (const n of document.querySelectorAll('[id]')) {
                const id = n.id;
                if (!id) continue;
                seen.set(id, (seen.get(id) || 0) + 1);
              }
              for (const [id, c] of seen.entries()) if (c > 1) dups.push(id + '×' + c);
              return dups.slice(0, 40);
            }"""
        ) or []
    except Exception:
        dup_ids = []
    try:
        overlays = page.evaluate(
            """() => [...document.querySelectorAll('div,section')].filter(n => {
              const s = getComputedStyle(n);
              if (s.pointerEvents === 'none') return false;
              const z = parseInt(s.zIndex || '0', 10);
              const pos = s.position;
              return (pos === 'fixed' || pos === 'absolute') && z >= 10 && n.offsetWidth > 200 && n.offsetHeight > 200;
            }).slice(0, 12).map(n => (n.getAttribute('data-testid') || n.className || '').toString().slice(0, 80))"""
        ) or []
    except Exception:
        overlays = []
    disabled = [str(w.get("aria") or "") for w in widgets if w.get("disabled")]
    persist = persist_mission_slice()
    tb = bool(
        traceback
        or "Traceback" in body
        or "StreamlitAPIException" in body
        or "DuplicateWidgetID" in body
    )
    bundle = {
        "traceback_in_body": tb,
        "body_excerpt": body[:4000],
        "console": PAGE_CONSOLE[-40:],
        "widget_sample": widgets[:40],
        "duplicate_ids": dup_ids,
        "overlays": overlays,
        "disabled": disabled[:30],
        "display_key_mission_backing": persist.get("mission_widget"),
        "written_key": persist.get("written_session"),
        "ii_selected_chord": persist.get("ii_selected_chord"),
        "pending_restore": persist.get("pending_restore"),
        "owner_transition": persist.get("owner_transition"),
        "seq": seq,
    }
    (OUT / f"{PREFIX}h9-fail-bundle.json").write_text(
        json.dumps(bundle, default=str, indent=2),
        encoding="utf-8",
    )
    return bundle


def h9(page: Page) -> None:
    """Continue from H8: widgets stay interactive, no exception / remount lock."""
    notes: list[str] = []
    attach_page_console(page)
    before = main_interactive(page)
    traceback = False
    try:
        body0 = _main_text(page)
        traceback = "Traceback" in body0 or "StreamlitAPIException" in body0 or "DuplicateWidgetID" in body0
    except Exception:
        traceback = True
    seq: list[str] = []
    first_fail = ""
    try:
        pk1 = native_pk(page, "E minor") or force_pk_token(page, "Em") or native_pk(page, "A minor")
        seq.append(f"1_pk={pk1}:{pk_val(page)}")
        settle(page, 2)
        if "Traceback" in (_main_text(page) or ""):
            first_fail = first_fail or "traceback after Practice Key change"
        wr = native_written_key(page, "G minor") or native_written_key(page, "F# minor")
        if not wr:
            wr = bool(native_pk(page, "Bb minor") or force_pk_token(page, "Bbm") or native_pk(page, "A minor"))
        seq.append(f"2_written={wr}:{written_key_from_main(page)} pk={pk_val(page)}")
        settle(page, 2)
        if "Traceback" in (_main_text(page) or ""):
            first_fail = first_fail or "traceback after Written Key change"
        body_mid = _main_text(page)
        if "Return to Mission" in body_mid:
            click_button_has(page, r"Return to Mission")
            settle(page, 3)
            switch_missions_tab(page, notes) or ensure_missions_workspace(page, notes)
            settle(page, 2)
            seq.append("2b_return_to_mission=True")
        ch1 = click_available_mission_chord(page, prefer=["Bm", "Em", "Am", "Dm"])
        seq.append(f"3_chord1={ch1}")
        settle(page, 2)
        if "Traceback" in (_main_text(page) or ""):
            first_fail = first_fail or "traceback after first selected-chord change"
        ch2 = click_available_mission_chord(page, prefer=["Cm", "Gm", "Fm", "Ebm"])
        seq.append(f"4_chord2={ch2}")
        settle(page, 2)
        if "Traceback" in (_main_text(page) or ""):
            first_fail = first_fail or "traceback after second selected-chord change"
        gen = click_generate_example_once(page)
        seq.append(f"5_example={gen}")
        settle(page, 2)
        if "Traceback" in (_main_text(page) or ""):
            first_fail = first_fail or "traceback after generate/update example"
        backing = False
        if not mission_backing_open(_main_text(page)):
            backing = bool(open_mission_backing(page, notes) or click_button_has(page, r"Practice in Backing Jam"))
            settle(page, 3)
        else:
            backing = bool(click_button_has(page, r"Advanced playback") or click_button_has(page, r"Play Backing"))
        seq.append(f"6_backing={backing}")
        settle(page, 2)
        if "Traceback" in (_main_text(page) or ""):
            first_fail = first_fail or "traceback after Backing control"
        other = (
            click_button_has(page, r"3/4")
            or click_button_has(page, r"Advanced")
            or click_button_has(page, r"Return to Mission")
        )
        seq.append(f"7_other={other}")
        settle(page, 2)
        if "Traceback" in (_main_text(page) or ""):
            first_fail = first_fail or "traceback after extra Mission/Backing control"
    except Exception as exc:
        seq.append(f"exc={exc!r}")
        traceback = True
        first_fail = first_fail or f"exception {exc!r}"
    after_body = _main_text(page)
    traceback = traceback or (
        "Traceback" in after_body
        or "StreamlitAPIException" in after_body
        or "DuplicateWidgetID" in after_body
    )
    still = main_interactive(page)
    widget_ok = True
    try:
        combo = page.get_by_role("combobox", name="Practice / Concert Key")
        if not combo.count():
            combo = page.locator('section[data-testid="stSidebar"] input[aria-label="Practice / Concert Key"]')
        widget_ok = bool(combo.count() and combo.first.is_enabled())
    except Exception:
        widget_ok = False
    first = first_fail
    if traceback:
        first = first or "traceback / Streamlit exception after H8 edits"
    elif not before:
        first = first or "page already uneditable at H9 start"
    elif not still or not widget_ok:
        first = first or "Practice Key or page controls frozen after edits"
    if first:
        bundle = h9_capture_fail_bundle(page, seq, traceback=traceback)
        notes.append(
            f"h9_fail_first={first} dup={bundle.get('duplicate_ids')} disabled={bundle.get('disabled')[:8]}"
        )
    mark(
        "H9",
        not first,
        f"before={before} still={still} widget_ok={widget_ok} seq={seq} notes={notes}",
        first_divergence=first,
    )


def wait_studio_safe(page: Page) -> dict:
    """Ready check without falling through to disabled sidebar Open buttons."""
    info: dict = {
        "sidebar": False,
        "songs_nav": False,
        "creative_nav": False,
        "picker": False,
        "ok": False,
    }
    try:
        page.wait_for_selector('section[data-testid="stSidebar"]', timeout=120_000)
        info["sidebar"] = True
    except Exception as exc:
        info["error"] = repr(exc)
        return info
    expand_sidebar(page)
    settle(page, 3)
    try:
        songs = page.locator('section[data-testid="stSidebar"] button').filter(
            has_text=re.compile(r"Song Selection", re.I)
        )
        creative = page.locator('section[data-testid="stSidebar"] button').filter(
            has_text=re.compile(r"Creative Lab", re.I)
        )
        info["songs_nav"] = bool(songs.count() and songs.first.is_visible())
        info["creative_nav"] = bool(creative.count() and creative.first.is_visible())
        if songs.count():
            songs.first.click(timeout=8000)
            settle(page, 4)
    except Exception as exc:
        info["songs_click_error"] = repr(exc)
    try:
        info["picker"] = page.locator('[data-testid="stMain"] [data-testid="stSelectbox"]').count() > 0
    except Exception:
        info["picker"] = False
    info["ok"] = bool(info["sidebar"] and (info["songs_nav"] or info["picker"]))
    return info


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 960})
        page.goto(URL, wait_until="domcontentloaded", timeout=180000)
        settle(page, 8)
        try:
            init = wait_studio_safe(page)
        except Exception as exc:
            log(f"init_exception={exc!r}")
            settle(page, 6)
            try:
                init = wait_studio_safe(page)
            except Exception as exc2:
                log(f"OVERALL=FAIL init_crash {exc2!r}")
                browser.close()
                return 1
        log(f"init={json.dumps(init)}")
        if not init.get("ok"):
            log("OVERALL=FAIL init")
            browser.close()
            return 1
        if want_gate("H1"):
            h1(page)
        if want_gate("H2"):
            h2(page)
        if want_gate("H3"):
            h3(page)
        if want_gate("H4"):
            h4(page)
        if want_gate("H5"):
            h5(page)
        if want_gate("H6"):
            h6(page)
        if want_gate("H7"):
            if GATES.get("H6") is False:
                mark("H7", False, "skipped until H6 is green", first_divergence="H6 not green")
            else:
                h7(page)
        if want_gate("H8"):
            if want_gate("H7") and GATES.get("H7") is False:
                mark("H8", False, "skipped until H7 is green", first_divergence="H7 not green")
            else:
                h8(page)
        if want_gate("H9"):
            if want_gate("H8") and GATES.get("H8") is False:
                mark("H9", False, "skipped until H8 is green", first_divergence="H8 not green")
            else:
                h9(page)
        browser.close()
    reds = [k for k, v in GATES.items() if not v]
    log(json.dumps({"gates": GATES, "traces": TRACES}, indent=2))
    log("OVERALL=" + ("PASS" if not reds else "RED") + f" PASS={sum(1 for v in GATES.values() if v)} RED={len(reds)}")
    (OUT / f"{PREFIX}summary.json").write_text(
        json.dumps({"gates": GATES, "traces": TRACES, "notes": NOTES[-60:]}, indent=2),
        encoding="utf-8",
    )
    return 0 if not reds else 1


if __name__ == "__main__":
    raise SystemExit(main())
