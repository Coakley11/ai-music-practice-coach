# VERSION: forced_fix_make_demo_band_style_note_2026-05-04 21:34:19

# FIX: Required helper for backing track note
def make_demo_band_style_note():
    return (
        "This backing track uses synthesized bass, drums, chord pads, and comping patterns. "
        "It is a prototype, not a real studio band yet. A future version could use MIDI soundfonts, "
        "real instrument samples, or an external AI music API for more realistic band audio."
    )


import streamlit as st
from datetime import date
import io
import wave
import numpy as np
import pandas as pd
import tempfile
import os

try:
    import librosa
    import soundfile as sf
    AUDIO_ANALYSIS_AVAILABLE = True
except Exception:
    AUDIO_ANALYSIS_AVAILABLE = False

st.set_page_config(page_title="Daniel Cohen AI Music Practice Coach", page_icon="🎵", layout="wide")

INSTRUMENT_SKILLS = {
    "Saxophone": ["Tone / long tones", "Breath support", "Embouchure", "Articulation", "Major scales", "Minor scales", "Chord tones", "ii–V–I lines", "Improvisation", "Sight-reading"],
    "Guitar": ["Open chords", "Barre chords", "Triads", "Pentatonics", "Blues scale", "Strumming", "Rhythm", "Chord melody", "Improvisation", "Fretboard notes"],
    "Piano": ["Scales", "Chord inversions", "Shell voicings", "Rootless voicings", "Left-hand comping", "Sight-reading", "ii–V–I progressions", "Improvisation"],
    "Voice": ["Breath support", "Pitch accuracy", "Tone", "Range", "Vibrato", "Phrasing", "Diction", "Ear training"],
    "Other": ["Tone", "Technique", "Rhythm", "Scales", "Chords", "Improvisation", "Sight-reading", "Ear training"]
}

STYLE_SONGS = {
    "Jazz Swing": [
        "Autumn Leaves", "Fly Me to the Moon", "All of Me", "Take the A Train",
        "Blue Monk", "Satin Doll", "There Will Never Be Another You",
        "Just Friends", "Summertime", "Misty", "So What", "On Green Dolphin Street",
        "Stella by Starlight", "All the Things You Are", "Have You Met Miss Jones"
    ],
    "Bossa Nova": [
        "Blue Bossa", "Girl from Ipanema-style Study", "Corcovado-style Study",
        "Wave-style Study", "Black Orpheus-style Study", "Minor Bossa Study",
        "Meditation-style Study", "One Note Samba-style Study"
    ],
    "Blues": [
        "12-Bar Blues in F", "C Jam Blues", "Now's the Time-style Study",
        "Straight No Chaser-style Study", "Stormy Monday-style Study",
        "Tenor Madness-style Study", "Billie's Bounce-style Study",
        "Blue Seven-style Study"
    ],
    "Jewish / Klezmer / Wedding": [
        "Hava Nagila", "Od Yishama", "Siman Tov U'Mazal Tov",
        "Mazel Tov Medley", "Freygish Dance Study", "Klezmer Hora Study",
        "Nigun Practice Study", "Yismechu-style Study", "D minor Freygish Study"
    ],
    "Funk": [
        "Funk Groove Study", "Chameleon-style Groove", "Cissy Strut-style Groove",
        "Superstition-style Groove", "Pick Up the Pieces-style Groove",
        "Watermelon Man-style Groove", "The Chicken-style Groove"
    ],
    "Pop / Ballad": [
        "Stand By Me-style Study", "Let It Be-style Study", "Simple Ballad Study",
        "Perfect-style Study", "Someone Like You-style Study",
        "Hallelujah-style Study", "Lean on Me-style Study", "Yesterday-style Study"
    ]
}
SONG_LIBRARY = {
    "Autumn Leaves": {
        "key": "G minor / Bb major", "style": "Jazz Swing", "default_bpm": 110,
        "progression": [("Cm7", 1), ("F7", 1), ("Bbmaj7", 1), ("Ebmaj7", 1), ("Am7b5", 1), ("D7", 1), ("Gm7", 2)],
        "analysis": "A classic cycle-of-fourths tune with major and minor ii–V–I movement.",
        "improv": "Target 3rds and 7ths. Land chord tones on beat 1 and use passing tones."
    },
    "Blue Bossa": {
        "key": "C minor", "style": "Bossa Nova", "default_bpm": 120,
        "progression": [("Cm7", 2), ("Fm7", 2), ("Dm7b5", 1), ("G7", 1), ("Cm7", 2), ("Dbmaj7", 2), ("G7", 2), ("Cm7", 2)],
        "analysis": "A minor bossa progression with smooth ii–V motion back to C minor.",
        "improv": "Use C Dorian/C minor pentatonic and outline the ii–V back to C minor."
    },
    "12-Bar Blues in F": {
        "key": "F", "style": "Blues", "default_bpm": 95,
        "progression": [("F7", 1), ("Bb7", 1), ("F7", 2), ("Bb7", 2), ("F7", 2), ("C7", 1), ("Bb7", 1), ("F7", 1), ("C7", 1)],
        "analysis": "A foundational I7–IV7–V7 blues form.",
        "improv": "Use F blues scale, F minor pentatonic, and target 3rds on each dominant chord."
    },
    "Hava Nagila": {
        "key": "D Freygish / D minor flavor", "style": "Jewish / Klezmer / Wedding", "default_bpm": 135,
        "progression": [("Dm", 2), ("A7", 2), ("Dm", 2), ("A7", 2), ("Dm", 2), ("Gm", 1), ("A7", 1), ("Dm", 2)],
        "analysis": "A freygish/klezmer sound built from tonic-minor and dominant tension.",
        "improv": "Use D Freygish: D Eb F# G A Bb C D. Add turns, slides, accents, and energetic articulation."
    },
    "Fly Me to the Moon": {
        "composer": "Bart Howard",
        "key": "C major / A minor",
        "style": "Jazz Swing",
        "default_bpm": 120,
        "progression": [("Am7", 1), ("Dm7", 1), ("G7", 1), ("Cmaj7", 1), ("Fmaj7", 1), ("Bm7b5", 1), ("E7", 1), ("Am7", 1)],
        "analysis": "A circle progression moving through minor and major resolution points.",
        "improv": "Connect guide tones and use short melodic cells through each ii–V movement."
    },
    "All of Me": {
        "composer": "Gerald Marks / Seymour Simons",
        "key": "C major",
        "style": "Jazz Swing",
        "default_bpm": 125,
        "progression": [("Cmaj7", 2), ("E7", 2), ("A7", 2), ("Dm7", 2), ("E7", 2), ("Am7", 2), ("D7", 2), ("Dm7", 1), ("G7", 1)],
        "analysis": "Classic jazz standard with secondary dominants that pull strongly toward temporary targets.",
        "improv": "Target the 3rd of each dominant chord and resolve clearly into the next chord."
    },
    "Take the A Train": {
        "composer": "Billy Strayhorn",
        "key": "C major",
        "style": "Jazz Swing",
        "default_bpm": 145,
        "progression": [("Cmaj7", 2), ("D7", 2), ("Dm7", 1), ("G7", 1), ("Cmaj7", 2), ("Fmaj7", 2), ("D7", 2), ("Dm7", 1), ("G7", 1), ("Cmaj7", 2)],
        "analysis": "A bright swing tune with a strong secondary dominant sound.",
        "improv": "Use C major language, then highlight D7 with dominant chord tones."
    },
    "Blue Monk": {
        "composer": "Thelonious Monk",
        "key": "Bb blues",
        "style": "Blues",
        "default_bpm": 100,
        "progression": [("Bb7", 4), ("Eb7", 2), ("Bb7", 2), ("F7", 1), ("Eb7", 1), ("Bb7", 1), ("F7", 1)],
        "analysis": "A blues form with a memorable chromatic melody and strong groove.",
        "improv": "Use Bb blues scale, dominant chord tones, and simple rhythmic motifs."
    },
    "Satin Doll": {
        "composer": "Duke Ellington / Billy Strayhorn",
        "key": "C major",
        "style": "Jazz Swing",
        "default_bpm": 120,
        "progression": [("Dm7", 1), ("G7", 1), ("Dm7", 1), ("G7", 1), ("Em7", 1), ("A7", 1), ("Em7", 1), ("A7", 1), ("Am7", 1), ("D7", 1), ("Abm7", 1), ("Db7", 1), ("Cmaj7", 2)],
        "analysis": "A chain of ii–V patterns with smooth dominant movement.",
        "improv": "Practice ii–V vocabulary in small chunks and connect each pair."
    },
    "C Jam Blues": {
        "composer": "Duke Ellington",
        "key": "C blues",
        "style": "Blues",
        "default_bpm": 115,
        "progression": [("C7", 4), ("F7", 2), ("C7", 2), ("G7", 1), ("F7", 1), ("C7", 1), ("G7", 1)],
        "analysis": "A simple blues melody over a standard blues form. Excellent for timing and phrasing.",
        "improv": "Use C blues scale, call-and-response, and repeated rhythmic ideas."
    },
    "Od Yishama": {
        "composer": "Traditional / Jewish wedding repertoire",
        "key": "D minor practice key",
        "style": "Jewish / Klezmer / Wedding",
        "default_bpm": 125,
        "progression": [("Dm", 2), ("Gm", 2), ("A7", 2), ("Dm", 2), ("F", 2), ("Gm", 1), ("A7", 1), ("Dm", 2)],
        "analysis": "A Jewish wedding-style progression emphasizing minor color and dominant return.",
        "improv": "Use minor and freygish colors, ornaments, and strong dance rhythm."
    },
    "Siman Tov U'Mazal Tov": {
        "composer": "Traditional",
        "key": "D minor / major celebration feel",
        "style": "Jewish / Klezmer / Wedding",
        "default_bpm": 145,
        "progression": [("Dm", 2), ("A7", 2), ("A7", 2), ("Dm", 2), ("Gm", 2), ("Dm", 2), ("A7", 2), ("Dm", 2)],
        "analysis": "A celebratory tune built on clear tonic-dominant motion.",
        "improv": "Keep phrases short, rhythmic, and energetic. Add ornaments at phrase endings."
    }

}

NOTE_TO_MIDI = {"C":60,"C#":61,"Db":61,"D":62,"D#":63,"Eb":63,"E":64,"F":65,"F#":66,"Gb":66,"G":67,"G#":68,"Ab":68,"A":69,"A#":70,"Bb":70,"B":71}

def chord_notes(chord):
    root = chord[:2] if len(chord) > 1 and chord[1] in ["b", "#"] else chord[0]
    root_midi = NOTE_TO_MIDI.get(root, 60)
    if "maj7" in chord:
        intervals = [0, 4, 7, 11]
    elif "m7b5" in chord:
        intervals = [0, 3, 6, 10]
    elif "m7" in chord:
        intervals = [0, 3, 7, 10]
    elif "m" in chord and "maj" not in chord:
        intervals = [0, 3, 7]
    elif "7" in chord:
        intervals = [0, 4, 7, 10]
    else:
        intervals = [0, 4, 7]
    return [root_midi + i for i in intervals]

def midi_to_freq(midi_note):
    return 440.0 * (2 ** ((midi_note - 69) / 12))

def sine_note(freq, duration, sr=22050, volume=0.15):
    t = np.linspace(0, duration, int(sr * duration), False)
    sound = np.sin(2 * np.pi * freq * t)
    attack = max(1, int(0.01 * sr))
    release = max(1, int(0.04 * sr))
    env = np.ones_like(sound)
    env[:attack] = np.linspace(0, 1, attack)
    env[-release:] = np.linspace(1, 0, release)
    return volume * sound * env

def noise_hit(duration, sr=22050, volume=0.10, decay=20):
    n = int(sr * duration)
    noise = np.random.uniform(-1, 1, n)
    env = np.exp(-np.linspace(0, decay, n))
    return volume * noise * env

def add(buffer, start, sound):
    end = min(len(buffer), start + len(sound))
    if end > start:
        buffer[start:end] += sound[:end-start]

def make_backing_track(song_name, bpm, style, instrument, choruses=2, count_in=True):
    sr = 22050
    beat = 60 / bpm
    bar = beat * 4
    progression = SONG_LIBRARY[song_name]["progression"]
    total_bars = sum(bars for _, bars in progression) * choruses + (1 if count_in else 0)
    audio = np.zeros(int(total_bars * bar * sr))
    current = bar if count_in else 0

    if count_in:
        for i in range(4):
            add(audio, int(i * beat * sr), sine_note(1200, 0.05, sr, 0.35))

    for _ in range(choruses):
        for chord, bars_count in progression:
            notes = chord_notes(chord)
            duration = bars_count * bar
            root = midi_to_freq(notes[0] - 24)

            for b in range(bars_count * 4):
                bt = current + b * beat
                add(audio, int(bt * sr), sine_note(root, beat * 0.70, sr, 0.17))
                if b % 4 in [0, 2]:
                    add(audio, int(bt * sr), sine_note(65, 0.10, sr, 0.30))
                if b % 4 in [1, 3]:
                    add(audio, int(bt * sr), noise_hit(0.10, sr, 0.12))
                hats = [0, .67] if style == "Jazz Swing" else [0, .5]
                for h in hats:
                    add(audio, int((bt + h * beat) * sr), noise_hit(0.04, sr, 0.035, 35))

            if instrument != "Piano":
                for n in notes:
                    add(audio, int(current * sr), sine_note(midi_to_freq(n), duration * 0.92, sr, 0.045))

            if instrument != "Guitar":
                for b in range(bars_count * 4):
                    bt = current + b * beat
                    for n in notes[:3]:
                        add(audio, int(bt * sr), sine_note(midi_to_freq(n+12), beat * .16, sr, 0.025))

            current += duration

    maxv = np.max(np.abs(audio))
    if maxv > 0:
        audio = audio / maxv * 0.85
    data = (audio * 32767).astype(np.int16)
    out = io.BytesIO()
    with wave.open(out, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(data.tobytes())
    out.seek(0)
    return out.getvalue()

def practice_block(instrument, minutes, focus):
    return [
        (max(3, int(minutes*.18)), "Warmup", f"Warm up slowly. Focus on {focus}."),
        (max(5, int(minutes*.30)), "Technique", f"Isolate {focus} with a metronome."),
        (max(7, int(minutes*.35)), "Song Work", "Practice the song in small sections with the backing track."),
        (max(3, int(minutes*.17)), "Record & Review", "Record one take and write one thing to improve.")
    ]

def feedback(instrument, song, focus, rating):
    strengths = ["You created a feedback loop by recording yourself, which is one of the fastest ways to improve."]
    needs = []
    plan = []
    if rating < 6:
        needs.append("Slow the track down and isolate the hardest 4–8 measures.")
    else:
        strengths.append("Your self-rating suggests the take felt reasonably controlled.")
    if instrument == "Saxophone":
        needs += ["Check intonation on long notes and phrase endings.", "Listen for whether your tone stays full when the chords change."]
        plan += ["5 minutes long tones with tuner.", "One chorus using only chord tones.", "One chorus using simple 2–4 note phrases."]
    elif instrument == "Guitar":
        needs += ["Check whether chord changes happen exactly in time.", "Listen for buzzing notes or uneven strumming."]
        plan += ["Loop two chords at a time.", "Practice triads over the progression.", "Record one clean rhythm-only take."]
    elif instrument == "Piano":
        needs += ["Check left/right hand coordination.", "Listen for whether voicings are clear and rhythm is steady."]
        plan += ["Practice shell voicings alone.", "Add melody only after the left hand feels automatic."]
    else:
        needs += ["Focus on timing, tone, and clarity."]
        plan += ["Practice slowly, then medium, then full tempo."]
    plan.append(f"Main focus for next session: {focus} on {song}.")
    return strengths, needs, plan

if "practice_log" not in st.session_state:
    st.session_state.practice_log = []

st.sidebar.title("🎵 Music Coach Setup")
name = st.sidebar.text_input("Your name", "Daniel")
instrument = st.sidebar.selectbox("Main instrument", list(INSTRUMENT_SKILLS.keys()))
level = st.sidebar.selectbox("Current level", ["Beginner", "Intermediate", "Advanced"])
style = st.sidebar.selectbox("Main style", list(STYLE_SONGS.keys()))
minutes = st.sidebar.slider("Practice time today", 10, 120, 30, step=5)
skills = st.sidebar.multiselect("Skills you already work on", INSTRUMENT_SKILLS[instrument], default=INSTRUMENT_SKILLS[instrument][:3])
custom_skill = st.sidebar.text_input("Add your own skill/focus", "")
if custom_skill and custom_skill not in skills:
    skills.append(custom_skill)
goals = st.sidebar.text_area("Your current music goal", "I want to know what to practice next and improve consistently.")

st.title("🎵 Daniel Cohen AI MUSIC PRACTICE COACH")
st.caption("Practice plans, backing tracks, recording feedback, song coaching, and theory breakdowns.")

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["Profile", "Practice Plan", "Song Coach", "Backing Track Studio", "Record & Feedback", "Progress Log"])

with tab1:
    st.header(f"{name}'s Music Profile")
    c1, c2, c3 = st.columns(3)
    c1.metric("Instrument", instrument)
    c2.metric("Level", level)
    c3.metric("Style", style)
    st.write("**Goal:**")
    st.info(goals)
    st.write("**Current skills:**", ", ".join(skills) if skills else "None selected")
    if instrument == "Saxophone":
        st.success("Recommended focus: tone, breath support, chord tones, and phrasing.")
    elif instrument == "Guitar":
        st.success("Recommended focus: rhythm, triads, clean chord changes, and fretboard knowledge.")
    elif instrument == "Piano":
        st.success("Recommended focus: voicings, left-hand rhythm, and chord progressions.")
    else:
        st.success("Recommended focus: tone, rhythm, and one clear technical skill.")

with tab2:
    st.header("Today's Personalized Practice Plan")
    focus = st.selectbox("Today's focus", INSTRUMENT_SKILLS[instrument])
    for mins, title, text in practice_block(instrument, minutes, focus):
        st.markdown(f"### {title} — {mins} minutes")
        st.write(text)
    st.info("Music is not judged like one math test. Improvement comes from repetition, feel, listening, tone, and consistency.")

with tab3:
    st.header("Song Coach")
    rec = STYLE_SONGS.get(style, ["Autumn Leaves"])[0]
    st.subheader("Recommended song")
    st.success(rec)
    song_choice = st.selectbox("Choose song for theory analysis", list(SONG_LIBRARY.keys()))
    data = SONG_LIBRARY[song_choice]
    st.write(f"**Key:** {data['key']}")
    st.write(f"**Progression:** {' | '.join([ch for ch, bars in data['progression']])}")
    st.write(f"**Analysis:** {data['analysis']}")
    st.write(f"**Improvisation idea:** {data['improv']}")
    st.write("**How to practice:** listen, clap rhythm, learn melody in chunks, practice slowly, record yourself.")

with tab4:
    st.header("Backing Track Studio")
    song = st.selectbox("Choose song", list(SONG_LIBRARY.keys()), key="bt_song")
    default_bpm = SONG_LIBRARY[song]["default_bpm"]
    track_style = st.selectbox("Backing track style", ["Jazz Swing", "Bossa Nova", "Blues", "Jewish / Klezmer / Wedding", "Funk", "Pop / Ballad"])
    bpm = st.slider("Tempo / BPM", 50, 180, default_bpm, step=5)
    choruses = st.slider("Number of choruses", 1, 5, 2)
    count_in = st.checkbox("Include 4-beat count-in", value=True)
    st.info(f"Selected instrument: {instrument}. The backing track avoids making {instrument} the main backing instrument when possible.")
    st.caption(make_demo_band_style_note())
    if st.button("Generate backing track"):
        with st.spinner("Generating WAV backing track..."):
            wav = make_backing_track(song, bpm, track_style, instrument, choruses, count_in)
        st.audio(wav, format="audio/wav")
        st.download_button("Download backing track WAV", wav, file_name=f"{song.replace(' ','_')}_{bpm}bpm.wav", mime="audio/wav")

with tab5:
    st.header("Record Yourself & Get Feedback")
    st.write("Play the backing track, record yourself, then get a structured feedback report.")
    fb_song = st.selectbox("Song you recorded", list(SONG_LIBRARY.keys()), key="fb_song")
    fb_focus = st.selectbox("Main thing you practiced", INSTRUMENT_SKILLS[instrument], key="fb_focus")
    rating = st.slider("How do you think the take went?", 1, 10, 6)

    recorded = None
    try:
        recorded = st.audio_input("Record directly in the app")
    except Exception:
        st.warning("Your Streamlit version may not support direct microphone recording. Upload a file below instead.")

    uploaded = st.file_uploader("Or upload a recording", type=["wav", "mp3", "m4a", "ogg"])

    if recorded:
        st.audio(recorded)
    if uploaded:
        st.audio(uploaded)

    expected_bpm_for_analysis = st.number_input(
        "Expected backing-track BPM for timing comparison",
        min_value=40,
        max_value=220,
        value=int(st.session_state.last_backing_bpm) if st.session_state.last_backing_bpm else 100,
        step=5
    )

    if st.button("Analyze my playing"):
        audio_for_analysis = recorded if recorded else uploaded

        if not audio_for_analysis:
            st.warning("Record or upload audio first.")
        else:
            st.subheader("Real Audio Analysis")
            analysis = analyze_audio_real(audio_for_analysis, expected_bpm=expected_bpm_for_analysis)
            render_real_audio_metrics(analysis)

            real_strengths, real_needs, real_plan = audio_analysis_feedback(instrument, analysis)

            st.subheader("AI Feedback Based on Real Audio Metrics")
            st.markdown("### Strengths")
            for x in real_strengths:
                st.write(f"- {x}")

            st.markdown("### Needs Work")
            for x in real_needs:
                st.write(f"- {x}")

            st.markdown("### Practice Prescription")
            for x in real_plan:
                st.write(f"- {x}")

            st.subheader("Additional Coach Context")
            try:
                strengths, needs, plan = feedback(instrument, fb_song, fb_focus, rating, st.session_state.recent_notes_summary)
            except TypeError:
                strengths, needs, plan = feedback(instrument, fb_song, fb_focus, rating)

            for x in plan:
                st.write(f"- {x}")

            render_targeted_exercises(
                instrument=instrument,
                song_name=fb_song,
                level=level,
                focus=fb_focus,
                rating=rating,
                recent_notes=st.session_state.recent_notes_summary
            )

            st.info(
                "This version now performs real basic audio analysis using librosa: tempo, onsets, volume stability, and pitch stability. "
                "It is still not a full professional transcription system, but it is real analysis rather than only self-rating logic."
            )

with tab6:
    st.header("Progress Log")
    with st.form("log_form"):
        log_date = st.date_input("Date", value=date.today())
        practiced = st.text_input("What did you practice?")
        log_rating = st.slider("How did it feel?", 1, 10, 6)
        note = st.text_area("Notes / what improved / what was hard")
        submitted = st.form_submit_button("Add practice log")
    if submitted:
        st.session_state.practice_log.append({"date": str(log_date), "instrument": instrument, "style": style, "practiced": practiced, "rating": log_rating, "note": note})
        st.success("Practice log added.")
    if st.session_state.practice_log:
        st.dataframe(pd.DataFrame(st.session_state.practice_log), use_container_width=True)
    else:
        st.info("No practice logs yet.")