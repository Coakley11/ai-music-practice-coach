Daniel Cohen AI MUSIC PRACTICE COACH
A Streamlit app prototype for a personalized AI-powered music practice coach.
New in this version: real audio analysis
This version adds real audio analysis using `librosa` and `soundfile`.
The app can now analyze a recorded or uploaded practice take and estimate:
recording duration
estimated tempo
tempo difference from selected backing-track BPM
onset density / note-attack activity
volume stability
rough pitch stability
median detected pitch/note when pitched material is detected
Then it gives feedback on:
timing
pitch stability
tone/volume consistency
whether the player may be rushing or playing too many notes
what to practice next
Existing features
Targeted exercise generator for weak areas
Larger song lists across styles
More instrument skills and custom skill entry
Practice history and history-based recommendations
Backing track generator
Multitrack recorder prototype
Full song form breakdowns by section
Complete chord progressions for each section
Chord chart tables
Deeper chord, scale, and chord-outline analysis
Level-based analysis
Microphone input
Record/upload feature
Progress log
Important note
This is real audio analysis, but still a prototype.
It does not yet perform full automatic transcription, exact wrong-note detection, or perfect comparison against the backing track. For that, a future version could add:
note transcription
beat-aligned comparison against generated backing track
chord-scale matching
intonation scoring by note
automatic section detection
multi-track alignment and mixing
Run locally
```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```
Streamlit Cloud main file path
```text
streamlit_app.py
```
