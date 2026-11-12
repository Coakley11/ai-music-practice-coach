"""Short standard Bb trumpet partial drills; audited fixed valve settings only.

Yamaha mechanism_f02_02_00/01/02: tempered written targets for partials
2,3,4,5,6,8. Pedals and the poorly tuned seventh partial are deliberately excluded.
No embouchure, alternate-fingering or exact acoustic-intonation model is claimed.
"""
from __future__ import annotations
import copy
import re
from music_coach_ami import warmup_engine as we, warmup_plan as wp

# Explicit audited targets, not an arbitrary transposed scale. Valves remain fixed for each drill.
HARMONICS = {
    "open": {2:("C",4),3:("G",4),4:("C",5),5:("E",5),6:("G",5),8:("C",6)},
    "1": {2:("Bb",3),3:("F",4),4:("Bb",4),5:("D",5),6:("F",5),8:("Bb",5)},
    "2": {2:("B",3),3:("F#",4),4:("B",4),5:("D#",5),6:("F#",5),8:("B",5)},
}
SETTINGS=("open","2","1")


def available(valve, level):
    if valve not in HARMONICS or level not in we.LEVELS:
        raise we.WarmupUnavailable("choose open valves, valve 1 or valve 2 and a supported level")
    p=we.make_player("trumpet","C");lo,hi=p.window(level)
    return [n for n,(name,octave) in HARMONICS[valve].items()
            if lo<=we.sph.midi_of(name,octave)<=hi and (level!="Beginner" or n<=4)]


def _selection(spec):
    pool=available(spec["valve"],spec["level"])
    start,count=spec["start"],spec["partial_count"]
    if start<0 or count<2 or start+count>len(pool):
        raise we.WarmupUnavailable("that many verified partials do not fit this placement and proficiency; no pedal or seventh partial will be substituted")
    return pool[start:start+count]


def build(spec):
    from music_coach_ami.flexible_single import package
    if spec["instrument"]!="trumpet":raise we.WarmupUnavailable("this drill requires standard Bb trumpet")
    if not 1<=spec["cells"]<=4 or spec["style"] not in ("slur","pairs","tongued"):
        raise we.WarmupUnavailable("invalid cell count or articulation style")
    selected=_selection(spec)
    player=we.make_player("trumpet",spec["concert_key"])
    if player.offset!=2:raise we.WarmupUnavailable("Bb trumpet must sound two semitones below written pitch")
    if spec["routine"]:
        pool=available(spec["valve"],spec["level"])
        stages=[pool[:2],pool[1:3],selected]
    else:stages=[selected]
    lv=we.LEVELS.index(spec["level"])
    unit=spec.get("rhythm") or (("half","quarter","eighth")[lv])
    if spec["buster"] and not spec.get("rhythm"):unit="sixteenth"
    notes=[];partials=[];groups=[];gid=0;stage_info=[]
    for stage in stages:
        if spec["buster"] and len(stage)>=4:
            order=[0,2,1,3,2,min(4,len(stage)-1),3,len(stage)-1,min(4,len(stage)-1),2,3,1,2,0]
            sequence=[stage[i] for i in order]
        elif len(stage)==2:sequence=stage[:]
        else:sequence=stage[:]
        if spec["direction"]=="descending":sequence.reverse()
        stage_info.append({"partials":stage,"sequence":sequence})
        for _ in range(spec["cells"]):
            gid+=1
            for i,n in enumerate(sequence):
                name,octave=HARMONICS[spec["valve"]][n]
                group=0 if spec["style"]=="tongued" else gid if spec["style"]=="slur" else gid+i//2
                # Pair groups must be unique, including across cells.
                if spec["style"]=="pairs":group=gid*100+i//2
                art=spec["articulation"] if spec["style"]=="tongued" else ""
                notes.append(we.Note(name,octave,unit,art,group));partials.append(n);groups.append(group)
            notes=we._fill_bar(notes)
            notes.append(we.Note("",0,"whole"))
    title=("Trumpet upper-register preparation warmup" if spec["routine"] else
           "Trumpet fixed-valve tongued partial drill" if spec["style"]=="tongued" else
           "Advanced trumpet lip-slur finger-buster" if spec["buster"] else "Trumpet lip-slur partial exercise")
    how=[f"Keep {'all valves released' if spec['valve']=='open' else 'valve '+spec['valve']+' pressed and the others released'} throughout each phrase; the pitch changes follow its verified harmonic partials.",
         "Slur the marked group without a fresh tongue attack between notes." if spec["style"]!="tongued" else "Tongue each note; this variation is a fixed-valve partial drill rather than a lip slur.",
         "Use a comfortable, even sound. Take every notated breath rest; stop and rest if tone deteriorates or effort increases. Do not force upper notes.",
         "These are charted pitch targets; use your ear/tuner for intonation. This does not prescribe embouchure changes or claim perfectly tuned acoustic partials."]
    if spec["routine"]:
        how.insert(0,"Three short stages: low-partial pair, middle-partial pair, then level-appropriate upper preparation, separated by breath rests.")
    built=we.Built(notes,spec["bpm"],title,how,[],{"window":list(player.window(spec["level"]))})
    tonic,mode=we.practical_key(*we.split_key(player.written_key))
    plan=package(spec,player,built,tonic,mode,allowed_pcs={n.midi%12 for n in notes if not n.rest})
    row=plan["items"][0];row.update(valve=spec["valve"],partial_numbers=partials,slur_groups=groups,stages=stage_info)
    if any((name,octave) not in HARMONICS[spec["valve"]].values() for name,octave in [(n.spelled,n.octave) for n in notes if not n.rest]):
        raise we.WarmupUnavailable("a note is not in this fixed valve's verified series")
    return plan


def response(plan,session,lead=""):
    from music_coach_ami.flexible_single import _reply
    s,r=plan["spec"],plan["items"][0]
    setting="open (no valves pressed)" if s["valve"]=="open" else f"valve {s['valve']} pressed, others released"
    return _reply(f"{lead}**{r['title']}** - standard Bb trumpet, {s['level']}; {setting}. "
                  f"Written pitches: {', '.join(r['written_notes'])}. Sounding pitch is written minus 2 semitones. "
                  f"Tempo {r['bpm']} BPM; {len(r['stages'])} stage(s), play {r['reps']} time(s); {plan['total_seconds']:.0f} seconds including notated rests. "
                  f"Style: {s['style']}. Partials: {', '.join(map(str,sorted(set(r['partial_numbers']))))}.",plan,session)


def _valve(q):
    combo=re.search(r"valves?\s+([123](?:\s*(?:\+|and|,|-)\s*[123])*)",q)
    if combo:return re.sub(r"\s*(?:and|,|-)\s*","+",combo[1]).replace(" ","")
    if "first valve" in q:return "1"
    if "second valve" in q:return "2"
    if "third valve" in q:return "3"
    if re.search(r"open|no valves|without (?:changing|using) valves",q):return "open"
    return ""


def handle(question,session,ami_ctx=None):
    from music_coach_ami import flexible_single as fs
    q=question.lower().strip(" .!?");plan=wp.current(session)
    active=bool(plan and plan["spec"].get("trumpet"))
    fresh=bool(re.search(r"\b(?:give|generate|create|build|want|need|help)\b",q))
    intent=bool(re.search(r"lip[ -]?slurs?|harmonic partials?|flexibility|open[ -]valves?|without changing valves|without a valve change|upper[ -]register|high[ -]register",q))
    if fresh and intent and not re.search(r"\b(?:over|song|chords?|chorus|bridge|scale[ -]patterns?)\b",q):
        req=wp.parse_request(question);page,_=wp._page_values(question,session,ami_ctx)
        player,why,_=wp.resolve_player(req,session,page,getattr(page,"current_practice_key","") or "C")
        # Register-only requests for other instruments retain their existing engine.
        if player and player.key!="trumpet" and not re.search(r"lip[ -]?slur|harmonic partial|open[ -]valves?|without changing valves",q):return None
        if player is None or player.key!="trumpet":
            return fs._reply(why or "This fixed-valve technique requires Bb trumpet; name it explicitly or select trumpet. No exercise changed.",plan,session,"instrument")
        if re.search(r"\b(?:c|d|eb|e-flat|piccolo|bass) trumpet\b|trumpet in (?!b[ -]?flat\b|bb\b)",q):
            return fs._reply("Only standard Bb trumpet is verified for this technique. No exercise changed.",plan,session,"instrument")
        valve=_valve(q) or "open"
        if valve not in HARMONICS or req.get("minutes") or re.search(r"pedal|seventh partial|partial 7|embouchure|triplet|swing",q):
            return fs._reply("This slice verifies open, valve 1 and valve 2, partials 2-6 and 8 within your level. Timed routines, pedals, partial 7 and that extra instruction are unsupported. No exercise changed.",plan,session,"parameters")
        level=req["level"] or str(getattr(page,"level","") or "Intermediate").capitalize()
        buster=bool(re.search(r"finger[ -]?buster",q))
        if buster and level!="Advanced":return fs._reply("This partial finger-buster requires an explicit Advanced level. No exercise changed.",plan,session,"level")
        pool=available(valve,level);count=min(len(pool),6 if buster else 2 if level=="Beginner" else 3)
        start=0 if level=="Beginner" or "low" in q or buster else 1
        if "middle" in q:start=min(1,len(pool)-count)
        if re.search(r"upper|high",q):start=max(0,len(pool)-count)
        start=min(start,len(pool)-count)
        from practice_focus_policy import category_for_focus
        focus=category_for_focus(str(getattr(page,"practice_focus","") or ""))
        spec={"single":True,"trumpet":True,"technique":"trumpet_partials","family":"technique","instrument":"trumpet","concert_key":player.concert_key,
              "level":level,"valve":valve,"partial_count":count,"start":start,"cells":1 if buster else 2,"buster":buster,
              "routine":bool(re.search(r"warm[ -]?up|routine",q)),"direction":"descending" if "descend" in q else "ascending",
              "style":"slur","articulation":"","rhythm":"half" if focus=="tone" and not buster else "","focus":focus,"bpm":48 if level=="Beginner" else 56,"reps":1,"register":"level-bounded partials"}
        fs.controls(spec,q)
        if re.search(r"tongu|staccato|tenuto|accent",q):spec["style"]="tongued"
        if re.search(r"slur (?:each )?pair|slur two",q):spec["style"]="pairs"
        try:new=build(spec)
        except (we.WarmupUnavailable,ValueError) as exc:return fs._reply(f"That partial exercise cannot be built correctly: {exc}. No exercise changed.",plan,session,"technique")
        wp._push(session,new,question,fresh=True);return response(new,session)
    if not active:return None
    if re.match(r"explain|why",q):
        s=plan["spec"]
        style_explanation="The current variation is tongued, so it has no lip-slur markings. " if s["style"]=="tongued" else "The marked slur groups join notes without re-tonguing. "
        return response(plan,session,style_explanation+"This trains controlled movement between resonant harmonic partials at one fixed tube length, not scale steps produced by changing valves. The selected level limits the range; notated rests limit continuous playing. No notes or history changed. ")
    if re.fullmatch(r"(?:undo|redo)(?: that)?",q):return None
    if not re.match(r"(?:now |please )?(?:make|move|change|keep|use|add|remove|descend|ascend|slower|faster)",q):return None
    spec=copy.deepcopy(plan["spec"])
    if re.search(r"pedal|partial 7|seventh partial|embouchure|triplet|swing|minutes?|transpose|flute|clarinet|sax|piano",q):
        return fs._reply("That revision is outside the verified Bb-trumpet partial rules. The stored exercise is unchanged.",plan,session,"revision")
    valve=_valve(q)
    if "different valve" in q:valve=SETTINGS[(SETTINGS.index(spec["valve"])+1)%len(SETTINGS)]
    if valve:
        if valve not in HARMONICS:return fs._reply("Only open, valve 1 and valve 2 are verified here. No exercise changed.",plan,session,"revision")
        spec["valve"]=valve
    if "easier" in q:
        spec["level"]=wp.LEVEL_DOWN.get(spec["level"],spec["level"]);spec["partial_count"]=2;spec["start"]=0;spec["buster"]=False;spec["rhythm"]="half";spec["bpm"]=max(36,spec["bpm"]-8)
    if "harder" in q and "rhythm" not in q:
        spec["level"]=wp.LEVEL_UP.get(spec["level"],spec["level"]);spec["partial_count"]+=1;spec["rhythm"]="eighth";spec["bpm"]=min(96,spec["bpm"]+4)
    if re.search(r"\blower\b",q):spec["start"]=max(0,spec["start"]-1)
    if re.search(r"\bhigher\b",q):spec["start"]+=1
    if re.search(r"add (?:an?other|one|a) partial",q):spec["partial_count"]+=1
    if re.search(r"descend",q):spec["direction"]="descending"
    elif re.search(r"ascend",q):spec["direction"]="ascending"
    if "slower" in q:spec["bpm"]=max(36,spec["bpm"]-8)
    if "faster" in q:spec["bpm"]=min(120,spec["bpm"]+8)
    if "rhythm" in q and re.search(r"difficult|harder",q):spec["rhythm"]="sixteenth" if spec["level"]=="Advanced" else "eighth"
    if re.search(r"tongu|staccato|tenuto|accent",q):spec["style"]="tongued"
    elif re.search(r"slur each pair|slur two",q):spec["style"]="pairs"
    elif "slur" in q:spec["style"]="slur";spec["articulation"]=""
    if "articulation" in q and not re.search(r"tongu|staccato|tenuto|accent|slur",q):
        spec["style"]="tongued" if spec["style"]!="tongued" else "slur"
    fs.controls(spec,q)
    if spec==plan["spec"]:return fs._reply("The exercise is already at that supported setting; no new version was created.",plan,session)
    try:new=build(spec)
    except (we.WarmupUnavailable,ValueError) as exc:return fs._reply(f"That revision would violate the verified partial/range rules: {exc}. The stored exercise is unchanged.",plan,session,"revision")
    wp._commit(session,new,question);return response(new,session)
