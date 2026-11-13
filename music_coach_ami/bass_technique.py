"""Standard four-string fretted electric bass, AMI Slice 1.

Tuning E1 A1 D2 G2; conventional written pitch is sounding +12.
Policy limits are conservative exercise choices, not claims about every player's
hands or every bass. Frets 0-12 only. No six-string-guitar TAB assumptions.
Sources and scope: docs/AMI_BASS_GUITAR_SLICE1.md.
"""
from __future__ import annotations
import copy
import re
from music_coach_ami import warmup_engine as we, warmup_plan as wp

# Low to high; standard bass string numbering: E=4, A=3, D=2, G=1.
OPEN = ((4, "E", 28), (3, "A", 33), (2, "D", 38), (1, "G", 43))
# maximum fret, hand-window width in semitones, maximum shift per attack
POLICY = {"Beginner": (5, 2, 1), "Intermediate": (7, 3, 3), "Advanced": (12, 3, 5)}
UNSUPPORTED = re.compile(r"slap|popp?ing|tapp?ing|harmonics?|fretless|double bass|upright|(?:five|six|5|6)[ -]strings?|alternate tuning|drop[ -]?[a-g]|capo|thumb|triplets?|swing|pentatonic|blues|dorian|melodic minor|harmonic minor", re.I)


def positions(sounding, level):
    cap, _, _ = POLICY[level]
    return [(s, name, sounding-o) for s, name, o in OPEN if 0 <= sounding-o <= cap]


def assign(written, level, crossing=False):
    """Shortest feasible path through (string, fret, hand-window) states.

    Every fretted note must be covered by its hand window; open strings allow
    the current position to remain. Consecutive hand windows may move only by
    the level's declared shift limit. Nothing is omitted or octave-displaced.
    """
    if level not in POLICY or not written:
        raise we.WarmupUnavailable("bass requires a supported level and nonempty notes")
    cap, width, shift = POLICY[level]
    paths = {}
    for i, w in enumerate(written):
        opts = positions(w-12, level)
        fresh = {}
        for string, name, fret in opts:
            hands = range(max(1, fret-width), min(cap-width, fret)+1) if fret else range(1, cap-width+1)
            for hand in hands:
                item = {"string": string, "name": name, "fret": fret, "hand_low": hand, "hand_high": hand+width,
                        "written_midi": w, "sounding_midi": w-12}
                if not i:
                    fresh[(string, fret, hand, False)] = (hand*.1+fret*.02, [item])
                    continue
                for (ps, pf, ph, crossed), (cost, path) in paths.items():
                    if abs(hand-ph) > shift: continue
                    did = crossed or string != ps
                    key = (string, fret, hand, did)
                    score = cost+4*abs(hand-ph)+abs(string-ps)+.05*abs(fret-pf)
                    if key not in fresh or score < fresh[key][0]:fresh[key] = (score, path+[item])
        paths = fresh
        if not paths:raise we.WarmupUnavailable("no complete string/fret path fits this level's position and shift policy")
    candidates = [v for k,v in paths.items() if not crossing or k[3]]
    if not candidates:raise we.WarmupUnavailable("the passage cannot include a verified string crossing at this level")
    return min(candidates,key=lambda x:x[0])[1]


def certify(built, level, crossing=False):
    written = [n.midi for n in built.notes if not n.rest]
    lo, hi = we.make_player("bass", "C").window(level)
    if not all(lo <= w <= hi for w in written):raise we.WarmupUnavailable("bass notes exceed the strict level window")
    path = assign(written, level, crossing)
    built.meta.update(positions=path, window=[lo,hi], bass_policy=list(POLICY[level]), tuning="E1 A1 D2 G2")
    guide = "; ".join(f"{i+1}: {p['name']} string ({p['string']}), fret {p['fret']}" for i,p in enumerate(path))
    built.how = [h for h in built.how if not h.startswith(("Note-by-note string/fret path", "Frets 0-"))]
    built.how += ["Note-by-note string/fret path (pitched notes only): " + guide,
                  f"Frets 0-{POLICY[level][0]}; fretted notes lie inside a {POLICY[level][1]+1}-fret hand window; shifts up to {POLICY[level][2]} fret(s) per attack. Open strings may ring while repositioning. Slow down before shifting; stop if uncomfortable."]
    return path


def _material(spec, player, tonic, mode):
    lo, hi = player.window(spec["level"])
    names = we.scale_spelling(tonic, mode)
    family = spec["family"]
    if family == "arpeggio":
        suffix = {"major":"", "minor":"m", "maj7":"maj7", "m7":"m7", "7":"7"}[spec["quality"]]
        roles = we.sph.chord_tone_roles(tonic+suffix)
        names = [we.sph._spell(("CDEFGAB".index(tonic[0])+degree)%7, pc)
                 for role,degree in (("R",0),("3",2),("5",4),("7",6)) for pc,r in roles.items() if r==role]
    pool = sorted((m,n) for n in names for m in range(lo,hi+1) if m%12==we.sph.pc_of(n))
    if spec["register"] == "low":lo = max(lo, min(m for m,n in pool if n==tonic))
    roots = [i for i,(m,n) in enumerate(pool) if n==tonic and m+12<=hi]
    if not roots and (family == "coordination" or spec.get("segment")):roots=[0]
    if not roots:raise we.WarmupUnavailable("a complete bass octave does not fit this key and level")
    base = roots[-1] if spec["register"]=="high" else roots[0]
    chosen = pool[base:base+len(names)+1]
    if family in ("coordination", "buster"):
        # Physical four-string coordination cells, independent of the scale.
        # Natural/minor key requests instead use a scale-degree permutation.
        order = [0,2,1,3,1,3,0,2]
        chosen = [chosen[i%len(chosen)] for i in order]
        if family=="coordination":
            # Four-string, small-position cells: choose two actual frets on
            # EACH standard string from the requested key, then alternate.
            by_pc={we.sph.pc_of(n):n for n in names}
            cells=[]
            for string,label,opened in OPEN:
                options=[(opened+f+12,by_pc[(opened+f)%12]) for f in range(1,5) if (opened+f)%12 in by_pc]
                if len(options)<2:raise we.WarmupUnavailable("two keyed coordination frets do not fit each string")
                a,b=options[0],options[-1]
                cells += [a,b,a,b]
            chosen=cells
        if family=="buster":
            spread=pool[base:]
            chosen=[spread[i%len(spread)] for i in [0,7,2,5,1,6,3,4,7,0,5,2,6,1,4,3]]*2
    if family=="octaves" or spec.get("octaves"):
        lows=[(m,n) for m,n in chosen if m+12<=hi]
        if not lows:raise we.WarmupUnavailable("no complete octave pairs fit this level")
        chosen=[v for m,n in (lows[:4] if len(lows)>1 else lows*4) for v in [(m,n),(m+12,n)]]
    if family=="arpeggio" and spec["level"]=="Advanced" and not spec.get("octaves"):
        spread=pool[base:]
        chosen=[spread[i%len(spread)] for i in [0,3,1,4,2,5,3,0,4,1,5,2]]
    if spec.get("fifth"):
        fifth=(we.sph.pc_of(tonic)+7)%12
        i=next((i for i,(m,n) in enumerate(chosen) if m%12==fifth),None)
        if i is None:raise we.WarmupUnavailable("this pattern has no fifth to start on")
        chosen=chosen[i:]+chosen[:i]
    if spec.get("crossing") and family=="scale":
        chosen=[chosen[i] for i in range(len(chosen)) if i%2==0]+[chosen[i] for i in range(len(chosen)) if i%2]
    if spec["direction"]=="descending":chosen.reverse()
    elif spec["direction"]=="up and down":chosen+=chosen[-2::-1]
    return chosen,names


def built_for(spec):
    player=we.make_player("bass",spec["concert_key"])
    if player.offset!=12 or player.clef!="bass":raise we.WarmupUnavailable("bass pitch/clef profile mismatch")
    tonic,mode=we.practical_key(*we.split_key(player.written_key))
    if spec["bpm"]>{"Beginner":80,"Intermediate":112,"Advanced":144}[spec["level"]]:
        raise we.WarmupUnavailable("tempo exceeds this slice's level ceiling")
    if spec["level"]=="Beginner" and spec.get("rhythm") in ("eighth","sixteenth"):
        raise we.WarmupUnavailable("Beginner bass uses quarter notes or longer; raise proficiency before faster subdivisions")
    chosen,names=_material(spec,player,tonic,mode)
    unit=spec.get("rhythm") or {"Beginner":"quarter","Intermediate":"eighth","Advanced":"sixteenth"}[spec["level"]]
    title="Bass guitar "+spec["family"]+(" segment" if spec.get("segment") else "")+" - "+we.key_text(tonic,mode)
    notes=[we.Note(n,we.sph.octave_for(n,m),unit,spec.get("articulation", "")) for m,n in chosen]
    built=we.Built(we._fill_bar(notes),spec["bpm"],title,
                  ["Play one note at a time with an even pluck; release or mute the previous string before the next attack. Keep rests silent.",
                   "Read the bass clef conventionally: sounding pitch is one octave below the printed note. String/fret numbers describe positions, not finger numbers."],[],{})
    certify(built,spec["level"],bool(spec.get("crossing") or spec["family"] in ("octaves","coordination","buster")))
    return player,built,tonic,mode,{we.sph.pc_of(n) for n in names}


def build(spec):
    from music_coach_ami.flexible_single import package
    player,built,tonic,mode,pcs=built_for(spec)
    plan=package(spec,player,built,tonic,mode,allowed_pcs=pcs)
    plan["items"][0]["meta"]=copy.deepcopy(built.meta)
    return plan


def warmup_built(player,level,tonic,mode,family,**kwargs):
    kind={"scale":"scale","intervals":"octaves" if kwargs.get("interval")=="octaves" else "coordination",
          "articulation":"coordination","long_tones":"scale","bass_arpeggio":"arpeggio"}[family]
    spec=_spec(level,we.key_token(tonic,mode),kind, "")
    spec["direction"]="up and down"
    spec["segment"]=True
    if family=="long_tones":spec["rhythm"]="half"
    if family=="articulation":spec["articulation"]="staccato";spec["rhythm"]="quarter" if level=="Beginner" else "eighth"
    _,built,_,_,_=built_for(spec)
    if family=="intervals" and kwargs.get("interval", "thirds")!="octaves":
        step=we.INTERVALS[kwargs.get("interval", "thirds")]
        p=we.make_player("bass",spec["concert_key"])
        lo,hi=p.window(level)
        hi=min(hi,lo+12)
        names=we.scale_spelling(tonic,mode)
        run=[(n,we.sph.octave_for(n,m),m) for m in range(lo,hi+1) for n in names if m%12==we.sph.pc_of(n)]
        pairs=[(run[i],run[i+step]) for i in range(len(run)-step)]
        if not pairs:raise we.WarmupUnavailable("the requested interval does not fit the bass level window")
        unit="quarter" if level=="Beginner" else "eighth"
        built.notes=we._fill_bar([we.Note(n,o,unit) for pair in pairs for n,o,_ in pair])
        built.title="Bass diatonic "+kwargs.get("interval","thirds")+" - "+we.key_text(tonic,mode)
        certify(built,level)
    if family=="long_tones":
        names=we.scale_spelling(tonic,mode);lo,hi=player.window(level)
        pool=[(m,n) for m in range(lo,hi+1) for n in names if m%12==we.sph.pc_of(n)]
        variant=int(kwargs.get("variant") or 0)
        chosen=[pool[(variant*2+i*3)%len(pool)] for i in range(4)]
        built.notes=we._fill_bar([part for m,n in chosen for part in (we.Note(n,we.sph.octave_for(n,m),"whole"),we.Note("",0,"whole"))])
        built.title="Bass sustain and controlled release - "+we.key_text(tonic,mode)
        certify(built,level)
    return built


def _spec(level,key,family,focus):
    return {"single":True,"bass":True,"instrument":"bass","level":level,"concert_key":key,"family":family,
            "quality":"minor" if we.split_key(key)[1]=="natural minor" else "major", "focus":focus,
            "register":"low","direction":"ascending","octaves":False,"crossing":False,"fifth":False,
            "rhythm":"","articulation":"","bpm":{"Beginner":56,"Intermediate":72,"Advanced":88}[level],"reps":1}


def response(plan,session,lead=""):
    from music_coach_ami.flexible_single import _reply
    row=plan["items"][0]
    return _reply(f"{lead}**{row['title']}** - standard four-string Bass Guitar, {plan['level']}, bass clef. "
                  "Tuning E1 A1 D2 G2 (sounding). Written E2 sounds E1: written minus 12 semitones. "
                  f"Tempo {row['bpm']} BPM; play {row['reps']} time(s). "
                  f"Written notes: {', '.join(row['written_notes'])}.",plan,session)


def handle(question,session,ami_ctx=None):
    from music_coach_ami import flexible_single as fs
    q=question.lower().strip(" .!?");plan=wp.current(session)
    active=bool(plan and plan['spec'].get('bass'))
    fresh=bool(re.search(r"\b(?:give|generate|write|create|build|want|need|help)\b",q))
    # A bass-line role for a song is not automatically a bass-guitar instrument override.
    # Keep the established Song Coach owner unless this is an explicit technique/chart drill.
    if fresh and re.search(r"\bbass[ -]line\b",q) and not re.search(r"bass guitar|\bover\b|chord changes|\bexercises?\b",q):return None
    vocab=bool(re.search(r"exercise|warm[ -]?up|scale|arpeggio|finger[ -]?buster|coordination|octaves?|bass line",q))
    req=wp.parse_request(question)
    page,_=wp._page_values(question,session,ami_ctx)
    player,_,_=wp.resolve_player(req,session,page,req['key'] or getattr(page,'current_practice_key','') or 'C')
    explicit_other=req.get('instrument_word') and req['instrument_word']!='bass'
    named=bool(re.search(r"\bbass(?: guitar)?\b",q)) and not explicit_other
    if fresh and vocab and (named or player and player.key=='bass'):
        if UNSUPPORTED.search(q):return fs._reply("This slice supports standard four-string fretted bass in E-A-D-G, frets 0-12. That technique or tuning is not verified. No exercise changed.",plan,session,"bass_scope")
        level=req['level'] or str(getattr(page,'level','') or 'Intermediate').capitalize()
        if level not in POLICY:return fs._reply("Choose Beginner, Intermediate or Advanced.",plan,session,"level")
        from practice_focus_policy import category_for_focus
        focus=req['focus'] or category_for_focus(str(getattr(page,'practice_focus','') or ''))
        req={**req,'instrument_word':'bass','unverified':''}
        # The existing chart engine alone loads and validates the authoritative snapshot/timeline.
        if re.search(r"\bover\b|chord changes|these chords|this song",q):
            req['families']=['chord_tones'];return wp.create(question,session,ami_ctx,request=req)
        if re.search(r"warm[ -]?up|routine",q):
            if not req['families']:
                req['families']={'harmony':['bass_arpeggio','scale'],'tone':['long_tones','scale'],
                                 'articulation':['articulation','scale'],'melody':['scale','intervals']}.get(focus,['scale','intervals','articulation'])
            elif 'chord_tones' in req['families']:req['families']=['bass_arpeggio' if f=='chord_tones' else f for f in req['families']]
            return wp.create(question,session,ami_ctx,request=req)
        family='buster' if re.search(r'finger[ -]?buster',q) else 'octaves' if 'octave' in q else 'coordination' if re.search(r'coordination|string crossing',q) else 'arpeggio' if 'arpeggio' in q else 'scale' if 'scale' in q or re.search(r'\bin [a-g]',q) else {'harmony':'arpeggio','articulation':'coordination','melody':'scale'}.get(focus,'coordination')
        if family=='buster':level='Advanced' if not req['level'] else level
        if family=='buster' and level!='Advanced':return fs._reply("Bass finger-busters require Advanced level; ask for a coordination exercise instead.",plan,session,"level")
        km=re.search(r'\b([A-G](?:#|b)?)\s+(minor|major)\b',question)
        key=req['key'] or (km[1]+('m' if km[2]=='minor' else '') if km else '') or getattr(page,'current_practice_key','') or 'C'
        spec=_spec(level,key,family,focus)
        if re.search(r'\b(?:high|upper|higher)[ -]register',q):spec['register']='high'
        if re.search(r'maj7|major seventh',q):spec['quality']='maj7'
        elif re.search(r'm7|minor seventh',q):spec['quality']='m7'
        elif 'dominant' in q:spec['quality']='7'
        if 'descending' in q:spec['direction']='descending'
        if focus=='articulation':spec['articulation']='staccato'
        fs.controls(spec,q)
        try:new=build(spec)
        except (we.WarmupUnavailable,ValueError) as exc:return fs._reply(f"I cannot build that bass passage within the verified rules: {exc}. No exercise changed.",plan,session,"bass")
        wp._push(session,new,question,fresh=True);return response(new,session)
    if active and explicit_other and not fresh:return fs._reply("Name the other instrument in a fresh exercise request. No bass exercise changed.",plan,session,"revision")
    if not active or explicit_other:return None
    if re.match(r'explain|why',q):
        return response(plan,session,"The pattern connects the named scale/chord tones or octave pairs using a verified four-string path. Each pitched note has a string, fret and bounded hand window. Mute unused strings for clean separation. No notes or history changed. ")
    if re.fullmatch(r'(?:undo|redo)(?: that)?',q):return None
    if not re.match(r'(?:now |please )?(?:make|move|start|add|use|change|keep|slower|faster)',q):return None
    spec=copy.deepcopy(plan['spec']);changed=False
    if UNSUPPORTED.search(q):return fs._reply("That revision is outside the supported four-string bass rules. No exercise changed.",plan,session,"revision")
    if 'harder' in q:
        spec['level']=wp.LEVEL_UP.get(spec['level'],spec['level']);spec['rhythm']='sixteenth' if spec['level']=='Advanced' else 'eighth';spec['crossing']=True;changed=True
    if 'lower' in q:spec['register']='low';changed=True
    if 'higher' in q:spec['register']='high';changed=True
    if 'fifth' in q:spec['fifth']=True;changed=True
    if 'octave' in q:spec['octaves']=True;changed=True
    if 'descending' in q:spec['direction']='descending';changed=True
    if 'ascending' in q:spec['direction']='ascending';changed=True
    if 'string crossing' in q:spec['crossing']=True;changed=True
    if 'slower' in q:spec['bpm']=max(36,spec['bpm']-10);changed=True
    if 'faster' in q:spec['bpm']=min(120,spec['bpm']+10);changed=True
    changed=fs.controls(spec,q) or changed
    if not changed:return fs._reply("I cannot apply that bass revision accurately yet. No exercise changed.",plan,session,"revision")
    if spec==plan['spec']:return response(plan,session,"Already at that supported setting; no new version. ")
    try:new=build(spec)
    except (we.WarmupUnavailable,ValueError) as exc:return fs._reply(f"That revision is not feasible: {exc}. No exercise changed.",plan,session,"revision")
    wp._commit(session,new,question);return response(new,session)
