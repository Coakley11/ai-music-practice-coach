"""Bounded model-specific trumpet lookups and canonical fixed-valve handoffs."""
import copy,re
from music_coach_ami import warmup_engine as we,warmup_plan as wp,flexible_single as fs
from music_coach_ami import trumpet_fingering_data as data,trumpet_technique as tt
from music_coach_ami.session_scope import ensure_owner,is_owned,stamp
from music_coach_ami.fingering_instructor import reply,attach,notes_in
from music_coach_ami.types import CoachResponse,CoachIntent

STATE='_ami_conv_trumpet_fingering'
LIMIT='This Yamaha YTR-2330 Bb trumpet pilot supports only open, valve 1 only and valve 2 only, partials 2-4. No exercise or history changed.'
EDUCATION='Valves select tube length, not one unique pitch. Coordinate lip vibration and airflow with resonance; use a comfortable tone without forcing or excessive pressure. Partial 1 is the theoretical fundamental/pedal reference (not enabled); the first ordinary slot here is partial 2. These are tempered pitch targets, not exact acoustic intonation measurements.'

def context(session):
    ensure_owner(session);v=session.get(STATE) if session is not None else None
    return copy.deepcopy(v) if is_owned(v,session) else {}

def remember(session,records=()):
    session.pop('_ami_conv_fingering',None)
    session[STATE]=stamp({'model':data.MODEL,'notes':[r['id'] for r in records]},session)

def pitches(question):
    text=re.sub(r'(?i)\b(?:b[ -]?flat|bb|b♭)\s+trumpet\b|\btrumpet\s+in\s+(?:bb|b[ -]?flat|b♭)\b','trumpet',question)
    return notes_in(text)

def valve_in(q):
    if re.search(r'first\s+(?:and|\+)\s+second|second\s+(?:and|\+)\s+first',q):return 'unsupported'
    m=re.search(r'valves?\s+([0-9](?:\s*(?:\+|and|,|-|&)\s*[0-9])*)',q)
    if m:return {'0':'open','1':'1','2':'2'}.get(m[1],'unsupported')
    if 'third valve' in q:return 'unsupported'
    if 'first valve' in q:return '1'
    if 'second valve' in q:return '2'
    if re.search(r'open[ -]?(?:valve|notes|harmonic|series)|all valves released|no valves|open valves',q):return 'open'
    return ''

def lookup(ids,session,lead=''):
    records=[data.record(n) for n in ids];p=we.make_player('trumpet','Bb')
    b=we.Built(we._fill_bar([we.Note(r['written_name'],r['written_octave'],'half') for r in records]),48,'Yamaha YTR-2330 - verified written targets',[],[],{'window':p.window('Beginner')})
    abc,diag=we.render(p,b,'C','major',title=b.title)
    we.verify(p,'Beginner',b,'C','major',diag,allowed_pcs={r['written_midi']%12 for r in records})
    detail='; '.join(f"written {r['id']} sounds {r['sounding_name']}{r['sounding_octave']}: {'all valves released' if r['valve']=='open' else 'valve '+r['valve']+' pressed, others released'}, partial {r['partial']}" for r in records)
    remember(session,records)
    return attach(CoachResponse(intent=CoachIntent.SCALE_PRACTICE,direct_answer=lead+'**Yamaha YTR-2330 Bb trumpet**. '+detail+'. '+EDUCATION+' Manufacturer/reference-supported; not teacher-reviewed or physically tested. Written C-major signature; fixed targets do not follow Practice Key. Existing exercise and Undo/Redo history unchanged.',notation_abc=abc,source_solver='TrumpetFingeringInstructor',confidence=1.0),records,True)

def build_practice(spec):
    if spec.get('trumpet_model')!=data.MODEL or spec['instrument']!='trumpet' or spec['concert_key']!='Bb':raise we.WarmupUnavailable('Model and fixed written targets cannot be substituted')
    if spec.get('routine') or spec.get('buster') or spec['style']!='slur' or spec['cells']!=1 or spec['rhythm'] not in ('half','quarter') or spec.get('articulation'):raise we.WarmupUnavailable('Only a short plain fixed-valve lip slur is enabled')
    selected=tt._selection(spec)
    if not set(selected)<= {2,3,4}:raise we.WarmupUnavailable('No next source-verified partial beyond 4 is enabled')
    verified={r['partial']:r for r in data.series(spec['valve'])}
    if any(n not in verified for n in selected):raise we.WarmupUnavailable('Unverified valve/partial selection')
    plan=tt.build(spec)
    if plan['items'][0]['written_midi']!=[verified[n]['written_midi'] for n in (selected if spec['direction']=='ascending' else selected[::-1])]:raise we.WarmupUnavailable('Canonical notes differ from the verified records')
    return plan

def practice_response(plan,session,lead=''):
    records=[data.record(n) for n in dict.fromkeys(plan['items'][0]['written_notes'])]
    remember(session,records)
    return attach(tt.response(plan,session,lead+'Yamaha YTR-2330 source-backed pilot (partials 2-4). '+EDUCATION+' '),records)

def commit(spec,session,question,lead=''):
    try:new=fs.build(spec)
    except (ValueError,we.WarmupUnavailable,KeyError) as exc:return reply(str(exc)+'. '+LIMIT,session)
    old=wp.current(session)
    if old and old['spec']==spec:return practice_response(old,session,'Already at those supported settings. ')
    wp._commit(session,new,question)
    return practice_response(new,session,lead)

def create(ids,session,question,level):
    records=[data.record(n) for n in ids];settings={r['valve'] for r in records}
    if len(settings)!=1:return reply('Choose notes from one verified fixed valve setting for a lip slur. '+LIMIT,session)
    valve=settings.pop();partials=sorted({r['partial'] for r in records})
    if len(partials)==1:
        partials=[2,3] if partials[0]<4 else [3,4]
    start=partials[0]-2;count=partials[-1]-partials[0]+1
    spec=dict(single=True,trumpet=True,trumpet_fingering=True,trumpet_model=data.MODEL,technique='trumpet_partials',family='technique',instrument='trumpet',concert_key='Bb',level=level,valve=valve,start=start,partial_count=count,cells=1,buster=False,routine=False,direction='ascending',style='slur',articulation='',rhythm='half',focus='tone',bpm=48,reps=1,register='level-bounded partials')
    return commit(spec,session,question,'Adjacent verified partial path (including any intermediate partial). ')

def handle(question,session,ami_ctx=None):
    if session is None:return None
    q=question.lower().strip(' .!?');ctx=context(session);plan=wp.current(session)
    active=bool(plan and plan['spec'].get('trumpet_fingering'))
    model=bool(re.search(r'ytr[ -]?2330\b',q));explicit=bool(re.search(r'trumpet|ytr[ -]?\d+',q))
    # An explicitly different ordinary instrument keeps its established owner.
    if re.search(r'\b(?:sax(?:ophone)?|yas[ -]?280|flute|clarinet|piano|bass guitar)\b',q) and not explicit:return None
    fresh=bool(re.search(r'finger|valves?|harmonic series|partial|low c.*high c|high c.*low c',q))
    handoff=bool(re.search(r'exercise|lip[ -]?slur|start with|move up',q))
    edit=active and bool(re.search(r'^(?:now |please )?(?:make|use|change|add|repeat|slower|faster|start|move|keep)',q))
    follow=bool(ctx.get('model') and re.search(r'those notes|these notes|that note|valves?|partials?|what changes|harmonic|finger|lip[ -]?slur|start with|exercise moving|low c.*high c|pedal|embouchure',q))
    if re.fullmatch(r'(?:undo|redo)(?: that)?',q):return None
    if not (model or (explicit and fresh) or follow or edit):
        if not fresh or ctx.get('model'):return None
        page,_=wp._page_values(question,session,ami_ctx)
        player,_,_=wp.resolve_player(wp.parse_request(question),session,page,'C')
        if player is None or player.key!='trumpet':return None
    # Generic trumpet drills and their revisions retain the existing owner.
    if not ctx.get('model') and not model and not re.search(r'fingering|^(?:what|which|show|how)',q):
        if handoff or (plan and plan['spec'].get('trumpet')):return None
    if model and re.search(r"(?:not|don't|do not|isn't|is not).{0,35}ytr[ -]?2330",q):
        session.pop(STATE,None);return reply('No trumpet model confirmed. '+LIMIT,session)
    if re.search(r'\b(?:c|d|eb|e-flat|piccolo|bass) trumpet\b|trumpet in (?!bb\b|b[ -]?flat\b|b♭\b)|(?:ytr)[ -]?(?!2330\b)\d+|modified|rotary|trombone|french horn|tuba',q):return reply('That type or model is outside the verified model. '+LIMIT,session)
    if not model and ctx.get('model')!=data.MODEL:return reply('Which trumpet model do you play? This fingering pilot supports standard Yamaha YTR-2330 Bb three-piston trumpet only. Say "I play a Yamaha YTR-2330" if it matches. No model assumed; no exercise changed.',session)
    if model and not re.search(r'finger|valve|partial|harmonic|exercise|lip[ -]?slur|low c|high c',q) and not pitches(question):
        if not re.search(r'^(?:i (?:play|have|use)|my .{0,25} is|(?:please )?use)',q):return reply('Identify your actual model explicitly; a model question does not confirm it. '+LIMIT,session)
        remember(session);return reply('Yamaha YTR-2330 Bb three-piston trumpet identified for this conversation. Ask for written C4/G4/C5, Bb3/F4/Bb4 or B3/F#4/B4. No exercise changed.',session)
    valve=valve_in(q)
    if valve=='unsupported' or re.search(r'pedal|embouchure|alternate|extreme|partial\s*(?:1\b|[5-9])|(?:fifth|sixth|seventh|eighth) partial|sixteenth|triplet|swing|transpose|minutes?',q):return reply(LIMIT+' Specialized techniques and unverified range/rhythm are not enabled.',session)
    found=pitches(question);ids=[]
    for note,unnumbered in found:
        name=note[:-1]
        matches=[n for n in data.supported_notes() if n[:-1]==name] if unnumbered else [note]
        if not matches or any(n not in data.supported_notes() for n in matches):return reply('That written pitch is unsupported. '+LIMIT,session)
        ids.extend(matches)
    ids=list(dict.fromkeys(ids))
    if ids and re.search(r'\bconcert|\bsounding',q):return reply('Please specify written trumpet pitches; sounding pitches are labelled separately. '+LIMIT,session)
    if active and (re.search(r'show.*valves.*each note|explain.*(?:changes|same)|what changes',q)):
        return practice_response(plan,session,'Read-only explanation of the stored exercise. No exercise or history changed. ')
    if edit:
        spec=copy.deepcopy(plan['spec'])
        if valve and valve!=spec['valve']:return reply('Choose an explicit new lookup and exercise for a different valve setting. '+LIMIT,session)
        if re.search(r'start.*c.*(?:up|to).*g',q):
            if spec['valve']!='open':return reply('C4-G4 uses the open setting. '+LIMIT,session)
            spec.update(start=0,partial_count=2)
        elif 'next' in q and 'partial' in q:spec['partial_count']+=1
        elif 'slower' in q:spec['bpm']=max(36,spec['bpm']-8)
        elif 'easier' in q:spec.update(start=0,partial_count=2,rhythm='half',bpm=max(36,spec['bpm']-8))
        elif 'repeat' in q:
            m=re.search(r'\b(\d+)\s+times',q);reps=int(m[1]) if m else 2
            if not 1<=reps<=12:return reply('Choose 1 to 12 repetitions. '+LIMIT,session)
            spec['reps']=reps
        else:return reply('That edit is outside this bounded source-backed pilot. '+LIMIT,session)
        return commit(spec,session,question,'Revised verified lip slur. ')
    if handoff and ctx.get('model') and not ids:ids=ctx.get('notes',[])
    if not ids and valve:ids=[r['id'] for r in data.series(valve)]
    if handoff:
        if not ids:ids=['C4','G4']
        if re.search(r'start.*c.*(?:up|to).*g',q):ids=['C4','G4']
        if any(default for _,default in found) and len({data.record(n)['valve'] for n in ids})>1:return reply('Specify exact written notes from one fixed valve series. '+LIMIT,session)
        page,_=wp._page_values(question,session,ami_ctx)
        level=wp.parse_request(question).get('level') or str(getattr(page,'level','') or 'Beginner').capitalize()
        return create(ids,session,question,level)
    if not ids:ids=ctx.get('notes',[])
    if not ids:return reply('Choose a written note with octave or ask for open-valve notes. '+LIMIT,session)
    if valve and any(data.record(n)['valve']!=valve for n in ids):return reply('The requested notes do not match that verified valve setting. '+LIMIT,session)
    lead='Supported harmonic-series slice only (partials 2-4), not the complete series. ' if re.search(r'harmonic|series|open.valve notes',q) else ''
    if any(default for _,default in found) or re.search(r'\b(?:low|high) c\b',q):lead+='Ambiguous register: clearly labelled supported possibilities below; specify a numbered written octave. "High C" is not assumed to mean C5. '
    return lookup(ids,session,lead)
