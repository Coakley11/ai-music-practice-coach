"""P5 — Practice / Concert Key editability matrix across Songs / Custom / Creative / Backing kinds."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _walk_reboot_persistence_ai_p19 import (  # noqa: E402
    URL,
    click_button_has,
    click_nav,
    click_radio,
    disk_state_path,
    goto_custom,
    goto_improv,
    meta,
    open_fresh,
    open_sbi_custom_source,
    page_family,
    pick_song,
    seed_trial_song_last_custom,
    settle,
    shot,
)
from _walk_pass8_validate import (  # noqa: E402
    _practice_concert_key_from_body,
    click_open_backing_studio,
    ensure_missions_workspace,
    goto_backing,
    open_jam_generator,
    open_mission_backing,
    set_practice_key,
)

OUT = Path(__file__).resolve().parent / "evidence-creative-backing"
OUT.mkdir(parents=True, exist_ok=True)
PREFIX = "p5-practice-key-matrix-"
INTERNAL = ("requires_pre_widget_activation", "active owner mismatch")


def row(gate: str, ok: bool, detail: str) -> dict:
    return {"gate": gate, "ok": bool(ok), "verdict": "PASS" if ok else "FAIL", "detail": detail}


def norm_key(s: str) -> str:
    return (s or "").replace("♯", "#").replace("♭", "b").strip()


def sidebar_text(page) -> str:
    try:
        return page.inner_text('[data-testid="stSidebar"]') or ""
    except Exception:
        return ""


def disk_pk_hints() -> dict:
    try:
        st = json.loads(disk_state_path().read_text(encoding="utf-8")).get("state") or {}
        sess = st.get("session") if isinstance(st.get("session"), dict) else {}
        ctx = st.get("backing_context")
        if not isinstance(ctx, dict):
            ctx = sess.get("backing_context") if isinstance(sess.get("backing_context"), dict) else {}
        pk_by = st.get("practice_key_by_source")
        if not isinstance(pk_by, dict):
            pk_by = (
                sess.get("practice_key_by_source")
                if isinstance(sess.get("practice_key_by_source"), dict)
                else {}
            )
        return {
            "display_key": st.get("display_key") or sess.get("display_key"),
            "ctx_key": (ctx or {}).get("display_key") or (ctx or {}).get("key"),
            "ctx_source": (ctx or {}).get("source"),
            "catalog": st.get("active_catalog_pick_key") or sess.get("active_catalog_pick_key"),
            "last_custom": st.get("last_custom_pick_key") or sess.get("last_custom_pick_key"),
            "pk_by": {str(k): v for k, v in list((pk_by or {}).items())[:8]},
        }
    except Exception as exc:
        return {"err": str(exc)}


def key_visible(text: str, key: str) -> bool:
    blob = (text or "").replace("♯", "#").replace("♭", "b")
    k = norm_key(key)
    if not k:
        return False
    return k in blob or bool(re.search(rf"\b{re.escape(k)}\b", blob))


def verify_pk(page, key: str, notes: list[str], tag: str) -> tuple[bool, str]:
    accepted = False
    for _try in range(2):
        accepted = bool(set_practice_key(page, key))
        settle(page, 2)
        if accepted:
            break
        settle(page, 1)
    body = page.inner_text("body") or ""
    side = sidebar_text(page)
    parsed = norm_key(_practice_concert_key_from_body(body) or "")
    disk = disk_pk_hints()
    leak_free = not any(m in (body + side).lower() for m in INTERNAL)
    ui_ok = accepted and (
        key_visible(side, key) or key_visible(body, key) or parsed == norm_key(key)
    )
    want = norm_key(key)

    def _root(token: str) -> str:
        t = norm_key(token)
        if t.endswith("m") and len(t) > 1:
            # Keep "Am" → "A"; keep "C#m" → "C#"; do not strip lone "m".
            return t[:-1]
        return t

    def _key_hit(raw: object) -> bool:
        got = norm_key(str(raw or ""))
        if not got or not want:
            return False
        return got == want or _root(got) == _root(want)

    disk_ok = (
        _key_hit(disk.get("display_key"))
        or _key_hit(disk.get("ctx_key"))
        or any(_key_hit(v) for v in (disk.get("pk_by") or {}).values())
    )
    ok = leak_free and (ui_ok or disk_ok)
    detail = (
        f"accepted={accepted} ui_ok={ui_ok} disk_ok={disk_ok} parsed={parsed!r} "
        f"leak_free={leak_free} disk={disk}"
    )
    notes.append(f"{tag}: {detail}")
    shot(page, f"{PREFIX}{tag}")
    return ok, detail


def open_harmony(page, notes: list[str]) -> bool:
    goto_improv(page, notes)
    settle(page, 1)
    ok = (
        click_radio(page, "Harmony Map")
        or click_radio(page, "Harmony")
        or click_button_has(page, r"Harmony Map")
        or click_button_has(page, r"Harmony")
    )
    settle(page, 2)
    notes.append(f"harmony_open={ok}")
    return bool(ok)


def open_sbi_active(page, notes: list[str]) -> bool:
    goto_improv(page, notes)
    settle(page, 1)
    # Creative Improvisation Intelligence: Entry & Jam → Song-Based Improvisation → Active.
    for _ in range(4):
        click_radio(page, "Entry & Jam") or click_radio(page, "Entry") or click_button_has(
            page, "Entry"
        )
        settle(page, 1)
        click_radio(page, "Song-Based Improvisation") or click_radio(
            page, "Song-Based"
        ) or click_button_has(page, r"Song-Based")
        settle(page, 1)
        click_radio(page, "Active song") or click_radio(page, "Active Song") or click_radio(
            page, "Active"
        ) or click_button_has(page, r"Active song")
        settle(page, 2)
        body = page.inner_text("body") or ""
        landed = (
            "Song-Based" in body
            or "song-based" in body.lower()
            or "Active song" in body
            or "Open in Backing Studio" in body
        )
        if landed:
            notes.append("sbi_active_landed=True")
            return True
    notes.append("sbi_active_landed=False")
    return False


def open_entry_style(page, notes: list[str]) -> bool:
    goto_improv(page, notes)
    settle(page, 1)
    click_radio(page, "Entry & Jam") or click_radio(page, "Entry") or click_button_has(page, "Entry")
    settle(page, 1)
    ok = (
        click_radio(page, "Style Jam Mode")
        or click_radio(page, "Style Jam")
        or click_button_has(page, r"Style Jam")
    )
    settle(page, 2)
    (
        click_button_has(page, r"Generate progression")
        or click_button_has(page, r"Generate style")
        or click_button_has(page, r"^Generate$")
    )
    settle(page, 3)
    notes.append(f"style_jam_open={ok}")
    return bool(ok)


def open_backing_from_here(page, notes: list[str], tag: str) -> bool:
    opened = (
        click_open_backing_studio(page, notes, tag)
        or click_button_has(page, r"Open in Backing Studio")
        or click_button_has(page, r"Open Backing")
        or click_button_has(page, r"Practice in.*Backing")
    )
    settle(page, 4)
    body = page.inner_text("body") or ""
    landed = str(page_family(body)).startswith("backing") or "Backing Track Studio" in body
    notes.append(f"{tag}_backing_open={opened} landed={landed}")
    return bool(opened and landed)


def main() -> int:
    notes: list[str] = []
    rows: list[dict] = []
    info = meta()
    results: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = open_fresh(browser)
        pick_song(page, notes, "Shape of You", "Pop")
        seed_trial_song_last_custom(page, notes)
        settle(page, 2)

        click_nav(page, "Songs") or click_button_has(page, r"Songs")
        settle(page, 2)
        ok, det = verify_pk(page, "G", notes, "Songs")
        results.append({"surface": "Songs", "ok": ok, "detail": det})

        goto_custom(page)
        settle(page, 2)
        ok, det = verify_pk(page, "Ab", notes, "Custom")
        results.append({"surface": "Custom", "ok": ok, "detail": det})

        goto_improv(page, notes)
        ensure_missions_workspace(page, notes)
        settle(page, 2)
        ok, det = verify_pk(page, "E", notes, "Mission")
        results.append({"surface": "Mission", "ok": ok, "detail": det})

        open_harmony(page, notes)
        ok, det = verify_pk(page, "F#", notes, "HarmonyMap")
        results.append({"surface": "Harmony Map", "ok": ok, "detail": det})

        open_sbi_active(page, notes)
        ok, det = verify_pk(page, "E", notes, "SBIActive")
        results.append({"surface": "SBI Active", "ok": ok, "detail": det})

        open_sbi_custom_source(page, notes)
        settle(page, 2)
        ok, det = verify_pk(page, "G", notes, "SBICustom")
        results.append({"surface": "SBI Custom", "ok": ok, "detail": det})

        click_nav(page, "Songs") or click_button_has(page, r"Songs")
        settle(page, 1)
        pick_song(page, notes, "Shape of You", "Pop")
        goto_backing(page)
        settle(page, 3)
        ok, det = verify_pk(page, "C#", notes, "BackingRegular")
        results.append({"surface": "Backing regular", "ok": ok, "detail": det})

        goto_improv(page, notes)
        ensure_missions_workspace(page, notes)
        settle(page, 2)
        open_mission_backing(page, notes)
        settle(page, 3)
        ok, det = verify_pk(page, "E", notes, "MissionBacking")
        results.append({"surface": "Mission Backing", "ok": ok, "detail": det})

        goto_improv(page, notes)
        open_sbi_active(page, notes)
        open_backing_from_here(page, notes, "sbi-active")
        ok, det = verify_pk(page, "D", notes, "SBIBacking")
        results.append({"surface": "SBI Backing", "ok": ok, "detail": det})

        before_disk = disk_pk_hints()
        catalog_before = before_disk.get("catalog")
        shape_pk_before = None
        for k, v in (before_disk.get("pk_by") or {}).items():
            if "shape" in str(k).lower():
                shape_pk_before = norm_key(str(v))
                break
        goto_improv(page, notes)
        open_sbi_custom_source(page, notes)
        settle(page, 2)
        open_backing_from_here(page, notes, "sbi-custom")
        ok, det = verify_pk(page, "Eb", notes, "CustomSBIBacking")
        after_disk = disk_pk_hints()
        shape_pk_after = None
        for k, v in (after_disk.get("pk_by") or {}).items():
            if "shape" in str(k).lower():
                shape_pk_after = norm_key(str(v))
                break
        catalog_ok = (
            catalog_before is None
            or after_disk.get("catalog") == catalog_before
            or "shape" in str(after_disk.get("catalog") or "").lower()
            or "shape" in str(catalog_before or "").lower()
        )
        no_global_contaminate = "trial" not in str(after_disk.get("catalog") or "").lower()
        # Temporary Custom/SBI key must not rewrite Global Active Shape of You PK.
        shape_pk_stable = (
            shape_pk_before is None
            or shape_pk_after is None
            or shape_pk_before == shape_pk_after
            or shape_pk_after not in {"Eb", "Ebm"}
        )
        ok = ok and catalog_ok and no_global_contaminate and shape_pk_stable
        det = (
            f"{det} catalog_before={catalog_before!r} "
            f"catalog_after={after_disk.get('catalog')!r} no_contam={no_global_contaminate} "
            f"shape_pk_before={shape_pk_before!r} shape_pk_after={shape_pk_after!r} "
            f"shape_pk_stable={shape_pk_stable}"
        )
        results.append({"surface": "Custom SBI Backing", "ok": ok, "detail": det})

        open_jam_generator(page, notes)
        settle(page, 1)
        (
            click_button_has(page, r"Generate jam session")
            or click_button_has(page, r"Generate jam")
            or click_button_has(page, r"^Generate$")
        )
        settle(page, 3)
        open_backing_from_here(page, notes, "jam")
        ok, det = verify_pk(page, "B", notes, "JamBacking")
        results.append({"surface": "Jam Backing", "ok": ok, "detail": det})

        open_entry_style(page, notes)
        open_backing_from_here(page, notes, "entry-style")
        ok, det = verify_pk(page, "F", notes, "EntryStyleBacking")
        results.append({"surface": "Entry Style Backing", "ok": ok, "detail": det})

        browser.close()

    for r in results:
        rows.append(row(f"P5_{r['surface'].replace(' ', '_')}", r["ok"], r["detail"]))

    all_pass = all(r["ok"] for r in results)
    summary = {
        "gate": "P5",
        "meta": info,
        "results": results,
        "notes": notes,
        "all_pass": all_pass,
        "pass_count": sum(1 for r in results if r["ok"]),
        "total": len(results),
    }
    (OUT / f"{PREFIX}results.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    lines = [
        f"branch={info.get('branch')}",
        f"sha={info.get('sha')}",
        f"url={info.get('url') or URL}",
        f"pass={summary['pass_count']}/{summary['total']}",
        "",
        *[f"{r['gate']}: {r['verdict']} — {r['detail']}" for r in rows],
        "",
        "NOTES",
        *notes[-50:],
    ]
    text = "\n".join(lines)
    (OUT / f"{PREFIX}summary.txt").write_text(text, encoding="utf-8")
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", "replace").decode("ascii"))
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
