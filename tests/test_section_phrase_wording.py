"""Song card sentences name a chart section once: "the B section", never "the Section B section"."""
import unittest

from song_card_guidance import section_phrase


class SectionPhraseWording(unittest.TestCase):
    def test_section_letter_names_read_once(self) -> None:
        self.assertEqual(section_phrase("Section B"), "the B section")
        self.assertEqual(section_phrase("Section A"), "the A section")
        self.assertEqual(section_phrase("section a2"), "the A2 section")
        self.assertEqual(section_phrase("Part A"), "the A section")

    def test_existing_forms_unchanged(self) -> None:
        self.assertEqual(section_phrase("A"), "the A section")
        self.assertEqual(section_phrase("B (Bridge)"), "the bridge")
        self.assertEqual(section_phrase("A section"), "the A section")
        self.assertEqual(section_phrase("Verse"), "the verse")
        self.assertEqual(section_phrase("Chorus 2"), "Chorus 2")
        self.assertEqual(section_phrase(""), "the song")


if __name__ == "__main__":
    unittest.main()
