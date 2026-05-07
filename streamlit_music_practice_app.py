# VERSION: v25_fixed_current_song_context

# VERSION: v18_full_chord_charts_transpose_any_key

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import io, os, json, wave, tempfile, zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import date
from collections import Counter, defaultdict

try:
    import pretty_midi
except Exception:
    pretty_midi = None

try:
    from scipy.signal import lfilter
except Exception:
    lfilter = None

try:
    import librosa
except Exception:
    librosa = None

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


st.set_page_config(page_title="Daniel Cohen AI MUSIC PRACTICE COACH", page_icon="🎵", layout="wide")
st.title("🎵 Daniel Cohen AI MUSIC PRACTICE COACH")
st.caption("Legal-safe song-aware practice coach: public-domain songs, original exercises, and user-uploaded MIDI/MusicXML.")

DATA_FILE = Path("practice_history.json")


# ============================================================
# BASIC DATA
# ============================================================

INSTRUMENTS = ["Piano", "Guitar", "Saxophone", "Flute", "Trumpet", "Voice", "Other"]

SKILLS = {
    "Piano": ["Melody", "Left-hand chords", "Both hands", "Sight-reading", "Chord voicings", "Improvisation"],
    "Guitar": ["Strumming", "Chord changes", "Melody", "Tab", "Chord melody", "Improvisation"],
    "Saxophone": ["Tone", "Articulation", "Melody", "Chord tones", "Improvisation", "Sight-reading"],
    "Flute": ["Tone", "Breath", "Melody", "Articulation", "Sight-reading", "Intonation"],
    "Trumpet": ["Tone", "Breath", "Melody", "Articulation", "Range", "Endurance"],
    "Voice": ["Pitch accuracy", "Tone", "Breath", "Phrasing", "Ear training"],
    "Other": ["Tone", "Rhythm", "Melody", "Chords", "Technique"]
}

PUBLIC_DOMAIN_SONGS = {
    "Ode to Joy": {
        "composer": "Ludwig van Beethoven",
        "key": "D",
        "progression": ["D", "A", "D", "G", "D", "A", "D"],
        "abc": "F F G A | A G F E | D D E F | F E E2 |",
        "melody_notes": "F#4 F#4 G4 A4 | A4 G4 F#4 E4 | D4 D4 E4 F#4 | F#4 E4 E4"
    },
    "Amazing Grace": {
        "composer": "Traditional",
        "key": "G",
        "progression": ["G", "C", "G", "D", "G"],
        "abc": "D G B | G B A | G E D | D G B |",
        "melody_notes": "D4 G4 B4 | G4 B4 A4 | G4 E4 D4 | D4 G4 B4"
    },
    "When the Saints Go Marching In": {
        "composer": "Traditional",
        "key": "C",
        "progression": ["C", "C", "F", "C", "G", "F", "C"],
        "abc": "C E F G | C E F G | C E F G E | C4 |",
        "melody_notes": "C4 E4 F4 G4 | C4 E4 F4 G4 | C4 E4 F4 G4 E4 | C4"
    },
    "Greensleeves": {
        "composer": "Traditional",
        "key": "Am",
        "progression": ["Am", "G", "F", "E7", "Am"],
        "abc": "E G A B | c B A G | F D E2 | A4 |",
        "melody_notes": "E4 G4 A4 B4 | C5 B4 A4 G4 | F4 D4 E4 | A4"
    },
    "Scarborough Fair": {
        "composer": "Traditional",
        "key": "Dm",
        "progression": ["Dm", "C", "Dm", "F", "C", "Dm"],
        "abc": "D D A A | E F E D | C D E D | D4 |",
        "melody_notes": "D4 D4 A4 A4 | E4 F4 E4 D4 | C4 D4 E4 D4"
    }
}


# ============================================================
# HISTORY
# ============================================================

def load_history():
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {"logs": []}
    return {"logs": []}

def save_history(history):
    try:
        DATA_FILE.write_text(json.dumps(history, indent=2), encoding="utf-8")
    except Exception:
        pass

def add_log(entry):
    history = load_history()
    history.setdefault("logs", []).append(entry)
    save_history(history)

def recent_logs(n=20):
    return load_history().get("logs", [])[-n:]


# ============================================================
# OPENAI UI KEY SUPPORT
# ============================================================

if "openai_api_key_ui" not in st.session_state:
    st.session_state.openai_api_key_ui = ""

def get_client():
    key = st.session_state.get("openai_api_key_ui", "").strip()
    if not key:
        key = os.environ.get("OPENAI_API_KEY", "")
        try:
            key = st.secrets.get("OPENAI_API_KEY", key)
        except Exception:
            pass
    if key and OpenAI:
        return OpenAI(api_key=key)
    return None


# ============================================================
# NOTE / CHORD HELPERS
# ============================================================

NOTE_TO_MIDI = {"C":60,"C#":61,"Db":61,"D":62,"D#":63,"Eb":63,"E":64,"F":65,"F#":66,"Gb":66,"G":67,"G#":68,"Ab":68,"A":69,"A#":70,"Bb":70,"B":71}
PC_NAMES = ["C","C#","D","Eb","E","F","F#","G","Ab","A","Bb","B"]

def note_name_to_midi(note_name):
    if not note_name:
        return 60
    note_name = note_name.strip()
    base = {"C":0,"D":2,"E":4,"F":5,"G":7,"A":9,"B":11}
    step = note_name[0].upper()
    if step not in base:
        return 60
    idx = 1
    acc = 0
    if len(note_name) > 1 and note_name[1] in ["#", "b"]:
        acc = 1 if note_name[1] == "#" else -1
        idx = 2
    try:
        octave = int(note_name[idx:])
    except Exception:
        octave = 4
    return 12 * (octave + 1) + base[step] + acc

def midi_to_note_name(midi_num):
    return f"{PC_NAMES[int(midi_num) % 12]}{int(midi_num)//12 - 1}"

def chord_root(chord):
    chord = str(chord).strip()
    if len(chord) >= 2 and chord[1] in ["b", "#"]:
        return chord[:2]
    return chord[:1]

def chord_notes(chord):
    root = chord_root(chord)
    root_midi = NOTE_TO_MIDI.get(root, 60)
    c = str(chord).lower()
    if "m7b5" in c or "ø" in c:
        ints = [0,3,6,10]
    elif "maj7" in c:
        ints = [0,4,7,11]
    elif "m7" in c:
        ints = [0,3,7,10]
    elif "m" in c and "maj" not in c:
        ints = [0,3,7]
    elif "7" in c:
        ints = [0,4,7,10]
    else:
        ints = [0,4,7]
    return [root_midi+i for i in ints]

def midi_to_freq(m):
    return 440.0 * (2 ** ((m - 69) / 12))


# ============================================================
# MUSICXML AND MIDI PARSING
# ============================================================

def parse_musicxml_detailed(uploaded_file):
    try:
        raw = uploaded_file.getvalue()
        fname = getattr(uploaded_file, "name", "uploaded.musicxml").lower()

        if fname.endswith(".mxl"):
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                names = [n for n in z.namelist() if n.endswith(".xml")]
                if not names:
                    return {"error": "No MusicXML file found inside MXL."}
                raw = z.read(names[0])

        root = ET.fromstring(raw)
        for elem in root.iter():
            if "}" in elem.tag:
                elem.tag = elem.tag.split("}", 1)[1]

        title = "Uploaded MusicXML"
        movement = root.find("movement-title")
        if movement is not None and movement.text:
            title = movement.text
        work = root.find("work")
        if work is not None:
            wt = work.find("work-title")
            if wt is not None and wt.text:
                title = wt.text

        parts = root.findall("part")
        if not parts:
            return {"error": "No musical part found."}

        part = parts[0]
        divisions = 1
        measures = []
        chord_list = []
        section_markers = []

        for m_idx, measure in enumerate(part.findall("measure"), start=1):
            attr = measure.find("attributes")
            if attr is not None and attr.findtext("divisions"):
                try:
                    divisions = int(attr.findtext("divisions"))
                except Exception:
                    divisions = 1

            measure_notes = []
            measure_chords = []
            measure_sections = []

            for direction in measure.findall("direction"):
                for words in direction.iter("words"):
                    if words.text and words.text.strip():
                        label = words.text.strip()
                        if len(label) <= 40:
                            measure_sections.append(label)
                            section_markers.append({"measure": m_idx, "label": label})
                for rehearsal in direction.iter("rehearsal"):
                    if rehearsal.text and rehearsal.text.strip():
                        label = rehearsal.text.strip()
                        measure_sections.append(label)
                        section_markers.append({"measure": m_idx, "label": label})

            for harmony in measure.findall("harmony"):
                root_el = harmony.find("root")
                if root_el is not None:
                    step = root_el.findtext("root-step", "")
                    alter = root_el.findtext("root-alter", "")
                    acc = "#" if alter == "1" else "b" if alter == "-1" else ""
                    kind = harmony.findtext("kind", "")
                    chord = step + acc
                    if kind:
                        kl = kind.lower()
                        if "minor-seventh" in kl:
                            chord += "m7"
                        elif "major-seventh" in kl:
                            chord += "maj7"
                        elif "minor" in kl and "major" not in kl:
                            chord += "m"
                        elif "dominant" in kl or kl == "7":
                            chord += "7"
                        elif "diminished" in kl:
                            chord += "dim"
                    measure_chords.append(chord)
                    chord_list.append(chord)

            time_pos = 0.0
            for note in measure.findall("note"):
                duration = note.findtext("duration")
                try:
                    dur = float(duration) / max(divisions, 1) if duration else 1.0
                except Exception:
                    dur = 1.0
                pitch = note.find("pitch")
                if pitch is not None and note.find("rest") is None:
                    step = pitch.findtext("step", "")
                    alter = pitch.findtext("alter", "")
                    octave = pitch.findtext("octave", "")
                    acc = "#" if alter == "1" else "b" if alter == "-1" else ""
                    name = f"{step}{acc}{octave}"
                    measure_notes.append({"note": name, "midi": note_name_to_midi(name), "duration": dur, "start": time_pos})
                time_pos += dur

            measures.append({"number": m_idx, "notes": measure_notes, "chords": measure_chords, "sections": measure_sections})

        all_notes = [n for m in measures for n in m["notes"]]
        return {"source_type": "MusicXML", "title": title, "measures": measures, "notes": all_notes, "chords": chord_list, "sections": section_markers,
                "summary": f"Parsed {len(measures)} measures, {len(all_notes)} notes, {len(chord_list)} chord symbols."}
    except Exception as e:
        return {"error": f"MusicXML parse error: {e}"}

def parse_midi_detailed(uploaded_file):
    if pretty_midi is None:
        return {"error": "MIDI parsing requires pretty_midi. Add pretty_midi to requirements.txt."}
    tmp = None
    try:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mid")
        tmp.write(uploaded_file.getvalue())
        tmp.close()

        pm = pretty_midi.PrettyMIDI(tmp.name)
        notes = []
        for inst in pm.instruments:
            if inst.is_drum:
                continue
            inst_name = inst.name or pretty_midi.program_to_instrument_name(inst.program)
            for n in inst.notes[:2000]:
                notes.append({"note": midi_to_note_name(n.pitch), "midi": int(n.pitch), "start": float(n.start), "end": float(n.end),
                              "duration": float(n.end-n.start), "instrument": inst_name})
        notes = sorted(notes, key=lambda x: x["start"])
        tempos = pm.get_tempo_changes()
        tempo = float(tempos[1][0]) if len(tempos[1]) else 100.0

        measures_map = defaultdict(list)
        sec_per_measure = 60.0 / max(tempo, 1) * 4
        for n in notes:
            mnum = int(n["start"] // sec_per_measure) + 1
            measures_map[mnum].append(n)
        measures = [{"number": k, "notes": v, "chords": [], "sections": []} for k, v in sorted(measures_map.items())]

        return {"source_type": "MIDI", "title": getattr(uploaded_file, "name", "Uploaded MIDI"), "measures": measures, "notes": notes, "chords": [],
                "sections": [], "tempo": tempo, "summary": f"Parsed {len(notes)} notes from MIDI. Approx tempo: {tempo:.1f} BPM."}
    except Exception as e:
        return {"error": f"MIDI parse error: {e}"}
    finally:
        if tmp:
            try:
                os.remove(tmp.name)
            except Exception:
                pass


# ============================================================
# ANALYSIS: KEY, CHORDS, SECTIONS, CHARTS
# ============================================================

def infer_key_from_notes(notes):
    pcs = [n["midi"] % 12 for n in notes if "midi" in n]
    if not pcs:
        return "Unknown"
    counts = Counter(pcs)
    profiles = {
        "C": [0,2,4,5,7,9,11], "G": [7,9,11,0,2,4,6], "D": [2,4,6,7,9,11,1],
        "A": [9,11,1,2,4,6,8], "E": [4,6,8,9,11,1,3], "F": [5,7,9,10,0,2,4],
        "Bb": [10,0,2,3,5,7,9], "Am": [9,11,0,2,4,5,7], "Em": [4,6,7,9,11,0,2],
        "Dm": [2,4,5,7,9,10,0], "Gm": [7,9,10,0,2,3,5]
    }
    return max(profiles, key=lambda k: sum(counts.get(pc,0) for pc in profiles[k]))

def infer_chords_from_measure_notes(measures):
    templates = {
        "C": [0,4,7], "Cm": [0,3,7], "C7": [0,4,7,10], "Cmaj7": [0,4,7,11],
        "D": [2,6,9], "Dm": [2,5,9], "D7": [2,6,9,0], "Dm7": [2,5,9,0],
        "E": [4,8,11], "Em": [4,7,11], "E7": [4,8,11,2],
        "F": [5,9,0], "Fm": [5,8,0], "F7": [5,9,0,3], "Fmaj7": [5,9,0,4],
        "G": [7,11,2], "Gm": [7,10,2], "G7": [7,11,2,5],
        "A": [9,1,4], "Am": [9,0,4], "A7": [9,1,4,7], "Am7": [9,0,4,7],
        "Bb": [10,2,5], "B": [11,3,6], "Bm": [11,2,6], "B7": [11,3,6,9]
    }
    inferred = []
    for m in measures:
        pcs = [n["midi"] % 12 for n in m.get("notes", [])]
        if not pcs:
            inferred.append("")
            continue
        counts = Counter(pcs)
        best = max(templates, key=lambda ch: sum(counts.get(pc,0) for pc in templates[ch]) * 2 - sum(counts.get(pc,0) for pc in counts if pc not in templates[ch]) * 0.35)
        inferred.append(best)
    return inferred

def detect_sections(analysis):
    measures = analysis.get("measures", [])
    explicit = analysis.get("sections", [])
    if explicit:
        sections = []
        for i, sec in enumerate(explicit):
            start = sec["measure"]
            end = explicit[i+1]["measure"] - 1 if i+1 < len(explicit) else len(measures)
            sections.append({"label": sec["label"], "start": start, "end": end})
        return sections
    labels = ["A", "B", "C", "D", "Ending"]
    sections = []
    start = 1
    idx = 0
    while start <= len(measures):
        end = min(start+7, len(measures))
        sections.append({"label": labels[min(idx, len(labels)-1)], "start": start, "end": end})
        start = end + 1
        idx += 1
    return sections

def accompaniment_from_analysis(analysis, section=None):
    measures = analysis.get("measures", [])
    inferred = infer_chords_from_measure_notes(measures)
    if section:
        measures = [m for m in measures if section["start"] <= m["number"] <= section["end"]]
    chords = []
    for m in measures[:24]:
        if m.get("chords"):
            ch = m["chords"][0]
        else:
            idx = m["number"] - 1
            ch = inferred[idx] if idx < len(inferred) else "C"
        if ch:
            chords.append((ch, 1))
    return chords or [("C",1), ("G",1), ("Am",1), ("F",1)]

def make_song_aware_chart(analysis, instrument, level):
    if "error" in analysis:
        return f"Could not analyze file: {analysis['error']}"
    measures = analysis.get("measures", [])
    inferred = infer_chords_from_measure_notes(measures)
    key = infer_key_from_notes(analysis.get("notes", []))
    sections = detect_sections(analysis)

    out = [f"# Song-Aware Chart: {analysis.get('title','Uploaded Song')}",
           f"Source: {analysis.get('source_type','Uploaded file')}",
           f"Estimated key: **{key}**",
           analysis.get("summary","")]

    out.append("\n## Section Map")
    for s in sections:
        out.append(f"- **{s['label']}**: measures {s['start']}–{s['end']}")

    out.append("\n## Chords / Harmony by Measure")
    for m in measures[:80]:
        chord = " / ".join(m.get("chords", [])) if m.get("chords") else (inferred[m["number"]-1] if m["number"]-1 < len(inferred) else "")
        if chord:
            out.append(f"- Measure {m['number']}: {chord}")

    out.append("\n## Extracted Melody by Measure")
    for m in measures[:32]:
        note_names = [n["note"] for n in m.get("notes", [])[:12]]
        if note_names:
            out.append(f"- Measure {m['number']}: " + " ".join(note_names))

    out.append(f"\n## {instrument} Practice Plan — {level}")
    if instrument == "Piano":
        out += ["- Right hand: practice extracted melody measure by measure.",
                "- Left hand: play one chord/root per measure from the chart.",
                "- Both hands: combine slowly, then add comping.",
                "- Advanced: add inversions and keep melody on top."]
    elif instrument == "Guitar":
        out += ["- Strum the detected/inferred chords first.",
                "- Find the melody on the top two strings.",
                "- Loop one section at a time.",
                "- Advanced: build chord melody and voice-leading."]
    elif instrument in ["Saxophone", "Flute", "Trumpet"]:
        out += ["- Practice extracted melody notes slowly.",
                "- Practice roots and chord tones from each measure.",
                "- Add articulation and phrasing after notes are secure."]
    else:
        out += ["- Practice melody first, then chords, then section loops."]
    return "\n".join(out)


# ============================================================
# ABC NOTATION RENDERING
# ============================================================

def abc_note_from_midi(midi):
    name = midi_to_note_name(midi)
    step = name[0]
    acc = "^" if "#" in name else "_" if "b" in name else ""
    try:
        octave = int(name[-1])
    except Exception:
        octave = 4
    abc = acc + step
    if octave >= 5:
        abc = abc.lower()
        if octave > 5:
            abc += "'" * (octave-5)
    elif octave < 4:
        abc += "," * (4-octave)
    return abc

def abc_from_analysis(analysis, instrument, level):
    title = analysis.get("title", "Uploaded Song")
    key = infer_key_from_notes(analysis.get("notes", []))
    if key == "Unknown":
        key = "C"
    tempo = 72 if level == "Beginner" else 96 if level == "Intermediate" else 116
    notes = analysis.get("notes", [])[:48]
    if not notes:
        melody = "C D E G | E D C G, | A, C E D | C4 |"
    else:
        abc_notes = [abc_note_from_midi(n.get("midi", 60)) for n in notes]
        bars = [" ".join(abc_notes[i:i+4]) for i in range(0, len(abc_notes), 4)]
        melody = " | ".join(bars) + " |"
    return f"""X:1
T:{title} - Extracted Practice Notation
C:User-uploaded file analysis
M:4/4
L:1/4
Q:1/4={tempo}
K:{key}
V:Melody clef=treble name="{instrument}"
[V:Melody] {melody}
"""

def public_domain_abc(song_name, instrument, level):
    song = PUBLIC_DOMAIN_SONGS[song_name]
    tempo = 72 if level == "Beginner" else 96 if level == "Intermediate" else 116
    if instrument == "Piano":
        return f"""X:1
T:{song_name} - Public Domain Practice Sheet
C:{song['composer']}
M:4/4
L:1/4
Q:1/4={tempo}
K:{song['key']}
V:RH clef=treble name="Right Hand"
V:LH clef=bass name="Left Hand"
[V:RH] {song['abc']}
[V:LH] C,,4 | G,,4 | A,,4 | F,,4 |
"""
    return f"""X:1
T:{song_name} - Public Domain Practice Sheet
C:{song['composer']}
M:4/4
L:1/4
Q:1/4={tempo}
K:{song['key']}
V:Melody clef=treble name="{instrument}"
[V:Melody] {song['abc']}
"""

def render_abc(abc_text, height=430):
    escaped = abc_text.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")
    html = f"""
    <html>
    <head><script src="https://cdn.jsdelivr.net/npm/abcjs@6.4.4/dist/abcjs-basic-min.js"></script></head>
    <body>
    <div id="paper"></div>
    <script>
    const abc = `{escaped}`;
    ABCJS.renderAbc("paper", abc, {{ responsive: "resize", staffwidth: 760, scale: 1.0 }});
    </script>
    </body>
    </html>
    """
    components.html(html, height=height, scrolling=True)


# ============================================================
# BACKING TRACK GENERATION
# ============================================================

def lowpass(y, amount=0.08):
    if lfilter is None:
        return y
    return lfilter([amount], [1, amount-1], y)

def env(n, sr, attack=0.01, release=0.08):
    a = max(1, int(attack*sr))
    r = max(1, int(release*sr))
    s = max(1, n-a-r)
    e = np.concatenate([np.linspace(0,1,a), np.ones(s), np.linspace(1,0,r)])
    return e[:n] if len(e) >= n else np.pad(e, (0, n-len(e)))

def tone(f, d, sr=44100, v=0.12, kind="piano"):
    t = np.linspace(0, d, int(sr*d), False)
    if kind == "bass":
        y = np.sin(2*np.pi*f*t) + .45*np.sin(2*np.pi*2*f*t)
    elif kind == "pad":
        y = np.sin(2*np.pi*f*t) + .25*np.sin(2*np.pi*1.01*f*t) + .2*np.sin(2*np.pi*2*f*t)
    else:
        y = np.sin(2*np.pi*f*t) + .3*np.sin(2*np.pi*2*f*t) + .12*np.sin(2*np.pi*3*f*t)
    y = y / (np.max(np.abs(y)) + 1e-9)
    y = lowpass(y, 0.12)
    return v * y * env(len(y), sr)

def noise_hit(d, sr=44100, v=0.07, decay=30):
    n = int(sr*d)
    y = np.random.uniform(-1,1,n) * np.exp(-decay*np.linspace(0,d,n))
    return v*y

def add_audio(buf, start, snd):
    end = min(len(buf), start+len(snd))
    if end > start:
        buf[start:end] += snd[:end-start]

def backing_track_from_chords(chords, bpm=100, choruses=3, count_in=True):
    sr = 44100
    beat = 60 / bpm
    bar = beat * 4
    chords = chords or [("C",1), ("G",1), ("Am",1), ("F",1)]
    total_bars = sum(b for c,b in chords) * choruses + (1 if count_in else 0)
    audio = np.zeros(int(total_bars*bar*sr))
    cur = bar if count_in else 0

    if count_in:
        for i in range(4):
            add_audio(audio, int(i*beat*sr), tone(1200, .05, sr, .25))

    for _ in range(choruses):
        for ch, bars in chords:
            ns = chord_notes(ch)
            for b in range(bars*4):
                bt = cur + b*beat
                bass_midi = ns[0]-24 if b % 2 == 0 else (ns[min(2,len(ns)-1)]-24)
                add_audio(audio, int(bt*sr), tone(midi_to_freq(bass_midi), beat*.85, sr, .18, "bass"))
                if b % 4 in [0,2]:
                    add_audio(audio, int(bt*sr), tone(55, .12, sr, .25, "bass"))
                if b % 4 in [1,3]:
                    add_audio(audio, int(bt*sr), noise_hit(.10, sr, .13, 25))
                for h in [0,.5]:
                    add_audio(audio, int((bt+h*beat)*sr), noise_hit(.04, sr, .035, 45))
                for off in [0,.5]:
                    for n in ns[:4]:
                        add_audio(audio, int((bt+off*beat)*sr), tone(midi_to_freq(n+12), beat*.15, sr, .028, "piano"))
            for n in ns[:4]:
                add_audio(audio, int(cur*sr), tone(midi_to_freq(n), bars*bar*.95, sr, .025, "pad"))
            cur += bars*bar

    audio = np.tanh(audio*1.5)/1.5
    audio = audio / (np.max(np.abs(audio)) + 1e-9) * .9
    data = (audio*32767).astype(np.int16)
    out = io.BytesIO()
    with wave.open(out, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(data.tobytes())
    out.seek(0)
    return out.getvalue()



# ============================================================
# SONG SEARCH / SIMILAR SONG DROPDOWN
# ============================================================

SONG_SUGGESTION_CATALOG = {
    "Amazing Grace": {"artist": "Traditional", "style": "Folk / Hymn"},
    "Ode to Joy": {"artist": "Beethoven", "style": "Classical"},
    "When the Saints Go Marching In": {"artist": "Traditional", "style": "Jazz / Gospel"},
    "Greensleeves": {"artist": "Traditional", "style": "Folk / Classical"},
    "Scarborough Fair": {"artist": "Traditional", "style": "Folk / Modal"},
    "House of the Rising Sun": {"artist": "Traditional", "style": "Folk / Rock"},

    "Viva La Vida": {"artist": "Coldplay", "style": "Pop / Rock"},
    "Yellow": {"artist": "Coldplay", "style": "Pop / Rock"},
    "Fix You": {"artist": "Coldplay", "style": "Pop Ballad"},
    "Clocks": {"artist": "Coldplay", "style": "Pop / Piano Rock"},
    "The Scientist": {"artist": "Coldplay", "style": "Pop Ballad"},

    "Shape of You": {"artist": "Ed Sheeran", "style": "Pop"},
    "Perfect": {"artist": "Ed Sheeran", "style": "Pop Ballad"},
    "Thinking Out Loud": {"artist": "Ed Sheeran", "style": "Pop Ballad"},
    "Photograph": {"artist": "Ed Sheeran", "style": "Pop Ballad"},

    "Say": {"artist": "John Mayer", "style": "Pop / Singer-Songwriter"},
    "Gravity": {"artist": "John Mayer", "style": "Blues / Soul"},
    "No Such Thing": {"artist": "John Mayer", "style": "Pop Rock"},
    "Daughters": {"artist": "John Mayer", "style": "Pop Ballad"},
    "Waiting on the World to Change": {"artist": "John Mayer", "style": "Pop / Soul"},
    "Slow Dancing in a Burning Room": {"artist": "John Mayer", "style": "Blues / Rock"},
    "Stop This Train": {"artist": "John Mayer", "style": "Acoustic"},
    "Neon": {"artist": "John Mayer", "style": "Acoustic Guitar"},

    "Don't Stop Believin'": {"artist": "Journey", "style": "Rock"},
    "Open Arms": {"artist": "Journey", "style": "Rock Ballad"},
    "Faithfully": {"artist": "Journey", "style": "Rock Ballad"},

    "Let It Be": {"artist": "The Beatles", "style": "Pop / Rock"},
    "Hey Jude": {"artist": "The Beatles", "style": "Pop / Rock"},
    "Yesterday": {"artist": "The Beatles", "style": "Pop Ballad"},
    "Here Comes the Sun": {"artist": "The Beatles", "style": "Folk Rock"},
    "Something": {"artist": "The Beatles", "style": "Rock Ballad"},
    "In My Life": {"artist": "The Beatles", "style": "Pop Ballad"},
    "Blackbird": {"artist": "The Beatles", "style": "Acoustic"},

    "Piano Man": {"artist": "Billy Joel", "style": "Piano Pop"},
    "Vienna": {"artist": "Billy Joel", "style": "Piano Ballad"},
    "Just the Way You Are": {"artist": "Billy Joel", "style": "Pop Ballad"},
    "New York State of Mind": {"artist": "Billy Joel", "style": "Piano / Jazz Pop"},
    "She's Always a Woman": {"artist": "Billy Joel", "style": "Piano Ballad"},

    "Stand By Me": {"artist": "Ben E. King", "style": "Soul / Pop"},
    "Hallelujah": {"artist": "Leonard Cohen", "style": "Folk / Ballad"},
    "Lean on Me": {"artist": "Bill Withers", "style": "Soul / Gospel"},
    "Imagine": {"artist": "John Lennon", "style": "Piano Ballad"},
}

def similarity_score(query, title, artist, style):
    q = (query or "").lower().strip()
    if not q:
        return 0

    hay = f"{title} {artist} {style}".lower()
    score = 0

    # Strong direct matches
    if q == title.lower():
        score += 100
    if q in title.lower():
        score += 70
    if q in artist.lower():
        score += 55
    if q in style.lower():
        score += 25

    # Word overlap
    q_words = [w for w in q.replace("'", "").split() if len(w) > 1]
    hay_words = hay.replace("'", "").split()
    for w in q_words:
        if w in hay_words:
            score += 12
        elif any(hw.startswith(w) or w.startswith(hw) for hw in hay_words):
            score += 6

    # Small typo tolerance using difflib
    try:
        import difflib
        score += int(30 * difflib.SequenceMatcher(None, q, title.lower()).ratio())
        score += int(18 * difflib.SequenceMatcher(None, q, artist.lower()).ratio())
    except Exception:
        pass

    return score

def get_similar_song_options(query, limit=12):
    scored = []
    for title, data in SONG_SUGGESTION_CATALOG.items():
        score = similarity_score(query, title, data.get("artist", ""), data.get("style", ""))
        if score > 10:
            label = f"{title} — {data.get('artist','Unknown')} ({data.get('style','')})"
            scored.append((score, label, title, data))
    scored.sort(reverse=True, key=lambda x: x[0])

    # If no query yet, give a useful starter list
    if not query.strip():
        starter = list(SONG_SUGGESTION_CATALOG.items())[:limit]
        return [(f"{title} — {data.get('artist','Unknown')} ({data.get('style','')})", title, data) for title, data in starter]

    return [(label, title, data) for score, label, title, data in scored[:limit]]

def render_song_search_dropdown(prefix="song_search"):
    st.subheader("Search Song")
    user_song_query = st.text_input(
        "Type a song title, artist, or style",
        key=f"{prefix}_query",
        placeholder="Example: John Mayer, Say, Ed Sheeran, Viva La Vida, Journey"
    )

    options = get_similar_song_options(user_song_query)
    if options:
        labels = [x[0] for x in options]
        selected_label = st.selectbox("Similar songs found", labels, key=f"{prefix}_dropdown")
        selected = options[labels.index(selected_label)]
        selected_title = selected[1]
        selected_data = selected[2]

        if st.button("Use selected song", key=f"{prefix}_use"):
            st.session_state["searched_song_title"] = selected_title
            st.session_state["searched_song_artist"] = selected_data.get("artist", "")
            st.session_state["searched_song_style"] = selected_data.get("style", "")
            st.success(f"Selected: {selected_title} — {selected_data.get('artist','')}")
        return selected_title, selected_data

    st.warning("No similar songs found. Try typing the artist name or a simpler title.")
    return None, None

def simple_selected_song_practice_sheet(title, data, instrument, level):
    artist = data.get("artist", "")
    style = data.get("style", "")
    return f"""
# {title} — Practice-Style Sheet

Artist: {artist}  
Style: {style}  
Instrument: {instrument}  
Level: {level}

## Important
This is not copyrighted sheet music. It is a practice-style exercise inspired by the selected song/style.

## Practice Plan
- Beginner: learn the basic pulse, simple chords, and short melody fragments.
- Intermediate: add chord tones, section loops, and rhythmic variation.
- Advanced: add reharmonization ideas, improvisation, and arrangement choices.

## Instrument Focus
- Piano: RH melody-style phrase + LH chord roots.
- Guitar: strumming pattern + chord-change loops.
- Sax/Flute/Trumpet: melody fragments + chord-tone drills.
- Voice: pitch matching + phrase shaping.

## Suggested Work
1. Listen to the song.
2. Identify verse/chorus feel.
3. Practice a short original exercise in that style.
4. Record one take and write what needs improvement.
"""


# ============================================================
# TRANSPOSE + FULL CHORD CHART HELPERS
# ============================================================

CHROMATIC_SHARPS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
FLAT_TO_SHARP = {
    "Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#", "Bb": "A#",
    "Cb": "B", "Fb": "E", "E#": "F", "B#": "C"
}

COMMON_KEYS = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]

def normalize_root(root):
    return FLAT_TO_SHARP.get(root, root)

def split_chord_root(chord):
    chord = str(chord).strip()
    if not chord:
        return "", ""
    if len(chord) >= 2 and chord[1] in ["b", "#"]:
        return chord[:2], chord[2:]
    return chord[:1], chord[1:]

def transpose_root(root, semitones):
    root = normalize_root(root)
    if root not in CHROMATIC_SHARPS:
        return root
    idx = CHROMATIC_SHARPS.index(root)
    return CHROMATIC_SHARPS[(idx + semitones) % 12]

def transpose_chord(chord, semitones):
    """
    Transposes chord names like C, Am, Fmaj7, Bb7, D/F#.
    Uses sharps for output to keep it simple.
    """
    chord = str(chord).strip()
    if not chord:
        return chord

    if "/" in chord:
        main, bass = chord.split("/", 1)
        return transpose_chord(main, semitones) + "/" + transpose_chord(bass, semitones)

    root, suffix = split_chord_root(chord)
    new_root = transpose_root(root, semitones)
    return new_root + suffix

def semitone_distance(from_key, to_key):
    from_key = normalize_root(from_key)
    to_key = normalize_root(to_key)
    if from_key not in CHROMATIC_SHARPS or to_key not in CHROMATIC_SHARPS:
        return 0
    return (CHROMATIC_SHARPS.index(to_key) - CHROMATIC_SHARPS.index(from_key)) % 12

def extract_key_root(key_text):
    if not key_text:
        return "C"
    first = str(key_text).split()[0].strip()
    first = first.replace("major", "").replace("minor", "").strip()
    if first.endswith("m") and len(first) <= 3:
        first = first[:-1]
    return first if first else "C"

def transpose_progression(chords, from_key, to_key):
    steps = semitone_distance(extract_key_root(from_key), to_key)
    return [transpose_chord(ch, steps) for ch in chords]

def full_chord_chart_for_selected_song(title, data, transpose_to=None):
    """
    Always shows all chord sections for a song and optionally transposes them.
    """
    original_key = data.get("key", "C")
    to_key = transpose_to or extract_key_root(original_key)
    steps = semitone_distance(extract_key_root(original_key), to_key)

    out = []
    out.append(f"## Full Chord Chart: {title}")
    out.append(f"**Original key:** {original_key}")
    out.append(f"**Displayed key:** {to_key}")
    out.append(f"**Artist/source:** {data.get('artist', data.get('composer', 'Unknown'))}")

    sections = data.get("sections", {})
    if not sections and data.get("progression"):
        sections = {"Main Form": data.get("progression", [])}

    for section, chords in sections.items():
        transposed = [transpose_chord(ch, steps) for ch in chords]
        out.append(f"\n### {section}")
        out.append("| " + " | ".join(transposed) + " |")

    if data.get("progression"):
        out.append("\n### Core Loop")
        out.append("| " + " | ".join([transpose_chord(ch, steps) for ch in data.get("progression", [])]) + " |")

    return "\n".join(out)

def chord_chart_from_uploaded_analysis(analysis, transpose_to=None):
    """
    Full chord chart by detected sections for uploaded MusicXML/MIDI analysis.
    """
    if not analysis:
        return "No uploaded analysis available."

    measures = analysis.get("measures", [])
    if not measures:
        return "No measures found."

    original_key = infer_key_from_notes(analysis.get("notes", []))
    if original_key == "Unknown":
        original_key = "C"
    to_key = transpose_to or original_key
    steps = semitone_distance(extract_key_root(original_key), to_key)

    inferred = infer_chords_from_measure_notes(measures)
    sections = detect_sections(analysis)

    out = []
    out.append(f"## Full Chord Chart: {analysis.get('title', 'Uploaded Song')}")
    out.append(f"**Estimated original key:** {original_key}")
    out.append(f"**Displayed key:** {to_key}")

    for sec in sections:
        out.append(f"\n### {sec['label']} — measures {sec['start']}–{sec['end']}")
        sec_chords = []
        for m in measures:
            if sec["start"] <= m["number"] <= sec["end"]:
                if m.get("chords"):
                    ch = m["chords"][0]
                else:
                    idx = m["number"] - 1
                    ch = inferred[idx] if idx < len(inferred) else ""
                if ch:
                    sec_chords.append(transpose_chord(ch, steps))
        if sec_chords:
            out.append("| " + " | ".join(sec_chords) + " |")
        else:
            out.append("_No chords detected in this section._")

    return "\n".join(out)

def transposed_chords_for_backing(chords, from_key, to_key):
    steps = semitone_distance(extract_key_root(from_key), to_key)
    return [(transpose_chord(ch, steps), bars) for ch, bars in chords]



# ============================================================
# INSTRUMENT / LEVEL / FOCUS SPECIFIC PRACTICE SHEET ENGINE
# ============================================================

def focus_specific_tasks(focus, instrument, level):
    focus_l = str(focus).lower()

    if "rhythm" in focus_l or "strum" in focus_l or "timing" in focus_l:
        return """
## Focus-Specific Work: Rhythm / Timing
- Clap the section rhythm before playing.
- Practice with metronome at 60 BPM.
- Play only on beat 1, then beats 1 and 3, then all beats.
- Record one take and listen only for steadiness.
"""
    if "melody" in focus_l:
        return """
## Focus-Specific Work: Melody
- Say note names before playing.
- Play the melody in 2-measure chunks.
- Circle the highest and lowest notes.
- Add phrase shaping only after notes are secure.
"""
    if "chord" in focus_l or "voicing" in focus_l or "harmony" in focus_l:
        return """
## Focus-Specific Work: Chords / Harmony
- Play roots through the whole form.
- Then play 1–3–5 chord tones.
- Then connect the closest chord tones between chords.
- Identify the hardest chord transition and loop it.
"""
    if "tone" in focus_l or "breath" in focus_l or "articulation" in focus_l:
        return """
## Focus-Specific Work: Tone / Breath / Articulation
- Long tone on the first note of the melody.
- Play the phrase legato once, then articulated once.
- Record phrase endings and check if they weaken.
- Keep sound quality more important than speed.
"""
    if "improv" in focus_l:
        return """
## Focus-Specific Work: Improvisation
- Chorus 1: chord tones only.
- Chorus 2: add passing notes.
- Chorus 3: repeat one motif through the progression.
- End each phrase on a strong chord tone.
"""
    return """
## Focus-Specific Work
- Identify the hardest 2 measures.
- Practice them slowly 5 times.
- Record one take.
- Write one concrete improvement for tomorrow.
"""

def instrument_level_sheet_block(song_ctx, instrument, level, focus):
    title = song_ctx.get("title", "Current Song")
    progression = song_ctx.get("progression", []) or ["C", "G", "Am", "F"]
    loop = " | ".join(progression[:8])

    if instrument == "Piano":
        if level == "Beginner":
            return f"""
## Piano — Beginner Sheet for {title}
### Main Goal
Play simple right-hand melody with left-hand roots.

### Right Hand
- Practice the melody/extracted notes slowly.
- Use one finger position at a time.
- Do not add rhythm complexity yet.

### Left Hand
- Play one root note per chord.
- Chord loop: | {loop} |
- Hold each bass note for 4 beats.

### Both Hands
1. RH only.
2. LH only.
3. Both hands together at 60 BPM.
4. Keep RH louder than LH.
"""
        if level == "Intermediate":
            return f"""
## Piano — Intermediate Sheet for {title}
### Main Goal
Coordinate melody with shell voicings and smoother chord movement.

### Right Hand
- Play melody with phrase shaping.
- Add dynamics to phrase endings.

### Left Hand
- Use root + 5th first.
- Then use shell voicings: 1–3–7.
- Chord loop: | {loop} |

### Both Hands
- LH plays chords on beat 1.
- RH plays melody.
- Add light comping after the melody is secure.
"""
        return f"""
## Piano — Advanced Sheet for {title}
### Main Goal
Create an arrangement.

### Harmony
- Use inversions and rootless voicings.
- Add passing diminished or secondary dominant ideas only where musical.
- Practice in the displayed transposed key.

### Performance Tasks
- Intro: create 2 bars.
- Main form: melody on top.
- Second pass: reharmonize one cadence.
- Final pass: record full performance.
"""

    if instrument == "Guitar":
        if level == "Beginner":
            return f"""
## Guitar — Beginner Sheet for {title}
### Main Goal
Clean chord changes and steady strumming.

### Chords
- Practice the progression slowly: | {loop} |
- Switch between the first two chords 10 times.
- Then add the next chord.

### Strumming
- Start with downstrokes only.
- Count 1-2-3-4 out loud.
- Add down-up only when changes are clean.

### Melody
- Find short melody fragments on the top two strings.
"""
        if level == "Intermediate":
            return f"""
## Guitar — Intermediate Sheet for {title}
### Main Goal
Combine rhythm guitar, melody fragments, and chord tones.

### Chord Work
- Use open/barre shapes where appropriate.
- Practice two-chord loops.
- Add muted strums for groove.

### Lead Work
- Play chord tones over each chord.
- Connect melody fragments to nearby chord shapes.

### Strumming
- Keep right hand moving continuously.
- Accent beats 2 and 4.
"""
        return f"""
## Guitar — Advanced Sheet for {title}
### Main Goal
Build a chord-melody/performance version.

### Advanced Tasks
- Use triads on top three strings.
- Voice-lead between chord shapes.
- Put melody note on top of chord.
- Create one solo chorus using chord tones and approach notes.
"""

    if instrument in ["Saxophone", "Flute", "Trumpet"]:
        if level == "Beginner":
            return f"""
## {instrument} — Beginner Sheet for {title}
### Main Goal
Play the melody clearly with good tone.

### Melody
- Say note names first.
- Play 2 measures at a time.
- Use full tone on every note.

### Chords
- Play roots only through the chord chart.
- Then play root–third–fifth slowly.

### Tone
- Long tone on the first note for 8 beats.
"""
        if level == "Intermediate":
            return f"""
## {instrument} — Intermediate Sheet for {title}
### Main Goal
Connect melody, chord tones, and phrasing.

### Melody
- Add slurs and articulations.
- Mark breath points.
- Shape phrase endings.

### Chord Tones
- Play 1–3–5–7 over each chord.
- Create one 2-bar phrase using only chord tones.

### Timing
- Practice with backing track at slow tempo.
"""
        return f"""
## {instrument} — Advanced Sheet for {title}
### Main Goal
Use the song as an improvisation and interpretation study.

### Advanced Tasks
- Play melody straight.
- Play ornamented melody.
- Improvise one chorus using guide tones.
- Add chromatic approaches into chord tones.
- Record two versions with different phrasing.
"""

    if instrument == "Voice":
        return f"""
## Voice Sheet for {title} — {level}
### Main Goal
Pitch, breath, and phrasing.

- Sing melody on “la” first.
- Mark breaths.
- Practice pitch targets slowly.
- Speak the phrase naturally, then sing it.
- Record and check pitch center and expression.
"""

    return f"""
## {instrument} Sheet for {title} — {level}
- Learn melody in small chunks.
- Practice chord roots.
- Add rhythm slowly.
- Record one clean take.
"""

def generate_song_fitted_adaptive_sheet(song_ctx, instrument, level, focus):
    section_lines = []
    for s in song_ctx.get("sections", []):
        if isinstance(s, dict) and s.get("start") is not None:
            section_lines.append(f"- {s['label']}: measures {s['start']}–{s['end']}")
        elif isinstance(s, dict):
            section_lines.append(f"- {s.get('label','Section')}")
        else:
            section_lines.append(f"- {s}")
    sections_text = "\\n".join(section_lines) if section_lines else "- Main Form"

    return f"""
# Adaptive Practice Sheet — Fitted to {song_ctx.get('title','Current Song')}

**Song/source:** {song_ctx.get('title','Current Song')}  
**Artist/composer:** {song_ctx.get('artist','')}  
**Key/source key:** {song_ctx.get('key','')}  
**Instrument:** {instrument}  
**Level:** {level}  
**Focus:** {focus}

## Song Sections
{sections_text}

## Full Chord Chart
{song_ctx.get('chords_text','')}

## Melody / Extracted Notes
{song_ctx.get('melody_text','')}

{instrument_level_sheet_block(song_ctx, instrument, level, focus)}

{focus_specific_tasks(focus, instrument, level)}

## Daily Progression Rule
Each time you return to this song:
1. continue the same section,
2. add one harder transition,
3. increase the tempo slightly,
4. record one take,
5. write one specific weakness for tomorrow.
"""


# ============================================================
# DAILY PRACTICE PAGE: SONG-SPECIFIC CHORDS + NOTES
# ============================================================

def daily_song_specific_notes(song_ctx, instrument, level):
    progression = song_ctx.get("progression", []) or ["C", "G", "Am", "F"]
    melody_text = song_ctx.get("melody_text", "")
    title = song_ctx.get("title", "Current Song")

    if melody_text and "No melody" not in melody_text and "copyrighted melody is not reproduced" not in melody_text:
        melody_block = melody_text
    else:
        # Legal-safe original practice notes based on the current chord loop
        melody_block = " | ".join([
            f"{ch}: root–3rd–5th" for ch in progression[:8]
        ])

    if instrument == "Piano":
        instrument_notes = """
### Piano Notes to Practice
- RH: play the melody/extracted notes slowly.
- LH: play the root of each chord.
- Then play root + 5th.
- Then play simple triads.
- Intermediate/advanced: use inversions or shell voicings.
"""
    elif instrument == "Guitar":
        instrument_notes = """
### Guitar Notes / Shapes to Practice
- Strum each chord once per measure.
- Loop the hardest two-chord change.
- Practice muted strums before full chords.
- Then find melody fragments on the top two strings.
- Advanced: connect chord shapes with nearby triads.
"""
    elif instrument in ["Saxophone", "Flute", "Trumpet"]:
        instrument_notes = f"""
### {instrument} Notes to Practice
- Play the melody/extracted notes slowly.
- Then play roots of the chord progression.
- Then play 1–3–5 over each chord.
- Add articulation only after notes are secure.
- Advanced: improvise short phrases using chord tones.
"""
    else:
        instrument_notes = """
### Notes to Practice
- Melody first.
- Chord roots second.
- Rhythm third.
- Record one take.
"""

    return f"""
## Song-Specific Notes for {title}

### Melody / Exercise Notes
{melody_block}

{instrument_notes}
"""

def daily_full_chord_chart(song_ctx):
    return f"""
## Full Chord Chart for Today's Song

{song_ctx.get("chords_text", "| C | G | Am | F |")}
"""

def daily_song_exercises(song_ctx, instrument, level, focus):
    progression = song_ctx.get("progression", []) or ["C", "G", "Am", "F"]
    title = song_ctx.get("title", "Current Song")

    first_loop = " | ".join(progression[:4])
    second_loop = " | ".join(progression[4:8]) if len(progression) >= 8 else first_loop

    if level == "Beginner":
        level_ex = f"""
### Beginner Exercises for {title}
1. Say the chord names out loud: | {first_loop} |
2. Play only the first chord for 4 beats.
3. Add the second chord and loop the change 10 times.
4. Play the first 2 measures only.
5. Record one slow take.
"""
    elif level == "Intermediate":
        level_ex = f"""
### Intermediate Exercises for {title}
1. Practice section 1: | {first_loop} |
2. Practice next section/loop: | {second_loop} |
3. Play roots through the whole chart.
4. Play 1–3–5 chord tones through the whole chart.
5. Add dynamics, articulation, or strumming groove.
"""
    else:
        level_ex = f"""
### Advanced Exercises for {title}
1. Play the full chart in the selected key.
2. Identify repeated chord loops and cadences.
3. Create one variation for each section.
4. Improvise one chorus using chord tones.
5. Reharmonize or revoice one section.
6. Record a full performance take.
"""

    focus_ex = focus_specific_tasks(focus, instrument, level) if "focus_specific_tasks" in globals() else ""

    return f"""
## Targeted Exercises for This Specific Song

{level_ex}

{focus_ex}
"""


# ============================================================
# HARDER EXERCISE GENERATOR
# ============================================================

def harder_exercise_for_song(song_ctx, instrument, level, focus, current_difficulty=1):
    title = song_ctx.get("title", "Current Song")
    progression = song_ctx.get("progression", []) or ["C", "G", "Am", "F"]
    loop = " | ".join(progression[:8])

    next_level = current_difficulty + 1

    if instrument == "Piano":
        if next_level <= 2:
            exercise = f"""
## Harder Exercise Level {next_level} — Piano

### Song: {title}
### Chord Loop
| {loop} |

### Task
- LH: play root + fifth for each chord.
- RH: play melody/extracted notes.
- Add metronome at 70 BPM.
- Keep RH louder than LH.

### Challenge
Play the full loop 3 times without stopping.
"""
        elif next_level <= 4:
            exercise = f"""
## Harder Exercise Level {next_level} — Piano

### Song: {title}
### Chord Loop
| {loop} |

### Task
- LH: use shell voicings, 1–3–7.
- RH: play melody with phrase shaping.
- Add one passing tone into each chord change.
- Practice hands together at 80 BPM.

### Challenge
Record one clean take with dynamics.
"""
        else:
            exercise = f"""
## Harder Exercise Level {next_level} — Piano

### Song: {title}

### Advanced Task
- Create a short intro.
- Use inversions or rootless voicings.
- Reharmonize one cadence.
- Play one full performance version.
- Then play the same section in another key.

### Challenge
Make it sound like an arrangement, not an exercise.
"""

    elif instrument == "Guitar":
        if next_level <= 2:
            exercise = f"""
## Harder Exercise Level {next_level} — Guitar

### Song: {title}
### Chord Loop
| {loop} |

### Task
- Use down-up strumming.
- Accent beats 2 and 4.
- Loop the hardest chord change 10 times.
- Then play the full loop.

### Challenge
Keep the right hand moving the whole time.
"""
        elif next_level <= 4:
            exercise = f"""
## Harder Exercise Level {next_level} — Guitar

### Song: {title}

### Task
- Add muted strums.
- Use triads on the top three strings.
- Connect melody fragments to nearby chord shapes.
- Play one section as rhythm guitar, then one section as melody.

### Challenge
Record rhythm guitar only and check groove.
"""
        else:
            exercise = f"""
## Harder Exercise Level {next_level} — Guitar

### Song: {title}

### Advanced Task
- Build a chord-melody version of one section.
- Put melody notes on top of chords.
- Add passing chords where natural.
- Improvise one chorus using chord tones.

### Challenge
Make it sound like a solo guitar arrangement.
"""

    elif instrument in ["Saxophone", "Flute", "Trumpet"]:
        if next_level <= 2:
            exercise = f"""
## Harder Exercise Level {next_level} — {instrument}

### Song: {title}

### Task
- Play the extracted melody slowly.
- Then play chord roots through the form.
- Then play 1–3–5 over each chord.

### Challenge
Play with full tone and clean articulation.
"""
        elif next_level <= 4:
            exercise = f"""
## Harder Exercise Level {next_level} — {instrument}

### Song: {title}

### Task
- Play 1–3–5–7 over each chord.
- Add one passing tone between chord tones.
- Mark breath points.
- Play one phrase legato, then one phrase articulated.

### Challenge
Record and check tone stability at phrase endings.
"""
        else:
            exercise = f"""
## Harder Exercise Level {next_level} — {instrument}

### Song: {title}

### Advanced Task
- Improvise one chorus using guide tones.
- Add chromatic approaches.
- Create one repeated motif and move it through the changes.
- Play melody straight, then ornamented.

### Challenge
Make the solo sound connected to the actual song, not random scales.
"""

    else:
        exercise = f"""
## Harder Exercise Level {next_level}

### Song: {title}
### Chord Loop
| {loop} |

### Task
- Increase tempo by 10 BPM.
- Add one harder transition.
- Add dynamics.
- Record one full take.

### Challenge
Play the full section without stopping.
"""

    return exercise, next_level


# ============================================================
# FALLBACK SONG CONTEXT BUILDER
# ============================================================

def current_song_context_for_sheet():
    """
    Builds the current song context for daily practice/adaptive sheets.
    Safe fallback if no uploaded song or selected catalog song exists.
    """
    analysis = st.session_state.get("uploaded_analysis", None)

    if analysis:
        key = infer_key_from_notes(analysis.get("notes", []))
        if key == "Unknown":
            key = "C"

        try:
            sections = detect_sections(analysis)
        except Exception:
            sections = [{"label": "A", "start": 1, "end": 8}]

        try:
            chords_text = chord_chart_from_uploaded_analysis(
                analysis,
                st.session_state.get("transpose_to_key", key)
            )
        except Exception:
            try:
                chords_text = make_song_aware_chart(analysis, instrument, level)
            except Exception:
                chords_text = "| C | G | Am | F |"

        melody_lines = []
        try:
            for m in analysis.get("measures", [])[:16]:
                notes = [n.get("note", "") for n in m.get("notes", [])[:12]]
                notes = [n for n in notes if n]
                if notes:
                    melody_lines.append(f"Measure {m.get('number','')}: " + " ".join(notes))
        except Exception:
            pass

        try:
            progression = [c for c, b in accompaniment_from_analysis(analysis)[:16]]
        except Exception:
            progression = ["C", "G", "Am", "F"]

        return {
            "source": "uploaded",
            "title": analysis.get("title", "Uploaded Song"),
            "artist": "User-uploaded file",
            "key": key,
            "sections": sections,
            "chords_text": chords_text,
            "melody_text": "\\n".join(melody_lines) if melody_lines else "No melody extracted yet.",
            "progression": progression
        }

    selected_title = st.session_state.get("searched_song_title", "")
    if "SONG_CATALOG" in globals() and selected_title in SONG_CATALOG:
        data = SONG_CATALOG[selected_title]
        try:
            display_key = st.session_state.get("transpose_to_key", extract_key_root(data.get("key", "C")))
            chart = full_chord_chart_for_selected_song(selected_title, data, display_key)
        except Exception:
            chart = "| " + " | ".join(data.get("progression", ["C", "G", "Am", "F"])) + " |"

        return {
            "source": "catalog",
            "title": selected_title,
            "artist": data.get("artist", ""),
            "key": data.get("key", "C"),
            "sections": [{"label": sec, "start": None, "end": None} for sec in data.get("sections", {}).keys()] or [{"label": "Main Form", "start": None, "end": None}],
            "chords_text": chart,
            "melody_text": "Practice-style melody fragments only. Exact copyrighted melody is not reproduced.",
            "progression": data.get("progression", ["C", "G", "Am", "F"])
        }

    # If no selected/uploaded song exists, use the current backing loop or a default loop.
    progression = [c for c, b in st.session_state.get("selected_chords", [("C",1), ("G",1), ("Am",1), ("F",1)])]
    if not progression:
        progression = ["C", "G", "Am", "F"]

    return {
        "source": "fallback",
        "title": st.session_state.get("searched_song_title", "Current Practice Song") or "Current Practice Song",
        "artist": st.session_state.get("searched_song_artist", ""),
        "key": st.session_state.get("transpose_to_key", "C"),
        "sections": [{"label": "Main Form", "start": None, "end": None}],
        "chords_text": "| " + " | ".join(progression) + " |",
        "melody_text": "Use chord tones for each chord: root–3rd–5th. Upload MIDI/MusicXML for extracted melody notes.",
        "progression": progression
    }

# ============================================================
# UI
# ============================================================

if "uploaded_analysis" not in st.session_state:
    st.session_state.uploaded_analysis = None
if "selected_chords" not in st.session_state:
    st.session_state.selected_chords = [("C",1), ("G",1), ("Am",1), ("F",1)]
if "selected_original_key" not in st.session_state:
    st.session_state.selected_original_key = "C"
if "transpose_to_key" not in st.session_state:
    st.session_state.transpose_to_key = "C"
if "harder_exercise_level" not in st.session_state:
    st.session_state.harder_exercise_level = 1
if "last_harder_exercise" not in st.session_state:
    st.session_state.last_harder_exercise = ""
if "multitrack_recordings" not in st.session_state:
    st.session_state.multitrack_recordings = {
        "Track 1": None,
        "Track 2": None,
        "Track 3": None,
    }
if "multitrack_names" not in st.session_state:
    st.session_state.multitrack_names = {
        "Track 1": "Instrument 1",
        "Track 2": "Instrument 2",
        "Track 3": "Instrument 3",
    }

st.sidebar.title("Setup")
instrument = st.sidebar.selectbox("Instrument", INSTRUMENTS)
level = st.sidebar.selectbox("Level", ["Beginner", "Intermediate", "Advanced"])
focus = st.sidebar.selectbox("Focus", SKILLS[instrument])
minutes = st.sidebar.slider("Practice minutes", 10, 120, 30, 5)
st.sidebar.subheader("Transpose")
transpose_to_key = st.sidebar.selectbox("Transpose/display key", COMMON_KEYS, index=COMMON_KEYS.index(st.session_state.get("transpose_to_key", "C")) if st.session_state.get("transpose_to_key", "C") in COMMON_KEYS else 0)
st.session_state.transpose_to_key = transpose_to_key

st.sidebar.subheader("OpenAI API Key")
typed_key = st.sidebar.text_input("Enter OpenAI API Key", value=st.session_state.openai_api_key_ui, type="password")
if typed_key:
    st.session_state.openai_api_key_ui = typed_key.strip()
    st.sidebar.success("API key entered for this session.")
else:
    st.sidebar.info("Optional. Leave blank to use non-AI mode.")

tabs = st.tabs([
    "Practice Memory",
    "Song Search",
    "Daily Practice Plan",
    "Song-Aware MIDI/MusicXML",
    "Section Playback / Backing Track",
    "Practice Sheet",
    "Multitrack Recorder",
    "Log"
])

with tabs[0]:
    st.header("Practice Memory")
    if st.button("Reset Practice Memory to Default"):
        save_history({"logs": []})
        st.session_state.uploaded_analysis = None
        st.session_state.selected_chords = [("C",1), ("G",1), ("Am",1), ("F",1)]
        st.success("Practice memory reset to default.")
    logs = recent_logs(50)
    if logs:
        st.dataframe(pd.DataFrame(logs), use_container_width=True)
    else:
        st.info("No practice logs yet.")


with tabs[1]:
    st.header("Song Search")
    st.write(
        "Type a song title, artist, or style. A dropdown list of similar songs will appear. "
        "This helps the user choose the song before generating practice materials or backing tracks."
    )

    selected_title, selected_data = render_song_search_dropdown("main_song_search")

    if selected_title and selected_data:
        st.subheader("Selected Song Preview")
        st.write(f"**Song:** {selected_title}")
        st.write(f"**Artist:** {selected_data.get('artist','')}")
        st.write(f"**Style:** {selected_data.get('style','')}")

        st.markdown(simple_selected_song_practice_sheet(selected_title, selected_data, instrument, level))
        # If this song exists in the detailed catalog, always show all chord sections and allow transposition.
        if "SONG_CATALOG" in globals() and selected_title in SONG_CATALOG:
            st.subheader("Full Chord Chart / Transposed")
            st.markdown(full_chord_chart_for_selected_song(selected_title, SONG_CATALOG[selected_title], st.session_state.transpose_to_key))

        if st.button("Use this song idea for practice memory", key="save_selected_song_to_memory"):
            add_log({
                "date": str(date.today()),
                "instrument": instrument,
                "focus": focus,
                "rating": 6,
                "note": f"Selected song from dropdown: {selected_title} by {selected_data.get('artist','')}"
            })
            st.success("Saved selected song to practice memory.")



with tabs[2]:
    st.header("Daily Practice Plan")
    st.write("Today's plan is fitted to the selected/uploaded song, with all chords, song-specific notes, and targeted exercises.")

    song_ctx = current_song_context_for_sheet()
    st.markdown(daily_full_chord_chart(song_ctx))
    st.markdown(daily_song_specific_notes(song_ctx, instrument, level))
    st.markdown(daily_song_exercises(song_ctx, instrument, level, focus))

    st.subheader("Need Something Harder?")
    st.write("If the current exercise is too easy, press the button and the app will generate a harder song-specific exercise.")
    if st.button("Generate a harder exercise"):
        harder, new_level = harder_exercise_for_song(
            song_ctx,
            instrument,
            level,
            focus,
            st.session_state.get("harder_exercise_level", 1)
        )
        st.session_state.harder_exercise_level = new_level
        st.session_state.last_harder_exercise = harder
        add_log({
            "date": str(date.today()),
            "instrument": instrument,
            "focus": focus,
            "rating": 6,
            "note": f"Generated harder exercise level {new_level} for {song_ctx.get('title','Current Song')}"
        })

    if st.session_state.get("last_harder_exercise", ""):
        st.markdown(st.session_state.last_harder_exercise)

    if st.button("Reset harder exercise level"):
        st.session_state.harder_exercise_level = 1
        st.session_state.last_harder_exercise = ""
        st.success("Harder exercise level reset.")

    st.subheader("Daily Timing Plan")
    warmup = max(5, int(minutes * 0.20))
    songwork = max(10, int(minutes * 0.50))
    recording = max(5, minutes - warmup - songwork)

    st.write(f"**Warmup — {warmup} minutes:** focus on {focus}.")
    st.write(f"**Song work — {songwork} minutes:** practice the chord chart and song-specific notes above.")
    st.write(f"**Record/review — {recording} minutes:** record one take and write one specific weakness.")

    if st.button("Save today's daily plan to practice memory"):
        add_log({
            "date": str(date.today()),
            "instrument": instrument,
            "focus": focus,
            "rating": 6,
            "note": f"Daily plan for {song_ctx.get('title','Current Song')}"
        })
        st.success("Saved today's song-specific daily plan.")


with tabs[3]:
    st.header("Song-Aware MIDI/MusicXML Integration")
    st.write("Upload a MIDI, MusicXML, or MXL file that you own, created, licensed, or are allowed to use.")
    uploaded = st.file_uploader("Upload MIDI / MusicXML / MXL", type=["mid","midi","xml","musicxml","mxl"])
    if uploaded is not None:
        fname = uploaded.name.lower()
        if fname.endswith((".xml",".musicxml",".mxl")):
            analysis = parse_musicxml_detailed(uploaded)
        else:
            analysis = parse_midi_detailed(uploaded)

        if "error" in analysis:
            st.error(analysis["error"])
        else:
            st.session_state.uploaded_analysis = analysis
            st.success(analysis["summary"])

            chart = make_song_aware_chart(analysis, instrument, level)
            st.markdown(chart)

            st.subheader("Full Chord Chart / Transposed")
            st.markdown(chord_chart_from_uploaded_analysis(analysis, st.session_state.transpose_to_key))

            abc = abc_from_analysis(analysis, instrument, level)
            st.subheader("Extracted Melody Notation")
            render_abc(abc)

            st.download_button("Download song-aware chart", chart, file_name="song_aware_chart.txt")
            st.download_button("Download extracted notation ABC", abc, file_name="extracted_notation.abc")

            original_key = infer_key_from_notes(analysis.get("notes", []))
            if original_key == "Unknown":
                original_key = "C"
            st.session_state.selected_original_key = original_key
            raw_chords = accompaniment_from_analysis(analysis)
            st.session_state.selected_chords = transposed_chords_for_backing(raw_chords, original_key, st.session_state.transpose_to_key)
            st.info(f"Accompaniment chords generated from uploaded file and transposed to {st.session_state.transpose_to_key}.")

with tabs[4]:
    st.header("Section-Based Playback / Real Accompaniment Generation")
    analysis = st.session_state.uploaded_analysis
    selected_section = None
    if analysis:
        sections = detect_sections(analysis)
        if sections:
            labels = [f"{s['label']} — measures {s['start']}–{s['end']}" for s in sections]
            label = st.selectbox("Choose section", labels)
            selected_section = sections[labels.index(label)]
            st.write(f"Selected: **{selected_section['label']}**, measures {selected_section['start']}–{selected_section['end']}")
            section_chords_raw = accompaniment_from_analysis(analysis, selected_section)
            original_key = infer_key_from_notes(analysis.get("notes", []))
            if original_key == "Unknown":
                original_key = "C"
            section_chords = transposed_chords_for_backing(section_chords_raw, original_key, st.session_state.transpose_to_key)
            st.session_state.selected_chords = section_chords
            st.write(f"Section chord loop in {st.session_state.transpose_to_key}: | " + " | ".join([c for c,b in section_chords]) + " |")
    else:
        st.info("Upload a MIDI/MusicXML file or select a public-domain song first.")

    st.subheader("Generate Backing Track")

    with st.expander("Optional: choose a song idea from dropdown"):
        bt_title, bt_data = render_song_search_dropdown("backing_song_search")
        if bt_title:
            st.caption(
                "This selects the song/style idea. For exact melody/chords, upload MIDI/MusicXML in the Song-Aware tab."
            )

    bpm = st.slider("BPM", 50, 180, 100, step=5)
    choruses = st.slider("Choruses", 1, 8, 3)
    st.write(f"Current chord loop in {st.session_state.transpose_to_key}: | " + " | ".join([c for c,b in st.session_state.selected_chords]) + " |")
    if st.button("Generate accompaniment from current song/section"):
        wav = backing_track_from_chords(st.session_state.selected_chords, bpm=bpm, choruses=choruses, count_in=True)
        st.audio(wav, format="audio/wav")
        st.download_button("Download backing track WAV", wav, file_name="song_aware_backing_track.wav", mime="audio/wav")

with tabs[5]:
    st.header("Adaptive Practice Sheet")
    st.write("This sheet now fits the actual selected/uploaded song context: sections, chords, melody/extracted notes, key, instrument, and level.")

    song_ctx = current_song_context_for_sheet()
    fitted_sheet = generate_song_fitted_adaptive_sheet(song_ctx, instrument, level, focus)
    st.markdown(fitted_sheet)

    st.download_button(
        "Download song-fitted adaptive practice sheet",
        data=fitted_sheet,
        file_name=f"{song_ctx['title'].replace(' ','_')}_{instrument}_{level}_adaptive_sheet.txt",
        mime="text/plain"
    )


with tabs[6]:
    st.header("Multitrack Recorder")
    st.write("Record or upload up to 3 instrument tracks. You can listen back to each one separately while practicing.")

    st.caption("Prototype: this stores tracks during the current app session. Future upgrade can mix/export all tracks together.")

    for track_label in ["Track 1", "Track 2", "Track 3"]:
        st.subheader(track_label)

        col_a, col_b = st.columns([1, 1])
        with col_a:
            inst_name = st.text_input(
                f"Instrument name for {track_label}",
                value=st.session_state.multitrack_names.get(track_label, track_label),
                key=f"{track_label}_name"
            )
            st.session_state.multitrack_names[track_label] = inst_name

        with col_b:
            uploaded_track = st.file_uploader(
                f"Upload audio for {track_label}",
                type=["wav", "mp3", "m4a", "ogg"],
                key=f"{track_label}_upload"
            )

        recorded_track = None
        try:
            recorded_track = st.audio_input(f"Record {track_label}", key=f"{track_label}_record")
        except Exception:
            st.caption("Direct microphone recording may not be available in this Streamlit version. You can upload audio instead.")

        if st.button(f"Save {track_label}", key=f"{track_label}_save"):
            audio_obj = recorded_track if recorded_track is not None else uploaded_track
            if audio_obj is not None:
                st.session_state.multitrack_recordings[track_label] = audio_obj.getvalue()
                st.success(f"{track_label} saved.")
            else:
                st.warning(f"Record or upload audio for {track_label} first.")

        saved_audio = st.session_state.multitrack_recordings.get(track_label)
        if saved_audio:
            st.write(f"Playback: **{st.session_state.multitrack_names.get(track_label, track_label)}**")
            st.audio(saved_audio)

    st.divider()

    if st.button("Clear all 3 tracks"):
        st.session_state.multitrack_recordings = {
            "Track 1": None,
            "Track 2": None,
            "Track 3": None,
        }
        st.success("All multitrack recordings cleared.")

    st.subheader("How to Use")
    st.write("""
1. Generate or play a backing track.
2. Record Track 1, for example guitar.
3. Play Track 1 back while recording Track 2, for example saxophone.
4. Add Track 3, for example voice, piano, or another instrument.
5. Listen back to each track and decide what to improve.
""")


with tabs[7]:
    st.header("Practice Log")
    with st.form("log_form"):
        d = st.date_input("Date", date.today())
        note = st.text_area("What did you practice?")
        rating = st.slider("How did it feel?", 1, 10, 6)
        submitted = st.form_submit_button("Save log")
    if submitted:
        add_log({"date": str(d), "instrument": instrument, "focus": focus, "rating": rating, "note": note})
        st.success("Saved.")
