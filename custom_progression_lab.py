"""Custom Progression Lab — builder, harmonic analysis, and practice exercises."""

from __future__ import annotations

import importlib.util
import copy
import re
import sys
from pathlib import Path
from typing import Any


def _load_music_theory():
    """Load music_theory (Streamlit Cloud may not have repo root on sys.path)."""
    try:
        from music_theory import semitone_distance as st_dist, transpose_chord as st_chord

        return st_dist, st_chord
    except ImportError:
        pass
    if "music_theory" in sys.modules:
        _mod = sys.modules["music_theory"]
        return _mod.semitone_distance, _mod.transpose_chord
    _path = Path(__file__).resolve().parent / "music_theory.py"
    if not _path.is_file():
        raise ImportError(f"music_theory.py not found next to {__file__}")
    _spec = importlib.util.spec_from_file_location("music_theory", str(_path))
    if _spec is None or _spec.loader is None:
        raise ImportError(f"Could not load music_theory from {_path}")
    _mod = importlib.util.module_from_spec(_spec)
    sys.modules["music_theory"] = _mod
    _spec.loader.exec_module(_mod)
    return _mod.semitone_distance, _mod.transpose_chord


semitone_distance, transpose_chord = _load_music_theory()

try:
    from music_theory import ENHARMONIC_MAJOR_KEYS, ENHARMONIC_MINOR_KEYS
except ImportError:
    ENHARMONIC_MAJOR_KEYS = [
        "C", "Db", "C#", "D", "Eb", "D#", "E", "F", "Gb", "F#", "G", "Ab", "G#", "A", "Bb", "A#", "B",
    ]
    ENHARMONIC_MINOR_KEYS = [
        "Cm", "Dbm", "C#m", "Dm", "D#m", "Ebm", "Em", "Fm", "Gbm", "F#m", "Gm", "G#m", "Abm", "Am", "A#m", "Bbm", "Bm",
    ]

from creative_lab_text import (
    chord_quality,
    chord_root,
    first_matching_pattern,
    root_pc,
    roman_path,
    section_analysis_lines,
    NOTE_TO_PC,
)

try:
    from chord_subdivisions import (
        SUBDIVISION_SEPARATOR as _SUB_SEP,
        join_subdivisions as _join_subs,
        make_hit_token as _make_hit_token,
    )
except ImportError:  # streamlit cloud / partial path setups
    _SUB_SEP = "|"

    def _join_subs(parts):
        return _SUB_SEP.join(parts)

    def _make_hit_token(chord):
        return f"{chord}.hit"


try:
    from music_theory import is_no_chord_token as _is_no_chord_token
except ImportError:
    def _is_no_chord_token(chord):
        if chord is None:
            return False
        cleaned = str(chord).strip().replace(" ", "").upper()
        return cleaned in {"N.C.", "NC", "N.C", "N/C", "(N.C.)", "TACET", "—", "-"}

CPL_SAVED_KEY = "cpl_saved_progressions"
CPL_ACTIVE_KEY = "cpl_active_progression"
CPL_LAST_DISPLAY_KEY = "cpl_last_display_key"

CPL_SECTION_NAMES: list[str] = [
    "Intro",
    "Verse",
    "Pre-Chorus",
    "Chorus",
    "Bridge",
    "Solo",
    "Outro",
    "Full Song",
]

CPL_EDITABLE_SECTIONS: list[str] = [n for n in CPL_SECTION_NAMES if n != "Full Song"]

CPL_PRESET_NAMES: list[str] = [
    "ii–V–I",
    "I–V–vi–IV",
    "Bossa cadence",
    "Jazz turnaround",
    "Neo soul",
]


def empty_cpl_sections() -> dict[str, list]:
    """All form sections, each starting with no chords."""
    return {name: [] for name in CPL_EDITABLE_SECTIONS}


def ensure_all_cpl_sections(sections: dict | None) -> dict[str, list]:
    """Guarantee every form section exists (empty list if missing). Drop stray keys."""
    raw = sections or {}
    base: dict[str, list] = {}
    for name in CPL_EDITABLE_SECTIONS:
        base[name] = [dict(entry) for entry in (raw.get(name) or [])]
    return base


def section_is_empty(entries: list | None) -> bool:
    if not entries:
        return True
    for entry in entries:
        if normalize_chord_symbol(entry.get("chord", "")):
            return False
    return True


def progression_is_empty(sections: dict | None) -> bool:
    return all(section_is_empty((sections or {}).get(name)) for name in CPL_EDITABLE_SECTIONS)


def default_active_progression():
    return {
        "name": "My Progression",
        "original_key_center": "C",
        "original_sections": empty_cpl_sections(),
        "progression_style": "Pop",
        "user_locked_home_key": False,
        "time_signature": "4/4",
        "bpm": 100,
        "groove_style": "Auto",
        "loops": 2,
    }


def deep_copy_sections(sections):
    return {
        name: [dict(entry) for entry in entries]
        for name, entries in (sections or {}).items()
    }


def ensure_original_structure(active):
    """Migrate legacy active dicts to original_sections + original_key_center."""
    if not active:
        return default_active_progression()
    if not active.get("original_sections"):
        legacy = active.get("sections")
        active["original_sections"] = (
            ensure_all_cpl_sections(legacy) if legacy else empty_cpl_sections()
        )
    else:
        active["original_sections"] = ensure_all_cpl_sections(active["original_sections"])
    if not active.get("original_key_center"):
        active["original_key_center"] = active.get("key_center", "C")
    active.pop("sections", None)
    active.pop("key_center", None)
    return active


def transpose_section_entries(entries, from_key, to_key):
    steps = semitone_distance(from_key, to_key)
    if steps == 0:
        return [dict(entry) for entry in entries or []]
    out = []
    for entry in entries or []:
        if is_repeat_entry(entry):
            out.append(
                {
                    "repeat": True,
                    "bars": max(1, int(entry.get("bars", 1) or 1)),
                }
            )
            continue
        chord = normalize_chord_symbol(entry.get("chord", ""))
        if not chord or chord == "%":
            continue
        out.append(
            {
                "chord": transpose_chord(chord, steps, reference_key=from_key),
                "bars": max(1, int(entry.get("bars", 1) or 1)),
            }
        )
    return out


def transpose_lab_sections(sections, from_key, to_key):
    return {
        name: transpose_section_entries(entries, from_key, to_key)
        for name, entries in (sections or {}).items()
    }


def normalize_chord_symbol(text):
    raw = str(text or "").strip()
    if not raw:
        return ""
    if raw == "%":
        return "%"
    head = raw.split("/", 1)[0].strip()
    if len(head) < 1:
        return ""
    return raw


def is_repeat_entry(entry: dict | None) -> bool:
    if not entry:
        return False
    if entry.get("repeat"):
        return True
    return str(entry.get("chord", "")).strip() == "%"


def expand_entries_to_display_slots(entries: list[dict] | None) -> list[tuple[str, str]]:
    """Per bar: (display_symbol, sounding_chord). Display may be % for repeats."""
    slots: list[tuple[str, str]] = []
    last = ""
    for entry in entries or []:
        if is_repeat_entry(entry):
            display = "%"
            sound = last
        else:
            sound = normalize_chord_symbol(entry.get("chord", ""))
            if sound and sound != "%":
                last = sound
            display = sound
        if not sound:
            continue
        bars = max(1, int(entry.get("bars", 1) or 1))
        for _ in range(bars):
            slots.append((display, sound))
    return slots


def expand_entries_to_chords(entries: list[dict] | None) -> list[str]:
    """Resolved chords for backing track (repeat → previous chord)."""
    return [s for _d, s in expand_entries_to_display_slots(entries) if s]


def weighted_chords_from_sections(sections):
    """Expand section entries to (chord, bar_weight) pairs in form order."""
    weighted = []
    for _name, entries in (sections or {}).items():
        for chord in expand_entries_to_chords(entries):
            weighted.append((chord, 1))
    return weighted


def _spell_tonic_pc(pc: int, roots_seen: set[str]) -> str:
    """Pick a spelling seen in the chart when possible."""
    for name in sorted(roots_seen, key=len, reverse=True):
        if NOTE_TO_PC.get(chord_root(name)) == pc:
            return chord_root(name)
    defaults = {
        0: "C",
        1: "Db",
        2: "D",
        3: "Eb",
        4: "E",
        5: "F",
        6: "F#",
        7: "G",
        8: "Ab",
        9: "A",
        10: "Bb",
        11: "B",
    }
    return defaults.get(pc % 12, "C")


def _key_label(key_name: str, mode: str) -> str:
    if mode == "minor":
        base = chord_root(str(key_name).rstrip("m"))
        return f"{base} minor"
    return f"{chord_root(key_name)} major"


def _storage_key_name(key_name: str, mode: str) -> str:
    base = chord_root(str(key_name).rstrip("m"))
    return f"{base}m" if mode == "minor" else base


def _is_dominant(q: str) -> bool:
    return "dominant" in q


def _is_major_tonic(q: str) -> bool:
    return q in ("major", "major seventh")


def _is_minor_tonic(q: str) -> bool:
    return q in ("minor", "minor seventh")


def _score_key_candidate(tonic_pc: int, mode: str, weighted_chords: list[tuple[str, int]]) -> tuple[float, list[str]]:
    """Score how well chords fit a tonal center using function, cadence, and placement."""
    score = 0.0
    reasons: list[str] = []
    n = len(weighted_chords)
    if not n:
        return 0.0, reasons

    for idx, (ch, bars) in enumerate(weighted_chords):
        root = root_pc(ch)
        if root is None:
            continue
        rel = (root - tonic_pc) % 12
        q = chord_quality(ch)
        w = float(bars)
        if idx == n - 1:
            w *= 2.8
        elif idx == n - 2:
            w *= 1.35

        if mode == "major":
            role = {
                0: 3.8 if _is_major_tonic(q) else 2.6,
                2: 1.6,
                4: 1.0,
                5: 2.1,
                7: 3.2 if _is_dominant(q) else 2.1,
                9: 2.1,
                10: 1.2,
            }.get(rel, 0.25)
        else:
            role = {
                0: 3.8 if _is_minor_tonic(q) else 2.6,
                2: 0.7,
                3: 1.8 if _is_major_tonic(q) else 1.0,
                5: 2.1,
                7: 3.0 if _is_dominant(q) else 2.0,
                8: 1.0,
                10: 2.0,
            }.get(rel, 0.25)
        score += role * w

    for idx in range(n - 1):
        ch_a, w_a = weighted_chords[idx]
        ch_b, w_b = weighted_chords[idx + 1]
        ra, rb = root_pc(ch_a), root_pc(ch_b)
        if ra is None or rb is None:
            continue
        qa, qb = chord_quality(ch_a), chord_quality(ch_b)
        rel_a = (ra - tonic_pc) % 12
        rel_b = (rb - tonic_pc) % 12

        if rel_a == 7 and rel_b == 0:
            bonus = 5.5 * w_b
            if mode == "major" and (_is_major_tonic(qb) or _is_minor_tonic(qb)):
                score += bonus if _is_major_tonic(qb) else bonus * 0.92
                reasons.append(f"dominant-to-tonic: {ch_a} -> {ch_b}")
            elif mode == "minor" and _is_minor_tonic(qb):
                score += bonus * 0.85
                reasons.append(f"V-i cadence: {ch_a} -> {ch_b}")

        if idx + 2 < n:
            ch_c, w_c = weighted_chords[idx + 2]
            rc = root_pc(ch_c)
            if rc is None:
                continue
            rel_c = (rc - tonic_pc) % 12
            if mode == "major" and rel_a == 2 and rel_b == 7 and rel_c == 0:
                score += 6.0 * w_c
                reasons.append(f"ii-V-I: {ch_a} -> {ch_b} -> {ch_c}")

    fifth_moves = 0
    for idx in range(n - 1):
        r1 = root_pc(weighted_chords[idx][0])
        r2 = root_pc(weighted_chords[idx + 1][0])
        if r1 is not None and r2 is not None and (r1 - r2) % 12 == 7:
            fifth_moves += 1
    if fifth_moves >= 2:
        score += 1.8 * fifth_moves
        reasons.append("circle-of-fifths root motion")

    last_ch, last_w = weighted_chords[-1]
    lr = root_pc(last_ch)
    lq = chord_quality(last_ch)
    if lr is not None:
        rel_last = (lr - tonic_pc) % 12
        if mode == "major" and rel_last == 0 and _is_major_tonic(lq):
            score += 4.0 * last_w
            reasons.append(f"final tonic rest on {last_ch}")
        elif mode == "minor" and rel_last == 0 and _is_minor_tonic(lq):
            score += 4.0 * last_w
            reasons.append(f"final tonic rest on {last_ch}")

    return score, reasons


def analyze_tonal_center(sections, user_home_key: str | None = None) -> dict:
    """Harmonic-function key analysis with confidence and relative-key hints."""
    weighted = weighted_chords_from_sections(sections)
    chords = [ch for ch, _w in weighted]
    roots_seen = {chord_root(ch) for ch in chords if chord_root(ch)}

    empty = {
        "primary_key": user_home_key or "C",
        "primary_mode": "major",
        "primary_label": user_home_key or "C major",
        "storage_key": user_home_key or "C",
        "confidence_label": "low",
        "confidence_score": 0.0,
        "alternate_key": None,
        "alternate_mode": None,
        "alternate_label": None,
        "summary": "Add chords to analyze the tonal center.",
        "reasons": [],
        "roman": "",
    }
    if not weighted:
        return empty

    candidates: list[tuple[float, int, str, list[str]]] = []
    for tonic_pc in range(12):
        for mode in ("major", "minor"):
            s, reasons = _score_key_candidate(tonic_pc, mode, weighted)
            candidates.append((s, tonic_pc, mode, reasons))

    candidates.sort(key=lambda row: row[0], reverse=True)
    best_score, best_pc, best_mode, best_reasons = candidates[0]
    second_score = candidates[1][0] if len(candidates) > 1 else 0.0

    primary_name = _spell_tonic_pc(best_pc, roots_seen)
    storage_key = _storage_key_name(primary_name, best_mode)
    primary_label = _key_label(primary_name, best_mode)

    gap = best_score - second_score
    if best_score < 4.0:
        confidence_label = "low"
        confidence_score = min(0.35, best_score / 12.0)
    elif gap < 2.5:
        confidence_label = "medium"
        confidence_score = min(0.75, 0.45 + gap / 10.0)
    else:
        confidence_label = "high"
        confidence_score = min(0.98, 0.55 + gap / 12.0)

    alternate_key = None
    alternate_mode = None
    alternate_label = None
    if len(candidates) > 1 and second_score >= best_score * 0.72:
        _s2, pc2, mode2, _r2 = candidates[1]
        alt_name = _spell_tonic_pc(pc2, roots_seen)
        alternate_key = _storage_key_name(alt_name, mode2)
        alternate_mode = mode2
        alternate_label = _key_label(alt_name, mode2)

    if best_mode == "major":
        rel_pc = (best_pc + 9) % 12
        rel_name = _spell_tonic_pc(rel_pc, roots_seen)
        rel_label = _key_label(rel_name, "minor")
        if alternate_label is None or alternate_label != rel_label:
            alternate_key = alternate_key or _storage_key_name(rel_name, "minor")
            alternate_mode = alternate_mode or "minor"
            alternate_label = alternate_label or rel_label
    else:
        rel_pc = (best_pc + 3) % 12
        rel_name = _spell_tonic_pc(rel_pc, roots_seen)
        rel_label = _key_label(rel_name, "major")
        if alternate_label is None or alternate_label != rel_label:
            alternate_key = alternate_key or rel_name
            alternate_mode = alternate_mode or "major"
            alternate_label = alternate_label or rel_label

    roman = roman_path(chords, storage_key, limit=12)
    summary_parts = [f"Likely tonal center: **{primary_label}**"]
    if confidence_label != "high":
        summary_parts[0] = f"Likely tonal center ({confidence_label} confidence): **{primary_label}**"
    if alternate_label and alternate_label != primary_label:
        summary_parts.append(f"relative / alternate: **{alternate_label}**")

    return {
        "primary_key": primary_name,
        "primary_mode": best_mode,
        "primary_label": primary_label,
        "storage_key": storage_key,
        "confidence_label": confidence_label,
        "confidence_score": round(confidence_score, 3),
        "alternate_key": alternate_key,
        "alternate_mode": alternate_mode,
        "alternate_label": alternate_label,
        "summary": " · ".join(summary_parts),
        "reasons": list(dict.fromkeys(best_reasons))[:5],
        "roman": roman,
        "chords_count": len(chords),
    }


def written_home_key(active) -> str:
    """Written / home key = tonal center of the stored progression (unless manually locked)."""
    active = ensure_original_structure(active)
    if active.get("user_locked_home_key") and active.get("original_key_center"):
        return active.get("original_key_center", "C")
    sections = active.get("original_sections") or {}
    analysis = analyze_tonal_center(sections)
    if analysis.get("chords_count", 0) >= 2 and analysis.get("confidence_score", 0) >= 0.35:
        return analysis.get("storage_key", active.get("original_key_center", "C"))
    return active.get("original_key_center", "C")


def sync_written_home_key(active, *, min_confidence: float = 0.35) -> dict:
    """Update stored home key from harmonic analysis unless the user locked it manually."""
    active = ensure_original_structure(active)
    if active.get("user_locked_home_key"):
        active.pop("home_key_uncertain", None)
        return active
    sections = active.get("original_sections") or {}
    analysis = analyze_tonal_center(sections)
    if analysis.get("chords_count", 0) < 2:
        return active
    if analysis.get("confidence_score", 0) < min_confidence:
        active["home_key_uncertain"] = True
        return active
    detected = analysis.get("storage_key")
    if detected:
        active["original_key_center"] = detected
        active["tonal_center_inferred"] = True
    active.pop("home_key_uncertain", None)
    return active


def display_sections_for_key(active, display_key):
    active = ensure_original_structure(active)
    home = written_home_key(active)
    original = active.get("original_sections") or {}
    return transpose_lab_sections(original, home, display_key)


def commit_home_sections(active, home_sections):
    """Persist chords in written/home key (respect user-chosen original key)."""
    active = ensure_original_structure(active)
    active["original_sections"] = deep_copy_sections(home_sections)
    if active.get("user_locked_home_key"):
        return active
    return sync_written_home_key(active)


def set_original_key_center(active: dict, new_key: str) -> dict:
    """Set the progression's original key; transpose stored chords if key changes."""
    active = ensure_original_structure(active)
    new_key = str(new_key or "C").strip() or "C"
    old_key = str(active.get("original_key_center") or "C").strip() or "C"
    sections = ensure_all_cpl_sections(active.get("original_sections"))
    if old_key != new_key and not progression_is_empty(sections):
        active["original_sections"] = transpose_lab_sections(sections, old_key, new_key)
    active["original_key_center"] = new_key
    active["user_locked_home_key"] = True
    active.pop("tonal_center_inferred", None)
    return active


def anchor_home_key_to_display(active, display_key):
    """Re-home the progression in the current sidebar display key."""
    active = ensure_original_structure(active)
    active["original_sections"] = display_sections_for_key(active, display_key)
    active["original_key_center"] = display_key
    active["user_locked_home_key"] = True
    active.pop("tonal_center_inferred", None)
    return active


def invalidate_cpl_derived_outputs(session_state):
    session_state.pop("cpl_backing_wav", None)
    session_state.pop("cpl_backing_signature", None)
    session_state.pop("cpl_analysis_md", None)
    session_state.pop("cpl_exercises_md", None)


def on_cpl_anchor_home_key() -> None:
    """Button callback: store transposed chart as the new written/home key."""
    import streamlit as st

    active = ensure_original_structure(st.session_state.get(CPL_ACTIVE_KEY) or {})
    practice_key = st.session_state.get("display_key", active.get("original_key_center", "C"))
    anchor_home_key_to_display(active, practice_key)
    st.session_state[CPL_ACTIVE_KEY] = active
    invalidate_cpl_derived_outputs(st.session_state)


def on_cpl_adopt_detected_home_key() -> None:
    """Button callback: lock written/home key to the detected tonal center."""
    import streamlit as st

    active = ensure_original_structure(st.session_state.get(CPL_ACTIVE_KEY) or {})
    analysis = analyze_tonal_center(active.get("original_sections") or {})
    active["original_key_center"] = analysis.get("storage_key", active.get("original_key_center", "C"))
    active["user_locked_home_key"] = True
    active.pop("tonal_center_inferred", None)
    active.pop("home_key_uncertain", None)
    st.session_state[CPL_ACTIVE_KEY] = active
    invalidate_cpl_derived_outputs(st.session_state)


def on_cpl_apply_manual_home_key() -> None:
    """Button callback: lock written/home key from the manual picker."""
    import streamlit as st

    active = ensure_original_structure(st.session_state.get(CPL_ACTIVE_KEY) or {})
    manual = st.session_state.get("cpl_manual_home_key_picker")
    if manual:
        active["original_key_center"] = manual
        active["user_locked_home_key"] = True
        active.pop("tonal_center_inferred", None)
        active.pop("home_key_uncertain", None)
        st.session_state[CPL_ACTIVE_KEY] = active
        invalidate_cpl_derived_outputs(st.session_state)


def on_global_display_key_change(session_state, display_key):
    last = session_state.get(CPL_LAST_DISPLAY_KEY)
    if last is None:
        session_state[CPL_LAST_DISPLAY_KEY] = display_key
        return False
    if last != display_key:
        session_state[CPL_LAST_DISPLAY_KEY] = display_key
        invalidate_cpl_derived_outputs(session_state)
        return True
    return False


def backing_signature(display_key, sections, bpm, loops, groove_style):
    flat = all_chords_from_lab_sections(sections)
    return (display_key, tuple(flat), int(bpm), int(loops), str(groove_style))


def format_chord_bar_line(sections, max_chords: int = 12) -> str:
    """Single-line bar chart preview, e.g. | G | Em | C | D |."""
    chords = all_chords_from_lab_sections(sections)[:max_chords]
    if not chords:
        return "(empty)"
    return "| " + " | ".join(chords) + " |"


def format_entries_friendly_line(entries: list[dict] | None) -> str:
    """Human-readable section line, e.g. G — 2 bars · C · Am."""
    if not entries:
        return ""
    parts: list[str] = []
    for entry in entries:
        ch = normalize_chord_symbol(entry.get("chord", ""))
        if not ch:
            continue
        bars = max(1, int(entry.get("bars", 1) or 1))
        if bars == 1:
            parts.append(ch)
        else:
            parts.append(f"{ch} — {bars} bars")
    return " · ".join(parts)


def clear_all_cpl_sections(home_sections: dict[str, list]) -> None:
    for name in CPL_EDITABLE_SECTIONS:
        home_sections[name] = []


def prepare_cpl_backing_handoff(
    session_state: dict,
    active: dict,
    *,
    section: str | None = None,
) -> None:
    """Sync CPL tempo/groove into Backing Track session keys and queue scope."""
    from types import SimpleNamespace

    from songs.key_state import BACKING_NEEDS_REGEN
    from songs.playback_defaults import (
        apply_backing_defaults_for_song,
        playback_song_id,
        prime_active_song_bpm,
    )

    # `prime_active_song_bpm` / `apply_backing_defaults_for_song` both expect an
    # `st`-like object exposing `session_state`. Build one with SimpleNamespace
    # instead of a class body — `class X: session_state = session_state` raises
    # NameError because Python class bodies cannot resolve a same-name binding
    # against the enclosing function's local scope.
    st_like = SimpleNamespace(session_state=session_state)

    default_bpm = int(active.get("bpm", 100) or 100)
    default_groove = str(active.get("groove_style", "Auto") or "Auto")
    song_id = playback_song_id(
        is_custom=True,
        song_title=str(active.get("name", "") or ""),
        song_artist="",
        custom_name=str(active.get("name", "") or ""),
        custom_revision=str(active.get("id", "") or ""),
    )
    session_state.pop("last_backing_defaults_song_id", None)
    prime_active_song_bpm(st_like, sync_id=song_id, active_song_bpm=default_bpm)
    apply_backing_defaults_for_song(
        st_like,
        song_id=song_id,
        default_bpm=default_bpm,
        default_groove=default_groove,
        song_data=active,
    )
    session_state["backing_track_loops"] = int(active.get("loops", 2) or 2)
    session_state[BACKING_NEEDS_REGEN] = True
    if section:
        session_state[PENDING_BACKING_SCOPE] = "Single section"
        session_state[PENDING_BACKING_SINGLE_SECTION] = section
    else:
        session_state[PENDING_BACKING_SCOPE] = "Full song"
        session_state.pop(PENDING_BACKING_SINGLE_SECTION, None)
    session_state[BACKING_AUTOPLAY] = True


def format_entries_bar_line(entries: list[dict] | None, *, max_chords: int = 24) -> str:
    """Bar line for one section's chord entries."""
    if not entries:
        return "(empty)"
    chords: list[str] = []
    for entry in entries[:max_chords]:
        ch = normalize_chord_symbol(entry.get("chord", ""))
        if not ch:
            continue
        bars = max(1, int(entry.get("bars", 1) or 1))
        chords.extend([ch] * bars)
    if not chords:
        return "(empty)"
    return "| " + " | ".join(chords) + " |"


DEFAULT_SONG_ARRANGEMENT: list[str] = [
    "Intro",
    "Verse",
    "Chorus",
    "Verse",
    "Chorus",
    "Bridge",
    "Chorus",
    "Outro",
]

CHORD_QUICK_EDIT_KEYS: list[str] = ["7", "maj7", "m7", "sus4", "dim", "add9"]

CPL_BUILDER_VERSION = 5

CPL_TIME_SIGNATURES: list[str] = ["4/4", "3/4", "6/8", "2/4"]

CPL_PROGRESSION_STYLES: list[str] = [
    "Pop",
    "Soul/R&B",
    "Jazz",
    "Bossa",
    "Blues",
    "Funk",
    "Rock",
]

CPL_UI_SECTION_ORDER: list[str] = [
    "Verse",
    "Chorus",
    "Bridge",
    "Intro",
    "Pre-Chorus",
    "Solo",
    "Outro",
]

PENDING_BACKING_SCOPE = "_pending_backing_scope"
PENDING_BACKING_SINGLE_SECTION = "_pending_backing_single_section"
PENDING_BACKING_LOOPS = "_pending_backing_loops"
BACKING_AUTOPLAY = "_backing_autoplay"


def sections_with_chords(active: dict, display_key: str) -> list[str]:
    return [
        name
        for name in CPL_EDITABLE_SECTIONS
        if display_entries_for_section(active, display_key, name)
    ]


def filled_section_names(home_sections: dict | None) -> list[str]:
    """Sections that have at least one chord, in UI order."""
    sections = home_sections or {}
    return [
        name
        for name in CPL_UI_SECTION_ORDER
        if name in CPL_EDITABLE_SECTIONS and not section_is_empty(sections.get(name))
    ]


def song_arrangement_flow_text(active: dict, display_key: str) -> str:
    filled = set(sections_with_chords(active, display_key))
    if not filled:
        return (
            " → ".join(DEFAULT_SONG_ARRANGEMENT)
            + "  (sections with chords will show here)"
        )
    flow: list[str] = []
    for name in DEFAULT_SONG_ARRANGEMENT:
        if name in filled:
            flow.append(name)
    for name in CPL_EDITABLE_SECTIONS:
        if name in filled and name not in flow:
            flow.append(name)
    return " → ".join(flow)


def song_structure_overview_html(
    active: dict,
    display_key: str,
    *,
    highlight_section: str | None = None,
    only_filled: bool = True,
) -> str:
    """Song map with chord cells; jazz form labels (A/B) when present."""
    home_sections = active.get("original_sections") or {}
    names = filled_section_names(home_sections)
    if not names:
        return ""

    labels: dict[str, str] = dict(active.get("section_labels") or {})
    time_sig = str(active.get("time_signature") or "4/4")
    use_lead = bool(labels) or bool(active.get("demo_chart_id"))
    prog_name = str(active.get("name") or "").strip()
    wrap_cls = "cpl-song-map cpl-lead-sheet-form" if use_lead else "cpl-song-map"
    blocks = [f'<div class="{wrap_cls}">']
    if prog_name:
        blocks.append(f'<p class="cpl-song-title">{_html.escape(prog_name)}</p>')
    for name in names:
        entries = display_entries_for_section(active, display_key, name)
        tiles = entries_chord_tiles_html(
            entries,
            time_signature=time_sig,
            lead_sheet=use_lead,
        )
        if not tiles:
            continue
        active_cls = " cpl-section-active" if name == highlight_section else ""
        letter = labels.get(name, "")
        letter_html = (
            f'<span class="cpl-form-label">Section {_html.escape(letter)}</span>'
            if letter
            else ""
        )
        blocks.append(
            f'<div class="cpl-section-card cpl-lead-section{active_cls}">'
            f"{letter_html}"
            f'<div class="cpl-section-label">{_html.escape(name)}</div>'
            f"{tiles}"
            "</div>"
        )
    blocks.append("</div>")
    return "".join(blocks)


def cpl_steps_strip_html(*, style: bool, key_set: bool, has_section_chords: bool, finished: bool) -> str:
    """Visual 5-step guide for the builder."""
    def _step(n: int, label: str, done: bool, active: bool) -> str:
        cls = "cpl-step-pill"
        if done:
            cls += " done"
        if active:
            cls += " active"
        return f'<span class="{cls}"><span class="cpl-step-n">{n}</span>{_html.escape(label)}</span>'

    return (
        '<div class="cpl-steps-strip">'
        + _step(1, "Style", style, not style)
        + _step(2, "Key", key_set, style and not key_set)
        + _step(3, "Chords", has_section_chords, key_set and not has_section_chords)
        + _step(4, "Finish", finished, has_section_chords and not finished)
        + _step(5, "Backing track", False, finished)
        + "</div>"
    )


def load_saved_progression(store: dict, name: str) -> dict:
    """Restore a named progression from the saved store (full deep copy)."""
    raw = store.get(name)
    if not raw:
        return default_active_progression()
    out = ensure_original_structure(dict(raw))
    out["name"] = str(raw.get("name") or name)
    out["user_locked_home_key"] = True
    out["original_key_center"] = str(raw.get("original_key_center") or out.get("original_key_center") or "C")
    out["progression_style"] = str(raw.get("progression_style") or out.get("progression_style") or "Pop")
    out["bpm"] = int(raw.get("bpm", out.get("bpm", 100)) or 100)
    out["loops"] = int(raw.get("loops", out.get("loops", 2)) or 2)
    out["groove_style"] = str(raw.get("groove_style") or out.get("groove_style") or "Auto")
    out["time_signature"] = str(raw.get("time_signature") or out.get("time_signature") or "4/4")
    out["original_sections"] = deep_copy_sections(
        ensure_all_cpl_sections(out.get("original_sections"))
    )
    out["section_labels"] = dict(raw.get("section_labels") or {})
    out["demo_chart_id"] = raw.get("demo_chart_id")
    return out


def start_new_progression() -> dict:
    """Blank progression — no chords, default settings."""
    return default_active_progression()


def clear_cpl_widget_state(session_state: dict) -> None:
    """Drop Streamlit widget keys so load/new picks up fresh progression data."""
    keep = {
        CPL_SAVED_KEY,
        CPL_ACTIVE_KEY,
        "cpl_builder_version",
        "display_key",
        "studio_page",
        "active_music_source",
    }
    for key in list(session_state.keys()):
        if key.startswith("cpl_") and key not in keep:
            session_state.pop(key, None)
        if key.startswith("_cpl_prev_bars_"):
            session_state.pop(key, None)
        if is_cpl_ephemeral_widget_key(key):
            session_state.pop(key, None)
    for key in ("_cpl_editing_display_key", "cpl_finished", "_cpl_last_bar_apply"):
        session_state.pop(key, None)
    for key in list(session_state.keys()):
        if key.startswith("cpl_pending_chord_") or key.startswith("cpl_last_bars_"):
            session_state.pop(key, None)


CPL_WIDGET_PERSIST_PREFIXES = (
    "cpl_pending_chord_",
    "cpl_last_bars_",
    "_cpl_prev_bars_",
)

# Streamlit widget keys (buttons, etc.) — never persist or restore.
CPL_EPHEMERAL_WIDGET_PREFIXES = (
    "cpl_sub_",
    "cpl_pick_",
    "cpl_b1_",
    "cpl_b2_",
    "cpl_b4_",
    "cpl_use_slash_",
    "cpl_use_typed_",
    "cpl_custom_sel_",
    "cpl_custom_add_",
    "cpl_demo_",
    "cpl_pre_",
    "cpl_ext_",
    "cpl_slash_root_",
    "cpl_slash_bass_",
    "cpl_custom_text_",
)

CPL_TIMING_PANEL_FIX_ID = "cpl-timing-v2-no-sub-widget-restore"


def is_cpl_ephemeral_widget_key(key: str) -> bool:
    """True for Streamlit widget keys that must not be written via session_state."""
    sk = str(key or "")
    if sk in CPL_WIDGET_PERSIST_SCALAR_KEYS:
        return False
    if sk.startswith("cpl_custom_") and sk not in CPL_WIDGET_PERSIST_SCALAR_KEYS:
        # e.g. cpl_custom_Verse text_input — widget-owned, not cpl_custom_text_* builder.
        parts = sk.split("_", 2)
        if len(parts) >= 3 and parts[0] == "cpl" and parts[1] == "custom":
            return True
    return any(sk.startswith(prefix) for prefix in CPL_EPHEMERAL_WIDGET_PREFIXES)

CPL_WIDGET_PERSIST_SCALAR_KEYS = (
    "cpl_finished",
    "_cpl_editing_display_key",
    CPL_LAST_DISPLAY_KEY,
    "cpl_edit_section",
    "cpl_name",
    "cpl_title_input",
    "cpl_artist_input",
    "cpl_original_key",
    "cpl_time_signature",
    "cpl_progression_style",
    "cpl_style_early",
    "cpl_bpm",
    "cpl_bpm_builder",
    "cpl_groove_style",
)


def purge_cpl_ephemeral_widget_keys(session_state: dict) -> None:
    """Remove persisted Streamlit widget keys that cause ValueAssignmentNotAllowedError."""
    for key in list(session_state.keys()):
        if is_cpl_ephemeral_widget_key(key):
            session_state.pop(key, None)


def export_cpl_widget_state(session_state: dict) -> dict[str, Any]:
    """Persist CPL bar/subdivision widget keys for cross-refresh restore."""
    import copy

    out: dict[str, Any] = {}
    for key in CPL_WIDGET_PERSIST_SCALAR_KEYS:
        if key in session_state:
            out[key] = copy.deepcopy(session_state[key])
    for key in list(session_state.keys()):
        sk = str(key)
        if any(sk.startswith(prefix) for prefix in CPL_WIDGET_PERSIST_PREFIXES):
            if is_cpl_ephemeral_widget_key(sk):
                continue
            out[sk] = copy.deepcopy(session_state[key])
    return out


def import_cpl_widget_state(session_state: dict, blob: dict[str, Any]) -> None:
    """Restore CPL widget keys before CPL widgets render."""
    import copy

    if not isinstance(blob, dict):
        return
    if session_state.get(CPL_WIDGETS_INITIALIZED_KEY):
        return
    for key, val in blob.items():
        sk = str(key)
        if is_cpl_ephemeral_widget_key(sk):
            continue
        session_state[sk] = copy.deepcopy(val)


def apply_cpl_session_progression(session_state: dict, active: dict) -> None:
    """Install progression as active and reset CPL UI widget cache."""
    session_state[CPL_ACTIVE_KEY] = ensure_original_structure(active)
    session_state.pop("cpl_finished", None)
    session_state["_cpl_editing_display_key"] = session_state.get(
        "display_key",
        written_home_key(session_state[CPL_ACTIVE_KEY]),
    )
    clear_cpl_widget_state(session_state)
    reset_cpl_widget_initialization(session_state)
    ensure_cpl_widget_keys_initialized(session_state, session_state[CPL_ACTIVE_KEY])
    invalidate_cpl_derived_outputs(session_state)


def migrate_cpl_builder_version(session_state: dict) -> None:
    """Upgrade builder metadata without wiping an in-progress draft."""
    stored = session_state.get("cpl_builder_version")
    if stored == CPL_BUILDER_VERSION:
        return
    if CPL_ACTIVE_KEY not in session_state:
        session_state[CPL_ACTIVE_KEY] = default_active_progression()
    else:
        session_state[CPL_ACTIVE_KEY] = ensure_original_structure(session_state[CPL_ACTIVE_KEY])
    session_state["cpl_builder_version"] = CPL_BUILDER_VERSION
    ensure_cpl_widget_keys_initialized(session_state, session_state[CPL_ACTIVE_KEY])


CPL_WIDGETS_INITIALIZED_KEY = "_cpl_widgets_initialized"


def reset_cpl_widget_initialization(session_state: dict) -> None:
    """Allow a one-time widget seed from canonical draft (load/new/cloud restore)."""
    session_state.pop(CPL_WIDGETS_INITIALIZED_KEY, None)


def ensure_cpl_widget_keys_initialized(session_state: dict, active: dict) -> None:
    """Seed CPL widget keys once per session; widgets stay source of truth until reset."""
    if session_state.get(CPL_WIDGETS_INITIALIZED_KEY):
        return
    seed_cpl_draft_widgets_from_active(session_state, active, force=True)
    session_state[CPL_WIDGETS_INITIALIZED_KEY] = True


def cpl_draft_chord_count(active: dict) -> int:
    """Count chord entries across all CPL sections."""
    home = ensure_all_cpl_sections((active or {}).get("original_sections"))
    return sum(len(home.get(name) or []) for name in CPL_EDITABLE_SECTIONS)


CPL_DRAFT_WIDGET_KEYS: tuple[str, ...] = (
    "cpl_title_input",
    "cpl_artist_input",
    "cpl_time_signature",
    "cpl_bpm_builder",
    "cpl_style_early",
    "cpl_original_key",
    "cpl_edit_section",
)


def seed_cpl_draft_widgets_from_active(
    session_state: dict,
    active: dict,
    *,
    force: bool = False,
) -> None:
    """Seed Streamlit widget keys from canonical draft fields before widgets render."""
    active = ensure_original_structure(active)
    values = {
        "cpl_title_input": str(active.get("name") or "My Progression"),
        "cpl_artist_input": str(active.get("artist") or ""),
        "cpl_name": str(active.get("name") or "My Progression"),
        "cpl_time_signature": str(active.get("time_signature") or "4/4"),
        "cpl_bpm_builder": int(active.get("bpm", 100) or 100),
        "cpl_bpm": int(active.get("bpm", 100) or 100),
        "cpl_style_early": str(active.get("progression_style") or "Pop"),
        "cpl_progression_style": str(active.get("progression_style") or "Pop"),
        "cpl_original_key": cpl_draft_written_key(active),
    }
    for key, val in values.items():
        if force or key not in session_state:
            session_state[key] = val


def sync_cpl_draft_widgets_to_active(session_state: dict, active: dict) -> dict:
    """Copy live CPL widget values into the canonical draft blob."""
    active = ensure_original_structure(active)
    if "cpl_title_input" in session_state:
        title = str(session_state.get("cpl_title_input") or "").strip()
        active["name"] = title or "My Progression"
    elif "cpl_name" in session_state:
        title = str(session_state.get("cpl_name") or "").strip()
        active["name"] = title or "My Progression"
    if "cpl_artist_input" in session_state:
        active["artist"] = str(session_state.get("cpl_artist_input") or "").strip()
    if "cpl_time_signature" in session_state:
        ts = str(session_state.get("cpl_time_signature") or "4/4").strip()
        if ts in CPL_TIME_SIGNATURES:
            active["time_signature"] = ts
    if "cpl_bpm_builder" in session_state:
        active["bpm"] = int(session_state.get("cpl_bpm_builder") or 100)
    elif "cpl_bpm" in session_state:
        active["bpm"] = int(session_state.get("cpl_bpm") or 100)
    if "cpl_style_early" in session_state:
        style = str(session_state.get("cpl_style_early") or "Pop").strip()
        if style in CPL_PROGRESSION_STYLES:
            active["progression_style"] = style
    elif "cpl_progression_style" in session_state:
        style = str(session_state.get("cpl_progression_style") or "Pop").strip()
        if style in CPL_PROGRESSION_STYLES:
            active["progression_style"] = style
    if "cpl_original_key" in session_state:
        picked = str(session_state.get("cpl_original_key") or "C").strip() or "C"
        stored = cpl_draft_written_key(active)
        if picked != stored:
            active = set_original_key_center(active, picked)
    return active


def persist_cpl_draft_state(st) -> None:
    """Flush CPL draft to local/cloud persistence."""
    import time

    ss = st.session_state
    ss["_cpl_last_persist_attempt_at"] = time.time()
    try:
        from songs.state import persist_music_local_state

        persist_music_local_state(st)
        ss["_cpl_last_persist_ok"] = True
        ss["_cpl_last_persist_error"] = None
    except Exception as exc:
        ss["_cpl_last_persist_ok"] = False
        ss["_cpl_last_persist_error"] = str(exc)
    try:
        exported = export_cpl_widget_state(ss)
        ss["_cpl_last_exported_widget_keys"] = sorted(str(k) for k in exported.keys())
    except Exception:
        ss["_cpl_last_exported_widget_keys"] = []


def cpl_active_from_session(session_state: dict) -> dict:
    """Read the canonical CPL draft from session_state."""
    return ensure_original_structure(session_state.get(CPL_ACTIVE_KEY) or default_active_progression())


def cpl_save_draft(
    session_state: dict,
    active: dict,
    sections: dict | None = None,
    *,
    persist: bool = True,
    st: Any | None = None,
) -> dict:
    """Single write path: widgets → draft blob → session → optional cloud persist."""
    active = ensure_original_structure(session_state.get(CPL_ACTIVE_KEY) or active)
    active = sync_cpl_draft_widgets_to_active(session_state, active)
    home = (
        ensure_all_cpl_sections(sections)
        if sections is not None
        else ensure_all_cpl_sections(active.get("original_sections"))
    )
    active["user_locked_home_key"] = True
    active = commit_home_sections(active, home)
    session_state[CPL_ACTIVE_KEY] = active
    if persist and st is not None:
        persist_cpl_draft_state(st)
    return active


def list_saved_progression_names(store: dict) -> list[str]:
    return sorted(str(k) for k in (store or {}).keys())


def apply_quick_chord_edit(chord: str, edit_key: str) -> str:
    """Replace extensions on the chord root (keeps slash bass if present)."""
    raw = normalize_chord_symbol(chord)
    if not raw:
        return ""
    if "/" in raw:
        head, bass = raw.split("/", 1)
        root = chord_root(head)
        return f"{root}{edit_key}/{bass.strip()}"
    root = chord_root(raw)
    return root + edit_key


def chord_with_bass(chord: str, bass_note: str) -> str:
    raw = normalize_chord_symbol(chord)
    bass = str(bass_note or "").strip()
    if not raw or not bass:
        return raw
    head = raw.split("/", 1)[0]
    root = chord_root(head)
    suffix = head[len(root) :]
    bass_root = chord_root(bass.split("/", 1)[0])
    return f"{root}{suffix}/{bass_root}"


def display_entries_for_section(active: dict, display_key: str, section_name: str) -> list[dict]:
    """Chord entries for one section, transposed to the sidebar display key."""
    home = written_home_key(active)
    home_sections = active.get("original_sections") or {}
    if section_name == "Full Song":
        merged: list[dict] = []
        for name in CPL_EDITABLE_SECTIONS:
            merged.extend(home_sections.get(name) or [])
        home_entries = merged
    else:
        home_entries = list(home_sections.get(section_name) or [])
    if display_key == home:
        return [dict(e) for e in home_entries]
    steps = semitone_distance(home, display_key)
    out = []
    for entry in home_entries:
        if is_repeat_entry(entry):
            out.append(
                {
                    "repeat": True,
                    "bars": max(1, int(entry.get("bars", 1) or 1)),
                }
            )
            continue
        ch = normalize_chord_symbol(entry.get("chord", ""))
        if not ch or ch == "%":
            continue
        out.append({
            "chord": transpose_chord(ch, steps, reference_key=home),
            "bars": max(1, int(entry.get("bars", 1) or 1)),
        })
    return out


def cpl_transpose_explanation_markdown(
    home_key: str,
    practice_key: str,
    original_sections,
    display_sections,
) -> str:
    """Beginner-friendly explanation of written vs practice key for the CPL page."""
    home_key = str(home_key or "C")
    practice_key = str(practice_key or home_key)
    steps = semitone_distance(home_key, practice_key)
    orig_line = format_chord_bar_line(original_sections)
    trans_line = format_chord_bar_line(display_sections)

    if steps == 0:
        shift_note = (
            f"Right now both keys are **{home_key}**, so the chords you see are exactly "
            "what you typed in the written key."
        )
    else:
        shift_note = (
            f"The app moved every chord **{'+' if steps else ''}{steps} semitone(s)** "
            f"from **{home_key}** to **{practice_key}** for display, backing track, and exercises."
        )

    example_home = format_chord_bar_line(
        {
            "Example": [
                {"chord": "Am", "bars": 1},
                {"chord": "Dm", "bars": 1},
                {"chord": "G", "bars": 1},
            ]
        }
    )
    example_practice = format_chord_bar_line(
        {
            "Example": [
                {"chord": "Gm", "bars": 1},
                {"chord": "Cm", "bars": 1},
                {"chord": "F", "bars": 1},
            ]
        }
    )

    return f"""### How keys work in Custom Progression Lab

**Written / Home Key — {home_key}**  
The **tonal center** of your progression (where the harmony belongs). Chords below are stored in this key.

**Practice / Display Key — {practice_key}**  
From the **sidebar** — the key you want to **practice and hear** right now. The app transposes from home → practice.

#### Example
| | |
|---|---|
| Home key **G** (tonal center) | {example_home} |
| Practice key **F** (sidebar) | {example_practice} |

#### Your progression right now
{shift_note}

**Original chords (home key {home_key}):**  
`{orig_line}`

**Practice chords (display key {practice_key}):**  
`{trans_line}`

*Edit chord boxes in the **home** key. Change the sidebar practice key to move everything up or down without retyping.*
"""


def transpose_debug_lines(active, display_key):
    """Human-readable transpose state for UI debugging."""
    active = ensure_original_structure(active)
    home = active.get("original_key_center", "C")
    steps = semitone_distance(home, display_key)
    original_flat = all_chords_from_lab_sections(active.get("original_sections") or {})
    display_flat = all_chords_from_lab_sections(display_sections_for_key(active, display_key))
    first_orig = original_flat[0] if original_flat else "(none)"
    first_disp = display_flat[0] if display_flat else "(none)"
    lines = [
        f"**Written / Home key:** {home}",
        f"**Practice / Display key:** {display_key}",
        f"**Transpose:** {'+' if steps else ''}{steps} semitone(s)",
        f"**First chord (written):** {first_orig}",
        f"**First chord (practice):** {first_disp}",
    ]
    if len(original_flat) >= 4:
        sample_orig = " | ".join(original_flat[:4])
        sample_disp = " | ".join(display_flat[:4])
        lines.append(f"**First four (written):** {sample_orig}")
        lines.append(f"**First four (practice):** {sample_disp}")
    return lines


_REPEAT_RE = re.compile(
    r"\s*[x×*]\s*(\d+)\s*$",
    re.IGNORECASE,
)
# Whitespace-around `/` means "two chords inside one bar". A bare `/`
# (e.g. ``D/F#``) stays a slash chord. The regex requires at least
# one whitespace character on either side of the slash.
_SPLIT_BAR_RE = re.compile(r"\s+/\s+")
# Chart-author shorthand for "rhythmic hit / stop-time" bars: any of
# ``Bm hit``, ``Bm hits``, ``Bm.hit``, ``Bm!`` followed by end of bar.
_HIT_TRAILER_RE = re.compile(
    r"\s*(?:!\.?|\.hit|\s+hit(?:s|stop)?|\s+stop[\- ]?time)\s*$",
    re.IGNORECASE,
)


def _is_rest_token(text: str) -> bool:
    """Plain rest markers (``rest``, ``-``, ``—``) parsed as N.C."""
    cleaned = str(text or "").strip().lower()
    return cleaned in {"rest", "tacet", "-", "—", "–"}


def _bar_to_entry(bar_text: str) -> dict | None:
    """Parse a single bar string into a CPL entry.

    Recognises:

    * ``"Bm"``                  -> normal bar
    * ``"Bm.hit"`` / ``"Bm hit"`` / ``"Bm!"`` -> stop-time hit bar
    * ``"Bm / Em"`` (with whitespace) -> half-bar split = ``"Bm|Em"``
    * ``"D/F#"`` (no whitespace) -> slash chord, untouched
    * ``"N.C."`` / ``"rest"`` / ``"-"`` -> tacet bar (``"N.C."``)
    """
    raw = str(bar_text or "").strip()
    if not raw:
        return None

    # Tacet / rest markers collapse to the canonical ``N.C.`` token.
    if _is_rest_token(raw) or _is_no_chord_token(raw):
        return {"chord": "N.C.", "bars": 1}

    # Half-bar split: ``"Bm / Em"`` -> ``"Bm|Em"`` (one bar, two
    # equal chords). The outer split is on whitespace-padded ``/`` so
    # bare slash chords like ``D/F#`` survive intact.
    if _SPLIT_BAR_RE.search(raw):
        sub_parts = [
            normalize_chord_symbol(p) for p in _SPLIT_BAR_RE.split(raw)
        ]
        sub_parts = [p for p in sub_parts if p]
        if len(sub_parts) >= 2:
            return {"chord": _join_subs(sub_parts), "bars": 1}

    # Hit / stop-time trailer: ``Bm hit``, ``Bm.hit``, ``Bm!``.
    hit_match = _HIT_TRAILER_RE.search(raw)
    if hit_match:
        chord_part = raw[: hit_match.start()].strip()
        chord_part = normalize_chord_symbol(chord_part)
        if chord_part:
            return {"chord": _make_hit_token(chord_part), "bars": 1}

    # Plain chord — possibly already a hit token (``"Bm.hit"``) which
    # ``normalize_chord_symbol`` will preserve as-is.
    chord = normalize_chord_symbol(raw)
    if not chord:
        return None
    return {"chord": chord, "bars": 1}


def parse_chord_line(line):
    """Parse a chart line into ``[{chord, bars, ...}, ...]`` entries.

    Supports the lead-sheet notations that real chord charts use:

    * Bar separators: ``|`` (preferred), ``,``, or whitespace.
    * Repeats: ``"Bm x2"`` / ``"Bm × 4"`` / ``"Bm * 3"`` -> the
      preceding chord expanded N times.
    * Half-bar splits: ``"Bm / Em"`` (whitespace around the slash) ->
      one bar with two equal sub-chords. Bare ``"D/F#"`` keeps its
      slash-bass meaning.
    * No-chord / tacet: ``"N.C."`` / ``"rest"`` / ``"-"`` /
      ``"(N.C.)"``.
    * Stop-time hits: ``"Bm hit"`` / ``"Bm.hit"`` / ``"Bm!"`` -> bar
      stings on beat 1, drums lay out for the rest of the bar.

    Examples::

        parse_chord_line("Bm | Em | G | A")
        parse_chord_line("Bm x2 | Em | G | A")
        parse_chord_line("Bm / Em | G / A")
        parse_chord_line("N.C. | N.C. | Bm | Em")
        parse_chord_line("Bm hit | rest | G | A")
    """
    if not line:
        return []

    # Normalize separators. ``|`` and ``,`` both split bars. We do not
    # collapse whitespace yet because ``Bm x2`` and ``Bm / Em`` need
    # their internal spaces preserved.
    raw = str(line).replace("|", ",")

    # Split on commas first; if the user wrote a single-comma-free
    # whitespace list (e.g. ``"Bm Em G A"``) fall back to whitespace
    # tokenisation for that part. We refuse the whitespace fallback
    # when the chunk already contains rich tokens (`x2`, `/`, `hit`,
    # `N.C.`, `(...)`) - those need explicit comma/bar separators
    # to disambiguate from bar-internal whitespace.
    chunks: list[str] = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        is_rich = bool(
            re.search(r"[x×*]\s*\d", chunk, re.IGNORECASE)
            or re.search(r"\s+/\s+", chunk)
            or re.search(r"hit|stop|rest|n\.?c\.?", chunk, re.IGNORECASE)
            or "/" in chunk and re.search(r"[A-Ga-g]", chunk.split("/")[1] or "")
            or re.search(r"\(.*\)", chunk)
        )
        if "," in chunk or is_rich:
            chunks.append(chunk)
            continue
        sub_words = chunk.split()
        # Only fall back to whitespace tokenisation when the chunk
        # looks like a list of plain chord tokens.
        if (
            len(sub_words) > 1
            and all(re.fullmatch(r"[A-Ga-g][^\s]*", w) for w in sub_words)
        ):
            chunks.extend(sub_words)
        else:
            chunks.append(chunk)

    out: list[dict] = []
    for chunk in chunks:
        # Repeat trailer ``" x2"`` / ``" ×3"`` applies to the bar
        # that immediately precedes it (i.e. the rest of this chunk).
        repeat_match = _REPEAT_RE.search(chunk)
        repeat_count = 1
        if repeat_match:
            try:
                repeat_count = max(1, min(64, int(repeat_match.group(1))))
            except (TypeError, ValueError):
                repeat_count = 1
            chunk = chunk[: repeat_match.start()].strip()

        entry = _bar_to_entry(chunk)
        if not entry:
            continue
        for _ in range(repeat_count):
            # ``copy()`` so the caller can mutate one without
            # spooking the others.
            out.append(dict(entry))
    return out


def flatten_sections_to_events(sections):
    events = []
    ordered_names = [n for n in CPL_EDITABLE_SECTIONS if (sections or {}).get(n)]
    for section_name in (sections or {}):
        if section_name not in ordered_names and section_name != "Full Song":
            ordered_names.append(section_name)
    for section_name in ordered_names:
        entries = (sections or {}).get(section_name) or []
        if not entries:
            continue
        section_bars = 0
        expanded = expand_entries_to_chords(entries)
        section_bars = len(expanded)
        for idx, chord in enumerate(expanded):
            events.append(
                {
                    "chord": chord,
                    "section": section_name,
                    "bar_in_section": idx,
                    "section_bars": max(1, section_bars),
                }
            )
    return events


def sections_to_chord_lists(sections):
    out = {}
    for name, entries in (sections or {}).items():
        chords = expand_entries_to_chords(entries)
        if chords:
            out[name] = chords
    return out


def all_chords_from_lab_sections(sections):
    chords = []
    for _name, chs in sections_to_chord_lists(sections).items():
        chords.extend(chs)
    return chords


def tonal_center_markdown(sections, stored_home_key: str | None = None) -> str:
    analysis = analyze_tonal_center(sections, user_home_key=stored_home_key)
    lines = [analysis["summary"]]
    if analysis.get("roman"):
        lines.append(f"Roman numerals (in {analysis['storage_key']}): {analysis['roman']}")
    if analysis.get("reasons"):
        lines.append("Why: " + "; ".join(analysis["reasons"]))
    stored = stored_home_key or "C"
    detected = analysis.get("storage_key", "C")
    if stored != detected and analysis.get("confidence_score", 0) >= 0.45:
        lines.append(
            f"Stored written/home key is **{stored}**, but the chord movement suggests **{analysis['primary_label']}**."
        )
    return "\n\n".join(lines)


def maybe_update_inferred_home_key(active: dict, *, min_confidence: float = 0.45) -> dict:
    """Backward-compatible alias for sync_written_home_key."""
    return sync_written_home_key(active, min_confidence=min_confidence)


def estimate_key_center(sections, fallback="C"):
    """Backward-compatible: return best tonal-center label (not a blind root count)."""
    analysis = analyze_tonal_center(sections)
    if analysis.get("chords_count", 0) < 1:
        return fallback
    return analysis.get("primary_label", fallback)


def commit_display_sections_to_original(active, display_sections, display_key):
    """Transpose practice-view chords back into written/home key storage."""
    active = ensure_original_structure(active)
    home = written_home_key(active)
    active["original_sections"] = transpose_lab_sections(
        display_sections,
        display_key,
        home,
    )
    return sync_written_home_key(active)


def detect_progression_patterns(chords, key_center):
    findings = []
    if not chords:
        return findings
    pattern = first_matching_pattern(chords, key_center)
    if pattern:
        findings.append(pattern)

    key_pc = NOTE_TO_PC.get(chord_root(key_center))
    if key_pc is None:
        return findings

    roots = [root_pc(ch) for ch in chords]
    rel = [None if pc is None else (pc - key_pc) % 12 for pc in roots]

    # ii-V-I (any start)
    for i in range(len(rel) - 2):
        if rel[i : i + 3] == [2, 7, 0]:
            findings.append("ii-V-I resolution (local)")
            break

    # circle of fifths descent
    if len(rel) >= 3:
        fifths = 0
        for i in range(len(rel) - 1):
            if rel[i] is not None and rel[i + 1] is not None and (rel[i] - rel[i + 1]) % 12 == 7:
                fifths += 1
        if fifths >= 2:
            findings.append("circle-of-fifths root motion")

    # blues fragment (I, IV, I, V or similar)
    if len(rel) >= 4 and rel[0] == 0 and 5 in rel[:4] and 7 in rel[:4]:
        findings.append("blues / dominant-cycle movement")

    # minor-key: i -> iv -> V
    if len(rel) >= 3 and rel[0] == 9 and rel[1] == 5 and rel[2] == 7:
        findings.append("minor-key motion (i-iv-V)")

    qualities = [chord_quality(ch) for ch in chords]
    if any("half-diminished" in q for q in qualities) and any("dominant" in q for q in qualities):
        if "minor ii-V tension" not in findings:
            findings.append("minor ii-V language")

    # modal mixture hint: bVI or bVII in major
    if key_pc is not None and any(r in (8, 10) for r in rel if r is not None):
        if 0 in rel or 9 in rel:
            findings.append("possible modal mixture (borrowed color)")

    # dominant resolution moments
    for i, ch in enumerate(chords):
        if "7" in str(ch).lower() and i + 1 < len(chords):
            nxt = chords[i + 1]
            if chord_quality(nxt) in ("major", "major seventh", "minor"):
                findings.append(f"dominant resolution: {ch} -> {nxt}")
                break

    return list(dict.fromkeys(findings))


def tension_resolution_notes(chords, key_center):
    if len(chords) < 2:
        return ["Single-chord or static harmony — focus on groove and melodic rhythm."]
    lines = []
    for i, ch in enumerate(chords):
        q = chord_quality(ch)
        if "dominant" in q or "diminished" in q or "half-diminished" in q:
            target = chords[i + 1] if i + 1 < len(chords) else chords[0]
            lines.append(f"Tension at **{ch}** — aim for resolution into **{target}**.")
    if not lines:
        lines.append("Harmony is mostly stable — create interest with rhythm, register, and phrasing.")
    return lines[:4]


def suggested_scales_for_chord(ch, key_center):
    q = chord_quality(ch)
    root = chord_root(ch)
    if "dominant" in q:
        return [f"{root} mixolydian", f"{root} diminished whole-half (passing)", "altered dominant (advanced)"]
    if "minor seventh" in q or q == "minor":
        return [f"{root} dorian", f"{root} minor pentatonic", f"{root} melodic minor (jazz)"]
    if "major seventh" in q:
        return [f"{root} major scale", f"{root} lydian (for #11 color)"]
    if "half-diminished" in q:
        return [f"{root} locrian", f"{root} locrian #2", "super Locrian / altered (over V)"]
    return [f"{root} major scale", f"{root} major pentatonic"]


def harmonic_analysis_markdown(sections, key_center, time_signature="4/4"):
    chord_lists = sections_to_chord_lists(sections)
    all_chords = all_chords_from_lab_sections(sections)
    analysis = analyze_tonal_center(sections, user_home_key=key_center)
    est_key = analysis.get("primary_label", key_center)
    lines = [
        "# Harmonic Analysis",
        f"**Practice / display key:** {key_center} | **Harmonic analysis:** {analysis.get('summary', est_key)}",
        f"**Time signature:** {time_signature}",
        "",
        "## Progression patterns",
    ]
    analysis_key = analysis.get("storage_key", key_center)
    patterns = detect_progression_patterns(all_chords, analysis_key)
    if patterns:
        lines.extend(f"- {p}" for p in patterns)
    else:
        lines.append("- No standard pop/jazz cell detected yet — listen for bass direction and dominant arrivals.")

    lines.append("\n## Roman numeral sketch")
    roman = analysis.get("roman") or roman_path(all_chords, analysis_key, limit=12)
    lines.append(f"- {roman or 'Add more chords to see a Roman numeral path.'}")

    lines.append("\n## Tension and resolution")
    lines.extend(f"- {n}" for n in tension_resolution_notes(all_chords, analysis_key))

    if analysis.get("reasons"):
        lines.append("\n## Tonal center clues")
        lines.extend(f"- {r}" for r in analysis["reasons"])

    lines.append("\n## Section breakdown")
    for sec, chords in chord_lists.items():
        lines.extend(section_analysis_lines(sec, chords, analysis_key))

    lines.append("\n## Scales / modes (by chord)")
    seen = set()
    for ch in all_chords[:8]:
        if ch in seen:
            continue
        seen.add(ch)
        scales = suggested_scales_for_chord(ch, analysis_key)
        lines.append(f"- **{ch}:** {', '.join(scales[:2])}")

    return "\n".join(lines)


def _instrument_exercise_block(instrument, level, focus, chords, key_center, groove_style, patterns):
    blocks = []
    inst = instrument or "General"
    pat_text = ", ".join(patterns[:3]) if patterns else "your progression"

    if inst in ["Saxophone", "Flute", "Trumpet", "Clarinet"]:
        blocks.append("### Horn / wind practice")
        blocks.append("- Play chord tones through each change: root, 3rd, 5th, 7th (where present).")
        blocks.append("- Target **3rds and 7ths** on strong beats; use lighter articulation on stable chords.")
        blocks.append("- Write a **guide-tone line** (3rd to 3rd, 7th to 3rd) through two passes.")
        blocks.append("- Add **approach notes** (half-step above/below) into target tones on beats 1 and 3.")
        if "ii-V-I" in pat_text:
            blocks.append("- On ii-V-I: use dorian on ii, mixolydian/altered on V, resolve to chord tones on I.")
        if level == "Advanced":
            blocks.append("- Practice rhythmic displacement: start phrases on the & of 2 or beat 4.")

    elif inst == "Guitar":
        blocks.append("### Guitar practice")
        blocks.append("- **Comping:** practice Freddie Green-style quarter-note pulses, then add skips on the &s.")
        blocks.append("- Map **triad shapes** on the top three strings for each chord; move the nearest shape.")
        blocks.append("- **Voice-leading grips:** connect 3rds/7ths on the middle strings without jumping.")
        blocks.append("- Arpeggiate each chord: root–3rd–5th–7th, then 3rd–5th–7th–9th where available.")
        if focus == "Rhythm":
            blocks.append(f"- Match the **{groove_style}** feel before adding fills.")

    elif inst == "Piano":
        blocks.append("### Piano practice")
        blocks.append("- **Shell voicings:** root or 5th in left hand; 3rd and 7th in right hand.")
        blocks.append("- **Left-hand roots** on beat 1; add fifth or octave on beat 3.")
        blocks.append("- **Comping rhythm:** Charleston or off-beat hits depending on groove.")
        blocks.append("- Connect 3rds/7ths by half-step motion between chords.")

    elif inst == "Bass":
        blocks.append("### Bass practice")
        blocks.append("- Lock **root / fifth / octave** pattern per chord first.")
        blocks.append("- Write a **two-bar walking line** using chord tones and chromatic approaches.")
        blocks.append("- Approach the next root from above or below by half-step on beat 4.")
        if "blues" in pat_text.lower():
            blocks.append("- Blues: emphasize b7 on dominant chords; use shuffle feel.")

    elif inst == "Voice":
        blocks.append("### Voice practice")
        blocks.append("- **Sing roots** of each chord on beat 1 to internalize the form.")
        blocks.append("- **Sing 3rds** to hear major vs minor color changes.")
        blocks.append("- Improvise **short melodic phrases** (2 bars) that land on a chord tone.")
        blocks.append("- Mark breaths before long phrases; save strongest dynamic for dominant arrivals.")

    else:
        blocks.append("### General practice")
        blocks.append("- Play chord roots, then add 3rds and 5ths through the form.")
        blocks.append("- Use 2-bar phrases that land on a chord tone on beat 1.")

    return blocks


def generate_exercises_markdown(
    *,
    sections,
    instrument,
    level,
    focus,
    key_center,
    groove_style,
    time_signature,
    bpm,
):
    chord_lists = sections_to_chord_lists(sections)
    all_chords = all_chords_from_lab_sections(sections)
    patterns = detect_progression_patterns(all_chords, key_center)

    lines = [
        "# Practice & Improvisation Exercises",
        f"**Instrument:** {instrument} | **Level:** {level} | **Focus:** {focus}",
        f"**Key:** {key_center} | **Feel:** {groove_style} | **{time_signature} @ {bpm} BPM**",
        "",
        "## Detected harmonic ideas",
    ]
    if patterns:
        for p in patterns:
            lines.append(f"- {p}")
            if "ii-V-I" in p:
                lines.append("  - Identify the ii, V, and I chords in your chart.")
                lines.append("  - Practice scales: dorian (ii), mixolydian/altered (V), major (I).")
                lines.append("  - Target notes: 3rd of ii, 7th of V, 3rd/7th of I.")
    else:
        lines.append("- Work chord-by-chord: root, 3rd, 5th, 7th on each change.")

    lines.append("\n## Instrument drills")
    lines.extend(_instrument_exercise_block(instrument, level, focus, all_chords, key_center, groove_style, patterns))

    lines.append("\n## Section loops")
    for sec, chords in chord_lists.items():
        path = " | ".join(chords[:8])
        if len(chords) > 8:
            path += " | ..."
        lines.append(f"- **{sec}:** loop slowly — {path}")

    lines.append("\n## Level guidance")
    if level == "Beginner":
        lines.append("- One chord per bar; roots only, then roots + 3rds.")
        lines.append("- Record yourself and check that changes land on beat 1.")
    elif level == "Intermediate":
        lines.append("- Add guide-tone targeting and one repeating 2-bar motif.")
        lines.append("- Practice with the backing at 70–80% tempo first.")
    else:
        lines.append("- Use chromatic approaches, delayed resolutions, and motivic development.")
        lines.append("- Try playing only on offbeats for one chorus.")

    return "\n".join(lines)


def lab_context_for_coaching(sections, key_center, instrument, level, focus):
    chord_lists = sections_to_chord_lists(sections)
    flat = all_chords_from_lab_sections(sections)
    first_sec = next(iter(chord_lists), "Custom")
    first_chords = chord_lists.get(first_sec, flat[:4])
    return {
        "sections": chord_lists,
        "flat_chords": flat,
        "first_section": first_sec,
        "first_chords": first_chords,
        "key_center": key_center,
        "instrument": instrument,
        "level": level,
        "focus": focus,
    }


def save_progression(store, name, data):
    data = ensure_original_structure(dict(data))
    save_name = str(data.get("name") or name).strip() or name
    store[save_name] = {
        "name": save_name,
        "original_key_center": data.get("original_key_center", "C"),
        "original_sections": deep_copy_sections(
            ensure_all_cpl_sections(data.get("original_sections"))
        ),
        "time_signature": data.get("time_signature", "4/4"),
        "bpm": int(data.get("bpm", 100) or 100),
        "groove_style": str(data.get("groove_style", "Auto") or "Auto"),
        "loops": int(data.get("loops", 2) or 2),
        "progression_style": str(data.get("progression_style", "Pop") or "Pop"),
        "user_locked_home_key": bool(data.get("user_locked_home_key", True)),
        "section_labels": dict(data.get("section_labels") or {}),
        "demo_chart_id": data.get("demo_chart_id"),
    }
    return store


def delete_progression(store, name):
    store.pop(name, None)
    return store


# --- UI presets & suggestions ---

import html as _html

CPL_STYLE_CHOICES = [
    "Jazz",
    "Pop",
    "Bossa Nova",
    "Blues",
    "Neo Soul",
    "Ballad",
    "Funk",
    "Rock",
    "Custom",
]

_STYLE_DEFAULTS: dict[str, dict] = {
    "Jazz": {
        "groove_style": "Jazz swing",
        "sections": {
            "Verse": [
                {"chord": "Dm7", "bars": 1},
                {"chord": "G7", "bars": 1},
                {"chord": "Cmaj7", "bars": 1},
                {"chord": "Am7", "bars": 1},
            ],
        },
    },
    "Pop": {
        "groove_style": "Pop groove",
        "sections": {
            "Verse": [
                {"chord": "C", "bars": 1},
                {"chord": "G", "bars": 1},
                {"chord": "Am", "bars": 1},
                {"chord": "F", "bars": 1},
            ],
        },
    },
    "Bossa Nova": {
        "groove_style": "Bossa nova",
        "sections": {
            "Verse": [
                {"chord": "Fmaj7", "bars": 1},
                {"chord": "G7", "bars": 1},
                {"chord": "Gm7", "bars": 1},
                {"chord": "C7", "bars": 1},
            ],
        },
    },
    "Blues": {
        "groove_style": "Rock groove",
        "sections": {
            "Verse": [
                {"chord": "C7", "bars": 1},
                {"chord": "C7", "bars": 1},
                {"chord": "C7", "bars": 1},
                {"chord": "C7", "bars": 1},
                {"chord": "F7", "bars": 1},
                {"chord": "C7", "bars": 1},
                {"chord": "C7", "bars": 1},
                {"chord": "G7", "bars": 1},
            ],
        },
    },
    "Neo Soul": {
        "groove_style": "Funk groove",
        "sections": {
            "Verse": [
                {"chord": "Dm9", "bars": 1},
                {"chord": "G7", "bars": 1},
                {"chord": "Cmaj7", "bars": 1},
                {"chord": "Am7", "bars": 1},
            ],
        },
    },
    "Ballad": {
        "groove_style": "Ballad",
        "sections": {
            "Verse": [
                {"chord": "Cmaj7", "bars": 1},
                {"chord": "Am7", "bars": 1},
                {"chord": "Dm7", "bars": 1},
                {"chord": "G7", "bars": 1},
            ],
        },
    },
    "Funk": {
        "groove_style": "Funk groove",
        "sections": {
            "Verse": [
                {"chord": "E9", "bars": 1},
                {"chord": "E9", "bars": 1},
                {"chord": "A9", "bars": 1},
                {"chord": "E9", "bars": 1},
            ],
        },
    },
    "Rock": {
        "groove_style": "Rock groove",
        "sections": {
            "Verse": [
                {"chord": "G", "bars": 1},
                {"chord": "D", "bars": 1},
                {"chord": "Em", "bars": 1},
                {"chord": "C", "bars": 1},
            ],
        },
    },
}

_CHORD_PRESETS: dict[str, list[tuple[int, str]]] = {
    "ii–V–I": [(2, "m7"), (5, "7"), (0, "maj7")],
    "I–V–vi–IV": [(0, "maj7"), (7, "7"), (9, "m7"), (5, "maj7")],
    "Jazz turnaround": [(0, "maj7"), (9, "7"), (2, "m7"), (7, "7")],
    "Bossa cadence": [(0, "maj7"), (7, "7"), (9, "m7"), (7, "7")],
    "Blues (8 bars)": [(0, "7"), (0, "7"), (0, "7"), (0, "7"), (5, "7"), (0, "7"), (0, "7"), (7, "7")],
    "Neo soul": [(2, "m9"), (5, "7"), (0, "maj7"), (9, "m7")],
}


def _chord_at_degree(home_key: str, degree: int, quality: str) -> str:
    key_pc = NOTE_TO_PC.get(chord_root(home_key))
    if key_pc is None:
        root = "C"
    else:
        root_pc = (key_pc + degree) % 12
        root = _spell_tonic_pc(root_pc, {chord_root(home_key)})
    q = quality or ""
    if q in ("maj7", "m7", "m9", "7", "m7b5"):
        return f"{root}{q}"
    if q == "m":
        return f"{root}m"
    if q == "":
        return root
    return root


def transpose_preset_entries(entries: list[dict], from_key: str, to_key: str) -> list[dict]:
    return transpose_section_entries(entries, from_key, to_key)


def apply_style_preset(style: str, home_key: str) -> dict | None:
    """Return {sections, groove_style} transposed to home_key, or None for Custom."""
    if style == "Custom" or style not in _STYLE_DEFAULTS:
        return None
    data = _STYLE_DEFAULTS[style]
    ref_key = "C"
    if style == "Bossa Nova":
        ref_key = "F"
    elif style == "Blues":
        ref_key = "C"
    sections = deep_copy_sections(data["sections"])
    for name, entries in sections.items():
        sections[name] = transpose_section_entries(entries, ref_key, home_key)
    return {"sections": sections, "groove_style": data["groove_style"]}


CPL_KEY_OPTIONS: list[str] = list(ENHARMONIC_MAJOR_KEYS) + list(ENHARMONIC_MINOR_KEYS)


def _is_minor_home_key(home_key: str) -> bool:
    k = str(home_key or "").strip()
    if not k:
        return False
    root = chord_root(k)
    suffix = k[len(root) :].lower()
    return suffix.startswith("m") and "maj" not in suffix


def format_key_label(home_key: str) -> str:
    """Human label for sidebar/display key, e.g. 'C major' or 'A minor'."""
    k = str(home_key or "C").strip() or "C"
    root = chord_root(k)
    if _is_minor_home_key(k):
        return f"{root} minor"
    return f"{root} major"


def cpl_draft_written_key(active: dict) -> str:
    """Original key shown in CPL — always the user-chosen original_key_center (no inference)."""
    active = ensure_original_structure(active)
    return str(active.get("original_key_center") or "C").strip() or "C"


def cpl_draft_preview_key(active: dict) -> str:
    """Written/home key for in-page chord preview — does not touch global display_key."""
    return cpl_draft_written_key(active)


def ensure_cpl_draft_home_tracking(st, active: dict) -> dict:
    """Invalidate derived CPL outputs when the draft written key changes."""
    home = cpl_draft_written_key(active)
    prev = st.session_state.get("_cpl_editing_home_key")
    if prev != home:
        st.session_state["_cpl_editing_home_key"] = home
        invalidate_cpl_derived_outputs(st.session_state)
    return active


def ensure_cpl_editing_in_display_key(st, active: dict, display_key: str) -> dict:
    """Backward-compatible alias — draft home key only (not global practice display key)."""
    _ = display_key
    return ensure_cpl_draft_home_tracking(st, active)


def simple_chords_for_key(home_key: str) -> list[str]:
    """Beginner triads in the key — C, Dm, Em, F, G, Am (no jazz extensions)."""
    k = str(home_key or "C").strip() or "C"
    if _is_minor_home_key(k):
        specs = [(0, "m"), (2, "m"), (3, ""), (5, "m"), (7, "m"), (8, ""), (10, "")]
    else:
        specs = [(0, ""), (2, "m"), (4, "m"), (5, ""), (7, ""), (9, "m")]
    out: list[str] = []
    seen: set[str] = set()
    for deg, qual in specs:
        ch = _chord_at_degree(k, deg, qual)
        if ch not in seen:
            seen.add(ch)
            out.append(ch)
    return out


STYLE_PRESET_SPECS: dict[str, dict[str, list[tuple[int, str]]]] = {
    "Pop": {
        "I–V–vi–IV": [(0, ""), (7, ""), (9, "m"), (5, "")],
        "vi–IV–I–V": [(9, "m"), (5, ""), (0, ""), (7, "")],
        "I–vi–IV–V": [(0, ""), (9, "m"), (5, ""), (7, "")],
    },
    "Soul/R&B": {
        "I–vi–IV–V": [(0, "maj7"), (9, "m7"), (5, "maj7"), (7, "7")],
        "vi–IV–I–V": [(9, "m7"), (5, "maj7"), (0, "maj7"), (7, "7")],
        "ii–V–I": [(2, "m7"), (5, "7"), (0, "maj7")],
        "I–IV–vi–V": [(0, "maj7"), (5, "maj7"), (9, "m7"), (7, "7")],
    },
    "Jazz": {
        "ii–V–I": [(2, "m7"), (5, "7"), (0, "maj7")],
        "I–vi–ii–V": [(0, "maj7"), (9, "m7"), (2, "m7"), (5, "7")],
        "Jazz turnaround": [(0, "maj7"), (9, "7"), (2, "m7"), (7, "7")],
        "Neo soul": [(2, "m9"), (5, "7"), (0, "maj7"), (9, "m7")],
    },
    "Bossa": {
        "Bossa ii–V": [(2, "m7"), (5, "7"), (0, "maj7")],
        "Minor bossa": [(9, "m7"), (7, "7"), (2, "m7"), (5, "7")],
        "Bossa cadence": [(0, "maj7"), (7, "7"), (9, "m7"), (7, "7")],
        "I–V–vi–IV": [(0, "maj7"), (7, "7"), (9, "m7"), (5, "maj7")],
    },
    "Blues": {
        "Blues (8 bars)": [
            (0, "7"),
            (0, "7"),
            (0, "7"),
            (0, "7"),
            (5, "7"),
            (0, "7"),
            (0, "7"),
            (7, "7"),
        ],
        "Quick change": [(0, "7"), (5, "7"), (0, "7"), (7, "7")],
        "ii–V–I": [(2, "m7"), (5, "7"), (0, "maj7")],
    },
    "Funk": {
        "I7 vamp": [(0, "7"), (0, "7"), (0, "7"), (0, "7")],
        "i7–IV7": [(0, "m7"), (5, "7"), (0, "m7"), (5, "7")],
        "I–IV–I": [(0, "7"), (5, "7"), (0, "7"), (7, "7")],
    },
    "Rock": {
        "I–V–vi–IV": [(0, ""), (7, ""), (9, "m"), (5, "")],
        "I–IV–V": [(0, ""), (5, ""), (7, "")],
        "vi–IV–I–V": [(9, "m"), (5, ""), (0, ""), (7, "")],
        "I–V–IV–V": [(0, ""), (7, ""), (5, ""), (7, "")],
    },
}

# Backward-compatible alias
SIMPLE_PRESET_SPECS = STYLE_PRESET_SPECS.get("Pop", {})


def preset_chords_for_key(spec: list[tuple[int, str]], home_key: str) -> list[str]:
    return [_chord_at_degree(home_key, deg, qual) for deg, qual in spec]


def preset_button_label(preset_id: str, home_key: str, spec: list[tuple[int, str]]) -> str:
    chords = preset_chords_for_key(spec, home_key)
    return f"{preset_id}: {' '.join(chords)}"


def presets_for_style(style: str) -> dict[str, list[tuple[int, str]]]:
    return STYLE_PRESET_SPECS.get(style, STYLE_PRESET_SPECS["Pop"])


def build_style_preset_entries(style: str, preset_id: str, home_key: str) -> list[dict]:
    spec = presets_for_style(style).get(preset_id)
    if not spec:
        return []
    return [{"chord": _chord_at_degree(home_key, deg, qual), "bars": 1} for deg, qual in spec]


def build_simple_preset_entries(preset_name: str, home_key: str) -> list[dict]:
    for style, presets in STYLE_PRESET_SPECS.items():
        if preset_name in presets:
            return build_style_preset_entries(style, preset_name, home_key)
    return []


def diatonic_chords_for_key(home_key: str) -> list[str]:
    """Useful jazz/pop chords in the chosen key (click-to-add on CPL page)."""
    k = str(home_key or "C").strip() or "C"
    if _is_minor_home_key(k):
        specs = [
            (0, "m7"),
            (2, "m7b5"),
            (3, "maj7"),
            (5, "m7"),
            (7, "m7"),
            (8, "maj7"),
            (10, "7"),
            (7, "7"),
        ]
    else:
        specs = [
            (0, "maj7"),
            (2, "m7"),
            (4, "m7"),
            (5, "maj7"),
            (7, "7"),
            (9, "m7"),
            (11, "m7b5"),
        ]
    out: list[str] = []
    seen: set[str] = set()
    for deg, qual in specs:
        ch = _chord_at_degree(k, deg, qual)
        if ch not in seen:
            seen.add(ch)
            out.append(ch)
    return out


def build_preset_entries(preset_name: str, home_key: str) -> list[dict]:
    spec = _CHORD_PRESETS.get(preset_name)
    if not spec:
        return []
    return [
        {"chord": _chord_at_degree(home_key, deg, qual), "bars": 1}
        for deg, qual in spec
    ]


def suggest_next_chords(
    sections: dict,
    home_key: str,
    *,
    limit: int = 4,
) -> list[str]:
    """Harmony-aware next-chord ideas from the last chord in the progression."""
    weighted = weighted_chords_from_sections(sections)
    if not weighted:
        return [
            _chord_at_degree(home_key, 0, "maj7"),
            _chord_at_degree(home_key, 2, "m7"),
            _chord_at_degree(home_key, 5, "7"),
        ][:limit]

    last = weighted[-1][0]
    q = chord_quality(last)
    key_pc = NOTE_TO_PC.get(chord_root(home_key))
    last_pc = root_pc(last)
    out: list[str] = []

    if key_pc is not None and last_pc is not None:
        rel = (last_pc - key_pc) % 12
        if "dominant" in q:
            out.append(_chord_at_degree(home_key, 0, "maj7"))
            out.append(_chord_at_degree(home_key, 9, "m7"))
            out.append(_chord_at_degree(home_key, 2, "m7"))
        elif "minor" in q and "half" not in q:
            out.append(_chord_at_degree(home_key, 5, "7"))
            out.append(_chord_at_degree(home_key, 0, "maj7"))
            out.append(_chord_at_degree(home_key, 7, "7"))
        elif "major" in q:
            out.append(_chord_at_degree(home_key, 2, "m7"))
            out.append(_chord_at_degree(home_key, 5, "7"))
            out.append(_chord_at_degree(home_key, 9, "m7"))
        else:
            out.append(_chord_at_degree(home_key, 5, "7"))
            out.append(_chord_at_degree(home_key, 0, "maj7"))

    for deg, qual in [(2, "m7"), (5, "7"), (0, "maj7"), (9, "m7"), (5, "maj7"), (7, "7")]:
        cand = _chord_at_degree(home_key, deg, qual)
        if cand != last and cand not in out:
            out.append(cand)

    if "maj7" in last.lower() and _chord_at_degree(home_key, 5, "7") not in out:
        out.insert(0, _chord_at_degree(home_key, 5, "7"))

    return out[:limit]


def chords_per_measure(time_signature: str) -> int:
    """How many chord slots fit in one notated measure row."""
    ts = str(time_signature or "4/4").strip()
    return {"3/4": 3, "2/4": 2, "6/8": 3}.get(ts, 4)


def entries_chord_tiles_html(
    entries: list[dict] | None,
    *,
    time_signature: str = "4/4",
    max_tiles: int = 48,
    lead_sheet: bool = False,
) -> str:
    """Chord cells grouped by time signature; % for repeat notation (lead-sheet style)."""
    slots = expand_entries_to_display_slots(entries)[:max_tiles]
    if not slots:
        return ""
    cells: list[str] = []
    for display, _sound in slots:
        cls = "chord-cell cpl-chord-cell"
        if display == "%":
            cls += " cpl-repeat-cell"
        cells.append(
            f'<div class="{cls}">'
            f'<div class="chord-symbol">{_html.escape(display)}</div>'
            f"</div>"
        )
    per_measure = max(1, chords_per_measure(time_signature))
    row_cls = "cpl-measure-row cpl-lead-measure-row" if lead_sheet else "cpl-measure-row"
    wrap_cls = "cpl-measures cpl-lead-sheet" if lead_sheet else "cpl-measures"
    rows: list[str] = []
    for i in range(0, len(cells), per_measure):
        chunk = cells[i : i + per_measure]
        rows.append(
            f'<div class="{row_cls}">'
            '<span class="cpl-measure-bar">|</span>'
            + "".join(chunk)
            + '<span class="cpl-measure-bar">|</span>'
            "</div>"
        )
    return f'<div class="{wrap_cls}">{"".join(rows)}</div>'


def chord_tiles_html(chords: list[str], *, max_tiles: int = 16) -> str:
    if not chords:
        return ""
    entries = [{"chord": ch, "bars": 1} for ch in chords[:max_tiles]]
    return entries_chord_tiles_html(entries, max_tiles=max_tiles)


def cpl_section_progression_view(
    active: dict,
    *,
    section_name: str,
    preview_key: str,
    pending_chord: str | None = None,
    time_signature: str = "4/4",
    use_lead_sheet: bool = False,
) -> dict[str, Any]:
    """View model for the CPL builder progression panel (Streamlit page + tests)."""
    active = ensure_original_structure(active)
    home_sections = ensure_all_cpl_sections(active.get("original_sections"))
    home_entries = list(home_sections.get(section_name) or [])
    section_display = display_entries_for_section(active, preview_key, section_name)
    if not section_display and not section_is_empty(home_entries):
        section_display = [
            dict(entry)
            for entry in home_entries
            if normalize_chord_symbol(str(entry.get("chord", "")))
        ]
    tiles_html = ""
    if section_display:
        tiles_html = entries_chord_tiles_html(
            section_display,
            time_signature=time_signature,
            lead_sheet=use_lead_sheet,
        )
    has_chords = bool(section_display) or not section_is_empty(home_entries)
    pending = str(pending_chord or "").strip() or None
    show_panel = has_chords or bool(pending)
    panel_bits: list[str] = ['<div class="cpl-live-progression">']
    if tiles_html:
        panel_bits.append(tiles_html)
    if pending:
        panel_bits.append(
            f'<p class="cpl-pending-hint">Selected: <strong>{_html.escape(pending)}</strong> '
            f"— click 1, 2, or 4 bars above to add it</p>"
        )
    panel_bits.append("</div>")
    native_rows: list[tuple[str, int]] = []
    for entry in section_display:
        chord_label = str(entry.get("chord", "")).strip()
        if not chord_label or chord_label == "%":
            continue
        bar_count = max(1, int(entry.get("bars", 1) or 1))
        native_rows.append((chord_label, bar_count))
    native_lines = [
        f"{chord_label} — {bar_count} bar{'s' if bar_count != 1 else ''}"
        for chord_label, bar_count in native_rows
    ]
    return {
        "section_display": section_display,
        "home_entries": home_entries,
        "tiles_html": tiles_html,
        "has_chords": has_chords,
        "show_panel": show_panel,
        "panel_html": "".join(panel_bits) if show_panel else "",
        "native_rows": native_rows,
        "native_lines": native_lines,
    }


def cpl_apply_pending_chord_to_section(
    active: dict,
    *,
    section_name: str,
    pending_chord: str,
    bars: int,
) -> dict:
    """Mirror CPL page bar-button flow: append pending chord, then persist sections."""
    active = ensure_original_structure(active)
    home_sections = ensure_all_cpl_sections(active.get("original_sections"))
    chord = normalize_chord_symbol(pending_chord) or str(pending_chord or "").strip()
    if not chord:
        return active
    home_sections[section_name].append({"chord": chord, "bars": max(1, int(bars or 1))})
    return commit_home_sections(active, home_sections)


def cpl_format_section_line(rows: list[tuple[str, int]]) -> str:
    parts: list[str] = []
    for chord, bar_count in rows:
        unit = "bar" if bar_count == 1 else "bars"
        parts.append(f"{chord} — {bar_count} {unit}")
    return " · ".join(parts)


def cpl_whole_song_progression_view(active: dict, preview_key: str) -> dict[str, Any]:
    """Whole-song display model for the CPL page (native + HTML fallbacks)."""
    active = ensure_original_structure(active)
    home_sections = ensure_all_cpl_sections(active.get("original_sections"))
    section_blocks: list[dict[str, Any]] = []
    for name in filled_section_names(home_sections):
        view = cpl_section_progression_view(
            active,
            section_name=name,
            preview_key=preview_key,
            time_signature=str(active.get("time_signature") or "4/4"),
        )
        if not view["native_rows"]:
            continue
        section_blocks.append(
            {
                "name": name,
                "rows": list(view["native_rows"]),
                "line": cpl_format_section_line(view["native_rows"]),
            }
        )
    return {
        "sections": section_blocks,
        "has_any": bool(section_blocks),
    }


def cpl_apply_chord_with_bars_to_session(
    session_state: dict,
    *,
    section_name: str,
    chord: str,
    bars: int,
    st: Any | None = None,
    persist: bool = False,
) -> dict:
    """Simulate CPL page flow: pick chord → choose bars → save draft."""
    active = cpl_active_from_session(session_state)
    home = ensure_all_cpl_sections(active.get("original_sections"))
    symbol = normalize_chord_symbol(chord) or str(chord or "").strip()
    if not symbol:
        return active
    home[section_name].append({"chord": symbol, "bars": max(1, int(bars or 1))})
    session_state.pop(f"cpl_pending_chord_{section_name}", None)
    return cpl_save_draft(session_state, active, home, persist=persist, st=st)


def build_cpl_developer_diagnostics(
    session_state: dict,
    active: dict,
    *,
    edit_section: str,
) -> dict[str, Any]:
    """Live CPL state snapshot for developer-mode panel."""
    active = ensure_original_structure(active)
    home = ensure_all_cpl_sections(active.get("original_sections"))
    pending_key = f"cpl_pending_chord_{edit_section}"
    bars_key = f"cpl_last_bars_{edit_section}"
    preview_key = cpl_draft_preview_key(active)
    section_view = cpl_section_progression_view(
        active,
        section_name=edit_section,
        preview_key=preview_key,
        pending_chord=session_state.get(pending_key),
        time_signature=str(active.get("time_signature") or "4/4"),
    )
    whole_song_view = cpl_whole_song_progression_view(active, preview_key)
    chord_count = cpl_draft_chord_count(active)
    return {
        "widgets": {
            key: session_state.get(key)
            for key in CPL_DRAFT_WIDGET_KEYS
        },
        "widget_lifecycle": {
            "widgets_initialized": bool(session_state.get(CPL_WIDGETS_INITIALIZED_KEY)),
            "reseed_flag_pending": bool(session_state.get("_cpl_reseed_widgets_from_active")),
        },
        "draft": {
            "title": active.get("name"),
            "artist": active.get("artist"),
            "style": active.get("progression_style"),
            "bpm": active.get("bpm"),
            "meter": active.get("time_signature"),
            "original_key": cpl_draft_written_key(active),
            "original_key_center": active.get("original_key_center"),
            "user_locked_home_key": active.get("user_locked_home_key"),
            "section_count": len(filled_section_names(home)),
            "chord_count": chord_count,
            "original_sections": copy.deepcopy(home),
        },
        "session_home_sections": {
            edit_section: copy.deepcopy(home.get(edit_section) or []),
        },
        "display_path": {
            "preview_key": preview_key,
            "section_view": {
                "show_panel": section_view["show_panel"],
                "has_chords": section_view["has_chords"],
                "native_rows": section_view["native_rows"],
                "home_entry_count": len(section_view["home_entries"]),
            },
            "whole_song_view": {
                "has_any": whole_song_view["has_any"],
                "section_names": [block["name"] for block in whole_song_view["sections"]],
                "sections": whole_song_view["sections"],
            },
        },
        "pending": {
            "edit_section": edit_section,
            "pending_chord": session_state.get(pending_key),
            "last_bars": session_state.get(bars_key),
        },
        "persistence": {
            "last_persist_attempt_at": session_state.get("_cpl_last_persist_attempt_at"),
            "last_persist_ok": session_state.get("_cpl_last_persist_ok"),
            "last_persist_error": session_state.get("_cpl_last_persist_error"),
            "exported_widget_keys": session_state.get("_cpl_last_exported_widget_keys"),
            "builder_version": session_state.get("cpl_builder_version"),
        },
    }


def cpl_page_end_save_should_preserve_sections(
    session_state: dict,
    *,
    sections_snapshot: dict,
) -> bool:
    """True when end-of-page save would not drop newly-added chords."""
    active = cpl_active_from_session(session_state)
    current = ensure_all_cpl_sections(active.get("original_sections"))
    snap = ensure_all_cpl_sections(sections_snapshot)
    snap_count = sum(len(snap.get(name) or []) for name in CPL_EDITABLE_SECTIONS)
    cur_count = sum(len(current.get(name) or []) for name in CPL_EDITABLE_SECTIONS)
    return cur_count >= snap_count
