"""Whose Practice Melody Backing composes: the jam on screen, or the active song.

Dev review 2026-11-25: a Style Jam in concert C was titled "Entry Style Jam" over a melody in E minor. Only the
TITLE followed the jam; the chords, the key and the identity were still the globally active song's. A jam is its
own source: its own sections, concert key, style, level and identity, and nothing when it has none -- never
another song's data.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Mapping

STYLE_JAM_OWNER = "style_jam"
GENERATOR_OWNER = "jam_session_generator"


@dataclass(frozen=True)
class MelodySource:
    """One generated jam as a Practice Melody's source (concert pitch)."""

    owner: str
    identity: str
    title: str
    sections: dict[str, list[str]] = field(default_factory=dict)
    concert_key: str = ""
    display_key: str = ""
    style: str = ""
    level: str = ""


def _clean(sections: Any) -> dict[str, list[str]]:
    if not isinstance(sections, Mapping):
        return {}
    out: dict[str, list[str]] = {}
    for name, chords in sections.items():
        if isinstance(chords, str):
            continue
        chs = [str(c).strip() for c in (chords or []) if str(c or "").strip()]
        if chs:
            out[str(name)] = chs
    return out


def _snapshot_sections(ctx: Any, concert_key: str) -> dict[str, list[str]]:
    """The whole generated form (never only the sections selected for playback), in ``concert_key``."""
    snap = getattr(ctx, "sealed_jam_snapshot", None)
    if not isinstance(snap, Mapping):
        return {}
    sections = _clean(snap.get("section_map"))
    tonic = str(snap.get("practice_tonic") or "").strip()
    if not sections or not tonic:
        return {}
    from music_theory import key_center_token, transpose_sections_dict

    made_in = key_center_token(tonic, str(snap.get("practice_mode") or "major"))
    if made_in != concert_key:
        sections = {k: list(v) for k, v in transpose_sections_dict(sections, made_in, concert_key).items()}
    return sections


def _relative(chord: str, tonic: str) -> str:
    """A chord token relative to the tonic, so a transposed jam keeps its identity."""
    from music_theory import semitone_distance, split_chord

    out = []
    for part in str(chord).replace("|", " ").split():
        body, _, bass = part.partition("/")
        root, quality = split_chord(body)
        token = f"{semitone_distance(tonic, root) % 12}{quality}"
        if bass[:1] in tuple("ABCDEFG"):
            token += f"/{semitone_distance(tonic, split_chord(bass)[0]) % 12}"
        elif bass:
            token += f"/{bass}"
        out.append(token)
    return ".".join(out)


def _identity(owner: str, sections: Mapping[str, list[str]], tonic: str, style: str, ensemble: str) -> str:
    """Stable over reload, Practice Key changes and Key Cycling; new when the form, harmony or band is new."""
    form = "|".join(f"{name}:{','.join(_relative(c, tonic) for c in chords)}" for name, chords in sections.items())
    return f"jam::{owner}::" + hashlib.sha256(f"{owner}|{style}|{ensemble}|{form}".encode()).hexdigest()[:16]


def jam_melody_source(ctx: Any, musical: Any = None) -> MelodySource | None:
    """The jam Backing plays as a melody source, or None when Backing is not playing a jam.

    ``sections`` is empty when the jam has no progression: the caller then composes nothing."""
    if ctx is None or str(getattr(ctx, "source", "") or "") != "entry_jam":
        return None
    entry = str(getattr(ctx, "entry_mode", "") or "")
    owner = GENERATOR_OWNER if entry == "Jam Session Generator" else STYLE_JAM_OWNER
    concert = str(
        getattr(musical, "practice_concert_key", "") or getattr(ctx, "concert_key", "") or getattr(ctx, "key", "") or ""
    ).strip()
    style = str(getattr(ctx, "style", "") or "").strip()
    sections: dict[str, list[str]] = {}
    if concert:
        sections = _snapshot_sections(ctx, concert) or _clean(getattr(musical, "concert_sections", None))
        if not sections:
            chords = [str(c).strip() for c in (getattr(ctx, "progression", None) or []) if str(c or "").strip()]
            sections = {style or "Jam": chords} if chords else {}
    difficulty = str(getattr(ctx, "difficulty", "") or "")
    return MelodySource(
        owner=owner,
        identity=(
            _identity(owner, sections, concert, style, str(getattr(ctx, "ensemble", "") or ""))
            if sections
            else f"jam::{owner}::none"
        ),
        title="Jam Session Generator" if owner == GENERATOR_OWNER else "Entry Style Jam",
        sections=sections,
        concert_key=concert,
        display_key=str(getattr(musical, "chart_display_key", "") or concert).strip(),
        style=style,
        level=next((lv for lv in ("Beginner", "Intermediate", "Advanced") if lv in difficulty), ""),
    )


__all__ = ("GENERATOR_OWNER", "MelodySource", "STYLE_JAM_OWNER", "jam_melody_source")
