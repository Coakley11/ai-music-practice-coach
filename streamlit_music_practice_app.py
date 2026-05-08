# VERSION: v33_fixed_genres_nameerror
if "GENRES" not in globals():
    GENRES = ["Jazz", "Pop", "Rock", "Funk", "Blues", "Classical"]

# VERSION: v32_fixed_song_library_nameerror

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import io, json, wave
from pathlib import Path
from datetime import date


GENRES = ["Jazz", "Pop", "Rock", "Funk", "Blues", "Classical"]

st.set_page_config(page_title="Daniel Cohen AI Music Practice Coach", page_icon="🎵", layout="wide")
st.title("🎵 Daniel Cohen AI MUSIC PRACTICE COACH")
st.caption("Simple workflow: choose genre → choose song → daily plan/practice sheet → backing track → log.")

DATA_FILE = Path("practice_history.json")


# ============================================================
# GENRE SETUP + FULL SONG SECTION SUPPORT
# ============================================================

GENRE_SONG_MAP = {
    "Pop": ["Shape of You", "Perfect", "Viva La Vida"],
    "Rock": ["Don't Stop Believin'", "Let It Be", "Say", "Gravity"],
    "Jazz": ["Autumn Leaves", "Blue Bossa", "So What", "All The Things You Are"],
    "Funk": ["Superstition", "Cissy Strut"],
    "Blues": ["Gravity"],
}

# Additional jazz/funk practice charts

# Removed old undefined SONG_LIBRARY patch.



# -----------------------------
# Sidebar setup
# -----------------------------
st.sidebar.header("Setup")

genre = st.sidebar.selectbox("What kind of music do you want to play today?", GENRES)
song_options = list(SONG_LIBRARY[genre].keys())
song = st.sidebar.selectbox(f"Choose a {genre} song", song_options)

instrument = st.sidebar.selectbox("Instrument", ["Piano", "Guitar", "Saxophone", "Flute", "Trumpet", "Voice", "Other"])
level = st.sidebar.selectbox("Level", ["Beginner", "Intermediate", "Advanced"])
focus = st.sidebar.selectbox("Skill/focus", ["Melody", "Chords / Harmony", "Rhythm / Timing", "Tone", "Improvisation", "Technique"])
display_key = st.sidebar.selectbox("Transpose/display key", COMMON_KEYS, index=COMMON_KEYS.index(SONG_LIBRARY[genre][song]["key"]) if SONG_LIBRARY[genre][song]["key"] in COMMON_KEYS else 0)
minutes = st.sidebar.slider("Practice minutes", 10, 120, 30, 5)

song_data = get_song_data(genre, song).copy()
song_data["title"] = song
sections = transpose_sections(song_data, display_key)
all_chords = all_progression_from_sections(sections)

# -----------------------------
# Tabs — NO separate practice sheet tab
# -----------------------------
tabs = st.tabs(["Daily Practice Plan", "Song Search", "Backing Track", "Multitrack Recorder", "Practice Log"])

with tabs[0]:
    st.header("Daily Practice Plan")
    st.write(f"**Genre:** {genre} | **Song:** {song} — {song_data['artist']} | **Instrument:** {instrument} | **Level:** {level} | **Focus:** {focus}")

    st.markdown(full_chord_chart(song_data, sections, instrument))

    if "show_sheet" not in st.session_state:
        st.session_state.show_sheet = False
    if "harder_sheet" not in st.session_state:
        st.session_state.harder_sheet = False

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Generate practice sheet"):
            st.session_state.show_sheet = True
            st.session_state.harder_sheet = False
    with c2:
        if st.button("Generate another practice sheet"):
            st.session_state.show_sheet = True
            st.session_state.harder_sheet = False
    with c3:
        if st.button("Make it harder"):
            st.session_state.show_sheet = True
            st.session_state.harder_sheet = True

    if st.session_state.show_sheet:
        st.markdown(practice_sheet(song, song_data, sections, instrument, level, focus, st.session_state.harder_sheet))
        st.subheader("Regular music notation")
        render_abc(abc_for_practice(song, sections, instrument, level))

    st.subheader("Harmony Breakdown")
    if st.button("Break down harmony and give improv tips"):
        st.markdown(full_chord_chart(song_data, sections, instrument))
        if level == "Beginner":
            st.write("Beginner improv: use chord roots first, then add 3rds and 5ths. Keep phrases short.")
        elif level == "Intermediate":
            st.write("Intermediate improv: use 1–3–5–7 chord tones and connect nearby notes between chords.")
        else:
            st.write("Advanced improv: use guide tones, chromatic approaches, motifs, substitutions, and rhythmic displacement.")

    st.subheader("Daily Time Plan")
    st.write(f"- Warmup: {max(5, int(minutes*.2))} minutes")
    st.write(f"- Song sections/chords: {max(8, int(minutes*.4))} minutes")
    st.write(f"- Focus skill ({focus}): {max(8, int(minutes*.25))} minutes")
    st.write(f"- Record/review: {max(5, int(minutes*.15))} minutes")

with tabs[1]:
    st.header("Song Search")
    st.write("The song list is filtered by the genre you picked in the Setup panel.")
    picked = st.selectbox(f"Pick a {genre} tune", song_options, index=song_options.index(song))
    st.info(f"To change the active song, choose it in the left Setup panel. Current active song: {song}.")
    preview = get_song_data(genre, picked).copy()
    preview["title"] = picked
    st.markdown(full_chord_chart(preview, transpose_sections(preview, display_key), instrument))

with tabs[2]:
    st.header("Backing Track")
    st.write(f"Backing track is based on the active song: **{song}**.")
    st.markdown(full_chord_chart(song_data, sections, instrument))

    bpm = st.slider("BPM", 50, 180, 100, 5)
    if st.button("Generate full-song backing track"):
        wav = generate_backing(all_chords, bpm=bpm)
        st.audio(wav, format="audio/wav")
        st.download_button("Download backing track WAV", wav, file_name=f"{song.replace(' ','_')}_backing_track.wav", mime="audio/wav")

with tabs[3]:
    st.header("Multitrack Recorder")
    if "tracks" not in st.session_state:
        st.session_state.tracks = {"Track 1": None, "Track 2": None, "Track 3": None}
    for tr in ["Track 1", "Track 2", "Track 3"]:
        st.subheader(tr)
        name = st.text_input(f"Instrument for {tr}", value=tr, key=f"{tr}_name")
        up = st.file_uploader(f"Upload audio for {tr}", type=["wav","mp3","m4a","ogg"], key=f"{tr}_upload")
        try:
            rec = st.audio_input(f"Record {tr}", key=f"{tr}_record")
        except Exception:
            rec = None
        if st.button(f"Save {tr}", key=f"{tr}_save"):
            audio = rec if rec is not None else up
            if audio is not None:
                st.session_state.tracks[tr] = audio.getvalue()
                st.success(f"{tr} saved.")
            else:
                st.warning("Record or upload audio first.")
        if st.session_state.tracks[tr]:
            st.write(f"Playback: {name}")
            st.audio(st.session_state.tracks[tr])
    if st.button("Clear all tracks"):
        st.session_state.tracks = {"Track 1": None, "Track 2": None, "Track 3": None}
        st.success("Tracks cleared.")

with tabs[4]:
    st.header("Practice Log")
    if st.button("Clear music practice / reset to default"):
        reset_history()
        st.success("Practice log cleared.")

    with st.form("log_form"):
        d = st.date_input("Date", date.today())
        what = st.text_area("What did you practice today?", value=f"{genre} practice — {song} — {instrument} — {focus}")
        rating = st.slider("How did it go?", 1, 10, 6)
        submitted = st.form_submit_button("Save music practice log")
    if submitted:
        add_log({"date": str(d), "genre": genre, "song": song, "instrument": instrument, "level": level, "focus": focus, "rating": rating, "practice": what})
        st.success("Music practice logged.")

    logs = load_history()
    if logs:
        st.dataframe(pd.DataFrame(logs), use_container_width=True)
    else:
        st.info("No practice logs yet.")
