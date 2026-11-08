"""The pianist: off by default, right notes, real variety, genre vocabularies, room for the player, light on memory."""

from __future__ import annotations

import json

import numpy as np
import pytest

import backing_audio as ba
import backing_pianist as pn
import backing_sample_cache as sc

SR = 44100
STYLES = ["Jazz swing", "Blues groove", "Pop groove", "Rock groove", "Funk groove", "Ballad", "Bossa nova", "Soul"]
CHORDS = ["C", "Am", "Dm7", "G7", "Cmaj7", "F#m7b5", "Bdim", "Caug", "A7b9", "E7#9", "Gsus4", "Bb6", "E5", "G/B", "Am/C", "D9", "Cm7", "F13", "Abmaj7", "C#m"]


def sec(name, chords):
    return [{"chord": c, "section": name, "bar_in_section": i, "section_bars": len(chords)} for i, c in enumerate(chords)]


FORM = sec("Verse 1", ["C", "G/B", "Am7", "F", "C", "G/B", "F", "G"] * 2) + sec("Chorus", ["F", "G", "Em7", "Am7"] * 2)


def player(style="Jazz swing", seed="song", **kw):
    return pn.start(style, seed, has_guitar=kw.get("has_guitar", False), level=kw.get("level", "Intermediate"), chord_notes=ba.chord_notes, bass_note=ba.bass_note)


def play(style, chords, *, role="verse", seed="song", quiet=False, level="Intermediate", has_guitar=False, pulses=4):
    p = player(style, seed, level=level, has_guitar=has_guitar)
    bars = []
    for i, c in enumerate(chords):
        nxt = chords[i + 1] if i + 1 < len(chords) else None
        bars.append(p.bar([(0.0, float(pulses), c)], nxt, role=role, quiet=quiet, bar_in_section=i, section_end=False, bar_index=i, pulses_per_bar=pulses))
    return bars


LOOP = ["Am7", "D7", "Gmaj7", "Cmaj7", "F#m7b5", "B7", "Em7", "Em7"] * 4


def render(style="Jazz swing", chart=FORM, title="Piano Test", layers=None, bpm=110):
    a, _ = ba.synthesize_chords_to_numpy(chart, bpm=bpm, loops=1, sr=SR, style=style, level="Intermediate", song_title=title, layers=layers)
    return np.asarray(a, dtype=np.float32)


# --- The switch. ------------------------------------------------------------------------------------------


def test_off_by_default(monkeypatch):
    monkeypatch.delenv("MUSIC_PIANO_V2", raising=False)
    assert pn.mode() == ""
    assert pn.piano_renderer_tag() == ""


@pytest.mark.parametrize("value", ["", "0", "off", "false", "no"])
def test_off_values(monkeypatch, value):
    monkeypatch.setenv("MUSIC_PIANO_V2", value)
    assert pn.mode() == ""


def test_saved_audio_from_each_version_is_kept_apart(monkeypatch):
    tags = set()
    for value in ("", "varied", "recorded"):
        monkeypatch.setenv("MUSIC_PIANO_V2", value)
        tags.add(pn.piano_renderer_tag())
    assert len(tags) == 3


def test_a_missing_pack_keeps_the_existing_sound(monkeypatch, tmp_path):
    monkeypatch.setenv("MUSIC_PIANO_V2", "recorded")
    monkeypatch.setattr(pn, "PIANO_PACK", tmp_path)
    assert pn.mode() == "varied"


def test_the_pack_is_complete_small_and_licensed():
    manifest = json.loads((pn.PIANO_PACK / "manifest.json").read_text(encoding="utf-8"))
    files = [t["file"] for z in manifest["zones"] for la in z["layers"] for t in la["takes"]]
    assert len(files) == 36 and all((pn.PIANO_PACK / f).is_file() for f in files)
    assert "CC0" in (pn.PIANO_PACK / "LICENSE").read_text(encoding="utf-8")
    assert sum(p.stat().st_size for p in pn.PIANO_PACK.iterdir()) < 12 * 1024 * 1024


# --- Correct harmony. -------------------------------------------------------------------------------------


@pytest.mark.parametrize("style", STYLES)
@pytest.mark.parametrize("chord", CHORDS)
def test_every_held_note_belongs_to_the_chord(style, chord):
    h = pn.harmony_of(chord, ba.chord_notes, ba.bass_note, colour=pn.HANDS.get(style, pn._FALLBACK).colour)
    allowed = set(h.allowed) | {h.bass}
    for role in ("verse", "chorus"):
        for bars in (play(style, [chord] * 12, role=role),):
            for hits in bars:
                for hit in hits:
                    if hit.kind == "figure":
                        continue
                    assert {n % 12 for n in hit.notes} <= allowed, (style, chord, hit)


@pytest.mark.parametrize("chord,expected", [("A7b9", True), ("E7#9", True), ("G7#5", True)])
def test_extensions_never_contradict_an_altered_chord(chord, expected):
    h = pn.harmony_of(chord, ba.chord_notes, ba.bass_note)
    assert h.extensions == ()


def test_dominant_and_minor_get_suitable_colours():
    g7 = pn.harmony_of("G7", ba.chord_notes, ba.bass_note)
    assert set(g7.extensions) == {9, 4}  # A and E: the 9th and 13th
    dm7 = pn.harmony_of("Dm7", ba.chord_notes, ba.bass_note)
    assert set(dm7.extensions) == {4, 7}  # E and G: the 9th and 11th


def test_plain_chords_can_stay_plain():
    h = pn.harmony_of("Cmaj7", ba.chord_notes, ba.bass_note, colour=False)
    assert h.extensions == ()


def test_power_chords_get_no_third_and_no_colours():
    h = pn.harmony_of("E5", ba.chord_notes, ba.bass_note)
    assert set(h.written) == {4, 11}
    assert h.extensions == ()
    assert h.third is None


def test_a_slash_chord_keeps_its_written_bass():
    h = pn.harmony_of("G/B", ba.chord_notes, ba.bass_note)
    assert h.bass == 11 and h.root == 7


@pytest.mark.parametrize("style", ["Jazz swing", "Blues groove", "Ballad", "Pop groove"])
def test_figures_resolve_onto_the_next_chord_and_passing_notes_are_only_between(style):
    seen = 0
    for seed in range(30):
        for hits in play(style, LOOP, seed=f"s{seed}"):
            figure = [h for h in hits if h.kind == "figure"]
            if not figure:
                continue
            seen += 1
            assert figure[-1].passing is False
            assert all(h.beats <= 1.0 for h in figure)
            assert all(not h.passing for h in figure[::2])
    assert seen > 5


def test_a_pushed_chord_is_already_the_next_chord():
    pushes = 0
    for seed in range(20):
        p = player("Jazz swing", f"s{seed}")
        for i, c in enumerate(LOOP[:-1]):
            nxt = LOOP[i + 1]
            for hit in p.bar([(0.0, 4.0, c)], nxt, role="verse", quiet=False, bar_in_section=i, section_end=False, bar_index=i, pulses_per_bar=4):
                if hit.kind == "chord" and hit.beat >= 3.5:
                    allowed = set(pn.harmony_of(nxt, ba.chord_notes, ba.bass_note).allowed) | set(pn.harmony_of(c, ba.chord_notes, ba.bass_note).allowed)
                    assert {n % 12 for n in hit.notes} <= allowed
                    pushes += 1
    assert pushes > 5


def test_jazz_voicings_leave_the_root_to_the_bass():
    rooted = total = 0
    h = pn.harmony_of("Dm7", ba.chord_notes, ba.bass_note)
    for hits in play("Jazz swing", ["Dm7"] * 40):
        for hit in hits:
            if hit.kind == "chord" and len(hit.notes) >= 3:
                total += 1
                rooted += h.root in {n % 12 for n in hit.notes}
    assert total and rooted < 0.2 * total


@pytest.mark.parametrize("style", STYLES)
@pytest.mark.parametrize("role", ["verse", "chorus"])
def test_every_playing_bar_states_its_chords_quality(style, role):
    chart = ["C", "Am", "Dm7", "G7", "Cmaj7", "F", "Em", "Bb"] * 5
    for seed in ("a", "b", "c"):
        for chord, hits in zip(chart, play(style, chart, role=role, seed=seed)):
            third = pn.harmony_of(chord, ba.chord_notes, ba.bass_note).third
            played = [h for h in hits if h.kind != "figure"]
            if played:
                assert third in {n % 12 for h in played for n in h.notes}, (style, role, chord, hits)


# --- Variety. ---------------------------------------------------------------------------------------------


def rhythm(hits):
    return tuple(round(h.beat, 2) for h in hits)


def voicings(bars):
    return [h.notes for hits in bars for h in hits if h.kind == "chord" and len(h.notes) >= 2]


@pytest.mark.parametrize("style", STYLES)
def test_bars_do_not_keep_repeating(style):
    bars = play(style, LOOP)
    assert len({rhythm(b) for b in bars}) >= 6
    assert max(sum(rhythm(b) == rhythm(x) for x in bars) for b in bars) <= 0.6 * len(bars)


@pytest.mark.parametrize("style", ["Jazz swing", "Blues groove", "Rock groove", "Funk groove", "Soul", "Bossa nova"])
def test_a_repeated_chord_changes_voicing(style):
    v = voicings(play(style, ["Am7"] * 24))
    assert len(set(v)) >= 3
    runs, best = 1, 1
    for a, b in zip(v, v[1:]):
        runs = runs + 1 if a == b else 1
        best = max(best, runs)
    assert best <= 8


@pytest.mark.parametrize("style", ["Jazz swing", "Blues groove", "Pop groove", "Ballad"])
def test_register_moves_through_the_song(style):
    tops = [max(h.notes) for hits in play(style, LOOP, role="chorus") for h in hits if h.kind == "chord"]
    assert max(tops) - min(tops) >= 4


@pytest.mark.parametrize("style", STYLES)
def test_dynamics_move(style):
    v = [h.velocity for hits in play(style, LOOP) for h in hits]
    assert max(v) - min(v) >= 0.15
    assert len({round(x, 3) for x in v}) > 8


@pytest.mark.parametrize("style", ["Jazz swing", "Blues groove", "Pop groove", "Soul", "Rock groove"])
def test_note_lengths_breathe(style):
    lengths = {round(h.beats, 2) for hits in play(style, LOOP) for h in hits}
    assert len(lengths) >= 8


def twelve_bar(seed):
    p = player("Blues groove", seed)
    chart = ["A7", "D7", "A7", "A7", "D7", "D7", "A7", "A7", "E7", "D7", "A7", "E7"]
    return [p.bar([(0.0, 4.0, c)], chart[i + 1] if i < 11 else "A7", role="verse", quiet=False, bar_in_section=i, section_bars=12, section_end=False, bar_index=i, pulses_per_bar=4) for i, c in enumerate(chart)]


def test_blues_turnarounds_come_occasionally_and_fall_to_the_fifth():
    turned = 0
    for seed in range(30):
        bar = twelve_bar(f"s{seed}")[10]
        if len(bar) == 5 and all(len(h.notes) == 2 for h in bar):
            turned += 1
            lows = [h.notes[0] for h in bar[:4]]
            assert lows == sorted(lows, reverse=True)
            assert bar[-1].passing is False and (bar[-1].notes[0] - bar[-1].notes[1]) % 12 == 7
    assert 5 < turned < 28


def test_figures_are_not_on_a_schedule():
    at = [i for i, hits in enumerate(play("Blues groove", ["A7", "D7", "A7", "E7"] * 16, seed="x")) if any(h.kind == "figure" for h in hits)]
    assert len(at) >= 3
    gaps = {b - a for a, b in zip(at, at[1:])}
    assert len(gaps) >= 2
    assert not all(i % 4 == 3 for i in at)


def test_figures_never_come_two_bars_running():
    for seed in range(20):
        flags = [any(h.kind == "figure" for h in hits) for hits in play("Blues groove", ["A7", "D7"] * 24, seed=f"s{seed}")]
        assert not any(a and b for a, b in zip(flags, flags[1:]))


def test_songs_play_differently():
    a = [rhythm(b) for b in play("Jazz swing", LOOP, seed="one")]
    b = [rhythm(x) for x in play("Jazz swing", LOOP, seed="two")]
    assert a != b


def test_a_song_plays_the_same_every_time():
    assert play("Jazz swing", LOOP, seed="one") == play("Jazz swing", LOOP, seed="one")


@pytest.mark.parametrize("style", ["Jazz swing", "Blues groove", "Pop groove", "Ballad", "Rock groove", "Funk groove"])
def test_most_bars_are_played_differently(style):
    chart = ["Am7", "D7", "Gmaj7", "Cmaj7"] * 8
    root = {c: ba.chord_notes(c)[0] for c in chart}
    bars = play(style, chart, role="chorus")
    played = [tuple((h.beat, tuple(n - root[c] for n in h.notes)) for h in b) for c, b in zip(chart, bars)]
    assert len(set(played)) >= 0.7 * len(played)


@pytest.mark.parametrize("style", ["Jazz swing", "Blues groove", "Pop groove"])
def test_a_phrase_is_still_one_idea(style):
    """Variety, not noise: neighbouring bars usually share some of their rhythm."""
    bars = [{round(h.beat, 2) for h in b} for b in play(style, LOOP * 2)]
    shared = [len(a & b) / max(1, len(a | b)) for a, b in zip(bars, bars[1:]) if a and b]
    assert np.mean(shared) > 0.18


def test_space_is_left_in_jazz():
    empties = sum(len(b) <= 1 for b in play("Jazz swing", LOOP * 2))
    assert empties >= 3


# --- It follows the song. ---------------------------------------------------------------------------------


def density(style, role, quiet=False):
    bars = play(style, ["Am7", "F", "C", "G"] * 12, role=role, quiet=quiet)
    return sum(len(h.notes) for b in bars for h in b) / len(bars)


@pytest.mark.parametrize("style", ["Pop groove", "Jazz swing", "Blues groove", "Rock groove"])
def test_a_chorus_is_fuller_than_a_verse(style):
    assert density(style, "chorus") > density(style, "verse")


def test_a_quiet_section_holds_chords():
    for hits in play("Pop groove", ["C", "F"] * 4, quiet=True):
        assert len(hits) == 1 and hits[0].beats > 2.5


def test_the_phrases_are_uneven():
    p = player("Jazz swing", "z")
    lengths = []
    for i in range(80):
        before = p.phrase_no
        p.bar([(0.0, 4.0, "Dm7")], "G7", role="verse", quiet=False, bar_in_section=i, section_end=False, bar_index=i, pulses_per_bar=4)
        if p.phrase_no != before:
            lengths.append(i)
    gaps = {b - a for a, b in zip(lengths, lengths[1:])}
    assert len(gaps) >= 2


def test_a_split_bar_plays_each_chord_in_its_place():
    p = player("Pop groove", "z")
    for i in range(30):
        hits = p.bar([(0.0, 2.0, "C"), (2.0, 4.0, "F")], "G", role="verse", quiet=False, bar_in_section=i, section_end=False, bar_index=i, pulses_per_bar=4)
        c, f = pn.harmony_of("C", ba.chord_notes, ba.bass_note), pn.harmony_of("F", ba.chord_notes, ba.bass_note)
        for h in hits:
            if h.kind == "figure":
                continue
            assert {n % 12 for n in h.notes} <= set((c if h.beat < 2.0 else f).allowed) | {c.bass, f.bass} | set(f.allowed if h.beat < 2.0 and h.beat >= 1.5 else ())
            if h.beat < 2.0:
                assert h.beat + h.beats <= 2.0 + 1e-6


def test_a_rest_in_the_chart_stays_silent():
    p = player("Pop groove", "z")
    for i in range(30):
        hits = p.bar([(0.0, 2.0, "C"), (2.0, 4.0, None)], "G", role="verse", quiet=False, bar_in_section=i, section_end=False, bar_index=i, pulses_per_bar=4)
        assert all(h.beat < 2.0 for h in hits)


def test_an_empty_bar_is_silent():
    assert player().bar([(0.0, 4.0, None)], "G", role="verse", quiet=False, bar_in_section=0, section_end=False, bar_index=0, pulses_per_bar=4) == []


@pytest.mark.parametrize("pulses", [3, 6])
def test_other_meters_keep_time(pulses):
    for hits in play("Pop groove", ["C", "F", "G", "Am"] * 3, pulses=pulses):
        assert hits
        for h in hits:
            assert 0.0 <= h.beat < pulses and h.beat + h.beats <= pulses + 1e-6


def test_a_beginner_hears_simpler_playing():
    assert density("Jazz swing", "verse") > 0
    simple = sum(len(b) for b in play("Jazz swing", LOOP, level="Beginner"))
    fuller = sum(len(b) for b in play("Jazz swing", LOOP))
    assert simple < fuller


# --- Leaving room. ----------------------------------------------------------------------------------------


def register_of(style):
    return pn.REGISTERS.get(style, pn._DEFAULT_REGISTER)


@pytest.mark.parametrize("style", STYLES)
def test_under_a_melody_each_style_keeps_to_its_ceiling(style):
    for role in ("verse", "chorus", "bridge"):
        for hits in play(style, LOOP, role=role):
            for h in hits:
                assert max(h.notes) <= register_of(style)[1], (style, role, h)


@pytest.mark.parametrize("style", STYLES)
def test_with_no_melody_the_hands_may_rise_but_stay_on_the_instrument(style):
    tops = [max(h.notes) for hits in play(style, LOOP, role="intro") for h in hits]
    assert max(tops) <= register_of(style)[2]
    assert register_of(style)[2] > register_of(style)[1]


def test_styles_live_in_different_places():
    jazz, bossa, ballad = register_of("Jazz swing"), register_of("Bossa nova"), register_of("Ballad")
    assert bossa[1] < jazz[1] < ballad[1]
    low = lambda s: min(min(h.notes) for hits in play(s, ["C", "Am", "F", "G"] * 12) for h in hits)
    assert low("Ballad") < low("Pop groove") < low("Jazz swing")


@pytest.mark.parametrize("style", ["Jazz swing", "Rock groove", "Funk groove", "Bossa nova", "Soul"])
def test_the_bass_range_stays_clear(style):
    for hits in play(style, LOOP):
        for h in hits:
            assert min(h.notes) >= register_of(style)[0], (style, h)


@pytest.mark.parametrize("style", STYLES)
def test_chords_are_not_muddy_low_down(style):
    total = bad = 0
    for hits in play(style, ["C", "Am7", "F", "G7", "Dm7", "Bb", "Eb", "Ab"] * 6):
        for h in hits:
            if h.kind == "chord" and len(h.notes) >= 2:
                total += 1
                bad += pn.muddy(list(h.notes)) > 0
    assert total and bad <= 0.05 * total, (bad, total)


@pytest.mark.parametrize("style", sorted(set(pn.HANDS) | {"Klezmer groove", "Jewish hora"}))
def test_the_left_hand_always_plays_the_chords_own_bass(style):
    # A left-hand range narrower than an octave once clamped some notes to its floor: C under an A chord.
    p = player(style)
    for root in ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]:
        for chord in (root, root + "m", root + "7", f"{root}/E"):
            h = p._h(chord)
            for full in (False, True):
                p.full = full
                assert {n % 12 for n in p._lh(h)} == {h.bass}, (style, chord, p._lh(h))


@pytest.mark.parametrize("style", ["Ballad", "Pop groove"])
def test_verses_leave_room_and_choruses_open_up(style):
    def per_bar(role):
        bars = [b for seed in range(12) for b in play(style, LOOP, role=role, seed=f"s{seed}")]
        return sum(len(b) for b in bars) / len(bars)

    verse, chorus = per_bar("verse"), per_bar("chorus")
    assert verse <= 3.6, verse
    assert chorus > verse, (verse, chorus)


def test_songs_sit_in_slightly_different_places():
    centres = {pn.Pianist("Pop groove", f"s{n}").song_centre for n in range(40)}
    assert len(centres) >= 3


def test_a_big_left_hand_in_a_ballad_chorus():
    bars = play("Ballad", ["C", "Am", "F", "G"] * 8, role="chorus")
    assert any(h.kind == "bass" and len(h.notes) == 2 and h.notes[1] - h.notes[0] == 12 for b in bars for h in b)


def test_with_a_guitar_the_piano_plays_above_it():
    plain = [np.mean(h.notes) for b in play("Rock groove", ["E5", "A5"] * 16) for h in b if h.kind == "chord"]
    above = [np.mean(h.notes) for b in play("Rock groove", ["E5", "A5"] * 16, has_guitar=True) for h in b if h.kind == "chord"]
    assert np.mean(above) > np.mean(plain)
    assert min(min(h.notes) for b in play("Rock groove", ["E5", "A5"] * 16, has_guitar=True) for h in b if h.kind == "chord") >= pn.GUITAR_FLOOR


# --- In the engine. ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("value", ["varied", "recorded"])
def test_on_differs_and_repeats_exactly(monkeypatch, value):
    monkeypatch.delenv("MUSIC_PIANO_V2", raising=False)
    today = render()
    monkeypatch.setenv("MUSIC_PIANO_V2", value)
    a, b = render(), render()
    assert not np.array_equal(today, a)
    assert np.array_equal(a, b)
    assert np.isfinite(a).all() and np.max(np.abs(a)) <= 1.0


@pytest.mark.parametrize("value", ["varied", "recorded"])
@pytest.mark.parametrize("style", STYLES[:7])
def test_the_rhythm_section_is_untouched(monkeypatch, value, style):
    monkeypatch.delenv("MUSIC_PIANO_V2", raising=False)
    a = render(style, layers=("rhythm",))
    monkeypatch.setenv("MUSIC_PIANO_V2", value)
    b = render(style, layers=("rhythm",))
    assert np.allclose(a, b, atol=0.03)


def test_the_keys_layer_sits_at_the_same_balance(monkeypatch):
    monkeypatch.setenv("MUSIC_PIANO_V2", "recorded")
    render("Pop groove")
    rhythm_rms, keys_rms = ba.LAST_MIX_STATS["rhythm_rms"], ba.LAST_MIX_STATS["keys_rms"]
    assert keys_rms / rhythm_rms == pytest.approx(ba._KEYS_BALANCE["Pop groove"], abs=0.1)


@pytest.mark.parametrize("style", ["Jazz swing", "Ballad", "Bossa nova", "Rock groove"])
def test_the_recorded_piano_reaches_todays_balance_in_sparse_styles(monkeypatch, style):
    # Sparse playing on a decaying recording once needed more lift than the balance allows, leaving it 3-6 dB low.
    monkeypatch.delenv("MUSIC_PIANO_V2", raising=False)
    render(style, chart=sec("Verse 1", LOOP[:8]) + sec("Chorus", LOOP[8:16]))
    today = ba.LAST_MIX_STATS["keys_rms"] / ba.LAST_MIX_STATS["rhythm_rms"]
    monkeypatch.setenv("MUSIC_PIANO_V2", "recorded")
    render(style, chart=sec("Verse 1", LOOP[:8]) + sec("Chorus", LOOP[8:16]))
    piano = ba.LAST_MIX_STATS["keys_rms"] / ba.LAST_MIX_STATS["rhythm_rms"]
    assert piano == pytest.approx(today, rel=0.12), (today, piano)


def test_recorded_notes_are_in_tune():
    inst = pn._grand()
    for midi in (48, 55, 60, 67, 72):
        bus = np.zeros(SR, dtype=np.float32)
        inst.add_note(bus, SR, 0.0, 0.9, midi, 1.0, 0.6, "tune")
        f0 = 440.0 * 2.0 ** ((midi - 69) / 12.0)
        w = bus[int(0.06 * SR) : int(0.7 * SR)].astype(np.float64)
        w = (w - w.mean()) * np.hanning(len(w))
        ac = np.fft.irfft(np.abs(np.fft.rfft(w, 2 * len(w))) ** 2)[: len(w)]
        lo, hi = int(SR / (f0 * 1.05)), int(SR / (f0 * 0.95)) + 2
        i = lo + int(np.argmax(ac[lo:hi]))
        y0, y1, y2 = ac[i - 1], ac[i], ac[i + 1]
        assert abs(1200.0 * np.log2((SR / (i + 0.5 * (y0 - y2) / (y0 - 2 * y1 + y2))) / f0)) < 10.0, midi


def test_a_harder_note_uses_a_harder_recording():
    inst = pn._grand()
    zone = inst._zone(60)
    soft = {inst._take(zone, 0.2, f"s{n}", None)["file"] for n in range(30)}
    hard = {inst._take(zone, 0.95, f"s{n}", None)["file"] for n in range(30)}
    assert not soft & hard


def test_a_song_costs_little_memory(monkeypatch):
    monkeypatch.setenv("MUSIC_PIANO_V2", "recorded")
    sc.SHARED.clear()
    render()
    assert 0 < sc.SHARED.bytes < 20 * 1024 * 1024
    assert all(v.dtype == np.int16 for v in sc.SHARED._items.values())
