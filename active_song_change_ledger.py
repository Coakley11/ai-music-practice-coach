"""Which operation changed the active song, and why (diagnostic only; user report 2026-11-19).

On Cloud Dev the user picked Shallow, Backing showed Shallow, and pressing Play Backing Track turned the
app back to Blackbird in E. Local reproductions never showed it, so the operations that CAN rewrite the
active song are instrumented here: each records the active song before / after itself and, when it
changed, appends one ledger row and writes one log line:

    [music_active_song] op=workspace_apply from="Shallow — Lady Gaga / Bradley Cooper (G)"
        to="Blackbird — The Beatles (E)" why=source=cloud reasons=cloud_newer_than_applied mid_session=1

The rows are shown with ``?dev=1`` (Deploy verification panel) and the lines appear in the Cloud log.

Privacy: Catalog songs are public titles. A Custom progression or Composition is the user's own work,
so it is shown only as ``custom:<8 hex>`` / ``composition:<8 hex>`` (a hash of its pick key), never by
name. No chords, lyrics or saved data are recorded.

Nothing here changes behaviour: every function swallows its own errors.
"""

from __future__ import annotations

import hashlib
import logging
import time
from typing import Any

log = logging.getLogger("music_active_song")

LEDGER_KEY = "_active_song_change_ledger"
LAST_LABEL_KEY = "_active_song_change_last_label"
LEDGER_MAX_ROWS = 40


def _hashed(kind: str, pick: str) -> str:
    return f"{kind}:{hashlib.sha1(pick.encode('utf-8', 'replace')).hexdigest()[:8]}"


def active_song_label(session: dict[str, Any]) -> str:
    """The active song as a short, non-sensitive label: "Title — Artist" (keys: active_key_state)."""
    try:
        try:
            from songs.practice_key_state import resolve_practice_source_pick

            pick = str(resolve_practice_source_pick(session) or "").strip()
        except Exception:
            pick = ""
        if not pick:
            sel = session.get("selected_song") if isinstance(session.get("selected_song"), dict) else {}
            pick = str(session.get("active_catalog_pick_key") or (sel or {}).get("pick_key") or "").strip()
        if not pick:
            return ""
        if pick.startswith("custom::"):
            name = _hashed("custom", pick)
        elif pick.startswith("composition::"):
            name = _hashed("composition", pick)
        elif "::" in pick:
            name = _hashed(pick.split("::", 1)[0][:12] or "other", pick)
        else:
            # Catalog pick key "Genre<US>Title — Artist": the public catalog title.
            name = pick.split("\x1f", 1)[-1].strip()[:60]
        return name
    except Exception:
        return ""


def _pick_label(pick: str) -> str:
    pick = str(pick or "").strip()
    if not pick:
        return ""
    if pick.startswith("custom::"):
        return _hashed("custom", pick)
    if pick.startswith("composition::"):
        return _hashed("composition", pick)
    if "::" in pick:
        return _hashed(pick.split("::", 1)[0][:12] or "other", pick)
    return pick.split("", 1)[-1].strip()[:60]


def active_key_state(session: dict[str, Any]) -> str:
    """The keys that decide what the musician hears and reads, for the D-major report (2026-11-20):
    dk = sidebar display key, ck = concert key, pend = queued display key, pk = the active song's saved
    Practice Key, kc = Key Cycling's temporary key (only while cycling is On), fx = Fixed Key mode."""
    try:
        try:
            from songs.practice_key_state import get_practice_concert_key, resolve_practice_source_pick

            pick = str(resolve_practice_source_pick(session) or "").strip()
            pk = str(get_practice_concert_key(session, pick) or "").strip() if pick else ""
        except Exception:
            pk = ""
        kc = ""
        try:
            from backing_key_cycle import is_cycle_active, temporary_playback_key

            if is_cycle_active(session):
                kc = str(temporary_playback_key(session) or "").strip()
        except Exception:
            kc = ""
        fx = str(session.get("practice_key_mode") or "").strip()[:10]
        parts = [
            f"dk={str(session.get('display_key') or '').strip()[:4]}",
            f"ck={str(session.get('concert_key') or '').strip()[:4]}",
            f"pend={str(session.get('_pending_display_key') or '').strip()[:4]}",
            f"pk={pk[:4]}",
        ]
        if kc:
            parts.append(f"kc={kc[:4]}")
        if fx and fx.lower() not in ("off", "song", "per_song", "normal"):
            parts.append(f"fx={fx}")
        return " ".join(parts)
    except Exception:
        return ""


def _caller(depth: int = 3) -> str:
    """file:function:line of the code that called a key writer (no data)."""
    try:
        import os
        import sys

        out = []
        f = sys._getframe(depth)
        for _ in range(3):
            if f is None:
                break
            out.append(f"{os.path.basename(f.f_code.co_filename)}:{f.f_code.co_name}:{f.f_lineno}")
            f = f.f_back
        return "<".join(out)
    except Exception:
        return ""


def _short(value: Any) -> str:
    text = str(value if value is not None else "").replace("\n", " ").strip()
    return text[:120]


def note_active_song(session: dict[str, Any], op: str, *, mark: bool = False, **why: Any) -> bool:
    """Record ``op`` if the active song differs from the last label seen; True when it changed.

    ``mark=True`` adds a row even without a change (e.g. the Play press), so the ledger shows what the
    next operation did after it. ``why`` values are short strings or numbers (never saved user data).
    """
    try:
        song = active_song_label(session)
        keys = active_key_state(session)
        now = f"{song} [{keys}]" if song else ""
        before = str(session.get(LAST_LABEL_KEY) or "")
        changed = bool(now) and bool(before) and now != before
        session[LAST_LABEL_KEY] = now or before
        if not changed and not mark:
            return False
        why_txt = " ".join(f"{k}={_short(v)}" for k, v in why.items() if v not in (None, "", [], {}))
        row = {
            "t": time.strftime("%H:%M:%S"),
            "op": str(op)[:48],
            "from": before,
            "to": now,
            "changed": changed,
            "page": str(session.get("studio_page") or "")[:16],
            "why": why_txt,
        }
        rows = session.get(LEDGER_KEY)
        rows = list(rows) if isinstance(rows, list) else []
        rows.append(row)
        session[LEDGER_KEY] = rows[-LEDGER_MAX_ROWS:]
        if changed:
            line = '[music_active_song] op=%s from="%s" to="%s" page=%s why=%s' % (
                row["op"], before, now, row["page"], why_txt or "-",
            )
            try:  # stderr, like the [music_deploy] line, so it reaches the Streamlit Cloud log
                import sys

                print(line, flush=True, file=sys.stderr)
            except Exception:
                pass
            log.info(line)
        return changed
    except Exception:
        return False


def ledger_rows(session: dict[str, Any]) -> list[dict[str, Any]]:
    rows = session.get(LEDGER_KEY)
    return list(rows) if isinstance(rows, list) else []


__all__ = [
    "active_key_state",
    "LEDGER_KEY",
    "LAST_LABEL_KEY",
    "active_song_label",
    "ledger_rows",
    "note_active_song",
]
