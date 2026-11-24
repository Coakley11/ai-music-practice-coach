"""Music Dev smoke test 2026-11-24 (after Slice 2): jam keys and Style Jam's own progression.

Reproduced in the real app (disposable data dir; Catalog song California Dreamin' C#m, a Composition song
"Jazz tune" used before) and traced write by write:

1. The Generator's Concert Key control, the sidebar and Backing disagreed. Its record held one key (the song's
   C#m when it was first opened, the musician's choice after an edit) while the control was assigned from a
   guess over the live widget and leftover tokens (a start-up Eb; a leftover C#m).
2. On Style Jam the sidebar's key preparation took the Generator's pending edit / a commit token another owner
   made, and wrote it into Style Jam's control (F -> Eb). A Style Jam key edit also rewrote the Generator's jam.
3. While one jam was on screen the other jam's controls were not drawn, and Streamlit dropped their values:
   older values came back (Style Jam: G / "Song Default" / 100 BPM / Auto), were saved, and after a reload
   picked a stale Style Jam record ("Song Default", Pop groove in G). The controls now persist while hidden.
4. Restoring Style Jam from a Backing context folded its sections into one section named after the context
   label -- with a song's label, "Jazz tune · Dmaj7–G7–C7–G7" appeared as Style Jam's generated jam.
"""

from __future__ import annotations

import ast
import pathlib
import unittest
from types import SimpleNamespace
from unittest import mock

import streamlit

from music_workflow_pending_generated_progression import (
    consume_pending_generated_progression,
    queue_generated_progression_intent,
)

ROOT = pathlib.Path(__file__).resolve().parents[1]
STYLE_FLAG = "_improv_style_key_mounted_this_run"
GEN_FLAG = "_improv_jam_key_mounted_this_run"
CALIFORNIA = "Pop\x1fCalifornia Dreamin' — The Mamas & the Papas"


def _style_jam_bossa_f() -> dict:
    """California Dreamin' (C#m) is the global song; Style Jam generated Bossa Nova in F."""
    s: dict = {
        "_suite_active_workspace_id": "daniel",
        "studio_page": "creative",
        "improv_intelligence_tab": "Entry & Jam",
        "improv_entry_mode": "Style Jam Mode",
        "active_catalog_pick_key": CALIFORNIA,
        "practice_key_by_source": {CALIFORNIA: "C#m"},
        "display_key": "C#m",
        "concert_key": "C#m",
        "improv_style": "Bossa Nova",
        "improv_style_key": "F",
        "improv_difficulty": "Intermediate",
        "improv_mood": "Mellow",
        "improv_groove": "Light",
        "improv_style_bpm": 112,
        STYLE_FLAG: True,
    }
    queue_generated_progression_intent(s, owner="style_jam")
    assert consume_pending_generated_progression(s) == "done"
    return s


def _then_generator(s: dict, key: str = "C#m") -> dict:
    """The musician switches to the Generator and generates (its key: the song's C#m unless given)."""
    s.pop(STYLE_FLAG, None)
    s["improv_entry_mode"] = "Jam Session Generator"
    s[GEN_FLAG] = True
    s.update({"improv_jam_key": key, "improv_jam_style": "Bossa Nova", "improv_ensemble": "Jazz trio",
              "improv_jam_mood": "Dark", "improv_jam_intensity": "Medium", "improv_jam_difficulty": "Intermediate",
              "improv_jam_bpm": 120})
    queue_generated_progression_intent(s, owner="jam_session_generator")
    assert consume_pending_generated_progression(s) == "done"
    return s


def _record(session: dict, owner: str) -> dict:
    blobs = (session.get("_music_workflow_state_store") or {}).get("blobs") or {}
    mine = [b for b in blobs.values() if isinstance(b, dict) and b.get("workflow_owner") == owner]
    return max(mine, key=lambda b: int(b.get("updated_at_seq") or 0)) if mine else {}


def _record_key(session: dict, owner: str) -> str:
    """The key the owner's latest record holds, read raw (works on every version)."""
    from music_theory import key_center_token

    keys = _record(session, owner).get("keys") or {}
    tonic = str(keys.get("practice_tonic") or "").strip()
    return key_center_token(tonic, str(keys.get("practice_mode") or "major")) if tonic else ""


def _generator_key_edit(s: dict, new: str) -> None:
    """The musician picks a new Concert Key in the Generator: its callback, then the pre-widget consumer."""
    from creative_key_sync import on_improv_jam_key_change
    from music_workflow_pending_generated_key_edit import run_pre_widget_generated_key_edit_consumer

    s["improv_jam_key"] = new
    with mock.patch.object(streamlit, "session_state", s):
        on_improv_jam_key_change()
    for k in (GEN_FLAG, "_streamlit_widgets_locked_this_run"):
        s.pop(k, None)
    run_pre_widget_generated_key_edit_consumer(s)


# --------------------------------------------------------------------------- 1. the Generator's visible key
class GeneratorVisibleKeyTests(unittest.TestCase):
    def test_the_control_is_assigned_the_generators_own_key_not_a_leftover(self) -> None:
        from creative_key_sync import seed_jam_concert_widget_before_mount

        s = _then_generator(_style_jam_bossa_f(), key="A")
        self.assertEqual(_record_key(s, "jam_session_generator"), "A")
        # Before the control is drawn again it holds a start-up default (Eb) and the song's key elsewhere.
        s["improv_jam_key"] = "Eb"
        s.pop("_pending_improv_jam_key", None)
        self.assertEqual(seed_jam_concert_widget_before_mount(s), "A")
        self.assertEqual(s["improv_jam_key"], "A")

    def test_a_generator_opened_for_the_first_time_shows_the_key_its_record_starts_in(self) -> None:
        # Browser 2026-11-24: first switch to the Generator. Its activation records the song's key (C#m, by
        # design a never-used jam starts in the song's key); the control showed a start-up Eb and the sidebar C.
        from creative_key_sync import creative_entry_concert_key, seed_jam_concert_widget_before_mount
        from music_workflow_compatibility import build_workflow_blob_from_legacy
        from music_workflow_state_store import save_workflow_blob

        s = _style_jam_bossa_f()
        s.pop(STYLE_FLAG, None)
        s["improv_entry_mode"] = "Jam Session Generator"
        blob = build_workflow_blob_from_legacy(s, "jam_session_generator")
        save_workflow_blob(s, blob, source="test_first_generator_activation")
        self.assertEqual(_record_key(s, "jam_session_generator"), "C#m")
        s["improv_jam_key"] = "Eb"  # the control's start-up value
        self.assertEqual(seed_jam_concert_widget_before_mount(s), "C#m")
        self.assertEqual(creative_entry_concert_key(s), "C#m")

    def test_a_key_change_is_what_the_control_the_sidebar_and_the_record_show(self) -> None:
        from creative_key_sync import creative_entry_concert_key, seed_jam_concert_widget_before_mount

        s = _then_generator(_style_jam_bossa_f())
        _generator_key_edit(s, "Eb")
        self.assertEqual(seed_jam_concert_widget_before_mount(s), "Eb")
        self.assertEqual(s["improv_jam_key"], "Eb")
        self.assertEqual(creative_entry_concert_key(s), "Eb")
        self.assertEqual(_record_key(s, "jam_session_generator"), "Eb")


# --------------------------------------------------------------------------- 2. Generator Eb never Style Jam's
class GeneratorKeyNeverStyleJamsTests(unittest.TestCase):
    def _prepare(self, s: dict) -> list:
        from creative_key_sync import prepare_creative_sidebar_display_key

        return prepare_creative_sidebar_display_key(SimpleNamespace(session_state=s), s)

    def test_back_on_style_jam_the_generators_edit_never_replaces_f(self) -> None:
        # The browser state after "Generator -> Eb, then Style Jam": the sidebar, the Generator's pending edit and
        # the shared commit token all say Eb.
        s = {"studio_page": "creative", "improv_intelligence_tab": "Entry & Jam", "improv_entry_mode": "Style Jam Mode",
             "instrument": "Piano", "improv_style_key": "F", "improv_jam_key": "Eb", "display_key": "Eb",
             "concert_key": "Eb", "_pending_improv_jam_key": "Eb", "_pk_user_commit_token": "Eb",
             "_pk_user_commit_pick": "creative::jam_session_generator",
             "practice_key_by_source": {"creative::jam_session_generator": "Eb", "creative::entry_style_jam": "F",
                                        CALIFORNIA: "C#m"}}
        self._prepare(s)
        self.assertEqual(s["improv_style_key"], "F")

    def test_with_the_generator_on_screen_the_sidebar_keeps_a_real_key(self) -> None:
        # Browser v3: the sidebar key was dropped and the control fell to its first option (C).
        s = {"studio_page": "creative", "improv_intelligence_tab": "Entry & Jam",
             "improv_entry_mode": "Jam Session Generator", "instrument": "Piano", "improv_style_key": "F",
             "improv_jam_key": "Eb", "display_key": "C#m", "concert_key": "C#m", "_pending_improv_jam_key": "Eb",
             "practice_key_by_source": {"creative::jam_session_generator": "Eb", CALIFORNIA: "C#m"}}
        options = self._prepare(s)
        self.assertIn(s.get("display_key"), {"C#m", "Eb"})
        # A value missing from the options shows the first option (C): the key shown must be one of them.
        self.assertIn(s.get("display_key"), options)
        self.assertEqual(s["improv_style_key"], "F")

    def test_style_jams_own_pending_edit_still_reaches_its_control(self) -> None:
        s = {"studio_page": "creative", "improv_intelligence_tab": "Entry & Jam", "improv_entry_mode": "Style Jam Mode",
             "instrument": "Piano", "improv_style_key": "F", "display_key": "G", "concert_key": "G",
             "_pending_improv_style_key": "G",
             "practice_key_by_source": {"creative::entry_style_jam": "G"}}
        self._prepare(s)
        self.assertEqual(s["improv_style_key"], "G")

    def test_a_style_jam_key_edit_never_rewrites_the_generators_jam(self) -> None:
        from creative_key_sync import apply_specialized_jam_practice_key

        s = _then_generator(_style_jam_bossa_f(), key="Eb")
        jam_key = s["improv_jam_session"].get("key")
        s["improv_entry_mode"] = "Style Jam Mode"
        apply_specialized_jam_practice_key(s, "G")
        self.assertEqual(s["improv_jam_session"].get("key"), jam_key)


# --------------------------------------------------------------------------- 3. Style Jam survives the Generator
class HiddenJamControlsPersistTests(unittest.TestCase):
    JAM_KEYS = {"improv_style", "improv_style_key", "improv_difficulty", "improv_mood", "improv_style_bpm",
                "improv_groove", "improv_ensemble", "improv_jam_style", "improv_jam_difficulty", "improv_jam_key",
                "improv_jam_bpm", "improv_jam_mood", "improv_jam_intensity"}

    def test_every_jam_control_keeps_its_value_while_the_other_mode_is_on_screen(self) -> None:
        tree = ast.parse((ROOT / "improvisation_intelligence_ui.py").read_text(encoding="utf-8"))
        found: dict[str, str] = {}
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            kw = {k.arg: k.value for k in node.keywords}
            key = kw.get("key")
            if isinstance(key, ast.Constant) and key.value in self.JAM_KEYS:
                ps = kw.get("persist_state")
                found[key.value] = ps.value if isinstance(ps, ast.Constant) else ""
        self.assertEqual(set(found), self.JAM_KEYS)
        self.assertEqual({k for k, v in found.items() if v != "session"}, set())

    def test_style_jams_record_id_is_saved_with_the_workspace(self) -> None:
        from music_persistent_state import _PERSIST_KEYS

        self.assertIn("_style_jam_workflow_session_id", _PERSIST_KEYS)
        self.assertIn("_jam_session_generator_session_id", _PERSIST_KEYS)

    def test_after_the_generator_and_a_reload_style_jam_finds_its_own_record(self) -> None:
        from music_workflow_compatibility import legacy_session_id_for_owner

        s = _then_generator(_style_jam_bossa_f(), key="Eb")
        sid = _record(s, "style_jam")["workflow_session_id"]
        # Reload: the Generator is the active workflow, the session-only id is gone, and the shared style
        # control holds what another tool left in it.
        s.pop("_style_jam_workflow_session_id", None)
        s["improv_style"] = "Song Default"
        self.assertEqual(legacy_session_id_for_owner(s, "style_jam"), sid)

    def test_style_jams_record_keeps_f_and_its_settings_after_the_generator(self) -> None:
        s = _then_generator(_style_jam_bossa_f(), key="Eb")
        rec = _record(s, "style_jam")
        self.assertEqual(_record_key(s, "style_jam"), "F")
        self.assertEqual((rec.get("style"), rec.get("tempo_bpm"), rec.get("mood")), ("Bossa Nova", 112, "Mellow"))


# --------------------------------------------------------------------------- 4. Generator Eb after Style Jam
class GeneratorKeepsItsKeyTests(unittest.TestCase):
    def test_returning_to_style_jam_and_back_keeps_the_generators_eb(self) -> None:
        from creative_key_sync import seed_jam_concert_widget_before_mount

        s = _then_generator(_style_jam_bossa_f())
        _generator_key_edit(s, "Eb")
        # Style Jam is shown (its own key F), then the Generator again with a start-up value in its control.
        s["improv_entry_mode"] = "Style Jam Mode"
        s["improv_style_key"] = "F"
        s["improv_entry_mode"] = "Jam Session Generator"
        s["improv_jam_key"] = "C#m"
        s.pop("_pending_improv_jam_key", None)
        self.assertEqual(seed_jam_concert_widget_before_mount(s), "Eb")


# --------------------------------------------------------------------------- 5 + 6. Style Jam's own progression
class StyleJamOwnProgressionTests(unittest.TestCase):
    def _song_context(self, s: dict):
        """A Backing context carrying a song's label and chords (as an SBI / Composition context does)."""
        from backing_context import build_entry_jam_context

        ctx = build_entry_jam_context(s)
        ctx.progression = ["Dmaj7", "G7", "C7", "G7"]
        ctx.progression_label = "Jazz tune · Dmaj7–G7–C7–G7"
        ctx.sealed_jam_snapshot = None
        return ctx

    def test_generated_bossa_nova_sections_are_style_jams_own(self) -> None:
        s = _style_jam_bossa_f()
        gen = s["improv_generated_sections"]
        self.assertEqual(list(gen), ["A (Bossa Nova)", "B (Bossa Nova)", "A' (Bossa Nova)"])
        self.assertEqual(_record(s, "style_jam")["section_map"], gen)

    def test_restoring_from_a_context_never_shows_another_songs_progression(self) -> None:
        from backing_source_navigation import restore_session_widgets_from_backing_context

        s = _style_jam_bossa_f()
        own = dict(s["improv_generated_sections"])
        restore_session_widgets_from_backing_context(s, self._song_context(s))
        self.assertEqual(s["improv_generated_sections"], own)
        self.assertNotIn("Jazz tune", " ".join(s["improv_generated_sections"]))

    def test_restoring_from_its_own_context_keeps_its_sections_apart(self) -> None:
        from backing_context import build_entry_jam_context
        from backing_source_navigation import restore_session_widgets_from_backing_context

        s = _style_jam_bossa_f()
        own = dict(s["improv_generated_sections"])
        ctx = build_entry_jam_context(s)
        ctx.sealed_jam_snapshot = None
        restore_session_widgets_from_backing_context(s, ctx)
        self.assertEqual(list(s["improv_generated_sections"]), list(own))

    def test_without_any_record_a_song_label_never_names_style_jams_section(self) -> None:
        from backing_source_navigation import _style_jam_sections_for_restore

        ctx = SimpleNamespace(progression=["Dmaj7", "G7", "C7", "G7"], progression_label="Jazz tune · Dmaj7–G7–C7–G7",
                              style="Bossa Nova", sealed_jam_snapshot=None)
        got = _style_jam_sections_for_restore({}, ctx)
        self.assertEqual(list(got), ["A (Bossa Nova)"])


class StaleSavedCreativeCopyTests(unittest.TestCase):
    """After a second reload the Generator's summary read "~110 BPM · Mellow" for its 120 / Dark jam: the saved
    Creative copy (refreshed only on explicit context saves) still held the Generator's first, empty jam."""

    STALE_JAM = {"id": "Song Default", "mood": "Mellow", "sections": {}}

    def _session(self) -> dict:
        s = _then_generator(_style_jam_bossa_f(), key="Eb")
        s["creative_workspace_state"] = {"improv_jam_session": dict(self.STALE_JAM),
                                         "improv_generated_sections": {"Jazz tune · Dmaj7–G7–C7–G7": ["Dmaj7"]}}
        return s

    def test_the_saved_copy_never_overwrites_a_jam_its_record_backs(self) -> None:
        from creative_context_snapshot_persistence import project_context_from_canonical
        from creative_workspace_state_persistence import project_creative_workspace_to_session

        for project in (project_context_from_canonical, project_creative_workspace_to_session):
            s = self._session()
            jam, gen = dict(s["improv_jam_session"]), dict(s["improv_generated_sections"])
            project(s, overwrite=True)
            self.assertEqual(s["improv_jam_session"], jam, project.__name__)
            self.assertEqual(s["improv_generated_sections"], gen, project.__name__)

    def test_on_reload_before_any_record_loads_an_empty_saved_jam_never_replaces_a_generated_one(self) -> None:
        # Browser trace t3: the disk restore projects the saved copy before the workflow store is loaded.
        from creative_context_snapshot_persistence import project_context_from_canonical

        s = self._session()
        live = dict(s["improv_jam_session"])
        s.pop("_music_workflow_state_store", None)
        project_context_from_canonical(s, overwrite=True)
        self.assertEqual(s["improv_jam_session"], live)

    def test_a_missing_value_is_still_filled_from_the_saved_copy(self) -> None:
        from creative_context_snapshot_persistence import project_context_from_canonical

        s = self._session()
        s.pop("improv_jam_session")
        project_context_from_canonical(s, overwrite=True)
        self.assertEqual(s["improv_jam_session"], self.STALE_JAM)


# --------------------------------------------------------------------------- 7. the song's own Practice Key
class SongPracticeKeyUntouchedTests(unittest.TestCase):
    def test_generator_and_style_jam_key_edits_never_change_california_dreamins_key(self) -> None:
        s = _then_generator(_style_jam_bossa_f())
        _generator_key_edit(s, "Eb")
        self.assertEqual(s["practice_key_by_source"].get(CALIFORNIA), "C#m")
        self.assertEqual(s["practice_key_by_source"].get("creative::jam_session_generator"), "Eb")


class CompositionSongContextNeverStyleJamTests(unittest.TestCase):
    """Android retest 2026-11-24: a reload while a Composition song ("Jazz tune", D) is the active song restores
    its own Backing context. That restore turned the Creative session into a Style Jam holding the song's chords
    ("Jazz tune · Dmaj7–G7–C7–G7" under the green "Generated Bossa Nova in D" heading)."""

    def _jazz_tune_ctx(self):
        from backing_context import BackingContext

        return BackingContext(
            source="composition_song", source_label="Composition song", active_song_id="composition::jazz",
            bpm=120, groove="Swing", song_title="Jazz tune", key="D", display_key="D", concert_key="D",
            style="Jazz", progression=["Dmaj7", "G7", "C7", "G7"], progression_label="Jazz tune · Dmaj7–G7–C7–G7",
        )

    def _restore(self, prior):
        from backing_source_navigation import restore_session_widgets_from_backing_context
        from creative_session_state import get_creative_session, set_creative_session

        s = {"studio_page": "creative", "instrument": "Piano", "improv_entry_mode": "Style Jam Mode",
             "improv_style": "Bossa Nova", "improv_style_key": "D"}
        set_creative_session(s, prior)
        restore_session_widgets_from_backing_context(s, self._jazz_tune_ctx(), widget_safe=False)
        return s, get_creative_session(s)

    def test_style_jam_never_gets_the_songs_chords(self):
        from creative_session_state import CreativeSession

        s, sess = self._restore(CreativeSession(
            session_id="b", tool_type="entry_style_jam", entry_mode="Style Jam Mode", style="Bossa Nova",
            concert_key="D", display_key="D", mood="Dreamy", bpm=112))
        self.assertFalse(s.get("improv_generated_sections"), s.get("improv_generated_sections"))
        self.assertEqual(s.get("improv_style"), "Bossa Nova")
        self.assertEqual((sess.tool_type, sess.style, dict(sess.sections or {})), ("entry_style_jam", "Bossa Nova", {}))

    def test_song_based_session_is_not_turned_into_a_style_jam(self):
        from creative_session_state import CreativeSession

        s, sess = self._restore(CreativeSession(
            session_id="a", tool_type="song_based_improvisation", entry_mode="Song-Based Improvisation",
            concert_key="D", display_key="D", sections={"Verse": ["Dmaj7", "G7"]}))
        self.assertEqual(sess.tool_type, "song_based_improvisation")
        self.assertFalse(s.get("improv_generated_sections"), s.get("improv_generated_sections"))

    def test_the_songs_practice_key_still_follows_its_context(self):
        from creative_session_state import CreativeSession

        s, _ = self._restore(CreativeSession(session_id="c", tool_type="entry_style_jam", entry_mode="Style Jam Mode",
                                             style="Bossa Nova", concert_key="D", display_key="D"))
        self.assertEqual(s.get("display_key"), "D")


class StyleJamShowsOnlyItsOwnJamTests(unittest.TestCase):
    """Under the green "Generated <style> in <key>" heading Style Jam shows only sections its generator made.
    Chords another source left in its slot (saved by 1f2df7a0 as "Jazz tune · Dmaj7–G7–C7–G7", by 3587e435 as
    "Jazz") are left as stored but never shown, or opened in Backing, as Style Jam's generated jam."""

    def test_every_generated_style_jam_is_recognised(self):
        from improvisation_intelligence import STYLE_JAM_STYLES, generate_style_progression, is_style_jam_section_map

        for style in STYLE_JAM_STYLES:
            for key in ("C", "D", "Eb", "F#", "C#m", "Am"):
                for seed in (1, 2, 3):
                    for mood in ("Mellow", "Dark"):
                        sec = generate_style_progression(style=style, key_center=key, mood=mood, seed=seed)
                        self.assertTrue(is_style_jam_section_map(sec), (style, key, mood, sec))

    def test_another_sources_chords_are_not_style_jams(self):
        from improvisation_intelligence import is_style_jam_section_map

        for leaked in ({"Jazz tune · Dmaj7–G7–C7–G7": ["Dmaj7", "G7", "C7", "G7"]},
                       {"Jazz": ["Dmaj7", "G7", "C7", "G7"]}, {"Verse": ["C", "G"]}, {}, None):
            self.assertFalse(is_style_jam_section_map(leaked), leaked)

    def test_the_renderer_checks_ownership_before_the_heading(self):
        src = (ROOT / "improvisation_intelligence_ui.py").read_text(encoding="utf-8")
        guard = src.index("if gen and not is_style_jam_section_map(gen):")
        heading = src.index('f"Generated **{_style_label}** in **{_key_label}** · "')
        self.assertLess(guard, heading)


class SavedLeakNeverReplacesStyleJamTests(unittest.TestCase):
    """A workspace saved by 1f2df7a0 keeps the leak in two saved copies: the Creative copy's Style Jam sections and
    a Creative session holding Jazz tune's chords, style, tempo (120) and feel. After the user generates a Style Jam,
    a reload must not bring either back."""

    LEAK = {"Jazz tune · Dmaj7–G7–C7–G7": ["Dmaj7", "G7", "C7", "G7"]}
    OWN = {"A (Bossa Nova)": ["Em7", "A7", "Dmaj7", "Dmaj7"], "B (Bossa Nova)": ["Em7", "A7", "F#m7", "B7"]}

    def test_saved_copy_of_another_sources_chords_never_replaces_a_generated_style_jam(self):
        from creative_context_snapshot_persistence import _jam_record_owns_context_key

        s = {"improv_generated_sections": dict(self.OWN)}
        self.assertTrue(_jam_record_owns_context_key(s, "improv_generated_sections", dict(self.LEAK)))

    def test_leaked_style_jam_session_never_reaches_style_jams_controls(self):
        from creative_session_state import CreativeSession, apply_creative_session_to_session

        s = {"improv_style": "Bossa Nova", "improv_style_bpm": 112, "improv_groove": "Light",
             "improv_generated_sections": dict(self.OWN), "improv_style_key": "D"}
        leaked = CreativeSession(session_id="x", tool_type="entry_style_jam", entry_mode="Style Jam Mode",
                                 style="Jazz", concert_key="D", display_key="D", bpm=120, groove_intensity="Medium",
                                 sections=dict(self.LEAK))
        apply_creative_session_to_session(s, leaked, widget_safe=False)
        self.assertEqual((s["improv_style"], s["improv_style_bpm"], s["improv_groove"]), ("Bossa Nova", 112, "Light"))
        self.assertEqual(s["improv_generated_sections"], self.OWN)

    def test_leaked_saved_copy_never_restores_the_songs_tempo_and_feel(self):
        from creative_context_snapshot_persistence import project_context_from_canonical

        live_meta = {"style": "Bossa Nova", "bpm": 112, "groove": "Light", "groove_intensity": "Light",
                     "entry_mode": "Style Jam Mode"}
        s = {"improv_style_meta": dict(live_meta), "improv_generated_sections": dict(self.OWN),
             "creative_workspace_state": {
                 "improv_generated_sections": dict(self.LEAK),
                 "improv_style_meta": {"style": "Jazz", "bpm": 120, "groove": "Medium", "groove_intensity": "Medium",
                                       "entry_mode": "Style Jam Mode"},
                 "creative_session": {"tool_type": "entry_style_jam", "style": "Jazz", "bpm": 120,
                                      "sections": dict(self.LEAK)}}}
        project_context_from_canonical(s, overwrite=True)
        self.assertEqual(s["improv_style_meta"], live_meta)
        self.assertEqual(s["improv_generated_sections"], self.OWN)
        self.assertNotIn("creative_session", s)

    def test_a_style_jams_own_saved_copy_still_projects(self):
        from creative_context_snapshot_persistence import leaked_style_jam_copy_key

        s = {"creative_workspace_state": {"improv_generated_sections": dict(self.OWN)}}
        for key in ("improv_generated_sections", "improv_style_meta"):
            self.assertFalse(leaked_style_jam_copy_key(s, key, {}))

    def test_leak_saved_by_3587e435_never_reaches_style_jams_controls(self):
        from creative_session_state import CreativeSession, apply_creative_session_to_session

        s = {"improv_style": "Bossa Nova", "improv_style_bpm": 112, "improv_groove": "Light",
             "improv_generated_sections": dict(self.OWN)}
        leaked = CreativeSession(session_id="z", tool_type="entry_style_jam", entry_mode="Style Jam Mode", style="Jazz",
                                 concert_key="D", display_key="D", bpm=120, groove_intensity="Medium",
                                 sections={"Jazz": ["Dmaj7", "G7", "C7", "G7"]})
        apply_creative_session_to_session(s, leaked, widget_safe=False)
        self.assertEqual((s["improv_style"], s["improv_style_bpm"], s["improv_groove"]), ("Bossa Nova", 112, "Light"))
        self.assertEqual(s["improv_generated_sections"], self.OWN)

    def test_other_sections_in_a_style_jam_session_are_not_written_as_style_jams(self):
        from creative_session_state import CreativeSession, apply_creative_session_to_session

        s = {"improv_generated_sections": dict(self.OWN)}
        sess = CreativeSession(session_id="w", tool_type="entry_style_jam", entry_mode="Style Jam Mode",
                               style="Bossa Nova", concert_key="F", display_key="F", bpm=75,
                               sections={"Bossa": ["Fmaj7", "Bbmaj7"]})
        apply_creative_session_to_session(s, sess, widget_safe=False)
        self.assertEqual((s["improv_style"], s["improv_style_bpm"]), ("Bossa Nova", 75))
        self.assertEqual(s["improv_generated_sections"], self.OWN)

    def test_style_jams_own_session_still_applies(self):
        from creative_session_state import CreativeSession, apply_creative_session_to_session

        s = {"improv_style": "Pop", "improv_style_bpm": 100}
        own = CreativeSession(session_id="y", tool_type="entry_style_jam", entry_mode="Style Jam Mode",
                              style="Bossa Nova", concert_key="D", display_key="D", bpm=112, groove_intensity="Light",
                              sections=dict(self.OWN))
        apply_creative_session_to_session(s, own, widget_safe=False)
        self.assertEqual((s["improv_style"], s["improv_style_bpm"], s["improv_groove"]), ("Bossa Nova", 112, "Light"))
        self.assertEqual(s["improv_generated_sections"], self.OWN)


if __name__ == "__main__":
    unittest.main()
