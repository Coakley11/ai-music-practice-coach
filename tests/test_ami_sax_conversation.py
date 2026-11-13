import copy,re
from fractions import Fraction
import pytest
from music_coach_ami import warmup_plan as wp,warmup_engine as we,warmup_song as ws,sax_chart_intervals as sci
from tests.test_ami_sax_technique import setup,ask,no_api
from tests.song_fixtures import lib_song,song_session
from tests import song_oracle as oracle
from tests.test_abc_bar_accidentals import read_abc

OFFSETS={'alto':9,'tenor':14,'soprano':2,'baritone':21}
SONGS=[('Blue Bossa','Section A'),('Autumn Leaves','A Section'),('Satin Doll','A'),('All the Things You Are','Bridge')]


def independent(row,song,section,offset,interval,approach=False):
    tune=oracle.read_tune(row['abc']);timeline=oracle.expected_timeline(ws.section_slots(song,section))
    assert read_abc(row['abc'].replace('(','').replace(')',''))==row['written_midi']
    assert row['sounding_midi']==[m-offset for m in row['written_midi']]
    # Independent degree and semitone oracle; no generator candidate metadata used.
    letters='CDEFGAB';degree={'thirds':2,'fourths':3,'sixths':5,'octaves':7}[interval]
    names=row['written_notes'];idx=[7*int(re.search(r'(-?\d+)$',n)[1])+letters.index(n[0]) for n in names]
    stride=4 if approach else 2
    for i in range(0,len(tune),stride):
        assert abs(idx[i+1]-idx[i])==degree
        assert abs(tune[i+1][2]-tune[i][2]) in {'thirds':(3,4),'fourths':(5,),'sixths':(8,9),'octaves':(12,)}[interval]
    for i,(t,d,m,c) in enumerate(tune):
        active=next((a,b,ch) for a,b,ch in timeline if a<=t<a+b)
        a,b,ch=active;assert t+d<=a+b
        roles=oracle.all_tones(ch); assert roles is not None
        pcs=set(roles.values())
        root=roles['R']
        # Independently include explicitly named extensions when deciding non-chord status.
        if re.search(r'(?<!b)9|11|13',ch):pcs.add((root+2)%12)
        if re.search(r'11|13',ch):pcs.add((root+5)%12)
        if '13' in ch:pcs.add((root+9)%12)
        if approach and i%4==2:
            assert (m-offset)%12 not in pcs
            assert abs(tune[i+1][2]-m)==1 and (tune[i+1][2]-offset)%12 in pcs
        else:assert (m-offset)%12 in pcs,(t,ch,m,offset)
    assert sum((d for _,d,_,_ in tune),Fraction())==4*len(ws.section_slots(song,section))
    assert all(58<=m<=89 for m in row['written_midi'])


@pytest.mark.parametrize('who',OFFSETS)
@pytest.mark.parametrize('title,section',SONGS)
@pytest.mark.parametrize('interval',['thirds','fourths','sixths','octaves'])
@pytest.mark.parametrize('approach',[False,True])
def test_real_chart_intervals(who,title,section,interval,approach):
    song=lib_song(title);p=we.make_player(who,song['practice_key'])
    o={'interval':interval,'direction':'alternating','register':'middle','chart_approach':approach}
    if title in ('All the Things You Are','Blue Bossa') and interval=='fourths':
        with pytest.raises(we.WarmupUnavailable,match='(?:C|G)7#5'): sci.build(p,'Advanced',song,section,None,o)
        return
    b=sci.build(p,'Advanced',song,section,None,o)
    tonic,mode=we.practical_key(*we.split_key(p.written_key));abc,diag=we.render(p,b,tonic,mode,title=b.title)
    assert all(c['ok'] for c in sci.verify(p,'Advanced',b,diag,song))
    notes=[n for n in b.notes if not n.rest]
    row={'abc':abc,'written_midi':[n.midi for n in notes],'written_notes':[n.spelled+str(n.octave) for n in notes],'sounding_midi':[n.midi-p.offset for n in notes]}
    independent(row,song,section,p.offset,interval,approach)


def routine():
    s=setup();r=ask(s,'Give me a ten-minute advanced alto saxophone technique warmup.')
    p=wp.current(s);assert p and p['spec'].get('sax') and len(p['items'])>=3,r.direct_answer
    return s,p


@pytest.mark.parametrize('q,index',[
 ('Make exercise three more difficult.',2),('Change the intervals in exercise two to fourths.',1),
 ('Slur every two notes in the first exercise.',0),('Make the last exercise slower.',-1),
 ('Keep the notes in exercise three but change the rhythm.',2),('Add accents to the last exercise.',-1),
 ('Adapt exercise three for tenor sax.',2),('Make only the second exercise harder.',1)])
def test_item_isolation_and_exact_history(q,index):
    s,p=routine();before=copy.deepcopy(p);r=ask(s,q);new=wp.current(s);index=index%len(p['items'])
    assert new!=before,r.direct_answer
    for i,row in enumerate(before['items']):
        if i!=index:assert new['items'][i]==row
    assert new['items'][index]['reps']==before['items'][index]['reps']
    ask(s,'Undo.');assert wp.current(s)==before
    ask(s,'Redo.');assert wp.current(s)==new
    h=wp.history(s);ask(s,f'Explain what exercise {index+1} is developing.');assert wp.current(s)==new and wp.history(s)==h


def test_full_conversation_preserves_unrequested_properties():
    s,p=routine()
    for q,i,changed in [('Make exercise three more difficult.',2,'pitches'),('Change the intervals in exercise two to fourths.',1,'pitches'),('Slur every two notes in the first exercise.',0,'art'),('Make the last exercise slower.',-1,'bpm'),('Keep the notes in exercise three but change the rhythm.',2,'rhythm')]:
        old=copy.deepcopy(wp.current(s));r=ask(s,q);p=wp.current(s);i%=len(p['items']);a=old['items'][i];b=p['items'][i]
        assert p!=old,r.direct_answer
        for j,row in enumerate(old['items']):
            if j!=i:assert row==p['items'][j]
        for prop in ['written_midi','durations','articulations','slur_groups','bpm','reps','instrument']:
            if (changed=='pitches' and prop=='written_midi') or (changed=='art' and prop in ('articulations','slur_groups')) or (changed=='bpm' and prop=='bpm') or (changed=='rhythm' and prop=='durations'):continue
            assert a[prop]==b[prop],(q,prop)


def test_ambiguous_and_invalid_references_are_read_only():
    s,p=routine();before=copy.deepcopy(p);h=wp.history(s)
    for q in ['Make the first and second exercises harder.', 'Add accents to the interval exercise.','Make it harder.','Change exercise 99 to fourths.','Explain the interval exercise.']:
        r=ask(s,q);assert wp.current(s)==before and wp.history(s)==h,r.direct_answer


@pytest.mark.parametrize('owner',['_suite_auth_user_id','_suite_active_workspace_id'])
def test_item_owner_isolation(owner):
    s,p=routine();s[owner]='other'
    from music_coach_ami.pipeline import run_coach_submit
    run_coach_submit('Make exercise three harder.',s,ami_ctx={'instrument':'Saxophone','display_key':'C'});assert wp.current(s) is None


def test_chart_conversation_sections_and_exact_history():
    s=song_session('All the Things You Are');r=ask(s,'Give me advanced tenor sax thirds over the bridge of All the Things You Are.')
    p=wp.current(s);assert p and p['spec']['sax'].get('chart_intervals'),r.direct_answer
    assert p['spec']['song_sel']['section']=='Bridge'
    r=ask(s,'Change the thirds to sixths.');new=wp.current(s);assert new!=p,r.direct_answer
    independent(new['items'][0],new['spec']['song'],'Bridge',14,'sixths')
    r=ask(s,'Use the A section instead.');a3=wp.current(s);assert a3!=new,r.direct_answer
    independent(a3['items'][0],a3['spec']['song'],'A',14,'sixths')
    assert a3['items'][0]['articulations']==new['items'][0]['articulations']
    assert a3['items'][0]['slur_groups']==new['items'][0]['slur_groups']
    h=wp.history(s);r=ask(s,'Explain why the notes fit these chords.');assert 'Bar 1, beat 1' in r.direct_answer
    assert wp.current(s)==a3 and wp.history(s)==h
    ask(s,'Undo.');assert wp.current(s)==new
    ask(s,'Redo.');assert wp.current(s)==a3


def test_unavailable_interval_and_unknown_chart_do_not_mutate():
    s,p=routine();h=wp.history(s)
    r=ask(s,'Give me fourths over the chords of Blue Bossa.');assert wp.current(s)==p and wp.history(s)==h
    song={'sections':{'A':['C']},'order':['A'],'meter':'4/4','practice_key':'C','original_key':'C','hash':'test','title':'Triad'}
    with pytest.raises(we.WarmupUnavailable,match='no ascending sevenths'):
        sci.build(we.make_player('alto','C'),'Advanced',song,'A',None,{'interval':'sevenths','direction':'ascending','register':'middle'})


def test_actual_split_measure_and_practice_key():
    s=song_session('Satin Doll',practice_key='Eb');r=ask(s,'Give me advanced alto sax fourths over the chords of Satin Doll.')
    p=wp.current(s);assert p and p['spec']['sax'].get('chart_intervals'),r.direct_answer
    song=p['spec']['song'];section=p['spec']['song_sel']['section']
    assert song['practice_key']=='Eb'
    assert any('|' in x for x in ws.section_slots(song,section))
    independent(p['items'][0],song,section,9,'fourths')

@pytest.mark.parametrize('who',OFFSETS)
@pytest.mark.parametrize('level',['Beginner','Intermediate','Advanced'])
@pytest.mark.parametrize('direction',['ascending','descending','alternating'])
def test_direction_level_and_exact_transposition(who,level,direction):
    song=lib_song('Satin Doll');p=we.make_player(who,song['practice_key'])
    b=sci.build(p,level,song,'A',None,{'interval':'thirds','direction':direction,'register':'middle'})
    notes=b.notes
    for i in range(0,len(notes),2):
        sign=-1 if direction=='descending' or direction=='alternating' and i//2%2 else 1
        assert 3<=(notes[i+1].midi-notes[i].midi)*sign<=4
    lo,hi={'Beginner':(62,79),'Intermediate':(60,84),'Advanced':(58,89)}[level]
    assert all(lo<=n.midi<=hi and n.midi-(n.midi-OFFSETS[who])==OFFSETS[who] for n in notes)


def test_adaptation_preserves_exact_concert_line_and_marks():
    s,p=routine();a=copy.deepcopy(p['items'][2]);settings={k:s.get(k) for k in ('instrument','selected_transposing_instrument','display_key','backing_track_bpm')}
    r=ask(s,'Adapt exercise three for tenor sax.');b=wp.current(s)['items'][2]
    assert b['instrument']=='tenor',r.direct_answer
    assert b['sounding_midi']==a['sounding_midi']
    for k in ('durations','articulations','slur_groups','bpm','reps'):assert b[k]==a[k]
    assert settings=={k:s.get(k) for k in settings}
    ask(s,'Make exercise three slower.');c=wp.current(s)['items'][2]
    assert c['instrument']=='tenor' and c['written_midi']==b['written_midi']


def test_register_move_preserves_rhythm_marks_and_other_rows():
    s=setup();ask(s,'Give me a five-minute alto sax repeated-note tonguing warmup.');old=copy.deepcopy(wp.current(s))
    r=ask(s,'Move exercise one into a lower register.');new=wp.current(s)
    assert new!=old,r.direct_answer
    assert new['items'][1:]==old['items'][1:]
    a=old['items'][0];b=new['items'][0]
    assert all(y-x==-12 for x,y in zip(a['written_midi'],b['written_midi']))
    for k in ('durations','articulations','slur_groups','bpm','reps'):assert a[k]==b[k]


def test_wide_chord_tone_request_and_chromatic_revision():
    s=song_session('Autumn Leaves');r=ask(s,'Make an advanced saxophone finger-buster using chord tones and wide intervals.')
    p=wp.current(s);assert p and p['spec']['sax']['chart_intervals'],r.direct_answer
    assert p['level']=='Advanced'
    r=ask(s,'Use sixths and chromatic approaches over the changes.');new=wp.current(s)
    assert new!=p,r.direct_answer
    independent(new['items'][0],new['spec']['song'],new['spec']['song_sel']['section'],9,'sixths',True)


def test_augmented_fourths_refusal_keeps_active_plan_and_history():
    s=song_session('Blue Bossa');ask(s,'Give me an alto sax exercise in thirds.');before=copy.deepcopy(wp.current(s));h=wp.history(s)
    r=ask(s,'Give me fourths over the chords of Blue Bossa.')
    assert 'G7#5' in r.direct_answer and 'no ascending fourths' in r.direct_answer
    assert wp.current(s)==before and wp.history(s)==h


def test_corrupted_actual_notes_and_timing_are_rejected():
    from dataclasses import replace
    song=lib_song('Satin Doll');p=we.make_player('alto','C');o={'interval':'thirds','direction':'ascending','register':'middle'}
    b=sci.build(p,'Advanced',song,'A',None,o);tonic,mode=we.practical_key(*we.split_key(p.written_key))
    b.notes[0]=replace(b.notes[0],dur='whole')
    with pytest.raises(we.WarmupUnavailable):
        abc,diag=we.render(p,b,tonic,mode,title=b.title)
        sci.verify(p,'Advanced',b,diag,song)

@pytest.mark.parametrize('who',['tenor','soprano','baritone'])
def test_adapted_title_matches_actual_written_key(who):
    s,p=routine();r=ask(s,f'Adapt exercise three for {who} sax.');row=wp.current(s)['items'][2]
    assert row['instrument']==who,r.direct_answer
    assert row['key'] in row['title']
    assert row['title'].count('Saxophone ')==1
    assert row['offset']==OFFSETS[who]
    assert read_abc(row['abc'].replace('(','').replace(')',''))==row['written_midi']
