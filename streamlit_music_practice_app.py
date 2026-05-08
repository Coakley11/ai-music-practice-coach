# VERSION: v37_multitrack_playalong_mix_export

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
# GLOBAL CONSTANTS
# -------------------------------------------------

DATA_FILE = Path("practice_history.json")

GENRES = [
    "Jazz",
    "Pop",
    "Rock",
    "Funk",
    "Blues",
    "Classical"
]

COMMON_KEYS = [
    "C","Db","D","Eb","E","F",
    "Gb","G","Ab","A","Bb","B"
]

CHROMATIC = [
    "C","C#","D","D#","E","F",
    "F#","G","G#","A","A#","B"
]

FLAT_TO_SHARP = {
    "Db":"C#",
    "Eb":"D#",
    "Gb":"F#",
    "Ab":"G#",
    "Bb":"A#"
}

NOTE_TO_MIDI = {
    "C":60,"C#":61,"Db":61,
    "D":62,"D#":63,"Eb":63,
    "E":64,
    "F":65,"F#":66,"Gb":66,
    "G":67,"G#":68,"Ab":68,
    "A":69,"A#":70,"Bb":70,
    "B":71
}

# -------------------------------------------------
# SONG LIBRARY
# -------------------------------------------------

SONG_LIBRARY = {

    "Jazz": {

        "Autumn Leaves": {
            "artist": "Jazz Standard",
            "key": "G",
            "sections": {
                "A Section": [
                    "Cm7","F7","Bbmaj7","Ebmaj7",
                    "Am7b5","D7","Gm7","Gm7"
                ],
                "B Section": [
                    "Cm7","F7","Bbmaj7","Ebmaj7",
                    "Am7b5","D7","Gm7","D7"
                ]
            },
            "guitar_tabs": {
                "Cm7":"x35343",
                "F7":"131211",
                "Bbmaj7":"x13231",
                "Ebmaj7":"x68786",
                "Am7b5":"5x554x",
                "D7":"xx0212",
                "Gm7":"353333"
            }
        },

        "Blue Bossa": {
            "artist": "Jazz Standard",
            "key": "C",
            "sections": {
                "A Section": [
                    "Cm7","Fm7","Dm7b5","G7",
                    "Cm7","Cm7"
                ],
                "B Section": [
                    "Ebm7","Ab7","Dbmaj7","Dbmaj7",
                    "Dm7b5","G7","Cm7","G7"
                ]
            },
            "guitar_tabs": {
                "Cm7":"x35343",
                "Fm7":"131111",
                "Dm7b5":"x5656x",
                "G7":"320001"
            }
        }
    },

    "Pop": {

        "Say": {
            "artist": "John Mayer",
            "key": "D",
            "sections": {
                "Verse": ["D","A","Bm","G"],
                "Chorus": ["D","A","G","D"],
                "Bridge": ["Bm","A","G","D"],
                "Final Chorus": ["D","A","G","D"]
            },
            "guitar_tabs": {
                "D":"xx0232",
                "A":"x02220",
                "Bm":"x24432",
                "G":"320003"
            }
        },

        "Perfect": {
            "artist": "Ed Sheeran",
            "key": "G",
            "sections": {
                "Verse": ["G","Em","C","D"],
                "Pre-Chorus": ["Em","C","G","D"],
                "Chorus": ["G","D","Em","C"]
            },
            "guitar_tabs": {
                "G":"320003",
                "Em":"022000",
                "C":"x32010",
                "D":"xx0232"
            }
        }
    },

    "Rock": {

        "Don't Stop Believin'": {
            "artist": "Journey",
            "key": "E",
            "sections": {
                "Low Part / Verse": [
                    "E","B","C#m","A"
                ],
                "Pre-Chorus": [
                    "A","E","B","C#m"
                ],
                "High Part / Chorus": [
                    "E","B","A","E"
                ],
                "Final Chorus": [
                    "E","B","A","E"
                ]
            },
            "guitar_tabs": {
                "E":"022100",
                "B":"x24442",
                "C#m":"x46654",
                "A":"x02220"
            }
        },

        "Gravity": {
            "artist": "John Mayer",
            "key": "G",
            "sections": {
                "Verse": ["G","C","G","D"],
                "Lift": ["Em","C","G","D"],
                "Solo Section": ["G7","C7","G7","D7"]
            },
            "guitar_tabs": {
                "G":"320003",
                "C":"x32010",
                "D":"xx0232"
            }
        }
    },

    "Funk": {

        "Superstition": {
            "artist": "Stevie Wonder",
            "key": "Eb",
            "sections": {
                "Main Groove": [
                    "Ebm7","Ebm7","Ebm7","Ebm7"
                ],
                "Chorus": [
                    "Ab7","Gb7","Ebm7","Ebm7"
                ]
            },
            "guitar_tabs": {
                "Ebm7":"x68676",
                "Ab7":"464544"
            }
        }
    },

    "Blues": {

        "12-Bar Blues in F": {
            "artist": "Traditional",
            "key": "F",
            "sections": {
                "Bars 1-4": [
                    "F7","Bb7","F7","F7"
                ],
                "Bars 5-8": [
                    "Bb7","Bb7","F7","F7"
                ],
                "Bars 9-12": [
                    "C7","Bb7","F7","C7"
                ]
            },
            "guitar_tabs": {
                "F7":"131211",
                "Bb7":"x13131",
                "C7":"x32310"
            }
        }
    },

    "Classical": {

        "Ode to Joy": {
            "artist": "Beethoven",
            "key": "D",
            "sections": {
                "Theme": [
                    "D","A","D","G",
                    "D","A","D"
                ]
            },
            "guitar_tabs": {
                "D":"xx0232",
                "A":"x02220",
                "G":"320003"
            }
        }
    }
}

# -------------------------------------------------
# HELPER FUNCTIONS
# -------------------------------------------------

def normalize_root(root):
    return FLAT_TO_SHARP.get(root, root)

def split_chord(chord):
    chord = str(chord)
    if len(chord) >= 2 and chord[1] in ["b", "#"]:
        return chord[:2], chord[2:]
    return chord[:1], chord[1:]

def semitone_distance(from_key, to_key):
    a = normalize_root(split_chord(from_key)[0])
    b = normalize_root(split_chord(to_key)[0])

    if a not in CHROMATIC or b not in CHROMATIC:
        return 0

    return (CHROMATIC.index(b) - CHROMATIC.index(a)) % 12

def transpose_chord(chord, steps):

    root, suffix = split_chord(chord)
    root = normalize_root(root)

    if root not in CHROMATIC:
        return chord

    new_root = CHROMATIC[
        (CHROMATIC.index(root) + steps) % 12
    ]

    return new_root + suffix

def transpose_sections(song_data, target_key):

    original_key = song_data["key"]

    steps = semitone_distance(
        original_key,
        target_key
    )

    out = {}

    for section_name, chords in song_data["sections"].items():

        out[section_name] = [
            transpose_chord(ch, steps)
            for ch in chords
        ]

    return out

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
    instrument
):

    out = []

    out.append(
        f"## Full Song Chords — {song_name}"
    )

    out.append(
        f"Artist: **{song_data['artist']}**"
    )

    out.append(
        f"Original key: **{song_data['key']}**"
    )

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

        tabs = song_data.get(
            "guitar_tabs",
            {}
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

def generate_backing_track(
    chords,
    bpm=100
):

    sr = 44100

    beat = 60 / bpm

    bar = beat * 4

    audio = np.zeros(
        int(sr * bar * len(chords))
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

    for chord in chords:

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
# APP UI
# -------------------------------------------------

st.title(
    "🎵 Daniel Cohen AI MUSIC PRACTICE COACH"
)

st.caption(
    "Genre-based practice plans, full-song chords, backing tracks, multitrack recording, and practice logs."
)

# SIDEBAR

st.sidebar.header("Setup")

genre = st.sidebar.selectbox(
    "What kind of music do you want to play today?",
    GENRES
)

song_options = list(
    SONG_LIBRARY[genre].keys()
)

song = st.sidebar.selectbox(
    f"Choose a {genre} song",
    song_options
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

song_data = SONG_LIBRARY[genre][song]

default_key_index = (
    COMMON_KEYS.index(song_data["key"])
    if song_data["key"] in COMMON_KEYS
    else 0
)

display_key = st.sidebar.selectbox(
    "Transpose / Display Key",
    COMMON_KEYS,
    index=default_key_index
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

full_song_chords = all_chords_from_sections(
    sections
)

# TABS

tabs = st.tabs([
    "Daily Practice Plan",
    "Song Search",
    "Backing Track",
    "Recording Analysis",
    "Multitrack Recorder",
    "Practice Log"
])

# -------------------------------------------------
# DAILY PRACTICE PLAN
# -------------------------------------------------

with tabs[0]:

    st.header("Daily Practice Plan")

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
            instrument
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

    st.header("Song Search")

    st.info(
        "Songs shown here are filtered by the selected genre."
    )

    preview_song = st.selectbox(
        "Preview Song",
        song_options
    )

    preview_data = SONG_LIBRARY[
        genre
    ][preview_song]

    preview_sections = transpose_sections(
        preview_data,
        display_key
    )

    st.markdown(
        full_chord_markdown(
            preview_song,
            preview_data,
            preview_sections,
            instrument
        )
    )

# -------------------------------------------------
# BACKING TRACK
# -------------------------------------------------

with tabs[2]:

    st.header("Backing Track")

    st.write(
        f"Backing track for: **{song}**"
    )

    bpm = st.slider(
        "Backing Track BPM",
        50,
        180,
        100,
        5
    )

    if st.button(
        "Generate Full Song Backing Track"
    ):

        wav = generate_backing_track(
            full_song_chords,
            bpm=bpm
        )

        st.audio(
            wav,
            format="audio/wav"
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

with tabs[5]:

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
