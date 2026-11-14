"""Advanced jazz cells over the existing authoritative timeline and harmonic roles.

No chord parser, optional unmarked extensions, fingering model or new transport.
"""
import copy
from dataclasses import replace
from fractions import Fraction
from music_coach_ami import warmup_engine as we, warmup_song as ws, warmup_chordline as wc
from music_coach_ami import scale_pattern_harmony as sph, sax_chart_intervals as sci

DEGREES={'R':0,'3':2,'5':4,'7':6,'6':5,'9':8,'11':10,'13':12}


def named_tones(seg,player):
    """Spell only roles already declared by the canonical chord reader."""
    root=seg.info['written']['root'];letter='CDEFGAB'.index(root[0]);out={}
    for pc,role in sph.chord_tone_roles(seg.chord).items():
        if role in DEGREES:
            name=sph._spell(letter+DEGREES[role],(pc+player.offset)%12)
            out[role]=(sph.pc_of(name),name)
    return out


def _timeline(player,song,section,bars):
    segs,first,last=ws.build_timeline(song,section,bars,player.offset,player.semitones)
    for s in segs:
        if not s.ok:raise we.WarmupUnavailable(f'{s.chord}, bar {s.src_bar}: {s.reason}; no harmonic time was substituted')
    return segs,first,last


def _permutation(player,level,song,section,bars,o):
    from music_coach_ami.flexible_single import _window
    segs,first,last=_timeline(player,song,section,bars);lo,hi=_window(player,level,o.get('register','level'))
    unit=we._DUR_BEATS[o.get('rhythm') or ('quarter' if level=='Beginner' else 'eighth')]
    choices=[];orders=[]
    for j,s in enumerate(segs):
        tones=named_tones(s,player);upper='7' if '7' in tones else '6' if '6' in tones else None
        if o.get('jazz_seventh') and '7' not in tones:raise we.WarmupUnavailable(f'{s.chord}, bar {s.src_bar}: no actual seventh is available')
        core=[r for r in ('R','3','5',upper) if r and r in tones]
        roles=list(o.get('jazz_roles') or (core if o.get('jazz_shape')=='straight' else [core[i] for i in ([0,3,1,2] if o.get('jazz_shape')=='zig' and len(core)==4 else [0,2,1,3] if len(core)==4 else [0,2,1])]))
        if '9' in roles and '9' in tones and (tones['9'][0]-tones['R'][0])%12!=2:
            raise we.WarmupUnavailable(f'{s.chord}, bar {s.src_bar}: only an altered ninth is named; natural 9 was not substituted')
        absent=[r for r in roles if r not in tones]
        if absent:raise we.WarmupUnavailable(f'{s.chord}, bar {s.src_bar}: requested roles {", ".join(absent)} are not named/supported chord tones. No optional scale extension was invented')
        if o.get('jazz_start'):
            role={'third':'3','seventh':'7','root':'R','fifth':'5'}[o['jazz_start']]
            if role not in roles:raise we.WarmupUnavailable(f'{s.chord}: the requested starting role is absent from this pattern')
            k=roles.index(role);roles=roles[k:]+roles[:k]
        down=o.get('direction')=='descending' or o.get('direction')=='alternating' and j%2
        if down:
            roles=list(reversed(roles))
            if o.get('jazz_start'):
                role={'third':'3','seventh':'7','root':'R','fifth':'5'}[o['jazz_start']];k=roles.index(role);roles=roles[k:]+roles[:k]
        if s.beats%unit:raise we.WarmupUnavailable('the requested note unit does not fit this exact chord duration')
        count=int(s.beats/unit);seq=[roles[i%len(roles)] for i in range(count)];orders.extend(seq)
        candidates=[];rootpc=tones['R'][0]
        for base in range(lo-12,hi+1):
            if base%12!=rootpc:continue
            mids={r:base+(pc-rootpc)%12+(12 if DEGREES[r]>=7 else 0) for r,(pc,nm) in tones.items()}
            if o.get('jazz_shape')=='straight' or o.get('jazz_roles'):
                previous=None
                for r in roles:
                    value=mids[r]
                    if previous is not None:
                        while value>=previous if down else value<=previous:value+=-12 if down else 12
                    mids[r]=value;previous=value
            voicings=[mids]
            if not o.get('jazz_roles') and o.get('jazz_shape')!='straight' and upper:
                lower=dict(mids);lower[upper]-=12
                if all(lo<=lower[r]<=hi for r in seq):voicings.append(lower)
            for k,voiced in enumerate(voicings):
                if any(not lo<=voiced[r]<=hi for r in seq):continue
                candidates.append(wc.Cand([wc.Note(voiced[r],tones[r][1],r,unit) for r in seq],key=(base,k)))
        if not candidates:raise we.WarmupUnavailable(f'{s.chord}, bar {s.src_bar}: that complete permutation does not fit the verified register')
        choices.append(candidates)
    chosen=wc.lead_lines(choices,lo,hi,smooth=True,loop=False,boundaries=[j==0 or s.chord!=segs[j-1].chord for j,s in enumerate(segs)])
    notes,placed=wc._emit(player,segs,{s.index:c.body for s,c in zip(segs,chosen)}, {})
    title='Jazz '+('-'.join(o['jazz_roles'])+' permutation' if o.get('jazz_roles') else o.get('jazz_shape','skip')+' chord-tone permutation')
    if o.get('jazz_start'):title+=' from the '+o['jazz_start']
    motion=o.get('direction','ascending') if o.get('jazz_shape')=='straight' else {'ascending':'forward','descending':'reversed','alternating':'alternating'}[o.get('direction','ascending')]
    title+=' ('+motion+' cells)'
    b=we.Built(notes,80 if level=='Advanced' else 64,title,[],[],{'window':[lo,hi]})
    b.meta.update(jazz_expected_roles=orders,jazz_event_kinds=['chord']*len(notes),jazz_groups=[])
    if o['jazz_kind']=='anticipation':
        cursor=0;starts=[]
        for c in chosen:starts.append(cursor);cursor+=len(c.body)
        for j in range(len(segs)-1):
            if segs[j].chord==segs[j+1].chord:continue
            i=starts[j+1]-1;t=starts[j+1];target=b.notes[t]
            b.notes[i]=replace(b.notes[i],spelled=target.spelled,octave=target.octave)
            b.meta['jazz_event_kinds'][i]='anticipation';b.meta['jazz_expected_roles'][i]=None
            b.meta['jazz_groups'].append({'indices':[i],'target':t,'kind':'anticipation'})
        b.title='Jazz untied anticipations and chord-tone permutations'
    b.meta.update(jazz_section=section,jazz_bars=[first,last])
    return b


def _canonical(player,level,song,section,bars,o):
    segs,first,last=_timeline(player,song,section,bars)
    if o['jazz_kind']=='guide':
        b=ws.build(player,level,song,section,bars,tones='both',first='third',style='cells',smooth=True)
    else:
        target=o.get('jazz_target','third')
        if target=='seventh' and any('7' not in named_tones(s,player) for s in segs):
            raise we.WarmupUnavailable('a selected chord has no actual seventh; its sixth or third was not substituted')
        b=wc.build_approach(player,level,song,section,bars,kind=o.get('jazz_approach','enclosure'),target=target,smooth=True,loop=False,allow_chord_neighbors=True)
        if b.meta.get('skipped_approaches'):raise we.WarmupUnavailable('an exact requested approach is unavailable: '+str(b.meta['skipped_approaches'][0]))
    flat=[n for s in b.meta['segments'] for n in s['notes']]
    if len(flat)!=len(b.notes):raise we.WarmupUnavailable('the canonical line contains unsupported/rested harmonic time')
    kinds=['neighbor' if n['role']=='approach' else 'chord' for n in flat]
    groups=[];i=0
    while i<len(kinds):
        if kinds[i]!='neighbor':i+=1;continue
        j=i
        while j<len(kinds) and kinds[j]=='neighbor':j+=1
        if j==len(kinds):raise we.WarmupUnavailable('an approach lacks an in-card resolution')
        groups.append({'indices':list(range(i,j)),'target':j,'kind':o.get('jazz_approach','enclosure')});i=j
    b.meta.update(jazz_expected_roles=[None if n['role']=='approach' else n['role'] for n in flat],jazz_event_kinds=kinds,jazz_groups=groups,jazz_section=section,jazz_bars=[first,last])
    b.title='Jazz guide-tone resolutions' if o['jazz_kind']=='guide' else 'Jazz '+o.get('jazz_approach','enclosure')+' approaches to the '+o.get('jazz_target','third')
    return b


def records(player,built,song):
    """Reconcile explanations with actual event positions after an allowed edit."""
    m=built.meta;segs,first,last=_timeline(player,song,m['jazz_section'],tuple(m['jazz_bars']));pos=Fraction();rows=[]
    for i,n in enumerate(built.notes):
        s=next((s for s in segs if (s.src_bar-first)*4+s.beat<=pos<(s.src_bar-first)*4+s.beat+s.beats),None)
        if s is None or n.rest or pos+n.beats>(s.src_bar-first)*4+s.beat+s.beats:raise we.WarmupUnavailable('a jazz event crosses a harmonic boundary or lacks a chord')
        role=sph.chord_tone_roles(s.chord).get((n.midi-player.offset)%12)
        semis=(n.midi-player.offset-s.info['root_pc'])%12
        tone_label={'3':{3:'b3',4:'3'},'5':{6:'b5',7:'5',8:'#5'},'7':{10:'b7',11:'maj7'},'9':{1:'b9',2:'9',3:'#9'},'11':{5:'11',6:'#11'},'13':{8:'b13',9:'13'}}.get(role,{}).get(semis,role or 'non-chord')
        rows.append({'bar':s.src_bar,'beat':float(pos-(s.src_bar-first)*4),'beats':float(n.beats),'concert':s.chord,'written_chord':s.info['symbol_written'],
                     'name':n.spelled,'midi':n.midi,'role':role or 'non-chord','tone_label':tone_label,'kind':m['jazz_event_kinds'][i],'segment':s.index})
        n.chord=s.info['symbol_written'] if pos==(s.src_bar-first)*4+s.beat else ''
        pos+=n.beats
    if pos!=sum((s.beats for s in segs),Fraction()):raise we.WarmupUnavailable('the jazz line does not fill the chart exactly')
    m['jazz_records']=rows
    leaps=[abs(z.midi-a.midi) for a,z in zip(built.notes,built.notes[1:])]
    joins=[abs(built.notes[i].midi-built.notes[i-1].midi) for i in range(1,len(rows)) if rows[i]['segment']!=rows[i-1]['segment']]
    m['jazz_voice_leading']={'largest_leap':max(leaps,default=0),'mean_leap':round(sum(leaps)/len(leaps),3) if leaps else 0,'boundary_leaps':joins}


def retime(built):
    """Redistribute supported durations inside each chord, retaining every event."""
    from functools import lru_cache
    notes=list(built.notes);rows=built.meta['jazz_records'];changed=False
    segments=list(dict.fromkeys(r['segment'] for r in rows))
    names={1:'sixteenth',2:'eighth',4:'quarter',8:'half',16:'whole'}
    for seg in segments:
        indices=[i for i,r in enumerate(rows) if r['segment']==seg]
        old=tuple(int(notes[i].beats*4) for i in indices);count=len(old);total=sum(old)
        @lru_cache(None)
        def solve(i,left,different):
            if i==count:return () if left==0 and different else None
            preferred=(2,4,1,1)[i%4]
            for unit in dict.fromkeys((preferred,2,4,1,8,16)):
                if unit>left or left-unit<count-i-1:continue
                rest=solve(i+1,left-unit,different or unit!=old[i])
                if rest is not None:return (unit,)+rest
            return None
        units=solve(0,total,False)
        if units:
            for i,u in zip(indices,units):notes[i]=replace(notes[i],dur=names[u])
            changed=True
    if not changed:raise we.WarmupUnavailable('the same event count cannot be retimed accurately using supported durations')
    built.notes=notes


def preserve_targets(before,after,player,song):
    """Preserve actual arrival pitches, including octaves, when adding neighbours."""
    old={r['segment']:n.midi for i,(r,n) in enumerate(zip(before.meta['jazz_records'],before.notes)) if i==0 or r['segment']!=before.meta['jazz_records'][i-1]['segment'] and r['concert']!=before.meta['jazz_records'][i-1]['concert']}
    rows=after.meta['jazz_records'];shifts={}
    for i,r in enumerate(rows):
        if r['segment'] not in old or i and r['segment']==rows[i-1]['segment']:continue
        delta=old[r['segment']]-after.notes[i].midi
        if delta%12:raise we.WarmupUnavailable('the requested target pitch classes differ')
        shifts[r['segment']]=delta
    for i,(n,r,kind) in enumerate(zip(after.notes,rows,after.meta['jazz_event_kinds'])):
        if kind=='chord' and r['segment'] in shifts:after.notes[i]=replace(n,octave=n.octave+shifts[r['segment']]//12)
    for group in after.meta['jazz_groups']:
        delta=shifts.get(rows[group['target']]['segment'],0)
        for i in group['indices']:after.notes[i]=replace(after.notes[i],octave=after.notes[i].octave+delta//12)
    records(player,after,song)


def build(player,level,song,section,bars,o):
    o=copy.deepcopy(o)
    if o['jazz_kind']=='interval':
        settings=dict(o,interval=o['jazz_intervals'][0],interval_cycle=o['jazz_intervals'],chart_approach=o.get('jazz_steps',False),mixed=False)
        b=sci.build(player,level,song,section,bars,settings)
        b.meta.update(jazz_event_kinds=['neighbor' if r['role']=='approach' else 'chord' for r in b.meta['chart_records']],
                      jazz_expected_roles=[None]*len(b.notes),jazz_groups=[],jazz_section=section,jazz_bars=b.meta['chart_bars'])
    else:b=_canonical(player,level,song,section,bars,o) if o['jazz_kind'] in ('approach','guide') else _permutation(player,level,song,section,bars,o)
    b.meta['jazz']=True;b.meta['sax_options']=copy.deepcopy(o)
    records(player,b,song)
    if o.get('mixed'):
        if o['jazz_kind']=='interval':raise we.WarmupUnavailable('mixed chart interval timing remains unsupported; no pitches or harmonic time changed')
        retime(b);records(player,b,song)
    from music_coach_ami.sax_technique import decorate
    b=decorate(b,o);b.title=b.title.removeprefix('Saxophone ')+' - '+song['title']+' - '+section
    b.how=['Follow the actual chord changes and the written chord symbols. Core tones and explicitly named extensions are distinct; no unmarked scale extensions are added.',
           'Connect interval/permutation cells through the changing harmony; a connection between cells need not retain the within-cell interval.',
           f"Articulation: {o['pattern']}; {'accents added' if o['accent'] else 'no added accents'}. Keep the notated event order and rest if coordination or tone deteriorates."]
    if o['jazz_kind'] in ('permutation','anticipation'):b.how.append('Core permutation order names chord roles, not a claim that every note ascends. Octave placement can connect cells more smoothly; explicit 3-5-7-9 and straight descending cells retain their ordered voicing.')
    if o['jazz_kind']=='approach':b.how.append('Chromatic neighbors are identified individually as named chord tones or non-chord notes of the departing chord. Each figure resolves to its requested target at the actual next harmonic change; the first chord establishes the line.')
    if o['jazz_kind']=='anticipation':b.how.append('Anticipations sound the next chord target early and repeat it on the change, without a tie. No anticipation is added after the final chord.')
    if o['jazz_kind']=='interval' and o.get('jazz_steps'):b.how.append('The extra chromatic neighbor resolves inside its own interval cell, not into the next chord. Connections between cells need not retain the named interval.')
    return b


def verify(player,level,built,diag,song):
    m=built.meta
    saved=copy.deepcopy(m['jazz_records']);metrics=copy.deepcopy(m['jazz_voice_leading']);records(player,built,song)
    if metrics!=m['jazz_voice_leading']:raise we.WarmupUnavailable('stored voice-leading metrics differ from actual notes')
    if saved!=m['jazz_records']:raise we.WarmupUnavailable('stored jazz explanation differs from actual pitches/timing')
    if m.get('sax_chart'):return sci.verify(player,level,built,diag,song)
    rows=m['jazz_records'];grouped={i for g in m['jazz_groups'] for i in g['indices']}
    for i,(n,r,kind,expected) in enumerate(zip(built.notes,rows,m['jazz_event_kinds'],m['jazz_expected_roles'])):
        if expected is not None and r['role']!=expected:raise we.WarmupUnavailable(f"bar {r['bar']}: actual {n.spelled} is not requested chord role {expected}")
        if kind=='chord' and r['role']=='non-chord':raise we.WarmupUnavailable('a declared chord tone is outside the actual chord')
        if kind!='chord' and i not in grouped:raise we.WarmupUnavailable('a neighbor or anticipation has no verified target')
    for g in m['jazz_groups']:
        indices=g['indices'];t=g['target'];target=built.notes[t];last=rows[indices[-1]];dest=rows[t]
        if dest['role']=='non-chord' or dest['beat']!=float(next(s.beat for s in _timeline(player,song,m['jazz_section'],tuple(m['jazz_bars']))[0] if s.index==dest['segment'])):
            raise we.WarmupUnavailable('a next-chord target does not land on its harmonic change')
        if dest['segment']!=last['segment']+1 or dest['concert']==last['concert']:raise we.WarmupUnavailable('a next-chord figure does not resolve across an actual change')
        offsets=[built.notes[i].midi-target.midi for i in indices]
        kind=g['kind']
        valid=(offsets==[0] if kind=='anticipation' else offsets in ([1,-1],[-1,1]) if kind=='enclosure' else offsets==[2,1] if kind=='double_above' else offsets in ([-2,-1],[2,1]) if kind=='double' else offsets==[1] if kind=='above' else offsets==[-1] if kind=='below' else len(offsets)==1 and abs(offsets[0])==1)
        if not valid:raise we.WarmupUnavailable('the actual chromatic/anticipation figure differs from its stated geometry')
    return we.verify(player,level,built,*we.practical_key(*we.split_key(player.written_key)),diag,allowed_pcs=set(range(12)))+[{'name':'jazz_harmony_targets_and_timing','ok':True,'detail':'actual roles, named extensions and next-chord targets checked'}]


def explain(row):
    lines=[f"{row['title']}: {row['bpm']} BPM, {row['reps']} repetitions.",*row['how']]
    for r in row['meta']['jazz_records']:
        lines.append(f"Bar {r['bar']}, beat {r['beat']+1:g}: concert {r['concert']} / written {r['written_chord']}; {r['name']}{sph.octave_for(r['name'],r['midi'])}, {r['beats']:g} beats; {r['kind']}, {r['tone_label']} of the current chord.")
    for g in row['meta'].get('jazz_groups',[]):
        a=row['meta']['jazz_records'][g['indices'][0]];t=row['meta']['jazz_records'][g['target']]
        lines.append(f"{g['kind']}: bar {a['bar']} into bar {t['bar']}, beat {t['beat']+1:g}, target {t['name']}{sph.octave_for(t['name'],t['midi'])} (role {t['role']} of {t['concert']}).")
    metrics=row['meta']['jazz_voice_leading'];lines.append(f"Actual largest leap: {metrics['largest_leap']} semitones; average {metrics['mean_leap']}. Boundary leaps: {metrics['boundary_leaps']}.")
    return '\n'.join(lines)
