"""Authoritative mission type + exact chord context for practice, backing, recording, and analysis."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any

from music_theory import (
    chord_quality_label,
    classify_chord_quality,
    normalize_chord_for_theory,
    split_chord,
)

MISSION_PRACTICE_CONTEXT_KEY = "improv_mission_practice_context"
MISSION_RECORDING_SEAL_KEY = "improv_mission_recording_seal"
MISSION_BACKING_SOUNDING_CHORD_KEY = "_mission_backing_sounding_chord"
MISSION_EXACT_BACKING_ARMED_KEY = "_mission_exact_backing_armed"
MISSION_CAPTURE_BLOCK_MESSAGE_KEY = "_mission_capture_block_message"
MISSION_PRACTICE_CONTEXT_SIG_KEY = "_mission_practice_context_sig"
MISSION_PRACTICE_CONTEXT_NEEDS_REFRESH_KEY = "_mission_practice_context_needs_refresh"
MISSION_RECORDING_STUDIO_ENGAGED_KEY = "_mission_recording_studio_engaged"

_CONTEXT_VERSION = 1


@dataclass
class ParsedMissionChord:
    symbol: str = ""
    root: str = ""
    quality: str = ""
    quality_label: str = ""
    extensions: str = ""
    bass: str = ""
    inversion_hint: str = ""
    section: str = ""
    chord_index: int = 0
    chord_label: str = ""


@dataclass
class MissionPracticeContext:
    version: int = _CONTEXT_VERSION
    mission_type: str = ""
    mission_pick: str = ""
    chord: ParsedMissionChord = field(default_factory=ParsedMissionChord)
    tempo_bpm: int = 100
    backing_style: str = ""
    backing_groove: str = ""
    meter: str = "4/4"
    loop: bool = True
    loops: int = 4
    volume: float = 0.85
    count_in_bars: int = 0
    song_title: str = ""
    pick_key: str = ""
    display_key: str = ""
    recording_association: str = ""
    context_fingerprint: str = ""
    sealed_at: str = ""
    evaluation_focus: str = ""
    score_against_example: bool = False

    def to_dict(self) -> dict[str, Any]:
        raw = asdict(self)
        return raw

    @classmethod
    def from_dict(cls, raw: Any) -> MissionPracticeContext | None:
        if not isinstance(raw, dict):
            return None
        chord_raw = raw.get("chord") if isinstance(raw.get("chord"), dict) else {}
        chord = ParsedMissionChord(
            symbol=str(chord_raw.get("symbol") or ""),
            root=str(chord_raw.get("root") or ""),
            quality=str(chord_raw.get("quality") or ""),
            quality_label=str(chord_raw.get("quality_label") or ""),
            extensions=str(chord_raw.get("extensions") or ""),
            bass=str(chord_raw.get("bass") or ""),
            inversion_hint=str(chord_raw.get("inversion_hint") or ""),
            section=str(chord_raw.get("section") or ""),
            chord_index=int(chord_raw.get("chord_index") or 0),
            chord_label=str(chord_raw.get("chord_label") or ""),
        )
        return cls(
            version=int(raw.get("version") or _CONTEXT_VERSION),
            mission_type=str(raw.get("mission_type") or ""),
            mission_pick=str(raw.get("mission_pick") or ""),
            chord=chord,
            tempo_bpm=int(raw.get("tempo_bpm") or 100),
            backing_style=str(raw.get("backing_style") or ""),
            backing_groove=str(raw.get("backing_groove") or ""),
            meter=str(raw.get("meter") or "4/4"),
            loop=bool(raw.get("loop", True)),
            loops=int(raw.get("loops") or 4),
            volume=float(raw.get("volume") or 0.85),
            count_in_bars=int(raw.get("count_in_bars") or 0),
            song_title=str(raw.get("song_title") or ""),
            pick_key=str(raw.get("pick_key") or ""),
            display_key=str(raw.get("display_key") or ""),
            recording_association=str(raw.get("recording_association") or ""),
            context_fingerprint=str(raw.get("context_fingerprint") or ""),
            sealed_at=str(raw.get("sealed_at") or ""),
            evaluation_focus=str(raw.get("evaluation_focus") or ""),
            score_against_example=bool(raw.get("score_against_example")),
        )


def parse_mission_chord(
    symbol: str,
    *,
    section: str = "",
    chord_index: int = 0,
    chord_label: str = "",
) -> ParsedMissionChord:
    head = normalize_chord_for_theory(symbol)
    if not head:
        return ParsedMissionChord(
            symbol=str(symbol or "").strip(),
            section=section,
            chord_index=chord_index,
            chord_label=chord_label or str(symbol or "").strip(),
        )
    slash_parts = head.split("/", 1)
    head_symbol = slash_parts[0].strip()
    bass = slash_parts[1].strip() if len(slash_parts) > 1 else ""
    root, suffix = split_chord(head_symbol)
    quality = classify_chord_quality(head_symbol)
    inversion_hint = ""
    if bass and bass != root:
        inversion_hint = f"/{bass}"
    return ParsedMissionChord(
        symbol=str(symbol or "").strip(),
        root=root,
        quality=quality,
        quality_label=chord_quality_label(head_symbol),
        extensions=str(suffix or "").strip(),
        bass=bass,
        inversion_hint=inversion_hint,
        section=str(section or "").strip(),
        chord_index=int(chord_index),
        chord_label=str(chord_label or symbol or "").strip(),
    )


def _authoritative_chord_fields(session: dict[str, Any]) -> tuple[str, str, int, str]:
    try:
        from creative_mission_config_persistence import canonical_mission_config_value
    except ImportError:
        canonical_mission_config_value = lambda _s, k: _s.get(k)  # type: ignore[assignment,misc]

    chords_flat = session.get("improv_mission_chord_options")
    idx_raw = canonical_mission_config_value(session, "ii_selected_chord_index")
    if idx_raw is None:
        idx_raw = session.get("ii_selected_chord_index")
    try:
        idx = int(idx_raw or 0)
    except (TypeError, ValueError):
        idx = 0
    symbol = ""
    if isinstance(chords_flat, list) and chords_flat:
        idx = max(0, min(idx, len(chords_flat) - 1))
        symbol = str(chords_flat[idx] or "").strip()
    if not symbol:
        symbol = str(canonical_mission_config_value(session, "ii_selected_chord") or "").strip()
    section = str(canonical_mission_config_value(session, "ii_selected_section") or "").strip()
    label = str(canonical_mission_config_value(session, "ii_selected_chord_label") or "").strip() or symbol
    return symbol, section, idx, label


def authoritative_mission_type(session: dict[str, Any]) -> str:
    try:
        from creative_mission_config_persistence import canonical_mission_config_value
    except ImportError:
        canonical_mission_config_value = lambda _s, k: _s.get(k)  # type: ignore[assignment,misc]

    pick = str(canonical_mission_config_value(session, "improv_mission_pick") or "").strip()
    active = str(canonical_mission_config_value(session, "improv_active_mission") or "").strip()
    return pick or active


def context_fingerprint(ctx: MissionPracticeContext) -> str:
    payload = {
        "v": ctx.version,
        "mission": ctx.mission_type,
        "chord": ctx.chord.symbol,
        "idx": ctx.chord.chord_index,
        "section": ctx.chord.section,
        "bpm": ctx.tempo_bpm,
        "style": ctx.backing_style,
        "groove": ctx.backing_groove,
        "meter": ctx.meter,
        "evaluation_focus": ctx.evaluation_focus,
        "score_against_example": ctx.score_against_example,
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:24]


def build_mission_practice_context(session: dict[str, Any]) -> MissionPracticeContext:
    try:
        from mission_song_backing_style import sync_mission_style_from_song

        sync_mission_style_from_song(session)
    except ImportError:
        pass
    mission_type = authoritative_mission_type(session)
    symbol, section, idx, label = _authoritative_chord_fields(session)
    parsed = parse_mission_chord(symbol, section=section, chord_index=idx, chord_label=label)

    style_meta = session.get("improv_style_meta") if isinstance(session.get("improv_style_meta"), dict) else {}
    bpm = int(
        session.get("backing_track_bpm")
        or style_meta.get("bpm")
        or session.get("improv_style_bpm")
        or 100
    )
    style = str(style_meta.get("style") or session.get("improv_style") or session.get("backing_groove_style") or "")
    groove = str(style_meta.get("groove") or session.get("improv_groove") or session.get("backing_groove_style") or "")
    meter = str(
        style_meta.get("meter")
        or session.get("improv_style_meter")
        or session.get("backing_time_signature")
        or "4/4"
    ).strip()
    loops = int(session.get("backing_track_loops") or session.get("improv_mission_loops") or 4)
    loop = bool(session.get("mission_exact_backing_loop", True))
    try:
        volume = float(session.get("mission_exact_backing_volume", 0.85))
    except (TypeError, ValueError):
        volume = 0.85
    count_in = 1 if session.get("mission_exact_backing_count_in") else 0

    song_title = str(session.get("song") or "").strip()
    pick_key = str(session.get("active_catalog_pick_key") or session.get("_active_pick_key") or "").strip()
    display_key = str(session.get("display_key") or session.get("chart_key") or "").strip()

    try:
        from mission_evaluation_focus import (
            authoritative_evaluation_focus,
            example_match_mode_enabled,
        )

        eval_focus = authoritative_evaluation_focus(session)
        match_example = example_match_mode_enabled(session)
    except ImportError:
        eval_focus = ""
        match_example = False

    ctx = MissionPracticeContext(
        mission_type=mission_type,
        mission_pick=mission_type,
        chord=parsed,
        tempo_bpm=max(40, min(240, bpm)),
        backing_style=style,
        backing_groove=groove or style,
        meter=meter or "4/4",
        loop=loop,
        loops=max(1, loops),
        volume=max(0.05, min(1.0, volume)),
        count_in_bars=count_in,
        song_title=song_title,
        pick_key=pick_key,
        display_key=display_key,
        evaluation_focus=eval_focus,
        score_against_example=match_example,
    )
    ctx.context_fingerprint = context_fingerprint(ctx)
    return ctx


def write_mission_practice_context(session: dict[str, Any], ctx: MissionPracticeContext) -> None:
    prev = session.get(MISSION_PRACTICE_CONTEXT_KEY)
    prev_fp = ""
    if isinstance(prev, dict):
        prev_fp = str(prev.get("context_fingerprint") or "")
    ctx.context_fingerprint = context_fingerprint(ctx)
    session[MISSION_PRACTICE_CONTEXT_KEY] = ctx.to_dict()
    if prev_fp and prev_fp != ctx.context_fingerprint:
        session.pop(MISSION_EXACT_BACKING_ARMED_KEY, None)
        try:
            from mission_exact_chord_backing import invalidate_exact_chord_backing_cache

            invalidate_exact_chord_backing_cache(session)
        except ImportError:
            pass


def mission_practice_context_input_signature(session: dict[str, Any]) -> tuple[Any, ...]:
    symbol, section, idx, label = _authoritative_chord_fields(session)
    return (
        authoritative_mission_type(session),
        symbol,
        section,
        idx,
        label,
        int(session.get("backing_track_bpm") or 0),
        str(session.get("backing_groove_style") or session.get("improv_groove") or ""),
        str(session.get("backing_time_signature") or "4/4"),
        int(session.get("backing_track_loops") or 0),
        bool(session.get("mission_exact_backing_loop", True)),
        round(float(session.get("mission_exact_backing_volume") or 0.85), 2),
        bool(session.get("mission_exact_backing_count_in")),
        str(session.get("improv_mission_evaluation_focus") or ""),
        bool(session.get("improv_mission_match_example_mode")),
    )


def mark_mission_practice_context_dirty(session: dict[str, Any]) -> None:
    session[MISSION_PRACTICE_CONTEXT_NEEDS_REFRESH_KEY] = True


def refresh_mission_practice_context(session: dict[str, Any]) -> MissionPracticeContext:
    ctx = build_mission_practice_context(session)
    write_mission_practice_context(session, ctx)
    session[MISSION_PRACTICE_CONTEXT_SIG_KEY] = mission_practice_context_input_signature(session)
    session.pop(MISSION_PRACTICE_CONTEXT_NEEDS_REFRESH_KEY, None)
    return ctx


def ensure_mission_practice_context(
    session: dict[str, Any],
    *,
    force: bool = False,
) -> MissionPracticeContext | None:
    if not force and not session.get(MISSION_PRACTICE_CONTEXT_NEEDS_REFRESH_KEY):
        sig = mission_practice_context_input_signature(session)
        if session.get(MISSION_PRACTICE_CONTEXT_SIG_KEY) == sig:
            loaded = MissionPracticeContext.from_dict(session.get(MISSION_PRACTICE_CONTEXT_KEY))
            if loaded is not None:
                return loaded
    if not force and not authoritative_mission_type(session) and not _authoritative_chord_fields(session)[0]:
        return None
    return refresh_mission_practice_context(session)


def load_mission_practice_context(session: dict[str, Any]) -> MissionPracticeContext | None:
    return ensure_mission_practice_context(session)


def backing_sounding_chord(session: dict[str, Any]) -> str:
    explicit = str(session.get(MISSION_BACKING_SOUNDING_CHORD_KEY) or "").strip()
    if explicit:
        return explicit
    try:
        from backing_context import get_backing_context

        ctx = get_backing_context(session)
        if ctx and ctx.source == "mission" and ctx.progression:
            return str(ctx.progression[0] or "").strip()
    except ImportError:
        pass
    return ""


def ui_backing_chord_mismatch(session: dict[str, Any]) -> tuple[bool, str]:
    """True when UI-selected chord disagrees with the chord backing is bound to."""
    symbol, _section, _idx, _label = _authoritative_chord_fields(session)
    if not symbol:
        return False, ""
    sounding = backing_sounding_chord(session)
    if not sounding:
        return False, ""
    ui_norm = normalize_chord_for_theory(symbol)
    back_norm = normalize_chord_for_theory(sounding)
    if ui_norm and back_norm and ui_norm != back_norm:
        return True, f"UI chord **{symbol}** does not match backing **{sounding}**. Press Play on exact-chord backing to sync."
    return False, ""


def seal_recording_context(session: dict[str, Any], *, association: str = "") -> MissionPracticeContext:
    from datetime import datetime, timezone

    ctx = build_mission_practice_context(session)
    ctx.sealed_at = datetime.now(timezone.utc).isoformat()
    if association:
        ctx.recording_association = association
    seal = copy.deepcopy(ctx.to_dict())
    session[MISSION_RECORDING_SEAL_KEY] = seal
    session[MISSION_EXACT_BACKING_ARMED_KEY] = True
    session.pop(MISSION_CAPTURE_BLOCK_MESSAGE_KEY, None)
    write_mission_practice_context(session, ctx)
    return ctx


def recording_context_stale_warning(session: dict[str, Any]) -> str:
    seal_raw = session.get(MISSION_RECORDING_SEAL_KEY)
    sealed = MissionPracticeContext.from_dict(seal_raw)
    if not sealed:
        return ""
    live = build_mission_practice_context(session)
    if sealed.context_fingerprint and sealed.context_fingerprint == live.context_fingerprint:
        return ""
    parts: list[str] = []
    if sealed.mission_type != live.mission_type:
        parts.append(f"mission changed from “{sealed.mission_type}” to “{live.mission_type}”")
    if sealed.chord.symbol != live.chord.symbol or sealed.chord.chord_index != live.chord.chord_index:
        parts.append(
            f"chord changed from **{sealed.chord.symbol}** ({sealed.chord.section}) "
            f"to **{live.chord.symbol}** ({live.chord.section})"
        )
    if sealed.tempo_bpm != live.tempo_bpm:
        parts.append(f"tempo changed from {sealed.tempo_bpm} to {live.tempo_bpm} BPM")
    if sealed.evaluation_focus != live.evaluation_focus:
        parts.append(
            f"evaluation focus changed from “{sealed.evaluation_focus}” to “{live.evaluation_focus}”"
        )
    if not parts:
        return "Mission practice context changed after this take was prepared."
    return "Take context changed: " + "; ".join(parts) + "."


def mission_capture_allowed(
    session: dict[str, Any],
    *,
    require_mission_workflow: bool,
    capture_path: str = "live",
) -> tuple[bool, str]:
    if not require_mission_workflow:
        return True, ""
    mission_type = authoritative_mission_type(session)
    symbol, _s, _i, _l = _authoritative_chord_fields(session)
    if not mission_type and not symbol:
        return True, ""

    mismatch, msg = ui_backing_chord_mismatch(session)
    if mismatch:
        session[MISSION_CAPTURE_BLOCK_MESSAGE_KEY] = msg
        return False, msg

    path = str(capture_path or "live").strip().lower()
    if path == "analysis":
        stale = recording_context_stale_warning(session)
        if stale:
            session[MISSION_CAPTURE_BLOCK_MESSAGE_KEY] = stale
            return False, stale
        return True, ""

    if path == "upload":
        session.pop(MISSION_CAPTURE_BLOCK_MESSAGE_KEY, None)
        return True, ""

    session.pop(MISSION_CAPTURE_BLOCK_MESSAGE_KEY, None)
    return True, ""


def enrich_analysis_context(session: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    """Attach authoritative mission type/chord and prefer single-chord scoring pool."""
    out = dict(ctx)
    mpc = ensure_mission_practice_context(session, force=True)
    if mpc is None:
        return out
    out["mission_practice_context"] = mpc.to_dict()
    out["improv_active_mission"] = mpc.mission_type
    out["mission_type"] = mpc.mission_type
    out["mission_chord"] = mpc.chord.symbol
    out["mission_section"] = mpc.chord.section
    out["mission_chord_index"] = mpc.chord.chord_index
    if mpc.chord.symbol:
        out["target_chords"] = [mpc.chord.symbol]
        sections = out.get("sections")
        if isinstance(sections, dict) and mpc.chord.section:
            out["sections"] = {mpc.chord.section: [mpc.chord.symbol]}
    out["evaluation_focus"] = mpc.evaluation_focus
    out["mission_evaluation_focus"] = mpc.evaluation_focus
    out["score_against_example"] = mpc.score_against_example
    if not mpc.score_against_example:
        out["optional_mission_example_only"] = True
    stale = recording_context_stale_warning(session)
    if stale:
        out["mission_context_stale_warning"] = stale
    return out


def validate_analysis_mission_context(session: dict[str, Any]) -> tuple[bool, str]:
    try:
        from mission_analysis_ui import is_analysis_criteria_locked
    except ImportError:
        is_analysis_criteria_locked = lambda _s: False  # type: ignore[assignment,misc]

    locked = is_analysis_criteria_locked(session)
    mission_type = authoritative_mission_type(session)
    symbol, _s, _i, _l = _authoritative_chord_fields(session)
    if locked and not (mission_type or symbol):
        return False, "Upload Analysis is locked to a mission take but mission type/chord are missing. Re-open from Metrics & AI."
    ok, msg = mission_capture_allowed(
        session,
        require_mission_workflow=locked,
        capture_path="analysis",
    )
    if not ok:
        return False, msg
    return True, ""


def hydrate_mission_practice_context_after_restore(session: dict[str, Any]) -> None:
    raw = session.get(MISSION_PRACTICE_CONTEXT_KEY)
    if isinstance(raw, dict) and raw.get("mission_type"):
        restored = MissionPracticeContext.from_dict(raw)
        if restored:
            live = build_mission_practice_context(session)
            if live.chord.symbol and not restored.chord.symbol:
                write_mission_practice_context(session, live)
            return
    refresh_mission_practice_context(session)
