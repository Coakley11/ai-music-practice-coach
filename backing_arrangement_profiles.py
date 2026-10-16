"""Song arrangement profiles: per-song groove / feel character as data.

Each :class:`SongArrangement` says *how a song is played* -- drum touch,
pocket, swing, ballad / anthem / groove character, outro fade and which
sections lift or settle. It is matched against the song's title + artist
and applied in table order on top of :data:`DEFAULT_PROFILE`.

An arrangement never decides *what* is played: song, key, BPM, meter and
the chord chart belong to the musical session and are not profile fields
(:data:`PROFILE_FIELDS` is the whole vocabulary, enforced by
:func:`validate_arrangements`). It also never overrides the user's style
choice -- per-style tweaks only refine the style that was picked.

Adding a song: append an entry to :data:`SONG_ARRANGEMENTS`. Matching is
case-insensitive substring matching on ``"<title> <artist>"``: ``match`` is
a tuple of alternatives, each alternative a tuple of terms that must *all*
appear; ``exclude`` terms veto the entry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

DEFAULT_PROFILE: Mapping[str, Any] = MappingProxyType(
    {
        "swing": 0.0,
        "humanize_ms": 0.012,
        "ghost_snare": False,
        "cross_stick": False,
        "ride_jazz": False,
        "pop_soul": False,
        "anthem_rock": False,
        "latin_relaxed": False,
        "kick_push": 1.0,
        "hat_soft": 1.0,
        "comp_stab": False,
        "riff_driven": False,
        "groove_based": False,
        "acoustic_unplugged": False,
        "vocal_ballad": False,
        "broadway_gospel": False,
        "disney_cinematic": False,
        "piano_centric": False,
        "jazz_ballad": False,
        "alt_rock_ballad": False,
        "jewish_traditional": False,
        # Off-beat timing in *beats* (negative = pushed, positive = laid back).
        "pocket_offset": 0.0,
        # Off-beat positions that get an open hi-hat.
        "hat_open_ands": [],
        # Programmed fade over the last N bars (0 = end cold).
        "outro_fade_bars": 0,
        # True when the user picked a style: song tints never replace it.
        "style_locked": False,
        # Song-specific section lifts, see :class:`SectionLift`.
        "section_lifts": (),
        # Layer levels relative to the style's own balance (1.0 = the style).
        # Derived from the character flags in ``song_arrangement_profile``.
        "keys_level": 1.0,
        "strings_level": 1.0,
    }
)

PROFILE_FIELDS = frozenset(DEFAULT_PROFILE)
# Musical-session facts an arrangement must never carry.
SESSION_OWNED_FIELDS = frozenset(
    {"key", "bpm", "tempo", "time_signature", "meter", "chords", "chart", "song", "title", "transpose"}
)


@dataclass(frozen=True)
class SectionLift:
    """Multiply a bar's intensity when it is in one of ``roles`` (verse, pre,
    chorus, bridge, intro, ...) or its section name contains one of
    ``names``; only while every flag in ``requires`` is on."""

    mul: float
    roles: tuple[str, ...] = ()
    names: tuple[str, ...] = ()
    requires: tuple[str, ...] = ()

    def applies(self, profile: Mapping[str, Any], role: str, section_name: str) -> bool:
        if not all(profile.get(f) for f in self.requires):
            return False
        name = str(section_name or "").lower()
        return role in self.roles or any(n in name for n in self.names)


@dataclass(frozen=True)
class Tweak:
    """Field edits: ``flags`` switch on, ``set`` assigns, ``at_least`` /
    ``at_most`` raise / cap a numeric field."""

    flags: tuple[str, ...] = ()
    set: Mapping[str, Any] = field(default_factory=dict)
    at_least: Mapping[str, float] = field(default_factory=dict)
    at_most: Mapping[str, float] = field(default_factory=dict)

    def apply(self, profile: dict[str, Any]) -> None:
        for flag in self.flags:
            profile[flag] = True
        for k, v in self.set.items():
            profile[k] = v
        for k, v in self.at_least.items():
            profile[k] = max(profile[k], v)
        for k, v in self.at_most.items():
            profile[k] = min(profile[k], v)

    def fields(self) -> set[str]:
        return set(self.flags) | set(self.set) | set(self.at_least) | set(self.at_most)


@dataclass(frozen=True)
class SongArrangement:
    name: str
    match: tuple[tuple[str, ...], ...]
    tweak: Tweak
    exclude: tuple[str, ...] = ()
    by_style: Mapping[str, Tweak] = field(default_factory=dict)
    section_lifts: tuple[SectionLift, ...] = ()

    def matches(self, text: str) -> bool:
        if any(x in text for x in self.exclude):
            return False
        return any(all(term in text for term in alt) for alt in self.match)


def _any(*terms: str) -> tuple[tuple[str, ...], ...]:
    return tuple((t,) for t in terms)


_ACOUSTIC_FADE_4 = dict(at_most={"hat_soft": 0.52}, at_least={"humanize_ms": 0.010, "pocket_offset": 0.014}, set={"outro_fade_bars": 4})

SONG_ARRANGEMENTS: tuple[SongArrangement, ...] = (
    SongArrangement(
        "John Mayer pop-soul",
        _any("waiting on the world", "say", "john mayer"),
        Tweak(flags=("pop_soul",), at_least={"swing": 0.03, "pocket_offset": 0.012}, set={"hat_soft": 0.82, "humanize_ms": 0.014}),
    ),
    SongArrangement(
        "Why Georgia (unplugged)",
        _any("why georgia"),
        Tweak(
            flags=("acoustic_unplugged", "pop_soul"),
            at_most={"hat_soft": 0.48},
            at_least={"humanize_ms": 0.012, "pocket_offset": 0.016},
            set={"outro_fade_bars": 8},
        ),
    ),
    SongArrangement(
        "Queen anthem",
        _any("champions", "queen"),
        Tweak(flags=("anthem_rock", "vocal_ballad"), set={"kick_push": 1.28, "outro_fade_bars": 6}, at_least={"humanize_ms": 0.011}),
    ),
    SongArrangement(
        "Thinking Out Loud",
        _any("thinking out loud"),
        Tweak(
            flags=("acoustic_unplugged", "vocal_ballad"),
            at_most={"hat_soft": 0.45},
            at_least={"humanize_ms": 0.010, "pocket_offset": 0.014},
            set={"outro_fade_bars": 4},
        ),
    ),
    SongArrangement(
        "Beatles riff groove",
        _any("come together", "day tripper"),
        Tweak(
            flags=("riff_driven", "comp_stab", "ghost_snare"),
            set={"kick_push": 1.18, "hat_soft": 0.88, "humanize_ms": 0.014, "pocket_offset": 0.016, "outro_fade_bars": 4},
        ),
    ),
    SongArrangement("Day Tripper drive", _any("day tripper"), Tweak(flags=("anthem_rock",), set={"kick_push": 1.22})),
    SongArrangement(
        "Autumn Leaves",
        _any("autumn leaves"),
        Tweak(flags=("cross_stick",), at_most={"hat_soft": 0.48, "humanize_ms": 0.009}, at_least={"pocket_offset": 0.022}),
        by_style={"Jazz swing": Tweak(flags=("ride_jazz",), at_least={"swing": 0.07})},
    ),
    SongArrangement(
        "All the Things You Are",
        _any("all the things", "things you are"),
        Tweak(
            flags=("jazz_ballad", "cross_stick"),
            at_most={"hat_soft": 0.48},
            at_least={"humanize_ms": 0.009, "pocket_offset": 0.022},
        ),
        by_style={
            "Jazz swing": Tweak(flags=("ride_jazz",), at_least={"swing": 0.10}),
            "Bossa nova": Tweak(flags=("latin_relaxed",), at_least={"swing": 0.04}),
        },
    ),
    SongArrangement(
        "Satin Doll",
        _any("satin doll"),
        Tweak(
            flags=("jazz_ballad", "comp_stab"),
            set={"kick_push": 1.08},
            at_most={"hat_soft": 0.90},
            at_least={"humanize_ms": 0.014, "pocket_offset": 0.010},
        ),
        by_style={
            "Jazz swing": Tweak(flags=("ride_jazz",), at_least={"swing": 0.11}),
            "Bossa nova": Tweak(flags=("latin_relaxed", "cross_stick"), at_least={"swing": 0.05, "pocket_offset": 0.016}),
        },
    ),
    SongArrangement(
        "Modern pop / funk groove",
        _any("attention", "treasure", "uptown funk", "get lucky", "charlie puth", "dance monkey", "tones and i", "shape of you"),
        Tweak(
            flags=("groove_based", "comp_stab", "ghost_snare"),
            at_least={"kick_push": 1.14, "humanize_ms": 0.011},
            at_most={"hat_soft": 0.92, "pocket_offset": -0.012},
        ),
    ),
    SongArrangement(
        "I'm Yours (acoustic)",
        _any("i'm yours", "im yours", "jason mraz"),
        Tweak(
            flags=("acoustic_unplugged",),
            at_most={"hat_soft": 0.42},
            at_least={"humanize_ms": 0.010, "pocket_offset": 0.016},
            set={"outro_fade_bars": 4},
        ),
    ),
    SongArrangement(
        "Love Story (acoustic ballad)",
        (("love story",), ("taylor swift", "story")),
        Tweak(flags=("acoustic_unplugged", "vocal_ballad"), **_ACOUSTIC_FADE_4),
    ),
    SongArrangement("Bossa standard", _any("blue bossa", "bossa"), Tweak(flags=("latin_relaxed", "cross_stick"))),
    SongArrangement(
        "Wave (Jobim)",
        (("wave", "jobim"),),
        Tweak(
            flags=("latin_relaxed", "cross_stick", "jazz_ballad"),
            at_most={"hat_soft": 0.40},
            at_least={"humanize_ms": 0.010, "pocket_offset": 0.018},
            set={"outro_fade_bars": 8},
        ),
        by_style={"Ballad": Tweak(at_most={"hat_soft": 0.36}), "Bossa nova": Tweak(at_least={"swing": 0.04})},
    ),
    SongArrangement(
        "Take On Me (MTV Unplugged)",
        (("take on me", "unplugged"), ("take on me", "mtv")),
        Tweak(
            flags=("acoustic_unplugged",),
            at_most={"hat_soft": 0.38},
            at_least={"humanize_ms": 0.010, "pocket_offset": 0.018},
            set={"outro_fade_bars": 8},
        ),
    ),
    SongArrangement(
        "Boy-band ballad",
        _any("want it that way", "backstreet"),
        Tweak(flags=("vocal_ballad",), at_most={"hat_soft": 0.52}, at_least={"humanize_ms": 0.009, "pocket_offset": 0.014}),
    ),
    SongArrangement(
        "Broadway gospel (Hercules)",
        _any("won't say", "wont say", "in love", "hercules", "muses", "megara"),
        Tweak(
            flags=("broadway_gospel", "vocal_ballad", "cross_stick"),
            at_most={"hat_soft": 0.44},
            at_least={"humanize_ms": 0.011, "pocket_offset": 0.016},
        ),
    ),
    SongArrangement(
        "The Scientist",
        _any("scientist"),
        Tweak(
            flags=("vocal_ballad", "piano_centric", "cross_stick"),
            at_most={"hat_soft": 0.38},
            at_least={"humanize_ms": 0.012, "pocket_offset": 0.018},
            set={"outro_fade_bars": 6},
        ),
    ),
    SongArrangement(
        "Cinematic ballad",
        _any("how far", "moana", "let it go", "part of your world", "reflection", "viva la vida", "clocks", "fix you"),
        Tweak(
            flags=("disney_cinematic", "vocal_ballad", "cross_stick"),
            at_most={"hat_soft": 0.40},
            at_least={"humanize_ms": 0.010, "pocket_offset": 0.020},
            set={"outro_fade_bars": 5},
        ),
    ),
    SongArrangement(
        "Billy Joel piano ballad",
        (("vienna",), ("joel", "piano man"), ("joel", "new york state")),
        Tweak(
            flags=("piano_centric", "vocal_ballad", "cross_stick"),
            at_most={"hat_soft": 0.46},
            at_least={"humanize_ms": 0.009, "pocket_offset": 0.022},
            set={"outro_fade_bars": 4},
        ),
    ),
    SongArrangement(
        "All of Me (John Legend)",
        (("all of me", "legend"),),
        Tweak(
            flags=("piano_centric", "vocal_ballad", "cross_stick"),
            at_most={"hat_soft": 0.42},
            at_least={"humanize_ms": 0.009, "pocket_offset": 0.016},
            set={"outro_fade_bars": 8},
        ),
        section_lifts=(
            SectionLift(1.04, roles=("pre",), requires=("piano_centric", "vocal_ballad")),
            SectionLift(1.10, names=("final",), requires=("piano_centric", "vocal_ballad")),
            SectionLift(0.92, names=("outro",), requires=("piano_centric", "vocal_ballad")),
        ),
    ),
    SongArrangement(
        "Imagine",
        (("imagine", "lennon"),),
        Tweak(
            flags=("piano_centric", "vocal_ballad", "cross_stick"),
            at_most={"hat_soft": 0.38},
            at_least={"humanize_ms": 0.010, "pocket_offset": 0.020},
            set={"outro_fade_bars": 6},
        ),
    ),
    SongArrangement(
        "Wonderwall (strummed)",
        _any("wonderwall", "oasis"),
        Tweak(
            flags=("acoustic_unplugged", "comp_stab"),
            at_most={"hat_soft": 0.58},
            at_least={"humanize_ms": 0.011, "pocket_offset": 0.012},
            set={"outro_fade_bars": 8},
        ),
    ),
    SongArrangement(
        "Breakaway (pop ballad)",
        _any("breakaway", "clarkson"),
        Tweak(
            flags=("vocal_ballad",),
            at_least={"kick_push": 1.10, "humanize_ms": 0.010, "pocket_offset": 0.008},
            at_most={"hat_soft": 0.72},
            set={"outro_fade_bars": 2},
        ),
    ),
    SongArrangement(
        "Complicated (acoustic pop-rock)",
        _any("complicated", "avril", "lavigne"),
        Tweak(
            flags=("acoustic_unplugged", "comp_stab"),
            at_least={"kick_push": 1.08, "humanize_ms": 0.011, "pocket_offset": 0.010},
            at_most={"hat_soft": 0.65},
            set={"outro_fade_bars": 8},
        ),
        by_style={"Rock groove": Tweak(flags=("ghost_snare",), at_least={"kick_push": 1.14})},
    ),
    SongArrangement(
        "Iris (alt-rock ballad)",
        _any("iris", "goo goo"),
        Tweak(
            flags=("alt_rock_ballad", "vocal_ballad"),
            at_most={"hat_soft": 0.58},
            at_least={"humanize_ms": 0.010, "kick_push": 1.06, "pocket_offset": 0.012},
            set={"outro_fade_bars": 6},
        ),
    ),
    SongArrangement(
        "Shalom Aleichem (traditional)",
        _any("shalom aleichem"),
        Tweak(
            flags=("jewish_traditional", "cross_stick"),
            at_most={"hat_soft": 0.32},
            at_least={"humanize_ms": 0.011, "pocket_offset": 0.020},
            set={"outro_fade_bars": 3},
        ),
        exclude=("hevenu",),
    ),
    SongArrangement(
        "Heal the World",
        _any("heal the world"),
        Tweak(
            flags=("vocal_ballad", "disney_cinematic", "cross_stick"),
            at_most={"hat_soft": 0.38},
            at_least={"humanize_ms": 0.010, "pocket_offset": 0.018},
            set={"outro_fade_bars": 6},
        ),
        section_lifts=(
            SectionLift(0.90, roles=("verse",), requires=("disney_cinematic",)),
            SectionLift(1.10, roles=("chorus",), names=("final",), requires=("disney_cinematic",)),
            SectionLift(0.88, names=("ending",), requires=("disney_cinematic",)),
        ),
    ),
    SongArrangement(
        "Beat It (riff groove)",
        _any("beat it"),
        Tweak(
            flags=("riff_driven", "groove_based"),
            at_least={"kick_push": 1.22, "humanize_ms": 0.008},
            at_most={"hat_soft": 0.72},
            set={"pocket_offset": 0.0},
        ),
        exclude=("legend",),
        section_lifts=(
            SectionLift(1.12, roles=("chorus",), requires=("groove_based",)),
            SectionLift(1.08, names=("solo",), requires=("groove_based",)),
        ),
    ),
    SongArrangement(
        "Ellington swing",
        _any("take the a train", "ellington"),
        Tweak(flags=("ride_jazz",), set={"swing": 0.12}),
    ),
)


def validate_arrangements(entries: tuple[SongArrangement, ...] = SONG_ARRANGEMENTS) -> list[str]:
    """Problems in the table (empty when it is sound)."""
    problems: list[str] = []
    for e in entries:
        tweaks = [e.tweak, *e.by_style.values()]
        for t in tweaks:
            for f in t.fields():
                if f in SESSION_OWNED_FIELDS:
                    problems.append(f"{e.name}: '{f}' belongs to the musical session")
                elif f not in PROFILE_FIELDS:
                    problems.append(f"{e.name}: unknown field '{f}'")
        for lift in e.section_lifts:
            for f in lift.requires:
                if f not in PROFILE_FIELDS:
                    problems.append(f"{e.name}: lift requires unknown flag '{f}'")
        if not e.match or any(not alt for alt in e.match):
            problems.append(f"{e.name}: empty match")
    return problems


def matching_arrangements(song_title: str, song_artist: str) -> list[SongArrangement]:
    text = f"{song_title} {song_artist}".lower()
    return [e for e in SONG_ARRANGEMENTS if e.matches(text)]


def song_arrangement_profile(song_title: str, song_artist: str, style: str, *, bpm: int = 100) -> dict[str, Any]:
    """Resolve the arrangement profile for a song played in ``style``."""
    profile = dict(DEFAULT_PROFILE)
    profile["hat_open_ands"] = []
    lifts: list[SectionLift] = []
    for entry in matching_arrangements(song_title, song_artist):
        entry.tweak.apply(profile)
        style_tweak = entry.by_style.get(style)
        if style_tweak is not None:
            style_tweak.apply(profile)
        lifts.extend(entry.section_lifts)
    if bpm >= 120 and profile["anthem_rock"]:
        profile["kick_push"] *= 1.05
    profile["section_lifts"] = tuple(lifts)
    _derive_layer_levels(profile)
    return profile


def _derive_layer_levels(profile: dict[str, Any]) -> None:
    """Who carries the song: a piano ballad puts the piano forward; the
    optional strings swell under cinematic / vocal ballads and stay out of
    the way of riff and groove songs."""
    if profile["piano_centric"]:
        profile["keys_level"] = 1.25
    strings_level = 1.0
    if profile["disney_cinematic"]:
        strings_level = 1.25
    elif profile["vocal_ballad"]:
        strings_level = 1.1
    if profile["groove_based"] or profile["riff_driven"]:
        strings_level *= 0.8
    profile["strings_level"] = strings_level


def apply_section_lifts(profile: Mapping[str, Any], role: str, section_name: str, intensity: float) -> float:
    """``intensity`` after the song's section lifts that apply to this bar."""
    for lift in profile.get("section_lifts", ()) or ():
        if lift.applies(profile, role, section_name):
            intensity *= lift.mul
    return intensity
