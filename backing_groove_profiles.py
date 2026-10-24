"""Groove profiles: how a song's drums, bass and comp move, as data.

A style recipe (:mod:`backing_style_recipes`) is the grammar a style shares;
a groove profile is one concrete way of playing it -- a cinematic ballad that
holds the kit back until the chorus, a dance-pop tresillo with offbeat hats, a
rock drive, a bossa clave. Songs that share a grammar share a profile; a song
that needs its own treatment names one.

A profile carries:

* ``grid`` -- the bar's rhythm (4/4 beat offsets) for kick, snare, hats, ghost
  notes, cross-stick, bass and comp, replacing the recipe's grid;
* ``by_role`` -- per-section-role changes to that grid (a thinner verse, a
  fuller chorus, a held-back intro);
* ``hat_accents`` -- velocity shape over the hat pattern (accented downbeats,
  softer offbeats) so a straight grid still breathes;
* ``fill`` / ``phrase_fill_bars`` -- which fill closes a section and how often
  a lighter fill closes a phrase inside one;
* ``role_dynamics`` -- intensity per section role;
* ``flags`` -- synthesis feel (pocket, swing, humanize, hat / kick weight);
* ``half_time_from_bpm`` / ``sixteenth_hats_to_bpm`` -- tempo-aware variants.

Resolution (:func:`resolve_groove_profile`): the song's own profile when it
refines the style being played, else the style's default profile, else none
(the recipe grid alone). A profile never changes key, tempo, meter or chords,
and never overrides the user's choice of style -- it only refines it.
Rendering stays deterministic: every hit is seeded from the song, bar and beat.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

GRID_KEYS = (
    "kick_beats",
    "snare_beats",
    "hat_beats",
    "ghost_snare",
    "cross_stick",
    "bass_beats",
    "comp_beats",
)
FILL_TYPES = frozenset({"none", "pickup", "snare_roll", "tom_run", "swell"})
ROLES = frozenset({"intro", "verse", "pre", "chorus", "bridge", "outro", "neutral"})


def _frozen(mapping: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return MappingProxyType(dict(mapping or {}))


@dataclass(frozen=True)
class GrooveProfile:
    id: str
    style: str
    summary: str
    grid: Mapping[str, Any]
    by_role: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    hat_accents: tuple[float, ...] = ()
    fill: str = "snare_roll"
    phrase_fill_bars: int = 0
    role_dynamics: Mapping[str, float] = field(default_factory=dict)
    flags: Mapping[str, Any] = field(default_factory=dict)
    half_time_from_bpm: int = 0
    sixteenth_hats_to_bpm: int = 0

    def bar_grid(self, base: Mapping[str, Any], role: str, *, bpm: int) -> dict[str, Any]:
        """The rhythm for one bar in ``role`` (4/4 beat offsets)."""
        out = dict(base)
        for key, val in self.grid.items():
            out[key] = list(val) if isinstance(val, (list, tuple)) else val
        for key, val in (self.by_role.get(role) or {}).items():
            out[key] = list(val) if isinstance(val, (list, tuple)) else val
        if self.half_time_from_bpm and bpm >= self.half_time_from_bpm and out.get("snare_beats"):
            # Fast tempo: the backbeat moves to beat 3 so the groove feels half-time.
            out["snare_beats"] = [2.0]
        if self.sixteenth_hats_to_bpm and bpm <= self.sixteenth_hats_to_bpm and out.get("hat_beats"):
            out["hat_beats"] = [i * 0.25 for i in range(16)]
        return out

    def hat_accent(self, beat: float) -> float:
        """Velocity multiplier for a hat at ``beat`` (cycles over 8th positions)."""
        if not self.hat_accents:
            return 1.0
        idx = int(round(float(beat) * 2)) % len(self.hat_accents)
        return float(self.hat_accents[idx])

    def dynamics(self, role: str) -> float:
        return float(self.role_dynamics.get(role, 1.0))


def _p(id: str, style: str, summary: str, grid: Mapping[str, Any], **kw: Any) -> GrooveProfile:
    return GrooveProfile(
        id=id,
        style=style,
        summary=summary,
        grid=_frozen(grid),
        by_role=_frozen({k: _frozen(v) for k, v in (kw.pop("by_role", {}) or {}).items()}),
        role_dynamics=_frozen(kw.pop("role_dynamics", {})),
        flags=_frozen(kw.pop("flags", {})),
        **kw,
    )


_QUARTERS = (0.0, 1.0, 2.0, 3.0)
_EIGHTHS = tuple(i * 0.5 for i in range(8))

GROOVE_PROFILES: Mapping[str, GrooveProfile] = MappingProxyType(
    {
        p.id: p
        for p in (
            _p(
                "cinematic_ballad",
                "Ballad",
                "Lyrical, spacious ballad: the kit waits, cross-stick and soft quarter hats "
                "carry the verse, a half-time kick/snare opens up the chorus, long held comp.",
                {
                    "kick_beats": (0.0,),
                    "snare_beats": (),
                    "cross_stick": (2.0,),
                    "hat_beats": _QUARTERS,
                    "ghost_snare": (),
                    "bass_beats": (0.0,),
                    "comp_beats": (0.0, 2.0),
                    "comp_dur": 1.6,
                },
                by_role={
                    "intro": {"kick_beats": (), "cross_stick": (), "hat_beats": (0.0, 2.0)},
                    "verse": {"hat_beats": (0.0, 2.0)},
                    "pre": {"kick_beats": (0.0, 2.5), "cross_stick": (1.0, 3.0)},
                    "chorus": {"kick_beats": (0.0, 1.5, 2.5), "snare_beats": (2.0,), "cross_stick": (), "bass_beats": (0.0, 2.0, 3.5)},
                    "bridge": {"kick_beats": (0.0, 2.5), "snare_beats": (2.0,), "cross_stick": ()},
                    "outro": {"kick_beats": (0.0,), "snare_beats": (), "cross_stick": (2.0,), "hat_beats": (0.0, 2.0)},
                },
                hat_accents=(1.0, 0.6),
                fill="swell",
                phrase_fill_bars=0,
                role_dynamics={"intro": 0.72, "verse": 0.8, "pre": 0.95, "chorus": 1.15, "bridge": 1.2, "outro": 0.78},
                flags={"hat_soft": 0.62, "pocket_offset": 0.018, "humanize_ms": 0.010},
            ),
            _p(
                "piano_ballad",
                "Ballad",
                "Piano-led ballad: soft kick on 1, cross-stick on 3, quarter hats, sustained comp.",
                {
                    "kick_beats": (0.0,),
                    "snare_beats": (),
                    "cross_stick": (2.0,),
                    "hat_beats": _QUARTERS,
                    "bass_beats": (0.0, 2.0),
                    "comp_beats": (0.0, 2.0, 3.5),
                    "comp_dur": 1.2,
                },
                by_role={
                    "chorus": {"kick_beats": (0.0, 2.5), "snare_beats": (2.0,), "cross_stick": ()},
                    "bridge": {"kick_beats": (0.0, 2.5), "snare_beats": (2.0,), "cross_stick": ()},
                },
                hat_accents=(1.0, 0.65),
                fill="swell",
                role_dynamics={"verse": 0.86, "chorus": 1.1, "outro": 0.85},
                flags={"hat_soft": 0.6, "pocket_offset": 0.016},
            ),
            _p(
                "dance_pop",
                "Pop groove",
                "Upbeat dance-pop: tresillo kick and bass (3+3+2), claps on 2 and 4, accented "
                "offbeat hats, syncopated short comp stabs; verse strips back, chorus drives.",
                {
                    "kick_beats": (0.0, 1.5, 3.0),
                    "snare_beats": (1.0, 3.0),
                    "hat_beats": _EIGHTHS,
                    "ghost_snare": (3.75,),
                    "bass_beats": (0.0, 1.5, 3.0),
                    "comp_beats": (0.0, 0.75, 1.5, 2.25, 3.0),
                    "comp_dur": 0.22,
                    "hat_open_ands": (1.5, 3.5),
                },
                by_role={
                    "intro": {"kick_beats": (), "snare_beats": (), "hat_beats": (0.5, 1.5, 2.5, 3.5)},
                    "verse": {"snare_beats": (1.0, 3.0), "kick_beats": (0.0, 1.5, 3.0), "ghost_snare": ()},
                    "chorus": {"kick_beats": (0.0, 1.0, 1.5, 2.0, 3.0), "ghost_snare": (2.75, 3.75)},
                    "bridge": {"kick_beats": (0.0, 2.0), "hat_beats": _QUARTERS},
                },
                hat_accents=(0.7, 1.0),
                fill="pickup",
                phrase_fill_bars=8,
                role_dynamics={"intro": 0.85, "verse": 0.92, "pre": 1.02, "chorus": 1.15, "bridge": 0.9},
                flags={"hat_soft": 1.0, "kick_push": 1.18, "pocket_offset": -0.006, "humanize_ms": 0.006},
                sixteenth_hats_to_bpm=0,
            ),
            _p(
                "pop_backbeat",
                "Pop groove",
                "Modern pop backbeat: kick 1 and the & of 3, snare 2 and 4, 8th hats with "
                "accented quarters; fuller chorus, pickup fills.",
                {
                    "kick_beats": (0.0, 2.5),
                    "snare_beats": (1.0, 3.0),
                    "hat_beats": _EIGHTHS,
                    "bass_beats": (0.0, 2.0, 2.5),
                    "comp_beats": (0.0, 1.5, 3.5),
                    "comp_dur": 0.3,
                },
                by_role={
                    "verse": {"kick_beats": (0.0, 2.5)},
                    "chorus": {"kick_beats": (0.0, 1.5, 2.5), "comp_beats": (0.0, 1.0, 1.5, 2.5, 3.5)},
                },
                hat_accents=(1.0, 0.7),
                fill="pickup",
                phrase_fill_bars=8,
                role_dynamics={"verse": 0.92, "chorus": 1.1},
                flags={"pocket_offset": 0.0},
            ),
            _p(
                "rock_drive",
                "Rock groove",
                "Driving rock: kick on 1 and 3 with an & push, big 2/4 backbeat, 8th hats "
                "accented on the beat, tom runs into sections.",
                {
                    "kick_beats": (0.0, 2.0, 2.5),
                    "snare_beats": (1.0, 3.0),
                    "hat_beats": _EIGHTHS,
                    "ghost_snare": (),
                    "bass_beats": _EIGHTHS,
                    "comp_beats": _QUARTERS,
                    "comp_dur": 0.42,
                },
                by_role={
                    "verse": {"kick_beats": (0.0, 2.0), "comp_beats": (0.0, 2.0)},
                    "chorus": {"kick_beats": (0.0, 1.5, 2.0, 2.5)},
                },
                hat_accents=(1.0, 0.82),
                fill="tom_run",
                phrase_fill_bars=8,
                role_dynamics={"verse": 0.9, "chorus": 1.15, "bridge": 1.05},
                half_time_from_bpm=168,
            ),
            _p(
                "funk_rnb",
                "Funk groove",
                "Funk / R&B pocket: syncopated kick, 2/4 snare with ghost notes, 16th hats "
                "with an accented 8th pulse, tight stabs.",
                {
                    "kick_beats": (0.0, 0.75, 2.5),
                    "snare_beats": (1.0, 3.0),
                    "hat_beats": tuple(i * 0.25 for i in range(16)),
                    "ghost_snare": (0.75, 1.75, 2.25, 3.75),
                    "comp_beats": (0.5, 1.25, 2.5, 3.25),
                    "comp_dur": 0.14,
                },
                hat_accents=(1.0, 0.45, 0.75, 0.45),
                fill="snare_roll",
                phrase_fill_bars=4,
                role_dynamics={"verse": 0.92, "chorus": 1.12},
                sixteenth_hats_to_bpm=0,
            ),
            _p(
                "jazz_ride",
                "Jazz swing",
                "Swing: spang-a-lang ride, feathered quarter kick, hi-hat foot on 2 and 4, "
                "walking bass, Charleston comp; no backbeat snare.",
                {
                    "kick_beats": _QUARTERS,
                    "snare_beats": (),
                    "hat_beats": (0.0, 1.0, 1.5, 2.0, 3.0, 3.5),
                    "ghost_snare": (),
                    "bass_beats": _QUARTERS,
                    "comp_beats": (0.0, 1.5),
                    "comp_dur": 0.32,
                },
                hat_accents=(0.62, 0.5),
                fill="none",
                role_dynamics={"chorus": 1.05},
                flags={"kick_push": 0.55},
            ),
            _p(
                "bossa_clave",
                "Bossa nova",
                "Bossa nova: cross-stick clave, soft kick on 1 and the & of 2, two-feel bass "
                "with the anticipation, gentle syncopated comp.",
                {
                    "kick_beats": (0.0, 1.5, 2.0, 3.5),
                    "snare_beats": (),
                    "cross_stick": (0.0, 0.75, 1.5, 2.5, 3.25),
                    "hat_beats": (),
                    "bass_beats": (0.0, 1.5, 2.0, 3.5),
                    "comp_beats": (0.0, 1.25, 2.5, 3.25),
                    "comp_dur": 0.36,
                },
                fill="none",
                role_dynamics={"chorus": 1.05},
                flags={"kick_push": 0.6},
            ),
        )
    }
)

# Default profile per style when a song has none of its own.
STYLE_DEFAULT_PROFILES: Mapping[str, str] = MappingProxyType(
    {
        "Ballad": "piano_ballad",
        "Pop groove": "pop_backbeat",
        "Pop": "pop_backbeat",
        "Rock groove": "rock_drive",
        "Funk groove": "funk_rnb",
        "Jazz swing": "jazz_ride",
        "Bossa nova": "bossa_clave",
    }
)


def validate_groove_profiles() -> list[str]:
    """Problems in the registry (empty when it is sound)."""
    problems: list[str] = []
    for pid, prof in GROOVE_PROFILES.items():
        if pid != prof.id:
            problems.append(f"{pid}: id mismatch")
        if prof.fill not in FILL_TYPES:
            problems.append(f"{pid}: unknown fill '{prof.fill}'")
        for role in list(prof.by_role) + list(prof.role_dynamics):
            if role not in ROLES:
                problems.append(f"{pid}: unknown role '{role}'")
        for grid in (prof.grid, *prof.by_role.values()):
            for key, val in grid.items():
                if key in GRID_KEYS and any(not 0.0 <= float(b) < 4.0 for b in val):
                    problems.append(f"{pid}: {key} has a beat outside the 4/4 bar")
    for style, pid in STYLE_DEFAULT_PROFILES.items():
        if pid not in GROOVE_PROFILES:
            problems.append(f"style {style}: unknown profile '{pid}'")
        elif GROOVE_PROFILES[pid].style not in (style, "Pop groove" if style == "Pop" else style):
            problems.append(f"style {style}: default '{pid}' refines {GROOVE_PROFILES[pid].style}")
    return problems


def resolve_groove_profile(
    style: str,
    *,
    song_profile_id: str = "",
    time_signature: str = "4/4",
) -> GrooveProfile | None:
    """The groove for a song played in ``style``.

    ``song_profile_id`` is the song's own profile; it applies only when it
    refines ``style`` (a song's groove never overrides the style the user
    picked). Profiles are written for 4/4; other meters keep the recipe grid.
    """
    if str(time_signature or "4/4").strip() != "4/4":
        return None
    canon = "Pop groove" if str(style or "").strip() == "Pop" else str(style or "").strip()
    own = GROOVE_PROFILES.get(str(song_profile_id or "").strip())
    if own is not None and own.style == canon:
        return own
    default_id = STYLE_DEFAULT_PROFILES.get(canon)
    return GROOVE_PROFILES.get(default_id) if default_id else None
