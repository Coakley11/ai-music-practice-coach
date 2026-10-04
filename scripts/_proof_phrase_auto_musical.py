"""Browser proof: Phrase / Motif Auto / Musical uses the pattern vocabulary (Slice C2).

Drives the real page and, for each generated pattern, checks three independent
views of the same pitches:

1. engine replay — ``build_phrase_pattern`` offline with the same key, chord,
   level, direction, and length, whose family and MIDI equal the live pattern
   (the live Build seed lives in restored session state, so it is searched);
2. live sheet music — the page's ABC decoded by the abcjs instance inside the
   app's own render iframe (sounding MIDI, key signature and bar accidentals);
3. live Guitar TAB — frets decoded back to MIDI (journey H).

Usage:
  python -m streamlit run streamlit_music_practice_app.py --server.port 8591
  python scripts/_proof_phrase_auto_musical.py http://127.0.0.1:8591 OUT_DIR
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path[:0] = [str(SCRIPTS), str(ROOT)]

# Import the engine (and its Streamlit dependencies) before Playwright starts its
# event loop; importing them mid-session dropped the Playwright driver connection.
from melodic_pattern_engine import get_family  # noqa: E402
from motif_engine import (  # noqa: E402
    build_phrase_pattern,
    motif_guitar_tab_placements,
    rebuild_phrase_pattern,
)
from playwright.sync_api import Page, sync_playwright  # noqa: E402

from _walk_pass8_nav_first_click import click_sidebar_once, expand_pages, wait  # noqa: E402
from walk_creative_backing_matrix import click_nav, click_radio, set_baseweb_select  # noqa: E402
from walk_guitar_shape_key import pick_song  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8591"
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else SCRIPTS / "evidence-phrase-auto-musical"
LEVEL = "improv_motif_setup--qc_level"  # Phrase / Motif page's own Level control
INSTRUMENT = "improv_motif_setup--qc_instrument"
CHROMATIC_CATEGORIES = {"chromatic_approach", "enclosure", "bebop", "chromatic_sequence"}
_GUITAR_OPEN = (64, 59, 55, 50, 45, 40)  # e B G D A E

_BUSY_JS = r"""() => {
  const w = document.querySelector('[data-testid="stStatusWidget"]');
  const running = !!(w && /running|stop/i.test(w.innerText || ''));
  return running || !!document.querySelector('[data-stale="true"]');
}"""

_DECODE_IN_APP_ABCJS = r"""(abc) => {
  const host = document.createElement('div');
  document.body.appendChild(host);
  const vo = ABCJS.renderAbc(host, abc)[0];
  const out = [];
  for (const tr of vo.setUpAudio().tracks) for (const ev of tr) if (ev.cmd === 'note') out.push(ev.pitch);
  host.remove();
  return {pitches: out, warnings: (vo.warnings || []).length};
}"""


class Proof:
    def __init__(self, page: Page) -> None:
        self.page = page
        self.checks: dict[str, bool] = {}
        self.log: list[dict[str, Any]] = []

    # ------------------------------------------------------------------ page helpers
    def settle(self, timeout: float = 150.0) -> None:
        """Wait until the Streamlit rerun has finished (no running status, no stale nodes)."""
        end = time.time() + timeout
        quiet = 0
        self.page.wait_for_timeout(400)
        while time.time() < end:
            quiet = 0 if self.page.evaluate(_BUSY_JS) else quiet + 1
            if quiet >= 3:
                return
            self.page.wait_for_timeout(350)
        raise TimeoutError("Streamlit rerun did not settle")

    def key(self, k: str):
        return self.page.locator(f".st-key-{k}").first

    def click_key(self, k: str, settle: int = 3500) -> None:
        btn = self.key(k).locator("button").first
        btn.scroll_into_view_if_needed()
        btn.click()
        del settle
        self.settle()

    def select(self, k: str, option: str, settle: int = 3500) -> None:
        """Set a Streamlit (react-aria ComboBox) selectbox and assert it took the value."""
        inp = self.key(k).locator('input[role="combobox"]').first
        inp.scroll_into_view_if_needed()
        if inp.input_value() == option:
            return
        inp.click()
        self.page.wait_for_timeout(400)
        inp.fill(option)
        self.page.wait_for_timeout(700)
        opt = self.page.locator('[role="listbox"] [role="option"]').filter(
            has_text=re.compile(rf"^\s*{re.escape(option)}\s*$")
        )
        if opt.count():
            opt.first.click()
        else:
            inp.press("Enter")
        del settle
        self.settle()
        got = self.key(k).locator('input[role="combobox"]').first.input_value()
        assert got == option, f"{k}: wanted {option!r}, widget shows {got!r}"

    def card(self) -> dict[str, str]:
        card = self.page.locator("#motif-live-card").first
        text = card.inner_text()
        fam = card.locator("[data-pattern-family]")
        return {
            "text": text,
            "family": fam.first.get_attribute("data-pattern-family") if fam.count() else "",
            "last_transform": card.locator("[data-last-transform]").first.get_attribute("data-last-transform") or "",
            "rhythm": next((ln[len("Rhythm: "):] for ln in text.splitlines() if ln.startswith("Rhythm: ")), ""),
            "label": next((ln for ln in text.splitlines() if ln.startswith("Pattern: ")), ""),
            # textContent: the card title is CSS-uppercased in innerText.
            "title": (card.locator(".ui-card-title").first.text_content() or "").strip(),
        }

    def abc(self) -> str:
        codes = self.page.locator('[data-testid="stExpander"]').filter(has_text="ABC source").locator("code")
        for _attempt in range(2):  # a click during a heavy rerun is occasionally dropped
            self.click_key("improv_motif_sheet")
            try:
                codes.first.wait_for(state="attached", timeout=20000)
                return codes.first.text_content() or ""
            except Exception:
                continue
        raise TimeoutError("sheet music ABC did not render")

    def abcjs_midi(self, abc: str) -> list[int]:
        for fr in self.page.frames:
            try:
                if fr.evaluate("typeof ABCJS !== 'undefined'"):
                    res = fr.evaluate(_DECODE_IN_APP_ABCJS, abc)
                    assert res["warnings"] == 0, res
                    return list(res["pitches"])
            except Exception:
                continue
        raise RuntimeError("no rendered abcjs iframe on the page")

    def tab_midi(self) -> tuple[list[int], list[tuple[int, int]]]:
        self.click_key("improv_motif_tab_btn")
        text = self.page.locator("code").filter(has_text="e|").first.text_content() or ""
        rows = [ln.split("|", 1)[1].rstrip("|") for ln in text.splitlines() if "|" in ln][:6]
        events: dict[int, tuple[int, int]] = {}
        for si, row in enumerate(rows):
            for m in re.finditer(r"\d+", row):
                events[m.start()] = (si, int(m.group()))
        placements = [events[c] for c in sorted(events)]
        return [_GUITAR_OPEN[si] + fr for si, fr in placements], placements

    # ------------------------------------------------------------------ verification
    def replay(self, *, key: str, chord: str, level: str, direction: str, length: int, seed: int) -> dict:
        return build_phrase_pattern(
            {"chord": chord, "notes": [], "meter": "4/4"}, key_center=key, pattern_type="auto",
            direction=direction, length=length, level=level, pattern_seed=seed,
        )

    def match_live(self, *, key: str, chord: str, level: str, direction: str, length: int,
                   family: str, sounding: list[int], max_seed: int = 400) -> dict | None:
        """Engine realization with the live family and exactly the live sounding MIDI.

        The app's Build counter survives in restored session state, so its seed is not
        known to the browser; search it instead of assuming it starts at 1.
        """
        for seed in range(max_seed):
            exp = self.replay(key=key, chord=chord, level=level, direction=direction, length=length, seed=seed)
            if exp.get("pattern_family") == family and exp["midi"] == sounding:
                exp["_matched_seed"] = seed
                return exp
        return None

    def verify(self, tag: str, *, expected: dict, card: dict, sounding: list[int]) -> bool:
        fam = get_family(expected["pattern_family"])
        ok = (
            card["family"] == fam.id
            and card["label"] == f"Pattern: {fam.name} · {fam.difficulty}"
            and sounding == expected["midi"]
        )
        self.log.append({
            "step": tag, "ok": ok, "label": card["label"], "category": fam.category,
            "notes": " ".join(expected["notes"][: 2 * fam.size]), "midi_head": expected["midi"][: 2 * fam.size],
            "sounding_matches_motif": sounding == expected["midi"], "rhythm": card["rhythm"],
            "sounding_len": len(sounding), "seed": expected.get("_matched_seed"),
        })
        print(f"[step] {tag}: ok={ok} {card['label']}", flush=True)
        return ok


def open_phrase_motif(page: Page) -> None:
    """Load "Perfect", open Creative → Improvisation Intelligence → Phrase / Motif.

    A fresh session's first run takes ~55 s, so every step waits for the rerun
    to finish instead of sleeping a fixed time.
    """
    pr = Proof(page)
    page.goto(URL, wait_until="domcontentloaded", timeout=120000)
    pr.settle()
    expand_pages(page)
    notes: list[str] = []
    for _attempt in range(2):
        if pick_song(page, notes, "Perfect", "Pop"):
            break
        pr.settle()
    pr.settle()
    click_nav(page, "Creative") or click_sidebar_once(page, "Creative")
    pr.settle()
    set_baseweb_select(page, "Analysis mode", "Improvisation Intelligence")
    pr.settle()
    gen = page.locator(".st-key-improv_gen_motif_chord")
    for _attempt in range(3):
        click_radio(page, "Phrase / Motif")
        pr.settle()
        if gen.count():
            return
    raise RuntimeError(f"Phrase / Motif did not open (song pick notes: {notes[-2:]})")


class Session:
    """One fresh browser session on Phrase / Motif with pinned pattern controls."""

    def __init__(self, pr: Proof) -> None:
        self.pr = pr
        pr.settle()
        pr.click_key("improv_gen_motif_chord")
        # Pattern controls are restored from the saved workspace: pin them explicitly.
        pr.select("improv_motif_pattern_type_widget", "Auto / Musical")
        pr.select("improv_motif_pattern_dir_widget", "Ascending")
        pr.select("improv_motif_pattern_length_widget", "8")
        self.chord = re.sub(r"^Motif(?: pattern)? on\s+", "", pr.card()["title"]).strip()
        self.key = "G"  # "Perfect" (Pop) — asserted per build from the sheet-music K: field

    def build(self, level: str, tag: str, direction: str = "ascending", length: int = 8) -> tuple[dict, dict]:
        pr = self.pr
        pr.click_key("improv_build_motif_pattern")
        card = pr.card()
        abc = pr.abc()
        k_field = next(ln[2:] for ln in abc.splitlines() if ln.startswith("K:"))
        assert k_field == self.key, (k_field, self.key)
        sounding = pr.abcjs_midi(abc)
        expected = pr.match_live(key=self.key, chord=self.chord, level=level, direction=direction,
                                 length=length, family=card["family"], sounding=sounding)
        if expected is None:  # no engine realization matches: record the failure explicitly
            expected = pr.replay(key=self.key, chord=self.chord, level=level, direction=direction,
                                 length=length, seed=0)
        pr.verify(tag, expected=expected, card=card, sounding=sounding)
        return expected, card


def journey_a(ss: Session) -> None:
    pr = ss.pr
    pr.select(LEVEL, "Beginner")
    exp, _ = ss.build("Beginner", "A beginner")
    fam = get_family(exp["pattern_family"])
    pr.checks["A_beginner"] = pr.log[-1]["ok"] and fam.difficulty == "Beginner" and fam.chromatic == "none"
    pr.page.locator("#motif-live-card").screenshot(path=str(OUT / "A_beginner_card.png"))


def journey_b(ss: Session) -> None:
    pr = ss.pr
    pr.select(LEVEL, "Intermediate")
    cats, oks = set(), []
    for i in range(6):
        exp, _ = ss.build("Intermediate", f"B intermediate #{i + 1}")
        oks.append(pr.log[-1]["ok"])
        cats.add(get_family(exp["pattern_family"]).category)
    pr.checks["B_intermediate_variety"] = all(oks) and len(cats) >= 3


def journey_c_g(ss: Session) -> None:
    pr = ss.pr
    pr.select(LEVEL, "Advanced")
    cats, diatonic_seen, oks, chromatic_steps = set(), False, [], []
    for i in range(10):
        exp, _ = ss.build("Advanced", f"C advanced #{i + 1}")
        oks.append(pr.log[-1]["ok"])
        fam = get_family(exp["pattern_family"])
        cats.add(fam.category)
        diatonic_seen |= fam.chromatic == "none"
        if fam.category in ("enclosure", "chromatic_approach"):
            chromatic_steps.append(pr.log[-1])
            if len(chromatic_steps) == 1:
                pr.page.locator("#motif-live-card").screenshot(path=str(OUT / "C_chromatic_card.png"))
                pr.page.screenshot(path=str(OUT / "G_sheet_chromatic.png"), full_page=True)
    pr.checks["C_advanced_reach"] = all(oks) and bool(cats & CHROMATIC_CATEGORIES) and diatonic_seen
    pr.checks["G_sheet_music_chromatic"] = bool(chromatic_steps) and all(
        e["sounding_matches_motif"] for e in chromatic_steps
    )


def journey_d_e(ss: Session) -> None:
    pr, key = ss.pr, ss.key
    pr.select(LEVEL, "Advanced")
    current, _ = ss.build("Advanced", "D base (ascending)")
    pr.select("improv_motif_pattern_dir_widget", "Descending")
    card = pr.card()
    abc = pr.abc()
    exp_d = rebuild_phrase_pattern(current, key_center=key, pattern_type="auto", direction="descending", level="Advanced")
    pr.verify("D descending", expected=exp_d, card=card, sounding=pr.abcjs_midi(abc))
    pr.checks["D_direction_keeps_family"] = (
        pr.log[-1]["ok"] and exp_d["pattern_family"] == current["pattern_family"]
        and exp_d["pattern_direction"] == "descending"
    )
    pr.page.screenshot(path=str(OUT / "D_descending.png"), full_page=True)
    prev, oks = exp_d, []
    for length in (12, 16):
        pr.select("improv_motif_pattern_length_widget", str(length))
        pr.click_key("improv_rebuild_motif_pattern")
        card = pr.card()
        abc = pr.abc()
        exp_e = rebuild_phrase_pattern(prev, key_center=key, pattern_type="auto", length=length, level="Advanced")
        pr.verify(f"E length {length}", expected=exp_e, card=card, sounding=pr.abcjs_midi(abc))
        oks.append(pr.log[-1]["ok"] and exp_e["pattern_family"] == current["pattern_family"]
                   and len(exp_e["cells"]) == length)
        prev = exp_e
    pr.checks["E_length_keeps_family"] = all(oks)


def journey_f(ss: Session) -> None:
    pr = ss.pr
    pr.select(LEVEL, "Advanced")
    base = None
    for i in range(8):
        exp, card = ss.build("Advanced", f"F candidate #{i + 1}")
        if get_family(exp["pattern_family"]).size in (3, 4) and pr.log[-1]["ok"]:
            base = (exp, card)
            break
    assert base is not None, "no 3/4-note Auto cell in 8 builds"
    exp_f, card_f = base
    before_abc = pr.abc()
    before_midi = pr.abcjs_midi(before_abc)
    pr.click_key("improv_pattern_change_rhythm")
    after = pr.card()
    after_abc = pr.abc()
    after_midi = pr.abcjs_midi(after_abc)
    pr.checks["F_change_rhythm_pitch_invariant"] = (
        after["family"] == card_f["family"]
        and after["label"] == card_f["label"]
        and after_midi == before_midi == exp_f["midi"]
        and after["rhythm"] != card_f["rhythm"]
        and after["last_transform"] == "change_rhythm"
        and after_abc != before_abc
    )
    pr.log.append({"step": "F change rhythm", "family": after["family"], "label": after["label"],
                   "rhythm_before": card_f["rhythm"], "rhythm_after": after["rhythm"],
                   "midi_equal_before_after_engine": after_midi == before_midi == exp_f["midi"],
                   "notes": " ".join(exp_f["notes"][:8])})
    print(f"[step] F change rhythm: ok={pr.checks['F_change_rhythm_pitch_invariant']} "
          f"{card_f['rhythm']} -> {after['rhythm']}", flush=True)
    pr.page.locator("#motif-live-card").screenshot(path=str(OUT / "F_after_change_rhythm_card.png"))


def journey_h(ss: Session) -> None:
    pr = ss.pr
    pr.select(LEVEL, "Advanced")
    pr.select(INSTRUMENT, "Guitar", settle=5000)
    exp_h, card_h = ss.build("Advanced", "H guitar base")
    tab_midi, placements = pr.tab_midi()
    optimized = motif_guitar_tab_placements(exp_h)
    pr.checks["H_guitar_tab_exact_and_optimized"] = tab_midi == exp_h["midi"] and placements == optimized
    pr.log.append({"step": "H guitar tab", "label": card_h["label"],
                   "tab_midi_equals_motif": tab_midi == exp_h["midi"],
                   "placements_equal_optimizer": placements == optimized, "placements_head": placements[:8]})
    print(f"[step] H guitar tab: ok={pr.checks['H_guitar_tab_exact_and_optimized']}", flush=True)
    pr.page.screenshot(path=str(OUT / "H_guitar_tab.png"), full_page=True)


JOURNEYS = {"A": journey_a, "B": journey_b, "C": journey_c_g, "DE": journey_d_e, "F": journey_f, "H": journey_h}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    checks: dict[str, bool] = {}
    log: list[dict[str, Any]] = []
    retries: list[str] = []
    for name, fn in JOURNEYS.items():
        for attempt in (1, 2):
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page(viewport={"width": 1400, "height": 1100})
                # A new session's first Phrase / Motif run takes ~55 s on this page.
                page.set_default_timeout(120000)
                pr = Proof(page)
                try:
                    open_phrase_motif(page)
                    fn(Session(pr))
                    checks.update(pr.checks)
                    log.extend(pr.log)
                    browser.close()
                    break
                except Exception as exc:  # driver drop / timeout / slow open: retry once in a fresh session
                    transient = ("Connection closed" in str(exc) or "Timeout" in type(exc).__name__
                                 or "did not open" in str(exc))
                    if not transient or attempt == 2:
                        raise
                    retries.append(f"{name}: {type(exc).__name__}")
                    print(f"[retry] journey {name} after {type(exc).__name__}", flush=True)
    ok = all(checks.values())
    summary = {"ok": ok, "checks": checks, "driver_retries": retries, "steps": log}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"ok": ok, "checks": checks, "driver_retries": retries}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
