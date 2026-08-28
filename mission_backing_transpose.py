"""One authoritative Mission Backing Practice Key interval.

``new_practice_key - sealed_mission_practice_key`` is applied exactly once to
the selected chord, backing harmony, example notes/MIDI/ABC, return dest, and
blue context card. Do not recompute from Written / Shape / global leftovers.
"""

from __future__ import annotations

import copy
from typing import Any

from music_theory import semitone_distance, transpose_chord


def _normalize_pk(token: str, *, default_mode: str = "minor") -> str:
    raw = str(token or "").strip()
    if not raw:
        return ""
    try:
        from workflow_key_identity import normalize_user_practice_key_selection

        _tonic, _mode, out = normalize_user_practice_key_selection(raw, default_mode=default_mode)
        return str(out or raw).strip()
    except ImportError:
        return raw


def _chord_root_matches_key(chord: str, key_token: str) -> bool:
    try:
        from music_theory import normalize_root, split_chord, split_key_center
    except ImportError:
        return False
    cr, _cs = split_chord(str(chord or "").strip())
    kt, _km = split_key_center(str(key_token or "").strip())
    if not cr or not kt:
        return False
    return normalize_root(cr) == normalize_root(kt)


def ensure_mission_backing_pitch_seal(dest: dict[str, Any]) -> dict[str, Any]:
    """Freeze handoff pitch material the first time; later PK changes project from it."""
    if not isinstance(dest, dict):
        return {}
    if str(dest.get("sealed_practice_key") or "").strip():
        return dest
    sealed_pk = str(dest.get("display_key") or dest.get("concert_key") or "").strip()
    dest["sealed_practice_key"] = sealed_pk
    dest["sealed_chord_symbol"] = str(dest.get("chord_symbol") or "").strip()
    dest["sealed_example_notes"] = [str(n) for n in (dest.get("example_notes") or [])]
    dest["sealed_example_midi"] = [int(m) for m in (dest.get("example_midi") or []) if str(m).strip() != ""]
    dest["sealed_example_display"] = str(dest.get("example_display") or "")
    dest["sealed_example_abc"] = str(dest.get("example_abc") or "")
    dest["sealed_example_rhythm"] = str(dest.get("example_rhythm") or "")
    dest["sealed_example_rhythm_key"] = str(dest.get("example_rhythm_key") or "")
    dest["sealed_example_rhythm_symbols"] = [str(s) for s in (dest.get("example_rhythm_symbols") or [])]
    dest["sealed_example_fingerprint"] = str(
        dest.get("example_fingerprint") or dest.get("example_material_fp") or ""
    )
    dest["sealed_progression"] = [
        str(c) for c in (dest.get("sealed_progression") or dest.get("progression") or []) if str(c).strip()
    ]
    if not dest["sealed_progression"] and dest["sealed_chord_symbol"]:
        dest["sealed_progression"] = [dest["sealed_chord_symbol"]]
    return dest


def _transpose_notes(
    notes: list[Any],
    midi: list[Any],
    *,
    steps: int,
    reference_key: str,
) -> tuple[list[str], list[int]]:
    from improvisation_motif import _midi_from_note, _note_from_midi

    out_notes: list[str] = []
    out_midi: list[int] = []
    for i, n in enumerate(notes):
        if i < len(midi) and str(midi[i]).strip() != "":
            m = int(midi[i]) + steps
        else:
            m = int(_midi_from_note(str(n), 4)) + steps
        out_notes.append(_note_from_midi(m, reference_key))
        out_midi.append(m)
    return out_notes, out_midi


def apply_mission_backing_practice_key_interval(
    session: dict[str, Any],
    new_key: str,
    *,
    from_key: str = "",
) -> dict[str, Any] | None:
    """Project sealed Mission material by ``new_key - sealed_practice_key`` once."""
    new = _normalize_pk(new_key)
    if not new:
        return None
    try:
        from mission_return_destination import (
            peek_mission_return_destination,
            seal_mission_return_destination,
        )
    except ImportError:
        return None
    dest = peek_mission_return_destination(session)
    if dest is None:
        dest = {
            "mission_id": str(session.get("improv_active_mission") or session.get("improv_mission_pick") or "mission"),
            "chord_symbol": str(session.get("ii_selected_chord") or session.get("II_SELECTED_CHORD") or ""),
            "display_key": str(from_key or session.get("display_key") or ""),
            "concert_key": str(from_key or session.get("concert_key") or session.get("display_key") or ""),
            "example_notes": [],
            "example_midi": [],
        }
        try:
            from improvisation_missions import MISSION_EXAMPLE_KEY

            raw = session.get(MISSION_EXAMPLE_KEY)
            if isinstance(raw, dict):
                motif = raw.get("motif") if isinstance(raw.get("motif"), dict) else {}
                dest["example_notes"] = list(motif.get("notes") or raw.get("example_notes") or [])
                dest["example_midi"] = list(motif.get("midi") or [])
                dest["example_display"] = str(motif.get("display") or "")
                dest["chord_symbol"] = str(raw.get("chord") or dest.get("chord_symbol") or "")
        except ImportError:
            pass
    dest = ensure_mission_backing_pitch_seal(copy.deepcopy(dest))
    sealed_pk = str(dest.get("sealed_practice_key") or from_key or "").strip()
    if not sealed_pk:
        sealed_pk = new
        dest["sealed_practice_key"] = sealed_pk
    steps = semitone_distance(sealed_pk, new) if sealed_pk != new else 0
    sealed_chord = str(dest.get("sealed_chord_symbol") or dest.get("chord_symbol") or "").strip()
    new_chord = (
        transpose_chord(sealed_chord, steps, reference_key=new) if sealed_chord and steps else sealed_chord
    )
    sealed_notes = [str(n) for n in (dest.get("sealed_example_notes") or dest.get("example_notes") or [])]
    sealed_midi = [int(m) for m in (dest.get("sealed_example_midi") or dest.get("example_midi") or []) if str(m).strip() != ""]
    new_notes, new_midi = (
        _transpose_notes(sealed_notes, sealed_midi, steps=steps, reference_key=new)
        if sealed_notes and steps
        else (list(sealed_notes), list(sealed_midi))
    )
    sealed_prog = [str(c) for c in (dest.get("sealed_progression") or []) if str(c).strip()]
    new_prog = [
        transpose_chord(c, steps, reference_key=new) if steps else c for c in sealed_prog
    ] or ([new_chord] if new_chord else [])

    dest["display_key"] = new
    dest["concert_key"] = new
    dest["chord_symbol"] = new_chord
    dest["example_notes"] = new_notes
    dest["example_midi"] = new_midi
    dest["example_display"] = " – ".join(new_notes)
    dest["progression"] = list(new_prog)
    section = str(dest.get("section_label") or session.get("ii_selected_section") or "").strip()
    if section or new_chord:
        dest["chord_display_label"] = f"{section} · {new_chord}".strip(" ·")

    session["display_key"] = new
    session["concert_key"] = new
    session["_pending_display_key"] = new
    if new_chord:
        session["ii_selected_chord"] = new_chord
        session["II_SELECTED_CHORD"] = new_chord
        session["_mission_backing_canonical_chord"] = new_chord
    click = session.get("_mission_chord_click_authority")
    if isinstance(click, dict) and new_chord:
        click = dict(click)
        click["chord"] = new_chord
        session["_mission_chord_click_authority"] = click

    if new_notes:
        try:
            from improvisation_missions import MISSION_EXAMPLE_KEY, MISSION_PRACTICE_LICK_KEY, build_mission_notation_abc

            raw = session.get(MISSION_EXAMPLE_KEY)
            raw = dict(raw) if isinstance(raw, dict) else {}
            motif = dict(raw.get("motif") or {})
            motif["notes"] = list(new_notes)
            motif["midi"] = list(new_midi)
            motif["display"] = dest["example_display"]
            if new_chord:
                motif["chord"] = new_chord
                raw["chord"] = new_chord
            raw["motif"] = motif
            raw["concert_key"] = new
            raw["display_key"] = new
            try:
                raw["abc"] = build_mission_notation_abc(
                    motif,
                    mission=str(raw.get("mission") or dest.get("mission_id") or ""),
                    key_center=new,
                    bpm=int(raw.get("bpm") or 100),
                )
            except Exception:
                pass
            dest["example_abc"] = str(raw.get("abc") or "")
            session[MISSION_EXAMPLE_KEY] = raw
            lick = session.get(MISSION_PRACTICE_LICK_KEY)
            if isinstance(lick, dict):
                lick = dict(lick)
                lick["motif"] = dict(motif)
                lick["chord"] = new_chord or lick.get("chord")
                lick["key_center"] = new
                lick["abc"] = str(raw.get("abc") or lick.get("abc") or "")
                session[MISSION_PRACTICE_LICK_KEY] = lick
        except ImportError:
            pass

    try:
        from backing_context import BACKING_CONTEXT_KEY, get_backing_context, set_backing_context

        ctx = get_backing_context(session)
        if ctx is not None and str(getattr(ctx, "source", "") or "") == "mission":
            ctx.display_key = new
            ctx.concert_key = new
            ctx.key = new
            if new_prog:
                ctx.progression = list(new_prog)
                ctx.progression_label = " – ".join(new_prog)
            if new_chord:
                try:
                    ctx.selected_chord = new_chord
                except Exception:
                    pass
            set_backing_context(session, ctx)
        blob = session.get(BACKING_CONTEXT_KEY)
        if isinstance(blob, dict) and str(blob.get("source") or "") == "mission":
            blob["display_key"] = new
            blob["concert_key"] = new
            blob["key"] = new
            if new_prog:
                blob["progression"] = list(new_prog)
                blob["progression_label"] = " – ".join(new_prog)
    except ImportError:
        pass

    session.pop("_mission_pk_transpose_from", None)
    try:
        seal_mission_return_destination(session, dest)
    except Exception:
        session["_music_mission_canonical_return_destination"] = dest
    return dest


def mission_card_progression_symbols(session: dict[str, Any], ctx: Any | None = None) -> list[str]:
    """Blue-card progression from the interval-projected dest / live chord."""
    try:
        from mission_return_destination import peek_mission_return_destination

        dest = peek_mission_return_destination(session)
    except ImportError:
        dest = None
    if isinstance(dest, dict):
        prog = [str(c) for c in (dest.get("progression") or []) if str(c).strip()]
        chord = str(dest.get("chord_symbol") or "").strip()
        if prog:
            return prog
        if chord:
            return [chord]
    live = str(session.get("ii_selected_chord") or session.get("II_SELECTED_CHORD") or "").strip()
    if live:
        return [live]
    if ctx is not None:
        prog = [str(c) for c in (getattr(ctx, "progression", None) or []) if str(c).strip()]
        if prog:
            return prog
    return []


__all__ = [
    "apply_mission_backing_practice_key_interval",
    "ensure_mission_backing_pitch_seal",
    "mission_card_progression_symbols",
]
