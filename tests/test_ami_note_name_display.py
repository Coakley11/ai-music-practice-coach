"""Independent presentation defaults, written pitches and read-only controls."""
import copy
import pytest
from music_coach_ami import note_name_display as nd, warmup_plan as wp, conversation_state as cs
from music_coach_ami.pipeline import run_coach_submit
from music_coach_ami.musical_idea_engine import MusicalEvent
from tests.test_ami_scale_pattern_exercise import ctx,session
from tests.test_abc_bar_accidentals import read_abc


def submit(s,q,level="Intermediate",instrument="Flute"):
    return run_coach_submit(q,s,ami_ctx=ctx(instrument=instrument,level=level))[1]


def test_written_event_rows_include_octave_rest_and_split_chord_boundary():
    events=[MusicalEvent("Bb",4,"half",0,0,chord="Gm"),MusicalEvent("",0,"quarter",0,2,chord="C7"),MusicalEvent("E",5,"quarter",0,3)]
    before=copy.deepcopy(events)
    assert nd.rows_from_events(events)==[
        {"bar":1,"beat":1.,"name":"Bb4","duration":"half","chord":"Gm","voice":""},
        {"bar":1,"beat":3.,"name":"rest","duration":"quarter","chord":"C7","voice":""},
        {"bar":1,"beat":4.,"name":"E5","duration":"quarter","chord":"C7","voice":""}]
    assert events==before


def test_filter_preserves_harmonic_and_technique_explanations():
    source="Title\n- Bar 3 (Gm): D E G A C Bb G\n- Bar 4: F#4 G4 A4\n- Keep the slur connected.\n- Bar 4: target the third of D7.\n- C7: E is the third."
    assert nd.clean_markdown(source)=="Title\n- Keep the slur connected.\n- Bar 4: target the third of D7.\n- C7: E is the third."


@pytest.mark.parametrize("level",["Beginner","Intermediate","Advanced"])
def test_actual_scale_rows_match_the_native_written_abc(level):
    s=session();r=submit(s,"Give me a C major scale pattern",level)
    rows=r.diagnostics["note_name_rows"];assert rows
    from music_coach_ami.scale_pattern_harmony import midi_of
    assert [midi_of(x["name"][:-1],int(x["name"][-1])) for x in rows if x["name"]!="rest"]==read_abc(r.notation_abc)


@pytest.mark.parametrize("question",["Show me the note names.","Hide the note names.","What are the notes in measure 4?","Explain the notes in this exercise."])
def test_explicit_display_requests_do_not_create_or_change_history(question):
    s=session();r=submit(s,"Give me a C major scale pattern")
    previous=copy.deepcopy(cs.current_version(s));history=copy.deepcopy(cs.history(s));plan=copy.deepcopy(wp.current(s))
    shown=submit(s,question)
    assert shown.source_solver=="NoteNameDisplay" and shown.notation_abc==r.notation_abc
    assert cs.current_version(s)==previous and cs.history(s)==history and wp.current(s)==plan
    if "measure 4" in question:assert all(x["bar"]==4 for x in shown.diagnostics["note_name_rows"])


def test_explicit_preference_is_owner_scoped():
    s=session();submit(s,"Give me a C major scale pattern");submit(s,"Show me the note names.")
    assert s[nd.PREFIX+"preference"] is True
    s["_suite_active_workspace_id"]="other"
    response=submit(s,"Show me the note names.")
    assert "no verified stored" in response.direct_answer and nd.PREFIX+"preference" not in s


def test_transposed_alto_scale_matches_written_staff_not_concert_names():
    s=session("Saxophone","Alto Saxophone");r=submit(s,"Give me a C major scale pattern",instrument="Saxophone")
    rows=r.diagnostics["note_name_rows"];assert rows
    from music_coach_ami.scale_pattern_harmony import midi_of
    assert [midi_of(x["name"][:-1],int(x["name"][-1])) for x in rows if x["name"]!="rest"]==read_abc(r.notation_abc)
    assert any(x["name"].startswith("F#") or x["name"].startswith("C#") or x["name"].startswith("G#") for x in rows)


def test_no_claimed_names_when_no_exercise_exists():
    r=submit(session(),"What are the notes in measure 4?")
    assert "no verified stored" in r.direct_answer and not r.notation_abc


def test_inline_written_transcription_is_hidden_without_losing_technique():
    assert nd.clean_markdown("Title. Written notes: G4, A4, Bb4. Keep the octave thumb coordinated.")=="Title. Keep the octave thumb coordinated."


def test_scale_revision_undo_redo_names_follow_the_stored_version():
    s=session();first=submit(s,"Give me a C major scale pattern")
    slower=submit(s,"Make it slower")
    undo=submit(s,"Undo");redo=submit(s,"Redo")
    assert undo.notation_abc==first.notation_abc and redo.notation_abc==slower.notation_abc
    assert undo.diagnostics["note_name_rows"]==first.diagnostics["note_name_rows"]
    assert redo.diagnostics["note_name_rows"]==slower.diagnostics["note_name_rows"]


@pytest.mark.parametrize("level,expected",[("Beginner",True),("Intermediate",False),("Advanced",False)])
def test_selected_level_controls_default_not_exercise_complexity(level,expected):
    s={"level":level,"exercise_level":"Advanced"}
    assert nd.show_by_default(s) is expected
    for choice in (True,False):
        s[nd.PREFIX+"preference"]=choice
        assert nd.show_by_default(s) is choice


def test_live_level_changes_do_not_change_stored_music():
    s={"level":"Beginner","stored_notes":["G4","A4","B4","D5"],"timing":[1,1,1,1]}
    before=copy.deepcopy(s)
    assert nd.show_by_default(s)
    s["level"]="Intermediate"
    assert not nd.show_by_default(s) and s["stored_notes"]==before["stored_notes"] and s["timing"]==before["timing"]


def test_note_query_follows_readonly_warmup_navigation():
    s=session();created=submit(s,"Give me a five-minute warmup")
    assert created.diagnostics.get("warmup_plan_id")
    viewed=wp.step_view(s,1);assert viewed
    history=copy.deepcopy(wp.history(s));plan=copy.deepcopy(wp.current(s))
    response=submit(s,"Show me the note names")
    assert response.notation_abc==viewed.notation_abc
    assert wp.history(s)==history and wp.current(s)==plan
    assert {r["exercise"] for r in response.diagnostics["note_name_rows"]}=={plan["items"][history["view"]["index"]]["title"]}


def test_lick_presentation_rows_survive_filtered_submit_diagnostics(monkeypatch):
    from unittest.mock import MagicMock
    from music_coach_ami.submit_integration import stage_routed_music_coach_insight
    from applied_math_return_insight import SESSION_PENDING_KEY
    s=session();req,r=run_coach_submit("Give me an advanced jazz lick in G major.",s,ami_ctx=ctx(level="Advanced"))
    rows=copy.deepcopy(r.diagnostics["note_name_rows"]);assert rows
    monkeypatch.setattr("applied_math_return_insight.store_applied_math_insight",lambda *a,**kw:"review")
    monkeypatch.setattr("applied_math_return_insight.stage_pending_insight",lambda *a,**kw:None)
    st=MagicMock();st.session_state=s
    stage_routed_music_coach_insight(st,s,question=req.raw_question,source_page="practice",coach_req=req,coach_resp=r,diagnostics={"result_path":"routed_coach"})
    assert s[SESSION_PENDING_KEY]["note_name_rows"]==rows
    r.diagnostics["note_name_rows"][0]["name"]="tampered"
    assert s[SESSION_PENDING_KEY]["note_name_rows"]==rows
