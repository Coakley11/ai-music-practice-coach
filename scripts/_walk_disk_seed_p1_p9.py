"""Disk-seed + reboot proofs for nested persistence (SBI Custom, P1–P9).

Usage:
  python scripts/_walk_disk_seed_p1_p9.py http://127.0.0.1:8512
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _walk_reboot_persistence_ai_p19 import (  # noqa: E402
    URL,
    click_button_has,
    click_nav,
    click_radio,
    creative_tab,
    disk_creative_slice,
    disk_state_path,
    disk_studio_page,
    enable_guitar_capo,
    goto_custom,
    goto_improv,
    has_any,
    open_fresh,
    page_family,
    reboot_server,
    seed_trial_song_last_custom,
    set_instrument,
    set_shape_tonic,
    set_sidebar_pk,
    settle,
    shot,
    wait_idle,
)

OUT = Path(__file__).resolve().parent / "evidence-creative-backing"
OUT.mkdir(parents=True, exist_ok=True)


def row(gate: str, ok: bool, detail: str, internal: str = "") -> dict:
    return {
        "gate": gate,
        "ok": bool(ok),
        "detail": detail,
        "internal": internal,
        "verdict": "PASS" if ok else "FAIL",
    }


def side(page: Page) -> str:
    try:
        return page.inner_text('[data-testid="stSidebar"]') or ""
    except Exception:
        return ""


def load_blob() -> tuple[Path, dict]:
    path = disk_state_path()
    return path, json.loads(path.read_text(encoding="utf-8"))


def stamp_page(st: dict, page: str) -> None:
    st["studio_page"] = page
    for key in (
        "studio_nav_state",
        "music_workspace_state",
        "practice_workspace_state",
        "core",
        "session",
    ):
        node = st.get(key)
        if not isinstance(node, dict):
            node = {}
            st[key] = node
        node["studio_page"] = page
        if key in ("studio_nav_state", "music_workspace_state", "practice_workspace_state"):
            node["page"] = page
        if key == "music_workspace_state":
            nested = node.get("practice_workspace_state")
            if isinstance(nested, dict):
                nested["studio_page"] = page
                nested["page"] = page


def merge_creative(st: dict, fields: dict) -> None:
    for k, v in fields.items():
        st[k] = v
    cw = st.get("creative_workspace_state")
    if not isinstance(cw, dict):
        cw = {}
        st["creative_workspace_state"] = cw
    cw.update(fields)
    sess = st.get("session")
    if isinstance(sess, dict):
        for k, v in fields.items():
            sess[k] = v


def wait_body(page: Page, *needles: str, timeout: float = 90.0) -> str:
    deadline = time.time() + timeout
    body = ""
    while time.time() < deadline:
        settle(page, 3)
        body = page.inner_text("body") or ""
        low = body.lower()
        if len(body) > 800 and any(n.lower() in low for n in needles):
            return body
    return body


def reboot_open(browser):
    reboot_server()
    return open_fresh(browser)


def save_blob(path: Path, blob: dict) -> None:
    path.write_text(json.dumps(blob, indent=2), encoding="utf-8")


def main() -> int:
    notes: list[str] = []
    rows: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        page = open_fresh(browser)
        seed_trial_song_last_custom(page, notes)
        settle(page, 2)
        page.context.close()

        # SBI Custom
        path, blob = load_blob()
        st = blob.setdefault("state", {})
        stamp_page(st, "creative")
        merge_creative(
            st,
            {
                "improv_entry_mode": "Song-Based Improvisation",
                "improv_intelligence_tab": "Entry & Jam",
                "creative_improv_intelligence_tab": "Entry & Jam",
                "improv_song_source": "Custom progression",
                "sbi_preview_source": "Custom progression",
            },
        )
        save_blob(path, blob)
        page = reboot_open(browser)
        wait_body(page, "entry & jam", "improvisation lab", "song-based", "custom progression")
        body = shot(page, "seed2-sbi-custom-post")
        fam, tab, disk = page_family(body), creative_tab(body), disk_studio_page()
        sl = disk_creative_slice()
        src = str(sl.get("sbi_preview_source") or sl.get("improv_song_source") or "")
        ok = fam == "creative" and disk == "creative" and "Custom" in src and has_any(body, "Trial Song")
        rows.append(row("SBI_CUSTOM", ok, f"fam={fam} tab={tab} src={src!r} trial={has_any(body,'Trial Song')}", disk))
        print("GATE SBI_CUSTOM", rows[-1], flush=True)
        page.context.close()

        # P1 Mission
        path, blob = load_blob()
        st = blob.setdefault("state", {})
        stamp_page(st, "creative")
        merge_creative(
            st,
            {
                "improv_intelligence_tab": "Missions",
                "creative_improv_intelligence_tab": "Missions",
                "improv_active_mission": "Improvise using only chord tones",
                "improv_mission_pick": "Improvise using only chord tones",
                "ii_selected_section": "Verse 1",
                "ii_selected_chord": "F#m",
                "ii_selected_chord_label": "Verse 1 · F#m",
            },
        )
        for node_key in ("music_workspace_state", "core", "session"):
            node = st.get(node_key)
            if isinstance(node, dict):
                node["display_key"] = "Ab"
        save_blob(path, blob)
        page = reboot_open(browser)
        wait_body(page, "mission", "improvisation lab", "generate example")
        body = shot(page, "seed2-P1-post")
        fam, tab, disk = page_family(body), creative_tab(body), disk_studio_page()
        sl = disk_creative_slice()
        sec = str(sl.get("ii_selected_section") or "")
        ch = str(sl.get("ii_selected_chord") or "")
        ok = fam == "creative" and disk == "creative" and (
            has_any(body, "Verse 1", "F#m") or (sec == "Verse 1" and "F#" in ch)
        )
        rows.append(
            row(
                "P1",
                ok,
                f"fam={fam} tab={tab} verse={has_any(body,'Verse 1')} fshm={has_any(body,'F#m')} sec={sec!r} ch={ch!r}",
                disk,
            )
        )
        print("GATE P1", rows[-1], flush=True)
        page.context.close()

        # P2 Harmony
        path, blob = load_blob()
        st = blob.setdefault("state", {})
        stamp_page(st, "creative")
        merge_creative(
            st,
            {
                "improv_intelligence_tab": "Harmony Map",
                "creative_improv_intelligence_tab": "Harmony Map",
                "harmony_map_section": "Chorus",
                "harmony_map_chord": "C#m",
                "ii_selected_section": "Chorus",
                "ii_selected_chord": "C#m",
            },
        )
        save_blob(path, blob)
        page = reboot_open(browser)
        wait_body(page, "harmony", "live coach", "improvisation lab")
        body = shot(page, "seed2-P2-post")
        fam, tab, disk = page_family(body), creative_tab(body), disk_studio_page()
        sl = disk_creative_slice()
        ok = fam == "creative" and disk == "creative" and (
            has_any(body, "Harmony Map", "Live Coach", "C#m", "Chorus")
            or bool(sl.get("harmony_map_chord") or sl.get("ii_selected_chord"))
        )
        rows.append(
            row(
                "P2",
                ok,
                f"fam={fam} tab={tab} harm={sl.get('harmony_map_chord')!r} cshm={has_any(body,'C#m')}",
                disk,
            )
        )
        page.context.close()

        # P3 Alto + Written (live)
        page = open_fresh(browser)
        click_nav(page, "Songs")
        settle(page, 3)
        set_instrument(page, "Saxophone")
        settle(page, 2)
        click_radio(page, "Alto") or click_button_has(page, r"Alto")
        settle(page, 2)
        written_click = (
            click_button_has(page, r"Show chart in written key")
            or click_button_has(page, r"Written Charts")
            or click_radio(page, "Written Charts")
        )
        set_sidebar_pk(page, "G")
        settle(page, 4)
        side_pre = side(page)
        body_pre = shot(page, "seed2-P3-pre")
        alto_pre = has_any(side_pre + body_pre, "alto")
        written_pre = has_any(side_pre + body_pre, "written")
        notes.append(f"P3 written_click={written_click} alto_pre={alto_pre} written_pre={written_pre}")
        page.context.close()
        page = reboot_open(browser)
        body = shot(page, "seed2-P3-post")
        sb = side(page)
        alto, written = has_any(sb + body, "alto"), has_any(sb + body, "written")
        if not (alto_pre and written_pre):
            kind, ok = "harness_or_setup", False
        elif alto and written:
            kind, ok = "product_ok", True
        else:
            kind, ok = "product_fail", False
        rows.append(row("P3", ok, f"kind={kind} alto={alto} written={written}", disk_studio_page()))
        page.context.close()

        # P4 Guitar Shape/Capo
        page = open_fresh(browser)
        click_nav(page, "Songs")
        settle(page, 2)
        set_instrument(page, "Guitar")
        settle(page, 2)
        enable_guitar_capo(page, notes, "C")
        set_shape_tonic(page, "Bb") or set_shape_tonic(page, "B")
        settle(page, 4)
        side_pre = side(page)
        body_pre = shot(page, "seed2-P4-pre")
        guitar_pre = has_any(side_pre, "guitar") and has_any(side_pre + body_pre, "shape", "capo")
        page.context.close()
        page = reboot_open(browser)
        body = shot(page, "seed2-P4-post")
        sb = side(page)
        guitar = has_any(sb, "guitar")
        shape = has_any(sb + body, "shape", "capo", "bb", "b♭")
        if not guitar_pre:
            kind, ok = "harness_or_setup", False
        elif guitar and shape:
            kind, ok = "product_ok", True
        else:
            kind, ok = "product_fail", False
        rows.append(row("P4", ok, f"kind={kind} guitar={guitar} shape={shape} pre={guitar_pre}", disk_studio_page()))

        # P5 Practice Key matrix
        pk_rows = []
        for label, go in [
            ("Songs", lambda: click_nav(page, "Songs")),
            ("Custom", lambda: goto_custom(page)),
            (
                "Mission",
                lambda: (
                    goto_improv(page, notes),
                    click_radio(page, "Missions") or click_button_has(page, r"Missions"),
                ),
            ),
            (
                "Harmony Map",
                lambda: (
                    goto_improv(page, notes),
                    click_radio(page, "Harmony Map") or click_button_has(page, r"Harmony"),
                ),
            ),
            (
                "SBI",
                lambda: (
                    goto_improv(page, notes),
                    click_radio(page, "Song-Based") or click_button_has(page, r"Song-Based"),
                ),
            ),
            ("Backing", lambda: click_nav(page, "Backing") or click_button_has(page, r"Backing")),
        ]:
            try:
                go()
                wait_idle(page, 1500)
                changed = set_sidebar_pk(page, "D")
                settle(page, 2)
                pk_rows.append({"surface": label, "editable": bool(changed)})
            except Exception as exc:
                pk_rows.append({"surface": label, "editable": False, "error": str(exc)[:100]})
        for label, needles in [
            ("Mission Backing", ("Missions",)),
            ("SBI Backing", ("Song-Based",)),
            ("Jam Backing", ("Entry & Jam", "Jam")),
            ("Entry Style Backing", ("Entry & Jam", "Style")),
            ("Custom SBI Backing", ("Song-Based", "Custom")),
        ]:
            try:
                goto_improv(page, notes)
                for n in needles:
                    click_radio(page, n) or click_button_has(page, n)
                    settle(page, 1)
                opened = click_button_has(page, r"Open Backing") or click_button_has(
                    page, r"Backing Studio"
                )
                settle(page, 3)
                changed = bool(set_sidebar_pk(page, "E")) if opened else False
                pk_rows.append({"surface": label, "editable": changed, "opened": bool(opened)})
            except Exception as exc:
                pk_rows.append({"surface": label, "editable": False, "error": str(exc)[:100]})
        editable_n = sum(1 for r in pk_rows if r.get("editable"))
        rows.append(row("P5", editable_n >= 6, f"editable={editable_n}/{len(pk_rows)}", json.dumps(pk_rows)))
        page.context.close()

        # P6 Custom SBI Backing
        path, blob = load_blob()
        st = blob.setdefault("state", {})
        stamp_page(st, "backing")
        merge_creative(
            st,
            {
                "improv_entry_mode": "Song-Based Improvisation",
                "improv_intelligence_tab": "Entry & Jam",
                "improv_song_source": "Custom progression",
                "sbi_preview_source": "Custom progression",
            },
        )
        bts = st.get("backing_track_state")
        if not isinstance(bts, dict):
            bts = {}
            st["backing_track_state"] = bts
        bts["backing_track_bpm"] = 137
        bts["backing_track_groove_style"] = "Pop"
        sess = st.setdefault("session", {})
        if isinstance(sess, dict):
            sess["backing_source"] = "song_improv"
            sess["_last_valid_backing_source"] = "song_improv"
            ctx = sess.get("backing_context")
            if not isinstance(ctx, dict):
                ctx = {}
                sess["backing_context"] = ctx
            ctx["source"] = "song_improv"
            ctx["display_key"] = "F"
        for node_key in ("music_workspace_state", "core", "session"):
            node = st.get(node_key)
            if isinstance(node, dict):
                node["display_key"] = "F"
        save_blob(path, blob)
        page = reboot_open(browser)
        wait_body(page, "return to", "tempo", "backing", "trial")
        body = shot(page, "seed2-P6-post")
        fam, disk = page_family(body), disk_studio_page()
        ok = (str(fam).startswith("backing") or disk == "backing") and has_any(body, "Trial Song")
        rows.append(
            row(
                "P6",
                ok,
                f"fam={fam} trial={has_any(body,'Trial Song')} shape={has_any(body,'Shape of You')}",
                disk,
            )
        )
        page.context.close()

        # P7 Mission Backing
        path, blob = load_blob()
        st = blob.setdefault("state", {})
        stamp_page(st, "backing")
        merge_creative(
            st,
            {
                "improv_intelligence_tab": "Missions",
                "improv_active_mission": "Improvise using only chord tones",
                "improv_mission_pick": "Improvise using only chord tones",
                "ii_selected_section": "Verse 1",
                "ii_selected_chord": "F#m",
            },
        )
        sess = st.setdefault("session", {})
        if isinstance(sess, dict):
            sess["backing_source"] = "mission"
            sess["_last_valid_backing_source"] = "mission"
            ctx = sess.get("backing_context")
            if not isinstance(ctx, dict):
                ctx = {}
                sess["backing_context"] = ctx
            ctx["source"] = "mission"
        bts = st.setdefault("backing_track_state", {})
        if isinstance(bts, dict):
            bts["backing_track_bpm"] = 118
        save_blob(path, blob)
        page = reboot_open(browser)
        wait_body(page, "return to mission", "tempo", "backing", "mission")
        body = shot(page, "seed2-P7-post")
        fam, disk = page_family(body), disk_studio_page()
        ok = (str(fam).startswith("backing") or disk == "backing") and has_any(
            body, "mission", "return to mission"
        )
        rows.append(row("P7", ok, f"fam={fam}", disk))
        click_button_has(page, r"Return to Mission") or click_button_has(page, r"Return to Creative")
        settle(page, 4)
        body_ret = shot(page, "seed2-P7-return")
        rows.append(
            row(
                "P7_RETURN",
                page_family(body_ret) == "creative" or has_any(body_ret, "mission", "improvisation"),
                f"fam={page_family(body_ret)}",
                disk_studio_page(),
            )
        )
        page.context.close()

        # P8 Jam Backing
        path, blob = load_blob()
        st = blob.setdefault("state", {})
        stamp_page(st, "backing")
        merge_creative(
            st,
            {
                "improv_intelligence_tab": "Entry & Jam",
                "improv_entry_mode": "Jam Session Generator",
            },
        )
        sess = st.setdefault("session", {})
        if isinstance(sess, dict):
            sess["backing_source"] = "entry_jam"
            sess["_last_valid_backing_source"] = "entry_jam"
            ctx = sess.get("backing_context")
            if not isinstance(ctx, dict):
                ctx = {}
                sess["backing_context"] = ctx
            ctx["source"] = "entry_jam"
            ctx["entry_mode"] = "jam_generator"
        bts = st.setdefault("backing_track_state", {})
        if isinstance(bts, dict):
            bts["backing_track_bpm"] = 142
        save_blob(path, blob)
        page = reboot_open(browser)
        wait_body(page, "return to", "tempo", "jam", "backing")
        body = shot(page, "seed2-P8-post")
        fam, disk = page_family(body), disk_studio_page()
        try:
            pk_ok = bool(set_sidebar_pk(page, "Db"))
        except Exception:
            pk_ok = False
        ok = (str(fam).startswith("backing") or disk == "backing") and has_any(body, "jam")
        rows.append(row("P8", ok, f"fam={fam} editable_after={pk_ok}", disk))
        page.context.close()

        # P9 Entry Style Backing
        path, blob = load_blob()
        st = blob.setdefault("state", {})
        stamp_page(st, "backing")
        merge_creative(
            st,
            {
                "improv_intelligence_tab": "Entry & Jam",
                "improv_entry_mode": "Style Jam Mode",
            },
        )
        sess = st.setdefault("session", {})
        if isinstance(sess, dict):
            sess["backing_source"] = "entry_jam"
            sess["_last_valid_backing_source"] = "entry_jam"
            ctx = sess.get("backing_context")
            if not isinstance(ctx, dict):
                ctx = {}
                sess["backing_context"] = ctx
            ctx["source"] = "entry_jam"
            ctx["entry_mode"] = "style_jam"
        bts = st.setdefault("backing_track_state", {})
        if isinstance(bts, dict):
            bts["backing_track_bpm"] = 126
        save_blob(path, blob)
        page = reboot_open(browser)
        wait_body(page, "return to", "tempo", "style", "backing", "entry")
        body = shot(page, "seed2-P9-post")
        fam, disk = page_family(body), disk_studio_page()
        ok = (str(fam).startswith("backing") or disk == "backing") and has_any(body, "style", "entry")
        rows.append(row("P9", ok, f"fam={fam}", disk))
        browser.close()

    report = {
        "url": URL,
        "rows": rows,
        "notes": notes[-60:],
        "passed": sum(1 for r in rows if r["ok"]),
        "total": len(rows),
    }
    (OUT / "disk-seed-p1-p9-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if all(r["ok"] for r in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
