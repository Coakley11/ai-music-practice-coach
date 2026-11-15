"""Read-only, owner-scoped note-name assistance from actual written events."""
from __future__ import annotations
import copy,re
from collections import defaultdict
from dataclasses import asdict

PREFIX = "_ami_conv_note_names_"

def rows_from_events(events, *, beat_origin=0):
    rows=[]
    chord=""
    for e in events:
        if e.chord: chord=e.chord
        rows.append({"bar":int(e.bar_index)+1,"beat":float(e.beat)+1-beat_origin,
                     "name":f"{e.spelled}{e.octave}" if e.spelled and not e.duration.startswith("rest") else "rest",
                     "duration":e.duration,"chord":chord,"voice":e.role})
    return rows

def rows_for(response, session):
    rows=response.diagnostics.get("note_name_rows")
    if rows is not None:return copy.deepcopy(rows)
    # Legacy structured revisions/Undo restore the exact written projection.
    exercise=response.diagnostics.get("generated_exercise")
    if not exercise:
        from music_coach_ami import conversation_state as cs
        version=cs.current_version(session)
        if version and version.get("abc")==response.notation_abc:exercise=version.get("exercise")
    if exercise:
        events=exercise.get("provenance",{}).get("written_events")
        if events:
            from types import SimpleNamespace
            return rows_from_events([SimpleNamespace(**{**e,"role":e.get("role", ""),"chord":e.get("chord", "")}) for e in events])
        from fractions import Fraction
        from music_coach_ami.exercise_model import GeneratedExercise
        from music_coach_ami.exercise_bridge import motif_view
        from music_coach_ami.scale_pattern_harmony import octave_for
        ex=GeneratedExercise.from_dict(exercise);view=motif_view(ex)
        num,den=map(int,ex.meter.split("/"));bar_beats=Fraction(num*4,den)
        result=[]
        for event in view["rhythm_events"]:
            onset=Fraction(str(event["on"]));index=event.get("n")
            name="rest" if index is None else view["notes"][index]+str(octave_for(view["notes"][index],view["midi"][index]))
            result.append({"bar":int(onset//bar_beats)+1,"beat":float(onset%bar_beats)+1,"name":name,
                           "duration":str(event["dur"]),"chord":view["chord"],"voice":""})
        return result
    from music_coach_ami import warmup_plan as wp
    plan=wp.current(session)
    if plan:
        view=response.diagnostics.get("warmup_view",{})
        items=plan["items"]
        if view.get("mode")=="item":items=items[int(view.get("index",0)):int(view.get("index",0))+1]
        scores=set(response.notation_abc_sections or [response.notation_abc])
        items=[item for item in items if item.get("abc") in scores]
        result=[]
        for i,item in enumerate(items):
            for row in item.get("note_name_rows",[]):result.append({**row,"exercise":item["title"]})
        if result:return result
    return []

def remember(response,session):
    if session is None or not response or not (response.notation_abc or response.notation_abc_sections):return
    rows=rows_for(response,session)
    response.diagnostics["note_name_rows"]=rows
    if rows:session[PREFIX+"snapshot"]=copy.deepcopy(asdict(response))
    elif session.get(PREFIX+"snapshot",{}).get("notation_abc") != response.notation_abc:
        session.pop(PREFIX+"snapshot",None)

def handle(question,session):
    q=re.sub(r"\s+"," ",question.lower()).strip(" .!?")
    show=bool(re.fullmatch(r"(?:please )?(?:show|list)(?: me)? (?:the )?(?:written )?note names",q))
    hide=bool(re.fullmatch(r"(?:please )?hide(?: me)? (?:the )?(?:written )?note names",q))
    measure=re.fullmatch(r"(?:what are|show(?: me)?) the notes in (?:measure|bar) (\d+)",q)
    explain=bool(re.fullmatch(r"explain (?:the )?notes in (?:this|the) exercise",q))
    if not (show or hide or measure or explain):return None
    from music_coach_ami.types import CoachResponse,CoachIntent
    snap=copy.deepcopy(session.get(PREFIX+"snapshot")) if session is not None else None
    if not snap:return CoachResponse(intent=CoachIntent.SCALE_PRACTICE,direct_answer="There is no verified stored note-name view. Generate an exercise first; no exercise changed.",source_solver="NoteNameDisplay")
    # Warmup navigation is read-only and bypasses submit; resolve its current view.
    from music_coach_ami import warmup_plan as wp
    plan=wp.current(session)
    if plan and snap.get("diagnostics",{}).get("warmup_plan_id")==plan["id"]:
        view=wp.history(session).get("view",{})
        items=plan["items"]
        if view.get("mode")=="item":items=items[int(view.get("index",0)):int(view.get("index",0))+1]
        snap["notation_abc_sections"]=[i["abc"] for i in items]
        snap["notation_abc"]=snap["notation_abc_sections"][0] if items else ""
        snap["diagnostics"]["note_name_rows"]=[{**row,"exercise":i["title"]} for i in items for row in i.get("note_name_rows",[])]
        snap["diagnostics"]["warmup_view"]=view
    r=CoachResponse(**snap)
    if show or hide:session[PREFIX+"preference"]=show
    elif measure or explain:session[PREFIX+"preference"]=True
    r.source_solver="NoteNameDisplay"
    r.direct_answer=("Note names are hidden." if hide else "Written note names for the stored exercise.")+" Notes, timing and exercise history are unchanged."
    r.diagnostics["note_names_readonly"]=True
    if measure:
        wanted=int(measure[1]);r.diagnostics["note_name_rows"]=[x for x in r.diagnostics["note_name_rows"] if x["bar"]==wanted]
        r.diagnostics["note_names_requested"]=True
        if not r.diagnostics["note_name_rows"]:r.direct_answer=f"Measure {wanted} is not available in this stored exercise. No exercise changed."
    if explain:r.diagnostics["note_names_requested"]=True
    return r

# Remove only redundant transcriptions; keep chord/scale rationale and technique.
_PITCHES=re.compile(r"^(?:[A-G](?:bb|##|[#b\u266d\u266f])?[0-8]?(?:[ ,;\u2013\u2014-]+|$))+$")
def clean_markdown(text):
    def inline(match):
        return "" if _PITCHES.fullmatch(match[1].strip()) else match[0]
    text=re.sub(r"\bWritten notes:\s*([^\n.]+)\.\s*",inline,text)
    out=[]
    for line in text.splitlines():
        bare=re.sub(r"^\s*[-*]\s+","",line).strip()
        m=re.match(r"^(?:Bar \d+(?: \([^)]*\))?|[RL]H):\s*(.+)$",bare)
        if m and _PITCHES.fullmatch(m[1].strip()):continue
        # Per-note jazz timeline is a transcription, not technique prose.
        if re.match(r"^Bar \d+, beat [\d.]+: concert .+ / written .+[;:] [A-G][#b]?[0-8], [\d.]+ beats;",bare):continue
        out.append(line)
    cleaned="\n".join(out)
    return re.sub(r"\*\*How to play it\*\*\s*(?=\*\*|$)","",cleaned)

def format_rows(rows):
    groups={}
    for row in rows:groups.setdefault((row.get("exercise",""),row["bar"]),[]).append(row)
    lines=[]
    for (title,bar),group in groups.items():
        chunks=[]
        for r in group:
            chord=f" ({r['chord']})" if r.get("chord") else ""
            voice=f" {r['voice']}" if r.get("voice") in {"rh","lh"} else ""
            duration=str(r["duration"])
            if re.fullmatch(r"[0-9./]+",duration):
                duration += " beats"
            else:
                duration=duration.removeprefix("rest_").replace("_"," ")+(" rest" if r["name"]=="rest" else " note")
            chunks.append(f"beat {r['beat']:g}{chord}{voice}: {r['name']} ({duration})")
        lines.append((f"**{title}** - " if title else "")+f"Bar {bar}: "+"; ".join(chunks))
    return lines

def show_by_default(session):
    pref=session.get(PREFIX+"preference")
    return pref if isinstance(pref,bool) else str(session.get("level","")).lower()=="beginner"


def render(st,data,text):
    from music_coach_ami.session_scope import ensure_owner
    ensure_owner(st.session_state)
    rows=data.get("note_name_rows")
    if rows is None:rows=(data.get("coach_submit_diagnostics") or {}).get("note_name_rows",[])
    if not rows and "note_name_rows" not in data:
        from music_coach_ami.types import CoachResponse, CoachIntent
        response=CoachResponse(intent=CoachIntent.SCALE_PRACTICE,notation_abc=data.get("notation_abc", ""),
                               notation_abc_sections=data.get("notation_abc_sections") or [],
                               diagnostics=data.get("coach_submit_diagnostics") or {})
        rows=rows_for(response,st.session_state)
    clean=clean_markdown(text)
    if not rows:return clean
    session=st.session_state
    pref=session.get(PREFIX+"preference")
    requested=bool((data.get("coach_submit_diagnostics") or {}).get("note_names_requested"))
    default=show_by_default(session)
    visible=bool(default)
    # A new key reflects a live level/default change; explicit choices persist in the owner-scoped preference.
    key=PREFIX+"toggle_"+str(visible)
    def changed():session[PREFIX+"preference"]=bool(session[key])
    if key in session and session[key] != visible:session[key]=visible
    show=st.checkbox("Show note names",value=visible,key=key,on_change=changed,width="stretch")
    if show:
        with st.expander("Written note names",expanded=True):
            for line in format_rows(rows):st.markdown(line)
    return clean
