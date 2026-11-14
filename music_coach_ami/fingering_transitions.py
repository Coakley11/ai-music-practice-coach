"""Verified octave comparisons and bounded recipes through the canonical AMI engine."""
import copy,re
from music_coach_ami import fingering_data as data,warmup_engine as we,warmup_plan as wp,flexible_single as fs

PAIRS={n:(n+'4',n+'5') for n in 'DEFGA'}

def resolve(question):
    """Resolve explicit pitch/register language; never infer keywork from pitch."""
    from music_coach_ami.fingering_instructor import notes_in
    found=notes_in(question);out=[]
    for note,default in found:
        letter=note[:-1];octave=note[-1]
        matches=list(re.finditer(r'\b(low|lower|high|higher|upper)\s+'+re.escape(letter)+r'([0-8]?)(?![A-Za-z0-9])',question,re.I))
        if matches:
            for m in matches:
                wanted='5' if m[1].lower() in ('high','higher','upper') else '4'
                if m[2] and m[2]!=wanted:raise ValueError('Register word conflicts with the numbered written pitch; please specify one exact pitch.')
                out.append(letter+wanted)
        else:
            if default and letter=='C':raise ValueError('Please specify the written octave for C; C4 is not in the verified set, while C5 is.')
            out.append(note)
    return list(dict.fromkeys(out))

def sequence(spec):
    t=spec['fingering_transition'];lo,hi=t['pair']
    a,b=data.record(lo),data.record(hi)
    if b['written_midi']-a['written_midi']!=12 or a['written_name']!=b['written_name']:
        raise we.WarmupUnavailable('An octave transition needs two verified pitches exactly 12 semitones apart.')
    pattern=t['pattern']
    if pattern=='jump':ids=[lo,hi]
    elif pattern=='harder':ids=[lo,hi,lo,hi]
    elif pattern=='lead':
        # The selected source-backed pilot has a documented three-note upper G lead-in.
        if hi!='G5':raise we.WarmupUnavailable('The verified lead-in is E5-F5-G5 only; choose the G octave pair.')
        ids=[lo,'E5','F5',hi]
    elif pattern=='ladder':ids=['D4','E4','F4','G4','A4','B4','C5','D5']
    else:raise we.WarmupUnavailable('Unknown transition pattern')
    for n in ids:data.record(n)
    if spec['direction']=='descending':ids=list(reversed(ids))
    elif spec['direction']!='ascending':raise we.WarmupUnavailable('Only ascending or descending verified patterns are available.')
    return ids

def build(spec):
    if spec['instrument']!='alto' or spec['concert_key']!='Eb' or spec['register']!='middle' or spec.get('buster'):
        raise we.WarmupUnavailable('Fixed Yamaha YAS-280 written pitches; instrument, key and register substitution unavailable.')
    if spec['rhythm'] not in ('half','quarter') or spec.get('articulation'):
        raise we.WarmupUnavailable('This pilot supports plain slow half/quarter-note practice only.')
    ids=sequence(spec);p=we.make_player('alto','Eb')
    notes=we._fill_bar([we.Note(data.record(n)['written_name'],data.record(n)['written_octave'],spec['rhythm']) for n in ids])
    built=we.Built(notes,spec['bpm'],'Verified octave transition - '+' / '.join(spec['fingering_transition']['pair']),
        ['Use the displayed source-backed controls; practice slowly. This does not assess your response, tone or intonation.',
         'The octave thumb changes for these documented pairs; moving the thumb alone does not guarantee a sounding pitch.'],[],{'window':p.window(spec['level'])})
    return fs.package(spec,p,built,'C','major',allowed_pcs={data.record(n)['written_midi']%12 for n in ids})

def compare(pair,session):
    from music_coach_ami import fingering_instructor as fi
    records=[data.record(n) for n in pair];p=we.make_player('alto','Eb')
    level='Intermediate' if max(r['written_midi'] for r in records)>79 else 'Beginner'
    b=we.Built([we.Note(r['written_name'],r['written_octave'],'half') for r in records],60,'Written octave comparison',[],[],{'window':p.window(level)})
    abc,diag=we.render(p,b,'C','major',title=b.title);we.verify(p,level,b,'C','major',diag,allowed_pcs={r['written_midi']%12 for r in records})
    delta=data.changes(*pair)
    text=('**Written octave comparison: '+pair[0]+' / '+pair[1]+' on Yamaha YAS-280**. Exactly 12 semitones apart. '+
          '; '.join(delta)+'. All other displayed finger controls stay the same. The sounding notes are '+
          ' / '.join(r['sounding_name']+str(r['sounding_octave']) for r in records)+'. '+
          'Here low/high means written octave 4/5 for this verified pair. These are documented basic fingerings, not a guarantee of response from thumb movement alone. '+
          'Manufacturer/reference-supported; not teacher-reviewed or physically tested. No exercise or history changed.')
    fi.remember(session,pair[-1],notes=pair)
    return fi.attach(fi.CoachResponse(intent=fi.CoachIntent.SCALE_PRACTICE,direct_answer=text,notation_abc=abc,source_solver='FingeringInstructor',confidence=1.0),records,True)

def commit(spec,session,question,lead=''):
    from music_coach_ami import fingering_instructor as fi
    try:p=fs.build(spec)
    except (ValueError,we.WarmupUnavailable) as e:return fi.reply(str(e)+' No exercise or history changed.',session)
    old=wp.current(session)
    if old and old['spec']==spec:return fi.practice_response(old,session,'Already at those settings. ')
    wp._commit(session,p,question)
    return fi.practice_response(p,session,lead)

def handle(question,session,ctx,plan):
    from music_coach_ami import fingering_instructor as fi
    q=question.lower();active=bool(plan and plan['spec'].get('fingering_transition'))
    intent=bool(re.search(r'octave|register.transition|low [a-g].*high [a-g]|difference.*finger|compare.*finger',q))
    intent=intent or (len(fi.notes_in(question))==2 and 'finger' in q)
    follow=bool(ctx.get('notes') and re.search(r'two notes|which keys|keys.*change|explain.*keys|show.*staff|give.*exercise|transition|gradually|leading into|repeat|harder',q))
    edit=active and bool(re.search(r'easier|descending|ascending|slower|faster|repeat|harder|gradually|leading into',q))
    # Register-qualified single lookups also need exact pitch resolution.
    qualified=bool(re.search(r'\b(?:low|high|upper|lower)\s+[a-g][0-8]?\b',q) and re.search(r'finger|keys.*press',q))
    if not (intent or follow or edit or qualified):return None
    if re.search(r'concert|sounding',q):return fi.reply('Please specify written pitches for this comparison; sounding pitches are labelled separately. No exercise changed.',session)
    try:found=resolve(question)
    except ValueError as e:return fi.reply(str(e)+' No exercise changed.',session)
    if any(n not in data.supported_notes() for n in found):return fi.reply('A requested pitch is outside the verified fingering set. No substitute or exercise change was made.',session)
    if qualified and not intent and len(found)==1:return fi.lookup(found[0],session)
    pair=None
    if len(found)>2:return fi.reply('Choose one verified octave pair: D4/D5, E4/E5, F4/F5, G4/G5 or A4/A5. No exercise changed.',session)
    if len(found)==2:
        pair=sorted(found,key=lambda n:data.record(n)['written_midi'])
    elif len(found)==1:
        pair=PAIRS.get(found[0][0])
    elif ctx.get('notes'):pair=ctx['notes']
    elif 'octave key' in q:pair=PAIRS['G']
    elif ctx.get('note'):pair=PAIRS.get(ctx['note'][0])
    if not pair or tuple(pair) not in PAIRS.values():return fi.reply('Choose one verified written octave pair: D4/D5, E4/E5, F4/F5, G4/G5 or A4/A5. No exercise changed.',session)
    if active and edit:
        spec=copy.deepcopy(plan['spec'])
        if found and tuple(pair)!=tuple(spec['fingering_transition']['pair']):return fi.reply('That is a different target pair. Ask explicitly for a new octave exercise; the stored exercise is unchanged.',session)
        if 'slower' in q or 'faster' in q:
            spec['bpm']=max(36,min(100,spec['bpm']+(-10 if 'slower' in q else 10)))
        elif 'repeat' in q:
            numbers=re.findall(r'\b(\d+)\s+times\b',q)
            if not numbers and 'four times' not in q:return fi.reply('Specify 1 to 12 repetitions. No exercise changed.',session)
            fs.controls(spec,q.replace('four times','4 times'))
        elif 'easier' in q:
            spec['fingering_transition']['pattern']='jump';spec['rhythm']='half'
        elif 'harder' in q:
            spec['fingering_transition']['pattern']='harder';spec['rhythm']='quarter'
        elif 'leading into' in q:
            if pair[-1]!='G5':return fi.reply('The verified upper-register lead-in is E5-F5-G5 only. No exercise changed.',session)
            spec['fingering_transition']['pattern']='lead';spec['rhythm']='quarter'
        elif 'gradually' in q:
            spec['fingering_transition'].update(pattern='ladder',pair=list(PAIRS['D']));spec['fingering']='D5';spec['rhythm']='quarter'
        elif 'descending' in q or 'ascending' in q:spec['direction']='descending' if 'descending' in q else 'ascending'
        return commit(spec,session,question,'Revised verified transition. ')
    if active and re.search(r'keys.*change|explain.*keys',q) and ('exercise' in q or ctx.get('notes')==plan['spec']['fingering_transition']['pair']):
        ids=plan['items'][0]['written_notes'];text='; '.join(a+' to '+b+': '+('; '.join(data.changes(a,b)) or 'same controls') for a,b in zip(ids,ids[1:]))
        fi.remember(session,plan['spec']['fingering'],notes=plan['spec']['fingering_transition']['pair'])
        return fi.attach(fs._reply('Key changes in the stored exercise: '+text+'. No exercise or history changed.',plan,session),[data.record(n) for n in dict.fromkeys(ids)])
    exercise=bool(re.search(r'give|create|generate|practice switching',q) and re.search(r'exercise|practice',q))
    if exercise:
        spec={'single':True,'fingering':pair[-1],'fingering_transition':{'pair':list(pair),'pattern':'jump'},'family':'fingering','instrument':'alto','concert_key':'Eb','level':'Intermediate' if data.record(pair[-1])['written_midi']>79 else 'Beginner','register':'middle','direction':'ascending','rhythm':'half','bpm':60,'reps':1,'buster':False,'articulation':'','quality':'major','count':2}
        fs.controls(spec,q)
        return commit(spec,session,question,'Verified octave exercise. ')
    return compare(pair,session)
