"""Read-only coherent musical view over the active workflow blob — not a second state owner.

Mutations must update the workflow blob first; this module only resolves and validates.
Nothing here persists key, mode, section_map, or selected chord as an independent copy.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field, asdict
from typing import Any

VIOLATION_UNTRANSPOSED_GENERATED_ARTIFACT = "UNTRANSPOSED_GENERATED_ARTIFACT"
VIOLATION_KEY_TONIC_MODE_SPLIT = "KEY_TONIC_MODE_SPLIT"
VIOLATION_PROGRESSION_SINGLE_CHORD_REPLACES_SONG = "PROGRESSION_SINGLE_CHORD_REPLACES_SONG"
VIOLATION_STALE_GENERATED_OWNER_ON_SONG_TAB = "STALE_GENERATED_OWNER_ON_SONG_TAB"
VIOLATION_GENERATED_CONTEXT_SPLIT_SOURCES = "GENERATED_CONTEXT_SPLIT_SOURCES"
# Legacy alias — prefer UNTRANSPOSED_GENERATED_ARTIFACT
VIOLATION_KEY_PROGRESSION_CENTER_MISMATCH = VIOLATION_UNTRANSPOSED_GENERATED_ARTIFACT

MUSICAL_CONTEXT_COHERENCE_BLOCK_KEY = "_musical_context_coherence_handoff_block"
MUSICAL_CONTEXT_COHERENCE_DIAG_KEY = "_musical_context_coherence_diag"

GENERATED_OWNERS = frozenset({"jam_session_generator", "style_jam"})
SONG_OWNERS = frozenset({"song_based_improvisation", "mission_jam"})


class CreativeBackingHandoffBlocked(RuntimeError):
    """Controlled failure — do not open Backing with a hybrid/incoherent generated context."""


@dataclass(frozen=True)
class CoherentMusicalContext:
    """Derived read-only projection of one workflow blob — never written back to session as authority."""

    owner: str
    workflow_session_id: str
    practice_tonic: str
    practice_mode: str
    key_token: str
    section_map: dict[str, list[str]]
    selected_section: str
    selected_chord: str
    original_tonic: str = ""
    original_mode: str = ""
    style_id: str = ""
    mood: str = ""
    difficulty: str = "Intermediate"
    progression_flat: tuple[str, ...] = field(default_factory=tuple)
    sources: dict[str, str] = field(default_factory=dict)


def _key_token_from_parts(tonic: str, mode: str) -> str:
    from music_theory import key_center_token

    return key_center_token(str(tonic or "C").strip() or "C", str(mode or "major").strip() or "major")


def _flatten_section_map(section_map: dict[str, list[str]]) -> list[str]:
    try:
        from improvisation_intelligence import flatten_sections

        return flatten_sections(section_map)
    except ImportError:
        out: list[str] = []
        for chords in section_map.values():
            if isinstance(chords, list):
                out.extend(str(c) for c in chords if str(c).strip())
        return out


def infer_major_tonic_from_progression(flat: list[str]) -> str:
    """Heuristic major tonic (last maj7 root spelling) — used only with provenance checks."""
    if not flat:
        return ""
    try:
        from harmonic_spelling import spelled_chord_root_from_symbol

        for ch in reversed(flat):
            sym = str(ch or "").strip()
            if not sym:
                continue
            sl = sym.lower()
            if "maj7" in sl and "m7" not in sl.replace("maj7", ""):
                spelled = spelled_chord_root_from_symbol(sym)
                if spelled:
                    return spelled
        for ch in flat:
            sym = str(ch or "").strip()
            if sym.lower().endswith("maj7"):
                spelled = spelled_chord_root_from_symbol(sym)
                if spelled:
                    return spelled
    except ImportError:
        pass
    return ""


def _progression_head(flat: list[str], n: int = 6) -> tuple[str, ...]:
    return tuple(str(c).strip() for c in flat[:n] if str(c).strip())


def _sections_head_match(expected: dict[str, list[str]], actual: dict[str, list[str]], n: int = 6) -> bool:
    return _progression_head(_flatten_section_map(expected), n) == _progression_head(_flatten_section_map(actual), n)


def _generated_progression_at_key(
    *,
    style: str,
    key_center: str,
    mood: str,
    difficulty: str,
) -> dict[str, list[str]]:
    from improvisation_intelligence import generate_style_progression

    return generate_style_progression(
        style=str(style or "Jazz Swing"),
        key_center=str(key_center or "C"),
        mood=str(mood or "Mellow"),
        difficulty=str(difficulty or "Intermediate"),
        seed=0,
    )


def validate_untransposed_generated_artifact(ctx: CoherentMusicalContext) -> list[str]:
    """Detect sealed key change without transposed section map — not general non-diatonic harmony."""
    if ctx.owner not in GENERATED_OWNERS:
        return []
    flat = list(ctx.progression_flat) or _flatten_section_map(ctx.section_map)
    if not flat or str(ctx.practice_mode or "").lower() != "major":
        return []

    practice_token = str(ctx.key_token or "").strip()
    orig_token = _key_token_from_parts(ctx.original_tonic or ctx.practice_tonic, ctx.original_mode or ctx.practice_mode)
    style = str(ctx.style_id or "Jazz Swing").strip() or "Jazz Swing"
    mood = str(ctx.mood or "Mellow").strip() or "Mellow"
    difficulty = str(ctx.difficulty or "Intermediate").strip() or "Intermediate"

    try:
        from music_theory import normalize_root, semitone_distance, split_chord

        practice_root = normalize_root(split_chord(practice_token)[0])
        orig_root = normalize_root(split_chord(orig_token)[0])
        inferred = infer_major_tonic_from_progression(flat)
        inferred_root = normalize_root(split_chord(inferred)[0]) if inferred else ""

        # Provenance: blob records original ≠ practice but progression still centered on original tonic.
        if orig_token != practice_token and inferred_root:
            if semitone_distance(inferred_root, orig_root) == 0 and semitone_distance(inferred_root, practice_root) != 0:
                return [
                    f"{VIOLATION_UNTRANSPOSED_GENERATED_ARTIFACT} "
                    f"original={orig_token} practice={practice_token} progression_center={inferred}"
                ]

        # Template match: section map still equals style template at original/inferred center, not at practice key.
        at_practice = _generated_progression_at_key(
            style=style, key_center=practice_token, mood=mood, difficulty=difficulty
        )
        if _sections_head_match(at_practice, ctx.section_map, n=3):
            return []

        for candidate in (orig_token, inferred):
            if not candidate:
                continue
            if semitone_distance(normalize_root(split_chord(candidate)[0]), practice_root) == 0:
                continue
            at_candidate = _generated_progression_at_key(
                style=style, key_center=candidate, mood=mood, difficulty=difficulty
            )
            if _sections_head_match(at_candidate, ctx.section_map, n=3):
                return [
                    f"{VIOLATION_UNTRANSPOSED_GENERATED_ARTIFACT} "
                    f"practice={practice_token} matches_template_at={candidate}"
                ]
    except ImportError:
        pass
    return []


def validate_coherent_musical_context(ctx: CoherentMusicalContext) -> list[str]:
    violations: list[str] = []
    declared = str(ctx.key_token or "").strip()
    try:
        from music_theory import key_is_minor
    except ImportError:
        key_is_minor = lambda _k: False  # type: ignore

    if declared and key_is_minor(declared) != (str(ctx.practice_mode or "") == "minor"):
        violations.append(VIOLATION_KEY_TONIC_MODE_SPLIT)

    violations.extend(validate_untransposed_generated_artifact(ctx))

    if ctx.owner in SONG_OWNERS:
        total = sum(len(v) for v in ctx.section_map.values() if isinstance(v, list))
        if total == 1 and len(ctx.section_map) <= 1:
            violations.append(VIOLATION_PROGRESSION_SINGLE_CHORD_REPLACES_SONG)

    return violations


def resolve_coherent_musical_context(
    session: dict[str, Any],
    *,
    prefer_owners: tuple[str, ...] | None = None,
) -> CoherentMusicalContext | None:
    """Read-only: active workflow blob → single coherent view (no session persistence)."""
    try:
        from music_workflow_state_store import get_active_workflow_pointer, get_workflow_blob

        ptr = get_active_workflow_pointer(session)
        if ptr and ptr.workflow_owner:
            owner = str(ptr.workflow_owner or "")
            if prefer_owners and owner not in prefer_owners:
                return None
            blob = get_workflow_blob(session, owner, str(ptr.workflow_session_id or ""))
            if blob is None:
                return None
            section_map = copy.deepcopy(blob.section_map or {})
            tonic = str(blob.keys.practice_tonic or "C").strip() or "C"
            mode = str(blob.keys.practice_mode or "major").strip() or "major"
            o_tonic = str(blob.keys.original_tonic or tonic).strip() or tonic
            o_mode = str(blob.keys.original_mode or mode).strip() or mode
            token = _key_token_from_parts(tonic, mode)
            flat = tuple(_flatten_section_map(section_map))
            return CoherentMusicalContext(
                owner=owner,
                workflow_session_id=str(blob.workflow_session_id or ""),
                practice_tonic=tonic,
                practice_mode=mode,
                key_token=token,
                section_map=section_map,
                selected_section=str(blob.selected_section or ""),
                selected_chord=str(blob.selected_chord_symbol or ""),
                original_tonic=o_tonic,
                original_mode=o_mode,
                style_id=str(blob.style or ""),
                mood=str(blob.mood or "Mellow"),
                difficulty=str(session.get("improv_difficulty") or "Intermediate"),
                progression_flat=flat,
                sources={
                    "key": f"workflow_blob:{owner}",
                    "section_map": f"workflow_blob:{owner}",
                    "selected_chord": f"workflow_blob:{owner}",
                },
            )
    except ImportError:
        return None
    return None


def _context_diag_summary(ctx: CoherentMusicalContext | None) -> dict[str, Any] | None:
    if ctx is None:
        return None
    return {
        "owner": ctx.owner,
        "workflow_session_id": ctx.workflow_session_id,
        "key_token": ctx.key_token,
        "original_key_token": _key_token_from_parts(ctx.original_tonic, ctx.original_mode),
        "style_id": ctx.style_id,
        "section_count": sum(len(v) for v in ctx.section_map.values() if isinstance(v, list)),
        "selected_section": ctx.selected_section,
        "selected_chord": ctx.selected_chord,
        "sources": dict(ctx.sources),
    }


def record_coherence_handoff_block(session: dict[str, Any], violations: list[str]) -> None:
    """Fail closed with diagnostics — no stale artifact fallback."""
    from generated_workflow_artifact import WORKFLOW_OWNER_INTEGRITY_USER_MESSAGE_KEY

    msg = "; ".join(str(v) for v in violations if str(v).strip())
    session[WORKFLOW_OWNER_INTEGRITY_USER_MESSAGE_KEY] = msg
    session[MUSICAL_CONTEXT_COHERENCE_BLOCK_KEY] = {
        "blocked": True,
        "violations": list(violations),
    }


def clear_coherence_handoff_block(session: dict[str, Any]) -> None:
    """Remove handoff block after a successful coherent seal or backing context."""
    session.pop(MUSICAL_CONTEXT_COHERENCE_BLOCK_KEY, None)
    try:
        from generated_workflow_artifact import WORKFLOW_OWNER_INTEGRITY_USER_MESSAGE_KEY

        session.pop(WORKFLOW_OWNER_INTEGRITY_USER_MESSAGE_KEY, None)
    except ImportError:
        pass


def raise_coherence_handoff_blocked(session: dict[str, Any], violations: list[str]) -> None:
    record_coherence_handoff_block(session, violations)
    raise CreativeBackingHandoffBlocked(violations[0] if violations else VIOLATION_UNTRANSPOSED_GENERATED_ARTIFACT)


def validate_session_owner_leaks(session: dict[str, Any]) -> list[str]:
    violations: list[str] = []
    try:
        from generated_jam_key_context import generated_jam_owns_practice_key
        from musical_context_authority import song_catalog_context_owns_practice_key

        if song_catalog_context_owns_practice_key(session) and generated_jam_owns_practice_key(session):
            violations.append(VIOLATION_STALE_GENERATED_OWNER_ON_SONG_TAB)
    except ImportError:
        pass
    return violations


def run_musical_context_coherence_checks(session: dict[str, Any]) -> dict[str, Any]:
    ctx = resolve_coherent_musical_context(session)
    violations: list[str] = []
    violations.extend(validate_session_owner_leaks(session))
    if ctx is not None:
        violations.extend(validate_coherent_musical_context(ctx))
    diag = {
        "coherent_context_summary": _context_diag_summary(ctx),
        "violations": violations,
        "consistent": not violations,
    }
    session[MUSICAL_CONTEXT_COHERENCE_DIAG_KEY] = diag
    return diag


def validate_generated_snapshot_coherence(
    *,
    practice_tonic: str,
    practice_mode: str,
    progression: list[str],
    original_tonic: str = "",
    original_mode: str = "",
    style_id: str = "",
    mood: str = "Mellow",
    owner: str = "jam_session_generator",
) -> list[str]:
    token = _key_token_from_parts(practice_tonic, practice_mode)
    ctx = CoherentMusicalContext(
        owner=owner,
        workflow_session_id="",
        practice_tonic=practice_tonic,
        practice_mode=practice_mode,
        key_token=token,
        section_map={"_": list(progression or [])},
        selected_section="",
        selected_chord="",
        original_tonic=original_tonic or practice_tonic,
        original_mode=original_mode or practice_mode,
        style_id=style_id,
        mood=mood,
        progression_flat=tuple(progression or []),
        sources={"progression": "artifact_snapshot"},
    )
    return validate_coherent_musical_context(ctx)


def validate_hybrid_generated_session_split(
    session: dict[str, Any],
    *,
    declared_key: str,
    progression: list[str],
    style_id: str = "Jazz Swing",
) -> list[str]:
    """Session-level hybrid: widget key vs session jam sections without blob authority."""
    if not progression:
        return []
    try:
        from music_theory import split_key_center

        tonic, mode = split_key_center(str(declared_key or "C"))
    except ImportError:
        tonic, mode = str(declared_key or "C"), "major"
    if mode not in {"major", "minor"}:
        mode = "major"
    mood = str(
        session.get("improv_mood") or session.get("improv_jam_mood") or "Mellow"
    ).strip() or "Mellow"
    ctx = CoherentMusicalContext(
        owner="style_jam" if str(session.get("improv_entry_mode") or "") == "Style Jam Mode" else "jam_session_generator",
        workflow_session_id="",
        practice_tonic=tonic,
        practice_mode=mode,
        key_token=str(declared_key or "C"),
        section_map={"_": list(progression)},
        selected_section="",
        selected_chord="",
        style_id=style_id,
        mood=mood,
        progression_flat=tuple(progression),
        sources={"progression": "session_improv_jam_session", "key": "session_widget"},
    )
    return validate_untransposed_generated_artifact(ctx)


__all__ = [
    "CoherentMusicalContext",
    "CreativeBackingHandoffBlocked",
    "GENERATED_OWNERS",
    "MUSICAL_CONTEXT_COHERENCE_BLOCK_KEY",
    "MUSICAL_CONTEXT_COHERENCE_DIAG_KEY",
    "SONG_OWNERS",
    "VIOLATION_GENERATED_CONTEXT_SPLIT_SOURCES",
    "VIOLATION_KEY_PROGRESSION_CENTER_MISMATCH",
    "VIOLATION_KEY_TONIC_MODE_SPLIT",
    "VIOLATION_PROGRESSION_SINGLE_CHORD_REPLACES_SONG",
    "VIOLATION_STALE_GENERATED_OWNER_ON_SONG_TAB",
    "VIOLATION_UNTRANSPOSED_GENERATED_ARTIFACT",
    "infer_major_tonic_from_progression",
    "raise_coherence_handoff_blocked",
    "clear_coherence_handoff_block",
    "record_coherence_handoff_block",
    "resolve_coherent_musical_context",
    "run_musical_context_coherence_checks",
    "validate_coherent_musical_context",
    "validate_generated_snapshot_coherence",
    "validate_hybrid_generated_session_split",
    "validate_session_owner_leaks",
    "validate_untransposed_generated_artifact",
]
