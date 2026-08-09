"""Specialized coach solvers — one module per intent family (vertical slice)."""

from __future__ import annotations

from typing import Callable

from music_coach_ami.app_knowledge import (
    CREATIVE_COMPARISONS,
    FEATURES,
    compare_features,
    context_completeness,
    feature_by_question,
    recommend_feature_for_goal,
)
from music_coach_ami.types import CoachContext, CoachIntent, CoachRequest, CoachResponse

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
    from music_coach_ami.scale_engine import (
        _interval_pattern_title,
        format_scale_request_summary,
        generate_scale_practice,
        parse_scale_practice_question,
        spec_to_dev_dict,
    )

    low = req.normalized_question.lower()
    instrument = (req.entities.instrument or req.context.instrument or "").strip()

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

    spec = parse_scale_practice_question(
        req.raw_question or req.normalized_question,
        instrument=instrument,
    )
    from music_coach_ami.exercise_patterns import apply_exercise_profile, exercise_profile_to_dev_dict

    profile = apply_exercise_profile(
        spec,
        level=req.context.level,
        practice_focus=req.context.practice_focus,
        instrument=instrument or req.context.instrument,
    )
    result = generate_scale_practice(spec)

    straight = len(spec.interval_patterns) == 1 and spec.interval_patterns[0] in (
        "straight",
        "scale",
        "unison",
    )
    pattern = spec.interval_patterns[0] if len(spec.interval_patterns) == 1 else ""
    if straight:
        heading = f"## {result.display_label}"
    else:
        interval_title = _interval_pattern_title(pattern) if pattern else "Diatonic intervals"
        heading = f"## {result.display_label} — {interval_title.lower()}"

    steps: list[str] = list(format_scale_request_summary(spec))
    if straight:
        steps.append(f"**Scale:** {result.scale_reference or result.written_sequence}")
        if result.scale_reference_descending:
            steps.append(f"**Descending scale:** {result.scale_reference_descending}")
    else:
        steps.append(f"**Scale:** {result.scale_reference or result.written_sequence}")
        if result.interval_pairs_display or result.interval_pairs_display_descending:
            short = pattern.rstrip("s").capitalize() + "s" if pattern else "Intervals"
            if spec.direction == "both":
                if result.interval_pairs_display:
                    steps.append(f"**Ascending {short} pattern:** {result.interval_pairs_display}")
                if result.interval_pairs_display_descending:
                    steps.append(
                        f"**Descending {short} pattern:** {result.interval_pairs_display_descending}"
                    )
            elif spec.direction == "descending":
                line = result.interval_pairs_display_descending or result.interval_pairs_display
                steps.append(f"**Descending {short} pattern:** {line}")
            elif result.interval_pairs_display:
                steps.append(f"**Ascending {short} pattern:** {result.interval_pairs_display}")
    steps.append("**Practice**")
    steps.extend(result.practice_guidance)
    steps.append("**Listen for**")
    steps.extend(result.what_to_listen_for)

    return CoachResponse(
        intent=CoachIntent.SCALE_PRACTICE,
        direct_answer=heading,
        explanation="",
        practice_steps=steps,
        what_to_listen_for=[],
        notation_abc=result.abc,
        notation_abc_sections=list(result.notation_sections or ([result.abc] if result.abc else [])),
        source_solver="ScalePracticeSolver",
        confidence=0.9,
        diagnostics={
            "tonic": result.tonic,
            "tonic_provenance": spec.tonic_provenance,
            "preferred_spelling": spec.preferred_spelling or result.display_label.split()[0],
            "scale_type": result.scale_type,
            "abc_key": result.abc_key,
            "reference_key": result.reference_key,
            "key_signature_hint": result.key_signature_hint,
            "notation_abc_present": bool(result.abc),
            "patterns": list(spec.interval_patterns),
            "octaves": spec.octave_count,
            "direction": spec.direction,
            "practice_sequence": result.practice_sequence,
            "scale_practice_spec": spec_to_dev_dict(spec, result),
            "exercise_profile": exercise_profile_to_dev_dict(profile),
            "instrument_used": profile.instrument or instrument or req.context.instrument,
            "instrument_provenance": req.context.extra.get("instrument_provenance")
            if isinstance(req.context.extra, dict)
            else {},
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


def _when_tail(when_to_use: str) -> str:
    text = str(when_to_use or "").strip()
    if text.lower().startswith("when "):
        return text[5:].strip()
    return text


def solve_app_navigation(req: CoachRequest) -> CoachResponse:
    low = req.normalized_question.lower()
    fid = req.entities.feature_id or feature_by_question(low) or "practice_log"
    feat = FEATURES.get(fid) or FEATURES["practice_log"]
    then_steps = [s for s in feat.usage_steps if not s.lower().startswith("open **practice log** from")]
    steps = [
        f"**Use:** {feat.display_name}",
        f"**Go to:** {feat.navigation_path or feat.display_name}",
        "**Then:**",
        *then_steps,
    ]
    when = _when_tail(feat.when_to_use)
    return CoachResponse(
        intent=CoachIntent.APP_NAVIGATION,
        direct_answer=feat.purpose,
        app_navigation_steps=steps,
        suggested_next_action=f"Use **{feat.display_name}** when {when.lower()}.",
        source_solver="AppNavigationSolver",
        confidence=0.9,
        diagnostics={
            "feature_id": feat.feature_id,
            "app_knowledge_consulted": feat.feature_id,
            "context_completeness": context_completeness(req.context),
        },
    )


def solve_feature_explanation(req: CoachRequest) -> CoachResponse:
    low = req.normalized_question.lower()
    if "difference between" in low and "backing" in low and "jam" in low:
        body = compare_features("backing_vs_jam") or CREATIVE_COMPARISONS["missions_vs_jam"]
        return CoachResponse(
            intent=CoachIntent.FEATURE_EXPLANATION,
            direct_answer=body,
            suggested_next_action="Use **Backing** for your current song; use **Jam Session Generator** for a fresh chart.",
            source_solver="FeatureExplanationSolver",
            confidence=0.92,
            diagnostics={"comparison": "backing_vs_jam", "app_knowledge_consulted": "backing,jam_session_generator"},
        )
    if "difference between" in low and "mission" in low and "live coach" in low:
        body = compare_features("missions_vs_live_coach")
        return CoachResponse(
            intent=CoachIntent.FEATURE_EXPLANATION,
            direct_answer=body,
            source_solver="FeatureExplanationSolver",
            confidence=0.92,
            diagnostics={"comparison": "missions_vs_live_coach"},
        )
    fid = req.entities.feature_id or feature_by_question(low)
    if not fid:
        if "backing" in low:
            fid = "backing"
        elif "practice log" in low:
            fid = "practice_log"
        elif "upload" in low:
            fid = "upload_analysis"
        elif "harmony map" in low:
            fid = "harmony_map"
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
        diagnostics={"feature_id": feat.feature_id, "app_knowledge_consulted": feat.feature_id},
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
    if "what part of the app" in low and any(p in low for p in ("scale", "chord", "theory")):
        steps = [
            "**Music Coach:** theory questions, scale exercises with notation, and coaching explanations "
            f"({FEATURES['music_coach'].navigation_path}).",
            "**Harmony Map:** visually explore chord relationships in your current practice key "
            f"({FEATURES['harmony_map'].navigation_path}).",
            "**Try:** Ask Music Coach e.g. “Show me B♭ major in thirds.”",
        ]
        return CoachResponse(
            intent=CoachIntent.APP_FEATURE_RECOMMENDATION,
            direct_answer=(
                "**Best fit:** Music Coach for scale exercises and theory; "
                "**Harmony Map** for visual chord relationships."
            ),
            practice_steps=steps,
            suggested_next_action="Open **Practice** for Music Coach, or **Creative → Harmony Map** for chords.",
            source_solver="FeatureRecommendationSolver",
            confidence=0.9,
            diagnostics={
                "selected_features": ["music_coach", "harmony_map"],
                "app_knowledge_consulted": "music_coach,harmony_map",
                "context_completeness": context_completeness(req.context),
            },
        )
    fid, why = recommend_feature_for_goal(low)
    feat = FEATURES.get(fid, FEATURES["practice"])
    return CoachResponse(
        intent=CoachIntent.APP_FEATURE_RECOMMENDATION,
        direct_answer=f"**Best fit:** {feat.display_name}",
        recommendation=why,
        app_navigation_steps=[
            f"**Go to:** {feat.navigation_path or feat.display_name}",
            *feat.usage_steps[:2],
        ],
        suggested_next_action=f"Open **{feat.display_name}** from the studio sidebar.",
        source_solver="FeatureRecommendationSolver",
        confidence=0.84,
        diagnostics={
            "feature_id": fid,
            "app_knowledge_consulted": fid,
            "context_completeness": context_completeness(req.context),
        },
    )


def _improv_beat_hint(_ctx: CoachContext) -> str:
    return "chord tones on **strong beats**"


def _improv_instrument_focus_lines(ctx: CoachContext) -> list[str]:
    from music_coach_instrument_voice import instrument_family

    fam = instrument_family(ctx.instrument)
    focus = str(ctx.practice_focus or "").lower()
    lines: list[str] = []
    if fam == "wind" and "tone" in focus:
        lines.append("Keep phrases **short and slurred**; prioritize tone before adding notes.")
    elif fam == "wind" and "artic" in focus:
        lines.append("Use **simple rhythms** with clear tonguing on each motif entry.")
    elif fam == "keyboard" and any(x in focus for x in ("harmony", "chord")):
        lines.append("Outline **guide tones** (3rd/7th) in the left hand while motifs stay sparse in the right.")
    elif fam == "guitar" and "rhythm" in focus:
        lines.append("Practice **motif rhythm** with one pitch first, then add notes from the progression.")
    return lines


def solve_improvisation_coaching(req: CoachRequest) -> CoachResponse:
    level = (req.context.level or "Intermediate").lower()
    completeness = context_completeness(req.context)
    song = str(req.context.active_song_title or "").strip()
    section = str(req.context.active_section or "").strip()
    chord = req.context.current_chord or "the current chord"
    prog = str(req.context.progression_summary or "").strip()
    practice_key = str(req.context.current_practice_key or "").strip()
    orig_key = str(req.context.song_original_key or "").strip()
    mission = str(req.context.active_mission or "").strip()
    bpm = req.context.tempo_bpm
    beat_hint = _improv_beat_hint(req.context)
    beginner = "begin" in level or "beginner" in level or "what is improvisation" in req.normalized_question.lower()

    key_note = ""
    if practice_key and orig_key and practice_key != orig_key:
        key_note = f" Practice in **{practice_key}** (your current concert key), not only the song's written key."

    if "what is improvisation" in req.normalized_question.lower():
        direct = (
            "**Improvisation** is composing in real time: you choose notes and rhythms that fit the "
            "harmony and style while you hear them."
        )
        steps = [
            "Start with **rhythm only** (one pitch) over a backing loop.",
            f"Add **{beat_hint}**.",
            "Turn a 3-note idea into a **motif** and repeat it with small changes.",
        ]
    elif completeness == "none" and ("this song" in req.normalized_question.lower() or "current" in req.normalized_question.lower()):
        direct = "Choose the **active song and section** you want to work on first, then loop that harmony."
        steps = [
            "Open **Practice** or the song picker and set your active song.",
            "Select the **section** (verse, chorus, etc.) you want to improvise over.",
            "Open **Backing Track Studio** and loop that section at a comfortable tempo.",
            f"Restrict the first pass to **{beat_hint}**, then develop one **motif**.",
        ]
    elif completeness in ("exact", "partial") and song:
        ctx_line = f"**{song}**"
        if section:
            ctx_line += f" — **{section}**"
        if prog:
            ctx_line += f" ({prog})"
        if bpm:
            ctx_line += f" at **{bpm} BPM**"
        if mission:
            ctx_line += f" · Mission: **{mission}**"
        direct = f"**Goal:** Develop improvisation over {ctx_line}.{key_note}"
        steps = [
            "Loop the section slowly in **Backing Track Studio** on the **actual song progression**.",
            f"Pass 1: **{beat_hint}** only.",
            "Pass 2: one **4-note motif** — repeat, then change rhythm.",
            "Pass 3: add **approach notes** on weak beats only.",
        ]
        steps.extend(_improv_instrument_focus_lines(req.context))
    elif beginner or "start improvis" in req.normalized_question.lower():
        direct = "Start small: **fewer notes, clearer rhythm**, and repeat one idea."
        steps = [
            f"Over **{chord}**, play roots and 3rds on **strong beats**.",
            "Use a **4-note motif**; repeat it twice, then change one note.",
            "Leave **space** — improv is also when you don't play.",
        ]
    elif "less random" in req.normalized_question.lower():
        direct = "Randomness usually means too many notes and no repeating idea."
        steps = [
            "Pick **one motif** (3–5 notes) and repeat it every 2 bars.",
            "Use **guide tones** (3rd and 7th) on chord changes.",
            "Plan **rests** on weak beats — call and response with yourself.",
        ]
    else:
        direct = f"Use the active harmony (**{chord}** when available) to target chord tones and motif development."
        steps = [
            "Map **guide tones** through the progression.",
            "Add **approach notes** only on weak beats.",
            "Develop a motif with **rhythmic displacement** (same notes, new rhythm).",
        ]

    listen = [
        "Chord changes feel like arrivals on strong beats",
        "You can hum your motif when you stop playing",
    ]
    backing = FEATURES["backing"]
    missions = FEATURES["missions"]
    upload = FEATURES["upload_analysis"]
    jam = FEATURES["jam_session_generator"]
    app_steps = [
        f"**Use in the app:** **{backing.display_name}** — {backing.purpose.split('.')[0]}.",
        f"**{missions.display_name}** — only when the mission keeps this song/section progression.",
        f"**{upload.display_name}** — feedback on a recorded take; **Live Coach** for live targets.",
        f"**Not for this goal:** **{jam.display_name}** — {jam.when_not_to_use.split('—')[0].strip()}.",
    ]
    next_action = (
        f"Open **Backing Track Studio**, scope to **{section or 'your section'}**, "
        "and loop at ~75% tempo before adding notes."
        if song
        else "Set your active song, then open **Backing Track Studio** to loop the section."
    )
    return CoachResponse(
        intent=CoachIntent.IMPROVISATION_COACHING,
        direct_answer=direct,
        practice_steps=steps + app_steps,
        what_to_listen_for=listen,
        suggested_next_action=next_action,
        source_solver="ImprovisationCoachSolver",
        confidence=0.83,
        diagnostics={
            "context_completeness": completeness,
            "active_song_title": song,
            "active_section": section,
            "progression_summary": prog,
            "current_practice_key": practice_key,
            "app_knowledge_consulted": "backing,missions,upload_analysis,jam_session_generator",
        },
    )


def _repertoire_query_mode(question: str) -> str:
    low = str(question or "").lower()
    if any(
        p in low
        for p in (
            "similar to",
            "like my current",
            "like this song",
            "songs like",
            "similar to my current",
        )
    ):
        return "similar"
    if any(
        p in low
        for p in (
            "improve improvisation",
            "improve improv",
            "learning improvisation",
            "to work on improv",
            "practice to improve improvisation",
        )
    ):
        return "goal_improv"
    return "broad"


def solve_repertoire_recommendation(req: CoachRequest) -> CoachResponse | None:
    mode = _repertoire_query_mode(req.raw_question or req.normalized_question)
    instrument = req.entities.instrument or req.context.instrument or "your instrument"
    song = req.context.active_song_title or "your active song"

    if mode == "broad":
        steps = [
            "**Comfort piece** — a song you can play slowly in time; focus on **phrasing and tone**.",
            "**Development piece** — harmony that supports your current skill (e.g. clear changes for improv study).",
            "**Stretch piece** — slightly harder range, rhythm, or technique; keep tempo conservative.",
        ]
        if req.context.active_song_title:
            steps.append(
                f"Keep **{req.context.active_song_title}** as one anchor; add the other roles from your song list."
            )
        return CoachResponse(
            intent=CoachIntent.REPERTOIRE_RECOMMENDATION,
            direct_answer="**Goal:** Balance repertoire by practice role, not only by similarity.",
            practice_steps=steps,
            suggested_next_action="Open the **song picker** and tag one comfort, one development, and one stretch tune.",
            source_solver="RepertoireSolver(broad)",
            confidence=0.86,
            diagnostics={
                "repertoire_mode": "broad",
                "context_completeness": context_completeness(req.context),
            },
        )

    if mode == "goal_improv":
        return CoachResponse(
            intent=CoachIntent.REPERTOIRE_RECOMMENDATION,
            direct_answer=f"**Goal:** Pick repertoire that builds improvisation on **{instrument}**.",
            practice_steps=[
                "**Development piece:** choose a tune with clear **ii–V–I** or modal loops you can outline with chord tones.",
                "**Comfort piece:** same song at slow tempo — repeat one **motif** until it feels natural.",
                "**Stretch piece:** a tune with faster harmonic rhythm; improvise only on **strong beats** first.",
            ],
            suggested_next_action="Open **Creative → Missions** on a development tune after you can loop it in **Backing**.",
            source_solver="RepertoireSolver(goal_improv)",
            confidence=0.84,
            diagnostics={"repertoire_mode": "goal_improv"},
        )

    try:
        from music_ami_instant_solver import _similar_songs_answer

        legacy_ctx = {
            "coach_page": req.context.coach_page,
            "instrument": instrument,
            "level": req.context.level,
            "active_song": {"title": song},
            "title": song,
        }
        q = req.raw_question
        if "my current song" in (q or "").lower() and song:
            q = f"What songs are similar to {song}?"
        result = _similar_songs_answer(q or req.normalized_question, legacy_ctx)
        return CoachResponse(
            intent=CoachIntent.REPERTOIRE_RECOMMENDATION,
            direct_answer=result.short_answer,
            source_solver="RepertoireSolver(similar_catalog)",
            confidence=0.8,
            diagnostics={"repertoire_mode": "similar", "model": result.model_name},
        )
    except ImportError:
        return CoachResponse(
            intent=CoachIntent.REPERTOIRE_RECOMMENDATION,
            direct_answer=(
                "Build a balanced repertoire: one **comfortable** song for tone/phrasing, "
                "one **harmony-rich** song for improvisation, and one **stretch** piece for technique."
            ),
            practice_steps=[
                "Pick a song you can already play slowly in time — focus on **musical phrasing**.",
                "Add a tune with clear **ii–V–I** or modal harmony for improv study.",
                "Keep one piece **slightly above** your performance tempo as a growth target.",
            ],
            suggested_next_action="Open the **song picker** and tag one song in each category.",
            source_solver="RepertoireSolver(fallback)",
            confidence=0.78,
            diagnostics={"repertoire_mode": mode, "context_completeness": context_completeness(req.context)},
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
