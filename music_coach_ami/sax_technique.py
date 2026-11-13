"""Saxophone technique over shared written pitches, events, chart engines and history.

No fingering prescription, altissimo model, new transport or chord parser.
"""
from __future__ import annotations
import copy
import re
from dataclasses import replace
from music_coach_ami import warmup_engine as we, warmup_plan as wp, scale_pattern_harmony as sph

SAX = ('soprano','alto','tenor','baritone')
TECH = r'articulation|tongu|legato|slur|staccato|accent|thirds|fourths|fifths|sixths|octaves?|register transitions?|wide leaps?|chromatic|finger.?coordination|finger.?buster|interval'
UNSUPPORTED = r'\bfrom\s+(?:written\s+)?(?:low|high)\s+[a-g]\b|\b(?:written|note|pitch)\s+[a-g][#b]?[3-7]\b|\b[a-g][#b][3-7]\b|altissimo|overtones?|multiphonics?|growl|flutter|double tongu|triple tongu|alternate finger|finger numbers?|high[ -]f[ -]?(?:sharp|#)|triplets?|swing|ties|tied'
NAMES = ('C','C#','D','Eb','E','F','F#','G','Ab','A','Bb','B')


def options(q, base=None):
    q=re.sub(r'\boctave jumps?\b','octaves',q)
    o=copy.deepcopy(base or {'recipe':'articulation','interval':'thirds','direction':'ascending','register':'middle','pattern':'alternate','accent':False,'rhythm':'','mixed':False})
    if re.search(r'\binterval',q):o['recipe']='intervals'
    intervals=list(re.finditer(r'\b('+ '|'.join(we.INTERVALS) +r')\b',q))
    if intervals:
        o.update(recipe='intervals',interval=intervals[-1][1]);o.pop('intervals_from_plan',None)
    if 'register transition' in q:o['recipe']='transition'
    if re.search(r'coordination|finger.?buster|wide leaps',q):o['recipe']='coordination'
    if 'chromatic' in q:o['recipe']='chromatic'
    if 'descending' in q:o['direction']='descending'
    elif 'ascending' in q:o['direction']='ascending'
    if re.search(r'changes? direction|alternating direction',q):o['direction']='alternating'
    if re.search(r'high[ -]register',q):o['register']='high'
    elif 'comfortable register' in q or 'middle register' in q:o['register']='middle'
    elif re.search(r'low[ -]register|move.*lower',q):o['register']='low'
    if re.search(r'slur (?:every )?(?:two|2)|two slurred|slurred.*tongued|alternat.*(?:tongued|slurred)',q):o['pattern']='alternate' if re.search(r'tongue|tongued',q) else 'pairs'
    elif 'legato' in q:o['pattern']='legato'
    elif 'staccato' in q:o['pattern']='staccato'
    elif re.search(r'tonguing|tongued|tongue every',q):o['pattern']='tongued'
    if re.search(r'repeated.?note|tonguing exercise',q) and not base:o['recipe']='repeated'
    if 'accent' in q:o['accent']=True
    for unit in ('whole','half','quarter','eighth','sixteenth'):
        if re.search(r'\b'+unit+r'[ -]notes?\b',q):o['rhythm']=unit;o['mixed']=False
    if 'rhythm' in q and re.search(r'difficult|harder|challeng',q):o['mixed']=True
    return o


def decorate(built, o):
    """Articulation only: never change a pitch, rest or duration here."""
    notes=[];i=0;group=0;pattern=o['pattern']
    for n in built.notes:
        if n.rest:
            notes.append(n);i=0;group+=1;continue
        pos=i%4
        sl=0
        if pattern=='legato':sl=group+1
        elif pattern=='pairs':sl=group*2+1+pos//2
        elif pattern=='alternate' and pos<2:sl=group+1
        art='staccato' if pattern=='staccato' else ''
        if o['accent'] and pos==0:art=(art+' accent').strip()
        notes.append(replace(n,art=art,slur=sl));i+=1
        if i%4==0:group+=2
    built.notes=we._unslur_singletons(notes)
    built.title='Saxophone '+built.title
    built.how=list(built.how)+[f"Articulation: {pattern}; {'accent the first of each four notes' if o['accent'] else 'no added accent pattern'}. Slurs mean tongue the first note, connect the following notes without another tongue stroke. Keep air steady; stop and rest if tone or coordination deteriorates.",
        'Notation prescribes articulation; this card does not verify playback of saxophone tonguing or reed technique. No alternate fingerings are prescribed.']
    built.meta['sax_options']=copy.deepcopy(o)
    return built


def built(player,level,tonic,mode,o,*,variant=0):
    from music_coach_ami.flexible_single import _window
    if player.key not in SAX:raise we.WarmupUnavailable('choose a verified saxophone')
    lo,hi=_window(player,level,o['register']);lv=we.LEVELS.index(level)
    names=we.scale_spelling(tonic,mode)
    pool=sorted((m,n) for n in names for m in range(lo,hi+1) if m%12==sph.pc_of(n))
    recipe=o['recipe'];span=we.INTERVALS[o['interval']] if recipe=='intervals' else 9 if recipe=='coordination' and lv==2 else 7 if recipe in ('coordination','transition') and lv else 2
    pairs=[]
    if o.get('pitches'):
        pairs=[(int(m),n) for m,n in o['pitches']]
    elif recipe=='transition':
        # Written C#5/D5 surrounds the ordinary middle-register transition.
        values=[71,73,74,76] if lv==0 else [64,76,73,74,76,64,74,73]
        if variant%2:values=list(reversed(values))
        pairs=[(m,NAMES[m%12]) for m in values]*2
    elif recipe=='chromatic':
        start=lo+2+variant%3;values=[start+i+j for i in range(min(4,hi-start-3)) for j in (0,2,1,3)]
        pairs=[(m,NAMES[m%12]) for m in values]
    elif recipe=='repeated':
        if not pool:raise we.WarmupUnavailable('no pitches fit the requested register')
        pairs=[pool[len(pool)//2]]*(8 if lv==0 else 16)
    elif recipe in ('intervals','coordination'):
        if len(pool)<=span:raise we.WarmupUnavailable('the requested interval does not fit this level/register')
        anchors=[i%(len(pool)-span) for i in range((4,6,8)[lv])]
        for i in anchors:
            pair=[pool[i],pool[i+span]]
            if o['direction']=='descending' or o['direction']=='alternating' and i%2:pair.reverse()
            pairs+=pair
        if o['direction']=='descending':
            pairs=[v for i in range(len(pairs)-2,-1,-2) for v in pairs[i:i+2]]
    else:
        pairs=pool[:min(len(pool),16)]
        if o['direction']=='descending':pairs.reverse()
    if not pairs or not all(lo<=m<=hi and player.play_low<=m<=player.play_high for m,_ in pairs):
        raise we.WarmupUnavailable('that exact passage does not fit the verified level/register; no notes were substituted')
    unit=o['rhythm'] or ('quarter','eighth','sixteenth')[lv]
    if level=='Beginner' and (unit=='sixteenth' or o['mixed']):raise we.WarmupUnavailable('mixed/sixteenth-note technique requires Intermediate or Advanced')
    notes=[]
    for i,(m,n) in enumerate(pairs):
        duration=('eighth','sixteenth','sixteenth','quarter')[i%4] if o['mixed'] else unit
        notes.append(we.Note(n,(m-sph.pc_of(n))//12-1,duration))
    notes=we._fill_bar(notes)
    if o.get('routine'):notes=(notes+[we.Note('',0,'whole')])*3
    else:notes=notes+[we.Note('',0,'whole')]
    title={'intervals':f"diatonic {o['interval']} ({o['direction']})",'coordination':('wide-interval finger coordination' if lv else 'finger coordination'),'transition':'middle-register transitions','chromatic':'chromatic finger coordination','repeated':'repeated-note tonguing','articulation':'articulation scale'}[recipe]
    if recipe not in ('transition','chromatic'):title+=' - '+we.key_text(tonic,mode)
    elif recipe=='transition':title+=' - cell '+str(variant%2+1)
    else:title+=' - written '+pairs[0][1]+str(pairs[0][0]//12-1)
    b=we.Built(notes,(56,72,80)[lv],title,[f"Develop {title} in the written register {lo}-{hi} MIDI. This is a key-based technical drill, not a chord-following line."],[],{'window':[lo,hi],'sax_recipe':recipe,'pair_span':span if recipe=='intervals' else None})
    if recipe=='transition':b.how[0]='Coordinate the written C#5/D5 middle-register boundary, including deliberate chromatic notes. This fixed written-register cell does not follow song chords or transpose its register boundary with the key.'
    elif recipe=='chromatic':b.how[0]='Coordinate neighboring semitone changes. This chromatic technical cell is not restricted to the diatonic key and does not follow song chords.'
    return decorate(b,o)


def allowed_pcs(recipe):
    return {1,2,4,11} if recipe=='transition' else set(range(12)) if recipe=='chromatic' else None


def build(spec):
    from music_coach_ami.flexible_single import package
    p=we.make_player(spec['instrument'],spec['concert_key']);tonic,mode=we.practical_key(*we.split_key(p.written_key))
    b=built(p,spec['level'],tonic,mode,spec['sax']);b.bpm=spec['bpm']
    allowed=allowed_pcs(spec['sax']['recipe'])
    plan=package(spec,p,b,tonic,mode,allowed_pcs=allowed)
    row=plan['items'][0];row.update(meta=b.meta,articulations=[n.art for n in b.notes if not n.rest],slur_groups=[n.slur for n in b.notes if not n.rest])
    return plan


def response(plan,session,lead=''):
    from music_coach_ami.flexible_single import _reply
    if not plan['spec'].get('single'):return wp._plan_response(plan,lead=lead,session_ref=session,view=wp.history(session).get('view'))
    r=plan['items'][0];p=plan['player']
    return _reply(f"{lead}**{r['title']}** - {p['label']}, {plan['level']}. Written notes: {', '.join(r['written_notes'])}. Sounding pitches are written minus {p['offset']} semitones. Tempo {r['bpm']} BPM. {r['how'][-1]}",plan,session)


def handle(question,session,ami_ctx=None):
    from music_coach_ami import flexible_single as fs
    if session is None:return None
    q=question.lower().strip(' .!?');plan=wp.current(session);active=bool(plan and plan['spec'].get('sax'))
    fresh=bool(re.search(r'\b(?:give|generate|write|create|build|want|need)\b|^make me',q))
    # Existing musical-idea/expression and mode owners retain their vocabulary.
    if fresh and re.search(r'pentatonic|dorian|harmonic minor|melodic minor',q):return None
    if fresh and re.search(r'\b(?:line|lick|phrase)\b',q) and not re.search(r'\b(?:exercises?|warm.?ups?|routine|technique)\b',q):return None
    unsupported_exercise=bool(re.search(UNSUPPORTED,q) and re.search(r'\b(?:exercises?|warm.?ups?|routine)\b',q))
    general=bool(re.fullmatch(r'(?:please )?give me (?:a|an|one) (?:(?:(?:alto|tenor|soprano|baritone) )?sax(?:ophone)? )?exercise',q))
    if not active and not (fresh and (re.search(TECH,q) or general or unsupported_exercise)):return None
    if fresh and re.search(r'finger.?buster',q) and not re.search(r'articulation|tongu|legato|slur|staccato|accent|interval|chromatic|coordination|wide leaps',q) and not unsupported_exercise:return None
    if fresh and re.search(r'\btwo[ -]note exercises?\b',q):return None  # Existing verified adaptive two-note routines retain their owner.
    req=wp.parse_request(question);page,_=wp._page_values(question,session,ami_ctx)
    if fresh and (re.search(TECH,q) or general or unsupported_exercise):
        p,why,facts=wp.resolve_player(req,session,page,req['key'] or getattr(page,'current_practice_key','') or 'C')
        if p is None:return None
        if p.key not in SAX:return None
        if facts.get('sax_assumed'):return fs._reply('Choose soprano, alto, tenor or baritone saxophone first.',plan,session,'instrument')
        if re.search(UNSUPPORTED,q):return fs._reply('That saxophone technique is outside the verified written Bb3-F6 profile and supported articulation/rhythm model. No exercise changed.',plan,session,'unsupported_sax')
        o=options(q)
        if not re.search(TECH,q):
            from practice_focus_policy import category_for_focus
            focus=category_for_focus(str(getattr(page,'practice_focus','') or ''))
            o['recipe']={'articulation':'articulation','tone':'transition','technique':'coordination'}.get(focus,'intervals')
            if 'scale' in str(getattr(page,'practice_focus','')).lower():o['recipe']='intervals'
            if focus=='tone':o['pattern']='legato'
            if focus=='harmony':
                req['families']=['chord_tones'];req['sax_settings']=o
                return wp.create(question,session,ami_ctx,request=req)
        level=req['level'] or str(getattr(page,'level','') or 'Intermediate').capitalize()
        if re.search(r'difficult|challeng|advanced|finger.?buster|wide leaps',q):level='Advanced' if not req['level'] else req['level']
        song=bool(re.search(r'\b(?:over|bridge|verse|chorus|guide tones?|chord changes)\b',q))
        full=bool(re.search(r'warm.?up|routine|minutes?',q))
        if full and (len(req['families'])>1 or len(req['intervals'])>1):return None  # Preserve explicitly mixed adaptive routines.
        if song:
            if o['recipe']=='intervals' or 'fourths' in q:
                return fs._reply('Exact scale-interval patterns over chords are not verified in this slice. Ask for chart-based guide tones, chord-tone arpeggios or chromatic approaches; no scale was relabelled as chord-following.',plan,session,'sax_song_interval')
            req['families']=['guide_tones'] if 'guide' in q else ['approach_notes'] if 'chromatic' in q else ['chord_tones']
            req['sax_settings']=o;req['level']=level;req['sax_single_song']=not full
            return wp.create(question,session,ami_ctx,request=req)
        if full:
            o['routine']=True
            req['families']=['intervals'] if o['recipe'] in ('intervals','transition','coordination','chromatic') else ['articulation']
            if req['families']==['articulation']:
                req['artic']=[{'alternate':'slur_tongue','pairs':'two_note','legato':'contrast','staccato':'repeated','tongued':'repeated'}[o['pattern']]]
            elif o['recipe']=='intervals':
                o['intervals_from_plan']=not bool(req['intervals'])
            else:req['intervals']=['thirds']  # One allocator stream; displayed recipe comes from the actual technical cell.
            req['sax_settings']=o;req['level']=level
            return wp.create(question,session,ami_ctx,request=req)
        spec={'single':True,'sax':o,'family':'sax_technique','instrument':p.key,'concert_key':p.concert_key,'level':level,'reps':1,'bpm':(56,72,80)[we.LEVELS.index(level)]}
        tempo=re.search(r'(\d+)\s*bpm',q)
        if tempo:spec['bpm']=max(36,min(160,int(tempo[1])))
        try:new=build(spec)
        except (ValueError,we.WarmupUnavailable) as exc:return fs._reply(f'I could not build that saxophone exercise accurately: {exc}.',plan,session,'sax_unavailable')
        wp._push(session,new,question,fresh=True);return response(new,session)
    if not active:return None
    if q in ('undo','undo that','redo','redo that'):return None
    if re.match(r'explain|why',q):return response(plan,session,'This stored technique develops controlled air, finger timing and the notated connections/attacks. ')
    if fresh:return None
    if req.get('unverified') or req.get('instrument_word') and req['instrument_word']!='saxophone':return response(plan,session,'Start a fresh exercise for another instrument; this saxophone technique cannot be relabelled. No exercise changed. ')
    if not re.match(r'(?:now |please )?(?:make|change|keep|use|add|slur|accent|move|adapt)',q):return None
    if re.search(UNSUPPORTED,q):return response(plan,session,'Unsupported saxophone technique; no exercise or history changed. ')
    spec=copy.deepcopy(plan['spec']);old=spec['sax'];o=options(q,old);spec['sax']=o
    if not spec.get('single'):
        if spec.get('song') and any(o[k]!=old[k] for k in ('recipe','interval','direction')):
            return response(plan,session,'That exact interval/direction rewrite over chart harmony is not verified. No pitches, timing, articulation or history changed. ')
        if re.search(r'rhythm|adapt|register',q):return response(plan,session,'For a timed/chart plan use its existing tempo, level or instrument controls; targeted rhythm/register rewrites are not verified here. No exercise changed. ')
        if o==old:return None
        try:new=wp._rebuild(plan,spec,replan=False)
        except ValueError as exc:return response(plan,session,f'That plan revision is unavailable: {exc}. ')
    else:
        pitch_change=bool(re.search(r'thirds|fourths|fifths|sixths|octave|descending|ascending|harder|easier|register|lower',q))
        if pitch_change:o.pop('pitches',None)
        if 'harder' in q and 'rhythm' not in q:spec['level']=wp.LEVEL_UP.get(spec['level'],spec['level'])
        elif 'easier' in q:spec['level']={'Advanced':'Intermediate','Intermediate':'Beginner','Beginner':'Beginner'}[spec['level']]
        elif 'slower' in q:spec['bpm']=max(36,spec['bpm']-10)
        elif 'faster' in q and 'rhythm' not in q:spec['bpm']=min(160,spec['bpm']+10)
        register_move=bool(re.search(r'register|move.*lower',q)) and o['register']!=old['register']
        if register_move:
            p=we.make_player(spec['instrument'],spec['concert_key']);lo,hi=fs._window(p,spec['level'],o['register']);row=plan['items'][0]
            shift=next((v for v in (0,-12,12,-24,24) if all(lo<=m+v<=hi for m in row['written_midi'])),None)
            if shift is None or o['recipe']=='transition' and shift:
                return response(plan,session,'The same passage cannot fit that register by a whole-octave shift. No pitches, timing, marks or history changed. ')
            o['pitches']=[(m+shift,re.sub(r'-?\d+$','',n)) for m,n in zip(row['written_midi'],row['written_notes'])]
        if 'adapt' in q or re.search(r'change.*(?:tenor|alto|soprano|baritone)',q):
            p,why,facts=wp.resolve_player(req,session,page,spec['concert_key'])
            if p is None or p.key not in SAX:return response(plan,session,'Choose a verified saxophone; no exercise changed. ')
            if o['recipe']=='transition' and p.key!=spec['instrument']:return response(plan,session,'This cell targets the fixed written C#5/D5 register boundary. Generate a fresh transition drill for the other saxophone; preserving sounding pitches would mislabel its technique. No exercise changed. ')
            delta=p.offset-plan['player']['offset'];row=plan['items'][0];lo,hi=fs._window(p,spec['level'],o['register'])
            values=[m+delta for m in row['written_midi']]
            shift=next((s for s in (0,-12,12,-24,24) if all(lo<=m+s<=hi for m in values)),None)
            if shift is None:return response(plan,session,'The same sounding passage cannot fit that saxophone/level by a whole-octave shift. No exercise changed. ')
            names=we.scale_spelling(*we.practical_key(*we.split_key(p.written_key)));spell={sph.pc_of(n):n for n in names}
            o['pitches']=[(m+shift,spell.get((m+shift)%12,NAMES[(m+shift)%12])) for m in values]
            spec['instrument']=p.key
            lead=f'Adapted the same sounding passage; octave shift {shift} semitones. '
        else:lead='Updated only the requested saxophone properties. '
        recognized=o!=old or spec!=plan['spec']
        if not recognized:return response(plan,session,'That revision is not supported or is already applied; no new version. ')
        try:new=build(spec)
        except ValueError as exc:return response(plan,session,f'That revision exceeds the verified limits: {exc}. No exercise changed. ')
    if new==plan:return response(plan,session,'Already at those settings; no new version. ')
    wp._commit(session,new,question);return response(new,session,lead if spec.get('single') else 'Updated the routine articulation without changing harmonic timing. ')
