"""The Practice Melodies a song or jam has, and the one on the page.

One melody is composed once, in the key the song was first met in (its home key), and only ever *projected* from
there: to the Practice Key, a Key Cycling key, an instrument's written key, guitar shapes, and that instrument's
register and clef. Nothing that only changes how it is read -- key, instrument, tempo, reload -- composes a note.

What composes: a song or jam without a melody, "Generate Another Melody", and a different style, level or Practice
Focus, which has its own set of melodies (the earlier ones stay and come back with their settings). Articulation and
Dynamics only mark the same notes. A melody the musician keeps is stored note for note and is never replaced.

Stored per song / jam identity in ``practice_melody_library`` (small JSON, saved with the session): which
alternatives exist and which is shown -- the notes themselves are reproducible -- plus the kept melodies.
"""

from __future__ import annotations

import hashlib
from dataclasses import replace
from typing import Any, Mapping, MutableMapping, Sequence

from music_theory import transpose_sections_dict
from practice_melody_composer import mark_events, note_intent, style_family
from practice_melody_generator import GENERATOR_VERSION, generate_practice_melody, register_window
from practice_melody_model import MelodyEvent, MelodySection, PracticeMelody
from practice_melody_transpose import transpose_practice_melody

LIBRARY_KEY = "practice_melody_library"
MEMO_KEY = "_practice_melody_memo"
_MAX_SOURCES, _MAX_ALTS, _MAX_KEPT, _MAX_MEMO = 30, 24, 12, 24

# Written ranges of instruments whose register the wind tables do not describe (bass reads bass clef; the guitar is
# written an octave above where it sounds).
_WRITTEN_RANGE: dict[str, dict[str, tuple[int, int]]] = {
    "bass": {"Beginner": (40, 55), "Intermediate": (40, 60), "Advanced": (40, 64)},
    "guitar": {"Beginner": (55, 74), "Intermediate": (52, 76), "Advanced": (52, 79)},
}


def melody_clef(instrument: str) -> str:
    from composition_melody_projection import clef_for_instrument

    if "trombone" in str(instrument or "").lower():
        return "bass"
    return clef_for_instrument(instrument)


def display_register(instrument: str, level: str, written_offset: int = 0) -> tuple[int, int] | None:
    """(low, high) MIDI the notes shown to this player should lie in; None when nothing is known about it."""
    name = str(instrument or "").strip().lower()
    if not name:
        return None
    for family, ranges in _WRITTEN_RANGE.items():
        if family in name and "clarinet" not in name:
            return ranges.get(level, ranges["Intermediate"])
    return register_window(level, instrument, written_offset)


# --- fitting -----------------------------------------------------------------------------------------


def _outside(midis: Sequence[int], low: int, high: int) -> int:
    return sum(max(0, low - m) + max(0, m - high) for m in midis)


def _best_shift(midis: Sequence[int], low: int, high: int, shifts: Sequence[int]) -> int:
    centre = (low + high) / 2
    return min(shifts, key=lambda s: (_outside([m + s for m in midis], low, high),
                                      abs(sum(midis) / len(midis) + s - centre) > 8, abs(s)))


def fit_to_register(melody: PracticeMelody, window: tuple[int, int] | None) -> PracticeMelody:
    """The same tune in the player's register: whole-melody octave first, then whole phrases, then single notes."""
    midis = [e.midi for s in melody.sections for e in s.events if e.midi is not None]
    if not window or not midis:
        return melody
    low, high = window
    shift = _best_shift(midis, low, high, (-36, -24, -12, 0, 12, 24, 36))
    if shift == 0 and _outside(midis, low, high) == 0:
        return melody

    def fold(m: int) -> int:
        while m < low and m + 12 <= high + 2:
            m += 12
        while m > high and m - 12 >= low - 2:
            m -= 12
        return m

    sections = []
    for section in melody.sections:
        events = [replace(e, midi=e.midi + shift) if e.midi is not None else e for e in section.events]
        phrase: list[int] = []
        for i, e in enumerate(events + [None]):
            if e is not None and not e.is_rest:
                phrase.append(i)
                continue
            if phrase and _outside([events[k].midi for k in phrase], low, high):
                s = _best_shift([events[k].midi for k in phrase], low, high, (-12, 0, 12))
                for k in phrase:
                    events[k] = replace(events[k], midi=fold(events[k].midi + s))
            phrase = []
        sections.append(replace(section, events=tuple(events)))
    return replace(melody, sections=tuple(sections))


def _with_chart_chords(melody: PracticeMelody, sections: Mapping[str, Sequence[str]], key_center: str) -> PracticeMelody:
    """The chart's own chord names (never respelled by a trip through the home key), and notes spelled to match."""
    from harmonic_spelling import spell_pitch_classes_for_chord
    from practice_melody_generator import _chord_at_factory

    out = []
    for section in melody.sections:
        chords = [str(c) for c in sections.get(section.section_id) or ()]
        if len(chords) != section.measures:
            out.append(section)
            continue
        chord_at = _chord_at_factory(section.beats_per_measure)
        events = []
        for e in section.events:
            chord = chord_at(chords[e.measure], e.beat) or chords[e.measure]
            pitch = e.pitch
            if e.midi is not None:
                pitch = spell_pitch_classes_for_chord([e.midi % 12], chord, song_display_key=key_center)[0]
            events.append(replace(e, chord=chord, pitch=pitch))
        out.append(replace(section, chords=tuple(chords), events=tuple(events)))
    return replace(melody, sections=tuple(out))


# --- the store ---------------------------------------------------------------------------------------


def _library(session: Mapping[str, Any]) -> dict[str, Any]:
    lib = session.get(LIBRARY_KEY)
    return lib if isinstance(lib, dict) else {}


def _entry(session: Mapping[str, Any], identity: str) -> dict[str, Any] | None:
    entry = _library(session).get(identity)
    return entry if isinstance(entry, dict) else None


def _save(session: MutableMapping[str, Any], identity: str, entry: dict[str, Any]) -> None:
    lib = dict(_library(session))
    lib.pop(identity, None)
    lib[identity] = entry
    for old in list(lib):
        if len(lib) <= _MAX_SOURCES:
            break
        if old != identity and not (lib[old] or {}).get("kept"):
            lib.pop(old)
    session[LIBRARY_KEY] = lib


def has_melody(session: Mapping[str, Any], identity: str) -> bool:
    return bool(identity) and _entry(session, identity) is not None


def shown_on_backing(session: Mapping[str, Any], identity: str) -> bool:
    return bool((_entry(session, identity) or {}).get("backing"))


def show_on_backing(session: MutableMapping[str, Any], identity: str) -> None:
    entry = _entry(session, identity)
    if entry is not None and not entry.get("backing"):
        _save(session, identity, {**entry, "backing": True})


def recipe_for(level: str, style: str, focus: str, meter: tuple[int, int]) -> str:
    return f"{level}|{style_family(style)}|{note_intent(focus)}|{int(meter[0])}/{int(meter[1])}"


def _form(sections: Mapping[str, Sequence[str]], order: Sequence[str]) -> str:
    return hashlib.sha256("|".join(f"{n}:{','.join(map(str, sections.get(n) or ()))}" for n in order).encode()).hexdigest()[:12]


def _pack(melody: PracticeMelody) -> dict[str, Any]:
    return {
        "key": melody.key_center,
        "meter": list(melody.meter),
        "sections": [
            [s.section_id, s.section_type, s.beats_per_measure, list(s.chords),
             [[e.measure, e.beat, e.duration_beats, e.midi, e.tone_role] for e in s.events]]
            for s in melody.sections
        ],
    }


def _unpack(row: Mapping[str, Any], *, like: Mapping[str, Any]) -> PracticeMelody:
    sections = []
    for name, kind, bpm, chords, events in row["sections"]:
        sections.append(MelodySection(
            section_id=str(name), section_type=str(kind), measures=len(chords), beats_per_measure=float(bpm),
            chords=tuple(map(str, chords)),
            events=tuple(
                MelodyEvent(measure=int(m), beat=float(b), duration_beats=float(d), is_rest=midi is None,
                            pitch=None if midi is None else "C", midi=None if midi is None else int(midi),
                            chord=str(chords[int(m)]), tone_role=str(role))
                for m, b, d, midi, role in events
            ),
        ))
    return PracticeMelody(
        schema_version=1, melody_id=str(like["id"]), source="generated", song_id=str(like["identity"]),
        song_title=str(like["title"]), level=str(like["level"]), key_center=str(row["key"]),
        meter=(int(row["meter"][0]), int(row["meter"][1])), tempo_bpm=float(like["tempo"]), style=str(like["style"]),
        seed=0, alt_index=int(like["alt"]), generator_version=GENERATOR_VERSION,
        section_order=tuple(s.section_id for s in sections), sections=tuple(sections), focus=str(like["focus"]),
    )


def _remember(session: MutableMapping[str, Any], key: str, value: Any) -> None:
    memo = session.get(MEMO_KEY)
    memo = dict(memo) if isinstance(memo, dict) else {}
    memo.pop(key, None)
    memo[key] = value
    while len(memo) > _MAX_MEMO:
        memo.pop(next(iter(memo)))
    session[MEMO_KEY] = memo


def resolve(
    session: MutableMapping[str, Any],
    *,
    identity: str,
    title: str,
    sections: Mapping[str, Sequence[str]] | None,
    section_order: Sequence[str] | None,
    sections_key: str,
    key_center: str = "",
    level: str,
    tempo_bpm: float,
    style: str,
    meter: tuple[int, int] = (4, 4),
    focus: str = "",
    instrument: str = "",
    written_offset: int = 0,
    another: bool = False,
    step: int = 0,
) -> PracticeMelody | None:
    """The melody to show for this song or jam now (None without chords).

    ``sections`` are in ``sections_key``; the result is in ``key_center`` (that key, when empty). ``another``
    composes a new alternative; ``step`` moves between the existing ones."""
    if not sections or not identity:
        return None
    shown = str(key_center or sections_key or "").strip()
    order = [n for n in (section_order or sections) if n in sections] + [n for n in sections if n not in (section_order or sections)]
    entry = dict(_entry(session, identity) or {"home": sections_key, "recipes": {}, "kept": []})
    recipes = dict(entry.get("recipes") or {})
    name = recipe_for(level, style, focus, meter)
    recipe = dict(recipes.get(name) or {"alts": [0], "at": 0, "style": style, "tempo": float(tempo_bpm or 100)})
    alts = [int(a) for a in recipe.get("alts") or [0]]
    at = min(max(0, int(recipe.get("at") or 0)), len(alts) - 1)
    if another:
        alts.append(max(alts) + 1)
        alts = alts[-_MAX_ALTS:]
        at = len(alts) - 1
    elif step:
        at = min(max(0, at + int(step)), len(alts) - 1)
    changed = (another or step) and entry.get("viewing")
    if changed:
        entry["viewing"] = ""
    new_recipe = {**recipe, "alts": alts, "at": at}
    if recipes.get(name) != new_recipe or _entry(session, identity) is None or changed:
        recipes.pop(name, None)
        recipes[name] = new_recipe
        _save(session, identity, {**entry, "recipes": dict(list(recipes.items())[-16:])})
        entry = dict(_entry(session, identity) or {})

    home = str(entry.get("home") or sections_key)
    view = str(entry.get("viewing") or "")
    kept = next((k for k in entry.get("kept") or [] if k.get("id") == view), None) if view else None
    cache = repr((identity, name, alts[at], view, home, shown, sections_key, _form(sections, order), instrument, written_offset,
                  focus, style, float(tempo_bpm or 0), title, level))
    memo = session.get(MEMO_KEY)
    if isinstance(memo, dict) and cache in memo:
        return memo[cache]

    if kept is not None:
        base = _unpack(kept["melody"], like={**kept, "identity": identity, "title": title})
    else:
        at_home = {n: list(c) for n, c in sections.items()}
        if home != sections_key:
            at_home = {n: list(c) for n, c in transpose_sections_dict(at_home, sections_key, home).items()}
        base = generate_practice_melody(
            song_id=identity, song_title=title, sections=at_home, section_order=order, key_center=home, level=level,
            tempo_bpm=float(recipe.get("tempo") or tempo_bpm or 100), style=str(recipe.get("style") or style), meter=meter,
            alt_index=alts[at], focus=focus,
        )
    melody = base
    if shown and base.key_center != shown:
        melody = transpose_practice_melody(base, new_key_center=shown)
    chart = {n: list(c) for n, c in sections.items()}
    if shown != sections_key:
        chart = {n: list(c) for n, c in transpose_sections_dict(chart, sections_key, shown).items()}
    if kept is None or fits(kept, sections, order, sections_key):
        melody = _with_chart_chords(melody, chart, shown)
    elif kept is not None:
        melody = _with_chart_chords(melody, {s.section_id: list(s.chords) for s in melody.sections}, shown)
    melody = fit_to_register(melody, display_register(instrument, level, written_offset) if instrument else None)
    marked = tuple(
        replace(s, events=tuple(mark_events(list(s.events), level=melody.level, style=melody.style if kept else style, focus=focus,
                                            bars=s.measures)))
        for s in melody.sections
    )
    melody = replace(
        melody, sections=marked, tempo_bpm=float(tempo_bpm or melody.tempo_bpm), song_title=title,
        style=melody.style if kept else style, focus=focus,
    )
    _remember(session, cache, melody)
    return melody


# --- alternatives and kept melodies -------------------------------------------------------------------


def alternatives(session: Mapping[str, Any], identity: str, recipe: str) -> tuple[int, int]:
    """(which alternative is shown, how many there are) for these settings."""
    row = ((_entry(session, identity) or {}).get("recipes") or {}).get(recipe) or {}
    alts = list(row.get("alts") or [0])
    return min(int(row.get("at") or 0), len(alts) - 1), len(alts)


def kept_melodies(session: Mapping[str, Any], identity: str) -> list[dict[str, Any]]:
    return [dict(k) for k in (_entry(session, identity) or {}).get("kept") or []]


def viewing(session: Mapping[str, Any], identity: str) -> str:
    return str((_entry(session, identity) or {}).get("viewing") or "")


def view_kept(session: MutableMapping[str, Any], identity: str, kept_id: str) -> None:
    entry = _entry(session, identity)
    if entry is not None and str(entry.get("viewing") or "") != str(kept_id or ""):
        _save(session, identity, {**entry, "viewing": str(kept_id or "")})


def _relative_form(sections: Mapping[str, Sequence[str]], order: Sequence[str], key: str) -> str:
    return _form(transpose_sections_dict({n: list(sections.get(n) or ()) for n in order}, key, "C"), order)


def fits(kept: Mapping[str, Any], sections: Mapping[str, Sequence[str]], order: Sequence[str], sections_key: str) -> bool:
    """False when the song's chords changed after the melody was kept (it belongs to the earlier progression)."""
    return str(kept.get("form") or "") == _relative_form(sections, order, sections_key)


def keep(
    session: MutableMapping[str, Any], identity: str, melody: PracticeMelody, *,
    sections: Mapping[str, Sequence[str]], section_order: Sequence[str] | None, sections_key: str,
) -> str:
    """Keep this melody note for note. Keeping the same one again changes nothing."""
    entry = dict(_entry(session, identity) or {"home": sections_key, "recipes": {}, "kept": []})
    kept = [dict(k) for k in entry.get("kept") or []]
    order = [n for n in (section_order or sections) if n in sections]
    packed = _pack(melody)
    kept_id = hashlib.sha256(repr((packed["sections"], melody.level, melody.style)).encode()).hexdigest()[:10]
    if not any(k.get("id") == kept_id for k in kept):
        kept.append({
            "id": kept_id, "alt": melody.alt_index, "level": melody.level, "style": melody.style, "focus": melody.focus,
            "tempo": melody.tempo_bpm, "form": _relative_form(sections, order, sections_key), "melody": packed,
        })
        _save(session, identity, {**entry, "kept": kept[-_MAX_KEPT:]})
    return kept_id


def drop_kept(session: MutableMapping[str, Any], identity: str, kept_id: str) -> None:
    entry = _entry(session, identity)
    if entry is None:
        return
    rest = [k for k in entry.get("kept") or [] if k.get("id") != kept_id]
    view = str(entry.get("viewing") or "")
    _save(session, identity, {**entry, "kept": rest, "viewing": "" if view == kept_id else view})


__all__ = (
    "LIBRARY_KEY", "alternatives", "display_register", "drop_kept", "fit_to_register", "fits", "has_melody", "keep",
    "kept_melodies", "melody_clef", "recipe_for", "resolve", "show_on_backing", "shown_on_backing",
    "view_kept", "viewing",
)
