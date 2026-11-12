"""Permanent bass acceptance, independent physical/musical checks and mutations."""
import copy
import pytest
from tests.test_ami_flexible_single import no_api,session,ask
from tests.bass_oracle import check
from music_coach_ami import warmup_plan as wp, warmup_engine as we, bass_technique as bass


def start(s,q='Give me an E minor bass scale.',level='Beginner',focus='Technique',instrument='Saxophone'):
    r=ask(s,q,level=level,focus=focus,instrument=instrument)
    p=wp.current(s)
    assert p,r.direct_answer
    assert not r.diagnostics.get('single_exercise_failed'),r.direct_answer
    assert check(p)==[],check(p)
    return p


def test_open_strings_octave_clef_and_actual_e_minor_notes():
    p=start(session());r=p['items'][0]
    assert bass.OPEN==((4,'E',28),(3,'A',33),(2,'D',38),(1,'G',43))
    assert we.make_player('bass','Em').offset==12
    assert r['written_midi']==[40,42,43,45,47,48,50,52]
    assert r['sounding_midi']==[28,30,31,33,35,36,38,40]
    assert r['written_notes']==['E2','F#2','G2','A2','B2','C3','D3','E3']
    assert [(p['string'],p['fret']) for p in r['meta']['positions']]==[(4,0),(4,2),(4,3),(3,0),(3,2),(3,3),(2,0),(2,2)]


@pytest.mark.parametrize('level',['Beginner','Intermediate','Advanced'])
@pytest.mark.parametrize('family',['scale','arpeggio','octaves','coordination'])
@pytest.mark.parametrize('key',['E minor','A minor','G major','C major'])
def test_notes_and_frets_for_levels_keys_and_families(level,family,key):
    s=session();p=start(s,f'Give me a {level} bass {family} exercise in {key}.',level)
    row=p['items'][0]
    allowed={0,2,4,5,7,9,11} if key.endswith('major') and key[0]=='C' else None
    if family=='octaves':assert all(abs(b-a)==12 for a,b in zip(row['written_midi'][::2],row['written_midi'][1::2]))
    if family=='arpeggio':
        root={'E':4,'A':9,'G':7,'C':0}[key[0]]
        assert {m%12 for m in row['sounding_midi']}=={root,(root+(3 if 'minor' in key else 4))%12,(root+7)%12}
    root={'E':4,'A':9,'G':7,'C':0}[key[0]]
    steps=(0,2,3,5,7,8,10) if 'minor' in key else (0,2,4,5,7,9,11)
    if family!='arpeggio':assert all((m-root)%12 in steps for m in row['sounding_midi'])
    if family=='coordination':assert {x['string'] for x in row['meta']['positions']}=={1,2,3,4}
    if allowed:assert all(m%12 in allowed for m in row['sounding_midi'])


def test_explicit_override_sidebar_fallback_and_focus():
    s=session();before=copy.deepcopy(s)
    p=start(s,'Give me a bass guitar exercise in E minor.',instrument='Saxophone')
    assert p['player']['key']=='bass' and s['instrument']==before['instrument']
    s=session();s['instrument']='Bass Guitar'
    p=start(s,'Give me an exercise.',instrument='Bass Guitar',focus='Harmony',level='Intermediate')
    assert p['spec']['family']=='arpeggio' and p['spec']['level']=='Intermediate'
    s=session();s['instrument']='Bass Guitar'
    p=start(s,'Give me an exercise.',instrument='Bass Guitar',focus='Articulation')
    assert p['spec']['articulation']=='staccato'


@pytest.mark.parametrize('focus,required',[('Technique',{'scale','intervals','articulation'}),('Harmony',{'bass_arpeggio','scale'}),('Melody',{'scale','intervals'}),('Articulation',{'articulation','scale'}),('Tone',{'long_tones','scale'})])
def test_full_warmup_reuses_adaptive_architecture(focus,required):
    p=start(session(),'Give me a beginner bass guitar warmup in E minor.',focus=focus)
    assert not p['spec'].get('single')
    assert set(p['spec']['families'])==required
    assert abs(p['total_seconds']-600)<=48
    for r in p['items']:assert not any(x in ' '.join(r['how']).lower() for x in ['tongue','embouchure','breath'])


def test_revisions_identity_exact_history_explain_and_refusal():
    s=session();p=start(s,'Give me an intermediate bass arpeggio in E minor.');identity={k:p['spec'][k] for k in ['instrument','concert_key','family']}
    for q in ['Make it harder.','Move it to a lower register.','Start on the fifth.','Use octave jumps.','Make it descending.','Add some string crossings.','Make it slower.']:
        old=copy.deepcopy(wp.current(s));r=ask(s,q);p=wp.current(s)
        assert not r.diagnostics.get('single_exercise_failed'),r.direct_answer
        assert {k:p['spec'][k] for k in identity}==identity
        assert check(p)==[]
        if old!=p:
            ask(s,'Undo.');assert wp.current(s)==old
            ask(s,'Redo.');assert wp.current(s)==p
    h=copy.deepcopy(wp.history(s));ask(s,'Explain why this pattern works.');assert wp.current(s)==p and wp.history(s)==h
    ask(s,'Use slap and harmonics.');assert wp.current(s)==p and wp.history(s)==h


def test_advanced_buster_and_arpeggio_are_permutations_with_crossings():
    for q in ['Give me a bass guitar finger-buster.','Give me a difficult bass arpeggio exercise.']:
        p=start(session(),q);r=p['items'][0]
        assert p['level']=='Advanced' and len(r['written_midi'])>=12
        assert len({x['string'] for x in r['meta']['positions']})>=2
        assert any(a>b for a,b in zip(r['written_midi'],r['written_midi'][1:]))
        assert any(a<b for a,b in zip(r['written_midi'],r['written_midi'][1:]))


@pytest.mark.parametrize('field',['fret','string','hand_low','written_midi','sounding_midi'])
def test_independent_oracle_rejects_corrupt_position(field):
    p=start(session());bad=copy.deepcopy(p);bad['items'][0]['meta']['positions'][0][field]+=9
    assert check(bad)


def test_missing_note_octave_error_and_outside_register_fail_oracle():
    p=start(session())
    for kind in ['missing','octave','register']:
        bad=copy.deepcopy(p);r=bad['items'][0]
        if kind=='missing':r['meta']['positions'].pop()
        elif kind=='octave':r['sounding_midi']=[x+12 for x in r['sounding_midi']]
        else:r['written_midi'][0]=20
        assert check(bad)


def test_scope_isolation():
    s=session();start(s);s['_suite_active_workspace_id']='two';assert wp.current(s) is None
    start(s);s['_suite_auth_user_id']='different';assert wp.current(s) is None


@pytest.mark.parametrize('q',['Give me a five-string bass exercise.','Give me a double bass scale.','Give me a slap bass exercise.','Give me a bass exercise in drop D tuning.','Give me a fretless bass exercise.'])
def test_unsupported_never_mutates(q):
    s=session();p=start(s);h=wp.history(s);ask(s,q);assert wp.current(s)==p and wp.history(s)==h


def test_song_bass_uses_actual_chart_and_independent_harmonic_oracle():
    from tests.song_fixtures import song_session,activate_song
    from tests.test_ami_warmup_chordlines import slots_of
    from tests.song_oracle import check_chordline
    s=song_session();activate_song(s,'Blue Bossa')
    r=ask(s,'Give me a bass line over these chord changes.',level='Intermediate',focus='Harmony')
    p=wp.current(s);assert p,r.direct_answer
    assert p['spec']['song']['title']=='Blue Bossa' and p['spec']['single_song']
    assert p['player']['offset']==12 and len(p['items'])==1
    assert check(p)==[]
    assert check_chordline(p['items'][0]['abc'],slots_of(p),12,approach=False)==[]


def test_no_chart_bass_line_refuses_instead_of_inventing_changes():
    s=session();r=ask(s,'Give me a bass line over these chord changes.');assert wp.current(s) is None
    assert r.diagnostics.get('warmup_failed') or 'chart' in r.direct_answer.lower()


def test_beginner_speed_and_missing_octave_never_escape_boundaries():
    s=session();p=start(s);h=wp.history(s)
    for q in ['Use sixteenth notes.','Use 160 BPM.','Give me a beginner bass scale in D major.']:
        ask(s,q);assert wp.current(s)==p and wp.history(s)==h


def test_full_warmup_sustain_variants_are_distinct():
    p=start(session(),'Give me a beginner bass guitar warmup.',focus='Tone')
    rows=[r for r in p['items'] if r['family']=='long_tones']
    assert len({tuple(r['written_midi']) for r in rows})==len(rows)


def test_octaves_follow_real_two_string_two_fret_geometry_in_low_e():
    p=start(session(),'Give me a beginner bass exercise using octaves in E minor.')
    path=p['items'][0]['meta']['positions']
    a,b=path[:2]
    assert b['sounding_midi']-a['sounding_midi']==12
    assert a['string']-b['string']==2 and b['fret']-a['fret']==2


def test_real_register_change_preserves_key_family_and_restores_exactly():
    s=session();p=start(s,'Give me an advanced high-register bass scale in E minor.')
    assert min(p['items'][0]['written_midi'])==52
    ask(s,'Move it to a lower register.');low=wp.current(s)
    assert low['items'][0]['written_midi']==[x-12 for x in p['items'][0]['written_midi']]
    assert check(low)==[]
    ask(s,'Undo.');assert wp.current(s)==p
    ask(s,'Redo.');assert wp.current(s)==low


@pytest.mark.parametrize('key',['Bb','D','Eb','F#'])
def test_warmup_shifted_key_segments_remain_bounded_and_allocate(key):
    from music_coach_ami.pipeline import run_coach_submit
    s=session()
    r=run_coach_submit('Give me a beginner bass guitar warmup.',s,ami_ctx={'instrument':'Saxophone','level':'Beginner','focus':'Scales','display_key':key})[1]
    p=wp.current(s);assert p,r.direct_answer
    assert p['spec']['concert_key']==key
    assert abs(p['total_seconds']-600)<=48
    assert check(p)==[]


def test_unavailable_variant_retry_limit_refuses_without_corrupting_history(monkeypatch):
    s=session();old=start(s);history=wp.history(s)
    original=wp.build_item
    def reject_variant(player,spec,desc):
        if desc['family']=='intervals' and desc['params'].get('variant')==1:
            raise we.WarmupUnavailable('test physically unavailable variant')
        return original(player,spec,desc)
    monkeypatch.setattr(wp,'build_item',reject_variant)
    from music_coach_ami.pipeline import run_coach_submit
    r=run_coach_submit('Give me a beginner bass guitar warmup.',s,ami_ctx={'instrument':'Saxophone','level':'Beginner','focus':'Scales','display_key':'Bb'})[1]
    assert wp.current(s)==old and wp.history(s)==history
    assert 'couldn' in r.direct_answer.lower()
