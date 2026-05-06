# VERSION: v11_fixed_missing_imports
import os
import json
import io
import wave
import tempfile

# VERSION: v8_ai_music_practice_tutor
import streamlit as st
import pandas as pd
import numpy as np
import requests

try:
    from scipy.signal import lfilter
except Exception:
    lfilter = None, os, json, io, wave, tempfile
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
        "Wonderful Tonight","Can't Help Falling in Love","Thinking Out Loud","Hey Jude","A Thousand Years",
        "Viva La Vida","Piano Man","Just the Way You Are","Vienna","She's Always a Woman",
        "New York State of Mind","Slow Dancing in a Burning Room","Gravity","Why Georgia","No Such Thing","Neon","Stop This Train","In Your Atmosphere","Daughters","Waiting on the World to Change","Heartbreak Warfare","Edge of Desire","Belief","Vultures","Who Says","Wild Blue","Rosie","Emoji of a Wave","Love on the Weekend","New Light","Just Say",
        "Your Body Is a Wonderland","Free Fallin'","Don't Stop Believin'","Faithfully",
        "Open Arms","Tiny Dancer","Rocket Man","Fields of Gold","Shape of You",
        "Photograph","Yellow","Fix You","Clocks","The Scientist","Here Comes the Sun",
        "Something","In My Life","While My Guitar Gently Weeps","Penny Lane"
    ],
    "Rock": [
        "Wish You Were Here","Come Together","Hotel California","Blackbird","Knockin' on Heaven's Door",
        "Sweet Child O' Mine","Wonderwall","Stairway to Heaven","Comfortably Numb","Brown Eyed Girl",
        "Don't Stop Believin'","Livin' on a Prayer","Dream On","Sweet Home Alabama",
        "Bohemian Rhapsody","Free Bird","Smoke on the Water","Back in Black",
        "Born to Run","More Than a Feeling","Carry On Wayward Son"
    ]
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
    "Flute": ["Tone / air stream","Breath support","Embouchure","Long tones","Major scales","Minor scales",
              "Articulation","Tonguing","Sight-reading","Intonation","Vibrato","Phrasing","High register",
              "Low register","Chromatic scale","Rhythm accuracy","Ear training"],
    "Trumpet": ["Tone / long tones","Breath support","Embouchure","Lip slurs","Valve technique","Major scales",
                "Minor scales","Articulation","Tonguing","Range building","Sight-reading","Intonation",
                "Flexibility","Endurance","Chord tones","Rhythm accuracy","Ear training"],
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

def lowpass(y, amount=0.08):
    """Simple smoothing filter for less harsh synthesized tones."""
    if lfilter is None:
        return y
    b = [amount]
    a = [1, amount - 1]
    return lfilter(b, a, y)

def adsr_env(n, sr=44100, attack=0.01, decay=0.08, sustain=0.75, release=0.08):
    a = max(1, int(attack * sr))
    d = max(1, int(decay * sr))
    r = max(1, int(release * sr))
    s = max(1, n - a - d - r)
    env = np.concatenate([
        np.linspace(0, 1, a),
        np.linspace(1, sustain, d),
        np.full(s, sustain),
        np.linspace(sustain, 0, r)
    ])
    if len(env) < n:
        env = np.pad(env, (0, n - len(env)), constant_values=0)
    return env[:n]

def instrument_tone(freq_hz, duration, sr=44100, volume=0.15, kind="piano"):
    t = np.linspace(0, duration, int(sr * duration), False)

    if kind == "bass":
        y = (
            np.sin(2*np.pi*freq_hz*t)
            + 0.45*np.sin(2*np.pi*2*freq_hz*t)
            + 0.20*np.sin(2*np.pi*3*freq_hz*t)
        )
        env = adsr_env(len(y), sr, attack=0.006, decay=0.08, sustain=0.55, release=0.12)

    elif kind == "piano":
        y = (
            np.sin(2*np.pi*freq_hz*t)
            + 0.35*np.sin(2*np.pi*2*freq_hz*t)
            + 0.18*np.sin(2*np.pi*3*freq_hz*t)
            + 0.08*np.sin(2*np.pi*4*freq_hz*t)
        )
        env = adsr_env(len(y), sr, attack=0.004, decay=0.18, sustain=0.35, release=0.18)

    elif kind == "organ_pad":
        y = (
            np.sin(2*np.pi*freq_hz*t)
            + 0.30*np.sin(2*np.pi*(freq_hz*1.01)*t)
            + 0.25*np.sin(2*np.pi*2*freq_hz*t)
        )
        env = adsr_env(len(y), sr, attack=0.05, decay=0.10, sustain=0.75, release=0.20)

    elif kind == "guitar":
        y = (
            np.sin(2*np.pi*freq_hz*t)
            + 0.20*np.sin(2*np.pi*2*freq_hz*t)
            + 0.10*np.sin(2*np.pi*3*freq_hz*t)
        )
        env = adsr_env(len(y), sr, attack=0.002, decay=0.12, sustain=0.25, release=0.10)

    else:
        y = np.sin(2*np.pi*freq_hz*t)
        env = adsr_env(len(y), sr)

    y = y / (np.max(np.abs(y)) + 1e-9)
    y = lowpass(y, 0.12)
    return volume * y * env

def drum_kick(sr=44100):
    d = 0.16
    t = np.linspace(0, d, int(sr*d), False)
    freq_curve = 85 * np.exp(-18*t) + 38
    phase = 2*np.pi*np.cumsum(freq_curve)/sr
    y = np.sin(phase) * np.exp(-22*t)
    return 0.55 * y

def drum_snare(sr=44100):
    d = 0.14
    n = int(sr*d)
    noise_y = np.random.uniform(-1, 1, n) * np.exp(-24*np.linspace(0, d, n))
    tone_y = np.sin(2*np.pi*190*np.linspace(0, d, n)) * np.exp(-18*np.linspace(0, d, n))
    return 0.22 * noise_y + 0.12 * tone_y

def drum_hat(sr=44100, open_hat=False):
    d = 0.12 if open_hat else 0.045
    n = int(sr*d)
    y = np.random.uniform(-1, 1, n)
    # crude high-pass by subtracting smoothed signal
    smooth = lowpass(y, 0.03)
    y = y - smooth
    y *= np.exp((-16 if open_hat else -55) * np.linspace(0, d, n))
    return 0.09 * y

def add_reverb(audio, sr=44100, delay_ms=70, decay=0.18):
    delay = int(sr * delay_ms / 1000)
    out = audio.copy()
    if delay < len(out):
        out[delay:] += decay * audio[:-delay]
    delay2 = int(delay * 1.7)
    if delay2 < len(out):
        out[delay2:] += (decay * 0.55) * audio[:-delay2]
    return out

def add_stereo_width(mono, sr=44100):
    """Return stereo audio with tiny delay difference for more realistic space."""
    delay = int(0.012 * sr)
    left = mono.copy()
    right = np.zeros_like(mono)
    right[delay:] = mono[:-delay]
    right[:delay] = mono[:delay]
    stereo = np.vstack([left, right]).T
    return stereo

def backing_track(style,instrument,bpm,choruses=3,count_in=True):
    """
    Higher-quality synthesized band:
    - walking/root-fifth bass
    - better kick/snare/hat
    - piano/guitar/organ-like comping
    - stereo width and light reverb
    This is still synthesized, not real sampled instruments.
    """
    sr=44100
    beat=60/bpm
    bar=beat*4
    prog=progression(style)
    total=sum(b for _,b in prog)*choruses+(1 if count_in else 0)
    audio=np.zeros(int(total*bar*sr))
    cur=bar if count_in else 0

    if count_in:
        for i in range(4):
            add(audio,int(i*beat*sr),instrument_tone(1300,.04,sr,.25,"piano"))

    for _ in range(choruses):
        for ch,bars in prog:
            ns=chord_notes(ch)
            dur=bars*bar

            # Bass pattern depends on style
            if style == "Blues":
                bass=[ns[0]-24, ns[2]-24 if len(ns)>2 else ns[0]-12, ns[0]-12, ns[2]-24 if len(ns)>2 else ns[0]-12]
            elif style == "Funk / R&B":
                bass=[ns[0]-24, ns[0]-24, ns[2]-24 if len(ns)>2 else ns[0]-12, ns[0]-12]
            else:
                bass=[ns[0]-24, ns[2]-24 if len(ns)>2 else ns[0]-12, ns[0]-12, ns[1]-12 if len(ns)>1 else ns[0]-12]

            for b in range(bars*4):
                bt=cur+b*beat

                # bass
                add(audio,int(bt*sr),instrument_tone(freq(bass[b%len(bass)]),beat*.92,sr,.20,"bass"))

                # drums
                if b%4 in [0,2]:
                    add(audio,int(bt*sr),drum_kick(sr))
                if b%4 in [1,3]:
                    add(audio,int(bt*sr),drum_snare(sr))

                if style=="Jazz Swing":
                    hats=[0,.67]
                elif style=="Funk / R&B":
                    hats=[0,.25,.5,.75]
                else:
                    hats=[0,.5]
                for h in hats:
                    add(audio,int((bt+h*beat)*sr),drum_hat(sr, open_hat=False))

            # pad bed if player is not piano
            if instrument!="Piano":
                for n in ns:
                    add(audio,int(cur*sr),instrument_tone(freq(n),dur*.96,sr,.035,"organ_pad"))

            # piano/guitar comping if player isn't that instrument
            for b in range(bars*4):
                bt=cur+b*beat

                if style=="Jazz Swing":
                    comp_offsets=[0.0,0.67]
                elif style=="Bossa Nova / Latin":
                    comp_offsets=[0.0,0.5,0.75]
                elif style=="Funk / R&B":
                    comp_offsets=[0.0,0.25,0.5,0.75]
                else:
                    comp_offsets=[0.0,0.5]

                for off in comp_offsets:
                    kind = "guitar" if instrument!="Guitar" else "piano"
                    vol = 0.030 if kind=="guitar" else 0.038
                    for n in ns[:4]:
                        add(audio,int((bt+off*beat)*sr),instrument_tone(freq(n+12),beat*.18,sr,vol,kind))

            cur+=dur

    # light compression / saturation
    audio = np.tanh(audio * 1.6) / 1.6

    # reverb + normalize
    audio = add_reverb(audio, sr, delay_ms=65, decay=0.16)
    audio=audio/(np.max(np.abs(audio))+1e-9)*.90

    stereo = add_stereo_width(audio, sr)
    data=(stereo*32767).astype(np.int16)

    out=io.BytesIO()
    with wave.open(out,"wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(data.tobytes())
    out.seek(0)
    return out.getvalue()

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



def written_note_exercises(instrument, song):
    if instrument == "Flute":
        return """
## Flute Written Note Exercises

### Exercise 1 — Long-Tone Note Reading
Read and play these notes slowly, holding each for 4 beats:

G4 — A4 — B4 — C5 — D5 — C5 — B4 — A4 — G4

### Exercise 2 — Scale Fragment
Play as quarter notes:

G4 A4 B4 C5 | D5 C5 B4 A4 | G4

### Exercise 3 — Articulation Pattern
Use the same notes, but tongue each note clearly:

TA TA TA TA | TA TA TA TA

### Exercise 4 — Phrase Shape
Play this as one musical sentence:

G4 — B4 — D5 — C5 — B4 — A4 — G4

### Flute Focus
- Keep the air stream steady.
- Do not squeeze the embouchure.
- Watch intonation on D5 and higher notes.
- Practice slowly before adding speed.
"""

    if instrument == "Trumpet":
        return """
## Trumpet Written Note Exercises

### Exercise 1 — Long-Tone Note Reading
Read and play these notes slowly, holding each for 4 beats:

C4 — D4 — E4 — F4 — G4 — F4 — E4 — D4 — C4

### Exercise 2 — Valve / Scale Pattern
Play as quarter notes:

C4 D4 E4 F4 | G4 F4 E4 D4 | C4

### Exercise 3 — Lip Slur Preparation
Play without forcing:

C4 — G4 — C5 — G4 — C4

### Exercise 4 — Articulation Pattern
Tongue each note clearly:

C4 C4 D4 D4 | E4 E4 F4 F4 | G4

### Trumpet Focus
- Use relaxed air, not pressure.
- Keep corners firm but not tight.
- Rest when tired.
- Focus on clean attacks and centered pitch.
"""
    if instrument == "Flute":
        return """
## Flute Melody + Technique Exercises

### Melody Exercises
- Say the note names before playing.
- Play the melody in 2-measure chunks.
- Use long, steady air through each phrase.
- Practice phrase endings without letting pitch sag.

### Note Reading Exercises
- Read notes slowly before adding rhythm.
- Circle high-register notes and practice them separately.
- Practice G major and C major scale fragments.

### Tone Tips
- Air speed controls register.
- Keep shoulders relaxed.
- Use a tuner for long notes.
"""

    if instrument == "Trumpet":
        return """
## Trumpet Melody + Technique Exercises

### Melody Exercises
- Say note names and valve combinations first.
- Play the melody slowly, resting often.
- Practice clean attacks at the start of every phrase.
- Do not force high notes.

### Chord / Note Exercises
- Practice chord tones as bugle-style outlines.
- Play root–third–fifth slowly.
- Use lip slurs to build flexibility.

### Tone Tips
- Use air support, not mouthpiece pressure.
- Rest as much as you play.
- Keep pitch centered with a tuner.
"""

    return ""

def piano_sheet_music_exercises(song):
    return f"""
## Piano Sheet-Music Style Exercises for {song}

These are original practice-version exercises, not copyrighted sheet music.

### Right Hand Melody Exercise
Treble clef note names:

C5 — D5 — E5 — G5 | E5 — D5 — C5 — G4 |
A4 — C5 — E5 — D5 | C5

Finger suggestion:
1 — 2 — 3 — 5 | 3 — 2 — 1 — 5 | 1 — 2 — 4 — 3 | 2

### Left Hand Chord Exercise
Bass clef chord roots / simple fifths:

C3–G3 | G2–D3 | A2–E3 | F2–C3

Practice:
- Hold each left-hand shape for 4 beats.
- Keep the left hand softer than the melody.

### Both Hands Together
Right hand:
C5 — D5 — E5 — G5 | E5 — D5 — C5 — G4

Left hand:
C3–G3 hold | G2–D3 hold | A2–E3 hold | F2–C3 hold

### Two-Hand Coordination Drill
1. Left hand only.
2. Right hand only.
3. Both hands, very slowly.
4. Add metronome at 60 BPM.
5. Record and listen for whether the melody is louder than the chords.

### Chord Change Practice
| C | G | Am | F |

Play:
- LH root + fifth
- RH simple melody
- Then RH block chord
- Then RH broken chord
"""

def song_practice_sheet_music(song, instrument):
    if instrument == "Piano":
        return piano_sheet_music_exercises(song)

    if instrument == "Flute":
        return f"""
## Flute Practice Sheet for {song}

Original practice melody:

4/4 time, moderate tempo

G4 A4 B4 C5 | D5 C5 B4 A4 | G4 B4 D5 C5 | B4 A4 G4

Practice steps:
1. Clap rhythm.
2. Say note names.
3. Play slowly with full tone.
4. Add phrase shape.
"""

    if instrument == "Trumpet":
        return f"""
## Trumpet Practice Sheet for {song}

Original practice melody:

4/4 time, moderate tempo

C4 D4 E4 F4 | G4 F4 E4 D4 | C4 E4 G4 F4 | E4 D4 C4

Practice steps:
1. Buzz lightly first.
2. Say valve combinations.
3. Play slowly with clean attacks.
4. Rest, then repeat.
"""

    return ""


def instrument_specific_exercises(instrument, song):
    if instrument == "Guitar":
        return """
## Guitar Melody + Chord Change Exercises

### Melody Exercises
- Learn the melody on ONE string first.
- Sing the melody before playing it.
- Play melody slowly with a metronome.
- Practice melody using alternate picking.
- Connect melody notes to nearby chord shapes.

### Chord Change Exercises
- Loop only two chords at a time.
- Practice silent chord switching without strumming.
- Play root notes before full chords.
- Practice voice-leading between nearby chord shapes.
- Use guide fingers to reduce motion.

### Strumming Tips
- Count aloud while strumming.
- Keep right hand moving continuously.
- Start with downstrokes only.
- Add upstrokes after rhythm is stable.
- Accent beats 2 and 4 for groove.
- For ballads: lighter touch and longer sustain.
- For funk/pop: shorter tighter strums.

### Rhythm Practice
- Play only muted strums first.
- Clap difficult rhythms before playing.
- Record your groove without melody.
"""

    if instrument == "Piano":
        return """
## Piano Melody + Chord Change Exercises

### Melody Exercises
- Practice right-hand melody alone slowly.
- Sing phrases before playing them.
- Shape phrase endings musically.
- Practice melody with different rhythms.
- Add dynamics: soft/loud phrase contrast.

### Chord Change Exercises
- Practice left-hand roots only first.
- Then add shell voicings (1-3-7).
- Move between chords using closest inversions.
- Practice difficult transitions repeatedly.
- Use metronome at slow tempo first.

### Comping / Rhythm Tips
- Keep comping lighter than melody.
- Lock left hand to the groove.
- Anticipate chord changes slightly.
- Use shorter voicings for faster songs.
- For jazz/bossa: lighter syncopated comping.
- For pop/ballads: simpler sustained voicings.

### Coordination Exercises
- Play melody while holding whole-note chords.
- Then gradually add rhythmic comping.
- Practice hands separately before combining.
"""
    return ""


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


def adaptive_sheet_for_player(song, artist, instrument, level, style, focus, history_summary):
    if instrument == "Piano":
        return piano_adaptive_sheet(song, level, style, focus, history_summary)
    if instrument == "Guitar":
        return guitar_adaptive_sheet(song, level, style, focus, history_summary)
    if instrument in ["Saxophone", "Flute", "Trumpet"]:
        return wind_adaptive_sheet(song, instrument, level, style, focus, history_summary)
    if instrument == "Voice":
        return voice_adaptive_sheet(song, level, style, focus, history_summary)
    return general_adaptive_sheet(song, instrument, level, style, focus, history_summary)

def level_header(level):
    if level == "Beginner":
        return "Beginner Sheet — simplified rhythm, large chunks, roots/chord tones first"
    if level == "Intermediate":
        return "Intermediate Sheet — fuller rhythm, chord tones, guide tones, and coordination"
    return "Advanced Sheet — reharmonization ideas, motivic development, voice-leading, and improvisation"

def piano_adaptive_sheet(song, level, style, focus, history_summary):
    if level == "Beginner":
        return f"""
# Practice Sheet: {song}
## Piano — {level_header(level)}

### Right Hand Melody — Treble Clef Note Names
C5  D5  E5  G5  | E5  D5  C5  G4 |
A4  C5  E5  D5  | C5  -   -   -  |

### Left Hand — Bass Clef Roots
C3  -   -   -   | G2  -   -   -  |
A2  -   -   -   | F2  -   -   -  |

### Chords
| C | G | Am | F |

### Both Hands Together
- RH plays melody.
- LH plays one bass note per measure.
- Count: 1 2 3 4.
- Keep left hand softer.

### Practice Steps
1. Say right-hand note names out loud.
2. Play right hand only.
3. Play left hand only.
4. Put both hands together at 60 BPM.
5. Record one take.

### Focus
{focus}
"""
    if level == "Intermediate":
        return f"""
# Practice Sheet: {song}
## Piano — {level_header(level)}

### Right Hand Melody
C5 D5 E5 G5 | A5 G5 E5 D5 |
C5 E5 G5 A5 | G5 E5 D5 C5 |

### Left Hand Shell Voicings
Cmaj7: C3 + E3 + B3  
G7: G2 + F3 + B3  
Am7: A2 + G3 + C4  
Fmaj7: F2 + E3 + A3  

### Chord Progression
| Cmaj7 | G7 | Am7 | Fmaj7 |
| Dm7 | G7 | Cmaj7 | Cmaj7 |

### Both Hands Coordination
- LH plays shell voicing on beat 1.
- RH plays melody.
- Add LH comping on beat 1 and the “and” of 2.

### Chord-Tone Drill
For each chord, play 1–3–5–7 ascending, then 7–5–3–1 descending.

### Based on History
{history_summary}
"""
    return f"""
# Practice Sheet: {song}
## Piano — {level_header(level)}

### Advanced Form
A: | Cmaj7 | E7alt | Am9 | Gm7 C7 |
B: | Fmaj7 | Fm7 Bb7 | Em7 A7 | Dm7 G7 |
Final A: | Cmaj9 | A7alt | Dm9 G13 | C6/9 |

### Advanced Piano Tasks
- Right hand: melody, then harmonized melody.
- Left hand: rootless voicings.
- Chorus 1: guide tones only.
- Chorus 2: motif development.
- Chorus 3: reharmonized final cadence.

### Main Focus
{focus}
"""

def guitar_adaptive_sheet(song, level, style, focus, history_summary):
    if level == "Beginner":
        return f"""
# Practice Sheet: {song}
## Guitar — {level_header(level)}

### Chords
| C | G | Am | F |

### Simple Strumming Pattern
Down  Down-Up  Up-Down-Up  
Count: 1  2-&  &-4-&

### Melody on High E / B Strings
E string: 0 1 3 | 3 1 0  
B string: 1 3 1 | 0 1

### Chord Change Drill
C → G | G → Am | Am → F | F → C

### Practice Steps
1. Mute strings and strum rhythm only.
2. Play chords without rhythm.
3. Add rhythm slowly.
4. Play melody separately.
5. Record one clean rhythm take.
"""
    if level == "Intermediate":
        return f"""
# Practice Sheet: {song}
## Guitar — {level_header(level)}

### Chord Progression
| Cmaj7 | G7 | Am7 | Fmaj7 |
| Dm7 | G7 | Cmaj7 | Cmaj7 |

### Comping Pattern
Beat 1: bass note  
Beat 2-and: chord stab  
Beat 4: light upstroke

### Solo Drill
Only use chord tones for one chorus:
Cmaj7: C E G B  
G7: G B D F  
Am7: A C E G  
Fmaj7: F A C E  

### Strumming Tips
- Keep right hand moving.
- Accent 2 and 4.
- For pop: lighter sustained strums.
- For funk: shorter muted strums.
"""
    return f"""
# Practice Sheet: {song}
## Guitar — {level_header(level)}

### Advanced Chord Map
| Cmaj9 | E7#9 | Am9 | Gm9 C13 |
| Fmaj9 | Fm9 Bb13 | Em9 A13 | Dm9 G13 |

### Advanced Tasks
- Shell voicings only.
- Drop-2 voicings on top four strings.
- Chord melody with melody note on top.
- Chorus 1: chord tones only.
- Chorus 2: chromatic approaches.
- Chorus 3: motif development.
"""

def wind_adaptive_sheet(song, instrument, level, style, focus, history_summary):
    if instrument == "Flute":
        notes = "G4 A4 B4 C5 | D5 C5 B4 A4 | G4 B4 D5 C5 | B4 A4 G4"
        reminder = "Use steady air and avoid squeezing the embouchure."
    elif instrument == "Trumpet":
        notes = "C4 D4 E4 F4 | G4 F4 E4 D4 | C4 E4 G4 F4 | E4 D4 C4"
        reminder = "Use air support, avoid mouthpiece pressure, and rest often."
    else:
        notes = "D4 E4 F4 G4 | A4 G4 F4 E4 | D4 F4 A4 G4 | F4 E4 D4"
        reminder = "Use full tone, clear articulation, and stable intonation."

    if level == "Beginner":
        return f"""
# Practice Sheet: {song}
## {instrument} — {level_header(level)}

### Written Note Exercise
{notes}

### Rhythm
All quarter notes first.

### Articulation
Tongue each note clearly: TA TA TA TA.

### Practice Steps
1. Say note names.
2. Clap rhythm.
3. Play slowly.
4. Add phrase shape.
5. Record one take.

### Tone Reminder
{reminder}
"""
    if level == "Intermediate":
        return f"""
# Practice Sheet: {song}
## {instrument} — {level_header(level)}

### Melody Study
{notes}

### Variation
Play the same notes as:
- quarter notes
- eighth notes
- slurred pairs
- tongue two / slur two

### Chord Tone Study
| Dm7 | G7 | Cmaj7 | Cmaj7 |

Dm7: D F A C  
G7: G B D F  
Cmaj7: C E G B  

### Improvisation
Use only chord tones for one chorus.
"""
    return f"""
# Practice Sheet: {song}
## {instrument} — {level_header(level)}

### Advanced Etude
{notes} | add chromatic approaches into target notes

### Guide Tone Study
| Dm7 | G7 | Cmaj7 | A7alt |
| Dm7 | G7 | Cmaj7 | Cmaj7 |

### Scale Colors
- Minor 7: Dorian
- Dominant 7: Mixolydian / altered color
- Major 7: major scale / lydian color
- Klezmer/freygish: lowered 2nd and raised 3rd color
"""

def voice_adaptive_sheet(song, level, style, focus, history_summary):
    return f"""
# Practice Sheet: {song}
## Voice — {level_header(level)}

### Vocal Melody Practice
Sing on “la” first, then use words later.

### Pitch Exercise
1–2–3–5–3–2–1  
Repeat in 3 comfortable keys.

### Breath Marks
Mark breaths before singing the full phrase.

### Focus
{focus}
"""

def general_adaptive_sheet(song, instrument, level, style, focus, history_summary):
    return f"""
# Practice Sheet: {song}
## {instrument} — {level_header(level)}

### Melody
Learn the melody in 2-measure chunks.

### Harmony
Practice roots first, then chord tones.

### Rhythm
Clap before playing.

### Focus
{focus}
"""

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

tabs=st.tabs(["Practice Memory","Find / Analyze Any Song","Daily Plan","Adaptive Practice Sheet","Backing Track","Record & Analyze","Multitrack","Log"])

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

    st.subheader("Practice Sheet / Written Notes")
    st.caption("These are original practice-version note exercises, not copyrighted sheet music.")
    sheet = song_practice_sheet_music(song, instrument)
    if sheet:
        st.markdown(sheet)
    else:
        st.info("Choose Piano, Flute, or Trumpet to see written-note practice sheets.")

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
    extra_instr = instrument_specific_exercises(instrument, st.session_state.song)
    if extra_instr:
        st.markdown(extra_instr)

    note_ex = written_note_exercises(instrument, st.session_state.song)
    if note_ex:
        st.markdown(note_ex)

    sheet_ex = song_practice_sheet_music(st.session_state.song, instrument)
    if sheet_ex:
        st.markdown(sheet_ex)


with tabs[3]:
    st.header("Adaptive Practice Sheet Generator")
    st.write(
        "This creates an original practice-version sheet based on the selected song, instrument, level, focus, and previous history. "
        "It does not copy copyrighted sheet music."
    )

    sheet_song = st.text_input("Song for practice sheet", st.session_state.song, key="sheet_song")
    sheet_artist = st.text_input("Artist/composer", st.session_state.artist, key="sheet_artist")
    sheet_level = st.selectbox("Sheet difficulty level", ["Beginner", "Intermediate", "Advanced"], index=["Beginner","Intermediate","Advanced"].index(level))
    sheet_focus = st.selectbox("Sheet focus", skills or SKILLS[instrument], key="sheet_focus")

    if st.button("Create adaptive practice sheet"):
        sheet = adaptive_sheet_for_player(
            song=sheet_song,
            artist=sheet_artist,
            instrument=instrument,
            level=sheet_level,
            style=style,
            focus=sheet_focus,
            history_summary=history_text()
        )
        st.markdown(sheet)

        st.download_button(
            "Download practice sheet as text",
            data=sheet,
            file_name=f"{sheet_song.replace(' ','_')}_{instrument}_{sheet_level}_practice_sheet.txt",
            mime="text/plain"
        )

        add_log({
            "date": str(date.today()),
            "song": sheet_song,
            "instrument": instrument,
            "focus": sheet_focus,
            "rating": 6,
            "note": f"Generated adaptive {sheet_level} practice sheet"
        })


with tabs[4]:
    st.header("Backing Track Studio")
    st.write("Higher-quality synthesized band: fuller bass, more realistic drums, chord pads, comping patterns, stereo width, and light reverb. For true real-band audio, the next upgrade would use MIDI soundfonts or an AI music API.")
    bpm=st.slider("BPM",50,180,st.session_state.bpm,5)
    choruses=st.slider("Choruses",1,8,3)
    count=st.checkbox("Count-in",True)
    if st.button("Generate backing track"):
        wav=backing_track(style,instrument,bpm,choruses,count)
        st.session_state.bpm=bpm
        st.audio(wav,format="audio/wav")
        st.download_button("Download WAV",wav,file_name=f"{style}_{bpm}bpm.wav",mime="audio/wav")

with tabs[5]:
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

with tabs[6]:
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

with tabs[7]:
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
