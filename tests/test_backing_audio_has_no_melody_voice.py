"""Backing audio is accompaniment only; the musician plays the composed melody.

The rule (user, 2026-11-27):

    Melody events may be read for visual notation, lead-sheet synchronization and
    highlighting, but they must not be introduced into accompaniment-only audio
    generation.

This file used to enforce that with one assertion: four terms, forbidden in every
``backing_*.py``. Three of them are the composition preview renderer's melody-into-sound
API -- ``include_melody`` and ``melody_override`` are parameters of
``composition_preview.generate_preview_wav``, which mixes a melody voice into rendered
audio. No visual use exists for any of them, so they stay forbidden everywhere, and
``melody_gain`` (the same renderer's melody level) is forbidden alongside them.

The fourth, ``composition_section_melody_events``, is only a data read: it returns the
composed melody's per-section events and renders nothing. Forbidding it outright also
forbade drawing the Original Melody panel on the Backing page, which is the legitimate
case the rule means to allow -- notation, page-follow and highlighting, no sound.

The allowance is deliberately an allow-list rather than a relaxation, so that it fails
closed: a backing module may read melody events only if it is named in
:data:`MELODY_READERS_ALLOWED` *and* generates no audio. A new module that starts reading
them fails this file until someone states the display reason, and an approved reader that
later grows an audio path fails it too.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Melody INTO sound: the parameters and entry point of the renderer that mixes a melody
# voice into audio. Forbidden in every backing module, with no exception.
MELODY_INTO_AUDIO = ("include_melody", "melody_override", "melody_gain", "generate_preview_wav")

# Reading the composed melody's events. Legitimate for notation only. Spelled out as a
# family so that a rename does not slip past the check.
MELODY_EVENT_SOURCES = (
    "composition_section_melody_events",
    "composition_melody_events",
    "section_melody_events",
    "melody_events_for_section",
    "project_melody_events",
)

# The backing modules allowed to read them, each with its stated display-only reason.
MELODY_READERS_ALLOWED = {
    "backing_melody_modes.py": (
        "draws the Original Melody panel under the Backing Lead Sheet: notation, "
        "page-follow and highlighting. original_melody_sections returns events; it "
        "renders no sound."
    ),
}

# Backing's audio-generating vocabulary, in the four areas the rule protects. Broad on
# purpose: a false hit means an approved reader *looks* like it makes audio, which is a
# failure worth having, whereas a miss would let a real leak through.
AUDIO_GENERATION = {
    "synthesis": r"synthesize\w*\(|_add_tone\(|np\.(zeros|sin|arange)\(|sample_rate|\bsr\s*=\s*\d",
    "instrument layers": (
        r"backing_horns|backing_pianist|backing_rock_guitar|backing_bass\b|"
        r"recorded_instruments|backing_sampled_instrument|start_part\("
    ),
    "mixing": (
        r"backing_gain|melody_gain|np\.clip\(|audio\s*\+=|\bmix\w*\s*=|_mixdown|"
        r"backing_band_balance|backing_eq|backing_loudness"
    ),
    "export": (
        r"wav_bytes_from_float|pcm16_wav_bytes|soundfile|sf\.write|st\.audio\(|"
        r"\.wav[\"']|backing_wav_runtime_cache"
    ),
}


def melody_audio_offenders(name: str, text: str) -> list[str]:
    """Why this backing module breaks the rule. An empty list means it is clean.

    Taking ``(name, text)`` rather than reading the file is what makes the rule itself
    testable: the leak-detection tests below feed it deliberately violating sources.
    """
    problems: list[str] = []
    for term in MELODY_INTO_AUDIO:
        if term in text:
            problems.append(f"{name}: puts melody into audio via {term!r}")
    if any(term in text for term in MELODY_EVENT_SOURCES):
        if name not in MELODY_READERS_ALLOWED:
            problems.append(
                f"{name}: reads composed-melody events but is not an approved display "
                f"module. Reading them is allowed only for notation, synchronization "
                f"and highlighting - add it to MELODY_READERS_ALLOWED with the display "
                f"reason, or keep the melody out of it."
            )
        else:
            for area, pattern in AUDIO_GENERATION.items():
                found = re.search(pattern, text)
                if found:
                    problems.append(
                        f"{name}: reads composed-melody events AND generates audio "
                        f"({area}: {found.group(0)!r}). An approved melody reader must "
                        f"stay display-only."
                    )
    return problems


class TestBackingAudioHasNoMelodyVoice(unittest.TestCase):
    """The real backing modules, as they stand."""

    def _scan(self) -> list[str]:
        problems: list[str] = []
        for path in sorted(ROOT.glob("backing_*.py")):
            text = path.read_text(encoding="utf-8", errors="ignore")
            problems += melody_audio_offenders(path.name, text)
        return problems

    def test_no_backing_module_puts_melody_into_audio(self) -> None:
        self.assertEqual([p for p in self._scan() if "into audio via" in p], [])

    def test_every_backing_module_satisfies_the_whole_rule(self) -> None:
        self.assertEqual(self._scan(), [])

    def test_the_scan_actually_covers_the_backing_modules(self) -> None:
        """Non-vacuity: an empty glob would make both tests above pass for nothing."""
        self.assertGreater(len(list(ROOT.glob("backing_*.py"))), 20)


class TestTheApprovedReaderIsDisplayOnly(unittest.TestCase):
    """The allowance is exercised, and genuinely narrow rather than a hole."""

    def test_the_allow_list_is_not_dead_weight(self) -> None:
        """Each approved reader must exist and must really read melody events."""
        for name, reason in MELODY_READERS_ALLOWED.items():
            with self.subTest(module=name):
                path = ROOT / name
                self.assertTrue(path.exists(), f"{name} is in the allow-list but is gone")
                text = path.read_text(encoding="utf-8")
                self.assertTrue(
                    any(term in text for term in MELODY_EVENT_SOURCES),
                    f"{name} no longer reads melody events - take it off the allow-list",
                )
                self.assertGreater(len(reason), 40, "the display reason must be stated")

    def test_the_approved_reader_generates_no_audio(self) -> None:
        text = (ROOT / "backing_melody_modes.py").read_text(encoding="utf-8")
        for area, pattern in AUDIO_GENERATION.items():
            with self.subTest(area=area):
                found = re.search(pattern, text)
                hit = found.group(0) if found else ""
                self.assertIsNone(
                    found,
                    f"the Original Melody display module now touches {area}: {hit!r}",
                )

    def test_reading_the_melody_returns_notation_data_and_no_sound(self) -> None:
        """Behaviour, not source text: the read hands back events, never audio bytes."""
        from backing_melody_modes import original_melody_sections

        doc = {
            "sections": [{"id": "s1", "label": "Verse"}],
            "melodies": {"s1": {"events": [{"beat": 0.0, "midi": 62, "duration_beats": 1.0}]}},
        }
        sections, source = original_melody_sections(composition_doc=doc, song_data=None)
        self.assertIsInstance(sections, dict)
        self.assertIsInstance(source, str)
        self.assertNotIsInstance(sections, (bytes, bytearray))
        for events in sections.values():
            self.assertIsInstance(events, list)
            for event in events:
                self.assertNotIsInstance(event, (bytes, bytearray))

    def test_a_synchronized_song_melody_is_read_the_same_display_only_way(self) -> None:
        from backing_melody_modes import original_melody_sections

        sections, source = original_melody_sections(
            composition_doc=None,
            song_data={
                "original_melody": {
                    "synchronized": True,
                    "sections": {"Verse": [{"beat": 0.0, "midi": 64, "duration_beats": 1.0}]},
                }
            },
        )
        self.assertEqual(source, "song")
        self.assertEqual(list(sections), ["Verse"])
        self.assertNotIsInstance(sections["Verse"], (bytes, bytearray))


class TestTheRuleCatchesADeliberateLeak(unittest.TestCase):
    """Feed the checker violations on purpose. If it stays silent, it is worthless."""

    CLEAN_DISPLAY = (
        "from composition_songs_bridge import composition_section_melody_events\n"
        "def draw(st, doc):\n"
        "    for label, events in composition_section_melody_events(doc).items():\n"
        "        st.write(label, len(events))  # notation only\n"
    )

    def test_a_clean_display_module_passes(self) -> None:
        self.assertEqual(
            melody_audio_offenders("backing_melody_modes.py", self.CLEAN_DISPLAY), []
        )

    def test_melody_synthesized_into_backing_audio_is_caught(self) -> None:
        leak = self.CLEAN_DISPLAY + (
            "    buf = synthesize_chords_to_numpy(chords)\n"
            "    for e in events:\n"
            "        _add_tone(buf, 44100, e['beat'], 1.0, e['midi'], 0.4)\n"
        )
        problems = melody_audio_offenders("backing_melody_modes.py", leak)
        self.assertTrue(problems, "a melody synthesized into the backing buffer went unnoticed")
        self.assertTrue(any("synthesis" in p for p in problems), problems)

    def test_melody_routed_through_an_instrument_layer_is_caught(self) -> None:
        leak = self.CLEAN_DISPLAY + (
            "    import backing_horns\n"
            "    backing_horns.start_part(events)\n"
        )
        problems = melody_audio_offenders("backing_melody_modes.py", leak)
        self.assertTrue(any("instrument layers" in p for p in problems), problems)

    def test_melody_mixed_into_the_backing_mix_is_caught(self) -> None:
        leak = self.CLEAN_DISPLAY + "    audio += melody_buffer * 0.5\n"
        problems = melody_audio_offenders("backing_melody_modes.py", leak)
        self.assertTrue(any("mixing" in p for p in problems), problems)

    def test_melody_written_into_an_exported_wav_is_caught(self) -> None:
        leak = self.CLEAN_DISPLAY + "    return wav_bytes_from_float(buf_with_melody, 44100)\n"
        problems = melody_audio_offenders("backing_melody_modes.py", leak)
        self.assertTrue(any("export" in p for p in problems), problems)

    def test_the_renderers_melody_api_is_caught_in_any_backing_module(self) -> None:
        for term in MELODY_INTO_AUDIO:
            for module in ("backing_melody_modes.py", "backing_display.py", "backing_new.py"):
                with self.subTest(term=term, module=module):
                    problems = melody_audio_offenders(module, f"x = {term}\n")
                    self.assertTrue(
                        any("into audio via" in p for p in problems),
                        f"{term} went unnoticed in {module}",
                    )

    def test_an_unapproved_module_reading_melody_is_caught(self) -> None:
        """Fails closed: a new reader is a failure until the display reason is stated."""
        problems = melody_audio_offenders("backing_display.py", self.CLEAN_DISPLAY)
        self.assertTrue(any("not an approved display module" in p for p in problems), problems)

    def test_a_module_with_no_melody_at_all_is_left_alone(self) -> None:
        """No false positives: audio code without melody is exactly what Backing is."""
        plain = (
            "def render(chords):\n"
            "    buf = synthesize_chords_to_numpy(chords)\n"
            "    return wav_bytes_from_float(buf, 44100)\n"
        )
        self.assertEqual(melody_audio_offenders("backing_audio.py", plain), [])


class TestTheBackingAudioPathIsAccompanimentOnly(unittest.TestCase):
    """The renderer that actually makes backing audio has no melody input at all."""

    def test_the_backing_synthesizer_accepts_no_melody(self) -> None:
        import inspect

        from backing_audio import synthesize_chords_to_numpy

        names = list(inspect.signature(synthesize_chords_to_numpy).parameters)
        self.assertIn("chords", names)
        for name in names:
            self.assertNotIn(
                "melody", name.lower(),
                f"the backing synthesizer grew a melody input: {name!r}",
            )

    def test_a_melody_cannot_be_passed_to_the_backing_synthesizer(self) -> None:
        """Not just absent from the signature: there is no way in. Raises before synthesis."""
        from backing_audio import synthesize_chords_to_numpy

        for kwarg in ("melody", "melody_events", "include_melody", "melody_override"):
            with self.subTest(kwarg=kwarg):
                with self.assertRaises(TypeError):
                    synthesize_chords_to_numpy(["C", "G"], **{kwarg: [{"midi": 60}]})

    def _panel_block(self) -> str:
        src = (ROOT / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
        head = re.search(r"^([ \t]*)#\s*-+\s*Original Melody panel[^\n]*$", src, re.M)
        self.assertIsNotNone(head, "the Original Melody panel section marker is gone")
        after = src[head.end():]
        ends = []
        nxt = re.search(r"^" + re.escape(head.group(1)) + r"#\s*-+\s", after, re.M)
        if nxt:
            ends.append(nxt.start())
        feature = after.find("enable_backing_user_edits")
        if feature != -1:
            ends.append(feature)
        block = src[head.start(): head.end() + min(ends)] if ends else src[head.start():]
        self.assertGreater(
            block.count("\n"), 40,
            "the panel block looks truncated - revisit the boundary rule, not the app",
        )
        return block

    def test_backing_page_never_requests_melody_audio(self) -> None:
        """The Backing page's Original Melody panel draws notation and asks for no sound.

        The block is located structurally rather than by exact wording. The old start was
        the literal comment "Original Melody panel (Composition songs only)", and that
        qualifier was dropped when the panel stopped being Composition-only; the old end
        was the first "\\n    try:" after it, but the panel's own body opens a try: block
        within a few lines, so the slice was six lines long and could not have contained
        the term it was forbidding.
        """
        block = self._panel_block()
        for term in MELODY_INTO_AUDIO:
            with self.subTest(term=term):
                self.assertNotIn(term, block)

    def test_the_panel_does_draw_the_melody_it_reads(self) -> None:
        """Non-vacuity for the test above: the block really is the melody panel."""
        block = self._panel_block()
        self.assertIn("project_melody_events", block)
        self.assertIn("measure_sync", block)


if __name__ == "__main__":
    unittest.main()
