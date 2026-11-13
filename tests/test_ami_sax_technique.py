"""Independent concrete musical checks for the saxophone technique slice."""
import copy,re
from fractions import Fraction
import pytest
from music_coach_ami import warmup_plan as wp,warmup_engine as we,sax_technique as sx
from tests.test_ami_flexible_single import session,no_api
from music_coach_ami.pipeline import run_coach_submit
from instrument_transposition import SELECTED_TRANSPOSING_INSTRUMENT_KEY
from tests.test_abc_bar_accidentals import read_abc
from tests.song_oracle import read_tune

OFFSETS={'soprano':2,'alto':9,'tenor':14,'baritone':21}
RANGES={'Beginner':(62,79),'Intermediate':(60,84),'Advanced':(58,89)}
def setup():
 s=session();s['instrument']='Saxophone';s[SELECTED_TRANSPOSING_INSTRUMENT_KEY]='Alto saxophone (Eb)';return s

def ask(s,q,level='Intermediate',focus='Scales'):
 r=run_coach_submit(q,s,ami_ctx={'instrument':'Saxophone','level':level,'focus':focus,'display_key':'C'})[1]
 assert r is not None
 return r

def check(p):
 for row in p['items']:
  clean=row['abc'].replace('(','').replace(')','')
  assert read_abc(clean)==row['written_midi']
  assert row['sounding_midi']==[m-OFFSETS[p['player']['key']] for m in row['written_midi']]
  lo,hi=RANGES[p['level']]
  if not p['spec'].get('sax') or p['spec'].get('song'):
   lo,hi=row.get('meta',{}).get('window') or (lo,hi)  # Existing adaptive/song fit policy; hard profile limits remain independently fixed.
  assert all(58<=m<=89 and lo<=m<=hi for m in row['written_midi'])
  tune=read_tune(row['abc']);assert sum((e[1] for e in tune),Fraction())%4==0
  assert row['abc'].count('(')==row['abc'].count(')')
 return p

def start(q,level='Intermediate',focus='Scales'):
 s=setup();r=ask(s,q,level,focus);p=wp.current(s);assert p and p['spec'].get('sax'),r.direct_answer;check(p);return s,p

@pytest.mark.parametrize('who',OFFSETS)
@pytest.mark.parametrize('level',RANGES)
@pytest.mark.parametrize('kind',['thirds','fourths','fifths','sixths','octaves'])
def test_all_saxes_levels_exact_diatonic_pairs(who,level,kind):
 s,p=start(f'Give me a {who} sax exercise in {kind}.',level)
 row=p['items'][0];degree={'thirds':2,'fourths':3,'fifths':4,'sixths':5,'octaves':7}[kind]
 idx=[7*int(re.search(r"(-?\d+)$",n)[1])+'CDEFGAB'.index(n[0]) for n in row['written_notes']]
 assert all(b-a==degree for a,b in zip(idx[::2],idx[1::2]))
 if kind=='octaves':assert all(b-a==12 for a,b in zip(row['written_midi'][::2],row['written_midi'][1::2]))

@pytest.mark.parametrize('prompt',[
 'Give me an alto sax articulation warmup.','Give me a tonguing exercise for tenor sax.',
 'Give me something to improve my legato.','Give me an exercise alternating tongued and slurred notes.',
 'Give me two slurred notes followed by two tongued notes.','Give me a challenging articulation exercise.',
 'Give me an advanced saxophone finger-buster with accents.','Give me something to improve my register transitions.',
 'Give me a difficult interval finger-buster.','Give me an exercise with wide leaps and challenging rhythms.',
 'Give me a chromatic saxophone coordination exercise.'])
def test_natural_requests_are_actual_verified_sax_music(prompt):
 s,p=start(prompt);assert len(p['items'][0]['written_midi'])>=4


def test_fixed_alto_concert_c_thirds_and_transpositions():
 s,p=start('Give me a beginner alto sax exercise in thirds.','Beginner')
 assert p['items'][0]['written_midi']==[62,66,64,68,66,69,68,71]
 assert p['items'][0]['sounding_midi']==[53,57,55,59,57,60,59,62]
 assert s[SELECTED_TRANSPOSING_INSTRUMENT_KEY]=='Alto saxophone (Eb)'


def test_articulation_and_rhythm_revisions_preserve_other_properties_and_history():
 s,p=start('Give me an alto sax exercise in thirds.');row=p['items'][0];old=copy.deepcopy(p)
 ask(s,'Slur every two notes.');a=wp.current(s);check(a)
 assert a['items'][0]['written_midi']==row['written_midi'] and a['items'][0]['durations']==row['durations']
 assert a['items'][0]['slur_groups'][0]==a['items'][0]['slur_groups'][1]!=0
 assert a['items'][0]['slur_groups'][2]==a['items'][0]['slur_groups'][3]!=a['items'][0]['slur_groups'][0]
 ask(s,'Accent the first note of every group.');b=wp.current(s)
 assert b['items'][0]['written_midi']==row['written_midi']
 assert b['items'][0]['articulations']==['accent' if i%4==0 else '' for i in range(len(row['written_midi']))]
 assert '!>!' in b['items'][0]['abc']
 ask(s,'Keep the pitches but make the rhythm more difficult.');c=wp.current(s);check(c)
 assert c['items'][0]['written_midi']==row['written_midi'] and c['items'][0]['durations']!=row['durations']
 assert c['items'][0]['articulations']==b['items'][0]['articulations']
 h=wp.history(s);ask(s,'Explain what technique this develops.');assert wp.current(s)==c and wp.history(s)==h
 ask(s,'Undo.');assert wp.current(s)==b
 ask(s,'Redo.');assert wp.current(s)==c


def test_two_slurred_two_tongued_repeated_and_staccato_symbols():
 s,p=start('Give me two slurred notes followed by two tongued notes.')
 g=p['items'][0]['slur_groups'];assert g[0]==g[1]!=0 and g[2:4]==[0,0]
 s,p=start('Give me a tonguing exercise for tenor sax.')
 assert len(set(p['items'][0]['written_midi']))==1 and not any(p['items'][0]['slur_groups'])
 ask(s,'Use staccato.');p=check(wp.current(s));assert all(a=='staccato' for a in p['items'][0]['articulations']);assert '.' in p['items'][0]['abc']


def test_interval_changes_direction_octaves_and_comfortable_register():
 s,p=start('Give me a fifths exercise that changes direction.')
 m=p['items'][0]['written_midi'];assert m[1]>m[0] and m[3]<m[2]
 ask(s,'Change the fifths to fourths.');p=check(wp.current(s));assert p['spec']['sax']['interval']=='fourths'
 ask(s,'Now make it descending.');p=check(wp.current(s));assert all(b<a for a,b in zip(p['items'][0]['written_midi'][::2],p['items'][0]['written_midi'][1::2]))
 ask(s,'Add octave jumps.');p=check(wp.current(s));assert all(abs(b-a)==12 for a,b in zip(p['items'][0]['written_midi'][::2],p['items'][0]['written_midi'][1::2]))
 ask(s,'Move it into a comfortable register.');check(wp.current(s))


def test_adapt_to_tenor_preserves_sounding_pitches_and_global_selection():
 s,p=start('Give me a beginner alto sax exercise in thirds.','Beginner');before=copy.deepcopy(s)
 r=ask(s,'Adapt this to tenor sax.','Beginner');q=check(wp.current(s));assert q['player']['key']=='tenor',r.direct_answer
 delta=q['items'][0]['sounding_midi'][0]-p['items'][0]['sounding_midi'][0]
 assert delta%12==0 and q['items'][0]['sounding_midi']==[m+delta for m in p['items'][0]['sounding_midi']]
 assert q['items'][0]['durations']==p['items'][0]['durations']
 assert s[SELECTED_TRANSPOSING_INSTRUMENT_KEY]==before[SELECTED_TRANSPOSING_INSTRUMENT_KEY]


def test_timed_routine_vs_single_and_explicit_focus_priority():
 s,p=start('Give me one exercise in thirds.',focus='Articulation');assert p['spec']['single'] and len(p['items'])==1
 assert p['spec']['sax']['recipe']=='intervals'
 s,p=start('Make me a ten-minute tenor saxophone articulation warmup.')
 assert not p['spec'].get('single') and len(p['items'])>1 and p['target_seconds']==600
 assert abs(p['total_seconds']-600)<90
 assert all('Saxophone' in r['title'] for r in p['items'])


@pytest.mark.parametrize('q',['Use altissimo.','Use high F sharp.','Use tied notes.','Use multiphonics.'])
def test_unsupported_refused_exactly(q):
 s,p=start('Give me an alto sax exercise in thirds.');h=wp.history(s);ask(s,q);assert wp.current(s)==p and wp.history(s)==h


def test_workspace_and_account_isolation():
 s,p=start('Give me an alto sax exercise in thirds.');s['_suite_active_workspace_id']='other';ask(s,'Slur every two notes.');assert wp.current(s) is None
 s,p=start('Give me an alto sax exercise in thirds.');s['_suite_auth_user_id']='other';ask(s,'Make it harder.');assert wp.current(s) is None


def test_song_articulation_uses_real_guide_tones_and_rejects_false_interval_labels():
 from tests.song_fixtures import song_session
 from tests.song_oracle import check_tune
 from music_coach_ami import warmup_song as ws
 s=song_session('Blue Bossa');r=ask(s,'Give me an alto sax articulation exercise using the guide tones.')
 p=wp.current(s);assert p and p['spec'].get('song') and p['spec'].get('single_song') and len(p['items'])==1,r.direct_answer
 sel=p['spec']['song_sel'];slots=ws.section_slots(p['spec']['song'],sel['section'])
 for row in p['items']:assert check_tune(row['abc'],slots,9)==[]
 old=copy.deepcopy(p);h=wp.history(s);r=ask(s,'Give me fourths over the bridge.');assert 'not verified' in r.direct_answer and wp.current(s)==old and wp.history(s)==h
 r=ask(s,'Change the thirds to fourths.');assert 'not verified' in r.direct_answer and wp.current(s)==old and wp.history(s)==h


@pytest.mark.parametrize('focus,recipe',[('Articulation','articulation'),('Tone','transition'),('Scales','intervals'),('Technique','coordination')])
def test_general_request_uses_selected_focus_without_instrument_override(focus,recipe):
 s,p=start('Give me an exercise.',focus=focus);assert p['spec']['sax']['recipe']==recipe
 assert p['player']['key']=='alto'


@pytest.mark.parametrize('q',['Give me an alto sax articulation exercise from F#6.','Give me a sax articulation exercise using altissimo.','Give me a soprano sax altissimo exercise.','Give me a tenor sax exercise using high F sharp.','Give me a baritone sax overtone exercise.'])
def test_fresh_unsupported_pitches_do_not_silently_become_an_unrelated_scale(q):
 s=setup();r=ask(s,q);assert wp.current(s) is None and r.diagnostics.get('single_exercise_failed')=='unsupported_sax'


def test_unplayable_exact_tenor_adaptation_is_refused_without_new_version():
 s,p=start('Give me a beginner alto sax articulation exercise.','Beginner');h=wp.history(s)
 r=ask(s,'Adapt this to tenor sax.','Beginner');assert wp.current(s)==p and wp.history(s)==h
 assert 'cannot fit' in r.direct_answer


def test_high_register_profiles_stop_at_f6_without_enabling_high_f_sharp():
 for who,offset in OFFSETS.items():
  p=we.make_player(who,'C');assert p.play_low==58 and p.play_high==89 and p.offset==offset
  s=setup();r=ask(s,f'Give me a high-register exercise for advanced {who} sax.','Advanced')
  plan=check(wp.current(s));assert max(plan['items'][0]['written_midi'])<=89


def test_song_chromatic_approach_is_verified_at_actual_chart_changes():
 from tests.song_fixtures import song_session
 from tests.song_oracle import check_chordline
 from music_coach_ami import warmup_song as ws
 s=song_session('All the Things You Are');r=ask(s,'Give me a chromatic tenor sax finger-buster over the bridge of All the Things You Are.','Advanced')
 p=wp.current(s);assert p and p['spec'].get('song') and p['spec'].get('single_song') and len(p['items'])==1,r.direct_answer
 sel=p['spec']['song_sel'];slots=ws.section_slots(p['spec']['song'],sel['section'])
 for row in p['items']:
  assert row['family']=='approach_notes'
  assert check_chordline(row['abc'],slots,14,approach=True,loop=bool(row['meta'].get('looping')))==[]


def test_timed_articulation_revision_and_undo_preserve_every_pitch_and_duration():
 s,p=start('Give me a five-minute alto sax articulation warmup.');before=copy.deepcopy(p)
 ask(s,'Slur every two notes throughout the whole routine.');new=wp.current(s)
 assert new!=before
 for old,row in zip(before['items'],new['items']):
  assert old['written_midi']==row['written_midi'] and old['durations']==row['durations'] and old['bpm']==row['bpm']
 ask(s,'Undo.');assert wp.current(s)==before
 ask(s,'Redo.');assert wp.current(s)==new



def test_interval_revision_keeps_the_same_phrase_length_rhythm_and_marks():
 s,p=start('Give me an alto sax exercise in thirds.');old=p['items'][0]
 for q in ['Change the thirds to fourths.','Add octave jumps.']:
  ask(s,q);row=check(wp.current(s))['items'][0]
  assert len(row['written_midi'])==len(old['written_midi'])
  assert row['durations']==old['durations'] and row['articulations']==old['articulations'] and row['slur_groups']==old['slur_groups']


def test_register_revision_preserves_phrase_shape_duration_and_marks_by_octave():
 s,p=start('Give me a high-register advanced alto sax articulation exercise.','Advanced');old=p['items'][0]
 ask(s,'Move it into a comfortable register.','Advanced');new=check(wp.current(s))['items'][0]
 assert new['written_midi']==[m-12 for m in old['written_midi']]
 assert new['durations']==old['durations'] and new['articulations']==old['articulations'] and new['slur_groups']==old['slur_groups']


@pytest.mark.parametrize('prompt,families',[
 ('Give me a five-minute alto sax warmup with long tones and articulation.',{'long_tones','articulation'}),
 ('Give me a five-minute tenor sax warmup with scales and thirds.',{'scale','intervals'}),
])
def test_explicit_mixed_routine_preserves_all_requested_families(prompt,families):
 s=setup();r=ask(s,prompt);p=wp.current(s);assert p,r.direct_answer
 assert {row['family'] for row in p['items']}==families
 assert not p['spec'].get('sax')
 check(p)



def test_explicit_mixed_interval_routine_keeps_both_thirds_and_fourths():
 s=setup();r=ask(s,'Give me a five-minute alto sax warmup with thirds and fourths.');p=wp.current(s)
 assert p,r.direct_answer
 assert {row['params']['interval'] for row in p['items']}=={'thirds','fourths'}
 assert not p['spec'].get('sax')
 check(p)


@pytest.mark.parametrize('words,recipe',[('interval','intervals'),('register transitions','transition'),('chromatic coordination','chromatic')])
def test_timed_technical_families_keep_their_actual_pitch_vocabulary(words,recipe):
 s,p=start(f'Make me a five-minute alto sax {words} warmup.')
 assert not p['spec'].get('single') and p['spec']['sax']['recipe']==recipe
 assert p['items'] and p['target_seconds']==300
 if recipe=='transition':assert {m%12 for row in p['items'] for m in row['written_midi']}<={1,2,4,11}
 if recipe=='chromatic':assert any(abs(b-a)==1 for a,b in zip(p['items'][0]['written_midi'],p['items'][0]['written_midi'][1:]))


def test_fixed_register_boundary_is_not_mislabelled_after_sounding_transposition():
 s,p=start('Give me an alto sax register transitions exercise.');h=wp.history(s)
 r=ask(s,'Adapt this to tenor sax.');assert wp.current(s)==p and wp.history(s)==h
 assert 'fixed written C#5/D5' in r.direct_answer



def test_timed_articulation_routine_has_distinct_actual_passages_not_duplicate_labels():
 s,p=start('Make me a ten-minute tenor saxophone articulation warmup.')
 assert len(p['items'])>1
 assert len({tuple(row['written_midi']) for row in p['items']})==len(p['items'])
 assert len({row['title'] for row in p['items']})==len(p['items'])
 assert all(row['params']['pattern']==row['meta']['sax_options']['pattern'] for row in p['items'])


def test_default_interval_routine_parameters_describe_actual_notated_intervals():
 s,p=start('Make me a five-minute alto sax interval warmup.')
 assert {row['params']['interval'] for row in p['items']}=={'thirds','fourths'}
 for row in p['items']:
  assert row['params']['interval']==row['meta']['sax_options']['interval']
  span={'thirds':2,'fourths':3}[row['params']['interval']]
  idx=[7*int(re.search(r"(-?\d+)$",n)[1])+'CDEFGAB'.index(n[0]) for n in row['written_notes']]
  # Every practice pass retains complete pairs, independent of breath rests.
  assert all(b-a==span for a,b in zip(idx[::2],idx[1::2]))


@pytest.mark.parametrize('prompt',[
 'Give me an A minor pentatonic line, accent every third note, slur each pair, starting p and crescendo to f.',
 'Give me a C major phrase with accents.',
 'Give me a saxophone lick with slurs.',
 'Give me a D dorian articulation exercise.',
])
def test_existing_expression_and_mode_requests_retain_their_previous_owner(prompt):
 s=setup();assert sx.handle(prompt,s,{'instrument':'Saxophone','level':'Intermediate','display_key':'C'}) is None
 assert wp.current(s) is None
 s,p=start('Give me an alto sax exercise in thirds.');h=wp.history(s)
 assert sx.handle(prompt,s,{'instrument':'Saxophone','level':'Intermediate','display_key':'C'}) is None
 assert wp.current(s)==p and wp.history(s)==h



def test_sax_articulation_honors_a3_chart_section_instead_of_reading_it_as_a_pitch():
 from tests.song_fixtures import song_session
 from tests.song_oracle import check_tune
 from music_coach_ami import warmup_song as ws
 s=song_session('All the Things You Are');r=ask(s,'Give me a tenor sax articulation exercise using guide tones over the A3 section.')
 p=wp.current(s);assert p and p['spec']['song_sel']['section']=='A3',r.direct_answer
 slots=ws.section_slots(p['spec']['song'],'A3')
 for row in p['items']:assert check_tune(row['abc'],slots,14)==[]
