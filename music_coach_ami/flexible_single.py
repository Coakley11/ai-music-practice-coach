"""Bounded standalone drills, using AMI's pitch writer, profiles and warmup history.

No API calls. Named keys are concert keys, as elsewhere in AMI. Requests outside
this vocabulary are refused rather than approximated as an unrelated scale.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re

from music_coach_ami import warmup_engine as we, warmup_plan as wp
from music_coach_ami import scale_pattern_harmony as sph
from music_coach_ami.types import CoachIntent, CoachResponse


def _reply(text, plan=None, session=None, failed=""):
    row = plan["items"][0] if plan else None
    return CoachResponse(
        intent=CoachIntent.SCALE_PRACTICE, direct_answer=text,
        source_solver="InstrumentExercise", confidence=0.95,
        notation_abc=row["abc"] if row else "",
        practice_steps=row["how"] if row else [],
        diagnostics={"single_exercise": True, "single_exercise_failed": failed,
                     "single_exercise_plan": copy.deepcopy(plan),
                     "single_exercise_history": wp.history(session) if session is not None else {}},
    )


def _response(plan, session, lead=""):
    if plan["spec"].get("trumpet"):
        from music_coach_ami.trumpet_technique import response
        return response(plan, session, lead)
    if plan["spec"].get("technique"):
        from music_coach_ami.instrument_technique import response
        return response(plan, session, lead)
    p, r, spec = plan["player"], plan["items"][0], plan["spec"]
    return _reply(
        f"{lead}**{r['title']}** — {p['label']}, {spec['level']}, {spec['register']} register. "
        f"Concert key {p['concert_key']}; written key {p['written_key']}. "
        f"♩ = {r['bpm']}; play {r['reps']} time(s).", plan, session)


def _window(player, level, register):
    # Split the existing level window, never widen a Beginner to the overall range.
    lo, hi = player.window(level)
    if register == "low":
        hi = min(hi, lo + 12)
    elif register == "high":
        lo = max(lo, hi - 12)
    elif register == "middle":
        mid = (lo + hi) // 2
        lo, hi = max(lo, mid - 9), min(hi, mid + 9)
    return lo, hi


def build(spec: dict) -> dict:
    if spec.get("trumpet"):
        from music_coach_ami.trumpet_technique import build as build_trumpet
        return build_trumpet(spec)
    if spec.get("technique"):
        from music_coach_ami.instrument_technique import build as build_technique
        return build_technique(spec)
    if spec["level"] not in we.LEVELS:
        raise we.WarmupUnavailable("choose Beginner, Intermediate or Advanced")
    player = we.make_player(spec["instrument"], spec["concert_key"])
    tonic, mode = we.practical_key(*we.split_key(player.written_key))
    lo, hi = _window(player, spec["level"], spec["register"])
    family, advanced = spec["family"], spec["level"] == "Advanced"
    names = we.scale_spelling(tonic, mode)
    if family == "arpeggio":
        # Use the shared chord reader for pitch classes; preserve diatonic spelling.
        suffix = {"major": "", "maj7": "maj7", "7": "7", "minor": "m", "m7": "m7"}[spec["quality"]]
        roles = sph.chord_tone_roles(tonic + suffix)
        letters = "CDEFGAB"
        start = letters.index(tonic[0])
        names = [sph._spell((start + degree) % 7, pc) for role in ("R", "3", "5", "7")
                 for pc, actual in roles.items() if actual == role
                 for degree in [{"R": 0, "3": 2, "5": 4, "7": 6}[role]]]
    candidates = sorted((m, name) for name in names for m in range(lo, hi + 1) if m % 12 == sph.pc_of(name))
    if not candidates:
        raise we.WarmupUnavailable("no notes fit the requested register")
    if family == "long_tones":
        count = spec["count"]
        if spec["register"] == "middle":
            candidates = [(m, n) for m, n in candidates if m <= lo + 9]
        # Evenly distributed, genuinely distinct pitches within the comfort window.
        if len(candidates) < count:
            raise we.WarmupUnavailable("that many distinct long tones do not fit the requested register")
        chosen = [candidates[round(i * (len(candidates) - 1) / max(1, count - 1))] for i in range(count)]
        unit = "whole"
    elif family == "register":
        # A generic instrument/register request is a short five-note drill,
        # not an implicit full-octave scale or a timed warmup.
        chosen = candidates[-5:] if spec["register"] == "high" else candidates[:5]
        if spec["direction"] == "descending":
            chosen.reverse()
        unit = {"Beginner": "quarter", "Intermediate": "eighth", "Advanced": "sixteenth"}[spec["level"]]
    else:
        roots = [i for i, (_, name) in enumerate(candidates) if name == tonic]
        span = len(names)
        valid = [i for i in roots if i + span < len(candidates)]
        if not valid:
            raise we.WarmupUnavailable("a complete octave does not fit this level and register; choose another key or register")
        base = valid[-1] if spec["register"] == "high" else valid[0]
        chosen = candidates[base:base + span + 1]
        unit = {"Beginner": "quarter", "Intermediate": "eighth", "Advanced": "sixteenth"}[spec["level"]]
        if spec["buster"]:
            # Permutations with alternating extremes and direction changes, not a renamed scale.
            if not advanced:
                raise we.WarmupUnavailable("finger-busters require Advanced level; ask for an easier technique exercise instead")
            pool = candidates[base:]
            if len(pool) < 5:
                pool = candidates
            order = []
            for i in range(len(pool) - 3):
                order.extend((i, min(i + 4, len(pool) - 1), i + 1, i + 3, i + 2, i, i + 3, i + 1))
            chosen = [pool[i] for i in order]
            if spec["direction"] == "descending":
                chosen.reverse()
        elif spec["direction"] == "descending":
            chosen.reverse()
        elif spec["direction"] == "up and down":
            chosen += chosen[-2::-1]
    unit = spec.get("rhythm") or unit
    notes = [we.Note(name, (m - sph.pc_of(name)) // 12 - 1, unit,
                     spec.get("articulation", "")) for m, name in chosen]
    if family == "long_tones":
        notes = [part for n in notes for part in (n, we.Note("", 0, "whole"))]
    notes = we._fill_bar(notes)
    bpm = spec["bpm"]
    title = "Finger-buster" if spec["buster"] else "Five-note register exercise" if family == "register" else family.replace("_", " ").capitalize()
    title += f" — {tonic} {spec['quality'] if family == 'arpeggio' else mode}"
    if family != "long_tones":
        title += f" ({spec['direction']})"
    else:
        title = f"{spec['count']} " + title
    built = we.Built(notes, bpm, title, ["Start slowly; keep every attack even. Stop and rest if coordination or tone deteriorates."], [], {"window": [lo, hi]})
    allowed = {sph.pc_of(n) for n in names} if family == "arpeggio" else None
    return package(spec, player, built, tonic, mode, allowed_pcs=allowed)


def package(spec, player, built, tonic, mode, *, allowed_pcs=None):
    """One canonical notation, verification and stored-plan path for single drills."""
    notes, bpm, title = built.notes, built.bpm, built.title
    family = spec["family"]
    lo, hi = built.meta["window"]
    abc, diag = we.render(player, built, tonic, mode, title=title)
    checks = we.verify(player, spec["level"], built, tonic, mode, diag, allowed_pcs=allowed_pcs)
    written = [n.midi for n in notes if not n.rest]
    if not all(lo <= m <= hi and player.play_low <= m <= player.play_high for m in written):
        raise we.WarmupUnavailable("notes exceed the instrument's level window")
    seconds = we.pass_seconds(built)
    row = {"uid": "single", "family": family, "title": title, "abc": abc, "bpm": bpm, "reps": spec["reps"],
           "how": built.how, "written_midi": written, "sounding_midi": [m - player.offset for m in written],
           "written_notes": [f"{n.spelled}{n.octave}" for n in notes if not n.rest],
           "durations": [n.dur for n in notes], "checks": checks, "pass_seconds": seconds}
    return {"id": "single-" + hashlib.sha1(json.dumps([spec, abc], sort_keys=True).encode()).hexdigest()[:12], "spec": copy.deepcopy(spec), "items": [row], "level": spec["level"],
            "player": {"key": player.key, "label": player.label, "offset": player.offset, "concert_key": player.concert_key,
                       "written_key": player.written_key}, "minutes": seconds / 60, "total_seconds": seconds * spec["reps"]}


def controls(spec, q):
    changed = False
    tempo = re.search(r"(?:tempo(?: of| to)?\s*|at\s+)(\d+)(?:\s*bpm)?|\b(\d+)\s*bpm\b", q)
    if tempo:
        spec["bpm"] = max(36, min(160, int(tempo[1] or tempo[2])))
        changed = True
    reps = re.search(r"\b(\d+)\s*(?:times|repetitions)|repetitions?(?: to| of)?\s+(\d+)", q)
    if reps:
        spec["reps"] = max(1, min(12, int(reps[1] or reps[2])))
        changed = True
    rhythm = re.search(r"\b(whole|half|quarter|eighth|sixteenth)[ -]notes?\b", q)
    if rhythm:
        spec["rhythm"] = rhythm[1]
        changed = True
    for art in ("staccato", "tenuto", "accent"):
        if art in q:
            spec["articulation"] = art
            changed = True
    return changed


def handle(question: str, session, ami_ctx: dict | None = None) -> CoachResponse | None:
    if session is None:
        return None
    q = question.lower().strip(" .!?")
    # M1d owns explicit scale patterns, modes, bar counts and their revisions.
    if re.search(r"\bscale[ -]patterns?\b", q):
        return None
    from music_coach_ami import trumpet_technique
    trumpet_response = trumpet_technique.handle(question, session, ami_ctx)
    if trumpet_response is not None:
        return trumpet_response
    from music_coach_ami import instrument_technique
    technique_response = instrument_technique.handle(question, session, ami_ctx)
    if technique_response is not None:
        return technique_response
    ctx = ami_ctx or {}
    plan = wp.current(session)
    active = bool(plan and plan["spec"].get("single"))
    fresh = bool(re.search(r"\b(?:give|generate|write|create|build|want|need)\b", q))
    full = bool(re.search(r"warm[ -]?up|routine", q))
    song = bool(re.search(r"\b(?:over|song|verse|bridge|chorus|chord changes|prepares? me for)\b", q))
    vocabulary = bool(re.search(r"\b(?:scale|long[ -]?tones?|arpeggio|finger[ -]?buster|finger technique|high[ -]note|low[ -]register|high[ -]register|middle[ -]register)\b", q))
    explicit = wp.parse_request(question)
    if explicit.get("instrument_word") and re.search(r"\bexercises?\b", q):
        vocabulary = True
    if fresh and not full and explicit.get("unverified") and re.search(r"exercise|warm[ -]?up|pattern|scale|tones?|arpeggio", q):
        return _reply(f"I don't have a verified range and written/sounding pitch profile for {explicit['unverified']} yet. No exercise was changed.", failed="instrument")
    specialized = bool(re.search(r"register[ -]break|lip[ -]slur|open valves?|partials?|harmonic flexibility|clarinet.*(?:octave|finger)|octave.*clarinet", q))
    if specialized and (fresh or "help me" in q):
        return _reply("This request needs a verified instrument-specific technique pattern. I can't generate that drill yet; no exercise was changed.", failed="unsupported_technique")
    if fresh and full:
        if re.search(r"\b(?:high|low|middle|upper)[ -]register\b", q):
            return _reply("Register selection currently applies to single exercises. Ask for a high-, middle- or low-register exercise, or a general warmup.", failed="parameters")
        return None
    if fresh and vocabulary and song:
        return None  # Existing authoritative song engine owns these requests.
    if fresh and vocabulary:
        req = wp.parse_request(question.replace("-flat", "b").replace("-sharp", "#"))
        page, _ = wp._page_values(question, session, ami_ctx)
        normalized = question.replace("-flat", "b").replace("-sharp", "#").replace("\u266d", "b").replace("\u266f", "#")
        named_key = re.search(r"\b([A-G](?:b|#)?)\s*(major|minor|maj7|m7|dominant|7)\b", normalized)
        key = req["key"] or ((named_key[1] + ("m" if named_key[2] == "minor" else "")) if named_key else "") or getattr(page, "current_practice_key", "") or ctx.get("display_key") or "C"
        if req.get("instrument_word") == "saxophone" and not req.get("sax_type_word"):
            from instrument_transposition import SELECTED_TRANSPOSING_INSTRUMENT_KEY
            if "sax" not in str(session.get("instrument", "")).lower() or not session.get(SELECTED_TRANSPOSING_INSTRUMENT_KEY):
                return _reply("Which saxophone: soprano, alto, tenor or baritone?", failed="instrument")
        player, why, facts = wp.resolve_player(req, session, page, key)
        if player is None or facts.get("sax_assumed"):
            return _reply(why or "Which saxophone: soprano, alto, tenor or baritone?", failed="instrument")
        if re.search(r"\b(?:minutes?|duration|dynamics?|slur|swing|triplet)\b", q):
            return _reply("This standalone slice supports note values, tempo and repetition count, but not that duration, dynamics or slur instruction yet. No exercise was changed.", failed="parameters")
        family = "long_tones" if re.search(r"long[ -]?tones?", q) else "arpeggio" if "arpeggio" in q or re.search(r"maj7|dominant|major seventh", q) else "scale" if re.search(r"\bscale|finger technique|finger[ -]?buster", q) else "register"
        if re.search(r"harmonic minor|melodic minor|dorian|pentatonic|chromatic|enclosure", q):
            return _reply("That pitch vocabulary isn't supported by this standalone drill yet. Ask for a major or natural-minor scale, or a major/minor arpeggio.", failed="vocabulary")
        unsupported = we.supports(player, family)
        if unsupported:
            return _reply(f"I can't build that exercise: {unsupported}.", failed="family")
        buster = bool(re.search(r"finger[ -]?buster", q))
        quality = "maj7" if re.search(r"maj7|major\s+(?:seventh|7)", q) else "7" if re.search(r"dominant|(?<![a-z])7\b", q) else "m7" if re.search(r"minor seventh|m7", question) else "minor" if "minor" in q else "major"
        # A chord name's quality must not turn the Practice Key into a minor chord.
        spec = {"single": True, "instrument": player.key, "concert_key": key, "family": family, "quality": quality,
                "level": req["level"] or str(getattr(page, "level", "") or ctx.get("level") or "Intermediate").capitalize(),
                "register": "high" if re.search(r"\b(?:high|upper)[ -]", q) else "low" if re.search(r"\blow(?:[ -]|$)", q) else "middle",
                "direction": "descending" if "descending" in q else "ascending", "buster": buster,
                "count": 3, "reps": 1, "bpm": 50 if "slow" in q or family == "long_tones" else 72, "articulation": "", "rhythm": ""}
        count = re.search(r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s+(?:(?:low|middle|high)[ -]register\s+)?long[ -]?tones?", q)
        if count:
            spec["count"] = int(count[1]) if count[1].isdigit() else wp._NUMBER_WORDS[count[1]]
        if not 1 <= spec["count"] <= 12:
            return _reply("Ask for between one and twelve long tones.", failed="count")
        controls(spec, q)
        try:
            new = build(spec)
        except (we.WarmupUnavailable, ValueError) as exc:
            return _reply(f"I couldn't build this exercise accurately: {exc}.", failed="unavailable")
        wp._push(session, new, question, fresh=True)
        return _response(new, session)
    if not active:
        return None
    if q in ("undo", "undo that", "redo", "redo that"):
        st = wp._state(session)
        delta = -1 if q.startswith("undo") else 1
        target = st["cursor"] + delta
        if 0 <= target < len(st["versions"]):
            st["cursor"] = target
            return _response(wp.current(session), session, "Restored the exact stored version. ")
        return _reply("There is no version to restore.", plan, session)
    if re.match(r"explain|why", q):
        r = plan["items"][0]
        return _reply(f"These are the written notes: {', '.join(r['written_notes'])}. "
                      f"They use the requested {plan['spec']['family']} vocabulary. Sounding pitches are the written MIDI pitches "
                      f"minus {plan['player']['offset']} semitones, including the octave.", plan, session)
    if not re.match(r"(?:now |please )?(?:make|change|keep|use|add|start|slower|faster)", q):
        return None
    spec = copy.deepcopy(plan["spec"])
    if "descending" in q or "ascending" in q:
        spec["direction"] = "descending" if "descending" in q else "ascending"
    elif "slower" in q or "faster" in q:
        spec["bpm"] = max(36, min(160, spec["bpm"] + (-10 if "slower" in q else 10)))
    elif re.search(r"higher|lower|middle|high|low", q):
        spec["register"] = "high" if re.search(r"higher|high", q) else "low" if re.search(r"lower|low", q) else "middle"
    elif re.search(r"\b(?:bpm|tempo|repetitions?|times|quarter|eighth|sixteenth|half|staccato|tenuto|accent)\b", q):
        if not controls(spec, q):
            return _reply("Please specify a tempo in BPM, repetitions, note value or articulation.", plan, session, "revision")
    elif "rhythm" in q and ("harder" in q or "difficult" in q):
        spec["rhythm"] = "sixteenth"
    elif "difficult" in q or "harder" in q:
        spec["level"] = wp.LEVEL_UP.get(spec["level"], spec["level"])
        spec["buster"] = spec["level"] == "Advanced"
    elif re.search(r"tenor|alto|baritone|soprano|flute|trumpet|clarinet|bass|guitar", q):
        req = wp.parse_request(question)
        page, _ = wp._page_values(question, session, ami_ctx)
        player, why, facts = wp.resolve_player(req, session, page, spec["concert_key"])
        if player is None or facts.get("sax_assumed"):
            return _reply(why or "Which saxophone type?", plan, session, "instrument")
        spec["instrument"] = player.key
    else:
        req = wp.parse_request(question)
        if req["key"]:
            spec["concert_key"] = req["key"]
        else:
            return _reply("I can't make that revision accurately yet. The exercise is unchanged.", plan, session, "revision")
    controls(spec, q)
    if spec == plan["spec"]:
        return _reply("The exercise already has those settings; no new version was needed.", plan, session)
    try:
        new = build(spec)
    except (we.WarmupUnavailable, ValueError) as exc:
        return _reply(f"That change doesn't fit this instrument and level: {exc}. The exercise is unchanged.", plan, session, "revision")
    wp._commit(session, new, question)
    return _response(new, session)
