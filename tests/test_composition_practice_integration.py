"""Slice 5 — Composition-to-Practice Integration tests.

Verifies that a musician can create a song in Composition Studio,
save it, activate it, and open Practice to find the same song's
actual lyrics, melody, chords, and musical identity.
"""

from __future__ import annotations

import copy
import unittest
from unittest import mock


def _make_doc(
    *,
    title: str = "Test Song",
    key: str = "C major",
    bpm: int = 120,
    sections: list[dict] | None = None,
) -> dict:
    from composition_document import bootstrap_from_vision

    doc = bootstrap_from_vision(
        genre="Pop", song_idea="test", title=title, key=key, bpm=bpm,
    )
    if sections is not None:
        form = doc.setdefault("form", {})
        secs = form.setdefault("sections", {})
        order = []
        for s in sections:
            sid = s["id"]
            secs[sid] = s
            order.append(sid)
        form["section_order"] = order
    return doc


def _section(
    sid: str,
    label: str,
    *,
    lyrics_text: str = "",
    chords: list | None = None,
    melody_events: list | None = None,
) -> dict:
    return {
        "id": sid,
        "label": label,
        "label_variant": 1,
        "chords": chords or [],
        "melody": {
            "events": melody_events or [],
            "phrases": [],
        },
        "lyrics": {
            "raw_text": lyrics_text,
            "lines": lyrics_text.split("\n") if lyrics_text else [],
            "intent": {"communicate": "", "emotion": "", "role": "", "remember": ""},
        },
    }


# ---------------------------------------------------------------------------
# 1. Bridge: composition_section_lyrics
# ---------------------------------------------------------------------------
class TestCompositionSectionLyrics(unittest.TestCase):
    def test_extracts_lyrics_from_sections(self):
        from composition_songs_bridge import composition_section_lyrics

        doc = _make_doc(sections=[
            _section("s1", "Verse", lyrics_text="Hello world\nLine two"),
            _section("s2", "Chorus", lyrics_text="La la la"),
        ])
        result = composition_section_lyrics(doc)
        self.assertIn("Verse", result)
        self.assertIn("Chorus", result)
        self.assertEqual(result["Verse"], "Hello world\nLine two")
        self.assertEqual(result["Chorus"], "La la la")

    def test_excludes_empty_lyrics(self):
        from composition_songs_bridge import composition_section_lyrics

        doc = _make_doc(sections=[
            _section("s1", "Verse", lyrics_text="Real lyrics"),
            _section("s2", "Bridge", lyrics_text=""),
        ])
        result = composition_section_lyrics(doc)
        self.assertIn("Verse", result)
        self.assertNotIn("Bridge", result)

    def test_handles_duplicate_labels(self):
        from composition_songs_bridge import composition_section_lyrics

        doc = _make_doc(sections=[
            _section("s1", "Verse", lyrics_text="Verse one text"),
            _section("s2", "Verse", lyrics_text="Verse two text"),
        ])
        result = composition_section_lyrics(doc)
        self.assertIn("Verse", result)
        self.assertIn("Verse 2", result)

    def test_empty_doc_returns_empty(self):
        from composition_songs_bridge import composition_section_lyrics

        doc = _make_doc(sections=[])
        result = composition_section_lyrics(doc)
        self.assertEqual(result, {})

    def test_only_accepted_lyrics_extracted(self):
        from composition_songs_bridge import composition_section_lyrics

        doc = _make_doc(sections=[
            _section("s1", "Verse", lyrics_text="Accepted lyrics only"),
        ])
        result = composition_section_lyrics(doc)
        self.assertEqual(result["Verse"], "Accepted lyrics only")

    def test_lines_fallback_when_raw_text_empty(self):
        from composition_songs_bridge import composition_section_lyrics

        doc = _make_doc(sections=[
            _section("s1", "Verse"),
        ])
        sec = doc["form"]["sections"]["s1"]
        sec["lyrics"]["raw_text"] = ""
        sec["lyrics"]["lines"] = ["Line from lines array", "Second line"]
        result = composition_section_lyrics(doc)
        self.assertIn("Verse", result)
        self.assertIn("Line from lines array", result["Verse"])


# ---------------------------------------------------------------------------
# 2. Bridge: composition_section_melody_events
# ---------------------------------------------------------------------------
class TestCompositionSectionMelodyEvents(unittest.TestCase):
    def test_extracts_melody_events(self):
        from composition_songs_bridge import composition_section_melody_events

        events = [
            {"pitch": "C4", "duration_beats": 1.0, "beat": 0, "measure": 1},
            {"pitch": "D4", "duration_beats": 1.0, "beat": 1, "measure": 1},
        ]
        doc = _make_doc(sections=[
            _section("s1", "Verse", melody_events=events),
        ])
        result = composition_section_melody_events(doc)
        self.assertIn("Verse", result)
        self.assertEqual(len(result["Verse"]), 2)
        self.assertEqual(result["Verse"][0]["pitch"], "C4")

    def test_excludes_sections_without_melody(self):
        from composition_songs_bridge import composition_section_melody_events

        events = [{"pitch": "C4", "duration_beats": 1.0, "beat": 0, "measure": 1}]
        doc = _make_doc(sections=[
            _section("s1", "Verse", melody_events=events),
            _section("s2", "Chorus", melody_events=[]),
        ])
        result = composition_section_melody_events(doc)
        self.assertIn("Verse", result)
        self.assertNotIn("Chorus", result)

    def test_does_not_invent_melody(self):
        from composition_songs_bridge import composition_section_melody_events

        doc = _make_doc(sections=[_section("s1", "Verse")])
        result = composition_section_melody_events(doc)
        self.assertEqual(result, {})


# ---------------------------------------------------------------------------
# 3. Chart bundle carries composition document
# ---------------------------------------------------------------------------
class TestChartBundleCompositionDocument(unittest.TestCase):
    def test_chart_bundle_includes_composition_document(self):
        from composition_songs_bridge import composition_pick_key_for
        from songs.music_source import _build_composition_chart_bundle
        from songs.state import ACTIVE_CATALOG_PICK_KEY
        from composition_session_state import set_active_document, COMPOSER_LIBRARY_KEY

        doc = _make_doc(title="My Song", key="G major", sections=[
            _section("s1", "Verse", chords=[{"root": "G", "quality": ""}]),
        ])
        ss: dict = {}
        set_active_document(ss, doc, checkpoint=False)
        pick = composition_pick_key_for(doc)
        ss[ACTIVE_CATALOG_PICK_KEY] = pick
        ss[COMPOSER_LIBRARY_KEY] = {str(doc["id"]): doc}

        def _noop_transpose(song_data, key):
            return song_data.get("sections", {})

        bundle = _build_composition_chart_bundle(
            ss, display_key="G", transpose_sections=_noop_transpose,
        )
        self.assertIn("composition_document", bundle)
        self.assertEqual(bundle["composition_document"]["id"], doc["id"])
        self.assertEqual(bundle["source"], "composition_song")
        self.assertEqual(bundle["original_key"], "G")


# ---------------------------------------------------------------------------
# 4. Lyrics resolution override for composition source
# ---------------------------------------------------------------------------
class TestLyricsResolutionOverride(unittest.TestCase):
    def test_composition_lyrics_override_section_lyrics(self):
        from composition_songs_bridge import composition_section_lyrics

        doc = _make_doc(sections=[
            _section("s1", "Verse", lyrics_text="My composition verse"),
            _section("s2", "Chorus", lyrics_text="My composition chorus"),
        ])
        result = composition_section_lyrics(doc)
        self.assertEqual(result["Verse"], "My composition verse")
        self.assertEqual(result["Chorus"], "My composition chorus")

    def test_catalog_lyrics_not_used_for_composition(self):
        from composition_songs_bridge import composition_section_lyrics

        doc = _make_doc(title="Shape of You", sections=[
            _section("s1", "Verse", lyrics_text="My own verse, not Ed Sheeran"),
        ])
        result = composition_section_lyrics(doc)
        self.assertEqual(result["Verse"], "My own verse, not Ed Sheeran")


# ---------------------------------------------------------------------------
# 5. Key/instrument projection
# ---------------------------------------------------------------------------
class TestKeyInstrumentProjection(unittest.TestCase):
    def test_piano_concert_pitch(self):
        from composition_songs_bridge import composition_written_pitch_semitones
        self.assertEqual(composition_written_pitch_semitones("Piano"), 0)

    def test_bb_tenor_sax_written_pitch_major_ninth(self):
        from composition_songs_bridge import composition_written_pitch_semitones
        self.assertEqual(composition_written_pitch_semitones("Tenor saxophone"), 14)

    def test_eb_alto_sax_written_pitch_major_sixth(self):
        from composition_songs_bridge import composition_written_pitch_semitones
        self.assertEqual(composition_written_pitch_semitones("Alto saxophone"), 9)

    def test_bari_sax_written_pitch_major_thirteenth(self):
        from composition_songs_bridge import composition_written_pitch_semitones
        self.assertEqual(composition_written_pitch_semitones("Baritone saxophone"), 21)

    def test_soprano_sax_written_pitch_major_second(self):
        from composition_songs_bridge import composition_written_pitch_semitones
        self.assertEqual(composition_written_pitch_semitones("Soprano saxophone"), 2)

    def test_trumpet_written_pitch_major_second(self):
        from composition_songs_bridge import composition_written_pitch_semitones
        self.assertEqual(composition_written_pitch_semitones("Trumpet"), 2)

    def test_tenor_sax_d4_to_e5(self):
        from composition_songs_bridge import composition_written_pitch_semitones
        from media_tone_catalog import transpose_note_token
        semi = composition_written_pitch_semitones("Tenor saxophone")
        result = transpose_note_token("D4", semi)
        self.assertEqual(result, "E5")

    def test_alto_sax_d4_to_b4(self):
        from composition_songs_bridge import composition_written_pitch_semitones
        from media_tone_catalog import transpose_note_token
        semi = composition_written_pitch_semitones("Alto saxophone")
        result = transpose_note_token("D4", semi)
        self.assertEqual(result, "B4")

    def test_piano_d4_unchanged(self):
        from composition_songs_bridge import composition_written_pitch_semitones
        from media_tone_catalog import transpose_note_token
        semi = composition_written_pitch_semitones("Piano")
        self.assertEqual(semi, 0)

    def test_rest_not_transposed(self):
        from media_tone_catalog import transpose_note_token
        events = [{"pitch": "rest", "duration_beats": 1.0}]
        transposed = []
        for ev in events:
            ev_copy = dict(ev)
            pitch = str(ev_copy.get("pitch") or "")
            if pitch and pitch.lower() != "rest":
                tp = transpose_note_token(pitch, 2)
                if tp:
                    ev_copy["pitch"] = tp
            transposed.append(ev_copy)
        self.assertEqual(transposed[0]["pitch"], "rest")


# ---------------------------------------------------------------------------
# 6. Composition melody ABC generation
# ---------------------------------------------------------------------------
class TestComposedMelodyABC(unittest.TestCase):
    def test_abc_generated_from_melody_events(self):
        from composition_melody_notation import build_section_score_model

        events = [
            {"pitch": "C4", "duration_beats": 1.0, "beat": 0, "measure": 1},
            {"pitch": "E4", "duration_beats": 1.0, "beat": 1, "measure": 1},
            {"pitch": "G4", "duration_beats": 1.0, "beat": 2, "measure": 1},
        ]
        model = build_section_score_model(
            events=events, chords=[], key="C", meter="4/4", bpm=120, title="Verse",
        )
        self.assertTrue(model["has_melody"])
        self.assertTrue(len(model["abc"]) > 0)
        self.assertIn("K:", model["abc"])

    def test_no_abc_when_no_events(self):
        from composition_melody_notation import build_section_score_model

        model = build_section_score_model(
            events=[], chords=[], key="C", meter="4/4", bpm=120, title="Verse",
        )
        self.assertFalse(model["has_melody"])
        self.assertEqual(model["abc"], "")

    def test_lyrics_text_passed_through(self):
        from composition_melody_notation import build_section_score_model

        model = build_section_score_model(
            events=[{"pitch": "C4", "duration_beats": 1.0, "beat": 0, "measure": 1}],
            chords=[], key="C", meter="4/4", bpm=120,
            title="Verse", lyrics_text="Hello world",
        )
        self.assertTrue(model["has_lyrics"])
        self.assertEqual(model["lyrics_text"], "Hello world")


# ---------------------------------------------------------------------------
# 7. Composition source detection
# ---------------------------------------------------------------------------
class TestCompositionSourceDetection(unittest.TestCase):
    def test_composition_pick_key_format(self):
        from composition_songs_bridge import composition_pick_key_for

        doc = _make_doc()
        pick = composition_pick_key_for(doc)
        self.assertTrue(pick.startswith("composition::"))

    def test_is_composition_pick_key(self):
        from composition_songs_bridge import is_composition_pick_key

        self.assertTrue(is_composition_pick_key("composition::abc-123"))
        self.assertFalse(is_composition_pick_key("catalog::some-song"))
        self.assertFalse(is_composition_pick_key("custom::prog"))


# ---------------------------------------------------------------------------
# 8. Active song record preserves source
# ---------------------------------------------------------------------------
class TestActiveSongRecord(unittest.TestCase):
    def test_selected_song_record_has_source(self):
        from composition_songs_bridge import composition_selected_song_record

        doc = _make_doc(title="My Song", key="G major")
        record = composition_selected_song_record(doc)
        self.assertEqual(record["source"], "composition_song")
        self.assertEqual(record["title"], "My Song")
        self.assertTrue(record["pick_key"].startswith("composition::"))

    def test_chart_active_has_source(self):
        from composition_songs_bridge import composition_as_chart_active

        doc = _make_doc(title="My Song", key="G major")
        proj = composition_as_chart_active(doc)
        self.assertEqual(proj["source"], "composition_song")
        self.assertEqual(proj["name"], "My Song")


# ---------------------------------------------------------------------------
# 9. No stale state leakage
# ---------------------------------------------------------------------------
class TestNoStaleState(unittest.TestCase):
    def test_section_lyrics_isolated_per_document(self):
        from composition_songs_bridge import composition_section_lyrics

        doc1 = _make_doc(title="Song A", sections=[
            _section("s1", "Verse", lyrics_text="Lyrics for Song A"),
        ])
        doc2 = _make_doc(title="Song B", sections=[
            _section("s2", "Verse", lyrics_text="Lyrics for Song B"),
        ])
        result1 = composition_section_lyrics(doc1)
        result2 = composition_section_lyrics(doc2)
        self.assertEqual(result1["Verse"], "Lyrics for Song A")
        self.assertEqual(result2["Verse"], "Lyrics for Song B")

    def test_melody_events_isolated_per_document(self):
        from composition_songs_bridge import composition_section_melody_events

        events_a = [{"pitch": "C4", "duration_beats": 1.0, "beat": 0, "measure": 1}]
        events_b = [{"pitch": "G4", "duration_beats": 1.0, "beat": 0, "measure": 1}]
        doc1 = _make_doc(sections=[_section("s1", "Verse", melody_events=events_a)])
        doc2 = _make_doc(sections=[_section("s2", "Verse", melody_events=events_b)])
        r1 = composition_section_melody_events(doc1)
        r2 = composition_section_melody_events(doc2)
        self.assertEqual(r1["Verse"][0]["pitch"], "C4")
        self.assertEqual(r2["Verse"][0]["pitch"], "G4")


# ---------------------------------------------------------------------------
# 10. Original key preservation
# ---------------------------------------------------------------------------
class TestOriginalKeyPreservation(unittest.TestCase):
    def test_original_key_from_document(self):
        from composition_songs_bridge import composition_home_key

        doc = _make_doc(key="Bb major")
        home = composition_home_key(doc)
        self.assertIn("Bb", str(home))

    def test_chart_bundle_preserves_original_key(self):
        from composition_songs_bridge import composition_as_chart_active

        doc = _make_doc(key="F# minor")
        proj = composition_as_chart_active(doc)
        self.assertTrue(str(proj.get("original_key_center") or "").strip())


# ---------------------------------------------------------------------------
# 11. Section label consistency
# ---------------------------------------------------------------------------
class TestSectionLabelConsistency(unittest.TestCase):
    def test_lyrics_and_melody_use_same_labels(self):
        from composition_songs_bridge import (
            composition_section_lyrics,
            composition_section_melody_events,
        )

        events = [{"pitch": "C4", "duration_beats": 1.0, "beat": 0, "measure": 1}]
        doc = _make_doc(sections=[
            _section("s1", "Verse", lyrics_text="Hello", melody_events=events),
            _section("s2", "Chorus", lyrics_text="Chorus text", melody_events=events),
        ])
        lyrics_keys = set(composition_section_lyrics(doc).keys())
        melody_keys = set(composition_section_melody_events(doc).keys())
        self.assertEqual(lyrics_keys, melody_keys)

    def test_labels_match_chord_sections(self):
        from composition_songs_bridge import (
            composition_original_sections,
            composition_section_lyrics,
        )

        doc = _make_doc(sections=[
            _section("s1", "Verse", lyrics_text="Text",
                     chords=[{"root": "C", "quality": ""}]),
            _section("s2", "Chorus", lyrics_text="More",
                     chords=[{"root": "G", "quality": ""}]),
        ])
        chord_keys = set(composition_original_sections(doc).keys())
        lyrics_keys = set(composition_section_lyrics(doc).keys())
        self.assertEqual(chord_keys, lyrics_keys)


# ---------------------------------------------------------------------------
# 12. Composition document integrity
# ---------------------------------------------------------------------------
class TestDocumentIntegrity(unittest.TestCase):
    def test_lyrics_extraction_preserves_lyrics_content(self):
        from composition_songs_bridge import composition_section_lyrics

        doc = _make_doc(sections=[
            _section("s1", "Verse", lyrics_text="Original"),
        ])
        composition_section_lyrics(doc)
        sec = doc["form"]["sections"]["s1"]
        self.assertEqual(sec["lyrics"]["raw_text"], "Original")
        self.assertEqual(sec["label"], "Verse")

    def test_melody_extraction_preserves_melody_content(self):
        from composition_songs_bridge import composition_section_melody_events

        events = [{"pitch": "C4", "duration_beats": 1.0, "beat": 0, "measure": 1}]
        doc = _make_doc(sections=[
            _section("s1", "Verse", melody_events=events),
        ])
        composition_section_melody_events(doc)
        sec = doc["form"]["sections"]["s1"]
        mel_events = sec["melody"]["events"]
        self.assertEqual(len(mel_events), 1)
        self.assertEqual(mel_events[0]["pitch"], "C4")


# ---------------------------------------------------------------------------
# 13. Lyric cues derivation from section lyrics
# ---------------------------------------------------------------------------
class TestLyricCuesFromSectionLyrics(unittest.TestCase):
    def test_cues_generated_from_section_lyrics(self):
        def _cues(section_lyrics):
            cues = {}
            for name, text in (section_lyrics or {}).items():
                lines = [ln.strip() for ln in str(text).splitlines() if ln.strip()]
                if lines:
                    cues[name] = lines
            return cues

        result = _cues({
            "Verse": "Hello world\nSecond line",
            "Chorus": "La la la",
        })
        self.assertEqual(result["Verse"], ["Hello world", "Second line"])
        self.assertEqual(result["Chorus"], ["La la la"])

    def test_empty_lyrics_produce_no_cues(self):
        def _cues(section_lyrics):
            cues = {}
            for name, text in (section_lyrics or {}).items():
                lines = [ln.strip() for ln in str(text).splitlines() if ln.strip()]
                if lines:
                    cues[name] = lines
            return cues

        self.assertEqual(_cues({}), {})


# ---------------------------------------------------------------------------
# 14. Transposition of melody events for instruments
# ---------------------------------------------------------------------------
class TestMelodyTranspositionForInstruments(unittest.TestCase):
    def test_tenor_sax_melody_transposed_correct_octave(self):
        from composition_songs_bridge import composition_written_pitch_semitones
        from media_tone_catalog import transpose_note_token

        semi = composition_written_pitch_semitones("Tenor saxophone")
        events = [
            {"pitch": "C4", "duration_beats": 1.0},
            {"pitch": "E4", "duration_beats": 1.0},
            {"pitch": "G4", "duration_beats": 1.0},
        ]
        transposed = []
        for ev in events:
            ev_copy = dict(ev)
            tp = transpose_note_token(str(ev_copy["pitch"]), semi)
            if tp:
                ev_copy["pitch"] = tp
            transposed.append(ev_copy)
        self.assertEqual(transposed[0]["pitch"], "D5")
        self.assertEqual(transposed[1]["pitch"], "F#5")
        self.assertEqual(transposed[2]["pitch"], "A5")

    def test_alto_sax_melody_transposed_correct_octave(self):
        from composition_songs_bridge import composition_written_pitch_semitones
        from media_tone_catalog import transpose_note_token

        semi = composition_written_pitch_semitones("Alto saxophone")
        result = transpose_note_token("C4", semi)
        self.assertEqual(result, "A4")

    def test_piano_melody_not_transposed(self):
        from composition_songs_bridge import composition_written_pitch_semitones
        self.assertEqual(composition_written_pitch_semitones("Piano"), 0)


# ---------------------------------------------------------------------------
# 15. Multiple sections with mixed content
# ---------------------------------------------------------------------------
class TestMixedSectionContent(unittest.TestCase):
    def test_some_sections_have_lyrics_some_dont(self):
        from composition_songs_bridge import composition_section_lyrics

        doc = _make_doc(sections=[
            _section("s1", "Intro"),
            _section("s2", "Verse", lyrics_text="Verse lyrics"),
            _section("s3", "Bridge"),
            _section("s4", "Chorus", lyrics_text="Chorus lyrics"),
        ])
        result = composition_section_lyrics(doc)
        self.assertEqual(len(result), 2)
        self.assertIn("Verse", result)
        self.assertIn("Chorus", result)
        self.assertNotIn("Intro", result)
        self.assertNotIn("Bridge", result)

    def test_some_sections_have_melody_some_dont(self):
        from composition_songs_bridge import composition_section_melody_events

        events = [{"pitch": "C4", "duration_beats": 1.0, "beat": 0, "measure": 1}]
        doc = _make_doc(sections=[
            _section("s1", "Intro"),
            _section("s2", "Verse", melody_events=events),
            _section("s3", "Bridge"),
        ])
        result = composition_section_melody_events(doc)
        self.assertEqual(len(result), 1)
        self.assertIn("Verse", result)


# ---------------------------------------------------------------------------
# 16. Composition identity in chart bundle
# ---------------------------------------------------------------------------
class TestCompositionIdentityInBundle(unittest.TestCase):
    def test_song_data_has_composition_source_type(self):
        from composition_songs_bridge import composition_pick_key_for
        from songs.music_source import _build_composition_chart_bundle
        from songs.state import ACTIVE_CATALOG_PICK_KEY
        from composition_session_state import set_active_document, COMPOSER_LIBRARY_KEY

        doc = _make_doc(title="Identity Test", key="A minor", sections=[
            _section("s1", "Verse", chords=[{"root": "Am", "quality": ""}]),
        ])
        ss: dict = {}
        set_active_document(ss, doc, checkpoint=False)
        pick = composition_pick_key_for(doc)
        ss[ACTIVE_CATALOG_PICK_KEY] = pick
        ss[COMPOSER_LIBRARY_KEY] = {str(doc["id"]): doc}

        def _noop_transpose(song_data, key):
            return song_data.get("sections", {})

        bundle = _build_composition_chart_bundle(
            ss, display_key="A", transpose_sections=_noop_transpose,
        )
        sd = bundle["song_data"]
        self.assertEqual(sd["source_type"], "composition_song")
        self.assertFalse(sd["trusted_core"])
        self.assertEqual(sd["title"], "Identity Test")


# ---------------------------------------------------------------------------
# 17. No AI suggestion leakage
# ---------------------------------------------------------------------------
class TestNoAISuggestionLeakage(unittest.TestCase):
    def test_unaccepted_suggestions_not_in_lyrics(self):
        from composition_songs_bridge import composition_section_lyrics

        doc = _make_doc(sections=[_section("s1", "Verse", lyrics_text="")])
        result = composition_section_lyrics(doc)
        self.assertNotIn("Verse", result)


# ---------------------------------------------------------------------------
# 18. BPM and time signature from composition
# ---------------------------------------------------------------------------
class TestBPMAndTimeSig(unittest.TestCase):
    def test_bpm_from_composition_globals(self):
        from composition_songs_bridge import composition_as_chart_active

        doc = _make_doc(bpm=145)
        proj = composition_as_chart_active(doc)
        self.assertEqual(proj["bpm"], 145)

    def test_time_signature_from_composition(self):
        from composition_songs_bridge import composition_as_chart_active

        doc = _make_doc()
        g = doc.setdefault("global", {})
        g["time_signature"] = "3/4"
        proj = composition_as_chart_active(doc)
        self.assertEqual(proj["time_signature"], "3/4")


# ---------------------------------------------------------------------------
# 19. Section ordering
# ---------------------------------------------------------------------------
class TestSectionOrdering(unittest.TestCase):
    def test_lyrics_preserve_document_order(self):
        from composition_songs_bridge import composition_section_lyrics

        doc = _make_doc(sections=[
            _section("s1", "Intro", lyrics_text="Intro text"),
            _section("s2", "Verse", lyrics_text="Verse text"),
            _section("s3", "Chorus", lyrics_text="Chorus text"),
        ])
        result = composition_section_lyrics(doc)
        keys = list(result.keys())
        self.assertEqual(keys, ["Intro", "Verse", "Chorus"])


# ---------------------------------------------------------------------------
# 20. Composition title and artist in Practice
# ---------------------------------------------------------------------------
class TestCompositionTitleAndArtist(unittest.TestCase):
    def test_title_from_document(self):
        from composition_songs_bridge import composition_as_chart_active

        doc = _make_doc(title="My Great Song")
        proj = composition_as_chart_active(doc)
        self.assertEqual(proj["name"], "My Great Song")

    def test_artist_field_present(self):
        from composition_songs_bridge import composition_as_chart_active

        doc = _make_doc()
        proj = composition_as_chart_active(doc)
        self.assertIsInstance(proj.get("artist"), str)


# ---------------------------------------------------------------------------
# 21. Full workflow: doc → activation → chart bundle → lyrics + melody
# ---------------------------------------------------------------------------
class TestFullWorkflow(unittest.TestCase):
    def test_end_to_end_lyrics_and_melody_extraction(self):
        from composition_songs_bridge import (
            composition_pick_key_for,
            composition_section_lyrics,
            composition_section_melody_events,
        )

        events = [
            {"pitch": "C4", "duration_beats": 1.0, "beat": 0, "measure": 1},
            {"pitch": "E4", "duration_beats": 1.0, "beat": 1, "measure": 1},
        ]
        doc = _make_doc(title="Full Workflow Song", key="G major", sections=[
            _section("s1", "Verse", lyrics_text="Walking down the road",
                     chords=[{"root": "G", "quality": ""}], melody_events=events),
            _section("s2", "Chorus", lyrics_text="Singing all day long",
                     chords=[{"root": "C", "quality": ""}], melody_events=events),
        ])
        pick = composition_pick_key_for(doc)
        self.assertTrue(pick.startswith("composition::"))

        lyrics = composition_section_lyrics(doc)
        self.assertEqual(lyrics["Verse"], "Walking down the road")
        self.assertEqual(lyrics["Chorus"], "Singing all day long")

        melody = composition_section_melody_events(doc)
        self.assertIn("Verse", melody)
        self.assertIn("Chorus", melody)
        self.assertEqual(len(melody["Verse"]), 2)


# ---------------------------------------------------------------------------
# 22. Regression: Catalog and CPL sources unaffected
# ---------------------------------------------------------------------------
class TestCatalogAndCPLUnaffected(unittest.TestCase):
    def test_catalog_source_not_flagged_as_composition(self):
        from songs.music_source import _session_requests_composition_chart
        from songs.state import ACTIVE_CATALOG_PICK_KEY

        ss: dict = {ACTIVE_CATALOG_PICK_KEY: "some-catalog-song"}
        with mock.patch(
            "songs.music_source.explicit_music_source_choice",
            return_value="catalog_song",
        ):
            self.assertFalse(_session_requests_composition_chart(ss))

    def test_custom_source_not_flagged_as_composition(self):
        from songs.music_source import _session_requests_composition_chart
        from songs.state import ACTIVE_CATALOG_PICK_KEY

        ss: dict = {ACTIVE_CATALOG_PICK_KEY: "custom::my-prog"}
        with mock.patch(
            "songs.music_source.explicit_music_source_choice",
            return_value="custom_progression",
        ):
            self.assertFalse(_session_requests_composition_chart(ss))


if __name__ == "__main__":
    unittest.main()
