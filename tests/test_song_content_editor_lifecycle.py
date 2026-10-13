"""Song Content Editor stays open until the musician closes it; lyrics are song-owned.

Two writers could close the open editor with no Close action:

* ``apply_pick_key`` cleared ``picker_song_editor_open`` whenever it re-applied
  catalog identity -- including for the *same* song (owner switch, fresh flag,
  pick-format drift) on an ordinary rerun such as the textarea blur before Save.
* a mid-session workspace re-apply (``apply_music_disk_state``, e.g. a cloud
  content-drift resync) restored the persisted ``picker_song_editor_open=False``
  over the editor the musician had just opened.

Practice / Karaoke lyrics read the saved per-song store, never the editor's
unsaved in-progress text.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from song_catalog import user_song_content as usc
from songs.user_lyrics_runtime import (
    hydrate_user_lyrics_session,
    mark_lyrics_dirty,
    resolve_user_lyrics_and_cues,
    save_lyrics_my_version,
    song_lyrics_slug,
)
from tests.test_r11_empty_and_composition_sbi import PERFECT, _Base, _FakeSt

LOVE_STORY = ("Country", "Love Story — Taylor Swift")


class TestEditorOpenLifecycle(_Base):
    def _open_editor(self, session: dict) -> None:
        from picker_song_editor import PICKER_EDITOR_OPEN_KEY, open_picker_editor

        open_picker_editor(session, "Lyrics & Cues")
        self.assertTrue(session[PICKER_EDITOR_OPEN_KEY])

    def test_reapplying_the_same_song_keeps_the_editor_open(self) -> None:
        from picker_song_editor import PICKER_EDITOR_OPEN_KEY
        from songs.state import apply_pick_key

        session = self.new_session()
        pick = self.activate_catalog(session, *PERFECT)
        self._open_editor(session)
        # The re-apply branch that used to fire on a plain rerun.
        session["_explicit_catalog_fresh_activation"] = True
        apply_pick_key(_FakeSt(session), pick, self.picker, song_library=self.library)
        self.assertTrue(session[PICKER_EDITOR_OPEN_KEY], "editor closed by a same-song re-apply")

    def test_switching_to_another_song_still_closes_it(self) -> None:
        from picker_song_editor import PICKER_EDITOR_OPEN_KEY
        from song_catalog.catalog import format_pick_key
        from songs.state import apply_pick_key

        session = self.new_session()
        self.activate_catalog(session, *PERFECT)
        self._open_editor(session)
        apply_pick_key(_FakeSt(session), format_pick_key(*LOVE_STORY), self.picker, song_library=self.library)
        self.assertFalse(session[PICKER_EDITOR_OPEN_KEY])

    def test_workspace_reapply_does_not_close_an_open_editor(self) -> None:
        from music_persistent_state import apply_music_disk_state
        from picker_song_editor import PICKER_EDITOR_OPEN_KEY, PICKER_EDITOR_TAB_KEY

        session = self.new_session()
        self.activate_catalog(session, *PERFECT)
        self._open_editor(session)
        payload = {"session": {PICKER_EDITOR_OPEN_KEY: False, PICKER_EDITOR_TAB_KEY: "Edit Song Chart"}}
        apply_music_disk_state(_FakeSt(session), payload, song_picker_catalog=self.picker, song_library=self.library)
        self.assertTrue(session[PICKER_EDITOR_OPEN_KEY])
        self.assertEqual(session[PICKER_EDITOR_TAB_KEY], "Lyrics & Cues")

    def test_startup_restore_still_applies_the_saved_editor_state(self) -> None:
        from music_persistent_state import apply_music_disk_state
        from picker_song_editor import PICKER_EDITOR_OPEN_KEY

        session = self.new_session()
        payload = {"session": {PICKER_EDITOR_OPEN_KEY: True}}
        apply_music_disk_state(_FakeSt(session), payload, song_picker_catalog=self.picker, song_library=self.library)
        self.assertTrue(session.get(PICKER_EDITOR_OPEN_KEY))


@pytest.fixture
def store(tmp_path, monkeypatch):
    path = tmp_path / "user_song_content.json"
    monkeypatch.setattr(usc, "USER_CONTENT_PATH", path)
    return path


def _save(state: dict, title: str, artist: str, lyrics: dict, cues: dict | None = None) -> None:
    slug = song_lyrics_slug(title, artist)
    state[f"section_lyrics::{slug}"] = dict(lyrics)
    state[f"lyric_cues::{slug}"] = dict(cues or {})
    save_lyrics_my_version(state, title=title, artist=artist, genre="Pop", section_names=list(lyrics))


def test_practice_reads_saved_lyrics_not_unsaved_editor_text(store) -> None:
    state: dict = {}
    _save(state, "Perfect", "Ed Sheeran", {"Verse": "Saved verse"}, {"Verse": ["Breathe"]})
    slug = song_lyrics_slug("Perfect", "Ed Sheeran")
    state[f"section_lyrics::{slug}"] = {"Verse": "half-typed, not saved"}   # editor working copy
    mark_lyrics_dirty(state, slug)
    lyrics, cues, _notes = resolve_user_lyrics_and_cues(state, title="Perfect", artist="Ed Sheeran")
    assert lyrics == {"Verse": "Saved verse"}
    assert cues == {"Verse": ["Breathe"]}


def test_updated_save_reaches_practice_and_cues_survive_a_lyrics_edit(store) -> None:
    state: dict = {}
    _save(state, "Perfect", "Ed Sheeran", {"Verse": "v1"}, {"Verse": ["Breathe"]})
    _save(state, "Perfect", "Ed Sheeran", {"Verse": "v2 updated"}, {"Verse": ["Breathe"]})
    lyrics, cues, _ = resolve_user_lyrics_and_cues(state, title="Perfect", artist="Ed Sheeran")
    assert lyrics["Verse"] == "v2 updated"
    assert cues == {"Verse": ["Breathe"]}


def test_each_song_restores_only_its_own_lyrics_after_a_fresh_session(store) -> None:
    writer: dict = {}
    _save(writer, "Perfect", "Ed Sheeran", {"Verse": "Perfect words"})
    _save(writer, "Love Story", "Taylor Swift", {"Verse": "Love Story words"})
    fresh: dict = {}                                      # refresh / reboot
    for title, artist, want in (("Perfect", "Ed Sheeran", "Perfect words"),
                                ("Love Story", "Taylor Swift", "Love Story words"),
                                ("Perfect", "Ed Sheeran", "Perfect words")):
        hydrate_user_lyrics_session(fresh, title=title, artist=artist)
        lyrics, _c, _n = resolve_user_lyrics_and_cues(fresh, title=title, artist=artist)
        assert lyrics == {"Verse": want}
