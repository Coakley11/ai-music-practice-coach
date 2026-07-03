"""Tests for harmonic rhythm / performance feel inference."""

from harmonic_rhythm_intelligence import (
    apply_harmonic_rhythm_intelligence,
    token_has_explicit_timing,
)


def test_explicit_split_bar_is_preserved():
    assert token_has_explicit_timing("Dm:2|Bb:2")
    assert token_has_explicit_timing("C:3.5|G:0.5p")
    assert token_has_explicit_timing("N.C.")
    assert token_has_explicit_timing("G.hit")
    assert not token_has_explicit_timing("Dm")


def test_explicit_manual_push_is_preserved():
    sections = {"Verse 1": ["C:3.5|G:0.5p", "Am", "F", "G"]}
    result = apply_harmonic_rhythm_intelligence(
        sections,
        groove_style="Pop groove",
        humanize_level="Strong",
    )
    assert result.sections["Verse 1"][0] == "C:3.5|G:0.5p"


def test_preserve_exact_timing_leaves_plain_bars():
    sections = {"Verse 1": ["Dm", "Bb", "F", "C"]}
    result = apply_harmonic_rhythm_intelligence(
        sections,
        groove_style="Pop groove",
        humanize_level="Strong",
        preserve_exact_timing=True,
    )
    assert result.sections == sections
    assert result.annotations == ()


def test_off_disables_inference():
    sections = {"Verse 1": ["Dm", "Bb", "F", "C"]}
    result = apply_harmonic_rhythm_intelligence(
        sections,
        groove_style="Pop groove",
        humanize_level="Off",
    )
    assert result.sections == sections
    assert result.annotations == ()


def test_nc_always_preserved():
    sections = {"Breakdown": ["N.C.", "N.C.", "G", "C"]}
    result = apply_harmonic_rhythm_intelligence(
        sections,
        groove_style="Funk groove",
        humanize_level="Strong",
        song_data={"title": "nc-test"},
    )
    assert result.sections["Breakdown"][0] == "N.C."
    assert result.sections["Breakdown"][1] == "N.C."


def test_same_root_consecutive_bars_not_split():
    sections = {"Verse 1": ["Am", "Am", "Am", "G"]}
    result = apply_harmonic_rhythm_intelligence(
        sections,
        groove_style="Pop groove",
        humanize_level="Strong",
        song_data={"title": "held-test"},
    )
    assert result.sections["Verse 1"][0] == "Am"
    assert result.sections["Verse 1"][1] == "Am"
    assert result.sections["Verse 1"][2] == "Am"


def test_written_split_honored():
    sections = {"Verse 1": ["Dm:2|Bb:2", "F:2|C:2"]}
    result = apply_harmonic_rhythm_intelligence(
        sections,
        groove_style="Funk groove",
        humanize_level="Strong",
    )
    assert result.sections == sections
    assert result.annotations == ()


def test_repeated_sections_share_inferred_timing():
    verse = ["Dm", "Bb", "F", "C"]
    sections = {"Verse 1": list(verse), "Verse 2": list(verse)}
    result = apply_harmonic_rhythm_intelligence(
        sections,
        groove_style="Pop groove",
        humanize_level="Strong",
        section_names=["Verse 1", "Verse 2"],
        song_data={"title": "repeat-verse-test", "genre": "Pop"},
    )
    v1 = result.sections["Verse 1"]
    v2 = result.sections["Verse 2"]
    assert v1 == v2


def test_lyric_heavy_verse_dampens_mid_phrase_pushes():
    sections = {"Verse 1": ["Dm", "Bb", "F", "C"]}
    heavy = apply_harmonic_rhythm_intelligence(
        sections,
        groove_style="Pop groove",
        humanize_level="Strong",
        song_data={"title": "lyric-heavy"},
        section_lyrics={
            "Verse 1": "line one\nline two\nline three\nline four\nline five\nline six"
        },
    )
    light = apply_harmonic_rhythm_intelligence(
        sections,
        groove_style="Pop groove",
        humanize_level="Strong",
        song_data={"title": "lyric-heavy"},
    )
    assert len(heavy.annotations) <= len(light.annotations)


def test_lyric_heavy_dampens_mid_phrase_more_than_instrumental():
    progression = ["C", "Am", "G", "F", "Em", "D", "G", "C"]
    heavy = apply_harmonic_rhythm_intelligence(
        {"Verse 1": list(progression)},
        groove_style="Pop groove",
        humanize_level="Strong",
        song_data={"title": "mid-phrase-vocal"},
        section_lyrics={"Verse 1": "\n".join(f"line {i}" for i in range(1, 9))},
    )
    sparse = apply_harmonic_rhythm_intelligence(
        {"Verse 1": list(progression)},
        groove_style="Pop groove",
        humanize_level="Strong",
        song_data={"title": "mid-phrase-vocal"},
    )
    heavy_mid = [a for a in heavy.annotations if a.bar > 1]
    sparse_mid = [a for a in sparse.annotations if a.bar > 1]
    assert len(heavy_mid) <= len(sparse_mid)


def test_broadway_favors_section_pickups():
    sections = {
        "Intro": ["C", "F", "G", "C"],
        "Verse 1": ["Am", "F", "C", "G"],
    }
    result = apply_harmonic_rhythm_intelligence(
        sections,
        groove_style="Ballad",
        humanize_level="Strong",
        section_names=["Intro", "Verse 1"],
        song_data={"title": "broadway-test", "genre": "Disney / Broadway"},
    )
    pickup_kinds = {a.kind for a in result.annotations}
    assert pickup_kinds.issubset({"section_pickup", "anticipation", "syncopated_change"})


def test_strong_pop_may_add_anticipation():
    sections = {"Verse 1": ["Dm", "Bb", "F", "C"], "Chorus": ["F", "C", "Dm", "Bb"]}
    result = apply_harmonic_rhythm_intelligence(
        sections,
        groove_style="Pop groove",
        humanize_level="Strong",
        section_names=["Verse 1", "Chorus"],
        song_data={"title": "pop-anticipation-test", "genre": "Pop"},
    )
    changed = [
        (orig, new)
        for sec, bars in sections.items()
        for orig, new in zip(bars, result.sections[sec])
        if orig != new
    ]
    assert changed or result.annotations
    for ann in result.annotations:
        assert "|" in ann.inferred_token
        assert ann.original_token != ann.inferred_token
        assert ann.push_confidence >= 0.0
        assert ann.section_confidence >= 0.0


def test_backing_track_still_generates_after_inference():
    from backing_audio import generate_backing_track

    sections = {"Verse 1": ["Dm", "Bb", "F", "C"]}
    result = apply_harmonic_rhythm_intelligence(
        sections,
        groove_style="Pop groove",
        humanize_level="Medium",
        song_data={"title": "wav-smoke"},
    )
    events = [
        {"chord": ch, "section": "Verse 1", "bar_in_section": i}
        for i, ch in enumerate(result.sections["Verse 1"])
    ]
    wav = generate_backing_track(
        events,
        bpm=100,
        loops=1,
        style="Pop groove",
        level="Intermediate",
        song_title="wav-smoke",
        time_signature="4/4",
    )
    assert isinstance(wav, (bytes, bytearray))
    assert len(wav) > 1000


def test_say_chart_push_timing_is_preserved_under_hri():
    from song_catalog.curated_songs import _say_chart_pack

    pack = _say_chart_pack()
    sections = pack["sections"]
    result = apply_harmonic_rhythm_intelligence(
        sections,
        groove_style="Ballad",
        humanize_level="Strong",
        song_data={"title": "Say", "artist": "John Mayer"},
    )
    assert result.sections["Verse 1"][0] == "G:3.5|C:0.5p"
    assert result.sections["Verse 1"][2] == "Em:3.5|D:0.5p"
    assert "0.5p" in result.sections["Bridge"][2]
    assert result.sections["Final Chorus"][0] == "Em:3.5|G:0.5p"
