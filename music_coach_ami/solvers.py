"""Specialized coach solvers — one module per intent family (vertical slice)."""

from __future__ import annotations

from typing import Callable

from music_coach_ami.app_knowledge import CREATIVE_COMPARISONS, FEATURES
from music_coach_ami.types import CoachIntent, CoachRequest, CoachResponse

SolverFn = Callable[[CoachRequest], CoachResponse | None]


def _minutes(req: CoachRequest) -> int:
    if req.constraints.requested_duration_minutes:
        return req.constraints.requested_duration_minutes
    if req.context.available_practice_minutes:
        return max(15, min(90, int(req.context.available_practice_minutes)))
    return 30


def _allocate(total: int, weights: dict[str, float]) -> dict[str, int]:
    if not weights:
        return {}
    norm = sum(max(0.0, float(v)) for v in weights.values()) or 1.0
    raw = {k: total * max(0.0, float(v)) / norm for k, v in weights.items()}
    rounded = {k: int(v) for k, v in raw.items()}
    remainder = total - sum(rounded.values())
    keys = list(raw.keys())
    i = 0
    while remainder > 0 and keys:
        rounded[keys[i % len(keys)]] += 1
        remainder -= 1
        i += 1
    return rounded


def solve_practice_plan(req: CoachRequest) -> CoachResponse:
    from music_coach_instrument_voice import instrument_family, practice_plan_profile, tone_focused_practice_plan

    minutes = _minutes(req)
    instrument = req.entities.instrument or req.context.instrument or "your instrument"
    tone = req.constraints.tone_focus or "tone" in req.normalized_question.lower()
    chord_focus = "chord" in req.normalized_question.lower()

    if tone:
        plan = tone_focused_practice_plan(
            instrument,
            minutes,
            level=req.context.level,
            song_title=req.context.active_song_title,
            section=req.context.active_section,
        )
        steps = list(plan.get("steps") or [])
        listen = list(plan.get("listen") or [])
        return CoachResponse(
            intent=CoachIntent.PRACTICE_PLAN,
            direct_answer=f"{plan.get('headline', '')}\n\n{plan.get('goal', '')}".strip(),
            practice_steps=steps,
            what_to_listen_for=listen,
            recommendation=str(plan.get("closing") or "").strip(),
            source_solver="PracticePlanSolver",
            confidence=0.88,
            diagnostics={"session_minutes": minutes, "tone_focus": True},
        )

    weights, focus_line = practice_plan_profile(instrument, chord_focus=chord_focus)
    blocks = _allocate(minutes, weights)
    steps = [f"**{m} min** — {label}" for label, m in blocks.items()]
    return CoachResponse(
        intent=CoachIntent.PRACTICE_PLAN,
        direct_answer=f"Here is a **{minutes}-minute** plan for **{instrument}**:",
        practice_steps=steps,
        recommendation=focus_line,
        progression_criteria=[
            "Advance tempo or range only when the current block stays clean 4/5 tries.",
        ],
        source_solver="PracticePlanSolver",
        confidence=0.85,
        diagnostics={"session_minutes": minutes, **blocks},
    )


def solve_scale_practice(req: CoachRequest) -> CoachResponse:
    from music_coach_ami.scale_engine import generate_scale_practice, parse_scale_practice_question

    low = req.normalized_question.lower()
    instrument = req.entities.instrument or req.context.instrument or ""

    if "what scales should i practice" in low:
        return CoachResponse(
            intent=CoachIntent.SCALE_PRACTICE,
            direct_answer="**Scale practice priorities for today**",
            practice_steps=[
                "Pick **one major and one minor** key you use in repertoire (or your current song's key).",
                "Run each **one octave straight**, then **in thirds** at 60–72 BPM.",
                "Add **fourths or sixths** only after thirds are clean three times.",
                "Log which keys felt unstable in Practice Log.",
            ],
            suggested_next_action='Ask: "Show me Eb major in thirds" for notation you can read at the stand.',
            source_solver="ScalePracticeSolver",
            confidence=0.82,
        )

    spec = parse_scale_practice_question(req.normalized_question, instrument=instrument)
    result = generate_scale_practice(spec)

    steps: list[str] = []
    if len(spec.interval_patterns) == 1 and spec.interval_patterns[0] in ("straight", "scale", "unison"):
        steps.append(f"**Scale:** {' '.join(result.scale_notes)}")
    else:
        steps.append(f"**Diatonic scale:** {' '.join(result.scale_notes)}")
    if result.written_sequence:
        steps.append(f"**Written sequence:** {result.written_sequence}")
    steps.extend(result.practice_guidance)

    listen = [
        "Even tone on every note of each interval pair",
        "Correct spelling / intonation on altered scale degrees (e.g. E♯ in C♯ major)",
    ]

    return CoachResponse(
        intent=CoachIntent.SCALE_PRACTICE,
        direct_answer=f"**{result.label}** — {result.key_signature_hint}",
        explanation="Use the staff below; key signature follows conventional spelling for this tonic.",
        practice_steps=steps,
        what_to_listen_for=listen,
        notation_abc=result.abc,
        source_solver="ScalePracticeSolver",
        confidence=0.9,
        diagnostics={
            "tonic": result.tonic,
            "scale_type": result.scale_type,
            "patterns": list(spec.interval_patterns),
            "octaves": spec.octave_count,
            "direction": spec.direction,
        },
    )


def solve_technique_problem(req: CoachRequest) -> CoachResponse:
    from music_coach_instrument_voice import instrument_family

    instrument = req.entities.instrument or req.context.instrument or "your instrument"
    fam = instrument_family(instrument)
    topic = req.entities.skill_topic or "tone"
    low = req.normalized_question.lower()

    if topic == "tone" or "airy" in low or "tone" in low:
        direct = (
            f"On **{instrument}**, an airy tone often means the airstream and embouchure are not "
            "focusing the column of air — not that you need to blow harder."
        )
        steps = [
            "Play **one comfortable mid-register note** for **8 seconds** (4 counts in, hold, 4 out).",
            "Repeat on **5 different notes** in the same register — same dynamic, same articulation.",
            "Keep the pitch stable: if pitch wavers, reduce air speed slightly and reset embouchure.",
            "Record one pass — you should hear a **clear core** (not only air noise).",
        ]
        listen = [
            "Stable pitch without wavering",
            "Even volume from start to end of the note",
            "A centered ‘core’ to the sound, not just breath noise",
        ]
        progress = [
            "Move to the next note or add 2 seconds only when **4 of 5** attempts pass the listen checklist.",
        ]
    elif topic == "articulation" or "articulation" in low:
        direct = f"Clean articulation on **{instrument}** starts with **slow, identical** attacks."
        steps = [
            "Choose one scale or 5-note pattern at **60–72 BPM**.",
            "Tongue or attack each note with the **same syllable** (e.g. ‘ta’) — no accents yet.",
            "Increase tempo by **4 BPM** only when every note speaks at the same instant.",
        ]
        listen = ["Instant response — no late or double attacks", "Even volume across notes"]
        progress = ["At target tempo, add one musical phrase from your active song."]
    else:
        direct = f"For **{instrument}**, isolate the problem at **slow tempo** before adding repertoire."
        steps = [
            "Identify the smallest motion (finger, breath, or slide) that fails.",
            "Loop **4–8 beats** at 50–70% performance tempo.",
            "Add tempo in **5 BPM** steps when the loop is clean 3 times in a row.",
        ]
        listen = ["Relaxed body — no extra tension at the break point"]
        progress = ["Connect the fixed fragment back into the full phrase."]

    if fam == "keyboard":
        steps[0] = "Play **one hand at a time** — " + steps[0].lower() if steps else steps

    return CoachResponse(
        intent=CoachIntent.TECHNIQUE_PROBLEM,
        direct_answer=direct,
        practice_steps=steps,
        what_to_listen_for=listen,
        progression_criteria=progress,
        source_solver="TechniqueCoachSolver",
        confidence=0.86,
    )


def solve_app_navigation(req: CoachRequest) -> CoachResponse:
    fid = req.entities.feature_id or "practice_log"
    feat = FEATURES.get(fid) or FEATURES["practice_log"]
    return CoachResponse(
        intent=CoachIntent.APP_NAVIGATION,
        direct_answer=f"To use **{feat.display_name}**:",
        app_navigation_steps=list(feat.usage_steps),
        explanation=feat.purpose,
        suggested_next_action=f"Open **{feat.display_name}** when {feat.when_to_use.lower()}",
        source_solver="AppNavigationSolver",
        confidence=0.9,
        diagnostics={"feature_id": feat.feature_id},
    )


def solve_feature_explanation(req: CoachRequest) -> CoachResponse:
    low = req.normalized_question.lower()
    fid = req.entities.feature_id
    if not fid:
        if "backing" in low:
            fid = "backing"
        elif "practice log" in low:
            fid = "practice_log"
        elif "upload" in low:
            fid = "upload_analysis"
        else:
            fid = "backing"
    feat = FEATURES.get(fid, FEATURES["backing"])
    return CoachResponse(
        intent=CoachIntent.FEATURE_EXPLANATION,
        direct_answer=f"**{feat.display_name}** — {feat.purpose}",
        explanation=f"**When to use it:** {feat.when_to_use}",
        app_navigation_steps=list(feat.usage_steps),
        suggested_next_action=f"Try **{feat.display_name}** on your current song or practice goal.",
        source_solver="FeatureExplanationSolver",
        confidence=0.88,
        diagnostics={"feature_id": feat.feature_id},
    )


def solve_creative_feature_help(req: CoachRequest) -> CoachResponse:
    low = req.normalized_question.lower()
    if "difference between" in low and "mission" in low and "jam" in low:
        body = CREATIVE_COMPARISONS["missions_vs_jam"]
        return CoachResponse(
            intent=CoachIntent.CREATIVE_FEATURE_HELP,
            direct_answer=body,
            suggested_next_action="Pick **Missions** for a structured song challenge, or **Jam Session Generator** to explore freely.",
            source_solver="CreativeHelpSolver",
            confidence=0.92,
        )
    fid = req.entities.feature_id or "creative"
    if "mission" in low:
        fid = "missions"
    elif "jam session generator" in low:
        fid = "jam_session_generator"
    elif "style jam" in low:
        fid = "style_jam"
    elif "live coach" in low:
        fid = "live_coach"
    elif "harmony map" in low:
        fid = "harmony_map"
    elif "motif" in low:
        fid = "motif"
    feat = FEATURES.get(fid, FEATURES["creative"])
    return CoachResponse(
        intent=CoachIntent.CREATIVE_FEATURE_HELP,
        direct_answer=f"**{feat.display_name}** — {feat.purpose}",
        explanation=f"Musicians use it when {feat.when_to_use.lower()}",
        app_navigation_steps=list(feat.usage_steps),
        source_solver="CreativeHelpSolver",
        confidence=0.87,
        diagnostics={"feature_id": feat.feature_id},
    )


def solve_app_feature_recommendation(req: CoachRequest) -> CoachResponse:
    low = req.normalized_question.lower()
    if "just want to jam" in low or "just improvise" in low:
        rec = "**Jam Session Generator** or **Style Jam** (Creative → Entry & Jam)."
        why = "Both give harmonic context for open-ended improvising without a fixed assignment."
    elif "structured" in low and "improv" in low:
        rec = "**Missions** (Creative → Missions) with your active song."
        why = "Missions set a concrete objective (motif, section, chord) instead of a free jam."
    elif "feedback" in low and ("record" in low or "take" in low):
        rec = "**Upload & Analysis**."
        why = "You get structured feedback on a recording you already made."
    elif "track" in low and "practiced" in low:
        rec = "**Practice Log**."
        why = "Sessions accumulate for progress reports and coaching history."
    elif "tone" in low or "technique" in low:
        rec = "**Practice** page with focused technique blocks, then **Upload Analysis** to check tone."
        why = "Technique needs isolated reps; analysis confirms what changed."
    elif "current song" in low or "practice my song" in low:
        rec = "**Practice** for reading/technique, **Backing** for tempo/groove, **Missions** for improv goals."
        why = "Each tool matches a different layer of song work."
    else:
        rec = "**Creative → Entry & Jam** for improv, **Practice Log** to track work."
        why = "Match the feature to whether you are exploring, structuring, or documenting."
    return CoachResponse(
        intent=CoachIntent.APP_FEATURE_RECOMMENDATION,
        direct_answer=f"Based on your goal: {rec}",
        recommendation=why,
        suggested_next_action="Open the recommended area from the studio sidebar.",
        source_solver="FeatureRecommendationSolver",
        confidence=0.84,
    )


def solve_improvisation_coaching(req: CoachRequest) -> CoachResponse:
    level = (req.context.level or "Intermediate").lower()
    chord = req.context.current_chord or "the current chord"
    beginner = "begin" in level or "beginner" in level or "what is improvisation" in req.normalized_question.lower()

    if "what is improvisation" in req.normalized_question.lower():
        direct = (
            "**Improvisation** is composing in real time: you choose notes and rhythms that fit the "
            "harmony and style while you hear them."
        )
        steps = [
            "Start with **rhythm only** (one pitch) over a backing loop.",
            "Add **chord tones** on strong beats.",
            "Turn a 3-note idea into a **motif** and repeat it with small changes.",
        ]
    elif beginner or "start improvis" in req.normalized_question.lower():
        direct = "Start small: **fewer notes, clearer rhythm**, and repeat one idea."
        steps = [
            f"Over **{chord}**, play only roots and 3rds on beats 1 and 3.",
            "Use a **4-note motif**; repeat it twice, then change one note.",
            "Leave **space** — improv is also when you don't play.",
        ]
    elif "less random" in req.normalized_question.lower():
        direct = "Randomness usually means too many notes and no repeating idea."
        steps = [
            "Pick **one motif** (3–5 notes) and repeat it every 2 bars.",
            "Use **guide tones** (3rd and 7th) on chord changes.",
            "Plan **rests** on bar 2 and 4 — call and response with yourself.",
        ]
    else:
        direct = f"Use the active harmony (**{chord}** when available) to target chord tones and motif development."
        steps = [
            "Map **guide tones** through the progression.",
            "Add **approach notes** only on weak beats.",
            "Develop a motif with **rhythmic displacement** (same notes, new rhythm).",
        ]

    listen = [
        "Chord changes feel ‘arrival’ on strong beats",
        "You can hum your motif when you stop playing",
    ]
    return CoachResponse(
        intent=CoachIntent.IMPROVISATION_COACHING,
        direct_answer=direct,
        practice_steps=steps,
        what_to_listen_for=listen,
        suggested_next_action="Open **Creative → Missions** or **Jam Session Generator** with the same key as your song.",
        source_solver="ImprovisationCoachSolver",
        confidence=0.83,
    )


def solve_repertoire_recommendation(req: CoachRequest) -> CoachResponse | None:
    """Delegate to legacy similar-songs solver when available."""
    try:
        from music_ami_instant_solver import _similar_songs_answer

        legacy_ctx = {
            "coach_page": req.context.coach_page,
            "instrument": req.entities.instrument or req.context.instrument,
            "level": req.context.level,
        }
        result = _similar_songs_answer(req.raw_question, legacy_ctx)
        return CoachResponse(
            intent=CoachIntent.REPERTOIRE_RECOMMENDATION,
            direct_answer=result.short_answer,
            source_solver="RepertoireSolver(legacy_catalog)",
            confidence=0.8,
            diagnostics={"model": result.model_name},
        )
    except ImportError:
        return CoachResponse(
            intent=CoachIntent.REPERTOIRE_RECOMMENDATION,
            direct_answer=(
                "Pick 3–5 songs one step below your performance tempo with clear harmony "
                "(e.g. I–V–vi–IV or ii–V–I forms) and loop one section daily."
            ),
            source_solver="RepertoireSolver",
            confidence=0.6,
        )


def solve_theory_explanation(req: CoachRequest) -> CoachResponse | None:
    try:
        from music_ami_instant_solver import _music_theory_answer

        legacy_ctx = {
            "display_key": req.context.current_practice_key,
            "practice_focus_section": req.context.active_section,
            "instrument": req.entities.instrument or req.context.instrument,
        }
        result = _music_theory_answer(req.raw_question, legacy_ctx)
        return CoachResponse(
            intent=CoachIntent.THEORY_EXPLANATION,
            direct_answer=result.short_answer,
            explanation="Connect this concept to the key and section you are practicing.",
            source_solver="TheorySolver",
            confidence=0.78,
        )
    except ImportError:
        return None


def solve_song_coaching(req: CoachRequest) -> CoachResponse:
    section = req.context.active_section or "the first section that feels shaky"
    song = req.context.active_song_title or "your active song"
    bpm = req.context.tempo_bpm
    tempo_line = (
        f"Start at **{max(40, int(bpm * 0.75))} BPM** (~75% of {bpm}) if transitions stumble."
        if bpm
        else "Start **15–25% below** your target tempo until the section is clean."
    )
    return CoachResponse(
        intent=CoachIntent.SONG_COACHING,
        direct_answer=f"For **{song}**, prioritize **{section}** first — it becomes the anchor for the rest.",
        practice_steps=[
            "Loop **4–8 bars** of that section with a metronome or Backing.",
            tempo_line,
            "When clean 3× in a row, add the **next section** for a 2-section chain.",
        ],
        suggested_next_action="Set Backing scope to that section and log the session in Practice Log.",
        source_solver="SongCoachSolver",
        confidence=0.8,
    )


SOLVER_REGISTRY: dict[CoachIntent, SolverFn] = {
    CoachIntent.PRACTICE_PLAN: solve_practice_plan,
    CoachIntent.TECHNIQUE_PROBLEM: solve_technique_problem,
    CoachIntent.APP_NAVIGATION: solve_app_navigation,
    CoachIntent.FEATURE_EXPLANATION: solve_feature_explanation,
    CoachIntent.CREATIVE_FEATURE_HELP: solve_creative_feature_help,
    CoachIntent.APP_FEATURE_RECOMMENDATION: solve_app_feature_recommendation,
    CoachIntent.IMPROVISATION_COACHING: solve_improvisation_coaching,
    CoachIntent.REPERTOIRE_RECOMMENDATION: solve_repertoire_recommendation,
    CoachIntent.THEORY_EXPLANATION: solve_theory_explanation,
    CoachIntent.SCALE_PRACTICE: solve_scale_practice,
    CoachIntent.SONG_COACHING: solve_song_coaching,
}
