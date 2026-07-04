"""Style-aware synthesis recipes — drum/bass/comp/voicing/density profiles."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from backing_musical_profile import BackingMusicalProfile

__all__ = (
    "STYLE_RECIPE_IDS",
    "apply_profile_to_synthesis",
    "blues_groove_pattern",
    "style_recipe_id",
)


STYLE_RECIPE_IDS: frozenset[str] = frozenset(
    {
        "pop_groove",
        "rock_groove",
        "jazz_swing",
        "bossa_nova",
        "funk_groove",
        "ballad",
        "blues_groove",
        "jewish_groove",
        "jewish_hora",
        "klezmer_groove",
        "jewish_ballad",
    }
)


def style_recipe_id(style: str) -> str:
    """Map canonical groove label to recipe id."""
    low = str(style or "").strip().lower()
    if "blues" in low:
        return "blues_groove"
    if "bossa" in low or "samba" in low:
        return "bossa_nova"
    if "jazz" in low or "swing" in low:
        return "jazz_swing"
    if "funk" in low:
        return "funk_groove"
    if "rock" in low:
        return "rock_groove"
    if "ballad" in low:
        return "ballad"
    if "hora" in low:
        return "jewish_hora"
    if "klezmer" in low:
        return "klezmer_groove"
    if "jewish" in low:
        return "jewish_ballad" if "ballad" in low else "jewish_groove"
    return "pop_groove"


def blues_groove_pattern(*, pulses: int = 4) -> dict[str, Any]:
    """12/8 shuffle blues grid — swung triplet feel with walking quarters.

    The hi-hat rides the long-short triplet subdivision (beat and the "trip-let"
    third partial at ~0.67) so the shuffle is clearly audible, not a straight 4.
    """
    if pulses == 4:
        return {
            "bass_beats": [0, 1, 2, 3],
            # Comp on the backbeat off-triplet gives the lazy blues push.
            "comp_beats": [0, 0.67, 1.67, 2.67, 3.67],
            # Shuffled hats: downbeat + last triplet partial of each beat.
            "hat_beats": [0, 0.67, 1, 1.67, 2, 2.67, 3, 3.67],
            "snare_beats": [1.0, 3.0],
            "kick_beats": [0, 2],
            "ghost_snare": [1.67, 2.67],
            "comp_dur": 0.58,
        }
    return {
        "bass_beats": [0, 3, 6, 9],
        "comp_beats": [0, 2, 3, 5, 6, 8, 9, 11],
        "hat_beats": list(range(pulses)),
        "snare_beats": [3, 9],
        "kick_beats": [0, 6],
        "ghost_snare": [5, 11],
        "comp_dur": 0.52,
    }


def _base_style_flags(recipe_id: str) -> dict[str, Any]:
    """Groove-character flags layered on top of song-specific overrides."""
    flags: dict[str, Any] = {
        "swing": 0.0,
        "humanize_ms": 0.012,
        "ghost_snare": False,
        "cross_stick": False,
        "ride_jazz": False,
        "kick_push": 1.0,
        "hat_soft": 1.0,
        "comp_stab": False,
        "pocket_offset": 0.0,
        "hat_open_ands": [],
        "density_mul": 1.0,
        "bass_density": 1.0,
        "comp_density": 1.0,
        "drum_energy": 1.0,
    }
    if recipe_id == "jazz_swing":
        flags.update(swing=0.11, ride_jazz=True, humanize_ms=0.018, pocket_offset=0.012)
    elif recipe_id == "bossa_nova":
        flags.update(cross_stick=True, swing=0.04, hat_soft=0.72, humanize_ms=0.015, pocket_offset=0.018)
    elif recipe_id == "funk_groove":
        flags.update(
            ghost_snare=True,
            comp_stab=True,
            kick_push=1.2,
            pocket_offset=-0.02,
            hat_open_ands=[2.5, 3.5],
            comp_density=1.15,
            drum_energy=1.1,
        )
    elif recipe_id == "rock_groove":
        flags.update(kick_push=1.2, hat_soft=0.9, pocket_offset=-0.008, drum_energy=1.15)
    elif recipe_id == "ballad":
        flags.update(hat_soft=0.55, humanize_ms=0.008, pocket_offset=0.020, density_mul=0.72, bass_density=0.65)
    elif recipe_id == "blues_groove":
        flags.update(
            swing=0.22,
            ghost_snare=True,
            humanize_ms=0.02,
            pocket_offset=0.016,
            hat_soft=0.82,
        )
    elif recipe_id == "jewish_groove":
        flags.update(swing=0.06, comp_stab=True, hat_soft=0.85, pocket_offset=0.010)
    return flags


def _mood_modifiers(mood: str) -> dict[str, float]:
    """Scalar modifiers from Creative / backing mood."""
    key = str(mood or "Mellow").strip().lower()
    table: dict[str, dict[str, float]] = {
        "bright": {"hat_soft": 1.12, "comp_density": 1.08, "drum_energy": 1.06},
        "mellow": {"hat_soft": 0.92, "density_mul": 0.9, "drum_energy": 0.9},
        "dark": {"hat_soft": 0.78, "comp_density": 0.88, "bass_density": 1.08},
        "energetic": {"kick_push": 1.18, "drum_energy": 1.28, "comp_density": 1.2, "hat_soft": 1.08},
        # Dreamy = more space and sustain: far fewer comp hits, long chords,
        # soft hats, laid-back pocket.
        "dreamy": {
            "hat_soft": 0.55,
            "density_mul": 0.6,
            "comp_density": 0.55,
            "bass_density": 0.7,
            "drum_energy": 0.6,
            "pocket_offset": 0.02,
            "sustain_mul": 1.6,
        },
        "gritty": {"kick_push": 1.12, "ghost_snare": 1.0, "drum_energy": 1.15, "hat_soft": 0.88},
        "relaxed": {"hat_soft": 0.7, "density_mul": 0.72, "comp_density": 0.72, "drum_energy": 0.74, "pocket_offset": 0.018},
    }
    return table.get(key, table["mellow"])


def _intensity_modifiers(intensity: str) -> dict[str, float]:
    """Light / Medium / Heavy arrangement density."""
    key = str(intensity or "Medium").strip().lower()
    table: dict[str, dict[str, float]] = {
        # Light = sparse comping, thin bass, soft quiet kit.
        "light": {
            "density_mul": 0.58,
            "bass_density": 0.6,
            "comp_density": 0.58,
            "drum_energy": 0.62,
            "hat_soft": 0.8,
        },
        "medium": {"density_mul": 1.0, "bass_density": 1.0, "comp_density": 1.0, "drum_energy": 1.0},
        # Heavy = louder driving kit, denser comp, harder kick.
        "heavy": {
            "density_mul": 1.3,
            "bass_density": 1.2,
            "comp_density": 1.28,
            "drum_energy": 1.45,
            "kick_push": 1.25,
        },
    }
    return table.get(key, table["medium"])


def _apply_scalar_flags(flags: dict[str, Any], mods: dict[str, float]) -> None:
    for key, mult in mods.items():
        if key == "ghost_snare" and mult >= 1.0:
            flags["ghost_snare"] = True
            continue
        if key not in flags:
            continue
        if isinstance(flags[key], bool):
            continue
        try:
            flags[key] = float(flags[key]) * float(mult)
        except (TypeError, ValueError):
            pass


def _thin_pattern(pattern: dict[str, Any], *, bass_mul: float, comp_mul: float) -> dict[str, Any]:
    """Reduce hit density for Light / Dreamy / Ballad profiles."""
    out = deepcopy(pattern)
    if bass_mul < 0.95 and len(out.get("bass_beats", [])) > 1:
        keep = max(1, int(round(len(out["bass_beats"]) * bass_mul)))
        out["bass_beats"] = out["bass_beats"][:keep]
    if comp_mul < 0.95 and len(out.get("comp_beats", [])) > 1:
        keep = max(1, int(round(len(out["comp_beats"]) * comp_mul)))
        out["comp_beats"] = out["comp_beats"][:keep]
    if bass_mul < 0.75:
        out["ghost_snare"] = []
    if comp_mul < 0.72:
        # Sparse comping: keep chords only on strong beats.
        strong = [b for b in out.get("comp_beats", []) if float(b) == int(float(b))]
        out["comp_beats"] = strong or out.get("comp_beats", [])[:1]
    if comp_mul < 0.7:
        out["hat_beats"] = out.get("hat_beats", [])[::2] or out.get("hat_beats", [])
    return out


def _thicken_pattern(pattern: dict[str, Any], *, drum_energy: float, comp_mul: float) -> dict[str, Any]:
    """Add drum + comp density for Heavy / Energetic / Funk profiles."""
    out = deepcopy(pattern)
    if drum_energy > 1.15:
        # Heavier kit: driving eighth-note kick + backbeat ghost snares.
        kicks = list(out.get("kick_beats", []))
        for extra in (2.5, 1.5):
            if extra not in kicks:
                kicks.append(extra)
        out["kick_beats"] = sorted(kicks)
        if not out.get("ghost_snare"):
            out["ghost_snare"] = [0.5, 1.5, 2.5, 3.5]
    if comp_mul > 1.12:
        # Denser comp: add syncopated off-beats between existing hits.
        comps = list(out.get("comp_beats", []))
        for off in (0.5, 1.5, 2.5, 3.5):
            if all(abs(off - c) > 0.2 for c in comps):
                comps.append(off)
        out["comp_beats"] = sorted(comps)
    return out


def apply_profile_to_synthesis(
    *,
    style: str,
    song_profile: dict[str, Any],
    patterns: dict[str, Any],
    profile: BackingMusicalProfile | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Merge canonical profile into synthesis flags and rhythm patterns.

    Returns ``(song_profile, patterns)`` copies — safe to mutate.
    """
    if profile is None:
        return song_profile, patterns

    sp = deepcopy(song_profile)
    pat = deepcopy(patterns)
    recipe = style_recipe_id(profile.canonical_style() or style)
    recipe_flags = _base_style_flags(recipe)

    # Groove-defining scalars the recipe should assert (take the stronger of
    # the two) so e.g. a Blues shuffle isn't flattened by a mild song default.
    _assert_max = {"swing", "pocket_offset"}
    for key, val in recipe_flags.items():
        if key in ("ghost_snare", "cross_stick", "ride_jazz", "comp_stab"):
            if val:
                sp[key] = True
        elif key in _assert_max and isinstance(val, (int, float)):
            try:
                cur = float(sp.get(key, 0.0))
                sp[key] = val if abs(val) > abs(cur) else cur
            except (TypeError, ValueError):
                sp[key] = val
        elif key not in sp:
            sp[key] = val

    if recipe == "blues_groove":
        pulses = len(pat.get("hat_beats", [])) or 4
        pat = blues_groove_pattern(pulses=pulses if pulses in (4, 12) else 4)

    sp.setdefault("sustain_mul", 1.0)
    _apply_scalar_flags(sp, _mood_modifiers(profile.mood))
    _apply_scalar_flags(sp, _intensity_modifiers(profile.intensity))

    # Fold drum_energy into knobs the synth loop actually reads so Heavy
    # is audibly louder/harder and Light is quieter/softer.
    drum_energy = float(sp.get("drum_energy", 1.0))
    sp["kick_push"] = float(sp.get("kick_push", 1.0)) * (0.55 + 0.45 * drum_energy)
    sp["hat_soft"] = float(sp.get("hat_soft", 1.0)) * (0.7 + 0.3 * drum_energy)

    # Dreamy/Ballad sustain: lengthen comp chord duration for more space.
    sustain_mul = float(sp.get("sustain_mul", 1.0))
    if sustain_mul != 1.0:
        pat["comp_dur"] = float(pat.get("comp_dur", 0.45)) * sustain_mul

    density = float(sp.get("density_mul", 1.0))
    bass_mul = float(sp.get("bass_density", 1.0)) * density
    comp_mul = float(sp.get("comp_density", 1.0)) * density
    if bass_mul < 0.98 or comp_mul < 0.98:
        pat = _thin_pattern(pat, bass_mul=bass_mul, comp_mul=comp_mul)
    if drum_energy > 1.15 or comp_mul > 1.12:
        pat = _thicken_pattern(pat, drum_energy=drum_energy, comp_mul=comp_mul)

    return sp, pat
