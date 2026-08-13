"""Horizontal, chord-aware melodic motion (not per-bar arpeggio dumps)."""

from __future__ import annotations

from typing import Any, Sequence


def _pc(note: str) -> int:
    from music_theory import pitch_class_from_spelled_note

    return int(pitch_class_from_spelled_note(note)) % 12


def _midi(note: str, octave: int) -> int:
    from music_theory import midi_from_spelled_note

    return int(midi_from_spelled_note(note, octave=octave))


def chord_vocabulary(chord: str, *, reference_key: str = "") -> dict[str, Any]:
    """Chord tones + fitting scale fragments for one harmony."""
    from improvisation_intelligence import spell_scale_notes
    from improvisation_motif import chord_tone_names
    from music_theory import classify_chord_quality, chord_root_for_theory, normalize_chord_for_theory

    head = str(chord or "").strip()
    tones = [t for t in (chord_tone_names(head, reference_key=reference_key) or []) if t]
    root = tones[0] if tones else (chord_root_for_theory(normalize_chord_for_theory(head)) or "C")
    if not tones:
        tones = [root]
    quality = classify_chord_quality(head)
    kind_map = {
        "major": "major",
        "maj7": "major",
        "minor": "dorian",
        "m7": "dorian",
        "dom": "mixolydian",
        "half-dim": "locrian",
        "dim": "locrian",
        "aug": "lydian",
        "sus": "mixolydian",
    }
    scale_kind = kind_map.get(quality, "major")
    low_chord = head.lower()
    if quality == "dom" and ("b9" in low_chord or "alt" in low_chord or "#9" in low_chord):
        scale_kind = "altered"
    scale = [n for n in spell_scale_notes(root, scale_kind, reference_key or root) if n]
    tone_by_pc = {_pc(t): t for t in tones}
    scale_spelled: list[str] = []
    seen: set[int] = set()
    for n in scale:
        pc = _pc(n)
        if pc in seen:
            continue
        seen.add(pc)
        scale_spelled.append(tone_by_pc.get(pc, n))
    for t in tones:
        if _pc(t) not in seen:
            scale_spelled.append(t)
            seen.add(_pc(t))
    extensions: list[str] = []
    if len(tones) >= 4:
        extensions.append(tones[3])
    if len(scale_spelled) >= 2 and _pc(scale_spelled[1]) not in {_pc(t) for t in tones}:
        extensions.append(scale_spelled[1])  # 9th
    if quality == "dom" and len(scale_spelled) >= 6:
        extensions.append(scale_spelled[5])  # 13 / 6
    return {
        "chord_tones": tones[:4],
        "scale": scale_spelled,
        "extensions": extensions,
        "quality": quality,
        "root": root,
        "scale_kind": scale_kind,
    }


def rhythm_plan(level: str, object_type: str, phase: int) -> list[tuple[float, str]]:
    """One bar of (beat, duration). Melody stays singable; improvisation is more active."""
    lvl = str(level or "intermediate").lower()
    obj = str(object_type or "improvisation").lower()
    melody = obj == "melody"
    if lvl == "beginner":
        if melody:
            if phase == 3:
                return [(0.0, "whole")]
            if phase % 2:
                return [(0.0, "half"), (2.0, "half")]
            return [(0.0, "quarter"), (1.0, "quarter"), (2.0, "half")]
        if phase == 3:
            return [(0.0, "half"), (2.0, "half")]
        return [(0.0, "quarter"), (1.0, "quarter"), (2.0, "quarter"), (3.0, "quarter")]
    if lvl == "advanced":
        if melody:
            if phase == 3:
                return [(0.0, "quarter"), (1.0, "eighth"), (1.5, "eighth"), (2.0, "half")]
            if phase == 1:
                return [(0.0, "eighth"), (0.5, "eighth"), (1.0, "quarter"), (2.0, "quarter"), (3.0, "quarter")]
            return [
                (0.0, "eighth"),
                (0.5, "eighth"),
                (1.0, "eighth"),
                (1.5, "eighth"),
                (2.0, "quarter"),
                (3.0, "quarter"),
            ]
        if phase == 3:
            return [
                (0.0, "eighth"),
                (0.5, "eighth"),
                (1.0, "eighth"),
                (1.5, "eighth"),
                (2.0, "quarter"),
                (3.0, "quarter"),
            ]
        if phase == 1:
            return [
                (0.5, "eighth"),
                (1.0, "eighth"),
                (1.5, "eighth"),
                (2.0, "eighth"),
                (2.5, "eighth"),
                (3.0, "eighth"),
                (3.5, "eighth"),
            ]
        if phase == 2:
            return [(i * 0.5, "eighth") for i in range(8)]
        return [
            (0.0, "eighth"),
            (0.5, "eighth"),
            (1.0, "eighth"),
            (1.5, "eighth"),
            (2.0, "eighth"),
            (2.5, "eighth"),
            (3.0, "quarter"),
        ]
    # intermediate
    if melody:
        if phase == 3:
            return [(0.0, "quarter"), (1.0, "quarter"), (2.0, "half")]
        if phase % 2:
            return [
                (0.0, "eighth"),
                (0.5, "eighth"),
                (1.0, "quarter"),
                (2.0, "quarter"),
                (3.0, "quarter"),
            ]
        return [
            (0.0, "quarter"),
            (1.0, "eighth"),
            (1.5, "eighth"),
            (2.0, "quarter"),
            (3.0, "quarter"),
        ]
    if phase == 3:
        return [(0.0, "eighth"), (0.5, "eighth"), (1.0, "eighth"), (1.5, "eighth"), (2.0, "half")]
    if phase == 0:
        return [
            (0.0, "eighth"),
            (0.5, "eighth"),
            (1.0, "eighth"),
            (1.5, "eighth"),
            (2.0, "eighth"),
            (2.5, "eighth"),
            (3.0, "quarter"),
        ]
    if phase == 2:
        return [
            (0.0, "eighth"),
            (0.5, "eighth"),
            (1.0, "quarter"),
            (2.0, "eighth"),
            (2.5, "eighth"),
            (3.0, "quarter"),
        ]
    return [
        (0.0, "eighth"),
        (0.5, "eighth"),
        (1.0, "eighth"),
        (1.5, "eighth"),
        (2.0, "quarter"),
        (3.0, "eighth"),
        (3.5, "eighth"),
    ]


def _scale_index(scale: Sequence[str], spelled: str) -> int:
    if not scale:
        return 0
    pc = _pc(spelled)
    best_i, best_d = 0, 99
    for i, n in enumerate(scale):
        d = min(( _pc(n) - pc) % 12, (pc - _pc(n)) % 12)
        if d < best_d:
            best_d, best_i = d, i
    return best_i


def _scale_step(scale: Sequence[str], spelled: str, direction: int) -> str:
    if not scale:
        return spelled
    idx = _scale_index(scale, spelled)
    return scale[(idx + (1 if direction >= 0 else -1)) % len(scale)]


def _chromatic_approach(target: str, *, below: bool = True) -> str:
    from music_theory import spell_note_in_key

    tpc = _pc(target)
    want = (tpc - 1) % 12 if below else (tpc + 1) % 12
    return spell_note_in_key(want, target)


def _pick_near(
    options: Sequence[str],
    *,
    prev_midi: int | None,
    low: int,
    high: int,
    prefer: int,
    max_leap: int,
    avoid_pc: int | None = None,
) -> tuple[str, int, int]:
    from music_coach_ami.musical_idea_engine import _place_spelled_note

    choices = [o for o in options if o]
    if avoid_pc is not None:
        filtered = [o for o in choices if _pc(o) != avoid_pc]
        if filtered:
            choices = filtered
    if not choices:
        choices = ["C"]
    best: tuple[tuple[int, int, int], str, int, int] | None = None
    for sp in choices:
        spelled, octv, midi = _place_spelled_note(
            sp,
            prefer_midi=prefer if prev_midi is None else prev_midi,
            low=low,
            high=high,
            direction="nearest" if prev_midi is not None else "",
            previous_midi=prev_midi,
        )
        leap = 0 if prev_midi is None else abs(midi - prev_midi)
        score = (
            0 if leap <= max_leap else 1,
            leap,
            0 if low <= midi <= high else 1,
        )
        if best is None or score < best[0]:
            best = (score, spelled, octv, midi)
    assert best is not None
    return best[1], best[2], best[3]


def generate_horizontal_line(
    timeline: Sequence[str],
    *,
    reference_key: str,
    level: str,
    object_type: str,
    meter: str = "4/4",
    low: int = 60,
    high: int = 84,
    prefer: int = 72,
    style: str = "",
) -> list[dict[str, Any]]:
    """Build a continuous line over bar-level harmony (stepwise default, chord targets on strong beats)."""
    _ = meter, style
    lvl = str(level or "intermediate").lower()
    obj = str(object_type or "improvisation").lower()
    obj_motion = "melody" if obj in {"melody", "phrase"} else "improvisation"

    events: list[dict[str, Any]] = []
    prev_midi: int | None = None
    prev_spelled = ""
    direction = 1
    run_len = 0
    last_large_leap_bar = -9
    max_leap_default = 7 if lvl == "beginner" else 5

    for bar_i, chord in enumerate(timeline):
        vocab = chord_vocabulary(str(chord), reference_key=reference_key)
        tones = list(vocab["chord_tones"] or [vocab["root"]])
        scale = list(vocab["scale"] or tones)
        ext = list(vocab["extensions"] or [])
        phase = bar_i % 4
        slots = rhythm_plan(lvl, obj_motion, phase)
        if phase == 0:
            direction = 1
        elif phase == 2:
            direction = -1

        third = tones[min(1, len(tones) - 1)]
        seventh = tones[min(3, len(tones) - 1)] if len(tones) > 3 else third
        guides = [third, seventh]
        if prev_spelled:
            guides = sorted(guides, key=lambda n: min((_pc(n) - _pc(prev_spelled)) % 12, (_pc(prev_spelled) - _pc(n)) % 12))

        allow_large = bar_i - last_large_leap_bar >= 2
        max_leap = 9 if allow_large and lvl == "advanced" and phase == 2 else max_leap_default

        for beat, dur in slots:
            is_strong = abs(beat - 0.0) < 1e-9 or abs(beat - 2.0) < 1e-9
            role = "chord_tone"
            if is_strong:
                options = list(guides) + [tones[0]]
                if lvl == "advanced" and ext and phase in {1, 2}:
                    options = list(ext[:1]) + options
                    role = "extension"
            elif lvl == "beginner":
                options = tones[:3]
            else:
                if prev_spelled and scale:
                    nxt = _scale_step(scale, prev_spelled, direction)
                    nxt2 = _scale_step(scale, nxt, direction)
                    options = [nxt, nxt2]
                    role = "passing"
                    if lvl == "advanced" and abs(beat - 1.5) < 1e-9:
                        options = [_chromatic_approach(guides[0], below=True), nxt]
                        role = "approach"
                    elif lvl == "advanced" and abs(beat - 3.5) < 1e-9:
                        options = [_chromatic_approach(tones[0], below=direction < 0), nxt]
                        role = "approach"
                    elif dur == "eighth" and run_len == 0 and third:
                        # neighbor into the run
                        options = [_scale_step(scale, prev_spelled, -direction), nxt]
                        role = "neighbor"
                else:
                    options = tones[:3]

            avoid = _pc(prev_spelled) if prev_spelled and dur in {"eighth", "triplet_eighth"} else None
            spelled, octv, midi = _pick_near(
                options or tones,
                prev_midi=prev_midi,
                low=low,
                high=high,
                prefer=prefer,
                max_leap=max_leap,
                avoid_pc=avoid,
            )
            leap = 0 if prev_midi is None else abs(midi - prev_midi)
            if leap >= 8:
                last_large_leap_bar = bar_i
                direction *= -1
                run_len = 0
            elif leap <= 2:
                run_len += 1
            else:
                run_len = 0
            turn_after = 6 if lvl == "advanced" else 4 if lvl != "beginner" else 8
            if run_len >= turn_after:
                direction *= -1
                run_len = 0

            events.append(
                {
                    "spelled": spelled,
                    "octave": octv,
                    "duration": dur,
                    "bar_index": bar_i,
                    "beat": float(beat),
                    "midi": midi,
                    "pitch_class": _pc(spelled),
                    "chord": str(chord),
                    "tone_role": role,
                }
            )
            prev_midi = midi
            prev_spelled = spelled
            prefer = midi + (2 if direction > 0 else -2)

    return events


def melodic_motion_metrics(events: Sequence[Any], *, role: str = "") -> dict[str, Any]:
    """Developer diagnostics for line quality (not musician-facing)."""

    def _role(e: Any) -> str:
        return str(e.get("role") if isinstance(e, dict) else getattr(e, "role", "") or "")

    def _bar(e: Any) -> int:
        return int(e.get("bar_index") if isinstance(e, dict) else getattr(e, "bar_index", 0) or 0)

    def _beat(e: Any) -> float:
        return float(e.get("beat") if isinstance(e, dict) else getattr(e, "beat", 0.0) or 0.0)

    evs = [e for e in events if not role or _role(e) == role]
    if not evs:
        evs = list(events)
    evs = sorted(evs, key=lambda e: (_bar(e), _beat(e)))
    n = len(evs)
    if n == 0:
        return {
            "note_count": 0,
            "eighth_note_count": 0,
            "rhythmic_density": 0.0,
            "stepwise_motion_pct": 0.0,
            "leap_count": 0,
            "large_leap_count": 0,
            "repeated_note_pct": 0.0,
            "chord_tone_pct": 0.0,
            "passing_approach_pct": 0.0,
        }

    midis: list[int] = []
    durs: list[str] = []
    spelled: list[str] = []
    tone_roles: list[str] = []
    for e in evs:
        if isinstance(e, dict):
            midi = int(e.get("midi") or 0)
            if not midi:
                midi = _midi(str(e.get("spelled") or "C"), int(e.get("octave") or 4))
            midis.append(midi)
            durs.append(str(e.get("duration") or ""))
            spelled.append(str(e.get("spelled") or ""))
            tone_roles.append(str(e.get("tone_role") or ""))
        else:
            midis.append(_midi(e.spelled, e.octave))
            durs.append(str(e.duration or ""))
            spelled.append(str(e.spelled or ""))
            tone_roles.append(str(getattr(e, "tone_role", "") or ""))

    eighths = sum(1 for d in durs if d in {"eighth", "triplet_eighth", "sixteenth"})
    steps = leaps = large = repeats = 0
    for i in range(1, n):
        iv = abs(midis[i] - midis[i - 1])
        if iv <= 2:
            steps += 1
        if iv >= 5:
            leaps += 1
        if iv >= 8:
            large += 1
        if spelled[i] == spelled[i - 1]:
            repeats += 1
    intervals = max(1, n - 1)
    passing_roles = {"passing", "neighbor", "approach"}
    chord_roles = {"chord_tone", "extension", ""}
    ct = sum(1 for r in tone_roles if r in chord_roles)
    passing = sum(1 for r in tone_roles if r in passing_roles)
    return {
        "note_count": n,
        "eighth_note_count": eighths,
        "rhythmic_density": round(eighths / n, 3),
        "stepwise_motion_pct": round(steps / intervals, 3),
        "leap_count": leaps,
        "large_leap_count": large,
        "repeated_note_pct": round(repeats / intervals, 3),
        "chord_tone_pct": round(ct / n, 3),
        "passing_approach_pct": round(passing / n, 3),
    }
