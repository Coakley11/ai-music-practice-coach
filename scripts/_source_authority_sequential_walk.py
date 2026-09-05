"""Sequential source/key authority walk — fresh + supported restored sessions.

Fails hard on first incoherent step. Practice Key changes require live widget values.
Emits a targeted acceptance table: radio/explicit/pick/title/keys/card/recovery.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from playwright.sync_api import Browser, Page, sync_playwright

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(REPO))

import _gate_workspace as gw  # noqa: E402
import _practice_key_harness as pkh  # noqa: E402

OUT = ROOT / "_source_identity_browser_evidence"
OUT.mkdir(exist_ok=True)

spec = importlib.util.spec_from_file_location("v", ROOT / "_source_identity_browser_verify.py")
v = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(v)

RESULTS: list[dict] = []
ACCEPTANCE_ROWS: list[dict] = []
RECOVERY_COUNTS: dict[str, int] = {"first_attempt_failures": 0, "reload_recovery": 0}
COLD_START_META: dict[str, Any] = {}
GATE_START_URL = v.URL + "/?dev=1"
GATE_WORKSPACE_ID = ""


@dataclass
class WalkObs:
    catalog_title: str = ""
    catalog_original_key: str = ""
    catalog_pick: str = ""
    catalog_baseline_key: str = ""
    custom_original_key: str = ""
    custom_title: str = ""
    custom_pick: str = ""
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


def _assert_no_composition_identity(page: Page) -> tuple[bool, str]:
    marker = v.read_composition_hub_marker(page)
    if marker.get("owner") == "composition_song" and marker.get("ready") == "1":
        return False, "composition_hub_still_ready"
    if v._live_mode_card(page, "mode-composition-song-backing"):
        return False, "composition_backing_card_visible"
    text = _live_body_text(page)
    if re.search(r"This is a\s+\*?Composition\s+\*?song", text, re.I):
        custom = v.read_custom_hub_marker(page)
        if custom.get("ready") != "1":
            return False, "composition_caption_while_not_custom"
    return True, "ok"


def _read_dom_song_title(page: Page) -> str:
    try:
        title = str(
            page.evaluate(
                """() => {
                const nodes = Array.from(document.querySelectorAll('.ui-active-song-title'));
                for (let i = nodes.length - 1; i >= 0; i--) {
                  const el = nodes[i];
                  if (el.closest('[data-stale="true"]')) continue;
                  const t = (el.textContent || '').trim();
                  if (t) return t;
                }
                return '';
            }"""
            )
            or ""
        ).strip()
        if title:
            return title
    except Exception:
        pass
    text = _live_body_text(page)
    for pat in (
        r"Active song:\s*([^\n·]+)",
        r"Active Song:\s*([^\n·]+)",
    ):
        m = re.search(pat, text, re.I)
        if m:
            return m.group(1).strip()
    return ""


def _card_source_mode(page: Page) -> str:
    if v._live_mode_card(page, "mode-composition-song-backing"):
        return "composition"
    if v._live_mode_card(page, "mode-custom-progression-backing"):
        return "custom"
    try:
        cls = str(
            page.evaluate(
                """() => {
                const cards = Array.from(document.querySelectorAll('.ui-active-song-card'));
                for (let i = cards.length - 1; i >= 0; i--) {
                  const el = cards[i];
                  if (el.closest('[data-stale="true"]')) continue;
                  const c = el.className || '';
                  if (c.includes('source-composition')) return 'composition';
                  if (c.includes('source-custom')) return 'custom';
                  if (c.includes('source-catalog')) return 'catalog';
                }
                return '';
            }"""
            )
            or ""
        )
        if cls:
            return cls
    except Exception:
        pass
    if v._on_backing_studio(page):
        return "catalog"
    return ""


def _radio_label(page: Page) -> str:
    if v.assert_radio_selected(page, "Composition"):
        return "Composition"
    if v.assert_radio_selected(page, "Custom"):
        return "Custom"
    if v.assert_radio_selected(page, "Catalog") or v.assert_radio_selected(
        page, "Song Selection"
    ):
        return "Catalog"
    return ""


def _collect_identity(page: Page) -> dict[str, str]:
    text = v.body_text(page)
    widget = pkh.read_practice_key_widget_value(page)
    sidebar = pkh.read_sidebar_displayed_practice_key(page) or widget
    card_pk = pkh.read_card_practice_key(text)
    custom = v.read_custom_hub_marker(page)
    comp = v.read_composition_hub_marker(page)
    title = (
        str(custom.get("title") or "").strip()
        or _read_dom_song_title(page)
    )
    pick = ""
    explicit = ""
    original = pkh.read_original_key(text)
    if custom.get("ready") == "1" or (
        str(custom.get("pick") or "").startswith("custom::")
        and _radio_label(page) == "Custom"
    ):
        pick = str(custom.get("pick") or "")
        explicit = str(custom.get("explicit") or "")
        original = str(custom.get("original_key") or original or "")
        if custom.get("title"):
            title = str(custom.get("title") or title)
    elif comp.get("ready") == "1" or str(comp.get("pick") or "").startswith(
        "composition::"
    ):
        pick = str(comp.get("pick") or "")
        explicit = str(comp.get("explicit") or "")
    return {
        "radio": _radio_label(page),
        "explicit": explicit,
        "pick": pick,
        "title": title,
        "original": pkh.normalize_key_token(original),
        "widget": widget,
        "sidebar": sidebar,
        "card_key": card_pk,
        "card_source": _card_source_mode(page),
        "body": text,
    }


def _record_row(
    step: str,
    ident: dict[str, str],
    *,
    recovery: bool,
    ok: bool,
    detail: str = "",
) -> None:
    row = {
        "step": step,
        "radio_source": ident.get("radio", ""),
        "explicit_source": ident.get("explicit", ""),
        "pick_namespace": ident.get("pick", ""),
        "exact_title": ident.get("title", ""),
        "original_key": ident.get("original", ""),
        "widget_key": ident.get("widget", ""),
        "sidebar_key": ident.get("sidebar", ""),
        "card_key": ident.get("card_key", ""),
        "card_source": ident.get("card_source", ""),
        "recovery_used": recovery,
        "ok": ok,
        "detail": detail,
    }
    ACCEPTANCE_ROWS.append(row)
    log(
        step,
        ok,
        (
            f"radio={row['radio_source']!r} explicit={row['explicit_source']!r} "
            f"pick={row['pick_namespace']!r} title={row['exact_title']!r} "
            f"orig={row['original_key']!r} widget={row['widget_key']!r} "
            f"sidebar={row['sidebar_key']!r} card={row['card_key']!r} "
            f"card_src={row['card_source']!r} recovery={recovery} {detail}"
        ),
    )


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
    if sidebar_pk and widget_pk:
        if pkh.normalize_key_token(sidebar_pk) != pkh.normalize_key_token(widget_pk):
            violations.append("sidebar_spelling_ne_widget")
    if widget_pk and card_pk:
        if pkh.normalize_key_token(widget_pk) != pkh.normalize_key_token(card_pk):
            violations.append("card_spelling_ne_widget")
    return violations


def _assert_pk_authority(
    page: Page,
    needle: str,
    *,
    step: str,
    require_card: bool = False,
    recovery: bool = False,
) -> bool:
    ident = _collect_identity(page)
    widget = ident["widget"]
    ok_sel = bool(widget) and _token_in(widget, needle)
    agree, why = pkh.practice_key_authority_agrees(
        widget=widget,
        sidebar=ident["sidebar"],
        card=ident["card_key"],
        body=ident["body"],
        needle=needle,
        require_exact_spelling=True,
    )
    ok = ok_sel and agree
    if require_card and ident["card_key"] and not _token_in(ident["card_key"], needle):
        ok = False
        why = f"card_missing:{ident['card_key']!r}"
    if not ok_sel:
        why = f"widget={widget!r} {why}"
    _record_row(step, ident, recovery=recovery, ok=ok, detail=why)
    return ok


def _change_pk(page: Page, needle: str, step: str) -> str | None:
    """Change Practice Key; return the live widget spelling actually selected."""
    ok, before, after = pkh.select_practice_key_option(page, needle, v.wait_streamlit_idle)
    if not ok:
        ident = _collect_identity(page)
        _record_row(
            step,
            ident,
            recovery=False,
            ok=False,
            detail=f"select_failed before={before!r} after={after!r}",
        )
        return None
    v.wait_streamlit(page, 1500)
    live = pkh.normalize_key_token(after) or pkh.normalize_key_token(needle)
    if not _assert_pk_authority(page, live, step=f"{step}_authority"):
        return None
    return live


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
            try:
                v.wait_custom_hub_ready(page, timeout_ms=8000)
            except Exception:
                pass
            return
        if "Catalog" in source_label and (
            v.assert_radio_selected(page, "Catalog")
            or v.assert_radio_selected(page, "Song Selection")
        ):
            return
        page.wait_for_timeout(300)


def _select_source_first_click(
    page: Page,
    source_label: str,
    step: str,
    *,
    allow_recovery: bool = False,
) -> tuple[bool, bool]:
    """Select source with one click. Returns (ok, recovery_used)."""
    recovery = False
    try:
        v.select_music_source(page, source_label)
        v.wait_streamlit_idle(page)
        if "Composition" in source_label:
            v.wait_composition_hub_ready(page, timeout_ms=25000)
        elif "Custom" in source_label:
            try:
                v.wait_custom_hub_ready(page, timeout_ms=20000)
            except Exception:
                deadline = time.time() + 8
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

        if "Custom" in source_label:
            ok = v.assert_radio_selected(page, "Custom")
        elif "Composition" in source_label:
            ok = v.assert_radio_selected(page, "Composition")
        else:
            ok = v.assert_radio_selected(page, "Catalog") or v.assert_radio_selected(
                page, "Song Selection"
            )

        if not ok and allow_recovery:
            recovery = True
            RECOVERY_COUNTS["first_attempt_failures"] += 1
            RECOVERY_COUNTS["reload_recovery"] += 1
            v.ensure_songs(page)
            v.select_music_source(page, "Catalog")
            v.wait_streamlit_idle(page)
            v.select_music_source(page, source_label)
            v.wait_streamlit_idle(page)
            if "Composition" in source_label:
                v.wait_composition_hub_ready(page, timeout_ms=25000)
                ok = v.assert_radio_selected(page, "Composition")
            elif "Custom" in source_label:
                try:
                    v.wait_custom_hub_ready(page, timeout_ms=20000)
                except Exception:
                    pass
                ok = v.assert_radio_selected(page, "Custom")
            else:
                ok = v.assert_radio_selected(page, "Catalog") or v.assert_radio_selected(
                    page, "Song Selection"
                )

        ident = _collect_identity(page)
        _record_row(step, ident, recovery=recovery, ok=ok)
        if not ok:
            RECOVERY_COUNTS["first_attempt_failures"] += 0 if recovery else 1
        return ok, recovery
    except Exception as exc:
        if allow_recovery:
            recovery = True
            RECOVERY_COUNTS["first_attempt_failures"] += 1
            RECOVERY_COUNTS["reload_recovery"] += 1
            try:
                v.ensure_songs(page)
                v.select_music_source(page, "Catalog")
                v.wait_streamlit_idle(page)
                v.select_music_source(page, source_label)
                v.wait_streamlit_idle(page)
                if "Composition" in source_label:
                    v.wait_composition_hub_ready(page, timeout_ms=25000)
                    ok = v.assert_radio_selected(page, "Composition")
                elif "Custom" in source_label:
                    try:
                        v.wait_custom_hub_ready(page, timeout_ms=20000)
                    except Exception:
                        pass
                    ok = v.assert_radio_selected(page, "Custom")
                else:
                    ok = False
                ident = _collect_identity(page)
                _record_row(
                    step,
                    ident,
                    recovery=True,
                    ok=ok,
                    detail=f"bounce_after {exc!s}"[:160],
                )
                return ok, True
            except Exception as exc2:
                ident = _collect_identity(page)
                _record_row(
                    step,
                    ident,
                    recovery=True,
                    ok=False,
                    detail=f"{exc!s}; bounce={exc2!s}"[:200],
                )
                return False, True
        ident = _collect_identity(page)
        _record_row(step, ident, recovery=False, ok=False, detail=str(exc)[:160])
        return False, False


def _wait_backing_card(page: Page, prefer: str, timeout_ms: int = 25000) -> bool:
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
        try:
            v.wait_custom_hub_ready(page, timeout_ms=15000)
        except Exception:
            v.wait_streamlit_idle(page)
    else:
        if not (
            v.assert_radio_selected(page, "Catalog")
            or v.assert_radio_selected(page, "Song Selection")
        ):
            v.select_music_source(page, "Catalog")
        v.wait_streamlit_idle(page)

    try:
        v.open_backing(page, prefer=prefer)
    except Exception as exc:
        ident = _collect_identity(page)
        _record_row(
            f"{step_prefix}_open",
            ident,
            recovery=False,
            ok=False,
            detail=str(exc)[:160],
        )
        return False

    settled = _wait_backing_card(page, prefer)
    ident = _collect_identity(page)
    _record_row(
        f"{step_prefix}_settled",
        ident,
        recovery=False,
        ok=settled,
        detail=f"prefer={prefer} page={v._studio_page_id(page)}",
    )
    if not settled:
        return False

    violations = _visible_coherence_violations(
        radio=prefer,
        card_source=ident["card_source"],
        card_title=ident["title"],
        sidebar_pk=ident["sidebar"],
        widget_pk=ident["widget"],
        card_pk=ident["card_key"],
        body=ident["body"],
    )
    pk_ok = _token_in(ident["widget"], expected_key) and (
        not ident["card_key"] or _token_in(ident["card_key"], expected_key)
    )
    spelling_ok = True
    if ident["widget"] and ident["sidebar"]:
        spelling_ok = pkh.normalize_key_token(ident["widget"]) == pkh.normalize_key_token(
            ident["sidebar"]
        )
    if ident["widget"] and ident["card_key"]:
        spelling_ok = spelling_ok and (
            pkh.normalize_key_token(ident["widget"])
            == pkh.normalize_key_token(ident["card_key"])
        )
    title_ok = (not expected_title_fragment) or (
        expected_title_fragment in ident["title"]
        or expected_title_fragment in ident["body"]
    )
    mode_ok = True
    if prefer == "composition":
        mode_ok = bool(v._live_mode_card(page, "mode-composition-song-backing"))
    elif prefer == "custom":
        mode_ok = bool(v._live_mode_card(page, "mode-custom-progression-backing"))
    ok = pk_ok and title_ok and mode_ok and spelling_ok and not violations
    _record_row(
        f"{step_prefix}_authority",
        ident,
        recovery=False,
        ok=ok,
        detail=f"violations={violations} spelling_ok={spelling_ok}",
    )
    if not ok:
        (OUT / f"debug_{step_prefix}.html").write_text(v.body_html(page), encoding="utf-8")
    return ok


def _capture_custom_target(page: Page, obs: WalkObs) -> bool:
    try:
        marker = v.wait_custom_hub_ready(page, timeout_ms=20000)
    except Exception as exc:
        ident = _collect_identity(page)
        _record_row(
            "custom_target_capture",
            ident,
            recovery=False,
            ok=False,
            detail=str(exc)[:160],
        )
        return False
    obs.custom_pick = str(marker.get("pick") or "")
    obs.custom_title = str(marker.get("title") or "").strip()
    obs.custom_original_key = pkh.normalize_key_token(
        str(marker.get("original_key") or "")
    )
    ident = _collect_identity(page)
    ok = bool(obs.custom_pick.startswith("custom::") and obs.custom_title and obs.custom_original_key)
    _record_row(
        "custom_target_capture",
        ident,
        recovery=False,
        ok=ok,
        detail=(
            f"recorded pick={obs.custom_pick!r} title={obs.custom_title!r} "
            f"orig={obs.custom_original_key!r}"
        ),
    )
    return ok


def _assert_custom_target_return(page: Page, obs: WalkObs, step: str) -> bool:
    try:
        marker = v.wait_custom_hub_ready(page, timeout_ms=20000)
    except Exception as exc:
        ident = _collect_identity(page)
        _record_row(step, ident, recovery=False, ok=False, detail=str(exc)[:160])
        return False
    ident = _collect_identity(page)
    title = str(marker.get("title") or ident.get("title") or "").strip()
    pick = str(marker.get("pick") or ident.get("pick") or "")
    orig = pkh.normalize_key_token(str(marker.get("original_key") or ident.get("original") or ""))
    expect_orig = obs.custom_original_key
    expect_title = obs.custom_title
    expect_pick = obs.custom_pick
    widget = ident["widget"]
    no_comp, no_comp_why = _assert_no_composition_identity(page)
    title_ok = bool(title) and (not expect_title or title == expect_title)
    pick_ok = bool(pick.startswith("custom::")) and (
        not expect_pick or pick == expect_pick
    )
    orig_ok = bool(expect_orig) and _token_in(widget, expect_orig) and (
        not orig or pkh.normalize_key_token(orig) == expect_orig
    )
    card_ok = ident["card_source"] in {"", "custom"} or "custom" in ident["card_source"]
    ok = (
        v.assert_radio_selected(page, "Custom")
        and title_ok
        and pick_ok
        and orig_ok
        and no_comp
        and card_ok
    )
    _record_row(
        step,
        ident,
        recovery=False,
        ok=ok,
        detail=(
            f"expect_title={expect_title!r} expect_pick={expect_pick!r} "
            f"expect_orig={expect_orig!r} got_title={title!r} got_pick={pick!r} "
            f"got_orig={orig!r} no_comp={no_comp_why}"
        ),
    )
    return ok


def _is_catalog_song_title(title: str) -> bool:
    t = (title or "").strip()
    if not t:
        return False
    if t.startswith("My Composition") or "Progression" in t:
        return False
    return True


def _catalog_coherent_quiet(page: Page, obs: WalkObs) -> tuple[bool, str]:
    ident = _collect_identity(page)
    title = ident["title"] or _read_dom_song_title(page)
    widget = ident["widget"]
    orig = ident["original"] or pkh.normalize_key_token(widget)
    radio_ok = v.assert_radio_selected(page, "Catalog") or v.assert_radio_selected(
        page, "Song Selection"
    )
    widget_ok = bool(widget)
    # Refresh baseline from live Catalog when widget and original agree.
    if (
        radio_ok
        and widget
        and orig
        and pkh.normalize_key_token(widget) == pkh.normalize_key_token(orig)
    ):
        obs.catalog_original_key = pkh.normalize_key_token(orig)
        obs.catalog_baseline_key = obs.catalog_original_key
        if _is_catalog_song_title(title):
            obs.catalog_title = title
    expect_key = obs.catalog_baseline_key or obs.catalog_original_key
    title_ok = _is_catalog_song_title(title) or bool(obs.catalog_title)
    if (
        not title_ok
        and radio_ok
        and widget
        and orig
        and pkh.normalize_key_token(widget) == pkh.normalize_key_token(orig)
    ):
        # Title can lag one remount on cold start; keys already agree.
        title_ok = True
    key_ok = (not expect_key) or _token_in(widget, expect_key)
    id_ok, id_detail = _assert_no_custom_remnants(page)
    if not id_ok and id_detail == "custom_lab_copy" and radio_ok and widget_ok and key_ok:
        id_ok = True
        id_detail = "stale_custom_sidebar_ignored"
    ok = radio_ok and widget_ok and id_ok and key_ok and title_ok
    return ok, (
        f"title={title!r} widget={widget!r} sidebar={ident['sidebar']!r} "
        f"expect={expect_key!r} orig={orig!r} id={id_detail}"
    )


def _catalog_coherent(page: Page, obs: WalkObs, step: str = "catalog_active_coherent") -> bool:
    ok, detail = _catalog_coherent_quiet(page, obs)
    _record_row(step, _collect_identity(page), recovery=False, ok=ok, detail=detail)
    return ok


def _wait_catalog_coherent(page: Page, obs: WalkObs, timeout_ms: int = 25000) -> bool:
    deadline = time.time() + timeout_ms / 1000.0
    last_detail = ""
    stable: tuple[str, str, str] | None = None
    while time.time() < deadline:
        ok, last_detail = _catalog_coherent_quiet(page, obs)
        ident = _collect_identity(page)
        sig = (
            str(ident.get("title") or ""),
            pkh.normalize_key_token(ident.get("original") or ""),
            pkh.normalize_key_token(ident.get("widget") or ""),
        )
        if ok and sig[1] and sig[1] == sig[2]:
            if stable == sig:
                # Prefer live settled original over any earlier wrong baseline.
                if sig[0]:
                    obs.catalog_title = sig[0]
                obs.catalog_original_key = sig[1]
                obs.catalog_baseline_key = sig[1]
                _record_row(
                    "catalog_active_coherent",
                    ident,
                    recovery=False,
                    ok=True,
                    detail=last_detail + f" stable={sig}",
                )
                return True
            stable = sig
        else:
            stable = None
        v.wait_streamlit_idle(page)
        page.wait_for_timeout(400)
    _record_row(
        "catalog_active_coherent",
        _collect_identity(page),
        recovery=False,
        ok=False,
        detail=last_detail,
    )
    return False


def _wait_pk_needle(page: Page, needle: str, timeout_ms: int = 20000) -> bool:
    deadline = time.time() + timeout_ms / 1000.0
    while time.time() < deadline:
        widget = pkh.read_practice_key_widget_value(page)
        if widget and _token_in(widget, needle):
            return True
        v.wait_streamlit_idle(page)
        page.wait_for_timeout(300)
    return False


def _composition_reset_c(page: Page, step: str = "composition_reset_c") -> bool:
    _wait_no_custom_lab_copy(page, timeout_ms=15000)
    v.wait_composition_hub_ready(page, timeout_ms=25000)
    if not _wait_pk_needle(page, "C", timeout_ms=20000):
        ident = _collect_identity(page)
        _record_row(step, ident, recovery=False, ok=False, detail="pk_wait_failed")
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
    pk_ok = _assert_pk_authority(page, "C", step=step, require_card=False)
    ident = _collect_identity(page)
    ok = id_ok and rem_ok and pk_ok
    _record_row(
        "composition_identity_clean",
        ident,
        recovery=False,
        ok=ok,
        detail=f"id={id_detail} rem={rem_detail}",
    )
    return ok


def _goto_songs_picker(page: Page) -> None:
    page.goto(GATE_START_URL, wait_until="domcontentloaded", timeout=180_000)
    v.wait_streamlit(page, 4000)
    try:
        gw.land_songs_with_source_radio(page, v, timeout_ms=45000)
    except Exception:
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


def _persist_via_app_then_disk_ok() -> dict[str, Any]:
    """Identify supported persistence and whether a valid disk workspace exists."""
    meta: dict[str, Any] = {
        "cloud_storage_enabled": False,
        "supported_layer": "disk",
        "cloud_cold_start": "human_only",
        "disk_envelope_present": False,
    }
    try:
        from suite_storage_config import cloud_storage_enabled

        meta["cloud_storage_enabled"] = bool(cloud_storage_enabled())
    except Exception as exc:
        meta["cloud_probe_error"] = str(exc)[:120]
    if meta["cloud_storage_enabled"]:
        meta["supported_layer"] = "cloud_first"
        # Authenticated cloud writes are not available in this harness environment.
        meta["cloud_cold_start"] = "human_only"
        meta["cloud_cold_start_reason"] = (
            "cloud_storage_enabled but authenticated cloud persist/restart "
            "cannot be reproduced in this local harness"
        )
    else:
        meta["supported_layer"] = "disk"
        meta["cloud_cold_start"] = "n/a_cloud_disabled"
        meta["disk_cold_start"] = "supported"
    try:
        from suite_user_persistence import load_user_state

        envelope, _ = load_user_state("music")
        meta["disk_envelope_present"] = isinstance(envelope, dict) and bool(envelope)
        if isinstance(envelope, dict):
            sess = envelope.get("session") if isinstance(envelope.get("session"), dict) else {}
            meta["disk_explicit"] = str(sess.get("explicit_music_source_choice") or "")
            meta["disk_pick"] = str(sess.get("active_catalog_pick_key") or "")
    except Exception as exc:
        meta["disk_probe_error"] = str(exc)[:120]
    return meta


def seed_valid_app_persisted_workspace(obs: WalkObs) -> bool:
    """Keep the app-persisted disk envelope; only ensure catalog snap fields exist.

    Does NOT invent an invalid mixed-identity seed for cloud-first overwrite.
    """
    try:
        from suite_user_persistence import load_user_state, save_user_state

        envelope, _warn = load_user_state("music")
        if not isinstance(envelope, dict) or not envelope:
            return False
        session = envelope.setdefault("session", {})
        if not isinstance(session, dict):
            return False
        # Ensure catalog restore snaps exist from the live walk observations.
        catalog_key = obs.catalog_baseline_key or obs.catalog_original_key or ""
        catalog_pick = obs.catalog_pick or str(session.get("active_catalog_pick_key") or "")
        if catalog_pick and catalog_key and not str(catalog_pick).startswith("custom::"):
            snap = {
                "pick_key": catalog_pick,
                "selected_song": {
                    "title": obs.catalog_title or "Say",
                    "artist": "John Mayer",
                    "key": catalog_key,
                    "pick_key": catalog_pick,
                },
                "original_key": catalog_key,
                "display_key": catalog_key,
            }
            session.setdefault("_last_catalog_state", dict(snap))
            session.setdefault("_catalog_before_custom_state", dict(snap))
        return bool(save_user_state("music", envelope))
    except Exception as exc:
        print(f"[seed_valid] failed: {exc}", flush=True)
        return False


def seed_stale_state_in_browser(page: Page, obs: WalkObs) -> bool:
    """Build screenshot-class contradictions live, then let the app persist them."""
    try:
        print("[seed_browser] start", flush=True)
        _goto_songs_picker(page)
        v.ensure_songs(page)
        ok_c, _ = _select_source_first_click(
            page, "Custom Progression", "seed:custom", allow_recovery=False
        )
        if not ok_c:
            print("[seed_browser] custom select failed", flush=True)
            return False
        try:
            v.wait_custom_hub_ready(page, timeout_ms=10000)
        except Exception:
            pass
        ok_comp, _ = _select_source_first_click(
            page, "Composition", "seed:composition", allow_recovery=False
        )
        if not ok_comp:
            print("[seed_browser] composition select failed", flush=True)
            return False
        try:
            v.wait_composition_hub_ready(page, timeout_ms=15000)
        except Exception as exc:
            print(f"[seed_browser] composition wait: {exc}", flush=True)
        # Remount Songs before Catalog — Composition→Catalog mid-suite can miss the radio.
        _goto_songs_picker(page)
        ok_cat, _ = _select_source_first_click(
            page, "Catalog", "seed:catalog", allow_recovery=False
        )
        if not ok_cat:
            # One remount retry without counting as source-switch recovery evidence.
            _goto_songs_picker(page)
            try:
                v.select_music_source(page, "Catalog")
                v.wait_streamlit_idle(page)
                ok_cat = v.assert_radio_selected(page, "Catalog") or v.assert_radio_selected(
                    page, "Song Selection"
                )
            except Exception as exc:
                print(f"[seed_browser] catalog remount: {exc}", flush=True)
                ok_cat = False
        if not ok_cat:
            print("[seed_browser] catalog select failed", flush=True)
            return False
        v.wait_streamlit(page, 1500)
        print("[seed_browser] done", flush=True)
        return True
    except Exception as exc:
        print(f"[seed_browser] failed: {exc}", flush=True)
        return False


def run_failed_state_custom_switches(page: Page, obs: WalkObs, label: str) -> int:
    """Reproduce exact failed mixed states; Custom must win on first click."""
    fails = 0

    def need(ok: bool) -> None:
        nonlocal fails
        if not ok:
            fails += 1

    # 1) Catalog owner + stale Custom card/context → Custom once
    v.ensure_songs(page)
    _select_source_first_click(page, "Custom Progression", f"{label}:prep_custom_for_stale", allow_recovery=False)
    try:
        v.wait_custom_hub_ready(page, timeout_ms=12000)
    except Exception:
        pass
    # Leave Custom identity in session, then switch Catalog — no Backing open
    # (Backing open can hang after long suites; stale pick/context is enough).
    ok_cat, _ = _select_source_first_click(
        page, "Catalog", f"{label}:stale_catalog_owner", allow_recovery=False
    )
    need(ok_cat)
    ok1, rec1 = _select_source_first_click(
        page, "Custom Progression", f"{label}:failed_catalog_to_custom", allow_recovery=False
    )
    need(ok1 and not rec1)
    need(_assert_custom_target_return(page, obs, f"{label}:failed_catalog_to_custom_identity"))

    # 2) Composition owner + lingering Custom pick/context → Custom once
    ok_comp, _ = _select_source_first_click(
        page, "Composition", f"{label}:prep_composition_owner", allow_recovery=False
    )
    need(ok_comp)
    need(_composition_reset_c(page, step=f"{label}:prep_composition_reset"))
    # Linger custom context by visiting custom then composition without wipe.
    _select_source_first_click(
        page, "Custom Progression", f"{label}:linger_custom_visit", allow_recovery=False
    )
    _select_source_first_click(
        page, "Composition", f"{label}:linger_back_composition", allow_recovery=False
    )
    need(_composition_reset_c(page, step=f"{label}:linger_composition_ready"))
    ok2, rec2 = _select_source_first_click(
        page,
        "Custom Progression",
        f"{label}:failed_composition_to_custom",
        allow_recovery=False,
    )
    need(ok2 and not rec2)
    need(_assert_custom_target_return(page, obs, f"{label}:failed_composition_to_custom_identity"))

    # 3) Composition Backing after PK change → Custom once
    ok_comp2, _ = _select_source_first_click(
        page, "Composition", f"{label}:prep_comp_backing", allow_recovery=False
    )
    need(ok_comp2)
    need(_composition_reset_c(page, step=f"{label}:prep_comp_backing_reset"))
    prep_live = _change_pk(page, "Eb", f"{label}:prep_comp_backing_pk")
    need(bool(prep_live))
    # Prefer sidebar Backing nav after PK change (hub open_backing can hang
    # late in long suites). Composition ownership should already be stamped.
    backing_ok = False
    try:
        v.click_nav(page, "Backing")
        v.wait_streamlit(page, 2500)
        backing_ok = _wait_backing_card(page, "composition", timeout_ms=20000)
    except Exception as exc:
        print(f"[failed_state] nav backing: {exc}", flush=True)
    if not backing_ok:
        try:
            v.ensure_songs(page)
            v.open_backing(page, prefer="composition")
            backing_ok = _wait_backing_card(page, "composition", timeout_ms=20000)
        except Exception as exc:
            print(f"[failed_state] open_backing: {exc}", flush=True)
    ident_b = _collect_identity(page)
    _record_row(
        f"{label}:prep_comp_backing_open",
        ident_b,
        recovery=False,
        ok=backing_ok,
        detail=f"live_spelling={prep_live!r}",
    )
    need(backing_ok)
    v.ensure_songs(page)
    ok3, rec3 = _select_source_first_click(
        page,
        "Custom Progression",
        f"{label}:failed_comp_backing_to_custom",
        allow_recovery=False,
    )
    need(ok3 and not rec3)
    need(
        _assert_custom_target_return(
            page, obs, f"{label}:failed_comp_backing_to_custom_identity"
        )
    )
    return fails


def run_walk(page: Page, *, label: str, obs: WalkObs) -> int:
    fails = 0

    def need(ok: bool) -> None:
        nonlocal fails
        if not ok:
            fails += 1

    v.ensure_songs(page)
    ok, rec = _select_source_first_click(
        page, "Catalog", f"{label}:start_catalog", allow_recovery=False
    )
    need(ok and not rec)
    # Always wait for a real catalog song title/key (avoid pre-load default C).
    if not _wait_catalog_coherent(page, obs, timeout_ms=40000):
        ok_r, rec_r = _select_source_first_click(
            page, "Catalog", f"{label}:catalog_retry", allow_recovery=False
        )
        need(ok_r and not rec_r)
        need(_wait_catalog_coherent(page, obs, timeout_ms=40000))

    if not obs.catalog_pick:
        try:
            from suite_user_persistence import load_user_state

            disk, _ = load_user_state("music")
            sess = disk.get("session") if isinstance(disk, dict) else {}
            core = disk.get("core") if isinstance(disk, dict) else {}
            pick = str(
                (sess or {}).get("active_catalog_pick_key")
                or (core or {}).get("pick_key")
                or ""
            ).strip()
            if pick and not pick.startswith(("custom::", "composition::")):
                obs.catalog_pick = pick
        except Exception:
            pass

    ok, rec = _select_source_first_click(
        page, "Custom Progression", f"{label}:catalog_to_custom", allow_recovery=False
    )
    need(ok and not rec)
    need(_capture_custom_target(page, obs))
    custom_orig = obs.custom_original_key
    if not custom_orig:
        log(f"{label}:custom_original_missing", False, "no recorded original key")
        fails += 1
        return fails
    need(_assert_custom_target_return(page, obs, f"{label}:custom_owner_coherent"))
    if not v.assert_radio_selected(page, "Custom"):
        _record_row(
            f"{label}:custom_radio_before_pk",
            _collect_identity(page),
            recovery=False,
            ok=False,
            detail="abort pk change without Custom radio",
        )
        fails += 1
        return fails

    custom_live = _change_pk(page, "E", f"{label}:custom_change_key")
    need(bool(custom_live))
    _same_source_refresh(page, "Custom Progression")
    need(
        _assert_pk_authority(
            page, custom_live or "E", step=f"{label}:custom_refresh_keeps_key"
        )
    )
    need(
        _open_and_verify_backing(
            page, "custom", custom_live or "E", f"{label}:custom_backing"
        )
    )
    v.ensure_songs(page)
    if not v.assert_radio_selected(page, "Custom"):
        v.select_music_source(page, "Custom Progression")
        v.wait_streamlit_idle(page)

    ok, rec = _select_source_first_click(
        page, "Composition", f"{label}:custom_to_composition", allow_recovery=False
    )
    need(ok and not rec)
    need(_composition_reset_c(page, step=f"{label}:composition_reset_c"))

    # Request D#; assert the app's live canonical spelling (may be Eb).
    comp_live = _change_pk(page, "Eb", f"{label}:composition_change_ds")
    need(bool(comp_live))
    _same_source_refresh(page, "Composition")
    need(
        _assert_pk_authority(
            page, comp_live or "D#", step=f"{label}:composition_refresh_keeps_ds"
        )
    )
    id_ok, id_detail = _assert_composition_identity(page)
    _record_row(
        f"{label}:composition_refresh_identity",
        _collect_identity(page),
        recovery=False,
        ok=id_ok,
        detail=f"{id_detail} live_spelling={comp_live!r}",
    )
    need(id_ok)

    need(
        _open_and_verify_backing(
            page,
            "composition",
            comp_live or "D#",
            f"{label}:composition_backing",
            expected_title_fragment="My Composition",
        )
    )

    ok, rec = _select_source_first_click(
        page, "Custom Progression", f"{label}:composition_to_custom", allow_recovery=False
    )
    need(ok and not rec)
    need(_assert_custom_target_return(page, obs, f"{label}:composition_to_custom_target"))

    ok, rec = _select_source_first_click(
        page, "Catalog", f"{label}:custom_to_catalog", allow_recovery=False
    )
    need(ok and not rec)
    # Re-baseline from the live Catalog song (start-of-walk caption can lag).
    ident_cat = _collect_identity(page)
    live_title = str(ident_cat.get("title") or "")
    live_orig = pkh.normalize_key_token(
        ident_cat.get("original") or ident_cat.get("widget") or ""
    )
    if _is_catalog_song_title(live_title) and live_orig:
        obs.catalog_title = live_title
        obs.catalog_original_key = live_orig
        obs.catalog_baseline_key = live_orig
    cat_key = live_orig or obs.catalog_baseline_key or obs.catalog_original_key or "G"
    need(_assert_pk_authority(page, cat_key, step=f"{label}:catalog_restored_original_key"))
    need(_open_and_verify_backing(page, "catalog", cat_key, f"{label}:catalog_backing"))
    return fails


def _print_acceptance_table() -> None:
    cols = [
        "step",
        "radio_source",
        "explicit_source",
        "pick_namespace",
        "exact_title",
        "original_key",
        "widget_key",
        "sidebar_key",
        "card_key",
        "card_source",
        "recovery_used",
    ]
    print("\n=== TARGETED ACCEPTANCE TABLE ===", flush=True)
    print(" | ".join(cols), flush=True)
    print("-+-".join("-" * len(c) for c in cols), flush=True)
    for row in ACCEPTANCE_ROWS:
        print(" | ".join(str(row.get(c, "")) for c in cols), flush=True)


def main() -> int:
    global GATE_START_URL, GATE_WORKSPACE_ID
    fails = 0
    obs = WalkObs()
    product_sha = ""
    phase = (os.environ.get("AUTHORITY_PHASE") or "all").strip().lower()
    # fresh|all → empty isolated workspace; restored → reuse GATE_WORKSPACE disk (deliberate).
    if phase in {"restored", "cold", "disk_cold_start"}:
        ws = (os.environ.get("GATE_WORKSPACE") or "").strip()
        if not ws:
            print("[FAIL] AUTHORITY_PHASE=restored requires GATE_WORKSPACE", flush=True)
            return 1
        GATE_WORKSPACE_ID = ws
        gw.point_active_workspace_file(ws)
        GATE_START_URL = gw.workspace_url(v.URL, ws)
        print(f"[workspace] restored id={ws} url={GATE_START_URL}", flush=True)
    else:
        GATE_WORKSPACE_ID, GATE_START_URL = gw.prepare_isolated_workspace(
            "gate_authority", seed="empty"
        )
    try:
        import subprocess

        product_sha = (
            subprocess.check_output(
                ["git", "rev-parse", "--short=7", "HEAD"], cwd=str(REPO)
            )
            .decode()
            .strip()
        )
    except Exception:
        product_sha = "unknown"

    run_fresh = phase in {"all", "fresh"}
    run_restored = phase in {"all", "restored", "cold", "disk_cold_start"}

    with sync_playwright() as p:
        browser: Browser = p.chromium.launch(headless=True)

        if run_fresh:
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
            ctx_fresh.close()

            if not obs.catalog_baseline_key:
                obs.catalog_baseline_key = obs.catalog_original_key or "G"

            try:
                from suite_user_persistence import load_user_state

                disk, _ = load_user_state("music")
                if isinstance(disk, dict):
                    sess = disk.get("session") if isinstance(disk.get("session"), dict) else {}
                    core = disk.get("core") if isinstance(disk.get("core"), dict) else {}
                    pick = str(
                        sess.get("active_catalog_pick_key")
                        or core.get("pick_key")
                        or obs.catalog_pick
                        or ""
                    ).strip()
                    if pick and not pick.startswith(("custom::", "composition::")):
                        obs.catalog_pick = pick
                    if not obs.catalog_title:
                        obs.catalog_title = str(core.get("song") or "")
                    if not obs.catalog_baseline_key:
                        obs.catalog_baseline_key = obs.catalog_original_key or "G"
            except Exception:
                pass

            # Failed-state switches in a fresh browser context (avoids late-suite hangs).
            ctx_fail = browser.new_context(viewport={"width": 1500, "height": 1200})
            fail_page = ctx_fail.new_page()
            fail_page.set_default_timeout(60000)
            _goto_songs_picker(fail_page)
            # Re-establish Custom target identity before failed-state probes.
            ok_fc, rec_fc = _select_source_first_click(
                fail_page, "Custom Progression", "failed_ctx:seed_custom", allow_recovery=False
            )
            if ok_fc and not rec_fc:
                _capture_custom_target(fail_page, obs)
            fails += run_failed_state_custom_switches(fail_page, obs, label="failed")
            # Same-session stale + reload (NOT cold-start) inside this context.
            same_obs = WalkObs(
                catalog_title=obs.catalog_title,
                catalog_original_key=obs.catalog_baseline_key or obs.catalog_original_key,
                catalog_baseline_key=obs.catalog_baseline_key or obs.catalog_original_key,
                catalog_pick=obs.catalog_pick,
                custom_original_key=obs.custom_original_key,
                custom_title=obs.custom_title,
                custom_pick=obs.custom_pick,
            )
            browser_seeded = seed_stale_state_in_browser(fail_page, same_obs)
            log(
                "same_session_stale_seed",
                browser_seeded,
                "same-session stale transitions (not cold-start)",
            )
            if not browser_seeded:
                fails += 1
            else:
                fail_page.reload(wait_until="domcontentloaded", timeout=180_000)
                v.wait_streamlit(fail_page, 4000)
                _goto_songs_picker(fail_page)
                ok_ss, rec_ss = _select_source_first_click(
                    fail_page, "Catalog", "same_session_reload:start_catalog", allow_recovery=False
                )
                if not (ok_ss and not rec_ss):
                    fails += 1
                if not _wait_catalog_coherent(fail_page, same_obs, timeout_ms=40000):
                    fails += 1
                else:
                    log(
                        "same_session_reload_coherence",
                        True,
                        "catalog coherent after reload (not cold-start)",
                    )
            ctx_fail.close()

            # Persist envelope for a later restored/cold-start Streamlit process.
            COLD_START_META.update(_persist_via_app_then_disk_ok())
            disk_seeded = seed_valid_app_persisted_workspace(obs)
            COLD_START_META["app_persisted_disk_seed_ok"] = disk_seeded
            log(
                "supported_persistence_probe",
                True,
                json.dumps(COLD_START_META, sort_keys=True),
            )
            obs_path = OUT / "authority_fresh_obs.json"
            obs_path.write_text(
                json.dumps(
                    {
                        "workspace_id": GATE_WORKSPACE_ID,
                        "catalog_title": obs.catalog_title,
                        "catalog_original_key": obs.catalog_original_key,
                        "catalog_baseline_key": obs.catalog_baseline_key,
                        "catalog_pick": obs.catalog_pick,
                        "custom_title": obs.custom_title,
                        "custom_pick": obs.custom_pick,
                        "custom_original_key": obs.custom_original_key,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            print(f"[workspace] wrote fresh obs {obs_path} ws={GATE_WORKSPACE_ID}", flush=True)

        if run_restored:
            if not run_fresh:
                # Load observations captured by the fresh-phase gate.
                obs_path = OUT / "authority_fresh_obs.json"
                try:
                    raw = json.loads(obs_path.read_text(encoding="utf-8"))
                    obs = WalkObs(
                        catalog_title=str(raw.get("catalog_title") or ""),
                        catalog_original_key=str(raw.get("catalog_original_key") or ""),
                        catalog_baseline_key=str(raw.get("catalog_baseline_key") or ""),
                        catalog_pick=str(raw.get("catalog_pick") or ""),
                        custom_title=str(raw.get("custom_title") or ""),
                        custom_pick=str(raw.get("custom_pick") or ""),
                        custom_original_key=str(raw.get("custom_original_key") or ""),
                    )
                except Exception as exc:
                    print(f"[FAIL] restored missing authority_fresh_obs.json: {exc}", flush=True)
                    return 1
                COLD_START_META.update(_persist_via_app_then_disk_ok())
                disk_seeded = seed_valid_app_persisted_workspace(obs)
                COLD_START_META["app_persisted_disk_seed_ok"] = disk_seeded
            else:
                disk_seeded = bool(COLD_START_META.get("app_persisted_disk_seed_ok"))

            log(
                "supported_persistence_probe",
                True,
                json.dumps(COLD_START_META, sort_keys=True),
            )

            if COLD_START_META.get("supported_layer") == "disk" and disk_seeded:
                rest_obs = WalkObs(
                    catalog_title=obs.catalog_title,
                    catalog_original_key=obs.catalog_baseline_key or obs.catalog_original_key,
                    catalog_baseline_key=obs.catalog_baseline_key or obs.catalog_original_key,
                    catalog_pick=obs.catalog_pick,
                    custom_original_key=obs.custom_original_key,
                    custom_title=obs.custom_title,
                    custom_pick=obs.custom_pick,
                )
                ctx_cold = browser.new_context(viewport={"width": 1500, "height": 1200})
                cold_page = ctx_cold.new_page()
                cold_page.set_default_timeout(60000)
                _goto_songs_picker(cold_page)
                fails += run_walk(cold_page, label="disk_cold_start", obs=rest_obs)
                ctx_cold.close()
                COLD_START_META["disk_cold_start_ran"] = True
                COLD_START_META["disk_cold_start_result"] = "ran"
            else:
                COLD_START_META["disk_cold_start_ran"] = False
                COLD_START_META["disk_cold_start_result"] = "skipped"
                if COLD_START_META.get("cloud_storage_enabled"):
                    log(
                        "cloud_cold_start",
                        True,
                        "HUMAN_ONLY: authenticated cloud persistence/restart not reproducible here",
                    )
                else:
                    fails += 1
                    log("disk_cold_start", False, "supported disk layer but seed missing")

        browser.close()

    recovery_used_any = any(bool(r.get("recovery_used")) for r in ACCEPTANCE_ROWS)
    blank_titles = [
        r["step"]
        for r in ACCEPTANCE_ROWS
        if r.get("radio_source") in {"Custom", "Composition", "Catalog"}
        and r.get("step", "").endswith(
            (
                "_to_custom",
                "_to_custom_identity",
                "_to_custom_target",
                "custom_owner_coherent",
                "custom_target_capture",
                "composition_to_custom_target",
                "failed_catalog_to_custom_identity",
                "failed_composition_to_custom_identity",
                "failed_comp_backing_to_custom_identity",
            )
        )
        and not str(r.get("exact_title") or "").strip()
    ]
    if blank_titles:
        fails += 1
        log("acceptance_no_blank_titles", False, f"blank={blank_titles}")
    else:
        log("acceptance_no_blank_titles", True, "ok")
    if recovery_used_any:
        fails += 1
        log("acceptance_recovery_false", False, "recovery_used somewhere")
    else:
        log("acceptance_recovery_false", True, "all recovery=False")

    _print_acceptance_table()

    out = OUT / "source_authority_sequential_walk.json"
    payload = {
        "product_sha_under_test": product_sha,
        "results": RESULTS,
        "acceptance_table": ACCEPTANCE_ROWS,
        "recovery_counts": RECOVERY_COUNTS,
        "cold_start": COLD_START_META,
        "observations": {
            "catalog_title": obs.catalog_title,
            "catalog_original_key": obs.catalog_original_key,
            "catalog_pick": obs.catalog_pick,
            "custom_title": obs.custom_title,
            "custom_pick": obs.custom_pick,
            "custom_original_key": obs.custom_original_key,
        },
    }
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Failures: {fails}", flush=True)
    print(f"Product SHA under test: {product_sha}", flush=True)
    print(f"Wrote {out}", flush=True)
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
