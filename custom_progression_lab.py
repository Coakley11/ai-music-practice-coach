"""Custom Progression Lab — builder, harmonic analysis, and practice exercises."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


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

from creative_lab_text import (
    chord_quality,
    chord_root,
    first_matching_pattern,
    root_pc,
    roman_path,
    section_analysis_lines,
    NOTE_TO_PC,
)

CPL_SAVED_KEY = "cpl_saved_progressions"
CPL_ACTIVE_KEY = "cpl_active_progression"
CPL_LAST_DISPLAY_KEY = "cpl_last_display_key"

DEFAULT_SECTIONS = {
    "Verse": [
        {"chord": "Am", "bars": 1},
        {"chord": "Dm", "bars": 1},
        {"chord": "G7", "bars": 1},
        {"chord": "Cmaj7", "bars": 1},
    ],
    "Chorus": [
        {"chord": "Fmaj7", "bars": 1},
        {"chord": "Bm7b5", "bars": 1},
        {"chord": "E7", "bars": 1},
        {"chord": "Am", "bars": 1},
    ],
}


def default_active_progression():
    home_key = "C"
    original = {k: [dict(x) for x in v] for k, v in DEFAULT_SECTIONS.items()}
    return {
        "name": "Untitled progression",
        "original_key_center": home_key,
        "original_sections": original,
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
        legacy = active.get("sections") or DEFAULT_SECTIONS
        active["original_sections"] = deep_copy_sections(legacy)
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
        chord = normalize_chord_symbol(entry.get("chord", ""))
        if not chord:
            continue
        out.append(
            {
                "chord": transpose_chord(chord, steps),
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
    head = raw.split("/", 1)[0].strip()
    if len(head) < 1:
        return ""
    return raw


def weighted_chords_from_sections(sections):
    """Expand section entries to (chord, bar_weight) pairs in form order."""
    weighted = []
    for _name, entries in (sections or {}).items():
        for entry in entries or []:
            chord = normalize_chord_symbol(entry.get("chord", ""))
            if not chord:
                continue
            weighted.append((chord, max(1, int(entry.get("bars", 1) or 1))))
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
    """Persist chords in written/home key and refresh tonal-center home key."""
    active = ensure_original_structure(active)
    active["original_sections"] = deep_copy_sections(home_sections)
    return sync_written_home_key(active)


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
        return "| *(add chords below)* |"
    return "| " + " | ".join(chords) + " |"


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


def parse_chord_line(line):
    if not line:
        return []
    parts = [p.strip() for p in line.replace("|", ",").split(",")]
    out = []
    for part in parts:
        ch = normalize_chord_symbol(part)
        if ch:
            out.append({"chord": ch, "bars": 1})
    return out


def flatten_sections_to_events(sections):
    events = []
    for section_name, entries in (sections or {}).items():
        if not entries:
            continue
        section_bars = 0
        expanded = []
        for entry in entries:
            chord = normalize_chord_symbol(entry.get("chord", ""))
            if not chord:
                continue
            bars = max(1, int(entry.get("bars", 1) or 1))
            for _ in range(bars):
                expanded.append(chord)
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
        chords = []
        for entry in entries or []:
            ch = normalize_chord_symbol(entry.get("chord", ""))
            if not ch:
                continue
            bars = max(1, int(entry.get("bars", 1) or 1))
            chords.extend([ch] * bars)
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
    store[name] = {
        "name": name,
        "original_key_center": data.get("original_key_center", "C"),
        "original_sections": deep_copy_sections(data.get("original_sections")),
        "time_signature": data.get("time_signature", "4/4"),
        "bpm": data.get("bpm", 100),
        "groove_style": data.get("groove_style", "Auto"),
        "loops": data.get("loops", 2),
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


CPL_KEY_OPTIONS: list[str] = [
    "C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B",
    "Cm", "C#m", "Dm", "Ebm", "Em", "Fm", "F#m", "Gm", "Abm", "Am", "Bbm", "Bm",
]


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


def ensure_cpl_editing_in_display_key(st, active: dict, display_key: str) -> dict:
    """When the global sidebar key changes, re-home the progression in that key."""
    display_key = str(display_key or "C").strip() or "C"
    prev = st.session_state.get("_cpl_editing_display_key")
    if prev != display_key:
        active = anchor_home_key_to_display(active, display_key)
        st.session_state[CPL_ACTIVE_KEY] = active
        st.session_state["_cpl_editing_display_key"] = display_key
        invalidate_cpl_derived_outputs(st.session_state)
    return active


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


def chord_tiles_html(chords: list[str], *, max_tiles: int = 16) -> str:
    if not chords:
        return '<div class="cpl-chord-row empty">Add chords below</div>'
    tiles = []
    for ch in chords[:max_tiles]:
        tiles.append(
            f'<div class="cpl-chord-tile"><span class="cpl-chord-name">{_html.escape(ch)}</span></div>'
        )
    return f'<div class="cpl-chord-row">{"".join(tiles)}</div>'
