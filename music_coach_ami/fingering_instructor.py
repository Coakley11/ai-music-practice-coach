"""Bounded note lookup and handoff through AMI's existing single-plan engine."""
import copy,re
from music_coach_ami import warmup_engine as we,warmup_plan as wp,flexible_single as fs
from music_coach_ami import scale_pattern_harmony as sph
from music_coach_ami.fingering_data import record,changes
from music_coach_ami.session_scope import ensure_owner,is_owned,stamp
from music_coach_ami.types import CoachResponse,CoachIntent

STATE='_ami_conv_fingering'

def context(session):
    ensure_owner(session)
    value=session.get(STATE) if session is not None else None
    return copy.deepcopy(value) if is_owned(value,session) else {}

def remember(session,note='',model=True):
    session[STATE]=stamp({'model':'yamaha-yas280' if model else '', 'note':note},session)

def reply(text,session):
    p=wp.current(session)
    if p and p['spec'].get('single'):return fs._reply(text,p,session,'fingering_limit')
    from music_coach_ami.sax_conversation import reply as existing
    return existing(p,session,text)

def attach(response,records,lookup=False):
    response.diagnostics.update(fingering_instruction=records,fingering_lookup=lookup)
    return response

def lookup(note,session,default=False):
    r=record(note);p=we.make_player('alto','Eb')
    b=we.Built([we.Note(r['written_name'],4,'whole')],60,'Written '+note+' - Yamaha YAS-280',[],[],{'window':p.window('Beginner')})
    abc,diag=we.render(p,b,'C','major',title=b.title)
    we.verify(p,'Beginner',b,'C','major',diag,allowed_pcs={r['written_midi']%12})
    pressed=', '.join(k for k,v in r['key_states'].items() if v)
    text=(f"**Yamaha YAS-280 alto saxophone - written {note}**, sounding {r['sounding_name']}{r['sounding_octave']}. "
        f"Press {pressed}; right-hand main keys, octave thumb and auxiliary finger controls are released. "
        'Manufacturer/reference-supported, not independently teacher-reviewed. The diagram is a logical control schematic. '
        'This is a fixed written pitch, independent of Practice Key; the staff uses a written C-major signature. '
        'The existing exercise and Undo/Redo history are unchanged. Ask for a short exercise to practice this note.')
    if default:text+=' For an unnumbered G, A or B, this Stage A pilot uses documented written octave 4.'
    remember(session,note)
    return attach(CoachResponse(intent=CoachIntent.SCALE_PRACTICE,direct_answer=text,notation_abc=abc,source_solver='FingeringInstructor',confidence=1.0),[r],True)

def build_practice(spec):
    """A fixed-note recipe packaged/rendered/verified by existing deterministic AMI."""
    r=record(spec['fingering']);p=we.make_player(spec['instrument'],spec['concert_key'])
    if p.key!='alto' or spec['concert_key']!='Eb' or spec['register']!='middle':
        raise we.WarmupUnavailable('Stage A preserves the exact written target on Yamaha YAS-280; no instrument/register/key substitution.')
    if spec.get('buster') or spec['rhythm'] not in ('quarter','half'):
        raise we.WarmupUnavailable('Stage A supports slow quarter/half-note practice only.')
    ids=['G4','A4','B4',r['id']] if spec.get('fingering_neighbors') else [r['id']]*(2 if spec['rhythm']=='half' else 4)
    if spec.get('fingering_neighbors'):
        ids.sort(key=lambda n:record(n)['written_midi'],reverse=spec['direction']=='descending')
    notes=we._fill_bar([we.Note(record(n)['written_name'],4,spec['rhythm']) for n in ids])
    b=we.Built(notes,spec['bpm'],'Fingering practice - '+r['id']+(' - '+spec['direction'] if spec.get('fingering_neighbors') else ''),
        ['Use only the displayed verified finger controls. Fixed written notes do not follow Practice Key.','Practice slowly; this is not an assessment of your tone or fingering performance.'],[],{'window':p.window(spec['level'])})
    if r['written_midi'] not in [n.midi for n in notes if not n.rest]:raise we.WarmupUnavailable('Target missing')
    return fs.package(spec,p,b,'C','major',allowed_pcs={7,9,11})

def practice_response(plan,session,lead=''):
    r=record(plan['spec']['fingering']);remember(session,r['id'])
    ids=list(dict.fromkeys(plan['items'][0]['written_notes']))
    records=[record(n) for n in ids]
    text=f"{lead}**Fingering practice - written {r['id']} on Yamaha YAS-280**. Sounds {r['sounding_name']}{r['sounding_octave']}. Tempo {plan['items'][0]['bpm']} BPM. Written notes: {', '.join(plan['items'][0]['written_notes'])}. Fixed written pitches; Practice Key and sidebar settings unchanged. Reference-supported, not teacher-reviewed."
    return attach(fs._reply(text,plan,session),records)

def create(note,session,question,neighbors=False):
    spec={'single':True,'fingering':note,'fingering_neighbors':neighbors,'family':'fingering','instrument':'alto','concert_key':'Eb','level':'Beginner','register':'middle','direction':'ascending','rhythm':'quarter','bpm':60,'reps':1,'buster':False,'articulation':'','quality':'major','count':4}
    p=build_practice(spec);wp._commit(session,p,question)
    return practice_response(p,session)

def notes_in(question):
    text=question.replace('\u266d','b').replace('\u266f','#')
    text=re.sub(r'\b([A-Ga-g])[- ]flat\b',lambda m:m[1].upper()+'b',text)
    text=re.sub(r'\b([A-Ga-g])[- ]sharp\b',lambda m:m[1].upper()+'#',text)
    found=re.findall(r'(?<![A-Za-z])([A-G])([b#]?)([0-8]?)(?![A-Za-z0-9])',text)
    if not found:
        found=re.findall(r'\b(?:for|finger|note|that)\s+(?:written\s+)?([a-g])([b#]?)([0-8]?)\b',text.lower())
    return [(n.upper()+a+(o or '4'),not bool(o)) for n,a,o in found]

def handle(question,session,ami_ctx=None):
    if session is None:return None
    q=question.lower().strip(' .!?');ctx=context(session);plan=wp.current(session)
    active=bool(plan and plan['spec'].get('fingering'))
    fresh=bool(re.search(r"(?:what|show|how|which).{0,60}fingerings?|(?:show|how).{0,40}finger\b|what.*keys.*press|fingering\s+(?:for|of)\s+[a-g]",q))
    follow=bool(ctx.get('note') and re.search(r'which keys|keys.*(?:press|change)|explain.*keys|show.*(?:note|staff)|exercise.*\b(?:that|it|this|note)\b|practice.*\b(?:that|it|this|note)\b|leading up',q))
    model_named=bool(re.search(r'yas[ -]?280\b',q))
    # Generic instrument coordination/fingering exercises retain their owners.
    if re.search(r'exercise|warm.?up',q) and not notes_in(question) and not model_named and not re.search(r'\b(?:it|that|this|note)\b',q) and not re.search(r'\b(?:explain|why)\b|keys.*change',q):
        return None
    if not (fresh or follow or model_named or (active and re.search(r'easier|descending|ascending|leading up',q))):return None
    if re.search(r'altissimo|overtones?|alternate.*fingering|alternative.*fingering|another fingering',q):
        return reply('Stage A contains one basic fingering per written G4, A4 and B4. No alternate or specialized fingering is supplied; no exercise changed.',session)
    if model_named and re.search(r"(?:not|don't|do not|isn't|is not).{0,35}yas[ -]?280",q):
        session.pop(STATE,None)  # Retract only lookup identity, never the stored exercise/history.
        return reply('No model was confirmed. Stage A covers standard Yamaha YAS-280 only; a different or uncertain model needs verified data. No exercise changed.',session)
    req=wp.parse_request(question)
    if req.get('instrument_word') and (req.get('instrument_word')!='saxophone' or req.get('sax_type_word') not in ('','alto')):
        return reply('Stage A covers Yamaha YAS-280 alto saxophone only; no different instrument was substituted and no exercise changed.',session)
    if re.search(r'(?i)(?:yas|yss|yts|ybs)[ -]?(?!280\b)\d+|selmer|yanagisawa|buffet|modified|custom keywork|left.hand',q):
        return reply('That model or keywork configuration is outside Stage A. Only standard Yamaha YAS-280 keywork is reference-supported; no model was substituted and no exercise changed.',session)
    bound_followup=bool(ctx.get('note') and not fresh and not req.get('instrument_word') and (follow or active))
    if not model_named and not req.get('sax_type_word') and not bound_followup:
        page,_=wp._page_values(question,session,ami_ctx)
        p,_,facts=wp.resolve_player(req,session,page,'C')
        if p is None or p.key!='alto':return reply('Stage A covers identified Yamaha YAS-280 alto saxophone only. Specify your instrument/model; no exercise changed.',session)
    if not model_named and ctx.get('model')!='yamaha-yas280':
        return reply('Which saxophone model do you play? Stage A supports Yamaha YAS-280 standard keywork only. If it matches, say "I play a Yamaha YAS-280". No model was assumed and no exercise changed.',session)
    found=notes_in(question);unique=list(dict.fromkeys(n for n,_ in found))
    if len(unique)>1:return reply('Choose one written pitch for this lookup: G4, A4 or B4. No exercise changed.',session)
    if re.search(r'(?:concert|sounding)\s+(?:note\s+)?[a-g][#b]?[0-8]?',q) and unique:
        return reply('Please specify the written pitch. Stage A accepts written G4, A4 or B4 and separately labels its sounding pitch; no exercise changed.',session)
    if re.search(r'\b(?:high|low|upper|lower|second octave)\b',q) and fresh:
        return reply('Please specify written G4, A4 or B4. Other registers are outside this pilot; no exercise changed.',session)
    note=unique[0] if unique else ctx.get('note','')
    if note and note not in ('G4','A4','B4'):
        return reply('That written note is unsupported. Stage A contains G4, A4 and B4 only; no substitute or exercise change was made.',session)
    if model_named and not note:
        if not re.search(r"^(?:i (?:play|have|use)\b|my .{0,20} is\b|(?:please )?use\b)",q):
            return reply('Please identify your actual model rather than infer it. If it matches this pilot, say "I play a Yamaha YAS-280". No model or exercise changed.',session)
        remember(session,ctx.get('note',''))
        return reply('Yamaha YAS-280 standard keywork identified for this conversation. Ask for written G4, A4 or B4. For unnumbered G/A/B the pilot uses written octave 4. No exercise changed.',session)
    if not note:return reply('Which written note: G4, A4 or B4? No exercise changed.',session)
    # Only successful, supported requests confirm model/note context.
    if active and re.search(r'explain.*keys|keys.*change|which keys',q) and not fresh and (ctx.get('note')==plan['spec']['fingering'] or re.search(r'\bexercise\b',q)):
        remember(session,plan['spec']['fingering'])
        ids=plan['items'][0]['written_notes'];lines=[]
        for a,b in zip(ids,ids[1:]):
            delta=changes(a,b);lines.append(a+' to '+b+': '+('; '.join(delta) or 'keep the same finger controls'))
        return attach(fs._reply('Key changes in the stored exercise: '+'; '.join(lines)+'. No exercise or history changed.',plan,session),[record(n) for n in dict.fromkeys(ids)])
    if active and 'easier' in q:
        spec=copy.deepcopy(plan['spec']);spec.update(fingering_neighbors=False,rhythm='half',bpm=max(36,spec['bpm']-10))
        if spec==plan['spec']:return practice_response(plan,session,'Already at these easier settings. ')
        new=build_practice(spec);wp._commit(session,new,question);return practice_response(new,session,'Simplified to the exact target note. ')
    if active and re.search(r'descending|ascending',q):
        if not plan['spec'].get('fingering_neighbors'):return reply('A repeated single pitch has no ascending/descending contour. Ask for the verified G4-A4-B4 transition exercise first; no exercise changed.',session)
        return None  # Existing single-plan revision/history engine owns the direction edit.
    handoff=bool(re.search(r'exercise|leading up|practice (?:playing|that|it|this)',q)) and bool(re.search(r'give|create|generate|practice|leading up|learn',q))
    if handoff:
        if 'leading up' in q and note!='B4':return reply('Two distinct verified notes below that target are unavailable in this three-note pilot. For B4, G4 and A4 provide a verified lead-in. No exercise changed.',session)
        return create(note,session,question,neighbors=bool(re.search(r'leading up|g4.*a4.*b4|transition',q)))
    return lookup(note,session,default=any(default for _,default in found))
