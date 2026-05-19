# VERSION: v48_metronome_lyrics_practice

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import io

try:
    import librosa
except Exception:
    librosa = None

import json
import wave
import tempfile
import html
import time
from pathlib import Path
from datetime import date

# -------------------------------------------------
# PAGE CONFIG
# -------------------------------------------------

st.set_page_config(
    page_title="Daniel Cohen AI Music Practice Coach",
    page_icon="🎵",
    layout="wide"
)

# -------------------------------------------------
# GLOBAL CONSTANTS + SONG CATALOG
# -------------------------------------------------

DATA_FILE = Path("practice_history.json")

import importlib.util
import sys

_MUSIC_THEORY_PATH = Path(__file__).resolve().parent / "music_theory.py"
if not _MUSIC_THEORY_PATH.is_file():
    raise ImportError(
        f"music_theory.py must sit next to this app (expected {_MUSIC_THEORY_PATH}). "
        "Add that file to the repository root and redeploy."
    )
_spec = importlib.util.spec_from_file_location(
    "music_theory",
    str(_MUSIC_THEORY_PATH),
)
if _spec is None or _spec.loader is None:
    raise ImportError(f"Could not load music_theory from {_MUSIC_THEORY_PATH}")
_music_theory = importlib.util.module_from_spec(_spec)
sys.modules["music_theory"] = _music_theory
_spec.loader.exec_module(_music_theory)

COMMON_KEYS = _music_theory.COMMON_KEYS
CHROMATIC = _music_theory.CHROMATIC
FLAT_TO_SHARP = _music_theory.FLAT_TO_SHARP
NOTE_TO_MIDI = _music_theory.NOTE_TO_MIDI
normalize_root = _music_theory.normalize_root
split_chord = _music_theory.split_chord
semitone_distance = _music_theory.semitone_distance
transpose_chord = _music_theory.transpose_chord
transpose_sections = _music_theory.transpose_sections
transpose_sections_dict = _music_theory.transpose_sections_dict
transpose_guitar_tabs = _music_theory.transpose_guitar_tabs

from song_catalog import (
    load_song_catalog,
    search_records,
    format_pick_key,
    parse_pick_key,
    record_for_pick_key,
)
from songs import (
    apply_pick_key,
    chord_blocks_for_backing,
    ensure_master_song_initialized,
    form_timeline_rows,
    get_song_context,
    section_order,
)

SONG_LIBRARY, SONG_PICKER_CATALOG, GENRES, ALL_SONG_RECORDS = load_song_catalog()
TRUSTED_CORE_RECORDS = [
    r for r in ALL_SONG_RECORDS
    if r.get("trusted_core") or r.get("chart_status") in {"verified", "practice_level_verified"}
]
DEFAULT_SONG_RECORDS = TRUSTED_CORE_RECORDS or ALL_SONG_RECORDS

ensure_master_song_initialized(
    st,
    all_records=DEFAULT_SONG_RECORDS,
    song_library=SONG_LIBRARY,
    song_picker_catalog=SONG_PICKER_CATALOG,
)

genre, song, song_data = get_song_context(
    st,
    song_library=SONG_LIBRARY,
    song_picker_catalog=SONG_PICKER_CATALOG,
)

if (
    DEFAULT_SONG_RECORDS
    and st.session_state.get("chart_library_mode", "Trusted core charts only") == "Trusted core charts only"
    and not song_data.get("trusted_core")
    and song_data.get("chart_status") not in {"verified", "practice_level_verified"}
):
    _r0 = DEFAULT_SONG_RECORDS[0]
    _pk0 = format_pick_key(_r0["genre"], f"{_r0['title']} — {_r0['artist']}")
    apply_pick_key(st, _pk0, SONG_PICKER_CATALOG)
    genre, song, song_data = get_song_context(
        st,
        song_library=SONG_LIBRARY,
        song_picker_catalog=SONG_PICKER_CATALOG,
    )

# -------------------------------------------------
# HELPER FUNCTIONS
# -------------------------------------------------

def all_chords_from_sections(sections):

    out = []

    for section_chords in sections.values():
        out.extend(section_chords)

    return out

def _chord_head(chord):
    return str(chord).strip().split("/", 1)[0]


def _chord_bass(chord):
    parts = str(chord).strip().split("/", 1)
    return parts[1] if len(parts) == 2 and parts[1] else parts[0]


def _midi_for_root_symbol(symbol, fallback=60):
    root = split_chord(symbol)[0]
    return NOTE_TO_MIDI.get(root, NOTE_TO_MIDI.get(normalize_root(root), fallback))


def chord_notes(chord):

    head = _chord_head(chord)

    root, suffix = split_chord(head)

    base = NOTE_TO_MIDI.get(root, 60)
    base = NOTE_TO_MIDI.get(normalize_root(root), base)

    low = suffix.lower()

    if "m7b5" in low:
        intervals = [0,3,6,10]

    elif "dim7" in low:
        intervals = [0,3,6,9]

    elif "dim" in low:
        intervals = [0,3,6]

    elif "maj9" in low:
        intervals = [0,4,7,11,14]

    elif "maj7" in low:
        intervals = [0,4,7,11]

    elif "m9" in low:
        intervals = [0,3,7,10,14]

    elif "m7" in low:
        intervals = [0,3,7,10]

    elif "m" in low and "maj" not in low:
        intervals = [0,3,7]

    elif "13" in low:
        intervals = [0,4,7,10,14,21]

    elif "add9" in low:
        intervals = [0,4,7,14]

    elif "9" in low:
        intervals = [0,4,7,10,14]

    elif "6" in low:
        intervals = [0,4,7,9]

    elif "sus" in low:
        intervals = [0,5,7,10] if "7" in low else [0,5,7]

    elif "7" in low:
        intervals = [0,4,7,10]

    else:
        intervals = [0,4,7]

    if "b9" in low:
        intervals.append(13)
    elif "#9" in low:
        intervals.append(15)
    if "#11" in low:
        intervals.append(18)
    if "b13" in low:
        intervals.append(20)

    return [base+i for i in intervals]


def bass_note(chord):
    return _midi_for_root_symbol(_chord_bass(chord), 48)


def _simplify_chord(chord, genre_name=""):
    chord = str(chord).strip()
    bass = ""
    head = chord
    if "/" in chord:
        head, bass = chord.split("/", 1)

    root, suffix = split_chord(head)
    s = suffix.lower()
    if "m7b5" in s or "dim" in s:
        out = root + "dim"
    elif s.startswith("m") and "maj" not in s:
        out = root + "m"
    elif "7" in s and ("blues" in genre_name.lower()):
        out = root + "7"
    else:
        out = root

    return f"{out}/{bass}" if bass else out


def _intermediate_chord(chord):
    chord = str(chord).strip()
    if "maj9" in chord:
        return chord.replace("maj9", "maj7")
    if "m9" in chord:
        return chord.replace("m9", "m7")
    if "13" in chord:
        return chord.replace("13", "7")
    return chord.replace("7#9", "7").replace("7b9", "7")


def _advanced_chord(chord, genre_name):
    chord = str(chord).strip()
    head = _chord_head(chord)
    bass = ""
    if "/" in chord:
        bass = "/" + chord.split("/", 1)[1]
    root, suffix = split_chord(head)
    s = suffix.lower()
    jazzish = genre_name in ["Jazz", "Blues"] or "maj7" in s or "m7" in s or "m7b5" in s

    if "13" in s or "9" in s or "alt" in s or "#9" in s or "b9" in s:
        return chord
    if jazzish and "maj7" in s:
        return root + "maj9" + bass
    if jazzish and "m7b5" in s:
        return root + "m7b5" + bass
    if jazzish and "m7" in s:
        return root + "m9" + bass
    if jazzish and "7" in s and "maj" not in s:
        return root + "13" + bass
    if genre_name in ["Pop", "Rock"] and s == "":
        return root + "add9" + bass
    if genre_name in ["Pop", "Rock"] and s == "m":
        return root + "m7" + bass
    return chord


def sections_for_level(song_data, level):
    explicit_versions = song_data.get("chart_versions") or {}
    if level in explicit_versions and explicit_versions[level]:
        return explicit_versions[level]

    raw = song_data.get("sections", {})
    genre_name = song_data.get("genre", "")
    if level == "Beginner":
        return {name: [_simplify_chord(ch, genre_name) for ch in chords] for name, chords in raw.items()}
    if level == "Intermediate":
        return {name: [_intermediate_chord(ch) for ch in chords] for name, chords in raw.items()}
    return {name: [_advanced_chord(ch, song_data.get("genre", "")) for ch in chords] for name, chords in raw.items()}


def chart_status_label(song_data):
    status = (song_data.get("chart_status") or "placeholder").strip()
    labels = {
        "verified": ("Verified chart", "success"),
        "practice_level_verified": ("Practice-level verified chart", "success"),
        "trusted": ("Practice approximation — trusted core", "info"),
        "practice_simplified": ("Practice approximation", "info"),
        "placeholder": ("Placeholder chart — needs verification", "warning"),
    }
    return labels.get(status, ("Placeholder chart — needs verification", "warning"))


def trusted_core_records(records):
    return [
        r for r in records
        if r.get("trusted_core") or r.get("chart_status") in {"verified", "practice_level_verified"}
    ]


def visible_records_for_mode(records, mode):
    if mode == "Trusted core charts only":
        return trusted_core_records(records)
    return [r for r in records if r.get("chart_status") != "placeholder"]


def filter_records_by_chart_status(records, status_filter):
    if status_filter == "Any non-placeholder":
        return [r for r in records if r.get("chart_status") != "placeholder"]
    if status_filter == "Trusted core":
        return trusted_core_records(records)
    if status_filter == "Verified":
        return [r for r in records if r.get("chart_status") in {"verified", "practice_level_verified"}]
    if status_filter == "Practice approximation":
        return [r for r in records if r.get("chart_status") in {"practice_simplified", "practice_level_verified"}]
    return records


def filter_records_by_level(records, level_filter):
    if level_filter == "Any level":
        return records

    def has_level_chart(row):
        versions = row.get("chart_versions") or {}
        return level_filter in versions or row.get("chart_status") != "placeholder"

    return [r for r in records if has_level_chart(r)]


def chord_blocks_for_selected_sections(sections, selected_names=None):
    selected = set(selected_names or [])
    out = []
    for section_name, section_chords in section_order(sections):
        if selected and section_name not in selected:
            continue
        out.extend(section_chords)
    return out


def chord_events_for_selected_sections(sections, selected_names=None):
    selected = set(selected_names or [])
    out = []
    for section_name, section_chords in section_order(sections):
        if selected and section_name not in selected:
            continue
        section_bars = len(section_chords)
        for idx, chord in enumerate(section_chords):
            out.append({
                "chord": chord,
                "section": section_name,
                "bar_in_section": idx,
                "section_bars": section_bars,
            })
    return out


def compact_bar_summary(chords):
    if not chords:
        return ""
    chunks = []
    last = chords[0]
    count = 1
    for ch in chords[1:]:
        if ch == last:
            count += 1
        else:
            chunks.append(f"{last} ({count} bar{'s' if count != 1 else ''})")
            last = ch
            count = 1
    chunks.append(f"{last} ({count} bar{'s' if count != 1 else ''})")
    return "| " + " | ".join(chunks) + " |"


def short_chord_summary(chords, limit=4):
    if not chords:
        return "No chords"
    unique = []
    for chord in chords:
        if chord not in unique:
            unique.append(chord)
    suffix = " ..." if len(unique) > limit else ""
    return " - ".join(unique[:limit]) + suffix


def _section_lyric_lines(section_name, lyric_cues=None, section_lyrics=None, limit=4):
    user_text = (section_lyrics or {}).get(section_name, "")
    lines = [line.strip() for line in str(user_text).splitlines() if line.strip()]
    if not lines:
        lines = [
            line.strip()
            for line in (lyric_cues or {}).get(section_name, [])
            if str(line).strip()
        ]
    return lines[:limit]


def _markdown_table_cell(value):
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def bar_grid_markdown(chords, bars_per_row=4):
    rows = []
    for i in range(0, len(chords), bars_per_row):
        row = chords[i:i + bars_per_row]
        display = []
        for j, ch in enumerate(row):
            absolute = i + j
            if absolute > 0 and ch == chords[absolute - 1]:
                display.append("%")
            else:
                display.append(ch)
        bars = [f"Bar {i + j + 1}" for j in range(len(row))]
        rows.append("| " + " | ".join(bars) + " |")
        rows.append("| " + " | ".join(["---"] * len(row)) + " |")
        rows.append("| " + " | ".join(f"**{cell}**" for cell in display) + " |")
        rows.append("")
    return "\n".join(rows).strip()


def lyric_aligned_bar_grid_markdown(section_name, chords, lyric_cues=None, section_lyrics=None, bars_per_row=4):
    lyric_lines = _section_lyric_lines(
        section_name,
        lyric_cues=lyric_cues,
        section_lyrics=section_lyrics,
        limit=max(1, int(np.ceil(max(1, len(chords)) / bars_per_row))),
    )
    if not lyric_lines:
        return bar_grid_markdown(chords, bars_per_row=bars_per_row)

    rows = []
    for i in range(0, len(chords), bars_per_row):
        row = chords[i:i + bars_per_row]
        display = []
        for j, ch in enumerate(row):
            absolute = i + j
            if absolute > 0 and ch == chords[absolute - 1]:
                display.append("%")
            else:
                display.append(ch)
        lyric = lyric_lines[min(i // bars_per_row, len(lyric_lines) - 1)]
        bars = [f"Bar {i + j + 1}" for j in range(len(row))]
        rows.append("| " + " | ".join(bars) + " | Phrase |")
        rows.append("| " + " | ".join(["---"] * len(row)) + " |---|")
        rows.append(
            "| "
            + " | ".join(f"**{_markdown_table_cell(cell)}**" for cell in display)
            + f" | _{_markdown_table_cell(lyric)}_ |"
        )
        rows.append("")
    return "\n".join(rows).strip()


def form_summary_markdown(sections):
    rows = ["| Section | Bars | Harmonic rhythm |", "|---|---:|---|"]
    for section_name, chords in sections.items():
        if not chords:
            continue
        rows.append(f"| {section_name} | {len(chords)} | {compact_bar_summary(chords)} |")
    return "\n".join(rows)


def render_song_timeline(sections, lyric_cues=None, section_lyrics=None):
    blocks = []
    total_bars = max(1, sum(len(chords) for chords in sections.values()))
    for section_name, chords in sections.items():
        if not chords:
            continue
        width = max(14, min(38, round((len(chords) / total_bars) * 100)))
        lyric_lines = _section_lyric_lines(
            section_name,
            lyric_cues=lyric_cues,
            section_lyrics=section_lyrics,
            limit=1,
        )
        lyric = lyric_lines[0] if lyric_lines else "Add a cue in the sidebar"
        blocks.append(
            f"""
            <div class="song-timeline-block" style="flex: {max(1, len(chords))} 1 {width}%;">
              <div class="timeline-section-name">{html.escape(section_name)}</div>
              <div class="timeline-bars">{len(chords)} bars</div>
              <div class="timeline-chords">{html.escape(short_chord_summary(chords))}</div>
              <div class="timeline-lyric">{html.escape(lyric)}</div>
            </div>
            """
        )

    if not blocks:
        st.info("No section data is available for this song yet.")
        return

    st.markdown(
        f"""
        <style>
        .song-timeline {{
            display: flex;
            gap: 10px;
            overflow-x: auto;
            padding: 10px 0 14px 0;
            margin-bottom: 8px;
        }}
        .song-timeline-block {{
            min-width: 150px;
            border: 1px solid rgba(49, 51, 63, 0.18);
            border-radius: 12px;
            padding: 12px;
            background: linear-gradient(180deg, rgba(240, 247, 255, 0.95), rgba(255, 255, 255, 0.98));
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
        }}
        .timeline-section-name {{
            font-weight: 750;
            font-size: 0.98rem;
            margin-bottom: 4px;
        }}
        .timeline-bars {{
            color: #5f6b7a;
            font-size: 0.82rem;
            margin-bottom: 8px;
        }}
        .timeline-chords {{
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            font-size: 0.84rem;
            color: #172033;
            margin-bottom: 8px;
            white-space: nowrap;
        }}
        .timeline-lyric {{
            color: #475569;
            font-size: 0.82rem;
            line-height: 1.25;
        }}
        </style>
        <div class="song-timeline">
          {''.join(blocks)}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _section_match_score(label, section_name):
    label_norm = " ".join(label.lower().replace("-", " ").replace("/", " ").split())
    section_norm = " ".join(section_name.lower().replace("-", " ").replace("/", " ").split())
    section_base = _section_base_name(section_name).replace("-", " ")
    if not label_norm or not section_norm:
        return None
    if label_norm == section_norm:
        return 0
    if label_norm == section_base:
        return 1
    section_tokens = set(section_norm.split())
    label_tokens = set(label_norm.split())
    if label_tokens and label_tokens.issubset(section_tokens):
        if label_norm == "chorus" and "pre" in section_tokens:
            return 8
        return 2
    if label_norm in section_norm:
        if label_norm == "chorus" and "pre chorus" in section_norm:
            return 8
        return 4
    return None


def match_lyric_section_label(label, section_names):
    scored = []
    for idx, section_name in enumerate(section_names):
        score = _section_match_score(label, section_name)
        if score is not None:
            scored.append((score, len(section_name), idx, section_name))
    if not scored:
        return None
    return sorted(scored)[0][3]


def parse_user_lyric_cues(raw_text, section_names):
    """User-provided cues only. No lyric scraping or generation."""
    if not raw_text:
        return {}

    cues = {name: [] for name in section_names}
    current = None

    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if ":" in line:
            maybe_section, cue = line.split(":", 1)
            match = match_lyric_section_label(maybe_section.strip(), section_names)
            if match:
                current = match
                if cue.strip():
                    cues[current].append(cue.strip())
                continue

        if current is None:
            current = section_names[0] if section_names else None

        if current:
            cues[current].append(line)

    return {name: lines for name, lines in cues.items() if lines}


def _song_slug(song_name, artist_name=""):
    raw = f"{song_name}_{artist_name}".lower()
    return "".join(c if c.isalnum() else "_" for c in raw).strip("_")


def _section_base_name(section_name):
    return section_name.split("(", 1)[0].split("/", 1)[0].strip().lower()


def split_lyrics_by_sections(raw_text, section_names):
    """Best-effort assignment from user-provided lyrics/cues to chart sections."""
    if not raw_text:
        return {}

    parsed = parse_user_lyric_cues(raw_text, section_names)
    if parsed:
        return {name: "\n".join(lines) for name, lines in parsed.items()}

    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    if not lines or not section_names:
        return {}

    out = {name: "" for name in section_names}
    chunk_size = max(1, int(np.ceil(len(lines) / max(1, len(section_names)))))
    for idx, section_name in enumerate(section_names):
        chunk = lines[idx * chunk_size:(idx + 1) * chunk_size]
        if chunk:
            out[section_name] = "\n".join(chunk)
    return {name: text for name, text in out.items() if text.strip()}


def lyric_cues_from_section_lyrics(section_lyrics):
    cues = {}
    for section_name, text in (section_lyrics or {}).items():
        lines = [line.strip() for line in str(text).splitlines() if line.strip()]
        if lines:
            cues[section_name] = lines
    return cues


def lyric_cue_markdown(section_name, chords, lyric_cues, instrument, full_section_lyrics=None):
    cues = lyric_cues.get(section_name, []) if lyric_cues else []
    section_text = (full_section_lyrics or {}).get(section_name, "")
    out = []

    if cues:
        out.append("**Lyric / phrase cues:**")
        for idx, cue in enumerate(cues[:4]):
            bar_hint = min(idx * 4 + 1, max(1, len(chords)))
            chord_hint = chords[bar_hint - 1] if chords else "the first chord"
            out.append(f"- Bar {bar_hint} ({chord_hint}): {cue}")
        if instrument == "Voice" and section_text:
            out.append("\n**User-provided lyric text for this section:**")
            for line in str(section_text).splitlines()[:8]:
                if line.strip():
                    out.append(f"> {line.strip()}")
    elif instrument == "Voice":
        entry = chords[0] if chords else "the first chord"
        peak = chords[max(0, len(chords) // 2)] if chords else "the middle of the phrase"
        end = chords[-1] if chords else "the final chord"
        out.append("**Vocal placement guide:**")
        out.append(f"- Enter lightly on **{entry}**; save stronger tone for the phrase peak.")
        out.append(f"- Breathe before the section and around bar {max(1, min(5, len(chords)))} if needed.")
        out.append(f"- Aim phrase shape toward **{peak}**, then release cleanly into **{end}**.")
        out.append("- Practice once on vowels only, then add diction without tightening the jaw.")
    else:
        entry = chords[0] if chords else "the first chord"
        out.append("**Section locator cue:**")
        out.append(f"- {section_name}: phrase/section entry starts around **{entry}**. Add your own lyric cue in the sidebar for tighter alignment.")

    return "\n".join(out)


def lyric_guide_markdown(sections, lyric_cues, instrument, section_lyrics=None):
    out = ["### Lyric / Section Cue Guide"]
    if instrument == "Voice":
        out.append("_Use this to map entrances, breaths, vowels, phrase peaks, and delivery. Paste your own lyrics/cues in the sidebar for exact alignment._")
    else:
        out.append("_Short locator cues help you know where you are in the form. The app does not fetch or generate full copyrighted lyrics._")

    for section_name, chords in sections.items():
        cue_lines = lyric_cues.get(section_name, []) if lyric_cues else []
        full_text = (section_lyrics or {}).get(section_name, "")
        entry = chords[0] if chords else "the first chord"
        peak = chords[max(0, len(chords) // 2)] if chords else "the middle"
        if cue_lines:
            cue = "; ".join(cue_lines[:2])
        elif instrument == "Voice":
            cue = f"Enter on {entry}; breathe before the section; shape toward {peak}."
        else:
            cue = f"{section_name} entry around {entry}; listen for the section change and phrase shape."
        out.append(f"- **{section_name}** ({len(chords)} bars): {cue}")
        if instrument == "Voice" and full_text:
            out.append(f"  - Delivery: speak the text in rhythm first, mark a breath before bar 1, and sing stronger near **{peak}**.")
            for line in str(full_text).splitlines()[:2]:
                if line.strip():
                    out.append(f"  - Lyric line: _{line.strip()}_")
    return "\n".join(out)


GUITAR_VOICING_LIBRARY = {
    "C": "x32010", "Cmaj7": "x32000", "Cmaj9": "x32430", "Cadd9": "x32030",
    "Cm": "x35543", "Cm7": "x35343", "Cm9": "x3133x", "C7": "x32310", "C13": "x32335",
    "D": "xx0232", "D/F#": "2x0232", "Dmaj7": "xx0222", "Dmaj9": "x5465x", "Dm": "xx0231",
    "Dm7": "xx0211", "Dm9": "x5355x", "D7": "xx0212", "D13": "x54557",
    "E": "022100", "Emaj7": "021100", "Em": "022000", "Em7": "020000", "Em9": "020002", "E7": "020100",
    "F": "133211", "Fmaj7": "1x2210", "Fmaj9": "1x2010", "Fm": "133111", "Fm7": "131111", "F7": "131211",
    "G": "320003", "G/B": "x20003", "Gmaj7": "3x443x", "Gmaj9": "3x423x", "Gm": "355333", "Gm7": "353333", "G7": "320001", "G13": "3x3455",
    "A": "x02220", "A/G": "3x2220", "Amaj7": "x02120", "Am": "x02210", "Am7": "x02010", "Am9": "x05500", "A7": "x02020", "A13": "x02022",
    "Bb": "x13331", "Bbmaj7": "x13231", "Bbm7": "x13121", "Bb7": "x13131",
    "B": "x24442", "Bm": "x24432", "Bm7": "x24232", "B7": "x21202", "Bm7b5": "x2323x",
}


def _voicing_family(chord, level):
    head = _chord_head(chord)
    root, suffix = split_chord(head)
    low = suffix.lower()
    if "m7b5" in low:
        return f"{chord}: half-diminished shell, root on 5th string, shape `x-1-2-1-2-x` moved to {root}"
    if "maj9" in low:
        return f"{chord}: maj9 color grip, root + 3rd + 7th + 9th (avoid doubling the 5th)"
    if "13" in low:
        return f"{chord}: dominant 13 shell, play 3rd + b7 + 13, omit the root if bass is covered"
    if "m9" in low:
        return f"{chord}: minor 9 shell, root + b3 + b7 + 9"
    if "maj7" in low:
        return f"{chord}: movable maj7 shell, keep 3rd and 7th on adjacent strings"
    if "m7" in low:
        return f"{chord}: minor 7 shell / drop-2 grip"
    if "7" in low:
        return f"{chord}: dominant 7 shell; advanced: add 9 or 13 on top"
    if level == "Advanced":
        return f"{chord}: try a triad inversion plus 9th if it fits the melody"
    return f"{chord}: playable open/barre grip; keep the top note clean"


def guitar_voicing_lines(chords, song_data, display_key, level):
    tabs = transpose_guitar_tabs(
        song_data.get("guitar_tabs", {}),
        song_data["key"],
        display_key,
    )
    seen = []
    for ch in chords:
        if ch not in seen:
            seen.append(ch)
    lines = ["\n## Guitar Chord Diagrams / Voicings", "_String order: E A D G B e_"]
    for ch in seen[:24]:
        if ch in tabs:
            lines.append(f"- **{ch}**: `{tabs[ch]}`")
        elif ch in GUITAR_VOICING_LIBRARY:
            lines.append(f"- **{ch}**: `{GUITAR_VOICING_LIBRARY[ch]}`")
        else:
            lines.append(f"- **{_voicing_family(ch, level)}**")
    if len(seen) > 24:
        lines.append(f"- ...plus {len(seen) - 24} more chord symbols in the full form.")
    return lines

def midi_note_name(m):

    names = [
        "C","C#","D","Eb","E","F",
        "F#","G","Ab","A","Bb","B"
    ]

    return names[m % 12]

def abc_note(midi_num):

    names = [
        "C","^C","D","_E","E","F",
        "^F","G","_A","A","_B","B"
    ]

    return names[midi_num % 12]

def render_abc(abc_text):

    escaped = (
        abc_text
        .replace("\\", "\\\\")
        .replace("`", "\\`")
        .replace("${", "\\${")
    )

    html = f"""
    <html>
    <head>
    <script src="https://cdn.jsdelivr.net/npm/abcjs@6.4.4/dist/abcjs-basic-min.js"></script>
    </head>
    <body>
    <div id="paper"></div>
    <script>
    ABCJS.renderAbc(
        "paper",
        `{escaped}`,
        {{
            responsive:"resize",
            staffwidth:760
        }}
    );
    </script>
    </body>
    </html>
    """

    components.html(
        html,
        height=350,
        scrolling=True
    )


def render_metronome_widget(default_bpm=100, default_signature="4/4"):
    config = json.dumps({
        "bpm": int(default_bpm),
        "signature": default_signature,
    })
    html = f"""
    <div id="metro-root" style="font-family: system-ui, -apple-system, Segoe UI, sans-serif; border:1px solid #ddd; border-radius:12px; padding:14px; max-width:760px;">
      <h4 style="margin:0 0 10px 0;">Practice Metronome</h4>
      <div style="display:flex; gap:12px; flex-wrap:wrap; align-items:end;">
        <label>BPM<br><input id="metro-bpm" type="range" min="40" max="240" value="{default_bpm}" style="width:220px;"></label>
        <div><strong id="metro-bpm-label">{default_bpm}</strong> BPM</div>
        <label>Time signature<br>
          <select id="metro-sig">
            <option>2/4</option><option>3/4</option><option selected>4/4</option>
            <option>6/8</option><option>3/8</option><option>5/4</option><option>7/8</option>
          </select>
        </label>
        <button id="metro-start" style="padding:8px 14px;">Start Metronome</button>
        <button id="metro-stop" style="padding:8px 14px;">Stop Metronome</button>
      </div>
      <div style="margin-top:12px;">
        <div>Beat: <strong id="metro-beat">-</strong> / <span id="metro-beats-per-measure">4</span> | Measure: <strong id="metro-measure">0</strong></div>
        <div id="metro-dots" style="display:flex; gap:8px; margin-top:10px;"></div>
      </div>
      <p style="margin:10px 0 0 0; color:#666; font-size:13px;">First beat is accented higher/louder; other beats are softer/lower. Audio starts after pressing Start.</p>
    </div>
    <script>
    (() => {{
      const cfg = {config};
      const bpmInput = document.getElementById("metro-bpm");
      const bpmLabel = document.getElementById("metro-bpm-label");
      const sigSelect = document.getElementById("metro-sig");
      const beatEl = document.getElementById("metro-beat");
      const measureEl = document.getElementById("metro-measure");
      const beatsPerEl = document.getElementById("metro-beats-per-measure");
      const dotsEl = document.getElementById("metro-dots");
      let ctx = null;
      let timer = null;
      let beat = 0;
      let measure = 0;

      bpmInput.value = cfg.bpm;
      bpmLabel.textContent = cfg.bpm;
      sigSelect.value = cfg.signature;

      function beatsPerMeasure() {{
        return parseInt(sigSelect.value.split("/")[0], 10);
      }}

      function drawDots(activeBeat) {{
        const beats = beatsPerMeasure();
        beatsPerEl.textContent = beats;
        dotsEl.innerHTML = "";
        for (let i = 1; i <= beats; i++) {{
          const dot = document.createElement("div");
          dot.textContent = i;
          dot.style.width = "34px";
          dot.style.height = "34px";
          dot.style.borderRadius = "50%";
          dot.style.display = "flex";
          dot.style.alignItems = "center";
          dot.style.justifyContent = "center";
          dot.style.border = "1px solid #aaa";
          dot.style.background = i === activeBeat ? (i === 1 ? "#ffcc66" : "#b7e4ff") : "#f5f5f5";
          dot.style.fontWeight = i === activeBeat ? "700" : "400";
          dotsEl.appendChild(dot);
        }}
      }}

      function click(accent) {{
        if (!ctx) return;
        const now = ctx.currentTime;
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.frequency.value = accent ? 1180 : 760;
        gain.gain.setValueAtTime(accent ? 0.42 : 0.20, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.07);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(now);
        osc.stop(now + 0.08);
      }}

      function tick() {{
        const beats = beatsPerMeasure();
        beat += 1;
        if (beat > beats) {{
          beat = 1;
          measure += 1;
        }}
        click(beat === 1);
        beatEl.textContent = beat;
        measureEl.textContent = measure;
        drawDots(beat);
      }}

      function start() {{
        stop();
        ctx = ctx || new (window.AudioContext || window.webkitAudioContext)();
        beat = 0;
        measure = 1;
        tick();
        const intervalMs = 60000 / parseInt(bpmInput.value, 10);
        timer = setInterval(tick, intervalMs);
      }}

      function stop() {{
        if (timer) clearInterval(timer);
        timer = null;
        beat = 0;
        measure = 0;
        beatEl.textContent = "-";
        measureEl.textContent = "0";
        drawDots(0);
      }}

      bpmInput.addEventListener("input", () => {{
        bpmLabel.textContent = bpmInput.value;
        if (timer) start();
      }});
      sigSelect.addEventListener("change", () => {{
        if (timer) start();
        else drawDots(0);
      }});
      document.getElementById("metro-start").addEventListener("click", start);
      document.getElementById("metro-stop").addEventListener("click", stop);
      drawDots(0);
    }})();
    </script>
    """
    components.html(html, height=230)

def build_abc(song_name, sections):

    chords = all_chords_from_sections(
        sections
    )[:8]

    melody = []

    for ch in chords:

        mids = chord_notes(ch)

        melody.extend([
            abc_note(mids[0]),
            abc_note(mids[1]),
            abc_note(mids[2]),
            abc_note(mids[0])
        ])

    bars = [
        " ".join(melody[i:i+4])
        for i in range(0, len(melody), 4)
    ]

    music = " | ".join(bars) + " |"

    return f"""
X:1
T:{song_name}
M:4/4
L:1/4
K:C
{music}
"""


def _chart_section_role(section_name):
    name = str(section_name or "").lower()
    if "chorus" in name and "pre" not in name:
        return "chorus"
    if "pre" in name:
        return "pre"
    if "verse" in name or "main loop" in name:
        return "verse"
    if "bridge" in name:
        return "bridge"
    if "solo" in name:
        return "solo"
    if "intro" in name or "outro" in name or "ending" in name:
        return "gray"
    return "neutral"


def _chart_feel_label(style):
    return {
        "Pop groove": "Pop 8th-note feel",
        "Rock groove": "Rock 8th-note feel",
        "Jazz swing": "Swing feel",
        "Bossa nova": "Bossa feel",
        "Funk groove": "Funk syncopation",
        "Ballad": "Ballad feel",
    }.get(style or "Pop groove", style or "Pop groove")


def _chart_lyric_lines(section_name, lyric_cues=None, section_lyrics=None):
    user_text = (section_lyrics or {}).get(section_name, "")
    lines = [line.strip() for line in str(user_text).splitlines() if line.strip()]
    if not lines:
        lines = [
            line.strip()
            for line in (lyric_cues or {}).get(section_name, [])
            if str(line).strip()
        ]
    return lines


def _chart_grid_html(chords, current_bar=None):
    if not chords:
        return "<div class='empty-chart'>No chords entered for this section.</div>"
    cells = []
    for idx, chord in enumerate(chords):
        previous = chords[idx - 1] if idx else None
        display = "%" if previous and chord == previous else str(chord)
        current_class = " current-chord" if current_bar == idx + 1 else ""
        repeat_count = 1
        if display != "%":
            for nxt in chords[idx + 1:]:
                if nxt != chord:
                    break
                repeat_count += 1
        duration = f"<span class='duration'>{repeat_count} bars</span>" if repeat_count > 1 else ""
        cells.append(
            f"<div class='chord-cell{current_class}'>"
            f"<div class='bar-num'>Bar {idx + 1}</div>"
            f"<div class='chord-symbol'>{html.escape(display)}</div>"
            f"{duration}"
            "</div>"
        )
    return "<div class='lead-grid'>" + "".join(cells) + "</div>"


def _roman_for_chord(chord, key_name):
    key_root, key_suffix = split_chord(str(key_name or "C"))
    root, suffix = split_chord(_chord_head(chord))
    minor_key = key_suffix.lower().startswith("m")
    romans = {
        0: ("I", "i"), 1: ("bII", "bII"), 2: ("II", "ii"), 3: ("bIII", "III"),
        4: ("III", "#III"), 5: ("IV", "iv"), 6: ("#IV", "#iv"), 7: ("V", "v"),
        8: ("bVI", "VI"), 9: ("VI", "#VI"), 10: ("bVII", "VII"), 11: ("VII", "#VII"),
    }
    r = NOTE_TO_MIDI.get(root, NOTE_TO_MIDI.get(normalize_root(root), 60)) % 12
    k = NOTE_TO_MIDI.get(key_root, NOTE_TO_MIDI.get(normalize_root(key_root), 60)) % 12
    roman = romans.get((r - k) % 12, ("?", "?"))[1 if minor_key else 0]
    low = str(suffix).lower()
    if low.startswith("m") and "maj" not in low:
        roman = roman.lower()
    if "dim" in low or "m7b5" in low:
        roman += "o"
    if "7" in low and "maj" not in low:
        roman += "7"
    return roman


def _inline_harmonic_analysis(section_name, chords, key_name):
    if not chords:
        return "No harmonic movement entered yet."
    condensed = []
    for chord in chords:
        if not condensed or condensed[-1] != chord:
            condensed.append(chord)
    roman_text = "-".join(_roman_for_chord(ch, key_name) for ch in condensed[:6])
    role = _chart_section_role(section_name)
    if role == "chorus":
        return f"Chorus harmony centers on <strong>{roman_text}</strong>; play it broader and let the resolution feel earned."
    if role == "bridge":
        return f"Bridge color: <strong>{roman_text}</strong> gives contrast before returning to the main form."
    if role == "verse":
        return f"Verse loop: <strong>{roman_text}</strong>. Keep the texture lighter so the melody has room."
    if any("/" in str(ch) for ch in chords):
        return f"Listen for bass movement inside <strong>{roman_text}</strong>; slash chords help connect the section."
    return f"Harmonic shape: <strong>{roman_text}</strong> across the main phrase."


def _backing_chord_color_tip(chords, instrument):
    family = _instrument_family(instrument) if "_instrument_family" in globals() else "general"
    for chord in chords:
        low = str(chord).lower()
        safe = html.escape(str(chord))
        if "add9" in low:
            return f"{safe} has an open add9 color; keep the 9th audible instead of burying it in a thick attack."
        if "maj7" in low:
            if family == "piano":
                return f"{safe} wants a lighter touch; voice the maj7 inside and let the top extension sing."
            if family == "guitar":
                return f"{safe} sounds best as a smaller grip; let the maj7 color ring instead of using a heavy full barre."
            return f"{safe} is a soft color chord; phrase into it gently and avoid over-accenting the 7th."
        if "sus" in low:
            return f"{safe} delays resolution; lean into the suspension, then release cleanly into the next bar."
        if "/" in str(chord):
            return f"{safe} is about bass motion; respect the written bass note when practicing the section."
        if "dim" in low or "m7b5" in low:
            return f"{safe} is passing tension; keep the line moving and resolve it clearly."
        if "7#9" in low or "7b9" in low or "13" in low:
            return f"{safe} adds dominant bite; make the tension rhythmic, then relax into the resolution."
    return ""


def _section_overlay(instrument, focus, chords, section_name="", groove_style=""):
    first = chords[0] if chords else "the first chord"
    second = chords[1] if len(chords) > 1 else first
    family = _instrument_family(instrument) if "_instrument_family" in globals() else "general"
    role = _chart_section_role(section_name)
    feel = _chart_feel_label(groove_style)
    color_tip = _backing_chord_color_tip(chords, instrument)
    role_action = {
        "verse": "keep the part sparse and leave air around the melody",
        "pre": "increase motion so the chorus feels pulled forward",
        "chorus": "widen the register and make the downbeats more confident",
        "bridge": "change texture or register so the listener hears a new color",
        "solo": "answer the groove with short phrases, not constant notes",
        "gray": "set up or release the form without overcrowding it",
    }.get(role, "make the section function clear")

    if family == "guitar":
        if focus == "Melody":
            base = f"Lead: target chord tones from <strong>{html.escape(str(first))}</strong>, then slide/bend into <strong>{html.escape(str(second))}</strong>; {role_action}."
        else:
            base = f"Guitar: in this {feel}, use muted strokes in setup sections and open strums for lift; keep compact voicings for <strong>{html.escape(str(first))} to {html.escape(str(second))}</strong>."
    if family == "piano":
        base = f"Piano: left hand roots/fifths, right hand shells or spread voicings; connect <strong>{html.escape(str(first))} to {html.escape(str(second))}</strong> by nearest motion and {role_action}."
    elif family == "bass":
        base = f"Bass: lock to the kick, root on beat 1, fifth or octave on beat 3, then approach <strong>{html.escape(str(second))}</strong> chromatically when the section builds."
    elif family == "winds":
        base = f"{html.escape(str(instrument))}: breathe before the phrase, answer the melody sparingly, and target the 3rd/7th over <strong>{html.escape(str(first))}</strong>."
    elif family == "voice":
        base = f"Voice: place breath before bar 1, keep vowels focused through <strong>{html.escape(str(first))}</strong>, and save the strongest dynamic for chorus/hook arrivals."
    elif family != "guitar":
        base = f"Lock the first change <strong>{html.escape(str(first))} to {html.escape(str(second))}</strong> to the {feel} before adding fills."
    return f"{base} {color_tip}" if color_tip else base


def _section_lyric_html(section_name, chords, instrument, lyric_cues=None, section_lyrics=None):
    lines = _chart_lyric_lines(section_name, lyric_cues=lyric_cues, section_lyrics=section_lyrics)
    family = _instrument_family(instrument) if "_instrument_family" in globals() else "general"
    if not lines:
        if family == "voice":
            return "<div class='lyric-box'>Voice phrase: add a lyric cue for exact alignment. Breathe before bar 1 and shape toward the middle of the section.</div>"
        return "<div class='lyric-box muted'>No lyric cue added for this section.</div>"
    safe_lines = [html.escape(line) for line in lines]
    if family == "voice":
        peak_bar = max(1, min(len(chords), int(np.ceil(max(1, len(chords)) / 2))))
        visible = "<br>".join(f"&ldquo;{line}&rdquo;" for line in safe_lines[:4])
        return (
            "<div class='lyric-box voice'>"
            f"<strong>Lyric / phrase cue:</strong><br>{visible}"
            f"<div class='phrase-note'>Breath before bar 1; phrase start at bar 1; grow toward bar {peak_bar}; chorus/hook sections carry the strongest delivery.</div>"
            "</div>"
        )
    return f"<div class='lyric-box'><strong>Lyric cue:</strong> &ldquo;{safe_lines[0]}&rdquo;</div>"


def full_chord_markdown(
    song_name,
    song_data,
    sections,
    instrument,
    display_key=None,
    level="Intermediate",
    lyric_cues=None,
    section_lyrics=None,
    groove_style="Pop groove",
    bpm=100,
    time_signature="4/4",
    current_section=None,
    current_bar=None,
    focus="",
):
    dk = display_key or song_data["key"]
    status_text, _status_kind = chart_status_label(song_data)
    total_bars = sum(len(chords) for chords in sections.values())
    now_playing = current_section or "Full song"
    ext = song_data.get("extensions") or {}

    style = """
<style>
.lead-sheet { font-family: system-ui, -apple-system, Segoe UI, sans-serif; }
.lead-header {
  border: 1px solid rgba(15, 23, 42, 0.12);
  border-radius: 16px;
  padding: 16px 18px;
  margin-bottom: 14px;
  background: linear-gradient(180deg, #ffffff, #f8fafc);
}
.lead-title { font-size: 1.35rem; font-weight: 800; margin-bottom: 4px; }
.lead-subtitle { color: #475569; margin-bottom: 12px; }
.meta-row { display: flex; gap: 8px; flex-wrap: wrap; }
.meta-pill {
  border: 1px solid rgba(15, 23, 42, 0.12);
  border-radius: 999px;
  padding: 5px 10px;
  background: #fff;
  font-size: 0.82rem;
  color: #334155;
}
.now-playing {
  border-left: 5px solid #22c55e;
  background: #f0fdf4;
  padding: 10px 12px;
  border-radius: 12px;
  margin: 12px 0 16px 0;
  font-weight: 750;
}
.section-card {
  border: 1px solid rgba(15, 23, 42, 0.13);
  border-left-width: 7px;
  border-radius: 16px;
  padding: 14px;
  margin-bottom: 14px;
  background: #fff;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.05);
}
.section-card.gray { border-left-color: #94a3b8; background: #f5f6f8; }
.section-card.verse { border-left-color: #60a5fa; background: #eef6ff; }
.section-card.pre { border-left-color: #2dd4bf; background: #eafaf7; }
.section-card.chorus { border-left-color: #22c55e; background: #eefaf0; }
.section-card.bridge { border-left-color: #a78bfa; background: #f5f0ff; }
.section-card.solo { border-left-color: #fb923c; background: #fff4e6; }
.section-card.neutral { border-left-color: #cbd5e1; background: #ffffff; }
.section-card.current {
  outline: 3px solid rgba(34, 197, 94, 0.28);
  box-shadow: 0 0 0 5px rgba(34, 197, 94, 0.08);
}
.section-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: baseline;
  margin-bottom: 10px;
}
.section-title { font-size: 1.12rem; font-weight: 800; color: #0f172a; }
.section-meta { color: #475569; font-size: 0.88rem; }
.lead-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(92px, 1fr));
  gap: 8px;
  margin: 10px 0;
}
.chord-cell {
  min-height: 62px;
  border: 1.5px solid rgba(15, 23, 42, 0.28);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.9);
  padding: 6px 8px;
}
.chord-cell.current-chord {
  background: #dcfce7;
  border-color: #16a34a;
  box-shadow: 0 0 0 3px rgba(22, 163, 74, 0.18);
}
.bar-num { color: #64748b; font-size: 0.68rem; font-weight: 700; margin-bottom: 4px; }
.chord-symbol {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 1.28rem;
  font-weight: 850;
  letter-spacing: -0.02em;
  color: #111827;
}
.duration {
  display: inline-block;
  margin-top: 3px;
  color: #64748b;
  font-size: 0.70rem;
  font-weight: 700;
}
.lyric-box, .analysis-box, .overlay-box {
  border-radius: 10px;
  padding: 9px 10px;
  margin-top: 8px;
  background: rgba(255, 255, 255, 0.72);
  color: #1f2937;
}
.lyric-box { font-style: italic; }
.lyric-box.voice { font-style: normal; }
.phrase-note { margin-top: 6px; color: #475569; font-size: 0.86rem; }
.analysis-box { border-left: 3px solid rgba(15, 23, 42, 0.22); }
.overlay-box { border-left: 3px solid rgba(37, 99, 235, 0.35); }
.muted { color: #64748b; }
@media (max-width: 760px) { .lead-grid { grid-template-columns: repeat(2, minmax(110px, 1fr)); } }
</style>
"""

    key_text = f"Key: {html.escape(str(dk))}"
    if dk != song_data["key"]:
        key_text += f" (orig. {html.escape(str(song_data['key']))})"
    meta_bits = [
        key_text,
        f"Level: {html.escape(str(level))}",
        f"Form: {total_bars} bars",
        f"Tempo: {int(bpm)} BPM",
        f"Time: {html.escape(str(time_signature))}",
        f"Feel: {html.escape(_chart_feel_label(groove_style))}",
        "Drums/Bass/Comping: active",
        html.escape(status_text),
    ]
    meta = "".join(f"<span class='meta-pill'>{bit}</span>" for bit in meta_bits)
    header_note = (
        f"<div class='lead-subtitle'>{html.escape(str(ext['arrangement_notes']))}</div>"
        if ext.get("arrangement_notes")
        else ""
    )

    section_cards = []
    current_parts = {part.strip() for part in str(current_section or "").split(" + ") if part.strip()}
    for section_name, chords in sections.items():
        if not chords:
            continue
        role = _chart_section_role(section_name)
        is_current = section_name in current_parts
        now_label = "Now Playing" if is_current else ""
        current_bar_for_section = current_bar if is_current else None
        section_cards.append(
            f"""
<section class="section-card {role}{' current' if is_current else ''}">
  <div class="section-head">
    <div>
      <div class="section-title">{html.escape(section_name)} - {len(chords)} bars</div>
      <div class="section-meta">{html.escape(_chart_feel_label(groove_style))}</div>
    </div>
    <div class="section-meta">{now_label}</div>
  </div>
  {_chart_grid_html(chords, current_bar=current_bar_for_section)}
  {_section_lyric_html(section_name, chords, instrument, lyric_cues=lyric_cues or {}, section_lyrics=section_lyrics or {})}
  <div class="overlay-box"><strong>{html.escape(str(instrument))}:</strong> {_section_overlay(instrument, focus, chords, section_name=section_name, groove_style=groove_style)}</div>
  <div class="analysis-box">{_inline_harmonic_analysis(section_name, chords, dk)}</div>
</section>
"""
            )

    return f"""
{style}
<div class="lead-sheet">
  <div class="lead-header">
    <div class="lead-title">{html.escape(song_name)} - Musician Chart</div>
    <div class="lead-subtitle">{html.escape(str(song_data.get('artist', '')))} | {html.escape(str(song_data.get('genre', '')))}</div>
    {header_note}
    <div class="meta-row">{meta}</div>
  </div>
  <div class="now-playing">Now Playing: {html.escape(str(now_playing))}</div>
  {''.join(section_cards)}
</div>
"""

def vocal_practice_text(level, sections):
    longest = max((len(chords) for chords in sections.values()), default=4)
    return f"""
### Voice-Specific Practice
- **Breathing:** mark breaths before each section and before long phrases over {min(longest, 8)}-bar spans.
- **Phrase length:** speak the rhythm first, then sing on a single vowel before adding words.
- **Range awareness:** find the pitch center from the first and last chord of each section; avoid pushing the top notes.
- **Sustains:** practice held notes with steady air, then taper the release into the next bar.
- **Diction:** keep consonants short and vowels consistent through sustained notes.
- **Dynamics:** sing verses lighter, choruses fuller, and bridges with a clear emotional shift.
- **Section practice:** loop verse entries quietly; practice chorus entrances with stronger breath support.
"""


def guitar_practice_text(focus, level):
    focus = focus or ""
    if focus == "Rhythm":
        return f"""
### Guitar Rhythm Practice
- **Groove feel:** mute lightly with the fretting hand and lock the strum to the backing track.
- **Strumming:** start with downstrokes on quarter notes, then add eighth-note upstrokes.
- **Muting:** practice dead-strum bars between chord changes to keep time moving.
- **Transitions:** isolate the two hardest chord changes and loop each for 2 minutes.
- **Comping:** use smaller 3- or 4-note voicings for clean rhythmic consistency.
- **Level target:** {level} players should keep time steady before adding syncopation or extensions.
"""
    if focus == "Melody":
        return f"""
### Guitar Melody / Lead Practice
- **Phrasing:** sing the line first, then play it; leave space between ideas.
- **Slides and bends:** target chord tones on strong beats, especially 3rds and 7ths.
- **Vibrato:** hold sustained notes over stable chords and match vibrato speed to the groove.
- **Hammer-ons / pull-offs:** use them as articulation, not speed tricks.
- **Double stops:** outline thirds/sixths through the section changes.
- **Positioning:** map the melody around one fretboard position, then shift only for expressive reasons.
"""
    return f"""
### Guitar Practice
- Use playable voicings from the chart; avoid full six-string shapes when a smaller grip sounds cleaner.
- Mark common tones between chords and keep them ringing where possible.
- Practice one section with metronome, then with the backing track.
- For {level} level, prioritize clean time, clean tone, and intentional voicing choices.
"""


GUITAR_FINGERING_OPTIONS = {
    "Fm9": [
        ("lower", "131113", "Lower movable color; keep it light because full minor-9 grips can get dense."),
        ("shell", "1x1113", "Root plus minor shell and 9th color; good for comping."),
        ("upper", "xx3143", "Upper-register color voicing when bass or piano covers the root."),
    ],
    "Aadd9": [
        ("open", "x02420", "Open, ringing pop color; let the B string carry the add9."),
        ("triad", "x07600", "Small upper-register color shape; useful for ambient sections."),
        ("barre", "577600", "Moveable A-root color with open top strings if the key allows it."),
    ],
    "Bsus4": [
        ("open-ish", "x24400", "Modern ringing sus color; mute the low E."),
        ("barre", "x24452", "Clear Bsus4 barre grip resolving easily to B."),
        ("triad", "xx4452", "Upper-string sus shape for clean rhythm comping."),
    ],
    "D/F#": [
        ("open", "2x0232", "Classic D over F# bass; use thumb or first finger on low F#."),
        ("compact", "2x023x", "Smaller grip if the top string rings too brightly."),
        ("no-root-top", "xx4232", "Upper inversion when bass covers F#."),
    ],
    "Dadd9": [
        ("open", "xx0230", "Easy open D color; leave high E open for the 9th."),
        ("triad", "x54255", "Higher D color around 5th position."),
        ("barre", "x57755", "A-shape D with added 9 on top for a fuller chorus."),
    ],
    "G/B": [
        ("open", "x20033", "Open G over B; very useful for stepwise bass motion."),
        ("compact", "x2003x", "Smaller version for clean voice leading."),
        ("triad", "xx5433", "Upper G inversion if bass handles B."),
    ],
    "Gadd9": [
        ("open", "320203", "Country-pop open G color; keep top notes clean."),
        ("open-alt", "3x0203", "Lighter grip with less low-end mud."),
        ("triad", "xx5435", "Upper-string G color for tighter comping."),
    ],
    "Bbmaj7": [
        ("barre", "x13231", "Standard A-shape maj7 color."),
        ("shell", "6x776x", "Moveable shell voicing; good for jazz/pop comping."),
        ("upper", "xx7765", "Higher color voicing with the maj7 on top."),
    ],
    "Am7b5": [
        ("standard", "x0101x", "Compact half-diminished grip; resolve it clearly."),
        ("movable", "5x554x", "Moveable root-position shell."),
        ("upper", "xx7888", "Upper-register color for jazzier sections."),
    ],
    "Eadd9": [
        ("open", "024100", "Open E with F# color; good for the Love Story key-change lift."),
        ("barre", "x79977", "Higher E add9 color for a bigger final chorus."),
        ("triad", "xx4452", "Compact upper-voice color."),
    ],
    "C#m7": [
        ("barre", "x46454", "Standard minor-7 barre shape."),
        ("easy", "x42400", "Open-string color; works when a ringing pop texture is acceptable."),
        ("triad", "xx2424", "Compact top-string minor color."),
    ],
    "B/D#": [
        ("slash", "x64442", "B chord with D# in the bass; supports stepwise bass motion."),
        ("compact", "xx4442", "Use when the bassist covers the slash bass."),
    ],
    "A/C#": [
        ("slash", "x42220", "A chord with C# in the bass; smooth descent into Bm."),
        ("compact", "xx2220", "Upper-string version if bass handles C#."),
    ],
}


def _interesting_chord_names(chords):
    out = []
    for chord in chords:
        low = str(chord).lower()
        interesting = (
            "maj7" in low
            or "m7" in low
            or "add9" in low
            or "sus" in low
            or "dim" in low
            or "7b9" in low
            or "7#9" in low
            or "13" in low
            or "9" in low
            or "/" in str(chord)
        )
        if interesting and chord not in out:
            out.append(chord)
    return out


def chord_function_summary(chord):
    low = str(chord).lower()
    if "/" in str(chord):
        return "Slash chord: the chord color stays familiar while the bass note creates smoother voice leading."
    if "add9" in low:
        return "Add9 chord: a major or minor triad with the 9th added for open, modern color."
    if "maj7" in low:
        return "Major 7 chord: a soft tonic/subdominant color; it sounds settled but more emotional than a plain major triad."
    if "m7b5" in low or "dim" in low:
        return "Diminished/half-diminished color: passing tension that wants clear resolution."
    if "sus" in low:
        return "Suspended chord: the 3rd is delayed, creating tension before resolving."
    if "7b9" in low or "7#9" in low or "13" in low:
        return "Altered/extended dominant: strong tension that points toward the next chord."
    if "m7" in low:
        return "Minor 7 chord: warmer and more relaxed than a plain minor triad."
    if "9" in low or "11" in low:
        return "Extended chord: upper chord tones add color while the 3rd and 7th define the harmony."
    return "Chord-tone target: identify root, 3rd, and 5th first, then add color tones."


def chord_playing_advice(chord, instrument, level):
    family = _instrument_family(instrument)
    tones = _chord_tone_names(chord)
    if family == "guitar":
        options = GUITAR_FINGERING_OPTIONS.get(str(chord), [])
        if options:
            lines = [f"- **{label.title()}** `{shape}`: {desc}" for label, shape, desc in options]
        else:
            root, suffix = split_chord(_chord_head(chord))
            lines = [
                f"- **Easy version:** play a clean {root} triad first; add the color tone only after the change is steady.",
                f"- **Barre/moveable version:** use a root-position shape around the 5th or 7th fret and keep only 3-4 strings if the full grip is muddy.",
                f"- **Triad version:** reduce **{chord}** to three adjacent strings for rhythm parts.",
            ]
        return "\n".join(lines)
    if family == "piano":
        if level == "Advanced":
            return (
                f"- Left hand: root plus 7th or rootless shell.\n"
                f"- Right hand: 3rd/7th plus color tone; spread **{chord}** so the top note sings.\n"
                f"- Practice nearest inversion into the next chord, not block jumping."
            )
        return (
            f"- Left hand: root or root-fifth.\n"
            f"- Right hand: play the 3rd and 7th if present, then add one color tone.\n"
            f"- Keep the top note stable while moving to the next chord."
        )
    if family == "bass":
        return (
            f"- Outline **{chord}** with root, 5th, octave, then one approach note.\n"
            f"- Emphasize chord tones: {tones}.\n"
            f"- If it is a slash chord, honor the written bass note on beat 1."
        )
    if family == "winds":
        return (
            f"- Target chord tones: {tones}.\n"
            f"- Put the 3rd or 7th on a strong beat for harmonic clarity.\n"
            f"- Use scale motion only to connect into a chord tone."
        )
    if family == "voice":
        return (
            f"- Sing the root, 3rd, and 5th of **{chord}** on a neutral vowel.\n"
            f"- For harmony singing, try holding the 3rd or 7th while the melody moves.\n"
            f"- Listen for whether the chord feels resolved or suspended before shaping the phrase."
        )
    return f"- Learn the chord tones first: {tones}. Then connect them to the next chord in the section."


def chord_coach_markdown(chord, instrument, level):
    return f"""
**{chord}**

{chord_function_summary(chord)}

**How to play / target it on {instrument}:**
{chord_playing_advice(chord, instrument, level)}
""".strip()


def render_chord_coach_ui(chords, instrument, level, key_prefix, expanded=True):
    unique_chords = []
    for chord in chords:
        if chord not in unique_chords:
            unique_chords.append(chord)
    if not unique_chords:
        st.info("No chords are available for the current song/section.")
        return

    with st.expander("Chord Coach / How to Play This Chord", expanded=expanded):
        st.caption("Pick any chord from the selected song and get instrument-specific playing guidance.")
        selected_chord = st.selectbox(
            "Chord to explain",
            unique_chords,
            key=f"{key_prefix}::chord_coach_select",
        )
        st.markdown(chord_coach_markdown(selected_chord, instrument, level))


TRANSPOSING_INSTRUMENTS = {
    "Alto Sax (Eb)": 9,
    "Tenor Sax (Bb)": 2,
    "Soprano Sax (Bb)": 2,
    "Bari Sax (Eb)": 9,
    "Bb Trumpet": 2,
    "Bb Clarinet": 2,
}


def transposing_instrument_options(instrument):
    if instrument == "Saxophone":
        return ["Alto Sax (Eb)", "Tenor Sax (Bb)", "Soprano Sax (Bb)", "Bari Sax (Eb)"]
    if instrument == "Trumpet":
        return ["Bb Trumpet"]
    if instrument == "Clarinet":
        return ["Bb Clarinet"]
    return []


def transposed_key_for_instrument(concert_key, instrument_label):
    steps = TRANSPOSING_INSTRUMENTS.get(instrument_label, 0)
    return transpose_chord(concert_key, steps)


def render_transposition_helper(concert_key, instrument, key_prefix):
    options = transposing_instrument_options(instrument)
    if not options:
        return concert_key, False, None

    st.subheader("Instrument Transposition Helper")
    col_a, col_b, col_c = st.columns([1.2, 1.2, 1])
    with col_a:
        instrument_key = st.selectbox(
            "Transposing instrument",
            options,
            key=f"{key_prefix}::transposing_instrument",
        )
    written_key = transposed_key_for_instrument(concert_key, instrument_key)
    with col_b:
        st.write(f"Concert key: **{concert_key}**")
        st.write(f"Instrument key: **{written_key}**")
    with col_c:
        show_written = st.checkbox(
            "Show chart in instrument key",
            value=False,
            key=f"{key_prefix}::show_written_key",
        )
    st.caption(
        f"{instrument_key}: written notes transpose so the part reads in **{written_key}** when the concert chart is **{concert_key}**."
    )
    return written_key if show_written else concert_key, show_written, instrument_key


def capo_fret_for_shape(sounding_key, shape_key):
    return semitone_distance(shape_key, sounding_key)


def render_guitar_capo_helper(base_sections, sounding_key, key_prefix):
    st.subheader("Guitar Capo Helper")
    col_a, col_b, col_c = st.columns([1.2, 1.2, 1])
    with col_a:
        shape_key = st.selectbox(
            "Play using chord shapes in",
            COMMON_KEYS,
            index=COMMON_KEYS.index("G") if "G" in COMMON_KEYS else 0,
            key=f"{key_prefix}::capo_shape_key",
        )
    capo = capo_fret_for_shape(sounding_key, shape_key)
    shape_sections = transpose_sections_dict(base_sections, sounding_key, shape_key)
    shape_chords = chord_blocks_for_selected_sections(shape_sections)[:8]
    with col_b:
        st.write(f"Sounding key: **{sounding_key}**")
        st.write(f"Shape key: **{shape_key}**")
    with col_c:
        st.metric("Suggested capo", f"{capo} fret" if capo == 1 else f"{capo} frets")
    st.caption(
        "Capo suggestion assumes standard tuning: play the shape-key chords with the capo placed so they sound in the selected chart key."
    )
    if shape_chords:
        st.write("First playable shapes: `" + " | ".join(shape_chords) + "`")


def playback_follow_position(events, bpm, loops, start_time=None, manual_index=0):
    if not events:
        return None
    total_events = events * max(1, int(loops))
    if start_time:
        bar_seconds = (60 / max(1, bpm)) * 4
        idx = int((time.time() - start_time) // bar_seconds) % len(total_events)
    else:
        idx = int(manual_index) % len(total_events)
    event = total_events[idx]
    next_event = total_events[(idx + 1) % len(total_events)]
    return {
        "absolute_bar": idx + 1,
        "total_bars": len(total_events),
        "section": event.get("section", ""),
        "bar_in_section": int(event.get("bar_in_section", 0)) + 1,
        "section_bars": int(event.get("section_bars", 1)),
        "chord": event.get("chord", ""),
        "next_chord": next_event.get("chord", ""),
    }


def render_follow_along_controls(events, bpm, loops, key_prefix):
    st.subheader("Live Chord Follow-Along")
    st.caption("Practical follow-along: start the tracker when you press play, or step through bars manually.")
    start_key = f"{key_prefix}::follow_start_time"
    index_key = f"{key_prefix}::follow_manual_index"
    st.session_state.setdefault(index_key, 0)

    col_a, col_b, col_c, col_d = st.columns(4)
    with col_a:
        if st.button("Start follow-along", key=f"{key_prefix}::follow_start"):
            st.session_state[start_key] = time.time()
            st.session_state[index_key] = 0
    with col_b:
        if st.button("Refresh position", key=f"{key_prefix}::follow_refresh"):
            st.rerun()
    with col_c:
        if st.button("Next bar", key=f"{key_prefix}::follow_next"):
            st.session_state.pop(start_key, None)
            st.session_state[index_key] += 1
    with col_d:
        if st.button("Stop/reset", key=f"{key_prefix}::follow_stop"):
            st.session_state.pop(start_key, None)
            st.session_state[index_key] = 0

    pos = playback_follow_position(
        events,
        bpm,
        loops,
        start_time=st.session_state.get(start_key),
        manual_index=st.session_state.get(index_key, 0),
    )
    if not pos:
        st.info("Choose at least one section to use follow-along.")
        return None

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Now Playing Section", pos["section"])
    c2.metric("Current Chord", pos["chord"])
    c3.metric("Current Bar", f"{pos['bar_in_section']} of {pos['section_bars']}")
    c4.metric("Next Chord", pos["next_chord"])
    st.caption(f"Absolute bar {pos['absolute_bar']} of {pos['total_bars']}. Highlighted in the chart below.")
    return pos


def _section_for_exercise(sections, variation):
    items = [(name, chords) for name, chords in sections.items() if chords]
    if not items:
        return "Full form", []
    return items[variation % len(items)]


def _transition_pair(chords, variation):
    if len(chords) < 2:
        return (chords[0], chords[0]) if chords else ("the tonic", "the next chord")
    idx = variation % (len(chords) - 1)
    return chords[idx], chords[idx + 1]


def _chord_tone_names(chord):
    try:
        return " - ".join(midi_note_name(m) for m in chord_notes(chord)[:4])
    except Exception:
        return "root - 3rd - 5th"


def _technical_pattern_for_exercise(instrument, focus, first_chord, second_chord):
    tones = _chord_tone_names(first_chord)
    family = _instrument_family(instrument)
    if focus == "Harmony":
        return f"Play/sing arpeggios through **{first_chord} -> {second_chord}**: {tones}, then connect to the nearest chord tone in the next bar."
    if focus == "Improvisation":
        return f"Create a 4-note motif from **{first_chord}** chord tones ({tones}); sequence it into **{second_chord}** without changing rhythm."
    if focus == "Rhythm":
        return f"Use one pitch or muted strings/keys to drill the section rhythm first; then add **{first_chord} -> {second_chord}**."
    if focus == "Melody":
        return f"Play a chord-tone line using {tones}; add one approach note into the target note over **{second_chord}**."
    if family == "winds":
        return f"Long-tone ladder: sustain root, 3rd, 5th, 7th of **{first_chord}** with clean attacks."
    if family == "voice":
        return f"Sing chord tones of **{first_chord}** on 'mah', then repeat on the vowel from your lyric cue."
    if family == "guitar":
        return f"Alternate-pick the arpeggio of **{first_chord}**, then switch positions for **{second_chord}**."
    if family == "piano":
        return f"Play **{first_chord}** inversions up the keyboard, then resolve to the nearest inversion of **{second_chord}**."
    if family == "bass":
        return f"Play root-5th-octave-approach for **{first_chord}**, resolving into **{second_chord}** on beat 1."
    return f"Practice the arpeggio of **{first_chord}**, then resolve cleanly into **{second_chord}**."


def _instrument_family(instrument):
    if instrument in ["Saxophone", "Flute", "Trumpet"]:
        return "winds"
    if instrument == "Voice":
        return "voice"
    if instrument == "Guitar":
        return "guitar"
    if instrument == "Piano":
        return "piano"
    if instrument == "Bass":
        return "bass"
    return "general"


FOCUS_OPTIONS_BY_INSTRUMENT = {
    "Guitar": [
        "Strumming",
        "Rhythm Guitar",
        "Chord Transitions",
        "Barre Chords",
        "Fingerstyle",
        "Triads",
        "Double Stops",
        "Lead Guitar",
        "Soloing",
        "Ear Training",
    ],
    "Piano": [
        "Voicings",
        "Left-Hand Patterns",
        "Comping",
        "Voice Leading",
        "Inversions",
        "Reharmonization",
        "Ear Training",
    ],
    "Bass": [
        "Groove",
        "Pocket",
        "Root Motion",
        "Walking Bass",
        "Syncopation",
        "Ear Training",
    ],
    "Saxophone": [
        "Tone",
        "Scales",
        "Articulation",
        "Bebop Phrasing",
        "Breath Support",
        "Guide Tones",
        "Ear Training",
    ],
    "Flute": [
        "Tone",
        "Scales",
        "Articulation",
        "Breath Support",
        "Guide Tones",
        "Phrasing",
        "Ear Training",
    ],
    "Trumpet": [
        "Tone",
        "Endurance",
        "Articulation",
        "Range",
        "Jazz Phrasing",
        "Guide Tones",
        "Ear Training",
    ],
    "Voice": [
        "Breath Control",
        "Phrasing",
        "Pitch Accuracy",
        "Emotional Delivery",
        "Harmony Singing",
        "Vibrato",
        "Ear Training",
    ],
}


def focus_options_for_instrument(instrument):
    return FOCUS_OPTIONS_BY_INSTRUMENT.get(
        instrument,
        ["Melody", "Harmony", "Rhythm", "Improvisation", "Technique", "Ear Training"],
    )


def _focus_area(focus):
    text = str(focus or "").lower()
    if any(token in text for token in ["strum", "rhythm", "comp", "groove", "pocket", "syncopation", "left-hand", "left hand"]):
        return "Rhythm"
    if any(token in text for token in ["voicing", "voice leading", "inversion", "reharm", "harmony", "triad", "barre", "transition", "root motion"]):
        return "Harmony"
    if any(token in text for token in ["lead", "melody", "double stop", "phrasing", "articulation", "tone", "breath", "vibrato", "range", "endurance"]):
        return "Melody"
    if any(token in text for token in ["solo", "improv", "walking", "bebop", "scales", "guide tone"]):
        return "Improvisation"
    if "ear" in text or "pitch accuracy" in text:
        return "Ear Training"
    return "Technique"


def _difficulty_phrase(level, variation):
    if level == "Beginner":
        return [
            "slow and clean",
            "with a metronome on every beat",
            "two bars at a time",
        ][variation % 3]
    if level == "Intermediate":
        return [
            "with steady groove and connected phrasing",
            "using chord tones on strong beats",
            "then over the whole section without stopping",
        ][variation % 3]
    return [
        "with expressive timing and dynamic shape",
        "using guide tones, anticipations, and motivic development",
        "then displace the rhythm by one eighth-note while staying locked to the form",
    ][variation % 3]


def _practice_time_blocks(minutes):
    total = max(10, int(minutes or 30))
    warmup = max(2, int(round(total * 0.18)))
    section = max(3, int(round(total * 0.36)))
    focus_block = max(3, int(round(total * 0.30)))
    review = max(1, total - warmup - section - focus_block)
    return {
        "total": total,
        "warmup": warmup,
        "section": section,
        "focus": focus_block,
        "review": review,
    }


def _exercise_span(level, bars):
    bars = max(1, bars)
    if level == "Beginner":
        return min(4, bars)
    if level == "Intermediate":
        return min(8, bars)
    return bars


def _chord_run(chords, limit=4):
    if not chords:
        return "the first chord"
    return " | ".join(chords[:max(1, min(limit, len(chords)))])


def _guide_tone_pair(chord):
    try:
        tones = chord_notes(chord)
        if len(tones) >= 4:
            return midi_note_name(tones[1]), midi_note_name(tones[3])
        if len(tones) >= 2:
            return midi_note_name(tones[1]), midi_note_name(tones[-1])
    except Exception:
        pass
    return "3rd", "7th"


def _root_and_fifth(chord):
    try:
        root = bass_note(chord)
        return midi_note_name(root), midi_note_name(root + 7)
    except Exception:
        return "root", "5th"


def _section_character(section_name):
    role = _section_role(section_name)
    if role == "chorus":
        return "play this fuller than the verse, with stronger beat-2/4 energy"
    if role == "verse":
        return "keep this lighter and leave space for the melody"
    if role == "bridge":
        return "change color here so the form feels like it has moved somewhere new"
    if role == "intro":
        return "make the entrance steady and uncluttered"
    if role == "outro":
        return "let the final pass relax without losing time"
    return "make the section shape clear without overplaying"


def _instrument_drills(
    *,
    family,
    instrument,
    level,
    focus,
    section_name,
    section_chords,
    first_chord,
    second_chord,
    chord_tones,
    span,
    blocks,
    variation,
    lyric_line="",
):
    chord_path = _chord_run(section_chords, span)
    guide_a, guide_b = _guide_tone_pair(first_chord)
    next_guide_a, next_guide_b = _guide_tone_pair(second_chord)
    root_a, fifth_a = _root_and_fifth(first_chord)
    root_b, fifth_b = _root_and_fifth(second_chord)
    reps = 2 if blocks["total"] <= 20 else 3 if blocks["total"] <= 45 else 4
    advanced = level == "Advanced"
    beginner = level == "Beginner"
    focus_area = _focus_area(focus)

    if family == "guitar":
        lead_task = (
            f"Lead drill: over **{first_chord}**, slide into **{guide_a}** from one fret below, "
            f"answer over **{second_chord}** by targeting **{next_guide_a}**, then add either a half-step bend or a double-stop on the last two beats."
        )
        rhythm_task = (
            f"Strumming drill: loop **{chord_path}** for {reps} passes. Pass 1 uses downstrokes on beats 1-2-3-4; "
            f"pass 2 uses `D D U - U D U`; pass 3 mutes beats 2 and 4 before opening up the last bar."
        )
        harmony_task = (
            f"Voicing transition: play **{first_chord} -> {second_chord}** as two compact 3- or 4-string grips, then move the same change to a second neck position. "
            f"Keep any common tone ringing and shift only the fingers that must move."
        )
        technique_task = (
            f"Picking/fretboard drill: alternate-pick **{chord_tones}** through **{first_chord}**, shift position, then resolve to **{next_guide_a}** on beat 1 of **{second_chord}**."
        )
        if focus_area == "Rhythm":
            primary = rhythm_task
        elif focus_area == "Melody":
            primary = lead_task
        elif focus_area == "Harmony":
            primary = harmony_task
        elif focus_area == "Improvisation":
            primary = f"Solo cell: make a two-bar phrase from **{guide_a}**, **{guide_b}**, and one bend/slide; repeat it over **{second_chord}** with one rhythmic change."
        elif focus_area == "Ear Training":
            primary = f"Ear drill: sing the roots of **{chord_path}**, then find them on one string before playing the chords. Check each change by ear before looking down."
        else:
            primary = technique_task
        secondary = lead_task if focus_area == "Rhythm" else rhythm_task
        return [
            primary,
            secondary,
            harmony_task if focus_area != "Harmony" else technique_task,
        ]

    if family == "piano":
        shell = (
            f"Shell voicing drill: left hand plays roots **{root_a} -> {root_b}**; right hand plays guide tones "
            f"**{guide_a}/{guide_b} -> {next_guide_a}/{next_guide_b}** with the smallest possible motion."
        )
        inversion = (
            f"Inversion drill: play **{first_chord} -> {second_chord}** in three right-hand positions, choosing the inversion that keeps the top note moving by step."
        )
        comping = (
            f"Comping rhythm: through **{chord_path}**, play short right-hand stabs on `1-and`, `2-and`, and beat 4; "
            f"left hand answers with root or fifth on beat 1 only."
        )
        reharm = (
            f"Reharm exercise: on the final bar of the {span}-bar loop, add a passing dominant or diminished approach into **{second_chord}**, then compare it to the plain chart."
        )
        if focus_area == "Rhythm":
            primary = comping
        elif focus_area == "Harmony":
            primary = shell if beginner else f"{shell} Then try: {reharm}"
        elif focus_area == "Melody":
            primary = f"Top-note melody: keep the right-hand top note singing through **{chord_path}** while the inner notes voice-lead quietly."
        elif focus_area == "Improvisation":
            primary = f"One-hand improv: left hand plays shells through **{chord_path}**; right hand improvises using **{chord_tones}** plus one neighbor tone."
        elif focus_area == "Ear Training":
            primary = f"Ear drill: play **{first_chord}**, sing its top note, then move to **{second_chord}** and identify whether the top note moved up, down, or stayed common."
        else:
            primary = inversion
        return [primary, shell, comping if not advanced else reharm]

    if family == "winds":
        articulation = (
            f"Articulation drill: play **{chord_tones}** over **{first_chord}** twice - first slurred, then tongued `ta-da ta-da`; "
            f"resolve to **{next_guide_a}** on beat 1 of **{second_chord}**."
        )
        guide = (
            f"Guide-tone target: make a {span}-bar line through **{chord_path}** where beat 1 of each bar lands on a 3rd or 7th, starting with **{guide_a}** or **{guide_b}**."
        )
        breath = (
            f"Breath/phrase plan: take one silent breath before **{section_name}**, play two-bar phrases, and leave a full eighth-note of space before the next phrase."
        )
        scale = (
            f"Scale-to-chord drill: run the scale around **{first_chord}** for one bar, then restrict bar 2 to chord tones only and land on **{next_guide_b}**."
        )
        if focus_area == "Rhythm":
            primary = articulation
        elif focus_area in ["Harmony", "Improvisation"]:
            primary = guide
        elif focus_area == "Melody":
            primary = f"Phrase shaping: play a two-bar question ending softly on **{guide_b}**, then answer louder into **{next_guide_a}** over **{second_chord}**."
        elif focus_area == "Ear Training":
            primary = f"Ear drill: sing **{guide_a}** and **{guide_b}** before playing them, then resolve by ear into **{next_guide_a}** over **{second_chord}**."
        else:
            primary = scale
        return [primary, breath, articulation if focus_area != "Rhythm" else guide]

    if family == "bass":
        groove = (
            f"Pocket drill: play **{root_a}** on beat 1 and **{fifth_a}** on beat 3 for **{first_chord}**, "
            f"then **{root_b}** and **{fifth_b}** for **{second_chord}**. Keep every note the same length."
        )
        walking = (
            f"Walking line: one note per beat over **{first_chord} -> {second_chord}**: root, fifth, octave, chromatic approach into **{root_b}**."
        )
        approach = (
            f"Approach-note drill: on beat 4 before each chord change in **{chord_path}**, approach the next root from a half-step below, then land firmly on beat 1."
        )
        rhythm = (
            f"Rhythmic consistency: loop the first {span} bars with the backing track, alternating one pass of quarter notes and one pass of eighth-note roots."
        )
        if focus_area == "Rhythm":
            primary = rhythm
        elif focus_area == "Harmony":
            primary = f"Outline drill: play root, 3rd, 5th, approach tone for each bar of **{chord_path}** without adding fills."
        elif focus_area == "Improvisation":
            primary = walking
        elif focus_area == "Melody":
            primary = f"Connecting line: write a simple bass melody from **{root_a}** to **{root_b}** using no more than four notes per bar."
        elif focus_area == "Ear Training":
            primary = f"Ear drill: sing each root in **{chord_path}**, then play root-fifth-root on bass and name the interval before moving on."
        else:
            primary = approach
        return [primary, groove, walking if not beginner else approach]

    if family == "voice":
        cue = lyric_line or f"the first phrase of {section_name}"
        breathing = (
            f"Breathing drill: inhale silently for 2 counts before **{section_name}**, sing _{cue}_ on `oo`, then repeat on `ah` without changing jaw height."
        )
        delivery = (
            f"Lyric delivery: speak _{cue}_ in time over **{chord_path}**, mark the word that should peak emotionally, then sing it with a softer pickup and stronger release."
        )
        dynamics = (
            f"Dynamic shape: sing bars 1-{span} mezzo-piano, grow into the strongest chord, then taper the final note without dropping pitch."
        )
        vowels = (
            f"Vowel shaping: sustain the main vowel from _{cue}_ over **{first_chord}**, then move to **{second_chord}** while keeping the vowel stable."
        )
        if focus_area == "Rhythm":
            primary = f"Rhythm/phrasing drill: speak _{cue}_ on subdivisions, clap beats 2 and 4, then sing only the rhythm on one pitch."
        elif focus_area == "Melody":
            primary = dynamics
        elif focus_area == "Harmony":
            primary = f"Pitch-center drill: hum the root of **{first_chord}**, sing **{chord_tones}** on `mah`, then resolve into **{second_chord}**."
        elif focus_area == "Improvisation":
            primary = f"Vocal variation: sing _{cue}_ once as written, then improvise a two-note answer on `na` using chord tones from **{first_chord}**."
        elif focus_area == "Ear Training":
            primary = f"Ear drill: sing the root, 3rd, and 5th of **{first_chord}** on `loo`, then identify which note feels most stable against **{second_chord}**."
        else:
            primary = breathing
        return [primary, delivery, vowels if focus_area != "Technique" else dynamics]

    return [
        f"Loop **{chord_path}** for {reps} passes and make the change **{first_chord} -> {second_chord}** land cleanly on beat 1.",
        f"Name and play/sing the chord tones of **{first_chord}**: {chord_tones}.",
        f"Record one pass of **{section_name}** and listen only for time, tone, and the section ending.",
    ]


def daily_practice_breakdown_markdown(song, sections, instrument, level, focus, minutes, variation=0):
    section_name, section_chords = _section_for_exercise(sections, variation)
    first_chord, second_chord = _transition_pair(section_chords, variation)
    blocks = _practice_time_blocks(minutes)
    span = _exercise_span(level, len(section_chords))
    chord_path = _chord_run(section_chords, span)
    family = _instrument_family(instrument)

    instrument_focus = {
        "guitar": f"right-hand groove plus **{first_chord} -> {second_chord}** voicing movement",
        "piano": f"shells, inversions, and voice leading through **{first_chord} -> {second_chord}**",
        "winds": f"articulation and guide-tone targets through **{first_chord} -> {second_chord}**",
        "bass": f"pocket, root/fifth movement, and approach notes into **{second_chord}**",
        "voice": f"breath, vowel, lyric delivery, and dynamics for **{section_name}**",
    }.get(family, f"clean time and chord-tone control through **{first_chord} -> {second_chord}**")

    return f"""
- Warmup ({blocks['warmup']} min): prepare **{instrument}** for {instrument_focus}.
- Song section ({blocks['section']} min): loop **{section_name}** from **{song}** for {span} bars: **{chord_path}**.
- {focus} block ({blocks['focus']} min): drill the exact change **{first_chord} -> {second_chord}** until it lands cleanly in time.
- Review ({blocks['review']} min): record one pass of **{section_name}**, then write one timing fix and one tone/phrasing fix.
""".strip()


def song_practice_plan(song, sections, instrument, level, focus, variation, section_lyrics=None, minutes=30):
    section_name, section_chords = _section_for_exercise(sections, variation)
    first_chord, second_chord = _transition_pair(section_chords, variation)
    family = _instrument_family(instrument)
    difficulty = _difficulty_phrase(level, variation)
    bars = len(section_chords)
    cycle = max(1, variation + 1)
    chord_tones = _chord_tone_names(first_chord)
    blocks = _practice_time_blocks(minutes)
    span = _exercise_span(level, bars)
    chord_path = _chord_run(section_chords, span)
    section_text = (section_lyrics or {}).get(section_name, "")
    first_line = next(
        (line.strip() for line in str(section_text).splitlines() if line.strip()),
        "",
    )
    lyric_application = ""
    if section_text and instrument == "Voice":
        lyric_application = (
            f"\n**Lyric application**\n"
            f"- Start with this section text: _{first_line}_\n"
            f"- Speak it in rhythm over **{chord_path}**, mark one breath, then sing it on vowels before adding consonants.\n"
        )
    elif section_text:
        lyric_application = (
            f"\n**Form cue**\n"
            f"- Use this cue to locate the section while playing: _{first_line}_\n"
        )

    drills = _instrument_drills(
        family=family,
        instrument=instrument,
        level=level,
        focus=focus,
        section_name=section_name,
        section_chords=section_chords,
        first_chord=first_chord,
        second_chord=second_chord,
        chord_tones=chord_tones,
        span=span,
        blocks=blocks,
        variation=variation,
        lyric_line=first_line,
    )

    if level == "Beginner":
        development = f"Keep the loop to {span} bars. Slow down until the change **{first_chord} -> {second_chord}** is clean twice in a row."
    elif level == "Intermediate":
        development = f"Connect the drill to the backing track for {blocks['focus']} minutes, then record one full pass of **{section_name}**."
    else:
        development = f"After the clean pass, add one controlled variation: displacement, reharm, articulation change, fill, or dynamic contrast based on your instrument."

    return f"""
### Personalized Exercise {cycle}: {section_name}
**Song:** {song}  
**Target section:** {section_name} — {bars} bars  
**Today:** {blocks['total']} minutes on **{instrument}**, **{level}**, **{focus}**  
**Chord focus:** **{first_chord} -> {second_chord}**  
**Loop:** **{chord_path}**  
**Section character:** {_section_character(section_name)}

**Warm-up ({blocks['warmup']} min)**
- Play/sing the chord tones of **{first_chord}**: {chord_tones}. Then resolve into **{second_chord}** {difficulty}.

**Main drill ({blocks['section']} min)**
- {drills[0]}

**Instrument-specific coaching ({blocks['focus']} min)**
- {drills[1]}
- {drills[2]}

{lyric_application}

**Progression / check ({blocks['review']} min)**
- {development}
"""


def default_time_signature(song, sections):
    text = " ".join([song] + list(sections.keys())).lower()
    if "3/4" in text or "piano man" in text:
        return "3/4"
    if "6/8" in text:
        return "6/8"
    if "perfect" in text:
        return "6/8"
    return "4/4"


def practice_text(level, instrument=None, sections=None, focus=None):

    if level == "Beginner":
        base = """
### Beginner Focus
- Practice slowly.
- Learn one section at a time.
- Focus on clean rhythm.
- Say chord names aloud.
"""
        if instrument == "Voice":
            base += vocal_practice_text(level, sections or {})
        if instrument == "Guitar":
            base += guitar_practice_text(focus, level)
        return base

    if level == "Intermediate":
        base = """
### Intermediate Focus
- Connect sections together.
- Practice rhythm consistency.
- Add chord-tone improvisation.
- Record one full section.
"""
        if instrument == "Voice":
            base += vocal_practice_text(level, sections or {})
        if instrument == "Guitar":
            base += guitar_practice_text(focus, level)
        return base

    base = """
### Advanced Focus
- Use voice leading.
- Add substitutions and inversions.
- Improvise over the full form.
- Create variations for each section.
"""
    if instrument == "Voice":
        base += vocal_practice_text(level, sections or {})
    if instrument == "Guitar":
        base += guitar_practice_text(focus, level)
    return base

def load_logs():

    if DATA_FILE.exists():

        try:
            return json.loads(
                DATA_FILE.read_text(
                    encoding="utf-8"
                )
            )

        except Exception:
            return []

    return []

def save_logs(logs):

    DATA_FILE.write_text(
        json.dumps(logs, indent=2),
        encoding="utf-8"
    )

def infer_groove_style(song_data, selected_style="Auto"):
    if selected_style != "Auto":
        return selected_style

    def safe_text(x):
        if x is None:
            return ""
        if isinstance(x, (list, tuple)):
            return " ".join(str(i) for i in x)
        if isinstance(x, dict):
            return " ".join(str(v) for v in x.values())
        return str(x)

    song_data = song_data or {}
    genre_name = safe_text(song_data.get("genre", ""))
    artist = safe_text(song_data.get("artist", ""))
    composer = safe_text(song_data.get("composer", ""))
    titleish = " ".join([
        safe_text(genre_name),
        safe_text(artist),
        safe_text(composer),
        safe_text(song_data.get("title", "")),
    ]).lower()
    if "ballad" in titleish:
        return "Ballad"
    if "jobim" in titleish or "bossa" in titleish:
        return "Bossa nova"
    if genre_name == "Jazz":
        return "Jazz swing"
    if genre_name in ["Funk", "Soul"]:
        return "Funk groove"
    if genre_name == "Rock":
        return "Rock groove"
    return "Pop groove"


def _freq(midi_num):
    return 440 * (2 ** ((midi_num - 69) / 12))


def _add_tone(audio, sr, start_sec, dur_sec, midi_num, volume, wave_type="sine"):
    start = int(start_sec * sr)
    if start >= len(audio) or dur_sec <= 0:
        return
    n = max(1, int(dur_sec * sr))
    end = min(len(audio), start + n)
    n = end - start
    t = np.linspace(0, dur_sec, n, False)
    if wave_type == "bass":
        sig = np.sin(2 * np.pi * _freq(midi_num) * t)
        sig += 0.35 * np.sin(2 * np.pi * _freq(midi_num) * 2 * t)
    elif wave_type == "organ":
        sig = np.sin(2 * np.pi * _freq(midi_num) * t)
        sig += 0.25 * np.sin(2 * np.pi * _freq(midi_num + 12) * t)
    else:
        sig = np.sin(2 * np.pi * _freq(midi_num) * t)
    attack = max(1, int(0.01 * sr))
    release = max(1, int(min(0.08, dur_sec * 0.35) * sr))
    env = np.ones(n)
    env[:min(attack, n)] = np.linspace(0, 1, min(attack, n))
    env[-min(release, n):] *= np.linspace(1, 0.02, min(release, n))
    audio[start:end] += sig * env * volume


def _add_noise_hit(audio, sr, start_sec, dur_sec, volume, seed=0):
    start = int(start_sec * sr)
    if start >= len(audio):
        return
    n = max(1, int(dur_sec * sr))
    end = min(len(audio), start + n)
    n = end - start
    rng = np.random.default_rng(seed)
    sig = rng.normal(0, 1, n)
    env = np.linspace(1, 0.01, n)
    audio[start:end] += sig * env * volume


def _coerce_chord_events(chords_or_events):
    events = []
    for idx, item in enumerate(chords_or_events or []):
        if isinstance(item, dict):
            chord = item.get("chord", "")
            section = item.get("section", "Practice Loop")
            bar_in_section = int(item.get("bar_in_section", idx))
            section_bars = int(item.get("section_bars", len(chords_or_events) or 1))
        else:
            chord = item
            section = "Practice Loop"
            bar_in_section = idx
            section_bars = len(chords_or_events) or 1
        events.append({
            "chord": chord,
            "section": section,
            "bar_in_section": bar_in_section,
            "section_bars": max(1, section_bars),
        })
    return events


def _section_role(section_name):
    name = str(section_name or "").lower()
    if "chorus" in name and "pre" not in name:
        return "chorus"
    if "verse" in name or "main loop" in name:
        return "verse"
    if "pre" in name:
        return "pre"
    if "bridge" in name:
        return "bridge"
    if "intro" in name:
        return "intro"
    if "outro" in name or "ending" in name:
        return "outro"
    if "solo" in name:
        return "solo"
    return "neutral"


def _section_intensity(section_name, style):
    role = _section_role(section_name)
    base = {
        "intro": 0.68,
        "verse": 0.78,
        "pre": 0.95,
        "chorus": 1.18,
        "bridge": 1.02,
        "solo": 1.08,
        "outro": 0.82,
        "neutral": 0.92,
    }.get(role, 0.92)
    if style == "Ballad":
        base *= 0.78
    elif style in ["Rock groove", "Funk groove"] and role == "chorus":
        base *= 1.08
    return base


def _is_section_edge(event, next_event):
    return bool(next_event and next_event.get("section") != event.get("section"))


def _bass_motion_pitch(chord, next_chord, style, slot_index, slot_count):
    notes = chord_notes(chord)
    root = bass_note(chord) - 12
    chord_root = notes[0] - 24
    third = notes[1] - 24 if len(notes) > 1 else chord_root + 4
    fifth = notes[2] - 24 if len(notes) > 2 else chord_root + 7

    if next_chord and slot_index == slot_count - 1:
        target = bass_note(next_chord) - 12
        return target - 1 if target >= root else target + 1

    if style == "Jazz swing":
        line = [root, third, fifth, root + 12]
    elif style == "Bossa nova":
        line = [root, fifth, root, fifth]
    elif style == "Funk groove":
        line = [root, root + 12, fifth, root, third, fifth]
    elif style == "Rock groove":
        line = [root, root, fifth, root + 12]
    elif style == "Ballad":
        line = [root, fifth]
    else:
        line = [root, fifth, root + 12, fifth]
    return int(line[slot_index % len(line)])


def _voicing_for_comp(chord, level, style, beat_index=0):
    notes = chord_notes(chord)
    if level == "Advanced" and len(notes) > 4:
        voicing = [notes[0], notes[2], notes[3], notes[4]]
    elif level == "Beginner":
        voicing = notes[:3]
    else:
        voicing = notes[:4]

    if beat_index % 2 and len(voicing) >= 3:
        voicing = voicing[1:] + voicing[:1]
    octave = 12 if style != "Ballad" else 0
    return [n + octave for n in voicing]


def _groove_time(bar_start, beat, beat_len, style):
    if style == "Jazz swing" and beat % 1:
        return bar_start + (beat + 0.08) * beat_len
    if style == "Funk groove" and beat % 1:
        return bar_start + (beat - 0.02) * beat_len
    return bar_start + beat * beat_len


def _style_patterns(style):
    if style == "Jazz swing":
        return {
            "bass_beats": [0, 1, 2, 3],
            "comp_beats": [1.0, 2.65, 3.65],
            "hat_beats": [0, 1.65, 2, 3.65],
            "snare_beats": [1.0, 3.0],
            "kick_beats": [0, 2],
            "comp_dur": 0.45,
        }
    if style == "Bossa nova":
        return {
            "bass_beats": [0, 1.5, 2, 3.5],
            "comp_beats": [0.0, 1.5, 2.5, 3.5],
            "hat_beats": [0, 0.5, 1.5, 2, 2.5, 3.5],
            "snare_beats": [1.5, 3.5],
            "kick_beats": [0, 2],
            "comp_dur": 0.32,
        }
    if style == "Funk groove":
        return {
            "bass_beats": [0, 0.75, 1.5, 2, 2.75, 3.5],
            "comp_beats": [0.75, 1.75, 2.5, 3.25],
            "hat_beats": [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5],
            "snare_beats": [1.0, 3.0],
            "kick_beats": [0, 1.5, 2.75],
            "comp_dur": 0.22,
        }
    if style == "Rock groove":
        return {
            "bass_beats": [0, 1, 2, 3],
            "comp_beats": [0, 1, 2, 3],
            "hat_beats": [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5],
            "snare_beats": [1.0, 3.0],
            "kick_beats": [0, 2],
            "comp_dur": 0.50,
        }
    if style == "Ballad":
        return {
            "bass_beats": [0, 2],
            "comp_beats": [0, 2.5, 3.5],
            "hat_beats": [0, 1, 2, 3],
            "snare_beats": [3.0],
            "kick_beats": [0],
            "comp_dur": 0.90,
        }
    return {
        "bass_beats": [0, 2],
        "comp_beats": [0, 1.5, 2.5, 3.5],
        "hat_beats": [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5],
        "snare_beats": [1.0, 3.0],
        "kick_beats": [0, 2.5],
        "comp_dur": 0.38,
    }


def synthesize_chords_to_numpy(
    chords,
    bpm=100,
    loops=1,
    sr=44100,
    *,
    style="Pop groove",
    level="Intermediate",
):

    beat = 60 / bpm
    bar = beat * 4
    event_cycle = _coerce_chord_events(chords)
    chord_list = event_cycle * max(1, int(loops))
    audio = np.zeros(int(sr * bar * len(chord_list)) + sr)
    patterns = _style_patterns(style)

    for idx, event in enumerate(chord_list):

        chord = event["chord"]
        next_event = chord_list[idx + 1] if idx + 1 < len(chord_list) else None
        next_chord = next_event["chord"] if next_event else None
        bar_start = idx * bar
        section_name = event.get("section", "Practice Loop")
        intensity = _section_intensity(section_name, style)
        role = _section_role(section_name)
        section_edge = _is_section_edge(event, next_event)
        notes = chord_notes(chord)
        bass_hits = patterns["bass_beats"]

        for n, b in enumerate(bass_hits):
            bass_pitch = _bass_motion_pitch(chord, next_chord, style, n, len(bass_hits))
            bass_dur = beat * (0.72 if style in ["Ballad", "Jazz swing"] else 0.50)
            if style == "Funk groove":
                bass_dur = beat * 0.32
            _add_tone(
                audio,
                sr,
                _groove_time(bar_start, b, beat, style),
                bass_dur,
                bass_pitch,
                0.11 * intensity,
                "bass",
            )

        for comp_idx, b in enumerate(patterns["comp_beats"]):
            if role == "verse" and comp_idx % 3 == 2:
                continue
            dur = beat * patterns.get("comp_dur", 0.45)
            if role == "chorus":
                dur *= 1.15
            voicing = _voicing_for_comp(chord, level, style, comp_idx)
            for note in voicing:
                _add_tone(
                    audio,
                    sr,
                    _groove_time(bar_start, b, beat, style),
                    dur,
                    note,
                    0.022 * intensity,
                    "organ",
                )

        for b in patterns["hat_beats"]:
            hat_vol = 0.007 if style == "Ballad" else 0.011
            if role == "chorus":
                hat_vol *= 1.25
            _add_noise_hit(
                audio,
                sr,
                _groove_time(bar_start, b, beat, style),
                0.030,
                hat_vol * intensity,
                seed=idx * 31 + int(b * 100),
            )

        for b in patterns["snare_beats"]:
            _add_noise_hit(
                audio,
                sr,
                _groove_time(bar_start, b, beat, style),
                0.055,
                0.030 * intensity,
                seed=idx * 67 + int(b * 100),
            )

        for b in patterns["kick_beats"]:
            _add_tone(
                audio,
                sr,
                bar_start + b * beat,
                0.07,
                36,
                0.070 * intensity,
                "bass",
            )

        if section_edge:
            approach = _bass_motion_pitch(chord, next_chord, style, len(bass_hits) - 1, len(bass_hits))
            _add_tone(audio, sr, bar_start + 3.55 * beat, beat * 0.25, approach, 0.075 * intensity, "bass")
            _add_noise_hit(audio, sr, bar_start + 3.75 * beat, 0.050, 0.018 * intensity, seed=idx * 101)
            if next_event and _section_role(next_event.get("section")) == "chorus":
                _add_tone(audio, sr, bar_start + 3.88 * beat, 0.09, 48, 0.055, "bass")

    audio = np.tanh(audio)
    audio = audio / (np.max(np.abs(audio)) + 1e-9) * 0.86
    return audio, sr


def pcm16_wav_bytes_from_float(audio, sr=44100):

    out = io.BytesIO()

    with wave.open(out, "wb") as wf:

        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)

        wf.writeframes(
            (audio * 32767)
            .astype(np.int16)
            .tobytes()
        )

    out.seek(0)

    return out.getvalue()


def generate_backing_track(
    chords,
    bpm=100,
    loops=1,
    style="Pop groove",
    level="Intermediate",
):

    audio, sr = synthesize_chords_to_numpy(
        chords,
        bpm=bpm,
        loops=loops,
        style=style,
        level=level,
    )
    return pcm16_wav_bytes_from_float(audio, sr)


def backing_bytes_to_float(chords, bpm=100, style="Pop groove", level="Intermediate"):

    y, _sr = synthesize_chords_to_numpy(
        chords,
        bpm=bpm,
        loops=1,
        style=style,
        level=level,
    )
    return y


def wav_bytes_from_float(audio, sr=44100):

    return pcm16_wav_bytes_from_float(audio, sr)


def make_count_in_click(*, bpm, beats, sr=44100):

    beat_dur = 60 / bpm
    total = int(np.ceil(sr * beat_dur * beats))
    y = np.zeros(total)

    def tick(t0, vol=0.35):

        dur = min(0.06, beat_dur * 0.25)
        t = np.linspace(0, dur, int(sr * dur), False)
        sig = np.sin(2 * np.pi * 880 * t) * vol
        env = np.linspace(1, 0.01, len(sig))
        sig = sig * env
        s0 = int(t0 * sr)
        e = min(total, s0 + len(sig))
        y[s0:e] += sig[: e - s0]

    for b in range(beats):
        tick(b * beat_dur)

    return y


def _load_audio_mono_bytes(audio_bytes, filename, sr):

    suffix = "." + filename.split(".")[-1].lower() if "." in filename else ".wav"

    if librosa is None:

        try:

            buf = io.BytesIO(audio_bytes)

            with wave.open(buf, "rb") as wf:

                n = wf.getnframes()
                ch = wf.getnchannels()
                raw = wf.readframes(n)
                sw = wf.getsampwidth()
                rate = wf.getframerate()

            if sw != 2:
                raise ValueError("Only 16-bit WAV supported without librosa.")

            x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32767.0

            if ch == 2:
                x = x.reshape(-1, 2).mean(axis=1)

            if rate != sr and rate > 0:

                x = np.interp(
                    np.linspace(0, len(x) - 1, int(len(x) * sr / rate)),
                    np.arange(len(x)),
                    x,
                )

            return x

        except Exception as exc:

            raise RuntimeError(
                "Loading this format needs librosa. Install librosa and soundfile, "
                f"or use WAV. ({exc})"
            ) from exc

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:

        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:

        y, _ = librosa.load(tmp_path, sr=sr, mono=True)

        return y

    finally:

        Path(tmp_path).unlink(missing_ok=True)


def mix_multitrack(backing_y, track_items, sr=44100):

    segs = []

    max_len = 0

    if backing_y is not None:

        max_len = len(backing_y)

    for item in track_items:

        y = _load_audio_mono_bytes(
            item["audio_bytes"],
            item["filename"],
            sr,
        )

        y = y * float(item["volume"])

        delay = float(item["delay"])

        ds = int(delay * sr)

        if ds > 0:

            y = np.concatenate([np.zeros(ds, dtype=y.dtype), y])

        elif ds < 0:

            y = y[-ds:]

        segs.append(y)

        max_len = max(max_len, len(y))

    mix = np.zeros(max_len, dtype=np.float64)

    if backing_y is not None:

        mix[: len(backing_y)] += backing_y.astype(np.float64)

    for y in segs:

        mix[: len(y)] += y.astype(np.float64)

    peak = np.max(np.abs(mix)) + 1e-9

    mix = (mix / peak * 0.95).astype(np.float32)

    return mix


# -------------------------------------------------
# INTERMEDIATE RECORDING ANALYSIS
# -------------------------------------------------

def analyze_recording_basic(audio_bytes, filename, target_chords, instrument, level):
    if librosa is None:
        return {"ok": False, "message": "Recording analysis requires librosa. Add librosa and soundfile to requirements.txt."}

    suffix = "." + filename.split(".")[-1].lower() if "." in filename else ".wav"

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        y, sr = librosa.load(tmp_path, sr=None, mono=True)
        duration = librosa.get_duration(y=y, sr=sr)

        try:
            tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
            tempo = float(np.asarray(tempo).flatten()[0])
            beat_count = int(len(beats))
        except Exception:
            tempo = None
            beat_count = 0

        pitch_summary = "Pitch tracking was not clear enough."
        pitch_stability = "Unknown"

        try:
            f0, voiced_flag, voiced_prob = librosa.pyin(
                y,
                fmin=librosa.note_to_hz("C2"),
                fmax=librosa.note_to_hz("C7")
            )
            voiced = f0[~np.isnan(f0)]
            if len(voiced) > 10:
                median_hz = float(np.median(voiced))
                pitch_note = librosa.hz_to_note(median_hz)
                cents_spread = float(np.std(1200 * np.log2(voiced / median_hz)))
                if cents_spread < 25:
                    pitch_stability = "fairly stable"
                elif cents_spread < 55:
                    pitch_stability = "moderately stable"
                else:
                    pitch_stability = "unstable / drifting"
                pitch_summary = f"Estimated center pitch: {pitch_note}. Pitch stability: {pitch_stability}."
        except Exception:
            pass

        rms = librosa.feature.rms(y=y)[0]
        dyn_range = float(np.percentile(rms, 90) - np.percentile(rms, 10))
        if dyn_range < 0.01:
            dynamics_comment = "Your dynamics look fairly flat. Try adding more shape and phrase direction."
        elif dyn_range < 0.04:
            dynamics_comment = "Your dynamics have some shape. Try making phrase peaks and endings more intentional."
        else:
            dynamics_comment = "Your dynamics show noticeable contrast. Focus on controlling it musically."

        try:
            onsets = librosa.onset.onset_detect(y=y, sr=sr)
            onset_rate = len(onsets) / max(duration, 1)
        except Exception:
            onset_rate = 0

        if onset_rate < 0.5:
            articulation_comment = "Few note attacks detected. This may mean long sustained notes, soft articulation, or unclear attacks."
        elif onset_rate < 2.5:
            articulation_comment = "Moderate note activity detected. Good for slow melody or chord work."
        else:
            articulation_comment = "Many note attacks detected. Focus on rhythmic cleanliness and not rushing."

        chord_tone_lines = []
        for ch in target_chords[:8]:
            try:
                note_names = [midi_note_name(m) for m in chord_notes(ch)[:4]]
                chord_tone_lines.append(f"- {ch}: " + " – ".join(note_names))
            except Exception:
                chord_tone_lines.append(f"- {ch}: root – 3rd – 5th")

        if level == "Beginner":
            next_steps = [
                "Play shorter sections.",
                "Focus on steady rhythm before speed.",
                "Match the first note/pitch center clearly.",
                "Record one clean 20–30 second take."
            ]
        elif level == "Intermediate":
            next_steps = [
                "Loop the weakest section with the backing track.",
                "Practice chord tones over the first 4 chords.",
                "Listen for rushing or dragging against the pulse.",
                "Record two takes and compare the second to the first."
            ]
        else:
            next_steps = [
                "Practice guide-tone lines through the form.",
                "Use rhythmic motifs, not random notes.",
                "Add intentional dynamics to each phrase.",
                "Record a full take and evaluate phrasing, time, and harmonic clarity."
            ]

        return {
            "ok": True,
            "duration": duration,
            "tempo": tempo,
            "beat_count": beat_count,
            "pitch_summary": pitch_summary,
            "dynamics_comment": dynamics_comment,
            "articulation_comment": articulation_comment,
            "chord_tones": "\n".join(chord_tone_lines),
            "next_steps": next_steps,
            "instrument": instrument,
            "level": level
        }

    except Exception as e:
        return {"ok": False, "message": f"Could not analyze recording: {e}"}


def render_recording_analysis_report(result, song, focus):
    if not result.get("ok"):
        st.error(result.get("message", "Analysis failed."))
        return

    st.subheader("Recording Analysis Report")
    st.write(f"**Song:** {song}")
    st.write(f"**Instrument:** {result.get('instrument')}")
    st.write(f"**Level:** {result.get('level')}")
    st.write(f"**Focus:** {focus}")
    st.write(f"**Recording length:** {result['duration']:.1f} seconds")

    if result.get("tempo"):
        st.write(f"**Estimated tempo:** {result['tempo']:.1f} BPM")
        st.write(f"**Detected beat count:** {result['beat_count']}")

    st.markdown("### Pitch / Intonation")
    st.write(result["pitch_summary"])

    st.markdown("### Rhythm / Articulation")
    st.write(result["articulation_comment"])

    st.markdown("### Dynamics")
    st.write(result["dynamics_comment"])

    st.markdown("### Chord Tones to Practice for This Song")
    st.markdown(result["chord_tones"])

    st.markdown("### Next Practice Steps")
    for step in result["next_steps"]:
        st.write(f"- {step}")


# -------------------------------------------------
# ACTIVE SONG FROM PICKER
# -------------------------------------------------

from creative_lab_text import (
    current_song_context_lab as lab_make_ctx,
    chord_quality as lab_chord_quality,
    deep_harmonic_analysis_text as lab_deep_harmonic,
    creativity_arrangement_text,
    improvisation_intelligence_text,
    adaptive_weakness_detection_text,
    musical_development_tracker_text as lab_musical_dev,
)


def current_song_context_lab():
    return lab_make_ctx(
        genre=genre,
        song=song,
        song_data=song_data,
        display_key=display_key,
        sections=sections,
        instrument=instrument,
        level=level,
        focus=focus,
    )


def chord_quality(ch):
    return lab_chord_quality(ch)


def deep_harmonic_analysis_text(ctx):
    return lab_deep_harmonic(ctx, all_chords_from_sections, lab_chord_quality)


def musical_development_tracker_text():
    return lab_musical_dev(load_logs)


# -------------------------------------------------
# APP UI
# -------------------------------------------------

st.title(
    "🎵 Daniel Cohen AI MUSIC PRACTICE COACH"
)

st.caption(
    "Genre-based practice plans, full-song chords, backing tracks, multitrack recording, and practice logs."
)

# -------------------------------------------------
# OPTIONAL OPENAI API KEY
# -------------------------------------------------

st.sidebar.divider()
st.sidebar.subheader("OpenAI API")

user_api_key = st.sidebar.text_input(
    "Enter OpenAI API Key",
    type="password",
    help="Optional. Needed only for AI-powered suggestion features.",
    key="openai_api_key_box"
)

if user_api_key:
    st.sidebar.success("API key loaded.")
else:
    st.sidebar.caption(
        "No API key loaded. Local app features still work."
    )


# SIDEBAR

st.sidebar.header("Setup")

st.sidebar.markdown(
    f"**Active song:** {song} — {song_data['artist']}  \n"
    f"**Style bin:** {genre}"
)

_chart_status_text, _chart_status_kind = chart_status_label(song_data)
if _chart_status_kind == "success":
    st.sidebar.success(_chart_status_text)
elif _chart_status_kind == "warning":
    st.sidebar.warning(_chart_status_text)
else:
    st.sidebar.info(_chart_status_text)

st.sidebar.caption(
    "Select or change the piece under **Song Picker**. "
    "That choice is the one source of truth for every tab."
)

_display_key_song_identity = (song_data.get("title"), song_data.get("artist"), song_data.get("key"))
if st.session_state.get("_display_key_song_identity") != _display_key_song_identity:
    st.session_state.display_key = song_data["key"]
    st.session_state["_display_key_song_identity"] = _display_key_song_identity

if "display_key" not in st.session_state:

    st.session_state.display_key = song_data["key"]

if st.session_state.display_key not in COMMON_KEYS:

    st.session_state.display_key = (
        song_data["key"]
        if song_data["key"] in COMMON_KEYS
        else COMMON_KEYS[0]
    )

display_key = st.sidebar.selectbox(
    "Transpose / Display Key",
    COMMON_KEYS,
    key="display_key",
)

instrument = st.sidebar.selectbox(
    "Instrument",
    [
        "Piano",
        "Guitar",
        "Bass",
        "Saxophone",
        "Flute",
        "Trumpet",
        "Clarinet",
        "Voice",
        "Other"
    ]
)

level = st.sidebar.selectbox(
    "Level",
    [
        "Beginner",
        "Intermediate",
        "Advanced"
    ]
)

_focus_options = focus_options_for_instrument(instrument)
if st.session_state.get("focus") not in _focus_options:
    st.session_state["focus"] = _focus_options[0]

focus = st.sidebar.selectbox(
    "Focus",
    _focus_options,
    key="focus",
)

minutes = st.sidebar.slider(
    "Practice Minutes",
    10,
    120,
    30,
    5
)

level_source_sections = sections_for_level(song_data, level)
level_song_data = {
    **song_data,
    "sections": level_source_sections,
}

sections = transpose_sections(
    level_song_data,
    display_key
)

full_song_chords = chord_blocks_for_backing(sections)
default_groove_style = infer_groove_style(song_data, "Auto")

song_lyrics_slug = _song_slug(song, song_data.get("artist", ""))
song_lyrics_key = f"song_lyrics::{song_lyrics_slug}"
section_lyrics_state_key = f"section_lyrics::{song_lyrics_slug}"

with st.sidebar.expander("Lyrics / lyric cues for selected song", expanded=(instrument == "Voice")):
    st.caption(
        "Paste only lyrics or cues you provide. The app does not fetch or generate copyrighted lyrics."
    )
    full_song_lyrics = st.text_area(
        "Paste lyrics for this song",
        value=st.session_state.get(song_lyrics_key, ""),
        placeholder=(
            "Paste user-provided lyrics or short cues here.\n"
            "Optional format:\n"
            "Verse: lyric/cue line\n"
            "Chorus: hook cue\n"
            "Bridge: delivery cue"
        ),
        key=song_lyrics_key,
        height=150,
    )

    suggested_section_lyrics = split_lyrics_by_sections(
        full_song_lyrics,
        list(sections.keys()),
    )
    section_lyrics_state = st.session_state.setdefault(section_lyrics_state_key, {})

    if st.button("Auto-assign lyrics to sections", key=f"auto_assign_lyrics::{song_lyrics_slug}"):
        st.session_state[section_lyrics_state_key] = dict(suggested_section_lyrics)
        st.rerun()

    st.caption("Adjust section lyric boxes below if automatic assignment is uncertain.")
    for section_name in sections.keys():
        default_text = section_lyrics_state.get(
            section_name,
            suggested_section_lyrics.get(section_name, ""),
        )
        section_lyrics_state[section_name] = st.text_area(
            f"{section_name} lyrics / cues",
            value=default_text,
            key=f"section_lyrics::{song_lyrics_slug}::{_song_slug(section_name)}",
            height=90,
        )

section_lyrics = st.session_state.get(section_lyrics_state_key, {})
catalog_lyric_cues = song_data.get("lyric_cues") or {}
lyric_cues = {
    **catalog_lyric_cues,
    **lyric_cues_from_section_lyrics(section_lyrics),
}

# TABS

tabs = st.tabs([
    "Practice",
    "Song Picker",
    "Backing Track",
    "Creative Lab",
    "Multitrack Recorder",
    "Upload / Recording Analysis",
    "Practice Log"
])

# -------------------------------------------------
# PRACTICE
# -------------------------------------------------

with tabs[0]:

    st.header("Practice")

    st.caption("For deeper analysis, use the Creative Lab tab: harmony, improvisation, arranging, weakness detection, and musical development tracking.")

    st.write(
        f"""
Genre: **{genre}**  
Song: **{song}**  
Instrument: **{instrument}**  
Level: **{level}**  
Focus: **{focus}**
"""
    )

    exercise_key = (
        f"exercise_variation::{song}::{instrument}::{level}::{focus}"
    )
    if exercise_key not in st.session_state:
        st.session_state[exercise_key] = 0

    st.subheader("Personalized Coach Exercise")

    st.markdown(
        song_practice_plan(
            song,
            sections,
            instrument,
            level,
            focus,
            st.session_state[exercise_key],
            section_lyrics=section_lyrics,
            minutes=minutes,
        )
    )

    col_ex_a, col_ex_b = st.columns([1, 2])

    with col_ex_a:
        if st.button("Generate New Exercise"):
            st.session_state[exercise_key] += 1
            st.rerun()

    with col_ex_b:
        st.caption(
            "Each new exercise rotates section targets and raises the musical demand gradually."
        )

    if level in ["Intermediate", "Advanced"]:
        render_chord_coach_ui(
            all_chords_from_sections(sections),
            instrument,
            level,
            key_prefix=f"practice::{song}::{instrument}::{level}",
            expanded=True,
        )

    st.subheader("Metronome")
    render_metronome_widget(
        default_bpm=100,
        default_signature=default_time_signature(song, sections),
    )

    st.markdown(
        lyric_guide_markdown(
            sections,
            lyric_cues,
            instrument,
            section_lyrics=section_lyrics,
        )
    )

    if st.button(
        "Generate Practice Sheet"
    ):

        st.markdown(
            practice_text(
                level,
                instrument=instrument,
                sections=sections,
                focus=focus,
            )
        )

        st.subheader(
            "Practice Notation"
        )

        abc = build_abc(
            song,
            sections
        )

        render_abc(abc)

    st.subheader(
        "Suggested Daily Time Breakdown"
    )

    st.markdown(
        daily_practice_breakdown_markdown(
            song,
            sections,
            instrument,
            level,
            focus,
            minutes,
            variation=st.session_state[exercise_key],
        )
    )

# -------------------------------------------------
# SONG PICKER
# -------------------------------------------------

with tabs[1]:

    st.header("Song Picker")

    chart_library_mode = st.radio(
        "Chart library",
        ["Trusted core charts only", "Include practice approximations"],
        horizontal=True,
        key="chart_library_mode",
    )

    visible_song_records = visible_records_for_mode(
        ALL_SONG_RECORDS,
        chart_library_mode,
    )

    status_filter = st.selectbox(
        "Chart status",
        [
            "Any non-placeholder",
            "Trusted core",
            "Verified",
            "Practice approximation",
        ],
        index=1 if chart_library_mode == "Trusted core charts only" else 0,
        key="song_picker_chart_status",
    )

    level_filter = st.selectbox(
        "Chart level available",
        [
            "Any level",
            "Beginner",
            "Intermediate",
            "Advanced",
        ],
        index=0,
        key="song_picker_level_filter",
    )

    visible_song_records = filter_records_by_chart_status(
        visible_song_records,
        status_filter,
    )
    visible_song_records = filter_records_by_level(
        visible_song_records,
        level_filter,
    )

    visible_genres = [
        g for g in GENRES
        if any(r.get("genre") == g for r in visible_song_records)
    ]

    st.caption(
        f"**{len(visible_song_records)} songs** visible in this chart library mode. "
        "Trusted core is the default; practice approximations are opt-in. "
        "Placeholder charts remain hidden. "
        "This tab is for browsing and selecting only; charts live in Backing Track and Practice."
    )

    search_scope = st.radio(
        "Search scope",
        ["Entire library", "Single genre"],
        horizontal=True,
        key="song_search_scope",
    )

    filter_genre = None
    if search_scope == "Single genre":
        if visible_genres:
            filter_genre = st.selectbox(
                "Genre filter",
                visible_genres,
                index=visible_genres.index(genre) if genre in visible_genres else 0,
                key="picker_genre",
            )
        else:
            st.warning("No genres match the current chart filters.")

    search_text = st.text_input(
        "Search (autocomplete-style)",
        placeholder="Search title, artist, composer, genre/style...",
        key="song_search_text",
    )

    filtered = search_records(
        visible_song_records,
        search_text,
        genre=filter_genre,
        limit=150,
    )

    if not filtered:
        st.info("No matches — clear the box or try a shorter fragment to see more songs.")
        filtered = visible_song_records[:80]

    master_sel = st.session_state.get("selected_song") or {}
    master_pk = master_sel.get("pick_key")
    master_rec = record_for_pick_key(visible_song_records, master_pk) if master_pk else None
    if master_rec:
        row_keys = {
            format_pick_key(r["genre"], f"{r['title']} — {r['artist']}")
            for r in filtered
        }
        mk = format_pick_key(
            master_rec["genre"],
            f"{master_rec['title']} — {master_rec['artist']}",
        )
        if mk not in row_keys:
            filtered = [master_rec] + filtered

    pick_options = [
        format_pick_key(r["genre"], f"{r['title']} — {r['artist']}")
        for r in filtered
    ]

    def _fmt_pick(opt: str) -> str:
        g, lab = parse_pick_key(opt)
        return f"{lab}  [{g}]"

    if not pick_options:

        st.warning("No songs match this filter. Widen your search.")

        pick_key = master_pk

    else:

        if st.session_state.get("matching_song_dropdown") not in pick_options:

            st.session_state.matching_song_dropdown = (
                master_pk if master_pk in pick_options else pick_options[0]
            )

        def _on_song_dropdown_change():

            apply_pick_key(
                st,
                st.session_state["matching_song_dropdown"],
                SONG_PICKER_CATALOG,
            )

            try:

                st.toast("Song selected. Go to Backing Track, Practice, or Multitrack Recorder.", icon="🎵")

            except Exception:

                pass

        st.selectbox(
            "Matching songs (pick one — this becomes the app-wide active song)",
            pick_options,
            format_func=_fmt_pick,
            key="matching_song_dropdown",
            on_change=_on_song_dropdown_change,
        )

        pick_key = st.session_state["matching_song_dropdown"]

    pick_genre, pick_label = parse_pick_key(pick_key)
    selected_data = SONG_PICKER_CATALOG[pick_genre][pick_label]

    selected_status, _selected_status_kind = chart_status_label(selected_data)
    selected_versions = selected_data.get("chart_versions") or {}
    available_levels = ", ".join(selected_versions.keys()) if selected_versions else "Generated from practice chart"

    st.success(
        f"Song selected: **{selected_data['title']}** — {selected_data['artist']}."
    )

    st.write(
        f"**Chart status:** {selected_status}  \n"
        f"**Genre/style:** {selected_data.get('genre', 'Unknown')}  \n"
        f"**Original key:** {selected_data.get('key', 'Unknown')}  \n"
        f"**Available chart levels:** {available_levels}"
    )

    st.info(
        "Go to **Backing Track** for the full chart and playback. "
        "Go to **Practice** for exercises. "
        "Go to **Multitrack Recorder** to record."
    )

# -------------------------------------------------
# BACKING TRACK
# -------------------------------------------------

with tabs[2]:

    st.header("Backing Track")

    st.write(
        f"Uses the **active song** (same as Song Picker / sidebar): **{song}** — {song_data['artist']}. "
        f"Chords are in **{display_key}** (transpose from the sidebar if needed)."
    )

    st.subheader("1. Backing Track Settings")

    _sec_names = [name for name, chs in section_order(sections) if chs]

    playback_scope = st.radio(
        "Playback range",
        [
            "Full song",
            "Single section",
            "Multiple selected sections",
        ],
        horizontal=True,
        key="backing_track_scope",
    )

    selected_section_names = []

    if playback_scope == "Single section" and _sec_names:
        one_section = st.selectbox(
            "Section to loop",
            _sec_names,
            key="backing_track_single_section",
        )
        selected_section_names = [one_section]

    elif playback_scope == "Multiple selected sections" and _sec_names:
        default_sections = [
            name for name in _sec_names
            if any(token in name.lower() for token in ["verse", "chorus"])
        ] or _sec_names[:2]
        selected_section_names = st.multiselect(
            "Sections to play (keeps original song order)",
            _sec_names,
            default=default_sections,
            key="backing_track_multi_sections",
        )

    selected_section_names = selected_section_names or []
    backing_chords = chord_blocks_for_selected_sections(
        sections,
        selected_section_names,
    )
    backing_events = chord_events_for_selected_sections(
        sections,
        selected_section_names,
    )

    col_bt_1, col_bt_2 = st.columns(2)

    with col_bt_1:
        groove_style = st.selectbox(
            "Groove / accompaniment style",
            [
                "Auto",
                "Pop groove",
                "Rock groove",
                "Jazz swing",
                "Bossa nova",
                "Funk groove",
                "Ballad",
            ],
            key="backing_groove_style",
        )

        bpm = st.slider(
            "Tempo (BPM)",
            50,
            180,
            100,
            5,
            key="backing_track_bpm",
        )

    with col_bt_2:
        form_loops = st.slider(
            "Number of repeats",
            1,
            10,
            2,
            1,
            key="backing_track_loops",
        )

        st.write(f"Display key: **{display_key}**")
        st.write(f"Chart level: **{level}**")

    resolved_groove = infer_groove_style(song_data, groove_style)
    section_scope_label = (
        "full form"
        if not selected_section_names
        else " + ".join(selected_section_names)
    )

    if not backing_chords:
        st.warning("Choose at least one section to generate a backing track.")

    st.caption(
        f"Playback target: **{section_scope_label}** | "
        f"Groove: **{resolved_groove}** | "
        f"{len(backing_chords)} bars per repeat, {len(backing_chords) * form_loops} total bars."
    )

    st.caption(
        f"Chart version used for audio: **{level}** — "
        f"**{chart_status_label(song_data)[0]}**"
    )

    if instrument == "Voice":
        st.caption("Voice lyric and phrasing cues are shown inside each chart section below.")

    chart_display_key = display_key
    transposition_label = None
    if transposing_instrument_options(instrument):
        chart_display_key, _show_written_key, transposition_label = render_transposition_helper(
            display_key,
            instrument,
            key_prefix=f"backing::{song}",
        )

    chart_level_song_data = {
        **song_data,
        "sections": level_source_sections,
    }
    chart_sections = transpose_sections(
        chart_level_song_data,
        chart_display_key,
    )
    chart_backing_chords = chord_blocks_for_selected_sections(
        chart_sections,
        selected_section_names,
    )
    chart_backing_events = chord_events_for_selected_sections(
        chart_sections,
        selected_section_names,
    )

    if instrument == "Guitar":
        render_guitar_capo_helper(
            sections,
            display_key,
            key_prefix=f"backing::{song}",
        )

    st.subheader("Chord Coach / How to Play This Chord")
    render_chord_coach_ui(
        chart_backing_chords or all_chords_from_sections(chart_sections),
        instrument,
        level,
        key_prefix=f"backing::{song}::{instrument}::{level}",
        expanded=True,
    )

    coach_section = selected_section_names[0] if selected_section_names else next((name for name, chs in section_order(chart_sections) if chs), "")
    coach_chords = chart_sections.get(coach_section, []) if coach_section else []
    if coach_chords:
        st.info(
            f"Instrument coaching for **{instrument} / {focus}**: "
            + _section_overlay(
                instrument,
                focus,
                coach_chords,
                section_name=coach_section,
                groove_style=resolved_groove,
            )
        )

    follow_position = render_follow_along_controls(
        chart_backing_events,
        bpm,
        form_loops,
        key_prefix=f"backing::{song}::{tuple(selected_section_names)}::{chart_display_key}",
    )
    current_chart_section = (
        follow_position["section"]
        if follow_position
        else (section_scope_label if selected_section_names else "Full song")
    )
    current_chart_bar = follow_position["bar_in_section"] if follow_position else None

    st.subheader("2. Full Song Chart")

    st.markdown(
        full_chord_markdown(
            song,
            song_data,
            chart_sections,
            instrument,
            display_key=chart_display_key,
            level=level,
            lyric_cues=lyric_cues,
            section_lyrics=section_lyrics,
            groove_style=resolved_groove,
            bpm=bpm,
            time_signature=default_time_signature(song, chart_sections),
            current_section=current_chart_section,
            current_bar=current_chart_bar,
            focus=focus,
        ),
        unsafe_allow_html=True,
    )

    with st.expander("Form timeline and selected playback order", expanded=False):
        _tl_rows = form_timeline_rows(sections)

        st.dataframe(
            pd.DataFrame(_tl_rows).rename(
                columns={
                    "section": "Section",
                    "start_bar": "Start bar",
                    "end_bar": "End bar",
                    "bars": "Bars (chords)",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

        selected_rows = [
            {
                "Section": name,
                "Bars": len(chords),
                "Included": "Yes" if (not selected_section_names or name in selected_section_names) else "No",
            }
            for name, chords in section_order(sections)
            if chords
        ]
        st.dataframe(
            pd.DataFrame(selected_rows),
            use_container_width=True,
            hide_index=True,
        )

    st.subheader("3. Generate / Play Backing Track")

    if st.button(
        "Generate backing track (from active song + settings above)",
        key="gen_backing_btn",
        disabled=not bool(backing_chords),
    ):

        _backing_signature = (
            song,
            display_key,
            level,
            resolved_groove,
            bpm,
            form_loops,
            tuple(selected_section_names),
            tuple(backing_chords),
        )

        wav = generate_backing_track(
            backing_events,
            bpm=bpm,
            loops=form_loops,
            style=resolved_groove,
            level=level,
        )

        st.session_state["_last_backing_wav"] = wav
        st.session_state["_last_backing_signature"] = _backing_signature

    _current_backing_signature = (
        song,
        display_key,
        level,
        resolved_groove,
        bpm,
        form_loops,
        tuple(selected_section_names),
        tuple(backing_chords),
    )

    if (
        st.session_state.get("_last_backing_wav")
        and st.session_state.get("_last_backing_signature") == _current_backing_signature
    ):

        st.audio(
            st.session_state["_last_backing_wav"],
            format="audio/wav",
        )

        _scope_bit = section_scope_label.replace(" ", "_").replace("/", "_")

        st.download_button(
            "Download backing track WAV",
            st.session_state["_last_backing_wav"],
            file_name=f"{song.replace(' ', '_')}_{_scope_bit}_{form_loops}loops.wav",
            mime="audio/wav",
            key="dl_backing_btn",
        )

# -------------------------------------------------
# UPLOAD / RECORDING ANALYSIS
# -------------------------------------------------

with tabs[5]:

    st.header("Upload / Recording Analysis")

    st.write("Upload or record your playing. The app gives intermediate feedback on tempo, pitch center, articulation, dynamics, and song-specific chord tones.")

    st.info("This is intermediate analysis, not perfect professional note-by-note grading.")

    analysis_audio = st.file_uploader(
        "Upload a recording to analyze",
        type=["wav", "mp3", "m4a", "ogg"],
        key="analysis_audio_upload"
    )

    try:
        mic_audio = st.audio_input("Or record directly", key="analysis_audio_record")
    except Exception:
        mic_audio = None
        st.caption("Direct microphone recording may not be available in this Streamlit version. Uploading audio will still work.")

    audio_obj = mic_audio if mic_audio is not None else analysis_audio

    if st.button("Analyze my recording"):

        if audio_obj is None:
            st.warning("Upload or record audio first.")
        else:
            audio_bytes = audio_obj.getvalue()
            filename = getattr(audio_obj, "name", "recording.wav")
            result = analyze_recording_basic(audio_bytes, filename, full_song_chords, instrument, level)
            render_recording_analysis_report(result, song, focus)




# -------------------------------------------------
# CREATIVE LAB
# -------------------------------------------------

with tabs[3]:

    st.header("AI Musical Development + Creative Lab")

    st.write(
        "This page starts moving the app beyond ordinary practice into deeper musical development: "
        "harmony, improvisation, arranging, weakness detection, and long-term growth tracking."
    )

    ctx = current_song_context_lab()

    lab_mode = st.selectbox(
        "Choose creative intelligence mode",
        [
            "Deep Harmonic Analyzer",
            "Improvisation Intelligence",
            "Creative Arrangement Assistant",
            "Adaptive Weakness Detection",
            "AI-Guided Musical Development Tracking"
        ]
    )

    if lab_mode == "Deep Harmonic Analyzer":
        st.markdown(deep_harmonic_analysis_text(ctx))

    elif lab_mode == "Improvisation Intelligence":
        st.markdown(improvisation_intelligence_text(ctx))

    elif lab_mode == "Creative Arrangement Assistant":
        target_style = st.selectbox(
            "Transform toward style",
            [
                "Jobim / Bossa",
                "Jazz Fusion",
                "Neo-Soul",
                "Rock Ballad",
                "Funk",
                "Cinematic"
            ]
        )
        arrangement_section = st.selectbox(
            "Arrangement focus",
            ["Full song"] + [name for name, chords in sections.items() if chords],
            key="creative_arrangement_section_focus",
        )
        st.markdown(creativity_arrangement_text(ctx, target_style, arrangement_section))

    elif lab_mode == "Adaptive Weakness Detection":
        st.markdown(adaptive_weakness_detection_text(ctx))

    else:
        st.markdown(musical_development_tracker_text())


# -------------------------------------------------
# MULTITRACK
# -------------------------------------------------

with tabs[4]:

    st.header("Multitrack Recorder")

    st.write(
        "This upgraded multitrack page supports a play-along backing track, count-in, track alignment, volume controls, and exporting a mixed WAV."
    )

    st.info(
        "Important: browser-based Streamlit recording cannot perfectly lock all tracks like GarageBand yet, but this version gives you practical count-in, playback, alignment sliders, volume controls, and mix export."
    )

    if "tracks" not in st.session_state:

        st.session_state.tracks = {
            "Track 1": None,
            "Track 2": None,
            "Track 3": None
        }

    if "track_filenames" not in st.session_state:

        st.session_state.track_filenames = {
            "Track 1": "track1.wav",
            "Track 2": "track2.wav",
            "Track 3": "track3.wav"
        }

    st.subheader("1. Play-Along Backing Track")

    mt_bpm = st.slider(
        "Multitrack backing BPM",
        50,
        180,
        100,
        5,
        key="multitrack_bpm"
    )

    count_in_beats = st.selectbox(
        "Count-in before recording",
        [0, 2, 4, 8],
        index=2,
        key="multitrack_countin"
    )

    include_backing_in_mix = st.checkbox(
        "Include backing track in exported mix",
        value=True,
        key="include_backing_mix"
    )

    backing_volume = st.slider(
        "Backing track volume",
        0.0,
        1.5,
        0.75,
        0.05,
        key="backing_volume"
    )

    if st.button("Generate play-along backing track with count-in"):

        backing_y = backing_bytes_to_float(
            chord_events_for_selected_sections(sections),
            bpm=mt_bpm,
            style=default_groove_style,
            level=level,
        )

        if count_in_beats > 0:
            count_y = make_count_in_click(
                bpm=mt_bpm,
                beats=count_in_beats
            )
            backing_y = np.concatenate([count_y, backing_y])

        backing_y = backing_y * backing_volume

        st.session_state.multitrack_backing_wav = wav_bytes_from_float(backing_y)

    if st.session_state.get("multitrack_backing_wav"):

        st.audio(
            st.session_state.multitrack_backing_wav,
            format="audio/wav"
        )

        st.caption(
            "Press play on this backing track, then record/upload a track below. Use alignment sliders after recording to line up the timing."
        )

    st.divider()

    st.subheader("2. Record or Upload 3 Instrument Tracks")

    track_items_for_mix = []

    for track_name in [
        "Track 1",
        "Track 2",
        "Track 3"
    ]:

        st.markdown(f"### {track_name}")

        col_a, col_b = st.columns(2)

        with col_a:

            instrument_name = st.text_input(
                f"Instrument name — {track_name}",
                value=track_name,
                key=f"{track_name}_instrument_name"
            )

            uploaded = st.file_uploader(
                f"Upload audio — {track_name}",
                type=["wav", "mp3", "m4a", "ogg"],
                key=f"{track_name}_upload"
            )

            try:
                recorded = st.audio_input(
                    f"Record {track_name}",
                    key=f"{track_name}_record"
                )
            except Exception:
                recorded = None
                st.caption(
                    "Direct recording may not be available in this Streamlit version. Uploading audio still works."
                )

            if st.button(
                f"Save {track_name}",
                key=f"{track_name}_save"
            ):

                audio_obj = recorded if recorded is not None else uploaded

                if audio_obj is not None:

                    st.session_state.tracks[track_name] = audio_obj.getvalue()

                    st.session_state.track_filenames[track_name] = getattr(
                        audio_obj,
                        "name",
                        f"{track_name}.wav"
                    )

                    st.success(
                        f"{track_name} saved."
                    )

                else:

                    st.warning(
                        "Record or upload audio first."
                    )

        with col_b:

            volume = st.slider(
                f"{track_name} volume",
                0.0,
                2.0,
                1.0,
                0.05,
                key=f"{track_name}_volume"
            )

            delay = st.slider(
                f"{track_name} alignment delay/advance seconds",
                -3.0,
                3.0,
                0.0,
                0.05,
                key=f"{track_name}_delay"
            )

            st.caption(
                "Positive delay moves the track later. Negative delay moves it earlier."
            )

        saved_audio = st.session_state.tracks.get(track_name)

        if saved_audio:

            st.write(f"Playback: **{instrument_name}**")

            st.audio(saved_audio)

            track_items_for_mix.append({
                "name": instrument_name,
                "audio_bytes": saved_audio,
                "filename": st.session_state.track_filenames.get(track_name, f"{track_name}.wav"),
                "volume": volume,
                "delay": delay
            })

    st.divider()

    st.subheader("3. Export Mixed Track")

    if st.button("Create mixed track"):

        try:

            backing_y = None

            if include_backing_in_mix:

                backing_y = backing_bytes_to_float(
                    chord_events_for_selected_sections(sections),
                    bpm=mt_bpm,
                    style=default_groove_style,
                    level=level,
                )

                if count_in_beats > 0:
                    count_y = make_count_in_click(
                        bpm=mt_bpm,
                        beats=count_in_beats
                    )
                    backing_y = np.concatenate([count_y, backing_y])

                backing_y = backing_y * backing_volume

            mixed = mix_multitrack(
                backing_y,
                track_items_for_mix
            )

            mixed_wav = wav_bytes_from_float(mixed)

            st.session_state.mixed_track_wav = mixed_wav

            st.success(
                "Mixed track created."
            )

        except Exception as e:

            st.error(
                f"Could not create mix: {e}"
            )

    if st.session_state.get("mixed_track_wav"):

        st.audio(
            st.session_state.mixed_track_wav,
            format="audio/wav"
        )

        st.download_button(
            "Download mixed track WAV",
            st.session_state.mixed_track_wav,
            file_name=f"{song.replace(' ', '_')}_multitrack_mix.wav",
            mime="audio/wav"
        )

    st.divider()

    if st.button("Clear all multitrack recordings"):

        st.session_state.tracks = {
            "Track 1": None,
            "Track 2": None,
            "Track 3": None
        }

        st.session_state.track_filenames = {
            "Track 1": "track1.wav",
            "Track 2": "track2.wav",
            "Track 3": "track3.wav"
        }

        st.session_state.mixed_track_wav = None

        st.success(
            "Tracks cleared."
        )

# -------------------------------------------------
# PRACTICE LOG
# -------------------------------------------------

with tabs[6]:

    st.header("Practice Log")

    if st.button(
        "Clear Music Practice / Reset"
    ):

        save_logs([])

        st.success(
            "Practice log cleared."
        )

    with st.form("practice_form"):

        practice_text_input = st.text_area(
            "What did you practice today?",
            value=f"{genre} practice — {song}"
        )

        rating = st.slider(
            "How did it go?",
            1,
            10,
            6
        )

        submitted = st.form_submit_button(
            "Save Practice Log"
        )

    if submitted:

        logs = load_logs()

        logs.append({
            "date": str(date.today()),
            "genre": genre,
            "song": song,
            "instrument": instrument,
            "level": level,
            "focus": focus,
            "practice": practice_text_input,
            "rating": rating
        })

        save_logs(logs)

        st.success(
            "Practice log saved."
        )

    logs = load_logs()

    if logs:

        st.dataframe(
            pd.DataFrame(logs),
            use_container_width=True
        )

    else:

        st.info(
            "No practice logs yet."
        )
