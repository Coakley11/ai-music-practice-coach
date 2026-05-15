"""Hand-curated songs with practice-level harmony (priority accuracy for listed artists)."""

from __future__ import annotations

from typing import Any


def _ext(**kwargs) -> dict[str, Any]:
    """Reserved slots for MIDI / MusicXML / analysis / improvisation metadata."""
    base = {
        "midi_path": None,
        "musicxml_path": None,
        "harmonic_analysis": None,
        "arrangement_notes": None,
    }
    base.update({k: v for k, v in kwargs.items() if v is not None})
    return base


def _s(
    title: str,
    artist: str,
    genre: str,
    key: str,
    sections: dict[str, list[str]],
    *,
    guitar_tabs: dict[str, str] | None = None,
    composer: str | None = None,
    extensions: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "title": title,
        "artist": artist,
        "genre": genre,
        "key": key,
        "sections": sections,
        "guitar_tabs": guitar_tabs or {},
        "composer": composer,
        "extensions": extensions or _ext(),
    }


def curated_song_records() -> list[dict[str, Any]]:
    return [
        # --- John Mayer / Pop foundations ---
        _s("Say", "John Mayer", "Pop", "Bb", {
            "Verse": ["Bb", "F", "Gm", "Eb"],
            "Chorus": ["Bb", "F", "Eb", "Bb"],
            "Bridge": ["Gm", "F", "Eb", "Bb"],
            "Outro / Final Chorus": ["Bb", "F", "Eb", "Bb"],
        }, guitar_tabs={"Bb": "x13331", "F": "133211", "Gm": "355333", "Eb": "x68886", "Gm7": "353333"}),
        _s("Gravity", "John Mayer", "Pop", "G", {
            "Verse Groove": ["G", "C", "G", "C"],
            "Chorus / Lift": ["Em", "C", "G", "D"],
            "Solo Section": ["G7", "C7", "G7", "D7"],
        }, guitar_tabs={"G": "320003", "C": "x32010", "Em": "022000", "D": "xx0232", "G7": "320001", "C7": "x32310", "D7": "xx0212"}),
        _s("Waiting on the World to Change", "John Mayer", "Pop", "D", {
            "Verse": ["D", "Bm", "G", "A"],
            "Chorus": ["D", "Bm", "G", "A"],
            "Bridge": ["Em", "G", "D", "A"],
        }),
        _s("Daughters", "John Mayer", "Pop", "D", {
            "Verse": ["D", "G", "D", "A"],
            "Chorus": ["Bm", "G", "D", "A"],
            "Bridge": ["Em", "G", "D", "A"],
        }),
        _s("Slow Dancing in a Burning Room", "John Mayer", "Pop", "C#m", {
            "Verse": ["C#m", "A", "E", "B"],
            "Chorus": ["A", "E", "B", "C#m"],
            "Solo": ["C#m", "A", "E", "B"],
        }),

        # --- Ed Sheeran ---
        _s("Shape of You", "Ed Sheeran", "Pop", "C#m", {
            "Verse": ["C#m", "F#m", "A", "B"],
            "Pre-Chorus": ["C#m", "F#m", "A", "B"],
            "Chorus": ["C#m", "F#m", "A", "B"],
            "Bridge": ["C#m", "F#m", "A", "B"],
        }),
        _s("Perfect", "Ed Sheeran", "Pop", "G", {
            "Verse": ["G", "Em", "C", "D"],
            "Pre-Chorus": ["Em", "C", "G", "D"],
            "Chorus": ["G", "D", "Em", "C"],
            "Bridge": ["Em", "C", "G", "D"],
        }),
        _s("Thinking Out Loud", "Ed Sheeran", "Pop", "D", {
            "Verse": ["D", "D/F#", "G", "A"],
            "Pre-Chorus": ["Em", "A", "D", "Bm"],
            "Chorus": ["D", "D/F#", "G", "A"],
        }),
        _s("Photograph", "Ed Sheeran", "Pop", "E", {
            "Verse": ["E", "C#m", "B", "A"],
            "Chorus": ["E", "B", "C#m", "A"],
            "Bridge": ["C#m", "A", "E", "B"],
        }),
        _s("Bad Habits", "Ed Sheeran", "Pop", "Bm", {
            "Verse": ["Bm", "G", "D", "A"],
            "Pre-Chorus": ["Bm", "G", "D", "A"],
            "Chorus": ["Bm", "G", "D", "A"],
            "Bridge": ["G", "A", "Bm", "D"],
        }),
        _s("Castle on the Hill", "Ed Sheeran", "Pop", "D", {
            "Verse": ["D", "G", "Bm", "A"],
            "Pre-Chorus": ["G", "A", "Bm", "D"],
            "Chorus": ["D", "G", "Bm", "A"],
            "Bridge": ["G", "D", "A", "Bm"],
        }),
        _s("Shivers", "Ed Sheeran", "Pop", "Bm", {
            "Verse": ["Bm", "G", "D", "A"],
            "Pre-Chorus": ["Bm", "G", "D", "A"],
            "Chorus": ["Bm", "G", "D", "A"],
        }),
        _s("The A Team", "Ed Sheeran", "Pop", "A", {
            "Verse": ["A", "E", "F#m", "D"],
            "Chorus": ["A", "E", "F#m", "D"],
            "Bridge": ["D", "A", "E", "E"],
        }),

        # --- Coldplay (guitar-friendly, rehearsal-level form) ---
        _s("Viva La Vida", "Coldplay", "Pop", "Ab", {
            "Intro (Strings Figure)": ["Ab", "Fm", "Db", "Eb"],
            "Verse": ["Db", "Eb", "Ab", "Fm"],
            "Pre-Chorus (Lift)": ["Db", "Ab", "Eb", "Fm"],
            "Chorus": ["Db", "Eb", "Ab", "Fm"],
            "Bridge (Breakdown)": ["Db", "Eb", "Ab", "Ab"],
            "Final Chorus / Outro": ["Db", "Eb", "Ab", "Fm"],
        }),
        _s("Yellow", "Coldplay", "Pop", "B", {
            "Intro": ["B", "B", "F#", "E"],
            "Verse": ["B", "F#", "E", "B"],
            "Chorus": ["E", "B", "F#", "E"],
            "Bridge": ["G#m", "F#", "E", "B"],
            "Outro": ["E", "B", "F#", "B"],
        }),
        _s("Fix You", "Coldplay", "Pop", "Eb", {
            "Intro (Organ)": ["Eb", "Gm", "Cm", "Bb"],
            "Verse": ["Eb", "Gm", "Cm", "Bb"],
            "Pre-Chorus": ["Ab", "Bb", "Gm", "Cm"],
            "Chorus": ["Ab", "Eb", "Bb", "Cm"],
            "Bridge (Build)": ["Ab", "Eb", "Bb", "Cm"],
            "Outro / Resolution": ["Ab", "Eb", "Bb", "Eb"],
        }),
        _s("The Scientist", "Coldplay", "Pop", "F", {
            "Intro": ["Dm", "Bb", "F", "F"],
            "Verse": ["Dm", "Bb", "F", "F"],
            "Pre-Chorus": ["Gm", "Bb", "F", "F"],
            "Chorus": ["Bb", "F", "C", "Dm"],
            "Bridge": ["Bb", "F", "C", "Dm"],
            "Outro": ["Dm", "Bb", "F", "F"],
        }),
        _s("Clocks", "Coldplay", "Pop", "Eb", {
            "Intro / Piano Riff": ["Eb", "Bbm", "Fm", "Fm"],
            "Verse (Riff)": ["Eb", "Bbm", "Fm", "Fm"],
            "Chorus": ["Ab", "Eb", "Bbm", "Fm"],
            "Bridge": ["Db", "Ab", "Eb", "Bbm"],
            "Solo / Outro Riff": ["Eb", "Bbm", "Fm", "Fm"],
        }),
        _s("A Sky Full of Stars", "Coldplay", "Pop", "F", {
            "Intro": ["F", "Am", "Dm", "Bb"],
            "Verse": ["F", "Am", "Dm", "Bb"],
            "Pre-Chorus": ["Bb", "C", "Dm", "Am"],
            "Chorus": ["F", "Am", "Dm", "Bb"],
            "Bridge": ["Bb", "C", "Dm", "F"],
            "Outro": ["F", "Am", "Dm", "Bb"],
        }),
        _s("Paradise", "Coldplay", "Pop", "F", {
            "Intro (Synth Theme)": ["F", "Gm", "Bb", "Dm"],
            "Verse": ["F", "Gm", "Bb", "Dm"],
            "Pre-Chorus": ["Gm", "Bb", "F", "C"],
            "Chorus": ["Bb", "F", "C", "Dm"],
            "Bridge": ["Gm", "Bb", "F", "C"],
            "Outro": ["Bb", "F", "C", "Dm"],
        }),

        # --- Billy Joel (composer = self where applicable) ---
        _s("Piano Man", "Billy Joel", "Pop", "C", {
            "Intro (Pickup / Band In)": ["C", "G/B", "Am", "C/G", "F", "C/E", "Dm7", "G7"],
            "Verse (Story)": ["C", "G/B", "Am", "C/G", "F", "C/E", "Dm7", "G7"],
            "Chorus (Sing Us a Song)": ["C", "G/B", "Am", "C/G", "F", "G", "C", "G"],
            "Instrumental / Harmonica Solo": ["C", "G", "F", "G", "C", "G", "F", "G"],
            "Final Chorus / Outro": ["C", "F", "C", "G", "C", "F", "C", "G"],
        }, composer="Billy Joel"),
        _s("Turn the Lights Back On", "Billy Joel", "Pop", "C", {
            "Verse": ["C", "Am", "F", "G", "C", "Am", "F", "G"],
            "Pre-Chorus": ["Dm", "G", "Em", "Am", "F", "G", "C", "G"],
            "Chorus": ["C", "Am", "F", "G", "C", "Am", "F", "G"],
            "Bridge": ["F", "G", "Em", "Am", "Dm", "G", "C", "G"],
        }, composer="Billy Joel"),
        _s("Just the Way You Are", "Billy Joel", "Pop", "D", {
            "Verse": ["Dmaj7", "Bm7", "Gmaj7", "A7", "F#m7", "B7", "Em7", "A7"],
            "Chorus": ["Gmaj7", "Gm6", "D/F#", "B7", "Em7", "A7", "Dmaj7", "A7"],
            "Bridge": ["Bbmaj7", "Eb", "Am7", "D7", "Gmaj7", "A7", "Dmaj7", "A7"],
        }, composer="Billy Joel"),
        _s("Vienna", "Billy Joel", "Pop", "Bb", {
            "Verse": ["Bb", "Dm", "Gm", "Eb", "Bb", "F", "Bb", "F"],
            "Chorus": ["Eb", "F", "Dm", "Gm", "Cm", "F", "Bb", "F"],
            "Bridge": ["Gm", "Dm", "Eb", "Bb", "Cm", "F", "Bb", "F"],
        }, composer="Billy Joel"),
        _s("New York State of Mind", "Billy Joel", "Jazz", "C", {
            "Verse": ["Cmaj7", "B7", "Em7", "A7", "Dm7", "G7", "Cmaj7", "Cmaj7"],
            "Chorus": ["Fmaj7", "Fm7", "Em7", "A7", "Dm7", "G7", "Cmaj7", "G7"],
            "Bridge": ["Abmaj7", "G7", "Cmaj7", "A7", "Dm7", "G7", "Cmaj7", "G7"],
        }, composer="Billy Joel"),
        _s("Scenes from an Italian Restaurant", "Billy Joel", "Rock", "F", {
            "Ballad Intro": ["F", "Dm7", "Bb", "C", "F", "Dm7", "Gm7", "C7"],
            "Groove Section": ["F7", "Bb7", "Eb7", "Ab7"],
            "Outro Vamp": ["F", "Bb", "F", "C7"],
        }, composer="Billy Joel"),
        _s("Uptown Girl", "Billy Joel", "Pop", "E", {
            "Verse": ["E", "A", "E", "B", "E", "A", "E", "B"],
            "Chorus": ["E", "B", "A", "B", "E", "B", "A", "B"],
            "Bridge": ["C#m", "G#m", "A", "B", "E", "B", "A", "B"],
        }, composer="Billy Joel"),
        _s("She's Always a Woman", "Billy Joel", "Pop", "Eb", {
            "Verse": ["Eb", "Gm7", "Cm7", "Ab", "Eb", "Gm7", "Cm7", "Bb"],
            "Chorus": ["Ab", "Bb", "Gm7", "Cm7", "Ab", "Bb", "Eb", "Bb"],
        }, composer="Billy Joel"),

        # --- The Beatles ---
        _s("Let It Be", "The Beatles", "Rock", "C", {
            "Intro": ["C", "G", "Am", "F"],
            "Verse": ["C", "G", "Am", "F"],
            "Chorus": ["C", "G", "F", "C"],
            "Bridge": ["Am", "G", "F", "C"],
            "Guitar Solo (Over Verse)": ["C", "G", "Am", "F"],
            "Final Chorus / Outro": ["C", "G", "F", "C"],
        }, composer="John Lennon & Paul McCartney"),
        _s("Hey Jude", "The Beatles", "Rock", "F", {
            "Intro": ["F", "C", "C7", "F"],
            "Verse": ["F", "C", "C7", "F"],
            "Pre-Chorus (Build)": ["Bb", "Bb", "F", "F"],
            "Chorus (Take a Sad Song)": ["Bb", "F", "C", "F"],
            "Bridge / Middle (Instrumental)": ["Bb", "F", "C", "F"],
            "Outro Vamp (Na-Na)": ["F", "Eb", "Bb", "F", "C", "F", "C", "F"],
        }, composer="Lennon–McCartney"),
        _s("Yesterday", "The Beatles", "Rock", "F", {
            "Intro": ["F", "F", "F", "F"],
            "Verse": ["F", "Em7", "A7", "Dm"],
            "Middle Eight": ["Bb", "C7", "F", "Dm7"],
            "Return / Tag": ["Gm7", "C7", "Fmaj7", "F6"],
        }, composer="Lennon–McCartney"),
        _s("Here Comes the Sun", "The Beatles", "Rock", "A", {
            "Verse": ["A", "D", "E7", "A"],
            "Chorus": ["D", "B7", "E7", "A"],
            "Bridge": ["C#m", "G#m", "A", "E7"],
        }, composer="George Harrison"),
        _s("Something", "The Beatles", "Rock", "F", {
            "Intro": ["F", "Eb", "G", "C"],
            "Verse": ["F", "Eb", "G", "C", "F", "G", "F", "Eb"],
            "Bridge (I Don't Want to Leave)": ["A", "A/G", "F#m7", "F", "D", "G", "C", "C"],
            "Guitar Solo (Verse Form)": ["F", "Eb", "G", "C"],
            "Final Verse / Outro": ["F", "Eb", "G", "C"],
        }, composer="George Harrison"),
        _s("Blackbird", "The Beatles", "Rock", "G", {
            "Intro / Verse": ["G", "Am7", "G/B", "C", "G", "Am7", "G/B", "C"],
            "Middle": ["C", "Cm", "G", "A7"],
            "Return": ["G", "Am7", "G/B", "C"],
        }, composer="Lennon–McCartney"),
        _s("In My Life", "The Beatles", "Rock", "A", {
            "Verse": ["A", "E", "F#m", "A7", "D", "Dm", "A", "A"],
            "Chorus": ["F#m", "D", "E", "A", "F#m", "B7", "E", "E"],
        }, composer="Lennon–McCartney"),
        _s("Come Together", "The Beatles", "Rock", "Dm", {
            "Verse Vamp": ["Dm7", "Dm7", "Dm7", "Dm7"],
            "Chorus": ["A7", "G7", "D7", "A7"],
            "Bridge": ["Bm", "G", "A", "A"],
        }, composer="Lennon–McCartney"),
        _s("While My Guitar Gently Weeps", "The Beatles", "Rock", "Am", {
            "Verse": ["Am", "Am/G", "D/F#", "F", "Am", "G", "D", "E"],
            "Chorus": ["A", "C#m", "F#m", "C#m", "Bm", "E", "A", "E"],
            "Bridge": ["Am", "G", "D", "E"],
        }, composer="George Harrison"),
        _s("Eleanor Rigby", "The Beatles", "Rock", "Em", {
            "Verse": ["Em", "Em", "C", "Em"],
            "Chorus": ["Em", "C", "Em", "C"],
            "Bridge": ["Am", "Em", "C", "Em"],
        }, composer="Lennon–McCartney"),
        _s("Twist and Shout", "The Beatles", "Rock", "D", {
            "Verse": ["D", "G", "A", "G"],
            "Chorus": ["D", "G", "A", "G"],
            "Break": ["D", "D", "A", "A"],
        }, composer="Bert Russell & Phil Medley"),
        _s("Across the Universe", "The Beatles", "Rock", "D", {
            "Verse": ["D", "Bm", "F#m", "A"],
            "Chorus": ["G", "A", "D", "D"],
            "Bridge": ["G", "D", "A", "A"],
        }, composer="Lennon–McCartney"),
        _s("A Day in the Life", "The Beatles", "Rock", "G", {
            "Verse": ["G", "Bm", "Em", "Em7"],
            "Orchestral Bridge": ["E", "E", "E", "E"],
            "Final": ["G", "Bm", "Em", "C"],
        }, composer="Lennon–McCartney"),
        _s("Help!", "The Beatles", "Rock", "A", {
            "Verse": ["A", "C#m", "F#m", "D"],
            "Chorus": ["E", "A", "D", "D"],
            "Bridge": ["Bm", "G", "A", "A"],
        }, composer="Lennon–McCartney"),
        _s("All You Need Is Love", "The Beatles", "Rock", "G", {
            "Verse": ["G", "D", "Em", "D"],
            "Chorus": ["C", "D", "G", "G"],
            "Bridge": ["Em", "A7", "D", "D"],
        }, composer="Lennon–McCartney"),

        # --- Jobim & bossa ---
        _s("The Girl from Ipanema", "Antonio Carlos Jobim", "Jazz", "F", {
            "Intro (Turnaround)": ["Gm7", "C7", "Gm7", "C7"],
            "Verse / A Section": ["Fmaj7", "G7", "Gm7", "C7", "Fmaj7", "G7", "Gm7", "C7"],
            "Bridge / B Section": ["Dbmaj7", "B7", "F#m7", "B7", "Gm7", "Eb7", "Am7", "D7"],
            "Last A (Recap)": ["Gm7", "C7", "Fmaj7", "Fmaj7"],
        }, composer="Antonio Carlos Jobim"),
        _s("Wave", "Antonio Carlos Jobim", "Jazz", "D", {
            "Intro": ["Dmaj7", "Dmaj7", "Dmaj7", "Dmaj7"],
            "Verse / A Section": ["Dmaj7", "Bbdim7", "Am7", "D7", "Gmaj7", "Gm6", "F#m7", "B7"],
            "Bridge / B Section": ["Em7", "A7", "Dmaj7", "Dmaj7", "Fm7", "Bb7", "Ebmaj7", "A7"],
            "Final A / Outro": ["Dmaj7", "Bbdim7", "Am7", "D7", "Gmaj7", "Gm6", "Dmaj7", "A7"],
        }, composer="Antonio Carlos Jobim"),
        _s("One Note Samba", "Antonio Carlos Jobim", "Jazz", "Bb", {
            "A Section": ["Bbmaj7", "Bdim7", "Cm7", "F7", "Cm7", "F7", "Bbmaj7", "F7"],
            "B Section": ["Dm7", "G7", "Cm7", "F7", "Dm7", "G7", "Cm7", "F7"],
            "Final A": ["Bbmaj7", "Bdim7", "Cm7", "F7", "Bbmaj7", "Bbmaj7"],
        }, composer="Antonio Carlos Jobim"),
        _s("Desafinado", "Antonio Carlos Jobim", "Jazz", "F", {
            "A Section": ["Fmaj7", "G7", "Gm7", "C7", "Am7", "D7", "Gm7", "C7"],
            "B Section": ["Fmaj7", "F#dim7", "Gm7", "C7", "Fmaj7", "D7", "Gm7", "C7"],
        }, composer="Antonio Carlos Jobim"),
        _s("Corcovado", "Antonio Carlos Jobim", "Jazz", "C", {
            "A Section": ["Cmaj7", "D7", "Dm7", "G7", "Cmaj7", "D7", "Dm7", "G7"],
            "B Section": ["Em7", "A7", "Dm7", "G7", "Cmaj7", "Cmaj7"],
        }, composer="Antonio Carlos Jobim"),
        _s("Meditation", "Antonio Carlos Jobim", "Jazz", "C", {
            "A Section": ["Cmaj7", "Cmaj7", "Bm7b5", "E7", "Am7", "D7", "Dm7", "G7"],
            "B Section": ["Em7", "A7", "Dm7", "G7", "Cmaj7", "Cmaj7"],
        }, composer="Antonio Carlos Jobim"),
        _s("Agua de Beber", "Antonio Carlos Jobim", "Jazz", "Am", {
            "A Section": ["Am7", "D7", "Am7", "D7", "Am7", "D7", "Gmaj7", "Gmaj7"],
            "B Section": ["Bm7b5", "E7", "Am7", "Am7", "Dm7", "G7", "Cmaj7", "E7"],
        }, composer="Antonio Carlos Jobim"),
        _s("How Insensitive", "Antonio Carlos Jobim", "Jazz", "Dm", {
            "A Section": ["Dm9", "Dm9/C", "Bdim7", "Bbmaj7", "A7", "A7", "Dm", "Dm"],
            "B Section": ["Gm7", "C7", "Fmaj7", "Bbmaj7", "Em7b5", "A7", "Dm", "A7"],
        }, composer="Antonio Carlos Jobim"),
        _s("Summer Samba", "Marcos Valle", "Jazz", "F", {
            "A Section": ["Fmaj7", "Gm7", "Am7", "Gm7", "Fmaj7", "Gm7", "Am7", "D7"],
            "B Section": ["Gm7", "C7", "Fmaj7", "Dm7", "Gm7", "C7", "Fmaj7", "C7"],
        }, composer="Marcos Valle"),

        # --- Jazz standards (practice forms) ---
        _s("Autumn Leaves", "Jazz Standard", "Jazz", "Gm", {
            "Intro (ii–V in relative minor)": ["Am7b5", "D7", "Gm7", "Gm7"],
            "Verse / A": ["Cm7", "F7", "Bbmaj7", "Ebmaj7", "Am7b5", "D7", "Gm7", "Gm7"],
            "Bridge / B": ["Cm7", "F7", "Bbmaj7", "Ebmaj7", "Am7b5", "D7", "Gm7", "D7"],
        }, composer="Joseph Kosma"),
        _s("Blue Bossa", "Kenny Dorham", "Jazz", "Cm", {
            "A Section": ["Cm7", "Fm7", "Dm7b5", "G7", "Cm7", "Cm7"],
            "B Section": ["Ebm7", "Ab7", "Dbmaj7", "Dbmaj7", "Dm7b5", "G7", "Cm7", "G7"],
        }, composer="Kenny Dorham"),
        _s("All of Me", "Jazz Standard", "Jazz", "C", {
            "A Section": ["Cmaj7", "E7", "A7", "Dm7", "E7", "Am7", "D7", "G7"],
            "B Section": ["Cmaj7", "E7", "A7", "Dm7", "Fmaj7", "Fm7", "Cmaj7", "A7"],
            "Turnaround": ["Dm7", "G7", "Cmaj7", "G7"],
        }, composer="Gerald Marks & Seymour Simons"),
        _s("Fly Me to the Moon", "Bart Howard", "Jazz", "C", {
            "A Section": ["Am7", "Dm7", "G7", "Cmaj7", "Fmaj7", "Bm7b5", "E7", "Am7"],
            "B Section": ["Dm7", "G7", "Cmaj7", "A7", "Dm7", "G7", "Cmaj7", "E7"],
        }, composer="Bart Howard"),
        _s("So What", "Miles Davis", "Jazz", "Dm", {
            "A Section": ["Dm7"] * 8,
            "Bridge": ["Ebm7"] * 8,
            "Final A": ["Dm7"] * 8,
        }, composer="Miles Davis"),
        _s("Take the A Train", "Duke Ellington", "Jazz", "C", {
            "A Section": ["Cmaj7", "Cmaj7", "D7", "D7", "Dm7", "G7", "Cmaj7", "G7"],
            "B Section": ["Fmaj7", "Fmaj7", "D7", "D7", "Dm7", "G7", "Cmaj7", "G7"],
        }, composer="Billy Strayhorn"),
        _s("There Will Never Be Another You", "Harry Warren", "Jazz", "Eb", {
            "A Section": ["Ebmaj7", "Cm7", "Fm7", "Bb7", "Gm7", "C7", "Fm7", "Bb7"],
            "B Section": ["Ebmaj7", "Abmaj7", "Dm7b5", "G7", "Cm7", "F7", "Fm7", "Bb7"],
        }, composer="Harry Warren"),
        _s("All the Things You Are", "Jerome Kern", "Jazz", "Ab", {
            "A Section": ["Fm7", "Bbm7", "Eb7", "Abmaj7", "Dbmaj7", "G7", "Cmaj7", "Cmaj7"],
            "B Section": ["Cm7", "Fm7", "Bb7", "Ebmaj7", "Abmaj7", "D7", "Gmaj7", "Gmaj7"],
        }, composer="Jerome Kern"),
        _s("Body and Soul", "Jazz Standard", "Jazz", "Db", {
            "A Section": ["Dbmaj7", "Ebm7", "E7", "Amaj7", "Abm7", "Db7", "Gbmaj7", "Gbmaj7"],
            "B Section": ["Fm7", "Bb7", "Ebmaj7", "Gm7b5", "C7", "Fm7", "Bb7", "Eb7"],
        }, composer="Johnny Green"),
        _s("Misty", "Erroll Garner", "Jazz", "Eb", {
            "A Section": ["Ebmaj7", "Bbm7", "Ebmaj7", "Gm7", "C7", "Fm7", "Bb7", "Ebmaj7"],
            "B Section": ["Am7b5", "D7", "Gm7", "C7", "Fm7", "Bb7", "Ebmaj7", "Ebmaj7"],
        }, composer="Erroll Garner"),
        _s("Satin Doll", "Duke Ellington", "Jazz", "C", {
            "A Section": ["D7", "D7", "Dm7", "G7", "Cmaj7", "Cmaj7", "Am7", "D7"],
            "B Section": ["Dm7", "G7", "Cmaj7", "A7", "Dm7", "G7", "Cmaj7", "Cmaj7"],
        }, composer="Duke Ellington"),
        _s("Blue in Green", "Miles Davis", "Jazz", "Gm", {
            "A Section": ["Gm7", "Gm7", "A7#9", "A7#9", "Gm7", "Gm7", "Gm7", "Gm7"],
        }, composer="Miles Davis / Bill Evans"),

        # --- Rock / Funk / Blues anchors ---
        _s("Don't Stop Believin'", "Journey", "Rock", "E", {
            "Low Part / Verse Piano Loop": ["E", "B", "C#m", "A"],
            "Pre-Chorus": ["A", "E", "B", "C#m"],
            "High Part / Chorus": ["E", "B", "A", "E"],
            "Final Chorus": ["E", "B", "A", "E"],
        }),
        _s("Superstition", "Stevie Wonder", "Funk", "Eb", {
            "Main Groove": ["Ebm7", "Ebm7", "Ebm7", "Ebm7"],
            "Chorus": ["Ab7", "Gb7", "Ebm7", "Ebm7"],
            "Final Groove": ["Ebm7", "Ebm7", "Ebm7", "Ebm7"],
        }),
        _s("Cissy Strut", "The Meters", "Funk", "C", {
            "Main Funk Vamp": ["C7", "C7", "C7", "C7"],
            "Turnaround": ["F7", "Eb7", "C7", "C7"],
        }),
        _s("12-Bar Blues in F", "Traditional", "Blues", "F", {
            "Bars 1-4": ["F7", "Bb7", "F7", "F7"],
            "Bars 5-8": ["Bb7", "Bb7", "F7", "F7"],
            "Bars 9-12": ["C7", "Bb7", "F7", "C7"],
        }),
        _s("Ode to Joy", "Beethoven", "Classical", "D", {
            "Main Theme": ["D", "A", "D", "G", "D", "A", "D"],
            "Practice Variation": ["D", "G", "A", "D"],
        }, composer="Ludwig van Beethoven"),
    ]
