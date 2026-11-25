"""Backing Engine 2.0: one arrangement plan for the whole take, so the band plays the song, not a loop.

Behind ``MUSIC_ARRANGEMENT_PLAN`` (off by default: every take renders exactly as before).

The plan is built once per render from the chart's sections (``chord_list`` events: ``section``,
``bar_in_section``, ``section_bars``), the passes through the form (a generated jam's form played several
times), the style, the band (:class:`backing_performance_plan.PerformancePlan`) and the take's seed. Every
player reads it, so they agree on where the song is going:

* **role** of each bar: the chart's own (intro, verse, pre-chorus, chorus, bridge, solo, outro ... via
  ``backing_section_arrangement.section_role``) or, for an unlabelled jam form, one from its passes - a jazz
  form plays a *head*, then *solo* choruses, then the *out* head; a pop / rock form moves from a verse feel
  to a chorus feel and back;
* **energy** (0-1): the role's place in the song, raised a little on repeats (Verse 2, the final chorus),
  moved by the jam's intensity, built up through a pre-chorus;
* **texture** for the existing groove knobs (``SectionTexture``): labelled sections keep the approved
  item-34 textures; the plan adds textures for jam passes and the head / solo / out roles;
* **drums**: the size of the fill that closes a section (small / medium / big, from the energy jump to the
  next section and biggest into the final chorus; a drop in energy gets only a setup), and how often the
  drummer adds a small move inside a phrase. Most bars stay plain;
* **horns**: per four-bar phrase, the textures the horn section may choose from (rests in intros and solos,
  harmony in choruses, a featured passage in an instrumental section), scaled by ``horn_presence``
  (``normal`` / ``sparse`` / ``solo_space``, for when you play a horn yourself);
* **guitar**: the rhythm part per section (muted in a verse, strummed in a chorus, ringing in a bridge, out in
  an intro);
* **percussion**: the Samba / Latin section's own intensity per section.

The same chart, band and seed give the same plan on every render (reload and replay keep the take); a new
seed (regenerate) gives a new one.
"""

from __future__ import annotations

import os
import zlib
from dataclasses import dataclass, field, replace
from typing import Any, Sequence

import backing_section_arrangement as sa

PLAN_VERSION = 2
SWITCH = "MUSIC_ARRANGEMENT_PLAN"

HEAD, SOLO_PASS, OUT_HEAD = "head", "solo_pass", "out_head"

# Where each role sits in a song (before repeats and intensity).
_ENERGY = {
    sa.INTRO: 0.30, sa.VERSE: 0.45, sa.PRE: 0.58, sa.CHORUS: 0.74, sa.REFRAIN: 0.68, sa.BRIDGE: 0.50,
    sa.INTERLUDE: 0.62, sa.SOLO: 0.55, sa.BREAKDOWN: 0.28, sa.OUTRO: 0.48, sa.NEUTRAL: 0.55,
    HEAD: 0.52, SOLO_PASS: 0.58, OUT_HEAD: 0.70,
}
_INTENSITY_SHIFT = {"Light": -0.14, "Medium": 0.0, "Heavy": 0.14}
_JAZZ_FORM_STYLES = frozenset({"Jazz swing", "Ballad", "Bossa nova", "Latin jazz", "Samba", "Blues groove"})
_HORN_PRESENCE = ("normal", "sparse", "solo_space")


def enabled() -> bool:
    return str(os.environ.get(SWITCH) or "").strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class BarArrangement:
    index: int
    role: str  # the role the band plays (chart role, or head / solo_pass / out_head for a jam's passes)
    chart_role: str  # backing_section_arrangement.section_role of the chart's label
    block: int  # section block within the pass
    pass_index: int  # which pass through the form (0-based)
    passes: int
    bar_in_section: int
    section_bars: int
    energy: float
    final_chorus: bool = False
    fill: str = ""  # at a section end: "small" / "medium" / "big" / "ending"; "" otherwise
    move_rate: float = 1.0  # the drummer's small moves inside a phrase, x the style's own rate
    guitar_part: str = ""  # backing_rock_guitar part for this section ("" = the guitarist's own; "rest" = out)
    guitar_level: float = 1.0  # the guitarist's touch here (x the bar's level): lighter in a verse than a chorus
    perc_intensity: str = "Medium"  # the Samba / Latin percussion section's intensity here
    horn_weights: dict = field(default_factory=dict)  # texture -> weight for the horn phrase starting here
    role_pass: int = 1  # which block of this role so far (Verse 2 -> 2), passes through the form included
    horn_dynamic: float = 0.0  # added to the horns' velocity for the phrase starting here (soft in a solo)
    perc_texture: str = ""  # Samba: which players of the bateria play this section ("" = all, as written)
    perc_call: str = ""  # Samba: at a section's last bar, the call into the next ("small" / "big" / "ending")

    @property
    def ends_section(self) -> bool:
        return self.bar_in_section == self.section_bars - 1


@dataclass(frozen=True)
class ArrangementPlan:
    style: str
    bars: tuple[BarArrangement, ...]
    seed: int
    horn_presence: str = "normal"

    def __len__(self) -> int:
        return len(self.bars)

    def at(self, idx: int) -> BarArrangement | None:
        return self.bars[idx] if 0 <= idx < len(self.bars) else None

    def tag(self) -> str:
        return f"+arrplan{PLAN_VERSION}-{self.horn_presence[:2]}"

    def describe(self) -> list[str]:
        """One line per section block and pass: role, energy, fill, guitar, horns (for listening notes)."""
        out, last = [], None
        for b in self.bars:
            key = (b.pass_index, b.block)
            if key != last:
                top = max(b.horn_weights, key=b.horn_weights.get) if b.horn_weights else "-"
                out.append(f"bar {b.index + 1}: {b.role} (energy {b.energy:.2f}, guitar {b.guitar_part or '-'}, horns ~{top})")
                last = key
            if b.fill:
                out[-1] += f" -> {b.fill} fill"
        return out


def _rand(seed: int, *parts: Any) -> float:
    return (zlib.crc32(repr((seed,) + parts).encode()) & 0xFFFFFF) / float(0x1000000)


# --- Roles -----------------------------------------------------------------------------------------------


def _jam_role(style: str, chart_role: str, block: int, blocks: int, pass_index: int, passes: int) -> str:
    """The role for a bar whose chart label names no role (a jam's "Head", "A", "Groove" ...)."""
    if style in _JAZZ_FORM_STYLES and passes > 2 and 0 < pass_index < passes - 1 and chart_role not in (sa.INTRO, sa.OUTRO):
        return SOLO_PASS  # the solo choruses blow over the whole form, its bridge included
    if chart_role != sa.NEUTRAL:
        return chart_role
    if style in _JAZZ_FORM_STYLES:
        if passes <= 1:
            return HEAD
        if pass_index == 0:
            return HEAD
        if pass_index == passes - 1:
            return OUT_HEAD
        return SOLO_PASS
    # Pop / rock / funk / soul: the first block of a pass is a verse feel, later blocks a chorus feel.
    if blocks <= 1:
        return sa.VERSE if pass_index < max(1, passes - 1) else sa.CHORUS
    return sa.VERSE if block == 0 else sa.CHORUS


def _energy(role: str, *, role_pass: int, final_chorus: bool, pass_index: int, passes: int, intensity: str,
            bar: int, bars: int) -> float:
    e = _ENERGY.get(role, 0.55)
    e += min(0.08, 0.04 * max(0, role_pass - 1))  # Verse 2 / Chorus 2 lean in a little
    if final_chorus:
        e += 0.12
    if passes > 1 and role not in (sa.INTRO, sa.OUTRO, sa.BREAKDOWN):
        e += 0.06 * pass_index / max(1, passes - 1)  # a jam builds across its passes
    if role == sa.PRE and bars > 1:
        e += 0.1 * bar / (bars - 1)  # a pre-chorus builds into the chorus
    e += _INTENSITY_SHIFT.get(str(intensity), 0.0)
    return float(min(1.0, max(0.08, e)))


# --- Instruments -----------------------------------------------------------------------------------------

# Horn texture weights by role (backing_horn_arranger.TEXTURES + "feature").
_HORN_ROLE_WEIGHTS: dict[str, dict[str, float]] = {
    sa.INTRO: {"rest": 1.0},
    sa.VERSE: {"rest": 3.0, "solo_pad": 2.0, "call": 2.0},
    HEAD: {"rest": 1.5, "soli": 2.5, "solo_pad": 1.5, "staggered": 1.5, "call": 2.0},
    sa.PRE: {"staggered": 3.0, "pad": 2.0},
    sa.CHORUS: {"pad": 2.0, "riff": 3.0, "hits": 1.5, "call": 1.0},
    sa.REFRAIN: {"pad": 2.0, "riff": 2.0, "call": 1.0},
    OUT_HEAD: {"soli": 2.5, "pad": 1.5, "riff": 2.0, "call": 1.5, "hits": 0.8},
    sa.BRIDGE: {"staggered": 2.0, "pad": 2.0, "solo_pad": 1.5, "rest": 1.0},
    sa.SOLO: {"rest": 4.5, "response": 1.5, "solo_pad": 1.0},
    SOLO_PASS: {"rest": 3.5, "response": 2.5, "solo_pad": 1.5},
    sa.INTERLUDE: {"feature": 3.0, "riff": 2.0, "call": 1.0},
    sa.BREAKDOWN: {"rest": 3.0, "solo_pad": 1.0},
    sa.OUTRO: {"pad": 3.0, "staggered": 1.0},
}
_FINAL_CHORUS_HORNS = {"riff": 3.0, "hits": 2.5, "pad": 1.5, "feature": 0.6}
# How loud the horns play each role (added to their velocity): under a soloist they drop back, the out head
# comes back stronger than the head.
_HORN_DYNAMIC = {SOLO_PASS: -0.12, sa.SOLO: -0.12, sa.BREAKDOWN: -0.08, sa.INTRO: -0.05, sa.VERSE: -0.04, HEAD: 0.0,
                 sa.BRIDGE: -0.02, OUT_HEAD: 0.05, sa.CHORUS: 0.03}


def horn_weights(role: str, energy: float, *, final_chorus: bool, presence: str) -> dict[str, float]:
    w = dict(_FINAL_CHORUS_HORNS if final_chorus else _HORN_ROLE_WEIGHTS.get(role, {"rest": 2.0, "solo_pad": 1.0, "call": 1.0}))
    if energy < 0.4:
        for k in ("riff", "hits"):
            w.pop(k, None)
        w["rest"] = w.get("rest", 0.0) + 1.5
    if presence == "sparse":
        w = {k: (v * (2.5 if k == "rest" else 0.5)) for k, v in w.items()}
        w.setdefault("rest", 1.5)
    elif presence == "solo_space":
        # You are playing a horn yourself: the section only frames the song (intros, outros, the big moments).
        keep = role in (sa.OUTRO,) or final_chorus
        w = {"rest": 1.0} if not keep else {k: v for k, v in w.items() if k in ("pad", "hits", "rest")} or {"rest": 1.0}
    if presence != "normal":
        w.pop("soli", None)  # a written line for both horns is foreground: only at normal presence
    return {k: float(v) for k, v in w.items() if v > 0}


# Rock guitar part per role (backing_rock_guitar.PARTS; "rest" = the guitarist lays out).
def _guitar_part(role: str, energy: float, seed: int, block: int, *, only_chords: bool = False, role_pass: int = 1) -> str:
    if role == sa.INTRO:
        # Piano, bass and drums set the song up; in a trio the guitar is the only chord instrument: it strums it in.
        return "strum" if only_chords else ("arena" if energy >= 0.4 else "rest")
    if role in (sa.VERSE, HEAD):
        if role_pass <= 1 and role == sa.VERSE:
            return "chug"  # the first verse sits under the voice: palm-muted eighths
        return "chug" if _rand(seed, "gtr-verse", role_pass) < 0.4 else "stabs"  # a later verse changes its part
    if role == sa.PRE:
        return "boogie" if _rand(seed, "gtr-pre") < 0.5 else "strum"
    if role in (sa.CHORUS, sa.REFRAIN, OUT_HEAD, sa.INTERLUDE):
        return "strum" if _rand(seed, "gtr-chorus", block % 2) < 0.55 else "arena"
    if role == sa.BRIDGE:
        return "arena"
    if role in (sa.SOLO, SOLO_PASS):
        return "stabs"
    if role in (sa.BREAKDOWN,):
        return "arena" if only_chords else "rest"
    if role == sa.OUTRO:
        return "arena"
    return ""


def _perc_intensity(energy: float) -> str:
    return "Light" if energy < 0.42 else "Heavy" if energy >= 0.72 else "Medium"


def _fill(cur: float, nxt: float | None, *, into_final: bool, ending: bool) -> str:
    if ending:
        return "ending"
    if nxt is None:
        return ""
    jump = nxt - cur
    if into_final or jump >= 0.2:
        return "big"
    if jump >= 0.06:
        return "medium"
    return "small"


# --- Samba: which players of the bateria play each section -------------------------------------------------

SAMBA = "Samba"
# light: surdos, pandeiro and ganza only | tamborim: + the tamborim's teleco-teco | bells: the agogo carries behind a
# soloist, the drums drop back | full: the whole bateria, the high surdo cutting, the pandeiro shaking.
SAMBA_TEXTURES = ("light", "tamborim", "bells", "full")


def _samba_texture(style: str, role: str, p: sa.BarPlace, passes: int, *, last_bar: bool, next_role, next_pass) -> tuple[str, str]:
    if style != SAMBA:
        return "", ""
    if role == HEAD:
        tex = "light" if (p.block == 0 and p.blocks > 1) else "tamborim"  # the A eases in, the tamborim joins for the B
    elif role in (SOLO_PASS, sa.SOLO, sa.BRIDGE, sa.BREAKDOWN):
        tex = "bells"
    elif role in (OUT_HEAD, sa.CHORUS, sa.REFRAIN, sa.OUTRO, sa.INTERLUDE):
        tex = "full"
    elif role == sa.INTRO:
        tex = "light"
    else:
        tex = "tamborim"
    call = ""
    if last_bar:
        if next_role is None:
            call = "ending"  # the last bar: the band's closing figure together, then silence
        elif next_pass is not None and next_pass != p.loop:
            call = "big"  # into a new chorus of the form: the surdos and tamborim call it in
        else:
            call = "small"  # inside a chorus: the tamborim alone marks the new section
    return tex, call


def samba_bass_figure(plan: "ArrangementPlan | None", idx: int) -> str:
    """The Samba bassist's figure for bar ``idx``: "two" (root and the low fifth, no pickups) while the bateria is
    light, "busy" (pickups and approach notes) with the full bateria, "" (as written) otherwise."""
    b = plan.at(idx) if plan is not None and plan.style == SAMBA else None
    if b is None:
        return ""
    return {"light": "two", "full": "busy"}.get(b.perc_texture, "")


# --- Rock: the drummer's and bassist's part per section -----------------------------------------------------

_ROCK_STYLES = frozenset({"Rock groove"})
_ROCK_DB_PER_ENERGY = 7.0  # the band's dynamics with the song: a verse ~1 dB under neutral, a final chorus ~2.4 dB over
_E8 = tuple(i * 0.5 for i in range(8))
_Q = (0.0, 1.0, 2.0, 3.0)


@dataclass(frozen=True)
class KitPart:
    """One bar of a Rock song's drum and bass part (the plan's orchestration of the groove).

    ``cymbal``: what the right hand plays - "hat" (closed hi-hat, as written), "wash" (a half-open hat, choked by the
    next stroke), "ride" or "floor" (the floor tom). ``grid``: (grid key, beats) that replace the groove's for this bar
    (kick, snare, cymbal and bass rhythm). ``crash``: a crash on the downbeat. ``level``: the section's dynamic, x the
    bar's intensity, for the whole band."""

    cymbal: str = "hat"
    grid: tuple = ()
    crash: bool = False
    level: float = 1.0


def kit_part(plan: "ArrangementPlan | None", idx: int) -> KitPart | None:
    if plan is None or plan.style not in _ROCK_STYLES:
        return None
    b = plan.at(idx)
    if b is None:
        return None
    level = float(10 ** (min(3.0, max(-2.0, (b.energy - 0.6) * _ROCK_DB_PER_ENERGY)) / 20.0))
    role, pos = b.role, b.bar_in_section
    seed = plan.seed
    if role in (sa.INTRO, sa.OUTRO, sa.BREAKDOWN, sa.NEUTRAL):
        return KitPart(level=level)  # the approved intro / outro textures (item 34), at the section's level
    if role in (sa.VERSE, HEAD):
        if b.role_pass <= 1:
            # Verse 1: the kick on 1 and 3; the bass in quarter notes under the vocal, moving to eighths for the
            # verse's second half.
            bass = _Q if pos < max(2, b.section_bars // 2) else _E8
            return KitPart(grid=(("kick_beats", (0.0, 2.0)), ("bass_beats", bass)), level=level)
        # Verse 2: the kick pushes the "and" of 3 every other bar, the bass moves to eighths.
        kick = (0.0, 2.0, 2.5) if pos % 2 == 1 else (0.0, 2.0)
        return KitPart(grid=(("kick_beats", kick), ("bass_beats", _E8)), level=level)
    if role == sa.PRE:
        if _rand(seed, "pre-kit") < 0.5:
            # The floor tom takes the eighths: the build everyone knows.
            return KitPart(cymbal="floor", grid=(("kick_beats", (0.0, 2.0)), ("bass_beats", _E8)), level=level)
        # Four on the floor under quarter-note hats.
        return KitPart(grid=(("kick_beats", _Q), ("hat_beats", _Q), ("bass_beats", _E8)), level=level)
    if role in (sa.CHORUS, sa.REFRAIN, OUT_HEAD):
        ride = _rand(seed, "chorus-cymbal") < 0.5
        cymbal = "wash" if (b.final_chorus or not ride) else "ride"
        kick = (0.0, 1.5, 2.0, 2.5)
        crash = b.final_chorus and pos % 4 == 0 and pos > 0  # the last chorus re-crashes each phrase
        return KitPart(cymbal=cymbal, grid=(("kick_beats", kick), ("bass_beats", _E8)), crash=crash, level=level)
    if role == sa.BRIDGE:
        # Half time on the ride: the backbeat on 3, the bass in half notes.
        return KitPart(cymbal="ride", grid=(("kick_beats", (0.0, 1.5)), ("snare_beats", (2.0,)), ("hat_beats", _Q),
                                            ("ghost_snare", ()), ("bass_beats", (0.0, 2.0))), level=level)
    if role in (sa.SOLO, SOLO_PASS, sa.INTERLUDE):
        return KitPart(cymbal="ride", grid=(("bass_beats", _E8),), level=level)
    return KitPart(level=level)


def build(
    chord_list: Sequence[dict],
    cycle_len: int,
    *,
    style: str,
    performance: Any = None,
    seed: int = 0,
    horn_presence: str = "normal",
) -> ArrangementPlan:
    """The arrangement for one render (``chord_list`` = the song x its loops, ``cycle_len`` bars per pass)."""
    places = sa.build_plan(list(chord_list), max(1, int(cycle_len)))
    intensity = str(getattr(performance, "intensity", "") or "Medium")
    presence = horn_presence if horn_presence in _HORN_PRESENCE else "normal"
    passes = max(1, places[-1].loops if places else 1)
    final_chorus_block = None
    chorus_blocks = [(p.loop, p.block) for p in places if p.role == sa.CHORUS]
    if len(set(chorus_blocks)) >= 2:
        final_chorus_block = max(chorus_blocks)
    plays = getattr(performance, "plays", None)
    only_chords = bool(callable(plays) and plays("guitar") and not plays("keys"))
    raw = []
    for idx, (ev, p) in enumerate(zip(chord_list, places)):
        role = _jam_role(style, p.role, p.block, p.blocks, p.loop, passes)
        final = role == sa.CHORUS and (p.loop, p.block) == final_chorus_block
        e = _energy(role, role_pass=p.role_pass + p.loop * p.role_blocks, final_chorus=final, pass_index=p.loop,
                    passes=passes, intensity=intensity, bar=p.bar, bars=p.bars)
        raw.append((idx, ev, p, role, final, e))
    bars: list[BarArrangement] = []
    for k, (idx, ev, p, role, final, e) in enumerate(raw):
        last_bar = p.bar == p.bars - 1
        nxt = raw[k + 1] if k + 1 < len(raw) else None
        ending = nxt is None and (role in (sa.OUTRO, OUT_HEAD) or passes > 1)
        fill = _fill(e, nxt[5] if nxt else None, into_final=bool(nxt and nxt[4] and not final), ending=ending) if last_bar else ""
        # Small moves: more as the song opens up, fewer in quiet sections.
        move_rate = float(min(1.6, max(0.35, 0.45 + 1.1 * e)))
        # The guitarist digs in with the song: a verse sits under its chorus, the last chorus on top.
        guitar_level = float(min(1.12, max(0.7, 0.45 + 0.7 * e)))
        horn_w = horn_weights(role, e, final_chorus=final, presence=presence) if (p.bar % 4 == 0) else {}
        horn_dyn = _HORN_DYNAMIC.get(role, 0.0) + (0.06 if final else 0.0)
        if role == OUT_HEAD and p.bars > 1:
            horn_dyn += 0.04 * p.bar / (p.bars - 1)  # the out head grows to the end
        perc_tex, perc_call = _samba_texture(style, role, p, passes, last_bar=last_bar,
                                             next_role=(nxt[3] if nxt else None), next_pass=(nxt[2].loop if nxt else None))
        bars.append(BarArrangement(
            index=idx, role=role, chart_role=p.role, block=p.block, pass_index=p.loop, passes=passes,
            bar_in_section=p.bar, section_bars=p.bars, energy=e, final_chorus=final, fill=fill, move_rate=move_rate,
            guitar_part=_guitar_part(role, e, seed, p.block, only_chords=only_chords, role_pass=p.role_pass + p.loop * p.role_blocks), guitar_level=guitar_level,
            perc_intensity=_perc_intensity(e), horn_weights=horn_w,
            role_pass=p.role_pass + p.loop * p.role_blocks, horn_dynamic=float(horn_dyn),
            perc_texture=perc_tex, perc_call=perc_call,
        ))
    return ArrangementPlan(str(style), tuple(bars), int(seed), presence)


# --- Textures for the groove knobs ---------------------------------------------------------------------


def bar_texture(plan: ArrangementPlan, idx: int, place: sa.BarPlace) -> sa.SectionTexture | None:
    """The groove texture for bar ``idx``: the chart's (item 34) where it names a role, the plan's for a jam's
    head / solo / out passes and unlabelled verse / chorus feels; ``None`` = the groove as written."""
    b = plan.at(idx)
    base = sa.bar_texture(plan.style, place)
    if b is None:
        return base
    T = sa.SectionTexture
    fam = sa.style_family(plan.style)
    last_bar = b.bar_in_section == b.section_bars - 1
    final_bar = idx == len(plan) - 1
    if final_bar and b.passes > 1:
        return T(b.role, drums="ending", comp="sustain", bass="roots", crash=fam != "light" or plan.style == "Jazz swing",
                 intensity=0.8)
    if base is not None and b.chart_role != sa.NEUTRAL:
        # The chart's textures; a final chorus opens the hats a little more, a repeated verse breathes.
        if b.final_chorus and fam == "strong" and not last_bar:
            return replace(base, open_hat_and4=base.open_hat_and4 or b.bar_in_section % 2 == 1, comp_extra_voice=True)
        return base
    if plan.style == SAMBA and b.perc_texture:
        # The piano follows the bateria: held chords while it eases in, a fuller voicing with the whole section.
        if b.perc_texture == "light":
            return T(b.role, comp="sustain", intensity=0.97)
        if b.perc_texture == "full":
            return T(b.role, comp="full", comp_extra_voice=True, pad=True, intensity=1.02)
        if b.perc_texture == "bells":
            return T(b.role, comp="sparse", intensity=0.98)
    if b.role == HEAD:
        if b.pass_index == 0 and b.block == 0 and b.bar_in_section < 2 and b.passes > 1:
            return T(b.role, comp="sparse", ghosts=False, bass="half" if plan.style == "Jazz swing" else "groove",
                     intensity=0.95)  # the head eases in
        return T(b.role, comp="sparse" if b.energy < 0.5 else "groove")
    if b.role == SOLO_PASS:
        return T(b.role, comp="sparse", intensity=1.0)  # room for the soloist, the band still swinging
    if b.role == OUT_HEAD:
        return T(b.role, comp="full" if fam != "light" else "groove", comp_extra_voice=fam != "light", intensity=1.02)
    if b.chart_role == sa.NEUTRAL and b.role in (sa.VERSE, sa.CHORUS):
        if b.role == sa.VERSE:
            return T(b.role, hats="lighter" if b.energy < 0.4 else "groove", ghosts=b.energy >= 0.45,
                     comp="sparse" if b.energy < 0.4 else "groove")
        return T(b.role, comp_extra_voice=fam == "strong", open_hat_and4=fam == "strong" and b.bar_in_section % 2 == 1,
                 intensity=1.02)
    return base
