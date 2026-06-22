"""Pop catalog extensions — Marry You, Man in the Mirror, Heal the World (A), You Belong With Me."""

from __future__ import annotations

from typing import Any


def _hold(chord: str, measures: int) -> list[str]:
    return [chord] * max(1, int(measures))


def _seq(chords: list[tuple[str, int]]) -> list[str]:
    out: list[str] = []
    for chord, measures in chords:
        out.extend(_hold(chord, measures))
    return out


def _marry_you_progression() -> list[str]:
    return _seq(
        [
            ("F", 2),
            ("F", 2),
            ("Gm", 2),
            ("Gm", 2),
            ("Bb", 2),
            ("Bb", 2),
            ("F", 2),
            ("F", 2),
        ]
    )


def _marry_you_chart_pack() -> dict[str, Any]:
    prog = _marry_you_progression()
    section_names = [
        "Intro",
        "Chorus 1",
        "Verse 1",
        "Bridge 1",
        "Chorus 2",
        "Verse 2",
        "Bridge 2",
        "Chorus 3",
        "Middle 8",
        "Chorus 4",
    ]
    sections = {name: list(prog) for name in section_names}
    scale_hints = {
        "F": ["F major", "F major pentatonic"],
        "Gm": ["G Dorian", "G minor pentatonic"],
        "Bb": ["Bb Mixolydian", "Bb major pentatonic"],
    }
    return {
        "key": "F",
        "sections": sections,
        "chart_versions": {
            "Beginner": sections,
            "Intermediate": sections,
            "Advanced": sections,
        },
        "chart_status": "practice_level_verified",
        "section_order": section_names,
        "composer": "Bruno Mars",
        "guitar_tabs": {
            "F": "133211",
            "Gm": "355333",
            "Bb": "x13331",
        },
        "extensions": {
            "default_bpm": 144,
            "default_groove": "Pop",
            "time_signature": "4/4",
            "arrangement_notes": "Doo-wop pop — each chord cell = 2 measures (16 bars per section).",
        },
        "scale_suggestions": scale_hints,
        "backing_character": "pop_doo_wop",
    }


def _man_in_the_mirror_intro_verse() -> list[str]:
    return _seq(
        [
            ("G", 1),
            ("D/F#", 1),
            ("Em7", 1),
            ("D/F#", 1),
            ("Csus2", 2),
            ("Csus2", 2),
        ]
    )


def _man_in_the_mirror_pre_chorus() -> list[str]:
    return _seq(
        [
            ("Am7", 2),
            ("Dsus4/B", 2),
            ("Csus2", 2),
            ("Dsus4/B", 2),
            ("Am7", 2),
            ("Dsus4/B", 2),
            ("Csus2", 2),
            ("C/D", 2),
        ]
    )


def _man_in_the_mirror_chorus() -> list[str]:
    return _seq(
        [
            ("G", 1),
            ("Dsus4/B", 1),
            ("Csus2", 1),
            ("C/D", 1),
            ("G", 1),
            ("Dsus4/B", 1),
            ("C", 1),
            ("C#dim", 1),
            ("D4", 2),
            ("D4", 2),
        ]
    )


def _man_in_the_mirror_chart_pack() -> dict[str, Any]:
    iv = _man_in_the_mirror_intro_verse()
    pc = _man_in_the_mirror_pre_chorus()
    ch = _man_in_the_mirror_chorus()
    sections = {
        "Intro": list(iv),
        "Verse 1": list(iv),
        "Pre-Chorus 1": list(pc),
        "Chorus 1": list(ch),
        "Verse 2": list(iv),
        "Pre-Chorus 2": list(pc),
        "Chorus 2": list(ch),
        "Final Chorus": list(ch),
    }
    return {
        "key": "G",
        "sections": sections,
        "chart_versions": {
            "Beginner": sections,
            "Intermediate": sections,
            "Advanced": sections,
        },
        "chart_status": "practice_level_verified",
        "section_order": list(sections.keys()),
        "composer": "Michael Jackson",
        "guitar_tabs": {
            "G": "320003",
            "D/F#": "2x0232",
            "Em7": "022030",
            "Csus2": "x30010",
            "Am7": "x02010",
            "Dsus4/B": "x20230",
            "C/D": "xx0010",
            "C": "x32010",
            "C#dim": "x4202x",
            "D4": "xx0230",
        },
        "extensions": {
            "default_bpm": 100,
            "default_groove": "Gospel Pop",
            "time_signature": "4/4",
            "arrangement_notes": "Gospel-pop soul ballad — one list item = one measure.",
        },
        "backing_character": "gospel_pop",
    }


def _heal_the_world_a_major_chart_pack() -> dict[str, Any]:
    intro = _seq([("A", 1), ("Bm7", 1), ("C#m7", 1), ("Bm7", 1)])
    verse = _seq([("A", 1), ("Bm7", 1), ("C#m7", 1), ("D/E", 1)]) * 3
    pre_chorus = _seq(
        [
            ("Bm7", 1),
            ("C#m7", 1),
            ("D", 1),
            ("C#m7", 1),
            ("Bm7", 2),
            ("D/E", 2),
        ]
    )
    chorus = _seq(
        [
            ("A", 2),
            ("Bm7", 2),
            ("D/E", 2),
            ("A|A|A|E/G#", 1),
            ("F#m7", 1),
            ("C#m7", 1),
            ("D", 1),
            ("C#m7", 1),
            ("Bm7", 2),
            ("D/E", 2),
        ]
    )
    bridge = _seq(
        [
            ("G", 2),
            ("A", 2),
            ("G", 2),
            ("A", 2),
            ("F#m7", 1),
            ("C#m7", 1),
            ("D", 1),
            ("C#m7", 1),
            ("Bm7", 2),
            ("D/E", 2),
        ]
    )
    mod1 = _seq(
        [
            ("B", 1),
            ("C#m7", 1),
            ("F#", 1),
            ("B", 1),
            ("F#/A#", 1),
            ("G#m7", 1),
            ("D#m7", 1),
            ("E", 1),
            ("D#m7", 1),
            ("C#m7", 1),
            ("F#", 1),
            ("B", 1),
        ]
    )
    mod2 = _seq(
        [
            ("C#", 1),
            ("D#m7", 1),
            ("G#", 1),
            ("C#", 1),
            ("G#/C", 1),
            ("A#m7", 1),
            ("Fm7", 1),
            ("F#", 1),
            ("Fm7", 1),
            ("D#m7", 1),
            ("G#", 1),
            ("C#", 1),
            ("G#/C", 1),
        ]
    )
    sections = {
        "Intro": list(intro),
        "Verse 1": list(verse),
        "Pre-Chorus 1": list(pre_chorus),
        "Chorus 1": list(chorus),
        "Verse 2": list(verse),
        "Pre-Chorus 2": list(pre_chorus),
        "Chorus 2": list(chorus),
        "Bridge": list(bridge),
        "Chorus 3": list(chorus),
        "Modulation 1": list(mod1),
        "Modulation 2": list(mod2),
        "Final Chorus": list(chorus),
    }
    return {
        "key": "A",
        "sections": sections,
        "chart_versions": {
            "Beginner": sections,
            "Intermediate": sections,
            "Advanced": sections,
        },
        "chart_status": "practice_level_verified",
        "section_order": list(sections.keys()),
        "composer": "Michael Jackson",
        "guitar_tabs": {
            "A": "x02220",
            "Bm7": "x24202",
            "C#m7": "x46454",
            "D/E": "002220",
            "D": "xx0232",
            "E/G#": "476454",
            "F#m7": "242222",
            "G": "320003",
            "B": "x24442",
            "F#": "244322",
            "F#/A#": "x476xx",
            "G#m7": "464444",
            "D#m7": "x68676",
            "E": "022100",
            "C#": "x46664",
            "G#": "466544",
            "G#/C": "x31144",
            "A#m7": "x13121",
            "Fm7": "131111",
        },
        "extensions": {
            "default_bpm": 80,
            "default_groove": "Ballad",
            "time_signature": "4/4",
            "arrangement_notes": "Inspirational A-major ballad with modulations to B and C#.",
        },
        "backing_character": "piano_vocal_ballad",
    }


def _you_belong_with_me_block() -> list[str]:
    return _seq([("F#", 4), ("C#", 4), ("D#m", 4), ("B", 4)])


def _you_belong_with_me_chart_pack() -> dict[str, Any]:
    block = _you_belong_with_me_block()
    intro = _hold("F#", 8)
    outro = _seq([("B", 4), ("F#", 4), ("C#", 4), ("D#m", 4), ("B", 4), ("F#", 4)])
    sections = {
        "Intro": list(intro),
        "Verse 1": list(block),
        "Pre-Chorus 1": list(block),
        "Chorus 1": list(block),
        "Verse 2": list(block),
        "Pre-Chorus 2": list(block),
        "Chorus 2": list(block),
        "Link": list(block),
        "Bridge": list(block) + list(block),
        "Final Chorus": list(block),
        "Outro": list(outro),
    }
    return {
        "key": "F#",
        "sections": sections,
        "chart_versions": {
            "Beginner": sections,
            "Intermediate": sections,
            "Advanced": sections,
        },
        "chart_status": "practice_level_verified",
        "section_order": list(sections.keys()),
        "composer": "Taylor Swift",
        "guitar_tabs": {
            "F#": "244322",
            "C#": "x46664",
            "D#m": "x68876",
            "B": "x24442",
        },
        "extensions": {
            "default_bpm": 130,
            "default_groove": "Country Pop",
            "time_signature": "4/4",
            "arrangement_notes": "Country-pop — practice key initializes to F#; each chord = 4 measures.",
        },
        "backing_character": "country_pop",
    }


def pop_extension_chart_overrides() -> dict[tuple[str, str], dict[str, Any]]:
    return {
        ("Marry You", "Bruno Mars"): _marry_you_chart_pack(),
        ("Man in the Mirror", "Michael Jackson"): _man_in_the_mirror_chart_pack(),
        ("Heal The World", "Michael Jackson"): _heal_the_world_a_major_chart_pack(),
        ("You Belong With Me", "Taylor Swift"): _you_belong_with_me_chart_pack(),
    }
