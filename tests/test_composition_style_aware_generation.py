"""Style- and song-intent-aware Composition harmony + melody generation."""

from __future__ import annotations

import unittest

from composition_chord_repeats import accept_full_progression
from composition_chord_suggestions import suggest_progressions
from composition_document import (
    apply_structure_template,
    bootstrap_from_vision,
    ordered_sections,
    parse_chord_paste,
)
from composition_melody_suggestions import suggest_melody_concepts
from composition_melody_shape import events_signature
from composition_song_intent import (
    build_song_intent_profile,
    describe_harmony_from_events,
    normalize_style_family,
    parse_creative_flags,
    parse_reference_attributes,
)


def _doc(
    *,
    genre: str,
    idea: str = "uplifting",
    refs: str = "",
    bpm: int = 110,
    energy: str = "Mid-tempo — steady groove",
    key: str = "C",
) -> tuple[dict, dict]:
    doc = bootstrap_from_vision(
        genre=genre,
        song_idea=idea,
        references=refs,
        energy=energy,
        mood="Hopeful",
        key=key,
        bpm=bpm,
        meter="4/4",
    )
    apply_structure_template(doc, "simple")
    chorus = next(s for s in ordered_sections(doc) if str(s.get("label") or "") == "Chorus")
    return doc, chorus


def _chord_sig(idea: dict) -> tuple[str, ...]:
    return tuple(
        str(c.get("chord") or "")
        for c in (idea.get("chords") or [])
        if isinstance(c, dict) and str(c.get("chord") or "").strip()
    )


class TestSongIntentProfile(unittest.TestCase):
    def test_existing_fields_feed_profile(self) -> None:
        doc, sec = _doc(
            genre="Jazz",
            idea="intimate love song that builds bigger in the chorus",
            refs="Bill Evans",
            bpm=92,
            energy="Ballad — slow and intimate",
        )
        profile = build_song_intent_profile(doc, sec, remember="a warm hook", melody_notes="piano-driven")
        self.assertEqual(profile["style_family"], "jazz")
        self.assertEqual(profile["key_center"], "C")
        self.assertEqual(profile["bpm"], 92)
        self.assertEqual(profile["section_goal"], "hook_peak")
        self.assertTrue(profile["flags"]["intimate"] or profile["flags"]["love"])
        self.assertTrue(profile["flags"]["build_chorus"] or profile["flags"]["love"])
        self.assertEqual(profile["listener_memory"], "a warm hook")
        self.assertIn("piano", str(profile["melody_notes"]).lower() + str(profile["flags"]))
        self.assertGreaterEqual(float(profile["harmonic_complexity"]), 0.7)
        self.assertGreaterEqual(float(profile["extension_bias"]), 0.7)

    def test_jewish_substyles_from_context(self) -> None:
        self.assertEqual(normalize_style_family("Jewish", notes="klezmer freylekh"), "jewish_klezmer")
        self.assertEqual(
            normalize_style_family("Jewish", concept="contemporary Jewish pop camp song"),
            "jewish_pop",
        )
        self.assertEqual(normalize_style_family("Jewish", references="Israeli Tel Aviv"), "jewish_israeli")

    def test_reference_attrs_not_copied_song(self) -> None:
        attrs = parse_reference_attributes("Billy Joel")
        self.assertTrue(attrs["piano_driven"])
        self.assertTrue(attrs["narrative_phrasing"])
        self.assertNotIn("just the way you are", str(attrs).lower())
        self.assertFalse(any("progression" in str(v).lower() for v in attrs.values() if not isinstance(v, bool)))


class TestStyleAwareHarmony(unittest.TestCase):
    def test_styles_produce_different_chord_vocab(self) -> None:
        lines: dict[str, set[tuple[str, ...]]] = {}
        for genre in ("Pop", "Jazz", "Rock", "Bossa"):
            doc, sec = _doc(genre=genre, idea="uplifting", bpm=110)
            ideas = suggest_progressions(doc, sec, "uplifting", limit=3)
            self.assertGreaterEqual(len(ideas), 2, genre)
            lines[genre] = {_chord_sig(i) for i in ideas}
            for idea in ideas:
                self.assertEqual(idea.get("style_family"), normalize_style_family(genre))
                why = str(idea.get("why") or "")
                sig = _chord_sig(idea)
                # Description must mention actual chord symbols.
                self.assertTrue(any(s in why for s in sig[:2]), (genre, why, sig))

        # Jazz should not collapse to the same Pop I–vi–IV–V set alone.
        pop_flat = {c for sig in lines["Pop"] for c in sig}
        jazz_flat = {c for sig in lines["Jazz"] for c in sig}
        rock_flat = {c for sig in lines["Rock"] for c in sig}
        bossa_flat = {c for sig in lines["Bossa"] for c in sig}
        self.assertTrue(
            any(("7" in c or "maj7" in c or "m7" in c) for c in jazz_flat),
            jazz_flat,
        )
        self.assertTrue(
            any(("7" in c or "maj7" in c or "9" in c or "6" in c) for c in bossa_flat),
            bossa_flat,
        )
        self.assertTrue(
            any(c.startswith(("Bb", "Eb", "Ab")) or c in {"Bb", "Eb", "F"} for c in rock_flat)
            or any(sig != next(iter(lines["Pop"])) for sig in lines["Rock"]),
            rock_flat,
        )
        self.assertNotEqual(lines["Pop"], lines["Jazz"])
        self.assertNotEqual(lines["Pop"], lines["Rock"])
        # Controlled C / 110 / Chorus / uplifting: styles must not all be identical.
        all_first = {next(iter(v)) for v in lines.values() if v}
        self.assertGreater(len(all_first), 1, lines)

    def test_tempo_changes_harmonic_rhythm(self) -> None:
        doc_slow, sec_s = _doc(genre="Pop", idea="story song", bpm=70, energy="Ballad — slow and intimate")
        doc_fast, sec_f = _doc(genre="Pop", idea="driving upbeat song", bpm=150, energy="Driving — high energy")
        slow = suggest_progressions(doc_slow, sec_s, "reflective", limit=3)
        fast = suggest_progressions(doc_fast, sec_f, "energetic", limit=3)
        slow_lens = [len(_chord_sig(i)) for i in slow]
        fast_lens = [len(_chord_sig(i)) for i in fast]
        self.assertNotEqual(slow_lens, fast_lens)

    def test_section_role_changes_profile_goal(self) -> None:
        doc = bootstrap_from_vision(genre="Pop", song_idea="uplifting", key="C", bpm=110, meter="4/4")
        apply_structure_template(doc, "simple")
        verse = next(s for s in ordered_sections(doc) if s.get("label") == "Verse")
        chorus = next(s for s in ordered_sections(doc) if s.get("label") == "Chorus")
        pv = build_song_intent_profile(doc, verse)
        pc = build_song_intent_profile(doc, chorus)
        self.assertEqual(pv["style_family"], pc["style_family"])
        self.assertEqual(pv["section_goal"], "story")
        self.assertEqual(pc["section_goal"], "hook_peak")

    def test_concept_flags_affect_profile(self) -> None:
        intimate = parse_creative_flags("intimate love song")
        anthem = parse_creative_flags("big celebratory anthem")
        self.assertTrue(intimate["intimate"] or intimate["love"])
        self.assertTrue(anthem["anthem"] or anthem["uplifting"])
        doc_i, sec_i = _doc(genre="Pop", idea="intimate love song", bpm=80, energy="Ballad — slow and intimate")
        doc_a, sec_a = _doc(genre="Pop", idea="big celebratory anthem", bpm=120, energy="Driving — high energy")
        pi = build_song_intent_profile(doc_i, sec_i)
        pa = build_song_intent_profile(doc_a, sec_a)
        self.assertNotEqual(pi["energy_tier"], pa["energy_tier"])
        ideas_i = {_chord_sig(i) for i in suggest_progressions(doc_i, sec_i, "reflective", limit=3)}
        ideas_a = {_chord_sig(i) for i in suggest_progressions(doc_a, sec_a, "uplifting", limit=3)}
        self.assertNotEqual(ideas_i, ideas_a)

    def test_harmony_description_grounded(self) -> None:
        why = describe_harmony_from_events(
            [{"chord": "Dm7"}, {"chord": "G7"}, {"chord": "Cmaj7"}],
            profile={"style_family": "jazz", "section_goal": "hook_peak"},
        )
        self.assertIn("Dm7", why)
        self.assertIn("ii–V", why)
        self.assertNotIn("bVII", why)


class TestStyleAwareMelody(unittest.TestCase):
    def test_melody_uses_song_profile_and_accepted_chords(self) -> None:
        doc, sec = _doc(genre="Jazz", idea="reflective", bpm=110)
        accept_full_progression(
            doc,
            str(sec["id"]),
            parse_chord_paste("Dm7 G7 Cmaj7 A7"),
            tiled=False,
        )
        concepts = suggest_melody_concepts(
            doc,
            sec,
            "lyrical",
            "expressive",
            limit=3,
            remember="a singable hook",
            notes="keep it warm",
        )
        self.assertEqual(len(concepts), 3)
        for c in concepts:
            self.assertEqual(c.get("style_family"), "jazz")
            self.assertEqual(c.get("chord_span"), 4)
            self.assertTrue(c.get("events"))
            self.assertIn("singable hook", str(c.get("remember") or ""))
            desc = str(c.get("contour") or "")
            self.assertEqual(desc, str(c.get("why") or ""))
            # Event-grounded: mention at least one pitch from events
            pitches = [str(e.get("pitch") or "") for e in c["events"] if e.get("pitch")]
            self.assertTrue(any(p in desc for p in pitches[:3]), desc)

    def test_style_changes_melody_events(self) -> None:
        sigs: dict[str, set] = {}
        for genre in ("Pop", "Jazz", "Rock", "Bossa"):
            doc, sec = _doc(genre=genre, idea="uplifting", bpm=110)
            # Use style-typical accepted chords so melody has material to respond to.
            chords = {
                "Pop": "C G Am F",
                "Jazz": "Dm7 G7 Cmaj7 A7",
                "Rock": "C Bb F C",
                "Bossa": "Cmaj7 Am7 Dm7 G9",
            }[genre]
            accept_full_progression(doc, str(sec["id"]), parse_chord_paste(chords), tiled=False)
            concepts = suggest_melody_concepts(doc, sec, "lyrical", "simple", limit=3)
            sigs[genre] = {events_signature(c["events"]) for c in concepts}
            self.assertEqual(len(sigs[genre]), 3, genre)
        self.assertNotEqual(sigs["Pop"], sigs["Jazz"])
        self.assertNotEqual(sigs["Pop"], sigs["Rock"])

    def test_tempo_energy_affects_melody_density(self) -> None:
        def _avg_dur(genre_bpm_energy):
            genre, bpm, energy, idea = genre_bpm_energy
            doc, sec = _doc(genre=genre, idea=idea, bpm=bpm, energy=energy)
            accept_full_progression(doc, str(sec["id"]), parse_chord_paste("C Am F G"), tiled=False)
            concepts = suggest_melody_concepts(doc, sec, "lyrical", "simple", limit=2)
            durs = [
                float(e.get("duration_beats") or 1.0)
                for c in concepts
                for e in c["events"]
                if not e.get("is_rest")
            ]
            return sum(durs) / max(1, len(durs)), len(durs)

        slow = _avg_dur(("Pop", 70, "Ballad — slow and intimate", "intimate love song"))
        fast = _avg_dur(("Pop", 150, "Driving — high energy", "driving upbeat song"))
        # Fast/high energy should tend toward shorter average durations or more events.
        self.assertTrue(fast[0] < slow[0] or fast[1] > slow[1], (slow, fast))

    def test_freeform_intent_preserved_chords_to_melody(self) -> None:
        idea = "I want it to start intimate and become much bigger in the chorus. Piano-driven story song."
        doc, sec = _doc(genre="Pop", idea=idea, refs="Billy Joel", bpm=96)
        profile = build_song_intent_profile(doc, sec)
        self.assertTrue(profile["flags"]["intimate"] or profile["flags"]["piano"] or profile["flags"]["build_chorus"])
        self.assertTrue(profile["reference_attrs"]["piano_driven"])
        accept_full_progression(doc, str(sec["id"]), parse_chord_paste("C Am F G"), tiled=False)
        concepts = suggest_melody_concepts(
            doc, sec, "emotional", "simple", limit=2, remember="the chorus lift", notes=idea
        )
        self.assertTrue(all(idea[:20] in str(c.get("notes_intent") or "") for c in concepts))

    def test_jewish_directions_differ(self) -> None:
        doc_pop, sec_pop = _doc(genre="Jewish", idea="contemporary Jewish pop camp song", bpm=110)
        doc_kl, sec_kl = _doc(genre="Jewish", idea="klezmer freylekh hora dance", bpm=120)
        pp = build_song_intent_profile(doc_pop, sec_pop)
        pk = build_song_intent_profile(doc_kl, sec_kl)
        self.assertEqual(pp["style_family"], "jewish_pop")
        self.assertEqual(pk["style_family"], "jewish_klezmer")
        pop_ideas = {_chord_sig(i) for i in suggest_progressions(doc_pop, sec_pop, "uplifting", limit=3)}
        kl_ideas = {_chord_sig(i) for i in suggest_progressions(doc_kl, sec_kl, "energetic", limit=3)}
        self.assertNotEqual(pop_ideas, kl_ideas)

    def test_reference_changes_profile_without_copying(self) -> None:
        doc_a, sec_a = _doc(genre="Pop", idea="story song", refs="Billy Joel", bpm=100)
        doc_b, sec_b = _doc(genre="Pop", idea="story song", refs="", bpm=100)
        pa = build_song_intent_profile(doc_a, sec_a)
        pb = build_song_intent_profile(doc_b, sec_b)
        self.assertTrue(pa["reference_attrs"]["piano_driven"])
        self.assertFalse(pb["reference_attrs"]["piano_driven"])
        # No hard-coded Billy Joel progression in recipes
        ideas = suggest_progressions(doc_a, sec_a, "stable", limit=3)
        joined = " ".join(str(i.get("line") or "") for i in ideas).lower()
        self.assertNotIn("just the way", joined)


if __name__ == "__main__":
    unittest.main()
