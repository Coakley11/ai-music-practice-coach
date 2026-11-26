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

def test_two_independent_sections_and_the_uploaded_one_starts_closed():
    assert bmm.MODES == ("practice", "uploaded")
    assert bmm.uploaded_section_open({}) is False
    assert bmm.uploaded_section_open({bmm.UPLOADED_OPEN_KEY: True}) is True
    # A session still holding the old single choice "uploaded" had that section on screen: it stays open.
    assert bmm.uploaded_section_open({bmm.MODE_KEY: "uploaded"}) is True
    assert bmm.uploaded_section_open({bmm.MODE_KEY: "practice"}) is False
    s = {bmm.MODE_KEY: "uploaded"}
    bmm.set_uploaded_section_open(s, False)
    assert bmm.uploaded_section_open(s) is False and bmm.MODE_KEY not in s


def test_a_hand_off_opens_its_own_section_once_and_never_closes_the_other():
    s = {bmm.UPLOADED_OPEN_KEY: True}
    bmm.request_melody_mode(s, "practice")              # Practice -> Practice with Backing
    assert bmm.apply_pending_melody_mode(s) == "practice"
    assert bmm.uploaded_section_open(s) is True         # the uploaded section stays open
    assert bmm.PENDING_MODE_KEY not in s
    bmm.set_uploaded_section_open(s, False)
    bmm.request_melody_mode(s, "uploaded")              # Practice -> Open on Backing Page
    assert bmm.apply_pending_melody_mode(s) == "uploaded" and bmm.uploaded_section_open(s) is True
    assert bmm.apply_pending_melody_mode(s) == ""      # once
    bmm.request_melody_mode(s, "nonsense")
    assert bmm.PENDING_MODE_KEY not in s


def test_the_practice_with_backing_hand_off_asks_for_the_practice_melody():
    i = APP.index('key="practice_melody_to_backing"')
    hand_off = APP[i:i + 2600]
    assert "request_melody_mode(st.session_state, MODE_PRACTICE)" in hand_off


def _backing_melody_block():
    i = APP.index("_bk_melodies_on = not _bk_in_karaoke_set")
    return APP[i:APP.index("if _developer_mode_enabled():", i)]


def test_both_sections_are_drawn_independently_practice_melody_first():
    """User 2026-11-26: a generated lick and an uploaded PDF on screen together; neither replaces the other."""
    block = _backing_melody_block()
    assert "_bk_melody_mode" not in APP and "render_melody_mode_selector" not in APP   # no exclusive choice left
    buttons = block.index("_bk_melody_buttons(")
    practice = block.index("if _bk_melodies_on and _pmb_melody is not None:")
    uploaded = block.index("render_uploaded_references(st, st.session_state)")
    assert buttons < practice < uploaded
    # The uploaded section is its own `if`, not an `elif` of the Practice Melody.
    assert "elif" not in block[practice:uploaded].split("\n    if _bk_melodies_on:")[-1]
    assert "    if _bk_melodies_on:\n        # Independent of the Practice Melody above" in block
    # The Practice Melody is shown whenever this song / jam has it on Backing, whatever else is open.
    assert "if _bk_melodies_on and (\n            _pmb_melody is not None or _pml.shown_on_backing(" in block
    # The second "Show a Practice Melody" step is gone: the Practice Melody button makes it.
    assert "backing_practice_melody_create" not in APP


def test_the_practice_melody_panel_uses_the_practice_pages_star_and_offers_remove():
    block = _backing_melody_block()
    assert 'feature_label("practice_melody_generated", "Practice Melody")' in block
    assert "FEATURE_ICONS['backing']} Practice Melody" not in APP
    assert block.index("render_melody_controls(") < block.index("_bk_remove_pm(st, st.session_state, _pmb_song_identity)")


# ---- uploaded references ---# ---- uploaded references -------------------------------------------------------------------------------------------

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

# ---- icons (user, 2026-11-22): the Backing buttons reuse the Practice page's own icons ----------------------------

def test_backing_mode_buttons_reuse_the_practice_page_icons_and_keep_their_labels():
    from music_feature_icons import FEATURE_ICONS, feature_label

    # The Practice page labels these two panels with these exact concepts (same source of icons).
    assert 'feature_label("practice_melody_generated", "Generated Practice Melody")' in APP
    assert 'feature_label("practice_melody_uploaded", "My Uploaded Melodies")' in APP
    assert bmm.mode_button_label("practice") == feature_label("practice_melody_generated", "Practice Melody")
    assert bmm.mode_button_label("uploaded") == feature_label("practice_melody_uploaded", "My Uploaded Melodies")
    assert bmm.mode_button_label("practice") == FEATURE_ICONS["practice_melody_generated"] + " Practice Melody"
    assert bmm.mode_button_label("uploaded") == FEATURE_ICONS["practice_melody_uploaded"] + " My Uploaded Melodies"
    assert bmm.MODE_LABELS == {"practice": "Practice Melody", "uploaded": "My Uploaded Melodies"}  # labels unchanged


class _ButtonsSt:
    """Records the buttons a draw makes (label, key, type, callback)."""

    def __init__(self):
        self.buttons, self.infos = {}, []

    def columns(self, n):
        from contextlib import nullcontext

        return [nullcontext() for _ in range(n if isinstance(n, int) else len(n))]

    def button(self, label, *, key, on_click=None, args=(), type="secondary", **_kw):
        self.buttons[key] = {"label": label, "type": type, "on_click": on_click, "args": args}
        return False

    def info(self, text, **_k):
        self.infos.append(text)

    def caption(self, *_a, **_k):
        pass


def _press(st, key):
    b = st.buttons[key]
    b["on_click"](*b["args"])


def test_the_two_openers_show_the_practice_icons_and_which_sections_are_open():
    from music_feature_icons import FEATURE_ICONS

    st, s = _ButtonsSt(), {}
    bmm.render_melody_section_buttons(st, s, identity="song|a", choose=lambda **_k: None, practice_open=False)
    pm, up = st.buttons[bmm.OPEN_PRACTICE_BUTTON_KEY], st.buttons[bmm.OPEN_UPLOADED_BUTTON_KEY]
    assert pm["label"] == FEATURE_ICONS["practice_melody_generated"] + " Practice Melody"        # the yellow star
    assert up["label"] == FEATURE_ICONS["practice_melody_uploaded"] + " My Uploaded Melodies"   # the upload icon
    assert (pm["type"], up["type"]) == ("secondary", "secondary")
    _press(st, bmm.OPEN_UPLOADED_BUTTON_KEY)
    st = _ButtonsSt()
    bmm.render_melody_section_buttons(st, s, identity="song|a", choose=lambda **_k: None, practice_open=True)
    assert st.buttons[bmm.OPEN_PRACTICE_BUTTON_KEY]["type"] == "primary"
    assert st.buttons[bmm.OPEN_UPLOADED_BUTTON_KEY]["type"] == "primary"   # both open together


# ---- Practice Melody: opens at once, never regenerates by itself (user, 2026-11-26) -------------------------------

SECTIONS = {"Verse": ["C", "Am", "F", "G"], "Chorus": ["F", "G", "C", "C"]}
IDENT = "catalog|Pop|Song A"


def _chooser(session, *, key="C", level="Intermediate"):
    import practice_melody_library as pml

    calls = []

    def choose(**kw):
        calls.append(kw)
        return pml.resolve(session, identity=IDENT, title="Song A", sections=SECTIONS, section_order=list(SECTIONS),
                           sections_key="C", key_center=key, level=level, tempo_bpm=100.0, style="Pop",
                           meter=(4, 4), focus="", instrument="", **kw)

    return choose, calls


def _alt(session):
    import practice_melody_library as pml

    return pml.alternatives(session, IDENT, pml.recipe_for("Intermediate", "Pop", "", (4, 4)))


def test_practice_melody_shows_a_melody_at_once_expanded():
    import melody_panel_visibility as mpv
    import practice_melody_library as pml

    s: dict = {}
    choose, calls = _chooser(s)
    assert not pml.shown_on_backing(s, IDENT)
    assert bmm.open_practice_melody(s, IDENT, choose) is True
    assert pml.shown_on_backing(s, IDENT) and mpv.is_open(s, mpv.PRACTICE, IDENT)
    assert calls == [{}]                                  # asked for the current melody, not another one
    assert _alt(s) == (0, 1)


def test_pressing_it_again_or_rerunning_shows_the_same_melody_never_a_new_one():
    s: dict = {}
    choose, calls = _chooser(s)
    bmm.open_practice_melody(s, IDENT, choose)
    first = choose()
    for _ in range(3):                                    # reruns, and Practice Melody pressed again
        bmm.open_practice_melody(s, IDENT, choose)
        assert choose() is first or choose() == first
    assert _alt(s) == (0, 1)
    assert all(not c for c in calls)                      # never another=True / step


def test_generate_another_replaces_the_shown_melody_and_practice_melody_keeps_it():
    s: dict = {}
    choose, _ = _chooser(s)
    bmm.open_practice_melody(s, IDENT, choose)
    first = choose()
    second = choose(another=True)                          # Generate Another
    assert _alt(s) == (1, 2) and second != first
    bmm.open_practice_melody(s, IDENT, choose)            # pressing Practice Melody does not go back or forward
    assert _alt(s) == (1, 2) and choose() == second


def test_collapse_keeps_the_same_melody_and_practice_melody_expands_it_again():
    import melody_panel_visibility as mpv

    s: dict = {}
    choose, _ = _chooser(s)
    bmm.open_practice_melody(s, IDENT, choose)
    shown = choose(another=True)
    mpv.set_open(s, mpv.PRACTICE, IDENT, False)            # the musician collapses it
    assert choose() == shown and _alt(s) == (1, 2)
    bmm.open_practice_melody(s, IDENT, choose)
    assert mpv.is_open(s, mpv.PRACTICE, IDENT) and choose() == shown


def test_remove_takes_it_off_backing_deletes_nothing_and_practice_melody_brings_the_same_one_back():
    import practice_melody_backing as pmb
    import practice_melody_library as pml

    s: dict = {
        bmm.SELECTED_REFERENCES_KEY: {"catalog|Pop|Song A": ["doc1", "doc2"]},
        bmm.UPLOADED_OPEN_KEY: True,
        "display_key": "D", "instrument": "Flute", "backing_track_bpm": 90,
        pmb.BACKING_MELODY_KEY: object(), pmb.BACKING_MELODY_SONG_IDENTITY_KEY: IDENT,
    }
    choose, _ = _chooser(s)
    bmm.open_practice_melody(s, IDENT, choose)
    shown = choose(another=True)
    before_lib = {k: v for k, v in s[pml.LIBRARY_KEY][IDENT].items() if k != "backing"}
    keep = {k: s[k] for k in (bmm.SELECTED_REFERENCES_KEY, bmm.UPLOADED_OPEN_KEY, "display_key", "instrument",
                              "backing_track_bpm")}
    bmm.remove_practice_melody(s, IDENT)
    assert not pml.shown_on_backing(s, IDENT)
    assert pmb.BACKING_MELODY_KEY not in s                   # the copy handed over from Practice is off the page too
    assert {k: v for k, v in s[pml.LIBRARY_KEY][IDENT].items() if k != "backing"} == before_lib  # nothing deleted
    assert {k: s[k] for k in keep} == keep                    # uploaded choice, section, key, instrument untouched
    bmm.open_practice_melody(s, IDENT, choose)
    assert pml.shown_on_backing(s, IDENT) and choose() == shown and _alt(s) == (1, 2)


def test_a_key_change_or_key_cycling_step_transposes_never_regenerates_or_opens_closes():
    import melody_panel_visibility as mpv
    import practice_melody_library as pml

    s: dict = {}
    choose_c, _ = _chooser(s, key="C")
    bmm.open_practice_melody(s, IDENT, choose_c)
    in_c = choose_c(another=True)
    mpv.set_open(s, mpv.PRACTICE, IDENT, False)
    choose_eb, calls = _chooser(s, key="Eb")                  # the next run, in the cycled key
    in_eb = choose_eb()
    assert in_eb.key_center == "Eb" and in_c.key_center == "C"
    assert _alt(s) == (1, 2) and calls == [{}]
    assert [e.duration_beats for e in in_eb.sections[0].events] == [e.duration_beats for e in in_c.sections[0].events]
    assert pml.shown_on_backing(s, IDENT) and not mpv.is_open(s, mpv.PRACTICE, IDENT)
    assert bmm.uploaded_section_open(s) is False


def test_without_chords_practice_melody_says_why_and_shows_nothing():
    st, s = _ButtonsSt(), {}
    assert bmm.open_practice_melody(s, IDENT, lambda **_k: None) is False
    bmm.render_melody_section_buttons(st, s, identity=IDENT, choose=lambda **_k: None, practice_open=False)
    assert st.infos and "can't be made" in st.infos[0]
    st = _ButtonsSt()
    bmm.render_melody_section_buttons(st, s, identity="another|song", choose=lambda **_k: None, practice_open=False)
    assert st.infos == []                                     # the note belongs to that song only


def test_opening_either_section_never_closes_the_other():
    import practice_melody_library as pml

    s: dict = {}
    choose, _ = _chooser(s)
    bmm.open_practice_melody(s, IDENT, choose)
    bmm.set_uploaded_section_open(s, True)
    assert pml.shown_on_backing(s, IDENT) and bmm.uploaded_section_open(s)
    bmm.open_practice_melody(s, IDENT, choose)
    assert bmm.uploaded_section_open(s)
    bmm.set_uploaded_section_open(s, False)                   # Hide My Uploaded Melodies
    assert pml.shown_on_backing(s, IDENT)
    bmm.remove_practice_melody(s, IDENT)
    bmm.set_uploaded_section_open(s, True)
    assert not pml.shown_on_backing(s, IDENT) and bmm.uploaded_section_open(s)


# ---- the uploaded section --------------------------------------------------------------------------------------------

def test_the_uploaded_section_draws_only_while_open_with_its_icon_and_a_hide_button(monkeypatch):
    from contextlib import nullcontext

    import song_document_catalog as cat
    import song_document_panel as panel
    from music_feature_icons import FEATURE_ICONS

    owner = {"source_type": "catalog", "source_id": "Pop|Shallow", "song_title": "Shallow"}
    monkeypatch.setattr(cat, "active_song_owner", lambda *_a, **_k: owner)
    monkeypatch.setattr(cat, "documents_for_owner", lambda *_a, **_k: [{"document_id": "a", "title": "Lick"}])
    monkeypatch.setattr(panel, "render_song_document_reference", lambda *_a, **_k: None)

    class St(_ButtonsSt):
        def __init__(self):
            super().__init__()
            self.md, self.panels, self.boxes = [], {}, []

        def container(self, **kw):
            self.boxes.append(kw.get("key"))
            return nullcontext()

        def markdown(self, text, **_k):
            self.md.append(text)

        def multiselect(self, *_a, key, **_k):
            return ["a"]

        def expander(self, label, *, expanded, key):
            self.panels[key] = label
            return nullcontext()

    s = {bmm.SELECTED_REFERENCES_KEY: {bmm.owner_identity(owner): ["a"]}}
    st = St()
    assert bmm.render_uploaded_references(st, s) == 0 and st.md == [] and st.panels == {}   # closed: not drawn
    bmm.set_uploaded_section_open(s, True)
    st = St()
    assert bmm.render_uploaded_references(st, s) == 1
    assert st.md == [f"**{FEATURE_ICONS['practice_melody_uploaded']} My Uploaded Melodies**"]
    assert list(st.panels.values()) == [f"{FEATURE_ICONS['practice_melody_uploaded']} Lick"]   # not a 📄
    assert not any(str(b).startswith(bmm.UPLOADED_PANEL_KEY_PREFIX) for b in st.boxes)   # only panels match the follow rule
    _press(st, bmm.HIDE_UPLOADED_BUTTON_KEY)
    assert bmm.uploaded_section_open(s) is False
    assert s[bmm.SELECTED_REFERENCES_KEY] == {bmm.owner_identity(owner): ["a"]}            # the choice is kept


# ---- Practice page wording and icons (user, 2026-11-26) ---------------------------------------------------------------

def test_the_practice_page_explains_the_choice_and_its_button_carries_the_backing_headphones():
    from music_feature_icons import FEATURE_ICONS

    assert bmm.PRACTICE_PICKER_LABEL == "Choose sheet music to practice with Backing"
    assert bmm.PRACTICE_PICKER_HELP == (
        "Select one or more uploaded melodies to view while practicing with your backing track.")
    assert bmm.open_on_backing_label() == f"{FEATURE_ICONS['backing']} Open on Backing Page"
    assert FEATURE_ICONS["backing"] == "🎧"
    src = (Path(__file__).resolve().parents[1] / "backing_melody_modes.py").read_text(encoding="utf-8")
    assert "Show while playing on Backing" not in src


def test_save_and_delete_carry_their_icons_save_sits_under_the_fields_delete_apart():
    src = (Path(__file__).resolve().parents[1] / "song_document_panel.py").read_text(encoding="utf-8")
    body = src[src.index("def _manage("):src.index("def _preview(")]
    assert 'action_label("save", "Save changes")' in body
    assert 'action_label("delete", "Delete this reference")' in body
    assert 'action_label("delete", "Yes, delete it")' in body
    assert "cols = st.columns([2, 1, 1])" in body and "cols[3]" not in body       # Save is not a fourth column
    fields, save = body.index('key=f"{KEY_PREFIX}edit_key_{did}"'), body.index('key=f"{KEY_PREFIX}save_{did}"')
    danger = body.index("with st.container(border=True, key=box):")
    assert fields < save < danger < body.index('key=f"{KEY_PREFIX}del_{did}"')
    assert "CONFIRM_KEY" in body and '"Keep it"' in body                           # the confirmation is unchanged
