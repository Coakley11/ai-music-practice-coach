import copy
import pytest
from tests.test_ami_bass_technique import start
from tests.test_ami_flexible_single import session,ask,no_api
from tests.bass_tab_oracle import check
from music_coach_ami import warmup_plan as wp,bass_tab as tab,warmup_engine as we,bass_technique as bass

@pytest.mark.parametrize('q',['Give me an E minor bass scale.','Give me a bass guitar finger-buster.','Give me a difficult bass arpeggio.','Give me a bass exercise using octaves.','Give me bass finger coordination.','Give me a beginner bass guitar warmup.'])
def test_same_notes_frets_rhythm_and_barlines(q):
    s=session();p=start(s,q);assert check(p)==[],check(p)
    r=ask(s,'Show me the TAB.');assert r.diagnostics['bass_tab_sections'] and wp.current(s)==p


def test_exact_open_e_and_d_string_e_with_quarters():
    p=start(session());t=p['items'][0]['meta']['bass_tab']
    a,b=t['events'][0],t['events'][7]
    assert (a['written_midi'],a['sounding_midi'],a['string'],a['fret'],a['bar'],a['beat'])==(40,28,4,0,0,1)
    assert (b['written_midi'],b['sounding_midi'],b['string'],b['fret'],b['bar'],b['beat'])==(52,40,2,2,1,4)


@pytest.mark.parametrize('unit',['whole','half','quarter','eighth','sixteenth'])
def test_durations_rests_repeats_and_sustain(unit):
    notes=we._fill_bar([we.Note('E',2,unit),we.Note('E',2,unit),we.Note('',0,unit)])
    b=we.Built(notes,72,'test',[],[],{});bass.certify(b,'Advanced');player=we.make_player('bass','C');abc,_=we.render(player,b,'C','major',title='test')
    t=tab.timeline(b,'Advanced',72,abc)
    assert t['events'][0]['written_midi']==t['events'][1]['written_midi']==40
    assert not t['events'][0]['rest'] and t['events'][2]['rest']
    assert sum(we.Fraction(*e['beats']) for e in t['events'])==4*t['bars']


def test_specific_string_position_and_different_string_exact_history():
    s=session();p=start(s,'Give me an advanced bass scale in E minor on the E string.')
    assert {p['string'] for p in p['items'][0]['meta']['positions']}=={4}
    assert check(p)==[]
    before=copy.deepcopy(p);ask(s,'Play this on a different string.');p=wp.current(s)
    # Explicit same-string rule must be removed for a deliberate different-string request.
    assert p!=before
    assert p['items'][0]['written_midi']==before['items'][0]['written_midi']
    assert check(p)==[]
    ask(s,'Undo.');assert wp.current(s)==before
    ask(s,'Redo.');assert wp.current(s)==p
    hist=wp.history(s);ask(s,'Show me the TAB.');ask(s,'Explain why this pattern works.');assert wp.current(s)==p and wp.history(s)==hist
    r=ask(s,'Play this on the G string.');assert wp.current(s)==p


def test_position_cells_are_generated_in_the_requested_window():
    p=start(session(),'Give me advanced bass coordination in position 5.')
    assert all(x['hand_low']==5 for x in p['items'][0]['meta']['positions'])
    assert check(p)==[]


def test_rhythm_revision_preserves_fingering_and_synchronizes_padding_rests():
    s=session();p=start(s,'Give me an intermediate E minor bass scale.');old=copy.deepcopy(p)
    ask(s,'Make the rhythm faster.');p=wp.current(s)
    assert p['items'][0]['meta']['positions']==old['items'][0]['meta']['positions']
    assert p['items'][0]['written_midi']==old['items'][0]['written_midi']
    assert p['items'][0]['meta']['bass_tab']!=old['items'][0]['meta']['bass_tab']
    assert check(p)==[]
    ask(s,'Undo.');assert wp.current(s)==old


def test_open_strings_more_crossings_and_unplayable_position_are_bounded():
    s=session();p=start(s,'Give me an intermediate E minor bass scale.')
    ask(s,'Use the open strings.');p=wp.current(s);assert any(x['fret']==0 for x in p['items'][0]['meta']['positions']);assert check(p)==[]
    ask(s,'Use more string crossings.');p=wp.current(s);assert check(p)==[]
    old=copy.deepcopy(p);h=wp.history(s);ask(s,'Use position 20.');assert wp.current(s)==old and wp.history(s)==h
    ask(s,'Use tied notes.');assert wp.current(s)==old and wp.history(s)==h


@pytest.mark.parametrize('field',['onset','beats','string','fret','written_midi','bar','rest'])
def test_independent_oracle_rejects_corrupt_projection(field):
    p=start(session());bad=copy.deepcopy(p);e=bad['items'][0]['meta']['bass_tab']['events'][0]
    if field in ['onset','beats']:e[field]=[99,1]
    elif field=='rest':e[field]=True
    else:e[field]+=1
    assert check(bad)


def test_scope_and_other_instrument_no_tab():
    s=session();start(s);s['_suite_active_workspace_id']='other';r=ask(s,'Show me the TAB.');assert not r.diagnostics.get('bass_tab_sections')
    s=session();r=ask(s,'Give me a flute scale in C major.');assert not r.diagnostics.get('bass_tab_sections')


def test_chart_split_bars_keep_exact_timeline():
    from tests.song_fixtures import song_session
    s=song_session();ask(s,'Give me a bass line over these chord changes.',level='Intermediate')
    p=wp.current(s);assert check(p)==[]
    assert any(e['chord'] for e in p['items'][0]['meta']['bass_tab']['events'])


def test_ties_and_cross_bar_sustain_are_not_invented():
    b=we.Built([we.Note('E',2,'whole'),we.Note('E',2,'half')],60,'test',[],[],{'positions':[]})
    with pytest.raises(we.WarmupUnavailable):tab.timeline(b,'Beginner',60,'unused')


def test_embedded_renderer_has_real_javascript_boundary_and_safe_json():
    from music_coach_ami.bass_tab_view import render_call
    result=render_call('score','</script>',{'abc':'</script>'})
    assert '\namiRenderBassTab(' in result
    assert r'\namiRenderBassTab(' not in result
    assert '</script>' not in result
    import json
    call=result.split('\namiRenderBassTab(',1)[1][:-2]
    assert json.loads('['+call+']')[1]=='</script>'


def test_legacy_version_is_not_retranscribed_or_mutated_for_show_tab():
    s=session();p=start(s);p['items'][0]['meta'].pop('bass_tab')
    wp._push(s,p,'legacy',fresh=True);old=copy.deepcopy(wp.current(s));h=wp.history(s)
    r=ask(s,'Show me the TAB.')
    assert 'predates' in r.direct_answer and not r.diagnostics.get('bass_tab_sections')
    assert wp.current(s)==old and wp.history(s)==h


def test_full_warmup_fingering_revision_and_navigation_restore_exactly():
    s=session();p=start(s,'Give me an intermediate bass guitar warmup in E minor.')
    wp.step_view(s,1);before=copy.deepcopy(wp.current(s));ask(s,'Play this on a different string.');new=wp.current(s)
    assert new!=before and check(new)==[]
    assert [r['written_midi'] for r in new['items']]==[r['written_midi'] for r in before['items']]
    ask(s,'Undo.');assert wp.current(s)==before
    ask(s,'Redo.');assert wp.current(s)==new
    r=wp.step_view(s,1);assert len(r.diagnostics['bass_tab_sections'])==1


def test_actual_satin_doll_split_measure_chords_keep_onsets():
    from tests.song_fixtures import song_session
    from tests.song_oracle import read_tune
    s=song_session('Satin Doll');ask(s,'Give me a bass line over these chord changes.',level='Intermediate')
    p=wp.current(s);assert check(p)==[]
    row=p['items'][0];events=row['meta']['bass_tab']['events'];tune=read_tune(row['abc'])
    assert any(e['chord'] and e['beat']!=1 for e in events)
    for event,actual in zip(events,tune):
        if event['chord']:assert event['chord']==actual[3]


def test_refused_revision_keeps_both_staff_and_selected_tab_in_response():
    s=session();p=start(s);h=wp.history(s)
    r=ask(s,'Use tied notes.')
    assert wp.current(s)==p and wp.history(s)==h
    assert r.notation_abc==p['items'][0]['abc']
    assert r.diagnostics['bass_tab_sections']==[p['items'][0]['meta']['bass_tab']]
