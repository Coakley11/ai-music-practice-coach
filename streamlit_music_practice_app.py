# VERSION: v46_master_song_architecture

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

from music_theory import (
    COMMON_KEYS,
    CHROMATIC,
    FLAT_TO_SHARP,
    NOTE_TO_MIDI,
    normalize_root,
    split_chord,
    semitone_distance,
    transpose_chord,
    transpose_sections,
    transpose_guitar_tabs,
)
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

ensure_master_song_initialized(
    st,
    all_records=ALL_SONG_RECORDS,
    song_library=SONG_LIBRARY,
    song_picker_catalog=SONG_PICKER_CATALOG,
)

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

def chord_notes(chord):

    root = split_chord(chord)[0]

    base = NOTE_TO_MIDI.get(root, 60)

    low = chord.lower()

    if "m7b5" in low:
        intervals = [0,3,6,10]

    elif "maj7" in low:
        intervals = [0,4,7,11]

    elif "m7" in low:
        intervals = [0,3,7,10]

    elif "m" in low and "maj" not in low:
        intervals = [0,3,7]

    elif "7" in low:
        intervals = [0,4,7,10]

    else:
        intervals = [0,4,7]

    return [base+i for i in intervals]

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

    ext = song_data.get("extensions") or {}
    if ext.get("arrangement_notes"):
        out.append(f"_Chart note:_ {ext['arrangement_notes']}")

    for section_name, chords in sections.items():

        out.append(
            f"\n### {section_name}"
        )

        out.append(
            "| " + " | ".join(chords) + " |"
        )

    if instrument == "Guitar":

        out.append(
            "\n## Guitar Chord Shapes"
        )

        tabs = transpose_guitar_tabs(
            song_data.get("guitar_tabs", {}),
            song_data["key"],
            dk,
        )

        for chord_name, tab in tabs.items():

            out.append(
                f"- {chord_name}: `{tab}`"
            )

    return "\n".join(out)

def practice_text(level):

    if level == "Beginner":
        return """
### Beginner Focus
- Practice slowly.
- Learn one section at a time.
- Focus on clean rhythm.
- Say chord names aloud.
"""

    if level == "Intermediate":
        return """
### Intermediate Focus
- Connect sections together.
- Practice rhythm consistency.
- Add chord-tone improvisation.
- Record one full section.
"""

    return """
### Advanced Focus
- Use voice leading.
- Add substitutions and inversions.
- Improvise over the full form.
- Create variations for each section.
"""

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

def synthesize_chords_to_numpy(chords, bpm=100, loops=1, sr=44100):

    beat = 60 / bpm

    bar = beat * 4

    chord_list = list(chords) * max(1, int(loops))

    audio = np.zeros(
        int(sr * bar * len(chord_list))
    )

    def freq(midi_num):

        return 440 * (
            2 ** ((midi_num - 69) / 12)
        )

    def tone(
        frequency,
        duration,
        volume=0.1
    ):

        t = np.linspace(
            0,
            duration,
            int(sr * duration),
            False
        )

        sig = np.sin(
            2 * np.pi * frequency * t
        )

        env = np.linspace(
            1,
            0.05,
            len(sig)
        )

        return sig * env * volume

    current = 0

    for chord in chord_list:

        mids = chord_notes(chord)

        for beat_num in range(4):

            for note in mids[:3]:

                sig = tone(
                    freq(note + 12),
                    beat * 0.8,
                    0.05
                )

                start = int(
                    (current + beat_num * beat)
                    * sr
                )

                end = min(
                    len(audio),
                    start + len(sig)
                )

                audio[start:end] += sig[:end-start]

        current += bar

    audio = np.tanh(audio)

    audio = (
        audio
        / (np.max(np.abs(audio)) + 1e-9)
        * 0.8
    )

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
    loops=1
):

    audio, sr = synthesize_chords_to_numpy(chords, bpm=bpm, loops=loops)
    return pcm16_wav_bytes_from_float(audio, sr)


def backing_bytes_to_float(chords, bpm=100):

    y, _sr = synthesize_chords_to_numpy(chords, bpm=bpm, loops=1)
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

sections = transpose_sections(
    song_data,
    display_key
)

full_song_chords = chord_blocks_for_backing(sections)

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

    st.markdown(
        full_chord_markdown(
            song,
            song_data,
            sections,
            instrument,
            display_key=display_key,
        )
    )

    if st.button(
        "Generate Practice Sheet"
    ):

        st.markdown(
            practice_text(level)
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

    st.caption(
        f"**{len(ALL_SONG_RECORDS)} songs** in the library. "
        "Results filter live as you type (title, artist, composer, genre)."
    )

    search_scope = st.radio(
        "Search scope",
        ["Entire library", "Single genre"],
        horizontal=True,
        key="song_search_scope",
    )

    filter_genre = None
    if search_scope == "Single genre":
        filter_genre = st.selectbox(
            "Genre filter",
            GENRES,
            index=GENRES.index(genre) if genre in GENRES else 0,
            key="picker_genre",
        )

    search_text = st.text_input(
        "Search (autocomplete-style)",
        placeholder="Try: pia, beat, job, coldplay, kosma, autumn…",
        key="song_search_text",
    )

    filtered = search_records(
        ALL_SONG_RECORDS,
        search_text,
        genre=filter_genre,
        limit=150,
    )

    if not filtered:
        st.info("No matches — clear the box or try a shorter fragment to see more songs.")
        filtered = ALL_SONG_RECORDS[:80]

    master_sel = st.session_state.get("selected_song") or {}
    master_pk = master_sel.get("pick_key")
    master_rec = record_for_pick_key(ALL_SONG_RECORDS, master_pk) if master_pk else None
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

                st.toast("Active song updated everywhere (charts, backing track, Creative Lab, analysis).", icon="🎵")

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

    st.caption(
        f"The list above is bound to the **active song**. It currently matches **{song}** — change it any time; all tabs follow."
    )

    preview_sections = transpose_sections(
        {
            "key": selected_data["key"],
            "sections": selected_data["sections"],
        },
        display_key
    )

    preview_song_data = {
        "artist": selected_data["artist"],
        "key": selected_data["key"],
        "sections": selected_data["sections"],
        "guitar_tabs": selected_data.get("guitar_tabs", {}),
        "composer": selected_data.get("composer"),
        "genre": selected_data.get("genre"),
        "extensions": selected_data.get("extensions") or {},
    }

    st.subheader("Preview Full Chords for Selected Song")

    st.markdown(
        full_chord_markdown(
            selected_data["title"],
            preview_song_data,
            preview_sections,
            instrument,
            display_key=display_key,
        )
    )

    st.caption(
        "These are practice-version chord charts. For exact licensed commercial charts or exact sheet music, upload a licensed MIDI/MusicXML file."
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

    st.subheader("Full Chords by Song Part")

    st.markdown(
        full_chord_markdown(
            song,
            song_data,
            sections,
            instrument,
            display_key=display_key,
        )
    )

    st.subheader("Form timeline (playback order)")

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

    st.caption(
        "Sections play in table order. Each chord = one 4/4 bar in the synth. "
        "Use **Start bar** / **End bar** to stay oriented during playback."
    )

    st.subheader("Backing Track Settings")

    _sec_names = [name for name, chs in section_order(sections) if chs]

    back_scope = st.radio(
        "What to loop",
        ["Entire song (all sections in order)", "Single section only"],
        horizontal=True,
        key="backing_track_scope",
    )

    _only_section = None

    if back_scope.startswith("Single") and _sec_names:

        _only_section = st.selectbox(
            "Section",
            _sec_names,
            key="backing_track_single_section",
        )

    backing_chords = chord_blocks_for_backing(
        sections,
        only_section=_only_section,
    )

    bpm = st.slider(
        "BPM",
        50,
        180,
        100,
        5,
        key="backing_track_bpm",
    )

    form_loops = st.slider(
        "How many loops?",
        1,
        10,
        2,
        1,
        key="backing_track_loops",
    )

    st.write(
        f"Sequence length: **{len(backing_chords)}** chord bars per loop "
        f"({_only_section or 'full form'})"
    )

    st.write(
        f"**{form_loops}** loop(s) → **{len(backing_chords) * form_loops}** total chord bars"
    )

    st.subheader("Chord source for this render")

    _src_sections = (
        [( _only_section, sections[_only_section])]
        if _only_section
        else section_order(sections)
    )

    for section_name, section_chords in _src_sections:

        if not section_chords:

            continue

        st.write(f"**{section_name}:**")

        st.write(
            "| " + " | ".join(section_chords) + " |"
        )

    if st.button(
        "Generate backing track (from active song + settings above)",
        key="gen_backing_btn",
    ):

        wav = generate_backing_track(
            backing_chords,
            bpm=bpm,
            loops=form_loops,
        )

        st.session_state["_last_backing_wav"] = wav

    if st.session_state.get("_last_backing_wav"):

        st.audio(
            st.session_state["_last_backing_wav"],
            format="audio/wav",
        )

        _scope_bit = (_only_section or "full").replace(" ", "_")

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
            bpm=mt_bpm
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
                    bpm=mt_bpm
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
