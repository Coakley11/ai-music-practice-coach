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
            match = next(
                (name for name in section_names if name.lower() == maybe_section.strip().lower()),
                None,
            )
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

def full_chord_markdown(
    song_name,
    song_data,
    sections,
    instrument,
    display_key=None,
    level="Intermediate",
    lyric_cues=None,
    section_lyrics=None,
):

    out = []

    out.append(
        f"## Full Song Chords — {song_name}"
    )

    out.append(
        f"Artist: **{song_data['artist']}**"
    )

    comp = song_data.get("composer")
    if comp:
        out.append(f"Composer: **{comp}**")

    g = song_data.get("genre")
    if g:
        out.append(f"Genre: **{g}**")

    dk = display_key or song_data["key"]
    out.append(
        f"Original key: **{song_data['key']}**"
    )
    if dk != song_data["key"]:
        out.append(f"Display key: **{dk}** (chords transposed)")

    out.append(f"Player level chart: **{level}**")
    status_text, _status_kind = chart_status_label(song_data)
    out.append(f"Chart reliability: **{status_text}**")
    out.append("_One grid cell = one 4/4 bar. `%` means repeat the previous bar._")

    total_bars = sum(len(chords) for chords in sections.values())
    out.append(f"Total form length: **{total_bars} bars**")

    ext = song_data.get("extensions") or {}
    if ext.get("arrangement_notes"):
        out.append(f"_Chart note:_ {ext['arrangement_notes']}")

    for section_name, chords in sections.items():

        out.append(f"\n### {section_name} — {len(chords)} bars")

        out.append(f"Compact rhythm: {compact_bar_summary(chords)}")
        out.append(bar_grid_markdown(chords))
        cue_text = lyric_cue_markdown(
            section_name,
            chords,
            lyric_cues or {},
            instrument,
            full_section_lyrics=section_lyrics or {},
        )
        if cue_text:
            out.append(cue_text)

    if instrument == "Guitar":
        out.extend(
            guitar_voicing_lines(
                all_chords_from_sections(sections),
                song_data,
                dk,
                level,
            )
        )

    return "\n".join(out)

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


def song_practice_plan(song, sections, instrument, level, focus, variation, section_lyrics=None):
    section_name, section_chords = _section_for_exercise(sections, variation)
    first_chord, second_chord = _transition_pair(section_chords, variation)
    family = _instrument_family(instrument)
    difficulty = _difficulty_phrase(level, variation)
    bars = len(section_chords)
    cycle = max(1, variation + 1)
    chord_tones = _chord_tone_names(first_chord)
    technical_pattern = _technical_pattern_for_exercise(
        instrument,
        focus,
        first_chord,
        second_chord,
    )
    section_text = (section_lyrics or {}).get(section_name, "")
    lyric_application = ""
    if section_text and instrument == "Voice":
        first_line = next(
            (line.strip() for line in str(section_text).splitlines() if line.strip()),
            "",
        )
        lyric_application = (
            f"\n**Lyric application**\n"
            f"- Start with this section text: _{first_line}_\n"
            f"- Speak it in rhythm over the chord grid, mark breaths, then sing it on vowels before adding consonants.\n"
        )
    elif section_text:
        first_line = next(
            (line.strip() for line in str(section_text).splitlines() if line.strip()),
            "",
        )
        lyric_application = (
            f"\n**Form cue**\n"
            f"- Use this cue to locate the section while playing: _{first_line}_\n"
        )

    warmups = {
        "guitar": [
            f"Fretboard warmup: find **{first_chord}** and **{second_chord}** in two positions, then switch for 2 minutes.",
            f"Right-hand warmup: mute the strings and strum the rhythm of **{section_name}** for {min(8, max(4, bars))} bars.",
            f"Voicing drill: play compact grips for **{first_chord} -> {second_chord}** without breaking time.",
        ],
        "piano": [
            f"Left-hand pattern: play roots for **{section_name}**, one bar per chord, then add fifths.",
            f"Voicing drill: connect **{first_chord} -> {second_chord}** with the nearest inversion.",
            f"Comping warmup: play shell voicings through the first {min(8, bars)} bars of **{section_name}**.",
        ],
        "winds": [
            f"Long tones: sustain the root of **{first_chord}**, then resolve into **{second_chord}**.",
            f"Articulation: tongue quarter notes through the first {min(8, bars)} bars of **{section_name}**.",
            f"Chord-tone warmup: play **{chord_tones}** over **{first_chord}** with steady air.",
        ],
        "voice": [
            f"Breath setup: inhale silently, hum the pitch center of **{first_chord}**, then release into the phrase.",
            f"Vowel warmup: sing the first {min(4, bars)} bars of **{section_name}** on 'oo', then 'ah'.",
            f"Phrase warmup: mark one breath before **{section_name}** and one recovery breath near the midpoint.",
        ],
        "bass": [
            f"Root motion: play one bar each of **{first_chord} -> {second_chord}** with a metronome.",
            f"Time warmup: outline the roots through **{section_name}**, then add fifths on beat 3.",
            f"Approach-tone drill: approach **{second_chord}** by half-step from below on beat 4.",
        ],
        "general": [
            f"Sing and clap the harmonic rhythm of **{section_name}** before playing it.",
            f"Name each chord in the first {min(8, bars)} bars and count the bar aloud.",
            f"Loop **{first_chord} -> {second_chord}** until the transition feels automatic.",
        ],
    }

    focus_templates = {
        "Rhythm": f"Clap, tap, or comp through **{section_name}** for {bars} bars. Keep the same pulse while changing from **{first_chord}** to **{second_chord}**. Then play it {difficulty}.",
        "Melody": f"Create a 2-bar phrase using chord tones from **{first_chord}** ({chord_tones}). Repeat it over **{second_chord}** with one note changed.",
        "Harmony": f"Analyze the movement **{first_chord} -> {second_chord}**. Play/sing the root, 3rd, and 7th where available, then connect them through **{section_name}**.",
        "Improvisation": f"Improvise only over **{section_name}**. Restrict yourself to chord tones for one pass, then add one passing tone per bar.",
        "Technique": f"Turn **{first_chord} -> {second_chord}** into a technical drill: slow reps first, then increase tempo by 5 BPM after three clean passes.",
    }

    instrument_specific = {
        "guitar": {
            "Rhythm": "Use two textures: muted eighth-note strums for verse-type sections, then fuller accents for chorus-type sections.",
            "Melody": "Add one slide into a chord tone, one controlled bend, and one vibrato note at a phrase ending.",
            "Harmony": "Use smaller 3- or 4-string voicings; avoid moving more fingers than needed between bars.",
            "Improvisation": "Build a solo from one motif and answer it in the next two bars.",
            "Technique": "Loop the hardest chord change with strict alternate picking or clean fingerstyle attack.",
        },
        "piano": {
            "Rhythm": "Left hand marks roots; right hand comps short offbeat stabs without rushing.",
            "Melody": "Play the top note of each voicing as a simple melody and shape it dynamically.",
            "Harmony": "Use guide tones in the right hand and roots/shells in the left.",
            "Improvisation": "Improvise a one-hand line while the other hand plays sparse shells.",
            "Technique": "Practice inversions hands-separately, then together at half tempo.",
        },
        "winds": {
            "Rhythm": "Articulate short-long patterns over the section while keeping breath relaxed.",
            "Melody": "Shape each phrase with a clear start, peak, and release.",
            "Harmony": "Target 3rds and 7ths on beats 1 and 3 where possible.",
            "Improvisation": "Use call-and-response: two bars simple, two bars answer.",
            "Technique": "Practice the chord-tone pattern slurred, then tongued.",
        },
        "voice": {
            "Rhythm": "Speak the lyric rhythm over the bar grid, then sing lightly on vowels.",
            "Melody": "Plan breath, vowel, and emotional arc before singing the phrase.",
            "Harmony": "Find the tonic and strongest resolution note in the section before adding words.",
            "Improvisation": "Improvise a short melodic answer on a neutral syllable, not full lyrics.",
            "Technique": "Use semi-occluded warmups (lip trill or hum) before full voice.",
        },
        "bass": {
            "Rhythm": "Lock roots to kick-style accents and keep every note length intentional.",
            "Melody": "Create a simple connecting line between roots without overcrowding.",
            "Harmony": "Outline root, fifth, octave, and approach tones through the section.",
            "Improvisation": "Build a walking or pop bass variation for four bars only.",
            "Technique": "Practice clean shifts and muting between every chord root.",
        },
        "general": {
            "Rhythm": "Count subdivisions aloud and keep the form steady.",
            "Melody": "Phrase in two-bar questions and answers.",
            "Harmony": "Identify stable and tense chords in the section.",
            "Improvisation": "Limit your idea to three notes and develop it.",
            "Technique": "Slow the hardest transition until it is relaxed.",
        },
    }

    family_specific = instrument_specific.get(family, instrument_specific["general"])
    warmup_list = warmups.get(family, warmups["general"])
    warmup = warmup_list[variation % len(warmup_list)]
    focus_task = focus_templates.get(focus, focus_templates["Technique"])
    instrument_task = family_specific.get(focus, family_specific["Technique"])

    if level == "Beginner":
        development = "Keep it short: 4 clean bars, rest, then repeat. Accuracy beats speed."
    elif level == "Intermediate":
        development = "Connect the drill to the backing track and record one pass for timing."
    else:
        development = "Add nuance: dynamics, articulation, space, and one intentional variation on the final pass."

    return f"""
### Personalized Exercise {cycle}: {section_name}
**Song:** {song}  
**Target section:** {section_name} — {bars} bars  
**Chord focus:** **{first_chord} -> {second_chord}**

**Warm-up**
- {warmup}

**Technical pattern**
- {technical_pattern}

**Main exercise**
- {focus_task}

**Instrument coaching**
- {instrument_task}
{lyric_application}

**Progression**
- {development}
"""


def default_time_signature(song, sections):
    text = " ".join([song] + list(sections.keys())).lower()
    if "3/4" in text or "piano man" in text:
        return "3/4"
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
    ]).lower()
    if "jobim" in titleish or "bossa" in titleish:
        return "Bossa nova"
    if genre_name == "Jazz":
        return "Jazz swing"
    if genre_name == "Funk":
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


def _style_patterns(style):
    if style == "Jazz swing":
        return {
            "bass_beats": [0, 1, 2, 3],
            "comp_beats": [1.0, 2.65],
            "hat_beats": [0, 1.65, 2, 3.65],
            "snare_beats": [1.0, 3.0],
        }
    if style == "Bossa nova":
        return {
            "bass_beats": [0, 1.5, 2, 3.5],
            "comp_beats": [0.0, 1.5, 2.5, 3.5],
            "hat_beats": [0, 0.5, 1.5, 2, 2.5, 3.5],
            "snare_beats": [1.5, 3.5],
        }
    if style == "Funk groove":
        return {
            "bass_beats": [0, 0.75, 1.5, 2, 2.75, 3.5],
            "comp_beats": [0.75, 1.75, 2.5, 3.25],
            "hat_beats": [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5],
            "snare_beats": [1.0, 3.0],
        }
    if style == "Rock groove":
        return {
            "bass_beats": [0, 1, 2, 3],
            "comp_beats": [0, 1, 2, 3],
            "hat_beats": [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5],
            "snare_beats": [1.0, 3.0],
        }
    return {
        "bass_beats": [0, 2],
        "comp_beats": [0, 1.5, 2.5, 3.5],
        "hat_beats": [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5],
        "snare_beats": [1.0, 3.0],
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
    chord_list = list(chords) * max(1, int(loops))
    audio = np.zeros(int(sr * bar * len(chord_list)) + sr)
    patterns = _style_patterns(style)

    for idx, chord in enumerate(chord_list):

        bar_start = idx * bar
        notes = chord_notes(chord)
        bass = bass_note(chord) - 12
        root = notes[0]
        fifth = root + 7

        for n, b in enumerate(patterns["bass_beats"]):
            bass_pitch = bass if n % 2 == 0 else min(fifth - 12, bass + 12)
            _add_tone(audio, sr, bar_start + b * beat, beat * 0.55, bass_pitch, 0.12, "bass")

        voicing = notes[:4]
        if level == "Advanced" and len(notes) > 4:
            voicing = [notes[0], notes[2], notes[3], notes[4]]
        elif level == "Beginner":
            voicing = notes[:3]

        for b in patterns["comp_beats"]:
            dur = beat * (0.45 if style in ["Funk groove", "Bossa nova"] else 0.75)
            for note in voicing:
                _add_tone(audio, sr, bar_start + b * beat, dur, note + 12, 0.025, "organ")

        for b in patterns["hat_beats"]:
            _add_noise_hit(audio, sr, bar_start + b * beat, 0.035, 0.012, seed=idx * 31 + int(b * 100))

        for b in patterns["snare_beats"]:
            _add_noise_hit(audio, sr, bar_start + b * beat, 0.06, 0.035, seed=idx * 67 + int(b * 100))

        for b in [0, 2]:
            _add_tone(audio, sr, bar_start + b * beat, 0.08, 36, 0.08, "bass")

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
    "Select or change the piece under **Song Search / Song Picker**. "
    "That choice is the one source of truth for every tab."
)

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

focus = st.sidebar.selectbox(
    "Focus",
    [
        "Melody",
        "Harmony",
        "Rhythm",
        "Improvisation",
        "Technique"
    ]
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
    "Daily Practice Plan",
    "Song Search",
    "Backing Track",
    "Recording Analysis",
    "Creative Lab",
    "Multitrack Recorder",
    "Practice Log"
])

# -------------------------------------------------
# DAILY PRACTICE PLAN
# -------------------------------------------------

with tabs[0]:

    st.header("Daily Practice Plan")

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

    with st.expander("Open chord chart for this practice plan", expanded=False):
        st.markdown(
            full_chord_markdown(
                song,
                song_data,
                sections,
                instrument,
                display_key=display_key,
                level=level,
                lyric_cues=lyric_cues,
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

    st.write(
        f"- Warmup: {max(5, int(minutes * 0.2))} minutes"
    )

    st.write(
        f"- Song sections: {max(8, int(minutes * 0.4))} minutes"
    )

    st.write(
        f"- {focus}: {max(8, int(minutes * 0.25))} minutes"
    )

    st.write(
        f"- Review/recording: {max(5, int(minutes * 0.15))} minutes"
    )

# -------------------------------------------------
# SONG SEARCH
# -------------------------------------------------

with tabs[1]:

    st.header("Song Search / Song Picker")

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
        "This tab is for browsing and selecting only; charts live in Backing Track and Daily Practice Plan."
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

                st.toast("Song selected. Go to Backing Track, Daily Practice Plan, or Multitrack Recorder.", icon="🎵")

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
        "Go to **Daily Practice Plan** for exercises. "
        "Go to **Multitrack Recorder** to record."
    )

# -------------------------------------------------
# BACKING TRACK
# -------------------------------------------------

with tabs[2]:

    st.header("Backing Track")

    st.write(
        f"Uses the **active song** (same as Song Search / sidebar): **{song}** — {song_data['artist']}. "
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

    st.markdown(
        lyric_guide_markdown(
            sections,
            lyric_cues,
            instrument,
            section_lyrics=section_lyrics,
        )
    )

    st.subheader("2. Full Song Chart")

    st.markdown(
        full_chord_markdown(
            song,
            song_data,
            sections,
            instrument,
            display_key=display_key,
            level=level,
            lyric_cues=lyric_cues,
            section_lyrics=section_lyrics,
        )
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
            backing_chords,
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
# RECORDING ANALYSIS
# -------------------------------------------------

with tabs[3]:

    st.header("Recording Analysis")

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

with tabs[4]:

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
        st.markdown(creativity_arrangement_text(ctx, target_style))

    elif lab_mode == "Adaptive Weakness Detection":
        st.markdown(adaptive_weakness_detection_text(ctx))

    else:
        st.markdown(musical_development_tracker_text())


# -------------------------------------------------
# MULTITRACK
# -------------------------------------------------

with tabs[5]:

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
            full_song_chords,
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
                    full_song_chords,
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
