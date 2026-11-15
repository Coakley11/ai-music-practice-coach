"""Literal musical oracles and public-pipeline contracts for short-cell exercises."""
import copy
import re
from fractions import Fraction
import pytest
from music_coach_ami import adaptive_cells as ac, warmup_plan as wp, session_scope
from music_coach_ami.pipeline import run_coach_submit
from tests.abc_pitch_decoder import decode_abc_events, abc_bar_totals
from instrument_transposition import SELECTED_TRANSPOSING_INSTRUMENT_KEY


def setup(instrument='Flute',level='Advanced',key='G',sax='Alto saxophone (Eb)'):
    s={'_suite_auth_user_id':'u1','_suite_active_workspace_id':'music','instrument':instrument,'level':level,'foreign':{'keep':[1,2]},'practice_key':'C','backing_key_cycle_on':True}
    from practice_setup_globals import INSTRUMENT_CHANGE_SOURCE_KEY
    s[INSTRUMENT_CHANGE_SOURCE_KEY]='test-explicit-selection'
    if instrument=='Saxophone':s[SELECTED_TRANSPOSING_INSTRUMENT_KEY]=sax
    c={'instrument':instrument,'level':level,'display_key':key,'active_song':{},'chart_sections':{},'bpm':72}
    return s,c


def ask(s,c,q):return run_coach_submit(q,s,ami_ctx=c)[1]
def current(s):return copy.deepcopy(wp.current(s))
def row(s):return wp.current(s)['items'][0]


def events(abc):
    """Read the actual serialized keys and events with the independent ABC reader."""
    lines=abc.splitlines();ki=next(i for i,l in enumerate(lines) if l.startswith('K:'))
    base=lines[:ki];key=lines[ki][2:];body='\n'.join(lines[ki+1:]);out=[];bars=[]
    pieces=re.split(r'\[K:([^\]]+)\]',body)
    for index in range(0,len(pieces),2):
        if index:key=pieces[index-1]
        text='\n'.join(base+['K:'+key,pieces[index]])
        out.extend(decode_abc_events(text));bars.extend(abc_bar_totals(text))
    return out,bars


@pytest.fixture(autouse=True)
def no_paid_api(monkeypatch):
    from music_coach_ami.claude_client import AnthropicTransport
    monkeypatch.setattr(AnthropicTransport,'complete',lambda *a,**k: (_ for _ in ()).throw(AssertionError('Paid API forbidden')))


@pytest.mark.parametrize('count',range(1,13))
def test_exact_attack_count_is_not_unique_pitches_beats_or_bars(count):
    s,c=setup();r=ask(s,c,f'Give me a {count}-note lick in G major.')
    decoded,bars=events(r.notation_abc)
    assert len([m for m,d in decoded if m is not None])==count
    assert all(b==4 for b in bars)
    assert sum(d for m,d in decoded if m is not None)==Fraction(count,2)
    assert '-' not in '\n'.join(r.notation_abc.splitlines()[6:])


@pytest.mark.parametrize('question,expected',[
 ('Give me a four-note lick in G major.',[67,69,71,74]),
 ('Give me a five-note jazz lick in G major.',[67,71,74,78,81]),
 ('Give me a six-note blues lick in G major.',[67,70,72,73,74,77]),
 ('Give me a descending six-note lick in G major.',[78,76,74,71,69,67]),
])
def test_literal_four_five_six_note_oracles(question,expected):
    s,c=setup();r=ask(s,c,question)
    assert row(s)['written_midi']==expected
    assert [m for m,d in events(r.notation_abc)[0] if m is not None]==expected
    assert len(row(s)['cells'])==1


def test_seven_degree_cells_are_diatonic_not_fixed_chromatic_transpositions():
    s,c=setup();ask(s,c,'Give me a four-note lick in G major.')
    r=ask(s,c,'Move it through all seven degrees.')
    expected=[[67,69,71,74],[69,71,72,76],[71,72,74,78],[72,74,76,79],[74,76,78,81],[76,78,79,83],[78,79,81,84]]
    assert [v['written_midi'] for v in row(s)['cells']]==expected
    assert [m for m,d in events(r.notation_abc)[0] if m is not None]==sum(expected,[])
    assert [b-a for a,b in zip(expected[1],expected[1][1:])]==[2,1,4]


def test_whole_scale_and_back_and_descending_preserve_each_cell():
    s,c=setup();ask(s,c,'Give me a four-note lick in G major and move it through the whole major scale and back down.')
    assert [v['starting_degree'] for v in row(s)['cells']]==list(range(1,9))+list(range(7,0,-1))
    ask(s,c,'Now make the sequence descending.')
    assert [v['starting_degree'] for v in row(s)['cells']]==list(range(8,0,-1))
    assert all(len(v['written_midi'])==4 for v in row(s)['cells'])


def test_thirds_revision_keeps_four_attacks_and_diatonic_context():
    s,c=setup();ask(s,c,'Give me a four-note lick in G major.');ask(s,c,'Move it through all seven degrees.')
    ask(s,c,'Do the same exercise in thirds.')
    assert wp.current(s)['spec']['degrees']==[0,2,4,6]
    assert row(s)['cells'][0]['written_midi']==[67,71,74,78]
    assert all(len(v['written_midi'])==4 for v in row(s)['cells'])


@pytest.mark.parametrize('q,keys',[
 ('Transpose the original lick through twelve keys.',['G','Ab','A','Bb','B','C','Db','D','Eb','E','F','F#']),
 ('Move it by whole steps.',['G','A','B','Db','Eb','F']),
 ('Move it around the circle of fourths.',['G','C','F','Bb','Eb','Ab','Db','F#','B','E','A','D']),
 ('Play the same lick in G, then G-sharp, A, B-flat and B.',['G','G#','A','Bb','B']),
])
def test_key_itineraries_preserve_literal_intervals_and_native_abc(q,keys):
    s,c=setup();ask(s,c,'Give me a four-note lick in G major.');r=ask(s,c,q)
    cells=row(s)['cells'];assert [v['concert_key'] for v in cells]==keys
    assert all([m-v['written_midi'][0] for m in v['written_midi']]==[0,2,4,7] for v in cells)
    decoded,bars=events(r.notation_abc)
    assert [m for m,d in decoded if m is not None]==sum([v['written_midi'] for v in cells],[])
    assert all(b==4 for b in bars)


def test_descending_key_order_and_explicit_list_replaces_old_direction():
    s,c=setup();ask(s,c,'Give me a four-note lick in G major.');ask(s,c,'Move it up by half steps.');ask(s,c,'Make the traversal descending.')
    assert [v['concert_key'] for v in row(s)['cells']]==['G','F#','F','E','Eb','D','Db','C','B','Bb','A','Ab']
    ask(s,c,'Play the same lick in G, then G-sharp, A, B-flat and B.')
    assert [v['concert_key'] for v in row(s)['cells']]==['G','G#','A','Bb','B']


def test_playback_enharmonic_preference_and_c_flat_octave():
    import backing_key_cycle as kc
    s,c=setup();s[kc.BACKING_KEY_SPELLING_PREFS_KEY]={'F#/Gb':'Gb'}
    ask(s,c,'Give me a four-note lick in G major.');r=ask(s,c,'Transpose this lick through twelve keys.')
    assert row(s)['cells'][-1]['concert_key']=='Gb' and row(s)['cells'][-1]['written_key']=='Gb'
    assert '[K:Gb' in r.notation_abc
    s,c=setup(level='Intermediate',key='Gb');ask(s,c,'Give me a four-note lick in Gb major.');r=ask(s,c,'Move it through all seven degrees.')
    assert row(s)['cells'][3]['written_midi']==[71,73,75,78]
    assert row(s)['written_notes'][12:16]==['Cb5','Db5','Eb5','Gb5']
    assert [m for m,d in events(r.notation_abc)[0] if m is not None][12:16]==[71,73,75,78]


@pytest.mark.parametrize('instrument,sax,offset',[('Flute','',0),('Piano','',0),('Saxophone','Alto saxophone (Eb)',9),('Saxophone','Tenor saxophone (Bb)',14),('Saxophone','Soprano saxophone (Bb)',2),('Saxophone','Baritone saxophone (Eb)',21),('Trumpet','',2),('Clarinet','',2),('Bass Guitar','',12)])
def test_written_sounding_range_and_foreign_state(instrument,sax,offset):
    s,c=setup(instrument=instrument,sax=sax);before={k:copy.deepcopy(v) for k,v in s.items()}
    r=ask(s,c,'Give me a four-note lick in G major.')
    assert r.notation_abc,r.direct_answer
    p=wp.current(s);assert p['player']['offset']==offset
    assert [m-offset for m in row(s)['written_midi']]==row(s)['sounding_midi']
    assert [m for m,d in events(r.notation_abc)[0] if m is not None]==row(s)['written_midi']
    for k,v in before.items():assert s[k]==v


def test_range_refusal_is_atomic_and_does_not_clamp_or_drop_keys():
    s,c=setup(level='Beginner');ask(s,c,'Give me a four-note lick in G major.');before=current(s);h=wp.history(s)
    r=ask(s,c,'Move it through the whole major scale and back down.')
    assert 'cannot' in r.direct_answer.lower() and current(s)==before and wp.history(s)==h
    r=ask(s,c,'Transpose this lick through twelve keys.')
    assert 'no keys or notes were removed' in r.direct_answer and current(s)==before


@pytest.mark.parametrize('q', ['Give me a 0-note lick.','Give me a 13-note lick.','Give me a 5.5-note lick.','Give me a 3/2-note lick.','Give me a -4-note lick.','Give me a four-note lick with tied notes.','Give me a four-note lick with triplets.','Give me a four-note lick over every chord of Blue Bossa.'])
def test_unsupported_requests_do_not_replace_working_exercise(q):
    s,c=setup();ask(s,c,'Give me a four-note lick in G major.');before=current(s);h=wp.history(s)
    r=ask(s,c,q);assert r.source_solver=='AdaptiveLickCell' and r.diagnostics['single_exercise_failed']=='adaptive_cell'
    assert not r.diagnostics.get('single_exercise_plan') or r.diagnostics['single_exercise_plan']==before
    assert current(s)==before and wp.history(s)==h


def test_full_conversation_original_review_explain_and_exact_history(monkeypatch):
    s,c=setup();initial=ask(s,c,'Give me a four-note lick in G major.');original=current(s)
    harder=ask(s,c,'Make it harder.');assert len(row(s)['written_midi'])==4 and row(s)['written_midi']!=original['items'][0]['written_midi']
    ask(s,c,'Use eighth notes.');ask(s,c,'Make it sixteenth notes.');ask(s,c,'Move the lick through the whole G major scale.')
    ask(s,c,'Now transpose the original lick through twelve keys.');ascending=current(s)
    assert ascending['spec']['rhythm']=='sixteenth' and ascending['spec']['offsets']==[0,2,4,7]
    ask(s,c,'Make the sequence descending.');descending=current(s);h=wp.history(s)
    with monkeypatch.context() as m:
        m.setattr(ac,'build',lambda *a,**k:(_ for _ in ()).throw(AssertionError('read-only action regenerated music')))
        shown=ask(s,c,'Show me the first lick again.');explain=ask(s,c,'Explain the pattern.')
        assert shown.notation_abc==initial.notation_abc==explain.notation_abc
    assert current(s)==descending and (wp.history(s)['versions'],wp.history(s)['cursor'])==(h['versions'],h['cursor'])
    ask(s,c,'Undo.');assert current(s)==ascending
    ask(s,c,'Redo.');assert current(s)==descending


@pytest.mark.parametrize('question,expected_first',[('Give me sixths in G major.',[67,76,69,78,71,79,72,81]),('Give me ascending fourths.',[67,72,69,74]),('Give me descending fifths.',[84,78,83,76]),('Give me octaves.',[67,79,69,81])])
def test_legacy_bare_interval_route_uses_real_playable_octaves(question,expected_first):
    s,c=setup();r=ask(s,c,question)
    assert r.source_solver=='AdaptiveLickCell' and row(s)['written_midi'][:len(expected_first)]==expected_first
    assert all(60<=m<=96 for m in row(s)['written_midi'])
    assert [m for m,d in events(r.notation_abc)[0] if m is not None]==row(s)['written_midi']
    assert all(b==4 for b in events(r.notation_abc)[1])


def test_beginner_interval_coverage_is_explicit_and_full_request_refuses():
    s,c=setup(level='Beginner');r=ask(s,c,'Give me sixths in G major.')
    assert '6 starting degree' in ' '.join(r.practice_steps) and 'shorter study' in ' '.join(r.practice_steps)
    before=current(s);r=ask(s,c,'Give me sixths through the whole scale in G major.')
    assert current(s)==before and 'complete requested interval traversal' in r.direct_answer


@pytest.mark.parametrize('owner',['_suite_auth_user_id','_suite_active_workspace_id'])
def test_owner_change_cannot_recall_or_revise_old_cell(owner):
    s,c=setup();ask(s,c,'Give me a four-note lick in G major.');s[owner]='other'
    ask(s,c,'Make it harder.');assert wp.current(s) is None


def test_level_defaults_and_explicit_note_controls_do_not_change_music():
    from music_coach_ami import note_name_display as nd
    s,c=setup(level='Beginner');initial=ask(s,c,'Give me a four-note lick in G major.');before=current(s);h=wp.history(s)
    assert nd.show_by_default(s)
    s['level']='Intermediate';assert not nd.show_by_default(s)
    for q,visible in [('Show me the note names.',True),('Hide the note names.',False)]:
        r=ask(s,c,q);assert nd.show_by_default(s) is visible and r.notation_abc==initial.notation_abc
        assert current(s)==before and wp.history(s)==h


def test_untouched_piano_default_is_not_inferred_as_a_user_choice():
    from practice_setup_globals import INSTRUMENT_CHANGE_SOURCE_KEY
    s,c=setup(instrument='Piano');s.pop(INSTRUMENT_CHANGE_SOURCE_KEY)
    r=ask(s,c,'Give me a four-note lick in G major.')
    assert not r.notation_abc and wp.current(s) is None
    r=ask(s,c,'Give me a four-note lick for piano in G major.')
    assert r.notation_abc


def test_repeated_pitch_attacks_are_counted_separately_without_ties():
    s,c=setup();ask(s,c,'Give me a four-note lick in G major.')
    spec=copy.deepcopy(wp.current(s)['spec']);spec['degrees']=[0,0,1,4];spec['offsets']=[0,0,2,7]
    p=ac.build(spec);decoded=events(p['items'][0]['abc'])[0]
    assert [m for m,d in decoded if m is not None]==[67,67,69,74]
    assert len(p['items'][0]['written_midi'])==4


def test_new_sequence_from_changed_level_refuses_before_replacing_old_music():
    s,c=setup();ask(s,c,'Give me a four-note lick in G major.');before=current(s)
    s['level']='Beginner'
    r=ask(s,c,'Move it through the whole major scale and back down.')
    assert current(s)==before and 'selected level' in r.direct_answer


def test_revisions_read_current_playback_preference_without_cycle_mutation():
    import backing_key_cycle as kc
    s,c=setup();ask(s,c,'Give me a four-note lick in G major.')
    s[kc.BACKING_KEY_SPELLING_PREFS_KEY]={'F#/Gb':'Gb'};foreign={k:copy.deepcopy(v) for k,v in s.items() if not session_scope.is_conversation_key(k)}
    ask(s,c,'Transpose this lick through twelve keys.')
    assert row(s)['cells'][-1]['concert_key']=='Gb'
    after={k:copy.deepcopy(s[k]) for k in foreign}
    # Existing context reads increment diagnostics; every write/revision/blob and
    # all transport/settings state must remain byte-for-byte equivalent.
    key='_music_workflow_state_store'
    if key in foreign:
        assert after[key]['stats']['reads']>=foreign[key]['stats']['reads']
        after[key]['stats']['reads']=foreign[key]['stats']['reads']
    assert after==foreign


def test_first_review_note_names_match_snapshot_not_active_sequence():
    s,c=setup();initial=ask(s,c,'Give me a four-note lick in G major.')
    ask(s,c,'Transpose this lick through twelve keys.');before=current(s)
    shown=ask(s,c,'Show me the first lick again.');h=wp.history(s)
    names=ask(s,c,'Show me the note names.')
    assert names.notation_abc==initial.notation_abc==shown.notation_abc
    assert len([r for r in names.diagnostics['note_name_rows'] if r['name']!='rest'])==4
    assert current(s)==before and wp.history(s)==h


def test_fresh_sequence_stores_original_tonic_cell_not_entire_traversal():
    s,c=setup();ask(s,c,'Give me a four-note lick in G major and move it through all seven degrees.')
    assert len(row(s)['cells'])==7
    r=ask(s,c,'Show me the first lick again.')
    assert [m for m,d in events(r.notation_abc)[0] if m is not None]==[67,69,71,74]


def test_explicit_instrument_target_survives_revisions_and_user_selection_can_change():
    s,c=setup();ask(s,c,'Give me a four-note lick for alto sax in G major.')
    assert wp.current(s)['player']['key']=='alto'
    ask(s,c,'Make it harder.');assert wp.current(s)['player']['key']=='alto'
    s['instrument']='Clarinet';ask(s,c,'Use quarter notes.')
    assert wp.current(s)['player']['key']=='clarinet' and wp.current(s)['player']['offset']==2


def test_interval_revision_and_tempo_leave_interval_quality_and_count_intact():
    s,c=setup();ask(s,c,'Give me sixths in G major.');ask(s,c,'Do the same exercise in thirds.')
    assert wp.current(s)['spec']['interval']=='thirds'
    pitches=list(row(s)['written_midi']);ask(s,c,'Make it slower.')
    assert row(s)['bpm']==62 and row(s)['written_midi']==pitches
    before=current(s);r=ask(s,c,'Use 300 bpm.');assert current(s)==before and '36 to 160' in r.direct_answer


def test_natural_minor_cell_and_variably_sized_diatonic_thirds():
    s,c=setup(key='Gm');r=ask(s,c,'Give me a four-note lick in G minor.')
    assert row(s)['written_midi']==[67,69,70,74]
    ask(s,c,'Move it through all seven degrees.')
    assert row(s)['cells'][1]['written_midi']==[69,70,72,75]
    assert [m for m,d in events(r.notation_abc)[0] if m is not None]==[67,69,70,74]


def test_cell_slurs_keep_pitches_durations_and_do_not_join_separate_cells():
    s,c=setup();ask(s,c,'Give me a four-note lick in G major.');before=current(s)
    r=ask(s,c,'Add slurs.');assert row(s)['written_midi']==before['items'][0]['written_midi'] and row(s)['durations']==before['items'][0]['durations']
    assert '(' in r.notation_abc and ')' in r.notation_abc
    r=ask(s,c,'Move it through all seven degrees.')
    body='\n'.join(r.notation_abc.splitlines()[6:]);assert body.count('(')==body.count(')')==7
    assert len([m for m,d in events(r.notation_abc)[0] if m is not None])==28


@pytest.mark.parametrize('q',['How do I play altissimo G6 on alto sax?','Give me an overtone exercise from D4.'])
def test_new_cells_cannot_bypass_existing_specialized_sax_gates(q):
    s,c=setup(instrument='Saxophone');ask(s,c,'Give me a four-note lick for alto sax in G major.');before=current(s);h=wp.history(s)
    r=ask(s,c,q);assert r.diagnostics['specialized_generation_supported'] is False
    assert current(s)==before and wp.history(s)==h


def test_explain_names_actual_degree_pattern_and_interval_definition_read_only():
    s,c=setup();ask(s,c,'Give me a four-note lick in G major.');before=current(s);h=wp.history(s)
    r=ask(s,c,'Explain the pattern.')
    assert '1-2-3-5' in r.direct_answer and 'Advanced study' in r.direct_answer
    assert current(s)==before and wp.history(s)==h
    ask(s,c,'Give me sixths in G major.');before=current(s);r=ask(s,c,'Explain the pattern.')
    assert '6 scale degrees' in r.direct_answer and current(s)==before


def test_unknown_selected_level_does_not_infer_an_instrument_window():
    s,c=setup(level='Expert');r=ask(s,c,'Give me a four-note lick in G major.')
    assert wp.current(s) is None and 'no range is inferred' in r.direct_answer
