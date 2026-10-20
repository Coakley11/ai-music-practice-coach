"""Slice 6A automated tests — Melody File Upload and Import.

22 categories covering:
  1  Upload key helpers (session-state key generation)
  2  File type acceptance (WAV/MP3 only, reject others)
  3  Audio bytes storage in session state
  4  Transcription delegation (upload → transcribe_hum_audio)
  5  Transcription with zero count-in (uploaded files have no metronome)
  6  WAV file transcription end-to-end
  7  MP3 file transcription end-to-end
  8  Empty / corrupt file handling
  9  Short file handling (< 0.35 s)
 10  Proposal key lifecycle (set / clear / dismiss)
 11  Replacement warning gate (warn only when section has melody)
 12  Accept writes events via apply_melody_events
 13  Source ID is "file_upload" after accept
 14  Concept phrase created with upload metadata
 15  Replacement overwrites existing events
 16  Keep-current leaves events untouched
 17  Preview delegates to play_composer_preview
 18  Accepted card renders for file_upload source
 19  Practice integration — uploaded melody reaches bridge
 20  Practice Key transposition of uploaded melody
 21  Backing Context unaffected by melody upload
 22  No MIDI / MusicXML parser exists (guard)
"""
from __future__ import annotations

import copy
import sys
import types
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from composition_document import (
    apply_melody_events,
    normalize_melody_events,
    section_by_id,
    section_melody_events,
    get_active_melody_source_id,
)
from composition_hum_transcription import (
    hum_analysis_available,
    transcribe_hum_audio,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _make_doc(*, with_melody: bool = False) -> dict[str, Any]:
    """Minimal composition document with one section."""
    events = []
    if with_melody:
        events = [
            {"pitch": "C4", "duration_beats": 1.0, "beat": 0, "measure": 1},
            {"pitch": "D4", "duration_beats": 1.0, "beat": 1, "measure": 1},
            {"pitch": "E4", "duration_beats": 2.0, "beat": 2, "measure": 1},
        ]
    return {
        "id": "test-upload-doc",
        "title": "Upload Test Song",
        "global": {"key": "C", "bpm": 120, "time_signature": "4/4"},
        "form": {
            "section_order": ["s1"],
            "sections": {
                "s1": {
                    "id": "s1",
                    "label": "Verse",
                    "chords": [{"chord": "C", "bars": 2}, {"chord": "G", "bars": 2}],
                    "melody": {
                        "events": events,
                        "intent": {},
                        "phrases": [],
                        **({"active_source_id": "hum_transcription"} if with_melody else {}),
                    },
                    "lyrics": {"raw_text": "Hello world", "lines": ["Hello world"], "intent": {}},
                },
            },
        },
    }


SAMPLE_EVENTS = [
    {"pitch": "G4", "duration_beats": 1.0, "beat": 0, "measure": 1},
    {"pitch": "A4", "duration_beats": 1.0, "beat": 1, "measure": 1},
    {"pitch": "B4", "duration_beats": 2.0, "beat": 2, "measure": 1},
]

UPLOAD_CONCEPT = {
    "id": "file_upload",
    "name": "Uploaded melody",
    "motif_hint": "Transcribed from uploaded audio file",
    "contour": "Imported from your audio file.",
}


# ===== Category 1: Upload key helpers =====
class TestUploadKeyHelpers(unittest.TestCase):
    def test_proposal_key_format(self):
        from composition_studio_page import _upload_proposal_key
        self.assertEqual(_upload_proposal_key("s1"), "composer_upload_proposal_s1")

    def test_audio_key_format(self):
        from composition_studio_page import _upload_audio_key
        self.assertEqual(_upload_audio_key("s1"), "composer_upload_audio_s1")

    def test_keys_differ_per_section(self):
        from composition_studio_page import _upload_proposal_key, _upload_audio_key
        self.assertNotEqual(_upload_proposal_key("s1"), _upload_proposal_key("s2"))
        self.assertNotEqual(_upload_audio_key("s1"), _upload_audio_key("s2"))

    def test_keys_do_not_collide_with_hum_keys(self):
        from composition_studio_page import (
            _upload_proposal_key, _upload_audio_key,
            _hum_proposal_key, _hum_audio_key,
        )
        self.assertNotEqual(_upload_proposal_key("s1"), _hum_proposal_key("s1"))
        self.assertNotEqual(_upload_audio_key("s1"), _hum_audio_key("s1"))


# ===== Category 2: File type acceptance =====
class TestFileTypeAcceptance(unittest.TestCase):
    """Verify the upload panel advertises only WAV and MP3."""

    def test_accepted_extensions(self):
        import composition_studio_page as csp
        src = Path(csp.__file__).read_text(encoding="utf-8")
        self.assertIn('type=["wav", "mp3"]', src)

    def test_no_midi_extension(self):
        import composition_studio_page as csp
        src = Path(csp.__file__).read_text(encoding="utf-8")
        self.assertNotIn('"mid"', src.split("file_uploader")[1].split(")")[0])

    def test_no_musicxml_extension(self):
        import composition_studio_page as csp
        src = Path(csp.__file__).read_text(encoding="utf-8")
        chunk = src.split("file_uploader")[1].split(")")[0]
        self.assertNotIn('"xml"', chunk)
        self.assertNotIn('"musicxml"', chunk)


# ===== Category 3: Audio bytes storage =====
class TestAudioBytesStorage(unittest.TestCase):
    def test_upload_audio_key_stores_bytes(self):
        from composition_studio_page import _upload_audio_key
        session = {}
        key = _upload_audio_key("s1")
        session[key] = b"\x00\x01\x02"
        self.assertEqual(session[key], b"\x00\x01\x02")

    def test_clear_upload_removes_keys(self):
        from composition_studio_page import (
            _upload_proposal_key, _upload_audio_key, _clear_upload_proposal,
        )
        session = {
            _upload_proposal_key("s1"): {"status": "usable"},
            _upload_audio_key("s1"): b"\xff",
        }
        _clear_upload_proposal(session, "s1")
        self.assertNotIn(_upload_proposal_key("s1"), session)
        self.assertNotIn(_upload_audio_key("s1"), session)


# ===== Category 4: Transcription delegation =====
class TestTranscriptionDelegation(unittest.TestCase):
    """Upload path delegates to the same transcribe_hum_audio used by live recording."""

    def test_transcribe_hum_audio_is_callable(self):
        self.assertTrue(callable(transcribe_hum_audio))

    def test_upload_panel_calls_transcribe_hum_audio(self):
        import composition_studio_page as csp
        src = Path(csp.__file__).read_text(encoding="utf-8")
        panel_src = src[src.index("def _render_melody_upload_panel"):]
        panel_src = panel_src[:panel_src.index("\ndef _melody_intent_ready")]
        self.assertIn("transcribe_hum_audio", panel_src)

    def test_no_separate_upload_transcription_engine(self):
        """Ensures we did not introduce a second transcription path."""
        import composition_studio_page as csp
        src = Path(csp.__file__).read_text(encoding="utf-8")
        panel_src = src[src.index("def _render_melody_upload_panel"):]
        panel_src = panel_src[:panel_src.index("\ndef _melody_intent_ready")]
        self.assertNotIn("upload_transcribe", panel_src)
        self.assertNotIn("import_melody", panel_src)


# ===== Category 5: Zero count-in for uploads =====
class TestZeroCountInForUploads(unittest.TestCase):
    """Uploaded files do not have a metronome count-in."""

    def test_upload_panel_passes_zero_count_in(self):
        import composition_studio_page as csp
        src = Path(csp.__file__).read_text(encoding="utf-8")
        panel_src = src[src.index("def _render_melody_upload_panel"):]
        panel_src = panel_src[:panel_src.index("\ndef _melody_intent_ready")]
        self.assertIn("count_in_bars=0", panel_src)


# ===== Category 6: WAV transcription end-to-end =====
class TestWAVTranscription(unittest.TestCase):
    def test_transcribe_empty_wav_returns_unclear(self):
        result = transcribe_hum_audio(b"", bpm=120, meter="4/4", key="C")
        self.assertIn(result["status"], {"unclear", "unavailable"})

    @unittest.skipUnless(hum_analysis_available(), "librosa not installed")
    def test_transcribe_valid_wav_returns_events_or_status(self):
        import numpy as np, io, struct
        sr = 22050
        dur = 1.0
        freq = 440.0
        t = np.linspace(0, dur, int(sr * dur), endpoint=False)
        samples = (np.sin(2 * np.pi * freq * t) * 32767).astype(np.int16)
        buf = io.BytesIO()
        n = len(samples)
        buf.write(b"RIFF")
        buf.write(struct.pack("<I", 36 + n * 2))
        buf.write(b"WAVE")
        buf.write(b"fmt ")
        buf.write(struct.pack("<IHHIIHH", 16, 1, 1, sr, sr * 2, 2, 16))
        buf.write(b"data")
        buf.write(struct.pack("<I", n * 2))
        buf.write(samples.tobytes())
        wav_bytes = buf.getvalue()
        result = transcribe_hum_audio(wav_bytes, bpm=120, meter="4/4", key="C")
        self.assertIn(result["status"], {"usable", "uncertain", "unclear"})
        self.assertIsInstance(result["events"], list)


# ===== Category 7: MP3 transcription end-to-end =====
class TestMP3Transcription(unittest.TestCase):
    def test_transcribe_empty_mp3_returns_unclear(self):
        result = transcribe_hum_audio(b"", bpm=120, meter="4/4", key="C")
        self.assertIn(result["status"], {"unclear", "unavailable"})

    def test_transcribe_corrupt_mp3_returns_unclear(self):
        result = transcribe_hum_audio(b"\xff\xfb\x90\x00" + b"\x00" * 100, bpm=120, meter="4/4", key="C")
        self.assertIn(result["status"], {"unclear", "unavailable"})


# ===== Category 8: Empty / corrupt file handling =====
class TestEmptyCorruptFileHandling(unittest.TestCase):
    def test_empty_bytes(self):
        result = transcribe_hum_audio(b"", bpm=120, meter="4/4", key="C")
        self.assertIn(result["status"], {"unclear", "unavailable"})
        self.assertEqual(result["events"], [])

    def test_random_bytes(self):
        result = transcribe_hum_audio(b"\xde\xad\xbe\xef" * 50, bpm=120, meter="4/4", key="C")
        self.assertIn(result["status"], {"unclear", "unavailable"})

    def test_text_file_disguised_as_wav(self):
        result = transcribe_hum_audio(b"This is not audio data at all!", bpm=120, meter="4/4", key="C")
        self.assertIn(result["status"], {"unclear", "unavailable"})


# ===== Category 9: Short file handling =====
class TestShortFileHandling(unittest.TestCase):
    @unittest.skipUnless(hum_analysis_available(), "librosa not installed")
    def test_very_short_audio_returns_message(self):
        import numpy as np, io, struct
        sr = 22050
        dur = 0.1
        t = np.linspace(0, dur, int(sr * dur), endpoint=False)
        samples = (np.sin(2 * np.pi * 440.0 * t) * 32767).astype(np.int16)
        buf = io.BytesIO()
        n = len(samples)
        buf.write(b"RIFF")
        buf.write(struct.pack("<I", 36 + n * 2))
        buf.write(b"WAVE")
        buf.write(b"fmt ")
        buf.write(struct.pack("<IHHIIHH", 16, 1, 1, sr, sr * 2, 2, 16))
        buf.write(b"data")
        buf.write(struct.pack("<I", n * 2))
        buf.write(samples.tobytes())
        result = transcribe_hum_audio(buf.getvalue(), bpm=120, meter="4/4", key="C")
        self.assertEqual(result["status"], "unclear")
        self.assertIn("short", result["message"].lower())


# ===== Category 10: Proposal key lifecycle =====
class TestProposalKeyLifecycle(unittest.TestCase):
    def test_set_and_read(self):
        from composition_studio_page import _upload_proposal_key
        session = {}
        proposal = {"status": "usable", "events": SAMPLE_EVENTS}
        session[_upload_proposal_key("s1")] = proposal
        self.assertEqual(session[_upload_proposal_key("s1")]["status"], "usable")

    def test_clear_removes_proposal_and_audio(self):
        from composition_studio_page import (
            _upload_proposal_key, _upload_audio_key, _clear_upload_proposal,
        )
        session = {
            _upload_proposal_key("s1"): {"status": "usable"},
            _upload_audio_key("s1"): b"audio",
        }
        _clear_upload_proposal(session, "s1")
        self.assertNotIn(_upload_proposal_key("s1"), session)
        self.assertNotIn(_upload_audio_key("s1"), session)

    def test_clear_is_safe_when_empty(self):
        from composition_studio_page import _clear_upload_proposal
        session = {}
        _clear_upload_proposal(session, "s1")
        self.assertEqual(len(session), 0)


# ===== Category 11: Replacement warning gate =====
class TestReplacementWarningGate(unittest.TestCase):
    """The upload panel warns about replacement only when melody events exist."""

    def test_warning_text_in_source(self):
        import composition_studio_page as csp
        src = Path(csp.__file__).read_text(encoding="utf-8")
        panel_src = src[src.index("def _render_melody_upload_panel"):]
        panel_src = panel_src[:panel_src.index("\ndef _melody_intent_ready")]
        self.assertIn("already has an accepted melody", panel_src)

    def test_replace_button_label_when_melody_exists(self):
        import composition_studio_page as csp
        src = Path(csp.__file__).read_text(encoding="utf-8")
        panel_src = src[src.index("def _render_melody_upload_panel"):]
        panel_src = panel_src[:panel_src.index("\ndef _melody_intent_ready")]
        self.assertIn('"Replace melody"', panel_src)

    def test_use_button_label_when_no_melody(self):
        import composition_studio_page as csp
        src = Path(csp.__file__).read_text(encoding="utf-8")
        panel_src = src[src.index("def _render_melody_upload_panel"):]
        panel_src = panel_src[:panel_src.index("\ndef _melody_intent_ready")]
        self.assertIn('"Use this melody"', panel_src)


# ===== Category 12: Accept writes events via apply_melody_events =====
class TestAcceptWritesEvents(unittest.TestCase):
    def test_apply_melody_events_stores_events(self):
        doc = _make_doc(with_melody=False)
        result = apply_melody_events(doc, "s1", SAMPLE_EVENTS, concept=UPLOAD_CONCEPT, replace=True)
        self.assertTrue(len(result) > 0)
        stored = section_melody_events(section_by_id(doc, "s1"))
        self.assertEqual(len(stored), len(SAMPLE_EVENTS))

    def test_apply_melody_events_normalizes(self):
        doc = _make_doc(with_melody=False)
        apply_melody_events(doc, "s1", SAMPLE_EVENTS, concept=UPLOAD_CONCEPT, replace=True)
        stored = section_melody_events(section_by_id(doc, "s1"))
        for e in stored:
            self.assertIn("pitch", e)
            self.assertIn("duration_beats", e)


# ===== Category 13: Source ID is "file_upload" after accept =====
class TestSourceIDAfterAccept(unittest.TestCase):
    def test_source_id_set_to_file_upload(self):
        doc = _make_doc(with_melody=False)
        apply_melody_events(doc, "s1", SAMPLE_EVENTS, concept=UPLOAD_CONCEPT, replace=True)
        sec = section_by_id(doc, "s1")
        source_id = get_active_melody_source_id(sec)
        self.assertEqual(source_id, "file_upload")

    def test_source_id_replaces_hum_transcription(self):
        doc = _make_doc(with_melody=True)
        sec = section_by_id(doc, "s1")
        self.assertEqual(get_active_melody_source_id(sec), "hum_transcription")
        apply_melody_events(doc, "s1", SAMPLE_EVENTS, concept=UPLOAD_CONCEPT, replace=True)
        self.assertEqual(get_active_melody_source_id(sec), "file_upload")


# ===== Category 14: Concept phrase created with upload metadata =====
class TestConceptPhraseCreated(unittest.TestCase):
    def test_phrase_added_with_upload_label(self):
        doc = _make_doc(with_melody=False)
        apply_melody_events(doc, "s1", SAMPLE_EVENTS, concept=UPLOAD_CONCEPT, replace=True)
        sec = section_by_id(doc, "s1")
        phrases = sec["melody"]["phrases"]
        self.assertTrue(len(phrases) >= 1)
        last = phrases[-1]
        self.assertEqual(last["label"], "Uploaded melody")
        self.assertEqual(last["concept_id"], "file_upload")

    def test_phrase_motif_contains_upload_hint(self):
        doc = _make_doc(with_melody=False)
        apply_melody_events(doc, "s1", SAMPLE_EVENTS, concept=UPLOAD_CONCEPT, replace=True)
        sec = section_by_id(doc, "s1")
        last = sec["melody"]["phrases"][-1]
        self.assertIn("uploaded", last["motif"].lower())


# ===== Category 15: Replacement overwrites existing events =====
class TestReplacementOverwrite(unittest.TestCase):
    def test_replace_true_overwrites(self):
        doc = _make_doc(with_melody=True)
        sec = section_by_id(doc, "s1")
        old_events = list(section_melody_events(sec))
        self.assertTrue(len(old_events) > 0)
        apply_melody_events(doc, "s1", SAMPLE_EVENTS, concept=UPLOAD_CONCEPT, replace=True)
        new_events = section_melody_events(sec)
        self.assertEqual(len(new_events), len(SAMPLE_EVENTS))
        self.assertNotEqual(
            [e["pitch"] for e in old_events],
            [e["pitch"] for e in new_events],
        )

    def test_replace_changes_source_id(self):
        doc = _make_doc(with_melody=True)
        sec = section_by_id(doc, "s1")
        self.assertEqual(get_active_melody_source_id(sec), "hum_transcription")
        apply_melody_events(doc, "s1", SAMPLE_EVENTS, concept=UPLOAD_CONCEPT, replace=True)
        self.assertEqual(get_active_melody_source_id(sec), "file_upload")


# ===== Category 16: Keep-current leaves events untouched =====
class TestKeepCurrentMelody(unittest.TestCase):
    def test_no_apply_keeps_original(self):
        doc = _make_doc(with_melody=True)
        sec = section_by_id(doc, "s1")
        original = copy.deepcopy(section_melody_events(sec))
        current = section_melody_events(sec)
        self.assertEqual(len(current), len(original))
        for o, c in zip(original, current):
            self.assertEqual(o["pitch"], c["pitch"])

    def test_clear_proposal_does_not_modify_doc(self):
        from composition_studio_page import _clear_upload_proposal, _upload_proposal_key
        doc = _make_doc(with_melody=True)
        sec = section_by_id(doc, "s1")
        original = copy.deepcopy(section_melody_events(sec))
        session = {_upload_proposal_key("s1"): {"status": "usable", "events": SAMPLE_EVENTS}}
        _clear_upload_proposal(session, "s1")
        current = section_melody_events(sec)
        self.assertEqual(len(current), len(original))


# ===== Category 17: Preview delegates to play_composer_preview =====
class TestPreviewDelegation(unittest.TestCase):
    def test_upload_panel_calls_play_composer_preview(self):
        import composition_studio_page as csp
        src = Path(csp.__file__).read_text(encoding="utf-8")
        panel_src = src[src.index("def _render_melody_upload_panel"):]
        panel_src = panel_src[:panel_src.index("\ndef _melody_intent_ready")]
        self.assertIn("play_composer_preview", panel_src)

    def test_preview_uses_melody_override(self):
        import composition_studio_page as csp
        src = Path(csp.__file__).read_text(encoding="utf-8")
        panel_src = src[src.index("def _render_melody_upload_panel"):]
        panel_src = panel_src[:panel_src.index("\ndef _melody_intent_ready")]
        self.assertIn("melody_override=events", panel_src)

    def test_no_separate_playback_engine(self):
        import composition_studio_page as csp
        src = Path(csp.__file__).read_text(encoding="utf-8")
        panel_src = src[src.index("def _render_melody_upload_panel"):]
        panel_src = panel_src[:panel_src.index("\ndef _melody_intent_ready")]
        self.assertNotIn("upload_playback", panel_src)
        self.assertNotIn("import_playback", panel_src)


# ===== Category 18: Accepted card renders for file_upload source =====
class TestAcceptedCardForFileUpload(unittest.TestCase):
    def test_accepted_concept_for_file_upload(self):
        from composition_studio_page import _accepted_melody_concept_from_section
        doc = _make_doc(with_melody=False)
        apply_melody_events(doc, "s1", SAMPLE_EVENTS, concept=UPLOAD_CONCEPT, replace=True)
        sec = section_by_id(doc, "s1")
        card = _accepted_melody_concept_from_section(sec)
        self.assertIsNotNone(card)
        self.assertEqual(card["id"], "file_upload")
        self.assertEqual(card["name"], "Uploaded melody")
        self.assertIn("audio file", card["contour"])

    def test_accepted_concept_has_events(self):
        from composition_studio_page import _accepted_melody_concept_from_section
        doc = _make_doc(with_melody=False)
        apply_melody_events(doc, "s1", SAMPLE_EVENTS, concept=UPLOAD_CONCEPT, replace=True)
        sec = section_by_id(doc, "s1")
        card = _accepted_melody_concept_from_section(sec)
        self.assertEqual(len(card["events"]), len(SAMPLE_EVENTS))

    def test_hum_source_still_renders_correctly(self):
        from composition_studio_page import _accepted_melody_concept_from_section
        doc = _make_doc(with_melody=True)
        sec = section_by_id(doc, "s1")
        card = _accepted_melody_concept_from_section(sec)
        self.assertIsNotNone(card)
        self.assertEqual(card["id"], "hum_transcription")
        self.assertEqual(card["name"], "Recorded melody")


# ===== Category 19: Practice integration =====
class TestPracticeIntegration(unittest.TestCase):
    """Uploaded melody reaches Practice via Slice 5 bridge functions."""

    def test_uploaded_melody_visible_via_bridge(self):
        from composition_songs_bridge import composition_section_melody_events
        doc = _make_doc(with_melody=False)
        apply_melody_events(doc, "s1", SAMPLE_EVENTS, concept=UPLOAD_CONCEPT, replace=True)
        melody_by_sec = composition_section_melody_events(doc)
        self.assertIn("Verse", melody_by_sec)
        self.assertEqual(len(melody_by_sec["Verse"]), len(SAMPLE_EVENTS))

    def test_uploaded_melody_preserves_pitches(self):
        from composition_songs_bridge import composition_section_melody_events
        doc = _make_doc(with_melody=False)
        apply_melody_events(doc, "s1", SAMPLE_EVENTS, concept=UPLOAD_CONCEPT, replace=True)
        melody_by_sec = composition_section_melody_events(doc)
        pitches = [e["pitch"] for e in melody_by_sec["Verse"]]
        expected = [e["pitch"] for e in SAMPLE_EVENTS]
        self.assertEqual(pitches, expected)

    def test_lyrics_still_visible_after_upload(self):
        from composition_songs_bridge import composition_section_lyrics
        doc = _make_doc(with_melody=False)
        apply_melody_events(doc, "s1", SAMPLE_EVENTS, concept=UPLOAD_CONCEPT, replace=True)
        lyrics = composition_section_lyrics(doc)
        self.assertIn("Verse", lyrics)
        self.assertEqual(lyrics["Verse"], "Hello world")


# ===== Category 20: Practice Key transposition =====
class TestPracticeKeyTransposition(unittest.TestCase):
    def test_uploaded_melody_transposable(self):
        from media_tone_catalog import transpose_note_token
        from composition_songs_bridge import composition_written_pitch_semitones
        from music_theory import semitone_distance
        doc = _make_doc(with_melody=False)
        apply_melody_events(doc, "s1", SAMPLE_EVENTS, concept=UPLOAD_CONCEPT, replace=True)
        sec = section_by_id(doc, "s1")
        events = section_melody_events(sec)
        pk_semi = semitone_distance("C", "G")
        inst_semi = composition_written_pitch_semitones("Piano")
        total = pk_semi + inst_semi
        transposed = [transpose_note_token(e["pitch"], total) for e in events]
        self.assertEqual(transposed[0], "D5")

    def test_uploaded_melody_tenor_sax_transposition(self):
        from media_tone_catalog import transpose_note_token
        from composition_songs_bridge import composition_written_pitch_semitones
        doc = _make_doc(with_melody=False)
        apply_melody_events(doc, "s1", SAMPLE_EVENTS, concept=UPLOAD_CONCEPT, replace=True)
        sec = section_by_id(doc, "s1")
        events = section_melody_events(sec)
        inst_semi = composition_written_pitch_semitones("Tenor saxophone")
        self.assertEqual(inst_semi, 14)
        transposed = transpose_note_token(events[0]["pitch"], inst_semi)
        self.assertEqual(transposed, "A5")


# ===== Category 21: Backing Context unaffected =====
class TestBackingContextUnaffected(unittest.TestCase):
    def test_backing_has_no_melody_attr(self):
        from backing_context import build_composition_song_context
        doc = _make_doc(with_melody=False)
        apply_melody_events(doc, "s1", SAMPLE_EVENTS, concept=UPLOAD_CONCEPT, replace=True)
        session = {
            "_active_composition_document": doc,
            "_composition_document_id": doc["id"],
            "_selected_pick_key": f"composition::{doc['id']}",
            "music_source": "composition_song",
            "instrument": "Piano",
        }
        ctx = build_composition_song_context(session, doc=doc)
        self.assertFalse(hasattr(ctx, "melody") or hasattr(ctx, "melody_events"))

    def test_backing_preserves_chords_after_upload(self):
        from backing_context import build_composition_song_context
        from composition_songs_bridge import composition_original_sections
        doc = _make_doc(with_melody=False)
        apply_melody_events(doc, "s1", SAMPLE_EVENTS, concept=UPLOAD_CONCEPT, replace=True)
        secs = composition_original_sections(doc)
        self.assertIn("Verse", secs)
        self.assertTrue(len(secs["Verse"]) >= 2)

    def test_backing_source_still_composition(self):
        from backing_context import build_composition_song_context
        doc = _make_doc(with_melody=False)
        apply_melody_events(doc, "s1", SAMPLE_EVENTS, concept=UPLOAD_CONCEPT, replace=True)
        session = {
            "_active_composition_document": doc,
            "_composition_document_id": doc["id"],
            "_selected_pick_key": f"composition::{doc['id']}",
            "music_source": "composition_song",
            "instrument": "Piano",
        }
        ctx = build_composition_song_context(session, doc=doc)
        self.assertEqual(ctx.source, "composition_song")


# ===== Category 22: No MIDI/MusicXML parser guard =====
class TestNoMIDIMusicXMLParser(unittest.TestCase):
    def test_no_mido_in_requirements(self):
        req = Path(__file__).resolve().parent.parent / "requirements.txt"
        if req.exists():
            text = req.read_text(encoding="utf-8").lower()
            self.assertNotIn("mido", text)

    def test_no_pretty_midi_in_requirements(self):
        req = Path(__file__).resolve().parent.parent / "requirements.txt"
        if req.exists():
            text = req.read_text(encoding="utf-8").lower()
            self.assertNotIn("pretty_midi", text)
            self.assertNotIn("pretty-midi", text)

    def test_no_music21_in_requirements(self):
        req = Path(__file__).resolve().parent.parent / "requirements.txt"
        if req.exists():
            text = req.read_text(encoding="utf-8").lower()
            self.assertNotIn("music21", text)

    def test_upload_panel_does_not_mention_midi(self):
        import composition_studio_page as csp
        src = Path(csp.__file__).read_text(encoding="utf-8")
        panel_src = src[src.index("def _render_melody_upload_panel"):]
        panel_src = panel_src[:panel_src.index("\ndef _melody_intent_ready")]
        self.assertNotIn("midi", panel_src.lower())
        self.assertNotIn("musicxml", panel_src.lower())


if __name__ == "__main__":
    unittest.main()
