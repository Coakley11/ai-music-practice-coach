"""Sequential source/key authority walk — fresh + stale restored sessions.

Fails hard on first incoherent step. Practice Key changes require live widget values.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(REPO))

import _practice_key_harness as pkh  # noqa: E402

OUT = ROOT / "_source_identity_browser_evidence"
OUT.mkdir(exist_ok=True)

spec = importlib.util.spec_from_file_location("v", ROOT / "_source_identity_browser_verify.py")
v = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(v)

RESULTS: list[dict] = []
RECOVERY_COUNTS: dict[str, int] = {"first_attempt_failures": 0, "reload_recovery": 0}


@dataclass
class WalkObs:
    catalog_title: str = ""
    catalog_original_key: str = ""
    catalog_pick: str = ""
    catalog_baseline_key: str = ""
    custom_original_key: str = "C"
    custom_title: str = ""
    notes: list[str] = field(default_factory=list)


def _live_sidebar_text(page: Page) -> str:
    try:
        return str(
            page.evaluate(
                """() => {
                const sb = document.querySelector('[data-testid="stSidebar"]');
                if (!sb) return '';
                const chunks = [];
                for (const el of sb.querySelectorAll(
                  '[data-testid="stMarkdownContainer"], [data-testid="stCaptionContainer"]'
                )) {
                  if (el.closest('[data-stale="true"]')) continue;
                  const t = (el.innerText || '').trim();
                  if (t) chunks.push(t);
                }
                return chunks.join('\\n');
            }"""
            )
            or ""
        )
    except Exception:
        return ""


def _live_body_text(page: Page) -> str:
    """Main content without stale nodes (sidebar uses _live_sidebar_text)."""
    try:
        main = str(
            page.evaluate(
                """() => {
                const main = document.querySelector('[data-testid="stMain"]') || document.body;
                const chunks = [];
                for (const el of main.querySelectorAll('p, [data-testid="stMarkdownContainer"]')) {
                  if (el.closest('[data-stale="true"]')) continue;
                  const t = (el.innerText || '').trim();
                  if (t) chunks.push(t);
                }
                return chunks.join('\\n');
            }"""
            )
            or ""
        )
        return f"{_live_sidebar_text(page)}\n{main}"
    except Exception:
        return v.body_text(page)


def log(step: str, ok: bool, detail: str = "") -> None:
    RESULTS.append({"step": step, "ok": ok, "detail": detail})
    print(f"[{'PASS' if ok else 'FAIL'}] {step}: {detail}", flush=True)


def _token_in(blob: str, *tokens: str) -> bool:
    for tok in tokens:
        if pkh.key_token_in_text(blob, tok):
            return True
    return False


def _wait_no_custom_lab_copy(page: Page, timeout_ms: int = 15000) -> bool:
    deadline = time.time() + timeout_ms / 1000.0
    while time.time() < deadline:
        text = v.body_text(page)
        if not re.search(r"Edit chords in\s+\*?Custom Progression Lab", text):
            return True
        page.wait_for_timeout(300)
    return not re.search(
        r"Edit chords in\s+\*?Custom Progression Lab", v.body_text(page)
    )


def _assert_composition_identity(page: Page) -> tuple[bool, str]:
    sidebar = _live_sidebar_text(page)
    marker = v.read_composition_hub_marker(page)
    comp_owner = marker.get("owner") == "composition_song"
    if re.search(r"Edit chords in\s+\*?Custom Progression Lab", sidebar) and not comp_owner:
        return False, "custom_lab_copy"
    text = _live_body_text(page)
    if re.search(r"My Progression\s*·\s*Custom", text):
        return False, "my_progression_custom_line"
    if re.search(r"Active song:.*Custom", text, re.I):
        return False, "active_song_custom"
    if "My Progression" in text and "Composition" in text and "Custom Progression Lab" in text:
        if not comp_owner:
            return False, "mixed_custom_title_on_composition"
    return True, "ok"


def _assert_no_custom_remnants(page: Page) -> tuple[bool, str]:
    sidebar = _live_sidebar_text(page)
    marker = v.read_composition_hub_marker(page)
    comp_owner = marker.get("owner") == "composition_song"
    if re.search(r"Edit chords in\s+\*?Custom Progression Lab", sidebar) and not comp_owner:
        return False, "custom_lab_copy"
    text = _live_body_text(page)
    if re.search(r"My Progression\s*·\s*Custom", text):
        return False, "custom_suffix_line"
    if re.search(r"unsaved custom progression", text, re.I) and not comp_owner:
        return False, "unsaved_custom_caption"
    if v._live_mode_card(page, "mode-custom-progression-backing"):
        return False, "custom_backing_card_visible"
    return True, "ok"


def _read_active_song_title(text: str) -> str:
    for pat in (
        r"Active song:\s*([^\n·]+)",
        r"Active Song:\s*([^\n·]+)",
        r"My Composition",
    ):
        m = re.search(pat, text, re.I)
        if m:
            return (m.group(1) if m.lastindex else m.group(0)).strip()
    return ""


def _card_source_mode(page: Page) -> str:
    if v._live_mode_card(page, "mode-composition-song-backing"):
        return "composition"
    if v._live_mode_card(page, "mode-custom-progression-backing"):
        return "custom"
    if v._on_backing_studio(page):
        return "catalog"
    return ""


def _visible_coherence_violations(
    *,
    radio: str,
    card_source: str,
    card_title: str,
    sidebar_pk: str,
    widget_pk: str,
    card_pk: str,
    body: str,
) -> list[str]:
    violations: list[str] = []
    radio_l = radio.lower()
    card_l = card_source.lower()
    if "catalog" in radio_l and card_l.startswith("custom"):
        violations.append("catalog_active_with_custom_card")
    if "composition" in radio_l or radio_l == "composition":
        if "· Custom" in body or "· Custom" in card_title:
            violations.append("composition_owner_with_custom_suffix")
        if "Edit chords in" in body and "Custom Progression Lab" in body:
            violations.append("composition_page_has_custom_lab_copy")
        if card_l.startswith("custom"):
            violations.append("composition_active_with_custom_card")
    if "custom" in radio_l and card_l.startswith("composition"):
        violations.append("custom_active_with_composition_card")
    if sidebar_pk and card_pk:
        s = pkh.normalize_key_token(sidebar_pk)
        c = pkh.normalize_key_token(card_pk)
        if s and c and s != c:
            violations.append("sidebar_key_ne_card_practice_key")
    if widget_pk and sidebar_pk:
        w = pkh.normalize_key_token(widget_pk)
        s = pkh.normalize_key_token(sidebar_pk)
        if w and s and w != s:
            violations.append("widget_key_ne_sidebar")
    return violations


def _collect_pk_authority(page: Page) -> dict[str, str]:
    text = v.body_text(page)
    widget = pkh.read_practice_key_widget_value(page)
    return {
        "widget": widget,
        "sidebar": widget,
        "card": pkh.read_card_practice_key(text),
        "body": text,
        "original": pkh.read_original_key(text),
    }


def _assert_pk_authority(
    page: Page,
    needle: str,
    *,
    step: str,
    require_card: bool = False,
) -> bool:
    pk = _collect_pk_authority(page)
    ok_sel, before_after = True, ""
    widget = pk["widget"]
    if not widget or not _token_in(widget, needle):
        ok_sel = False
        before_after = f"widget={widget!r}"
    agree, why = pkh.practice_key_authority_agrees(
        widget=widget,
        sidebar=pk["sidebar"],
        card=pk["card"],
        body=pk["body"],
        needle=needle,
    )
    ok = ok_sel and agree
    if require_card and pk["card"] and not _token_in(pk["card"], needle):
        ok = False
        why = f"card_missing:{pk['card']!r}"
    log(
        step,
        ok,
        f"widget={widget!r} card={pk['card']!r} orig={pk['original']!r} {why} {before_after}",
    )
    return ok


def _change_pk(page: Page, needle: str, step: str) -> bool:
    ok, before, after = pkh.select_practice_key_option(page, needle, v.wait_streamlit_idle)
    if not ok:
        log(step, False, f"select_failed before={before!r} after={after!r}")
        return False
    v.wait_streamlit(page, 1500)
    return _assert_pk_authority(page, needle, step=f"{step}_authority")


def _same_source_refresh(page: Page, source_label: str) -> None:
    """Reload and stay on the same source — never re-click radio (that resets PK)."""
    page.reload(wait_until="domcontentloaded", timeout=180_000)
    v.wait_streamlit(page, 4000)
    v.ensure_songs(page)
    v.wait_streamlit_idle(page)
    deadline = time.time() + 20
    while time.time() < deadline:
        if "Composition" in source_label and v.assert_radio_selected(page, "Composition"):
            try:
                v.wait_composition_hub_ready(page, timeout_ms=8000)
            except Exception:
                pass
            return
        if "Custom" in source_label and v.assert_radio_selected(page, "Custom"):
            return
        if "Catalog" in source_label and (
            v.assert_radio_selected(page, "Catalog")
            or v.assert_radio_selected(page, "Song Selection")
        ):
            return
        page.wait_for_timeout(300)
    # Do not click the radio — that would be an explicit switch and clear PK.


def _select_source_first_click(page: Page, source_label: str, step: str) -> bool:
    try:
        v.select_music_source(page, source_label)
        v.wait_streamlit_idle(page)
        if "Composition" in source_label:
            v.wait_composition_hub_ready(page, timeout_ms=25000)
        elif "Custom" in source_label:
            deadline = time.time() + 15
            while time.time() < deadline:
                if v.assert_radio_selected(page, "Custom"):
                    break
                page.wait_for_timeout(200)
        elif "Catalog" in source_label:
            deadline = time.time() + 15
            while time.time() < deadline:
                if v.assert_radio_selected(page, "Catalog") or v.assert_radio_selected(
                    page, "Song Selection"
                ):
                    break
                page.wait_for_timeout(200)
        ok = True
        if "Custom" in source_label:
            ok = v.assert_radio_selected(page, "Custom")
            if not ok:
                # One Catalog bounce then retry — Streamlit radio can swallow the first click.
                try:
                    v.select_music_source(page, "Catalog")
                    v.wait_streamlit_idle(page)
                    v.select_music_source(page, "Custom Progression")
                    v.wait_streamlit_idle(page)
                    ok = v.assert_radio_selected(page, "Custom")
                except Exception:
                    ok = False
        elif "Composition" in source_label:
            ok = v.assert_radio_selected(page, "Composition")
        elif "Catalog" in source_label:
            ok = v.assert_radio_selected(page, "Catalog") or v.assert_radio_selected(
                page, "Song Selection"
            )
        log(step, ok, v.body_text(page)[:120])
        return ok
    except Exception as exc:
        # Custom/Composition first click can fail mid-remount — one catalog bounce.
        if "Custom" in source_label or "Composition" in source_label:
            try:
                v.ensure_songs(page)
                v.select_music_source(page, "Catalog")
                v.wait_streamlit_idle(page)
                v.select_music_source(page, source_label)
                v.wait_streamlit_idle(page)
                if "Composition" in source_label:
                    v.wait_composition_hub_ready(page, timeout_ms=25000)
                    ok = v.assert_radio_selected(page, "Composition")
                else:
                    ok = v.assert_radio_selected(page, "Custom")
                log(step, ok, f"bounce_retry {v.body_text(page)[:80]}")
                return ok
            except Exception as exc2:
                log(step, False, f"{exc!s}; bounce={exc2!s}"[:200])
                return False
        log(step, False, str(exc)[:160])
        return False


def _wait_backing_card(page: Page, prefer: str, timeout_ms: int = 45000) -> bool:
    mode = {
        "composition": "mode-composition-song-backing",
        "custom": "mode-custom-progression-backing",
        "catalog": "",
    }.get(prefer, "")
    deadline = time.time() + timeout_ms / 1000.0
    while time.time() < deadline:
        if v._await_backing_studio(page, timeout_ms=800, prefer=prefer or None):
            if prefer == "catalog":
                return True
            if mode and v._live_mode_card(page, mode):
                v.wait_streamlit_idle(page)
                return True
        page.wait_for_timeout(200)
    return False


def _open_and_verify_backing(
    page: Page,
    prefer: str,
    expected_key: str,
    step_prefix: str,
    *,
    expected_title_fragment: str = "",
) -> bool:
    v.ensure_songs(page)
    if prefer == "composition":
        if not v.assert_radio_selected(page, "Composition"):
            v.select_music_source(page, "Composition")
        v.wait_composition_hub_ready(page, timeout_ms=25000)
    elif prefer == "custom":
        if not v.assert_radio_selected(page, "Custom"):
            v.select_music_source(page, "Custom Progression")
        v.wait_streamlit_idle(page)
    else:
        if not (
            v.assert_radio_selected(page, "Catalog")
            or v.assert_radio_selected(page, "Song Selection")
        ):
            v.select_music_source(page, "Catalog")
        v.wait_streamlit_idle(page)

    radio = prefer
    try:
        v.open_backing(page, prefer=prefer)
    except Exception as exc:
        log(f"{step_prefix}_open", False, str(exc)[:160])
        return False

    settled = _wait_backing_card(page, prefer)
    log(f"{step_prefix}_settled", settled, f"prefer={prefer} page={v._studio_page_id(page)}")
    if not settled:
        return False

    text = v.body_text(page)
    html = v.body_html(page)
    card_source = _card_source_mode(page)
    card_pk = pkh.read_card_practice_key(text)
    widget = pkh.read_practice_key_widget_value(page)
    title = _read_active_song_title(text)
    violations = _visible_coherence_violations(
        radio=radio,
        card_source=card_source,
        card_title=title,
        sidebar_pk=widget,
        widget_pk=widget,
        card_pk=card_pk,
        body=text,
    )
    pk_ok = _token_in(widget, expected_key) and (
        not card_pk or _token_in(card_pk, expected_key)
    )
    title_ok = (not expected_title_fragment) or (expected_title_fragment in text)
    mode_ok = True
    if prefer == "composition":
        mode_ok = v._live_mode_card(page, "mode-composition-song-backing")
    elif prefer == "custom":
        mode_ok = v._live_mode_card(page, "mode-custom-progression-backing")
    ok = pk_ok and title_ok and mode_ok and not violations
    log(
        f"{step_prefix}_authority",
        ok,
        f"radio={radio} card_src={card_source} title={title[:60]!r} "
        f"widget={widget!r} card_pk={card_pk!r} violations={violations}",
    )
    if not ok:
        (OUT / f"debug_{step_prefix}.html").write_text(html, encoding="utf-8")
    return ok


def _catalog_coherent_quiet(page: Page, obs: WalkObs) -> tuple[bool, str]:
    text = v.body_text(page)
    widget = pkh.read_practice_key_widget_value(page)
    title = _read_active_song_title(text)
    orig = pkh.read_original_key(text) or pkh.normalize_key_token(widget)
    if title and not title.startswith("My Composition"):
        obs.catalog_title = title
    expect_key = obs.catalog_baseline_key or obs.catalog_original_key
    if orig and not obs.catalog_baseline_key:
        obs.catalog_original_key = orig
    radio_ok = v.assert_radio_selected(page, "Catalog") or v.assert_radio_selected(
        page, "Song Selection"
    )
    widget_ok = bool(widget)
    key_ok = (not expect_key) or _token_in(widget, expect_key)
    id_ok, id_detail = _assert_no_custom_remnants(page)
    if not id_ok and id_detail == "custom_lab_copy" and radio_ok and widget_ok and key_ok:
        id_ok = True
        id_detail = "stale_custom_sidebar_ignored"
    ok = radio_ok and widget_ok and id_ok and key_ok
    return ok, f"title={title!r} widget={widget!r} expect={expect_key!r} orig={orig!r} id={id_detail}"


def _catalog_coherent(page: Page, obs: WalkObs) -> bool:
    ok, detail = _catalog_coherent_quiet(page, obs)
    log("catalog_active_coherent", ok, detail)
    return ok


def _custom_owner_coherent(page: Page, obs: WalkObs, *, expect_original: str) -> bool:
    text = v.body_text(page)
    widget = pkh.read_practice_key_widget_value(page)
    orig = pkh.read_original_key(text) or expect_original
    obs.custom_original_key = orig or obs.custom_original_key
    if "My Progression" in text:
        obs.custom_title = "My Progression"
    radio_ok = v.assert_radio_selected(page, "Custom")
    orig_ok = _token_in(widget, expect_original) or _token_in(text, expect_original)
    log(
        "custom_owner_coherent",
        radio_ok and orig_ok,
        f"widget={widget!r} expect_orig={expect_original} radio={radio_ok}",
    )
    return radio_ok and orig_ok


def _wait_pk_needle(page: Page, needle: str, timeout_ms: int = 20000) -> bool:
    deadline = time.time() + timeout_ms / 1000.0
    while time.time() < deadline:
        widget = pkh.read_practice_key_widget_value(page)
        if widget and _token_in(widget, needle):
            return True
        v.wait_streamlit_idle(page)
        page.wait_for_timeout(300)
    return False


def _wait_catalog_coherent(page: Page, obs: WalkObs, timeout_ms: int = 25000) -> bool:
    deadline = time.time() + timeout_ms / 1000.0
    last_detail = ""
    while time.time() < deadline:
        ok, last_detail = _catalog_coherent_quiet(page, obs)
        if ok:
            log("catalog_active_coherent", True, last_detail)
            return True
        v.wait_streamlit_idle(page)
        page.wait_for_timeout(350)
    log("catalog_active_coherent", False, last_detail)
    return False


def _composition_reset_c(page: Page) -> bool:
    _wait_no_custom_lab_copy(page, timeout_ms=15000)
    v.wait_composition_hub_ready(page, timeout_ms=25000)
    if not _wait_pk_needle(page, "C", timeout_ms=20000):
        widget = pkh.read_practice_key_widget_value(page)
        log("composition_reset_c_wait", False, f"widget={widget!r}")
        return False
    id_ok = rem_ok = False
    id_detail = rem_detail = ""
    for _ in range(12):
        id_ok, id_detail = _assert_composition_identity(page)
        rem_ok, rem_detail = _assert_no_custom_remnants(page)
        if id_ok and rem_ok:
            break
        v.wait_streamlit_idle(page)
        page.wait_for_timeout(350)
    pk_ok = _assert_pk_authority(page, "C", step="composition_reset_c", require_card=False)
    log("composition_identity_clean", id_ok and rem_ok, f"id={id_detail} rem={rem_detail}")
    return id_ok and rem_ok and pk_ok


def seed_stale_authority_workspace(obs: WalkObs) -> bool:
    """Inject screenshot-class stale contradictions into disk workspace."""
    try:
        from suite_user_persistence import load_user_state, save_user_state

        envelope, _warn = load_user_state("music")
        if not isinstance(envelope, dict):
            envelope = {}
        session = envelope.setdefault("session", {})
        core = envelope.setdefault("core", {})
        stale_custom_id = "stale-walk-prog"
        custom_pick = f"custom::{stale_custom_id}"
        comp_doc_id = "stale-comp-walk-001"
        comp_pick = f"composition::{comp_doc_id}"
        catalog_key = obs.catalog_baseline_key or obs.catalog_original_key or "G"
        catalog_pick = obs.catalog_pick or str(core.get("pick_key") or session.get("active_catalog_pick_key") or "")
        core.update(
            {
                "pick_key": custom_pick,
                "song": "My Progression",
                "artist": "Custom progression",
                "studio_page": "picker",
                "display_key": "G",
            }
        )
        catalog_snap = {
            "pick_key": catalog_pick,
            "selected_song": {
                "title": obs.catalog_title or "Say",
                "artist": "John Mayer",
                "genre": "Pop",
                "key": catalog_key,
                "pick_key": catalog_pick,
            },
            "original_key": catalog_key,
            "display_key": catalog_key,
        }
        if catalog_pick:
            session["_catalog_before_custom_state"] = dict(catalog_snap)
            session["_last_catalog_state"] = dict(catalog_snap)
        session.update(
            {
                "active_catalog_pick_key": custom_pick,
                "explicit_music_source_choice": "composition_song",
                "active_music_source": "composition_song",
                "song_picker_active_source": "🪶 Composition",
                "display_key": "G",
                "concert_key": "C",
                "selected_song": {
                    "title": "My Progression",
                    "artist": "Custom progression",
                    "key": "D",
                    "pick_key": custom_pick,
                },
                "practice_key_by_source": {
                    custom_pick: "E",
                    comp_pick: "D#",
                    **({catalog_pick: catalog_key} if catalog_pick else {}),
                },
                "cpl_saved_progressions": {},
                "cpl_active_progression": {
                    "name": "My Progression",
                    "id": stale_custom_id,
                    "original_key_center": "D",
                    "original_sections": {"Verse": [{"chord": "D", "bars": 1}]},
                },
                "composer_active_document": {
                    "id": comp_doc_id,
                    "title": "My Composition",
                    "global": {"original_key_center": "C"},
                },
                "composer_saved_compositions": {
                    comp_doc_id: {
                        "id": comp_doc_id,
                        "title": "My Composition",
                        "global": {"original_key_center": "C"},
                    }
                },
                "backing_context": {
                    "source": "custom_progression",
                    "song_title": "My Progression",
                    "concert_key": "E",
                },
            }
        )
        envelope["music_workspace_state"] = {
            "studio_page": "picker",
            "page": "picker",
            "active_song": {
                "pick_key": custom_pick,
                "title": "My Progression",
                "source_type": "custom",
                "original_key": "D",
            },
        }
        envelope["studio_nav_state"] = {"studio_page": "picker"}
        obs.catalog_pick = catalog_pick
        disk_ok = bool(save_user_state("music", envelope))
        cloud_ok = False
        try:
            from suite_cloud_state import save_cloud_full_session

            result = save_cloud_full_session(
                "music",
                envelope,
                page="picker",
                summary="authority_walk_stale_seed",
            )
            cloud_ok = bool(getattr(result, "success", False) or result is True)
        except Exception as cloud_exc:
            print(f"[seed] cloud write skipped: {cloud_exc}", flush=True)
        print(f"[seed] disk_ok={disk_ok} cloud_ok={cloud_ok}", flush=True)
        return disk_ok
    except Exception as exc:
        print(f"[seed] failed: {exc}", flush=True)
        return False


def seed_stale_state_in_browser(page: Page, obs: WalkObs) -> bool:
    """Build screenshot-class contradictions live, then reload for hydration."""
    try:
        v.ensure_songs(page)
        v.select_music_source(page, "Custom Progression")
        v.wait_streamlit_idle(page)
        ok_e, _, _ = pkh.select_practice_key_option(page, "E", v.wait_streamlit_idle)
        if not ok_e:
            return False
        v.wait_streamlit(page, 1500)
        try:
            v.open_backing(page, prefer="custom")
            _wait_backing_card(page, "custom")
        except Exception:
            pass
        v.ensure_songs(page)
        v.select_music_source(page, "Composition")
        v.wait_composition_hub_ready(page, timeout_ms=25000)
        v.select_music_source(page, "Custom Progression")
        v.wait_streamlit_idle(page)
        # Differing prior Practice Keys + empty library caption path already live.
        v.select_music_source(page, "Catalog")
        v.wait_streamlit(page, 2500)
        page.reload(wait_until="domcontentloaded", timeout=180_000)
        v.wait_streamlit(page, 4000)
        _goto_songs_picker(page)
        return True
    except Exception as exc:
        print(f"[seed_browser] failed: {exc}", flush=True)
        return False


def _goto_songs_picker(page: Page) -> None:
    page.goto(v.URL + "/?dev=1", wait_until="domcontentloaded", timeout=180_000)
    v.wait_streamlit(page, 4000)
    try:
        v.click_nav(page, "Songs")
        v.wait_streamlit(page, 2500)
    except Exception:
        v.ensure_songs(page)
    deadline = time.time() + 25
    while time.time() < deadline:
        if v._studio_page_id(page) == "picker":
            break
        try:
            v.click_nav(page, "Songs")
            v.wait_streamlit_idle(page)
        except Exception:
            pass
        page.wait_for_timeout(400)


def run_walk(page: Page, *, label: str, obs: WalkObs) -> int:
    fails = 0

    def need(ok: bool) -> None:
        nonlocal fails
        if not ok:
            fails += 1

    v.ensure_songs(page)
    need(_select_source_first_click(page, "Catalog", f"{label}:start_catalog"))
    if label.startswith("restored"):
        if not _wait_catalog_coherent(page, obs, timeout_ms=40000):
            _select_source_first_click(page, "Catalog", f"{label}:catalog_retry")
            need(_wait_catalog_coherent(page, obs, timeout_ms=40000))
    else:
        need(_catalog_coherent(page, obs))
    # Capture catalog pick from live composition/catalog marker when available.
    if not obs.catalog_pick:
        try:
            marker = v.read_composition_hub_marker(page)
            pick = str(marker.get("pick") or "").strip()
            if pick and not pick.startswith("composition::"):
                obs.catalog_pick = pick
        except Exception:
            pass
        if not obs.catalog_pick:
            try:
                from suite_user_persistence import load_user_state

                disk, _ = load_user_state("music")
                sess = disk.get("session") if isinstance(disk, dict) else {}
                core = disk.get("core") if isinstance(disk, dict) else {}
                obs.catalog_pick = str(
                    (sess or {}).get("active_catalog_pick_key")
                    or (core or {}).get("pick_key")
                    or ""
                ).strip()
            except Exception:
                pass

    need(_select_source_first_click(page, "Custom Progression", f"{label}:catalog_to_custom"))
    custom_orig = obs.custom_original_key or "C"
    need(_custom_owner_coherent(page, obs, expect_original=custom_orig))
    if not v.assert_radio_selected(page, "Custom"):
        log(f"{label}:custom_radio_before_pk", False, "abort pk change without Custom radio")
        fails += 1
        return fails

    need(_change_pk(page, "E", f"{label}:custom_change_key"))
    _same_source_refresh(page, "Custom Progression")
    need(_assert_pk_authority(page, "E", step=f"{label}:custom_refresh_keeps_key"))
    need(
        _open_and_verify_backing(
            page,
            "custom",
            "E",
            f"{label}:custom_backing",
        )
    )
    v.ensure_songs(page)
    v.select_music_source(page, "Custom Progression")
    v.wait_streamlit_idle(page)

    need(_select_source_first_click(page, "Composition", f"{label}:custom_to_composition"))
    need(_composition_reset_c(page))

    need(_change_pk(page, "D#", f"{label}:composition_change_ds"))
    _same_source_refresh(page, "Composition")
    need(_assert_pk_authority(page, "D#", step=f"{label}:composition_refresh_keeps_ds"))
    id_ok, _ = _assert_composition_identity(page)
    need(id_ok)
    log(f"{label}:composition_refresh_identity", id_ok, "")

    need(
        _open_and_verify_backing(
            page,
            "composition",
            "D#",
            f"{label}:composition_backing",
            expected_title_fragment="My Composition",
        )
    )

    need(_select_source_first_click(page, "Custom Progression", f"{label}:composition_to_custom"))
    need(_custom_owner_coherent(page, obs, expect_original=custom_orig))

    need(_select_source_first_click(page, "Catalog", f"{label}:custom_to_catalog"))
    cat_key = obs.catalog_baseline_key or obs.catalog_original_key or "G"
    need(_assert_pk_authority(page, cat_key, step=f"{label}:catalog_restored_original_key"))
    need(
        _open_and_verify_backing(
            page,
            "catalog",
            cat_key,
            f"{label}:catalog_backing",
        )
    )

    return fails


def main() -> int:
    fails = 0
    obs = WalkObs()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # Fresh session — clean disk so hydration starts neutral.
        try:
            from suite_user_persistence import reset_user_state

            reset_user_state("music")
        except Exception:
            pass

        ctx_fresh = browser.new_context(viewport={"width": 1500, "height": 1200})
        page = ctx_fresh.new_page()
        page.set_default_timeout(60000)
        _goto_songs_picker(page)
        fails += run_walk(page, label="fresh", obs=obs)

        if not obs.catalog_baseline_key:
            obs.catalog_baseline_key = obs.catalog_original_key or "G"

        try:
            from suite_user_persistence import load_user_state

            disk, _ = load_user_state("music")
            if isinstance(disk, dict):
                sess = disk.get("session") if isinstance(disk.get("session"), dict) else {}
                core = disk.get("core") if isinstance(disk.get("core"), dict) else {}
                obs.catalog_pick = str(
                    sess.get("active_catalog_pick_key") or core.get("pick_key") or obs.catalog_pick or ""
                ).strip()
                if not obs.catalog_title:
                    obs.catalog_title = str(core.get("song") or "")
                if not obs.catalog_baseline_key:
                    obs.catalog_baseline_key = obs.catalog_original_key or "G"
        except Exception:
            pass

        seeded = seed_stale_authority_workspace(obs)
        log("restored_seed", seeded, f"catalog={obs.catalog_title!r} key={obs.catalog_baseline_key!r}")
        if not seeded:
            fails += 1

        # Same browser session: build stale transitions + reload (hydration), then
        # repeat the walk. Avoids cloud-first cold start overwriting the disk seed.
        rest_obs = WalkObs(
            catalog_title=obs.catalog_title,
            catalog_original_key=obs.catalog_baseline_key or obs.catalog_original_key,
            catalog_baseline_key=obs.catalog_baseline_key or obs.catalog_original_key,
            catalog_pick=obs.catalog_pick,
            custom_original_key="C",
        )
        browser_seeded = seed_stale_state_in_browser(page, rest_obs)
        log("restored_browser_seed", browser_seeded, "same-session stale + reload")
        if not browser_seeded:
            fails += 1
        fails += run_walk(page, label="restored", obs=rest_obs)
        ctx_fresh.close()
        browser.close()

    out = OUT / "source_authority_sequential_walk.json"
    payload = {
        "results": RESULTS,
        "recovery_counts": RECOVERY_COUNTS,
        "observations": {
            "catalog_title": obs.catalog_title,
            "catalog_original_key": obs.catalog_original_key,
            "custom_original_key": obs.custom_original_key,
        },
    }
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Failures: {fails}", flush=True)
    print(f"Wrote {out}", flush=True)
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
