"""Bounded flute/standard Bb-clarinet technique; written-pitch recipes, shared profiles/history.

Technical facts and deliberately unsupported capabilities are documented in
``docs/ami-flute-clarinet-20261112.md``. No fingering diagrams or alternates are generated.
"""
from __future__ import annotations
import copy
import re
from music_coach_ami import warmup_engine as we, warmup_plan as wp, scale_pattern_harmony as sph

TITLES = {"octaves": "Octave jumps", "twelfths": "Clarinet perfect twelfths",
          "flute_coordination": "Flute octave and finger coordination",
          "clarinet_break": "Clarinet register-break crossing",
          "clarinet_coordination": "Clarinet throat-to-clarion coordination"}
PURPOSE = {
    "octaves": "Develop accurate octave placement and an even tone through a 12-semitone jump. An ordinary octave is not the clarinet's register-key twelfth.",
    "twelfths": "Connect written notes a perfect twelfth (19 semitones) apart, the clarinet's lower-to-clarion register relationship. This is not an octave exercise.",
    "flute_coordination": "Coordinate neighboring finger changes with alternating lower/upper octave notes on flute. Keep the tone even through the register changes; do not force the upper notes.",
    "clarinet_break": "Coordinate the throat-to-clarion transition at written Bb4-B4. This break is a semitone boundary, distinct from an octave jump or a register-key twelfth.",
    "clarinet_coordination": "Coordinate changing note groups around the clarinet's written Bb4-B4 throat-to-clarion boundary, with neighboring notes on both sides. Keep air steady through the crossings.",
}
_NAMES = ("C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B")


def _name(midi):
    return _NAMES[midi % 12], midi // 12 - 1


def _pitched(spec):
    kind, level = spec["technique"], spec["level"]
    cells = spec["count"]
    if kind in ("octaves", "twelfths"):
        low = spec["base_midi"] + spec["shift"]
        name = spec["base_name"]
        upper = low + spec["span"]
        upper_letter = ("CDEFGAB".index(name[0]) + (4 if spec["span"] == 19 else 0)) % 7
        upper_name = sph._spell(upper_letter, upper % 12)
        pairs = [(low, name), (upper, upper_name)]
        result = pairs * cells
    elif kind in ("clarinet_break", "clarinet_coordination"):
        # Keep the actual break fixed. Higher/lower moves its neighboring notes, not the boundary itself.
        pos, width = spec["placement"], spec["width"]
        if kind == "clarinet_break" or level == "Beginner":
            cell = [69, 70, 71, 72]
            if pos > 0: cell = [70, 71, 72, 74]
            elif pos < 0: cell = [67, 69, 70, 71]
            if width > 1: cell = [67 if pos <= 0 else 69, 70, 71, 74 if pos >= 0 else 72]
            values = cell * cells
        else:
            pool = [[69,70,71,72], [69,71,70,71], [67,70,71,74], [72,71,70,69]]
            if width > 1: pool = [[67,70,71,76], [69,72,70,71], [65,70,71,74], [74,71,70,67]]
            values = [m for i in range(cells) for m in pool[(i + pos) % len(pool)]]
        result = [(m, _name(m)[0]) for m in values]
    else:
        # Original short coordination cells, not a renamed ascending scale.
        bases = [67,69,71,72] if level == "Beginner" else [67,69,71,72] if level == "Intermediate" else [62,64,65,67]
        values = []
        for i in range(cells):
            base = bases[i % len(bases)] + spec["shift"]
            if level == "Beginner": values += [base, base+1, base, base+2+spec["width"]-1]
            else: values += [base, base+12+2*(spec["width"]-1), base+1, base+13+2*(spec["width"]-1)]
        result = [(m, _name(m)[0]) for m in values]
    if spec["direction"] == "descending": result.reverse()
    return result


def build(spec):
    from music_coach_ami.flexible_single import package
    if spec["level"] not in we.LEVELS or not 1 <= spec["count"] <= 8:
        raise we.WarmupUnavailable("choose a supported level and one to eight short cells")
    player = we.make_player(spec["instrument"], spec["concert_key"])
    kind = spec["technique"]
    required = "clarinet" if kind.startswith("clarinet") or kind == "twelfths" else None
    if player.key not in ("flute", "clarinet") or (required and player.key != required) or (kind.startswith("flute") and player.key != "flute"):
        raise we.WarmupUnavailable("this technique does not match the requested instrument")
    if kind=="octaves" and spec["span"] not in (12,24):
        raise we.WarmupUnavailable("an octave recipe must span 12 or 24 semitones")
    if kind=="twelfths" and spec["span"]!=19:
        raise we.WarmupUnavailable("a perfect twelfth must span 19 semitones")
    pairs = _pitched(spec)
    lo, hi = player.window(spec["level"])
    if not all(lo <= m <= hi and player.play_low <= m <= player.play_high for m, _ in pairs):
        raise we.WarmupUnavailable(f"the specified written pitches do not fit {spec['level']} {player.label} ({lo}-{hi} MIDI); choose another starting octave or level")
    lv = we.LEVELS.index(spec["level"])
    unit = spec.get("rhythm") or (("quarter","eighth","sixteenth")[lv] if "coordination" in kind else ("half","quarter","eighth")[lv])
    notes = [we.Note(name, (m-sph.pc_of(name))//12-1, unit, spec["articulation"]) for m,name in pairs]
    notes = we._fill_bar(notes) + [we.Note("",0,"whole")]
    title = TITLES[kind]
    if kind == "octaves" and spec["span"] == 24: title = "Two-octave jumps"
    if kind in ("octaves","twelfths"):
        title += f" - written {pairs[0][1]}{pairs[0][0]//12-1} to {pairs[1][1]}{pairs[1][0]//12-1}"
    purpose = PURPOSE[kind]
    if kind == "octaves" and spec["span"] == 24: purpose = "Develop placement across two octaves (24 semitones), with an even tone and a full breath rest."
    how = [purpose, f"Play {len(pairs)} written notes, then take the notated full-bar breath rest. Use your usual standard fingerings; no alternate fingering is prescribed.",
           "Start slowly. Keep attacks even and stop to rest if coordination or tone deteriorates."]
    built = we.Built(notes,spec["bpm"],title,how,[],{"window":[lo,hi]})
    tonic,mode = we.practical_key(*we.split_key(player.written_key))
    return package(spec,player,built,tonic,mode,allowed_pcs={m%12 for m,_ in pairs})


def response(plan, session, lead=""):
    from music_coach_ami.flexible_single import _reply
    spec,row,p = plan["spec"],plan["items"][0],plan["player"]
    return _reply(f"{lead}**{row['title']}** - {p['label']}, {spec['level']}. "
                  f"Pitch names in this technique are written pitches; sounding pitches are written minus {p['offset']} semitones. "
                  f"Tempo {row['bpm']} BPM; play {row['reps']} time(s). Articulation: {spec['articulation'] or 'ordinary tongued attacks'}.",plan,session)


def _start(question, kind, player, page, req):
    level = req["level"] or str(getattr(page,"level","") or "Intermediate").capitalize()
    match = re.search(r"\bfrom\s+(?:low\s+)?([A-G](?:#|b)?)([3-7])?(?:\s+to\s+(?:high\s+)?([A-G](?:#|b)?)([3-7])?)?\b",question,re.I)
    if match:
        parts=list(match.groups())
        parts[0]=parts[0][0].upper()+parts[0][1:].lower()
        if parts[2]:parts[2]=parts[2][0].upper()+parts[2][1:].lower()
        if re.match(r"\s+to\b",question[match.end():],re.I):
            raise we.WarmupUnavailable("specify a valid written endpoint note")
    if kind in ("octaves","twelfths") and re.search(r"\bfrom\b",question,re.I) and not match:
        raise we.WarmupUnavailable("specify valid written endpoint notes, for example from F4 to F5")
    name,octave = (parts[0],int(parts[1] or 4)) if match else ("D" if player.key=="flute" else "F",4)
    if kind == "twelfths" and not match: name,octave="G",3
    if kind=="octaves" and not match and player.key=="clarinet" and level=="Beginner": name,octave="G",3
    span = 19 if kind=="twelfths" else 12
    if match and parts[2]:
        upper_letter=("CDEFGAB".index(name[0])+(4 if span==19 else 0))%7
        expected_name=sph._spell(upper_letter,(sph.pc_of(name)+span)%12)
        if parts[2]!=expected_name: raise we.WarmupUnavailable("those endpoint note names do not match the requested interval")
        if parts[3] and sph.midi_of(parts[2],int(parts[3]))-sph.midi_of(name,octave)!=span:
            raise we.WarmupUnavailable("those endpoints are not the requested interval")
    from practice_focus_policy import category_for_focus
    focus=category_for_focus(str(getattr(page,"practice_focus","") or ""))
    return {"single":True,"technique":kind,"family":"technique","instrument":player.key,"concert_key":player.concert_key,
            "quality":"major","level":level,"register":"specified written pitches","direction":"descending" if re.search(r"descend",question,re.I) else "ascending","buster":False,
            "base_name":name,"base_midi":sph.midi_of(name,octave),"span":span,"shift":0,"placement":0,"width":1,
            "count":4,"reps":1,"bpm":48 if level=="Beginner" else 56 if level=="Intermediate" else 64,
            "rhythm":"half" if focus=="tone" and kind in ("octaves","twelfths") else "",
            "articulation":"staccato" if focus=="articulation" else "","focus":focus}


def handle(question, session, ami_ctx=None):
    from music_coach_ami import flexible_single as fs
    q=question.lower().strip(" .!?")
    plan=wp.current(session)
    active=bool(plan and plan["spec"].get("technique"))
    fresh=bool(re.search(r"\b(?:give|generate|write|create|build|want|need)\b|^help me",q))
    kind="clarinet_break" if re.search(r"register[ -]break|crossing (?:the )?break",q) else "twelfths" if "twelfth" in q else "octaves" if re.search(r"octave (?:jumps?|exercise)|octave exercises",q) else "coordination" if "fingering exercise" in q else ""
    if fresh and kind and re.search(r"\b(?:over|song|chords?|changes|chorus|bridge|bars?|scale[ -]patterns?)\b",q):
        return None  # Existing song/span/scale-pattern owners keep authority.
    if fresh and kind:
        req=wp.parse_request(question);page,_=wp._page_values(question,session,ami_ctx)
        player,why,facts=wp.resolve_player(req,session,page,getattr(page,"current_practice_key","") or "C")
        if player is None or facts.get("sax_assumed"):
            return fs._reply(why or "Choose a specific verified instrument.",plan,session,"instrument")
        if player.key not in ("flute","clarinet") or (kind in ("clarinet_break","twelfths") and player.key!="clarinet"):
            return fs._reply("This bounded technique supports flute octaves/coordination and Bb clarinet octaves/break/twelfths. Choose a matching instrument; no exercise changed.",plan,session,"unsupported_technique")
        if kind=="coordination":kind=player.key+"_coordination"
        if re.search(r"alternate|finger positions?|finger numbers?|slurs?|partials?|swing|triplets?|dynamics?|minutes?|harmonic minor|pentatonic|dorian",q):
            return fs._reply("That technical instruction is not verified in this slice; no exercise changed.",plan,session,"unsupported_technique")
        try:
            spec=_start(question,kind,player,page,req);fs.controls(spec,q)
            new=build(spec)
        except (we.WarmupUnavailable,ValueError) as exc:
            return fs._reply(f"I couldn't build that technique accurately: {exc}. The stored exercise is unchanged.",plan,session,"technique")
        wp._push(session,new,question,fresh=True)
        return response(new,session)
    if not active:return None
    if re.match(r"explain|why",q):
        r=plan["items"][0]
        return response(plan,session,f"{r['how'][0]} Written notes: {', '.join(r['written_notes'])}. No notes or history were changed. ")
    if re.fullmatch(r"(?:undo|redo)(?: that)?",q):return None  # shared exact snapshot restoration
    if not re.match(r"(?:now |please )?(?:make|change|keep|use|add|start|descend|ascend|slower|faster|give me fewer)",q):return None
    spec=copy.deepcopy(plan["spec"]);kind=spec["technique"]
    if re.search(r"\b(?:alternate|fingerings?|finger positions?|slurs?|dynamics?|swing|triplets?|transpose|concert key)\b",q):
        return fs._reply("That revision needs an additional verified technique rule; the stored exercise is unchanged.",plan,session,"revision")
    # Preserve technique identity and reject incompatible instrument changes explicitly.
    req=wp.parse_request(question)
    if req.get("instrument_word") or req.get("unverified"):
        return fs._reply("Start a new technique request to change instruments; this stored technique is unchanged.",plan,session,"instrument")
    if re.search(r"descend|descending",q):spec["direction"]="descending"
    elif re.search(r"ascend|ascending",q):spec["direction"]="ascending"
    if "slower" in q:spec["bpm"]=max(36,spec["bpm"]-8)
    if "faster" in q:spec["bpm"]=min(120,spec["bpm"]+8)
    if re.search(r"\b(?:higher|lower)\b",q):
        direction=1 if "higher" in q else -1
        if kind.startswith("clarinet_"):spec["placement"]=max(-1,min(1,spec["placement"]+direction))
        else:spec["shift"]+=12*direction
    if re.search(r"wider|wide intervals",q):
        if kind=="octaves":
            spec["span"]=19 if spec["instrument"]=="clarinet" else 24
            if spec["span"]==19:spec["technique"]="twelfths"
        elif kind=="twelfths":
            return fs._reply("This verified clarinet register relationship is a perfect twelfth; I cannot widen it further while preserving that technique. No exercise changed.",plan,session,"revision")
        else:spec["width"]=2
    if "fewer" in q:spec["count"]=max(1,spec["count"]-1)
    if "harder" in q:
        spec["level"]=wp.LEVEL_UP.get(spec["level"],spec["level"])
        spec["bpm"]=min(120,spec["bpm"]+8)
    if "easier" in q:spec["level"]=wp.LEVEL_DOWN.get(spec["level"],spec["level"])
    if "articulation" in q and not re.search(r"staccato|tenuto|accent",q):
        spec["articulation"]="tenuto" if spec["articulation"]=="staccato" else "staccato"
    fs.controls(spec,q)
    if spec==plan["spec"]:
        return fs._reply("No supported setting changed; the stored exercise and history are unchanged.",plan,session,"revision")
    try:new=build(spec)
    except (we.WarmupUnavailable,ValueError) as exc:
        return fs._reply(f"That revision does not fit this technique and level: {exc}. The exercise is unchanged.",plan,session,"revision")
    wp._commit(session,new,question)
    return response(new,session)
