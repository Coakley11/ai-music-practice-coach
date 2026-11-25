"""Backing Engine 2.0: a generated jam's ensemble, mood, intensity and difficulty change how the band plays.

The plan is opt-in (generated jams only); song sources render exactly as before - proven separately by
render hashes against origin/dev.
"""

from __future__ import annotations

import numpy as np
import pytest

import backing_audio as ba
import backing_pianist as pn
from backing_drum_kit import BarContext, bar_extras
from backing_performance_plan import ENSEMBLES, resolve_performance_plan
from backing_section_arrangement import SectionTexture

PROG = ["Dm7", "G7", "Cmaj7", "A7", "Dm7", "G7", "Em7", "A7"]


def _plan(**kw):
    kw.setdefault("style", "Jazz swing")
    kw.setdefault("guitar_available", True)
    return resolve_performance_plan(**kw)


# --- who plays ---------------------------------------------------------------------------------------------


def test_every_generator_ensemble_has_a_real_roster():
    for name in ("Jazz trio", "Jazz quartet", "Neo-soul band", "Rock trio", "Latin quartet", "Lo-fi duo"):
        assert name in ENSEMBLES
    assert _plan(ensemble="Jazz trio").roles == ("keys", "bass", "drums")
    assert _plan(ensemble="Lo-fi duo").roles == ("keys", "drums")
    rock = _plan(style="Rock groove", ensemble="Rock trio")
    assert rock.roles == ("guitar", "bass", "drums") and not rock.plays("keys")


def test_members_without_a_renderer_are_reported_never_faked():
    quartet = _plan(ensemble="Jazz quartet")
    assert quartet.unavailable == ("horns",)
    assert "horns" not in quartet.roles
    assert _plan(ensemble="Latin quartet", style="Bossa nova").unavailable == ("percussion",)


def test_a_rock_trio_without_a_guitar_keeps_a_harmony_player_and_says_so():
    plan = resolve_performance_plan(style="Rock groove", ensemble="Rock trio", guitar_available=False)
    assert plan.plays("keys") and not plan.plays("guitar")
    assert "guitar" in plan.unavailable and plan.fallbacks


def test_style_jam_without_an_ensemble_is_the_style_s_own_band():
    assert _plan(style="Bossa nova").roles == ("keys", "bass", "drums")
    assert _plan(style="Rock groove").roles == ("keys", "guitar", "bass", "drums")
    assert resolve_performance_plan(style="Rock groove", guitar_available=False).roles == ("keys", "bass", "drums")


# --- mood and intensity are separate controls ----------------------------------------------------------------


def test_mood_shapes_touch_and_articulation_intensity_shapes_density():
    mellow_light = _plan(mood="Mellow", intensity="Light")
    mellow_heavy = _plan(mood="Mellow", intensity="Heavy")
    energetic_light = _plan(mood="Energetic", intensity="Light")
    energetic_heavy = _plan(mood="Energetic", intensity="Heavy")
    # Same mood, different intensity: same touch, different amount of playing.
    assert mellow_light.keys.velocity == mellow_heavy.keys.velocity
    assert mellow_light.keys.density < 1.0 < mellow_heavy.keys.density
    # Same intensity, different mood: same amount, different touch and articulation.
    assert mellow_light.keys.density == energetic_light.keys.density
    assert mellow_light.keys.velocity < energetic_light.keys.velocity
    assert mellow_light.keys.length > energetic_light.keys.length
    tags = {p.tag() for p in (mellow_light, mellow_heavy, energetic_light, energetic_heavy)}
    assert len(tags) == 4


def test_moods_are_musical_characters_not_volumes():
    bright, dark, dreamy, gritty = (_plan(mood=m) for m in ("Bright", "Dark", "Dreamy", "Gritty"))
    assert bright.keys.register > 0 > dark.keys.register
    assert dreamy.keys.length > 1.5 and dreamy.keys.roll > 0 and dreamy.drums.fills < 0.5
    assert gritty.keys.velocity > 1.0 and gritty.drums.velocity > 1.0 and gritty.keys.length < 1.0


def test_difficulty_decides_harmonic_colour_last():
    assert _plan(mood="Bright", level="Beginner").keys.colour == "plain"
    assert _plan(mood="Gritty", level="Advanced").keys.colour == "rich"
    assert _plan(level="Advanced").keys.push > _plan(level="Beginner").keys.push


# --- the texture every player reads --------------------------------------------------------------------------


def test_light_thins_the_whole_band_and_jazz_goes_to_two_feel():
    tex = _plan(intensity="Light").texture(None, "verse")
    assert tex.drums == "light" and tex.hats == "lighter" and not tex.ghosts
    assert tex.comp == "sparse" and tex.bass == "half"


def test_heavy_fills_out_without_doubling_a_ride_or_bossa_pattern():
    rock = _plan(style="Rock groove", mood="Energetic", intensity="Heavy").texture(None, "chorus")
    assert rock.hats == "denser" and rock.comp == "full" and rock.open_hat_and4
    jazz = _plan(style="Jazz swing", intensity="Heavy").texture(None, "chorus")
    assert jazz.hats == "groove" and jazz.comp == "full"
    bossa = _plan(style="Bossa nova", intensity="Heavy").texture(None, "verse")
    assert bossa.hats == "groove"


def test_the_song_s_own_section_decisions_survive():
    intro = SectionTexture("intro", drums="hats", comp="sustain", bass="roots")
    light = _plan(style="Pop groove", intensity="Light").texture(intro, "intro")
    assert light.drums == "hats" and light.comp == "sustain" and light.bass == "roots"
    ending = SectionTexture("outro", drums="ending", comp="sustain", crash=True)
    assert _plan(intensity="Heavy").texture(ending, "outro") is ending
    assert _plan(intensity="Medium").texture(None, "verse") is None


# --- the players --------------------------------------------------------------------------------------------


def _pianist_bars(plan, style="Jazz swing", bars=32):
    p = pn.Pianist(style, "jam-test", level=plan.level, chord_notes=ba.chord_notes, bass_note=ba.bass_note,
                   performance=plan.keys)
    hits = []
    for i in range(bars):
        chord = PROG[i % len(PROG)]
        hits += p.bar([(0.0, 4.0, chord)], PROG[(i + 1) % len(PROG)], role="verse", quiet=False, bar_in_section=i % 8,
                      section_bars=8, section_end=i % 8 == 7, bar_index=i, pulses_per_bar=4)
    return p, hits


@pytest.mark.parametrize("style", ["Jazz swing", "Bossa nova", "Pop groove", "Funk groove"])
def test_the_pianist_plays_less_when_light_and_more_when_heavy(style):
    _, light = _pianist_bars(_plan(style=style, intensity="Light"), style)
    _, medium = _pianist_bars(_plan(style=style, intensity="Medium"), style)
    _, heavy = _pianist_bars(_plan(style=style, intensity="Heavy"), style)
    notes = lambda hs: sum(len(h.notes) for h in hs)  # noqa: E731
    assert notes(light) < notes(medium) < notes(heavy)
    assert notes(light) <= 0.85 * notes(medium)


def test_the_pianist_s_touch_and_articulation_follow_the_mood():
    mellow, mh = _pianist_bars(_plan(mood="Mellow"))
    energetic, eh = _pianist_bars(_plan(mood="Energetic"))
    assert mellow.hands.velocity < energetic.hands.velocity
    assert np.mean([h.beats for h in mh]) > np.mean([h.beats for h in eh])


def test_dark_and_bright_move_the_pianist_on_the_keyboard():
    _, dark = _pianist_bars(_plan(mood="Dark"))
    _, bright = _pianist_bars(_plan(mood="Bright"))
    top = lambda hs: np.mean([max(h.notes) for h in hs if h.notes])  # noqa: E731
    assert top(dark) + 4 < top(bright)


def test_without_a_plan_the_pianist_is_unchanged():
    a = pn.Pianist("Jazz swing", "s", level="Intermediate", chord_notes=ba.chord_notes, bass_note=ba.bass_note)
    b = pn.Pianist("Jazz swing", "s", level="Intermediate", chord_notes=ba.chord_notes, bass_note=ba.bass_note, performance=None)
    assert a.hands == b.hands == pn.HANDS["Jazz swing"]


def test_a_drummer_asked_for_space_fills_less():
    def fills(rate):
        n = 0
        for bar in range(400):
            ctx = BarContext(style="Rock groove", bar_in_section=bar % 8, role="verse", next_role="chorus",
                             ends_section=bar % 8 == 7, pulses_per_bar=4.0, song_seed=7, bar_index=bar, fill_rate=rate)
            n += len(bar_extras(ctx))
        return n

    assert fills(0.3) < fills(1.0) < fills(1.6)


def test_ensemble_masks_reach_the_mix():
    rock = resolve_performance_plan(style="Rock groove", ensemble="Rock trio", guitar_available=False)
    assert rock.plays("keys")  # fallback when the guitar renderer is off
    duo = _plan(style="Ballad", ensemble="Lo-fi duo")
    audio, _sr = ba.synthesize_chords_to_numpy(PROG[:4], bpm=90, style="Ballad", performance=duo, layers=["rhythm"])
    with_bass, _ = ba.synthesize_chords_to_numpy(PROG[:4], bpm=90, style="Ballad", layers=["rhythm"])
    # The duo's rhythm layer is the beat alone: much less low end than drums + bass.
    def low(x):
        spec = np.abs(np.fft.rfft(x))
        f = np.fft.rfftfreq(len(x), 1 / 44100)
        return spec[(f > 30) & (f < 200)].sum() / (spec.sum() + 1e-9)

    assert low(audio) < 0.6 * low(with_bass)


def test_mellow_heavy_is_fuller_and_warm_energetic_light_is_lively_and_sparse():
    mellow_heavy = _plan(style="Pop groove", mood="Mellow", intensity="Heavy").texture(None, "chorus")
    assert mellow_heavy.comp == "full" and mellow_heavy.comp_extra_voice  # a fuller band
    assert mellow_heavy.hats == "groove" and not mellow_heavy.open_hat_and4  # not busier on top
    energetic_light = _plan(style="Pop groove", mood="Energetic", intensity="Light").texture(None, "verse")
    mellow_light = _plan(style="Pop groove", mood="Mellow", intensity="Light").texture(None, "verse")
    assert energetic_light.drums == mellow_light.drums == "light" and energetic_light.comp == "sparse"
    assert energetic_light.hats == "groove" and mellow_light.hats == "lighter"  # the motion stays


def test_energetic_plays_with_more_rhythmic_life_than_mellow_at_the_same_intensity():
    _, mellow = _pianist_bars(_plan(mood="Mellow", intensity="Light"))
    _, energetic = _pianist_bars(_plan(mood="Energetic", intensity="Light"))
    off_beat = lambda hs: sum(1 for h in hs if h.beat % 1.0)  # noqa: E731
    assert off_beat(energetic) > off_beat(mellow)


def test_advanced_and_beginner_accompany_differently():
    _, beginner = _pianist_bars(_plan(level="Beginner", ensemble="Jazz trio"), bars=16)
    _, inter = _pianist_bars(_plan(level="Intermediate", ensemble="Jazz trio"), bars=16)
    _, advanced = _pianist_bars(_plan(level="Advanced", ensemble="Jazz trio"), bars=16)
    sig = lambda hs: [(h.beat, h.notes) for h in hs]  # noqa: E731
    assert sig(beginner) != sig(inter) != sig(advanced)
    assert _plan(level="Beginner").texture(None, "verse").bass == "half"  # a clear two-feel
    assert _plan(level="Advanced").texture(None, "verse") is None  # the walking line stays


def test_a_duo_without_a_bass_player_keeps_its_keys_in_front():
    duo = _plan(style="Ballad", ensemble="Lo-fi duo")
    ba.synthesize_chords_to_numpy(PROG[:4], bpm=90, style="Ballad", performance=duo)
    stats = dict(ba.LAST_MIX_STATS)
    assert stats["keys_rms"] > stats["rhythm_rms"]
