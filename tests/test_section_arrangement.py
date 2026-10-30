"""Section-aware backing: sections differ by texture, not just loudness.

Measured before (Attention, Funk, 100 BPM): every section played the same kick /
snare / 16th hats / bass line / stabs and differed only in level (8.5 dB from
intro to final chorus). Unlabelled practice loops and unknown labels render
sample-identical to before (checked against dev 95cdedb8 with the render-hash
harness); these tests pin the classifier, the form plan and the textures.
"""
from __future__ import annotations

import statistics

import numpy as np
import pytest

import backing_audio as ba
import backing_section_arrangement as sa
from backing_musical_profile import resolve_backing_musical_profile


@pytest.mark.parametrize(
    "label, role",
    [
        ("Intro", sa.INTRO), ("Verse 1", sa.VERSE), ("Verse 3A", sa.VERSE), ("Pre-Chorus 2", sa.PRE),
        ("Chorus", sa.CHORUS), ("Chorus 1", sa.CHORUS), ("Final Chorus", sa.CHORUS),
        ("Final Chorus Repeat", sa.CHORUS), ("Final Chorus (Key Change)", sa.CHORUS),
        ("Refrain 1", sa.REFRAIN), ("Post-Chorus", sa.REFRAIN), ("Bridge", sa.BRIDGE),
        ("Middle Eight", sa.BRIDGE), ("Interlude 2", sa.INTERLUDE), ("Instrumental", sa.INTERLUDE),
        ("Solo", sa.SOLO), ("Guitar Solo", sa.SOLO), ("Guitar Break", sa.SOLO), ("Breakdown", sa.BREAKDOWN),
        ("Vocal Break", sa.BREAKDOWN), ("Outro", sa.OUTRO), ("Outro Sax", sa.OUTRO), ("Ending", sa.OUTRO),
        ("Sax Intro", sa.INTRO), ("Intro (Organ)", sa.INTRO), ("Intro Riff Return", sa.INTERLUDE),
        # Not a chorus just because the word appears.
        ("Chorus Prep", sa.PRE), ("Chorus Prep / Bridge", sa.PRE), ("Pre-Final Chorus", sa.PRE),
        ("Verse Build", sa.PRE),
        # Compound labels take the first part that has a role.
        ("Bridge / Oh Section", sa.BRIDGE), ("Final Chorus / Outro Build", sa.CHORUS),
        ("Intro / Groove", sa.INTRO),
        # Unknown / form letters stay neutral: the groove exactly as before.
        ("Practice Loop", sa.NEUTRAL), ("A Section", sa.NEUTRAL), ("B", sa.NEUTRAL), ("Key Change", sa.NEUTRAL),
        ("Turnaround", sa.NEUTRAL), ("Head", sa.NEUTRAL), ("", sa.NEUTRAL),
    ],
)
def test_section_role(label, role) -> None:
    assert sa.section_role(label) == role


def _events(form):
    out = []
    for name, chords in form:
        out += [{"chord": c, "section": name, "bar_in_section": i, "section_bars": len(chords)} for i, c in enumerate(chords)]
    return out


FORM = [
    ("Intro", ["Em7", "A7", "Em7", "A7"]),
    ("Verse 1", ["Em7", "A7", "Dm7", "G7"]),
    ("Pre-Chorus", ["Cmaj7", "Cmaj7", "D7", "D7"]),
    ("Chorus 1", ["G", "Em7", "Cmaj7", "D7"]),
    ("Verse 2", ["Em7", "A7", "Dm7", "G7"]),
    ("Bridge", ["Am7", "D7", "Bm7", "E7"]),
    ("Final Chorus", ["G", "Em7", "Cmaj7", "D7"]),
    ("Outro", ["G", "Em7", "Cmaj7", "G"]),
]


def test_plan_knows_the_form_and_the_loops() -> None:
    ev = _events(FORM)
    plan = sa.build_plan(ev * 2, len(ev))
    assert len(plan) == 64
    v2 = plan[16]
    assert (v2.role, v2.role_pass, v2.role_blocks, v2.bar, v2.bars) == (sa.VERSE, 2, 2, 0, 4)
    final = plan[24]
    assert final.role == sa.CHORUS and final.role_pass == final.role_blocks == 2
    assert plan[31].block == plan[31].blocks - 1 and plan[31].loop == 0
    assert plan[63].loop == 1 and plan[63].loops == 2


def test_texture_choices() -> None:
    ev = _events(FORM)
    plan = sa.build_plan(ev * 2, len(ev))
    for style in ("Pop groove", "Rock groove", "Funk groove"):
        assert sa.bar_texture(style, plan[0]).drums == "hats"          # intro builds in on the first pass
        assert sa.bar_texture(style, plan[3]).drums == "light"
        assert sa.bar_texture(style, plan[32]).drums != "hats"         # ...not again on the second pass
        assert sa.bar_texture(style, plan[12]).comp_extra_voice        # chorus: fuller chords
        assert sa.bar_texture(style, plan[24]).pad                     # final chorus: one more layer
        assert sa.bar_texture(style, plan[63]).drums == "ending"       # the last bar of the song
        assert sa.bar_texture(style, plan[31]).drums != "ending"       # loop 1 runs on into loop 2
    assert sa.bar_texture("Pop groove", sa.build_plan([{"chord": "C", "section": "Practice Loop"}], 1)[0]) is None
    # Jazz / Bossa: light touches only -- no stripped-down drums or chorus layers.
    for style in ("Jazz swing", "Bossa nova"):
        for i in (12, 24):
            t = sa.bar_texture(style, plan[i])
            assert not t.comp_extra_voice and not t.pad and t.drums == "groove"


def _render(style, events, *, textures=True, **kw):
    log = []
    orig = (ba._add_tone, ba._add_comp_chord, ba._add_kick, ba._add_snare, ba._add_noise_hit)

    def tone(audio, sr, t, dur, midi, vol, wave="sine"):
        if str(wave).startswith("bass"):
            log.append(("bass", t, dur, midi, vol))
        return orig[0](audio, sr, t, dur, midi, vol, wave)

    def comp(bus, sr, t, dur, voicing, vol, wave, **k):
        log.append(("comp", t, dur, len(voicing or ()), vol))
        return orig[1](bus, sr, t, dur, voicing, vol, wave, **k)

    def kick(audio, sr, t, vol, **k):
        log.append(("kick", t, 0.0, 0, vol))
        return orig[2](audio, sr, t, vol, **k)

    def snare(audio, sr, t, vol, **k):
        log.append(("snare", t, 0.0, 0, vol))
        return orig[3](audio, sr, t, vol, **k)

    def noise(audio, sr, t, dur, vol, **k):
        log.append(("noise", t, dur, 0, vol))
        return orig[4](audio, sr, t, dur, vol, **k)

    ba._add_tone, ba._add_comp_chord, ba._add_kick, ba._add_snare, ba._add_noise_hit = tone, comp, kick, snare, noise
    orig_tex = sa.bar_texture
    if not textures:
        sa.bar_texture = lambda style, place: None  # the arrangement before section textures
    try:
        prof = resolve_backing_musical_profile(style=style, tempo=100, level="Intermediate")
        audio, sr = ba.synthesize_chords_to_numpy(events, bpm=100, sr=22050, style=style, musical_profile=prof, **kw)
    finally:
        ba._add_tone, ba._add_comp_chord, ba._add_kick, ba._add_snare, ba._add_noise_hit = orig
        sa.bar_texture = orig_tex
    return log, audio, sr


def _in(log, kind, bars, bar_sec=2.4):
    lo, hi = bars[0] * bar_sec - 0.02, bars[1] * bar_sec - 0.02
    return [e for e in log if e[0] == kind and lo <= e[1] < hi]


def _rms_db(audio, sr, bars, bar_sec=2.4):
    seg = audio[int(bars[0] * bar_sec * sr): int(bars[1] * bar_sec * sr)].astype(np.float64)
    return 20 * np.log10(float(np.sqrt(np.mean(seg ** 2))) + 1e-9)


@pytest.mark.parametrize("style", ["Pop groove", "Rock groove", "Funk groove"])
def test_sections_are_audibly_different(style) -> None:
    log, audio, sr = _render(style, _events(FORM))
    intro, verse, chorus, bridge, final, outro = (0, 4), (4, 8), (12, 16), (20, 24), (24, 28), (28, 32)
    drums = lambda b: len(_in(log, "kick", b)) + len(_in(log, "snare", b))  # noqa: E731
    # Intro: sparser drums, held chords; it builds in (no kick / snare in its first half).
    assert drums(intro) < drums(verse)
    assert drums((0, 2)) == 0
    assert statistics.median(e[2] for e in _in(log, "comp", (0, 2))) > 1.5   # held chords, not stabs
    # Chorus: fuller chords than the verse; the final chorus adds a held layer.
    assert max(e[3] for e in _in(log, "comp", chorus)) > max(e[3] for e in _in(log, "comp", verse))
    assert len(_in(log, "comp", final)) > len(_in(log, "comp", chorus))
    # Bridge: a different, thinner texture from the verse (fewer kicks or half the hats, ghosts out).
    kit = lambda b: drums(b) + len(_in(log, "noise", b))  # noqa: E731
    assert kit(bridge) < kit(verse)
    # Outro: thins out and ends on one hit -- no snare in the last bar.
    assert not _in(log, "snare", (31, 32)) and len(_in(log, "kick", (31, 32))) == 1
    # Energy: the chorus is louder than the intro, but by a few dB, not 8-9.
    gap = _rms_db(audio, sr, chorus) - _rms_db(audio, sr, intro)
    assert 2.0 <= gap <= 7.0, gap
    assert _rms_db(audio, sr, intro) <= _rms_db(audio, sr, verse) + 0.5
    assert float(np.max(np.abs(audio))) <= 1.0


def test_tempo_and_bar_count_never_change() -> None:
    plain = [c for _n, chords in FORM for c in chords]
    _l1, a1, _s = _render("Pop groove", _events(FORM))
    _l2, a2, _s = _render("Pop groove", plain)
    assert a1.shape == a2.shape


def test_bass_and_comp_stay_on_the_chord() -> None:
    log, _a, _sr = _render("Rock groove", _events(FORM))
    chords = [c for _n, cs in FORM for c in cs]
    for kind, t, _d, midi, _v in (e for e in log if e[0] == "bass"):
        bar = int((t + 0.03) // 2.4)
        if bar >= len(chords) or (t + 0.03) % 2.4 >= 1.8:
            continue  # beat 4: walk-ups into the next bar
        tones = {n % 12 for n in ba.chord_notes(chords[bar])}
        assert midi % 12 in tones, (bar, chords[bar], midi)


def test_funk_pocket_kept_in_verse_and_chorus() -> None:
    """Verse and chorus play the Funk bass line note for note as before (only the level moves)."""
    form = [("Verse 1", ["Em7", "A7", "Em7", "A7"]), ("Chorus", ["Em7", "A7", "Em7", "A7"])]
    new, _a, _s = _render("Funk groove", _events(form))
    old, _a, _s = _render("Funk groove", _events(form), textures=False)
    notes = lambda log: [(round(e[1], 4), round(e[2], 4), e[3]) for e in _in(log, "bass", (0, 8))]  # noqa: E731
    assert notes(new) == notes(old)


def test_jazz_and_bossa_keep_their_pocket() -> None:
    form = [("Verse", ["Dm7", "G7", "Cmaj7", "A7"]), ("Chorus", ["Dm7", "G7", "Cmaj7", "A7"])]
    for style in ("Jazz swing", "Bossa nova"):
        log, audio, sr = _render(style, _events(form))
        old, _a, _s = _render(style, _events(form), textures=False)
        rhythm = lambda lg: [(round(e[1], 4), e[3]) for e in lg if e[0] in ("bass", "kick", "snare")]  # noqa: E731
        assert rhythm(log) == rhythm(old)  # same bass line and kit, bar for bar
        assert abs(_rms_db(audio, sr, (4, 8)) - _rms_db(audio, sr, (0, 4))) < 3.5


def test_add_top_voice() -> None:
    assert sa.add_top_voice([60, 64, 67]) == [60, 64, 67, 72]
    assert sa.add_top_voice([60, 64, 67, 72]) == [60, 64, 67, 72, 76]
    assert sa.add_top_voice([]) == []
