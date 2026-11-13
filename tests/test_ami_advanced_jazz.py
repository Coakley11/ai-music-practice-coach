"""Independent ABC, harmony and conversational acceptance for advanced jazz."""
import copy,re
from fractions import Fraction
import pytest
from music_coach_ami import warmup_engine as we,warmup_plan as wp,jazz_engine as je,jazz_patterns as jp
from tests.song_fixtures import lib_song,song_session
from tests import song_oracle as oracle
from tests.test_ami_sax_technique import ask,no_api

OFFSETS={'alto':9,'tenor':14,'soprano':2,'baritone':21}
CHARTS=[('Blue Bossa','Section A'),('Autumn Leaves','A Section'),('Satin Doll','A'),('All the Things You Are','Bridge')]


def roles(chord):
    found=oracle.all_tones(chord);assert found is not None
    match=re.match(r'([A-G][#b]?)(.*)',chord);q=match[2];root=found['R']
    for token,semis,label in [('b9',1,'9'),('#9',3,'9'),('#11',6,'11'),('b13',8,'13')]:
        if token in q:found[label]=(root+semis)%12
    for token,semis,label in [('9',2,'9'),('11',5,'11'),('13',9,'13')]:
        if re.search(r'(?<![b#])'+token,q):found.setdefault(label,(root+semis)%12)
    return found


def check(b,abc,song,section,offset,bars=None):
    slots=song['sections'][section];slots=slots[bars[0]-1:bars[1]] if bars else slots
    timeline=oracle.expected_timeline(slots);events=oracle.read_tune(abc)
    assert [e[2] for e in events]==[n.midi for n in b.notes]
    assert sum((e[1] for e in events),Fraction())==4*len(slots)
    kinds=b.meta['jazz_event_kinds'];expected=b.meta['jazz_expected_roles']
    for i,(onset,dur,m,ch) in enumerate(events):
        start,length,chord=next(v for v in timeline if v[0]<=onset<v[0]+v[1]);assert onset+dur<=start+length
        actual=roles(chord);pc=(m-offset)%12
        written_root=re.match(r'[A-G][#b]?',ch)[0]
        assert oracle.note_pc(written_root)==(actual['R']+offset)%12
        if kinds[i]=='chord':assert pc in actual.values(),(onset,chord,pc)
        if expected[i] is not None:assert pc==actual[expected[i]],(onset,chord,expected[i],pc)
        assert 58<=m<=89
    if b.meta.get('sax_chart'):
        cycle=b.meta['sax_options']['jazz_intervals']
        for i,pair in enumerate(b.meta['interval_pairs']):
            a,z=pair['indices'];interval=cycle[i%len(cycle)]
            assert pair['interval']==interval
            assert abs(events[z][2]-events[a][2]) in {'thirds':(3,4),'fourths':(5,),'fifths':(7,),'sixths':(8,9),'octaves':(12,)}[interval]
        for i,kind in enumerate(kinds):
            if kind=='neighbor':
                assert abs(events[i+1][2]-events[i][2])==1
                assert b.meta['jazz_records'][i]['segment']==b.meta['jazz_records'][i+1]['segment']
    for g in b.meta['jazz_groups']:
        t=g['target'];target=events[t];source=events[g['indices'][-1]]
        assert source[0]+source[1]==target[0]
        assert any(start==target[0] for start,duration,chord in timeline)
        differences=[events[i][2]-target[2] for i in g['indices']]
        if g['kind']=='anticipation':assert differences==[0]
        elif g['kind']=='enclosure':assert differences in ([1,-1],[-1,1])
        elif g['kind'] in ('double','double_above'):assert differences in ([-2,-1],[2,1])
        else:assert len(differences)==1 and abs(differences[0])==1
    return events


def built(who,title,section,kind,**kw):
    song=lib_song(title);p=we.make_player(who,song['practice_key']);o=jp.options('');o.update(jazz_kind=kind,**kw)
    b=je.build(p,'Advanced',song,section,None,o);tonic,mode=we.practical_key(*we.split_key(p.written_key));abc,diag=we.render(p,b,tonic,mode,title=b.title)
    assert all(c['ok'] for c in je.verify(p,'Advanced',b,diag,song));check(b,abc,song,section,OFFSETS[who]);return b,abc,song


@pytest.mark.parametrize('who',OFFSETS)
@pytest.mark.parametrize('title,section',CHARTS)
@pytest.mark.parametrize('kind',['permutation','approach','anticipation','guide'])
def test_all_saxes_real_charts_independent_notes_and_timing(who,title,section,kind):
    built(who,title,section,kind)


@pytest.mark.parametrize('who',OFFSETS)
def test_named_ninths_are_actual_ninths_and_unsupported_ninths_refuse(who):
    session=song_session('Blue Bossa');ask(session,f'Give me an advanced {who} sax arpeggio permutation over Blue Bossa.')
    song=wp.current(session)['spec']['song'];p=we.make_player(who,song['practice_key']);o=jp.options('Give me patterns using 3-5-7-9')
    b=je.build(p,'Advanced',song,'Section A',(1,4),o);abc,diag=we.render(p,b,*we.practical_key(*we.split_key(p.written_key)),title=b.title)
    je.verify(p,'Advanced',b,diag,song);events=check(b,abc,song,'Section A',OFFSETS[who],(1,4))
    for i,(_,_,m,_) in enumerate(events):
        chord='Cm9' if events[i][0]<8 else 'Fm9';assert (m-OFFSETS[who])%12==roles(chord)[['3','5','7','9'][i%4]]
    with pytest.raises(we.WarmupUnavailable,match='not named|altered ninth'):je.build(p,'Advanced',song,'Section A',None,o)


@pytest.mark.parametrize('who',OFFSETS)
def test_third_start_and_descending_seventh_cells(who):
    b,abc,song=built(who,'Satin Doll','A','permutation',jazz_start='third')
    events=oracle.read_tune(abc)
    for start,length,chord in oracle.expected_timeline(song['sections']['A']):
        first=next(e for e in events if e[0]==start);assert (first[2]-OFFSETS[who])%12==roles(chord)['3']
    b,abc,song=built(who,'Satin Doll','A','permutation',jazz_shape='straight',jazz_seventh=True,direction='descending')
    events=oracle.read_tune(abc)
    for start,length,chord in oracle.expected_timeline(song['sections']['A']):
        notes=[e[2] for e in events if start<=e[0]<start+length][:4]
        assert all(a>b for a,b in zip(notes,notes[1:]))


@pytest.mark.parametrize('kind',['below','above','double','double_above','enclosure'])
def test_chromatic_geometry_and_next_seventh(kind):
    # Direct supported chart without invented extensions; exact side requests may refuse when unavailable.
    song={'title':'Turnaround','practice_key':'C','original_key':'C','meter':'4/4','sections':{'A':['Dm7','G7','Cmaj7']},'order':['A'],'hash':'checked'}
    p=we.make_player('tenor','C');o=jp.options('');o.update(jazz_kind='approach',jazz_approach=kind,jazz_target='seventh')
    try:b=je.build(p,'Advanced',song,'A',None,o);abc,diag=we.render(p,b,*we.practical_key(*we.split_key(p.written_key)),title=b.title);je.verify(p,'Advanced',b,diag,song)
    except we.WarmupUnavailable as exc:
        assert kind in ('above','below','double_above') and 'geometry' in str(exc);return
    check(b,abc,song,'A',14)
    for g in b.meta['jazz_groups']:
        r=b.meta['jazz_records'][g['target']];assert r['role']=='7'


def test_pitch_preserving_rhythm_crosses_beats_without_moving_changes():
    b,abc,song=built('alto','Satin Doll','A','permutation');old=[n.midi for n in b.notes];je.retime(b);je.records(we.make_player('alto',song['practice_key']),b,song)
    abc,diag=we.render(we.make_player('alto',song['practice_key']),b,*we.practical_key(*we.split_key(we.make_player('alto',song['practice_key']).written_key)),title=b.title)
    je.verify(we.make_player('alto',song['practice_key']),'Advanced',b,diag,song);events=check(b,abc,song,'A',9)
    assert [e[2] for e in events]==old
    assert any(d==1 and t%1==Fraction(1,2) for t,d,_,_ in events)


def start(q='Give me an advanced alto sax arpeggio permutation over Blue Bossa.'):
    s=song_session('Blue Bossa');r=ask(s,q);p=wp.current(s);assert p and p['spec'].get('sax',{}).get('jazz'),r.direct_answer;return s,p


def test_single_and_ordered_warmup_are_distinct():
    s,p=start();assert p['spec']['single_song'] and len(p['items'])==1
    s,p=start('Give me a ten-minute alto sax jazz improvisation warmup over Blue Bossa.')
    assert len(p['items'])>=3 and not p['spec'].get('single_song')
    assert [p['items'][i]['sax_options']['jazz_kind'] for i in range(3)]==['guide','permutation','approach']


@pytest.mark.parametrize('q,index',[
 ('Make the second exercise harder.',1),('Change the first exercise to enclosures.',0),
 ('Keep the notes in exercise two but alter the rhythm.',1),('Make exercise three suitable for tenor sax.',2),
 ('Add accents to the second exercise.',1)])
def test_selected_item_revisions_exact_others_and_history(q,index):
    s,p=start('Give me a ten-minute alto sax jazz improvisation warmup over Blue Bossa.');old=copy.deepcopy(p);r=ask(s,q);new=wp.current(s);assert new!=old,r.direct_answer
    assert all(i==index or row==new['items'][i] for i,row in enumerate(old['items']))
    assert old['items'][index]['reps']==new['items'][index]['reps']
    ask(s,'Undo.');assert wp.current(s)==old
    ask(s,'Redo.');assert wp.current(s)==new
    h=wp.history(s);ask(s,f'Explain exercise {index+1}.');assert wp.current(s)==new and wp.history(s)==h


def test_sections_and_read_only_why_and_targets():
    s=song_session('All the Things You Are');r=ask(s,'Give me a tenor sax jazz technical pattern over the bridge of All the Things You Are.')
    p=wp.current(s);assert p and p['spec']['sax']['jazz'],r.direct_answer
    assert p['spec']['song_sel']['section']=='Bridge'
    r=ask(s,'Use the A section instead.');new=wp.current(s);assert new!=p,r.direct_answer
    h=wp.history(s);r=ask(s,'Explain why those notes work.');assert 'Bar 1, beat 1' in r.direct_answer and wp.current(s)==new and wp.history(s)==h


@pytest.mark.parametrize('owner',['_suite_auth_user_id','_suite_active_workspace_id'])
def test_owner_and_ambiguity_isolation(owner):
    s,p=start('Give me a ten-minute alto sax jazz improvisation warmup over Blue Bossa.');h=wp.history(s);ask(s,'Make it harder.');assert wp.current(s)==p and wp.history(s)==h
    s[owner]='other';jp.handle('Make exercise one harder.',s);assert wp.current(s) is None


def test_no_unmarked_or_altered_natural_ninth():
    s,p=start();h=wp.history(s);r=ask(s,'Give me patterns using 3-5-7-9 over Blue Bossa.')
    assert 'not named' in r.direct_answer or 'altered ninth' in r.direct_answer
    assert wp.current(s)==p and wp.history(s)==h
    assert r.notation_abc==p['items'][0]['abc']
    song={'title':'Altered','practice_key':'C','meter':'4/4','sections':{'A':['C7b9']},'order':['A'],'hash':'test'}
    with pytest.raises(we.WarmupUnavailable,match='altered ninth'):je.build(we.make_player('alto','C'),'Advanced',song,'A',None,jp.options('3-5-7-9'))

@pytest.mark.parametrize('who',OFFSETS)
def test_keep_actual_targets_when_adding_chromatic_neighbors(who):
    s=song_session('Satin Doll');r=ask(s,f'Give me an advanced {who} sax arpeggio permutation over Satin Doll.')
    ask(s,'Start each arpeggio on the third.');old=copy.deepcopy(wp.current(s));a=old['items'][0]
    r=ask(s,'Add chromatic approaches but keep the chord-tone targets.');new=wp.current(s);assert new!=old,r.direct_answer
    before={x['segment']:x['midi'] for i,x in enumerate(a['meta']['jazz_records']) if i==0 or x['segment']!=a['meta']['jazz_records'][i-1]['segment'] and x['concert']!=a['meta']['jazz_records'][i-1]['concert']}
    b=new['items'][0]
    for i,x in enumerate(b['meta']['jazz_records']):
        if i==0 or x['segment']!=b['meta']['jazz_records'][i-1]['segment'] and x['concert']!=b['meta']['jazz_records'][i-1]['concert']:
            assert x['midi']==before[x['segment']]


def test_default_permutation_is_the_declared_core_order_and_voice_leads():
    b,abc,song=built('alto','Satin Doll','A','permutation');events=oracle.read_tune(abc)
    boundaries=[]
    for start,length,chord in oracle.expected_timeline(song['sections']['A']):
        segment=[e for e in events if start<=e[0]<start+length];expected=roles(chord)
        for i,e in enumerate(segment):assert (e[2]-9)%12==expected[['R','5','3','7'][i%4]]
        boundaries.append(segment)
    assert all(abs(a[-1][2]-z[0][2])<=12 for a,z in zip(boundaries,boundaries[1:]))


def test_mixed_chart_intervals_and_unavailable_fourths_are_honest():
    s=song_session('Blue Bossa');r=ask(s,'Give me alto sax jazz thirds and fourths over Blue Bossa, first four bars.')
    p=wp.current(s);assert p,r.direct_answer;row=p['items'][0]
    pairs=row['meta']['interval_pairs'];assert [x['interval'] for x in pairs[:4]]==['thirds','fourths','thirds','fourths']
    notes=oracle.read_tune(row['abc'])
    for x in pairs:
        a,z=x['indices'];assert abs(notes[z][2]-notes[a][2]) in ((3,4) if x['interval']=='thirds' else (5,))
    old=copy.deepcopy(p);h=wp.history(s);r=ask(s,'Give me jazz thirds and fourths over Blue Bossa.')
    assert 'G7#5' in r.direct_answer and wp.current(s)==old and wp.history(s)==h


def test_independent_checker_rejects_mutated_event_pitches_and_timing():
    from dataclasses import replace
    b,abc,song=built('alto','Satin Doll','A','permutation');p=we.make_player('alto',song['practice_key'])
    b.notes[0]=replace(b.notes[0],spelled='C',octave=5)
    with pytest.raises((we.WarmupUnavailable,AssertionError)):
        abc,diag=we.render(p,b,*we.practical_key(*we.split_key(p.written_key)),title=b.title)
        je.verify(p,'Advanced',b,diag,song)
        check(b,abc,song,'A',9)

@pytest.mark.parametrize('who',OFFSETS)
def test_actual_voice_leading_metrics_and_guide_semitone_resolutions(who):
    b,abc,song=built(who,'Satin Doll','A','guide');events=oracle.read_tune(abc)
    leaps=[abs(a[2]-z[2]) for a,z in zip(events,events[1:])]
    assert b.meta['jazz_voice_leading']['largest_leap']==max(leaps)
    timeline=oracle.expected_timeline(song['sections']['A']);joins=[]
    for start,length,chord in timeline[1:]:
        i=next(i for i,e in enumerate(events) if e[0]==start);joins.append(abs(events[i][2]-events[i-1][2]))
    assert b.meta['jazz_voice_leading']['boundary_leaps']==joins
    assert 1 in joins


def test_rhythm_preserves_every_event_articulation_tempo_and_targets():
    s,p=start('Give me an advanced alto sax jazz enclosure exercise over Blue Bossa.');before=copy.deepcopy(p);r=ask(s,'Keep the notes but alter the rhythm.');new=wp.current(s)
    assert new!=before,r.direct_answer
    a=before['items'][0];b=new['items'][0]
    for field in ('written_midi','sounding_midi','articulations','slur_groups','bpm','reps','instrument'):assert a[field]==b[field]
    assert len(a['durations'])==len(b['durations'])


def test_interval_rhythm_and_specialized_techniques_refuse_without_mutation():
    s=song_session('Blue Bossa');r=ask(s,'Give me alto sax jazz thirds and fourths over Blue Bossa, first four bars.');p=copy.deepcopy(wp.current(s));h=wp.history(s)
    for q in ('Keep the notes but alter the rhythm.','Add swing.','Add altissimo.','Use alternate fingerings.'):
        r=ask(s,q);assert wp.current(s)==p and wp.history(s)==h,r.direct_answer


def test_the_exact_direction_changing_finger_buster_request_uses_jazz():
    s,p=start('Make a finger-buster that changes direction over each chord.')
    assert p['spec']['sax']['jazz'] and p['items'][0]['sax_options']['direction']=='alternating'


def test_mutated_anticipation_or_target_is_rejected():
    from dataclasses import replace
    b,abc,song=built('tenor','Satin Doll','A','anticipation');p=we.make_player('tenor',song['practice_key']);i=b.meta['jazz_groups'][0]['indices'][0]
    n=b.notes[i];b.notes[i]=replace(n,octave=n.octave+1)
    with pytest.raises(we.WarmupUnavailable):
        abc,diag=we.render(p,b,*we.practical_key(*we.split_key(p.written_key)),title=b.title)
        je.verify(p,'Advanced',b,diag,song)


def test_current_item_references_keep_the_selected_scope():
    s,p=start('Give me a ten-minute alto sax jazz improvisation warmup over Blue Bossa.')
    ask(s,'Make the second exercise harder.');before=copy.deepcopy(wp.current(s));r=ask(s,'Keep the notes but alter the rhythm.');new=wp.current(s);assert new!=before,r.direct_answer
    assert new['items'][1]['written_midi']==before['items'][1]['written_midi']
    assert all(i==1 or x==new['items'][i] for i,x in enumerate(before['items']))
    h=wp.history(s);ask(s,'Explain why those notes work.');assert wp.current(s)==new and wp.history(s)==h


def test_unsupported_extension_combination_does_not_apply_just_the_accent():
    s,p=start();h=wp.history(s);r=ask(s,'Add elevenths and accents.');assert wp.current(s)==p and wp.history(s)==h,r.direct_answer


def test_named_ninth_request_is_one_actual_pipeline_exercise():
    s,p=start('Give me advanced alto sax jazz patterns using 3-5-7-9 over Blue Bossa, first four bars.')
    assert p['spec']['single_song'] and len(p['items'])==1
    assert p['items'][0]['meta']['jazz_bars']==[1,4]
    assert p['items'][0]['sax_options']['jazz_roles']==['3','5','7','9']


def test_sixteenth_anticipation_and_local_stepwise_interval_requests():
    for title,q,kind in [('Satin Doll','Give me an advanced soprano sax jazz anticipation exercise in sixteenth notes over Satin Doll.','anticipation'),('Autumn Leaves','Give me an advanced alto sax jazz pattern with wide leaps and stepwise resolutions over Autumn Leaves.','interval')]:
        s=song_session(title);r=ask(s,q);p=wp.current(s);assert p and p['spec']['sax']['jazz'],r.direct_answer
        assert p['items'][0]['sax_options']['jazz_kind']==kind
        if kind=='anticipation':assert set(p['items'][0]['durations'])=={'sixteenth'}

@pytest.mark.parametrize('who',OFFSETS)
def test_descending_cells_keep_their_direction_when_started_on_third(who):
    b,abc,song=built(who,'Satin Doll','A','permutation',jazz_shape='straight',jazz_seventh=True,jazz_start='third',direction='descending')
    events=oracle.read_tune(abc)
    for start,length,chord in oracle.expected_timeline(song['sections']['A']):
        notes=[e[2] for e in events if start<=e[0]<start+length]
        assert (notes[0]-OFFSETS[who])%12==roles(chord)['3']
        for i in range(0,len(notes),4):assert all(a>z for a,z in zip(notes[i:i+3],notes[i+1:i+4]))


def test_explicit_register_is_not_overwritten_by_the_jazz_default():
    assert jp.options('Give me a high-register jazz permutation')['register']=='high'
    assert jp.options('Give me a low-register jazz permutation')['register']=='low'
    song={'title':'Register','practice_key':'C','meter':'4/4','sections':{'A':['Cmaj7']},'order':['A'],'hash':'register'}
    p=we.make_player('alto','C');o=jp.options('Give me a high-register jazz permutation')
    b=je.build(p,'Advanced',song,'A',None,o)
    assert all(77<=n.midi<=89 for n in b.notes)


@pytest.mark.parametrize('who',OFFSETS)
def test_alternating_permutation_order_is_actual_not_just_a_label(who):
    b,abc,song=built(who,'Satin Doll','A','permutation',direction='alternating');events=oracle.read_tune(abc)
    for j,(start,length,chord) in enumerate(oracle.expected_timeline(song['sections']['A'])):
        sequence=['7','3','5','R'] if j%2 else ['R','5','3','7']
        actual=[e[2] for e in events if start<=e[0]<start+length]
        expected=roles(chord)
        assert all((m-OFFSETS[who])%12==expected[sequence[i%4]] for i,m in enumerate(actual))
