"""The arrangement plan, round 2: Rock orchestration by section, the Samba bateria by section, the quintet's horns
under a soloist.

Checked: a Rock song's drummer changes groove and orchestration by section (not only fills) and the band's dynamic
follows the song; a Rock trio is never given a piano and its guitar never lays out; Samba sections change players,
calls and the ending (and with no plan the bateria plays exactly as written); the Samba bass follows the bateria;
under a soloist the two horns only rest or answer softly, and come back with a pickup, never out of the intro.
"""

from __future__ import annotations

import pytest

import backing_arrangement_plan as ap
import backing_horn_arranger as harr
import backing_performance_plan as pp
import backing_samba_ensemble as se

from tests.test_arrangement_plan import JAZZ, SONG, _blocks, _form, _plan

SAMBA = [("A (Samba)", ["Dm7", "G7", "Cmaj7", "A7", "Dm7", "G7", "Cmaj7", "Cmaj7"]),
         ("B (Samba)", ["Fmaj7", "Bb7", "Em7", "A7", "Dm7", "G7", "Cmaj7", "A7"])]


# --- Rock ---------------------------------------------------------------------------------------------------


def _kit_by_block(plan):
    return [(b.role, b.final_chorus, ap.kit_part(plan, b.index)) for b in _blocks(plan)]


def test_the_rock_drummer_changes_groove_and_orchestration_by_section():
    plan, _ = _plan(SONG, "Rock groove", ensemble="Rock trio")
    kit = _kit_by_block(plan)
    by_role = {}
    for role, final, k in kit:
        by_role.setdefault((role, final), k)
    verse, chorus, bridge = by_role[("verse", False)], by_role[("chorus", False)], by_role[("bridge", False)]
    final = by_role[("chorus", True)]
    grid = lambda k: dict(k.grid)  # noqa: E731
    assert verse.cymbal == "hat" and chorus.cymbal in ("ride", "wash") and final.cymbal == "wash"
    assert len(grid(chorus)["kick_beats"]) > len(grid(verse)["kick_beats"])  # the chorus kick drives
    assert grid(bridge)["snare_beats"] == (2.0,)  # the bridge goes half time
    assert grid(bridge)["bass_beats"] == (0.0, 2.0)
    pre = by_role[("pre", False)]
    assert pre.cymbal == "floor" or grid(pre)["kick_beats"] == (0.0, 1.0, 2.0, 3.0)  # the pre-chorus builds
    # The band's dynamic: a verse under its chorus, the final chorus on top, the bridge down.
    assert verse.level < chorus.level < final.level and bridge.level < chorus.level
    # Verse 2 is not a copy of verse 1.
    verses = [k for role, _f, k in kit if role == "verse"]
    assert verses[0].grid != verses[1].grid


def test_only_rock_gets_the_kit_part_and_only_with_the_plan():
    jazz, _ = _plan(JAZZ, "Jazz swing", loops=4)
    assert all(ap.kit_part(jazz, b.index) is None for b in jazz.bars)
    assert ap.kit_part(None, 0) is None


def test_a_rock_trio_has_no_piano_and_its_guitar_never_lays_out():
    rows, cl = _form(SONG)
    perf = pp.resolve_performance_plan(style="Rock groove", ensemble="Rock trio", guitar_available=True)
    assert not perf.plays("keys") and perf.plays("guitar")
    plan = ap.build(rows, cl, style="Rock groove", performance=perf, seed=5)
    assert all(b.guitar_part != "rest" for b in plan.bars)
    # The style's own band (with piano) lets the piano set the intro up.
    four = ap.build(rows, cl, style="Rock groove", performance=pp.resolve_performance_plan(style="Rock groove", guitar_available=True), seed=5)
    assert any(b.guitar_part == "rest" for b in four.bars if b.role == "intro")
    # Without a guitar renderer the trio keeps a piano (the approved fallback, named as such): not the plan's choice.
    assert pp.resolve_performance_plan(style="Rock groove", ensemble="Rock trio", guitar_available=False).fallbacks


def test_the_first_verse_guitar_is_muted_and_a_later_verse_changes():
    plan, _ = _plan(SONG, "Rock groove", ensemble="Rock trio")
    verses = [b for b in _blocks(plan) if b.role == "verse"]
    assert verses[0].guitar_part == "chug"
    assert all(b.guitar_level < c.guitar_level for b in verses for c in _blocks(plan) if c.role == "chorus")


# --- Samba --------------------------------------------------------------------------------------------------


def test_samba_sections_change_players_and_calls():
    plan, _ = _plan(SAMBA, "Samba", loops=3)
    blocks = _blocks(plan)
    assert [b.perc_texture for b in blocks] == ["light", "tamborim", "bells", "bells", "full", "full"]
    last = [plan.at(b.index + b.section_bars - 1) for b in blocks]
    assert [b.perc_call for b in last] == ["small", "big", "small", "big", "small", "ending"]
    assert all(b.perc_call == "" for b in plan.bars if not b.ends_section)
    assert ap.samba_bass_figure(plan, blocks[0].index) == "two" and ap.samba_bass_figure(plan, blocks[-1].index) == "busy"


def _voices(strokes):
    return {s.voice.split("_")[0] for s in strokes}


def test_each_samba_texture_has_its_own_players():
    light = se.bar_strokes(1, texture="light", bar_in_section=1, section_bars=8, seed=3)
    tam = se.bar_strokes(1, texture="tamborim", bar_in_section=1, section_bars=8, seed=3)
    bells = se.bar_strokes(1, texture="bells", bar_in_section=1, section_bars=8, seed=3)
    full = se.bar_strokes(1, texture="full", bar_in_section=1, section_bars=8, seed=3)
    assert _voices(light) == {"surdo", "pandeiro", "ganza"}
    assert "tamborim" in _voices(tam) and "agogo" not in _voices(tam)
    assert "agogo" in _voices(bells) and "tamborim" not in _voices(bells)
    assert {"surdo", "pandeiro", "ganza", "tamborim", "agogo"} <= _voices(full)
    assert len(light) < len(tam) < len(full)
    assert any(s.voice == "pandeiro_shake" for s in full) and not any(s.voice == "pandeiro_shake" for s in tam)


def test_samba_calls_and_the_ending():
    small = se.bar_strokes(7, texture="light", call="small", bar_in_section=7, section_bars=8, seed=3)
    assert [s.beat for s in small if s.voice == "tamborim"] == [3.0, 3.25, 3.5, 3.75]  # the tamborim enters with its call
    big = se.bar_strokes(15, texture="tamborim", call="big", bar_in_section=7, section_bars=8, seed=3)
    assert {3.25, 3.5, 3.75} <= {s.beat for s in big if s.voice.startswith("surdo")}
    end = se.bar_strokes(47, texture="full", call="ending", bar_in_section=7, section_bars=8, seed=3)
    assert max(s.beat for s in end) == se.ENDING_LAST  # then silence
    assert {s.beat for s in end} == set(se.ENDING_FIGURE) | {se.ENDING_LAST}


@pytest.mark.parametrize("bar", [0, 3, 7, 12])
def test_without_the_plan_the_bateria_plays_as_written(bar):
    assert se.bar_strokes(bar, intensity="Medium", bar_in_section=bar % 8, section_bars=8, seed=4) == se.bar_strokes(
        bar, intensity="Medium", bar_in_section=bar % 8, section_bars=8, seed=4, texture="", call="")


def test_the_samba_bass_follows_the_bateria():
    import numpy as np

    import backing_audio as ba

    def notes(fig):
        return ba._samba_bass_bar("Dm7", "G7", {}, np.random.default_rng(1), figure=fig)

    assert len(notes("two")) == 4  # root and low fifth in each half, no pickups
    assert len(notes("busy")) == 8  # a pickup and an approach note in each half
    assert notes("") == ba._samba_bass_bar("Dm7", "G7", {}, np.random.default_rng(1))


# --- The quintet's horns under a soloist ---------------------------------------------------------------------


def _jazz_arrangement(seed=2):
    plan, rows = _plan(JAZZ, "Jazz swing", loops=4, ensemble="Jazz quintet")
    bars = [harr.ArrBar(i, i * 2.0, 0.5, ((r["chord"], 0.0, 4.0),), bar_in_section=r["bar_in_section"], section_bars=r["section_bars"])
            for i, r in enumerate(rows)]
    weights = {b.index: b.horn_weights for b in plan.bars if b.horn_weights}
    dyn = {b.index: b.horn_dynamic for b in plan.bars if b.horn_weights}
    return plan, harr.arrange(bars, intensity="Medium", seed=seed, swing=0.62, phrase_weights=weights, phrase_dynamics=dyn)


@pytest.mark.parametrize("seed", [1, 2, 3, 4])
def test_under_a_soloist_the_horns_rest_or_answer_softly(seed):
    plan, arr = _jazz_arrangement(seed)
    for start, tex in arr.phrases:
        if plan.bars[start].role == "solo_pass":
            assert tex in ("rest", "solo_pad", "response"), (start, tex)
    notes = arr.notes["trumpet"] + arr.notes["tenor"]
    solo_v = [n.velocity for n in notes if plan.at(int(n.start_sec // 2.0)) and plan.at(int(n.start_sec // 2.0)).role == "solo_pass"]
    out_v = [n.velocity for n in notes if plan.at(int(n.start_sec // 2.0)) and plan.at(int(n.start_sec // 2.0)).role == "out_head"]
    assert out_v and (not solo_v or max(solo_v) < sum(out_v) / len(out_v))


def test_a_response_sits_in_the_soloists_breath():
    plan, rows = _plan(JAZZ, "Jazz swing", loops=4, ensemble="Jazz quintet")
    bars = [harr.ArrBar(i, i * 2.0, 0.5, ((r["chord"], 0.0, 4.0),), bar_in_section=r["bar_in_section"], section_bars=r["section_bars"])
            for i, r in enumerate(rows)]
    arr = harr.arrange(bars, seed=3, swing=0.62, phrase_weights={16: {"response": 1.0}})
    assert dict(arr.phrases)[16] == "response"
    notes = [n for n in arr.notes["trumpet"] + arr.notes["tenor"] if 32.0 <= n.start_sec < 40.0]
    assert notes and all(38.0 <= n.start_sec for n in notes)  # only in the phrase's last bar
    assert len({k for k in ("trumpet", "tenor") if any(32.0 <= n.start_sec < 40.0 for n in arr.notes[k])}) == 1


def test_the_horns_come_back_with_a_pickup_not_out_of_the_intro():
    rows, _ = _form([("Intro", ["C", "Am", "F", "G"]), ("Head", ["Dm7", "G7", "Cmaj7", "Cmaj7"]),
                     ("Solo", ["Dm7", "G7", "Cmaj7", "Cmaj7"]), ("Out", ["Dm7", "G7", "Cmaj7", "Cmaj7"])])
    bars = [harr.ArrBar(i, i * 2.0, 0.5, ((r["chord"], 0.0, 4.0),), bar_in_section=r["bar_in_section"], section_bars=r["section_bars"])
            for i, r in enumerate(rows)]
    arr = harr.arrange(bars, seed=1, swing=0.5, phrase_weights={0: {"rest": 1.0}, 4: {"soli": 1.0}, 8: {"rest": 1.0}, 12: {"soli": 1.0}})
    notes = arr.notes["trumpet"] + arr.notes["tenor"]
    assert not any(n.start_sec < 8.0 - 0.05 for n in notes)  # no pickup out of the intro
    pickup = [n for n in notes if 22.0 <= n.start_sec < 24.0]  # the last bar of the solo, into the out head
    assert len(pickup) >= 4 and all(n.start_sec >= 22.0 + 2.25 * 0.5 - 0.05 for n in pickup)


def test_a_soli_phrase_is_a_harmonised_line_for_both_horns():
    rows, _ = _form([("Head", ["Dm7", "G7", "Cmaj7", "A7"])])
    bars = [harr.ArrBar(i, i * 2.0, 0.5, ((r["chord"], 0.0, 4.0),), bar_in_section=i, section_bars=4) for i, r in enumerate(rows)]
    arr = harr.arrange(bars, seed=4, swing=0.62, phrase_weights={0: {"soli": 1.0}})
    top, low = arr.notes["trumpet"], arr.notes["tenor"]
    assert len(top) >= 6 and len(low) >= 6
    assert {round(n.start_sec, 1) for n in top if n.start_sec < 4.0} & {round(n.start_sec, 1) for n in low if n.start_sec < 4.0}
