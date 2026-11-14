"""Issue 79 acceptance in the real app: Tone Sustain Practice on a known note.

The signal suite proves the arithmetic. This proves the screen: that the panel the musician uses
really offers an octave, really shows five separated readings, really explains an octave difference
instead of presenting it as 1169 cents of bad tuning, really saves the take with its measurement,
and really brings it back.

The microphone is a file. Chromium's ``--use-file-for-fake-audio-capture`` feeds a WAV to
``getUserMedia``, so ``st.audio_input`` records audio whose pitch is known to the cent - a steady
E5, 31 cents flat, which is the user's own reported case. Without that, the fake device's beep
would make every number a guess and the acceptance would prove only that nothing crashed.

Usage:
  python scripts/_accept_issue79_app.py http://127.0.0.1:8597
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))

from tests.tone_test_signals import E5_HZ, tone, wav_bytes  # noqa: E402
from walk_creative_backing_matrix import click_nav  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8597"
OUT = SCRIPTS / "evidence-issue79"
OUT.mkdir(parents=True, exist_ok=True)

#: The microphone, as a file: E5 held 31 cents flat for eight seconds (long enough that however
#: much of it the recorder catches, the sustained portion is well over the minimum).
MIC_WAV = OUT / "mic-e5-flat31.wav"
MIC_WAV.write_bytes(wav_bytes(tone(E5_HZ * 2 ** (-31 / 1200.0), 8.0, amp=0.35)))

GATES: dict[str, bool] = {}
MEASURED: dict[str, object] = {}


def log(msg: str) -> None:
    print(msg.encode("ascii", "replace").decode("ascii"), flush=True)


def mark(gate: str, ok: bool, detail: object = "") -> None:
    GATES[gate] = bool(ok)
    if not isinstance(detail, str):
        try:
            detail = json.dumps(detail, default=str)
        except Exception:
            detail = repr(detail)
    detail = (detail or "").replace(chr(10), " | ")[:240]
    log(f"  {'PASS' if ok else 'FAIL'}  {gate}{('  -> ' + detail) if detail else ''}")


def settle(page: Page, s: float = 2.5) -> None:
    page.wait_for_timeout(int(s * 1000))


def low(s: str) -> str:
    return (s or "").lower()


def body(page: Page) -> str:
    return page.inner_text("body") or ""


def boot(page: Page) -> bool:
    page.goto(URL, wait_until="domcontentloaded")
    waited = 0
    while waited < 180:
        text = body(page)
        if len(text.strip()) > 400 and "PAGES" in text.upper():
            return True
        settle(page, 3)
        waited += 3
    return False


def click_button_by_text(page: Page, text: str, *, timeout_s: float = 8.0) -> bool:
    """Click the first visible button whose label contains ``text``."""
    loc = page.locator("button").filter(has_text=re.compile(re.escape(text), re.I))
    for i in range(loc.count()):
        el = loc.nth(i)
        try:
            if not el.is_visible():
                continue
            el.scroll_into_view_if_needed(timeout=int(timeout_s * 1000))
            el.click(timeout=int(timeout_s * 1000))
            return True
        except Exception:
            continue
    return False


def select_option(page: Page, label: str, value: str, *, timeout_s: float = 12.0) -> str:
    """Set a Streamlit selectbox by its label, with real clicks.

    BaseWeb's listbox ignores a dispatched .click(), which cost a whole run on Issue 78B; these are
    real Playwright clicks, retried, and the chosen value is read back rather than assumed.
    """
    for attempt in range(1, 4):
        try:
            holder = page.locator(f'div[data-testid="stSelectbox"]:has-text("{label}")').first
            holder.scroll_into_view_if_needed(timeout=int(timeout_s * 1000))
            holder.locator("div[role='combobox'], input").first.click(timeout=int(timeout_s * 1000))
            page.wait_for_timeout(400)
            option = page.get_by_role("option", name=value, exact=True)
            if option.count() == 0:
                option = page.locator("li, div[role='option']").filter(
                    has_text=re.compile(rf"^{re.escape(value)}$")
                )
            option.first.click(timeout=int(timeout_s * 1000))
            settle(page, 3)
            return read_select(page, label)
        except Exception as exc:  # pragma: no cover - harness robustness
            log(f"    select_option({label!r}, {value!r}) attempt {attempt}: {exc}")
            page.keyboard.press("Escape")
            page.wait_for_timeout(600)
    return read_select(page, label)


def read_select(page: Page, label: str) -> str:
    """The value a selectbox holds. Its container's text includes the label, so read the input."""
    return page.evaluate(
        """(label) => {
            const boxes = [...document.querySelectorAll('div[data-testid="stSelectbox"]')];
            for (const b of boxes) {
                if (!(b.innerText || '').toLowerCase().includes(label.toLowerCase())) continue;
                const inp = b.querySelector('input');
                if (inp && inp.value) return inp.value;
                const combo = b.querySelector("div[role='combobox']");
                if (combo) return (combo.innerText || '').trim();
            }
            return '';
        }""",
        label,
    )


def click_practice_page(page: Page) -> bool:
    """Open the Practice page - the one with the tools, not the Practice Log.

    ``click_nav(page, "Practice")`` matches any button whose text CONTAINS "Practice" and takes the
    last one, which is "Practice Log". A whole acceptance run reported "Tone Sustain Practice does
    not open" from the wrong page because of it.
    """
    return bool(
        page.evaluate(
            r"""() => {
                const want = /^(?:[^A-Za-z]*\s*)?practice$/i;
                const buttons = [...document.querySelectorAll('button')];
                for (const b of buttons) {
                    const t = (b.innerText || '').trim();
                    if (!want.test(t)) continue;
                    if (b.offsetParent === null) continue;
                    b.click();
                    return true;
                }
                return false;
            }"""
        )
    )


def tone_panel_open(page: Page) -> bool:
    return "tone sustain practice" in low(body(page))


def goto_tone_sustain(page: Page) -> bool:
    """Practice page -> Metronome, Tuner & Tone tool -> Tone Sustain Practice view."""
    if tone_panel_open(page):
        return True
    if not click_practice_page(page):
        click_nav(page, "Practice")
    settle(page, 8)
    if tone_panel_open(page):
        return True
    # The tool launcher is a TOGGLE: clicking the tool that is already active closes it. After a
    # reload the app restores the tool as active, so clicking blindly here shut the panel and every
    # gate after it looked at a page with nothing on it.
    already_active = page.evaluate(
        """() => {
            const el = document.querySelector('.st-key-practice_tool_pick_time_and_pitch button');
            if (!el) return false;
            return (el.getAttribute('kind') || el.className || '').includes('primary');
        }"""
    )
    tool = page.locator(".st-key-practice_tool_pick_time_and_pitch button")
    if tool.count() and not already_active:
        try:
            tool.first.click(timeout=12000)
            settle(page, 8)
        except Exception as exc:
            log(f"    opening the Time & Pitch tool failed: {exc}")
    # The view switcher is a radio: "Live Tuner" / "Tone Sustain Practice".
    picked = page.evaluate(
        """() => {
            const labels = [...document.querySelectorAll('label')];
            for (const l of labels) {
                if ((l.innerText || '').toLowerCase().includes('tone sustain')) {
                    const el = l.querySelector('input') || l;
                    el.click();
                    return true;
                }
            }
            return false;
        }"""
    )
    if picked:
        settle(page, 6)
    return "tone sustain practice" in low(body(page))


def record_long_tone(page: Page, seconds: float = 5.0) -> bool:
    """Press the audio_input record button, hold, then stop - and wait for the analysis."""
    rec = page.locator('[data-testid="stAudioInputActionButton"]').first
    if rec.count() == 0:
        return False
    rec.click(timeout=15000)
    page.wait_for_timeout(int(seconds * 1000))
    stop = page.locator('[data-testid="stAudioInputActionButton"]').first
    stop.click(timeout=15000)
    # The analysis runs server side; wait for a readout or an honest refusal.
    for _ in range(40):
        settle(page, 2)
        text = low(body(page))
        if "pitch stability" in text or "not enough reliable pitch" in text:
            return True
    return False


def readouts(page: Page) -> dict[str, object]:
    """The numbers and words the panel is showing, parsed from the rendered page."""
    text = body(page)
    out: dict[str, object] = {"raw": text}
    for key, pattern in (
        ("pitch_stability", r"Pitch stability\s*\n\s*([0-9.]+)%"),
        ("volume_consistency", r"Volume consistency\s*\n\s*([0-9.]+)%"),
        ("sustain", r"Sustain\s*\n\s*([0-9.]+)s"),
    ):
        m = re.search(pattern, text, re.I)
        out[key] = float(m.group(1)) if m else None
    m = re.search(r"Detected note:\s*([A-G][#b]?-?\d)", text)
    out["detected_note"] = m.group(1) if m else None
    m = re.search(r"Tuning offset:\s*([+-]?[0-9.]+)", text)
    out["tuning_offset"] = float(m.group(1)) if m else None
    m = re.search(r"Confidence:\s*([0-9.]+)%", text)
    out["confidence"] = float(m.group(1)) if m else None
    m = re.search(r"Octave:\s*([^\n·]+)", text)
    out["octave_line"] = m.group(1).strip() if m else None
    out["octave_notice"] = "octave difference, not a tuning error" in low(text)
    out["insufficient"] = "not enough reliable pitch detected" in low(text)
    return out


def gate_panel_offers_the_contract(page: Page) -> None:
    log("\n== the panel states its target contract ==")
    text = body(page)
    mark("the Tone Sustain panel is open", "tone sustain practice" in low(text))
    mark("a target note can be chosen", "Target note" in text)
    mark("a target OCTAVE can be chosen", "Target octave" in text,
         f"octave selector present: {'Target octave' in text}")
    note = read_select(page, "Target note")
    octave = read_select(page, "Target octave")
    mark("the contract is readable from the page", bool(note),
         json.dumps({"note": note, "octave": octave}))
    contract_lines = [
        ln.strip() for ln in text.split(chr(10)) if ln.strip().startswith("Target:")
    ]
    mark("the default contract is stated in words",
         "tuning is measured against the octave you play" in low(text)
         or "a specific" in low(text),
         contract_lines[:2])


def gate_measured_readouts(page: Page) -> dict[str, object]:
    log("\n== recording a known E5, 31 cents flat ==")
    select_option(page, "Target note", "E")
    oct_value = select_option(page, "Target octave", "5")
    mark("the target octave can be set to 5", oct_value == "5", f"reads {oct_value!r}")
    ok = record_long_tone(page)
    mark("a long tone can be recorded and analysed", ok)
    if not ok:
        return {}
    r = readouts(page)
    MEASURED["e5_target_e5"] = {k: v for k, v in r.items() if k != "raw"}
    mark("pitch stability is reported as a number", isinstance(r["pitch_stability"], float),
         r["pitch_stability"])
    mark("a steady recorded tone is not scored near zero",
         isinstance(r["pitch_stability"], float) and r["pitch_stability"] >= 70.0,
         r["pitch_stability"])
    mark("volume consistency is reported, with silence around the note excluded",
         isinstance(r["volume_consistency"], float) and r["volume_consistency"] >= 70.0,
         r["volume_consistency"])
    mark("sustain is reported in seconds", isinstance(r["sustain"], float), r["sustain"])
    mark("the detected note names its octave", r["detected_note"] == "E5", r["detected_note"])
    mark("tuning offset is reported separately from stability",
         isinstance(r["tuning_offset"], float), r["tuning_offset"])
    mark("the tuning offset is the ~31 cents flat that was played",
         isinstance(r["tuning_offset"], float) and -55.0 <= r["tuning_offset"] <= -8.0,
         r["tuning_offset"])
    mark("detection confidence is shown", isinstance(r["confidence"], float), r["confidence"])
    mark("no octave difference is claimed when there is none", not r["octave_notice"])
    mark("the pitch trace is drawn", "pitch trace" in low(r["raw"]))
    return r


def gate_e4_reference(page: Page, measured: dict[str, object]) -> None:
    """The headline defect: the same recording against an E4 reference."""
    log("\n== the same take, against an E4 reference ==")
    oct_value = select_option(page, "Target octave", "4")
    mark("the target octave can be changed to 4", oct_value == "4", f"reads {oct_value!r}")
    settle(page, 6)
    r = readouts(page)
    MEASURED["e5_target_e4"] = {k: v for k, v in r.items() if k != "raw"}
    mark("the detected note is still E5", r["detected_note"] == "E5", r["detected_note"])
    mark("the octave difference is stated as an octave difference", bool(r["octave_notice"]),
         r["octave_line"])
    mark("the tuning offset is NOT presented as ~1200 cents",
         isinstance(r["tuning_offset"], float) and abs(r["tuning_offset"]) < 100.0,
         r["tuning_offset"])
    mark("the tuning offset is still the ~31 cents that were played",
         isinstance(r["tuning_offset"], float) and -55.0 <= r["tuning_offset"] <= -8.0,
         r["tuning_offset"])
    if isinstance(measured.get("pitch_stability"), float) and isinstance(
        r["pitch_stability"], float
    ):
        mark("pitch stability does not depend on the reference octave",
             abs(r["pitch_stability"] - measured["pitch_stability"]) <= 2.0,
             {"e5": measured["pitch_stability"], "e4": r["pitch_stability"]})
    mark("the explanation names the reference it is talking about",
         "e4" in low(r["raw"]),
         [ln.strip() for ln in str(r["raw"]).split(chr(10)) if "e4" in ln.lower()][:2])


def gate_any_octave(page: Page) -> None:
    log("\n== the deliberate any-octave contract ==")
    oct_value = select_option(page, "Target octave", "Any octave")
    mark("the target octave can be set to Any octave", oct_value == "Any octave",
         f"reads {oct_value!r}")
    settle(page, 6)
    r = readouts(page)
    MEASURED["e5_any_octave"] = {k: v for k, v in r.items() if k != "raw"}
    mark("any-octave practice is identified on screen",
         "any octave" in low(r["octave_line"] or "") or "any e" in low(r["raw"]),
         r["octave_line"])
    mark("no octave difference is reported under an any-octave contract",
         not r["octave_notice"])
    mark("tuning is measured against the octave played",
         isinstance(r["tuning_offset"], float) and -55.0 <= r["tuning_offset"] <= -8.0,
         r["tuning_offset"])


def open_tone_history(page: Page) -> str:
    """Expand the Tone History section and return the page text."""
    # Open by clicking the summary only when it is shut. Setting `open` and then clicking toggles
    # it closed again, which is why this found no rows in a page that had just saved one.
    page.evaluate(
        r"""() => {
            let opened = 0;
            for (const d of document.querySelectorAll('details')) {
                const sum = d.querySelector('summary');
                const t = ((sum && sum.innerText) || '').toLowerCase();
                if (!/tone history|saved tone|tone take/.test(t)) continue;
                if (!d.open && sum) { sum.click(); opened++; }
            }
            return opened;
        }"""
    )
    settle(page, 4)
    # Then open every row inside it, the same way.
    page.evaluate(
        r"""() => {
            let opened = 0;
            for (const d of document.querySelectorAll('details')) {
                const sum = d.querySelector('summary');
                const t = ((sum && sum.innerText) || '').toLowerCase();
                if (/tone history|saved tone/.test(t)) continue;
                if (!/[0-9]{4}|take|stability|✓|·|!/.test(t)) continue;
                if (!d.open && sum) { sum.click(); opened++; }
            }
            return opened;
        }"""
    )
    settle(page, 4)
    return body(page)


def history_rows(page: Page) -> list[str]:
    """The text of each Tone History row, so a claim about one is about a real row."""
    return page.evaluate(
        r"""() => {
            const out = [];
            for (const d of document.querySelectorAll('details')) {
                const sum = d.querySelector('summary');
                const title = ((sum && sum.innerText) || '').toLowerCase();
                if (/tone history|library view/.test(title)) continue;  // the container, not a row
                const t = (d.innerText || '');
                if (/pitch report|not measured|stability/i.test(t)) out.push(t.slice(0, 600));
            }
            return out;
        }"""
    )


def gate_save_and_reopen(page: Page) -> None:
    log("\n== saving the take and reading it back ==")
    # The pending-save control is keyed, and it is NOT the only button on the page whose label
    # contains "Save" - "Quick Save Practice Session" is another, and clicking that one proved
    # nothing at all on the first run of this harness.
    btn = page.locator('[class*="st-key-"][class*="tone_save_btn"] button')
    if btn.count() == 0:
        btn = page.locator("button").filter(has_text=re.compile(r"^Save Tone Take$", re.I))
    clicked = False
    if btn.count():
        try:
            btn.first.scroll_into_view_if_needed(timeout=8000)
            btn.first.click(timeout=12000)
            clicked = True
        except Exception as exc:
            log(f"    Save Tone Take click failed: {exc}")
    mark("the Save Tone Take control is present and clickable", clicked,
         f"{btn.count()} matching buttons")
    if not clicked:
        return
    saved_text = ""
    for _ in range(15):
        settle(page, 2)
        saved_text = body(page)
        if "tone take saved" in low(saved_text) or "could not save" in low(saved_text):
            break
    mark("the app confirms the take was saved", "tone take saved" in low(saved_text),
         [ln.strip() for ln in saved_text.split(chr(10)) if "tone take" in ln.lower()][:3])

    # The save triggers a rerun; the history list renders when it renders. Poll rather than
    # assume one settle() was enough - that is what reported "0 rows" for a row the very next
    # gate then found after a reload.
    text = open_tone_history(page)
    rows = history_rows(page)
    waited_rows = 0.0
    while not rows and waited_rows < 30.0:
        page.wait_for_timeout(3000)
        waited_rows += 3.0
        text = open_tone_history(page)
        rows = history_rows(page)
    mark("tone history is reachable", "tone history" in low(text))
    MEASURED["history_rows"] = len(rows)
    MEASURED["history_rows_waited_s"] = waited_rows
    (OUT / "tone-history.txt").write_text(
        text + chr(10) * 2 + ("=" * 40) + chr(10) + (chr(10) * 2).join(rows), encoding="utf-8"
    )
    mark("the saved take appears in tone history", bool(rows),
         f"{len(rows)} rows found after {waited_rows:.0f}s: "
         + str([r.split(chr(10))[0][:60] for r in rows[:2]]))
    joined = " ".join(rows)
    # "0% stability" is a SUBSTRING of "100% stability", so the obvious check fails a perfect
    # take. Match a standalone zero instead.
    zero_score = re.search(r"(?<![0-9])0%\s*stability", low(joined))
    mark("the saved row shows a measurement, not 0%", zero_score is None,
         [r.replace(chr(10), " ")[:140] for r in rows[:2]])
    mark("no stored score prints as None", "none%" not in low(joined), [r[:120] for r in rows[:2]])
    mark("the new row is not labelled a legacy measurement",
         "legacy measurement" not in low(joined),
         f"legacy label occurrences: {low(joined).count('legacy measurement')}")

    page.reload(wait_until="domcontentloaded")
    settle(page, 20)
    mark("the workspace comes back after a reload", len(body(page).strip()) > 400)
    if goto_tone_sustain(page):
        after = open_tone_history(page)
        rows_after = history_rows(page)
        mark("the saved take is still there after a full reload", bool(rows_after),
             f"{len(rows_after)} rows after reload")
        mark("and its measurement came back with it",
             any("stability" in low(r) for r in rows_after),
             [r[:120] for r in rows_after[:2]])
        del after
    else:
        mark("the saved take is still there after a full reload", False,
             "could not reopen the Tone Sustain panel after the reload")


def gate_responsive(page: Page, width: int) -> None:
    page.set_viewport_size({"width": width, "height": 820})
    settle(page, 4)
    over = page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
    mark(f"no horizontal page scroll at {width} px", over <= 2, f"overflow={over}px")
    vis = page.evaluate(
        """() => {
            const out = {};
            for (const b of document.querySelectorAll('div[data-testid="stSelectbox"]')) {
                const t = (b.innerText || '').toLowerCase();
                if (!t.includes('target')) continue;
                const r = b.getBoundingClientRect();
                out[t.split('\\n')[0]] = {w: Math.round(r.width), right: Math.round(r.right)};
            }
            return out;
        }"""
    )
    mark(f"both target selectors are laid out at {width} px", len(vis) >= 2, json.dumps(vis))
    inside = all(v["right"] <= width + 2 for v in vis.values()) if vis else False
    mark(f"the target selectors are not clipped at {width} px", inside, json.dumps(vis))
    page.set_viewport_size({"width": 1400, "height": 950})
    settle(page, 3)


def main() -> int:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=[
                "--use-fake-ui-for-media-stream",
                "--use-fake-device-for-media-stream",
                f"--use-file-for-fake-audio-capture={MIC_WAV.as_posix()}",
                "--autoplay-policy=no-user-gesture-required",
                "--mute-audio",
            ],
        )
        ctx = browser.new_context(viewport={"width": 1400, "height": 950},
                                  permissions=["microphone"])
        page = ctx.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        try:
            if not boot(page):
                mark("the app loads", False)
                return 1
            mark("the app loads", True)
            if not goto_tone_sustain(page):
                mark("Tone Sustain Practice opens", False, low(body(page))[:200])
                return 1
            mark("Tone Sustain Practice opens", True)

            gate_panel_offers_the_contract(page)
            measured = gate_measured_readouts(page)
            if measured:
                gate_e4_reference(page, measured)
                gate_any_octave(page)
                gate_save_and_reopen(page)
            gate_responsive(page, 390)
            gate_responsive(page, 360)
            mark("no uncaught JS errors on the page", not errors, errors[:3])
        finally:
            (OUT / "app-body.txt").write_text(body(page), encoding="utf-8")
            page.screenshot(path=str(OUT / "app-final.png"), full_page=True)
            (OUT / "app-report.json").write_text(
                json.dumps(
                    {
                        "passed": sum(1 for v in GATES.values() if v),
                        "total": len(GATES),
                        "failed": sorted(k for k, v in GATES.items() if not v),
                        "measured": MEASURED,
                        "js_errors": errors,
                    },
                    indent=1,
                    default=str,
                ),
                encoding="utf-8",
            )
            ctx.close()
            browser.close()
    passed = sum(1 for v in GATES.values() if v)
    log(f"\n{passed}/{len(GATES)} gates passed")
    for name, ok in sorted(GATES.items()):
        if not ok:
            log(f"  FAILED: {name}")
    log(f"evidence in {OUT}")
    return 0 if passed == len(GATES) else 1


if __name__ == "__main__":
    raise SystemExit(main())
