"""Browser proof for C3.1 on the real Phrase / Motif page.

Reproduces the two human-test findings and proves the corrections:

1. Beginner Auto / Musical stays inside the key — the live sheet music must not
   fill up with accidentals (the reported Gb / Ab / B / Db case).
2. The generated motif is the canonical seed — Build develops it and the opening
   cell keeps showing it across Length / Pattern Type / Direction / Change
   Rhythm, while New motif is what replaces it.

Usage:
  python -m streamlit run streamlit_music_practice_app.py --server.port 8525
  python scripts/_proof_c31_seed_and_beginner.py http://127.0.0.1:8525 OUT_DIR
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path[:0] = [str(SCRIPTS), str(ROOT)]

from improvisation_motif import _parse_key_scale, _pc_of_note, chord_tone_names  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

import _proof_phrase_auto_musical as base  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8525"
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else SCRIPTS / "evidence-c31"
OUT.mkdir(parents=True, exist_ok=True)
base.URL = URL
base.OUT = OUT
LEVEL = base.LEVEL

REPORT: dict = {"checks": {}, "detail": {}}


def card_notes(pr) -> list[str]:
    """The motif/pattern notes as the card shows them (cells separated by |)."""
    text = pr.card()["text"]
    line = next(
        (ln for ln in text.splitlines() if "–" in ln and not ln.startswith(("Rhythm:", "Pattern:"))),
        "",
    )
    return [n.strip() for n in re.split(r"[–|]", line) if n.strip()]


def first_cell(pr) -> list[str]:
    text = pr.card()["text"]
    line = next(
        (ln for ln in text.splitlines() if "–" in ln and not ln.startswith(("Rhythm:", "Pattern:"))),
        "",
    )
    head = line.split("|")[0]
    return [n.strip() for n in head.split("–") if n.strip()]


def accidental_count(abc: str) -> int:
    body = "\n".join(ln for ln in abc.splitlines() if not re.match(r"^[A-Za-z]:", ln))
    return len(re.findall(r"[_^=][A-Ga-g]", body))


def run() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--disable-gpu", "--no-sandbox"],
        )
        page = browser.new_page(viewport={"width": 1400, "height": 1000})
        page.set_default_timeout(60000)
        base.open_phrase_motif(page)
        pr = base.Proof(page)
        pr.settle()

        # --- fresh motif, pinned Auto / Musical controls -----------------------
        pr.click_key("improv_gen_motif_chord")
        pr.select("improv_motif_pattern_type_widget", "Auto / Musical")
        pr.select("improv_motif_pattern_dir_widget", "Ascending")
        pr.select("improv_motif_pattern_length_widget", "8")
        chord = re.sub(r"^Motif(?: pattern)? on\s+", "", pr.card()["title"]).strip()
        REPORT["detail"]["chord"] = chord

        # ================= 1. Beginner stays diatonic ==========================
        pr.select(LEVEL, "Beginner")
        pr.click_key("improv_gen_motif_chord")
        seed = card_notes(pr)
        REPORT["detail"]["beginner_seed"] = seed
        page.locator("#motif-live-card").screenshot(path=str(OUT / "c31_beginner_seed.png"))

        beginner_acc: dict[str, int] = {}
        beginner_outside: dict[str, list[str]] = {}
        key_sig = ""
        for length in ("8", "12", "16"):
            pr.select("improv_motif_pattern_length_widget", length)
            pr.click_key("improv_build_motif_pattern")
            abc = pr.abc()
            key_sig = next((ln[2:].strip() for ln in abc.splitlines() if ln.startswith("K:")), key_sig)
            beginner_acc[length] = accidental_count(abc)
            _mode, diatonic = _parse_key_scale(key_sig)
            allowed = set(diatonic) | {
                _pc_of_note(t) for t in chord_tone_names(chord, reference_key=key_sig) if str(t).strip()
            }
            notes = card_notes(pr)
            beginner_outside[length] = sorted({n for n in notes if _pc_of_note(n) not in allowed})
            if length == "16":
                page.locator("#motif-live-card").screenshot(path=str(OUT / "c31_beginner_len16.png"))
        REPORT["detail"]["key"] = key_sig
        REPORT["detail"]["beginner_accidentals"] = beginner_acc
        REPORT["detail"]["beginner_outside"] = beginner_outside
        REPORT["checks"]["beginner_no_accidentals"] = all(v == 0 for v in beginner_acc.values())
        REPORT["checks"]["beginner_inside_key"] = all(not v for v in beginner_outside.values())

        # Sequence Up / Down must stay diatonic too (the reported leak).
        seq_outside: dict[str, list[str]] = {}
        _mode, diatonic = _parse_key_scale(key_sig)
        allowed = set(diatonic) | {
            _pc_of_note(t) for t in chord_tone_names(chord, reference_key=key_sig) if str(t).strip()
        }
        for key_name, tag in (("improv_xform_up", "sequence_up"), ("improv_xform_down", "sequence_down")):
            pr.click_key(key_name)
            seq_outside[tag] = sorted({n for n in card_notes(pr) if _pc_of_note(n) not in allowed})
        REPORT["detail"]["beginner_sequence_outside"] = seq_outside
        REPORT["checks"]["beginner_sequence_diatonic"] = all(not v for v in seq_outside.values())
        page.locator("#motif-live-card").screenshot(path=str(OUT / "c31_beginner_after_sequence.png"))

        # ================= 2. Seed is canonical ================================
        pr.select("improv_motif_pattern_length_widget", "8")
        pr.click_key("improv_gen_motif_chord")
        seed2 = card_notes(pr)
        REPORT["detail"]["seed_under_test"] = seed2

        pr.click_key("improv_build_motif_pattern")
        opening = first_cell(pr)
        REPORT["detail"]["opening_after_build"] = opening
        REPORT["checks"]["build_keeps_seed"] = opening == seed2

        # Repeated Build must not change it.
        pr.click_key("improv_build_motif_pattern")
        pr.click_key("improv_build_motif_pattern")
        REPORT["detail"]["opening_after_3_builds"] = first_cell(pr)
        REPORT["checks"]["repeated_build_keeps_seed"] = first_cell(pr) == seed2

        # Length / Pattern Type / Direction / Change Rhythm keep the seed.
        kept: dict[str, list[str]] = {}
        pr.select("improv_motif_pattern_length_widget", "12")
        pr.click_key("improv_rebuild_motif_pattern")
        kept["length_12"] = first_cell(pr)
        pr.select("improv_motif_pattern_type_widget", "Thirds")
        pr.click_key("improv_rebuild_motif_pattern")
        kept["type_thirds"] = first_cell(pr)
        pr.select("improv_motif_pattern_type_widget", "Auto / Musical")
        pr.click_key("improv_rebuild_motif_pattern")
        kept["type_auto"] = first_cell(pr)
        pr.click_key("improv_pattern_change_rhythm")
        kept["change_rhythm"] = first_cell(pr)
        REPORT["detail"]["opening_after_changes"] = kept
        REPORT["checks"]["changes_keep_seed"] = all(v == seed2 for v in kept.values())
        page.locator("#motif-live-card").screenshot(path=str(OUT / "c31_seed_kept.png"))

        # New motif replaces the seed, and the next Build opens on the new one.
        pr.click_key("improv_motif_new")
        new_seed = card_notes(pr)
        REPORT["detail"]["new_seed"] = new_seed
        REPORT["checks"]["new_motif_changes_seed"] = new_seed != seed2
        pr.select("improv_motif_pattern_length_widget", "8")
        pr.click_key("improv_build_motif_pattern")
        REPORT["detail"]["opening_after_new_motif_build"] = first_cell(pr)
        REPORT["checks"]["build_follows_new_seed"] = first_cell(pr) == new_seed
        page.locator("#motif-live-card").screenshot(path=str(OUT / "c31_new_seed_build.png"))

        # ================= 3. Advanced still rich ==============================
        pr.select(LEVEL, "Advanced")
        pr.click_key("improv_motif_new")
        adv_seed = card_notes(pr)
        pr.click_key("improv_build_motif_pattern")
        adv_abc = pr.abc()
        REPORT["detail"]["advanced_seed"] = adv_seed
        REPORT["detail"]["advanced_accidentals"] = accidental_count(adv_abc)
        REPORT["detail"]["advanced_opening"] = first_cell(pr)
        REPORT["checks"]["advanced_has_colour"] = accidental_count(adv_abc) > 0
        REPORT["checks"]["advanced_keeps_seed"] = first_cell(pr) == adv_seed
        page.locator("#motif-live-card").screenshot(path=str(OUT / "c31_advanced.png"))

        browser.close()

    (OUT / "C31_PROOF.json").write_text(json.dumps(REPORT, indent=2), encoding="utf-8")
    print(json.dumps(REPORT, indent=2), flush=True)
    print("ALL OK" if all(REPORT["checks"].values()) else "FAILURES PRESENT", flush=True)


if __name__ == "__main__":
    run()
