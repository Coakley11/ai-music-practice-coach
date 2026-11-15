"""Bounded short-cell transformations using AMI's existing writer, profiles and history.

Keys are concert keys. Degree movement and literal key transposition are distinct.
No transport, global Practice Key, instrument selection or second history is owned here.
"""
from __future__ import annotations
import copy
import re
from fractions import Fraction
from music_coach_ami import warmup_engine as we, warmup_plan as wp, scale_pattern_harmony as sph

_WORDS = {k:int(v) for k,v in wp._NUMBER_WORDS.items() if v <= 12}
_COUNT = re.compile(r"(?<![\d.])\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)[ -]notes?\b")
_PLAIN = (0,1,2,4,5,6,7,9,10,11,12,14)
_BLUES = (0,3,5,6,7,10)
_SONG = re.compile(r"\b(?:song|verse|chorus|bridge|chord changes|every chord|over\s+\w+)\b")
_UNSUPPORTED = re.compile(r"\b(?:ties?|tied|triplets?|tuplets?|dotted|offbeat|swing|custom rests?|syncopation|harmonic minor|melodic minor|dorian|pentatonic|left hand|both hands)\b")


def _player_reason(why):
    return (why or 'Choose an instrument and, for saxophone, its type').replace('warmups','exercises').replace('warmup','exercise').replace('Slice 1 covers','Verified profiles cover')


def _selection(session):
    from practice_setup_globals import GLOBAL_INSTRUMENT_KEY
    from instrument_transposition import SELECTED_TRANSPOSING_INSTRUMENT_KEY
    return [str(session.get(GLOBAL_INSTRUMENT_KEY) or session.get('instrument') or ''),str(session.get(SELECTED_TRANSPOSING_INSTRUMENT_KEY) or '')]


def _count(q):
    m=_COUNT.search(q)
    return (int(m[1]) if m[1].isdigit() else _WORDS[m[1]]) if m else None


def _degree_semitone(degree, mode):
    steps=we._STEPS[mode]
    return 12*(degree//7)+steps[degree%7]


def _template(count, style, mode):
    if not 1 <= count <= 12:
        raise we.WarmupUnavailable('ask for one to twelve attacks per cell')
    if style=='blues':
        return [], [_BLUES[i%6]+12*(i//6) for i in range(count)]
    degrees=[2*i for i in range(count)] if style=='jazz' else list(_PLAIN[:count])
    return degrees,[_degree_semitone(d,mode) for d in degrees]


def _practical(player, prefs, *, use_preference=False):
    import backing_key_cycle as kc
    tonic,mode=we.split_key(player.written_key)
    preferred=kc.spell_key_tonic(sph.pc_of(tonic),'minor' if mode=='natural minor' else 'major',prefs)
    # Explicit single-key spelling wins; key itineraries honor Playback preferences
    # in both concert and written domains, within the existing writer's limits.
    return (*we.practical_key(preferred if use_preference else tonic,mode), player.written_key)


def _note(name, midi, spec, slur=0):
    return we.Note(name,sph.octave_for(name,midi),spec['rhythm'],spec['articulation'],slur)


def _chromatic_name(tonic, mode, offset, style, prefs):
    scale=we.scale_spelling(tonic,mode)
    pc=(sph.pc_of(tonic)+offset)%12
    if style=='blues':
        degree={0:0,3:2,5:3,6:4,7:4,10:6}[offset%12]
        name=sph._spell('CDEFGAB'.index(tonic[0])+degree,pc)
        if offset%12==6:
            import backing_key_cycle as kc
            name=kc.spell_key_tonic(pc,'major',prefs)
        return name
    return next((n for n in scale if sph.pc_of(n)==pc),None) or __import__('music_theory').spell_note_in_key(pc,we.key_token(tonic,mode))


def _parts_abc(parts, title):
    headers=[];bodies=[]
    for index,part in enumerate(parts):
        lines=part.splitlines();ki=next(i for i,l in enumerate(lines) if l.startswith('K:'))
        if index==0:
            headers=[('T:'+title if l.startswith('T:') else l) for l in lines[:ki+1]]
        body='\n'.join(lines[ki+1:]).strip()
        if index<len(parts)-1:body=body.replace('|]','|')
        bodies.append(('['+lines[ki]+'] ' if index else '')+body)
    return '\n'.join(headers+bodies)


def build(spec):
    """Generate all requested events or refuse before any session mutation."""
    from music_coach_ami import flexible_single as fs
    import backing_key_cycle as kc
    if spec['level'] not in we.LEVELS:raise we.WarmupUnavailable('choose Beginner, Intermediate or Advanced; no range is inferred from an unknown level')
    player=we.make_player(spec['instrument'],spec['concert_key'])
    tonic,mode,requested_written=_practical(player,spec['spelling_prefs'])
    lo,hi=player.window(spec['level']);how=[];cells=[];parts=[];all_notes=[]
    if spec['family']=='intervals':
        gap=we.INTERVALS[spec['interval']]
        cover=spec.get('coverage',7)
        while cover:
            need=cover-1+gap
            run=we.build_run(tonic,mode,lo,hi,steps=need)
            if len(run)==need+1:break
            if spec.get('require_full'):raise we.WarmupUnavailable('the complete requested interval traversal exceeds the selected level window')
            cover-=1
        if not cover:raise we.WarmupUnavailable('even a complete interval pair does not fit this key and selected level window')
        roots=list(range(cover))
        direction=spec['direction']
        pairs=[(i,i+gap) for i in roots] if direction!='descending' else [(i+gap,i) for i in reversed(roots)]
        if direction=='up and down':pairs += [(i+gap,i) for i in reversed(roots)]
        for cell_index,(a,b) in enumerate(pairs):
            notes=[we.n_(run,d,spec['rhythm'],spec['articulation'],cell_index+1 if spec.get('slur') else 0) for d in (a,b)]
            cells.append({'degrees':[a,b],'written_midi':[n.midi for n in notes]})
            all_notes.extend(notes)
        all_notes=we._fill_bar(all_notes)
        title=spec['interval'].capitalize()+' - '+we.key_text(tonic,mode)+' ('+direction+')'
        how=[f"{cover} starting degree(s), complete diatonic {spec['interval']}; {direction}. No individual pitch is clamped.",
             f"The notes fit the selected {spec['level']} written range. Concert pitches follow {player.label} transposition."]
        how.append(f"Each {we.INTERVAL_SINGULAR[spec['interval']]} spans {gap+1} scale degrees, counting both endpoints; its quality follows the selected scale.")
        if cover<spec.get('coverage',7):how.append('This explicitly shorter study uses the starting degrees that fit the selected comfort window; it is not a full seven-degree traversal.')
    else:
        offsets=spec['offsets'];degrees=spec['degrees'];step=spec['step']
        if len(offsets)!=spec['count']:raise we.WarmupUnavailable('cell count and stored attacks disagree')
        positions=[0]
        if step=='diatonic':
            if not degrees:raise we.WarmupUnavailable('a chromatic blues cell has no unique diatonic degree mapping; use literal key transposition instead')
            positions=list(range(8 if spec.get('octave_endpoint') else 7))
            if spec['direction']=='descending':positions.reverse()
            elif spec['direction']=='up and down':positions += positions[-2::-1]
        if step in ('single','diatonic'):
            if degrees:
                need=max(positions)+max(degrees)
                run=we.build_run(tonic,mode,lo,hi,steps=need)
                if len(run)!=need+1:raise we.WarmupUnavailable('the complete cell/degree traversal does not fit this key and selected level; choose fewer starting degrees, another key or an appropriate selected level')
                for cell_index,pos in enumerate(positions):
                    notes=[we.n_(run,pos+d,spec['rhythm'],spec['articulation'],cell_index+1 if spec.get('slur') and spec['count']>1 else 0) for d in degrees]
                    cells.append({'starting_degree':pos+1,'concert_key':spec['concert_key'],'written_key':we.key_token(tonic,mode),'written_midi':[n.midi for n in notes]})
                    all_notes.extend(we._fill_bar(notes))
            else:
                candidates=[m for m in range(lo,hi+1) if m%12==sph.pc_of(tonic) and all(lo<=m+d<=hi for d in offsets)]
                if not candidates:raise we.WarmupUnavailable('the complete blues cell does not fit the selected level window')
                notes=[_note(_chromatic_name(tonic,mode,d,spec['style'],spec['spelling_prefs']),candidates[0]+d,spec,1 if spec.get('slur') and spec['count']>1 else 0) for d in offsets]
                cells=[{'concert_key':spec['concert_key'],'written_key':we.key_token(tonic,mode),'written_midi':[n.midi for n in notes]}]
                all_notes=we._fill_bar(notes)
        else:
            if spec['cycle']=='explicit':
                keys=list(spec['keys'])
                if spec['direction']=='descending':keys.reverse()
            else:
                delta={'half':1,'whole':2,'fourths':5}[spec['cycle']]
                if spec['direction']=='descending':delta=-delta
                length=12 if spec['cycle']=='fourths' else kc.cycle_sequence_length(interval=abs(delta))
                keys=[kc.cycle_concert_practice_key(spec['concert_key'],semitones=i*delta,spelling_prefs=spec['spelling_prefs']) for i in range(length)]
            if spec['direction']=='up and down':keys += keys[-2::-1]
            previous=None
            for cell_index,key in enumerate(keys):
                p=we.make_player(spec['instrument'],key);t,m,requested=_practical(p,spec['spelling_prefs'],use_preference=True)
                candidates=[v for v in range(lo,hi+1) if v%12==sph.pc_of(t) and all(lo<=v+d<=hi for d in offsets)]
                if not candidates:raise we.WarmupUnavailable(f'the entire cell in concert {key} cannot fit the selected level; no keys or notes were removed')
                desired=candidates[0] if previous is None else previous+((sph.pc_of(t)-previous)%12 if spec['direction']!='descending' else -((previous-sph.pc_of(t))%12))
                if previous is not None and spec['cycle']=='fourths':desired=previous+(-5 if spec['direction']=='descending' else 5)
                root=min(candidates,key=lambda v:abs(v-desired));previous=root
                notes=[_note(_chromatic_name(t,m,d,spec['style'],spec['spelling_prefs']),root+d,spec,cell_index+1 if spec.get('slur') and spec['count']>1 else 0) for d in offsets]
                notes=we._fill_bar(notes)
                built=we.Built(notes,spec['bpm'],f"Cell in concert {key}",[],[],{'window':[lo,hi]})
                part=fs.package({**spec,'concert_key':key},p,built,t,m,allowed_pcs={sph.pc_of(n.spelled) for n in notes if not n.rest})
                cells.append({'concert_key':key,'written_key':we.key_token(t,m),'requested_written_key':requested,'octave_adjustment':root-desired,'written_midi':part['items'][0]['written_midi'],'checks':part['items'][0]['checks']})
                parts.append(part['items'][0]['abc']);all_notes.extend(notes)
        title=f"{spec['count']}-note {spec['style']} cell - {step} ({spec['direction']})"
        how=[f"Exactly {spec['count']} pitched attacks in each cell. Repeated pitches count as attacks; separating/padding rests do not. No ties are generated.",
             'Diatonic movement preserves scale-degree relationships; key traversal preserves the cell\'s chromatic intervals.',
             f"The notes fit the selected {spec['level']} written range. This is a standalone study, not a song-harmony adaptation."]
        how.append(('Base-cell scale degrees: '+'-'.join(str(d+1) for d in degrees)+'.') if degrees else 'Minor-blues semitone offsets above the tonic: '+', '.join(str(d) for d in offsets)+'.')
        if step=='diatonic':how.append(f"{len(positions)} cells; starting degrees "+', '.join(str(i+1) for i in positions)+'. Octave continuation is explicit; no cell is shortened.')
        if step=='keys':
            how.append('Concert key order: '+', '.join(c['concert_key'] for c in cells)+'.')
            if any(c['octave_adjustment'] for c in cells):how.append('Whole-cell octave repositioning keeps the requested key order playable; every internal interval is preserved.')
            if any(we.split_key(c['requested_written_key'])[0]!=we.split_key(c['written_key'])[0] for c in cells):how.append('The existing writer uses equivalent practical written key spellings where a theoretical key would require unsupported double accidentals.')
    built=we.Built(all_notes,spec['bpm'],title,how,[],{'window':[lo,hi]})
    if we.key_token(tonic,mode)!=requested_written:
        built.how.append(f'Requested written key {requested_written} is displayed as the equivalent practical key {we.key_token(tonic,mode)}.')
    plan=fs.package(spec,player,built,tonic,mode,allowed_pcs={sph.pc_of(n.spelled) for n in all_notes if not n.rest})
    plan['player']['written_key']=cells[0]['written_key'] if parts else we.key_token(tonic,mode)
    if parts:plan['player']['concert_key']=cells[0]['concert_key']
    row=plan['items'][0];row['cells']=cells
    if parts:row['abc']=_parts_abc(parts,title)
    if spec.get('slur'):row['how'].append('Slur each complete multi-attack cell; a single attack stays unmarked. Slurs do not join separate cells.')
    if spec['family']=='lick' and any(len(c['written_midi'])!=spec['count'] for c in cells):raise we.WarmupUnavailable('exact cell-count verification failed')
    return plan


def response(plan,session,lead=''):
    from music_coach_ami import flexible_single as fs
    state=wp._state(session);original=bool(state and state['view'].get('mode')=='original')
    shown=plan.get('original',plan) if original else plan
    row=shown['items'][0]
    r=fs._reply(lead+'**'+row['title']+'**. '+shown['player']['label']+', '+shown['spec']['level']+' study. Concert key '+shown['player']['concert_key']+'; written key '+shown['player']['written_key']+f". Tempo {row['bpm']} BPM.",shown,session)
    r.source_solver='AdaptiveLickCell'
    r.diagnostics.update(note_name_rows=copy.deepcopy(row['note_name_rows']),adaptive_cell=True,adaptive_original_view=original)
    return r


def _apply(q,spec):
    from music_coach_ami import flexible_single as fs
    if _UNSUPPORTED.search(q):raise we.WarmupUnavailable('this exercise supports straight note values and untied attacks; that rhythm, scale or hand instruction needs a separate supported generator')
    if re.search(r'\bslur(?:s|red)?\b',q):spec['slur']=not bool(re.search(r'\b(?:no|remove|without)\s+slur',q))
    count=_count(q)
    if count is not None and count!=spec['count']:
        spec['count']=count;spec['degrees'],spec['offsets']=_template(count,spec['style'],spec['mode'])
    if 'original lick' in q:
        spec['degrees']=list(spec['seed_degrees']);spec['offsets']=list(spec['seed_offsets']);spec['count']=len(spec['offsets'])
        spec['mode']=spec.get('seed_mode',spec['mode']);spec['concert_key']=spec.get('seed_key',spec['concert_key'])
    if 'harder' in q or 'more difficult' in q:
        indices=[];a,b=0,spec['count']-1
        while a<=b:
            indices.append(a)
            if a!=b:indices.append(b)
            a+=1;b-=1
        spec['offsets']=[spec['offsets'][i] for i in indices]
        if spec['degrees']:spec['degrees']=[spec['degrees'][i] for i in indices]
        spec['articulation']='accent'
    if re.search(r'\bin thirds\b',q) and spec['family']=='lick':
        if not spec['degrees']:raise we.WarmupUnavailable('choose a diatonic cell before asking for a thirds pattern')
        spec['degrees']=[2*i for i in range(spec['count'])];spec['offsets']=[_degree_semitone(d,spec['mode']) for d in spec['degrees']]
    named=re.search(r'\b([a-g][#b]?)\s+(major|minor)\b',q)
    if named:
        spec['concert_key']=named[1][0].upper()+named[1][1:]+('m' if named[2]=='minor' else '')
        spec['mode']='natural minor' if named[2]=='minor' else 'major'
        if spec['degrees']:spec['offsets']=[_degree_semitone(d,spec['mode']) for d in spec['degrees']]
    if spec['family']=='intervals':
        interval=next((name for name in we.INTERVALS if re.search(r'\b'+name+r'\b',q)),None)
        if interval:spec['interval']=interval
    explicit=re.search(r'\bin\s+([a-g][#b]?(?:\s*,|\s+then\b).*)',q)
    keys=re.findall(r'\b([a-g](?:#|b)?)(?=\s*(?:,|then\b|and\b|$))',explicit[1]) if explicit else []
    if len(keys)>1:
        spec.update(step='keys',cycle='explicit',keys=[k[0].upper()+k[1:] for k in keys],direction='ascending',concert_key=keys[0][0].upper()+keys[0][1:])
    elif re.search(r'twelve keys|12 keys|half[ -]steps?|semitones?|whole[ -]steps?|circle of fourths',q):
        spec.update(step='keys',cycle='fourths' if 'fourths' in q else 'whole' if re.search(r'whole[ -]steps?',q) else 'half')
    elif re.search(r'(?:through|all seven|whole).*scale|all seven degrees|through.*degrees',q):
        spec['step']='diatonic';spec['octave_endpoint']=bool(re.search(r'whole.*scale',q)) and 'seven' not in q
    if re.search(r'descending|\bdown(?:wards?)?\b',q):
        if spec['step']=='single' and spec['direction']!='descending':
            spec['offsets'].reverse();spec['degrees'].reverse()
        spec['direction']='descending'
    elif re.search(r'ascending|\bup(?:wards?)?\b',q):
        if spec['step']=='single' and spec['direction']=='descending':spec['offsets'].reverse();spec['degrees'].reverse()
        spec['direction']='ascending'
    if re.search(r'up and down|back down',q):spec['direction']='up and down'
    tempo=re.search(r'\b(\d+)\s*bpm\b|(?:tempo(?: of| to)?|at)\s+(\d+)',q)
    if tempo and not 36<=int(tempo[1] or tempo[2])<=160:raise we.WarmupUnavailable('choose a tempo from 36 to 160 BPM')
    if not tempo and ('slower' in q or 'faster' in q):spec['bpm']=max(36,min(160,spec['bpm']+(-10 if 'slower' in q else 10)))
    fs.controls(spec,q)


def handle(question,session,ami_ctx=None,*,bare_only=False):
    if session is None:return None
    from music_coach_ami import flexible_single as fs
    import backing_key_cycle as kc
    q=question.lower().strip(' .!?').replace('-sharp','#').replace('-flat','b')
    plan=wp.current(session);active=bool(plan and plan['spec'].get('adaptive_cell'))
    bare=bool(re.search(r'\b(?:give|generate|write|create|build|show)\b',q) and re.search(r'\b(?:thirds|fourths|fifths|sixths|sevenths|octaves|intervals)\b',q) and not re.search(r'lick|warmup|warm-up|routine|minutes?|scale[ -]pattern|pentatonic|song|verse|chorus|bridge|over\b|jazz|finger|sax',q))
    if bare_only and not bare:return None
    if not bare_only and bare:return None
    fresh=not bare_only and bool(re.search(r'\b(?:give|generate|write|create|build|want|need)\b',q)) and 'lick' in q and (_count(q) is not None or bool(re.search(r'\d+(?:[./]\d+)?[ -]notes?',q)) or bool(re.search(r'through|twelve|12 keys|half.step|whole.step|circle',q)))
    if not fresh and not bare and not active:return None
    if not fresh and not bare:
        if q in ('undo','undo that','redo','redo that'):
            state=wp._state(session);target=state['cursor']+(-1 if q.startswith('undo') else 1)
            if not 0<=target<len(state['versions']):return response(plan,session,'There is no version to restore. ')
            state['cursor']=target;state['view']={'mode':'plan','index':0}
            return response(wp.current(session),session,'Restored the exact stored version. ')
        if re.search(r'\bshow.*(?:first|original).*lick',q):
            wp._state(session)['view']={'mode':'original','index':0};return response(plan,session,'Read-only first-lick snapshot. ')
        if re.fullmatch(r'(?:explain|why)(?: the)?(?: pattern| exercise| lick| sequence| these notes)?',q):
            return response(plan,session,'Read-only explanation: '+ ' '.join((plan.get('original',plan) if wp._state(session)['view'].get('mode')=='original' else plan)['items'][0]['how'])+' ')
        if not re.match(r'(?:now |please )?(?:make|change|use|add|move|transpose|take|do|play|slower|faster)',q):return None
    try:
        if re.search(r'\d+[./]\d+[ -]note|(?<!\w)-\d+[ -]note',q):raise we.WarmupUnavailable('the attack count must be an integer')
        if _SONG.search(q):raise we.WarmupUnavailable('I cannot adapt this exact cell to song harmony yet; choose a standalone key or scale traversal')
        if fresh or bare:
            req=wp.parse_request(question.replace('-sharp','#').replace('-flat','b'))
            page,_=wp._page_values(question,session,ami_ctx)
            named=re.search(r'\b([a-g][#b]?)\s+(major|minor)\b',q)
            key=req['key'] or ((named[1][0].upper()+named[1][1:]+('m' if named[2]=='minor' else '')) if named else '') or getattr(page,'current_practice_key','') or (ami_ctx or {}).get('display_key') or 'C'
            player,why,facts=wp.resolve_player(req,session,page,key)
            if player is None or facts.get('sax_assumed'):raise we.WarmupUnavailable(_player_reason(why))
            if req.get('unverified'):raise we.WarmupUnavailable('that instrument has no verified profile for this study')
            level=str(session.get('level') or getattr(page,'level','') or (ami_ctx or {}).get('level') or 'Intermediate').capitalize()
            mode=we.split_key(key)[1];count=2 if bare else _count(q) or 4
            style='interval' if bare else 'blues' if 'blues' in q else 'jazz' if 'jazz' in q else 'diatonic'
            degrees,offsets=_template(count,'major' if bare else style,mode)
            spec={'adaptive_cell':True,'single':True,'instrument':player.key,'concert_key':key,'level':level,'family':'intervals' if bare else 'lick','mode':mode,'style':style,'count':count,'degrees':degrees,'offsets':offsets,'seed_degrees':list(degrees),'seed_offsets':list(offsets),'seed_key':key,'seed_mode':mode,'selection_anchor':_selection(session),'step':'intervals' if bare else 'single','cycle':'half','keys':[],'direction':'up and down' if bare else 'ascending','register':'middle','buster':False,'quality':'major','rhythm':'quarter' if level=='Beginner' else 'eighth','articulation':'','slur':False,'bpm':72,'reps':1,'spelling_prefs':kc.spelling_prefs_from_session(session)}
            if bare:spec.update(interval=next((name for name in we.INTERVALS if re.search(r'\b'+name+r'\b',q)),'thirds'),coverage=7,require_full=bool(re.search(r'whole|all seven',q)))
        else:
            spec=copy.deepcopy(plan['spec'])
            selected=str(session.get('level') or '').capitalize()
            if selected in we.LEVELS:spec['level']=selected
            spec['spelling_prefs']=kc.spelling_prefs_from_session(session)
            requested=wp.parse_request(question)
            if requested.get('instrument_word') or _selection(session)!=spec.get('selection_anchor',_selection(session)):
                page,_=wp._page_values(question,session,ami_ctx)
                player,why,facts=wp.resolve_player(requested,session,page,spec['concert_key'])
                if player is None or facts.get('sax_assumed'):raise we.WarmupUnavailable(_player_reason(why))
                spec['instrument']=player.key;spec['selection_anchor']=_selection(session)
        _apply(q,spec)
        if not fresh and not bare and spec==plan['spec']:return response(plan,session,'Those musical settings are already stored; no new version was needed. ')
        if fresh or bare:
            spec['seed_degrees']=list(spec['degrees']);spec['seed_offsets']=list(spec['offsets'])
        new=build(spec)
        if fresh and spec['step']!='single':
            original_spec=copy.deepcopy(spec);original_spec['step']='single';original_spec['direction']='ascending'
            new['original']=build(original_spec)
        else:
            new['original']=copy.deepcopy(new if fresh or bare else plan.get('original',plan))
        wp._push(session,new,question,fresh=bool(fresh or bare))
        return response(new,session,'Exact cell study. ')
    except (we.WarmupUnavailable,ValueError) as exc:
        r=fs._reply('I cannot make that change accurately: '+str(exc)+'. No exercise was changed.',plan if active else None,session,failed='adaptive_cell')
        r.source_solver='AdaptiveLickCell';return r
