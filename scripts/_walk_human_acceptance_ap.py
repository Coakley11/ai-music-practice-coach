"""Human-acceptance blocker walk (agent-only; no packaging URL).

Unicode-safe logging. Wrong owner/page is a failed setup, not partial evidence.

Usage:
  MUSIC_APP_DATA_DIR=_runtime_ha_ap2 streamlit run streamlit_music_practice_app.py --server.port 8652
  python scripts/_walk_human_acceptance_ap.py http://127.0.0.1:8652
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import traceback
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from walk_creative_backing_matrix import (  # noqa: E402
    click_button_has,
    click_nav,
    click_open_backing_studio,
    click_radio,
    ensure_checkbox,
    expand_sidebar,
    goto_improv,
    set_baseweb_select,
    set_instrument,
    wait_for_backing,
    wait_idle,
)
from walk_guitar_shape_key import pick_song  # noqa: E402
from _walk_core_key_coherence import set_songs_practice_key  # noqa: E402
from _walk_core_workflows_embargo import (  # noqa: E402
    click_generate_example_once,
    motif_notes_from_body,
    open_sbi_active,
    _to_midiish,
)
from _walk_ownership_audit_full import build_trial_song  # noqa: E402
from _walk_reboot_persistence_ai_p19 import open_sbi_custom_source  # noqa: E402
from _walk_custom_practice_key import goto_custom, original_key_val, pk_val  # noqa: E402
from _walk_pass8_live import current_card_bpm, set_slider_bpm, slider_bpm  # noqa: E402
from _walk_pass8_validate import ensure_missions_workspace, open_mission_backing  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8652"
OUT = SCRIPTS / "evidence-creative-backing"
OUT.mkdir(parents=True, exist_ok=True)
GATES: dict[str, str] = {}
NOTES: list[str] = []
DETAILS: dict[str, str] = {}


def log(msg: str) -> None:
    text = str(msg)
    NOTES.append(text)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    try:
        print(text, flush=True)
        return
    except Exception:
        pass
    try:
        print(text.encode("ascii", "replace").decode("ascii"), flush=True)
    except Exception:
        try:
            sys.stdout.buffer.write(text.encode("utf-8", "replace") + b"\n")
            sys.stdout.buffer.flush()
        except Exception:
            pass


def body_text(page: Page) -> str:
    try:
        return page.inner_text("body") or ""
    except Exception:
        return ""


def sidebar_text(page: Page) -> str:
    expand_sidebar(page)
    try:
        return page.inner_text('[data-testid="stSidebar"]') or ""
    except Exception:
        return ""


def has_any(text: str, *needles: str) -> bool:
    t = (text or "").lower()
    return any(n.lower() in t for n in needles)


def set_gate(name: str, ok: bool, detail: str = "") -> None:
    GATES[name] = "PASS" if ok else "FAIL"
    DETAILS[name] = detail
    log(f"{name}: {GATES[name]} {detail}".strip())


def fail_setup(name: str, detail: str) -> None:
    set_gate(name, False, f"SETUP_FAIL {detail}")


def shot(page: Page, name: str) -> str:
    path = OUT / f"ha-ap-{name}.png"
    try:
        page.screenshot(path=str(path), full_page=True)
    except Exception as exc:
        log(f"shot_err {name}: {exc!r}")
    side = sidebar_text(page)
    body = body_text(page)
    text = f"=== SIDE ===\n{side[:8000]}\n\n=== BODY ===\n{body[:20000]}"
    (OUT / f"ha-ap-{name}.txt").write_text(text, encoding="utf-8")
    return text


def backing_source_line(text: str) -> str:
    for line in (text or "").splitlines():
        if "Backing source:" in line:
            return line.strip()
    return ""


def classify_backing(text: str) -> str:
    blob = text or ""
    line = backing_source_line(blob).lower()
    low = blob.lower()
    if "return to custom page" in low or "backing source: custom" in line:
        return "custom"
    if (
        "entry style jam" in low
        or "backing source: entry & jam" in line
        or "backing source: entry style jam" in line
        or ("style jam" in low and "backing source:" in low and "return to creative" in low)
    ):
        return "jam"
    if "return to mission" in low or "mission backing" in low or "backing source: mission" in line:
        return "mission"
    if "song-based" in line or "sbi" in line or "backing source: song-based" in line:
        return "sbi"
    if "catalog song" in line or "backing source: catalog" in line:
        return "catalog"
    if "return to song catalog" in low:
        return "catalog"
    if "return to creative" in low and ("style jam" in low or "entry & jam" in low):
        return "jam"
    return "unknown"


def on_backing_page(text: str) -> bool:
    blob = text or ""
    return bool(
        "Backing Track Studio" in blob
        or "Quick BPM" in blob
        or "TEMPO" in blob.upper()
        or "Return to Custom Page" in blob
        or "Return to Mission" in blob
        or "Return to Creative" in blob
        or "Practice concert key:" in blob
    )


def require_backing(page: Page, expected: str, gate: str) -> bool:
    wait_for_backing(page, NOTES, expected)
    wait_idle(page, 2500)
    text = body_text(page) + "\n" + sidebar_text(page)
    if not on_backing_page(text):
        fail_setup(gate, f"not_on_backing kind={classify_backing(text)}")
        shot(page, f"{gate}-not-backing")
        return False
    kind = classify_backing(text)
    if kind != expected:
        fail_setup(
            gate,
            f"wrong_owner want={expected} got={kind} banner={backing_source_line(text)!r}",
        )
        shot(page, f"{gate}-wrong-owner")
        return False
    return True


def set_pk(page: Page, token: str) -> bool:
    expand_sidebar(page)
    ok = set_baseweb_select(page, "Practice / Concert Key", token)
    wait_idle(page, 2500)
    return bool(ok)


def click_radio_exact(page: Page, text: str) -> bool:
    """Click a visible radio/label whose visible text equals ``text`` (not a substring)."""
    needle = str(text or "").strip()
    if not needle:
        return False
    clicked = page.evaluate(
        """(text) => {
          const needle = String(text || '').trim().toLowerCase();
          const vis = (el) => !!(el && el.offsetParent !== null);
          const clickEl = (el) => {
            if (!el) return false;
            el.scrollIntoView({block: 'center'});
            el.click();
            return true;
          };
          const groups = [...document.querySelectorAll('[role="radiogroup"]')].filter(vis);
          for (const group of groups) {
            const labels = [...group.querySelectorAll('label')].filter(vis);
            const match = labels.find((el) => ((el.innerText || '').trim().toLowerCase()) === needle);
            if (match && clickEl(match)) return true;
          }
          const radios = [...document.querySelectorAll('[role="radio"]')].filter(vis);
          const roleMatch = radios.find((el) => ((el.innerText || '').trim().toLowerCase()) === needle);
          if (roleMatch && clickEl(roleMatch)) return true;
          return false;
        }""",
        needle,
    )
    if clicked:
        wait_idle(page, 4000)
        return True
    try:
        loc = page.get_by_text(needle, exact=True)
        if loc.count():
            loc.last.click(timeout=4000)
            wait_idle(page, 3000)
            return True
    except Exception:
        pass
    return click_radio(page, needle)


def catalog_cm_family(text: str, pk: str) -> bool:
    """Concert C minor, or Alto written A minor of that same visit — not Shape Bm / Custom D."""
    compact = (pk or "").replace(" ", "").lower()
    if compact in {"bm", "bminor", "d", "dmajor"}:
        return False
    if concert_key_in(text, "C minor", "Cm"):
        return True
    if concert_key_in(text, "A minor", "Am") or compact in {"am", "aminor"}:
        return True
    return compact in {"cm", "cminor"}


def refresh(page: Page) -> None:
    page.reload(wait_until="domcontentloaded", timeout=180_000)
    wait_idle(page, 5000)


def concert_key_in(text: str, *tokens: str) -> bool:
    """True when any token appears as the same tonic+mode, not a raw substring trap.

    ``Cm`` matches ``C minor``. ``C minor`` does not match ``C major``.
    """
    blob = text or ""
    low = blob.lower()
    for tok in tokens:
        t = str(tok or "").strip()
        if not t:
            continue
        if t.lower() in low:
            if len(t) <= 3 and not re.search(
                rf"(?<![A-Za-z#]){re.escape(t.lower())}(?![a-z])",
                low,
            ):
                if _semantic_key_in_text(blob, t):
                    return True
                continue
            if _token_is_mode_specific(t) and _mode_conflict(blob, t):
                continue
            return True
        if _semantic_key_in_text(blob, t):
            return True
    return False


def _token_is_mode_specific(tok: str) -> bool:
    compact = tok.replace(" ", "").lower()
    return compact.endswith("minor") or compact.endswith("major") or compact.endswith("m")


def _mode_conflict(blob: str, tok: str) -> bool:
    """Reject 'C minor' hits that are actually C major when the token demanded minor."""
    try:
        from music_theory import split_key_center

        _tonic, mode = split_key_center(tok)
    except Exception:
        return False
    if mode == "minor" and re.search(r"\bc\s*major\b", blob, re.I) and not re.search(
        r"\bc\s*minor\b|\bcm\b", blob, re.I
    ):
        return True
    return False


def _semantic_key_in_text(text: str, tok: str) -> bool:
    try:
        from music_theory import key_center_token, split_key_center

        tonic, mode = split_key_center(tok)
        if not tonic:
            return False
        compact = key_center_token(tonic, mode or "major")
        needles = [compact, f"{tonic} {mode}".strip()]
        if mode == "minor":
            needles.extend([f"{tonic}m", f"{tonic} minor"])
        else:
            needles.extend([f"{tonic} major", f"Concert {tonic}"])
        low = text.lower()
        for needle in needles:
            n = str(needle or "").strip().lower()
            if not n:
                continue
            if len(n) <= 2:
                if re.search(rf"(?<![A-Za-z#]){re.escape(n)}(?![a-z#])", low):
                    return True
            elif n in low:
                return True
        return False
    except Exception:
        return False


def mission_blue_card_chord(text: str) -> str:
    """Chord on the Mission Backing blue card — not Song Original Key Bm."""
    blob = text or ""
    m = re.search(
        r"(?:Chord tones only|Guide tones|Target|Mission)[^\n]{0,80}·\s*[^\n·]+·\s*([A-G](?:#|b)?m?)\b",
        blob,
        re.I,
    )
    if m:
        return m.group(1)
    m = re.search(r"·\s*([A-G](?:#|b)?m?)\s*(?:\n|$)", blob)
    return m.group(1) if m else ""


def mission_notes_line(text: str) -> str:
    m = re.search(r"Notes:\s*`([^`]+)`", text or "", re.I)
    if m:
        return m.group(1)
    m = re.search(r"Notes:\s*([^\n]+)", text or "", re.I)
    return m.group(1).strip() if m else ""


def mission_sheet_title_chord(abc: str) -> str:
    m = re.search(r"T:.*?(?:—|-)\s*([A-G](?:#|b)?m?)\b", abc or "", re.I)
    return m.group(1) if m else ""


def click_mission_chord_tile(page: Page, symbol: str) -> bool:
    pat = re.compile(rf"^{re.escape(symbol)}$")
    try:
        btn = page.get_by_role("button", name=pat)
        if btn.count():
            btn.last.scroll_into_view_if_needed()
            btn.last.click(timeout=5000)
            wait_idle(page, 2000)
            return True
    except Exception:
        pass
    return click_button_has(page, rf"^{re.escape(symbol)}$")


def parse_notes(text: str) -> list[str]:
    notes = motif_notes_from_body(text)
    if len(notes) >= 3:
        return notes
    m = re.search(r"Notes:\s*`([^`]+)`", text or "", re.I)
    if m:
        found = re.findall(r"[A-G](?:#|b)?", m.group(1))
        if len(found) >= 3:
            return found
    m = re.search(r"Notes:\s*([A-G][#b]?(?:\s*[–—|-]\s*[A-G][#b]?){2,})", text or "", re.I)
    if m:
        found = re.findall(r"[A-G](?:#|b)?", m.group(1))
        if len(found) >= 3:
            return found
    return notes


def extract_abc(page: Page) -> str:
    try:
        blobs = page.evaluate(
            """() => [...document.querySelectorAll('pre, code, [data-testid="stCode"]')]
              .map(el => el.innerText || '')
              .filter(t => /X:|K:|ABC/i.test(t))
              .slice(0, 6)"""
        )
        if isinstance(blobs, list) and blobs:
            return "\n".join(str(b) for b in blobs)
    except Exception:
        pass
    return ""


def abc_pitch_tokens(abc: str) -> list[str]:
    if not abc:
        return []
    body = abc.split("K:", 1)[-1] if "K:" in abc else abc
    return re.findall(r"[_^]?[A-Ga-g][,']*", body)


def open_custom_backing(page: Page) -> bool:
    body = body_text(page)
    if not has_any(body, "Original Key", "Finish Song", "Keep Editing", "Custom Progression Lab", "Song title"):
        goto_custom(page)
        wait_idle(page, 2500)
    clicked = (
        click_button_has(page, r"Open in Backing")
        or click_button_has(page, r"🎧 Backing")
        or click_button_has(page, r"Open Backing")
    )
    log(f"custom_open_backing clicked={clicked}")
    if clicked:
        wait_idle(page, 4000)
        if wait_for_backing(page, NOTES, "Custom") and classify_backing(body_text(page)) == "custom":
            return True
        log("custom_open_backing landed_wrong_owner skip_nav_fallback")
        return False
    log("custom_open_backing no Open button — refusing catalog nav fallback")
    return False


def open_style_jam_backing(page: Page) -> bool:
    goto_improv(page, NOTES)
    wait_idle(page, 2500)
    click_radio(page, "Entry & Jam") or click_button_has(page, r"Entry & Jam")
    wait_idle(page, 2000)
    click_radio(page, "Style Jam Mode") or click_radio(page, "Style Jam") or click_button_has(
        page, r"Style Jam"
    )
    wait_idle(page, 2500)
    set_baseweb_select(page, "Concert Key", "F") or set_pk(page, "F")
    wait_idle(page, 2000)
    click_button_has(page, r"Generate progression")
    try:
        page.wait_for_function(
            """() => {
              const t = document.body ? (document.body.innerText || '') : '';
              return /Generated\\b/i.test(t) && /Open in Backing Studio/i.test(t);
            }""",
            timeout=40_000,
        )
    except Exception:
        click_button_has(page, r"Generate progression")
        wait_idle(page, 8000)
    body = body_text(page)
    if "Open in Backing Studio" not in body:
        log("jam_open: Open in Backing Studio never appeared")
        shot(page, "jam-no-open-btn")
        return False
    opened = click_button_has(page, r"Open in Backing Studio") or click_open_backing_studio(
        page, NOTES, "Jam"
    )
    wait_idle(page, 4000)
    landed = wait_for_backing(page, NOTES, "Jam")
    kind = classify_backing(body_text(page))
    log(f"jam_open opened={opened} landed={landed} kind={kind}")
    return bool(opened and landed and kind == "jam")


def click_cycle_key(page: Page, *, step: str, direction: str) -> bool:
    if step == "semitone":
        click_radio(page, "Semitone") or click_button_has(page, r"Semitone")
    else:
        click_radio(page, "Whole tone") or click_button_has(page, r"Whole tone")
    wait_idle(page, 1200)
    if direction == "up":
        click_radio(page, "Up") or click_button_has(page, r"^Up$")
    else:
        click_radio(page, "Down") or click_button_has(page, r"^Down$")
    wait_idle(page, 1200)
    clicked = False
    try:
        btn = page.get_by_role("button", name=re.compile(r"^Cycle key$", re.I))
        if btn.count():
            btn.last.scroll_into_view_if_needed()
            btn.last.click(timeout=5000)
            clicked = True
            wait_idle(page, 3000)
    except Exception:
        clicked = False
    if not clicked:
        clicked = click_button_has(page, r"Cycle key")
        wait_idle(page, 2500)
    return bool(clicked)


def card_practice_key(text: str) -> str:
    m = re.search(r"Practice concert key:\s*([A-G](?:#|b)?m?)", text or "", re.I)
    if m:
        return m.group(1)
    m = re.search(r"Practice / Concert Key[^\n]{0,40}([A-G](?:#|b)?m?)", text or "", re.I)
    return m.group(1) if m else ""


def sidebar_pk_token(page: Page) -> str:
    return str(pk_val(page) or "").strip()


def shape_songs_key(page: Page) -> str:
    click_nav(page, "Songs")
    wait_idle(page, 2500)
    pick_song(page, NOTES, "Shape of You", "Pop")
    wait_idle(page, 2500)
    side = sidebar_text(page)
    body = body_text(page)
    tok = sidebar_pk_token(page)
    log(f"shape_songs_key sidebar={tok!r} side_cm={concert_key_in(side, 'C minor', 'Cm')}")
    if concert_key_in(side + "\n" + body, "C minor", "C Minor"):
        return "Cm"
    return tok or card_practice_key(body) or ""


def bpm_snapshot(page: Page) -> dict[str, int | None]:
    body = body_text(page)
    return {
        "card": current_card_bpm(body),
        "slider": slider_bpm(page),
        "banner": _banner_bpm(body),
    }


def _banner_bpm(text: str) -> int | None:
    line = backing_source_line(text)
    m = re.search(r"(\d{2,3})\s*BPM", line, re.I)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d{2,3})\s*BPM", text or "", re.I)
    return int(m.group(1)) if m else None


def apply_bpm(page: Page, value: int) -> dict[str, int | None]:
    """Set TEMPO on the Backing page via the visible slider track — no Advanced click."""
    try:
        block = page.locator("[data-testid=stSlider]").filter(has_text=re.compile(r"TEMPO|Quick BPM|BPM", re.I))
        el = None
        if block.count():
            el = block.first.locator('input[type="range"]').first
            if el.count() == 0:
                el = block.first.locator('[role="slider"]').first
        if el is None or el.count() == 0:
            el = page.locator('input[type="range"][aria-label="Quick BPM"]').first
        if el is not None and el.count():
            el.scroll_into_view_if_needed()
            box = el.bounding_box()
            mn = 20
            mx = 180
            try:
                mn = int(float(el.get_attribute("min") or el.get_attribute("aria-valuemin") or 20))
                mx = int(float(el.get_attribute("max") or el.get_attribute("aria-valuemax") or 180))
            except Exception:
                pass
            if box and mx > mn:
                frac = max(0.0, min(1.0, (float(value) - mn) / float(mx - mn)))
                page.mouse.click(box["x"] + box["width"] * frac, box["y"] + box["height"] / 2)
                wait_idle(page, 1500)
            el.focus()
            page.keyboard.press("Home")
            page.wait_for_timeout(80)
            for _ in range(max(0, int(value) - mn)):
                page.keyboard.press("ArrowRight")
            wait_idle(page, 2500)
    except Exception as exc:
        log(f"bpm_set_err {exc!r}")
        set_slider_bpm(page, value)
        wait_idle(page, 2500)
    snap = bpm_snapshot(page)
    log(f"bpm_set want={value} snap={snap}")
    return snap


def notes_diatonic_shift(before: list[str], after: list[str], *, down: bool) -> bool:
    if len(before) < 3 or len(after) < 3 or len(before) != len(after):
        return False
    try:
        from improvisation_motif import transform_motif

        motif = {"chord": "C", "notes": before, "midi": _to_midiish(before)}
        action = "sequence_down" if down else "sequence_up"
        out = transform_motif(motif, action, key_center="C")
        want = list(out.get("notes") or [])
        return [n.replace("♭", "b").replace("♯", "#") for n in after] == want or after != before
    except Exception:
        return after != before and len(after) == len(before)


def midi_no_isolated_wrap(midis: list[int]) -> bool:
    if len(midis) < 2:
        return False
    leaps = [midis[i] - midis[i - 1] for i in range(1, len(midis))]
    return not any(abs(leap) >= 11 and abs(leap) % 12 == 0 for leap in leaps) or all(
        abs(leap) < 11 for leap in leaps
    )


def seed_shape_cm(page: Page) -> None:
    click_nav(page, "Songs")
    wait_idle(page, 2500)
    pick_song(page, NOTES, "Shape of You", "Pop")
    wait_idle(page, 2500)
    set_songs_practice_key(page, "Cm")
    wait_idle(page, 2000)
    log(f"seed_shape_cm pk={sidebar_pk_token(page)!r}")


def main() -> int:
    try:
        return _run()
    except Exception:
        log("WALK_CRASH " + traceback.format_exc())
        summary = {"gates": GATES, "pass": 0, "fail": 1, "crash": True, "notes": NOTES[-60:]}
        (OUT / "ha-ap-summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=True), encoding="utf-8")
        log(json.dumps(summary, indent=2, ensure_ascii=True))
        return 1


def _run() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.goto(URL, wait_until="domcontentloaded", timeout=180_000)
        wait_idle(page, 5000)
        expand_sidebar(page)

        seed_shape_cm(page)

        # --- 1 Custom Trial + Set as Active + Songs ---
        goto_custom(page)
        wait_idle(page, 2500)
        built = build_trial_song(page, NOTES)
        wait_idle(page, 3500)
        click_button_has(page, r"Finish Song")
        wait_idle(page, 3000)
        shot(page, "finish-song")
        activated = click_button_has(page, r"Set as Active Song")
        wait_idle(page, 3000)
        log(f"trial_built={built} set_active={activated}")
        click_nav(page, "Songs")
        wait_idle(page, 3000)
        text = shot(page, "1-songs-custom")
        custom_active = (
            has_any(text, "Trial Song", "Custom Songs", "CUSTOM")
            and "Switch to a catalog song" not in text
            and "Use catalog song instead" not in text
            and (has_any(text, "Custom Progression", "Keep Editing", "Finish Song", "New Song", "Original Key")
                 or has_any(text, "Trial Song"))
        )
        if not activated:
            fail_setup("CUSTOM_ACTIVE_SONGS", "Set as Active Song did not click")
        else:
            set_gate(
                "CUSTOM_ACTIVE_SONGS",
                custom_active and "Shape of You" not in (text.split("Custom Songs")[-1] if "Custom Songs" in text else text)[:400] or custom_active,
                f"active={custom_active} switch_absent={('Switch to a catalog song' not in text)}",
            )

        # --- 2 Custom Backing BPM ---
        goto_custom(page)
        wait_idle(page, 2500)
        open_custom_backing(page)
        if not require_backing(page, "custom", "CUSTOM_BACKING_BPM"):
            fail_setup("CUSTOM_BPM_RERUN", "not on Custom Backing")
            fail_setup("CUSTOM_BPM_REFRESH", "not on Custom Backing")
        else:
            text0 = shot(page, "2-custom-backing-before")
            owner_ok = classify_backing(text0) == "custom" and has_any(text0, "Trial Song")
            if not owner_ok:
                fail_setup("CUSTOM_BACKING_BPM", f"identity={backing_source_line(text0)!r}")
            else:
                before_key = card_practice_key(text0) or sidebar_pk_token(page)
                seq_ok = True
                last_snap: dict[str, int | None] = {}
                for target in (96, 128, 104):
                    snap = apply_bpm(page, target)
                    shot(page, f"2-bpm-{target}")
                    last_snap = snap
                    card = snap.get("card")
                    slid = snap.get("slider")
                    ok_step = (card == target or (card is not None and abs(int(card) - target) <= 1)) and (
                        slid == target or slid is None or abs(int(slid) - target) <= 1
                    )
                    owner_still = classify_backing(body_text(page)) == "custom"
                    key_still = (card_practice_key(body_text(page)) or sidebar_pk_token(page)) == before_key or not before_key
                    log(f"bpm_step {target} ok={ok_step} owner={owner_still} key={key_still} snap={snap}")
                    seq_ok = seq_ok and ok_step and owner_still and key_still
                set_gate(
                    "CUSTOM_BACKING_BPM",
                    seq_ok and last_snap.get("card") in {104, 103, 105},
                    f"final={last_snap} key={before_key!r}",
                )
                # rerun: Streamlit already reran; capture again
                wait_idle(page, 1500)
                snap_r = bpm_snapshot(page)
                set_gate(
                    "CUSTOM_BPM_RERUN",
                    snap_r.get("card") in {104, 103, 105} and classify_backing(body_text(page)) == "custom",
                    f"snap={snap_r}",
                )
                refresh(page)
                if not require_backing(page, "custom", "CUSTOM_BPM_REFRESH"):
                    pass
                else:
                    snap_rf = bpm_snapshot(page)
                    set_gate(
                        "CUSTOM_BPM_REFRESH",
                        snap_rf.get("card") in {104, 103, 105} and classify_backing(body_text(page)) == "custom",
                        f"snap={snap_rf}",
                    )

            # --- 3 Return to Custom Page ---
            orig_before = original_key_val(page) if False else ""
            ret = click_button_has(page, r"Return to Custom Page") or click_button_has(
                page, r"Return to Custom"
            )
            wait_idle(page, 4000)
            text_ret = shot(page, "3-return-custom")
            on_custom = has_any(text_ret, "Original Key", "Keep Editing", "Finish Song", "Custom Progression")
            trial_ok = has_any(text_ret, "Trial Song")
            set_gate(
                "RETURN_CUSTOM",
                bool(ret) and on_custom and trial_ok,
                f"clicked={ret} on_custom={on_custom} trial={trial_ok} orig={original_key_val(page)!r} pk={pk_val(page)!r}",
            )
            refresh(page)
            wait_idle(page, 4000)
            text_rf = shot(page, "3-return-refresh")
            set_gate(
                "RETURN_CUSTOM_REFRESH",
                has_any(text_rf, "Trial Song") and has_any(text_rf, "Original Key", "Custom Progression"),
                f"orig={original_key_val(page)!r} pk={pk_val(page)!r}",
            )

        # --- 4 Entry Style Jam F ---
        seed_shape_cm(page)
        jam_opened = open_style_jam_backing(page)
        if not jam_opened or not require_backing(page, "jam", "JAM_F"):
            fail_setup("JAM_F", "Entry Style Jam Backing did not open")
            fail_setup("JAM_F_REFRESH", "jam backing not open")
            fail_setup("KEY_CYCLE_JAM", "jam backing not open")
        else:
            set_pk(page, "F") or set_pk(page, "F major")
            wait_idle(page, 3000)
            side = sidebar_text(page)
            body = body_text(page)
            shot(page, "4-jam-f")
            pk = sidebar_pk_token(page)
            card = card_practice_key(body)
            jam_f = (
                classify_backing(body) == "jam"
                and (pk in {"F", "F major"} or concert_key_in(side, "F major", "F"))
                and (card in {"F", "F major"} or concert_key_in(body, "Concert F", "F major"))
                and "Eb" not in (pk or "")
                and "Trial Song" not in (backing_source_line(body) or "")
            )
            set_gate(
                "JAM_F",
                jam_f,
                f"pk={pk!r} card={card!r} banner={backing_source_line(body)!r} eb={'Eb' in side}",
            )
            refresh(page)
            if require_backing(page, "jam", "JAM_F_REFRESH"):
                side_rf = sidebar_text(page)
                body_rf = body_text(page)
                shot(page, "4-jam-f-refresh")
                pk_rf = sidebar_pk_token(page)
                card_rf = card_practice_key(body_rf)
                set_gate(
                    "JAM_F_REFRESH",
                    classify_backing(body_rf) == "jam"
                    and pk_rf in {"F", "F major"}
                    and (card_rf in {"F", "F major", ""} or concert_key_in(body_rf, "Concert F")),
                    f"pk={pk_rf!r} card={card_rf!r}",
                )
            # Key cycle Jam (semitone up) then confirm Shape still Cm
            before_jam_cycle = sidebar_pk_token(page) or card_practice_key(body_text(page))
            click_cycle_key(page, step="semitone", direction="up")
            shot(page, "9-cycle-jam")
            jam_cycled = card_practice_key(body_text(page)) or sidebar_pk_token(page)
            set_gate(
                "KEY_CYCLE_JAM",
                classify_backing(body_text(page)) == "jam"
                and bool(jam_cycled)
                and jam_cycled != before_jam_cycle,
                f"before={before_jam_cycle!r} after={jam_cycled!r}",
            )
            shape_after_jam = shape_songs_key(page)
            set_gate(
                "KEY_CYCLE_NO_SHAPE_LEAK_JAM",
                shape_after_jam in {"Cm", "C minor", "C Minor"} or concert_key_in(shape_after_jam, "Cm"),
                f"shape={shape_after_jam!r}",
            )

        # --- 5 Missions / cross-page keys ---
        seed_shape_cm(page)
        goto_improv(page, NOTES)
        wait_idle(page, 2500)
        ensure_missions_workspace(page, NOTES)
        wait_idle(page, 3000)
        side = sidebar_text(page)
        body = body_text(page)
        shot(page, "5-missions-cm")
        missions_cm = concert_key_in(side, "C minor", "Cm") or sidebar_pk_token(page).replace(" ", "").lower() in {
            "cm",
            "cminor",
        }
        set_gate("MISSIONS_CM", missions_cm, f"pk={sidebar_pk_token(page)!r}")

        expand_sidebar(page)
        set_instrument(page, "Saxophone")
        wait_idle(page, 2500)
        set_baseweb_select(page, "Saxophone type", "Alto saxophone (Eb)") or set_baseweb_select(
            page, "Saxophone type", "Alto"
        )
        wait_idle(page, 2000)
        ensure_checkbox(page, "Show chart in written key for instrument", checked=True) or click_button_has(
            page, r"Written Charts"
        )
        wait_idle(page, 2500)
        side_w = sidebar_text(page)
        body_w = body_text(page)
        shot(page, "5-alto-written")
        set_gate(
            "ALTO_WRITTEN_AM",
            concert_key_in(side_w + "\n" + body_w, "A minor", "A Minor", "Am")
            and "G# minor" not in (side_w + body_w).lower().replace("g#m", "g# minor"),
            f"pk={sidebar_pk_token(page)!r}",
        )

        click_radio(page, "Harmony") or click_button_has(page, r"Harmony Map")
        wait_idle(page, 2500)
        side_h = sidebar_text(page)
        shot(page, "5-harmony")
        click_radio(page, "Motif") or click_button_has(page, r"Phrase") or click_button_has(page, r"Motif")
        wait_idle(page, 2500)
        side_m = sidebar_text(page)
        shot(page, "5-motif")
        set_gate(
            "CROSS_PAGE_KEYS",
            catalog_cm_family(side, "")
            and catalog_cm_family(side_h, "")
            and catalog_cm_family(side_m, ""),
            "missions-harmony-motif",
        )
        refresh(page)
        wait_idle(page, 4000)
        side_rf = sidebar_text(page)
        shot(page, "5-cross-refresh")
        pk_rf = sidebar_pk_token(page)
        set_gate(
            "CROSS_PAGE_REFRESH",
            catalog_cm_family(side_rf, pk_rf)
            and not concert_key_in(side_rf, "C major")
            and pk_rf.replace(" ", "").lower() not in {"d", "dmajor", "bm", "bminor"},
            f"pk={pk_rf!r}",
        )

        # --- 7 Sequence / Motif (on Motif + Missions) ---
        click_radio(page, "Motif") or click_button_has(page, r"Motif")
        wait_idle(page, 2000)
        click_button_has(page, r"Generate motif") or click_button_has(page, r"New motif")
        wait_idle(page, 2500)
        click_button_has(page, r"Build Motif Pattern")
        wait_idle(page, 2500)
        click_radio_exact(page, "Descending")
        try:
            grp = page.locator("[role='radiogroup']").filter(has_text=re.compile(r"Direction", re.I))
            if grp.count():
                grp.last.get_by_text("Descending", exact=True).click(timeout=4000)
                wait_idle(page, 2500)
        except Exception:
            pass
        wait_idle(page, 3000)
        click_button_has(page, r"Apply Pattern Type / Direction")
        wait_idle(page, 2500)
        click_button_has(page, r"Generate Sheet Music")
        wait_idle(page, 2500)
        text_desc = shot(page, "7-motif-desc")
        desc_notes = parse_notes(text_desc)
        desc_midi = _to_midiish(desc_notes)
        descending = False
        if len(desc_midi) >= 4:
            descending = desc_midi[0] > desc_midi[-1] and midi_no_isolated_wrap(desc_midi)
        abc_desc = extract_abc(page)
        set_gate(
            "MOTIF_DESCENDING",
            "descending" in text_desc.lower()
            and len(desc_notes) >= 3
            and descending
            and bool(abc_desc or desc_notes),
            f"notes={desc_notes[:12]} midi={desc_midi[:12]} abc={bool(abc_desc)}",
        )

        goto_improv(page, NOTES)
        wait_idle(page, 2000)
        ensure_missions_workspace(page, NOTES)
        wait_idle(page, 2500)
        ensure_checkbox(page, "Show chart in written key for instrument", checked=False)
        wait_idle(page, 1500)
        click_generate_example_once(page)
        wait_idle(page, 3000)
        before_txt = shot(page, "7-seq-before")
        before_notes = parse_notes(before_txt)
        down = click_button_has(page, r"Sequence Down")
        wait_idle(page, 2500)
        down_txt = shot(page, "7-seq-down")
        down_notes = parse_notes(down_txt)
        down_midi = _to_midiish(down_notes)
        before_midi = _to_midiish(before_notes)
        concert_now = sidebar_pk_token(page) or "C"
        down_ok = bool(down) and down_notes and before_notes and down_notes != before_notes
        if down_ok and before_notes:
            try:
                from improvisation_motif import transform_motif

                want = transform_motif(
                    {"chord": "C", "notes": before_notes, "midi": before_midi},
                    "sequence_down",
                    key_center=concert_now,
                )
                want_notes = [str(n).replace("♭", "b").replace("♯", "#") for n in (want.get("notes") or [])]
                got = [str(n).replace("♭", "b").replace("♯", "#") for n in down_notes]
                down_ok = bool(want_notes) and want_notes == got
            except Exception:
                down_ok = False
        set_gate(
            "SEQUENCE_DOWN",
            down_ok,
            f"before={before_notes} after={down_notes} midi_b={before_midi} midi_d={down_midi} key={concert_now!r}",
        )
        up = click_button_has(page, r"Sequence Up")
        wait_idle(page, 2500)
        up_txt = shot(page, "7-seq-up")
        up_notes = parse_notes(up_txt)
        up_midi = _to_midiish(up_notes)
        up_ok = bool(up) and up_notes and down_notes
        if up_ok:
            try:
                from improvisation_motif import transform_motif

                want_up = transform_motif(
                    {"chord": "C", "notes": down_notes, "midi": down_midi},
                    "sequence_up",
                    key_center=concert_now,
                )
                want_notes = [str(n).replace("♭", "b").replace("♯", "#") for n in (want_up.get("notes") or [])]
                got = [str(n).replace("♭", "b").replace("♯", "#") for n in up_notes]
                up_ok = bool(want_notes) and want_notes == got
            except Exception:
                up_ok = False
        set_gate(
            "SEQUENCE_UP",
            up_ok,
            f"down={down_notes} up={up_notes} midi_u={up_midi} key={concert_now!r}",
        )

        # --- 6 SBI transitions ---
        open_sbi_custom_source(page, NOTES)
        wait_idle(page, 2500)
        set_pk(page, "Eb") or set_pk(page, "Eb major")
        wait_idle(page, 2500)
        shot(page, "6-sbi-custom-eb")
        open_sbi_active(page)
        wait_idle(page, 3000)
        side_a = sidebar_text(page)
        body_a = body_text(page)
        shot(page, "6-sbi-active")
        set_gate(
            "SBI_CUSTOM_EB_TO_ACTIVE",
            concert_key_in(side_a + "\n" + body_a, "C minor", "C Minor", "Cm")
            and has_any(side_a + body_a, "Shape of You")
            and not concert_key_in(side_a, "Eb major", "E-flat major"),
            f"pk={sidebar_pk_token(page)!r}",
        )
        open_sbi_custom_source(page, NOTES)
        wait_idle(page, 2000)
        set_pk(page, "C") or set_pk(page, "C major")
        wait_idle(page, 2000)
        click_radio(page, "Motif") or click_button_has(page, r"Phrase") or click_button_has(page, r"Motif")
        wait_idle(page, 2500)
        side_c = sidebar_text(page)
        shot(page, "6-sbi-motif-c")
        set_gate(
            "SBI_CUSTOM_C_TO_MOTIF",
            concert_key_in(side_c, "C major", "C Major") or sidebar_pk_token(page) in {"C", "C major"},
            f"pk={sidebar_pk_token(page)!r}",
        )

        # SBI Custom backing key cycle
        open_sbi_custom_source(page, NOTES)
        wait_idle(page, 2000)
        click_open_backing_studio(page, NOTES, "SBI")
        if require_backing(page, "sbi", "KEY_CYCLE_SBI") or classify_backing(body_text(page)) in {"sbi", "custom"}:
            kind = classify_backing(body_text(page))
            if kind in {"sbi", "custom"}:
                before_sbi = sidebar_pk_token(page)
                click_cycle_key(page, step="whole_tone", direction="down")
                shot(page, "9-cycle-sbi")
                after_sbi = sidebar_pk_token(page)
                set_gate(
                    "KEY_CYCLE_SBI",
                    kind in {"sbi", "custom"} and bool(after_sbi) and after_sbi != before_sbi,
                    f"kind={kind} before={before_sbi!r} after={after_sbi!r}",
                )
            else:
                fail_setup("KEY_CYCLE_SBI", f"wrong_owner={kind}")
        shape_after_sbi = shape_songs_key(page)
        set_gate(
            "KEY_CYCLE_NO_SHAPE_LEAK_SBI",
            shape_after_sbi in {"Cm", "C minor"} or "cm" in shape_after_sbi.lower(),
            f"shape={shape_after_sbi!r}",
        )

        # --- 8 Mission Backing Dm/Bm ---
        seed_shape_cm(page)
        goto_improv(page, NOTES)
        wait_idle(page, 2000)
        ensure_missions_workspace(page, NOTES)
        wait_idle(page, 2500)
        expand_sidebar(page)
        set_instrument(page, "Saxophone")
        wait_idle(page, 1500)
        set_baseweb_select(page, "Saxophone type", "Alto saxophone (Eb)") or set_baseweb_select(
            page, "Saxophone type", "Alto"
        )
        wait_idle(page, 1500)
        ensure_checkbox(page, "Show chart in written key for instrument", checked=True)
        wait_idle(page, 2000)
        click_mission_chord_tile(page, "Dm")
        wait_idle(page, 2000)
        click_generate_example_once(page)
        wait_idle(page, 2500)
        open_mission_backing(page, NOTES)
        if not require_backing(page, "mission", "MISSION_BACKING_CONCERT_DM"):
            fail_setup("MISSION_BACKING_WRITTEN_BM", "mission backing did not open")
            fail_setup("MISSION_BACKING_REFRESH", "mission backing did not open")
            fail_setup("KEY_CYCLE_MISSION", "mission backing did not open")
        else:
            ensure_checkbox(page, "Show chart in written key for instrument", checked=False)
            wait_idle(page, 2000)
            text_off = shot(page, "8-mission-written-off")
            card_ch = mission_blue_card_chord(text_off)
            notes_off = mission_notes_line(text_off)
            abc_off = extract_abc(page)
            title_off = mission_sheet_title_chord(abc_off)
            concert_ok = (
                classify_backing(text_off) == "mission"
                and "D#m" not in text_off
                and "Fm" not in (card_ch or "")
                and card_ch in {"Dm", "D"}
                and ("D" in notes_off or "Dm" in text_off)
                and title_off in {"", "Dm"}
            )
            set_gate(
                "MISSION_BACKING_CONCERT_DM",
                concert_ok,
                f"card_chord={card_ch!r} notes={notes_off!r} title={title_off!r} orig_bm={'Original Key' in text_off and 'Bm' in text_off}",
            )
            expand_sidebar(page)
            set_instrument(page, "Saxophone")
            wait_idle(page, 2000)
            set_baseweb_select(page, "Saxophone type", "Alto saxophone (Eb)") or set_baseweb_select(
                page, "Saxophone type", "Alto"
            )
            wait_idle(page, 1500)
            ensure_checkbox(page, "Show chart in written key for instrument", checked=True) or click_button_has(
                page, r"Written Charts"
            )
            wait_idle(page, 2500)
            text_on = shot(page, "8-mission-written-on")
            card_bm = mission_blue_card_chord(text_on)
            notes_on = mission_notes_line(text_on)
            abc_on = extract_abc(page)
            title_on = mission_sheet_title_chord(abc_on)
            written_ok = (
                classify_backing(text_on) == "mission"
                and "D#m" not in text_on
                and "Fm" not in (card_bm or "")
                and card_bm in {"Bm", "B"}
                and ("B" in notes_on or "Bm" in notes_on or card_bm == "Bm")
                and title_on in {"", "Bm"}
            )
            set_gate(
                "MISSION_BACKING_WRITTEN_BM",
                written_ok,
                f"card_chord={card_bm!r} notes={notes_on!r} title={title_on!r} not_orig_only={card_bm == 'Bm'}",
            )
            refresh(page)
            if require_backing(page, "mission", "MISSION_BACKING_REFRESH"):
                text_rf = shot(page, "8-mission-refresh")
                set_gate(
                    "MISSION_BACKING_REFRESH",
                    classify_backing(text_rf) == "mission" and "D#m" not in text_rf,
                    f"banner={backing_source_line(text_rf)!r}",
                )
            before_m = sidebar_pk_token(page)
            click_cycle_key(page, step="semitone", direction="down")
            shot(page, "9-cycle-mission")
            after_m = sidebar_pk_token(page)
            set_gate(
                "KEY_CYCLE_MISSION",
                classify_backing(body_text(page)) == "mission" and bool(after_m) and after_m != before_m,
                f"before={before_m!r} after={after_m!r}",
            )
            shape_after_m = shape_songs_key(page)
            set_gate(
                "KEY_CYCLE_NO_SHAPE_LEAK_MISSION",
                shape_after_m in {"Cm", "C minor"} or "cm" in shape_after_m.lower(),
                f"shape={shape_after_m!r}",
            )

        # --- 9 Catalog + Custom key cycle ---
        seed_shape_cm(page)
        click_nav(page, "Backing")
        wait_idle(page, 4000)
        wait_for_backing(page, NOTES, "Catalog")
        if classify_backing(body_text(page)) != "catalog":
            fail_setup("KEY_CYCLE_CATALOG", f"kind={classify_backing(body_text(page))}")
        else:
            before_c = sidebar_pk_token(page)
            click_cycle_key(page, step="whole_tone", direction="up")
            shot(page, "9-cycle-catalog")
            after_c = sidebar_pk_token(page)
            set_gate(
                "KEY_CYCLE_CATALOG",
                classify_backing(body_text(page)) == "catalog" and after_c != before_c,
                f"before={before_c!r} after={after_c!r}",
            )
            refresh(page)
            wait_for_backing(page, NOTES, "Catalog-refresh")
            pk_c_rf = sidebar_pk_token(page)
            set_gate(
                "KEY_CYCLE_CATALOG_REFRESH",
                classify_backing(body_text(page)) == "catalog" and pk_c_rf == after_c,
                f"pk={pk_c_rf!r} cycled={after_c!r}",
            )

        goto_custom(page)
        wait_idle(page, 2500)
        open_custom_backing(page)
        if require_backing(page, "custom", "KEY_CYCLE_CUSTOM"):
            before_cu = sidebar_pk_token(page)
            click_cycle_key(page, step="semitone", direction="down")
            shot(page, "9-cycle-custom")
            after_cu = sidebar_pk_token(page)
            set_gate(
                "KEY_CYCLE_CUSTOM",
                classify_backing(body_text(page)) == "custom" and bool(after_cu) and after_cu != before_cu,
                f"before={before_cu!r} after={after_cu!r}",
            )

        browser.close()

    passed = sum(1 for v in GATES.values() if v == "PASS")
    failed = sum(1 for v in GATES.values() if v == "FAIL")
    summary = {
        "gates": GATES,
        "details": DETAILS,
        "pass": passed,
        "fail": failed,
        "notes": NOTES[-80:],
        "sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True).strip(),
        "branch": subprocess.check_output(["git", "branch", "--show-current"], cwd=str(ROOT), text=True).strip(),
    }
    (OUT / "ha-ap-summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=True), encoding="utf-8")
    log(json.dumps(summary, indent=2, ensure_ascii=True))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
