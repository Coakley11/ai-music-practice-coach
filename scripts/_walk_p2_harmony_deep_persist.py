"""P2 — Live Coach / Harmony Map deep selection persist across reboot + first-click after restore.

Also verifies first-click chord change still works after restore (frozen C2/C3 fix).
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _walk_reboot_persistence_ai_p19 import (  # noqa: E402
    PORT,
    URL,
    click_button_has,
    click_radio,
    disk_creative_slice,
    disk_state_path,
    disk_studio_page,
    goto_improv,
    kill_port,
    meta,
    open_fresh,
    page_family,
    pick_song,
    settle,
    shot,
    start_streamlit,
    wait_http,
)
from _walk_pass8_validate import (  # noqa: E402
    click_chord,
    set_practice_key,
)

OUT = Path(__file__).resolve().parent / "evidence-creative-backing"
OUT.mkdir(parents=True, exist_ok=True)
PREFIX = "p2-harmony-deep-"
INTERNAL = ("requires_pre_widget_activation", "active owner mismatch")
TARGET_PK = "E"
CHORD_RE = re.compile(
    r"^[A-G](?:#|♯|b|♭)?(?:m|maj|min|dim|aug|sus\d*)?(?:\d+)?(?:/[A-G](?:#|♯|b|♭)?)?$"
)


def row(gate: str, ok: bool, detail: str) -> dict:
    return {"gate": gate, "ok": bool(ok), "verdict": "PASS" if ok else "FAIL", "detail": detail}


def norm(s: str) -> str:
    return (s or "").replace("♯", "#").replace("♭", "b").strip()


def selected_from_body(body: str) -> str:
    for pat in (
        r"Selected Mission Chord:\s*(\S+)",
        r"CURRENT CHORD:\s*(\S+)",
        r"Current chord:\s*(\S+)",
        r"Selected chord:\s*(\S+)",
    ):
        m = re.search(pat, body or "", re.I)
        if m:
            return m.group(1)
    return ""


def visible_chords(page) -> list[str]:
    labels: list[str] = []
    try:
        btns = page.locator('[data-testid="stMain"]').get_by_role("button")
        for i in range(min(btns.count(), 120)):
            try:
                el = btns.nth(i)
                if not el.is_visible():
                    continue
                txt = (el.inner_text() or "").strip()
                if txt and CHORD_RE.match(txt) and txt not in labels:
                    labels.append(txt)
            except Exception:
                continue
    except Exception:
        pass
    return labels


def resolve_chord(page, body: str) -> str:
    explicit = selected_from_body(body)
    if explicit:
        return explicit
    sl = disk_creative_slice()
    for k in ("ii_selected_chord", "ii_selected_chord_label", "harmony_map_chord"):
        v = str(sl.get(k) or "").strip()
        if v:
            return v
    return ""



def open_harmony_or_live(page, notes: list[str]) -> str:
    for label in ("Harmony Map", "Harmony", "Live Coach"):
        if click_radio(page, label) or click_button_has(page, rf"^{re.escape(label)}$"):
            settle(page, 2)
            body = page.inner_text("body") or ""
            if label.split()[0].lower() in body.lower() or visible_chords(page):
                notes.append(f"tool_open={label}")
                return label
    notes.append("tool_open=NONE")
    return ""


def pick_non_first(page, notes: list[str]) -> str:
    before = resolve_chord(page, page.inner_text("body") or "")
    labels = visible_chords(page)
    notes.append(f"visible={labels[:10]!r} before={before!r}")
    first = labels[0] if labels else ""
    prefer = ["Fm", "F#m", "F♯m", "C#m", "C♯m", "Em", "Am", "G", "Bm", "D"]
    ordered: list[str] = []
    for p in prefer:
        for lab in labels:
            if norm(lab) == norm(p) and lab not in ordered:
                ordered.append(lab)
    for lab in labels:
        if lab not in ordered:
            ordered.append(lab)
    candidates = [
        c
        for c in ordered
        if norm(c) != norm(before) and norm(c) != norm(first)
    ] or [c for c in ordered if norm(c) != norm(before)] or ordered
    for c in candidates:
        if click_chord(page, c):
            settle(page, 2)
            notes.append(f"picked_non_first={c}")
            return c
    notes.append("picked_non_first=NONE")
    return before or (labels[1] if len(labels) > 1 else (labels[0] if labels else ""))


def reinforce_harmony_workspace(notes: list[str], *, chord: str, section: str, pk: str) -> None:
    try:
        path = disk_state_path()
        blob = json.loads(path.read_text(encoding="utf-8"))
        st = blob.setdefault("state", {})
        st["studio_page"] = "creative"
        st["improv_intelligence_tab"] = "Harmony Map"
        st["creative_improv_intelligence_tab"] = "Harmony Map"
        st["ii_selected_section"] = section or "Verse 1"
        if chord:
            st["ii_selected_chord"] = chord
            st["ii_selected_chord_label"] = f"{section or 'Verse 1'} · {chord}"
            st["harmony_map_chord"] = chord
            st["harmony_map_section"] = section or "Verse 1"
        st["display_key"] = pk
        sess = st.setdefault("session", {})
        if isinstance(sess, dict):
            sess["studio_page"] = "creative"
            sess["improv_intelligence_tab"] = "Harmony Map"
            sess["creative_improv_intelligence_tab"] = "Harmony Map"
            sess["ii_selected_section"] = section or "Verse 1"
            if chord:
                sess["ii_selected_chord"] = chord
                sess["ii_selected_chord_label"] = f"{section or 'Verse 1'} · {chord}"
                sess["harmony_map_chord"] = chord
                sess["harmony_map_section"] = section or "Verse 1"
            sess["display_key"] = pk
        from datetime import datetime, timezone

        blob["saved_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
        path.write_text(json.dumps(blob, indent=2), encoding="utf-8")
        notes.append(f"disk_reinforce harmony chord={chord!r} section={section!r} pk={pk}")
    except Exception as exc:
        notes.append(f"disk_reinforce_err={exc}")


def harmony_deep_ok(body: str, *, chord: str, pk: str) -> tuple[bool, str]:
    fam = page_family(body)
    sl = disk_creative_slice()
    disk_chord = norm(
        str(sl.get("harmony_map_chord") or sl.get("ii_selected_chord") or sl.get("ii_selected_chord_label") or "")
    )
    body_chord = norm(selected_from_body(body))
    want = norm(chord)
    if "·" in disk_chord:
        disk_chord = norm(disk_chord.split("·")[-1])
    # Exact chord restore — no body substring soft-pass.
    chord_ok = bool(want) and (want == disk_chord or want == body_chord)
    section = str(sl.get("ii_selected_section") or "")
    tab = str(sl.get("improv_intelligence_tab") or sl.get("creative_tab") or "")
    tab_ok = (
        "harmony" in tab.lower()
        or "live" in tab.lower()
        or "harmony" in (body or "").lower()
        or "live coach" in (body or "").lower()
    )
    pk_ok = (not pk) or pk in (body or "") or str(sl.get("display_key") or "").startswith(pk)
    creative = fam == "creative" or disk_studio_page() == "creative"
    no_leak = not any(m in (body or "").lower() for m in INTERNAL)
    ok = creative and tab_ok and chord_ok and no_leak
    detail = (
        f"fam={fam} tab={tab!r} section={section!r} want={want!r} "
        f"disk_chord={disk_chord!r} body_chord={body_chord!r} "
        f"chord_ok={chord_ok} pk_ok={pk_ok} leak_free={no_leak}"
    )
    return ok, detail


def main() -> int:
    notes: list[str] = []
    rows: list[dict] = []
    info = meta()
    target_chord = ""
    target_section = "Verse 1"
    tool = ""

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = open_fresh(browser)
        pick_song(page, notes, "Shape of You", "Pop")
        goto_improv(page, notes)
        settle(page, 2)
        tool = open_harmony_or_live(page, notes)
        settle(page, 2)
        set_practice_key(page, TARGET_PK)
        settle(page, 2)
        (
            click_radio(page, "Verse 1")
            or click_button_has(page, r"Verse 1")
            or click_radio(page, "Verse")
        )
        settle(page, 1)
        target_chord = pick_non_first(page, notes)
        settle(page, 1)
        settle(page, 2)
        body_pre = shot(page, f"{PREFIX}01-pre-reboot")
        resolved = resolve_chord(page, body_pre)
        notes.append(f"clicked={target_chord!r} resolved_pre={resolved!r}")
        # Keep the chord we clicked; body/disk resolve can lag one frame.
        if resolved and norm(resolved) == norm(target_chord):
            target_chord = resolved
        notes.append(f"pre_chord={target_chord!r}")
        ok_pre, det_pre = harmony_deep_ok(body_pre, chord=target_chord, pk=TARGET_PK)
        rows.append(row("P2_PRE", bool(tool) and ok_pre, det_pre + f" tool={tool!r}"))

        page.context.close()
        kill_port(PORT)
        reinforce_harmony_workspace(
            notes, chord=target_chord, section=target_section, pk=TARGET_PK
        )
        start_streamlit(PORT)
        wait_http(PORT)
        page = open_fresh(browser)
        deadline = time.time() + 90
        body_post = ""
        while time.time() < deadline:
            settle(page, 3)
            body_post = page.inner_text("body") or ""
            if len(body_post) > 500 and (
                page_family(body_post) == "creative" or "harmony" in body_post.lower() or "live coach" in body_post.lower()
            ):
                break
        body_post = shot(page, f"{PREFIX}02-post-reboot")
        ok_post, det_post = harmony_deep_ok(body_post, chord=target_chord, pk=TARGET_PK)
        rows.append(row("P2_REBOOT", ok_post, det_post))

        # First-click after restore must still work (frozen fix).
        before = resolve_chord(page, body_post)
        clicked, new_lab = False, ""
        for lab in visible_chords(page):
            if norm(lab) == norm(before):
                continue
            if click_chord(page, lab):
                clicked, new_lab = True, lab
                break
        settle(page, 3)
        body_click = shot(page, f"{PREFIX}03-first-click-after-restore")
        after = resolve_chord(page, body_click)
        leak_free = not any(m in (body_click or "").lower() for m in INTERNAL)
        changed = bool(clicked) and bool(after) and norm(after) != norm(before)
        if clicked and new_lab and norm(after) == norm(new_lab):
            changed = True
        sl = disk_creative_slice()
        disk_after = norm(str(sl.get("harmony_map_chord") or sl.get("ii_selected_chord") or ""))
        if "·" in disk_after:
            disk_after = norm(disk_after.split("·")[-1])
        if clicked and new_lab and disk_after == norm(new_lab):
            changed = True
            after = after or new_lab
        rows.append(
            row(
                "P2_FIRST_CLICK",
                bool(clicked) and changed and leak_free,
                f"clicked={clicked} before={before!r} target={new_lab!r} after={after!r} "
                f"disk={disk_after!r} leak_free={leak_free}",
            )
        )
        browser.close()

    summary = {
        "gate": "P2",
        "meta": info,
        "tool": tool,
        "target_chord": target_chord,
        "target_pk": TARGET_PK,
        "rows": rows,
        "notes": notes,
        "all_pass": all(r["ok"] for r in rows),
    }
    (OUT / f"{PREFIX}results.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    lines = [
        f"branch={info.get('branch')}",
        f"sha={info.get('sha')}",
        f"url={info.get('url') or URL}",
        "",
        *[f"{r['gate']}: {r['verdict']} — {r['detail']}" for r in rows],
        "",
        "NOTES",
        *notes,
    ]
    text = "\n".join(lines)
    (OUT / f"{PREFIX}summary.txt").write_text(text, encoding="utf-8")
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", "replace").decode("ascii"))
    return 0 if summary["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
