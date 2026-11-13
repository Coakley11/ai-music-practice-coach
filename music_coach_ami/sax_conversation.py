"""Local, owner-scoped saxophone item revisions on the existing warmup history."""
import copy
import re
from dataclasses import asdict, replace
from fractions import Fraction
from music_coach_ami import warmup_plan as wp, warmup_engine as we, scale_pattern_harmony as sph


def snapshot(built):
    return {'notes':[asdict(n) for n in built.notes], 'bpm':built.bpm, 'title':built.title,
            'how':list(built.how), 'listen':list(built.listen), 'meta':copy.deepcopy(built.meta)}


def restore(data):
    return we.Built([we.Note(**n) for n in data['notes']], data['bpm'], data['title'], list(data['how']), list(data['listen']), copy.deepcopy(data['meta']))


def reply(plan, session, text):
    return wp._plan_response(plan, lead=text, session_ref=session, view=wp.history(session).get('view')) if plan else wp._simple(text)


def target(plan, question, session):
    q=question.lower(); rows=plan['items']; ref=wp.ref_from(q)
    mentions=re.findall(r'\b(?:exercise|item)\s+(\d+|one|two|three|four|five|six|seven|eight)\b',q)
    ordinals=re.findall(r'\b(first|second|third|fourth|fifth|sixth|seventh|eighth|last)\b(?=.{0,30}\b(?:exercise|item)\b)',q)
    if len(set(ordinals))>1:return None,'Name one exercise for this revision. No exercise changed.'
    if len(set(mentions))>1:return None,'Name one exercise for this revision. No exercise changed.'
    # Existing numeric parser handles digits; spoken cardinal numbers after item are also supported.
    words={'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8}
    match=re.search(r'\b(?:exercise|item)\s+('+'|'.join(words)+r')\b',q)
    if match: ref={'index':words[match[1]]}
    if ref.get('index'):
        found,err=wp._resolve_ref(rows,ref)
        return (found[0] if len(found)==1 else None),err
    # Exact supported title or interval name is safe only when unique.
    hits=[r for r in rows if r['title'].lower() in q]
    old_interval=re.search(r'change (?:the )?(seconds|thirds|fourths|fifths|sixths|sevenths|octaves) to',q)
    if old_interval: hits=[r for r in rows if r.get('sax_options',{}).get('interval')==old_interval[1] and r.get('sax_options',{}).get('recipe')=='intervals']
    elif ref.get('family'): hits=[r for r in rows if r['family']==ref['family']]
    if len(hits)==1: return hits[0],''
    if len(hits)>1: return None,'That name matches more than one exercise. Which exercise number do you mean?'
    if len(rows)==1: return rows[0],''
    view=wp.history(session).get('view') or {}
    if re.search(r'\b(?:this|that) (?:exercise|one)|\bit\b',q):
        uid=plan.get('sax_selected_uid')
        if view.get('mode')=='item': return rows[view['index']],''
        if uid: return next((r for r in rows if r['uid']==uid),None),''
    return None,'Which exercise number or unique exercise name do you mean? No exercise changed.'


def _fresh_chart(question, session, ctx):
    from music_coach_ami import sax_technique as sx
    q=question.lower(); req=wp.parse_request(question); page,_=wp._page_values(question,session,ctx)
    p,why,facts=wp.resolve_player(req,session,page,req['key'] or getattr(page,'current_practice_key','') or 'C')
    if p is None or p.key not in sx.SAX: return None
    if facts.get('sax_assumed'): return wp._simple('Choose soprano, alto, tenor or baritone saxophone first.')
    if re.search(sx.UNSUPPORTED,q): return wp._simple('That saxophone technique is outside the verified profile. No exercise changed.')
    song,why_song=wp.ws.read_song(page)
    if 'bridge' in q and song and not any('bridge' in name.lower() for name in song['order']):
        return reply(wp.current(session),session,'A bridge section is not verified in this chart. Name an actual chart section; no exercise changed.')
    o=sx.options(q);o['recipe']='intervals';o['chart_intervals']=True
    if not re.search(r'\b('+'|'.join(we.INTERVALS)+r')\b',q): o.update(interval='sixths',direction='alternating')
    o['chart_approach']='chromatic' in q
    req.update(families=['chord_tones'],sax_settings=o,sax_single_song=not bool(re.search(r'warm.?up|routine|minutes?',q)))
    if 'advanced' in q or 'buster' in q:req['level']='Advanced'
    return wp.create(question,session,ctx,request=req)


def _rhythm(built, question, level):
    q=question.lower()
    if level=='Beginner': raise we.WarmupUnavailable('mixed rhythm requires Intermediate or Advanced')
    if built.meta.get('sax_chart'): raise we.WarmupUnavailable('pitch-preserving chart rhythm displacement is not verified; ask for an explicit eighth- or sixteenth-note chart cell')
    # Replace each four equal attacks with a 2:1:1:4 subdivision in sixteenth units.
    # Eighth + sixteenth + sixteenth + quarter is two beats; all pitch/mark identities survive.
    unit=next((u for u in ('whole','half','quarter','eighth','sixteenth') if re.search(r'\b'+u+r'[ -]notes?\b',q)),None)
    pattern=[unit]*4 if unit else ['eighth','sixteenth','sixteenth','quarter']
    notes=[];i=0
    for n in built.notes:
        notes.append(n if n.rest else replace(n,dur=pattern[i%4]))
        if not n.rest:i+=1
    if we.total_beats(notes)%4: raise we.WarmupUnavailable('that exact pitch count and rhythm do not form complete bars; no rests or pitches were added')
    built.notes=notes


def _retain_shape(new, old):
    """A pitch edit keeps the old event grid and marks; never silently truncate."""
    values=[n for n in new.notes if not n.rest]
    old_values=[n for n in old.notes if not n.rest]
    if len(values)!=len(old_values):
        if not values: raise we.WarmupUnavailable('no pitch pattern is available')
        values=[values[i%len(values)] for i in range(len(old_values))]
    it=iter(values);notes=[]
    for n in old.notes:
        if n.rest:notes.append(n)
        else:
            pitch=next(it);notes.append(replace(n,spelled=pitch.spelled,octave=pitch.octave))
    new.notes=notes


def handle(question, session, ami_ctx=None):
    from music_coach_ami import sax_technique as sx, sax_chart_intervals as sci
    q=question.lower().strip(' .!?'); plan=wp.current(session)
    fresh=bool(re.search(r'\b(?:give|generate|write|create|build|want|need)\b|^make (?:me|a |an )',q))
    interval_word=bool(re.search(r'\b(?:'+'|'.join(we.INTERVALS)+r'|wide intervals)\b',q))
    if fresh and interval_word and re.search(r'\b(?:over|chords|chord tones|bridge|(?:the|actual|chord) changes)\b',q) and not re.search(r'pentatonic|dorian|melodic minor|harmonic minor|\b(?:lick|line|phrase)\b',q):
        return _fresh_chart(question,session,ami_ctx)
    if fresh and re.search(r'sax(?:ophone)? technique warm.?up',q):
        req=wp.parse_request(question);page,_=wp._page_values(question,session,ami_ctx)
        p,_,facts=wp.resolve_player(req,session,page,req['key'] or getattr(page,'current_practice_key','') or 'C')
        if p and p.key in sx.SAX:
            o=sx.options(q);o.update(recipe='intervals',routine=True,intervals_from_plan=True)
            req.update(families=['intervals'],intervals=['thirds','fifths','sixths','octaves'],sax_settings=o)
            return wp.create(question,session,ami_ctx,request=req)
    if not plan or not plan['spec'].get('sax') or plan['spec'].get('single') or fresh:return None
    if q in ('undo','undo that','redo','redo that'):return None
    explain=bool(re.match(r'explain|why',q))
    revision=bool(re.match(r'(?:now |please )?(?:make|change|keep|use|add|slur|accent|move|adapt)',q))
    if not explain and not revision:return None
    if re.search(r'\b(?:whole|entire|all exercises)\b',q):
        if any(d.get('sax_snapshot') for d in plan['spec']['items']):return reply(plan,session,'After individual edits, name an exercise for further musical changes. Whole-plan musical rewrites are not verified for mixed item settings. No exercise changed.')
        return None
    row,why=target(plan,question,session)
    if row is None:return reply(plan,session,why or 'Choose an exercise number. No exercise changed.')
    if explain:
        text=sci.explain(row) if row.get('meta',{}).get('sax_chart') else f"Exercise {wp._index_of(plan,row['uid'])}: {row['title']}; {row.get('instrument_label',plan['player']['label'])}, {row['item_level']}, {row['bpm']} BPM, {row['reps']} repetitions. Written notes: {', '.join(row['written_notes'])}. "+' '.join(row['how'])
        return reply(plan,session,text)
    if re.search(sx.UNSUPPORTED,q):return reply(plan,session,'Unsupported saxophone technique; no exercise or history changed.')
    req=wp.parse_request(question)
    if req.get('unverified') or req.get('instrument_word') and req['instrument_word']!='saxophone':return reply(plan,session,'Choose a verified saxophone for this item. No exercise changed.')
    new=copy.deepcopy(plan);spec=new['spec'];index=wp._index_of(plan,row['uid'])-1
    desc=next(d for d in spec['items'] if d['uid']==row['uid'])
    old_options=copy.deepcopy(row.get('sax_options',spec['sax']));o=sx.options(q,old_options)
    if row.get('meta',{}).get('sax_chart'):
        o['recipe']='intervals'
        if 'chromatic' in q:o['chart_approach']=True
    desc['sax_options']=o
    level=row['item_level'];who=row.get('instrument',plan['player']['key'])
    p=we.make_player(who,spec['concert_key'])
    if not row.get('sax_snapshot'):return reply(plan,session,'This stored item predates note snapshots. Generate a fresh saxophone warmup before targeting it; no exercise changed.')
    built=restore(row['sax_snapshot']);lead=''
    try:
        sections=spec.get('song',{}).get('order',[]) if spec.get('song') else []
        section=wp.ws.find_section(sections,q) if sections else ''
        section_requested=bool(section and re.search(r'use|instead|switch|change',q))
        interval_change=any(o.get(k)!=old_options.get(k) for k in ('recipe','interval','direction'))
        harder=bool(re.search(r'harder|more difficult',q) and 'rhythm' not in q)
        easier='easier' in q
        pitch_edit=interval_change or harder or easier or o.get('chart_approach')!=old_options.get('chart_approach')
        if (harder or easier) and built.meta.get('sax_chart'):
            level=wp.LEVEL_UP.get(level,level) if harder else wp.LEVEL_DOWN.get(level,level)
            if harder and level==row['item_level']:o['direction']='alternating' if o['direction']!='alternating' else 'descending'
        elif harder or easier:
            level=wp.LEVEL_UP.get(level,level) if harder else wp.LEVEL_DOWN.get(level,level)
            if harder and level==row['item_level']:
                o.update(recipe='coordination',direction='alternating' if o['direction']!='alternating' else 'descending')
        desc['sax_level']=level
        if 'slower' in q or 'faster' in q:
            desc['tempo']=max(36,min(160,row['bpm']+(-10 if 'slower' in q else 10)))
        else:desc['tempo']=row['bpm']
        if section_requested or pitch_edit:
            if spec.get('song'):
                if not built.meta.get('sax_chart'):
                    # Convert only an explicitly targeted canonical chord-tone item.
                    if row['family']!='chord_tones' or not interval_word:
                        raise we.WarmupUnavailable('that pitch transformation is not verified for this chart exercise family')
                    o.update(chart_intervals=True,recipe='intervals')
                sel=copy.deepcopy(desc.get('sax_song_sel',spec['song_sel']))
                if section_requested:sel.update(section=section,bars=None)
                desc['sax_song_sel']=sel
                rebuilt=sci.build(p,level,spec['song'],sel['section'],tuple(sel['bars']) if sel.get('bars') else None,o)
                # Interval-only changes retain the same event grid and all articulation.
                if not section_requested and not harder and not easier and o.get('chart_approach')==old_options.get('chart_approach'):
                    if len(rebuilt.notes)!=len(built.notes):raise we.WarmupUnavailable('the new interval would change event count')
                    rebuilt.notes=[replace(a,dur=b.dur,art=b.art,slur=b.slur) for a,b in zip(rebuilt.notes,built.notes)]
                else:
                    rebuilt=sx.decorate(rebuilt,o)
                built=rebuilt
                if section_requested:
                    lead=f'Using {section} for this item. '
                    if len(plan['items'])==1:spec['song_sel']=copy.deepcopy(sel)
            else:
                o.pop('pitches',None);o.pop('intervals_from_plan',None)
                rebuilt=sx.built(p,level,row['tonic'],row['tonality'],o,variant=int(row['params'].get('variant') or 0))
                _retain_shape(rebuilt,built);built=rebuilt
        if 'rhythm' in q:
            _rhythm(built,q,level);o['mixed']=not any(re.search(r'\b'+u+r'[ -]notes?\b',q) for u in we._DUR_BEATS)
        if re.search(r'register|move.*lower',q) and o.get('register')!=old_options.get('register'):
            from music_coach_ami.flexible_single import _window
            lo,hi=_window(p,level,o['register']);values=[n.midi for n in built.notes if not n.rest]
            shifts=(-12,-24,0,12,24) if o['register']=='low' else (0,12,-12,24,-24)
            shift=next((v for v in shifts if all(lo<=m+v<=hi for m in values)),None)
            if shift is None or o['recipe']=='transition' and shift:raise we.WarmupUnavailable('the same passage cannot fit that register by a whole-octave shift')
            built.notes=[n if n.rest else replace(n,octave=n.octave+shift//12) for n in built.notes]
            built.meta['window']=[lo,hi]
            if built.meta.get('sax_chart'):
                for r in built.meta['chart_records']:r['midi']+=shift
            lead+=f'Whole-octave register shift {shift:+d} semitones. '
        if 'adapt' in q or re.search(r'change.*(?:alto|tenor|soprano|baritone)',q):
            page,_=wp._page_values(question,session,ami_ctx)
            target_p,_,_=wp.resolve_player(req,session,page,spec['concert_key'])
            if target_p is None or target_p.key not in sx.SAX:raise we.WarmupUnavailable('choose a verified saxophone')
            if o['recipe']=='transition' and target_p.key!=p.key:raise we.WarmupUnavailable('a fixed written register-boundary cell needs a fresh exercise for another saxophone')
            from music_coach_ami.flexible_single import _window
            lo,hi=(target_p.window(level) if o.get('register','middle')=='middle' else _window(target_p,level,o['register']));delta=target_p.offset-p.offset
            values=[n.midi+delta for n in built.notes if not n.rest]
            shift=next((v for v in (0,-12,12,-24,24) if all(lo<=m+v<=hi for m in values)),None)
            if shift is None:raise we.WarmupUnavailable('the same sounding passage cannot fit the target saxophone by a whole-octave shift')
            # Shared spelled transposition preserves interval letter structure.
            converted=[]
            for n in built.notes:
                if n.rest:converted.append(n);continue
                name=sph.transpose_spelled(n.spelled,delta);m=n.midi+delta+shift
                converted.append(replace(n,spelled=name,octave=sph.octave_for(name,m),chord=''))
            built.notes=converted;p=target_p;desc['sax_instrument']=p.key;built.meta['window']=[lo,hi]
            if built.meta.get('sax_chart'):
                segs,_,_=wp.ws.build_timeline(spec['song'],built.meta['chart_section'],tuple(built.meta['chart_bars']),p.offset,p.semitones)
                for i,r in enumerate(built.meta['chart_records']):
                    seg=next(s for s in segs if s.src_bar==r['bar'] and s.beat<=r['beat']<s.beat+s.beats)
                    r.update(midi=built.notes[i].midi,name=built.notes[i].spelled,written_chord=seg.info['symbol_written'])
                    if Fraction(r['beat'])==seg.beat:built.notes[i].chord=seg.info['symbol_written']
            if not built.meta.get('sax_chart'):
                tonic,mode=we.practical_key(*we.split_key(p.written_key))
                tonic,mode=wp._shift_key(tonic,mode,int(desc['params'].get('variant') or 0))
                built.title=built.title.replace(row['key'],we.key_text(tonic,mode))
                pitched=[n for n in built.notes if not n.rest]
                if o['recipe']=='chromatic' and pitched:
                    built.title=re.sub(r'written [A-G][#b]?-?\d+',f'written {pitched[0].spelled}{pitched[0].octave}',built.title)
            lead+=f'Adapted this item for {p.label}; sounding octave shift {shift:+d} semitones. '
        marks=any(o.get(k)!=old_options.get(k) for k in ('pattern','accent'))
        if marks:
            built=sx.decorate(built,o)
        built.title=re.sub(r'^(?:Saxophone )+', 'Saxophone ', built.title)
        # Explain current settings, never leave a stale tempo/pitch instruction after an edit.
        if not built.meta.get('sax_chart'):
            built.how=[f"Develop {o['recipe']} with the stored pitch pattern, {o['direction']} motion, {o['pattern']} articulation and {'added' if o['accent'] else 'no added'} accents. This is a key-based technique item, not a chord-following line.", 'Keep air steady; slurs connect without re-tonguing. Rest when coordination or tone deteriorates. No alternate fingerings or tonguing playback are verified.']
        built.how=[f"Stored {p.label} item: {level}; follow the rendered pitches, rhythm and articulation at {desc['tempo']} BPM."] + [h for h in built.how if not h.startswith('Stored ')]
        built.meta['sax_options']=copy.deepcopy(o)
        desc['params']['sax_recipe']=o['recipe']
        if desc['family']=='intervals':desc['params']['interval']=o['interval']
        if desc['family']=='articulation':desc['params']['pattern']=o['pattern']
        desc['sax_snapshot']=snapshot(built)
        # Every requested result passes the same render/range/harmony checks as creation.
        newrow=wp.build_item(wp._player_of(plan),spec,desc)
        newrow['reps']=row['reps'];newrow['seconds']=round(newrow['reps']*newrow['pass_seconds']+(newrow['reps']-1)*we.GAP_SECONDS,1)
        if all(newrow[k]==row[k] for k in ('abc','bpm','reps','instrument')):return reply(plan,session,'Already at those settings, or that revision is unsupported. No exercise or history changed.')
        new['items'][index]=newrow;new['sax_selected_uid']=row['uid'];new['total_seconds']=round(wp._total(new['items']),1)
        if len(new['items'])==1 and spec.get('single_song'):
            new['player']={k:getattr(p,k) for k in ('key','label','written_key','concert_key','offset','semitones')}
            new['level']=level
            new['target_seconds']=new['total_seconds']
        for j,r in enumerate(plan['items']):
            if j!=index and new['items'][j]!=r:raise AssertionError('an untargeted row changed')
        wp._commit(session,new,question)
        return reply(new,session,f"Updated exercise {index+1} only. "+lead+'All other exercises and repetitions are preserved exactly. The total duration reflects this edit.')
    except (ValueError,KeyError) as exc:
        return reply(plan,session,f'That item revision is unavailable: {exc}. No exercise or history changed.')

