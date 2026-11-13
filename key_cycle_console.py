"""Key Cycling practice console: compact transport readouts and the Live Mission Example.

Key Cycling is a temporary performance context. Everything that changes with a
cycle step is shown here (current / next key, written / shape / sounding key,
capo fret, the transposed Mission example); the normal song / Backing / Mission
card keeps the saved Practice Key (see ``backing_musical_state.card_view``).

Pure models first (``console_model``, ``live_mission_model``), then the
Streamlit renderers. No transposition engine of its own: the sequence comes from
``backing_key_cycle.cycle_key_sequence``, reading keys from
``project_cycle_display_key`` (written / shape aware, Key Spelling aware), the
capo from ``cycle_shape_projection`` (the shared capo source) and the Mission example from
``improvisation_missions._derive_mission_example_from_canon`` -- always from the
canonical example, never from a previously transposed one.
"""

from __future__ import annotations

import html
from typing import Any

# Status of the cycling transport, as the console shows it.
CONSOLE_PLAYING = "playing"
CONSOLE_PAUSED = "paused"
CONSOLE_STOPPED = "stopped"
CONSOLE_STARTING = "starting"

_STATUS_TEXT = {
    CONSOLE_PLAYING: "Cycling",
    CONSOLE_PAUSED: "Paused",
    CONSOLE_STOPPED: "Stopped",
    CONSOLE_STARTING: "Starting…",
}

# Mission → short exercise type shown beside the Mission title.
_EXERCISE_TYPES: tuple[tuple[str, str], ...] = (
    ("guide tone", "Guide Tones"),
    ("chord tone", "Chord Tones"),
    ("pentatonic", "Pentatonic Scale"),
    ("blues scale", "Blues Scale"),
    ("chromatic", "Chromatic Approach"),
    ("enclose", "Enclosures"),
    ("bebop", "Bebop Line"),
    ("scalar", "Scale Runs"),
    ("rhythm", "Rhythm Study"),
    ("syncopat", "Rhythm Study"),
    ("silence", "Rhythm Study"),
    ("motif", "Motif Development"),
    ("resolve", "Resolution"),
    ("tension", "Tension & Release"),
    ("5 notes", "Limited Notes"),
    ("arpeggio", "Arpeggios"),
    ("interval", "Interval Patterns"),
    ("third", "Thirds"),
    ("fourth", "Fourths"),
)


def exercise_type_for_mission(title: str) -> str:
    low = str(title or "").lower()
    for needle, label in _EXERCISE_TYPES:
        if needle in low:
            return label
    return ""


def key_label(token: str) -> str:
    """'Bb' -> 'Bb major', 'C#m' -> 'C# minor' (the app's key label style)."""
    tok = str(token or "").strip()
    if not tok:
        return ""
    try:
        from music_theory import format_key_label_from_parts, split_key_center

        tonic, mode = split_key_center(tok)
        return format_key_label_from_parts(tonic, mode or "major")
    except Exception:
        return tok


def _pretty(text: str) -> str:
    """Musician-facing accidentals (b -> ♭, # -> ♯) for display only."""
    out = []
    s = str(text or "")
    for i, ch in enumerate(s):
        if ch == "#":
            out.append("♯")
        elif ch == "b" and i > 0 and s[i - 1] in "ABCDEFG":
            out.append("♭")
        else:
            out.append(ch)
    return "".join(out)


def _index_in(seq: list[str], key: str) -> int:
    from backing_key_cycle import _keys_equivalent

    for i, k in enumerate(seq):
        if _keys_equivalent(k, key):
            return i
    return -1


def _concert_display(session: dict[str, Any], token: str) -> str:
    """A concert key named with the live Key Spelling preference."""
    from backing_key_cycle import apply_spelling_prefs_to_key, spelling_prefs_from_session

    return apply_spelling_prefs_to_key(str(token or ""), spelling_prefs_from_session(session)) or str(token or "")


def _shape(session: dict[str, Any], sounding: str) -> dict[str, Any] | None:
    """The shared capo projection (playbar, cycle Lead Sheet and in-app sheet read the same)."""
    from backing_key_cycle import cycle_shape_projection

    return cycle_shape_projection(session, sounding)


def console_model(
    session: dict[str, Any],
    *,
    current_concert: str,
    status: str,
) -> dict[str, Any]:
    """Everything the transport shows for one cycle position.

    ``current_concert`` is the cycle position the console describes (concert
    token from the cycle sequence). Next is the following position in the
    configured sequence (Next / Previous move along it; the natural pass stops
    after the last key, manual Next wraps to the first).
    """
    from backing_key_cycle import (
        CYCLE_STEP_LABELS,
        cycle_chart_mode,
        cycle_key_sequence,
        cycle_sequence_index,
        cycle_step_name_for_interval,
        get_owner_cycle_session,
        project_cycle_display_key,
    )

    data = get_owner_cycle_session(session) or {}
    seq = list(cycle_key_sequence(session))
    n = len(seq)
    idx = _index_in(seq, current_concert) if current_concert else -1
    if idx < 0:
        idx = cycle_sequence_index(session) if n else 0
    cur = seq[idx] if n else str(current_concert or "")
    nxt = seq[(idx + 1) % n] if n else cur
    mode = cycle_chart_mode(session)

    def reading(tok: str) -> str:
        return str(project_cycle_display_key(session, tok) or tok)

    model: dict[str, Any] = {
        "status": status,
        "status_text": _STATUS_TEXT.get(status, status.title()),
        "mode": mode,
        "sequence": seq,
        "index": idx,
        "count": n,
        "position": f"{idx + 1} / {n}" if n else "",
        "wraps": bool(n and idx == n - 1),
        "current_concert": cur,
        "next_concert": nxt,
        "interval_label": CYCLE_STEP_LABELS.get(cycle_step_name_for_interval(data.get("interval")), ""),
        "direction_label": "Descending" if str(data.get("direction") or "up") == "down" else "Ascending",
        "show_sounding": False,
        "sounding_label": "",
        "next_sounding_label": "",
        "shape_key_label": "",
        "capo": None,
        "next_capo": None,
        "capo_wraps": False,
    }
    if mode == "shape":
        cur_proj = _shape(session, cur)
        next_proj = _shape(session, nxt)
        capo = int(cur_proj["capo_fret"]) if cur_proj else 0
        next_capo = int(next_proj["capo_fret"]) if next_proj else 0
        model.update(
            current_label=key_label(reading(cur)),
            next_label=key_label(reading(nxt)),
            shape_key_label=key_label(str((cur_proj or {}).get("shape_key") or reading(cur))),
            capo=capo,
            next_capo=next_capo,
            # The capo cannot keep climbing: the fixed shape returns to a lower
            # fret for the same sounding key an octave down (existing 0-11 rule).
            capo_wraps=bool(cur_proj) and next_capo < capo,
            show_sounding=True,
            sounding_label=key_label(_concert_display(session, cur)),
            next_sounding_label=key_label(_concert_display(session, nxt)),
        )
    elif mode == "written":
        model.update(
            current_label=key_label(reading(cur)),
            next_label=key_label(reading(nxt)),
            show_sounding=True,
            sounding_label=key_label(_concert_display(session, cur)),
            next_sounding_label=key_label(_concert_display(session, nxt)),
        )
    else:
        model.update(
            current_label=key_label(_concert_display(session, cur)),
            next_label=key_label(_concert_display(session, nxt)),
        )
    # Per-position labels so the page script can refresh the readouts on a
    # seamless handoff before Python re-renders.
    labels, sounding, capos = [], [], []
    for tok in seq:
        if mode == "concert":
            labels.append(key_label(_concert_display(session, tok)))
        else:
            labels.append(key_label(reading(tok)))
        sounding.append(key_label(_concert_display(session, tok)))
        if mode == "shape":
            proj = _shape(session, tok)
            capos.append(str(int(proj["capo_fret"])) if proj else "")
    model["labels"] = labels
    model["sounding_labels"] = sounding
    model["capo_labels"] = capos
    return model


# --------------------------------------------------------------------------- #
# Live Mission Example
# --------------------------------------------------------------------------- #


def _mission_base_concert(session: dict[str, Any]) -> str:
    """The saved Mission Practice Key the cycle is anchored on (never the cycle key)."""
    from backing_key_cycle import current_backing_owner_practice_key, get_owner_cycle_session

    data = get_owner_cycle_session(session) or {}
    return str(data.get("base_practice_key") or current_backing_owner_practice_key(session) or "").strip()


def _cycle_offset(from_key: str, to_key: str) -> int:
    from music_theory import semitone_distance

    try:
        return int(semitone_distance(from_key, to_key) or 0) % 12
    except Exception:
        return 0


def _sounding_chord(chord: str, *, base_concert: str, sounding: str) -> str:
    """The concert chord moved by the cycle offset, spelled in the sounding key."""
    src = str(chord or "").strip()
    if not src:
        return ""
    steps = _cycle_offset(base_concert, sounding)
    if not steps:
        return src
    try:
        from music_theory import transpose_chord

        return str(transpose_chord(src, steps, reference_key=sounding) or src)
    except Exception:
        return src


def live_mission_model(session: dict[str, Any], *, current_concert: str) -> dict[str, Any] | None:
    """The Mission example at the current cycle position, or None outside a Mission cycle.

    Ordinary instruments: derived from the canonical example, transposed by the
    cycle offset (the chord keeps its relationship to the key: Dm7 in C is Gm7
    in F), written in the instrument's key. Guitar Shape mode: the written
    shape, chord and notation stay exactly the stable example; only the capo
    and the sounding labels move.
    """
    from backing_key_cycle import OWNER_MISSION, is_cycle_active, resolve_cycle_owner

    if not is_cycle_active(session) or resolve_cycle_owner(session) != OWNER_MISSION:
        return None
    base = _mission_base_concert(session)
    cur = str(current_concert or "").strip()
    if not base or not cur:
        return None
    try:
        from mission_span_backing import active_span_backing
    except ImportError:
        active_span_backing = None  # type: ignore[assignment]
    if active_span_backing is not None and active_span_backing(session) is not None:
        return _live_span_model(session, base=base, current=cur)
    return _live_single_model(session, base=base, current=cur)


def _model_shell(session: dict[str, Any], *, base: str, current: str, title: str) -> dict[str, Any]:
    from backing_key_cycle import cycle_chart_mode, project_cycle_display_key

    mode = cycle_chart_mode(session)
    return {
        "kind": "single",
        "mode": mode,
        "title": title or "Mission",
        "exercise_type": exercise_type_for_mission(title),
        "instrument": str(session.get("instrument") or ""),
        "base_concert": base,
        "current_concert": current,
        "sounding_key": _concert_display(session, current),
        "chart_key": str(project_cycle_display_key(session, current) or current),
        "notation": "",
        "abc": "",
        "tab": "",
        "notes": "",
        "chords_written": [],
        "chords_sounding": [],
        "fallback": "",
    }


def _live_single_model(session: dict[str, Any], *, base: str, current: str) -> dict[str, Any]:
    import copy

    from improvisation_missions import (
        _CANON_KEY,
        _canon_for,
        _derive_mission_example_from_canon,
        build_mission_notation_abc,
        mission_practice_lick_payload,
    )

    payload = mission_practice_lick_payload(session)
    title = str((payload or {}).get("mission_title") or session.get("improv_mission_pick") or "")
    model = _model_shell(session, base=base, current=current, title=title)
    if not payload:
        model["fallback"] = (
            "This Mission has no notated example yet. Generate one on the Mission to read it here in every key."
        )
        return model
    inst = str(payload.get("instrument") or session.get("instrument") or "")
    model["instrument"] = inst
    motif0 = copy.deepcopy(payload.get("motif") or {})
    blob = {
        "chord": payload.get("chord") or payload.get("_concert_chord") or "",
        "motif": motif0,
        "concert_key": base,
        "display_key": str(payload.get("key_center") or base),
        "mission": title,
        "instrument": inst,
        "bpm": payload.get("bpm") or 100,
        _CANON_KEY: payload.get(_CANON_KEY),
    }
    canon = _canon_for(blob, base)
    concert_chord_base = str(motif0.get("_concert_chord") or payload.get("_concert_chord") or payload.get("chord") or "")
    mode = model["mode"]
    if mode == "shape":
        # Fixed shapes: the stable written example, unchanged. The capo moves the sound.
        dest = str(canon.get("concert_key") or base)
        dest_chart = str(canon.get("display_key") or payload.get("key_center") or dest)
    else:
        dest = model["sounding_key"]
        dest_chart = model["chart_key"]
    try:
        out = _derive_mission_example_from_canon(
            blob, canon, dest=dest, dest_chart=dest_chart, session_state=session
        )
    except Exception:
        out = dict(blob)
    motif = out.get("motif") if isinstance(out.get("motif"), dict) else motif0
    written_chord = str(motif.get("chord") or out.get("chord") or "")
    concert_chord = str(motif.get("_concert_chord") or "") or concert_chord_base
    if mode == "shape":
        sounding_chord = _sounding_chord(concert_chord_base, base_concert=base, sounding=model["sounding_key"])
    elif mode == "written":
        sounding_chord = concert_chord
    else:
        sounding_chord = written_chord or concert_chord
        written_chord = sounding_chord
    try:
        bpm = int(payload.get("bpm") or 100)
    except (TypeError, ValueError):
        bpm = 100
    try:
        # Rebuilt with the instrument so the clef is right (bass clef for Bass).
        abc = build_mission_notation_abc(motif, mission=title, key_center=dest_chart, bpm=bpm, instrument=inst)
    except Exception:
        abc = str(out.get("abc") or "")
    try:
        from phrase_measure_format import format_phrase_notes_by_measure

        notes = format_phrase_notes_by_measure(motif)
    except Exception:
        notes = " – ".join(str(n) for n in (motif.get("notes") or []))
    model.update(
        motif=motif,
        abc=abc,
        tab=str(out.get("tab") or ""),
        notes=notes,
        rhythm=str(motif.get("rhythm") or ""),
        chords_written=[written_chord] if written_chord else [],
        chords_sounding=[sounding_chord] if sounding_chord else [],
        chart_key=dest_chart if mode != "shape" else model["chart_key"],
        level=str(payload.get("level") or ""),
    )
    return model


def _live_span_model(session: dict[str, Any], *, base: str, current: str) -> dict[str, Any]:
    """2- / 3-chord Missions: the whole progression moves consistently."""
    from improvisation_motif import build_motif_abc, build_motif_guitar_tab, notation_clef_for_instrument
    from mission_span_backing import (
        SPAN_LICK_KEY,
        active_span_backing,
        key_change_semitones,
        span_concert_chords,
    )
    from span_motif_engine import project_span_motif

    payload = active_span_backing(session) or {}
    lick = session.get(SPAN_LICK_KEY)
    title = str(payload.get("mission_label") or (lick or {}).get("mission_label") or "Mission")
    model = _model_shell(session, base=base, current=current, title=title)
    model["kind"] = "span"
    if not isinstance(lick, dict) or not lick.get("motif"):
        model["fallback"] = "This Mission has no notated example yet. Generate one on the Mission to read it here."
        return model
    mode = model["mode"]
    src = str(lick.get("practice_key") or payload.get("practice_key") or base)
    live = base if mode == "shape" else current
    chart = model["chart_key"] if mode != "shape" else _stable_chart_key(session, base)
    from music_theory import semitone_distance, transpose_chord

    shift = key_change_semitones(src, live) + (semitone_distance(live, chart) or 0)
    concert_chords = [c for c, _b in span_concert_chords(payload, live)]

    def to_chart(ch: str) -> str:
        try:
            from effective_practice_context import musician_facing_chord

            return musician_facing_chord(ch, concert_key=live, chart_key=chart) or ch
        except Exception:
            return ch

    written = [to_chart(c) for c in concert_chords]
    mapping = dict(zip([str(t.get("chord")) for t in payload.get("timeline") or []], written))
    motif = dict(lick["motif"])
    shown = (
        project_span_motif(motif, semitones=shift, chart_key=chart, project_chord=lambda ch: mapping.get(ch, ch))
        if shift
        else motif
    )
    inst = str(lick.get("instrument") or session.get("instrument") or "")
    try:
        bpm = int(lick.get("bpm") or 100)
    except (TypeError, ValueError):
        bpm = 100
    abc = build_motif_abc(
        shown,
        key_center=chart if shift else str(motif.get("key_center") or chart),
        bpm=bpm,
        title=f"Mission: {title}",
        clef=notation_clef_for_instrument(inst),
    )
    if mode == "shape":
        offset = _cycle_offset(base, current)
        sounding = [transpose_chord(c, offset, reference_key=model["sounding_key"]) if offset else c for c in concert_chords]
    else:
        sounding = [c for c, _b in span_concert_chords(payload, current)]
    try:
        from phrase_measure_format import format_phrase_notes_by_measure

        notes = format_phrase_notes_by_measure(shown)
    except Exception:
        notes = " – ".join(str(n) for n in (shown.get("notes") or []))
    model.update(
        motif=shown,
        abc=abc,
        tab=build_motif_guitar_tab(shown) if "guitar" in inst.lower() else "",
        notes=notes,
        rhythm=str(shown.get("rhythm") or ""),
        chords_written=written,
        chords_sounding=sounding,
        instrument=inst,
        level=str(lick.get("level") or ""),
    )
    return model


def _stable_chart_key(session: dict[str, Any], concert: str) -> str:
    try:
        from effective_practice_context import musician_facing_chart_key

        return str(musician_facing_chart_key(session, concert) or concert)
    except Exception:
        return concert


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #

CONSOLE_CSS = """
<style>
/* Key Cycling console -- Music Practice Coach palette: the dark navy / indigo
   cards (#0f172a -> #211e54), purple accents (#7c3aed / #8b5cf6), gold
   highlights (#facc15, #fbbf24 -> #f59e0b) and white / #eef2ff text. */
.kc-console{--kc-gold:#facc15;--kc-gold-2:#fbbf24;--kc-purple:#8b5cf6;--kc-purple-2:#7c3aed;
  --kc-ink:#eef2ff;--kc-muted:#c7d2fe;--kc-track:rgba(139,92,246,.28);
  position:relative;border-radius:20px;padding:.85rem 1rem .9rem;color:var(--kc-ink);
  background:linear-gradient(160deg,#0f172a 0%,#211e54 58%,#2e1065 100%);
  border:1px solid rgba(250,204,21,.28);box-shadow:0 10px 28px rgba(30,27,75,.35);
  display:flex;flex-direction:column;align-items:stretch;gap:.55rem;overflow:hidden}
.kc-console *{box-sizing:border-box}
.kc-title{display:flex;align-items:center;justify-content:space-between;gap:.5rem;flex-wrap:wrap}
.kc-brand{display:inline-flex;align-items:center;gap:.45rem;font-weight:900;font-size:1.28rem;letter-spacing:-.01em;line-height:1}
.kc-brand .kc-logo{width:2rem;height:2rem;flex:0 0 auto;display:block}
.kc-brand .kc-brand-key{color:#ffffff}
.kc-brand .kc-brand-cyc{color:var(--kc-gold);text-shadow:0 1px 3px rgba(0,0,0,.35)}
.kc-chip{display:inline-flex;align-items:center;gap:.35rem;font-size:.72rem;font-weight:800;letter-spacing:.05em;
  text-transform:uppercase;padding:.2rem .55rem;border-radius:999px;background:rgba(255,255,255,.08);
  border:1px solid rgba(199,210,254,.25);color:var(--kc-ink)}
.kc-console-dot{width:.5rem;height:.5rem;border-radius:50%;background:#94a3b8;display:inline-block}
.kc-console[data-status="playing"] .kc-console-dot{background:var(--kc-gold);box-shadow:0 0 0 3px rgba(250,204,21,.22)}
.kc-console[data-status="paused"] .kc-console-dot{background:var(--kc-purple)}
.kc-console[data-status="stopped"] .kc-console-dot{background:#f87171}
.kc-console[data-status="starting"] .kc-console-dot{background:var(--kc-muted)}
.kc-console-pos{font-size:.74rem;color:var(--kc-muted);text-align:center}
.kc-sounding{text-align:center;margin-top:.1rem}
.kc-sounding .kc-console-cap{display:block}
.kc-sounding-key{font-size:1.5rem;font-weight:900;color:#ffffff;line-height:1.15}
.kc-sounding-note{font-size:.72rem;color:var(--kc-muted);font-style:italic}
.kc-ring{--kc-p:0%;width:7.2rem;height:7.2rem;margin:.15rem auto .05rem;border-radius:50%;display:grid;place-items:center;
  background:conic-gradient(#8b5cf6 0%,#facc15 var(--kc-p),rgba(139,92,246,.26) var(--kc-p),rgba(139,92,246,.26) 100%);
  box-shadow:0 0 18px rgba(139,92,246,.35);transition:background .4s ease}
.kc-ring-in{width:calc(100% - 14px);height:calc(100% - 14px);border-radius:50%;background:#18153f;
  display:flex;flex-direction:column;align-items:center;justify-content:center;gap:.1rem}
.kc-ring-pos{font-size:1.35rem;font-weight:900;color:#ffffff;line-height:1}
.kc-ring-sub{font-size:.58rem;font-weight:800;color:#c7d2fe;letter-spacing:.07em;text-transform:uppercase}
.kc-console[data-status="paused"] .kc-ring{filter:saturate(.6)}
.kc-console-keys{display:grid;grid-template-columns:1fr auto 1fr;align-items:start;gap:.4rem;text-align:center}
.kc-console-sep{width:1px;align-self:stretch;background:rgba(199,210,254,.25)}
.kc-console-cell{min-width:0}
.kc-console-cap{font-size:.7rem;text-transform:uppercase;letter-spacing:.07em;color:var(--kc-muted);font-weight:700}
.kc-console-big{font-size:1.5rem;font-weight:900;line-height:1.15;color:#ffffff;word-break:break-word}
.kc-console-mid{font-size:1.5rem;font-weight:800;line-height:1.15;color:#e0e7ff;word-break:break-word}
.kc-console-tag{display:inline-block;margin-top:.1rem;font-size:.68rem;font-weight:800;letter-spacing:.05em;
  text-transform:uppercase;color:var(--kc-gold)}
.kc-dots{display:flex;justify-content:center;flex-wrap:wrap;gap:.28rem;margin-top:.1rem}
.kc-dot{width:.42rem;height:.42rem;border-radius:50%;background:rgba(199,210,254,.3)}
.kc-dot.is-now{background:var(--kc-gold);box-shadow:0 0 0 2px rgba(250,204,21,.25)}
.kc-dot.is-next{background:var(--kc-purple)}
.kc-console-foot{display:flex;flex-wrap:wrap;justify-content:center;gap:.2rem .9rem;font-size:.8rem;color:var(--kc-muted)}
.kc-console-foot strong{color:#ffffff;font-weight:800}
.kc-console-note{font-size:.76rem;color:var(--kc-muted);text-align:center}
.ui-key-cycle-playbar .ui-key-cycle-seq{display:none!important}
.kc-sr{position:absolute!important;width:1px!important;height:1px!important;overflow:hidden!important;
  clip:rect(0 0 0 0)!important;white-space:nowrap!important}
.kc-live{border-radius:20px;padding:.75rem .95rem;color:#eef2ff;
  background:linear-gradient(160deg,#0f172a 0%,#211e54 70%,#2e1065 100%);
  border:1px solid rgba(139,92,246,.45);box-shadow:0 10px 28px rgba(30,27,75,.3)}
.kc-live-head{display:flex;align-items:center;gap:.45rem;font-size:.74rem;text-transform:uppercase;letter-spacing:.07em;
  font-weight:800;color:#c7d2fe}
.kc-live-head .kc-live-icon{width:1.05rem;height:1.05rem;display:block}
.kc-live-title{font-weight:800;font-size:1rem;line-height:1.25;margin:.25rem 0 .1rem;color:#ffffff}
.kc-live-type{display:inline-block;font-size:.95rem;font-weight:700;color:#c4b5fd;margin-right:.35rem}
.kc-live-row{display:flex;flex-wrap:wrap;align-items:baseline;gap:.2rem .9rem;font-size:.84rem;margin-top:.2rem;color:#c7d2fe}
.kc-live-row strong{color:#ffffff}
.kc-live-chord{font-size:1.45rem;font-weight:900;color:#facc15;letter-spacing:-.01em}
@media (max-width: 640px){
  .kc-console{padding:.75rem .7rem .8rem}
  .kc-console-big,.kc-console-mid{font-size:1.25rem}
  .kc-sounding-key{font-size:1.3rem}
  .kc-ring{width:6rem;height:6rem}
}
</style>
"""

_LOGO_SVG_SRC = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40">'
    '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
    '<stop offset="0" stop-color="#8b5cf6"/><stop offset="1" stop-color="#facc15"/></linearGradient></defs>'
    # Two cycling arcs with arrow heads around a note: motion + music.
    '<path d="M20 4a16 16 0 0 1 15.2 11" fill="none" stroke="url(#g)" stroke-width="3.2" stroke-linecap="round"/>'
    '<path d="M35.8 9.6l-.4 6.2-5.6-2.6" fill="none" stroke="#facc15" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>'
    '<path d="M20 36A16 16 0 0 1 4.8 25" fill="none" stroke="url(#g)" stroke-width="3.2" stroke-linecap="round"/>'
    '<path d="M4.2 30.4l.4-6.2 5.6 2.6" fill="none" stroke="#8b5cf6" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>'
    '<path d="M22.5 11v13.2a3.6 3.6 0 1 1-2-3.2V13.5l6-1.6v3.2z" fill="#ffffff"/>'
    "</svg>"
)


def _svg_img(svg: str, cls: str) -> str:
    """Inline SVG is dropped by st.html's sanitizer; a data-URI image is kept."""
    from urllib.parse import quote

    return f'<img class="{cls}" alt="" aria-hidden="true" src="data:image/svg+xml,{quote(svg)}">'


_LOGO_SVG = _svg_img(_LOGO_SVG_SRC, "kc-logo")

_LIVE_ICON_SVG = _svg_img(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20">'
    '<circle cx="10" cy="10" r="8" fill="none" stroke="#8b5cf6" stroke-width="2"/>'
    '<circle cx="10" cy="10" r="3.6" fill="#facc15"/></svg>',
    "kc-live-icon",
)

def _ring_svg(index: int, count: int, interval_label: str) -> str:
    """Cycle progress ring (CSS conic gradient; purple to gold as the cycle advances)."""
    pct = (100.0 * (index + 1) / count) if count else 0.0
    sub = {"Circle of Fourths": "Fourths", "Whole tones": "Whole tones", "Semitones": "Semitones"}.get(
        interval_label, str(interval_label or "")
    )
    return (
        f'<div class="kc-ring" style="--kc-p:{pct:.1f}%" role="img" aria-label="Key {index + 1} of {count}">'
        '<div class="kc-ring-in">'
        f'<div class="kc-ring-pos kc-console-position">{index + 1} / {count}</div>'
        f'<div class="kc-ring-sub">{html.escape(sub)}</div>'
        "</div></div>"
    )


def _cell(cap: str, value: str, *, cls: str, big: bool = True, tag: str = "", sr: str = "") -> str:
    size = "kc-console-big" if big else "kc-console-mid"
    tag_html = f'<div class="kc-console-tag">{html.escape(tag)}</div>' if tag else ""
    return (
        f'<div class="kc-console-cell"><div class="kc-console-cap">{html.escape(cap)}</div>'
        f'<div class="{size} {cls}" aria-label="{html.escape(sr or cap)}">{html.escape(_pretty(value)) or "—"}</div>'
        f"{tag_html}</div>"
    )


def _dots(index: int, count: int) -> str:
    if not count or count > 12:
        return ""
    nxt = (index + 1) % count
    out = []
    for i in range(count):
        cls = "kc-dot is-now" if i == index else ("kc-dot is-next" if i == nxt else "kc-dot")
        out.append(f'<span class="{cls}" data-i="{i}"></span>')
    return f'<div class="kc-dots" aria-hidden="true">{"".join(out)}</div>'


def console_readout_html(model: dict[str, Any]) -> str:
    """The console card (no buttons): title, conditional Sounding Key, ring, Current / Next.

    Classes are refreshed by the page script on a seamless handoff.
    """
    mode = model.get("mode")
    status = str(model.get("status") or "")
    title = (
        '<div class="kc-title">'
        f'<span class="kc-brand">{_LOGO_SVG}<span><span class="kc-brand-key">Key </span>'
        '<span class="kc-brand-cyc">Cycling</span></span></span>'
        f'<span class="kc-chip"><span class="kc-console-dot" aria-hidden="true"></span>'
        f'<span class="kc-console-status-text">{html.escape(model.get("status_text") or "")}</span></span>'
        "</div>"
        f'<div class="kc-console-pos">{html.escape(str(model.get("interval_label") or ""))} · '
        f'{html.escape(str(model.get("direction_label") or ""))}</div>'
    )
    sounding = ""
    if model.get("show_sounding"):
        note = "Capo moves the sound; the shape stays" if mode == "shape" else "Concert pitch you hear"
        sounding = (
            '<div class="kc-sounding"><span class="kc-console-cap">Sounding key</span>'
            f'<div class="kc-sounding-key kc-console-sounding">{html.escape(_pretty(model.get("sounding_label") or ""))}</div>'
            f'<div class="kc-sounding-note">{html.escape(note)}</div></div>'
        )
    ring = _ring_svg(int(model.get("index") or 0), int(model.get("count") or 0), str(model.get("interval_label") or ""))
    sep = '<div class="kc-console-sep" aria-hidden="true"></div>'
    if mode == "shape":
        keys = (
            '<div class="kc-console-keys">'
            + _cell("Current capo", f"Fret {model.get('capo')}", cls="kc-console-capo", tag="Capo")
            + sep
            + _cell("Next capo", f"Fret {model.get('next_capo')}", cls="kc-console-next-capo", big=False,
                    tag="↺ lower fret, same shape" if model.get("capo_wraps") else "Capo")
            + "</div>"
        )
        foot = (
            '<div class="kc-console-foot">'
            f'<span>Shape key <strong>{html.escape(_pretty(model.get("shape_key_label") or ""))}</strong> · fixed</span>'
            f'<span>Next sounding <strong class="kc-console-next-sounding">{html.escape(_pretty(model.get("next_sounding_label") or ""))}</strong></span>'
            "</div>"
        )
    else:
        tag = "Written" if mode == "written" else ""
        keys = (
            '<div class="kc-console-keys">'
            + _cell("Current key", str(model.get("current_label") or ""), cls="kc-console-current", tag=tag)
            + sep
            + _cell("Next key", str(model.get("next_label") or ""), cls="kc-console-next", big=False, tag=tag)
            + "</div>"
        )
        foot = ""
        if model.get("show_sounding"):
            foot = (
                '<div class="kc-console-foot">'
                f'<span>Next sounding <strong class="kc-console-next-sounding">{html.escape(_pretty(model.get("next_sounding_label") or ""))}</strong></span>'
                "</div>"
            )
    dots = _dots(int(model.get("index") or 0), int(model.get("count") or 0))
    note = ""
    if model.get("wraps"):
        note = '<div class="kc-console-note">Last key of the cycle — Next returns to the first key.</div>'
    if status == CONSOLE_STOPPED:
        note = '<div class="kc-console-note">Stopped. Press Play on the card to start the cycle again from its first key.</div>'
    return f"{title}{sounding}{ring}{keys}{dots}{foot}{note}"


def render_live_mission_panel(st: Any, session: dict[str, Any], model: dict[str, Any]) -> None:
    """The Live Mission Example beside the transport (below it on a phone)."""
    mode = model.get("mode")
    title = str(model.get("title") or "Mission")
    etype = str(model.get("exercise_type") or "")
    written = " → ".join(_pretty(c) for c in model.get("chords_written") or [])
    sounding = " → ".join(_pretty(c) for c in model.get("chords_sounding") or [])
    rows: list[str] = []
    if mode == "shape":
        rows.append(f"Shape key <strong>{html.escape(_pretty(key_label(model.get('chart_key') or '')))}</strong> · fixed")
        rows.append(f"Sounding <strong>{html.escape(_pretty(key_label(model.get('sounding_key') or '')))}</strong>")
    elif mode == "written":
        rows.append(f"Written <strong>{html.escape(_pretty(key_label(model.get('chart_key') or '')))}</strong>")
        rows.append(f"Sounding <strong>{html.escape(_pretty(key_label(model.get('sounding_key') or '')))}</strong>")
    else:
        rows.append(f"Key <strong>{html.escape(_pretty(key_label(model.get('sounding_key') or '')))}</strong>")
    chord_line = ""
    if written:
        lead = "Shape chord" if mode == "shape" else ("Written chord" if mode == "written" else "Chord")
        chord_line = (
            f'<div class="kc-live-row"><span>{lead}</span> <span class="kc-live-chord">{html.escape(written)}</span>'
        )
        if mode in {"shape", "written"} and sounding and sounding != written:
            chord_line += f'<span>sounds as <strong>{html.escape(sounding)}</strong></span>'
        chord_line += "</div>"
    type_html = f'<span class="kc-live-type">{html.escape(etype)}</span>' if etype else ""
    st.markdown(
        CONSOLE_CSS
        + '<div class="kc-live" data-kc-live-mission="1">'
        f'<div class="kc-live-head">{_LIVE_ICON_SVG}<span>Live Mission Example</span></div>'
        f'<div class="kc-live-title">{type_html}<span>{html.escape(title)}</span></div>'
        f"{chord_line}"
        f'<div class="kc-live-row">{"".join(f"<span>{r}</span>" for r in rows)}</div>'
        "</div>",
        unsafe_allow_html=True,
    )
    if model.get("fallback"):
        st.caption(str(model["fallback"]))
        return
    if model.get("notes"):
        st.markdown(f"**Notes:** `{model['notes']}`")
    abc = str(model.get("abc") or "")
    if abc:
        try:
            from improvisation_intelligence_ui import _focus_expression_abc, _render_motif_sheet_music

            motif = model.get("motif") or {}
            shown_abc, _note = _focus_expression_abc(
                session, abc, motif, instrument=str(model.get("instrument") or ""), level=str(model.get("level") or "")
            )
            n_notes = len(motif.get("notes") or [])
            _render_motif_sheet_music(st, shown_abc, height=min(560, max(300, 240 + n_notes * 12)))
        except Exception:
            st.code(abc, language=None)
    if model.get("tab"):
        st.markdown("**Guitar TAB**" + (" — same shapes at every capo position" if mode == "shape" else ""))
        st.code(str(model["tab"]), language=None)


__all__ = [
    "CONSOLE_CSS",
    "CONSOLE_PAUSED",
    "CONSOLE_PLAYING",
    "CONSOLE_STARTING",
    "CONSOLE_STOPPED",
    "console_model",
    "console_readout_html",
    "exercise_type_for_mission",
    "key_label",
    "live_mission_model",
    "render_live_mission_panel",
]
