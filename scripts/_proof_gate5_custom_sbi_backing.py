"""Focused gate 5/5b/5c: Custom SBI Backing PK must be Trial D, not Shape Dm."""
from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8521"
sys.argv = [sys.argv[0], URL]

from _walk_ownership_audit_full import (  # noqa: E402
    build_trial_song,
    open_fresh,
    rendered_em_em_d_d,
    shot,
)
from _walk_custom_practice_key import (  # noqa: E402
    goto_custom,
    pk_val,
    set_practice_key as set_custom_pk,
)
from _walk_pass8_live import set_practice_key as set_sidebar_pk  # noqa: E402
from _walk_reboot_persistence_ai_p19 import open_sbi_custom_source, settle  # noqa: E402
from walk_creative_backing_matrix import (  # noqa: E402
    click_button_has,
    click_nav,
    click_open_backing_studio,
)
from walk_guitar_shape_key import pick_song  # noqa: E402

PREFIX = "gate5-focus"
OUT = SCRIPTS / "evidence-creative-backing"


def is_token(s: str, *opts: str) -> bool:
    t = (s or "").strip().lower().replace("♭", "b").replace("♯", "#")
    for o in opts:
        if t == o.lower() or t.startswith(o.lower() + " "):
            return True
    return False


def is_d_major(s: str) -> bool:
    return is_token(s, "D", "D major") and not is_token(s, "Dm", "D minor")


def is_dm(s: str) -> bool:
    return is_token(s, "Dm", "D minor")


def main() -> int:
    notes: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = open_fresh(browser)
        # Seed Shape Dm so bleed is detectable.
        click_nav(page, "Songs")
        settle(page, 2)
        pick_song(page, notes, "Shape of You", "Pop")
        settle(page, 2)
        set_sidebar_pk(page, "D minor") or set_sidebar_pk(page, "Dm")
        settle(page, 2)
        shape_seed = pk_val(page)
        notes.append(f"shape_seed={shape_seed!r}")

        build_trial_song(page, notes)
        settle(page, 2)
        set_custom_pk(page, "D") or set_sidebar_pk(page, "D")
        settle(page, 2)

        open_sbi_custom_source(page, notes)
        settle(page, 3)
        sbi_pk = pk_val(page)
        notes.append(f"sbi_pk={sbi_pk!r}")

        opened = click_open_backing_studio(page, notes, "g5") or click_button_has(
            page, r"Open in Backing"
        )
        settle(page, 5)
        # Do NOT force D first — product must land on Custom sticky/home alone.
        body = shot(page, f"{PREFIX}-05-backing")
        pk0 = pk_val(page)
        specialized = "SBI Custom" in body
        prog = rendered_em_em_d_d(body) or bool(
            __import__("re").search(
                r"Progression:\s*[^\n]*Em\s*[–\-]\s*Em\s*[–\-]\s*D\s*[–\-]\s*D", body
            )
        )
        g5 = bool(opened) and specialized and prog and is_d_major(pk0)
        notes.append(f"5 open={opened} specialized={specialized} pk={pk0!r} prog={prog} -> {g5}")

        set_sidebar_pk(page, "E") or set_custom_pk(page, "E")
        settle(page, 3)
        pk_e = pk_val(page)
        g5b = is_token(pk_e, "E", "E major")
        shot(page, f"{PREFIX}-05b-e")
        notes.append(f"5b pk={pk_e!r} -> {g5b}")

        click_button_has(page, r"Return to Creative") or True
        settle(page, 2)
        click_nav(page, "Songs")
        settle(page, 2)
        pick_song(page, notes, "Shape of You", "Pop")
        settle(page, 2)
        pk_shape = pk_val(page)
        g5c = is_dm(pk_shape)
        shot(page, f"{PREFIX}-05c-shape")
        notes.append(f"5c pk={pk_shape!r} -> {g5c}")
        browser.close()

    out = OUT / "gate5-focus-summary.txt"
    lines = notes + [
        f"PASS={sum([g5, g5b, g5c])}/3",
        f"5={g5} 5b={g5b} 5c={g5c}",
    ]
    out.write_text("\n".join(lines), encoding="utf-8")
    try:
        print("\n".join(lines))
    except UnicodeEncodeError:
        print("\n".join(lines).encode("ascii", "replace").decode("ascii"))
    return 0 if g5 and g5b and g5c else 1


if __name__ == "__main__":
    raise SystemExit(main())
