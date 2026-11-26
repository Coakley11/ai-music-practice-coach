"""Backing melodies (user rules 2026-11-20): Practice Melody and My Uploaded Melodies are exclusive modes; the
Original Melody coexists with either and always leads; an open uploaded panel stops automatic scrolling unless the
Original Melody leads; a three-second manual hold everywhere.

The page behaviour is proven in the browser (scratchpad probe_melmodes.py); these pin the rules and the wiring.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import backing_melody_modes as bmm  # noqa: E402
import lead_sheet_page_follow as lpf  # noqa: E402

APP = (ROOT / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
JS = lpf._CONTROLLER_JS


# ---- modes ---------------------------------------------------------------------------------------------------------

def test_practice_melody_is_the_default_mode_and_only_two_modes_exist():
    assert bmm.MODES == ("practice", "uploaded")
    assert bmm.melody_mode({}) == "practice"
    assert bmm.melody_mode({bmm.MODE_KEY: "uploaded"}) == "uploaded"
    assert bmm.melody_mode({bmm.MODE_KEY: "both"}) == "practice"       # never a third, combined state


def test_a_hand_off_asks_for_practice_mode_once_then_the_widget_owns_it():
    s = {bmm.MODE_KEY: "uploaded"}
    bmm.request_melody_mode(s, "practice")
    assert bmm.apply_pending_melody_mode(s) == "practice"
    assert bmm.PENDING_MODE_KEY not in s
    s[bmm.MODE_KEY] = "uploaded"                                        # the musician switches back
    assert bmm.apply_pending_melody_mode(s) == "uploaded"
    bmm.request_melody_mode(s, "nonsense")
    assert bmm.PENDING_MODE_KEY not in s


def test_the_practice_with_backing_hand_off_switches_backing_to_practice_melody_mode():
    i = APP.index('key="practice_melody_to_backing"')
    hand_off = APP[i:i + 2600]
    assert "request_melody_mode(st.session_state, MODE_PRACTICE)" in hand_off


def test_only_the_active_modes_panels_are_drawn():
    """A hidden display can never take part in scrolling: the other mode's panels are not on the page at all."""
    assert "if _bk_melody_mode == _BK_MODE_PRACTICE and _pmb_melody is not None:" in APP
    assert "elif _bk_melody_mode == _BK_MODE_UPLOADED:" in APP
    up = APP[APP.index("elif _bk_melody_mode == _BK_MODE_UPLOADED:"):APP.index("if _developer_mode_enabled():",
                                                                              APP.index("elif _bk_melody_mode == _BK_MODE_UPLOADED:"))]
    assert "render_uploaded_references(st, st.session_state)" in up and "render_abc" not in up


# ---- uploaded references -------------------------------------------------------------------------------------------

def test_reference_choices_are_per_song_deduplicated_and_pruned_to_what_still_exists():
    s: dict = {}
    bmm.set_selected_reference_ids(s, "catalog|shallow", ["a", "b", "a", ""])
    bmm.set_selected_reference_ids(s, "custom|mine", ["z"])
    assert bmm.selected_reference_ids(s, "catalog|shallow", ["a", "b", "c"]) == ["a", "b"]
    assert bmm.selected_reference_ids(s, "catalog|shallow", ["b"]) == ["b"]        # a deleted one drops out
    assert bmm.selected_reference_ids(s, "custom|mine", ["a", "z"]) == ["z"]        # never carried across songs
    assert bmm.selected_reference_ids(s, "catalog|other", ["a"]) == []


def test_each_uploaded_panel_is_a_keyed_expander_the_controller_recognises():
    assert "st-key-" + bmm.UPLOADED_PANEL_KEY_PREFIX == lpf.UPLOADED_PANEL_CLASS_PREFIX
    assert bmm.uploaded_panel_key("doc 1/x").startswith(bmm.UPLOADED_PANEL_KEY_PREFIX)
    src = (ROOT / "backing_melody_modes.py").read_text(encoding="utf-8")
    # closed, except the panels an explicit "Open in Backing" on Practice just sent here (Slice 2, 2026-11-25)
    assert "expanded=did in opened, key=uploaded_panel_key(did)" in src
    assert bmm.panels_open_from_practice({}, "catalog|shallow") == set()


def test_uploaded_melodies_never_follow_or_highlight():
    src = (ROOT / "backing_melody_modes.py").read_text(encoding="utf-8")
    panel = (ROOT / "song_document_panel.py").read_text(encoding="utf-8")
    for text in (src, panel):
        assert "__lsFollow" not in text and "render_abc" not in text and "measure_sync" not in text


def test_several_open_references_each_keep_their_own_page():
    panel = (ROOT / "song_document_panel.py").read_text(encoding="utf-8")
    ref = panel[panel.index("def render_song_document_reference("):panel.index("def render_song_documents_panel(")]
    assert 'reader=f"::{namespace}{did}::"' in ref
    prev = panel[panel.index("def _preview("):panel.index("def render_song_document_reference(")]
    assert "st.session_state[PAGE_KEY + reader]" in prev and "key_prefix = KEY_PREFIX + reader" in prev


# ---- Original Melody -----------------------------------------------------------------------------------------------

def test_a_composition_melody_is_the_original_melody(monkeypatch):
    import composition_songs_bridge as csb

    monkeypatch.setattr(csb, "composition_section_melody_events", lambda doc: {"Verse": [{"pitch": "C4"}]})
    secs, source = bmm.original_melody_sections(composition_doc={"sections": []}, song_data=None)
    assert source == "composition" and secs == {"Verse": [{"pitch": "C4"}]}


def test_a_future_synchronized_catalog_melody_is_accepted_but_nothing_else():
    good = {"original_melody": {"synchronized": True, "sections": {"Verse": [{"pitch": "E4", "beat": 0}]}}}
    secs, source = bmm.original_melody_sections(composition_doc=None, song_data=good)
    assert source == "song" and list(secs) == ["Verse"]
    for bad in ({"original_melody": {"sections": {"Verse": [{"pitch": "E4"}]}}},          # not synchronized
                {"original_melody": {"synchronized": True, "pdf": "melody.pdf"}},         # an uploaded PDF
                {"original_melody": {"synchronized": True, "sections": {"Verse": []}}},
                {"title": "Shallow"}, None):
        assert bmm.original_melody_sections(composition_doc=None, song_data=bad) == ({}, "")


def test_backing_takes_its_original_melody_from_the_one_source_agnostic_hook():
    start = APP.index("# ----- Original Melody panel -----")
    om = APP[start:APP.index('follow_role="original-melody")', start)]
    assert "_bk_original_melody_sections(" in om
    assert "if _bk_comp_doc:" not in om                                  # no longer Composition-only
    assert 'if _bk_om_source == "composition":' in om                    # lyric alignment stays Composition's


# ---- the controller ------------------------------------------------------------------------------------------------

def test_an_open_uploaded_panel_lets_only_a_melody_staff_lead():
    act = JS[JS.index("C.blocked = function ()"):JS.index("function transportProvider()")]
    assert 'details[open]' in act and "UPREF" in act
    assert "cap = C.blocked() ? MELODY_PRIORITY : -1" in act
    assert "if (pr0 < cap) return;" in act
    assert lpf.ORIGINAL_MELODY_PRIORITY > lpf.MELODY_PRIORITY > lpf.LEAD_SHEET_PRIORITY
    code = lpf.page_follow_controller_js()
    assert "__PM_PRIO__" not in code and "__UPREF__" not in code


def test_with_nothing_eligible_a_follow_request_moves_nothing():
    req = JS[JS.index("C.request = function"):JS.index("// ---- compact transport")]
    assert "if (!p && C.blocked()) return false;" in req


def test_scrolling_a_pdf_leaves_no_hold_behind_when_it_is_why_nothing_follows():
    tick = JS[JS.index("var timer = top.setInterval("):]
    assert "if (C.blocked() && !activeProvider()) { C.lastInteraction = 0; C.wasSuspended = false; }" in tick
    assert tick.index("C.lastInteraction = 0") < tick.index("var s = C.suspended();")


def test_the_lead_sheets_own_box_obeys_the_same_rule():
    assert "function followBlocked()" in APP
    assert "if (!el || !el.isConnected || followHeld() || followBlocked()) return false;" in APP


def test_a_new_controller_version_replaces_pages_that_still_run_the_old_one():
    assert lpf.CONTROLLER_VERSION >= 6


def test_three_seconds_is_the_hold_everywhere():
    assert lpf.HOLD_MS == 3000
    lowered = APP.lower()
    assert "six-second" not in lowered and "six seconds" not in lowered and "6 s manual hold" not in lowered


def test_one_destination_the_singing_panel_leads_with_the_lead_sheet_open_or_closed():
    """Voice / Karaoke: one destination at a time. User rule 2026-11-21 (superseding 2026-11-20's open-sheet rule):
    the lit lyric line, else the singing panel itself, leads whether the Lead Sheet is open or closed."""
    i = APP.index("function highlightActiveLine(event)")
    body = APP[i:APP.index("window.__karaokeUpdateLyricPanel = function", i)]
    assert "window.__karaokeBoxFollow(activeLine)" in body
    assert "lyricTarget === activeLine && window.__karaokeBoxFollow" in body
    tgt = APP[APP.index("function karaokeFollowTarget()"):APP.index("let lastBoxTarget = null;")]
    assert "leadSheetOpenOnPage()" not in tgt
    # The lit lyric line, else the singing panel itself (user rule 2026-11-21) - never the chart while there is a panel.
    assert "return karaokePanelEl() || (chartIsPrimary() ? chord : null);" in tgt


def test_in_normal_voice_the_full_height_sheet_follows_the_lyrics_when_the_lead_sheet_is_closed():
    """Normal Voice has PAGE_FOLLOW and the singing lyrics in one frame; the lyrics provider owns it. The chord-change
    request must follow that provider's target (lyric line with the Lead Sheet closed), never the chord regardless."""
    i = APP.index("if (eventChanged && PAGE_FOLLOW) {{")
    branch = APP[i:APP.index("}} else if (eventChanged && clock && !clock.paused) {{", i)]
    assert "const lyricLead = KARAOKE_HOLD ? karaokeFollowTarget() : null;" in branch
    # A lyric line or the singing panel itself (a song without lyrics) is the singing target (user rule 2026-11-21).
    assert "toLyric = !!(lyricLead && window.__karaokeIsPanelTarget && window.__karaokeIsPanelTarget(lyricLead))" in branch
    assert 'request("lead-sheet", toLyric ? lyricLead : currentCell, {{ why: toLyric ? "karaoke-lyric" : "chord" }})' in branch


def test_open_in_backing_opens_the_panels_for_one_backing_visit_only():
    """QA 2026-11-26 (browser): Songs -> Backing reopened both panels, even one the musician had closed."""
    s = {}
    bmm.open_in_backing(s, "custom|trial", ["a", "b"])
    bmm.note_studio_page(s, "practice")              # the run that pressed it: still wanted
    assert bmm.panels_open_from_practice(s, "custom|trial") == {"a", "b"}
    bmm.note_studio_page(s, "backing")
    assert bmm.panels_open_from_practice(s, "custom|trial") == {"a", "b"}
    bmm.mark_open_from_practice_shown(s)             # Backing drew them
    bmm.note_studio_page(s, "backing")               # reruns on the same visit keep the request
    assert bmm.panels_open_from_practice(s, "custom|trial") == {"a", "b"}
    bmm.note_studio_page(s, "picker")                # left Backing: the visit is over
    assert bmm.panels_open_from_practice(s, "custom|trial") == set()
    bmm.note_studio_page(s, "backing")
    assert bmm.panels_open_from_practice(s, "custom|trial") == set()


def test_a_request_backing_never_drew_survives_other_pages():
    s = {}
    bmm.open_in_backing(s, "custom|trial", ["a"])
    bmm.note_studio_page(s, "songs")
    assert bmm.panels_open_from_practice(s, "custom|trial") == {"a"}


def test_the_app_tells_backing_melody_modes_which_page_is_drawn():
    src = (Path(__file__).resolve().parents[1] / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
    i = src.index("note_page_visit(st.session_state, _studio_page)")
    assert "_bmm_note_studio_page(st.session_state, _studio_page)" in src[i:i + 400]
