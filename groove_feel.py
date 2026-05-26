"""Single source of truth for the Rhythm / Groove Feel dropdown.

Every groove-aware surface in the app (Rhythm Guide, Section Deep
Focus, Practice Coach exercises, Generated Notation / TAB, chord-chart
overlay, vocal/bass/wind practice hints) reads from this module so
changing the dropdown produces a real, visible difference in the
practice guidance.

``GROOVE_PROFILE[label]`` returns a dict with the following keys:

- ``label``         user-visible groove name (matches the dropdown option)
- ``feel``          one-line "feel" tagline ("driving 8th-note backbeat")
- ``count_in``      counting cue ("1-and-2-and-3-and-4-and", "1 a-2 a-3")
- ``accent``        where the accent falls ("on 2 & 4", "on 1 & 3")
- ``dynamics``      dynamics guidance ("gentle p->mf swells")
- ``articulation``  articulation guidance ("legato lines, no staccato")
- ``time_feel``     time-feel guidance ("straight 8ths", "swing 8ths")
- ``tempo_hint``    typical BPM range ("60-80 BPM", "120-160 BPM")
- ``strum``         8-cell strum pattern for guitar (list[str])
- ``piano_comp``    short piano comp description
- ``bass``          bass-line shape description
- ``voice``         vocal phrasing tip
- ``winds``         wind/horn phrasing tip
- ``notation``      one-line notation feel tag (used in ABC stem hint)
- ``tab_pattern``   compact strum/comp cell label used by TAB renderer

Callers should always go through :func:`resolve_groove_style` first so
the user-facing ``"Auto"`` option is materialized against the active
song's metadata (genre / artist / title) before any lookup.
"""

from __future__ import annotations

from typing import Any, Mapping


# ---------------------------------------------------------------------------
# Canonical groove labels (must match the dropdown options)
# ---------------------------------------------------------------------------

GROOVE_AUTO = "Auto"
GROOVE_POP = "Pop groove"
GROOVE_ROCK = "Rock groove"
GROOVE_JAZZ = "Jazz swing"
GROOVE_BOSSA = "Bossa nova"
GROOVE_FUNK = "Funk groove"
GROOVE_BALLAD = "Ballad"

ALL_GROOVE_LABELS: tuple[str, ...] = (
    GROOVE_POP,
    GROOVE_ROCK,
    GROOVE_JAZZ,
    GROOVE_BOSSA,
    GROOVE_FUNK,
    GROOVE_BALLAD,
)


def resolve_groove_style(
    groove_style: str | None,
    song_data: Mapping[str, Any] | None = None,
) -> str:
    """Resolve an incoming groove value to a concrete profile label.

    * ``None`` / empty / ``"Auto"`` -> infer from ``song_data`` via
      :func:`backing_audio.infer_groove_style` (genre / artist / title
      heuristics). Falls back to ``"Pop groove"`` if inference fails or
      ``song_data`` is missing.
    * Any other string is normalized to one of :data:`ALL_GROOVE_LABELS`;
      unknown labels fall back to ``"Pop groove"`` so downstream lookups
      never crash on stale session_state.
    """
    raw = str(groove_style or "").strip()
    if not raw or raw.lower() == "auto":
        try:
            from backing_audio import infer_groove_style  # local: avoids cycles
            inferred = infer_groove_style(song_data or {}, "Auto")
        except Exception:
            inferred = GROOVE_POP
        return _canonical(inferred)
    return _canonical(raw)


def _canonical(label: str) -> str:
    """Best-effort match of an arbitrary groove string to a canonical label."""
    low = label.strip().lower()
    if not low:
        return GROOVE_POP
    if "bossa" in low or "samba" in low or "jobim" in low:
        return GROOVE_BOSSA
    if "jazz" in low or "swing" in low or "shuffle" in low or "bebop" in low:
        return GROOVE_JAZZ
    if "funk" in low or "soul" in low or "groove" in low and "funk" in low:
        return GROOVE_FUNK
    if "rock" in low or "metal" in low or "punk" in low:
        return GROOVE_ROCK
    if "ballad" in low or "slow" in low:
        return GROOVE_BALLAD
    if "pop" in low:
        return GROOVE_POP
    return GROOVE_POP


# ---------------------------------------------------------------------------
# Per-groove profiles
# ---------------------------------------------------------------------------

GROOVE_PROFILE: dict[str, dict[str, Any]] = {
    GROOVE_POP: {
        "label": GROOVE_POP,
        "feel": "straight 8th-note pop pulse",
        "count_in": "1-and-2-and-3-and-4-and",
        "accent": "on 2 & 4 (light backbeat)",
        "dynamics": "even mf; small lift into the chorus",
        "articulation": "clean, slightly detached strums; even attack",
        "time_feel": "straight 8ths",
        "tempo_hint": "92-118 BPM",
        "strum": ["D", "-", "D", "U", "-", "U", "D", "U"],
        "piano_comp": (
            "Left hand: root on beat 1, fifth on beat 3. "
            "Right hand: chord shells on every 8th note, slightly softer on the off-beats."
        ),
        "bass": (
            "Root on beat 1, fifth on beat 3, walk a passing tone into the next bar. "
            "Lock to the kick drum."
        ),
        "voice": (
            "Phrase across the bar line in 4-bar arcs; place the title hook on beat 1 of the chorus. "
            "Soft, conversational delivery on verses."
        ),
        "winds": (
            "Long sustained lines over the verse, short answering figures in the chorus. "
            "Breathe at phrase endings, not mid-phrase."
        ),
        "notation": "straight 8ths, pop feel",
        "tab_pattern": "Pop 8th-note strum",
    },
    GROOVE_ROCK: {
        "label": GROOVE_ROCK,
        "feel": "driving 8th-note rock with a hard backbeat",
        "count_in": "1-AND-2-AND-3-AND-4-AND",
        "accent": "hard on 2 & 4 (snare backbeat)",
        "dynamics": "f throughout; punch into the chorus, do not back off",
        "articulation": (
            "palm-muted or down-stroked 8ths; aggressive attack on beats 2 & 4"
        ),
        "time_feel": "straight 8ths, locked to the kick",
        "tempo_hint": "110-160 BPM",
        "strum": ["D", "D", "D", "D", "D", "D", "D", "D"],
        "piano_comp": (
            "Left hand: root octaves on every quarter. "
            "Right hand: chord stabs on beats 2 & 4; let space ring on 1 & 3."
        ),
        "bass": (
            "Root-fifth-octave rock pattern, eighth-note pulse, all down-strokes if using a pick. "
            "Lock 1-1-1-1 with the kick under verses, open up to root-fifth-root under choruses."
        ),
        "voice": (
            "Push into the consonants; over-deliver beats 2 & 4 of every line. "
            "Belt the title hook, but stay supported - don't shout."
        ),
        "winds": (
            "Short, accented 8th-note riffs; double the rhythm guitar pattern when in doubt. "
            "Vibrato only on long held notes."
        ),
        "notation": "straight 8ths, hard backbeat",
        "tab_pattern": "Rock 8th-note pulse",
    },
    GROOVE_JAZZ: {
        "label": GROOVE_JAZZ,
        "feel": "swung 8ths with a walking, conversational pulse",
        "count_in": "1 a-2 a-3 a-4 a (triplet sub-divisions)",
        "accent": "on 2 & 4 (ride cymbal & hi-hat chick)",
        "dynamics": "mp baseline; build through the form, peak at the bridge",
        "articulation": (
            "swung 8ths (long-short); legato comping; ghost the back-beat of beat 4"
        ),
        "time_feel": "swing 8ths (12/8 sub-feel inside 4/4)",
        "tempo_hint": "100-220 BPM (medium swing)",
        "strum": ["D", "-", "u", "D", "-", "u", "D", "-"],
        "piano_comp": (
            "Left hand: rootless shell voicings (3-7 or 7-3) every 2 beats, "
            "anticipating beat 3 by an 8th. Right hand: sparse upper-structure chord stabs "
            "on the AND of beat 2 and AND of beat 4. Comp in conversation with the soloist."
        ),
        "bass": (
            "Walking quarters: root on beat 1, chord tones / approach tones on 2-3-4, "
            "chromatic leading tone into beat 1 of the next bar. Stay in the pocket."
        ),
        "voice": (
            "Scoop into long notes, place the lyric a hair behind the beat. "
            "Phrase across bar lines; breathe where the band breathes."
        ),
        "winds": (
            "Eighths are swung (long-short). "
            "Phrase like a horn player - target chord tones, ghost approach tones, end phrases on 3 or 5."
        ),
        "notation": "swing 8ths (notate straight, performed long-short)",
        "tab_pattern": "Swing comp (Freddie Green 4-to-the-bar)",
    },
    GROOVE_BOSSA: {
        "label": GROOVE_BOSSA,
        "feel": "syncopated 2-bar bossa pattern with a soft offbeat",
        "count_in": "1-and-2-and-3-and-4-and (clave aware)",
        "accent": "syncopation on the AND of 2 and AND of 4",
        "dynamics": "mp throughout; never push - keep it relaxed and breathy",
        "articulation": (
            "fingerstyle, soft picado; chords held, never strummed hard; "
            "rim-click rhythm in the head"
        ),
        "time_feel": "straight 8ths with a relaxed, late pocket",
        "tempo_hint": "120-150 BPM",
        "strum": ["D", "-", "U", "-", "-", "U", "D", "-"],
        "piano_comp": (
            "Left hand: alternating root and fifth, often syncopated with a tied AND of beat 2. "
            "Right hand: held chord, voiced 3-5-7-9, played softly on the AND of 2 and AND of 4."
        ),
        "bass": (
            "Two-feel: root on beat 1, fifth on beat 3, with a syncopated push on the AND of 2 "
            "tying into beat 3. Almost no quarter-note walking."
        ),
        "voice": (
            "Whispered, intimate delivery. Phrase off the bar - land lyric stresses on the "
            "syncopation (AND of 2, AND of 4) rather than on downbeats."
        ),
        "winds": (
            "Long held notes over the comp. "
            "When phrasing, target the AND of 2 / AND of 4 for syncopated melodic stabs."
        ),
        "notation": "straight 8ths, bossa clave",
        "tab_pattern": "Bossa fingerstyle (R-and-AND-R-3-AND-AND-3)",
    },
    GROOVE_FUNK: {
        "label": GROOVE_FUNK,
        "feel": "tight 16th-note syncopation with short rhythmic cells",
        "count_in": "1-e-and-a-2-e-and-a-3-e-and-a-4-e-and-a (16ths)",
        "accent": "ghost the e and a; pop the AND of every beat",
        "dynamics": (
            "consistent mp-mf groove; do not crescendo through the bar - sit in the pocket"
        ),
        "articulation": (
            "short, percussive, muted 16th-note cells; ghost notes between accented hits"
        ),
        "time_feel": "16th-note grid, slightly behind the beat",
        "tempo_hint": "92-120 BPM",
        "strum": ["x", "x", "D", "x", "x", "x", "U", "x"],
        "piano_comp": (
            "Right hand: muted single-line riffs in 16ths, ghosting most notes. "
            "Left hand: octave or root-and-fifth stab on the AND of beat 1 and beat 3."
        ),
        "bass": (
            "Lock to the kick. Slap-and-pop or fingerstyle 16ths with heavy ghost notes. "
            "Use chromatic approach tones into beat 1 of the next bar."
        ),
        "voice": (
            "Stab consonants on the syncopated accents. "
            "Stay tight to the rhythm section - no flowing legato."
        ),
        "winds": (
            "Short rhythmic horn stabs on the AND of every beat; "
            "blend with the rhythm section, do not solo over it."
        ),
        "notation": "16th-note funk pocket",
        "tab_pattern": "Funk 16th-note muted",
    },
    GROOVE_BALLAD: {
        "label": GROOVE_BALLAD,
        "feel": "sustained, lyrical, half-time ballad feel",
        "count_in": "1...2...3...4... (relaxed, half-time)",
        "accent": "on 1 & 3 (very light backbeat on 3)",
        "dynamics": (
            "pp to mp; build slowly through the form; gentle p->mf swells into the chorus"
        ),
        "articulation": (
            "let chords ring across the bar; fingerpicking or arpeggios "
            "instead of strumming; legato everywhere"
        ),
        "time_feel": "half-time straight 8ths; very relaxed",
        "tempo_hint": "55-80 BPM",
        "strum": ["D", "-", "-", "-", "u", "-", "u", "-"],
        "piano_comp": (
            "Left hand: root + tenth held across the bar. "
            "Right hand: broken-chord arpeggios in 8ths, swelling gently. "
            "Use the sustain pedal generously."
        ),
        "bass": (
            "Whole-note roots with a gentle pickup into each chord change. "
            "Almost no walking; let the harmony breathe."
        ),
        "voice": (
            "Lyrical, sustained delivery. "
            "Use breath swells through long notes; place vibrato near the end of each held tone. "
            "Phrase across the bar line; do not chop sentences at bar boundaries."
        ),
        "winds": (
            "Long sustained melodic lines, soft attack, lots of vibrato. "
            "Breathe at phrase endings only; build dynamically through each phrase."
        ),
        "notation": "half-time straight 8ths; sustained chords",
        "tab_pattern": "Ballad arpeggio (R-3-5-7 fingerpicking)",
    },
}


def get_profile(groove_style: str | None) -> dict[str, Any]:
    """Return the canonical profile for *groove_style*, falling back to Pop.

    Caller is responsible for resolving ``"Auto"`` first via
    :func:`resolve_groove_style`.
    """
    label = _canonical(str(groove_style or ""))
    return GROOVE_PROFILE.get(label, GROOVE_PROFILE[GROOVE_POP])


# ---------------------------------------------------------------------------
# Instrument-aware bite-size helpers
# ---------------------------------------------------------------------------

def instrument_phrasing_hint(
    instrument: str | None,
    groove_style: str,
) -> str:
    """Return a one-line phrasing tip for *instrument* in *groove_style*."""
    profile = get_profile(groove_style)
    inst = (instrument or "").strip().lower()
    if "guitar" in inst:
        return f"Strum pattern: {'  '.join(profile['strum'])} - {profile['articulation']}"
    if "piano" in inst or "key" in inst:
        return profile["piano_comp"]
    if "bass" in inst:
        return profile["bass"]
    if "voice" in inst or "vocal" in inst or "sing" in inst:
        return profile["voice"]
    if (
        "sax" in inst
        or "horn" in inst
        or "trumpet" in inst
        or "flute" in inst
        or "clarinet" in inst
        or "wind" in inst
    ):
        return profile["winds"]
    return f"{profile['feel'].capitalize()}; {profile['articulation']}"


def short_feel_tag(groove_style: str) -> str:
    """One-line tag for headers and badges ("Driving 8th-note rock...")."""
    return get_profile(groove_style)["feel"].capitalize()


__all__ = [
    "GROOVE_AUTO",
    "GROOVE_POP",
    "GROOVE_ROCK",
    "GROOVE_JAZZ",
    "GROOVE_BOSSA",
    "GROOVE_FUNK",
    "GROOVE_BALLAD",
    "ALL_GROOVE_LABELS",
    "GROOVE_PROFILE",
    "resolve_groove_style",
    "get_profile",
    "instrument_phrasing_hint",
    "short_feel_tag",
]
