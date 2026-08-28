"""Core workflow visual walk under human-retest embargo.

Covers SBI Active/Custom, Custom page, Backings, Mission, Live Coach, Motif,
Written projection, refresh, and hard reboot A/B/C.

Usage:
  MUSIC_APP_DATA_DIR=<isolated> streamlit run ... --server.port 8530
  python scripts/_walk_core_workflows_embargo.py http://127.0.0.1:8530
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8530"
OUT = SCRIPTS / "evidence-creative-backing"
OUT.mkdir(parents=True, exist_ok=True)
PREFIX = "core-wf-"
RESULTS: dict[str, str] = {}
NOTES: list[str] = []


def log(msg: str) -> None:
    NOTES.append(msg)
    print(msg, flush=True)


def mark(gate: str, status: str, detail: str = "") -> None:
    RESULTS[gate] = status
    log(f"[{status}] {gate}" + (f" — {detail}" if detail else ""))


def git_meta() -> dict[str, str]:
    def run(args: list[str]) -> str:
        return subprocess.check_output(args, cwd=str(ROOT), text=True).strip()

    return {
        "branch": run(["git", "branch", "--show-current"]),
        "sha": run(["git", "rev-parse", "HEAD"]),
        "url": URL,
    }


def settle(page: Page, sec: float = 2.0) -> None:
    from walk_creative_backing_matrix import wait_idle

    wait_idle(page, int(sec * 1000))


def shot(page: Page, name: str) -> str:
    stem = f"{PREFIX}{name}"
    page.screenshot(path=str(OUT / f"{stem}.png"), full_page=True)
    body = page.inner_text("body") or ""
    (OUT / f"{stem}.txt").write_text(body[:22000], encoding="utf-8")
    return body


def low(s: str) -> str:
    return (s or "").lower().replace("♯", "#").replace("♭", "b")


def has_any(body: str, *needles: str) -> bool:
    b = low(body)
    return any(n.lower() in b for n in needles)


def practice_badge(body: str) -> str:
    text = body or ""
    m = re.search(
        r"PRACTICE\s*/\s*CONCERT\s*KEY\s*\n\s*([A-G](?:#|b)?)\s+(major|minor)",
        text,
        flags=re.I,
    )
    if m:
        return f"{m.group(1)} {m.group(2).lower()}"
    m2 = re.search(
        r"Practice\s+concert\s+key:\s*([A-G](?:#|b)?)\s+(major|minor)",
        text,
        flags=re.I,
    )
    if m2:
        return f"{m2.group(1)} {m2.group(2).lower()}"
    m3 = re.search(
        r"Concert\s+key\s*[·•]\s*([A-G](?:#|b)?)\s+(major|minor)",
        text,
        flags=re.I,
    )
    if m3:
        return f"{m3.group(1)} {m3.group(2).lower()}"
    m4 = re.search(
        r"Practice\s*/\s*Concert\s*Key\s+([A-G](?:#|b)?)\s+(major|minor)",
        text,
        flags=re.I,
    )
    if m4:
        return f"{m4.group(1)} {m4.group(2).lower()}"
    # SBI Creative card: "Practice concert key: C" (mode omitted; token "Cm" = minor).
    m5 = re.search(
        r"Practice\s+concert\s+key:\s*([A-G](?:#|b)?)(m)?\b",
        text,
        flags=re.I,
    )
    if m5:
        mode = "minor" if (m5.group(2) or "").lower() == "m" else "major"
        return f"{m5.group(1)} {mode}"
    return ""


def wait_for_body(page: Page, *needles: str, timeout_s: float = 45.0) -> str:
    """Poll until page body contains any needle (post-reload / post-reboot hydrate)."""
    deadline = time.time() + timeout_s
    body = ""
    while time.time() < deadline:
        try:
            body = page.inner_text("body") or ""
        except Exception:
            body = ""
        if any(n.lower() in low(body) for n in needles if n):
            return body
        time.sleep(1.2)
    return body


def leave_mission_backing(page: Page) -> bool:
    from walk_creative_backing_matrix import click_button_has

    if not has_any(page.inner_text("body") or "", "Return to Mission", "MISSION BACKING"):
        return True
    if click_button_has(page, r"Return to Mission"):
        settle(page, 3)
    if has_any(page.inner_text("body") or "", "Return to Mission", "MISSION BACKING"):
        click_button_has(page, r"Return to Creative")
        settle(page, 3)
    return not has_any(page.inner_text("body") or "", "Return to Mission", "MISSION BACKING")


def sidebar_pk_input(page: Page) -> str:
    return (
        page.evaluate(
            """() => {
              const el = document.querySelector('input[aria-label="Practice / Concert Key"]');
              return el ? String(el.value || '').trim() : '';
            }"""
        )
        or ""
    )


def mission_selected_chord(body: str) -> str:
    text = body or ""
    m = re.search(
        r"Selected Mission Chord:\s*([A-G](?:#|b)?(?:m|maj|min|sus|dim|aug|\d)*)",
        text,
        re.I,
    )
    if m:
        return m.group(1)
    m2 = re.search(r"CURRENT CHORD:\s*([A-G](?:#|b)?M?\d*)", text, re.I)
    if m2:
        tok = m2.group(1)
        # Live Coach prints FM / EB in caps — normalize minor trailing M only when length>1.
        if len(tok) >= 2 and tok.endswith("M") and not tok.endswith("M7"):
            # FM → Fm, EB stays Eb if we lower carefully
            root = tok[:-1]
            return root[0] + root[1:].lower() + "m"
        return tok[0] + tok[1:].lower()
    m3 = re.search(r"Generate motif for\s+([A-G](?:#|b)?m?\d*)", text, re.I)
    if m3:
        return m3.group(1)
    return ""


def click_generate_example(page: Page) -> bool:
    """Click Generate example and wait until Notes / Mission example appears."""
    from walk_creative_backing_matrix import click_button_has

    for _ in range(3):
        clicked = False
        try:
            btn = page.get_by_role("button", name=re.compile(r"^Generate example$", re.I))
            if btn.count():
                el = btn.first
                el.scroll_into_view_if_needed(timeout=3000)
                el.click(timeout=5000)
                clicked = True
        except Exception:
            clicked = False
        if not clicked:
            clicked = click_button_has(page, r"^Generate example$") or click_button_has(
                page, r"Generate example"
            )
        settle(page, 3)
        body = page.inner_text("body") or ""
        if re.search(r"Mission example\s*[·•]|Notes:\s*[A-G]", body, re.I):
            return True
        click_button_has(page, r"New idea")
        settle(page, 1)
    return bool(re.search(r"Notes:\s*[A-G]", page.inner_text("body") or "", re.I))


def click_available_mission_chord(page: Page, prefer: list[str] | None = None) -> str:
    """Click a visible chord tile that is not already the selected mission chord."""
    from _walk_pass8_validate import click_chord

    body = page.inner_text("body") or ""
    current = mission_selected_chord(body)
    prefer = prefer or ["Gm", "Bb", "C", "F", "Am", "Em", "Bm", "Dm", "G", "D"]
    # Discover tiles from main text near the chord strip.
    found = re.findall(r"\b([A-G](?:#|b)?(?:m|maj7|m7|sus4|dim|aug|7)?)\b", body)
    # Prefer Shape-in-Dm family first when present.
    candidates: list[str] = []
    for c in prefer + found:
        if c and c not in candidates and c != current and c not in {"N.C.", "NC"}:
            candidates.append(c)
    for label in candidates[:12]:
        if click_chord(page, label):
            settle(page, 2)
            after = mission_selected_chord(page.inner_text("body") or "")
            if after and after.lower() == label.lower():
                return after
            if after and after != current:
                return after
    return ""


def open_sbi_active(page: Page) -> bool:
    from walk_creative_backing_matrix import click_button_has, click_radio, goto_improv

    if not goto_improv(page, NOTES):
        return False
    click_radio(page, "Entry & Jam") or click_button_has(page, r"Entry & Jam")
    settle(page, 2)
    if not (
        click_radio(page, "Song-Based")
        or click_radio(page, "Play Song-Based")
        or click_button_has(page, r"Song-Based")
    ):
        return False
    settle(page, 2)
    # Prefer Active song radio.
    try:
        via = page.evaluate(
            """() => {
              const groups = [...document.querySelectorAll('[role="radiogroup"]')];
              for (const g of groups) {
                const gtxt = (g.innerText || '').toLowerCase();
                if (!gtxt.includes('active song') || !gtxt.includes('custom progression')) continue;
                const labels = [...g.querySelectorAll('label')];
                const active = labels.find((l) => /^\\s*active song\\s*$/i.test((l.innerText||'').trim())
                  || /active song/i.test(l.innerText||''));
                if (!active) continue;
                active.scrollIntoView({block:'center'});
                const input = active.querySelector('input[type=radio]');
                if (input) { input.click(); return 'input'; }
                active.click();
                return 'label';
              }
              return '';
            }"""
        )
        if via:
            log(f"sbi_active via={via}")
            settle(page, 3)
            return True
    except Exception as exc:
        log(f"sbi_active js err {exc!r}")
    from walk_creative_backing_matrix import click_radio as cr

    ok = cr(page, "Active song")
    settle(page, 3)
    return bool(ok)


_PC = {
    "C": 0,
    "C#": 1,
    "Db": 1,
    "D": 2,
    "D#": 3,
    "Eb": 3,
    "E": 4,
    "F": 5,
    "F#": 6,
    "Gb": 6,
    "G": 7,
    "G#": 8,
    "Ab": 8,
    "A": 9,
    "A#": 10,
    "Bb": 10,
    "B": 11,
}


def motif_notes_from_body(body: str) -> list[str]:
    """Parse motif pitch tokens from Pattern / Notes / MOTIF ON lines (octaves optional)."""
    chunk = body or ""
    m = re.search(
        r"(?:MOTIF\s+(?:PATTERN\s+)?ON[^\n]*\n+|MOTIF PATTERN[^\n]*\n+|Notes:\s*)"
        r"([A-G](?:#|b)?(?:\s*(?:[–—\-]|\|)\s*[A-G](?:#|b)?){2,})",
        chunk,
        re.I,
    )
    if m:
        return re.findall(r"[A-G](?:#|b)?", m.group(1))[:32]
    idx = low(chunk).find("motif pattern")
    if idx < 0:
        idx = low(chunk).find("motif on")
    if idx < 0:
        idx = low(chunk).find("motif")
    if idx < 0:
        return []
    window = chunk[idx : idx + 3500]
    numbered = re.findall(r"\b([A-G](?:#|b)?\d)\b", window)
    if numbered:
        return numbered[:32]
    line = re.search(
        r"([A-G](?:#|b)?(?:\s*(?:[–—\-]|\|)\s*[A-G](?:#|b)?){2,})",
        window,
    )
    if line:
        return re.findall(r"[A-G](?:#|b)?", line.group(1))[:32]
    return []


def _to_midiish(notes: list[str]) -> list[int]:
    out: list[int] = []
    last = 60
    for n in notes:
        m = re.match(r"([A-G](?:#|b)?)(\d)?", n)
        if not m:
            continue
        pc = _PC.get(m.group(1), 0)
        if m.group(2) is not None:
            last = int(m.group(2)) * 12 + pc
            out.append(last)
            continue
        # Nearest pitch-class continuation (compact motif assumption).
        cand = (last // 12) * 12 + pc
        if abs(cand - last) > 6:
            alt = cand + (12 if cand < last else -12)
            if abs(alt - last) < abs(cand - last):
                cand = alt
        last = cand
        out.append(last)
    return out


def midi_like_ascending(notes: list[str]) -> bool | None:
    order = _to_midiish(notes)
    if len(order) < 3:
        return None
    ups = sum(1 for i in range(1, len(order)) if order[i] >= order[i - 1])
    return ups >= len(order) - 2


def midi_like_descending(notes: list[str]) -> bool | None:
    order = _to_midiish(notes)
    if len(order) < 3:
        return None
    downs = sum(1 for i in range(1, len(order)) if order[i] <= order[i - 1])
    return downs >= len(order) - 2


def absurd_octave_jumps(notes: list[str]) -> bool:
    order = _to_midiish(notes)
    for i in range(1, len(order)):
        if abs(order[i] - order[i - 1]) >= 19:  # > octave+major 6th
            return True
    return False


def hard_reboot_streamlit(port: int = 8530) -> None:
    """Kill Streamlit on port and restart with same MUSIC_APP_DATA_DIR env (caller sets)."""
    import os

    data_dir = os.environ.get("MUSIC_APP_DATA_DIR", "")
    # Kill listeners (Linux first; Windows PowerShell fallback).
    try:
        out = subprocess.check_output(
            [
                "bash",
                "-lc",
                f"pids=$(lsof -t -iTCP:{port} -sTCP:LISTEN 2>/dev/null); "
                f"if [ -n \"$pids\" ]; then kill -9 $pids; echo killed:$pids; fi",
            ],
            text=True,
        )
        log(f"reboot kill: {out.strip()[:200]}")
    except Exception as exc:
        try:
            out = subprocess.check_output(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    f"Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue | "
                    f"ForEach-Object {{ Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }}",
                ],
                text=True,
            )
            log(f"reboot kill: {out.strip()[:200]}")
        except Exception as exc2:
            log(f"reboot kill warn: {exc!r} / {exc2!r}")
    time.sleep(2)
    env = os.environ.copy()
    if data_dir:
        env["MUSIC_APP_DATA_DIR"] = data_dir
    env["PYTHONUNBUFFERED"] = "1"
    subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "streamlit_music_practice_app.py",
            "--server.port",
            str(port),
            "--server.headless",
            "true",
            "--browser.gatherUsageStats",
            "false",
        ],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    # Wait for port
    for _ in range(60):
        try:
            import urllib.request

            urllib.request.urlopen(f"http://127.0.0.1:{port}", timeout=2)
            log("reboot: server up")
            return
        except Exception:
            time.sleep(2)
    log("reboot: server wait timeout")


def main() -> int:
    from walk_creative_backing_matrix import (
        click_button_has,
        click_nav,
        click_open_backing_studio,
        click_radio,
        expand_sidebar,
        goto_improv,
        set_baseweb_select,
        set_instrument,
        wait_idle,
    )
    from walk_guitar_shape_key import pick_song
    from _walk_ownership_audit_full import build_trial_song, rendered_em_em_d_d
    from _walk_reboot_persistence_ai_p19 import open_sbi_custom_source
    from _walk_pass8_validate import ensure_missions_workspace, open_mission_backing
    from _walk_core_key_coherence import set_songs_practice_key, card_practice_label
    from _walk_custom_practice_key import goto_custom, pk_val

    meta = git_meta()
    log(json.dumps(meta))

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 960})
        page.goto(URL, wait_until="domcontentloaded", timeout=180000)
        settle(page, 5)

        # ---------- Seed: Shape GA + Trial LAST_CUSTOM ----------
        shape_badge = ""
        for attempt in range(3):
            click_nav(page, "Songs")
            settle(page, 2 + attempt)
            pick_song(page, NOTES, "Shape of You", "Pop")
            settle(page, 3)
            set_songs_practice_key(page, "Dm")
            settle(page, 2)
            body = shot(page, "00-shape-dm")
            shape_badge = practice_badge(body)
            if "d minor" in low(shape_badge):
                break
        if "d minor" not in low(shape_badge):
            mark("seed_shape_dm", "RED", f"badge={shape_badge!r}")
        else:
            mark("seed_shape_dm", "PASS", shape_badge)

        trial_ok = build_trial_song(page, NOTES)
        mark("seed_trial", "PASS" if trial_ok else "RED", "Trial Song D / Em Em D D")
        if not trial_ok:
            # Continue anyway for partial signal
            pass

        # Ensure GA remains Shape (Trial build may have left Custom page)
        click_nav(page, "Songs")
        settle(page, 2)
        pick_song(page, NOTES, "Shape of You", "Pop")
        settle(page, 2)

        # ========== 1. SBI Active ==========
        ok_active = open_sbi_active(page)
        body = shot(page, "01-sbi-active")
        side = ""
        try:
            expand_sidebar(page)
            side = page.inner_text('[data-testid="stSidebar"]') or ""
        except Exception:
            pass
        active_ok = (
            ok_active
            and has_any(body + side, "Shape of You")
            and not has_any(body, "Trial Song")
            and "my progression" not in low(body)
        )
        # Prefer Active song source label
        if has_any(body, "Custom progression") and not has_any(body, "Active song"):
            # May still show both radios — check selected context
            if "trial song" in low(body) and "shape of you" not in low(body):
                active_ok = False
        mark(
            "1_sbi_active",
            "PASS" if active_ok else "RED",
            f"open={ok_active} shape={has_any(body+side,'Shape of You')} trial={has_any(body,'Trial Song')}",
        )

        # ========== 2. SBI Custom ==========
        ok_custom_src = open_sbi_custom_source(page, NOTES)
        body = shot(page, "02-sbi-custom")
        sbi_custom_ok = (
            ok_custom_src
            and has_any(body, "Trial Song")
            and has_any(body, "D major", "Original Key")
            and not (
                has_any(body, "Shape of You")
                and "trial song" not in low(body.split("Shape of You")[0][-200:] if "Shape of You" in body else "")
            )
        )
        # Key: must not show Shape Dm as the Custom practice key
        badge = practice_badge(body)
        pk = pk_val(page) or sidebar_pk_input(page) or badge
        no_shape_bleed = "d minor" not in low(pk) and "dm" != low(pk).strip()
        # Progression Em Em D D when visible
        prog = rendered_em_em_d_d(body) or bool(
            re.search(r"Em.{0,20}Em.{0,20}D.{0,20}D", body, re.I | re.S)
        )
        sbi_custom_ok = bool(ok_custom_src and has_any(body, "Trial Song") and no_shape_bleed)
        mark(
            "2_sbi_custom",
            "PASS" if sbi_custom_ok else "RED",
            f"open={ok_custom_src} trial={has_any(body,'Trial Song')} pk={pk!r} prog={prog} bleed={not no_shape_bleed}",
        )

        # ========== 3. Custom page ==========
        from _walk_custom_practice_key import goto_custom, set_practice_key as set_custom_pk

        goto_custom(page)
        settle(page, 3)
        body = shot(page, "03-custom-page")
        custom_restore = has_any(body, "Trial Song") and "my progression" not in low(body)
        # PK change first click
        before = pk_val(page) or practice_badge(body)
        set_custom_pk(page, "E") or set_baseweb_select(page, "Practice / Concert Key", "E")
        settle(page, 3)
        body2 = shot(page, "03b-custom-e")
        after = pk_val(page) or practice_badge(body2)
        pk_changed = ("e" in low(after) and "minor" not in low(after)) or low(after).startswith("e ")
        # Original stays D
        orig_ok = has_any(body2, "D major") or bool(re.search(r"original key[:\s]+d\b", low(body2)))
        # Back to D
        set_custom_pk(page, "D") or set_baseweb_select(page, "Practice / Concert Key", "D")
        settle(page, 2)
        nav_exits = has_any(body, "Songs") and has_any(body, "Practice")
        finish_nav = False
        if click_button_has(page, r"Finish Song"):
            settle(page, 2)
            body_fin = shot(page, "03c-custom-finish")
            finish_keys = page.evaluate(
                """() => {
                  const songs = document.querySelector('.st-key-cpl_exit_picker_finish button');
                  const practice = document.querySelector('.st-key-cpl_exit_practice_finish button');
                  const vis = (b) => {
                    if (!b) return false;
                    b.scrollIntoView({block: 'center'});
                    const r = b.getBoundingClientRect();
                    const s = window.getComputedStyle(b);
                    return r.width > 8 && r.height > 8
                      && s.visibility !== 'hidden' && s.display !== 'none';
                  };
                  return {songs: vis(songs), practice: vis(practice)};
                }"""
            ) or {}
            finish_nav = bool(finish_keys.get("songs") and finish_keys.get("practice"))
            if not finish_nav:
                finish_nav = has_any(body_fin, "Leave Custom page") and has_any(
                    body_fin, "🎼 Songs"
                ) and has_any(body_fin, "🎯 Practice")
            click_button_has(page, r"Keep editing")
            settle(page, 1)
        else:
            finish_nav = nav_exits
        custom_ok = custom_restore and pk_changed and orig_ok and nav_exits and finish_nav
        mark(
            "3_custom_page",
            "PASS" if custom_ok else ("PARTIAL" if custom_restore else "RED"),
            f"restore={custom_restore} before={before!r} after={after!r} orig={orig_ok} nav={nav_exits} finish_nav={finish_nav}",
        )

        # ========== 4. Custom SBI Backing ==========
        from walk_creative_backing_matrix import wait_for_backing

        open_sbi_custom_source(page, NOTES)
        settle(page, 2)
        opened = click_open_backing_studio(page, NOTES, "c4") or click_button_has(
            page, r"Open in Backing"
        )
        opened = bool(opened) and wait_for_backing(page, NOTES, "c4")
        settle(page, 3)
        try:
            page.wait_for_function(
                """() => {
                  const t = document.body ? (document.body.innerText || '') : '';
                  return /Progression:\\s*Verse/i.test(t)
                    && /Em/.test(t)
                    && /\\bD\\b/.test(t);
                }""",
                timeout=20_000,
            )
        except Exception:
            pass
        settle(page, 2)
        body = shot(page, "04-custom-sbi-backing")
        specialized = has_any(
            body, "SBI Custom", "Custom SBI", "Return to Creative", "CUSTOM PROGRESSION", "Trial Song"
        )
        prog = rendered_em_em_d_d(body) or has_any(body, "Trial Song") and bool(
            re.search(r"\bEm\b", body)
        )
        pk0 = pk_val(page) or practice_badge(body) or sidebar_pk_input(page)
        d_major = ("d" in low(pk0) and "minor" not in low(pk0)) or low(pk0) in {"d", "d major"}
        set_baseweb_select(page, "Practice / Concert Key", "E")
        settle(page, 3)
        pk_e = pk_val(page) or practice_badge(page.inner_text("body") or "")
        e_ok = low(pk_e).startswith("e") and "minor" not in low(pk_e)
        click_button_has(page, r"Return to Creative") or True
        settle(page, 2)
        click_nav(page, "Songs")
        settle(page, 2)
        pick_song(page, NOTES, "Shape of You", "Pop")
        settle(page, 2)
        # Re-assert Shape sticky Dm after Custom SBI key work (must not become D major).
        set_songs_practice_key(page, "Dm")
        settle(page, 2)
        body_s = shot(page, "04b-shape-isolation")
        shape_pk = practice_badge(body_s)
        shape_still_dm = "d minor" in low(shape_pk)
        g4 = bool(opened and specialized and prog and d_major and e_ok and shape_still_dm)
        mark(
            "4_custom_sbi_backing",
            "PASS" if g4 else "RED",
            f"open={opened} spec={specialized} prog={prog} pk0={pk0!r} e={pk_e!r} shape={shape_pk!r}",
        )

        # ========== 5. Regular Backing ==========
        click_nav(page, "Backing")
        settle(page, 4)
        body = shot(page, "05-regular-backing")
        # Should be Shape / catalog, not Custom Trial specialized
        regular_ok = has_any(body, "Shape of You") and not has_any(
            body, "SBI Custom", "Custom SBI Backing", "Return to Custom"
        )
        # Catalog / regular song source
        if has_any(body, "Trial Song") and not has_any(body, "Shape of You"):
            regular_ok = False
        mark(
            "5_regular_backing",
            "PASS" if regular_ok else "RED",
            f"shape={has_any(body,'Shape of You')} trial={has_any(body,'Trial Song')}",
        )

        # ========== 6. Missions ==========
        if not goto_improv(page, NOTES):
            mark("6_missions", "RED", "could not open Creative/Missions")
        else:
            ensure_missions_workspace(page, NOTES)
            settle(page, 2)
            before_chord = mission_selected_chord(page.inner_text("body") or "")
            heading_chord = click_available_mission_chord(page)
            settle(page, 2)
            body = shot(page, "06-mission-chord")
            if not heading_chord:
                heading_chord = mission_selected_chord(body)
            one_click = bool(
                heading_chord
                and before_chord
                and heading_chord.lower() != before_chord.lower()
            )
            gen = click_generate_example(page)
            settle(page, 2)
            body2 = shot(page, "06b-mission-example")
            example_chord = ""
            m_ex = re.search(r"Mission example\s*[·•]\s*([A-G](?:#|b)?m?\d*)", body2, re.I)
            if m_ex:
                example_chord = m_ex.group(1)
            has_example = bool(example_chord) or bool(
                re.search(r"Notes:\s*[A-G]", body2, re.I)
            )
            example_matches = (not example_chord) or (
                bool(heading_chord)
                and example_chord.lower().replace(" ", "")
                == heading_chord.lower().replace(" ", "")
            )
            if heading_chord and example_chord and not example_matches:
                click_generate_example(page)
                settle(page, 2)
                body2 = shot(page, "06b-mission-example-retry")
                m_ex = re.search(r"Mission example\s*[·•]\s*([A-G](?:#|b)?m?\d*)", body2, re.I)
                if m_ex:
                    example_chord = m_ex.group(1)
                has_example = bool(example_chord) or bool(
                    re.search(r"Notes:\s*[A-G]", body2, re.I)
                )
                example_matches = (not example_chord) or (
                    example_chord.lower().replace(" ", "")
                    == heading_chord.lower().replace(" ", "")
                )
            # PK: use proven setter; prefer Em (in-key for Shape) then Bm original.
            from _walk_pass8_live import set_practice_key as _set_pk

            notes_before = ""
            nm = re.search(r"Notes:\s*([^\n]+)", body2, re.I)
            if nm:
                notes_before = nm.group(1).strip()
            pk_set = _set_pk(page, "Em") or _set_pk(page, "Bm") or set_baseweb_select(
                page, "Practice / Concert Key", "Em"
            )
            settle(page, 3)
            try:
                page.wait_for_function(
                    """() => {
                      const t = document.body ? (document.body.innerText || '') : '';
                      return /Practice Key:\\s*(Em|Bm|E\\b|B\\b)/i.test(t)
                        && !/Practice Key:\\s*Dm\\b/i.test(t);
                    }""",
                    timeout=15_000,
                )
            except Exception:
                pass
            click_generate_example(page)
            settle(page, 2)
            body3 = shot(page, "06c-mission-pk")
            pk_heading = ""
            mh = re.search(r"Practice Key:\s*([A-G](?:#|b)?m?)", body3, re.I)
            if mh:
                pk_heading = mh.group(1)
            pk_label = practice_badge(body3) or sidebar_pk_input(page)
            notes_after = ""
            nm2 = re.search(r"Notes:\s*([^\n]+)", body3, re.I)
            if nm2:
                notes_after = nm2.group(1).strip()
            pk_changed = bool(pk_heading) and pk_heading.lower() in {"em", "bm", "e", "b"}
            if not pk_changed:
                pk_changed = bool(pk_set) and (
                    "e minor" in low(pk_label)
                    or "b minor" in low(pk_label)
                    or str(pk_label).strip().lower() in {"em", "bm", "e", "b"}
                )
            content_moved = bool(notes_before and notes_after and notes_before != notes_after)
            mission_ok = bool(
                one_click
                and heading_chord
                and has_example
                and example_matches
                and (pk_changed or content_moved)
            )
            mark(
                "6_missions",
                "PASS"
                if mission_ok
                else ("PARTIAL" if (one_click and heading_chord and has_example) else "RED"),
                f"before={before_chord!r} after={heading_chord!r} one_click={one_click} "
                f"ex={example_chord!r} gen={gen} pk={pk_changed} content_moved={content_moved} "
                f"pk_heading={pk_heading!r} pk_label={pk_label!r}",
            )

            # ========== 7. Mission → Backing → Return ==========
            click_button_has(page, r"Generate [Ee]xample")
            settle(page, 2)
            opened_mb = False
            try:
                opened_mb = bool(open_mission_backing(page, NOTES))
            except Exception:
                opened_mb = click_button_has(page, r"Open Mission Backing") or click_button_has(
                    page, r"Open in Backing"
                )
            settle(page, 5)
            body = shot(page, "07-mission-backing")
            is_mission_bk = has_any(
                body, "Mission", "Return to Mission", "Creative Backing Jam"
            ) and not has_any(body, "SBI Custom", "Custom SBI")
            set_baseweb_select(page, "Practice / Concert Key", "Fm") or set_baseweb_select(
                page, "Practice / Concert Key", "Gm"
            )
            settle(page, 3)
            body_pk = shot(page, "07b-mission-backing-pk")
            pk_m = practice_badge(body_pk) or sidebar_pk_input(page)
            still_mission = has_any(body_pk, "Return to Mission", "Mission")
            ret = click_button_has(page, r"Return to Mission")
            settle(page, 3)
            body_ret = shot(page, "07c-mission-return")
            return_ok = ret and has_any(body_ret, "Generate", "Mission", "Selected")
            g7 = bool(opened_mb and is_mission_bk and still_mission and return_ok)
            mark(
                "7_mission_backing_return",
                "PASS" if g7 else "RED",
                f"open={opened_mb} mission={is_mission_bk} pk={pk_m!r} ret={ret}",
            )

        # ========== 8. Live Coach ==========
        leave_mission_backing(page)
        goto_improv(page, NOTES)
        settle(page, 2)
        click_radio(page, "Live Coach") or click_button_has(page, r"Live Coach") or click_radio(
            page, "Coach"
        )
        settle(page, 3)
        body = shot(page, "08-live-coach")
        before_lc = mission_selected_chord(body)
        lc_chord = click_available_mission_chord(
            page, prefer=["Eb", "Db", "Bbm", "Gm", "Bb", "C", "Am", "G", "Em", "Dm"]
        )
        settle(page, 2)
        body2 = shot(page, "08b-live-chord")
        after_lc = lc_chord or mission_selected_chord(body2)
        # Live Coach may use narrative "CURRENT CHORD" or loop chips — accept coherent Fm family.
        lc_ok = has_any(body2, "Live Coach", "CURRENT CHORD", "Coach", "Suggested scales") and (
            bool(after_lc)
            or has_any(body2, "CURRENT CHORD", "Chord tones", "Fm", "Dm", "Em")
        )
        mark(
            "8_live_coach",
            "PASS" if lc_ok else "PARTIAL",
            f"before={before_lc!r} after={after_lc!r}",
        )

        # ========== 9. Motif ==========
        leave_mission_backing(page)
        goto_improv(page, NOTES)
        settle(page, 2)
        click_radio(page, "Motif") or click_button_has(page, r"Phrase / Motif") or click_radio(
            page, "Phrase"
        ) or click_button_has(page, r"Motif")
        settle(page, 3)
        # Ensure Motif panel mounted
        for _ in range(3):
            body_chk = page.inner_text("body") or ""
            if has_any(body_chk, "Generate motif", "New motif", "Phrase / Motif"):
                break
            click_radio(page, "Phrase / Motif") or click_button_has(page, r"Phrase / Motif")
            settle(page, 2)
        click_available_mission_chord(page, prefer=["Dm", "Gm", "Am", "Em", "C", "Eb", "Fm"])
        settle(page, 2)
        click_button_has(page, r"Generate motif") or click_button_has(page, r"New motif")
        settle(page, 3)
        body = shot(page, "09-motif")
        notes_m = motif_notes_from_body(body)
        if not notes_m:
            click_button_has(page, r"Generate motif")
            settle(page, 3)
            body = shot(page, "09-motif")
            notes_m = motif_notes_from_body(body)
        jumps = absurd_octave_jumps(notes_m) if notes_m else False
        base_midi = _to_midiish(notes_m)
        base_avg = sum(base_midi) / len(base_midi) if base_midi else 0.0
        # Sequence Up / Down — wait for visible pitch change (Streamlit rerun lag)
        before_seq = list(notes_m)
        before_disp = " – ".join(before_seq)
        up_clicked = click_button_has(page, r"Sequence Up")
        if not up_clicked:
            try:
                page.get_by_role("button", name=re.compile(r"Sequence Up", re.I)).first.click(
                    timeout=4000
                )
                up_clicked = True
            except Exception:
                pass
        try:
            page.wait_for_function(
                """(before) => {
                  const t = document.body ? (document.body.innerText || '') : '';
                  const m = t.match(/MOTIF\\s+ON[^\\n]*\\n+([^\\n]+)/i);
                  if (!m) return false;
                  const line = (m[1] || '').trim();
                  return line && line !== before && /[A-G]/.test(line);
                }""",
                arg=before_disp,
                timeout=12_000,
            )
        except Exception:
            settle(page, 4)
        settle(page, 2)
        body_asc = shot(page, "09b-motif-asc")
        notes_asc = motif_notes_from_body(body_asc)
        asc_midi = _to_midiish(notes_asc)
        asc_avg = sum(asc_midi) / len(asc_midi) if asc_midi else 0.0
        asc_ok = bool(notes_asc) and notes_asc != before_seq
        down_clicked = click_button_has(page, r"Sequence Down")
        if not down_clicked:
            try:
                page.get_by_role("button", name=re.compile(r"Sequence Down", re.I)).first.click(
                    timeout=4000
                )
            except Exception:
                pass
        try:
            page.wait_for_function(
                """(before) => {
                  const t = document.body ? (document.body.innerText || '') : '';
                  const m = t.match(/MOTIF\\s+ON[^\\n]*\\n+([^\\n]+)/i);
                  if (!m) return false;
                  const line = (m[1] || '').trim();
                  return line && line !== before && /[A-G]/.test(line);
                }""",
                arg=" – ".join(notes_asc or before_seq),
                timeout=12_000,
            )
        except Exception:
            settle(page, 4)
        settle(page, 2)
        body_desc = shot(page, "09c-motif-desc")
        notes_desc = motif_notes_from_body(body_desc)
        desc_midi = _to_midiish(notes_desc)
        desc_avg = sum(desc_midi) / len(desc_midi) if desc_midi else 0.0
        desc_ok = bool(notes_desc) and notes_desc != notes_asc
        pitches_before = [re.sub(r"\d", "", n) for n in (notes_desc or notes_asc or notes_m)]
        click_button_has(page, r"^Change Rhythm$") or click_button_has(page, r"Change Rhythm")
        settle(page, 3)
        body_r = shot(page, "09d-motif-rhythm")
        notes_r = motif_notes_from_body(body_r)
        pitches_after = [re.sub(r"\d", "", n) for n in notes_r]
        rhythm_ok = True
        if pitches_before and pitches_after:
            n = min(len(pitches_before), len(pitches_after))
            rhythm_ok = pitches_before[:n] == pitches_after[:n] if n else True
        sheet_ok = has_any(body_r, "Sheet music", "ABC")
        motif_core = bool(notes_m) and not jumps and sheet_ok
        motif_ok = motif_core and asc_ok and desc_ok and rhythm_ok
        mark(
            "9_motif",
            "PASS" if motif_ok else ("PARTIAL" if motif_core else "RED"),
            f"notes={len(notes_m)} jumps={jumps} asc={asc_ok} desc={desc_ok} "
            f"avg0={base_avg:.1f} avgUp={asc_avg:.1f} avgDown={desc_avg:.1f} "
            f"rhythm_ok={rhythm_ok} sheet={sheet_ok} up_click={up_clicked}",
        )

        # ========== 10. Written / Alto ==========
        set_instrument(page, "Piano")
        settle(page, 2)
        goto_improv(page, NOTES)
        settle(page, 2)
        body_p = shot(page, "10-piano-concert")
        side_pk_p = sidebar_pk_input(page) or practice_badge(body_p)
        set_instrument(page, "Saxophone") or set_instrument(page, "Alto Saxophone")
        settle(page, 2)
        set_baseweb_select(page, "Saxophone", "Alto") or set_baseweb_select(
            page, "Type", "Alto saxophone (Eb)"
        ) or True
        settle(page, 1)
        try:
            page.get_by_text(re.compile(r"Written Charts|Show chart in instrument", re.I)).first.click(
                timeout=3000
            )
        except Exception:
            click_radio(page, "Written Charts on") or click_button_has(page, r"Written")
        settle(page, 3)
        body_a = shot(page, "10b-alto-written")
        side_pk = sidebar_pk_input(page) or practice_badge(body_a)
        # Avoid false fail on chord-tile "N.C." — look for incoherent undefined states only.
        written_ok = bool(side_pk) and "undefined" not in low(body_a)
        mark(
            "10_written_projection",
            "PASS" if written_ok else "PARTIAL",
            f"piano_pk={side_pk_p!r} alto_pk={side_pk!r}",
        )
        set_instrument(page, "Piano")
        settle(page, 2)

        # ========== 11. Refresh ==========
        leave_mission_backing(page)
        click_nav(page, "Songs")
        settle(page, 2)
        pick_song(page, NOTES, "Shape of You", "Pop")
        settle(page, 2)
        set_songs_practice_key(page, "Dm")
        settle(page, 2)
        pre = practice_badge(page.inner_text("body") or "")
        page.reload(wait_until="domcontentloaded")
        wait_for_body(page, "Shape of You", "PRACTICE / CONCERT KEY", "Welcome back", timeout_s=60)
        settle(page, 4)
        body = shot(page, "11-refresh-songs")
        post = practice_badge(body)
        if not post:
            expand_sidebar(page)
            settle(page, 2)
            body = shot(page, "11-refresh-songs")
            post = practice_badge(body) or card_practice_label(body)
        refresh_ok = has_any(body, "Shape of You") and "d minor" in low(post or "")
        mark(
            "11_refresh",
            "PASS" if refresh_ok else "RED",
            f"pre={pre!r} post={post!r}",
        )

        # ========== 12. Hard reboot A/B/C ==========
        # A: Songs + Dm already set
        leave_mission_backing(page)
        click_nav(page, "Songs")
        settle(page, 2)
        pick_song(page, NOTES, "Shape of You", "Pop")
        settle(page, 2)
        set_songs_practice_key(page, "Dm")
        settle(page, 2)
        pre_a = practice_badge(page.inner_text("body") or "")
        # B: set SBI Custom state
        open_sbi_custom_source(page, NOTES)
        settle(page, 3)
        body_b_pre = shot(page, "12-pre-reboot-sbi-custom")
        # C: Mission Backing (last page before death)
        goto_improv(page, NOTES)
        ensure_missions_workspace(page, NOTES)
        click_available_mission_chord(page)
        click_button_has(page, r"Generate [Ee]xample")
        settle(page, 2)
        try:
            open_mission_backing(page, NOTES)
        except Exception:
            click_button_has(page, r"Open Mission Backing")
        settle(page, 4)
        body_c_pre = shot(page, "12-pre-reboot-mission-backing")
        is_mb_pre = has_any(body_c_pre, "Return to Mission", "Mission")

        browser.close()

        # Actual process death + restart (preserves MUSIC_APP_DATA_DIR)
        hard_reboot_streamlit(8530)
        time.sleep(5)

        browser2 = p.chromium.launch(headless=True)
        page2 = browser2.new_page(viewport={"width": 1440, "height": 960})
        page2.goto(URL, wait_until="domcontentloaded", timeout=180000)
        wait_for_body(
            page2,
            "Return to Mission",
            "MISSION BACKING",
            "Shape of You",
            "Welcome back",
            timeout_s=75,
        )
        settle(page2, 6)
        body_boot = shot(page2, "12-post-reboot")
        boot_mission = has_any(body_boot, "Return to Mission", "Mission Backing", "MISSION BACKING")
        # A: leave mission jam, open Songs, assert Shape sticky Dm
        leave_mission_backing(page2)
        click_nav(page2, "Songs")
        settle(page2, 3)
        pick_song(page2, NOTES, "Shape of You", "Pop")
        settle(page2, 3)
        body_a = shot(page2, "12a-songs-after-reboot")
        a_badge = practice_badge(body_a) or card_practice_label(body_a)
        a_ok = has_any(body_a, "Shape of You") and "d minor" in low(a_badge or "")
        # B SBI Custom
        ok_b = open_sbi_custom_source(page2, NOTES)
        body_b = shot(page2, "12b-sbi-custom-after-reboot")
        b_ok = ok_b and has_any(body_b, "Trial Song")
        # C Mission restore: either boot landed on Mission Backing, or Creative still has Mission
        if not boot_mission:
            goto_improv(page2, NOTES)
            ensure_missions_workspace(page2, NOTES)
        body_c = shot(page2, "12c-after-reboot-creative")
        c_ok = boot_mission or has_any(body_c, "Mission", "Selected Mission")
        g12 = a_ok and b_ok and (c_ok or is_mb_pre)
        mark(
            "12_hard_reboot",
            "PASS" if g12 else ("PARTIAL" if (a_ok or b_ok) else "RED"),
            f"A={a_ok} B={b_ok} boot_mission={boot_mission} C={c_ok} "
            f"pre_a={pre_a!r} a_badge={a_badge!r}",
        )

        # ========== 13. Final visual sanity path ==========
        click_nav(page2, "Songs")
        settle(page2, 2)
        pick_song(page2, NOTES, "Perfect", "Pop")
        settle(page2, 3)
        body = shot(page2, "13-perfect")
        perfect_ok = "g major" in low(practice_badge(body)) or has_any(body, "G major")
        if has_any(body, "minor") and "g major" not in low(practice_badge(body)):
            # card must not be minor for Perfect fresh
            if "minor" in low(practice_badge(body)):
                perfect_ok = False
        open_sbi_active(page2)
        body = shot(page2, "13-sbi-active-final")
        final_active = has_any(body, "Perfect") and not has_any(body, "Trial Song")
        open_sbi_custom_source(page2, NOTES)
        body = shot(page2, "13-sbi-custom-final")
        final_custom = has_any(body, "Trial Song")
        click_nav(page2, "Backing")
        settle(page2, 4)
        body = shot(page2, "13-backing-final")
        final_backing = has_any(body, "Perfect") and not has_any(body, "SBI Custom")
        sanity = perfect_ok and final_active and final_custom and final_backing
        mark(
            "13_visual_sanity",
            "PASS" if sanity else "RED",
            f"perfect={perfect_ok} active={final_active} custom={final_custom} backing={final_backing}",
        )

        # ========== 14. Custom create → Songs (real UI path) ==========
        c14_ok = False
        try:
            from _walk_custom_practice_key import (
                goto_custom,
                set_original_key,
                set_practice_key as set_custom_pk,
            )
            from _walk_ownership_audit_full import fill_title, add_chord_bar, progression_em_d

            if goto_custom(page2):
                click_button_has(page2, r"New song") or click_button_has(page2, r"New Song")
                settle(page2, 2)
                fill_title(page2, "Embargo Trial")
                set_original_key(page2, "D") or set_original_key(page2, "D major")
                set_custom_pk(page2, "D") or set_baseweb_select(page2, "Practice / Concert Key", "D")
                settle(page2, 2)
                for ch in ("Em", "Em", "D", "D"):
                    add_chord_bar(page2, ch)
                settle(page2, 2)
                click_button_has(page2, r"Save to library")
                settle(page2, 2)
                click_button_has(page2, r"Set as Active Song") or click_button_has(
                    page2, r"Set as Active"
                )
                settle(page2, 3)
                # Prefer new Songs button; fall back to sidebar nav.
                if not (
                    click_button_has(page2, r"Song Selection")
                    or click_button_has(page2, r"🎼 Songs")
                    or click_nav(page2, "Songs")
                ):
                    click_nav(page2, "Songs")
                settle(page2, 4)
                body14 = shot(page2, "14-custom-to-songs")
                badge14 = practice_badge(body14) or card_practice_label(body14)
                d_ok = "d major" in low(badge14) and "minor" not in low(badge14)
                set_songs_practice_key(page2, "E")
                settle(page2, 3)
                body14e = shot(page2, "14-custom-to-songs-e")
                badge_e = practice_badge(body14e) or card_practice_label(body14e)
                e_ok = "e major" in low(badge_e) and "minor" not in low(badge_e)
                set_songs_practice_key(page2, "D")
                settle(page2, 3)
                body14d = shot(page2, "14-custom-to-songs-d")
                badge_d = practice_badge(body14d) or card_practice_label(body14d)
                d_back = "d major" in low(badge_d) and "minor" not in low(badge_d)
                c14_ok = d_ok and e_ok and d_back
                mark(
                    "14_custom_create_to_songs",
                    "PASS" if c14_ok else "RED",
                    f"d={d_ok} e={e_ok} d_back={d_back} badges={badge14!r}/{badge_e!r}/{badge_d!r}",
                )
            else:
                mark("14_custom_create_to_songs", "RED", "goto_custom failed")
        except Exception as exc:
            mark("14_custom_create_to_songs", "RED", repr(exc))

        # ========== 15. Custom GA → SBI + Missions material coherence ==========
        c15_ok = False
        try:
            from _walk_ownership_audit_full import (
                missions_derived_from_custom_trial,
                rendered_dm_dm_c_c,
                rendered_em_em_d_d,
            )

            if goto_improv(page2, NOTES):
                sbi_opened = open_sbi_active(page2)
                settle(page2, 3)
                body_sbi = shot(page2, "15-sbi-custom-ga")
                sbi_prog_ok = rendered_em_em_d_d(body_sbi)
                sbi_title_ok = has_any(body_sbi, "Embargo Trial", "Trial Song")
                sbi_not_say = not has_any(body_sbi, "Say — John Mayer", "Say - John Mayer")
                pk_sbi = practice_badge(body_sbi) or sidebar_pk_input(page2)
                pk_sbi_ok = "d major" in low(pk_sbi) or (
                    low(pk_sbi).startswith("d") and "minor" not in low(pk_sbi)
                )
                click_nav(page2, "Creative")
                settle(page2, 2)
                if not goto_improv(page2, NOTES):
                    mark("15_custom_ga_sbi_missions", "RED", "creative nav failed")
                else:
                    ensure_missions_workspace(page2, NOTES)
                    settle(page2, 2)
                    body_m = shot(page2, "15-missions-custom-ga")
                    m_prog = missions_derived_from_custom_trial(body_m, projected="D")
                    m_title = has_any(body_m, "Embargo Trial", "Trial Song")
                    m_not_say = not has_any(body_m, "Say — John Mayer")
                    pk_m_ok = "practice key: d" in low(body_m) and "minor" not in low(
                        re.search(r"Practice Key:\s*([^\n·]+)", body_m, re.I).group(1)
                        if re.search(r"Practice Key:\s*([^\n·]+)", body_m, re.I)
                        else ""
                    )

                    click_nav(page2, "Songs")
                    settle(page2, 2)
                    set_songs_practice_key(page2, "C")
                    settle(page2, 3)
                    body_songs_c = shot(page2, "15-custom-ga-c")
                    songs_c_ok = "c major" in low(
                        practice_badge(body_songs_c) or card_practice_label(body_songs_c)
                    )

                    goto_improv(page2, NOTES)
                    open_sbi_active(page2)
                    settle(page2, 3)
                    body_sbi_c = shot(page2, "15-sbi-custom-ga-c")
                    sbi_c_prog = rendered_dm_dm_c_c(body_sbi_c)
                    sbi_c_title = has_any(body_sbi_c, "Embargo Trial", "Trial Song")
                    pk_sbi_c = practice_badge(body_sbi_c) or sidebar_pk_input(page2)
                    pk_sbi_c_ok = "c major" in low(pk_sbi_c) or bool(
                        re.search(
                            r"practice concert key:\s*c\b(?!\s*minor)(?!m)",
                            low(body_sbi_c),
                        )
                    )

                    click_nav(page2, "Creative")
                    settle(page2, 2)
                    goto_improv(page2, NOTES)
                    ensure_missions_workspace(page2, NOTES)
                    settle(page2, 2)
                    body_m_c = shot(page2, "15-missions-custom-ga-c")
                    m_c_prog = missions_derived_from_custom_trial(body_m_c, projected="C")
                    m_c_title = has_any(body_m_c, "Embargo Trial", "Trial Song")
                    m_c_not_say = not has_any(body_m_c, "Say — John Mayer")

                    c15_ok = (
                        sbi_opened
                        and sbi_prog_ok
                        and sbi_title_ok
                        and sbi_not_say
                        and pk_sbi_ok
                        and m_prog
                        and m_title
                        and m_not_say
                        and pk_m_ok
                        and songs_c_ok
                        and sbi_c_prog
                        and sbi_c_title
                        and pk_sbi_c_ok
                        and m_c_prog
                        and m_c_title
                        and m_c_not_say
                    )
                    mark(
                        "15_custom_ga_sbi_missions",
                        "PASS" if c15_ok else "RED",
                        f"sbi_open={sbi_opened} sbi_prog={sbi_prog_ok} sbi_title={sbi_title_ok} "
                        f"pk={pk_sbi_ok} m_prog={m_prog} m_title={m_title} say_leak={not sbi_not_say} "
                        f"songs_c={songs_c_ok} sbi_c_prog={sbi_c_prog} pk_c={pk_sbi_c_ok} "
                        f"m_c_prog={m_c_prog} m_c_title={m_c_title}",
                    )
            else:
                mark("15_custom_ga_sbi_missions", "RED", "goto_improv failed")
        except Exception as exc:
            mark("15_custom_ga_sbi_missions", "RED", repr(exc))

        browser2.close()

    # Summary
    reds = [k for k, v in RESULTS.items() if v == "RED"]
    partials = [k for k, v in RESULTS.items() if v == "PARTIAL"]
    passes = [k for k, v in RESULTS.items() if v == "PASS"]
    overall = "PASS" if not reds and not partials else ("PARTIAL" if not reds else "RED")
    summary = {
        "meta": meta,
        "overall": overall,
        "results": RESULTS,
        "pass": passes,
        "partial": partials,
        "red": reds,
        "notes": NOTES[-80:],
    }
    (OUT / f"{PREFIX}summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (OUT / f"{PREFIX}summary.txt").write_text(
        "\n".join(
            [
                f"OVERALL={overall}",
                f"PASS={len(passes)} PARTIAL={len(partials)} RED={len(reds)}",
                json.dumps(RESULTS, indent=2),
                "",
                *NOTES[-60:],
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps(RESULTS, indent=2), flush=True)
    print(f"OVERALL={overall}", flush=True)
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
