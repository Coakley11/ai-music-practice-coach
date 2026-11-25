"""The arrangement plan (MUSIC_ARRANGEMENT_PLAN): one plan the band follows through the song.

Checked: off = nothing changes; roles from the chart and from a jam's passes; energy shape (intro low, chorus
high, final chorus highest, a drop after a chorus); fills sized by where the song goes (big only into big
moments, never in every bar); horns rest in intros / solos and harmonise in choruses, and give way entirely
in ``solo_space``; the guitar changes part by section; percussion follows the section energy; the same take
plans the same way and a new seed differently; in the band the planned take keeps -22 LUFS and varies.
"""

from __future__ import annotations

import numpy as np
import pytest

import backing_arrangement_plan as ap
import backing_drum_kit as dk
import backing_horn_arranger as harr
import backing_performance_plan as pp
import backing_section_arrangement as sa


def _form(secs, loops=1):
    one = [{"chord": c, "section": n, "bar_in_section": i, "section_bars": len(cs)} for n, cs in secs for i, c in enumerate(cs)]
    return one * loops, len(one)


SONG = [("Intro", ["C", "Am", "F", "G"]), ("Verse 1", ["C", "G", "Am", "F"] * 2), ("Pre-Chorus", ["Dm", "Em", "F", "G"]),
        ("Chorus", ["C", "G", "Am", "F"] * 2), ("Verse 2", ["C", "G", "Am", "F"] * 2), ("Pre-Chorus", ["Dm", "Em", "F", "G"]),
        ("Chorus", ["C", "G", "Am", "F"] * 2), ("Bridge", ["Am", "F", "C", "G"] * 2), ("Final Chorus", ["C", "G", "Am", "F"] * 2),
        ("Outro", ["C", "G", "F", "C"])]
JAZZ = [("Head (Jazz Swing)", ["Dm7", "G7", "Cmaj7", "Cmaj7", "Em7b5", "A7", "Dm7", "G7"]),
        ("Bridge (Jazz Swing)", ["Fm7", "Bb7", "Ebmaj7", "Ebmaj7", "Em7b5", "A7", "Dm7", "G7"])]


def _plan(secs, style, loops=1, seed=5, **kw):
    rows, cl = _form(secs, loops)
    perf = pp.resolve_performance_plan(style=style, ensemble=kw.pop("ensemble", ""), intensity=kw.pop("intensity", "Medium"))
    return ap.build(rows, cl, style=style, performance=perf, seed=seed, **kw), rows


def _blocks(plan):
    out = []
    for b in plan.bars:
        if not out or (out[-1][0], out[-1][1]) != (b.pass_index, b.block):
            out.append([b.pass_index, b.block, b])
    return [x[2] for x in out]


def test_off_by_default(monkeypatch):
    monkeypatch.delenv(ap.SWITCH, raising=False)
    assert not ap.enabled()
    monkeypatch.setenv(ap.SWITCH, "1")
    assert ap.enabled()


def test_a_song_plans_by_its_sections():
    plan, _ = _plan(SONG, "Rock groove")
    blocks = _blocks(plan)
    roles = [b.role for b in blocks]
    assert roles == ["intro", "verse", "pre", "chorus", "verse", "pre", "chorus", "bridge", "chorus", "outro"]
    e = {i: b.energy for i, b in enumerate(blocks)}
    assert e[0] < e[1] < e[2] < e[3]  # intro -> verse -> pre -> chorus builds
    assert e[4] < e[3]  # Verse 2 drops back
    assert e[4] > e[1]  # ... but leans in a little more than Verse 1
    assert e[8] == max(e.values()) and blocks[8].final_chorus  # the final chorus is the top
    assert e[7] < e[6]  # the bridge thins out


def test_fills_are_sized_by_where_the_song_goes_and_never_every_bar():
    plan, _ = _plan(SONG, "Rock groove")
    fills = [b.fill for b in plan.bars if b.fill]
    assert len(fills) == len(_blocks(plan))  # one at each section end, none elsewhere
    by_next = {}
    bars = plan.bars
    for i, b in enumerate(bars[:-1]):
        if b.fill:
            by_next[(b.role, bars[i + 1].role, bars[i + 1].final_chorus)] = b.fill
    assert by_next[("bridge", "chorus", True)] == "big"  # into the final chorus
    assert by_next[("chorus", "verse", False)] == "small"  # a drop: only a setup
    assert bars[-1].fill == "ending"
    assert sum(f == "big" for f in fills) <= 2


def test_a_jazz_jam_plays_head_solos_out():
    plan, _ = _plan(JAZZ, "Jazz swing", loops=4, ensemble="Jazz quintet")
    by_pass = {}
    for b in plan.bars:
        by_pass.setdefault(b.pass_index, set()).add(b.role)
    assert "head" in by_pass[0] and by_pass[1] == {"solo_pass"} and by_pass[2] == {"solo_pass"}
    assert "out_head" in by_pass[3]
    assert plan.bars[-1].fill == "ending"
    first, out = plan.bars[0].energy, max(b.energy for b in plan.bars if b.pass_index == 3)
    assert out > first


def test_horns_leave_space_and_harmonise_where_it_counts():
    plan, _ = _plan(SONG, "Rock groove", ensemble="Jazz quintet")
    w = {b.role: b.horn_weights for b in plan.bars if b.horn_weights}
    assert set(w["intro"]) == {"rest"}
    assert w["verse"].get("rest", 0) >= max(v for k, v in w["verse"].items() if k != "rest")
    assert {"riff", "hits"} & set(w["chorus"])
    jazz, _ = _plan(JAZZ, "Jazz swing", loops=4, ensemble="Jazz quintet")
    solo = [b for b in jazz.bars if b.horn_weights and b.role == "solo_pass"]
    # Under a soloist the horns rest or answer softly at the end of the soloist's phrase; anything that holds or
    # plays through the phrase (a pad, a held guide tone) is the rare exception, and they play softer than in a head.
    quiet = ("rest", "response")
    assert solo and all(sum(b.horn_weights.get(k, 0) for k in quiet) > 2.5 * sum(v for k, v in b.horn_weights.items() if k not in quiet)
                        for b in solo)
    assert not any({"riff", "hits", "soli", "call"} & set(b.horn_weights) for b in solo)
    heads = [b.horn_dynamic for b in jazz.bars if b.horn_weights and b.role == "head"]
    outs = [b.horn_dynamic for b in jazz.bars if b.horn_weights and b.role == "out_head"]
    assert all(b.horn_dynamic < min(heads) for b in solo) and min(outs) > max(heads)


def test_solo_space_keeps_the_horns_out_of_your_way():
    plan, _ = _plan(SONG, "Rock groove", ensemble="Jazz quintet", horn_presence="solo_space")
    for b in plan.bars:
        if b.horn_weights and b.role not in ("outro",) and not b.final_chorus:
            assert set(b.horn_weights) == {"rest"}, (b.role, b.horn_weights)
    assert plan.tag().endswith("-so")


def test_the_guitar_changes_its_part_by_section():
    plan, _ = _plan(SONG, "Rock groove")
    parts = {b.role: b.guitar_part for b in plan.bars}
    assert parts["intro"] == "rest"
    assert parts["verse"] in ("chug", "stabs") and parts["chorus"] in ("strum", "arena")
    assert parts["bridge"] == "arena" and parts["verse"] != parts["chorus"]



def test_the_guitarist_plays_a_verse_under_its_chorus():
    plan, _ = _plan(SONG, "Rock groove")
    level = {}
    for b in plan.bars:
        level.setdefault((b.role, b.final_chorus), b.guitar_level)
    assert level[("verse", False)] < level[("pre", False)] < level[("chorus", False)] < level[("chorus", True)]
    assert all(0.7 <= b.guitar_level <= 1.12 for b in plan.bars)

def test_percussion_follows_the_section_energy():
    plan, _ = _plan(SONG, "Samba")
    levels = {b.role: b.perc_intensity for b in plan.bars}
    assert levels["intro"] == "Light" and levels["chorus"] in ("Medium", "Heavy")
    final = [b.perc_intensity for b in plan.bars if b.final_chorus]
    assert set(final) == {"Heavy"}


def test_the_same_take_plans_the_same_way_and_a_new_seed_differently():
    a, _ = _plan(SONG, "Rock groove", seed=11)
    b, _ = _plan(SONG, "Rock groove", seed=11)
    assert a == b
    parts = {tuple(b.guitar_part for b in _plan(SONG, "Rock groove", seed=s)[0].bars) for s in range(8)}
    assert len(parts) >= 2


def test_intensity_moves_the_whole_arc():
    light, _ = _plan(SONG, "Rock groove", intensity="Light")
    heavy, _ = _plan(SONG, "Rock groove", intensity="Heavy")
    assert all(h.energy > l.energy for h, l in zip(heavy.bars, light.bars))


def test_unlabelled_sections_get_textures_labelled_ones_keep_item_34():
    plan, rows = _plan(SONG, "Rock groove")
    places = sa.build_plan(rows, len(rows))
    for i, p in enumerate(places[:-1]):
        assert ap.bar_texture(plan, i, p) == sa.bar_texture("Rock groove", p) or plan.bars[i].final_chorus
    jazz, jrows = _plan(JAZZ, "Jazz swing", loops=3)
    jplaces = sa.build_plan(jrows, len(jrows) // 3)
    tex = [ap.bar_texture(jazz, i, p) for i, p in enumerate(jplaces)]
    solo = [t for t, b in zip(tex, jazz.bars) if b.role == "solo_pass"]
    assert solo and all(t is not None and t.comp == "sparse" for t in solo)
    assert tex[-1] is not None and tex[-1].drums == "ending"


# --- The drummer's sized fills ----------------------------------------------------------------------------


def _ctx(style, fill, bar=7, **kw):
    return dk.BarContext(style=style, bar_in_section=bar, role="verse", next_role="chorus", ends_section=True,
                         pulses_per_bar=4.0, song_seed=3, bar_index=bar, fill=fill, **kw)


@pytest.mark.parametrize("style", ["Rock groove", "Pop groove", "Funk groove", "Jazz swing"])
def test_fill_sizes_grow_and_keep_the_style(style):
    small = dk.bar_extras(_ctx(style, "small"))
    big = dk.bar_extras(_ctx(style, "big"))
    notes = lambda hs: [h for h in hs if h.voice in ("tom", "ghost", "kick", "open")]  # noqa: E731
    assert len(notes(big)) > len(notes(small))
    assert dk.bar_extras(_ctx(style, "ending")) == dk._style_bed(_ctx(style, "ending"))
    if style == "Jazz swing":
        assert not any(h.voice == "tom" for h in big)  # a jazz drummer never plays a rock tom run


def test_quiet_sections_move_less():
    def moves(rate):
        return sum(bool(dk._phrase_move(dk.BarContext(style="Rock groove", bar_in_section=b % 8, role="verse", next_role="",
                                                      ends_section=False, pulses_per_bar=4.0, song_seed=s, bar_index=b,
                                                      move_rate=rate)))
                   for s in range(20) for b in range(1, 8))
    assert moves(0.5) < moves(1.0) < moves(1.5)


# --- The horn arranger follows the plan -------------------------------------------------------------------


def test_the_horn_arranger_takes_the_plans_phrases():
    plan, rows = _plan(SONG, "Rock groove", ensemble="Jazz quintet")
    bars = [harr.ArrBar(i, i * 2.0, 0.5, ((r["chord"], 0.0, 4.0),), bar_in_section=r["bar_in_section"], section_bars=r["section_bars"])
            for i, r in enumerate(rows)]
    weights = {b.index: b.horn_weights for b in plan.bars if b.horn_weights}
    arr = harr.arrange(bars, intensity="Medium", seed=2, swing=0.5, phrase_weights=weights)
    tex = dict(arr.phrases)
    for start, t in tex.items():
        role = plan.bars[start].role
        assert t in weights[start], (start, role, t)
    assert tex[0] == "rest"  # the intro
    notes = arr.notes["trumpet"] + arr.notes["tenor"]
    assert not any(n.start_sec < 8.0 - 0.05 for n in notes if n.articulation)  # nothing in the four intro bars


def test_a_feature_phrase_gives_one_horn_a_melodic_passage():
    rows, _ = _form([("Interlude", ["Dm7", "G7", "Cmaj7", "A7"])])
    bars = [harr.ArrBar(i, i * 2.0, 0.5, ((r["chord"], 0.0, 4.0),), bar_in_section=i, section_bars=4) for i, r in enumerate(rows)]
    arr = harr.arrange(bars, seed=1, swing=0.62, phrase_weights={0: {"feature": 1.0}})
    assert arr.phrases[0][1] == "feature"
    lead = max(("trumpet", "tenor"), key=lambda k: len(arr.notes[k]))
    first3 = [n for n in arr.notes[lead] if n.start_sec < 6.0]
    assert len({int(n.start_sec // 2.0) for n in first3}) == 3  # it plays in each of the first three bars


# --- In the band ------------------------------------------------------------------------------------------


def test_a_planned_take_keeps_its_loudness_and_its_switch(monkeypatch):
    import backing_audio as ba
    import backing_loudness as bl

    monkeypatch.setenv("MUSIC_BACKING_LOUDNESS", "match")
    monkeypatch.setenv("MUSIC_DRUM_KIT_V2", "1")  # the plan's fills and moves are the recorded drummer's
    monkeypatch.setenv("MUSIC_ROCK_GUITAR", "recorded")  # ... and its guitar parts the recorded guitarist's
    rows, _ = _form(SONG[:4])
    monkeypatch.delenv(ap.SWITCH, raising=False)
    off, sr = ba.synthesize_chords_to_numpy(rows, bpm=110, loops=1, style="Rock groove")
    tag_off = ba.drum_renderer_tag()
    monkeypatch.setenv(ap.SWITCH, "1")
    on, _ = ba.synthesize_chords_to_numpy(rows, bpm=110, loops=1, style="Rock groove")
    assert "+arrplan" in ba.drum_renderer_tag() and "+arrplan" not in tag_off
    assert abs(bl.integrated_lufs(on, sr) + 22.0) < 0.5 and abs(bl.integrated_lufs(off, sr) + 22.0) < 0.5
    n = min(len(on), len(off))
    assert not np.allclose(on[:n], off[:n])


@pytest.mark.parametrize("style", ["Samba", "Latin jazz"])
@pytest.mark.parametrize("plan_on", [False, True])
def test_the_recorded_percussion_renders_with_and_without_the_plan(monkeypatch, style, plan_on):
    """The Samba section and the Latin percussionist read the bar's plan before anything else does (a take with
    them on used to stop on the first bar, plan on or off)."""
    import backing_audio as ba
    import backing_latin_percussion as lp
    import backing_samba_ensemble as se

    for k, v in (("MUSIC_LATIN_GROOVES", "1"), ("MUSIC_SAMBA_ENSEMBLE", "1"), ("MUSIC_DRUM_KIT_V2", "1")):
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("MUSIC_BACKING_LOUDNESS", raising=False)
    if plan_on:
        monkeypatch.setenv(ap.SWITCH, "1")
    else:
        monkeypatch.delenv(ap.SWITCH, raising=False)
    assert se.enabled() if style == "Samba" else lp.plays(style)
    rows = [{"chord": c, "section": n, "bar_in_section": i, "section_bars": 2}
            for n, cs in (("A", ["Dm7", "G7"]), ("B", ["Cmaj7", "A7"])) for i, c in enumerate(cs)]
    audio, sr = ba.synthesize_chords_to_numpy(rows, bpm=104, loops=1, style=style)
    assert len(audio) > sr and float(np.max(np.abs(audio))) > 0.01
