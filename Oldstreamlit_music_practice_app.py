
import streamlit as st
from datetime import date

st.set_page_config(
    page_title="AI Music Practice Coach",
    page_icon="🎵",
    layout="wide"
)

INSTRUMENT_SKILLS = {
    "Saxophone": [
        "Tone / long tones", "Breath support", "Embouchure", "Articulation / tonguing",
        "Major scales", "Minor scales", "Pentatonics", "Blues scale",
        "Chord tones", "ii–V–I lines", "Improvisation", "Sight-reading"
    ],
    "Guitar": [
        "Open chords", "Barre chords", "Triads", "Major scales", "Minor scales",
        "Pentatonics", "Blues scale", "Fingerpicking", "Strumming", "Rhythm",
        "Chord melody", "Improvisation", "Fretboard notes"
    ],
    "Piano": [
        "Major scales", "Minor scales", "Chord inversions", "Shell voicings",
        "Rootless voicings", "Left-hand comping", "Sight-reading", "Rhythm",
        "ii–V–I progressions", "Improvisation", "Accompaniment"
    ],
    "Voice": [
        "Breath support", "Pitch accuracy", "Tone", "Range", "Vibrato",
        "Phrasing", "Diction", "Ear training", "Performance confidence"
    ],
    "Other": [
        "Tone", "Technique", "Rhythm", "Scales", "Chords", "Improvisation",
        "Sight-reading", "Ear training", "Performance"
    ]
}

STYLE_SONGS = {
    "Jazz": ["Autumn Leaves", "Blue Bossa", "Fly Me to the Moon", "All of Me", "Take the A Train"],
    "Blues": ["12-Bar Blues in F", "C Jam Blues", "Sweet Home Chicago", "Stormy Monday"],
    "Rock": ["Wish You Were Here", "Come Together", "Seven Nation Army", "Knockin' on Heaven's Door"],
    "Pop": ["Stand By Me", "Let It Be", "Perfect", "Someone Like You"],
    "Jewish / Klezmer / Wedding": ["Od Yishama", "Siman Tov U'Mazal Tov", "Hava Nagila", "Mazel Tov Medley"],
    "Funk": ["Cissy Strut", "Chameleon", "Superstition", "Pick Up the Pieces"],
    "Classical": ["Ode to Joy", "Minuet in G", "Canon in D", "Gymnopédie No. 1"]
}

COMMON_PROGRESSIONS = {
    "Autumn Leaves": {
        "key": "G minor / Bb major",
        "progression": "Cm7 → F7 → Bbmaj7 → Ebmaj7 → Am7♭5 → D7 → Gm",
        "analysis": "A classic cycle-of-fourths progression. It uses ii–V–I movement in major and minor, giving a strong feeling of tension and release.",
        "improv": "Target 3rds and 7ths. Use Bb major over the major section, then G harmonic minor or chord tones over the minor ii–V–I."
    },
    "Blue Bossa": {
        "key": "C minor",
        "progression": "Cm7 → Fm7 → Dm7♭5 → G7 → Cm7, with a brief Dbmaj7 → Gb7 → Cmaj7 shift",
        "analysis": "Mostly minor key harmony with a smooth bossa feel. The middle section briefly moves to a brighter major color.",
        "improv": "Use C minor pentatonic, C Dorian, and chord-tone targeting. Keep phrases relaxed and lyrical."
    },
    "12-Bar Blues in F": {
        "key": "F",
        "progression": "F7 → Bb7 → F7 → C7 → Bb7 → F7",
        "analysis": "A foundation progression built on I7, IV7, and V7. The dominant sound creates a bluesy tension throughout.",
        "improv": "Use F blues scale, F minor pentatonic, and target chord tones when the chord changes."
    },
    "Fly Me to the Moon": {
        "key": "C major / A minor",
        "progression": "Am7 → Dm7 → G7 → Cmaj7 → Fmaj7 → Bm7♭5 → E7 → Am7",
        "analysis": "A descending circle progression. It moves smoothly through functional harmony and is excellent for practicing ii–V relationships.",
        "improv": "Use chord tones, approach notes, and short melodic cells. Practice connecting guide tones."
    },
    "Hava Nagila": {
        "key": "Often D minor / Freygish sound",
        "progression": "Minor/freygish modal harmony with strong tonic-dominant motion",
        "analysis": "The distinctive sound comes from the freygish mode, similar to harmonic minor with a lowered 2nd flavor.",
        "improv": "Use D freygish: D Eb F# G A Bb C D. Add ornaments, turns, bends, and energetic articulation."
    }
}

def practice_block(instrument, minutes, level, focus):
    warmup = max(3, int(minutes * 0.18))
    technique = max(5, int(minutes * 0.30))
    song = max(7, int(minutes * 0.35))
    creative = max(3, minutes - warmup - technique - song)

    if instrument == "Saxophone":
        warm = "Long tones with tuner: hold notes steady, focus on full air and relaxed embouchure."
        tech = f"Scale/chord-tone work focused on {focus}: slow first, then metronome."
        songwork = "Play the melody in small phrases. Mark breaths. Focus on tone, intonation, and articulation."
        create = "Improvise 4-bar phrases using chord tones, then add passing notes."
    elif instrument == "Guitar":
        warm = "Finger warmup + clean chord changes. Use slow metronome."
        tech = f"Work on {focus}: isolate one shape or pattern and move it to 2 keys."
        songwork = "Practice verse/chorus sections slowly. Focus on rhythm and clean transitions."
        create = "Create a short 4-chord loop and improvise or write a melody over it."
    elif instrument == "Piano":
        warm = "Scales slowly with both hands, focusing on even tone."
        tech = f"Practice {focus}: inversions, voicings, or ii–V–I movement."
        songwork = "Play melody separately, then left-hand chords, then combine slowly."
        create = "Reharmonize 4 measures using simple substitutions."
    else:
        warm = "Tone/rhythm warmup with metronome."
        tech = f"Technique drill focused on {focus}."
        songwork = "Break the song into small sections and practice slowly."
        create = "Create a short phrase using today’s skill."

    return [
        (warmup, "Warmup", warm),
        (technique, "Technique", tech),
        (song, "Song Work", songwork),
        (creative, "Creative / Improvisation", create),
    ]

def recommend_song(style, level):
    songs = STYLE_SONGS.get(style, ["Simple Melody Study"])
    if level == "Beginner":
        return songs[0]
    if level == "Intermediate":
        return songs[min(1, len(songs)-1)]
    return songs[min(2, len(songs)-1)]

if "practice_log" not in st.session_state:
    st.session_state.practice_log = []

st.sidebar.title("🎵 Music Coach Setup")

name = st.sidebar.text_input("Your name", "Daniel")
instrument = st.sidebar.selectbox("Main instrument", list(INSTRUMENT_SKILLS.keys()))
level = st.sidebar.selectbox("Current level", ["Beginner", "Intermediate", "Advanced"])
style = st.sidebar.selectbox("Main style", list(STYLE_SONGS.keys()))
minutes = st.sidebar.slider("Practice time today", 10, 120, 30, step=5)

skills = st.sidebar.multiselect(
    "Skills you already work on",
    INSTRUMENT_SKILLS[instrument],
    default=INSTRUMENT_SKILLS[instrument][:3]
)

goals = st.sidebar.text_area(
    "Your current music goal",
    "I want to know what to practice next and improve consistently."
)

st.title("🎵 AI Music Practice Coach")
st.caption("A personalized practice planner, song recommender, and music theory coach.")

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Profile",
    "Practice Plan",
    "Song Coach",
    "Chord / Theory Breakdown",
    "Custom Exercise Generator",
    "Progress Log"
])

with tab1:
    st.header(f"{name}'s Music Profile")
    col1, col2 = st.columns(2)

    with col1:
        st.metric("Instrument", instrument)
        st.metric("Level", level)
        st.metric("Style", style)

    with col2:
        st.metric("Practice Time", f"{minutes} min")
        st.write("**Current goal:**")
        st.info(goals)

    st.subheader("Current Skills")
    if skills:
        st.write(", ".join(skills))
    else:
        st.warning("Select at least one skill in the sidebar.")

    st.subheader("Recommended next focus")
    if instrument == "Saxophone":
        st.success("Focus on tone + chord tones. For sax, great sound and strong chord targeting matter more than just playing many notes.")
    elif instrument == "Guitar":
        st.success("Focus on triads + rhythm. These create musical control across the fretboard.")
    elif instrument == "Piano":
        st.success("Focus on voicings + left-hand rhythm. This makes songs sound full and professional.")
    else:
        st.success("Focus on tone, rhythm, and one clear technical skill at a time.")

with tab2:
    st.header("Today's Personalized Practice Plan")

    focus = st.selectbox("What should today's focus be?", INSTRUMENT_SKILLS[instrument])
    plan = practice_block(instrument, minutes, level, focus)

    for mins, title, desc in plan:
        st.markdown(f"### {title} — {mins} minutes")
        st.write(desc)

    st.divider()
    st.subheader("Practice mindset")
    st.write(
        "Do not judge one practice session like a math test. Music improves through repetition, feel, tone, timing, and consistency over weeks."
    )

with tab3:
    st.header("Song Coach")

    known_songs = st.text_area(
        "Songs you have practiced recently",
        "Autumn Leaves, Hava Nagila, Fly Me to the Moon"
    )

    mode = st.radio("Recommendation type", ["Real song", "Create a custom practice song"])
    rec = recommend_song(style, level)

    if mode == "Real song":
        st.subheader("Recommended song")
        st.success(rec)
        st.write(f"Why: This fits your level, your style interest in **{style}**, and your instrument: **{instrument}**.")
    else:
        st.subheader("Custom practice song idea")
        st.success(f"{style} Practice Study in {level} Style")
        st.write("This would be a short original study designed around your selected skill and instrument.")

    st.subheader("How to practice the song")
    st.write("""
1. Listen once without playing.
2. Clap or tap the rhythm.
3. Learn the melody in 2–4 measure chunks.
4. Practice slowly with a metronome.
5. Add expression: dynamics, articulation, phrasing.
6. Record yourself and write one thing to improve.
""")

with tab4:
    st.header("Chord / Theory Breakdown")

    song_choice = st.selectbox(
        "Choose or type a song",
        list(COMMON_PROGRESSIONS.keys()) + ["Other / type below"]
    )

    custom_song = st.text_input("If other, type song title and composer", "")

    chosen = custom_song if song_choice == "Other / type below" and custom_song else song_choice

    if chosen in COMMON_PROGRESSIONS:
        data = COMMON_PROGRESSIONS[chosen]
        st.subheader(chosen)
        st.write(f"**Key:** {data['key']}")
        st.write(f"**Progression:** {data['progression']}")
        st.write(f"**Analysis:** {data['analysis']}")
        st.write(f"**Improvisation idea:** {data['improv']}")
    else:
        st.info("For a full AI version, this section would look up or analyze the song and generate a chord breakdown.")
        st.write("""
Prototype analysis:
- Identify the key center.
- List chords in order.
- Convert chords to Roman numerals.
- Look for ii–V–I, blues, modal, secondary dominants, or borrowed chords.
- Give instrument-specific improvisation ideas.
""")

    st.subheader("Instrument-specific approach")
    if instrument == "Saxophone":
        st.write("Use long tones before practicing. Then target 3rds and 7ths of each chord. Keep phrases singable.")
    elif instrument == "Guitar":
        st.write("Map the chords as triads first. Then add 7ths. Practice comping rhythm before soloing.")
    elif instrument == "Piano":
        st.write("Use shell voicings first: root + 3rd + 7th. Then try rootless voicings.")
    else:
        st.write("Start with rhythm and chord tones. Then add passing notes and stylistic details.")

with tab5:
    st.header("Custom Exercise Generator")

    exercise_focus = st.selectbox("Exercise focus", INSTRUMENT_SKILLS[instrument], key="exercise_focus")
    difficulty = st.select_slider("Difficulty", options=["Easy", "Medium", "Hard"], value="Medium")

    if st.button("Generate exercise"):
        st.subheader(f"{instrument} Exercise: {exercise_focus}")

        if instrument == "Saxophone":
            st.write("""
**Exercise**
- Play a concert Bb major scale slowly.
- Then play 1–3–5–7 arpeggios on each chord.
- Improvise using only chord tones for 2 minutes.
- Add one passing note between chord tones.
""")
        elif instrument == "Guitar":
            st.write("""
**Exercise**
- Choose one string set.
- Play major and minor triads in 3 inversions.
- Create a 4-chord progression.
- Improvise using only notes from those triads.
""")
        elif instrument == "Piano":
            st.write("""
**Exercise**
- Play ii–V–I in C, F, and Bb.
- Left hand: shell voicings.
- Right hand: simple melody using chord tones.
- Then add one chromatic approach note.
""")
        else:
            st.write("""
**Exercise**
- Pick one scale.
- Play it slowly with metronome.
- Create a 4-measure phrase.
- Repeat it with different rhythms.
""")

with tab6:
    st.header("Progress Log")

    with st.form("log_form"):
        log_date = st.date_input("Date", value=date.today())
        practiced = st.text_input("What did you practice?")
        rating = st.slider("How did it feel?", 1, 10, 6)
        note = st.text_area("Notes / what improved / what was hard")
        submitted = st.form_submit_button("Add practice log")

    if submitted:
        st.session_state.practice_log.append({
            "date": str(log_date),
            "instrument": instrument,
            "practiced": practiced,
            "rating": rating,
            "note": note
        })
        st.success("Practice log added.")

    if st.session_state.practice_log:
        st.subheader("Your logs")
        st.dataframe(st.session_state.practice_log, use_container_width=True)
    else:
        st.info("No practice logs yet.")
