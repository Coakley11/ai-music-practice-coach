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
    """12/8 shuffle blues grid — triplet backbeat with walking quarters."""
    if pulses == 4:
        return {
            "bass_beats": [0, 1, 2, 3],
            "comp_beats": [0, 1.5, 2, 3.5],
            "hat_beats": [0, 1, 2, 3],
            "snare_beats": [1.0, 3.0],
            "kick_beats": [0, 2],
            "ghost_snare": [1.5, 2.5],
            "comp_dur": 0.55,
        }
    return {
        "bass_beats": [0, 3, 6, 9],
        "comp_beats": [0, 2, 3, 5, 6, 8, 9, 11],
        "hat_beats": list(range(pulses)),
        "snare_beats": [3, 9],
        "kick_beats": [0, 6],
        "comp_dur": 0.48,
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
        flags.update(ghost_snare=True, comp_stab=True, kick_push=1.12, pocket_offset=-0.015, hat_open_ands=[3.5])
    elif recipe_id == "rock_groove":
        flags.update(kick_push=1.2, hat_soft=0.9, pocket_offset=-0.008, drum_energy=1.15)
    elif recipe_id == "ballad":
        flags.update(hat_soft=0.55, humanize_ms=0.008, pocket_offset=0.020, density_mul=0.72, bass_density=0.65)
    elif recipe_id == "blues_groove":
        flags.update(swing=0.08, ghost_snare=True, humanize_ms=0.016, pocket_offset=0.010, hat_soft=0.82)
    elif recipe_id == "jewish_groove":
        flags.update(swing=0.06, comp_stab=True, hat_soft=0.85, pocket_offset=0.010)
    return flags


def _mood_modifiers(mood: str) -> dict[str, float]:
    """Scalar modifiers from Creative / backing mood."""
    key = str(mood or "Mellow").strip().lower()
    table: dict[str, dict[str, float]] = {
        "bright": {"hat_soft": 1.08, "comp_density": 1.05, "drum_energy": 1.04},
        "mellow": {"hat_soft": 0.95, "density_mul": 0.92, "drum_energy": 0.94},
        "dark": {"hat_soft": 0.82, "comp_density": 0.9, "bass_density": 1.05},
        "energetic": {"kick_push": 1.12, "drum_energy": 1.18, "comp_density": 1.12, "hat_soft": 1.05},
        "dreamy": {"hat_soft": 0.68, "density_mul": 0.78, "comp_density": 0.82, "pocket_offset": 0.014},
        "gritty": {"kick_push": 1.08, "ghost_snare": 1.0, "drum_energy": 1.1, "hat_soft": 0.9},
        "relaxed": {"hat_soft": 0.75, "density_mul": 0.8, "drum_energy": 0.82, "pocket_offset": 0.016},
    }
    return table.get(key, table["mellow"])


def _intensity_modifiers(intensity: str) -> dict[str, float]:
    """Light / Medium / Heavy arrangement density."""
    key = str(intensity or "Medium").strip().lower()
    table: dict[str, dict[str, float]] = {
        "light": {"density_mul": 0.72, "bass_density": 0.7, "comp_density": 0.75, "drum_energy": 0.78},
        "medium": {"density_mul": 1.0, "bass_density": 1.0, "comp_density": 1.0, "drum_energy": 1.0},
        "heavy": {"density_mul": 1.22, "bass_density": 1.15, "comp_density": 1.18, "drum_energy": 1.25, "kick_push": 1.1},
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
    if bass_mul < 0.95 and len(out.get("bass_beats", [])) > 2:
        keep = max(2, int(round(len(out["bass_beats"]) * bass_mul)))
        out["bass_beats"] = out["bass_beats"][:keep]
    if comp_mul < 0.95 and len(out.get("comp_beats", [])) > 2:
        keep = max(2, int(round(len(out["comp_beats"]) * comp_mul)))
        out["comp_beats"] = out["comp_beats"][:keep]
    if bass_mul < 0.85:
        out["ghost_snare"] = []
    if comp_mul < 0.8:
        out["hat_beats"] = out.get("hat_beats", [])[::2] or out.get("hat_beats", [])
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

    for key, val in recipe_flags.items():
        if key not in sp:
            sp[key] = val
        elif key in ("ghost_snare", "cross_stick", "ride_jazz", "comp_stab") and val:
            sp[key] = True

    if recipe == "blues_groove":
        pulses = len(pat.get("hat_beats", [])) or 4
        pat = blues_groove_pattern(pulses=pulses if pulses in (4, 12) else 4)

    _apply_scalar_flags(sp, _mood_modifiers(profile.mood))
    _apply_scalar_flags(sp, _intensity_modifiers(profile.intensity))

    density = float(sp.get("density_mul", 1.0))
    bass_mul = float(sp.get("bass_density", 1.0)) * density
    comp_mul = float(sp.get("comp_density", 1.0)) * density
    if bass_mul < 0.98 or comp_mul < 0.98:
        pat = _thin_pattern(pat, bass_mul=bass_mul, comp_mul=comp_mul)

    if float(sp.get("drum_energy", 1.0)) > 1.1 and "ghost_snare" in pat:
        if not pat.get("ghost_snare"):
            pat["ghost_snare"] = [0.5, 1.5, 2.5, 3.5]

    return sp, pat
