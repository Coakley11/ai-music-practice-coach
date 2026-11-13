"""Measured features of a melody + descriptions / concept claims derived from them.

Nothing here reads a recipe or a title: every statement is computed from the events (and the
chords they sound over), and ``verify_concept_claim`` lets tests (and the UI) check that the
concept a candidate is *labelled* with really is what the notes do.
"""

from __future__ import annotations

from typing import Any

from composition_melody_audit import (
    LABEL_CHORD_TONE,
    LABEL_CHROMATIC_APPROACH,
    audit_melody,
    bar_beats,
    chord_at_beat,
    chord_info,
    chord_segments,
    is_compound,
    is_rest_event,
    tonic_pc,
)

_DEGREE_NAMES = {0: "tonic", 2: "2nd degree", 4: "3rd degree", 5: "4th degree", 7: "5th degree",
                 9: "6th degree", 11: "7th degree", 3: "minor 3rd degree", 8: "b6 degree", 10: "b7 degree"}


def _sounding(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [e for e in events or [] if isinstance(e, dict) and not is_rest_event(e) and e.get("midi") is not None]


def _is_off_pulse(beat: float, *, comp: bool) -> bool:
    return abs(beat % 3.0) > 1e-6 if comp else abs(beat - round(beat)) > 1e-6


def melody_features(
    events: list[dict[str, Any]],
    chords: list[str],
    *,
    key: str = "C",
    meter: str = "4/4",
) -> dict[str, Any]:
    bar = bar_beats(meter)
    comp = is_compound(meter)
    evs = [e for e in events or [] if isinstance(e, dict)]
    snd = _sounding(evs)
    total = max((float(e.get("beat") or 0) + float(e.get("duration_beats") or 1.0) for e in evs), default=0.0)
    midis = [int(e["midi"]) for e in snd]
    ivs = [midis[i + 1] - midis[i] for i in range(len(midis) - 1)]
    nonzero = [iv for iv in ivs if iv]
    up = sum(1 for iv in nonzero if iv > 0)
    down = len(nonzero) - up
    off = [e for e in snd if _is_off_pulse(float(e.get("beat") or 0), comp=comp)]
    accented_off = [e for e in off if str(e.get("articulation") or "") == "accent"]
    nbars = max(1, int(round(total / bar))) if total else 0
    # per-bar rhythm signatures (onset offsets + durations) for repetition detection
    sigs: list[tuple] = []
    for b in range(nbars):
        row = tuple(
            (round(float(e.get("beat") or 0) - b * bar, 3), round(float(e.get("duration_beats") or 1.0), 3),
             bool(is_rest_event(e)))
            for e in evs if b * bar - 1e-6 <= float(e.get("beat") or 0) < (b + 1) * bar - 1e-6
        )
        sigs.append(row)
    rows = audit_melody(evs, chords, key=key, meter=meter)
    strong_rows = [r for r in rows if r["strong"] and r["label"] != "rest"]
    peak_i = max(range(len(midis)), key=lambda i: midis[i]) if midis else 0
    return {
        "bars": nbars, "total_beats": total, "attacks": len(snd),
        "rests": sum(1 for e in evs if is_rest_event(e)),
        "attacks_per_bar": (len(snd) / nbars) if nbars else 0.0,
        "intervals": ivs,
        "stepwise_share": (sum(1 for iv in ivs if abs(iv) <= 2) / len(ivs)) if ivs else 0.0,
        "up_share": (up / len(nonzero)) if nonzero else 0.0,
        "down_share": (down / len(nonzero)) if nonzero else 0.0,
        "net_motion": (midis[-1] - midis[0]) if midis else 0,
        "range_semitones": (max(midis) - min(midis)) if midis else 0,
        "largest_leap": max((abs(iv) for iv in ivs), default=0),
        "offbeat_attacks": len(off), "accented_offbeat_attacks": len(accented_off),
        "offbeat_share": (len(off) / len(snd)) if snd else 0.0,
        "bar_rhythm_signatures": sigs,
        "repeated_rhythm_bars": sum(1 for i in range(len(sigs)) for j in range(i) if sigs[i] == sigs[j] and sigs[i]),
        "distinct_rhythm_bars": len(set(sigs)),
        "peak_pitch": snd[peak_i].get("pitch") if snd else "", "peak_position": (peak_i / max(1, len(snd) - 1)),
        "strong_chord_tone_share": (
            sum(1 for r in strong_rows if r["label"] == LABEL_CHORD_TONE) / len(strong_rows) if strong_rows else 1.0
        ),
        "chromatic_tones": sum(1 for r in rows if r["chromatic"]),
        "chromatic_approaches": sum(1 for r in rows if r["label"] == LABEL_CHROMATIC_APPROACH),
        "audit": rows,
    }


def phrase_split_beat(total_beats: float, meter: str = "4/4") -> float:
    bar = bar_beats(meter)
    nbars = max(1, int(round(total_beats / bar)))
    return (nbars // 2) * bar if nbars >= 2 else bar / 2.0


def question_answer_facts(
    events: list[dict[str, Any]], chords: list[str], *, key: str = "C", meter: str = "4/4"
) -> dict[str, Any]:
    """Question phrase = everything before the midpoint; answer = the rest."""
    snd = _sounding(events)
    if len(snd) < 2:
        return {"ok": False, "reason": "too few notes"}
    total = max(float(e.get("beat") or 0) + float(e.get("duration_beats") or 1.0) for e in events)
    split = phrase_split_beat(total, meter)
    q = [e for e in snd if float(e["beat"]) < split - 1e-6]
    a = [e for e in snd if float(e["beat"]) >= split - 1e-6]
    if not q or not a:
        return {"ok": False, "reason": "no second phrase"}
    t = tonic_pc(key)
    segs = chord_segments(chords, meter)
    q_end, a_end = q[-1], a[-1]
    q_pc, a_pc = int(q_end["midi"]) % 12, int(a_end["midi"]) % 12
    q_info = chord_info(chord_at_beat(segs, float(q_end["beat"])), key)
    a_info = chord_info(chord_at_beat(segs, float(a_end["beat"])), key)
    q_chord_tone = bool(q_info and q_pc in q_info.tone_pcs)
    q_open = q_pc != t and q_chord_tone
    stable_pc = t if (a_info and t in a_info.tone_pcs) else (a_info.root_pc if a_info else t)
    a_resolves = a_pc == stable_pc
    q_len, a_len = split, total - split
    return {
        "ok": q_open and a_resolves and min(q_len, a_len) / max(q_len, a_len) >= 0.5,
        "q_end": q_end.get("pitch"), "q_end_pc": q_pc, "q_open": q_open,
        "q_degree": _DEGREE_NAMES.get((q_pc - t) % 12, "chromatic degree"),
        "a_end": a_end.get("pitch"), "a_resolves": a_resolves,
        "a_on_tonic": a_pc == t, "a_chord": a_info.symbol if a_info else "",
        "a_descends": int(a[-1]["midi"]) < int(a[0]["midi"]),
        "q_beats": q_len, "a_beats": a_len, "split": split,
        "q_bars": int(round(q_len / bar_beats(meter))), "a_bars": int(round(a_len / bar_beats(meter))),
    }


def verify_concept_claim(
    concept_id: str, events: list[dict[str, Any]], chords: list[str], *, key: str = "C", meter: str = "4/4"
) -> tuple[bool, list[str]]:
    """Does the melody really do what ``concept_id`` says?  Returns (ok, failures)."""
    f = melody_features(events, chords, key=key, meter=meter)
    bad: list[str] = []
    if concept_id == "offbeat_accent":
        if f["accented_offbeat_attacks"] < 2:
            bad.append("fewer than two accented off-beat attacks")
        if f["offbeat_share"] < 0.4:
            bad.append("off-beat attacks are under 40% of the notes")
    elif concept_id == "question_answer":
        qa = question_answer_facts(events, chords, key=key, meter=meter)
        if not qa.get("ok"):
            bad.append(f"question/answer not recognisable: {qa}")
    elif concept_id == "direct_line":
        if f["stepwise_share"] < 0.6:
            bad.append("less than 60% stepwise motion")
        if max(f["up_share"], f["down_share"]) < 0.5:
            bad.append("no dominant direction")
    elif concept_id == "expressive_arch":
        if not (0.3 <= f["peak_position"] <= 0.85):
            bad.append("peak is not inside the phrase")
        if f["range_semitones"] < 7:
            bad.append("range under a fifth")
    elif concept_id == "groove_pocket":
        if f["rests"] < 1:
            bad.append("no rests")
    elif concept_id == "forward_climb":
        if f["offbeat_share"] < 0.3 and f["attacks_per_bar"] < 5:
            bad.append("not driving (too few attacks)")
        if f["up_share"] < 0.5:
            bad.append("mostly falling")
    elif concept_id == "sighing_descent":
        if f["down_share"] < 0.55 or f["net_motion"] >= 0:
            bad.append("not descending")
    elif concept_id == "motif_hook":
        if f["repeated_rhythm_bars"] < 1:
            bad.append("no repeated rhythmic cell")
    return (not bad, bad)


def describe_melody_with_harmony(
    events: list[dict[str, Any]],
    chords: list[str],
    *,
    key: str = "C",
    meter: str = "4/4",
    concept_id: str = "",
) -> str:
    """Prose from measured features only.  Concept-specific sentences appear only when the
    measured evidence for them is present."""
    snd = _sounding(events)
    if not snd:
        return "No pitched notes to describe yet."
    f = melody_features(events, chords, key=key, meter=meter)
    parts: list[str] = []
    parts.append(f"{f['attacks']} notes over {f['bars']} bar{'s' if f['bars'] != 1 else ''}"
                 f" ({f['attacks_per_bar']:.1f} per bar)")
    if f["stepwise_share"] >= 0.6:
        direction = "rising" if f["up_share"] >= 0.55 else ("falling" if f["down_share"] >= 0.55 else "wavering")
        parts.append(f"mostly stepwise, overall {direction}")
    elif f["largest_leap"] >= 7:
        parts.append(f"uses leaps up to {f['largest_leap']} semitones")
    else:
        parts.append("a balance of steps and small skips")
    parts.append(f"opens on {snd[0].get('pitch')} and peaks on {f['peak_pitch']}")
    if f["offbeat_attacks"]:
        if f["accented_offbeat_attacks"]:
            parts.append(
                f"{f['accented_offbeat_attacks']} of {f['attacks']} attacks are accented off-beats (syncopation)"
            )
        else:
            parts.append(f"{f['offbeat_attacks']} off-beat attacks")
    if f["rests"]:
        parts.append(f"{f['rests']} rest{'s' if f['rests'] != 1 else ''} for space")
    if concept_id == "question_answer":
        qa = question_answer_facts(events, chords, key=key, meter=meter)
        if qa.get("ok"):
            parts.append(
                f"question (bars 1-{qa['q_bars']}) ends open on {qa['q_end']}, the {qa['q_degree']}; "
                f"answer (bars {qa['q_bars'] + 1}-{qa['q_bars'] + qa['a_bars']}) settles on {qa['a_end']}"
                + (" (the tonic)" if qa["a_on_tonic"] else f" (root of {qa['a_chord']})")
            )
    if f["repeated_rhythm_bars"]:
        parts.append(f"repeats its rhythmic cell in {f['repeated_rhythm_bars']} bar(s)")
    parts.append(
        f"{round(100 * f['strong_chord_tone_share'])}% of structural beats land on chord tones"
    )
    if f["chromatic_approaches"]:
        parts.append(f"{f['chromatic_approaches']} chromatic approach tone(s), each resolving by semitone")
    last = snd[-1]
    parts.append(f"ends on {last.get('pitch')}")
    text = "; ".join(parts)
    return text[0].upper() + text[1:] + f". Written across all {len(chords)} chord occurrences."
