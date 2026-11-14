"""Bounded YCL-255 lookups and source-verified register recipes through AMI."""
import copy,re
from music_coach_ami import warmup_engine as we,warmup_plan as wp,flexible_single as fs
from music_coach_ami import clarinet_fingering_data as data
from music_coach_ami.session_scope import ensure_owner,is_owned,stamp
from music_coach_ami.fingering_instructor import reply,attach,notes_in
from music_coach_ami.types import CoachResponse,CoachIntent
STATE='_ami_conv_clarinet_fingering'
LIMIT='This Yamaha YCL-255 Bb Boehm pilot verifies E3/F3/G3/Bb4/B4/C5/D5 with the displayed basic little-finger choices only. No exercise or history changed.'
EDUCATION='A register-key twelfth is 19 semitones (12 + 7), an ordinary octave is 12, and the Bb4-B4 register break is one semitone. Pressing the register key opens a vent; it does not simply act as a saxophone octave key or guarantee a response. Practice slowly and rest if uncomfortable; no specialized embouchure or breathing method is prescribed.'

def context(session):
    ensure_owner(session);v=session.get(STATE) if session is not None else None
    return copy.deepcopy(v) if is_owned(v,session) else {}

def remember(session,ids=(),recipe=None):
    session.pop('_ami_conv_fingering',None);session.pop('_ami_conv_trumpet_fingering',None)
    session[STATE]=stamp({'model':data.MODEL,'instrument':'clarinet','notes':list(ids),'recipe':copy.deepcopy(recipe)},session)

def pitches(question):
    text=re.sub(r'(?i)\b(?:b[ -]?flat|bb|b♭)\s+clarinet\b|\bclarinet\s+in\s+(?:bb|b[ -]?flat|b♭)\b','clarinet',question)
    text=re.sub(r'(?i)\b(?:a|the) clarinet\b','clarinet',text)
    return notes_in(text)

def resolve(question):
    ids=[];ambiguous=False
    for note,default in pitches(question):
        name=note[:-1]
        if not default:
            if note not in data.supported_notes():raise ValueError('That exact written octave is unsupported')
            qualified=re.search(r'\blow\s+'+re.escape(name)+r'([0-8])?\b',question,re.I)
            if qualified and note not in ('E3','F3','G3'):raise ValueError('Low-register wording conflicts with this numbered target')
            found=[note]
        else:
            low=bool(re.search(r'\blow\s+'+re.escape(name)+r'\b',question,re.I))
            high=bool(re.search(r'\bhigh\s+'+re.escape(name)+r'\b',question,re.I))
            if low:
                n={'E':'E3','F':'F3','G':'G3'}.get(name)
                if not n:raise ValueError('Choose an explicit verified lower-register written pitch')
                found=[n]
            elif high:
                n={'B':'B4','C':'C5','D':'D5'}.get(name)
                if not n:raise ValueError('That high-register fingering is outside the pilot')
                found=[n];ambiguous=True
            else:
                found=[n for n in data.supported_notes() if n[:-1]==name]
                if not found:raise ValueError('That note has no verified fingering here')
                ambiguous=not bool(re.search(r'\bclarion\b|above.*break',question,re.I))
        ids.extend(found)
    return list(dict.fromkeys(ids)),ambiguous

def infer(ids):
    if not ids:return None
    if ids==['Bb4'] or (len(ids)==2 and set(ids)==set(data.BREAK)):return {'kind':'break'}
    for i,pair in enumerate(data.PAIRS):
        if set(ids)<=set(pair):return {'kind':'twelfth','pairs':[i]}
    return None

def lookup(ids,session,lead='',recipe=None):
    records=[data.record(n) for n in ids];player=we.make_player('clarinet','Bb')
    notes=we._fill_bar([we.Note(r['written_name'],r['written_octave'],'half') for r in records])
    built=we.Built(notes,48,'Yamaha YCL-255 - verified written fingerings',[],[],{'window':player.window('Intermediate')})
    abc,diag=we.render(player,built,'C','major',title=built.title);we.verify(player,'Intermediate',built,'C','major',diag,allowed_pcs={r['written_midi']%12 for r in records})
    from music_coach_ami.clarinet_fingering_view import description
    text='; '.join('written '+r['id']+' sounds '+r['sounding_name']+str(r['sounding_octave'])+'. '+description(r) for r in records)
    if len(ids)==2:
        interval=abs(records[1]['written_midi']-records[0]['written_midi'])
        text+=f' Interval: {interval} semitones. Changes: '+('; '.join(data.changes(*ids)) or 'none')+'. '
        if set(ids)==set(data.BREAK):text+='The register key stays pressed in both selected break fingerings. '
        elif interval==19:text+='Only the register key changes for this selected source pair; the thumb hole and chosen little finger stay the same. This does not generalize to every clarinet note. '
    remember(session,ids,recipe or infer(ids))
    response=CoachResponse(intent=CoachIntent.SCALE_PRACTICE,direct_answer=lead+'**Yamaha YCL-255 Bb clarinet - standard Boehm, 17 keys, 6 rings**. '+text+' '+EDUCATION+' Fixed written targets, sounding a major second lower; Practice Key and sidebar unchanged. Reference-supported, not teacher-reviewed or physically tested. E3/F3 exercise handoffs require the existing Intermediate range; this read-only staff display does not change proficiency. Existing exercise and Undo/Redo history unchanged.',notation_abc=abc,source_solver='ClarinetFingeringInstructor',confidence=1.0)
    return attach(response,records,True)

def build_practice(spec):
    if spec.get('clarinet_model')!=data.MODEL or spec['instrument']!='clarinet' or spec['concert_key']!='Bb':raise we.WarmupUnavailable('No model, instrument or written-target substitution is enabled')
    if spec['level'] not in we.LEVELS or spec.get('buster') or spec.get('articulation') or spec['rhythm'] not in ('half','quarter') or spec['register']!='source-bounded' or not 36<=spec['bpm']<=96 or not 1<=spec['reps']<=12:raise we.WarmupUnavailable('Use the bounded level, plain half/quarter notes, 36-96 BPM and 1-12 repetitions')
    groups=data.groups(spec['clarinet_recipe'],spec['direction']);player=we.make_player('clarinet','Bb');lo,hi=player.window(spec['level']);notes=[]
    for group in groups:
        records=[data.record(n) for n in group]
        if any(not lo<=r['written_midi']<=hi for r in records):raise we.WarmupUnavailable('These notes exceed the existing '+spec['level']+' range. E3/F3 require explicit Intermediate level; Beginner can use G3-D5 or Bb4-B4')
        notes+=we._fill_bar([we.Note(r['written_name'],r['written_octave'],spec['rhythm']) for r in records])+[we.Note('',0,'whole')]
    title='Verified clarinet register-break crossing' if spec['clarinet_recipe']['kind']=='break' else 'Verified clarinet twelfth transitions'
    how=[EDUCATION,'Use the displayed source-backed controls. Each selected pair is followed by a full-bar breath rest; reset comfortably during the rest.','Each twelfth pair spans 19 semitones; connections between different pairs are not necessarily twelfths.' if spec['clarinet_recipe']['kind']=='twelfth' else 'Bb4-B4 crosses the break by one semitone: keep the register key pressed, release A, cover the thumb and six holes, and press left E/B (reverse these actions when descending).']
    built=we.Built(notes,spec['bpm'],title,how,[],{'window':[lo,hi]})
    return fs.package(spec,player,built,'C','major',allowed_pcs={n.midi%12 for n in notes if not n.rest})

def practice_response(plan,session,lead=''):
    ids=list(dict.fromkeys(plan['items'][0]['written_notes']));records=[data.record(n) for n in ids];s=plan['spec'];row=plan['items'][0]
    deltas='; '.join(a+' to '+b+': '+', '.join(data.changes(a,b)) for a,b in data.groups(s['clarinet_recipe'],s['direction']))
    remember(session,ids,s['clarinet_recipe'])
    text=f"{lead}**{row['title']} - Yamaha YCL-255 Bb Boehm clarinet**, {s['level']}. Written notes: {', '.join(row['written_notes'])}. Sounding pitches are written minus 2 semitones. Tempo {s['bpm']} BPM; play {s['reps']} time(s), including notated rests. {deltas}. "+EDUCATION+' Fixed written pitches; sidebar and Practice Key unchanged. Reference-supported, not teacher-reviewed or physically tested.'
    return attach(fs._reply(text,plan,session),records)

def commit(spec,session,question,lead=''):
    try:new=fs.build(spec)
    except (ValueError,KeyError,we.WarmupUnavailable) as exc:return reply(str(exc)+'. '+LIMIT,session)
    old=wp.current(session)
    if old and old['spec']==spec:return practice_response(old,session,'Already at those settings. ')
    wp._commit(session,new,question);return practice_response(new,session,lead)

def handle(question,session,ami_ctx=None):
    if session is None:return None
    q=question.lower().strip(' .!?');ctx=context(session);plan=wp.current(session)
    active=bool(plan and plan['spec'].get('clarinet_fingering'));model=bool(re.search(r'ycl[ -]?255\b',q));explicit=bool(re.search(r'clarinet|ycl[ -]?\d+',q));named_model=bool(re.search(r'\bycl[ -]?\d+',q))
    if re.search(r'\b(?:sax(?:ophone)?|yas[ -]?\d+|trumpet|ytr[ -]?\d+|flute|piano|bass guitar)\b',q) and not explicit:return None
    if not explicit and (ctx.get('model') or ctx.get('instrument')=='clarinet'):
        requested=wp.parse_request(question)
        if requested.get('unverified') or requested.get('instrument_word') not in ('','clarinet'):return None
    if re.fullmatch(r'(?:undo|redo)(?: that)?',q):return None
    handoff=bool(re.search(r'exercise|warm[ -]?up|practice moving',q))
    fresh=bool(re.search(r'finger|register key|how do i play.*break|difference.*register',q))
    edit=active and bool(re.match(r'(?:now |please )?(?:make|repeat|add|use|change|move|slower|faster|keep|remove|ascend|descend|transpose)',q))
    follow=bool((ctx.get('model') or ctx.get('instrument')=='clarinet') and (re.search(r'finger|register|break|twelfth|these notes|those notes|that note|embouchure|breathing|altissimo|alternate|oehler|albert|bass clarinet|eb clarinet|e-flat clarinet|clarinet in',q) or (handoff and (re.search(r'\b[a-g][b#]?[0-8]\b|\b(?:from|between)\b|\b(?:low|high)\s+[a-g]\b',q) or re.search(r'\b(?:it|this|that|these|those)\b',q)))))
    ordinary_generation=handoff and re.search(r'\b(?:scales?|arpeggios?|jazz|patterns?|songs?|chords?|progressions?|backing|melody|chorus|bridge|major|minor|dorian|mixolydian|lydian|phrygian|aeolian|locrian|modes?|pentatonic|bebop|blues|over)\b|\bin\s+(?:concert\s+)?[a-g][b#]?\b',q)
    if ordinary_generation and not re.search(r'finger|register[ -]?key|twelfth|break',q):return None
    if not (model or named_model or (explicit and fresh) or follow or edit):
        if not fresh or handoff:return None
        page,_=wp._page_values(question,session,ami_ctx);player,_,_=wp.resolve_player(wp.parse_request(question),session,page,'C')
        if player is None or player.key!='clarinet':return None
    if not model and not ctx.get('model') and not ctx.get('instrument') and handoff and not pitches(question):return None
    if model and re.search(r"(?:not|don't|do not|isn't|is not).{0,35}ycl[ -]?255",q):
        session.pop(STATE,None);return reply('No clarinet model confirmed. '+LIMIT,session)
    if re.search(r'\b(?:bass|contra(?:bass|alto)|eb|e-flat|c|d) clarinet\b|clarinet in (?!bb\b|b[ -]?flat\b|b♭\b)|a[ -]key clarinet|(?:ycl)[ -]?(?!255\b)\d+|oehler|albert|german|modified|custom keywork',q):
        if re.search(r'^(?:i (?:play|have|use)\b|my .{0,25} is\b)',q):
            session.pop('_ami_conv_fingering',None);session.pop('_ami_conv_trumpet_fingering',None)
            session[STATE]=stamp({'model':'','instrument':'clarinet','notes':[],'recipe':None},session)
        return reply('That clarinet type, model or key system is outside the verified pilot. '+LIMIT,session)
    if not model and ctx.get('model')!=data.MODEL:return reply('Which clarinet model and system do you play? This pilot supports Yamaha YCL-255 Bb clarinet, standard Boehm 17 keys and 6 rings. Say "I play a Yamaha YCL-255" if it matches. No model assumed; no exercise changed.',session)
    if model and not pitches(question) and not handoff and not fresh:
        if not re.search(r'^(?:i (?:play|have|use)|my .{0,25} is|(?:please )?use)',q):return reply('Identify your actual model explicitly; a model question does not confirm it. '+LIMIT,session)
        remember(session);return reply('Yamaha YCL-255 Bb Boehm 17-key, 6-ring model identified for this conversation. Ask for E3/F3/G3/Bb4/B4/C5/D5, a twelfth pair, or the register break. No exercise changed.',session)
    if re.search(r'altissimo|alternate|embouchure|circular breath|breathing method|sixteenth|triplet|swing|transpose|minutes?',q):return reply('That specialized fingering, method or edit is outside this source-backed slice. '+LIMIT,session)
    if 'octave' in q:return reply('An ordinary octave is 12 semitones; these source-backed register pairs are twelfths (19), and Bb4-B4 is the one-semitone break. No fingering-specific octave recipe is enabled. '+LIMIT,session)
    try:ids,ambiguous=resolve(question)
    except ValueError as exc:return reply(str(exc)+'. '+LIMIT,session)
    if ids and re.search(r'\bconcert|\bsounding',q):return reply('Specify written clarinet pitches; sounding pitches are labelled separately. '+LIMIT,session)
    if active and re.search(r'explain|what.*chang|show.*fingers',q) and ('exercise' in q or ctx.get('notes')==list(dict.fromkeys(plan['items'][0]['written_notes']))):return practice_response(plan,session,'Read-only finger changes in the stored exercise. No exercise or history changed. ')
    if edit:
        spec=copy.deepcopy(plan['spec'])
        if 'slower' in q:spec['bpm']=max(36,spec['bpm']-8)
        elif 'easier' in q:
            spec['rhythm']='half';spec['bpm']=max(36,spec['bpm']-8)
            if spec['clarinet_recipe']['kind']=='twelfth':spec['clarinet_recipe']['pairs']=spec['clarinet_recipe']['pairs'][:1]
        elif 'repeat' in q:
            text=q.replace('four times','4 times').replace('twice','2 times');m=re.search(r'\b(\d+)\s+(?:times|repetitions)',text);reps=int(m[1]) if m else 2
            if not 1<=reps<=12:return reply('Choose 1-12 repetitions. '+LIMIT,session)
            spec['reps']=reps
        elif 'descending' in q or q.startswith('descend'):spec['direction']='descending'
        elif 'ascending' in q or q.startswith('ascend'):spec['direction']='ascending'
        elif 'add' in q and re.search(r'another|next',q) and 'twelfth' in q:
            if spec['clarinet_recipe']['kind']!='twelfth':return reply('Choose a twelfth exercise before adding another twelfth pair. '+LIMIT,session)
            other=next((i for i in range(3) if i not in spec['clarinet_recipe']['pairs']),None)
            if other is None:return reply('All three verified twelfth pairs are already present. '+LIMIT,session)
            spec['clarinet_recipe']['pairs'].append(other)
        else:return reply('That revision is outside the bounded verified recipes. '+LIMIT,session)
        return commit(spec,session,question,'Revised verified clarinet transition. ')
    recipe={'kind':'break'} if 'break' in q else infer(ids) if ids else ctx.get('recipe')
    if handoff:
        if not recipe:
            if ids:return reply('Choose one verified twelfth pair or Bb4-B4 for the register break. '+LIMIT,session)
            recipe={'kind':'twelfth','pairs':[2]}
        page,_=wp._page_values(question,session,ami_ctx);level=wp.parse_request(question).get('level') or str(getattr(page,'level','') or 'Intermediate').capitalize()
        spec=dict(single=True,clarinet_fingering=True,clarinet_model=data.MODEL,clarinet_recipe=recipe,technique='clarinet_fingerings',family='fingering',instrument='clarinet',concert_key='Bb',level=level,register='source-bounded',direction='descending' if 'descending' in q else 'ascending',rhythm='half',bpm=48,reps=1,buster=False,articulation='',count=2)
        fs.controls(spec,q.replace('four times','4 times'))
        return commit(spec,session,question,'Verified source-backed handoff. ')
    if 'break' in q and not ids:ids=list(data.BREAK)
    if not ids and re.search(r'register|twelfth|low.*high',q):ids=list(data.PAIRS[0]);recipe={'kind':'twelfth','pairs':[0]}
    if not ids:ids=ctx.get('notes',[])
    if not ids:return reply('Choose an exact written note or a verified register pair. '+LIMIT,session)
    lead='Register wording is ambiguous: this is the labelled supported candidate, not an assumption about every use of "high". Specify a numbered written octave. ' if ambiguous else ''
    return lookup(ids,session,lead,recipe)
