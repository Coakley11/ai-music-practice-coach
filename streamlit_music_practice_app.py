# VERSION: v37_api_midi_recording_restored

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import io
import json
import wave
import difflib
import tempfile
import os
from pathlib import Path
from datetime import date

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

try:
    import pretty_midi
except Exception:
    pretty_midi = None

try:
    import librosa
except Exception:
    librosa = None

st.set_page_config(page_title="Daniel Cohen AI Music Practice Coach", page_icon="🎵", layout="wide")

DATA_FILE = Path("practice_history.json")

GENRES = ["Jazz", "Pop", "Rock", "Funk", "Blues", "Classical", "Jewish / Klezmer"]
COMMON_KEYS = ["C","Db","D","Eb","E","F","Gb","G","Ab","A","Bb","B"]
CHROMATIC = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"]
FLAT_TO_SHARP = {"Db":"C#","Eb":"D#","Gb":"F#","Ab":"G#","Bb":"A#"}
NOTE_TO_MIDI = {"C":60,"C#":61,"Db":61,"D":62,"D#":63,"Eb":63,"E":64,"F":65,"F#":66,"Gb":66,"G":67,"G#":68,"Ab":68,"A":69,"A#":70,"Bb":70,"B":71}

SONG_LIBRARY = {
    "Jazz": {
        "Autumn Leaves": {"artist":"Joseph Kosma / Jazz Standard","key":"G","sections":{"A Section":["Cm7","F7","Bbmaj7","Ebmaj7","Am7b5","D7","Gm7","Gm7"],"B Section":["Cm7","F7","Bbmaj7","Ebmaj7","Am7b5","D7","Gm7","D7"]},"guitar_tabs":{"Cm7":"x35343","F7":"131211","Bbmaj7":"x13231","Ebmaj7":"x68786","Am7b5":"5x554x","D7":"xx0212","Gm7":"353333"}},
        "Blue Bossa": {"artist":"Kenny Dorham","key":"C","sections":{"A Section":["Cm7","Fm7","Dm7b5","G7","Cm7","Cm7"],"B Section":["Ebm7","Ab7","Dbmaj7","Dbmaj7","Dm7b5","G7","Cm7","G7"]},"guitar_tabs":{"Cm7":"x35343","Fm7":"131111","Dm7b5":"x5656x","G7":"320001","Ebm7":"x68676","Ab7":"464544","Dbmaj7":"x46564"}},
        "So What": {"artist":"Miles Davis","key":"D","sections":{"A Section":["Dm7"]*8,"Bridge":["Ebm7"]*8,"Final A":["Dm7"]*8},"guitar_tabs":{"Dm7":"x57565","Ebm7":"x68676"}},
        "All The Things You Are": {"artist":"Jerome Kern","key":"Ab","sections":{"A1":["Fm7","Bbm7","Eb7","Abmaj7","Dbmaj7","Dm7b5","G7","Cmaj7"],"A2":["Cm7","Fm7","Bb7","Ebmaj7","Abmaj7","Am7b5","D7","Gmaj7"],"Bridge":["Am7","D7","Gmaj7","Gmaj7","F#m7","B7","Emaj7","C7"]},"guitar_tabs":{"Fm7":"131111","Bbm7":"x13121","Eb7":"x68686","Abmaj7":"4x554x","Dbmaj7":"x46564","G7":"320001","Cmaj7":"x32000"}},
        "Take Five": {"artist":"Paul Desmond","key":"Eb","sections":{"Main Vamp":["Ebm7","Bbm7","Ebm7","Bbm7"],"Bridge":["Cbmaj7","Bbm7","Abm7","Bbm7"]},"guitar_tabs":{"Ebm7":"x68676","Bbm7":"686666","Cbmaj7":"x35453","Abm7":"464444"}},
    },
    "Pop": {
        "Say": {"artist":"John Mayer","key":"D","sections":{"Verse / Main Loop":["D","A","Bm","G"],"Chorus":["D","A","G","D"],"Bridge":["Bm","A","G","D"],"Final Chorus":["D","A","G","D"]},"guitar_tabs":{"D":"xx0232","A":"x02220","Bm":"x24432","G":"320003"}},
        "Gravity": {"artist":"John Mayer","key":"G","sections":{"Verse":["G","C","G","D"],"Lift":["Em","C","G","D"],"Solo Section":["G7","C7","G7","D7"]},"guitar_tabs":{"G":"320003","C":"x32010","D":"xx0232","Em":"022000","G7":"320001","C7":"x32310","D7":"xx0212"}},
        "Daughters": {"artist":"John Mayer","key":"B","sections":{"Verse":["B","F#","G#m","E"],"Chorus":["E","B","F#","B"],"Bridge":["G#m","F#","E","B"]},"guitar_tabs":{"B":"x24442","F#":"244322","G#m":"466444","E":"022100"}},
        "Waiting on the World to Change": {"artist":"John Mayer","key":"D","sections":{"Verse":["D","Bm","G","A"],"Chorus":["D","Bm","G","A"],"Bridge":["Em","G","D","A"]},"guitar_tabs":{"D":"xx0232","Bm":"x24432","G":"320003","A":"x02220","Em":"022000"}},
        "Piano Man": {"artist":"Billy Joel","key":"C","sections":{"Verse":["C","G","F","C"],"Chorus":["F","C","G","C"],"Turnaround":["Am","D7","G","G"]},"guitar_tabs":{"C":"x32010","G":"320003","F":"133211","Am":"x02210","D7":"xx0212"}},
        "Vienna": {"artist":"Billy Joel","key":"Bb","sections":{"Verse":["Bb","Dm","Eb","F"],"Chorus":["Gm","Eb","Bb","F"],"Bridge":["Cm","F","Bb","Gm"]},"guitar_tabs":{"Bb":"x13331","Dm":"xx0231","Eb":"x68886","F":"133211","Gm":"355333","Cm":"x35543"}},
        "Just the Way You Are": {"artist":"Billy Joel","key":"D","sections":{"Verse":["Dmaj7","Bm7","Gmaj7","A7"],"Chorus":["Gmaj7","F#m7","Em7","A7"],"Bridge":["Bbmaj7","C7","Fmaj7","A7"]},"guitar_tabs":{"Dmaj7":"xx0222","Bm7":"x24232","Gmaj7":"3x443x","A7":"x02020","F#m7":"242222","Em7":"022030"}},
        "Shape of You": {"artist":"Ed Sheeran","key":"C#","sections":{"Verse":["C#m","F#m","A","B"],"Pre-Chorus":["C#m","F#m","A","B"],"Chorus":["C#m","F#m","A","B"]},"guitar_tabs":{"C#m":"x46654","F#m":"244222","A":"x02220","B":"x24442"}},
        "Perfect": {"artist":"Ed Sheeran","key":"G","sections":{"Verse":["G","Em","C","D"],"Pre-Chorus":["Em","C","G","D"],"Chorus":["G","D","Em","C"]},"guitar_tabs":{"G":"320003","Em":"022000","C":"x32010","D":"xx0232"}},
        "Viva La Vida": {"artist":"Coldplay","key":"Ab","sections":{"Verse / Main Loop":["Db","Eb","Ab","Fm"],"Chorus":["Db","Eb","Ab","Fm"],"Bridge":["Db","Eb","Ab","Ab"]},"guitar_tabs":{"Db":"x46664","Eb":"x68886","Ab":"466544","Fm":"133111"}},
        "Let It Be": {"artist":"The Beatles","key":"C","sections":{"Verse":["C","G","Am","F"],"Chorus":["C","G","F","C"],"Bridge":["Am","G","F","C"]},"guitar_tabs":{"C":"x32010","G":"320003","Am":"x02210","F":"133211"}},
    },
    "Rock": {
        "Don't Stop Believin'": {"artist":"Journey","key":"E","sections":{"Low Part / Verse":["E","B","C#m","A"],"Pre-Chorus":["A","E","B","C#m"],"High Part / Chorus":["E","B","A","E"],"Final Chorus":["E","B","A","E"]},"guitar_tabs":{"E":"022100","B":"x24442","C#m":"x46654","A":"x02220"}},
        "Open Arms": {"artist":"Journey","key":"D","sections":{"Verse":["D","A","Bm","G"],"Chorus":["G","D","Em","A"],"Bridge":["Bm","F#m","G","A"]},"guitar_tabs":{"D":"xx0232","A":"x02220","Bm":"x24432","G":"320003","Em":"022000","F#m":"244222"}},
        "Hey Jude": {"artist":"The Beatles","key":"F","sections":{"Verse":["F","C","C7","F"],"Chorus":["Bb","F","C7","F"],"Na-Na Outro":["F","Eb","Bb","F"]},"guitar_tabs":{"F":"133211","C":"x32010","C7":"x32310","Bb":"x13331","Eb":"x68886"}},
        "Here Comes the Sun": {"artist":"The Beatles","key":"A","sections":{"Verse":["A","D","E","A"],"Chorus":["D","B7","E","E"],"Bridge":["F","C","G","D"]},"guitar_tabs":{"A":"x02220","D":"xx0232","E":"022100","B7":"x21202","F":"133211","C":"x32010","G":"320003"}},
        "Wonderwall": {"artist":"Oasis","key":"Em","sections":{"Verse":["Em7","G","Dsus4","A7sus4"],"Chorus":["Cadd9","Dsus4","Em7","G"],"Bridge":["Cadd9","Em7","G","Dsus4"]},"guitar_tabs":{"Em7":"022033","G":"320033","Dsus4":"xx0233","A7sus4":"x02033","Cadd9":"x32033"}},
    },
    "Funk": {
        "Superstition": {"artist":"Stevie Wonder","key":"Eb","sections":{"Main Groove":["Ebm7","Ebm7","Ebm7","Ebm7"],"Chorus":["Ab7","Gb7","Ebm7","Ebm7"]},"guitar_tabs":{"Ebm7":"x68676","Ab7":"464544","Gb7":"242322"}},
        "Cissy Strut": {"artist":"The Meters","key":"C","sections":{"Main Funk Vamp":["C7","C7","C7","C7"],"Turnaround":["F7","Eb7","C7","C7"]},"guitar_tabs":{"C7":"x32310","F7":"131211","Eb7":"x68686"}},
        "Chameleon": {"artist":"Herbie Hancock","key":"Bb","sections":{"Bass Vamp":["Bbm7","Bbm7","Bbm7","Bbm7"],"Bridge":["Eb7","Db7","Bbm7","Bbm7"]},"guitar_tabs":{"Bbm7":"686666","Eb7":"x68686","Db7":"x46464"}},
    },
    "Blues": {
        "12-Bar Blues in F": {"artist":"Traditional","key":"F","sections":{"Bars 1-4":["F7","Bb7","F7","F7"],"Bars 5-8":["Bb7","Bb7","F7","F7"],"Bars 9-12":["C7","Bb7","F7","C7"]},"guitar_tabs":{"F7":"131211","Bb7":"x13131","C7":"x32310"}},
        "Sweet Home Chicago": {"artist":"Robert Johnson / Blues Standard","key":"E","sections":{"12-Bar Form":["E7","A7","E7","E7","A7","A7","E7","E7","B7","A7","E7","B7"]},"guitar_tabs":{"E7":"020100","A7":"x02020","B7":"x21202"}},
        "The Thrill Is Gone": {"artist":"B.B. King","key":"Bm","sections":{"Minor Blues":["Bm","Em","Bm","Bm","Em","Em","Bm","Bm","G","F#7","Bm","F#7"]},"guitar_tabs":{"Bm":"x24432","Em":"022000","G":"320003","F#7":"242322"}},
    },
    "Classical": {
        "Ode to Joy": {"artist":"Beethoven","key":"D","sections":{"Main Theme":["D","A","D","G","D","A","D"],"Variation":["D","G","A","D"]},"guitar_tabs":{"D":"xx0232","A":"x02220","G":"320003"}},
        "Canon Style Practice": {"artist":"Classical Practice","key":"D","sections":{"Main Progression":["D","A","Bm","F#m","G","D","G","A"],"Variation":["D","A","Bm","F#m","G","D","G","A"]},"guitar_tabs":{"D":"xx0232","A":"x02220","Bm":"x24432","F#m":"244222","G":"320003"}},
    },
    "Jewish / Klezmer": {
        "Hava Nagila": {"artist":"Traditional","key":"Dm","sections":{"A Section":["Dm","A7","Dm","A7"],"B Section":["Gm","Dm","A7","Dm"],"Dance Loop":["Dm","Gm","A7","Dm"]},"guitar_tabs":{"Dm":"xx0231","A7":"x02020","Gm":"355333"}},
        "Siman Tov Mazel Tov": {"artist":"Traditional","key":"Am","sections":{"Main":["Am","E7","Am","E7"],"Chorus":["Dm","Am","E7","Am"]},"guitar_tabs":{"Am":"x02210","E7":"020100","Dm":"xx0231"}},
    },
}

def normalize_root(root): return FLAT_TO_SHARP.get(root, root)
def split_chord(chord):
    chord = str(chord)
    if len(chord) >= 2 and chord[1] in ["b", "#"]:
        return chord[:2], chord[2:]
    return chord[:1], chord[1:]
def semitone_distance(from_key, to_key):
    a = normalize_root(split_chord(from_key)[0])
    b = normalize_root(split_chord(to_key)[0])
    if a not in CHROMATIC or b not in CHROMATIC: return 0
    return (CHROMATIC.index(b) - CHROMATIC.index(a)) % 12
def transpose_chord(chord, steps):
    root, suffix = split_chord(chord)
    root = normalize_root(root)
    if root not in CHROMATIC: return chord
    return CHROMATIC[(CHROMATIC.index(root)+steps)%12] + suffix
def transpose_sections(song_data, target_key):
    steps = semitone_distance(song_data["key"], target_key)
    return {sec:[transpose_chord(ch, steps) for ch in chords] for sec, chords in song_data["sections"].items()}
def all_chords_from_sections(sections):
    out = []
    for chords in sections.values(): out.extend(chords)
    return out
def chord_notes(chord):
    root = split_chord(chord)[0]
    base = NOTE_TO_MIDI.get(root, 60)
    low = str(chord).lower()
    if "m7b5" in low: ints=[0,3,6,10]
    elif "maj7" in low: ints=[0,4,7,11]
    elif "m7" in low: ints=[0,3,7,10]
    elif "m" in low and "maj" not in low: ints=[0,3,7]
    elif "7" in low: ints=[0,4,7,10]
    else: ints=[0,4,7]
    return [base+i for i in ints]
def midi_note_name(m):
    names=["C","C#","D","Eb","E","F","F#","G","Ab","A","Bb","B"]
    return names[m%12]
def abc_note(m):
    names=["C","^C","D","_E","E","F","^F","G","_A","A","_B","B"]
    return names[m%12]
def render_abc(abc_text):
    escaped = abc_text.replace("\\","\\\\").replace("`","\\`").replace("${","\\${")
    html=f"""<html><head><script src="https://cdn.jsdelivr.net/npm/abcjs@6.4.4/dist/abcjs-basic-min.js"></script></head><body><div id="paper"></div><script>ABCJS.renderAbc("paper", `{escaped}`, {{responsive:"resize", staffwidth:760}});</script></body></html>"""
    components.html(html, height=350, scrolling=True)
def build_abc(song_name, sections):
    chords=all_chords_from_sections(sections)[:8]
    melody=[]
    for ch in chords:
        mids=chord_notes(ch)
        melody += [abc_note(mids[0]), abc_note(mids[min(1,len(mids)-1)]), abc_note(mids[min(2,len(mids)-1)]), abc_note(mids[0])]
    bars=[" ".join(melody[i:i+4]) for i in range(0,len(melody),4)]
    return f"""X:1\nT:{song_name}\nM:4/4\nL:1/4\nK:C\n{" | ".join(bars)} |\n"""
def load_logs():
    if DATA_FILE.exists():
        try: return json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except Exception: return []
    return []
def save_logs(logs): DATA_FILE.write_text(json.dumps(logs, indent=2), encoding="utf-8")
def full_chord_markdown(song_name, song_data, sections, instrument):
    out=[f"## Full Song Chords — {song_name}", f"Artist/composer: **{song_data['artist']}**", f"Original key: **{song_data['key']}**"]
    for section, chords in sections.items():
        out.append(f"\n### {section}")
        out.append("| " + " | ".join(chords) + " |")
    if instrument == "Guitar":
        out.append("\n## Guitar Chord Shapes / Tablature-Style Fret Numbers")
        tabs=song_data.get("guitar_tabs",{})
        for chord, tab in tabs.items():
            out.append(f"- {chord}: `{tab}`")
        out.append("\nString order is low E to high E. Example: `xx0232` means mute low E/A, then frets 0-2-3-2.")
    if instrument in ["Saxophone","Flute","Trumpet"]:
        out.append(f"\n## {instrument} Chord-Tone Notes")
        for section, chords in sections.items():
            out.append(f"\n**{section}**")
            for ch in chords:
                out.append(f"- {ch}: " + " – ".join(midi_note_name(n) for n in chord_notes(ch)[:4]))
    return "\n".join(out)
def practice_text(level):
    if level=="Beginner":
        return "### Beginner Focus\n- Practice one section at a time.\n- Say chord names aloud.\n- Slow tempo, simple rhythm only.\n- Use roots and simple chord tones."
    if level=="Intermediate":
        return "### Intermediate Focus\n- Practice the whole form by sections.\n- Use roots, 3rds, 5ths, and 7ths.\n- Add phrasing and rhythm.\n- Record one full section."
    return "### Advanced Focus\n- Practice the full form.\n- Use guide tones, inversions, voice-leading, and variations.\n- Improvise one chorus.\n- Record a performance-level take."
def score_song(query_title, query_artist, title, data):
    q = (query_title + " " + query_artist).lower().strip()
    hay = (title + " " + data.get("artist","")).lower()
    if not q: return 1
    score = 0
    if query_title.lower() in title.lower(): score += 70
    if query_artist.lower() and query_artist.lower() in data.get("artist","").lower(): score += 70
    for w in q.split():
        if w in hay: score += 10
    score += int(35*difflib.SequenceMatcher(None, q, hay).ratio())
    return score
def song_matches(genre, query_title="", query_artist="", limit=20):
    scored=[]
    for title,data in SONG_LIBRARY[genre].items():
        scored.append((score_song(query_title, query_artist, title, data), title, data))
    scored.sort(reverse=True, key=lambda x:x[0])
    return [(title,data) for score,title,data in scored[:limit] if score > 0]
def generate_backing_track(chords, bpm=100, repeats=1):
    chords = chords * repeats
    sr=44100; beat=60/bpm; bar=beat*4
    audio=np.zeros(int(sr*bar*len(chords)))
    def freq(m): return 440*(2**((m-69)/12))
    def tone(f,d,v=.1):
        t=np.linspace(0,d,int(sr*d),False)
        sig=np.sin(2*np.pi*f*t)+.25*np.sin(2*np.pi*2*f*t)
        env=np.linspace(1,.05,len(sig))
        return sig*env*v
    def add(start_s,sig):
        i=int(start_s*sr); e=min(len(audio),i+len(sig))
        if e>i: audio[i:e]+=sig[:e-i]
    cur=0
    for ch in chords:
        mids=chord_notes(ch)
        for b in range(4):
            add(cur+b*beat, tone(freq(mids[0]-24), beat*.8, .18))
            for m in mids[:3]: add(cur+b*beat, tone(freq(m+12), beat*.25, .05))
        cur += bar
    audio=np.tanh(audio)
    audio=audio/(np.max(np.abs(audio))+1e-9)*.8
    out=io.BytesIO()
    with wave.open(out,"wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
        wf.writeframes((audio*32767).astype(np.int16).tobytes())
    out.seek(0)
    return out.getvalue()


# -----------------------------
# API / MIDI / RECORDING HELPERS
# -----------------------------

def get_openai_client():
    key = st.session_state.get("openai_api_key_ui", "").strip()
    if not key:
        key = os.environ.get("OPENAI_API_KEY", "")
        try:
            key = st.secrets.get("OPENAI_API_KEY", key)
        except Exception:
            pass
    if key and OpenAI is not None:
        return OpenAI(api_key=key)
    return None

def api_song_suggestions(genre, title_query, artist_query):
    client = get_openai_client()
    if client is None:
        return None
    try:
        prompt = f"""
Give 12 {genre} songs matching this search.
Title search: {title_query}
Artist/composer search: {artist_query}

Return concise plain text lines only:
Song Title — Artist/Composer — Style
Do not include copyrighted lyrics or melodies.
"""
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"user","content":prompt}],
            temperature=0.4,
            max_tokens=350,
        )
        return resp.choices[0].message.content
    except Exception as e:
        return f"API suggestion error: {e}"

def analyze_uploaded_midi(uploaded_file):
    if uploaded_file is None:
        return None
    if pretty_midi is None:
        return {"error": "pretty_midi is not installed. Add pretty_midi to requirements.txt for MIDI analysis."}
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mid")
    try:
        tmp.write(uploaded_file.getvalue())
        tmp.close()
        pm = pretty_midi.PrettyMIDI(tmp.name)
        notes = []
        for inst in pm.instruments:
            if inst.is_drum:
                continue
            for n in inst.notes[:300]:
                notes.append({
                    "pitch": int(n.pitch),
                    "note": midi_note_name(int(n.pitch)),
                    "start": round(float(n.start), 2),
                    "duration": round(float(n.end - n.start), 2),
                    "instrument": inst.name or "MIDI Instrument"
                })
        tempo = 100
        try:
            tempos = pm.get_tempo_changes()[1]
            if len(tempos):
                tempo = round(float(tempos[0]), 1)
        except Exception:
            pass
        return {"notes": notes, "tempo": tempo, "count": len(notes)}
    except Exception as e:
        return {"error": str(e)}
    finally:
        try:
            os.remove(tmp.name)
        except Exception:
            pass

def analyze_uploaded_recording(uploaded_audio):
    if uploaded_audio is None:
        return None
    if librosa is None:
        return {"error": "librosa is not installed. Add librosa and soundfile to requirements.txt for audio analysis."}
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    try:
        tmp.write(uploaded_audio.getvalue())
        tmp.close()
        y, sr = librosa.load(tmp.name, sr=None, mono=True)
        duration = round(librosa.get_duration(y=y, sr=sr), 2)
        tempo = None
        try:
            tempo = round(float(librosa.beat.tempo(y=y, sr=sr)[0]), 1)
        except Exception:
            pass
        rms = float((y**2).mean() ** 0.5)
        return {
            "duration": duration,
            "tempo": tempo,
            "rms": round(rms, 4),
            "summary": f"Recording length: {duration} seconds. Estimated tempo: {tempo if tempo else 'unknown'} BPM. Volume/RMS: {round(rms,4)}."
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        try:
            os.remove(tmp.name)
        except Exception:
            pass

st.title("🎵 Daniel Cohen AI MUSIC PRACTICE COACH")
st.caption("Genre search, song dropdowns, full-song chords, practice sheets, backing tracks, multitrack recording, and logs.")

st.sidebar.header("Setup")

st.sidebar.subheader("OpenAI API Key")
if "openai_api_key_ui" not in st.session_state:
    st.session_state.openai_api_key_ui = ""
api_key_input = st.sidebar.text_input(
    "Enter OpenAI API Key",
    value=st.session_state.openai_api_key_ui,
    type="password",
    help="Optional. Enables AI song suggestions and deeper feedback."
)
if api_key_input:
    st.session_state.openai_api_key_ui = api_key_input.strip()
    st.sidebar.success("API key entered for this session.")
else:
    st.sidebar.caption("Optional. App still works without API.")

genre = st.sidebar.selectbox("What kind of music do you want to play today?", GENRES)
query_title = st.sidebar.text_input("Type song title", "")
query_artist = st.sidebar.text_input("Type composer / artist", "")
matches = song_matches(genre, query_title, query_artist)
labels = [f"{title} — {data['artist']}" for title,data in matches]
if not labels:
    labels = [f"{title} — {data['artist']}" for title,data in SONG_LIBRARY[genre].items()]
selected_label = st.sidebar.selectbox(f"Choose a {genre} song", labels)
song = selected_label.split(" — ")[0]
song_data = SONG_LIBRARY[genre][song]

instrument = st.sidebar.selectbox("Instrument", ["Piano","Guitar","Saxophone","Flute","Trumpet","Voice","Other"])
level = st.sidebar.selectbox("Level", ["Beginner","Intermediate","Advanced"])
focus = st.sidebar.selectbox("Focus", ["Melody","Harmony","Rhythm","Improvisation","Technique"])
default_key_index = COMMON_KEYS.index(song_data["key"]) if song_data["key"] in COMMON_KEYS else 0
display_key = st.sidebar.selectbox("Transpose / Display Key", COMMON_KEYS, index=default_key_index)
minutes = st.sidebar.slider("Practice Minutes", 10, 120, 30, 5)

sections = transpose_sections(song_data, display_key)
full_song_chords = all_chords_from_sections(sections)

tabs = st.tabs(["Daily Practice Plan","Song Search","Backing Track","MIDI / Recording Analysis","Multitrack Recorder","Practice Log"])

with tabs[0]:
    st.header("Daily Practice Plan")
    st.write(f"Genre: **{genre}** | Song: **{song}** — {song_data['artist']} | Instrument: **{instrument}** | Level: **{level}** | Focus: **{focus}**")
    st.markdown(full_chord_markdown(song, song_data, sections, instrument))
    if "show_sheet" not in st.session_state: st.session_state.show_sheet = False
    if "harder_sheet" not in st.session_state: st.session_state.harder_sheet = False
    c1,c2,c3=st.columns(3)
    with c1:
        if st.button("Generate Practice Sheet"):
            st.session_state.show_sheet=True; st.session_state.harder_sheet=False
    with c2:
        if st.button("Generate Another Practice Sheet"):
            st.session_state.show_sheet=True; st.session_state.harder_sheet=False
    with c3:
        if st.button("Make It Harder"):
            st.session_state.show_sheet=True; st.session_state.harder_sheet=True
    if st.session_state.show_sheet:
        st.markdown(practice_text(level))
        if st.session_state.harder_sheet:
            st.markdown("### Harder Add-On\n- Increase tempo by 10 BPM.\n- Play another key.\n- Add a fill or variation in every section.")
        st.subheader("Practice Notation")
        render_abc(build_abc(song, sections))
    st.subheader("Daily Time Breakdown")
    st.write(f"- Warmup: {max(5,int(minutes*.2))} minutes")
    st.write(f"- Song sections: {max(8,int(minutes*.4))} minutes")
    st.write(f"- {focus}: {max(8,int(minutes*.25))} minutes")
    st.write(f"- Review/recording: {max(5,int(minutes*.15))} minutes")

with tabs[1]:
    st.header("Song Search")
    st.subheader("AI Song Suggestions")
    st.caption("Optional: uses your OpenAI API key if entered in the sidebar.")
    if st.button("Ask AI for more matching song ideas"):
        ideas = api_song_suggestions(genre, query_title, query_artist)
        if ideas:
            st.markdown(ideas)
        else:
            st.info("No API key entered. Using built-in song list only.")

    st.write("Type title and/or composer/artist in the left sidebar. This dropdown is filtered by the genre you selected.")
    preview_label = st.selectbox("Similar songs", labels, index=labels.index(selected_label) if selected_label in labels else 0)
    preview_song = preview_label.split(" — ")[0]
    preview_data = SONG_LIBRARY[genre][preview_song]
    preview_sections = transpose_sections(preview_data, display_key)
    st.markdown(full_chord_markdown(preview_song, preview_data, preview_sections, instrument))
    st.info("To make this the active song, choose it in the left sidebar.")

with tabs[2]:
    st.header("Backing Track")
    st.write(f"Backing track defaults to the selected song: **{song}**.")
    st.markdown(full_chord_markdown(song, song_data, sections, instrument))
    bpm = st.slider("Backing Track BPM", 50, 180, 100, 5)
    repeats = st.slider("Repeats of the full song form", 1, 10, 2)
    st.write("Full form used for backing track:")
    st.write(" | ".join(full_song_chords))
    if st.button("Generate Full-Song Backing Track"):
        wav = generate_backing_track(full_song_chords, bpm=bpm, repeats=repeats)
        st.audio(wav, format="audio/wav")
        st.download_button("Download backing track WAV", wav, file_name=f"{song.replace(' ','_')}_backing_track.wav", mime="audio/wav")


with tabs[3]:
    st.header("MIDI / Recording Analysis")
    st.write("Upload a MIDI file or a recording of yourself. The app will analyze it and connect it to the selected song/practice session.")

    st.subheader("Upload MIDI")
    midi_file = st.file_uploader("Upload MIDI file", type=["mid", "midi"], key="midi_analysis_upload")
    if midi_file is not None:
        midi_result = analyze_uploaded_midi(midi_file)
        if midi_result and "error" in midi_result:
            st.error(midi_result["error"])
        elif midi_result:
            st.success(f"Parsed {midi_result['count']} MIDI notes. Estimated tempo: {midi_result['tempo']} BPM.")
            if midi_result["notes"]:
                st.dataframe(pd.DataFrame(midi_result["notes"][:80]), use_container_width=True)

    st.subheader("Upload / Analyze Your Recording")
    audio_file = st.file_uploader("Upload your recording", type=["wav", "mp3", "m4a", "ogg"], key="recording_analysis_upload")
    if audio_file is not None:
        st.audio(audio_file.getvalue())
        audio_result = analyze_uploaded_recording(audio_file)
        if audio_result and "error" in audio_result:
            st.error(audio_result["error"])
        elif audio_result:
            st.success(audio_result["summary"])

            client = get_openai_client()
            if client and st.button("Ask AI for feedback on this recording summary"):
                prompt = f"""
The user practiced {song} by {song_data['artist']} on {instrument}.
Level: {level}. Focus: {focus}.
Audio analysis summary: {audio_result['summary']}

Give practical, instrument-specific feedback. Do not claim to hear exact details beyond the summary.
"""
                try:
                    resp = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role":"user","content":prompt}],
                        max_tokens=350,
                    )
                    st.markdown(resp.choices[0].message.content)
                except Exception as e:
                    st.error(f"AI feedback error: {e}")


with tabs[4]:
    st.header("Multitrack Recorder")
    if "tracks" not in st.session_state:
        st.session_state.tracks={"Track 1":None,"Track 2":None,"Track 3":None}
    for tr in ["Track 1","Track 2","Track 3"]:
        st.subheader(tr)
        uploaded=st.file_uploader(f"Upload Audio — {tr}", type=["wav","mp3","m4a"], key=tr)
        if uploaded is not None:
            st.session_state.tracks[tr]=uploaded.read()
        if st.session_state.tracks[tr]:
            st.audio(st.session_state.tracks[tr])
    if st.button("Clear All Tracks"):
        st.session_state.tracks={"Track 1":None,"Track 2":None,"Track 3":None}
        st.success("Tracks cleared.")

with tabs[5]:
    st.header("Practice Log")
    if st.button("Clear Music Practice / Reset"):
        save_logs([])
        st.success("Practice log cleared.")
    with st.form("practice_form"):
        practice_input=st.text_area("What did you practice today?", value=f"{genre} practice — {song} — {instrument} — {focus}")
        rating=st.slider("How did it go?",1,10,6)
        submitted=st.form_submit_button("Save Practice Log")
    if submitted:
        logs=load_logs()
        logs.append({"date":str(date.today()),"genre":genre,"song":song,"artist":song_data["artist"],"instrument":instrument,"level":level,"focus":focus,"practice":practice_input,"rating":rating})
        save_logs(logs)
        st.success("Practice log saved.")
    logs=load_logs()
    if logs: st.dataframe(pd.DataFrame(logs), use_container_width=True)
    else: st.info("No practice logs yet.")
