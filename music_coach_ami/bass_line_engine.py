"""Compose playable bass lines from active chart harmony + ABC notation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from music_coach_ami.notation_profile import (
    NotationProfile,
    apply_register_override,
    notation_profile_for_instrument,
)


def _clean(text: object) -> str:
    return str(text or "").strip()


def _level_label(level: str) -> str:
    low = _clean(level).lower()
    if "advanced" in low:
        return "advanced"
    if "begin" in low or "easy" in low or "simple" in low:
        return "beginner"
    return "intermediate"


def _is_walking_focus(focus: str, *, style: str = "") -> bool:
    blob = f"{focus} {style}".lower()
    return "walking" in blob or "walk bass" in blob


def _spell_root(chord: str, reference_key: str) -> str:
    from music_theory import (
        chord_root_for_theory,
        normalize_chord_for_theory,
        pitch_class_from_spelled_note,
        spell_note_in_key,
    )

    theory = normalize_chord_for_theory(chord)
    root_name = chord_root_for_theory(theory)
    if not root_name:
        return "?"
    pc = pitch_class_from_spelled_note(root_name)
    return spell_note_in_key(pc, reference_key or "C")


def _chord_tones(chord: str, reference_key: str) -> list[str]:
    from improvisation_motif import chord_tone_names

    return [t for t in chord_tone_names(chord, reference_key=reference_key) if t]


def _note_midi(note: str, octave: int) -> int:
    from music_theory import midi_from_spelled_note

    return int(midi_from_spelled_note(note, octave=octave))


def _midi_to_note(midi: int, reference_key: str) -> str:
    from music_theory import spell_note_in_key

    return spell_note_in_key(int(midi) % 12, reference_key)


def _spell_approach_midi(midi: int, *, target_note: str, target_midi: int, reference_key: str) -> str:
    """Spell an approach pitch by melodic function, not key-forced enharmonics.

    Chromatic lower neighbor of C → B (not Cb). Chromatic upper of Db → D.
    """
    from music_theory import pitch_class_from_spelled_note

    pc = int(midi) % 12
    tpc = pitch_class_from_spelled_note(target_note) % 12
    delta = (pc - tpc) % 12
    if delta > 6:
        delta -= 12
    # Half-step neighbors: preserve chromatic letter function vs target spelling.
    letter = re.sub(r"[^A-Ga-g]", "", target_note)[:1].upper() or "C"
    letters = "CDEFGAB"
    idx = letters.find(letter)
    if delta == -1 and idx >= 0:
        # Lower chromatic: previous letter, accidentals to match pitch class.
        prev = letters[(idx - 1) % 7]
        return _match_letter_to_pc(prev, pc)
    if delta == 1 and idx >= 0:
        nxt = letters[(idx + 1) % 7]
        return _match_letter_to_pc(nxt, pc)
    # Whole-step / other: prefer key spelling when diatonic, else letter-aware.
    spelled = _midi_to_note(midi, reference_key)
    if abs(delta) == 2 and idx >= 0:
        # Diatonic-ish approach: letter two steps when it matches PC.
        step = -1 if delta < 0 else 1
        cand = letters[(idx + step) % 7]
        matched = _match_letter_to_pc(cand, pc)
        if pitch_class_from_spelled_note(matched) % 12 == pc:
            return matched
    return spelled


def _match_letter_to_pc(letter: str, pc: int) -> str:
    """Pick accidental for *letter* so the note matches pitch class *pc*."""
    from music_theory import pitch_class_from_spelled_note

    base = {
        "C": 0,
        "D": 2,
        "E": 4,
        "F": 5,
        "G": 7,
        "A": 9,
        "B": 11,
    }[letter.upper()]
    diff = (pc - base) % 12
    if diff > 6:
        diff -= 12
    if diff == 0:
        return letter.upper()
    if diff == 1:
        return f"{letter.upper()}#"
    if diff == -1:
        return f"{letter.upper()}b"
    if diff == 2:
        return f"{letter.upper()}##"
    if diff == -2:
        return f"{letter.upper()}bb"
    # Fallback natural letter (should be rare)
    return letter.upper()


def _clamp_midi(midi: int, low: int, high: int) -> int:
    while midi < low:
        midi += 12
    while midi > high:
        midi -= 12
    if midi < low:
        return low
    if midi > high:
        return high
    return midi


def _place_pitch(note: str, *, prefer_midi: int, low: int, high: int) -> tuple[str, int, int]:
    """Choose written octave so *note* lands near prefer_midi within [low, high]."""
    from music_theory import pitch_class_from_spelled_note

    pc = pitch_class_from_spelled_note(note)
    # Candidate midis for this pitch class near prefer_midi
    base = prefer_midi - ((prefer_midi - pc) % 12)
    candidates = [base - 12, base, base + 12, base + 24]
    best = None
    best_dist = 10**9
    for midi in candidates:
        clamped = _clamp_midi(midi, low, high)
        if clamped % 12 != pc % 12:
            continue
        dist = abs(clamped - prefer_midi)
        if dist < best_dist:
            best_dist = dist
            best = clamped
    if best is None:
        best = _clamp_midi(prefer_midi - (prefer_midi % 12) + (pc % 12), low, high)
    octave = (best // 12) - 1
    return note, octave, best


def _nearest_chord_tone_midi(
    tones: list[str],
    *,
    from_midi: int,
    low: int,
    high: int,
    reference_key: str,
    avoid_midi: int | None = None,
) -> tuple[str, int, int]:
    best: tuple[str, int, int] | None = None
    best_dist = 10**9
    for tone in tones:
        _n, octv, midi = _place_pitch(tone, prefer_midi=from_midi, low=low, high=high)
        if avoid_midi is not None and midi == avoid_midi:
            continue
        dist = abs(midi - from_midi)
        # Prefer stepwise motion when distances tie
        if dist < best_dist or (dist == best_dist and best is not None and midi < best[2]):
            best_dist = dist
            best = (tone, octv, midi)
    if best is None and tones:
        return _place_pitch(tones[0], prefer_midi=from_midi, low=low, high=high)
    if best is None:
        return _place_pitch("C", prefer_midi=from_midi, low=low, high=high)
    return best


def _approach_candidates(
    *,
    target_note: str,
    target_midi: int,
    from_midi: int,
    level: str,
    bar_idx: int,
    reference_key: str,
    low: int,
    high: int,
) -> list[tuple[str, int, int, str]]:
    """Return (note, octave, midi, kind) approach options into next root."""
    out: list[tuple[str, int, int, str]] = []
    # Chromatic / diatonic neighbors around the target
    raw = [
        (target_midi - 1, "chromatic_below"),
        (target_midi + 1, "chromatic_above"),
        (target_midi - 2, "diatonic_below"),
        (target_midi + 2, "diatonic_above"),
    ]
    for midi0, kind in raw:
        midi = _clamp_midi(midi0, low, high)
        if midi == target_midi:
            continue
        note = _spell_approach_midi(midi, target_note=target_note, target_midi=target_midi, reference_key=reference_key)
        out.append((note, (midi // 12) - 1, midi, kind))
    # Nearby scale step from current pitch toward target
    step = 1 if target_midi >= from_midi else -1
    mid = _clamp_midi(from_midi + step, low, high)
    if mid != target_midi:
        note = _midi_to_note(mid, reference_key)
        out.append((note, (mid // 12) - 1, mid, "scale_step"))
    # Beginner: de-prioritize chromatic every bar — keep them available but tagged.
    if level == "beginner" and bar_idx % 2 == 0:
        # Prefer diatonic / scale on even bars by ordering
        out.sort(key=lambda t: 0 if t[3].startswith("diatonic") or t[3] == "scale_step" else 1)
    elif level == "beginner":
        out.sort(key=lambda t: 0 if t[3].startswith("chromatic") else 1)
    elif level == "intermediate":
        out.sort(key=lambda t: 0 if "chromatic" in t[3] else 1)
    return out


def _path_cost(
    midis: list[int],
    *,
    next_root_midi: int,
    level: str,
    approach_kind: str,
) -> float:
    """Score an entire bar path using written MIDI distances."""
    cost = 0.0
    for a, b in zip(midis, midis[1:]):
        leap = abs(b - a)
        if leap == 0:
            cost += 80.0  # unintended duplicate
        elif leap == 1:
            cost += 0.5
        elif leap == 2:
            cost += 1.0
        elif leap <= 4:
            cost += 2.0 + (leap - 2) * 0.5
        elif leap <= 7:
            cost += 6.0 + (leap - 5) * 2.0
        else:
            cost += 18.0 + (leap - 7) * 6.0
    # Approach into next root
    approach = abs(midis[-1] - next_root_midi)
    if approach == 1:
        cost += 0.5 if level != "beginner" else 1.5
    elif approach == 2:
        cost += 1.5
    elif approach <= 4:
        cost += 5.0
    else:
        cost += 14.0
    # Beginner: chromatic approaches are optional teaching tools, not defaults.
    if level == "beginner":
        if approach_kind.startswith("chromatic"):
            cost += 4.0
        if approach_kind.startswith("diatonic") or approach_kind == "scale_step":
            cost -= 1.0
        # Extra penalty for any internal leap > P4
        for a, b in zip(midis, midis[1:]):
            if abs(b - a) > 5:
                cost += 10.0
    elif level == "intermediate":
        if approach_kind.startswith("chromatic"):
            cost -= 0.5
    else:  # advanced
        if approach_kind.startswith("chromatic"):
            cost -= 1.0
    return cost


def _candidate_midis_for_tones(
    tones: list[str],
    *,
    prefer_midi: int,
    low: int,
    high: int,
    limit: int = 4,
) -> list[tuple[str, int, int]]:
    scored: list[tuple[float, str, int, int]] = []
    seen: set[int] = set()
    for tone in tones:
        for prefer in (prefer_midi, prefer_midi - 12, prefer_midi + 12):
            note, octv, midi = _place_pitch(tone, prefer_midi=prefer, low=low, high=high)
            if midi in seen:
                continue
            seen.add(midi)
            scored.append((abs(midi - prefer_midi), note, octv, midi))
    scored.sort(key=lambda t: t[0])
    return [(n, o, m) for _, n, o, m in scored[:limit]]


def _select_walking_bar(
    *,
    root: str,
    tones: list[str],
    third: str,
    fifth: str,
    seventh: str,
    next_root: str,
    prev_midi: int,
    center: int,
    low: int,
    high: int,
    level: str,
    bar_idx: int,
    reference_key: str,
) -> tuple[list[BassLineNote], int]:
    """Enumerate a small set of whole-bar paths and pick the lowest-cost realization."""
    root_note, root_oct, root_midi = _place_pitch(root, prefer_midi=prev_midi, low=low, high=high)
    if abs(root_midi - prev_midi) > 7:
        root_note, root_oct, root_midi = _place_pitch(root, prefer_midi=center, low=low, high=high)

    next_root_placed = _place_pitch(next_root, prefer_midi=root_midi, low=low, high=high)
    next_root_midi = next_root_placed[2]

    # Beat-2 pool: chord tones near root
    if level == "advanced":
        beat2_tones = [seventh, third, fifth]
    elif level == "intermediate":
        beat2_tones = [third, fifth, seventh]
    else:
        beat2_tones = [fifth, third, root]
    beat2_opts = _candidate_midis_for_tones(beat2_tones, prefer_midi=root_midi, low=low, high=high, limit=3)

    # Beat-3 pool: chord / scale tones toward next root
    if level == "beginner":
        beat3_tones = [third, fifth, root]
    else:
        beat3_tones = [third, fifth, seventh, root]
    mid_pref = (root_midi + next_root_midi) // 2
    beat3_opts = _candidate_midis_for_tones(beat3_tones, prefer_midi=mid_pref, low=low, high=high, limit=3)
    # Also allow a one-step connector from each beat2 (added during search)

    best_cost = 10**9
    best_notes: list[BassLineNote] | None = None
    best_last = root_midi

    for t2, o2, m2 in beat2_opts:
        if m2 == root_midi:
            continue
        for t3, o3, m3 in beat3_opts + _candidate_midis_for_tones(
            beat3_tones, prefer_midi=m2 + (1 if next_root_midi >= m2 else -1), low=low, high=high, limit=2
        ):
            if m3 == m2:
                continue
            approaches = _approach_candidates(
                target_note=next_root,
                target_midi=next_root_midi,
                from_midi=m3,
                level=level,
                bar_idx=bar_idx,
                reference_key=reference_key,
                low=low,
                high=high,
            )
            for t4, o4, m4, kind in approaches[:6]:
                if m4 == m3:
                    continue
                midis = [root_midi, m2, m3, m4]
                cost = _path_cost(midis, next_root_midi=next_root_midi, level=level, approach_kind=kind)
                # Prefer clear root on beat 1 (already fixed) and smooth entry from prev
                cost += abs(root_midi - prev_midi) * 0.25
                if cost < best_cost:
                    best_cost = cost
                    best_notes = [
                        BassLineNote(root_note, "quarter", root_oct),
                        BassLineNote(t2, "quarter", o2),
                        BassLineNote(t3, "quarter", o3),
                        BassLineNote(t4, "quarter", o4),
                    ]
                    best_last = m4

    if best_notes is None:
        # Deterministic fallback: root–fifth–scale–approach
        t2, o2, m2 = _place_pitch(fifth, prefer_midi=root_midi + 7, low=low, high=high)
        if m2 == root_midi:
            t2, o2, m2 = _place_pitch(third, prefer_midi=root_midi + 4, low=low, high=high)
        t3, o3, m3 = _scale_connector(
            m2, toward_midi=next_root_midi, reference_key=reference_key, low=low, high=high, avoid_midi=m2
        )
        apps = _approach_candidates(
            target_note=next_root,
            target_midi=next_root_midi,
            from_midi=m3,
            level=level,
            bar_idx=bar_idx,
            reference_key=reference_key,
            low=low,
            high=high,
        )
        t4, o4, m4, _k = apps[0] if apps else (next_root, root_oct, next_root_midi, "fallback")
        best_notes = [
            BassLineNote(root_note, "quarter", root_oct),
            BassLineNote(t2, "quarter", o2),
            BassLineNote(t3, "quarter", o3),
            BassLineNote(t4, "quarter", o4),
        ]
        best_last = m4

    return best_notes, best_last


def _scale_connector(
    from_midi: int,
    *,
    toward_midi: int,
    reference_key: str,
    low: int,
    high: int,
    avoid_midi: int | None = None,
) -> tuple[str, int, int]:
    step = 1 if toward_midi >= from_midi else -1
    midi = _clamp_midi(from_midi + step, low, high)
    if avoid_midi is not None and midi == avoid_midi:
        midi = _clamp_midi(from_midi + 2 * step, low, high)
    if midi == from_midi:
        midi = _clamp_midi(from_midi + 2 * step, low, high)
    note = _midi_to_note(midi, reference_key)
    return note, (midi // 12) - 1, midi


@dataclass(frozen=True)
class BassLineNote:
    note: str
    duration: str
    written_octave: int


@dataclass(frozen=True)
class BassLineBar:
    chord: str
    notes: tuple[BassLineNote, ...]


@dataclass(frozen=True)
class BassLineComposition:
    bars: tuple[BassLineBar, ...]
    reference_key: str
    meter: str
    section_label: str
    strategy: str
    notation_profile: NotationProfile
    style: str = ""


def compose_bass_line_from_chords(
    chords: list[str],
    *,
    reference_key: str,
    level: str,
    instrument: str,
    meter: str = "4/4",
    section_label: str = "",
    max_bars: int = 8,
    practice_focus: str = "",
    style: str = "",
    difficulty_override: str = "",
    register: str = "",
) -> BassLineComposition:
    """Deterministic phrase-aware bass line aligned to one chord per bar."""
    usable = [_clean(c) for c in chords if _clean(c)][:max_bars]
    lvl = _level_label(difficulty_override or level)
    walking = _is_walking_focus(practice_focus, style=style)
    profile = apply_register_override(notation_profile_for_instrument(instrument), register)
    ref = _clean(reference_key) or "C"
    low, high = profile.midi_low, profile.midi_high
    center = (low + high) // 2

    bars: list[BassLineBar] = []
    prev_midi = center
    strategy = "beginner_walking" if walking and lvl == "beginner" else (
        "intermediate_walking" if walking and lvl == "intermediate" else (
            "advanced_walking" if walking else f"{lvl}_bass_line"
        )
    )

    roots = [_spell_root(c, ref) for c in usable]
    tone_sets = [_chord_tones(c, ref) for c in usable]

    for idx, chord in enumerate(usable):
        root = roots[idx]
        tones = tone_sets[idx] or [root]
        third = tones[1] if len(tones) >= 2 else root
        fifth = tones[2] if len(tones) >= 3 else (tones[1] if len(tones) >= 2 else root)
        seventh = tones[3] if len(tones) >= 4 else third
        next_root = roots[idx + 1] if idx + 1 < len(usable) else root

        pitched: list[BassLineNote] = []

        if walking or lvl != "beginner":
            pitched, prev_midi = _select_walking_bar(
                root=root,
                tones=tones,
                third=third,
                fifth=fifth,
                seventh=seventh,
                next_root=next_root,
                prev_midi=prev_midi,
                center=center,
                low=low,
                high=high,
                level=lvl,
                bar_idx=idx,
                reference_key=ref,
            )
        else:
            # Beginner non-walking: root–fifth halves, smooth register
            root_note, root_oct, root_midi = _place_pitch(root, prefer_midi=prev_midi, low=low, high=high)
            if abs(root_midi - prev_midi) > 7:
                root_note, root_oct, root_midi = _place_pitch(root, prefer_midi=center, low=low, high=high)
            fifth_n, fifth_o, fifth_m = _place_pitch(fifth, prefer_midi=root_midi + 7, low=low, high=high)
            if fifth_m == root_midi:
                fifth_n, fifth_o, fifth_m = _place_pitch(fifth, prefer_midi=root_midi - 5, low=low, high=high)
            pitched = [
                BassLineNote(root_note, "half", root_oct),
                BassLineNote(fifth_n, "half", fifth_o),
            ]
            prev_midi = fifth_m

        bars.append(BassLineBar(chord=chord, notes=tuple(pitched)))

    return BassLineComposition(
        bars=tuple(bars),
        reference_key=ref,
        meter=meter or "4/4",
        section_label=_clean(section_label),
        strategy=strategy,
        notation_profile=profile,
        style="walking_bass" if walking else _clean(style) or "bass_line",
    )


def bar_written_midis(bar: BassLineBar) -> list[int]:
    """Written MIDI values for voice-leading / range assertions."""
    return [_note_midi(n.note, n.written_octave) for n in bar.notes]


def build_bass_line_abc(
    composition: BassLineComposition,
    *,
    title: str = "Bass line",
    bpm: int = 84,
) -> str:
    from music_coach_ami.scale_engine import build_abc_from_chord_bass_line

    return build_abc_from_chord_bass_line(
        composition,
        title=title,
        bpm=bpm,
    )


def bass_line_play_summary(composition: BassLineComposition) -> list[str]:
    """Chord play lines without list markers — composer adds a single bullet each."""
    lines: list[str] = []
    for bar in composition.bars:
        note_text = " · ".join(f"**{n.note}** ({n.duration})" for n in bar.notes)
        lines.append(f"**{bar.chord}:** {note_text}")
    return lines


def composition_to_diagnostics(composition: BassLineComposition, chart: dict[str, Any]) -> dict[str, Any]:
    profile = composition.notation_profile
    return {
        "generation_strategy": composition.strategy,
        "bass_line_style": composition.style,
        "notation_clef": profile.clef,
        "written_register_octave": profile.written_octave,
        "sounding_to_written_shift": profile.sounding_to_written_shift,
        "written_midi_range": [profile.midi_low, profile.midi_high],
        "reference_key_spelling": composition.reference_key,
        "meter": composition.meter,
        "section_label": composition.section_label,
        "bars_generated": len(composition.bars),
        "generated_notes": [
            {
                "chord": bar.chord,
                "notes": [
                    {"note": n.note, "duration": n.duration, "written_octave": n.written_octave}
                    for n in bar.notes
                ],
            }
            for bar in composition.bars
        ],
        "chart_source": chart.get("chart_source"),
        "chart_available": chart.get("chart_available"),
        "active_section": chart.get("active_section"),
        "chord_timeline_used": list(chart.get("active_section_chords") or []),
        "practice_key": chart.get("practice_key"),
        "original_key": chart.get("original_key"),
    }
