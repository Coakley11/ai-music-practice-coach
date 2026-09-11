"""Canonical musical profile for style-aware backing-track generation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

__all__ = (
    "BackingMusicalProfile",
    "normalize_backing_play_intensity",
    "profile_cache_tuple",
    "resolve_backing_musical_profile",
    "resolve_backing_musical_profile_from_context",
    "resolve_backing_musical_profile_from_session",
)


@dataclass(frozen=True)
class BackingMusicalProfile:
    """
    Structured input for the backing synthesis engine.

    Example::

        {
            "style": "Funk groove",
            "mood": "Energetic",
            "intensity": "Heavy",
            "tempo": 110,
            "key": "C",
            "progression": ["Em7", "Em7", "Am7", "Am7"],
        }
    """

    style: str
    mood: str = "Mellow"
    intensity: str = "Medium"
    tempo: int = 100
    key: str = "C"
    level: str = "Intermediate"
    time_signature: str = "4/4"
    feel: str = ""
    progression: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row["progression"] = list(self.progression)
        return row

    def canonical_style(self) -> str:
        from songs.playback_defaults import normalize_groove_label

        return normalize_groove_label(self.style or "Pop groove")


def resolve_backing_musical_profile(
    *,
    style: str,
    mood: str = "",
    intensity: str = "",
    tempo: int = 100,
    key: str = "C",
    level: str = "Intermediate",
    time_signature: str = "4/4",
    feel: str = "",
    progression: list[str] | tuple[str, ...] | None = None,
) -> BackingMusicalProfile:
    """Build a normalized profile from explicit generation inputs."""
    from songs.playback_defaults import normalize_groove_label

    mood_norm = _normalize_mood(mood)
    intensity_norm = _normalize_intensity(intensity)
    prog = tuple(str(c).strip() for c in (progression or ()) if str(c).strip())
    return BackingMusicalProfile(
        style=normalize_groove_label(style or "Pop groove"),
        mood=mood_norm,
        intensity=intensity_norm,
        tempo=max(40, min(240, int(tempo or 100))),
        key=str(key or "C").strip() or "C",
        level=str(level or "Intermediate").strip() or "Intermediate",
        time_signature=str(time_signature or "4/4").strip() or "4/4",
        feel=str(feel or "").strip(),
        progression=prog,
    )


def resolve_backing_musical_profile_from_context(
    ctx: Any | None,
    *,
    style: str = "",
    tempo: int = 100,
    key: str = "C",
    level: str = "Intermediate",
    time_signature: str = "4/4",
    progression: list[str] | tuple[str, ...] | None = None,
    session_mood: str = "",
    session_intensity: str = "",
    session_feel: str = "",
) -> BackingMusicalProfile:
    """Resolve from a BackingContext (creative/custom handoffs)."""
    mood = str(session_mood or "").strip()
    intensity = str(session_intensity or "").strip()
    feel = str(session_feel or "").strip()
    ctx_style = style
    if ctx is not None:
        ctx_mood = str(getattr(ctx, "mood", "") or "").strip()
        ctx_intensity = str(getattr(ctx, "groove_intensity", "") or "").strip()
        mood = ctx_mood or mood
        intensity = ctx_intensity or intensity
        ctx_style = str(getattr(ctx, "style", "") or getattr(ctx, "groove", "") or style).strip()
        if not tempo:
            tempo = int(getattr(ctx, "bpm", 0) or tempo)
        if not time_signature:
            time_signature = str(getattr(ctx, "meter", "") or time_signature)
        if not feel:
            feel = str(getattr(ctx, "feel", "") or "").strip()
    return resolve_backing_musical_profile(
        style=ctx_style,
        mood=mood,
        intensity=intensity,
        tempo=tempo,
        key=key,
        level=level,
        time_signature=time_signature,
        feel=feel,
        progression=progression,
    )


def resolve_backing_musical_profile_from_session(
    session: Mapping[str, Any],
    *,
    style: str,
    tempo: int = 100,
    key: str = "C",
    level: str = "Intermediate",
    time_signature: str = "4/4",
    progression: list[str] | tuple[str, ...] | None = None,
) -> BackingMusicalProfile:
    """Best-effort profile from session state + explicit style/tempo."""
    mood = str(session.get("improv_mood") or session.get("improv_jam_mood") or "").strip()
    intensity = str(session.get("improv_groove") or "").strip()
    feel = str(session.get("improv_feel") or "").strip()
    meta = session.get("improv_style_meta")
    if isinstance(meta, dict):
        mood = str(meta.get("mood") or mood).strip()
        intensity = str(meta.get("groove_intensity") or meta.get("groove") or intensity).strip()
        feel = str(meta.get("feel") or feel).strip()
    try:
        from backing_context import get_backing_context

        ctx = get_backing_context(session)
        if ctx is not None:
            return resolve_backing_musical_profile_from_context(
                ctx,
                style=style,
                tempo=tempo,
                key=key,
                level=level,
                time_signature=time_signature,
                progression=progression,
                session_mood=mood,
                session_intensity=intensity,
                session_feel=feel,
            )
    except ImportError:
        pass
    if not feel:
        try:
            from backing_style_recipes import resolve_feel_for_style

            feel = resolve_feel_for_style(style, "")
        except ImportError:
            pass
    return resolve_backing_musical_profile(
        style=style,
        mood=mood,
        intensity=intensity,
        tempo=tempo,
        key=key,
        level=level,
        time_signature=time_signature,
        feel=feel,
        progression=progression,
    )


def profile_cache_tuple(profile: BackingMusicalProfile | None) -> tuple[Any, ...]:
    """Hashable tuple for WAV cache signatures."""
    if profile is None:
        return ()
    return (
        profile.canonical_style(),
        profile.mood,
        profile.intensity,
        int(profile.tempo),
        profile.level,
        profile.time_signature,
        profile.feel,
        profile.progression[:8],
    )


def _normalize_mood(raw: str) -> str:
    text = str(raw or "").strip()
    if not text:
        return "Mellow"
    options = {
        "bright": "Bright",
        "mellow": "Mellow",
        "dark": "Dark",
        "energetic": "Energetic",
        "dreamy": "Dreamy",
        "gritty": "Gritty",
        "relaxed": "Relaxed",
    }
    return options.get(text.lower(), text.title())


def _normalize_intensity(raw: str) -> str:
    text = str(raw or "").strip()
    if not text:
        return "Medium"
    options = {
        "light": "Light",
        "medium": "Medium",
        "heavy": "Heavy",
        "relaxed": "Light",
        "energetic": "Heavy",
    }
    return options.get(text.lower(), text.title())


_VALID_PLAY_INTENSITIES = frozenset({"light", "medium", "heavy"})


def normalize_backing_play_intensity(raw: str, *, difficulty: str = "") -> str:
    """Humanize level (Light/Medium/Heavy) — never catalog groove names like 'Jewish ballad'."""
    text = str(raw or "").strip()
    if text:
        norm = _normalize_intensity(text)
        if norm.lower() in _VALID_PLAY_INTENSITIES:
            return norm
    diff = str(difficulty or "").strip().lower()
    if diff in {"beginner", "easy"}:
        return "Light"
    if diff in {"advanced", "pro"}:
        return "Heavy"
    return "Medium"
