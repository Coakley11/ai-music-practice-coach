# AI Music Practice Coach

A Streamlit app prototype for a personalized music practice coach.

## Features

- Instrument-specific practice plans
- Song recommendations
- Chord progression and theory breakdowns
- Backing track generator
- Adjustable tempo, style, and number of choruses
- Audio player and downloadable WAV practice tracks
- Record/upload feature for practice takes
- AI-style feedback report
- Progress log

## Important note

This version creates simple synthesized WAV backing tracks directly in Python.

The feedback feature is a prototype. It does not yet truly detect pitch, rhythm, tone, or wrong notes from the audio. It gives structured coaching feedback based on instrument, song, focus, and self-rating.

A future version could use real audio analysis to evaluate pitch accuracy, rhythm accuracy, tone, phrasing, and improvisation choices.

## Run locally

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Streamlit Cloud main file path

```text
streamlit_app.py
```
# ai-music-practice-coach
AI-powered Streamlit music practice coach that creates personalized practice plans, song recommendations, chord breakdowns, improvisation ideas, exercises, and progress logs by instrument.

# AI Music Practice Coach

A Streamlit prototype for a personalized AI-powered music practice app.

## What it does

- Lets the user choose an instrument: saxophone, guitar, piano, voice, or other
- Adapts practice plans to the instrument
- Creates daily practice routines
- Recommends songs based on level and style
- Breaks down common chord progressions
- Gives improvisation ideas
- Generates custom exercises
- Tracks practice logs

## How to run locally

Install Streamlit:

```bash
pip install streamlit
