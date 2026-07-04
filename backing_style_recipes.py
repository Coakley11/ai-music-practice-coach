"""Style-aware synthesis recipes — drum/bass/comp/voicing/density profiles."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from backing_musical_profile import BackingMusicalProfile

__all__ = (
    "STYLE_RECIPE_IDS",
    "apply_profile_to_synthesis",
    "blues_groove_pattern",
    "resolve_feel_for_style",
    "style_pattern_for_recipe",
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


def resolve_feel_for_style(style: str, feel: str = "") -> str:
    """Best-effort feel string from explicit input or groove_feel profile."""
    text = str(feel or "").strip()
    if text:
        return text
    try:
        from groove_feel import GROOVE_PROFILE

        row = GROOVE_PROFILE.get(style, {})
        return str(row.get("time_feel") or row.get("feel") or "").strip()
    except ImportError:
        return ""


def blues_groove_pattern(*, pulses: int = 4) -> dict[str, Any]:
    """Exaggerated 12/8 shuffle — every triplet partial audible."""
    if pulses == 4:
        return {
            "bass_beats": [0, 1, 2, 3],
            "comp_beats": [0, 0.67, 1.33, 2, 2.67, 3.33],
            "hat_beats": [0, 0.67, 1, 1.33, 1.67, 2, 2.67, 3, 3.33, 3.67],
            "snare_beats": [1.0, 3.0],
            "kick_beats": [0, 2],
            "ghost_snare": [1.33, 2.33, 2.67],
            "comp_dur": 0.68,
        }
    return {
        "bass_beats": [0, 3, 6, 9],
        "comp_beats": [0, 2, 3, 5, 6, 8, 9, 11],
        "hat_beats": list(range(pulses)),
        "snare_beats": [3, 9],
        "kick_beats": [0, 6],
        "ghost_snare": [5, 11],
        "comp_dur": 0.58,
    }


def style_pattern_for_recipe(recipe_id: str, *, pulses: int = 4) -> dict[str, Any]:
    """Canonical rhythm grid for a style recipe — single source of truth."""
    if recipe_id == "pop_groove":
        # Clean modern pop: sparse bass, light offbeat comp, straight 8ths.
        return {
            "bass_beats": [0, 2],
            "comp_beats": [1.5, 3.5],
            "hat_beats": [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5],
            "snare_beats": [1.0, 3.0],
            "kick_beats": [0, 2.5],
            "comp_dur": 0.26,
        }
    if recipe_id == "rock_groove":
        # Driving rock: eighth bass pump, power comp every beat, big backbeat.
        return {
            "bass_beats": [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5],
            "comp_beats": [0, 1, 2, 3],
            "hat_beats": [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5],
            "snare_beats": [1.0, 3.0],
            "kick_beats": [0, 1, 2, 3],
            "ghost_snare": [0.5, 1.5, 2.5, 3.5],
            "comp_dur": 0.40,
        }
    if recipe_id == "jazz_swing":
        # Jazz: walking bass quarters, ride spang-a-lang, very sparse comp.
        return {
            "bass_beats": [0, 1, 2, 3],
            "comp_beats": [2.5, 3.5],
            "hat_beats": [0, 1.5, 2, 3.5],
            "snare_beats": [],
            "kick_beats": [0, 2],
            "ghost_snare": [1.5],
            "comp_dur": 0.34,
        }
    if recipe_id == "bossa_nova":
        # Bossa: syncopated bass, cross-stick pulse, soft syncopated comp.
        return {
            "bass_beats": [0, 1.5, 2.75, 3.5],
            "comp_beats": [0.0, 1.25, 2.5, 3.25, 3.75],
            "hat_beats": [],
            "snare_beats": [],
            "kick_beats": [0],
            "cross_stick": [1.0, 2.5, 3.0],
            "comp_dur": 0.38,
        }
    if recipe_id == "funk_groove":
        # Funk: dense 16th bass + syncopated stabs + ghost backbeat.
        return {
            "bass_beats": [0, 0.25, 0.5, 0.75, 1.25, 1.5, 1.75, 2.25, 2.5, 2.75, 3.25, 3.5, 3.75],
            "comp_beats": [0.5, 0.75, 1.25, 1.75, 2.5, 3.25],
            "hat_beats": [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5],
            "snare_beats": [1.0, 3.0],
            "ghost_snare": [0.25, 0.75, 1.25, 1.75, 2.25, 2.75, 3.25, 3.75],
            "kick_beats": [0, 1.5, 2.75],
            "comp_dur": 0.12,
        }
    if recipe_id == "blues_groove":
        return blues_groove_pattern(pulses=pulses if pulses in (4, 12) else 4)
    if recipe_id == "ballad":
        return {
            "bass_beats": [0, 2],
            "comp_beats": [0, 2.5, 3.5],
            "hat_beats": [0, 1, 2, 3],
            "snare_beats": [3.0],
            "kick_beats": [0],
            "comp_dur": 0.95,
        }
    if recipe_id in ("jewish_groove", "klezmer_groove"):
        return {
            "bass_beats": [0, 1.5, 2, 3],
            "comp_beats": [0, 0.75, 1.5, 2.25, 3],
            "hat_beats": [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5],
            "snare_beats": [1.0, 2.5, 3.0],
            "kick_beats": [0, 2],
            "comp_dur": 0.32,
        }
    if recipe_id == "jewish_hora":
        return {
            "bass_beats": [0, 1.5, 2, 3],
            "comp_beats": [0, 0.75, 1.5, 2.25, 3],
            "hat_beats": [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5],
            "snare_beats": [1.0, 2.5, 3.0],
            "kick_beats": [0, 2],
            "comp_dur": 0.32,
        }
    if recipe_id == "jewish_ballad":
        return {
            "bass_beats": [0, 2],
            "comp_beats": [0, 3.5],
            "hat_beats": [0, 2],
            "snare_beats": [3.0],
            "kick_beats": [0],
            "comp_dur": 1.05,
        }
    return style_pattern_for_recipe("pop_groove", pulses=pulses)


def _base_style_flags(recipe_id: str) -> dict[str, Any]:
    """Groove-character flags for each style recipe."""
    flags: dict[str, Any] = {
        "recipe_id": recipe_id,
        "style_locked": True,
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
        "sustain_mul": 1.0,
        "syncopation": 1.0,
        "bass_mode": "generic",
        "comp_mode": "block",
        "comp_wave": "organ",
    }
    if recipe_id == "pop_groove":
        flags.update(
            pocket_offset=0.0,
            hat_open_ands=[3.5],
            bass_mode="pop_support",
            comp_mode="block",
            comp_wave="organ",
            humanize_ms=0.006,
        )
    elif recipe_id == "rock_groove":
        flags.update(
            kick_push=1.35,
            hat_soft=0.95,
            pocket_offset=-0.012,
            drum_energy=1.35,
            bass_mode="rock_root",
            comp_mode="power",
            comp_wave="sine",
            comp_stab=True,
            ghost_snare=True,
        )
    elif recipe_id == "jazz_swing":
        flags.update(
            swing=0.20,
            ride_jazz=True,
            humanize_ms=0.022,
            pocket_offset=0.016,
            bass_mode="walk",
            comp_mode="shell",
            comp_wave="organ",
        )
    elif recipe_id == "bossa_nova":
        flags.update(
            cross_stick=True,
            swing=0.05,
            hat_soft=0.55,
            humanize_ms=0.018,
            pocket_offset=0.022,
            bass_mode="bossa_two_feel",
            comp_mode="bossa",
            comp_wave="organ",
        )
    elif recipe_id == "funk_groove":
        flags.update(
            ghost_snare=True,
            comp_stab=True,
            kick_push=1.28,
            pocket_offset=-0.025,
            hat_open_ands=[2.5, 3.5],
            comp_density=1.25,
            drum_energy=1.2,
            syncopation=1.55,
            bass_mode="funk_sync",
            comp_mode="stab",
            comp_wave="organ",
        )
    elif recipe_id == "blues_groove":
        flags.update(
            swing=0.32,
            ghost_snare=True,
            humanize_ms=0.024,
            pocket_offset=0.020,
            hat_soft=0.78,
            bass_mode="blues_shuffle",
            comp_mode="blues",
            comp_wave="organ",
        )
    elif recipe_id == "ballad":
        flags.update(
            hat_soft=0.55,
            humanize_ms=0.008,
            pocket_offset=0.020,
            density_mul=0.72,
            bass_density=0.65,
            sustain_mul=1.35,
            bass_mode="whole_note",
            comp_mode="open",
            comp_wave="organ",
        )
    elif recipe_id == "jewish_groove":
        flags.update(swing=0.06, comp_stab=True, hat_soft=0.85, pocket_offset=0.010)
    return flags


def _feel_modifiers(feel: str) -> dict[str, float]:
    """Map time-feel / groove feel text to synthesis scalars."""
    key = str(feel or "").strip().lower()
    if not key:
        return {}
    if "swing" in key or "shuffle" in key or "triplet" in key or "12/8" in key:
        return {"swing": 1.2, "humanize_ms": 1.12, "pocket_offset": 0.012}
    if "16th" in key or "funk" in key or "syncop" in key:
        return {"syncopation": 1.25, "pocket_offset": -0.012, "comp_density": 1.08}
    if "half-time" in key or "half time" in key or "relaxed" in key or "laid" in key:
        return {"density_mul": 0.85, "pocket_offset": 0.014, "sustain_mul": 1.2}
    if "behind" in key or "late pocket" in key:
        return {"pocket_offset": 0.018, "humanize_ms": 1.08}
    if "straight" in key or "locked" in key or "grid" in key:
        return {"swing": 0.75, "pocket_offset": -0.004, "humanize_ms": 0.92}
    if "driving" in key or "hard backbeat" in key:
        return {"kick_push": 1.1, "drum_energy": 1.12, "comp_density": 1.06}
    return {}


def _mood_modifiers(mood: str) -> dict[str, float]:
    """Scalar modifiers from Creative / backing mood."""
    key = str(mood or "Mellow").strip().lower()
    table: dict[str, dict[str, float]] = {
        "bright": {"hat_soft": 1.12, "comp_density": 1.08, "drum_energy": 1.06},
        "mellow": {"hat_soft": 0.92, "density_mul": 0.9, "drum_energy": 0.9},
        "dark": {"hat_soft": 0.78, "comp_density": 0.88, "bass_density": 1.08},
        "energetic": {"kick_push": 1.18, "drum_energy": 1.28, "comp_density": 1.2, "hat_soft": 1.08},
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
        "relaxed": {
            "hat_soft": 0.7,
            "density_mul": 0.72,
            "comp_density": 0.72,
            "drum_energy": 0.74,
            "pocket_offset": 0.018,
            "sustain_mul": 1.15,
        },
    }
    return table.get(key, table["mellow"])


def _intensity_modifiers(intensity: str) -> dict[str, float]:
    """Light / Medium / Heavy arrangement density."""
    key = str(intensity or "Medium").strip().lower()
    table: dict[str, dict[str, float]] = {
        "light": {
            "density_mul": 0.58,
            "bass_density": 0.6,
            "comp_density": 0.58,
            "drum_energy": 0.62,
            "hat_soft": 0.8,
        },
        "medium": {"density_mul": 1.0, "bass_density": 1.0, "comp_density": 1.0, "drum_energy": 1.0},
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
        strong = [b for b in out.get("comp_beats", []) if float(b) == int(float(b))]
        out["comp_beats"] = strong or out.get("comp_beats", [])[:1]
    if comp_mul < 0.7:
        out["hat_beats"] = out.get("hat_beats", [])[::2] or out.get("hat_beats", [])
    return out


def _thicken_pattern(
    pattern: dict[str, Any],
    *,
    drum_energy: float,
    comp_mul: float,
    syncopation: float = 1.0,
) -> dict[str, Any]:
    """Add drum + comp density for Heavy / Energetic / Funk profiles."""
    out = deepcopy(pattern)
    if drum_energy > 1.15:
        kicks = list(out.get("kick_beats", []))
        for extra in (2.5, 1.5):
            if extra not in kicks:
                kicks.append(extra)
        out["kick_beats"] = sorted(kicks)
        if not out.get("ghost_snare"):
            out["ghost_snare"] = [0.5, 1.5, 2.5, 3.5]
    if comp_mul > 1.12 or syncopation > 1.15:
        comps = list(out.get("comp_beats", []))
        for off in (0.5, 1.5, 2.5, 3.5):
            if all(abs(off - c) > 0.2 for c in comps):
                comps.append(off)
        out["comp_beats"] = sorted(comps)
    return out


def _apply_recipe_flags(sp: dict[str, Any], recipe_flags: dict[str, Any]) -> None:
    """Style-first merge: recipe asserts groove identity over song defaults."""
    _assert_max = {"swing", "pocket_offset", "syncopation"}
    _recipe_owned = {
        "recipe_id",
        "style_locked",
        "bass_mode",
        "comp_mode",
        "comp_wave",
        "hat_open_ands",
    }
    for key, val in recipe_flags.items():
        if key in ("ghost_snare", "cross_stick", "ride_jazz", "comp_stab"):
            if val:
                sp[key] = True
        elif key in _recipe_owned:
            sp[key] = val
        elif key in _assert_max and isinstance(val, (int, float)):
            try:
                cur = float(sp.get(key, 0.0))
                sp[key] = val if abs(val) > abs(cur) else cur
            except (TypeError, ValueError):
                sp[key] = val
        elif key not in sp or key in (
            "kick_push",
            "hat_soft",
            "humanize_ms",
            "density_mul",
            "bass_density",
            "comp_density",
            "drum_energy",
            "sustain_mul",
        ):
            sp[key] = val


def apply_profile_to_synthesis(
    *,
    style: str,
    song_profile: dict[str, Any],
    patterns: dict[str, Any],
    profile: BackingMusicalProfile | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Merge canonical profile into synthesis flags and rhythm patterns.

    Style recipe always owns the rhythm grid when a profile is present.
    Song-specific flags may tint arrangement but cannot replace the grid.
    """
    if profile is None:
        return song_profile, patterns

    sp = deepcopy(song_profile)
    canonical = profile.canonical_style() or style
    recipe = style_recipe_id(canonical)
    recipe_flags = _base_style_flags(recipe)
    pulses = len(patterns.get("hat_beats", [])) or 4
    pat = style_pattern_for_recipe(recipe, pulses=pulses)

    _apply_recipe_flags(sp, recipe_flags)
    sp["style_locked"] = True
    sp["recipe_id"] = recipe

    feel_text = resolve_feel_for_style(canonical, profile.feel)
    sp.setdefault("sustain_mul", 1.0)
    sp.setdefault("syncopation", 1.0)
    _apply_scalar_flags(sp, _feel_modifiers(feel_text))
    _apply_scalar_flags(sp, _mood_modifiers(profile.mood))
    _apply_scalar_flags(sp, _intensity_modifiers(profile.intensity))

    drum_energy = float(sp.get("drum_energy", 1.0))
    syncopation = float(sp.get("syncopation", 1.0))
    sp["kick_push"] = float(sp.get("kick_push", 1.0)) * (0.55 + 0.45 * drum_energy)
    sp["hat_soft"] = float(sp.get("hat_soft", 1.0)) * (0.7 + 0.3 * drum_energy)

    sustain_mul = float(sp.get("sustain_mul", 1.0))
    if sustain_mul != 1.0:
        pat["comp_dur"] = float(pat.get("comp_dur", 0.45)) * sustain_mul
    if recipe == "funk_groove" or syncopation > 1.2:
        pat["comp_dur"] = min(float(pat.get("comp_dur", 0.45)), 0.24)

    density = float(sp.get("density_mul", 1.0))
    bass_mul = float(sp.get("bass_density", 1.0)) * density
    comp_mul = float(sp.get("comp_density", 1.0)) * density
    if bass_mul < 0.98 or comp_mul < 0.98:
        pat = _thin_pattern(pat, bass_mul=bass_mul, comp_mul=comp_mul)
    if drum_energy > 1.15 or comp_mul > 1.12 or syncopation > 1.15:
        pat = _thicken_pattern(
            pat,
            drum_energy=drum_energy,
            comp_mul=comp_mul,
            syncopation=syncopation,
        )

    return sp, pat
