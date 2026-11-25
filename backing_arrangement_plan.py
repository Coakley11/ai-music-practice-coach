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

PLAN_VERSION = 1
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
    perc_intensity: str = "Medium"  # the Samba / Latin percussion section's intensity here
    horn_weights: dict = field(default_factory=dict)  # texture -> weight for the horn phrase starting here

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
    HEAD: {"rest": 2.0, "solo_pad": 2.0, "staggered": 1.5, "call": 2.0},
    sa.PRE: {"staggered": 3.0, "pad": 2.0},
    sa.CHORUS: {"pad": 2.0, "riff": 3.0, "hits": 1.5, "call": 1.0},
    sa.REFRAIN: {"pad": 2.0, "riff": 2.0, "call": 1.0},
    OUT_HEAD: {"pad": 2.0, "riff": 2.5, "call": 2.0, "hits": 1.0},
    sa.BRIDGE: {"staggered": 2.0, "pad": 2.0, "solo_pad": 1.5, "rest": 1.0},
    sa.SOLO: {"rest": 5.0, "solo_pad": 1.0},
    SOLO_PASS: {"rest": 4.0, "solo_pad": 1.5, "pad": 0.8},
    sa.INTERLUDE: {"feature": 3.0, "riff": 2.0, "call": 1.0},
    sa.BREAKDOWN: {"rest": 3.0, "solo_pad": 1.0},
    sa.OUTRO: {"pad": 3.0, "staggered": 1.0},
}
_FINAL_CHORUS_HORNS = {"riff": 3.0, "hits": 2.5, "pad": 1.5, "feature": 0.6}


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
    return {k: float(v) for k, v in w.items() if v > 0}


# Rock guitar part per role (backing_rock_guitar.PARTS; "rest" = the guitarist lays out).
def _guitar_part(role: str, energy: float, seed: int, block: int) -> str:
    if role == sa.INTRO:
        return "rest" if energy < 0.4 else "arena"
    if role in (sa.VERSE, HEAD):
        return "chug" if _rand(seed, "gtr-verse") < 0.6 else "stabs"
    if role == sa.PRE:
        return "boogie" if _rand(seed, "gtr-pre") < 0.5 else "strum"
    if role in (sa.CHORUS, sa.REFRAIN, OUT_HEAD, sa.INTERLUDE):
        return "strum" if _rand(seed, "gtr-chorus", block % 2) < 0.55 else "arena"
    if role == sa.BRIDGE:
        return "arena"
    if role in (sa.SOLO, SOLO_PASS):
        return "stabs"
    if role in (sa.BREAKDOWN,):
        return "rest"
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
        horn_w = horn_weights(role, e, final_chorus=final, presence=presence) if (p.bar % 4 == 0) else {}
        bars.append(BarArrangement(
            index=idx, role=role, chart_role=p.role, block=p.block, pass_index=p.loop, passes=passes,
            bar_in_section=p.bar, section_bars=p.bars, energy=e, final_chorus=final, fill=fill, move_rate=move_rate,
            guitar_part=_guitar_part(role, e, seed, p.block), perc_intensity=_perc_intensity(e), horn_weights=horn_w,
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
