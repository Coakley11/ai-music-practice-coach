"""Feel-profile registry and genre defaults for harmonic rhythm intelligence.

Extensibility hooks for future:
  * learned song templates
  * artist-specific feel profiles (Mayer, Joel, …)
  * groove libraries
  * style transfer between profiles
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True)
class FeelProfile:
    """Named performance-feel defaults merged into inference."""

    name: str
    base_prob: float = 0.46
    push_beats: float = 0.5
    syncopated: bool = False
    offbeat_half: bool = False
    section_boost: float = 1.25
    downbeat_only: bool = False
    confidence_floor: float = 0.48
    vocal_entrance_pickups_only: bool = False
    bass_anticipation: bool = True
    chord_anticipation: bool = True
    jazz_walking: bool = False
    ii_v_i_boost: float = 1.0
    dominant_anticipation_boost: float = 1.0
    turnaround_boost: float = 1.0
    held_chord_bias: float = 0.0
    instrumental_boost: float = 1.2
    lyric_heavy_dampen: float = 0.55
    tags: tuple[str, ...] = ()


# --- Genre / groove defaults -------------------------------------------------

GENRE_FEEL_PROFILES: dict[str, FeelProfile] = {
    "pop": FeelProfile(
        name="Pop",
        base_prob=0.46,
        section_boost=1.3,
        tags=("pop", "chorus_entry"),
    ),
    "rock": FeelProfile(
        name="Rock",
        base_prob=0.28,
        section_boost=1.45,
        downbeat_only=True,
        confidence_floor=0.52,
        tags=("rock",),
    ),
    "jazz": FeelProfile(
        name="Jazz",
        base_prob=0.58,
        section_boost=1.2,
        jazz_walking=True,
        ii_v_i_boost=1.35,
        dominant_anticipation_boost=1.3,
        turnaround_boost=1.25,
        confidence_floor=0.46,
        tags=("jazz", "swing", "walking_bass"),
    ),
    "bossa": FeelProfile(
        name="Bossa",
        base_prob=0.38,
        section_boost=1.12,
        bass_anticipation=True,
        chord_anticipation=False,
        confidence_floor=0.50,
        tags=("bossa",),
    ),
    "funk": FeelProfile(
        name="Funk",
        base_prob=0.72,
        syncopated=True,
        section_boost=1.25,
        confidence_floor=0.42,
        tags=("funk",),
    ),
    "reggae": FeelProfile(
        name="Reggae",
        base_prob=0.68,
        syncopated=True,
        offbeat_half=True,
        section_boost=1.15,
        confidence_floor=0.44,
        tags=("reggae",),
    ),
    "ballad": FeelProfile(
        name="Ballad",
        base_prob=0.16,
        section_boost=1.1,
        held_chord_bias=0.35,
        confidence_floor=0.58,
        tags=("ballad",),
    ),
    "broadway": FeelProfile(
        name="Broadway / Disney",
        base_prob=0.32,
        section_boost=1.4,
        vocal_entrance_pickups_only=True,
        held_chord_bias=0.28,
        confidence_floor=0.54,
        instrumental_boost=1.35,
        lyric_heavy_dampen=0.42,
        tags=("broadway", "disney", "musical"),
    ),
    "singer_songwriter": FeelProfile(
        name="Singer-Songwriter",
        base_prob=0.22,
        section_boost=1.08,
        confidence_floor=0.62,
        lyric_heavy_dampen=0.48,
        tags=("folk", "acoustic", "storytelling"),
    ),
}


# --- Future artist / ensemble stubs (style-transfer hooks) -------------------

ARTIST_FEEL_PROFILE_STUBS: dict[str, FeelProfile] = {
    "john_mayer": FeelProfile(
        name="John Mayer",
        base_prob=0.34,
        section_boost=1.15,
        confidence_floor=0.56,
        tags=("fingerstyle", "pop_rock", "stub"),
    ),
    "billy_joel": FeelProfile(
        name="Billy Joel",
        base_prob=0.40,
        section_boost=1.22,
        tags=("piano_pop", "stub"),
    ),
    "disney_broadway": FeelProfile(
        name="Disney / Broadway",
        base_prob=0.32,
        vocal_entrance_pickups_only=True,
        held_chord_bias=0.30,
        section_boost=1.4,
        tags=("disney", "broadway", "stub"),
    ),
    "jazz_trio": FeelProfile(
        name="Jazz Trio",
        base_prob=0.62,
        jazz_walking=True,
        ii_v_i_boost=1.4,
        dominant_anticipation_boost=1.35,
        turnaround_boost=1.3,
        tags=("jazz", "trio", "stub"),
    ),
    "bossa_ensemble": FeelProfile(
        name="Bossa Nova Ensemble",
        base_prob=0.36,
        bass_anticipation=True,
        chord_anticipation=False,
        tags=("bossa", "stub"),
    ),
}


@dataclass
class FeelProfileRegistry:
    """Register and resolve feel profiles for songs (future style transfer)."""

    profiles: dict[str, FeelProfile] = field(default_factory=dict)
    song_template_hooks: dict[str, Callable[..., Any]] = field(default_factory=dict)
    groove_libraries: dict[str, dict[str, Any]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.profiles:
            self.profiles = {
                **GENRE_FEEL_PROFILES,
                **ARTIST_FEEL_PROFILE_STUBS,
            }

    def register(self, key: str, profile: FeelProfile) -> None:
        self.profiles[key] = profile

    def register_song_template_hook(
        self, key: str, hook: Callable[..., Any]
    ) -> None:
        self.song_template_hooks[key] = hook

    def register_groove_library(self, key: str, library: dict[str, Any]) -> None:
        self.groove_libraries[key] = library

    def resolve(
        self,
        *,
        groove_style: str,
        genre: str = "",
        artist: str = "",
        profile_key: str | None = None,
    ) -> FeelProfile:
        if profile_key and profile_key in self.profiles:
            return self.profiles[profile_key]

        artist_l = str(artist or "").lower()
        for key, prof in ARTIST_FEEL_PROFILE_STUBS.items():
            if key.replace("_", " ") in artist_l or prof.name.lower() in artist_l:
                return prof

        g = str(groove_style or "").lower()
        genre_l = str(genre or "").lower()

        if any(k in genre_l for k in ("disney", "broadway", "musical", "show tune")):
            return self.profiles["broadway"]
        if any(k in genre_l for k in ("singer-songwriter", "folk", "acoustic")):
            return self.profiles["singer_songwriter"]
        if "funk" in g:
            return self.profiles["funk"]
        if "reggae" in g:
            return self.profiles["reggae"]
        if "jazz" in g or "swing" in g:
            return self.profiles["jazz"]
        if "bossa" in g:
            return self.profiles["bossa"]
        if "rock" in g:
            return self.profiles["rock"]
        if "ballad" in g:
            return self.profiles["ballad"]
        return self.profiles["pop"]


DEFAULT_FEEL_REGISTRY = FeelProfileRegistry()
