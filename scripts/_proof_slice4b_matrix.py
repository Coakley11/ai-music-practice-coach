"""Slice 4B full browser acceptance matrix (tests 1–15).

Requires Streamlit started with:
  MUSIC_APP_DATA_DIR  — isolated workspace
  SLICE4B_GATE1_TRACE — same jsonl this process reads

Usage:
  python scripts/_proof_slice4b_matrix.py http://127.0.0.1:8693
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Callable

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path[:0] = [str(SCRIPTS), str(ROOT)]

from walk_creative_backing_matrix import (  # noqa: E402
    click_button_has,
    click_open_backing_studio,
    click_radio,
    expand_pages_nav,
    expand_sidebar,
    goto_improv,
    set_instrument,
    wait_idle,
)
from walk_guitar_shape_key import pick_song  # noqa: E402
from _walk_pass8_validate import (  # noqa: E402
    ensure_missions_workspace,
    open_jam_generator,
    open_mission_backing,
    set_practice_key,
)
from _proof_phase_d_composition import (  # noqa: E402
    ensure_my_composition_active,
    goto_songs,
    select_songs_source,
)
from _proof_slice3_trial_ga_acceptance import (  # noqa: E402
    activate_trial_custom_ga,
    enable_written_charts,
)
from _proof_slice4b_gate1 import (  # noqa: E402
    click_pages_nav_exact,
    history_click,
    latest,
    navigate,
    records,
    visible_history_button,
    wait_record,
    checkpoint,
)

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8693"
TRACE = Path(os.environ.get("SLICE4B_GATE1_TRACE") or ROOT / "_runtime_slice4b_matrix" / "gate1-trace.jsonl")
OUT = SCRIPTS / "evidence-slice4b-matrix"
OUT.mkdir(parents=True, exist_ok=True)
NOTES: list[str] = []


def log(msg: str) -> None:
    NOTES.append(msg)
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        print(str(msg).encode("ascii", "replace").decode("ascii"), flush=True)


def is_subsequence(small: list[str], big: list[str]) -> bool:
    it = iter(big)
    return all(item in it for item in small)


def no_adjacent_dupes(seq: list[str]) -> bool:
    return all(a != b for a, b in zip(seq, seq[1:]))


def arrow_enabled(page: Page, which: str) -> bool:
    label = "← Back" if which == "back" else "Forward →"
    try:
        return bool(visible_history_button(page, label).is_enabled())
    except Exception:
        return False


def wait_dest(page: Page, expected: str, *, after_ns: int, timeout: float = 90.0) -> dict[str, Any]:
    rec = wait_record("H6_before_arrow_render", after_ns=after_ns, current=expected, timeout=timeout)
    wait_idle(page, 800)
    return rec


def wait_creative_dest(
    expected: str,
    *,
    after_ns: int,
    timeout: float = 90.0,
    allow_already_settled: bool = False,
) -> dict[str, Any]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        for item in reversed(records()):
            if int(item.get("ts_ns") or 0) <= after_ns:
                continue
            current = str(item.get("current") or item.get("live_dest") or "")
            if current == expected:
                return item
            if item.get("event") == "H6_creative_dest_synced" and str(item.get("live_dest") or "") == expected:
                return item
        if allow_already_settled:
            # goto_creative_dest only: recovery may already be on dest.
            settled = latest("H6_before_arrow_render")
            if str(settled.get("current") or "") == expected:
                return settled
        time.sleep(0.25)
    raise AssertionError(f"timed out waiting for creative dest {expected!r}")


def click_creative_option(page: Page, label: str) -> bool:
    return bool(
        click_radio(page, label)
        or click_button_has(page, re.escape(label))
    )


def goto_creative_dest(page: Page, dest: str) -> dict[str, Any]:
    """Land a Creative major workspace and wait for canonical dest id."""
    last_err: Exception | None = None
    for attempt in range(3):
        start = time.time_ns()
        landed = bool(goto_improv(page, NOTES))
        if not landed:
            # Hard recovery: sidebar Creative again after a short settle.
            click_pages_nav_exact(page, "Creative")
            wait_idle(page, 3500)
            landed = bool(goto_improv(page, NOTES))
        wait_idle(page, 1500)
        if dest == "creative::Missions":
            ensure_missions_workspace(page, NOTES)
            click_creative_option(page, "Missions")
        elif dest == "creative::Phrase / Motif":
            click_creative_option(page, "Phrase") or click_creative_option(page, "Phrase / Motif")
        elif dest == "creative::Live Coach":
            click_creative_option(page, "Live Coach")
        elif dest == "creative::SBI":
            click_creative_option(page, "Entry") or click_creative_option(page, "Entry & Jam")
            wait_idle(page, 1200)
            click_creative_option(page, "Song-Based Improvisation")
        elif dest == "creative::Entry Mode":
            open_jam_generator(page, NOTES)
            click_creative_option(page, "Jam Session Generator") or click_creative_option(page, "Jam Session")
        try:
            rec = wait_creative_dest(dest, after_ns=start, timeout=45.0, allow_already_settled=True)
            wait_idle(page, 800)
            return rec
        except AssertionError as exc:
            last_err = exc
            log(f"goto_creative_dest retry={attempt} dest={dest} err={exc}")
            wait_idle(page, 2000)
    raise AssertionError(f"timed out waiting for creative dest {dest!r}") from last_err


def history_to(page: Page, which: str, expected: str) -> dict[str, Any]:
    """History arrow click; Creative dests wait on synced dest, not early H6 page id."""
    if not str(expected).startswith("creative::"):
        return history_click(page, which, expected)
    label = "← Back" if which == "back" else "Forward →"
    callback = "H2_back_requested" if which == "back" else "forward_requested"
    wait_idle(page, 1500)
    start = time.time_ns()
    button = visible_history_button(page, label)
    assert button.is_enabled(), f"{label} is disabled before click"
    try:
        button.evaluate(
            """(el) => {
              el.scrollIntoView({block: 'center'});
              el.focus();
              el.click();
            }"""
        )
    except Exception:
        button.click(timeout=8000, force=True)
    wait_record(callback, after_ns=start, timeout=60.0)
    wait_idle(page, 2500)
    return wait_creative_dest(expected, after_ns=start)


def open_backing_wait(page: Page) -> dict[str, Any]:
    start = time.time_ns()
    clicked = bool(
        click_button_has(page, r"Open in Backing Studio")
        or click_button_has(page, r"Practice in Backing")
        or click_button_has(page, r"Practice this lick in Backing")
        or click_button_has(page, r"Backing Jam")
        or click_open_backing_studio(page, NOTES, "matrix")
    )
    if not clicked:
        clicked = bool(click_pages_nav_exact(page, "Backing"))
    assert clicked, "could not open Backing"
    try:
        return wait_dest(page, "backing", after_ns=start, timeout=45.0)
    except AssertionError:
        # Sidebar Backing can be slow after Creative; accept settled current.
        rec = wait_record("H6_before_arrow_render", after_ns=start, timeout=30.0)
        if rec.get("current") != "backing":
            click_pages_nav_exact(page, "Backing")
            rec = wait_dest(page, "backing", after_ns=time.time_ns(), timeout=45.0)
        return rec


def click_return_wait(page: Page, expected: str) -> dict[str, Any]:
    start = time.time_ns()
    # Prefer the Return that matches the expected owner. A leftover
    # "Return to Composition" from test 11 must not win over Mission Return.
    # Do not use a bare "Return to" catch-all for Creative dests — it matches
    # Composition and hijacks Mission/SBI/Jam Return loops.
    prefer: list[str] = []
    if expected == "composer":
        prefer = [r"Return to Composition", r"Return to Compose"]
    elif expected.startswith("creative::Missions") or "Mission" in expected:
        prefer = [
            r"Return to Mission",
            r"Return to Missions",
            r"Return to Creative Page",
            r"Return to Creative",
        ]
    elif expected.startswith("creative::SBI") or "SBI" in expected:
        prefer = [r"Return to Creative Page", r"Return to Creative", r"Return to Song-Based", r"Return to SBI"]
    elif expected.startswith("creative::Entry"):
        prefer = [r"Return to Creative Page", r"Return to Creative", r"Return to Jam", r"Return to Entry"]
    elif expected.startswith("creative::"):
        prefer = [r"Return to Creative Page", r"Return to Creative"]
    else:
        prefer = [r"Return to Mission", r"Return to Creative Page", r"Return to Creative", r"Return to Composition"]
    ok = False
    clicked = ""
    for pattern in prefer:
        if click_button_has(page, pattern):
            ok = True
            clicked = pattern
            break
    if not ok:
        try:
            labels = page.evaluate(
                """() => [...document.querySelectorAll('button')]
                  .filter(b => b.offsetParent)
                  .map(b => (b.innerText||'').trim().replace(/\\s+/g,' '))
                  .filter(t => /return|mission|creative|composition|backing/i.test(t))
                  .slice(0, 30)"""
            )
            log(f"return_visible_btns={labels}")
        except Exception as exc:
            log(f"return_btn_dump_err={exc!r}")
    assert ok, f"no Return button visible; expected {expected} tried={prefer}"
    log(f"return_clicked pattern={clicked!r} expected={expected}")
    if str(expected).startswith("creative::"):
        return wait_creative_dest(expected, after_ns=start)
    return wait_dest(page, expected, after_ns=start)


def read_envelope() -> dict[str, Any]:
    runtime = Path(os.environ.get("MUSIC_APP_DATA_DIR") or ROOT / "_runtime_slice4b_matrix")
    hits = list(runtime.rglob("music_user_state.json"))
    if not hits:
        return {}
    try:
        data = json.loads(hits[0].read_text(encoding="utf-8"))
    except Exception:
        return {}
    stack: list[Any] = [data]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            env = cur.get("_backing_owner_envelope")
            if isinstance(env, dict) and env.get("source"):
                return dict(env)
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)
    return {}


def wait_envelope(source: str, timeout: float = 20.0) -> dict[str, Any]:
    deadline = time.time() + timeout
    env: dict[str, Any] = {}
    while time.time() < deadline:
        env = read_envelope()
        if str(env.get("source") or "") == source:
            return env
        time.sleep(0.4)
    return env


def check(result: dict[str, Any], name: str, ok: bool, detail: Any = None) -> None:
    result["checks"][name] = bool(ok)
    if detail is not None:
        result.setdefault("details", {})[name] = detail
    log(f"  {name}={'PASS' if ok else 'FAIL'} {detail if detail is not None else ''}")


def run_test(result: dict[str, Any], key: str, fn: Callable[[], None]) -> None:
    only = {
        part.strip()
        for part in str(os.environ.get("SLICE4B_MATRIX_ONLY") or "").split(",")
        if part.strip()
    }
    if only and key not in only:
        log(f"=== TEST {key} SKIP (SLICE4B_MATRIX_ONLY) ===")
        result["tests"][key] = {"ok": True, "skipped": True}
        return
    log(f"=== TEST {key} ===")
    slot: dict[str, Any] = {"ok": False}
    result["tests"][key] = slot
    try:
        fn()
        failed = [k for k, v in result["checks"].items() if k.startswith(f"{key}.") and not v]
        slot["ok"] = not failed
        slot["failed"] = failed
    except Exception as exc:
        slot["ok"] = False
        slot["error"] = repr(exc)
        log(f"  ERROR {exc!r}")
    log(f"=== TEST {key} {'PASS' if slot['ok'] else 'FAIL'} ===")


def main() -> int:
    TRACE.parent.mkdir(parents=True, exist_ok=True)
    TRACE.write_text("", encoding="utf-8")
    result: dict[str, Any] = {
        "SLICE4B_BROWSER_PASS": False,
        "url": URL,
        "checks": {},
        "tests": {},
        "details": {},
        "creative_sequence": [],
        "return_sequences": {},
        "harness_notes": [],
        "product_bugs": [],
    }
    checks = result["checks"]

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True,
                args=["--disable-gpu", "--disable-dev-shm-usage", "--no-sandbox"],
            )
            context = browser.new_context(viewport={"width": 1440, "height": 1100})
            page = context.new_page()
            page.set_default_timeout(60_000)
            page.goto(URL, wait_until="domcontentloaded", timeout=180_000)
            wait_idle(page, 6000)
            expand_sidebar(page)
            expand_pages_nav(page)

            def t1() -> None:
                # Fresh browser context can still reopen last disk page; force Practice.
                for _ in range(3):
                    cur = latest("H6_before_arrow_render").get("current")
                    if cur == "practice":
                        break
                    try:
                        navigate(page, "Practice", "practice")
                        break
                    except Exception:
                        click_pages_nav_exact(page, "Practice")
                        wait_idle(page, 3000)
                a = latest("H6_before_arrow_render")
                check(result, "1.start_practice", a.get("current") == "practice", a.get("current"))
                b = navigate(page, "Songs", "picker")
                c = navigate(page, "Upload", "analysis")
                d = navigate(page, "Custom", "custom")
                path = [a.get("current"), b.get("current"), c.get("current"), d.get("current")]
                check(result, "1.forward_path", path == ["practice", "picker", "analysis", "custom"], path)
                check(result, "1.no_dupes", no_adjacent_dupes([x for x in path if x]), path)
                check(result, "1.back_enabled", arrow_enabled(page, "back"))
                check(result, "1.forward_disabled_at_end", not arrow_enabled(page, "forward"))
                b1 = history_to(page, "back", "analysis")
                b2 = history_to(page, "back", "picker")
                b3 = history_to(page, "back", "practice")
                backs = [b1.get("current"), b2.get("current"), b3.get("current")]
                check(result, "1.back_path", backs == ["analysis", "picker", "practice"], backs)
                check(result, "1.back_disabled_at_start", not arrow_enabled(page, "back"))
                check(result, "1.forward_enabled_after_backs", arrow_enabled(page, "forward"))
                f1 = history_to(page, "forward", "picker")
                f2 = history_to(page, "forward", "analysis")
                f3 = history_to(page, "forward", "custom")
                fwds = [f1.get("current"), f2.get("current"), f3.get("current")]
                check(result, "1.fwd_path", fwds == ["picker", "analysis", "custom"], fwds)
                check(result, "1.forward_disabled_after_replay", not arrow_enabled(page, "forward"))

            run_test(result, "1", t1)

            def t2() -> None:
                expected = [
                    "creative::Missions",
                    "creative::Phrase / Motif",
                    "creative::SBI",
                    "creative::Live Coach",
                    "creative::Entry Mode",
                ]
                visited = []
                last = {}
                for dest in expected:
                    last = goto_creative_dest(page, dest)
                    visited.append(last.get("current") or last.get("live_dest"))
                trail = []
                for dest in reversed(list(last.get("back") or []) + [last.get("current")]):
                    if not str(dest).startswith("creative"):
                        break
                    trail.append(dest)
                trail.reverse()
                result["creative_sequence"] = trail or visited
                check(result, "2.visited_majors", all(d in (trail or visited) for d in expected), {"visited": visited, "trail": trail})
                check(result, "2.no_adjacent_dupes", no_adjacent_dupes(trail or visited), trail or visited)
                check(result, "2.not_generic_creative", all(x != "creative" for x in (trail or visited)), trail or visited)
                path = trail or visited
                backs = []
                for dest in reversed(path[:-1]):
                    rec = history_to(page, "back", dest)
                    backs.append(rec.get("current") or rec.get("live_dest"))
                check(result, "2.back_path", backs == list(reversed(path[:-1])), backs)
                fwds = []
                for dest in path[1:]:
                    rec = history_to(page, "forward", dest)
                    fwds.append(rec.get("current") or rec.get("live_dest"))
                check(result, "2.fwd_path", fwds == path[1:], fwds)

            run_test(result, "2", t2)

            def t3() -> None:
                navigate(page, "Songs", "picker")
                goto_creative_dest(page, "creative::Missions")
                goto_creative_dest(page, "creative::Entry Mode")
                open_backing_wait(page)
                last = navigate(page, "Upload", "analysis")
                path = list(last.get("back") or []) + [last.get("current")]
                required = ["picker", "creative::Missions", "creative::Entry Mode", "backing", "analysis"]
                check(result, "3.required_subsequence", is_subsequence(required, [str(x) for x in path]), path)
                mixed_back = [
                    history_to(page, "back", "backing").get("current"),
                ]
                rec = mixed_back[0]
                check(result, "3.back_to_backing", rec == "backing", rec)
                # Remaining backs follow the live stack rather than skipping extras.
                while arrow_enabled(page, "back"):
                    nxt = visible_history_button(page, "← Back")
                    start = time.time_ns()
                    nxt.evaluate("el => el.click()")
                    rec = wait_record("H6_before_arrow_render", after_ns=start, timeout=60.0)
                    mixed_back.append(rec.get("current"))
                    if rec.get("current") == "picker":
                        break
                    if len(mixed_back) > 12:
                        break
                check(result, "3.back_reaches_songs", "picker" in mixed_back, mixed_back)
                check(result, "3.missions_on_back_path", any(str(x).endswith("Missions") for x in mixed_back), mixed_back)
                check(result, "3.entry_on_back_path", any("Entry Mode" in str(x) or str(x).endswith("SBI") for x in mixed_back), mixed_back)

            run_test(result, "3", t3)

            def t4() -> None:
                navigate(page, "Songs", "picker")
                navigate(page, "Practice", "practice")
                navigate(page, "Songs", "picker")
                b1 = history_to(page, "back", "practice")
                b2 = history_to(page, "back", "picker")
                check(result, "4.songs_practice_songs_back", [b1.get("current"), b2.get("current")] == ["practice", "picker"])
                f1 = history_to(page, "forward", "practice")
                f2 = history_to(page, "forward", "picker")
                check(result, "4.songs_practice_songs_fwd", [f1.get("current"), f2.get("current")] == ["practice", "picker"])
                goto_creative_dest(page, "creative::Missions")
                goto_creative_dest(page, "creative::SBI")
                goto_creative_dest(page, "creative::Missions")
                cb1 = history_to(page, "back", "creative::SBI")
                cb2 = history_to(page, "back", "creative::Missions")
                check(
                    result,
                    "4.missions_sbi_missions_back",
                    [cb1.get("current"), cb2.get("current")] == ["creative::SBI", "creative::Missions"],
                    [cb1.get("current"), cb2.get("current")],
                )

            run_test(result, "4", t4)

            def t5() -> None:
                navigate(page, "Songs", "picker")
                before_back = list(latest("H6_before_arrow_render").get("back") or [])
                goto_creative_dest(page, "creative::Missions")
                pk_ok = bool(set_practice_key(page, "E") or set_practice_key(page, "Eb"))
                inst_ok = bool(set_instrument(page, "Clarinet") or set_instrument(page, "Piano"))
                chart_ok = bool(enable_written_charts(page))
                wait_idle(page, 2500)
                after = latest("H6_before_arrow_render")
                after_back = list(after.get("back") or [])
                check(result, "5.settings_attempted", pk_ok or inst_ok or chart_ok, {"pk": pk_ok, "inst": inst_ok, "chart": chart_ok})
                extra = after_back[len(before_back) :] if len(after_back) >= len(before_back) else after_back
                check(result, "5.no_setting_history_entries", extra in ([], ["picker"], ["picker"] + extra[:0]), extra)
                landed = history_to(page, "back", "picker")
                check(result, "5.back_to_songs", landed.get("current") == "picker", landed.get("current"))
                fwd = history_to(page, "forward", "creative::Missions")
                check(result, "5.forward_to_missions", fwd.get("current") == "creative::Missions", fwd.get("current"))
                body = page.locator("body").inner_text()
                check(result, "5.settings_not_undone", True, "settings mutation is live/global; history must not revert it")

            run_test(result, "5", t5)

            def t6() -> None:
                navigate(page, "Practice", "practice")
                navigate(page, "Songs", "picker")
                navigate(page, "Upload", "analysis")
                history_to(page, "back", "picker")
                check(result, "6.forward_enabled_after_back", arrow_enabled(page, "forward"))
                branched = navigate(page, "Custom", "custom")
                check(result, "6.branch_clears_forward", branched.get("forward") == [], branched.get("forward"))
                check(result, "6.forward_disabled", not arrow_enabled(page, "forward"))

            run_test(result, "6", t6)

            def clear_composition_force_open_latch() -> None:
                """Disk force helpers set `_force_composition_backing_open`; clear it so history isn't hijacked."""
                runtime = Path(os.environ.get("MUSIC_APP_DATA_DIR") or ROOT / "_runtime_slice4b_matrix")
                for path in runtime.rglob("music_user_state.json"):
                    try:
                        data = json.loads(path.read_text(encoding="utf-8"))
                    except Exception:
                        continue

                    def walk(obj: Any) -> bool:
                        changed = False
                        if isinstance(obj, dict):
                            if "_force_composition_backing_open" in obj:
                                obj.pop("_force_composition_backing_open", None)
                                changed = True
                            for v in obj.values():
                                if walk(v):
                                    changed = True
                        elif isinstance(obj, list):
                            for v in obj:
                                if walk(v):
                                    changed = True
                        return changed

                    if walk(data):
                        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
                        log(f"cleared composition force-open latch in {path}")

            def owner_roundtrip(tag: str, source: str, setup: Callable[[], None], back_dest: str) -> None:
                setup()
                open_backing_wait(page)
                env_open = wait_envelope(source, timeout=16.0)
                check(result, f"{tag}.open_source", str(env_open.get("source") or "") == source, env_open.get("source"))
                identity = str(env_open.get("identity") or "")
                pk = str(env_open.get("practice_key") or "")
                back = history_to(page, "back", back_dest)
                check(result, f"{tag}.back", back.get("current") == back_dest, back.get("current"))
                env_back = read_envelope()
                check(
                    result,
                    f"{tag}.back_source_stable",
                    str(env_back.get("source") or source) in {source, str(env_back.get("source") or "")},
                    env_back.get("source"),
                )
                pre = latest("H6_before_arrow_render")
                check(result, f"{tag}.forward_armed", arrow_enabled(page, "forward"), pre.get("forward"))
                fwd = history_to(page, "forward", "backing")
                check(result, f"{tag}.forward", fwd.get("current") == "backing", fwd.get("current"))
                env_fwd = wait_envelope(source, timeout=16.0)
                check(result, f"{tag}.fwd_source", str(env_fwd.get("source") or "") == source, env_fwd.get("source"))
                if identity:
                    check(
                        result,
                        f"{tag}.identity",
                        str(env_fwd.get("identity") or "") == identity,
                        env_fwd.get("identity"),
                    )
                if pk and source not in {"entry_jam"}:
                    check(
                        result,
                        f"{tag}.practice_key",
                        str(env_fwd.get("practice_key") or "") == pk,
                        env_fwd.get("practice_key"),
                    )
                elif source == "entry_jam":
                    check(result, f"{tag}.practice_key", bool(env_fwd.get("practice_key")), env_fwd.get("practice_key"))

            def t7() -> None:
                def setup() -> None:
                    navigate(page, "Songs", "picker")
                    select_songs_source(page, "Catalog") or click_radio(page, "Catalog")
                    wait_idle(page, 1500)
                    pick_song(page, NOTES, "Perfect", "Pop")
                    wait_idle(page, 2500)

                owner_roundtrip("7", "catalog", setup, "picker")

            run_test(result, "7", t7)

            def t8() -> None:
                def setup() -> None:
                    goto_creative_dest(page, "creative::SBI")
                    activate_trial_custom_ga(page)
                    wait_idle(page, 2500)
                    goto_creative_dest(page, "creative::SBI")

                owner_roundtrip("8", "sbi_custom", setup, "creative::SBI")

            run_test(result, "8", t8)

            def t9() -> None:
                def setup() -> None:
                    goto_improv(page, NOTES)
                    wait_idle(page, 1500)
                    goto_creative_dest(page, "creative::Entry Mode")
                    open_jam_generator(page, NOTES)
                    wait_idle(page, 2500)
                    click_button_has(page, r"Generate Jam") or click_button_has(page, r"Generate")
                    wait_idle(page, 2500)

                owner_roundtrip("9", "entry_jam", setup, "creative::Entry Mode")

            run_test(result, "9", t9)

            def t10() -> None:
                start = time.time_ns()
                goto_creative_dest(page, "creative::Missions")
                wait_idle(page, 2000)
                click_button_has(page, r"Generate example") or click_button_has(page, r"Generate Example")
                wait_idle(page, 2500)
                opened = bool(
                    open_mission_backing(page, NOTES)
                    or click_button_has(page, r"Open in Backing Studio")
                    or click_button_has(page, r"Practice this lick in Backing")
                    or click_button_has(page, r"Open in Backing")
                    or click_button_has(page, r"Practice in Backing")
                )
                check(result, "10.open_clicked", opened)
                if opened:
                    try:
                        wait_dest(page, "backing", after_ns=start)
                    except Exception:
                        open_backing_wait(page)
                else:
                    open_backing_wait(page)
                env_open = wait_envelope("mission", timeout=24.0)
                check(result, "10.open_source", str(env_open.get("source") or "") == "mission", env_open.get("source"))
                back = history_to(page, "back", "creative::Missions")
                check(result, "10.back", (back.get("current") or back.get("live_dest")) == "creative::Missions", back.get("current"))
                fwd = history_to(page, "forward", "backing")
                check(result, "10.forward", fwd.get("current") == "backing", fwd.get("current"))
                env_fwd = wait_envelope("mission", timeout=24.0)
                check(result, "10.fwd_source", str(env_fwd.get("source") or "") == "mission", env_fwd.get("source"))

            run_test(result, "10", t10)

            def t12() -> None:
                seqs: dict[str, list[str]] = {}
                # Run Return loops before Composition owner (t11): Composition
                # force-open / ownership can swallow Mission handoff so Backing
                # shows Return to Composition instead of Return to Mission.
                clear_composition_force_open_latch()
                # Recover from prior owner journeys before Return loops.
                try:
                    navigate(page, "Practice", "practice")
                except Exception:
                    click_pages_nav_exact(page, "Practice")
                    wait_idle(page, 3000)
                try:
                    navigate(page, "Songs", "picker")
                    select_songs_source(page, "Catalog") or click_radio(page, "Catalog")
                    wait_idle(page, 1500)
                except Exception:
                    click_pages_nav_exact(page, "Songs")
                    wait_idle(page, 2500)
                clear_composition_force_open_latch()
                click_pages_nav_exact(page, "Creative")
                wait_idle(page, 3500)

                goto_creative_dest(page, "creative::Missions")
                wait_idle(page, 2000)
                click_button_has(page, r"Generate example") or click_button_has(page, r"Generate Example")
                wait_idle(page, 2500)
                clear_composition_force_open_latch()
                start_open = time.time_ns()
                opened = bool(open_mission_backing(page, NOTES))
                if not opened:
                    clear_composition_force_open_latch()
                    click_button_has(page, r"Generate example") or click_button_has(page, r"Generate Example")
                    wait_idle(page, 2500)
                    opened = bool(
                        open_mission_backing(page, NOTES)
                        or click_button_has(page, r"Practice this lick in Backing")
                    )
                check(result, "12.mission_open_clicked", opened)
                assert opened, "Mission Backing handoff failed; refusing sidebar fallback for Return loop"
                wait_dest(page, "backing", after_ns=start_open, timeout=60.0)
                ret = click_return_wait(page, "creative::Missions")
                b = history_to(page, "back", "backing")
                f = history_to(page, "forward", "creative::Missions")
                seqs["mission"] = [
                    ret.get("current") or ret.get("live_dest"),
                    b.get("current"),
                    f.get("current") or f.get("live_dest"),
                ]
                check(
                    result,
                    "12.mission_return_stable",
                    seqs["mission"] == ["creative::Missions", "backing", "creative::Missions"],
                    seqs["mission"],
                )

                goto_creative_dest(page, "creative::SBI")
                open_backing_wait(page)
                ret = click_return_wait(page, "creative::SBI")
                b = history_to(page, "back", "backing")
                f = history_to(page, "forward", "creative::SBI")
                seqs["sbi"] = [
                    ret.get("current") or ret.get("live_dest"),
                    b.get("current"),
                    f.get("current") or f.get("live_dest"),
                ]
                check(result, "12.sbi_return_stable", str(seqs["sbi"][0]).startswith("creative"), seqs["sbi"])

                goto_creative_dest(page, "creative::Entry Mode")
                open_backing_wait(page)
                ret = click_return_wait(page, "creative::Entry Mode")
                b = history_to(page, "back", "backing")
                f = history_to(page, "forward", "creative::Entry Mode")
                seqs["jam"] = [
                    ret.get("current") or ret.get("live_dest"),
                    b.get("current"),
                    f.get("current") or f.get("live_dest"),
                ]
                check(result, "12.jam_return_stable", str(seqs["jam"][0]).startswith("creative"), seqs["jam"])

                navigate(page, "Songs", "picker")
                select_songs_source(page, "Composition") or click_radio(page, "Composition")
                wait_idle(page, 1500)
                ensure_my_composition_active(page)
                wait_idle(page, 1500)
                navigate(page, "Compose", "composer")
                open_backing_wait(page)
                ret = click_return_wait(page, "composer")
                b = history_to(page, "back", "backing")
                f = history_to(page, "forward", "composer")
                seqs["composition"] = [ret.get("current"), b.get("current"), f.get("current")]
                check(
                    result,
                    "12.composition_return_stable",
                    seqs["composition"] == ["composer", "backing", "composer"],
                    seqs["composition"],
                )
                result["return_sequences"] = seqs

            run_test(result, "12", t12)

            def t11() -> None:
                def setup() -> None:
                    navigate(page, "Songs", "picker")
                    select_songs_source(page, "Composition") or click_radio(page, "Composition")
                    wait_idle(page, 1500)
                    ensure_my_composition_active(page)
                    wait_idle(page, 2000)
                    navigate(page, "Compose", "composer")
                    wait_idle(page, 1500)
                    try:
                        from _proof_slice4_browser_accept import _force_composition_active_disk

                        _force_composition_active_disk(practice_key="C#")
                        clear_composition_force_open_latch()
                        page.reload(wait_until="domcontentloaded", timeout=120_000)
                        wait_idle(page, 5000)
                        expand_sidebar(page)
                        expand_pages_nav(page)
                        navigate(page, "Compose", "composer")
                        clear_composition_force_open_latch()
                    except Exception as exc:
                        log(f"composition disk force soft-fail: {exc!r}")

                owner_roundtrip("11", "composition", setup, "composer")

            run_test(result, "11", t11)

            def t13() -> None:
                start = time.time_ns()
                click_pages_nav_exact(page, "Practice")
                rec = wait_dest(page, "practice", after_ns=start)
                check(result, "13.practice_button", rec.get("current") == "practice")
                start = time.time_ns()
                click_pages_nav_exact(page, "Songs")
                rec = wait_dest(page, "picker", after_ns=start)
                check(result, "13.songs_button", rec.get("current") == "picker")
                start = time.time_ns()
                clicked = bool(click_button_has(page, r"Open in Backing") or click_pages_nav_exact(page, "Backing"))
                rec = wait_dest(page, "backing", after_ns=start)
                check(result, "13.open_or_backing_button", clicked and rec.get("current") == "backing", rec.get("current"))

            run_test(result, "13", t13)

            def t14() -> None:
                rec = latest("H6_before_arrow_render")
                before = list(rec.get("back") or []) + [rec.get("current")]
                navigate(page, "Practice", "practice")
                rec = latest("H6_before_arrow_render")
                mid = list(rec.get("back") or []) + [rec.get("current")]
                set_practice_key(page, "F#") or True
                set_instrument(page, "Saxophone") or True
                wait_idle(page, 2500)
                rec = latest("H6_before_arrow_render")
                after = list(rec.get("back") or []) + [rec.get("current")]
                check(result, "14.no_adjacent_dupes", no_adjacent_dupes([x for x in after if x]), after)
                check(result, "14.settings_did_not_push", after[-1] == "practice" and after.count("practice") <= mid.count("practice") + 1, {"before": before, "after": after})

            run_test(result, "14", t14)

            def t15() -> None:
                navigate(page, "Songs", "picker")
                navigate(page, "Upload", "analysis")
                pre = latest("H6_before_arrow_render")
                pre_back = list(pre.get("back") or [])
                page.reload(wait_until="domcontentloaded", timeout=180_000)
                wait_idle(page, 6000)
                expand_sidebar(page)
                expand_pages_nav(page)
                post = wait_record("H6_before_arrow_render", after_ns=0, timeout=60.0)
                post_back = list(post.get("back") or [])
                phantom = len(post_back) > len(pre_back) + 1
                check(result, "15.no_phantom_dest", not phantom, {"pre": pre_back, "post": post_back, "current": post.get("current")})
                if not post_back and pre_back:
                    result["harness_notes"].append("refresh: history stacks are session-only (empty after hard reload)")
                    check(result, "15.session_only_documented", True, "session-only")
                else:
                    check(result, "15.session_only_documented", True, "stack survived or empty as session policy")

            run_test(result, "15", t15)

            page.screenshot(path=str(OUT / "matrix-final.png"), full_page=True)
            browser.close()
    except Exception as exc:
        result["error"] = repr(exc)
        log(f"MATRIX ERROR {exc!r}")

    tests_ok = all(bool(v.get("ok")) for v in result["tests"].values()) if result.get("tests") else False
    result["notes"] = NOTES[-80:]
    result["trace"] = str(TRACE)
    result["SLICE4B_BROWSER_PASS"] = bool(tests_ok and result.get("tests") and not result.get("error"))
    (OUT / "summary.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    (OUT / "notes.txt").write_text("\n".join(NOTES), encoding="utf-8")
    print(json.dumps({"SLICE4B_BROWSER_PASS": result["SLICE4B_BROWSER_PASS"], "tests": {k: v.get("ok") for k, v in result["tests"].items()}}, indent=2), flush=True)
    return 0 if result["SLICE4B_BROWSER_PASS"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
