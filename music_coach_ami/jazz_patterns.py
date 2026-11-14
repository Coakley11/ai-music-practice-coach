"""Bounded conversational jazz patterns using existing warmup ownership/history."""
import copy,re
from dataclasses import replace
from music_coach_ami import warmup_plan as wp,warmup_engine as we,sax_technique as sx,jazz_engine as je
from music_coach_ami import sax_conversation as sc,scale_pattern_harmony as sph

UNVERIFIED_EXTENSIONS=r'elevenths|thirteenths|(?:extensions?|tensions?|add|use)\s+(?:the\s+)?(?:11|13)\b|9\s*-\s*11|11\s*-\s*13'
NEW = r'permutations?|enclosures?|bebop|anticipat|3\s*[-,]\s*5\s*[-,]\s*7\s*[-,]\s*9|descending seventh.chord|jazz|improvisation warm.?up|wide leaps.*stepwise|technical pattern.*bridge|finger.?buster.*(?:changes? direction|each chord)'


def options(q,base=None):
    o=sx.options(q,base);o.update(jazz=True,recipe='jazz')
    if not base:o.update(jazz_kind='permutation',jazz_shape='skip',jazz_target='third',jazz_approach='enclosure',jazz_intervals=['sixths'])
    if not base and not re.search(r'register|move.*lower',q):o['register']='level'
    if re.search(r'permut|arpeggio|seventh.chord',q):o['jazz_kind']='permutation'
    if re.search(r'descending seventh.chord',q):o.update(jazz_seventh=True,jazz_shape='straight',direction='descending')
    if re.search(r'3\s*[-,]\s*5\s*[-,]\s*7\s*[-,]\s*9',q):o.update(jazz_kind='permutation',jazz_roles=['3','5','7','9'])
    if re.search(r'guide.?tone|guide tones|resolutions',q) and not re.search(r'wide|stepwise',q):o['jazz_kind']='guide'
    if re.search(r'enclos|bebop|chromatic approach|approach.*(?:next chord|third|seventh)',q):
        o['jazz_kind']='approach'
        o['jazz_approach']='enclosure' if 'enclos' in q or 'bebop' in q else 'double' if 'double' in q else 'above' if 'above' in q else 'below' if 'below' in q else 'mixed'
    if 'double' in q:o.update(jazz_kind='approach',jazz_approach='double_above' if 'above' in q else 'double')
    if 'anticipat' in q:o['jazz_kind']='anticipation'
    if re.search(r'target.*seventh|next chord.s seventh',q):o['jazz_target']='seventh'
    elif re.search(r'target.*third|third of each chord',q):o['jazz_target']='third'
    m=re.search(r'start.*(?:on|from) (?:the )?(third|seventh|root|fifth)',q)
    if m:o['jazz_start']=m[1]
    intervals=re.findall(r'\b(thirds|fourths|fifths|sixths|octaves)\b',q)
    if intervals and not re.search(r'target|start|chord.s (?:third|seventh)',q):
        o['jazz_kind']='interval';o['jazz_intervals']=[intervals[-1]] if re.search(r'change.*\bto\b',q) else list(dict.fromkeys(intervals))
    if re.search(r'wide leaps|stepwise resolutions',q):o.update(jazz_kind='interval',jazz_steps=True,jazz_intervals=['sixths'])
    if re.search(r'changes? direction|changing directions',q):o['direction']='alternating'
    if re.search(r'low[ -]register|move.*lower',q):o['register']='low'
    if 'rhythm' in q and re.search(r'alter|change|challeng|difficult|harder',q):o['mixed']=True
    return o


def item_options(spec,desc):
    o=copy.deepcopy(desc.get('sax_options',spec['sax']))
    if o['jazz_kind']=='plan':
        o['jazz_kind']={'guide_tones':'guide','chord_tones':'permutation','approach_notes':'approach'}[desc['family']]
        v=int(desc['params'].get('variant') or 0)
        if o['jazz_kind']=='permutation':o['jazz_shape']=('skip','zig','straight')[v%3]
        if o['jazz_kind']=='approach':o['jazz_approach']=('enclosure','double','mixed')[v%3]
    return o


def _reply(plan,session,text):return sc.reply(plan,session,text)


def _create(question,session,ami_ctx):
    q=question.lower();req=wp.parse_request(question);page,_=wp._page_values(question,session,ami_ctx)
    p,_,facts=wp.resolve_player(req,session,page,req['key'] or getattr(page,'current_practice_key','') or 'C')
    if p is None or p.key not in sx.SAX:return None
    if facts.get('sax_assumed'):return _reply(wp.current(session),session,'Choose a verified saxophone first; no exercise changed.')
    if re.search(sx.UNSUPPORTED,q) or re.search(UNVERIFIED_EXTENSIONS,q) or 'optional scale extensions' in q:return _reply(wp.current(session),session,'That technique, extension or rhythm is outside this verified jazz slice. No exercise changed.')
    o=options(q)
    full=bool(re.search(r'warm.?up|routine|minutes?',q))
    if full and re.search(r'improvisation|jazz warm.?up',q) and not re.search(r'only|just|enclosure|3-5-7-9',q):o['jazz_kind']='plan'
    family='guide_tones' if o['jazz_kind']=='guide' else 'approach_notes' if o['jazz_kind']=='approach' else 'chord_tones'
    req.update(families=['guide_tones','chord_tones','approach_notes'] if o['jazz_kind']=='plan' else [family],sax_settings=o,sax_single_song=not full)
    req['level']=req['level'] or 'Advanced'
    song,_=wp.ws.read_song(page)
    if 'bridge' in q and song and not any('bridge' in name.lower() for name in song['order']):return _reply(wp.current(session),session,'This chart has no verified bridge section. Name an actual section; no exercise changed.')
    previous=wp.current(session);history=wp.history(session)
    result=wp.create(question,session,ami_ctx,request=req)
    if previous and not result.notation_abc and not result.notation_abc_sections and wp.current(session)==previous and wp.history(session)==history:
        return _reply(previous,session,'No exercise changed. '+result.direct_answer)
    return result


def handle(question,session,ami_ctx=None):
    if session is None:return None
    q=question.lower().strip(' .!?');plan=wp.current(session);active=bool(plan and plan['spec'].get('sax',{}).get('jazz'))
    fresh=bool(re.search(r'\b(?:give|generate|write|create|build|want|need)\b|^make (?:me|a |an )',q))
    exercise_scope=bool(re.search(r'exercises?|drills?|patterns?|warm.?up|routine|permutation|arpeggio|finger.?buster|3\s*[-,]\s*5\s*[-,]\s*7\s*[-,]\s*9|thirds and fourths.*(?:over|changes)',q))
    if fresh and (exercise_scope or active) and (re.search(NEW,q) or re.search(r'thirds and fourths.*(?:over|changes)',q) or active and re.search(r'pattern|arpeggio|enclosure|sixths|fourths|thirds',q)) and not re.search(r'\b(?:lick|line|phrase|pentatonic|dorian)\b',q):return _create(question,session,ami_ctx)
    if not active:return None
    if q in ('undo','undo that','redo','redo that') or re.search(r'^(?:next|previous|show|go to)',q):return None
    if fresh:return None
    if not re.match(r'(?:now |please )?(?:make|change|keep|use|add|slur|accent|move|adapt|start|approach|explain|why)',q):return None
    reference=question
    if re.search(r'(?:these|those) notes|keep (?:the )?(?:notes|pitches)|use.*(?:bridge|section).*instead',q):reference+=' this exercise'
    row,why=sc.target(plan,reference,session)
    if row is None:return _reply(plan,session,why or 'Name one exercise; no exercise changed.')
    if re.match(r'explain|why',q):return _reply(plan,session,je.explain(row))
    if re.search(sx.UNSUPPORTED,q) or re.search(UNVERIFIED_EXTENSIONS,q):return _reply(plan,session,'That jazz rhythm or saxophone technique is unsupported. No exercise changed.')
    req=wp.parse_request(question)
    if req.get('unverified') or req.get('instrument_word') and req['instrument_word']!='saxophone':return _reply(plan,session,'Choose a verified saxophone. No exercise changed.')
    new=copy.deepcopy(plan);spec=new['spec'];index=wp._index_of(plan,row['uid'])-1;desc=next(d for d in spec['items'] if d['uid']==row['uid'])
    old=row['sax_options'];o=options(q,old);p=we.make_player(row['instrument'],spec['concert_key']);level=row['item_level'];b=sc.restore(row['sax_snapshot']);lead=''
    try:
        sel=copy.deepcopy(desc.get('sax_song_sel',spec['song_sel']));section=wp.ws.find_section(spec['song']['order'],q)
        section_change=bool(section and re.search(r'use|instead|switch|change',q))
        if section_change:sel.update(section=section,bars=None);lead=f'Using {section} for this item. '
        if re.search(r'harder|more difficult',q) and 'rhythm' not in q:
            level='Advanced';o['direction']='alternating';o['jazz_shape']='zig' if old.get('jazz_shape')!='zig' else 'skip'
            if old['jazz_kind']=='guide':o.update(jazz_kind='approach',jazz_approach='double',jazz_target='third')
            if old['jazz_kind']=='approach':o['jazz_approach']='double' if old.get('jazz_approach')!='double' else 'enclosure'
        rhythm_only=bool('rhythm' in q and re.search(r'keep.*(?:notes|pitches)|without changing',q))
        music_keys=('jazz_kind','jazz_shape','jazz_roles','jazz_start','jazz_seventh','jazz_target','jazz_approach','jazz_intervals','jazz_steps','direction','rhythm')
        rebuild=section_change or level!=row['item_level'] or any(o.get(k)!=old.get(k) for k in music_keys)
        keep_targets=bool(re.search(r'keep.*targets',q))
        if keep_targets:
            arrivals=[r for i,r in enumerate(b.meta['jazz_records']) if i==0 or r['segment']!=b.meta['jazz_records'][i-1]['segment'] and r['concert']!=b.meta['jazz_records'][i-1]['concert']]
            roles={r['role'] for r in arrivals}
            words={'R':'root','3':'third','5':'fifth','7':'seventh'}
            if section_change or len(roles)!=1 or next(iter(roles)) not in words:raise we.WarmupUnavailable('those targets cannot be retained by one verified target recipe')
            o['jazz_target']=words[next(iter(roles))];rebuild=True
        if rebuild and not rhythm_only:
            before=b
            b=je.build(p,level,spec['song'],sel['section'],tuple(sel['bars']) if sel.get('bars') else None,o)
            if keep_targets:je.preserve_targets(before,b,p,spec['song'])
            if len(b.notes)==len(before.notes) and o['pattern']==old['pattern'] and o['accent']==old['accent']:
                b.notes=[replace(a,art=z.art,slur=z.slur) for a,z in zip(b.notes,before.notes)]
        elif rhythm_only:
            if b.meta.get('sax_chart'):raise we.WarmupUnavailable('pitch-preserving mixed interval timing is unsupported')
            je.retime(b);je.records(p,b,spec['song']);o['mixed']=True
        if o['pattern']!=old['pattern'] or o['accent']!=old['accent']:b=sx.decorate(b,o)
        if re.search(r'adapt|suitable',q) or re.search(r'for (?:tenor|alto|soprano|baritone) sax',q):
            page,_=wp._page_values(question,session,ami_ctx);target,_,_=wp.resolve_player(req,session,page,spec['concert_key'])
            if target is None or target.key not in sx.SAX:raise we.WarmupUnavailable('choose a verified saxophone')
            lo,hi=target.window(level);delta=target.offset-p.offset
            shift=next((v for v in (0,-12,12,-24,24) if all(lo<=n.midi+delta+v<=hi for n in b.notes if not n.rest)),None)
            if shift is None:raise we.WarmupUnavailable('the exact passage cannot fit this saxophone by a whole-octave shift')
            notes=[]
            for n in b.notes:
                nm=sph.transpose_spelled(n.spelled,delta);m=n.midi+delta+shift;notes.append(replace(n,spelled=nm,octave=sph.octave_for(nm,m)))
            b.notes=notes;p=target;desc['sax_instrument']=p.key;b.meta['window']=[lo,hi]
            if b.meta.get('sax_chart'):
                for r,n in zip(b.meta['chart_records'],b.notes):r.update(name=n.spelled,midi=n.midi)
            je.records(p,b,spec['song'])
            if b.meta.get('sax_chart'):
                for a,z in zip(b.meta['chart_records'],b.meta['jazz_records']):a['written_chord']=z['written_chord']
            lead+=f'Adapted for {p.label}; sounding octave shift {shift:+d} semitones. '
        if o.get('register')!=old.get('register'):
            from music_coach_ami.flexible_single import _window
            lo,hi=_window(p,level,o['register']);shift=next((v for v in (-12,-24,0,12,24) if all(lo<=n.midi+v<=hi for n in b.notes)),None)
            if shift is None:raise we.WarmupUnavailable('the unchanged pitch pattern cannot fit that register through whole octaves')
            b.notes=[replace(n,octave=n.octave+shift//12) for n in b.notes];b.meta['window']=[lo,hi]
            if b.meta.get('sax_chart'):
                for r in b.meta['chart_records']:r['midi']+=shift
            je.records(p,b,spec['song']);lead+=f'Written register shift {shift:+d} semitones. '
        desc['tempo']=max(36,min(160,row['bpm']+(-10 if 'slower' in q else 10 if 'faster' in q else 0)))
        b.title=re.sub(r'^(?:Saxophone )+','',b.title)
        b.how=[h for h in b.how if not h.startswith('Articulation:')] + [f"Articulation: {o['pattern']}; {'accents added' if o['accent'] else 'no added accents'}; {desc['tempo']} BPM."]
        b.meta['sax_options']=copy.deepcopy(o);desc.update(sax_options=o,sax_level=level,level=level,sax_song_sel=sel,sax_snapshot=sc.snapshot(b))
        updated=wp.build_item(wp._player_of(plan),spec,desc);updated['reps']=row['reps'];updated['seconds']=round(updated['reps']*updated['pass_seconds']+(updated['reps']-1)*we.GAP_SECONDS,1)
        if all(updated[k]==row[k] for k in ('abc','bpm','reps','instrument')):return _reply(plan,session,'Already at those settings, or that revision is unsupported. No exercise changed.')
        new['items'][index]=updated;new['sax_selected_uid']=row['uid'];new['total_seconds']=round(wp._total(new['items']),1)
        if len(new['items'])==1:
            spec['song_sel']=sel;new['player']={k:getattr(p,k) for k in ('key','label','written_key','concert_key','offset','semitones')};new['level']=level
            if spec.get('single_song'):new['target_seconds']=new['total_seconds']
        assert all(i==index or new['items'][i]==r for i,r in enumerate(plan['items']))
        wp._commit(session,new,question)
        return _reply(new,session,f'Updated jazz exercise {index+1} only. '+lead+'Untargeted exercises, their repetitions and sidebar settings are preserved.')
    except (ValueError,KeyError) as exc:return _reply(plan,session,f'That jazz revision is unavailable: {exc}. No exercise or history changed.')
