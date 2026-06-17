"""Local Music Coach instant solver — practice plans, chord work, tempo/key guidance."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

MUSIC_AMI_BUILD_ID = "music-ami-v3-reliability-routing"

_MUSIC_SOLVER_INTENTS = frozenset(
    {
        "practice_plan",
        "chord_transition",
        "section_focus",
        "tempo_key",
        "backing_track",
        "skill_technique",
        "difficulty",
        "music_transposition",
        "music_theory",
        "similar_songs",
    }
)


@dataclass
class MusicSolverRoute:
    problem_type: str
    model_name: str
    model_rationale: str = ""


@dataclass
class MusicSolverResult:
    short_answer: str
    math_idea: str = ""
    problem_type: str = ""
    model_name: str = ""
    variables: str = ""
    assumptions: list[str] = field(default_factory=list)
    confidence_pct: int | None = 85
    computed: dict[str, Any] = field(default_factory=dict)


def _ctx_value(ctx: dict[str, Any], *keys: str, default: Any = "") -> Any:
    for key in keys:
        val = ctx.get(key)
        if val is not None and str(val).strip() != "":
            return val
    snap = ctx.get("practice_snapshot")
    if isinstance(snap, dict):
        for key in keys:
            val = snap.get(key)
            if val is not None and str(val).strip() != "":
                return val
    active = ctx.get("active_song")
    if isinstance(active, dict):
        for key in keys:
            val = active.get(key)
            if val is not None and str(val).strip() != "":
                return val
    return default


def _session_minutes_from_question(question: str) -> int | None:
    import re

    m = re.search(r"\b(\d{1,3})\s*minutes?\b", str(question or ""), flags=re.I)
    if not m:
        return None
    try:
        return max(5, min(120, int(m.group(1))))
    except (TypeError, ValueError):
        return None


def _session_minutes(ctx: dict[str, Any], question: str = "") -> int:
    parsed = _session_minutes_from_question(question)
    if parsed is not None:
        return parsed
    raw = _ctx_value(ctx, "practice_minutes", "session_minutes", "minutes", default=30)
    try:
        minutes = int(float(raw))
    except (TypeError, ValueError):
        minutes = 30
    return max(15, min(90, minutes))


def _session_minutes_assumption(ctx: dict[str, Any], question: str, minutes: int) -> str:
    if _session_minutes_from_question(question) is not None:
        return f"Session length parsed from your question ({minutes} minutes)."
    raw = _ctx_value(ctx, "practice_minutes", "session_minutes", "minutes", default="")
    try:
        ctx_minutes = int(float(raw))
    except (TypeError, ValueError):
        ctx_minutes = None
    if ctx_minutes and ctx_minutes != 30:
        return f"Session length taken from your practice context ({minutes} minutes)."
    return "Session length defaults to 30 minutes when not set in practice context."


def _allocate_minutes(total: int, weights: dict[str, float]) -> dict[str, int]:
    if not weights:
        return {}
    norm = sum(max(0.0, float(v)) for v in weights.values()) or 1.0
    raw = {k: total * max(0.0, float(v)) / norm for k, v in weights.items()}
    rounded = {k: int(v) for k, v in raw.items()}
    remainder = total - sum(rounded.values())
    order = sorted(raw.keys(), key=lambda k: raw[k] - rounded[k], reverse=True)
    idx = 0
    while remainder > 0 and order:
        rounded[order[idx % len(order)]] += 1
        remainder -= 1
        idx += 1
    return rounded


def _practice_plan_answer(question: str, ctx: dict[str, Any], *, chord_focus: bool) -> MusicSolverResult:
    minutes = _session_minutes(ctx, question)
    section = str(_ctx_value(ctx, "practice_focus_section", "section_focus_named", default="")).strip()
    instrument = str(_ctx_value(ctx, "instrument", default="your instrument")).strip()
    song = str(_ctx_value(ctx, "question_song", "song", default="")).strip()
    if chord_focus:
        weights = {
            "chord transitions": 0.40,
            "rhythm / groove": 0.30,
            "melody / licks": 0.20,
            "full run-through": 0.10,
        }
        focus_line = "Prioritize clean chord changes before speed."
    else:
        weights = {
            "technique / drills": 0.35,
            "rhythm / groove": 0.25,
            "repertoire section": 0.25,
            "full run-through": 0.15,
        }
        focus_line = "Balance technique, time feel, and musical run-throughs."
    blocks = _allocate_minutes(minutes, weights)
    lines = [f"Suggested {minutes}-minute practice split:"]
    for label, block_min in blocks.items():
        lines.append(f"- **{block_min} min** {label}")
    if section:
        lines.append(f"- Keep **{section}** as your primary section focus.")
    if song:
        lines.append(f"- Anchor the plan to **{song}**.")
    lines.append(f"- On **{instrument}**, {focus_line}")
    short = "\n".join(lines)
    return MusicSolverResult(
        short_answer=short,
        math_idea="Time-boxed practice blocks weighted toward the user's stated focus.",
        problem_type="practice_plan",
        model_name="Music Coach practice planner",
        variables=f"session_minutes={minutes}; chord_focus={chord_focus}",
        assumptions=[
            _session_minutes_assumption(ctx, question, minutes),
            "Adjust blocks ±2 minutes if your warmup or cooldown needs more time.",
        ],
        confidence_pct=82,
        computed={"session_minutes": minutes, **blocks},
    )


def _chord_transition_answer(ctx: dict[str, Any], question: str = "") -> MusicSolverResult:
    minutes = max(10, min(25, _session_minutes(ctx, question) // 2 or 15))
    bpm = _ctx_value(ctx, "bpm", "practice_bpm", default="")
    instrument = str(_ctx_value(ctx, "instrument", default="your instrument")).strip()
    lines = [
        f"Spend about **{minutes} minutes** on chord-change drills, then plug them into the song.",
        "- Loop pairs of chords slowly (metronome 60–70% of target tempo).",
        "- Practice common-finger anchors and lift only the fingers that must move.",
        "- Run 4-bar loops, then 8-bar loops, then add rhythm on **{inst}**.".format(inst=instrument),
    ]
    if bpm:
        lines.append(f"- Target tempo ladder: 70% → 85% → 100% of **{bpm} BPM**.")
    else:
        lines.append("- Target tempo ladder: comfortable → medium → performance tempo.")
    return MusicSolverResult(
        short_answer="\n".join(lines),
        math_idea="Isolated transition reps before tempo and groove integration.",
        problem_type="chord_transition",
        model_name="Music Coach chord transitions",
        variables=f"drill_minutes={minutes}",
        assumptions=["One chord pair at a time beats rushing the full progression."],
        confidence_pct=84,
        computed={"drill_minutes": minutes},
    )


def _section_focus_answer(ctx: dict[str, Any], question: str = "") -> MusicSolverResult:
    section = str(_ctx_value(ctx, "practice_focus_section", "section_focus_named", default="this section")).strip()
    minutes = _session_minutes(ctx, question)
    drill = max(8, minutes // 3)
    return MusicSolverResult(
        short_answer=(
            f"For **{section}**: loop **{drill} min** slow reps, **{drill} min** rhythm-focused reps, "
            f"then **{max(5, minutes - 2 * drill)} min** connecting into the full song."
        ),
        math_idea="Section loops with escalating tempo and context.",
        problem_type="section_focus",
        model_name="Music Coach section focus",
        confidence_pct=80,
        computed={"section": section, "loop_minutes": drill},
    )


def _tempo_key_answer(ctx: dict[str, Any]) -> MusicSolverResult:
    bpm = str(_ctx_value(ctx, "bpm", "practice_bpm", default="")).strip()
    display_key = str(_ctx_value(ctx, "display_key", "key", default="")).strip()
    level = str(_ctx_value(ctx, "level", default="Intermediate")).strip()
    tempo_line = (
        f"Try **{int(float(bpm) * 0.75)} BPM** as a learning tempo (about 75% of {bpm})."
        if bpm
        else "Start 15–25% below performance tempo until transitions stay clean."
    )
    key_line = f"Written key **{display_key}** is fine for practice." if display_key else "Match the chart key you are reading."
    return MusicSolverResult(
        short_answer=f"{tempo_line}\n{key_line}\nFor **{level}** players, add +5 BPM only after two clean passes.",
        math_idea="Tempo ladder with key context from the active chart.",
        problem_type="tempo_key",
        model_name="Music Coach tempo & key",
        confidence_pct=78,
        computed={"suggested_bpm_pct": 75},
    )


def _skill_technique_answer(ctx: dict[str, Any]) -> MusicSolverResult:
    level = str(_ctx_value(ctx, "level", default="your level")).strip()
    instrument = str(_ctx_value(ctx, "instrument", default="your instrument")).strip()
    return MusicSolverResult(
        short_answer=(
            f"At **{level}** on **{instrument}**, build technique before full-tempo performance: "
            "slow reps with a metronome, short bursts at target tempo, then rest. "
            "If the song feels too hard, reduce tempo 20% and isolate the hardest bar."
        ),
        math_idea="Readiness check with technique-first progression.",
        problem_type="skill_technique",
        model_name="Music Coach technique roadmap",
        confidence_pct=76,
    )


def _backing_track_answer(ctx: dict[str, Any]) -> MusicSolverResult:
    groove = str(_ctx_value(ctx, "groove", "practice_groove_style", "backing_groove_style", default="the groove")).strip()
    section = str(_ctx_value(ctx, "practice_focus_section", default="the chorus")).strip()
    return MusicSolverResult(
        short_answer=(
            f"Loop **{section}** with **{groove}** at a comfortable tempo. "
            "Practice chord changes first without the backing, then add the track for time feel."
        ),
        math_idea="Backing-track practice order: technique → groove integration.",
        problem_type="backing_track",
        model_name="Music Coach backing track",
        confidence_pct=77,
    )


_NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
_FLAT_TO_SHARP = {"DB": "C#", "EB": "D#", "GB": "F#", "AB": "G#", "BB": "A#", "CB": "B", "FB": "E"}


def _normalize_note_name(raw: str) -> str:
    token = str(raw or "").strip().upper().replace("♭", "B").replace("♯", "#")
    if not token:
        return ""
    if len(token) > 1 and token[1] == "B" and len(token) >= 2:
        token = token[0] + "B" + token[2:]
    token = _FLAT_TO_SHARP.get(token, token)
    return token if token in _NOTE_NAMES else token[0] if token[:1] in _NOTE_NAMES else ""


def _parse_key_pair_from_question(question: str) -> tuple[str, str]:
    import re

    q = str(question or "")
    m = re.search(
        r"\bin\s+([A-Ga-g][#b]?)\s+instead\s+of\s+([A-Ga-g][#b]?)",
        q,
        flags=re.I,
    )
    if m:
        return _normalize_note_name(m.group(2)), _normalize_note_name(m.group(1))
    return "", ""


def _semitone_index(note: str) -> int | None:
    try:
        return _NOTE_NAMES.index(note)
    except ValueError:
        return None


def _interval_name(semitones: int) -> str:
    mapping = {
        1: "a half step (minor second)",
        2: "a whole step (major second)",
        -1: "down a half step",
        -2: "down a whole step",
    }
    if semitones in mapping:
        return mapping[semitones]
    if semitones > 0:
        return f"up {semitones} semitones"
    return f"down {abs(semitones)} semitones"


def _transposing_instrument_note(instrument: str) -> str:
    low = str(instrument or "").lower()
    if "alto sax" in low or low == "alto":
        return (
            "**Alto sax** is an **Eb transposing** instrument: written notes sound a major sixth lower "
            "than concert pitch. When the concert key moves, your written chart shifts by the same interval."
        )
    if "tenor sax" in low or low == "tenor":
        return (
            "**Tenor sax** is a **Bb transposing** instrument: written notes sound a major ninth lower "
            "than concert pitch. Shift every written note by the same interval as the concert-key change."
        )
    if "trumpet" in low or "clarinet" in low or "soprano sax" in low:
        return (
            f"On **{instrument}**, use the written chart for your transposing instrument and shift each "
            "note/chord by the same interval as the concert-key change."
        )
    return "Shift each note and chord in your chart by the same interval as the concert-key change."


def _transposition_answer(question: str, ctx: dict[str, Any]) -> MusicSolverResult:
    from_key, to_key = _parse_key_pair_from_question(question)
    display_key = str(_ctx_value(ctx, "display_key", "key", default="")).strip()
    instrument = str(_ctx_value(ctx, "instrument", default="your instrument")).strip()
    song = str(_ctx_value(ctx, "question_song", "song", default="this song")).strip()

    if not from_key and display_key:
        from_key = _normalize_note_name(display_key.split()[0])

    lines: list[str] = []
    if from_key and to_key:
        src_i = _semitone_index(from_key)
        dst_i = _semitone_index(to_key)
        if src_i is not None and dst_i is not None:
            shift = (dst_i - src_i) % 12
            if shift > 6:
                shift -= 12
            lines.append(
                f"Moving **{song}** from concert **{from_key}** to **{to_key}** is **{_interval_name(shift)}**."
            )
            lines.append(
                f"Every chord and melody note moves by that same interval — e.g. a {from_key} chord becomes **{to_key}**."
            )
        else:
            lines.append(f"Transpose from **{from_key}** to **{to_key}** by shifting every note the same distance.")
    else:
        lines.append(
            "Identify the interval between the old and new key, then move every note and chord by that same amount."
        )

    lines.append(_transposing_instrument_note(instrument))
    if "alto" in instrument.lower():
        lines.append(
            "Practical check: if the guitar chart is in concert **E**, alto players often read in **C#**; "
            "for concert **F**, read in **D** (same written shift as the concert change)."
        )

    return MusicSolverResult(
        short_answer="\n".join(lines),
        math_idea="Uniform transposition: preserve interval relationships while changing home key.",
        problem_type="music_transposition",
        model_name="Music Coach transposition",
        variables=f"from_key={from_key or '?'}; to_key={to_key or '?'}",
        assumptions=[
            "Chord roots and melody tones move by the same interval unless you are deliberately reharmonizing.",
            "Transposing-instrument written keys differ from concert pitch — match the interval, not just the letter name.",
        ],
        confidence_pct=86,
        computed={"from_key": from_key, "to_key": to_key},
    )


_SIMILAR_SONG_LIBRARY: dict[str, tuple[str, ...]] = {
    "perfect": (
        "Thinking Out Loud — Ed Sheeran",
        "All of Me — John Legend",
        "Say You Won't Let Go — James Arthur",
        "A Thousand Years — Christina Perri",
        "Photograph — Ed Sheeran",
    ),
    "thinking out loud": (
        "Perfect — Ed Sheeran",
        "Make You Feel My Love — Adele",
        "Marry Me — Train",
        "Better Together — Jack Johnson",
    ),
    "someone like you": (
        "When I Was Your Man — Bruno Mars",
        "All of Me — John Legend",
        "Say Something — A Great Big World",
        "Stay — Rihanna ft. Mikky Ekko",
    ),
}


def _extract_reference_song(question: str, ctx: dict[str, Any]) -> str:
    import re

    q = str(question or "")
    m = re.search(r"similar to\s+(.+?)(?:\?|$)", q, flags=re.I)
    if m:
        return m.group(1).strip().strip("?.,")
    m = re.search(r"songs? like\s+(.+?)(?:\?|$)", q, flags=re.I)
    if m:
        return m.group(1).strip().strip("?.,")
    named = str(_ctx_value(ctx, "question_song", default="")).strip()
    if named:
        return named
    return _ctx_value(ctx, "title", default="your current song")


def _similar_songs_answer(question: str, ctx: dict[str, Any]) -> MusicSolverResult:
    reference = _extract_reference_song(question, ctx)
    ref_key = reference.lower().strip()
    instrument = str(_ctx_value(ctx, "instrument", default="your instrument")).strip()
    level = str(_ctx_value(ctx, "level", default="your level")).strip()
    picks = _SIMILAR_SONG_LIBRARY.get(ref_key)
    if not picks:
        for key, songs in _SIMILAR_SONG_LIBRARY.items():
            if key in ref_key or ref_key in key:
                picks = songs
                break
    if not picks:
        picks = (
            "Thinking Out Loud — Ed Sheeran",
            "All of Me — John Legend",
            "Say You Won't Let Go — James Arthur",
            "A Thousand Years — Christina Perri",
            "Photograph — Ed Sheeran",
        )
    lines = [f"Songs similar to **{reference}** for **{instrument}** at **{level}** level:"]
    for title in picks[:5]:
        lines.append(f"- **{title}** — acoustic pop ballad feel, steady groove, singable melody.")
    lines.append(
        "Use them to practice the same strumming/pulse, verse–chorus dynamics, and left-hand changes "
        "without learning a brand-new harmonic language."
    )
    return MusicSolverResult(
        short_answer="\n".join(lines),
        math_idea="Repertoire clustering by tempo, harmony density, and melodic range.",
        problem_type="similar_songs",
        model_name="Music Coach repertoire",
        assumptions=[
            "Picks favor mid-tempo pop ballads with I–V–vi–IV-style harmony similar to the reference.",
            "Choose one song and run a short section loop before adding the next title.",
        ],
        confidence_pct=81,
        computed={"reference_song": reference, "recommendations": list(picks[:5])},
    )


def _music_theory_answer(question: str, ctx: dict[str, Any]) -> MusicSolverResult:
    display_key = str(_ctx_value(ctx, "display_key", "key", default="")).strip() or "the song key"
    section = str(_ctx_value(ctx, "practice_focus_section", default="the section")).strip()
    return MusicSolverResult(
        short_answer=(
            f"For **{section}** in **{display_key}**, start with the **tonic scale** and chord functions: "
            "I = home, IV = lift, V = tension, vi = emotional color in pop harmony. "
            "Name the chords as scale degrees first, then connect that to what you hear in the progression. "
            "If you share a specific chord change from the question, isolate that pair and compare the voice-leading."
        ),
        math_idea="Functional harmony and scale-degree mapping for the active chart.",
        problem_type="music_theory",
        model_name="Music Coach theory",
        confidence_pct=74,
    )


def _route_for_intent(intent: str) -> MusicSolverRoute:
    labels = {
        "practice_plan": ("practice_plan", "Music Coach practice planner"),
        "chord_transition": ("chord_transition", "Music Coach chord transitions"),
        "section_focus": ("section_focus", "Music Coach section focus"),
        "tempo_key": ("tempo_key", "Music Coach tempo & key"),
        "backing_track": ("backing_track", "Music Coach backing track"),
        "skill_technique": ("skill_technique", "Music Coach technique roadmap"),
        "difficulty": ("skill_technique", "Music Coach technique roadmap"),
        "music_transposition": ("music_transposition", "Music Coach transposition"),
        "music_theory": ("music_theory", "Music Coach theory"),
        "similar_songs": ("similar_songs", "Music Coach repertoire"),
    }
    problem_type, model_name = labels.get(intent, ("music_general", "Music Coach"))
    return MusicSolverRoute(
        problem_type=problem_type,
        model_name=model_name,
        model_rationale=f"Routed from music intent `{intent}`.",
    )


def solve_instant_music_insight(
    question: str,
    context: dict[str, Any] | None,
) -> tuple[MusicSolverRoute, MusicSolverResult] | None:
    """Return (route, result) for supported music coaching questions."""
    q = str(question or "").strip()
    if not q:
        return None
    ctx = dict(context or {})
    try:
        from music_ami_context import detect_music_send_intent
    except ImportError:
        return None

    coach_page = str(ctx.get("coach_page") or ctx.get("source_page") or "").strip().lower()
    intent = detect_music_send_intent(q, coach_page)
    if intent not in _MUSIC_SOLVER_INTENTS:
        return None

    low = q.lower()
    chord_focus = intent in {"practice_plan", "chord_transition"} or any(
        p in low for p in ("chord change", "chord changes", "chord transition", "transitions")
    )

    if intent == "practice_plan":
        result = _practice_plan_answer(q, ctx, chord_focus=chord_focus)
    elif intent == "chord_transition":
        result = _chord_transition_answer(ctx, q)
    elif intent == "section_focus":
        result = _section_focus_answer(ctx, q)
    elif intent == "tempo_key":
        result = _tempo_key_answer(ctx)
    elif intent in {"skill_technique", "difficulty"}:
        result = _skill_technique_answer(ctx)
    elif intent == "backing_track":
        result = _backing_track_answer(ctx)
    elif intent == "music_transposition":
        result = _transposition_answer(q, ctx)
    elif intent == "similar_songs":
        result = _similar_songs_answer(q, ctx)
    elif intent == "music_theory":
        result = _music_theory_answer(q, ctx)
    else:
        return None

    route = _route_for_intent(intent)
    result.problem_type = route.problem_type
    result.model_name = route.model_name
    return route, result
