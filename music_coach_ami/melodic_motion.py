"""Horizontal, chord-aware melodic motion (not per-bar arpeggio dumps)."""

from __future__ import annotations

from typing import Any, Sequence


def _pc(note: str) -> int:
    from music_theory import pitch_class_from_spelled_note

    return int(pitch_class_from_spelled_note(note)) % 12


def _midi(note: str, octave: int) -> int:
    from music_theory import midi_from_spelled_note

    return int(midi_from_spelled_note(note, octave=octave))


def _dominant_tension_kind(chord: str) -> str:
    """Altered-dominant marker from the chord *suffix*, never the root spelling.

    ``Bb9`` must not look like ``b9`` just because the root is Bb.
    """
    from music_theory import normalize_chord_for_theory, split_chord

    head = normalize_chord_for_theory(chord) or str(chord or "").strip()
    _, suffix = split_chord(head)
    low = str(suffix or "").lower()
    if "alt" in low:
        return "alt"
    if "b9" in low:
        return "b9"
    if "#9" in low:
        return "#9"
    return ""


def chord_vocabulary(chord: str, *, reference_key: str = "") -> dict[str, Any]:
    """Chord tones + fitting scale fragments for one harmony."""
    from improvisation_intelligence import spell_scale_notes
    from improvisation_motif import chord_tone_names
    from music_theory import classify_chord_quality, chord_root_for_theory, normalize_chord_for_theory

    head = str(chord or "").strip()
    theory_head = normalize_chord_for_theory(head) or head
    tones = [t for t in (chord_tone_names(theory_head, reference_key=reference_key) or []) if t]
    root = tones[0] if tones else (chord_root_for_theory(theory_head) or "C")
    if not tones:
        tones = [root]
    quality = classify_chord_quality(theory_head)
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
    tension = _dominant_tension_kind(theory_head) if quality == "dom" else ""
    if tension:
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
                (2.0, "half"),
            ]
        if phase == 1:
            return [
                (0.0, "rest_eighth"),
                (0.5, "eighth"),
                (1.0, "eighth"),
                (1.5, "eighth"),
                (2.0, "eighth"),
                (2.5, "eighth"),
                (3.0, "eighth"),
                (3.5, "eighth"),
            ]
        if phase == 2:
            return [
                (0.0, "eighth"),
                (0.5, "eighth"),
                (1.0, "eighth"),
                (1.5, "eighth"),
                (2.0, "quarter"),
                (3.0, "eighth"),
                (3.5, "eighth"),
            ]
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


def _is_rest_duration(duration: str) -> bool:
    return str(duration or "").lower().startswith("rest")


def _pick_near(
    options: Sequence[str],
    *,
    prev_midi: int | None,
    low: int,
    high: int,
    prefer: int,
    max_leap: int,
    avoid_pc: int | None = None,
    comfort_high: int | None = None,
    pull_down: bool = False,
) -> tuple[str, int, int]:
    from music_coach_ami.musical_idea_engine import _place_spelled_note

    choices = [o for o in options if o]
    if avoid_pc is not None:
        filtered = [o for o in choices if _pc(o) != avoid_pc]
        if filtered:
            choices = filtered
    if not choices:
        choices = ["C"]
    cap = int(comfort_high) if comfort_high is not None else high
    best: tuple[tuple[int, int, int, int], str, int, int] | None = None
    for sp in choices:
        spelled, octv, midi = _place_spelled_note(
            sp,
            prefer_midi=prefer if prev_midi is None else (prefer if pull_down else prev_midi),
            low=low,
            high=high,
            direction="descending" if pull_down and prev_midi is not None else (
                "nearest" if prev_midi is not None else ""
            ),
            previous_midi=prev_midi,
        )
        leap = 0 if prev_midi is None else abs(midi - prev_midi)
        score = (
            0 if leap <= max_leap else 1,
            0 if midi <= cap else 1,
            leap,
            abs(midi - prefer),
        )
        if best is None or score < best[0]:
            best = (score, spelled, octv, midi)
    assert best is not None
    return best[1], best[2], best[3]


def _beats_per_bar(meter: str) -> float:
    text = str(meter or "4/4").strip() or "4/4"
    if text == "3/4":
        return 3.0
    if text == "6/8":
        return 3.0
    if "/" in text:
        try:
            num, den = text.split("/", 1)
            return (float(num) * 4.0) / float(den)
        except (TypeError, ValueError):
            return 4.0
    return 4.0


def _active_chord_at_beat(bar_token: str, beat: float, *, beats_per_bar: float = 4.0) -> str:
    """Resolve sub-bar harmony from chart tokens such as ``Gm7|C7`` or ``Gm7:2|C7:2``."""
    try:
        from chord_subdivisions import chord_at_beat
    except ImportError:
        head = str(bar_token or "").split("|", 1)[0].strip()
        return head or str(bar_token or "").strip()
    active = chord_at_beat(bar_token, beat, beats_per_bar=beats_per_bar)
    return str(active or bar_token or "").strip()


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
    instrument_family: str = "",
) -> list[dict[str, Any]]:
    """Build a continuous line over timed harmony (stepwise default, chord targets on strong beats)."""
    _ = style
    lvl = str(level or "intermediate").lower()
    obj = str(object_type or "improvisation").lower()
    obj_motion = "melody" if obj in {"melody", "phrase"} else "improvisation"
    family = str(instrument_family or "").lower()
    wind = family == "wind"
    bpb = _beats_per_bar(meter)
    comfort_high = min(high, max(prefer + 9, prefer + 6))
    center = int(prefer)

    events: list[dict[str, Any]] = []
    prev_midi: int | None = None
    prev_spelled = ""
    direction = 1
    run_len = 0
    extreme_run = 0
    last_large_leap_bar = -9
    if wind:
        max_leap_default = 4 if obj_motion == "melody" else 5
    else:
        max_leap_default = 7 if lvl == "beginner" else 5
    vocab_cache: dict[str, dict[str, Any]] = {}

    for bar_i, bar_token in enumerate(timeline):
        phase = bar_i % 4
        slots = rhythm_plan(lvl, obj_motion, phase)
        if phase == 0:
            direction = 1
        elif phase == 2:
            direction = -1

        allow_large = bar_i - last_large_leap_bar >= 2
        max_leap = 9 if allow_large and lvl == "advanced" and phase == 2 and not wind else max_leap_default
        if wind:
            max_leap = min(max_leap, 5 if lvl == "advanced" else 4)

        for beat, dur in slots:
            if _is_rest_duration(dur):
                events.append(
                    {
                        "spelled": "",
                        "octave": 0,
                        "duration": dur,
                        "bar_index": bar_i,
                        "beat": float(beat),
                        "midi": 0,
                        "pitch_class": None,
                        "chord": _active_chord_at_beat(str(bar_token), beat, beats_per_bar=bpb),
                        "tone_role": "rest",
                    }
                )
                continue

            chord = _active_chord_at_beat(str(bar_token), beat, beats_per_bar=bpb)
            vocab = vocab_cache.get(chord)
            if vocab is None:
                vocab = chord_vocabulary(chord, reference_key=reference_key)
                vocab_cache[chord] = vocab
            tones = list(vocab["chord_tones"] or [vocab["root"]])
            scale = list(vocab["scale"] or tones)
            ext = list(vocab["extensions"] or [])
            third = tones[min(1, len(tones) - 1)]
            seventh = tones[min(3, len(tones) - 1)] if len(tones) > 3 else third
            guides = [third, seventh]
            if prev_spelled:
                guides = sorted(
                    guides,
                    key=lambda n: min((_pc(n) - _pc(prev_spelled)) % 12, (_pc(prev_spelled) - _pc(n)) % 12),
                )

            is_strong = abs(beat - 0.0) < 1e-9 or abs(beat - 2.0) < 1e-9
            role = "chord_tone"
            pull_down = extreme_run >= 2 or (prev_midi is not None and prev_midi >= comfort_high)
            if pull_down:
                direction = -1
            if is_strong:
                options = list(guides) + [tones[0]]
                if lvl == "advanced" and ext and phase in {1, 2} and not pull_down:
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
                    if lvl == "advanced" and abs(beat - 1.5) < 1e-9 and not pull_down:
                        options = [_chromatic_approach(guides[0], below=True), nxt]
                        role = "approach"
                    elif lvl == "advanced" and abs(beat - 3.5) < 1e-9 and not pull_down:
                        options = [_chromatic_approach(tones[0], below=direction < 0), nxt]
                        role = "approach"
                    elif dur == "eighth" and run_len == 0 and third:
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
                prefer=center if pull_down else prefer,
                max_leap=max_leap,
                avoid_pc=avoid,
                comfort_high=comfort_high,
                pull_down=pull_down,
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
            if midi >= comfort_high:
                extreme_run += 1
            else:
                extreme_run = 0
            turn_after = 6 if lvl == "advanced" else 4 if lvl != "beginner" else 8
            if run_len >= turn_after or extreme_run >= 3:
                direction = -1
                run_len = 0
                extreme_run = 0

            events.append(
                {
                    "spelled": spelled,
                    "octave": octv,
                    "duration": dur,
                    "bar_index": bar_i,
                    "beat": float(beat),
                    "midi": midi,
                    "pitch_class": _pc(spelled),
                    "chord": chord,
                    "tone_role": role,
                }
            )
            prev_midi = midi
            prev_spelled = spelled
            prefer = midi + (2 if direction > 0 else -2)
            if prefer > comfort_high:
                prefer = center
                direction = -1

    return events


def adapt_motif_to_harmony(
    core: Sequence[dict[str, Any]],
    dest_chords: Sequence[str],
    *,
    bar_offset: int,
    reference_key: str,
    low: int,
    high: int,
    prefer: int,
    instrument_family: str = "",
) -> list[dict[str, Any]]:
    """Reuse a motif's rhythm/contour/articulation, remapped to destination harmony."""
    family = str(instrument_family or "").lower()
    max_leap = 4 if family == "wind" else 5
    out: list[dict[str, Any]] = []
    prev_midi: int | None = None
    dest_list = [str(c) for c in dest_chords if str(c).strip()] or ["C"]
    for item in core:
        src_bar = int(item.get("bar_index") or 0)
        if src_bar >= len(dest_list):
            continue
        dest_chord = dest_list[src_bar]
        new_item = dict(item)
        new_item["bar_index"] = int(bar_offset) + src_bar
        new_item["chord"] = dest_chord
        new_item["cell_index"] = int(bar_offset) // max(1, len(dest_list))
        if _is_rest_duration(str(item.get("duration") or "")) or not str(item.get("spelled") or "").strip():
            new_item["midi"] = 0
            out.append(new_item)
            continue
        src_chord = str(item.get("chord") or dest_chord)
        src_vocab = chord_vocabulary(src_chord, reference_key=reference_key)
        dst_vocab = chord_vocabulary(dest_chord, reference_key=reference_key)
        src_scale = list(src_vocab.get("scale") or src_vocab.get("chord_tones") or ["C"])
        dst_scale = list(dst_vocab.get("scale") or dst_vocab.get("chord_tones") or ["C"])
        dst_tones = list(dst_vocab.get("chord_tones") or [dst_vocab.get("root") or "C"])
        src_tones = list(src_vocab.get("chord_tones") or [src_vocab.get("root") or "C"])
        idx = _scale_index(src_scale, str(item.get("spelled") or "C"))
        dest_spelled = dst_scale[idx % len(dst_scale)] if dst_scale else dst_tones[0]
        role = str(item.get("tone_role") or "")
        if role in {"chord_tone", "extension"}:
            src_pc = _pc(str(item.get("spelled") or "C"))
            func_i = next((i for i, t in enumerate(src_tones) if _pc(t) == src_pc), None)
            if func_i is not None and func_i < len(dst_tones):
                dest_spelled = dst_tones[func_i]
        options = [dest_spelled]
        if dst_scale:
            options.append(dst_scale[(idx + 1) % len(dst_scale)])
            options.append(dst_scale[(idx - 1) % len(dst_scale)])
        options.extend(dst_tones[:2])
        spelled, octv, midi = _pick_near(
            options,
            prev_midi=prev_midi,
            low=low,
            high=high,
            prefer=prefer if prev_midi is None else prev_midi,
            max_leap=max_leap,
        )
        new_item["spelled"] = spelled
        new_item["octave"] = octv
        new_item["midi"] = midi
        new_item["pitch_class"] = _pc(spelled)
        out.append(new_item)
        prev_midi = midi
        prefer = midi
    return out


def motif_interval_shape(events: Sequence[dict[str, Any]]) -> list[int]:
    sounding = [e for e in events if str(e.get("spelled") or "").strip() and not _is_rest_duration(str(e.get("duration") or ""))]
    shape: list[int] = []
    for i in range(1, len(sounding)):
        a = int(sounding[i - 1].get("midi") or 0)
        b = int(sounding[i].get("midi") or 0)
        if a and b:
            shape.append(b - a)
    return shape


def motif_rhythmic_fingerprint(events: Sequence[dict[str, Any]]) -> list[tuple[float, str]]:
    return [
        (float(e.get("beat") or 0.0), str(e.get("duration") or "quarter"))
        for e in events
        if int(e.get("bar_index") or 0) == int(events[0].get("bar_index") or 0)
    ] if events else []


def motif_articulation_fingerprint(events: Sequence[dict[str, Any]]) -> list[tuple[bool, str]]:
    """Slur membership + articulation mark per sounding note — lick identity, not pitches."""
    out: list[tuple[bool, str]] = []
    for e in events:
        if _is_rest_duration(str(e.get("duration") or "")) or not str(e.get("spelled") or "").strip():
            continue
        out.append((int(e.get("slur_group") or 0) > 0, str(e.get("articulation") or "")))
    return out


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

    def _dur_of(e: Any) -> str:
        return str(e.get("duration") if isinstance(e, dict) else getattr(e, "duration", "") or "")

    sounding = [e for e in evs if not _is_rest_duration(_dur_of(e))]
    n = len(sounding)
    if n == 0:
        return {
            "note_count": 0,
            "eighth_note_count": 0,
            "rest_count": sum(1 for e in evs if _is_rest_duration(_dur_of(e))),
            "breathing_opportunities": sum(1 for e in evs if _is_rest_duration(_dur_of(e))),
            "rhythmic_density": 0.0,
            "stepwise_motion_pct": 0.0,
            "leap_count": 0,
            "large_leap_count": 0,
            "repeated_note_pct": 0.0,
            "chord_tone_pct": 0.0,
            "passing_approach_pct": 0.0,
            "duration_variety": 0,
            "median_midi": 0,
            "max_midi": 0,
            "consecutive_extreme_high_max": 0,
            "pct_above_comfort": 0.0,
            "average_interval": 0.0,
            "consecutive_large_leaps_max": 0,
            "range_semitones": 0,
        }

    midis: list[int] = []
    durs: list[str] = []
    spelled: list[str] = []
    tone_roles: list[str] = []
    for e in sounding:
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
    rests = sum(1 for e in evs if _is_rest_duration(_dur_of(e)))
    duration_kinds = {d.split("_", 1)[-1] if d.startswith("rest_") else d for d in [_dur_of(e) for e in evs] if d}
    steps = leaps = large = repeats = 0
    consecutive_large = consecutive_large_max = 0
    interval_sum = 0
    for i in range(1, n):
        iv = abs(midis[i] - midis[i - 1])
        interval_sum += iv
        if iv <= 2:
            steps += 1
            consecutive_large = 0
        if iv >= 5:
            leaps += 1
        if iv >= 8:
            large += 1
            consecutive_large += 1
            consecutive_large_max = max(consecutive_large_max, consecutive_large)
        else:
            if iv >= 5:
                consecutive_large += 1
                consecutive_large_max = max(consecutive_large_max, consecutive_large)
            else:
                consecutive_large = 0
        if spelled[i] == spelled[i - 1]:
            repeats += 1
    intervals = max(1, n - 1)
    passing_roles = {"passing", "neighbor", "approach"}
    chord_roles = {"chord_tone", "extension", ""}
    ct = sum(1 for r in tone_roles if r in chord_roles)
    passing = sum(1 for r in tone_roles if r in passing_roles)
    comfort_high = 81  # A5 — one ledger above the treble staff
    extreme_high = 88  # E6 — three ledger lines; peaks OK, not a plateau
    extreme_run = extreme_max = 0
    for midi in midis:
        if midi >= extreme_high:
            extreme_run += 1
            extreme_max = max(extreme_max, extreme_run)
        else:
            extreme_run = 0
    above_comfort = sum(1 for m in midis if m > comfort_high)
    ordered = sorted(midis)
    return {
        "note_count": n,
        "eighth_note_count": eighths,
        "rest_count": rests,
        "breathing_opportunities": rests,
        "rhythmic_density": round(eighths / n, 3),
        "stepwise_motion_pct": round(steps / intervals, 3),
        "leap_count": leaps,
        "large_leap_count": large,
        "repeated_note_pct": round(repeats / intervals, 3),
        "chord_tone_pct": round(ct / n, 3),
        "passing_approach_pct": round(passing / n, 3),
        "duration_variety": len(duration_kinds),
        "median_midi": ordered[n // 2],
        "max_midi": max(midis),
        "consecutive_extreme_high_max": extreme_max,
        "pct_above_comfort": round(above_comfort / n, 3),
        "average_interval": round(interval_sum / intervals, 3),
        "consecutive_large_leaps_max": consecutive_large_max,
        "range_semitones": (max(midis) - min(midis)) if midis else 0,
    }
