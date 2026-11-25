"""Backing Engine 2.0 - how the musician's choices become a band's performance.

Style Jam and the Jam Session Generator hand the engine a style, a mood, a groove intensity, a
difficulty and (Jam Session Generator) an ensemble. Before this module the engine turned mood and
intensity into a handful of volume scalars, most of which the loudness match and the groove grid then
undid: the recorded pianist played the same notes for every mood, and Light and Heavy only differed
in a few ghost snares. A :class:`PerformancePlan` is the one place where those choices are decided as
*playing*:

* **who plays** - the ensemble's real roster (a Rock trio has no piano; a Lo-fi duo is keys and a
  beat). A member with no renderer yet is reported in :attr:`PerformancePlan.unavailable`, never
  rendered as a silent placeholder, and never relabelled as something else;
* **how much they play** - groove intensity, through the section-texture vocabulary every player
  already reads (:class:`backing_section_arrangement.SectionTexture`): a Light band thins the kit,
  comps sparsely and plays a two-feel; a Heavy band doubles the hats, comps fuller and drives the bass;
* **how they play it** - mood, as articulation (note length), touch (velocity, which changes the
  recorded instruments' timbre, not only their level), register, fills, anticipations and rolled
  chords; independent of intensity, so Mellow + Heavy and Energetic + Light are both possible;
* **what they know** - difficulty, as harmonic colour and rhythmic sophistication of the
  accompaniment (never faster or louder).

The plan is opt-in: :func:`backing_audio.synthesize_chords_to_numpy` uses it only when one is passed,
so Catalog, Custom, Composition and Song-Based Improvisation songs render exactly as before. It never
changes chords, key, tempo, meter or form, and the final loudness match keeps every take at the same
loudness, so what changes is the arrangement, not the volume.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

__all__ = (
    "ENSEMBLES",
    "PLAN_VERSION",
    "PerformancePlan",
    "RolePerformance",
    "resolve_performance_plan",
)

PLAN_VERSION = 1

# Roles the engine can render today. "horns" and "percussion" are known members of real ensembles
# with no renderer yet: they are listed as unavailable, not faked.
RENDERABLE_ROLES = frozenset({"drums", "bass", "keys", "guitar"})


@dataclass(frozen=True)
class RolePerformance:
    """How one player plays. 1.0 / 0 everywhere = the style's own way of playing."""

    plays: bool = True
    density: float = 1.0  # how many notes: < 1 leaves room, > 1 plays more
    velocity: float = 1.0  # touch; recorded instruments pick a softer or harder sample layer
    length: float = 1.0  # articulation: < 1 short and detached, > 1 legato / ringing
    register: int = 0  # semitones the part's centre moves (bright up, dark down)
    colour: str = "style"  # chord colour: "plain" (triads / 7ths), "style", "rich" (9ths, 13ths)
    fills: float = 1.0  # chance of fills and figures at phrase ends
    push: float = 1.0  # chance of anticipating the next chord
    space: float = 1.0  # chance of leaving a hit out for air
    roll: float = 0.0  # extra seconds between the notes of a chord (a spread, dreamy chord)
    motion: float = 1.0  # rhythmic life: contrasting bars, displaced hits, answering hits


@dataclass(frozen=True)
class EnsembleSpec:
    roles: tuple[str, ...]  # members that play, in renderable roles
    missing: tuple[str, ...] = ()  # members the engine cannot render yet (reported, never faked)
    note: str = ""
    horns: tuple[str, ...] = ()  # the recorded horns (backing_horns.HORNS) its "horns" member plays, top first


# The Jam Session Generator's ensembles (improvisation_intelligence_ui: "Ensemble" selectbox).
ENSEMBLES: dict[str, EnsembleSpec] = {
    "Jazz trio": EnsembleSpec(("keys", "bass", "drums"), note="piano, upright bass, drums"),
    "Jazz quartet": EnsembleSpec(
        ("keys", "bass", "drums"), ("horns",),
        note="piano, upright bass, drums; the horn is the recorded tenor sax (MUSIC_HORNS)",
        horns=("tenor",),
    ),
    # Offered only while both horns have working audio (jam_control_ownership.jam_ensembles).
    "Jazz quintet": EnsembleSpec(
        ("keys", "bass", "drums"), ("horns",),
        note="trumpet and tenor sax over piano, upright bass and drums (MUSIC_HORNS); backing_horn_arranger",
        horns=("trumpet", "tenor"),
    ),
    "Neo-soul band": EnsembleSpec(
        ("keys", "bass", "drums"), ("guitar",),
        note="keys, bass, drums; a neo-soul guitar part needs its own renderer",
    ),
    "Rock trio": EnsembleSpec(("guitar", "bass", "drums"), note="electric guitar, bass, drums - no piano"),
    "Latin quartet": EnsembleSpec(
        ("keys", "bass", "drums"), ("percussion",),
        note="piano, bass, drums; congas / bongos / timbales need percussion samples first",
    ),
    "Lo-fi duo": EnsembleSpec(("keys", "drums"), note="keys and a soft beat; the keys' left hand carries the low end"),
}

# The styles whose guitar renderer exists today (backing_rock_guitar: power chords, riffs, strums).
_GUITAR_STYLES = frozenset({"Rock groove"})

# --- Mood: character, independent of how busy the band is ---------------------------------------------
# keys / bass / drums performance changes per mood. Velocity < 1 is a softer touch (and a softer sample
# layer), length > 1 lets notes ring, register moves the keys' centre.
_MOOD: dict[str, dict[str, dict[str, Any]]] = {
    "Mellow": {
        "keys": dict(velocity=0.80, length=1.18, fills=0.7, push=0.6, space=1.1, motion=0.75),
        "bass": dict(velocity=0.85, length=1.12),
        "drums": dict(velocity=0.78, fills=0.6),
    },
    "Relaxed": {
        "keys": dict(velocity=0.82, length=1.15, fills=0.7, push=0.6, space=1.15, motion=0.75),
        "bass": dict(velocity=0.86, length=1.1),
        "drums": dict(velocity=0.8, fills=0.6),
    },
    "Bright": {
        "keys": dict(velocity=0.98, length=0.95, register=4, colour="rich", fills=1.1, motion=1.15),
        "bass": dict(velocity=1.0),
        "drums": dict(velocity=1.0, fills=1.0),
    },
    "Dark": {
        "keys": dict(velocity=0.86, length=1.1, register=-5, space=1.2, fills=0.7, push=0.8, motion=0.9),
        "bass": dict(velocity=0.92, length=1.1),
        "drums": dict(velocity=0.84, fills=0.7),
    },
    "Energetic": {
        "keys": dict(velocity=1.06, length=0.8, push=1.8, fills=1.4, space=0.8, motion=1.7),
        "bass": dict(velocity=1.06, length=0.85, density=1.1),
        "drums": dict(velocity=1.06, fills=1.6),
    },
    "Dreamy": {
        "keys": dict(velocity=0.72, length=1.7, register=3, space=1.4, fills=0.4, push=0.4, roll=0.035, motion=0.45),
        "bass": dict(velocity=0.8, length=1.3, density=0.85),
        "drums": dict(velocity=0.7, fills=0.3),
    },
    "Gritty": {
        "keys": dict(velocity=1.12, length=0.8, colour="plain", fills=1.1, push=1.2, motion=1.25),
        "bass": dict(velocity=1.1, length=0.8),
        "drums": dict(velocity=1.14, fills=1.25),
    },
}

# --- Groove intensity: how much the band plays (the arrangement, not the loudness) -----------------------
_INTENSITY: dict[str, dict[str, dict[str, Any]]] = {
    "Light": {
        "keys": dict(density=0.6, space=1.6),
        "bass": dict(density=0.75),
        "drums": dict(density=0.6, fills=0.6),
    },
    "Medium": {},
    "Heavy": {
        "keys": dict(density=1.3, space=0.5, fills=1.3),
        "bass": dict(density=1.15),
        "drums": dict(density=1.3, fills=1.5),
    },
}

# --- Difficulty: harmonic and rhythmic sophistication of the accompaniment --------------------------------
_LEVEL: dict[str, dict[str, dict[str, Any]]] = {
    "Beginner": {"keys": dict(colour="plain", push=0.3, fills=0.5, motion=0.5), "drums": dict(fills=0.6)},
    "Intermediate": {},
    "Advanced": {"keys": dict(colour="rich", push=1.6, fills=1.6, motion=1.6, space=0.85), "drums": dict(fills=1.4)},
}

# Styles whose bass plays a two-feel when the band is Light (half notes; a walking or groove line otherwise).
_TWO_FEEL_STYLES = frozenset({"Jazz swing", "Ballad", "Blues groove", "Pop groove"})
# Styles whose hats may double when Heavy (a ride / bossa pattern doubled is not a heavier groove).
_DENSER_HAT_STYLES = frozenset({"Pop groove", "Rock groove", "Funk groove", "Blues groove"})
# Moods that drive: a light band keeps its hats moving and a heavy band adds drive on top. The others stay
# relaxed at every intensity: a heavy Mellow band is fuller and warmer, not busier on top.
_DRIVING_MOODS = frozenset({"Energetic", "Gritty", "Bright"})


def _norm(text: Any, choices, default: str) -> str:
    raw = str(text or "").strip()
    for c in choices:
        if raw.lower() == c.lower():
            return c
    return default


def _merge(base: RolePerformance, change: dict[str, Any]) -> RolePerformance:
    out = {}
    for k, v in change.items():
        cur = getattr(base, k)
        if k in ("velocity", "length", "fills", "push", "space", "density", "motion"):
            out[k] = float(cur) * float(v)
        elif k in ("register",):
            out[k] = int(cur) + int(v)
        elif k == "roll":
            out[k] = max(float(cur), float(v))
        elif k == "colour":
            # Difficulty decides harmony last: a Beginner never gets 13ths, an Advanced player keeps them.
            out[k] = v
        else:
            out[k] = v
    return replace(base, **out)


@dataclass(frozen=True)
class PerformancePlan:
    style: str
    mood: str
    intensity: str
    level: str
    ensemble: str
    roles: tuple[str, ...]
    keys: RolePerformance = field(default_factory=RolePerformance)
    bass: RolePerformance = field(default_factory=RolePerformance)
    drums: RolePerformance = field(default_factory=RolePerformance)
    guitar: RolePerformance = field(default_factory=RolePerformance)
    unavailable: tuple[str, ...] = ()
    fallbacks: tuple[str, ...] = ()
    horns: tuple[str, ...] = ()  # the recorded horns playing the "horns" role, top first (empty: no horns)

    def plays(self, role: str) -> bool:
        return role in self.roles

    def tag(self) -> str:
        """Part of the take's identity: a different plan is a different take, never a replayed one."""
        # Two horns are a written arrangement (backing_horn_arranger): its version is part of the take. One
        # horn (the quartet's tenor) keeps the tag it always had.
        horns = ""
        if self.plays("horns") and len(self.horns) > 1:
            from backing_horn_arranger import arranger_tag

            horns = arranger_tag(self.horns[0], self.horns[1])
        return (
            f"+perf{PLAN_VERSION}-{self.mood[:3]}{self.intensity[:1]}{self.level[:1]}"
            f"-{'.'.join(r[0] for r in self.roles)}{horns}"
        )

    def texture(self, base, role: str):
        """The section texture for one bar with the groove intensity applied on top of the song's own.

        ``base`` is the section-aware texture (or ``None`` for an unlabelled section); the result keeps the
        song's section decisions (an intro still enters lightly, an ending still ends) and moves the whole
        band lighter or fuller around them.
        """
        from backing_section_arrangement import SectionTexture

        tex = base if base is not None else SectionTexture(role or "neutral")
        if base is not None and base.drums == "ending":
            return base  # the ending is the ending at every intensity
        driving = self.mood in _DRIVING_MOODS
        two_feel = self.style in _TWO_FEEL_STYLES and tex.bass == "groove"
        if self.intensity == "Light":
            return replace(
                tex,
                drums="light" if tex.drums == "groove" else tex.drums,
                hats=tex.hats if driving else "lighter",
                ghosts=False,
                open_hat_and4=False,
                comp="sparse" if tex.comp in ("groove", "full") else tex.comp,
                comp_extra_voice=False,
                pad=False,
                bass="half" if two_feel else tex.bass,
                bass_density=tex.bass_density * self.bass.density,
            )
        # A beginner jam: a clear two-feel bass where the style has one.
        beginner_bass = "half" if (self.level == "Beginner" and two_feel) else tex.bass
        if self.intensity == "Heavy":
            chorus = role in ("chorus", "refrain", "interlude", "outro")
            return replace(
                tex,
                hats="denser" if (driving and self.style in _DENSER_HAT_STYLES and tex.hats == "groove" and tex.drums == "groove") else tex.hats,
                ghosts=True if tex.drums == "groove" else tex.ghosts,
                open_hat_and4=tex.open_hat_and4 or (driving and chorus and self.style in _DENSER_HAT_STYLES),
                comp="full" if tex.comp == "groove" else tex.comp,
                comp_extra_voice=True if tex.comp in ("groove", "full") else tex.comp_extra_voice,
                bass=beginner_bass,
                bass_density=tex.bass_density * self.bass.density,
            )
        if base is None and self.bass.density == 1.0 and beginner_bass == tex.bass:
            return None
        return replace(tex, bass=beginner_bass, bass_density=tex.bass_density * self.bass.density)

    def describe(self) -> dict[str, Any]:
        return {
            "style": self.style, "mood": self.mood, "intensity": self.intensity, "level": self.level,
            "ensemble": self.ensemble, "roles": list(self.roles), "unavailable": list(self.unavailable),
            "fallbacks": list(self.fallbacks), "horns": list(self.horns),
            "keys": self.keys.__dict__, "bass": self.bass.__dict__, "drums": self.drums.__dict__,
        }


def resolve_performance_plan(
    *,
    style: str,
    mood: str = "",
    intensity: str = "",
    level: str = "",
    ensemble: str = "",
    guitar_available: bool | None = None,
) -> PerformancePlan:
    """The band's performance for one generated jam.

    ``style`` is the engine groove (``songs.playback_defaults.GROOVE_STYLE_CHOICES``). ``ensemble`` is one of
    :data:`ENSEMBLES` (Jam Session Generator) or empty (Style Jam: the style's own band). ``guitar_available``
    defaults to whether the recorded guitar is switched on: a Rock trio without a guitar renderer keeps its
    piano rather than playing as a duo, and says so in :attr:`PerformancePlan.fallbacks`.
    """
    mood_n = _norm(mood, _MOOD, "Mellow")
    inten_n = _norm(intensity, _INTENSITY, "Medium")
    level_n = _norm(level, _LEVEL, "Intermediate")
    ens_n = _norm(ensemble, ENSEMBLES, "")
    if guitar_available is None:
        try:
            import backing_rock_guitar as _rg

            guitar_available = bool(_rg.enabled())
        except ImportError:
            guitar_available = False

    fallbacks: list[str] = []
    horns: tuple[str, ...] = ()
    if ens_n:
        spec = ENSEMBLES[ens_n]
        roles = list(spec.roles)
        missing = list(spec.missing)
        if "horns" in missing and _horns_playable(spec.horns or ("tenor",)):
            # MUSIC_HORNS: the recorded horns play the part; never claimed without every one of them.
            missing.remove("horns")
            roles.append("horns")
            horns = tuple(spec.horns or ("tenor",))
    else:
        roles = ["keys", "bass", "drums"]
        missing = []
        if style in _GUITAR_STYLES and guitar_available:
            roles.append("guitar")
    if "guitar" in roles and not (guitar_available and style in _GUITAR_STYLES):
        roles.remove("guitar")
        missing.append("guitar")
        if "keys" not in roles:
            roles.insert(0, "keys")
            fallbacks.append("keys instead of guitar (no guitar renderer for this style / switch off)")
    if _latin_percussion_plays(style):
        # MUSIC_LATIN_GROOVES: the recorded percussionist plays this groove, whatever the band: it is named as
        # playing, never as missing.
        if "percussion" in missing:
            missing.remove("percussion")
        roles.append("percussion")

    perf = {r: RolePerformance(plays=r in roles) for r in ("keys", "bass", "drums", "guitar")}
    for table, key in ((_MOOD, mood_n), (_INTENSITY, inten_n), (_LEVEL, level_n)):
        for role, change in table.get(key, {}).items():
            perf[role] = _merge(perf[role], change)
    return PerformancePlan(
        style=str(style), mood=mood_n, intensity=inten_n, level=level_n, ensemble=ens_n,
        roles=tuple(r for r in ("keys", "guitar", "horns", "bass", "drums", "percussion") if r in roles),
        keys=perf["keys"], bass=perf["bass"], drums=perf["drums"], guitar=perf["guitar"],
        unavailable=tuple(missing), fallbacks=tuple(fallbacks), horns=horns,
    )


def _horns_playable(names: tuple[str, ...] = ("tenor",)) -> bool:
    """The horn part has working audio: ``MUSIC_HORNS`` is on and every named horn's pack is present."""
    try:
        import backing_horns as _bh

        return bool(_bh.enabled()) and all(_bh.available(n) for n in names)
    except (ImportError, ValueError):
        return False


def ensemble_playable(name: str) -> bool:
    """Whether a horn ensemble's horns can all be heard. Other ensembles are always offered (their missing
    members are named as unavailable); a two-horn ensemble exists only for its horns, so without them it is not."""
    spec = ENSEMBLES.get(str(name or ""))
    if spec is None:
        return False
    if len(spec.horns) < 2:
        return True
    return _horns_playable(spec.horns)


def _latin_percussion_plays(style: str) -> bool:
    """The recorded Latin percussionist plays ``style`` (backing_latin_percussion: switch on, pack present)."""
    try:
        import backing_latin_percussion as _lp

        return bool(_lp.plays(str(style)))
    except ImportError:
        return False


# Rollback switch for the jam wiring (slice 2). Generated jams use their plan unless this is set to
# "off"; songs never get one, whatever it says.
JAM_PERFORMANCE_SWITCH = "MUSIC_JAM_PERFORMANCE"


def jam_performance_enabled() -> bool:
    import os

    return str(os.environ.get(JAM_PERFORMANCE_SWITCH, "on") or "on").strip().lower() not in {
        "0", "off", "false", "no",
    }


def performance_plan_for_backing_context(ctx: Any, *, style: str) -> PerformancePlan | None:
    """The plan for the take the Backing page is about to build, or ``None`` (unchanged sound).

    Only a generated jam (``source == "entry_jam"``: Entry & Style Jam, Jam Session Generator) gets a
    plan; Catalog, Custom, Composition, Karaoke, Missions and Song-Based Improvisation get ``None`` and
    render byte-for-byte as before. ``style`` is the groove the engine will actually play (the Backing
    Feel), so the plan and the audio can never disagree about the style. Mood, intensity, difficulty
    and ensemble are the jam's own, as sealed into its Backing context.
    """
    if ctx is None or str(getattr(ctx, "source", "") or "") != "entry_jam":
        return None
    if not jam_performance_enabled():
        return None
    return resolve_performance_plan(
        style=str(style or getattr(ctx, "style", "") or ""),
        mood=str(getattr(ctx, "mood", "") or ""),
        intensity=str(getattr(ctx, "groove_intensity", "") or ""),
        level=str(getattr(ctx, "difficulty", "") or ""),
        ensemble=str(getattr(ctx, "ensemble", "") or ""),
    )


_ROLE_NAMES = {"keys": "piano", "guitar": "guitar", "bass": "bass", "drums": "drums", "horns": "tenor sax",
               "percussion": "Latin percussion"}
_HORN_NAMES = {"tenor": "tenor sax", "trumpet": "trumpet", "trombone": "trombone"}


def role_names(plan: PerformancePlan) -> list[str]:
    """The players the engine renders for ``plan``, by instrument ("trumpet", "tenor sax", "piano", ...)."""
    out: list[str] = []
    for r in plan.roles:
        if r == "horns" and plan.horns:
            out.extend(_HORN_NAMES.get(h, h) for h in plan.horns)
        else:
            out.append(_ROLE_NAMES.get(r, r))
    return out
_MISSING_NAMES = {"horns": "horns", "percussion": "Latin percussion", "guitar": "guitar"}


def band_summary(plan: PerformancePlan | None) -> str:
    """What the Backing card says the band is: exactly the roles the engine renders.

    A member the ensemble calls for but no renderer plays yet is named as not available, never
    implied ("piano, bass, drums · horns not available yet").
    """
    if plan is None:
        return ""
    playing = ", ".join(role_names(plan))
    text = playing[:1].upper() + playing[1:]
    missing = [_MISSING_NAMES.get(m, m) for m in plan.unavailable]
    if missing:
        text += " · " + " & ".join(missing) + " not available yet"
    return text
