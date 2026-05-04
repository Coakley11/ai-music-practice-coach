
# VERSION: v8_ai_music_practice_tutor
import streamlit as st
import pandas as pd
import numpy as np
import requests, os, json, io, wave, tempfile
from pathlib import Path
from datetime import date

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

try:
    import librosa
except Exception:
    librosa = None

st.set_page_config(page_title="Daniel Cohen AI MUSIC PRACTICE COACH", page_icon="🎵", layout="wide")
st.title("🎵 Daniel Cohen AI MUSIC PRACTICE COACH")
st.caption("AI song coach, adaptive practice tutor, backing tracks, recording feedback, and practice memory.")

DATA_FILE = Path("practice_history.json")

STYLE_SEED_SONGS = {
    "Jazz Swing": [
        "Autumn Leaves","Fly Me to the Moon","All of Me","Take the A Train","Blue Monk","Satin Doll",
        "There Will Never Be Another You","Just Friends","Summertime","Misty","So What","On Green Dolphin Street",
        "Stella by Starlight","All the Things You Are","Have You Met Miss Jones","Days of Wine and Roses",
        "Beautiful Love","My Funny Valentine","I Got Rhythm","Cherokee","Donna Lee","Confirmation","Body and Soul",
        "Lullaby of Birdland","A Night in Tunisia","Recorda Me","Solar","Oleo","Doxy","In a Sentimental Mood"
    ],
    "Bossa Nova / Latin": [
        "Blue Bossa","The Girl from Ipanema","Corcovado","Wave","Black Orpheus","Meditation","One Note Samba",
        "Desafinado","Triste","How Insensitive","Agua de Beber","Summer Samba","Manha de Carnaval","Mas Que Nada",
        "Once I Loved","No More Blues"
    ],
    "Blues": [
        "12-Bar Blues in F","C Jam Blues","Now's the Time","Straight No Chaser","Billie's Bounce","Tenor Madness",
        "Blue Monk","Stormy Monday","Sweet Home Chicago","The Thrill Is Gone","Freddie Freeloader","Blue Seven"
    ],
    "Jewish / Klezmer / Wedding": [
        "Hava Nagila","Od Yishama","Siman Tov U'Mazal Tov","Mazel Tov Medley","Freygish Dance Study",
        "Klezmer Hora Study","Nigun Practice Study","Yismechu","Erev Shel Shoshanim","Dodi Li",
        "Yerushalayim Shel Zahav","Tzena Tzena","Hevenu Shalom Aleichem","Oseh Shalom","Freylekhs Study"
    ],
    "Funk / R&B": [
        "Chameleon","Cissy Strut","Superstition","Pick Up the Pieces","The Chicken","Watermelon Man",
        "Mercy Mercy Mercy","Cold Duck Time","Pass the Peas","Ain't No Sunshine","Use Me","I Wish"
    ],
    "Pop / Ballad": [
        "Stand By Me","Let It Be","Yesterday","Hallelujah","Perfect","Someone Like You","Lean on Me","Imagine",
        "Wonderful Tonight","Can't Help Falling in Love","Thinking Out Loud","Hey Jude","A Thousand Years"
    ],
    "Rock": ["Wish You Were Here","Come Together","Hotel California","Blackbird","Knockin' on Heaven's Door",
             "Sweet Child O' Mine","Wonderwall","Stairway to Heaven","Comfortably Numb","Brown Eyed Girl"]
}

SKILLS = {
    "Saxophone": ["Tone / long tones","Breath support","Embouchure","Articulation","Major scales","Minor scales",
                  "Pentatonics","Blues scale","Chord tones","Guide tones","ii–V–I lines","Improvisation",
                  "Sight-reading","Phrasing","Intonation","Klezmer ornaments","Jazz articulation","Overtones"],
    "Guitar": ["Open chords","Barre chords","Triads","CAGED system","Pentatonics","Blues scale","Strumming",
               "Fingerpicking","Rhythm guitar","Chord melody","Improvisation","Fretboard notes","Comping",
               "Clean transitions","Arpeggios","Voice leading","Funk rhythm"],
    "Piano": ["Scales","Chord inversions","Shell voicings","Rootless voicings","Left-hand comping","Walking bass",
              "Sight-reading","ii–V–I progressions","Improvisation","Hand coordination","Jazz voicings"],
    "Voice": ["Breath support","Pitch accuracy","Tone","Range","Vibrato","Phrasing","Diction","Ear training"],
    "Other": ["Tone","Technique","Rhythm","Scales","Chords","Improvisation","Sight-reading","Ear training"]
}

def load_history():
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text())
        except Exception:
            pass
    return {"logs": []}

def save_history(h):
    try:
        DATA_FILE.write_text(json.dumps(h, indent=2))
    except Exception:
        pass

def add_log(entry):
    h = load_history()
    h.setdefault("logs", []).append(entry)
    save_history(h)

def recent_logs(n=10):
    return load_history().get("logs", [])[-n:]

def history_text():
    logs = recent_logs(8)
    if not logs:
        return "No previous practice history yet."
    return "\n".join([f"{x.get('date')}: {x.get('song')} | focus={x.get('focus')} | rating={x.get('rating')} | notes={x.get('note')}" for x in logs])

def get_client():
    key = os.environ.get("OPENAI_API_KEY")
    try:
        key = st.secrets.get("OPENAI_API_KEY", key)
    except Exception:
        pass
    if key and OpenAI is not None:
        return OpenAI(api_key=key)
    return None

def search_musicbrainz(title, artist):
    q = []
    if title: q.append(f'recording:"{title}"')
    if artist: q.append(f'artist:"{artist}"')
    try:
        r = requests.get(
            "https://musicbrainz.org/ws/2/recording/",
            params={"query": " AND ".join(q) or title, "fmt": "json", "limit": 10},
            headers={"User-Agent": "DanielCohenAIMusicPracticeCoach/1.0"},
            timeout=8
        )
        data = r.json()
        out = []
        for rec in data.get("recordings", []):
            artists = ", ".join([c.get("artist", {}).get("name", "") for c in rec.get("artist-credit", []) if isinstance(c, dict)])
            out.append({"title": rec.get("title", ""), "artist": artists})
        return out
    except Exception:
        return []

def fallback_analysis(song, artist, style, instrument, level, focus):
    if style in ["Jazz Swing","Bossa Nova / Latin"]:
        chart = """
**A section**  
| Dm7 | G7 | Cmaj7 | Cmaj7 |  
| Em7♭5 | A7 | Dm7 | Dm7 |

**B / bridge**  
| Fmaj7 | Fm7 Bb7 | Em7 | A7 |  
| Dm7 | G7 | Cmaj7 | A7 |

**Final A**  
| Dm7 | G7 | Cmaj7 | Am7 |  
| Dm7 | G7 | Cmaj7 | Cmaj7 |
"""
        harmony = "This practice-version chart emphasizes ii–V–I motion, secondary dominants, guide tones, and tension/resolution."
        scales = "- m7: Dorian/chord tones\n- 7: Mixolydian first, altered later\n- maj7: major scale, target 3–5–7–9\n- m7♭5: chord tones first"
    elif style == "Blues":
        chart = """
**12-bar form**  
| I7 | IV7 | I7 | I7 |  
| IV7 | IV7 | I7 | I7 |  
| V7 | IV7 | I7 | V7 |
"""
        harmony = "Blues harmony treats dominant 7th chords as home sounds. Groove and call-and-response matter more than complexity."
        scales = "- Blues scale\n- Minor pentatonic\n- Add major 3rd for dominant blues color\n- Target chord tones on IV7 and V7"
    elif style == "Jewish / Klezmer / Wedding":
        chart = """
**A section**  
| Dm | Dm | A7 | A7 |  
| Dm | Gm | A7 | Dm |

**B section**  
| Gm | Dm | A7 | Dm |  
| Dm | Gm | A7 | Dm |
"""
        harmony = "This uses tonic minor, dominant return, and freygish/harmonic minor color. Articulation, ornaments, and rhythmic drive matter."
        scales = "- D Freygish: D Eb F# G A Bb C D\n- D harmonic minor\n- Target A7 chord tones resolving to Dm"
    else:
        chart = """
**Verse**  
| C | G | Am | F |

**Chorus**  
| F | G | C | Am |  
| F | G | C | C |
"""
        harmony = "This practice chart uses common pop diatonic harmony. Focus on melody, emotion, rhythm, and clean phrasing."
        scales = "- Major scale\n- Major pentatonic\n- Target chord tones at phrase endings"

    depth = {
        "Beginner": "Learn the form, melody, roots, and basic rhythm. Work only 2–4 measures at a time.",
        "Intermediate": "Add chord tones, guide tones, and section-by-section practice. Record yourself after each section.",
        "Advanced": "Use motif development, substitutions, chromatic approaches, reharmonization ideas, and multiple contrasting choruses."
    }.get(level, "")

    return f"""
## {song} — AI Practice Coach Report

Artist/composer: {artist or "not specified"}  
Style: {style}  
Instrument: {instrument}  
Level: {level}  
Focus: {focus}

## Full Practice-Version Form / Chords by Section

{chart}

## Deeper Harmony Analysis

{harmony}

## Scales and Sounds

{scales}

## Chord Outlines to Practice

- Major 7: 1–3–5–7  
- Minor 7: 1–♭3–5–♭7  
- Dominant 7: 1–3–5–♭7  
- Half-diminished: 1–♭3–♭5–♭7  
- Minor triad: 1–♭3–5  

## What to Work on First

1. Count the form out loud.
2. Learn the melody slowly.
3. Play only roots through the form.
4. Play 1–3–5–7 through the form.
5. Record one take with the backing track.

## Level-Based Analysis

{depth}

## Instrument-Specific Advice

For **{instrument}**, focus on sound quality, rhythm, and making the song feel musical before adding complexity.

## Based on Previous Practice History

{history_text()}

## Today's Assignment

- 5 minutes: warm up on {focus}.
- 10 minutes: isolate the hardest section.
- 10 minutes: play chord tones with backing track.
- 5 minutes: record and write one weakness.

## Next Session

Continue from the weakest section instead of restarting randomly from the beginning.
"""

def ai_song_report(song, artist, style, instrument, level, focus):
    client = get_client()
    if not client:
        return fallback_analysis(song, artist, style, instrument, level, focus)

    prompt = f"""
Create a deep music practice coaching report for:
Song: {song}
Artist/composer/singer: {artist}
Style: {style}
Instrument: {instrument}
Level: {level}
Focus: {focus}
Previous practice history:
{history_text()}

Give:
1. Full song form by sections A/B/C/bridge/ending.
2. Practice-version chord progression for every section.
3. Deep harmonic analysis: ii-V-I, secondary dominants, tonic/dominant, blues, freygish, modal interchange where relevant.
4. Chord outlines and guide-tone advice.
5. Scales/sounds to use over each section.
6. Exact sections to practice first and why.
7. Exercises by level.
8. Today's assignment, tomorrow's assignment, next-session recommendation.
9. Instrument-specific advice.
Do not provide copyrighted lyrics.
If exact official chords are uncertain, label it "practice-version changes".
"""
    try:
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"system","content":"You are an expert music theory and practice coach."},
                      {"role":"user","content":prompt}],
            temperature=0.35
        )
        return res.choices[0].message.content
    except Exception as e:
        return fallback_analysis(song, artist, style, instrument, level, focus) + f"\n\nAI error fallback: {e}"

NOTE = {"C":60,"C#":61,"Db":61,"D":62,"D#":63,"Eb":63,"E":64,"F":65,"F#":66,"Gb":66,"G":67,"G#":68,"Ab":68,"A":69,"A#":70,"Bb":70,"B":71}
def root(chord): return chord[:2] if len(chord)>1 and chord[1] in ["b","#"] else chord[:1]
def chord_notes(ch):
    r=NOTE.get(root(ch),60); c=ch.lower()
    if "m7b5" in c: ints=[0,3,6,10]
    elif "maj7" in c: ints=[0,4,7,11]
    elif "m7" in c: ints=[0,3,7,10]
    elif "m" in c: ints=[0,3,7]
    elif "7" in c: ints=[0,4,7,10]
    else: ints=[0,4,7]
    return [r+i for i in ints]
def freq(m): return 440*(2**((m-69)/12))
def tone(f,d,sr=44100,v=.15):
    t=np.linspace(0,d,int(sr*d),False)
    y=np.sin(2*np.pi*f*t)+.3*np.sin(2*np.pi*2*f*t)+.15*np.sin(2*np.pi*3*f*t)
    y=y/(np.max(np.abs(y))+1e-9)
    env=np.ones_like(y); a=max(1,int(.01*sr)); rel=max(1,int(.05*sr))
    env[:a]=np.linspace(0,1,a); env[-rel:]=np.linspace(1,0,rel)
    return v*y*env
def noise(d,sr=44100,v=.08,decay=25):
    n=int(sr*d); y=np.random.uniform(-1,1,n); env=np.exp(-np.linspace(0,decay,n)); return v*y*env
def add(buf,start,snd):
    end=min(len(buf),start+len(snd))
    if end>start: buf[start:end]+=snd[:end-start]
def progression(style):
    if style in ["Jazz Swing","Bossa Nova / Latin"]: return [("Dm7",1),("G7",1),("Cmaj7",2),("Em7b5",1),("A7",1),("Dm7",2)]
    if style=="Blues": return [("F7",4),("Bb7",2),("F7",2),("C7",1),("Bb7",1),("F7",1),("C7",1)]
    if style=="Jewish / Klezmer / Wedding": return [("Dm",2),("A7",2),("Dm",2),("Gm",1),("A7",1),("Dm",2)]
    if style=="Funk / R&B": return [("Dm7",2),("G7",2),("Dm7",2),("G7",2)]
    return [("C",1),("G",1),("Am",1),("F",1)]
def backing_track(style,instrument,bpm,choruses=3,count_in=True):
    sr=44100; beat=60/bpm; bar=beat*4; prog=progression(style)
    total=sum(b for _,b in prog)*choruses+(1 if count_in else 0)
    audio=np.zeros(int(total*bar*sr)); cur=bar if count_in else 0
    if count_in:
        for i in range(4): add(audio,int(i*beat*sr),tone(1300,.04,sr,.25))
    for _ in range(choruses):
        for ch,bars in prog:
            ns=chord_notes(ch); dur=bars*bar
            bass=[ns[0]-24, ns[min(2,len(ns)-1)]-24, ns[0]-12, ns[min(2,len(ns)-1)]-24]
            for b in range(bars*4):
                bt=cur+b*beat
                add(audio,int(bt*sr),tone(freq(bass[b%4]),beat*.85,sr,.18))
                if b%4 in [0,2]: add(audio,int(bt*sr),tone(55,.12,sr,.28))
                if b%4 in [1,3]: add(audio,int(bt*sr),noise(.1,sr,.12,28))
                hats=[0,.67] if style=="Jazz Swing" else [0,.5]
                for h in hats: add(audio,int((bt+h*beat)*sr),noise(.035,sr,.035,45))
            if instrument!="Piano":
                for n in ns: add(audio,int(cur*sr),tone(freq(n),dur*.9,sr,.04))
            if instrument!="Guitar":
                for b in range(bars*4):
                    for off in ([0,.67] if style=="Jazz Swing" else [0,.5]):
                        for n in ns[:3]: add(audio,int((cur+b*beat+off*beat)*sr),tone(freq(n+12),beat*.15,sr,.025))
            cur+=dur
    audio=audio/(np.max(np.abs(audio))+1e-9)*.88
    data=(audio*32767).astype(np.int16)
    out=io.BytesIO()
    with wave.open(out,"wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr); wf.writeframes(data.tobytes())
    out.seek(0); return out.getvalue()

def analyze_audio(obj,bpm):
    if not obj: return {"error":"No audio uploaded."}
    if librosa is None: return {"error":"librosa not installed. Check requirements.txt."}
    data=obj.getvalue()
    tmp=tempfile.NamedTemporaryFile(delete=False,suffix=".wav"); tmp.write(data); tmp.close()
    try:
        y,sr=librosa.load(tmp.name,sr=22050,mono=True)
        dur=librosa.get_duration(y=y,sr=sr)
        tempo,beats=librosa.beat.beat_track(y=y,sr=sr); tempo=float(np.asarray(tempo).flatten()[0])
        rms=librosa.feature.rms(y=y)[0]; vol=float(1/(1+np.std(rms)/(np.mean(rms)+1e-8)))
        onsets=librosa.onset.onset_detect(y=y,sr=sr); onset_density=len(onsets)/max(dur,1)
        f0,_,_=librosa.pyin(y,fmin=librosa.note_to_hz("C2"),fmax=librosa.note_to_hz("C7"),sr=sr)
        voiced=f0[~np.isnan(f0)]
        if len(voiced)>10:
            med=float(np.median(voiced)); pstab=float(1/(1+(1200*np.std(np.log2(voiced/med)))/100)); note=librosa.hz_to_note(med)
        else: pstab=None; note="Not enough pitched material"
        return {"duration":dur,"tempo":tempo,"tempo_diff":abs(tempo-bpm),"volume_stability":vol,"onset_density":onset_density,"pitch_stability":pstab,"note":note}
    except Exception as e:
        return {"error":str(e)}
    finally:
        try: os.remove(tmp.name)
        except Exception: pass

def weak_areas(focus, rating, notes):
    text=(focus+" "+notes).lower(); out=[]
    if any(w in text for w in ["time","rhythm","beat","rushing","dragging"]): out.append("Timing")
    if any(w in text for w in ["tone","sound","air","breath","pitch","intonation"]): out.append("Tone / Pitch")
    if any(w in text for w in ["chord","guide","harmony","changes"]): out.append("Chord Tones")
    if any(w in text for w in ["scale","mode","key"]): out.append("Scales")
    if any(w in text for w in ["phrase","phrasing","expression"]): out.append("Phrasing")
    if rating<=5: out.append("Technique / Control")
    return list(dict.fromkeys(out)) or ["Timing","Tone / Pitch","Chord Tones"]
def exercises(area,song):
    d={
        "Timing":[f"Quarter-note chorus through {song}.","Clap rhythm before playing.","Metronome on beats 2 and 4 only."],
        "Tone / Pitch":["Long tones 8 beats each.","Crescendo-decrescendo without pitch change.","Record phrase endings and check if they weaken."],
        "Chord Tones":[f"Play 1–3–5–7 for every chord in {song}.","Guide tones only: 3rds and 7ths.","Approach-note drill into chord tones."],
        "Scales":["Main scale slowly, then melody.","Three-note cells: 1–2–3, 2–3–4.","End scale phrases on chord tones."],
        "Phrasing":["2-bar call and 2-bar response.","Repeat one idea three ways.","Leave silence between phrases."],
        "Technique / Control":["Hardest 4 measures at half speed.","10 perfect slow reps.","Record only the difficult section."]
    }
    return d.get(area,d["Technique / Control"])

# Sidebar
st.sidebar.title("Setup")
instrument=st.sidebar.selectbox("Instrument",list(SKILLS.keys()))
level=st.sidebar.selectbox("Level",["Beginner","Intermediate","Advanced"])
style=st.sidebar.selectbox("Style",list(STYLE_SEED_SONGS.keys()))
minutes=st.sidebar.slider("Practice minutes",10,120,30,5)
skills=st.sidebar.multiselect("Skills",SKILLS[instrument],default=SKILLS[instrument][:3])
custom=st.sidebar.text_input("Add custom skill")
if custom: skills.append(custom)
focus=st.sidebar.selectbox("Main focus",skills or SKILLS[instrument])

if "song" not in st.session_state: st.session_state.song="Autumn Leaves"
if "artist" not in st.session_state: st.session_state.artist=""
if "bpm" not in st.session_state: st.session_state.bpm=100
if "tracks" not in st.session_state: st.session_state.tracks=[]

tabs=st.tabs(["Practice Memory","Find / Analyze Any Song","Daily Plan","Backing Track","Record & Analyze","Multitrack","Log"])

with tabs[0]:
    st.header("Practice Memory")
    logs=recent_logs(12)
    if logs:
        st.dataframe(pd.DataFrame(logs),use_container_width=True)
        last=logs[-1]
        st.success(f"Continue from last time: {last.get('song')} — focus on {last.get('focus')}.")
    else:
        st.info("No history yet. The app will adapt once you save logs.")

with tabs[1]:
    st.header("Find / Analyze Any Song")
    song=st.text_input("Song title",st.session_state.song)
    artist=st.text_input("Composer / singer / artist",st.session_state.artist)
    col1,col2,col3=st.columns(3)
    if col1.button("Search public song database"):
        res=search_musicbrainz(song,artist)
        if res:
            for i,r in enumerate(res,1): st.write(f"{i}. **{r['title']}** — {r['artist']}")
        else: st.warning("No metadata found. AI analysis can still create a practice-version chart.")
    if col2.button("Use this song"):
        st.session_state.song=song; st.session_state.artist=artist; st.success(f"Selected {song}")
    if col3.button("Generate deep AI practice analysis"):
        st.markdown(ai_song_report(song,artist,style,instrument,level,focus))
        add_log({"date":str(date.today()),"song":song,"instrument":instrument,"focus":focus,"rating":6,"note":"Generated song analysis"})
    if not get_client():
        st.warning("OPENAI_API_KEY not connected. App uses fallback analysis. Add key in Streamlit Secrets for true AI custom analysis.")
    st.subheader("Style song examples")
    st.write(", ".join(STYLE_SEED_SONGS[style]))

with tabs[2]:
    st.header("Daily Practice Plan")
    logs=recent_logs(10)
    if logs:
        last=logs[-1]
        st.success(f"Recommended continuation: work on **{last.get('song')}**, especially **{last.get('focus')}**.")
    warm=max(5,int(minutes*.2)); tech=max(5,int(minutes*.3)); songwork=max(5,int(minutes*.35)); review=max(3,minutes-warm-tech-songwork)
    st.write(f"**Warmup — {warm} min:** connect warmup to {focus}.")
    st.write(f"**Technique — {tech} min:** slow metronome work.")
    st.write(f"**Song work — {songwork} min:** isolate one section of {st.session_state.song}.")
    st.write(f"**Record/review — {review} min:** record one take and write one weakness.")
    rating=st.slider("How hard does it feel?",1,10,6)
    note_summary=history_text()
    st.subheader("Targeted exercises")
    for area in weak_areas(focus,rating,note_summary):
        st.markdown(f"### {area}")
        for e in exercises(area,st.session_state.song): st.write(f"- {e}")

with tabs[3]:
    st.header("Backing Track Studio")
    st.write("Improved synthesized band: bass, drums, chord pads, and comping. For true real-band sound, connect MIDI soundfonts or an AI music API.")
    bpm=st.slider("BPM",50,180,st.session_state.bpm,5)
    choruses=st.slider("Choruses",1,8,3)
    count=st.checkbox("Count-in",True)
    if st.button("Generate backing track"):
        wav=backing_track(style,instrument,bpm,choruses,count)
        st.session_state.bpm=bpm
        st.audio(wav,format="audio/wav")
        st.download_button("Download WAV",wav,file_name=f"{style}_{bpm}bpm.wav",mime="audio/wav")

with tabs[4]:
    st.header("Record & Analyze")
    bpm=st.number_input("Expected BPM",40,220,int(st.session_state.bpm),5)
    rec=None
    try: rec=st.audio_input("Record in app")
    except Exception: st.caption("Direct recording may not be supported; upload instead.")
    up=st.file_uploader("Upload recording",type=["wav","mp3","m4a","ogg"])
    obj=rec or up
    if obj: st.audio(obj)
    if st.button("Analyze recording"):
        m=analyze_audio(obj,bpm)
        if "error" in m: st.error(m["error"])
        else:
            c1,c2,c3=st.columns(3)
            c1.metric("Duration",f"{m['duration']:.1f}s"); c2.metric("Tempo",f"{m['tempo']:.1f}"); c3.metric("Tempo diff",f"{m['tempo_diff']:.1f}")
            c4,c5,c6=st.columns(3)
            c4.metric("Volume stability",f"{m['volume_stability']:.2f}"); c5.metric("Onsets/sec",f"{m['onset_density']:.2f}"); c6.metric("Median note",m["note"])
            st.subheader("Practice feedback")
            if m["tempo_diff"]>15: st.write("- Timing is far from target. Count/clap before playing.")
            elif m["tempo_diff"]>5: st.write("- Timing drifts somewhat. Practice 10 BPM slower.")
            else: st.write("- Tempo is close to target.")
            if m["volume_stability"]<.65: st.write("- Tone/volume is uneven. Do sustained-note practice.")
            if m["pitch_stability"] is not None and m["pitch_stability"]<.55: st.write("- Pitch stability needs work. Use tuner/drone.")
        add_log({"date":str(date.today()),"song":st.session_state.song,"instrument":instrument,"focus":focus,"rating":6,"note":"Audio analyzed"})

with tabs[5]:
    st.header("Multitrack Recorder")
    name=st.text_input("Track name",f"Track {len(st.session_state.tracks)+1}")
    ti=st.selectbox("Track instrument",list(SKILLS.keys()),key="ti")
    tr=None
    try: tr=st.audio_input("Record track")
    except Exception: st.caption("Direct recording may not be supported; upload instead.")
    tu=st.file_uploader("Upload track",type=["wav","mp3","m4a","ogg"],key="tu")
    if st.button("Save track"):
        obj=tr or tu
        if obj:
            st.session_state.tracks.append({"name":name,"instrument":ti,"audio":obj.getvalue()})
            st.success("Track saved.")
    for i,t in enumerate(st.session_state.tracks,1):
        st.markdown(f"### {i}. {t['name']} — {t['instrument']}")
        st.audio(t["audio"])
    if st.button("Clear tracks"): st.session_state.tracks=[]

with tabs[6]:
    st.header("Practice Log")
    with st.form("log"):
        d=st.date_input("Date",date.today())
        s=st.text_input("Song",st.session_state.song)
        f=st.text_input("Focus",focus)
        r=st.slider("Rating",1,10,6)
        n=st.text_area("Notes")
        ok=st.form_submit_button("Save log")
    if ok:
        add_log({"date":str(d),"song":s,"instrument":instrument,"focus":f,"rating":r,"note":n})
        st.success("Saved. Recommendations will use this history.")
    logs=recent_logs(100)
    if logs: st.dataframe(pd.DataFrame(logs),use_container_width=True)
