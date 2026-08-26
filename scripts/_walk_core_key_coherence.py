"""Core Songs Practice Key coherence — rendered sidebar vs song card.

Asserts the human-visible failures that unit suites miss:
  Shape: Bm → Dm → Bm (mode preserved; first-click sticks)
  Perfect: fresh G major → A major (mode preserved)
  Sidebar label == card Practice Key label

Usage:
  MUSIC_APP_DATA_DIR=<isolated> streamlit run ... --server.port 8530
  python scripts/_walk_core_key_coherence.py http://127.0.0.1:8530
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from walk_creative_backing_matrix import (  # noqa: E402
    click_nav,
    expand_sidebar,
    set_baseweb_select,
    wait_idle,
)
from walk_guitar_shape_key import pick_song  # noqa: E402


def set_songs_practice_key(page: Page, token: str) -> bool:
    """Change Songs sidebar Practice Key and verify via the song card badge."""
    expand_sidebar(page)
    ok = set_baseweb_select(page, "Practice / Concert Key", token)
    wait_idle(page, 3500)
    expect = _norm_label(token_to_label(token))

    def _card_ok() -> bool:
        body = page.inner_text("body") or ""
        card = card_practice_label(body)
        return expect in _norm_label(card) or token.lower() in _norm_label(card).replace(" ", "")

    if _card_ok():
        return bool(ok)
    # Same-rerun badge lag: nudge Songs and wait for the Practice Key badge.
    try:
        click_nav(page, "Songs")
        wait_idle(page, 2500)
    except Exception:
        pass
    try:
        page.wait_for_function(
            """(label) => {
              const t = document.body ? (document.body.innerText || '') : '';
              const re = new RegExp(
                'PRACTICE\\\\s*/\\\\s*CONCERT\\\\s*KEY\\\\s*\\\\n\\\\s*' + label.replace(' ', '\\\\s+'),
                'i'
              );
              return re.test(t);
            }""",
            arg=expect,
            timeout=12_000,
        )
    except Exception:
        pass
    wait_idle(page, 1500)
    return bool(ok and _card_ok())

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8530"
OUT = Path(__file__).resolve().parent / "evidence-creative-backing"
OUT.mkdir(parents=True, exist_ok=True)
PREFIX = "core-key-"


def _git() -> dict[str, str]:
    root = Path(__file__).resolve().parents[1]

    def run(args: list[str]) -> str:
        return subprocess.check_output(args, cwd=str(root), text=True).strip()

    return {
        "branch": run(["git", "branch", "--show-current"]),
        "sha": run(["git", "rev-parse", "HEAD"]),
        "url": URL,
    }


def shot(page: Page, name: str) -> tuple[str, str]:
    stem = f"{PREFIX}{name}"
    page.screenshot(path=str(OUT / f"{stem}.png"), full_page=True)
    body = page.inner_text("body") or ""
    side = ""
    try:
        expand_sidebar(page)
        side = page.inner_text('[data-testid="stSidebar"]') or ""
    except Exception:
        side = ""
    (OUT / f"{stem}.txt").write_text(
        f"=== SIDEBAR ===\n{side[:8000]}\n\n=== BODY ===\n{body[:16000]}",
        encoding="utf-8",
    )
    return side, body


def _norm_label(text: str) -> str:
    t = (text or "").lower().replace("♯", "#").replace("♭", "b")
    t = re.sub(r"\s+", " ", t).strip()
    return t


def sidebar_pk_token(side: str) -> str:
    """Best-effort token from sidebar Practice / Concert Key control text."""
    blob = side or ""
    m = re.search(
        r"Practice\s*/\s*Concert Key\s*\n?\s*([A-G](?:#|b)?m?)\b",
        blob,
        flags=re.I,
    )
    if m:
        return m.group(1).strip()
    # Fallback: last short key-like token near the label.
    idx = blob.lower().find("practice / concert key")
    if idx >= 0:
        window = blob[idx : idx + 120]
        keys = re.findall(r"\b([A-G](?:#|b)?m?)\b", window)
        if keys:
            return keys[-1]
    return ""


def card_practice_label(body: str) -> str:
    """Human Practice Key label on the active song card ('D minor', 'G major')."""
    blob = body or ""
    # Songs card badge block (preferred — never confuse with Original Key).
    m = re.search(
        r"PRACTICE\s*/\s*CONCERT\s*KEY\s*\n\s*([A-G](?:#|b)?)\s+(major|minor)",
        blob,
        flags=re.I,
    )
    if m:
        return f"{m.group(1).strip()} {m.group(2).strip().lower()}"
    m = re.search(
        r"Practice\s*/\s*Concert\s*Key\s*[:\n]\s*([A-G](?:#|b)?(?:\s*(?:major|minor))?)",
        blob,
        flags=re.I,
    )
    if m:
        return m.group(1).strip()
    m = re.search(
        r"Practice\s*Key\s*[:\n]\s*([A-G](?:#|b)?(?:\s*(?:major|minor))?)",
        blob,
        flags=re.I,
    )
    if m:
        return m.group(1).strip()
    return ""


def token_to_label(token: str) -> str:
    tok = str(token or "").strip()
    if not tok:
        return ""
    if tok.endswith("m") and not tok.endswith("dim"):
        return f"{tok[:-1]} minor"
    return f"{tok} major"


def labels_agree(side_tok: str, card_label: str, expect_tok: str) -> bool:
    expect = _norm_label(token_to_label(expect_tok))
    card_l = _norm_label(card_label)
    if not expect or not card_l:
        return False
    if expect not in card_l and card_l not in expect:
        if "minor" in expect and "major" in card_l and "minor" not in card_l:
            return False
        if "major" in expect and "minor" in card_l:
            return False
        if expect.split()[0] not in card_l:
            return False
    # Sidebar Baseweb often omits the live value from innerText — card is required.
    if side_tok:
        if _norm_label(expect_tok) not in _norm_label(side_tok) and expect not in _norm_label(
            token_to_label(side_tok)
        ):
            return False
    return True


def assert_coherent(page: Page, name: str, expect_tok: str, notes: list[str]) -> bool:
    wait_idle(page, 2000)
    side, body = shot(page, name)
    side_tok = sidebar_pk_token(side)
    card = card_practice_label(body)
    expect_minor = expect_tok.endswith("m") and len(expect_tok) > 1
    ok_card = _norm_label(token_to_label(expect_tok)) in _norm_label(card) or (
        expect_tok.lower() in _norm_label(card).replace(" ", "")
    )
    if card:
        if expect_minor and "major" in _norm_label(card) and "minor" not in _norm_label(card):
            ok_card = False
        if (not expect_minor) and "minor" in _norm_label(card):
            ok_card = False
    ok_side = True
    if side_tok:
        ok_side = side_tok.lower() == expect_tok.lower() or expect_tok.lower() in _norm_label(
            side
        )
    ok = bool(ok_card and ok_side and labels_agree(side_tok, card, expect_tok))
    notes.append(
        f"{name}: expect={expect_tok} side={side_tok!r} card={card!r} ok_side={ok_side} ok_card={ok_card} PASS={ok}"
    )
    return ok


def main() -> int:
    meta = _git()
    notes: list[str] = [json.dumps(meta)]
    results: dict[str, bool] = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.goto(URL, wait_until="domcontentloaded", timeout=120000)
        wait_idle(page, 4000)

        click_nav(page, "Songs")
        wait_idle(page, 2500)

        # --- Shape of You (minor) ---
        ok_pick = pick_song(page, notes, "Shape of You", "Pop")
        notes.append(f"pick_shape={ok_pick}")
        results["shape_pick"] = bool(ok_pick)
        wait_idle(page, 3000)

        # Fresh activation: Bm preferred; sticky Dm still must be minor + coherent.
        wait_idle(page, 2500)
        side0, body0 = shot(page, "shape-fresh-probe")
        tok0 = sidebar_pk_token(side0)
        expect_fresh = "Bm" if tok0.upper() in {"", "BM"} else (tok0 if tok0.lower().endswith("m") else "Bm")
        if expect_fresh.upper() == "BM":
            expect_fresh = "Bm"
        results["shape_fresh"] = assert_coherent(page, "shape-fresh", expect_fresh, notes)
        # Force known sticky then exercise Dm ↔ Bm.
        results["shape_to_dm"] = set_songs_practice_key(page, "Dm") and assert_coherent(
            page, "shape-dm", "Dm", notes
        )
        results["shape_back_bm"] = set_songs_practice_key(page, "Bm") and assert_coherent(
            page, "shape-bm", "Bm", notes
        )
        results["shape_dm_again"] = set_songs_practice_key(page, "Dm") and assert_coherent(
            page, "shape-dm2", "Dm", notes
        )

        # --- Perfect (major) ---
        ok_perf = pick_song(page, notes, "Perfect", "Pop")
        notes.append(f"pick_perfect={ok_perf}")
        results["perfect_pick"] = bool(ok_perf)
        wait_idle(page, 3000)
        results["perfect_fresh"] = assert_coherent(page, "perfect-fresh", "G", notes)
        results["perfect_to_a"] = set_songs_practice_key(page, "A") and assert_coherent(
            page, "perfect-a", "A", notes
        )

        # Reactivate Shape — must not inherit Perfect major sticky as mode.
        ok_shape2 = pick_song(page, notes, "Shape of You", "Pop")
        notes.append(f"repick_shape={ok_shape2}")
        wait_idle(page, 3000)
        side, body = shot(page, "shape-reactivate")
        card = card_practice_label(body)
        # Must be minor mode for Shape working state (Bm or prior Dm sticky).
        mode_ok = "minor" in _norm_label(card) or sidebar_pk_token(side).lower().endswith("m")
        results["shape_reactivate_minor"] = bool(mode_ok)
        notes.append(
            f"shape_reactivate: side={sidebar_pk_token(side)!r} card={card!r} minor_ok={mode_ok}"
        )

        browser.close()

    summary = {
        "meta": meta,
        "results": results,
        "notes": notes,
        "all_pass": all(results.values()),
    }
    (OUT / f"{PREFIX}summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (OUT / f"{PREFIX}summary.txt").write_text(
        "\n".join(notes + ["", f"ALL_PASS={summary['all_pass']}", json.dumps(results, indent=2)]),
        encoding="utf-8",
    )
    print(json.dumps(results, indent=2))
    print(f"ALL_PASS={summary['all_pass']}")
    return 0 if summary["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
