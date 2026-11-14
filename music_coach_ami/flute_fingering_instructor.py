"""Bounded C-foot YFL-222 lookups and octave practice through existing AMI engines."""
import copy,re
from music_coach_ami import warmup_engine as we,warmup_plan as wp,flexible_single as fs
from music_coach_ami import flute_fingering_data as data
from music_coach_ami.session_scope import ensure_owner,is_owned,stamp
from music_coach_ami.fingering_instructor import reply,attach,notes_in
from music_coach_ami.types import CoachResponse,CoachIntent
STATE='_ami_conv_flute_fingering'
LIMIT='This Yamaha YFL-222 C-foot pilot verifies E4/F4/G4/E5/F5/G5 only, with the selected primary B-natural thumb lever. No exercise or history changed.'
EDUCATION='Each verified pair spans 12 semitones, one octave. No finger controls change within these selected pairs; there is no octave key. UNSW flute acoustics explains that air-jet behavior selects the register while these fingerings repeat. Finger actions and air/embouchure adjustments are distinct. Use a comfortable slow tempo and rests; detailed physical technique is not prescribed. These are flute octave transitions, not trumpet lip slurs.'
CONFIG='Yamaha YFL-222 concert C flute, covered keys, offset G, C footjoint, no split-E mechanism'

def context(session):
    ensure_owner(session);v=session.get(STATE) if session is not None else None
    return copy.deepcopy(v) if is_owned(v,session) else {}

def remember(session,ids=(),recipe=None,model=data.MODEL):
    for key in ('_ami_conv_fingering','_ami_conv_trumpet_fingering','_ami_conv_clarinet_fingering'):session.pop(key,None)
    session[STATE]=stamp({'model':model,'instrument':'flute','notes':list(ids),'recipe':copy.deepcopy(recipe)},session)

def pitches(question):
    text=re.sub(r'(?i)\b(?:concert\s+)?c\s+flute\b|\bflute\s+in\s+c\b','flute',question)
    text=re.sub(r'(?i)\b(?:offset\s+g|(?:no\s+)?split[ -]?e(?:\s+mechanism)?|c\s+foot(?:joint)?|(?:a|the) flute)\b','flute',text)
    text=re.sub(r'\b([a-g][b#]?[0-8])\b',lambda m:m[1][0].upper()+m[1][1:],text)
    text=re.sub(r'\b([efg])\b',lambda m:m[1].upper(),text)
    return notes_in(text)

def resolve(question,ctx):
    ids=[];ambiguous=False;q=question.lower()
    both=re.search(r'\blow\s+(?:and\s+)?high\s+([efg])\b',q) or re.search(r'\blow\s+([efg])\b.*\bhigh\s+\1\b',q)
    if both:return [both[1].upper()+'4',both[1].upper()+'5'],False
    for note,default in pitches(question):
        name=note[:-1]
        if not default:
            if note not in data.supported_notes():raise ValueError('That exact flute note/octave is unsupported')
            if re.search(r'\blow\s+'+name+r'[0-8]?\b',q,re.I) and note[-1]!='4':raise ValueError('Low-register wording conflicts with the numbered octave')
            found=[note]
        elif name not in ('E','F','G'):raise ValueError('Choose one of the six verified notes')
        elif re.search(r'\b(?:low|lower)\s+'+name+r'\b',q,re.I):found=[name+'4']
        elif re.search(r'\b(?:high|higher)\s+'+name+r'\b|\bhigher octave\b',q,re.I):found=[name+'5'];ambiguous=True
        else:found=[name+'4',name+'5'];ambiguous=True
        ids.extend(found)
    if not ids and 'higher octave' in q and len(ctx.get('notes',[]))==1:
        low=ctx['notes'][0]
        if low[-1]=='4':ids=[low[0]+'5']
    return list(dict.fromkeys(ids)),ambiguous

def infer(ids):
    for i,pair in enumerate(data.PAIRS):
        if ids and set(ids)<=set(pair):return {'kind':'octave','pairs':[i]}
    if set(ids)==set(data.supported_notes()):return {'kind':'octave','pairs':[0,1,2]}
    return None

def lookup(ids,session,lead='',recipe=None):
    records=[data.record(n) for n in ids];player=we.make_player('flute','C')
    notes=we._fill_bar([we.Note(r['written_name'],r['written_octave'],'half') for r in records]);built=we.Built(notes,48,'Yamaha YFL-222 - verified written fingerings',[],[],{'window':player.window('Intermediate')})
    abc,diag=we.render(player,built,'C','major',title=built.title);we.verify(player,'Intermediate',built,'C','major',diag,allowed_pcs={r['written_midi']%12 for r in records})
    from music_coach_ami.flute_fingering_view import description
    text='; '.join('written '+r['id']+' sounds '+r['id']+'. '+description(r) for r in records)
    if len(ids)==2:text+=f' Interval: {abs(records[1]["written_midi"]-records[0]["written_midi"])} semitones. Finger changes: '+('; '.join(data.changes(*ids)) or 'none; identical selected key states')+'. '
    remember(session,ids,recipe or infer(ids))
    response=CoachResponse(intent=CoachIntent.SCALE_PRACTICE,direct_answer=lead+'**'+CONFIG+'**. '+text+' '+EDUCATION+' Written and concert pitches match; fixed targets, Practice Key and sidebar unchanged. Reference-supported, not teacher-reviewed or physically tested. E4/F4 exercise handoffs require the existing Intermediate range; read-only display does not change proficiency. Existing exercise and Undo/Redo history unchanged. Sources: https://newt.phys.unsw.edu.au/jw/fluteacoustics.html ; https://www.vsl.co.at/academy/woodwinds/concert-flute',notation_abc=abc,source_solver='FluteFingeringInstructor',confidence=1.0)
    return attach(response,records,True)

def build_practice(spec):
    if spec.get('flute_model')!=data.MODEL or spec['instrument']!='flute' or spec['concert_key']!='C':raise we.WarmupUnavailable('No instrument, model, keywork or fixed-target substitution is enabled')
    if spec['level'] not in we.LEVELS or spec.get('buster') or spec.get('articulation') or spec['rhythm'] not in ('half','quarter') or spec['register']!='source-bounded' or not 36<=spec['bpm']<=96 or not 1<=spec['reps']<=12:raise we.WarmupUnavailable('Use plain half/quarter notes, 36-96 BPM and 1-12 repetitions at an existing level')
    groups=data.groups(spec['flute_recipe'],spec['direction']);player=we.make_player('flute','C');lo,hi=player.window(spec['level']);notes=[]
    for group in groups:
        records=[data.record(n) for n in group]
        if any(not lo<=r['written_midi']<=hi for r in records):raise we.WarmupUnavailable('These notes exceed the existing '+spec['level']+' flute range. E4/F4 require explicit Intermediate level; Beginner can use G4-G5')
        notes+=we._fill_bar([we.Note(r['written_name'],r['written_octave'],spec['rhythm']) for r in records])+[we.Note('',0,'whole')]
    built=we.Built(notes,spec['bpm'],'Verified flute octave transitions',[EDUCATION,'Use the displayed selected finger actions. A full-bar rest follows each pair; reset comfortably.','The octave label applies within each pair, not to every connection between different pairs.'],[],{'window':[lo,hi]})
    return fs.package(spec,player,built,'C','major',allowed_pcs={n.midi%12 for n in notes if not n.rest})

def practice_response(plan,session,lead=''):
    ids=list(dict.fromkeys(plan['items'][0]['written_notes']));s=plan['spec'];row=plan['items'][0];remember(session,ids,s['flute_recipe'])
    text=f"{lead}**{row['title']} - {CONFIG}**, {s['level']}. Written and sounding notes: {', '.join(row['written_notes'])}. Tempo {s['bpm']} BPM; play {s['reps']} time(s), including notated rests. "+EDUCATION+' Fixed targets; Practice Key and sidebar unchanged. Reference-supported, not teacher-reviewed or physically tested. Source: https://newt.phys.unsw.edu.au/jw/fluteacoustics.html'
    return attach(fs._reply(text,plan,session),[data.record(n) for n in ids])

def commit(spec,session,question,lead=''):
    try:new=fs.build(spec)
    except (ValueError,KeyError,we.WarmupUnavailable) as exc:return reply(str(exc)+'. '+LIMIT,session)
    old=wp.current(session)
    if old and old['spec']==spec:return practice_response(old,session,'Already at those settings. ')
    wp._commit(session,new,question);return practice_response(new,session,lead)

def handle(question,session,ami_ctx=None):
    if session is None:return None
    q=question.lower().strip(' .!?');ctx=context(session);plan=wp.current(session);active=bool(plan and plan['spec'].get('flute_fingering'))
    model=bool(re.search(r'\byfl[ -]?222\b',q));named=bool(re.search(r'\byfl[ -]?\d+[a-z]*',q));explicit=bool(re.search(r'\bflutes?\b|\bpiccolo\b|\byfl[ -]?\d+',q))
    if re.fullmatch(r'(?:undo|redo)(?: that)?',q):return None
    if not explicit and (ctx.get('instrument')=='flute' or active):
        req=wp.parse_request(question)
        if req.get('unverified') or req.get('instrument_word') not in ('','flute'):return None
    if re.search(r'\b(?:sax(?:ophone)?|yas[ -]?\d+|trumpet|ytr[ -]?\d+|clarinet|ycl[ -]?\d+|piano|bass guitar)\b',q) and not explicit:return None
    handoff=bool(re.search(r'exercise|warm[ -]?up|practice moving|^alternate between',q))
    if handoff and not model and not named and not ctx.get('instrument') and not pitches(question):return None
    fresh=bool(re.search(r'finger|how.*(?:play|move|octave|register)|difference|compare|octave key|lip slur|breathing method',q))
    edit=active and bool(re.match(r'(?:now |please )?(?:make|repeat|add|alternate|use|change|move|slower|faster|keep|remove|ascend|descend|transpose)',q))
    follow=ctx.get('instrument')=='flute' and bool(re.search(r'finger|octave|register|these notes|those notes|that note|embouchure|altissimo|alternate|multiphonic|higher|lower|how.*(?:play|move)|breath|lip slur|difference|compare|low|high',q) or (handoff and re.search(r'\b[a-g][b#]?[0-8]\b|\b(?:from|between|using|it|this|that|these|those)\b',q)))
    ordinary=handoff and re.search(r'\b(?:scales?|arpeggios?|jazz|patterns?|songs?|chords?|progressions?|backing|melody|chorus|bridge|major|minor|dorian|modes?|pentatonic|bebop|blues|over)\b|\bin\s+(?:concert\s+)?[a-g][b#]?\b',q)
    if ordinary and not re.search(r'finger|octave transition|register transition',q):return None
    if not (model or named or (explicit and (fresh or handoff and re.search(r'octave|register|[a-g][45]',q))) or follow or edit):
        if not fresh:return None
        page,_=wp._page_values(question,session,ami_ctx);player,_,_=wp.resolve_player(wp.parse_request(question),session,page,'C')
        if player is None or player.key!='flute':return None
    if re.search(r'\b(?:not|don.t|do not)\b.{0,35}\byfl[ -]?222\b',q):
        remember(session,model='');return reply('No flute model confirmed. '+LIMIT,session)
    unsupported=bool(re.search(r'\byfl[ -]?(?!222\b)\d+[a-z]*|\b(?:alto|bass|irish|baroque|piccolo)\s*(?:flute)?\b|\bb[ -]?foot(?:joint)?\b|gizmo|open[ -]?hole|in[ -]?line|modified|custom keywork|with (?:a )?split[ -]?e',q))
    if unsupported:
        if re.search(r'^(?:i (?:play|have|use)\b|my .{0,25} is\b)',q):remember(session,model='')
        return reply('That flute type, model or keywork configuration is outside this verified pilot. '+LIMIT,session)
    if not model and ctx.get('model')!=data.MODEL:return reply('Which flute model and keywork do you play? This pilot supports '+CONFIG+'. Say "I play a Yamaha YFL-222" if that configuration matches. No model assumed; no exercise changed.',session)
    if model and not pitches(question) and not handoff and not fresh:
        if not re.search(r'^(?:i (?:play|have|use)|my .{0,25} is|(?:please )?use)',q):return reply(CONFIG+'. A model question does not confirm your instrument. Identify your actual model and configuration before fingering handoffs. '+LIMIT,session)
        remember(session);return reply(CONFIG+' identified for this conversation. Ask for E4/F4/G4/E5/F5/G5 or a verified octave comparison. No exercise changed.',session)
    if re.search(r'altissimo|alternate fingering|multiphonic|circular breath|breathing method|sixteenth|triplet|swing|transpose|minutes?|lip slur',q):return reply('That specialized fingering, physical method or edit is outside this bounded flute slice. '+LIMIT,session)
    try:ids,ambiguous=resolve(question,ctx)
    except ValueError as exc:return reply(str(exc)+'. '+LIMIT,session)
    if active and re.search(r'explain|which fingers|what.*chang',q) and ('exercise' in q or ctx.get('notes')==list(dict.fromkeys(plan['items'][0]['written_notes']))):return practice_response(plan,session,'Read-only finger changes in the stored exercise. No exercise or history changed. ')
    if edit:
        spec=copy.deepcopy(plan['spec'])
        if 'slower' in q:spec['bpm']=max(36,spec['bpm']-8)
        elif 'easier' in q:spec['rhythm']='half';spec['bpm']=max(36,spec['bpm']-8);spec['flute_recipe']['pairs']=spec['flute_recipe']['pairs'][:1]
        elif 'harder' in q or 'challenging' in q:spec['rhythm']='quarter';spec['bpm']=min(96,spec['bpm']+8)
        elif 'repeat' in q:
            text=q.replace('four times','4 times').replace('twice','2 times');m=re.search(r'\b(\d+)\s+(?:times|repetitions)',text);spec['reps']=int(m[1]) if m else 2
            if not 1<=spec['reps']<=12:return reply('Choose 1-12 repetitions. '+LIMIT,session)
        elif 'descending' in q or q.startswith('descend'):spec['direction']='descending'
        elif 'ascending' in q or q.startswith('ascend'):spec['direction']='ascending'
        elif q.startswith('alternate') and infer(ids):spec['flute_recipe']=infer(ids)
        elif 'add' in q and re.search(r'another|next',q):
            other=next((i for i in range(3) if i not in spec['flute_recipe']['pairs']),None)
            if other is None:return reply('All three verified octave pairs are already present. '+LIMIT,session)
            spec['flute_recipe']['pairs'].append(other)
        else:return reply('That revision is outside the bounded verified octave recipes. '+LIMIT,session)
        return commit(spec,session,question,'Revised verified flute transition. ')
    recipe={'kind':'octave','pairs':[0,1,2]} if re.search(r'all three|all 3',q) else infer(ids) if ids else ctx.get('recipe')
    if handoff:
        if not recipe:
            if ids:return reply('Choose a verified E4-E5, F4-F5 or G4-G5 octave pair. '+LIMIT,session)
            recipe={'kind':'octave','pairs':[2]}
        page,_=wp._page_values(question,session,ami_ctx);level=wp.parse_request(question).get('level') or str(getattr(page,'level','') or 'Intermediate').capitalize()
        spec=dict(single=True,flute_fingering=True,flute_model=data.MODEL,flute_recipe=recipe,technique='flute_fingerings',family='fingering',instrument='flute',concert_key='C',level=level,register='source-bounded',direction='descending' if 'descending' in q else 'ascending',rhythm='half',bpm=48,reps=1,buster=False,articulation='',count=2)
        fs.controls(spec,q.replace('four times','4 times'));return commit(spec,session,question,'Verified source-backed flute handoff. ')
    if not ids and re.search(r'octave|register|low.*high',q):ids=list(data.PAIRS[0]);recipe={'kind':'octave','pairs':[0]}
    if not ids:ids=ctx.get('notes',[])
    if not ids:return reply('Choose an exact supported written octave or one of the three verified pairs. '+LIMIT,session)
    lead='Octave wording is ambiguous: the supported numbered candidate(s) are labelled below; specify the intended numbered octave. ' if ambiguous else ''
    return lookup(ids,session,lead,recipe)
