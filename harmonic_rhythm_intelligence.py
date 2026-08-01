"""Infer tasteful chord anticipations and performance feel from plain chart bars.

Explicit chart notation always wins: subdivisions, weights, push markers,
``.hit`` tokens, and ``N.C.`` are never rewritten. When humanize is off or
"Preserve exact chart timing" is enabled, sections pass through unchanged.
"""

from __future__ import annotations

import copy
import re
import zlib
from dataclasses import dataclass
from typing import Any, Mapping

from chord_events import beats_per_bar_from_signature
from chord_subdivisions import (
    Subdivision,
    any_push,
    has_push,
    is_hit_token,
    is_subdivided_bar,
    join_weighted_subdivisions,
    primary_chord,
)
from hri_profiles import DEFAULT_FEEL_REGISTRY, FeelProfile
from music_theory import NOTE_TO_MIDI, is_no_chord_token, normalize_root, split_chord

BACKING_HUMANIZE_LEVEL_KEY = "backing_humanize_chord_timing"
BACKING_PRESERVE_EXACT_KEY = "backing_preserve_exact_timing"
HUMANIZE_LEVEL_CHOICES = ("Off", "Subtle", "Medium", "Strong")

_LEVEL_SCALE = {
    "Off": 0.0,
    "Subtle": 0.38,
    "Medium": 0.62,
    "Strong": 0.88,
}

_CONFIDENCE_FLOOR_BY_LEVEL = {
    "Subtle": 0.55,
    "Medium": 0.48,
    "Strong": 0.40,
}

_INSTRUMENTAL_ROLES = frozenset(
    {"intro", "solo", "outro", "breakdown", "interlude", "instrumental"}
)


@dataclass(frozen=True)
class InferredChange:
    section: str
    bar: int  # 1-indexed within section
    original_token: str
    inferred_token: str
    reason: str
    kind: str
    push_confidence: float = 0.0
    section_confidence: float = 0.0


@dataclass(frozen=True)
class HarmonicRhythmResult:
    sections: dict[str, list[str]]
    annotations: tuple[InferredChange, ...]


@dataclass(frozen=True)
class _BarDecision:
    apply: bool
    inferred_token: str | None
    kind: str
    reason: str
    push_confidence: float
    section_confidence: float


@dataclass(frozen=True)
class InferenceConfidence:
    push_confidence: float
    section_confidence: float

    @property
    def combined(self) -> float:
        return self.push_confidence * self.section_confidence


def annotations_lookup(
    annotations: tuple[InferredChange, ...] | list[InferredChange],
) -> dict[tuple[str, int], InferredChange]:
    return {(a.section, a.bar): a for a in annotations}


def token_has_explicit_timing(token: object) -> bool:
    """True when the author already specified rhythm inside the bar."""
    if token is None:
        return True
    s = str(token).strip()
    if not s:
        return True
    if is_no_chord_token(s):
        return True
    if is_hit_token(s):
        return True
    if is_subdivided_bar(s):
        return True
    if has_push(s) or any_push(s):
        return True
    if ":" in s:
        return True
    return False


def _section_role(section_name: str) -> str:
    name = str(section_name or "").strip().lower()
    if not name:
        return "section"
    if "intro" in name:
        return "intro"
    if "pre" in name:
        return "pre_chorus"
    if "chorus" in name or "refrain" in name:
        return "chorus"
    if "verse" in name:
        return "verse"
    if "bridge" in name or "middle" in name:
        return "bridge"
    if "break" in name or "breakdown" in name:
        return "breakdown"
    if "interlude" in name or "instrumental" in name:
        return "interlude"
    if "outro" in name or "ending" in name or "tag" in name or "final" in name:
        return "outro"
    if "solo" in name:
        return "solo"
    return "section"


def _section_archetype(section_name: str) -> str:
    name = str(section_name or "").strip().lower()
    name = re.sub(r"\s*\d+\s*$", "", name)
    return name or "section"


def _quality_bucket(token: str) -> str:
    from music_theory import classify_chord_quality

    return classify_chord_quality(token)


def _is_minor_seventh(token: str) -> bool:
    return _quality_bucket(token) in ("m7", "half-dim")


def _is_dominant_seventh(token: str) -> bool:
    return _quality_bucket(token) == "dom"


def _is_major_tonic(token: str) -> bool:
    return _quality_bucket(token) in ("major", "maj7")


def _root_pc(token: str) -> int | None:
    head = primary_chord(str(token or ""))
    if not head or is_no_chord_token(head):
        return None
    root, _ = split_chord(head)
    if not root:
        return None
    norm = normalize_root(root)
    midi = NOTE_TO_MIDI.get(norm)
    if midi is None:
        return None
    return int(midi) % 12


def _resolve_sounding_chord(token: str) -> str | None:
    if not token:
        return None
    if is_no_chord_token(token):
        return None
    if is_hit_token(token):
        from chord_subdivisions import hit_underlying_chord

        head = hit_underlying_chord(token)
        return head if head and not is_no_chord_token(head) else None
    if is_subdivided_bar(token):
        head = primary_chord(token)
        return head if head and not is_no_chord_token(head) else None
    return str(token).strip()


def _stable_roll(*parts: object) -> int:
    key = "|".join(str(p) for p in parts)
    return zlib.crc32(key.encode("utf-8")) & 0xFFFFFFFF


def _lyric_line_count(
    section_name: str,
    *,
    lyric_cues: Mapping[str, Any] | None,
    section_lyrics: Mapping[str, Any] | None,
    song_data: dict[str, Any] | None,
) -> int:
    user = (section_lyrics or {}).get(section_name)
    if user:
        return len([ln for ln in str(user).splitlines() if ln.strip()])
    cues = (lyric_cues or {}).get(section_name)
    if cues is None and song_data:
        cues = (song_data.get("lyric_cues") or {}).get(section_name)
    if isinstance(cues, (list, tuple)):
        return len([c for c in cues if str(c).strip()])
    if cues:
        return len([ln for ln in str(cues).splitlines() if ln.strip()])
    return 0


def _section_vocal_density(
    section_name: str,
    *,
    lyric_cues: Mapping[str, Any] | None,
    section_lyrics: Mapping[str, Any] | None,
    song_data: dict[str, Any] | None,
) -> float:
    """0 = instrumental / sparse, 1 = lyric-heavy."""
    role = _section_role(section_name)
    if role in _INSTRUMENTAL_ROLES:
        return 0.0
    lines = _lyric_line_count(
        section_name,
        lyric_cues=lyric_cues,
        section_lyrics=section_lyrics,
        song_data=song_data,
    )
    if lines >= 6:
        return 1.0
    if lines >= 3:
        return 0.72
    if lines >= 1:
        return 0.48
    if role in {"verse", "chorus", "pre_chorus"}:
        return 0.35
    return 0.15


def _transition_boost(
    cur_section: str,
    next_section: str | None,
    *,
    is_last_in_section: bool,
    is_first_in_section: bool,
) -> tuple[float, str | None, float]:
    """Return (multiplier, reason, section_confidence 0–1)."""
    if is_first_in_section:
        cur_role = _section_role(cur_section)
        if cur_role in {"verse", "chorus", "pre_chorus"}:
            return 1.45, "pickup into vocal entrance", 0.82

    if not is_last_in_section or not next_section:
        return 1.0, None, 0.55

    cur_role = _section_role(cur_section)
    nxt_role = _section_role(next_section)
    if cur_role in {"verse", "pre_chorus", "intro"} and nxt_role == "chorus":
        return 1.55, "pickup into chorus", 0.88
    if cur_role == "pre_chorus" and nxt_role == "chorus":
        return 1.62, "pre-chorus build into chorus", 0.92
    if nxt_role == "bridge":
        return 1.35, "pickup into bridge", 0.78
    if nxt_role == "breakdown":
        return 1.2, "tension before breakdown", 0.72
    if nxt_role == "outro" and cur_role in {"chorus", "bridge", "solo"}:
        return 1.15, "release into outro", 0.68
    if cur_role == "bridge" and nxt_role == "chorus":
        return 1.5, "return to chorus", 0.86
    if nxt_role in {"verse", "chorus"} and cur_role in _INSTRUMENTAL_ROLES:
        return 1.48, "pickup into vocal entrance", 0.84
    return 1.0, None, 0.55


def _harmonic_context_boost(
    token: str,
    nxt_head: str,
    nxt_nxt_head: str | None,
    profile: FeelProfile,
) -> tuple[float, str | None]:
    boost = 1.0
    reason: str | None = None

    if _is_dominant_seventh(nxt_head):
        boost *= profile.dominant_anticipation_boost
        reason = "dominant anticipation"

    if (
        _is_minor_seventh(token)
        and _is_dominant_seventh(nxt_head)
        and nxt_nxt_head
        and _is_major_tonic(nxt_nxt_head)
    ):
        boost *= profile.ii_v_i_boost
        reason = "ii–V–I approach"

    if nxt_nxt_head and _root_pc(token) == _root_pc(nxt_nxt_head):
        boost *= profile.turnaround_boost
        if reason is None:
            reason = "turnaround approach"

    return boost, reason


def _compute_confidence(
    *,
    profile: FeelProfile,
    level: str,
    sec_boost: float,
    section_confidence: float,
    vocal_density: float,
    section_role: str,
    sec_reason: str | None,
    harmonic_boost: float,
    bar_idx: int,
    is_last_in_section: bool,
) -> InferenceConfidence:
    level_scale = _LEVEL_SCALE[level]
    push = float(profile.base_prob) * level_scale * sec_boost * harmonic_boost

    if section_role in _INSTRUMENTAL_ROLES:
        push *= profile.instrumental_boost
    elif vocal_density >= 0.6 and not sec_reason:
        push *= profile.lyric_heavy_dampen
    elif vocal_density >= 0.35 and not is_last_in_section and bar_idx > 0:
        push *= max(profile.lyric_heavy_dampen, 0.65)

    if profile.vocal_entrance_pickups_only and not sec_reason and bar_idx > 0:
        push *= 0.35

    if profile.held_chord_bias and not sec_reason:
        push *= max(0.0, 1.0 - profile.held_chord_bias)

    push_confidence = max(0.0, min(push, 1.0))
    return InferenceConfidence(
        push_confidence=push_confidence,
        section_confidence=max(0.0, min(section_confidence, 1.0)),
    )


def _anticipation_token(
    current: str,
    nxt: str,
    *,
    beats_per_bar: float,
    push_beats: float,
    use_syncopated_half: bool,
    use_push: bool,
) -> tuple[str, str]:
    bpb = max(1.0, float(beats_per_bar))
    push = max(0.25, min(float(push_beats), bpb * 0.5))
    hold = bpb - push

    if use_syncopated_half and not use_push and bpb >= 4.0:
        half = bpb / 2.0
        token = join_weighted_subdivisions(
            [Subdivision(current, half, False), Subdivision(nxt, half, False)]
        )
        return token, "syncopated_change"

    if use_push:
        token = join_weighted_subdivisions(
            [Subdivision(current, hold, False), Subdivision(nxt, push, True)]
        )
        return token, "anticipation"

    token = join_weighted_subdivisions(
        [Subdivision(current, hold, False), Subdivision(nxt, push, False)]
    )
    return token, "anticipation"


def _evaluate_bar(
    *,
    sec_name: str,
    bar_idx: int,
    token: str,
    nxt_token: str,
    nxt_nxt_token: str,
    is_last_in_section: bool,
    is_first_in_section: bool,
    next_section_name: str | None,
    profile: FeelProfile,
    level: str,
    bpb: float,
    song_id: str,
    groove_style: str,
    vocal_density: float,
) -> _BarDecision | None:
    if token_has_explicit_timing(token):
        return None

    cur_root = _root_pc(token)
    if cur_root is None:
        return None

    nxt_head = _resolve_sounding_chord(nxt_token)
    if not nxt_head:
        return None

    nxt_root = _root_pc(nxt_head)
    if nxt_root is None or nxt_root == cur_root:
        return None

    nxt_nxt_head = _resolve_sounding_chord(nxt_nxt_token) if nxt_nxt_token else None
    sec_boost, sec_reason, section_confidence = _transition_boost(
        sec_name,
        next_section_name,
        is_last_in_section=is_last_in_section,
        is_first_in_section=is_first_in_section,
    )

    if profile.downbeat_only and sec_boost <= 1.05:
        return _BarDecision(False, None, "", "", 0.0, section_confidence)

    harmonic_boost, harmonic_reason = _harmonic_context_boost(
        token, nxt_head, nxt_nxt_head, profile
    )
    confidence = _compute_confidence(
        profile=profile,
        level=level,
        sec_boost=sec_boost,
        section_confidence=section_confidence,
        vocal_density=vocal_density,
        section_role=_section_role(sec_name),
        sec_reason=sec_reason,
        harmonic_boost=harmonic_boost,
        bar_idx=bar_idx,
        is_last_in_section=is_last_in_section,
    )

    floor = max(
        profile.confidence_floor,
        _CONFIDENCE_FLOOR_BY_LEVEL.get(level, 0.48),
    )
    if confidence.combined < floor:
        return _BarDecision(
            False, None, "", "", confidence.push_confidence, confidence.section_confidence
        )

    roll = _stable_roll(song_id, sec_name, bar_idx + 1, groove_style, level)
    if (roll % 100) >= int(confidence.push_confidence * 100):
        return _BarDecision(
            False, None, "", "", confidence.push_confidence, confidence.section_confidence
        )

    use_syncopated = bool(profile.syncopated) and (roll % 5 == 0)
    use_push = profile.chord_anticipation and (
        not use_syncopated or profile.offbeat_half
    )
    if not profile.bass_anticipation and not profile.chord_anticipation:
        return _BarDecision(
            False, None, "", "", confidence.push_confidence, confidence.section_confidence
        )
    if profile.bass_anticipation and not profile.chord_anticipation:
        use_push = False

    if profile.downbeat_only and sec_boost <= 1.2:
        use_push = True
        use_syncopated = False

    inferred, kind = _anticipation_token(
        token,
        nxt_head,
        beats_per_bar=bpb,
        push_beats=profile.push_beats,
        use_syncopated_half=use_syncopated,
        use_push=use_push,
    )
    if inferred == token:
        return _BarDecision(
            False, None, "", "", confidence.push_confidence, confidence.section_confidence
        )

    reason_bits = [f"Auto {kind.replace('_', ' ')} · {groove_style}"]
    if sec_reason:
        reason_bits.append(sec_reason)
    if harmonic_reason:
        reason_bits.append(harmonic_reason)
    reason = " — ".join(reason_bits)
    final_kind = kind if sec_reason is None else "section_pickup"

    return _BarDecision(
        True,
        inferred,
        final_kind,
        reason,
        confidence.push_confidence,
        confidence.section_confidence,
    )


def apply_harmonic_rhythm_intelligence(
    sections: dict[str, list[str]],
    *,
    groove_style: str = "Pop groove",
    time_signature: str = "4/4",
    humanize_level: str = "Subtle",
    preserve_exact_timing: bool = False,
    section_names: list[str] | None = None,
    song_data: dict[str, Any] | None = None,
    section_lyrics: Mapping[str, Any] | None = None,
    lyric_cues: Mapping[str, Any] | None = None,
    feel_registry=DEFAULT_FEEL_REGISTRY,
) -> HarmonicRhythmResult:
    """Return a copy of ``sections`` with inferred anticipations applied."""
    level = humanize_level if humanize_level in _LEVEL_SCALE else "Subtle"
    if preserve_exact_timing or level == "Off" or not sections:
        return HarmonicRhythmResult(
            sections=copy.deepcopy(sections),
            annotations=(),
        )

    from songs.form import section_order

    genre = str((song_data or {}).get("genre") or "")
    artist = str((song_data or {}).get("artist") or "")
    song_id = str(
        (song_data or {}).get("title")
        or (song_data or {}).get("id")
        or "song"
    )
    profile = feel_registry.resolve(
        groove_style=groove_style,
        genre=genre,
        artist=artist,
    )
    bpb = beats_per_bar_from_signature(time_signature)

    source = {name: list(chords) for name, chords in sections.items()}
    out: dict[str, list[str]] = copy.deepcopy(source)
    annotations: list[InferredChange] = []
    section_templates: dict[tuple[str, tuple[str, ...]], list[_BarDecision | None]] = {}

    ordered = section_order(source, section_names=section_names)

    for sec_name, bars in ordered:
        if not bars:
            continue
        sig = tuple(str(t) for t in bars)
        archetype = _section_archetype(sec_name)
        template_key = (archetype, sig)
        vocal_density = _section_vocal_density(
            sec_name,
            lyric_cues=lyric_cues,
            section_lyrics=section_lyrics,
            song_data=song_data,
        )

        if template_key in section_templates:
            cached = section_templates[template_key]
            for bar_idx, decision in enumerate(cached):
                if bar_idx >= len(bars) or not decision or not decision.apply:
                    continue
                if token_has_explicit_timing(bars[bar_idx]):
                    continue
                out[sec_name][bar_idx] = decision.inferred_token or bars[bar_idx]
                annotations.append(
                    InferredChange(
                        section=sec_name,
                        bar=bar_idx + 1,
                        original_token=bars[bar_idx],
                        inferred_token=decision.inferred_token or bars[bar_idx],
                        reason=f"{decision.reason} — matched {archetype} repeat",
                        kind=decision.kind,
                        push_confidence=decision.push_confidence,
                        section_confidence=decision.section_confidence,
                    )
                )
            continue

        section_decisions: list[_BarDecision | None] = []
        for bar_idx, token in enumerate(bars):
            nxt_token = bars[bar_idx + 1] if bar_idx + 1 < len(bars) else ""
            nxt_nxt_token = bars[bar_idx + 2] if bar_idx + 2 < len(bars) else ""
            is_last = bar_idx == len(bars) - 1
            is_first = bar_idx == 0

            next_section_name = None
            if is_last:
                sec_list = [n for n, _ in ordered]
                try:
                    sec_i = sec_list.index(sec_name)
                    if sec_i + 1 < len(sec_list):
                        next_section_name = sec_list[sec_i + 1]
                        nxt_token = out.get(next_section_name, [""])[0] if out.get(next_section_name) else ""
                except ValueError:
                    pass

            decision = _evaluate_bar(
                sec_name=sec_name,
                bar_idx=bar_idx,
                token=str(token),
                nxt_token=str(nxt_token),
                nxt_nxt_token=str(nxt_nxt_token),
                is_last_in_section=is_last,
                is_first_in_section=is_first,
                next_section_name=next_section_name,
                profile=profile,
                level=level,
                bpb=bpb,
                song_id=song_id,
                groove_style=groove_style,
                vocal_density=vocal_density,
            )
            section_decisions.append(decision)

            if decision and decision.apply and decision.inferred_token:
                out[sec_name][bar_idx] = decision.inferred_token
                annotations.append(
                    InferredChange(
                        section=sec_name,
                        bar=bar_idx + 1,
                        original_token=str(token),
                        inferred_token=decision.inferred_token,
                        reason=decision.reason,
                        kind=decision.kind,
                        push_confidence=decision.push_confidence,
                        section_confidence=decision.section_confidence,
                    )
                )

        section_templates[template_key] = section_decisions

    return HarmonicRhythmResult(sections=out, annotations=tuple(annotations))
