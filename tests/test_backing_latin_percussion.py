"""Slice 3: the recorded Latin percussionist (VCSL, CC0) — what it plays per style, that it is off by default, and
where it sits in the band."""

from __future__ import annotations

import json

import numpy as np
import pytest

import backing_audio as ba
import backing_latin_grooves as lg
import backing_latin_percussion as lp

CHORDS = ["Dm7", "G7", "Cmaj7", "A7"] * 2


def _voices(hits, voice):
    return [h.beat for h in hits if h.voice == voice]


def test_off_by_default(monkeypatch):
    monkeypatch.delenv("MUSIC_LATIN_GROOVES", raising=False)
    assert not lp.enabled()
    assert not any(lp.plays(s) for s in (lg.SAMBA, lg.LATIN_JAZZ, "Bossa nova"))
    assert lp.renderer_tag() == "" and lp.replaced_kit_parts(lg.SAMBA) == ()


def test_ab_switch_turns_only_the_percussionist_off(monkeypatch):
    monkeypatch.setenv("MUSIC_LATIN_GROOVES", "1")
    monkeypatch.setenv("MUSIC_LATIN_PERCUSSION", "0")
    assert lg.engine_style_for("Latin") == lg.LATIN_JAZZ and not lp.enabled()


def test_pack_is_complete_and_cc0():
    manifest = json.loads((lp.PACK / "manifest.json").read_text(encoding="utf-8"))
    assert set(lp.LEVEL) <= set(manifest)
    for voice, layers in manifest.items():
        for names in layers:
            for name in names:
                assert (lp.PACK / name).is_file(), name
    assert "CC0 1.0 Universal" in (lp.PACK / "LICENSE").read_text(encoding="utf-8")


def test_latin_jazz_plays_the_son_clave_and_a_tumbao():
    for side in (0, 1):
        hits = lp.bar_hits(lg.LATIN_JAZZ, side)
        assert tuple(_voices(hits, "clave")) == lg.SON_CLAVE_2_3[side]
        # open tones on 4 (conga) and the "and" of 4 (tumba), the slap on 2
        assert _voices(hits, "conga_open") == [3.0] and _voices(hits, "tumba_open") == [3.5]
        slap = [h for h in hits if h.voice == "conga_muted" and h.beat == 1.0]
        assert slap and slap[0].velocity > 0.8
    light = lp.bar_hits(lg.LATIN_JAZZ, 0, intensity="Light")
    assert len(_voices(light, "conga_muted")) == 1  # the slap only, no heel-toe taps
    heavy = lp.bar_hits(lg.LATIN_JAZZ, 0, intensity="Heavy")
    assert _voices(heavy, "cowbell") == [0.0, 1.0, 2.0, 3.0]  # the bongo bell joins at Heavy


def test_samba_ganza_tamborim_and_agogo():
    hits = lp.bar_hits(lg.SAMBA, 0)
    shaker = [h for h in hits if h.voice.startswith("shaker")]
    assert len(shaker) == 16
    accents = [h.beat for h in shaker if h.velocity > 0.9]
    assert accents == [0.75, 1.75, 2.75, 3.75]  # the ganza's accent on the last sixteenth of each beat
    assert tuple(_voices(hits, "tamb")) == lg.PARTIDO_ALTO
    assert _voices(hits, "agogo_high") and _voices(hits, "agogo_low")
    light = lp.bar_hits(lg.SAMBA, 0, intensity="Light")
    assert not _voices(light, "agogo_high") and len([h for h in light if h.voice.startswith("shaker")]) == 8


def test_bossa_is_only_a_quiet_shaker_never_a_clave():
    hits = lp.bar_hits("Bossa nova", 0)
    assert {h.voice for h in hits} <= {"shaker_down", "shaker_up"}
    assert max(h.velocity for h in hits) < 0.4


def test_real_parts_replace_the_kits_stand_ins(monkeypatch):
    monkeypatch.setenv("MUSIC_LATIN_GROOVES", "1")
    assert lp.replaced_kit_parts(lg.SAMBA) == ("hat_beats", "cross_stick")
    assert lp.replaced_kit_parts(lg.LATIN_JAZZ) == ("cross_stick",)
    assert lp.replaced_kit_parts("Bossa nova") == ()


def test_switch_off_renders_exactly_as_without_the_module(monkeypatch):
    monkeypatch.delenv("MUSIC_LATIN_GROOVES", raising=False)
    calls = []
    monkeypatch.setattr(lp, "play_bar", lambda *a, **k: calls.append(1))
    a, _ = ba.synthesize_chords_to_numpy(CHORDS, style="Bossa nova", bpm=120, loops=1)
    assert not calls
    monkeypatch.setattr(lp, "plays", lambda style: False)
    b, _ = ba.synthesize_chords_to_numpy(CHORDS, style="Bossa nova", bpm=120, loops=1)
    assert np.array_equal(a, b)


@pytest.mark.parametrize(
    "style, lo, hi",
    [("Bossa nova", -26.0, -18.0), (lg.SAMBA, -13.0, -7.0), (lg.LATIN_JAZZ, -13.0, -7.0)],
)
def test_percussion_level_against_the_rhythm_layer(monkeypatch, style, lo, hi):
    """Bossa's shaker stays in the background; Samba's and Latin jazz's percussion is clearly part of the band."""
    monkeypatch.setenv("MUSIC_LATIN_GROOVES", "1")
    stem = {}
    real = lp.play_bar

    def spy(audio, sr, hits, place, **kw):
        if stem.get("buf") is None:
            stem["buf"] = np.zeros_like(audio)
        real(stem["buf"], sr, hits, place, **kw)
        real(audio, sr, hits, place, **kw)

    monkeypatch.setattr(lp, "play_bar", spy)
    ba.synthesize_chords_to_numpy(CHORDS, style=style, bpm=104 if style == lg.SAMBA else 120, loops=1)
    rms = float(np.sqrt(np.mean(np.square(stem["buf"].astype(np.float64)))))
    level = 20 * np.log10(rms / float(ba.LAST_MIX_STATS["rhythm_rms"]))
    assert lo <= level <= hi, level


def test_percussion_changes_the_take_and_its_identity(monkeypatch):
    monkeypatch.setenv("MUSIC_LATIN_GROOVES", "1")
    with_perc, _ = ba.synthesize_chords_to_numpy(CHORDS, style=lg.LATIN_JAZZ, bpm=120, loops=1)
    tag_on = ba.drum_renderer_tag()
    monkeypatch.setenv("MUSIC_LATIN_PERCUSSION", "0")
    without, _ = ba.synthesize_chords_to_numpy(CHORDS, style=lg.LATIN_JAZZ, bpm=120, loops=1)
    assert "+perc-" in tag_on and "+perc-" not in ba.drum_renderer_tag()
    n = min(len(with_perc), len(without))
    assert not np.allclose(with_perc[:n], without[:n])


# --- Phrasing with the song (Latin jazz congas) ------------------------------------------------------------


def _phrased(n, bars=8, seed=7, intensity="Medium"):
    return lp.bar_hits(lg.LATIN_JAZZ, n, intensity=intensity, bar_in_section=n % bars, section_bars=bars, seed=seed)


def test_without_section_information_the_bar_is_the_plain_pattern():
    assert lp.bar_hits(lg.LATIN_JAZZ, 3) == lp.bar_hits(lg.LATIN_JAZZ, 3, seed=99)


def test_the_clave_never_changes_for_a_fill_or_a_variation():
    for n in range(32):
        claves = [h.beat for h in _phrased(n) if h.voice == "clave"]
        assert claves == list(lg.SON_CLAVE_2_3[n % 2]), n


def test_a_section_ends_with_a_fill_and_the_next_starts_on_the_tumba():
    end = _phrased(7)
    opens = [(h.beat, h.voice) for h in end if h.voice in ("conga_open", "tumba_open")]
    assert (2.0, "conga_open") in opens and (3.25, "tumba_open") in opens and (3.5, "tumba_open") in opens
    assert not any(h.voice == "conga_muted" and h.beat > 1.0 for h in end)  # the fill replaces the heel-toe
    start = _phrased(8)
    assert any(h.beat == 0.0 and h.voice == "tumba_open" for h in start)
    assert not any(h.beat == 0.0 and h.voice == "tumba_open" for h in _phrased(0))  # not on the take's first beat


def test_the_tumbao_varies_like_a_player_not_a_loop():
    def shape(n, **kw):
        return tuple((h.beat, h.voice, h.velocity > 0.6) for h in _phrased(n, **kw) if h.voice != "clave")  # where the accents fall

    inner = [n for n in range(64) if n % 8 not in (0, 7)]
    assert len({shape(n) for n in inner}) >= 3
    assert shape(5) == shape(5)  # the same take plays the same way
    assert [shape(n) for n in inner] != [shape(n, seed=8) for n in inner]  # another take differently
    varied = {k: sum(any(h.beat == 1.5 and h.voice == "tumba_open" for h in _phrased(n, intensity=k)) for n in inner)
              for k in ("Light", "Heavy")}
    assert varied["Light"] < varied["Heavy"]


def test_velocities_move_a_little_but_keep_the_slap_and_open_tones_strong():
    for n in range(1, 7):
        for h in _phrased(n):
            if h.voice in ("conga_open", "tumba_open") and h.beat in (3.0, 3.5):
                assert h.velocity > 0.7
