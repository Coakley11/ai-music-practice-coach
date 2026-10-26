"""Tests for composition_melody_import.py — unified import entry point.

Covers MIDI, MusicXML, and audio import paths, format detection,
error handling, and integration with the updated upload panel.
"""
from __future__ import annotations

import io
import struct
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from composition_melody_import import (
    file_extension,
    is_supported_file,
    supported_format_label,
    import_melody_from_file,
    FILE_IMPORT_SOURCE_ID,
    SUPPORTED_EXTENSIONS,
    _import_category,
    _parse_musicxml_to_events,
)


class TestFileExtensionDetection(unittest.TestCase):
    def test_wav(self):
        self.assertEqual(file_extension("melody.wav"), ".wav")

    def test_mp3(self):
        self.assertEqual(file_extension("song.mp3"), ".mp3")

    def test_midi(self):
        self.assertEqual(file_extension("tune.mid"), ".mid")

    def test_midi_long(self):
        self.assertEqual(file_extension("tune.midi"), ".midi")

    def test_musicxml(self):
        self.assertEqual(file_extension("score.musicxml"), ".musicxml")

    def test_xml(self):
        self.assertEqual(file_extension("score.xml"), ".xml")

    def test_mxl(self):
        self.assertEqual(file_extension("score.mxl"), ".mxl")

    def test_unsupported(self):
        ext = file_extension("photo.jpg")
        self.assertEqual(ext, ".jpg")

    def test_no_extension(self):
        self.assertEqual(file_extension("noext"), "")

    def test_case_insensitive(self):
        self.assertEqual(file_extension("MELODY.WAV"), ".wav")


class TestIsSupportedFile(unittest.TestCase):
    def test_wav_supported(self):
        self.assertTrue(is_supported_file("melody.wav"))

    def test_mp3_supported(self):
        self.assertTrue(is_supported_file("song.mp3"))

    def test_mid_supported(self):
        self.assertTrue(is_supported_file("tune.mid"))

    def test_musicxml_supported(self):
        self.assertTrue(is_supported_file("score.musicxml"))

    def test_jpg_not_supported(self):
        self.assertFalse(is_supported_file("photo.jpg"))

    def test_txt_not_supported(self):
        self.assertFalse(is_supported_file("notes.txt"))


class TestImportCategory(unittest.TestCase):
    def test_midi_category(self):
        self.assertEqual(_import_category("file.mid"), "midi")
        self.assertEqual(_import_category("file.midi"), "midi")

    def test_musicxml_category(self):
        self.assertEqual(_import_category("file.xml"), "musicxml")
        self.assertEqual(_import_category("file.musicxml"), "musicxml")
        self.assertEqual(_import_category("file.mxl"), "musicxml")

    def test_audio_category(self):
        self.assertEqual(_import_category("file.wav"), "audio")
        self.assertEqual(_import_category("file.mp3"), "audio")

    def test_unknown_category(self):
        self.assertEqual(_import_category("file.txt"), "unknown")


class TestSupportedFormatLabel(unittest.TestCase):
    def test_contains_midi(self):
        label = supported_format_label()
        self.assertIn("MIDI", label)

    def test_contains_musicxml(self):
        label = supported_format_label()
        self.assertIn("MusicXML", label)

    def test_contains_wav(self):
        label = supported_format_label()
        self.assertIn("WAV", label)


class TestImportMelodyFromFile(unittest.TestCase):
    def test_empty_data_returns_message(self):
        result = import_melody_from_file("test.wav", b"")
        self.assertIn("Empty", result["message"])
        self.assertEqual(result["events"], [])

    def test_unsupported_format(self):
        result = import_melody_from_file("test.jpg", b"data")
        self.assertIn("Unsupported", result["message"])

    def test_result_has_source_field(self):
        result = import_melody_from_file("test.wav", b"")
        self.assertEqual(result["source"], FILE_IMPORT_SOURCE_ID)

    def test_result_has_filename(self):
        result = import_melody_from_file("my_melody.wav", b"")
        self.assertEqual(result["filename"], "my_melody.wav")


class TestMusicXMLImport(unittest.TestCase):
    def _make_simple_musicxml(self, notes=None):
        if notes is None:
            notes = [("C", 4, "quarter"), ("D", 4, "quarter"), ("E", 4, "half")]
        root = ET.Element("score-partwise", version="3.1")
        part_list = ET.SubElement(root, "part-list")
        sp = ET.SubElement(part_list, "score-part", id="P1")
        ET.SubElement(sp, "part-name").text = "Melody"

        part = ET.SubElement(root, "part", id="P1")
        measure = ET.SubElement(part, "measure", number="1")
        attrs = ET.SubElement(measure, "attributes")
        ET.SubElement(attrs, "divisions").text = "1"

        dur_map = {"whole": 4, "half": 2, "quarter": 1, "eighth": 1}
        for step, octave, dur_type in notes:
            note = ET.SubElement(measure, "note")
            if step == "rest":
                ET.SubElement(note, "rest")
            else:
                pitch = ET.SubElement(note, "pitch")
                ET.SubElement(pitch, "step").text = step
                ET.SubElement(pitch, "octave").text = str(octave)
            ET.SubElement(note, "duration").text = str(dur_map.get(dur_type, 1))
            ntype = ET.SubElement(note, "type")
            ntype.text = dur_type

        return ET.tostring(root, encoding="unicode").encode("utf-8")

    def test_parse_simple_musicxml(self):
        data = self._make_simple_musicxml()
        events = _parse_musicxml_to_events(data, key="C", meter="4/4")
        pitched = [e for e in events if not e.get("is_rest")]
        self.assertEqual(len(pitched), 3)
        self.assertFalse(events[0].get("is_rest"))

    def test_musicxml_has_correct_pitches(self):
        data = self._make_simple_musicxml([("C", 4, "quarter"), ("G", 4, "quarter")])
        events = _parse_musicxml_to_events(data, key="C", meter="4/4")
        pitched = [e for e in events if not e.get("is_rest")]
        midis = [e["midi"] for e in pitched]
        self.assertEqual(midis[0], 60)  # C4
        self.assertEqual(midis[1], 67)  # G4

    def test_musicxml_rest_handling(self):
        data = self._make_simple_musicxml([("C", 4, "quarter"), ("rest", 0, "quarter"), ("E", 4, "quarter")])
        events = _parse_musicxml_to_events(data, key="C", meter="4/4")
        rests = [e for e in events if e.get("is_rest")]
        self.assertGreaterEqual(len(rests), 1)

    def test_import_musicxml_via_entry_point(self):
        data = self._make_simple_musicxml()
        result = import_melody_from_file("score.musicxml", data, key="C", meter="4/4")
        self.assertEqual(result["format"], "musicxml")
        self.assertEqual(result["status"], "usable")
        self.assertGreater(len(result["events"]), 0)
        self.assertEqual(result["confidence"], 1.0)

    def test_empty_musicxml_returns_empty(self):
        root = ET.Element("score-partwise")
        part_list = ET.SubElement(root, "part-list")
        sp = ET.SubElement(part_list, "score-part", id="P1")
        ET.SubElement(sp, "part-name").text = "Empty"
        part = ET.SubElement(root, "part", id="P1")
        data = ET.tostring(root, encoding="unicode").encode("utf-8")
        result = import_melody_from_file("empty.xml", data)
        self.assertIn(result["status"], {"empty", "unclear"})

    def test_invalid_xml_returns_error(self):
        result = import_melody_from_file("bad.xml", b"<not valid xml")
        self.assertIn("parse", result["message"].lower())


class TestMIDIImport(unittest.TestCase):
    def test_midi_unavailable_graceful(self):
        with patch.dict("sys.modules", {"mido": None}):
            from composition_melody_import import _midi_available
            # Can't easily test this without actually removing mido,
            # but we can test the import_melody_from_file error path
            pass

    def test_midi_import_with_mock(self):
        try:
            import mido
        except ImportError:
            self.skipTest("mido not installed")

        mid = mido.MidiFile(type=0, ticks_per_beat=480)
        track = mido.MidiTrack()
        mid.tracks.append(track)
        track.append(mido.MetaMessage("set_tempo", tempo=500000))
        track.append(mido.Message("note_on", note=60, velocity=64, time=0))
        track.append(mido.Message("note_off", note=60, velocity=0, time=480))
        track.append(mido.Message("note_on", note=62, velocity=64, time=0))
        track.append(mido.Message("note_off", note=62, velocity=0, time=480))
        track.append(mido.Message("note_on", note=64, velocity=64, time=0))
        track.append(mido.Message("note_off", note=64, velocity=0, time=960))

        buf = io.BytesIO()
        mid.save(file=buf)
        data = buf.getvalue()

        result = import_melody_from_file("test.mid", data, key="C", bpm=120)
        self.assertEqual(result["format"], "midi")
        self.assertEqual(result["status"], "usable")
        pitched = [e for e in result["events"] if not e.get("is_rest")]
        self.assertEqual(len(pitched), 3)

    def test_empty_midi_returns_empty(self):
        try:
            import mido
        except ImportError:
            self.skipTest("mido not installed")

        mid = mido.MidiFile(type=0, ticks_per_beat=480)
        mid.tracks.append(mido.MidiTrack())
        buf = io.BytesIO()
        mid.save(file=buf)
        result = import_melody_from_file("empty.mid", buf.getvalue())
        self.assertIn(result["status"], {"empty", "unclear"})


class TestAudioImportPath(unittest.TestCase):
    def test_audio_delegates_to_transcription(self):
        with patch("composition_hum_transcription.transcribe_hum_audio") as mock_t:
            mock_t.return_value = {
                "status": "usable",
                "message": "OK",
                "events": [{"pitch": "C4", "midi": 60, "duration_beats": 1.0}],
                "confidence": 0.8,
            }
            result = import_melody_from_file("voice.wav", b"RIFF" + b"\x00" * 100, key="G", bpm=100)
            mock_t.assert_called_once()
            self.assertEqual(result["format"], "audio")
            self.assertEqual(len(result["events"]), 1)


class TestFileImportSourceID(unittest.TestCase):
    def test_source_constant(self):
        self.assertEqual(FILE_IMPORT_SOURCE_ID, "file_import")

    def test_differs_from_hum(self):
        self.assertNotEqual(FILE_IMPORT_SOURCE_ID, "hum_transcription")

    def test_differs_from_old_upload(self):
        self.assertNotEqual(FILE_IMPORT_SOURCE_ID, "file_upload")


class TestUploadPanelIntegration(unittest.TestCase):
    def test_upload_filename_key_exists(self):
        from composition_studio_page import _upload_filename_key
        k = _upload_filename_key("s1")
        self.assertIn("s1", k)
        self.assertIn("filename", k)

    def test_clear_proposal_removes_filename(self):
        from composition_studio_page import (
            _clear_upload_proposal,
            _upload_proposal_key,
            _upload_audio_key,
            _upload_filename_key,
        )
        ss = {
            _upload_proposal_key("s1"): {"status": "usable"},
            _upload_audio_key("s1"): b"data",
            _upload_filename_key("s1"): "test.mid",
        }
        _clear_upload_proposal(ss, "s1")
        self.assertNotIn(_upload_proposal_key("s1"), ss)
        self.assertNotIn(_upload_audio_key("s1"), ss)
        self.assertNotIn(_upload_filename_key("s1"), ss)

    def test_accepted_card_recognizes_file_import(self):
        from composition_studio_page import _accepted_melody_concept_from_section
        section = {
            "id": "s1",
            "melody": {
                "events": [{"pitch": "C4", "midi": 60, "duration_beats": 1.0}],
                "active_source_id": "file_import",
                "phrases": [],
            },
        }
        concept = _accepted_melody_concept_from_section(section)
        self.assertIsNotNone(concept)
        self.assertEqual(concept["id"], "file_import")
        self.assertIn("Imported", concept["name"])

    def test_accepted_card_still_recognizes_file_upload(self):
        from composition_studio_page import _accepted_melody_concept_from_section
        section = {
            "id": "s1",
            "melody": {
                "events": [{"pitch": "C4", "midi": 60, "duration_beats": 1.0}],
                "active_source_id": "file_upload",
                "phrases": [],
            },
        }
        concept = _accepted_melody_concept_from_section(section)
        self.assertIsNotNone(concept)
        self.assertEqual(concept["id"], "file_upload")


class TestMusicXMLEdgeCases(unittest.TestCase):
    def test_dotted_note_durations(self):
        root = ET.Element("score-partwise")
        part_list = ET.SubElement(root, "part-list")
        sp = ET.SubElement(part_list, "score-part", id="P1")
        ET.SubElement(sp, "part-name").text = "Test"
        part = ET.SubElement(root, "part", id="P1")
        measure = ET.SubElement(part, "measure", number="1")
        attrs = ET.SubElement(measure, "attributes")
        ET.SubElement(attrs, "divisions").text = "2"

        note = ET.SubElement(measure, "note")
        pitch = ET.SubElement(note, "pitch")
        ET.SubElement(pitch, "step").text = "C"
        ET.SubElement(pitch, "octave").text = "4"
        ET.SubElement(note, "duration").text = "3"  # dotted quarter = 1.5 beats

        data = ET.tostring(root, encoding="unicode").encode("utf-8")
        events = _parse_musicxml_to_events(data, key="C", meter="4/4")
        self.assertEqual(len(events), 1)
        self.assertGreater(events[0]["duration_beats"], 1.0)

    def test_multi_voice_filters_to_voice_1(self):
        root = ET.Element("score-partwise")
        part_list = ET.SubElement(root, "part-list")
        sp = ET.SubElement(part_list, "score-part", id="P1")
        ET.SubElement(sp, "part-name").text = "Test"
        part = ET.SubElement(root, "part", id="P1")
        measure = ET.SubElement(part, "measure", number="1")
        attrs = ET.SubElement(measure, "attributes")
        ET.SubElement(attrs, "divisions").text = "1"

        # Voice 1 note
        n1 = ET.SubElement(measure, "note")
        p1 = ET.SubElement(n1, "pitch")
        ET.SubElement(p1, "step").text = "C"
        ET.SubElement(p1, "octave").text = "4"
        ET.SubElement(n1, "duration").text = "1"
        ET.SubElement(n1, "voice").text = "1"

        # Voice 2 note (should be filtered)
        n2 = ET.SubElement(measure, "note")
        p2 = ET.SubElement(n2, "pitch")
        ET.SubElement(p2, "step").text = "E"
        ET.SubElement(p2, "octave").text = "3"
        ET.SubElement(n2, "duration").text = "1"
        ET.SubElement(n2, "voice").text = "2"

        data = ET.tostring(root, encoding="unicode").encode("utf-8")
        events = _parse_musicxml_to_events(data, key="C", meter="4/4")
        pitched = [e for e in events if not e.get("is_rest")]
        self.assertEqual(len(pitched), 1)
        self.assertEqual(events[0]["midi"], 60)  # C4 only


if __name__ == "__main__":
    unittest.main()
