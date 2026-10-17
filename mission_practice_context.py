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
# Set while the sealed context belongs to a take restored from the pending-upload envelope: that take is
# judged and coached against the context it was recorded with, not against the Mission as it is now.
MISSION_SEALED_BY_ENVELOPE_KEY = "_mission_take_sealed_by_envelope"
# The take's analysis context (Practice Focus, level, instruments, Evaluation Criteria) as recorded; only
# meaningful while MISSION_SEALED_BY_ENVELOPE_KEY is set.
MISSION_SEALED_ANALYSIS_KEY = "_mission_take_sealed_analysis_context"
# The restored take's own copy of its sealed Mission context. MISSION_RECORDING_SEAL_KEY is the *working*
# seal for the live Mission (staging a backing, opening Upload Analysis, recording … all re-seal it from
# live state), so the saved take must not live there.
MISSION_TAKE_SEAL_KEY = "_mission_take_sealed_context"


def end_restored_take_authority(session: dict[str, Any]) -> None:
    """A new take, a new handoff, or clearing the prepared take ends the restored take's authority."""
    for key in (MISSION_SEALED_BY_ENVELOPE_KEY, MISSION_TAKE_SEAL_KEY, MISSION_SEALED_ANALYSIS_KEY):
        session.pop(key, None)


def sealed_take_context(session: dict[str, Any]) -> "MissionPracticeContext | None":
    """The Mission context a restored take was recorded with (None for a live take)."""
    if not session.get(MISSION_SEALED_BY_ENVELOPE_KEY):
        return None
    return MissionPracticeContext.from_dict(session.get(MISSION_TAKE_SEAL_KEY))


def sealed_take_analysis_context(session: dict[str, Any]) -> dict[str, Any]:
    """What a restored take was recorded with, or {} (a live take / no restored context)."""
    if not session.get(MISSION_SEALED_BY_ENVELOPE_KEY):
        return {}
    block = session.get(MISSION_SEALED_ANALYSIS_KEY)
    return block if isinstance(block, dict) else {}

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
    # MC4: 2- / 3-chord Missions only (mission_span_recording_context). Absent → one-chord take,
    # and the serialized dict / fingerprint are exactly what they were before.
    span: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        raw = asdict(self)
        if raw.get("span") is None:
            raw.pop("span", None)
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
            span=copy.deepcopy(raw["span"]) if isinstance(raw.get("span"), dict) else None,
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
    if ctx.span:
        # Span takes: the span identity (song, span, Mission, key, timeline, tempo, meter,
        # instrument). Never added for one-chord takes, whose fingerprint is unchanged.
        payload["span"] = str(ctx.span.get("span_fingerprint") or "")
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
        mission_tempo_override(session)
        or session.get("backing_track_bpm")
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
    loops = int(mission_passes_override(session) or session.get("backing_track_loops") or session.get("improv_mission_loops") or 4)
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
    try:
        from mission_span_recording_context import build_span_block

        span = build_span_block(
            session, bpm=ctx.tempo_bpm, meter=ctx.meter, loops=ctx.loops, count_in_bars=ctx.count_in_bars,
        )
    except Exception:
        span = None
    if span:
        ctx.span = span
        ctx.mission_type = str(span.get("mission_label") or ctx.mission_type)
        ctx.mission_pick = ctx.mission_type
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


def _span_signature(session: dict[str, Any]) -> tuple[Any, ...]:
    """Inputs of the MC4 span block — only while a 2/3-chord Mission scope is active."""
    try:
        from mission_span_recording_context import (
            MISSION_SPAN_RECORDING_CONTEXT_KEY,
            _live_practice_key,
            _song_session,
            span_scope_active,
            timeline_fingerprint,
        )
    except ImportError:
        return ()
    if not span_scope_active(session):
        return ()
    raw = session.get(MISSION_SPAN_RECORDING_CONTEXT_KEY)
    raw = raw if isinstance(raw, dict) else {}
    return (
        "span",
        str(raw.get("scope") or ""),
        timeline_fingerprint(raw.get("timeline") or []),
        str(raw.get("span_id") or ""),
        str(raw.get("mission_id") or ""),
        str(raw.get("practice_key") or ""),
        str(raw.get("instrument") or ""),
        str(raw.get("example_id") or ""),
        _live_practice_key(session),
        _song_session(session),
        str(session.get("instrument") or ""),
    )


def mission_practice_context_input_signature(session: dict[str, Any]) -> tuple[Any, ...]:
    symbol, section, idx, label = _authoritative_chord_fields(session)
    return _span_signature(session) + (
        authoritative_mission_type(session),
        symbol,
        section,
        idx,
        label,
        int(session.get("backing_track_bpm") or 0),
        int(mission_tempo_override(session) or 0),
        int(mission_passes_override(session) or 0),
        str(session.get("backing_groove_style") or session.get("improv_groove") or ""),
        str(session.get("backing_time_signature") or "4/4"),
        int(session.get("backing_track_loops") or 0),
        bool(session.get("mission_exact_backing_loop", True)),
        round(float(session.get("mission_exact_backing_volume") or 0.85), 2),
        bool(session.get("mission_exact_backing_count_in")),
        str(session.get("improv_mission_evaluation_focus") or ""),
        bool(session.get("improv_mission_match_example_mode")),
    )


# The Mission recorder's tempo. ``backing_track_bpm`` belongs to the Backing page: its canonical
# state re-applies it at the start of every run, so a Mission tempo written only there reverted
# to the Backing page's value on the next rerun (recorder 129, everything else 82).
MISSION_TEMPO_KEY = "_mission_recording_tempo"


def _tempo_song(session: dict[str, Any]) -> str:
    try:
        from music_workflow_mission_session import mission_blob_session_id

        return str(mission_blob_session_id(session) or "")
    except Exception:
        return str(session.get("active_catalog_pick_key") or session.get("song") or "")


def mission_tempo_override(session: dict[str, Any]) -> int | None:
    """The tempo the player set on the Mission recorder — for the song it was set on only."""
    raw = session.get(MISSION_TEMPO_KEY)
    if not isinstance(raw, dict) or not raw.get("bpm"):
        return None
    if str(raw.get("song") or "") != _tempo_song(session):
        return None
    return max(40, min(240, int(raw["bpm"])))


def set_mission_tempo(session: dict[str, Any], bpm: int) -> bool:
    """Make ``bpm`` the Mission tempo everywhere (context, span, backing, seal, analysis).

    A backing rendered at the old tempo is dropped (WAV, sounding claim, armed flag): it stops,
    and the next Play renders the same span at the new tempo.
    """
    bpm = max(40, min(240, int(bpm)))
    current = ensure_mission_practice_context(session)
    if current is not None and int(current.tempo_bpm) == bpm and mission_tempo_override(session) == bpm:
        return False
    session[MISSION_TEMPO_KEY] = {"bpm": bpm, "song": _tempo_song(session)}
    session.pop(MISSION_EXACT_BACKING_ARMED_KEY, None)
    try:
        from mission_exact_chord_backing import invalidate_exact_chord_backing_cache

        invalidate_exact_chord_backing_cache(session)
    except ImportError:
        pass
    mark_mission_practice_context_dirty(session)
    ensure_mission_practice_context(session)
    return True


# The Mission recorder's "Passes of the span" / "Loop bars". Same ownership rule as the tempo:
# ``backing_track_loops`` is the Backing page's widget key (dropped while that widget is not on
# screen, and the Backing page's own preference), so the Mission keeps its own, per song.
MISSION_PASSES_KEY = "_mission_recording_passes"


def mission_passes_override(session: dict[str, Any]) -> int | None:
    raw = session.get(MISSION_PASSES_KEY)
    if not isinstance(raw, dict) or not raw.get("passes"):
        return None
    if str(raw.get("song") or "") != _tempo_song(session):
        return None
    return max(1, min(16, int(raw["passes"])))


def set_mission_passes(session: dict[str, Any], passes: int) -> bool:
    """Make ``passes`` the Mission's loop count everywhere; a backing of the old length is dropped."""
    passes = max(1, min(16, int(passes)))
    current = ensure_mission_practice_context(session)
    if current is not None and int(current.loops) == passes and mission_passes_override(session) == passes:
        return False
    session[MISSION_PASSES_KEY] = {"passes": passes, "song": _tempo_song(session)}
    session.pop(MISSION_EXACT_BACKING_ARMED_KEY, None)
    try:
        from mission_exact_chord_backing import invalidate_exact_chord_backing_cache

        invalidate_exact_chord_backing_cache(session)
    except ImportError:
        pass
    mark_mission_practice_context_dirty(session)
    ensure_mission_practice_context(session)
    return True


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


MISSION_BACKING_SOUNDING_SPAN_KEY = "_mission_backing_sounding_span"


def _live_span_block(session: dict[str, Any]) -> dict[str, Any] | None:
    try:
        from mission_span_recording_context import span_scope_active

        if not span_scope_active(session):
            return None
    except ImportError:
        return None
    ctx = ensure_mission_practice_context(session)
    return ctx.span if ctx is not None else None


def ui_backing_chord_mismatch(session: dict[str, Any]) -> tuple[bool, str]:
    """True when UI-selected chord disagrees with the chord backing is bound to."""
    span = _live_span_block(session)
    if span is not None:
        return _span_backing_mismatch(session, span)
    symbol, _section, _idx, _label = _authoritative_chord_fields(session)
    if not symbol:
        return False, ""
    sounding = backing_sounding_chord(session)
    if not sounding:
        return False, ""
    ui_norm = normalize_chord_for_theory(symbol)
    back_norm = normalize_chord_for_theory(sounding)
    if ui_norm and back_norm and ui_norm != back_norm:
        return True, f"UI chord **{symbol}** does not match the generated backing **{sounding}**. Generate Backing to sync."
    return False, ""


def seal_recording_context(session: dict[str, Any], *, association: str = "") -> MissionPracticeContext:
    from datetime import datetime, timezone

    ctx = build_mission_practice_context(session)
    if association == "live_record_take":
        end_restored_take_authority(session)  # a new recording supersedes the restored take; other seals do not
    ctx.sealed_at = datetime.now(timezone.utc).isoformat()
    if association:
        ctx.recording_association = association
    seal = copy.deepcopy(ctx.to_dict())
    session[MISSION_RECORDING_SEAL_KEY] = seal
    session[MISSION_EXACT_BACKING_ARMED_KEY] = True
    session.pop(MISSION_CAPTURE_BLOCK_MESSAGE_KEY, None)
    write_mission_practice_context(session, ctx)
    return ctx


def _mission_backing_span_harmony(session: dict[str, Any], practice_key: str) -> list[list[Any]] | None:
    """Harmony of the span Mission Backing (Backing Jam) owns for this song, in concert pitch
    at the live Practice Key — ``None`` when Mission Backing does not own a span backing."""
    try:
        from backing_context import get_backing_context
        from mission_span_backing import active_span_backing, span_concert_chords
        from mission_span_recording_context import harmonic_timeline
    except ImportError:
        return None
    ctx = get_backing_context(session)
    if ctx is None or ctx.source != "mission":
        return None
    payload = active_span_backing(session)  # song-scoped: another song's span is never returned
    if payload is None:
        return None
    return harmonic_timeline(span_concert_chords(payload, practice_key))


def _span_backing_mismatch(session: dict[str, Any], span: dict[str, Any]) -> tuple[bool, str]:
    """Is the backing that is actually sounding this span? (canonical harmony, not strings)

    Owners, in order: the recorder's span backing (its claim exists only while its WAV does),
    then Mission Backing Jam's staged span for this song. Nothing sounding → no mismatch
    (backing is optional for uploads).
    """
    from mission_span_recording_context import span_chart_label, span_harmonic_timeline

    label = span_chart_label(span)
    want = span_harmonic_timeline(span)
    claim = session.get(MISSION_BACKING_SOUNDING_SPAN_KEY)
    if isinstance(claim, dict) and session.get("mission_exact_backing_wav"):
        if claim.get("harmony") != want:
            return True, f"The generated backing is not **{label}**. Generate Backing to sync."
        if int(claim.get("bpm") or 0) != int(span.get("bpm") or 0) or str(claim.get("meter") or "") != str(span.get("meter") or ""):
            return True, (
                f"The generated backing is **{label}** at {claim.get('bpm')} BPM {claim.get('meter')}, but this Mission is set "
                f"to {span.get('bpm')} BPM {span.get('meter')}. Generate Backing to sync."
            )
        return False, ""
    jam = _mission_backing_span_harmony(session, str(span.get("practice_key") or ""))
    if jam is not None and jam != want:
        return True, f"The generated backing is not **{label}**. Generate Backing to sync."
    return False, ""


def span_backing_identity(span: dict[str, Any]) -> str:
    """What a span backing WAV was rendered for (timeline, key, tempo, meter)."""
    return "|".join(
        str(span.get(k) or "") for k in ("timeline_fingerprint", "practice_key", "bpm", "meter", "span_id")
    )


def recording_context_stale_warning(session: dict[str, Any], *, for_analysis: bool = False) -> str:
    seal_raw = session.get(MISSION_RECORDING_SEAL_KEY)
    sealed = MissionPracticeContext.from_dict(seal_raw)
    if not sealed:
        return ""
    if for_analysis and session.get(MISSION_SEALED_BY_ENVELOPE_KEY):
        return ""  # a restored take is not stale because the Mission moved on after it was recorded
    live = build_mission_practice_context(session)
    if sealed.span or live.span:
        # Span takes are judged on span identity only (never the one-chord selected chord).
        if sealed.span and live.span and sealed.span.get("span_fingerprint") == live.span.get("span_fingerprint"):
            return ""
        if not sealed.span:
            return "This take was prepared for a single-chord Mission — record a new take for this span."
        from mission_span_recording_context import span_stale_reasons

        reasons = span_stale_reasons(sealed.span, live.span)
        return ("Take context changed: " + "; ".join(reasons) + ".") if reasons else ""
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
        stale = recording_context_stale_warning(session, for_analysis=True)
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
    take = None
    try:
        from mission_span_take import analysis_span_take

        take = analysis_span_take(session)
    except ImportError:
        take = None
    if take is not None:
        # A 2/3-chord take: its own sealed span is the harmonic context — never the old
        # one-chord selected chord, and never the union-of-chords "target" shortcut alone.
        span = take["span"]
        chords = [str(t.get("chord") or "") for t in span.get("timeline") or []]
        out["mission_span_take"] = take
        out["mission_type"] = str(span.get("mission_label") or "")
        out["improv_active_mission"] = out["mission_type"]
        out["mission_chord"] = ""
        out["mission_section"] = str(span.get("section") or "")
        out["mission_span_chords"] = chords
        out["target_chords"] = list(dict.fromkeys(c for c in chords if c))
        if isinstance(out.get("sections"), dict):
            out["sections"] = {str(span.get("section") or "Span"): chords}
        out["display_key"] = str(span.get("practice_key") or out.get("display_key") or "")
        out["practice_bpm"] = int(span.get("bpm") or out.get("practice_bpm") or 0) or out.get("practice_bpm")
        out["time_signature"] = str(span.get("meter") or out.get("time_signature") or "")
        out["evaluation_focus"] = str(span.get("evaluation_focus") or "")
        out["mission_evaluation_focus"] = out["evaluation_focus"]
        out["optional_mission_example_only"] = True
        return out
    mpc = sealed_take_context(session)
    if mpc is None:
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
    stale = recording_context_stale_warning(session, for_analysis=True)
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
    sealed_span_take = None
    try:
        from mission_span_take import analysis_span_take

        sealed_span_take = analysis_span_take(session)
    except ImportError:
        sealed_span_take = None
    ok, msg = mission_capture_allowed(
        session,
        require_mission_workflow=locked,
        # A 2/3-chord take is evaluated with its own sealed span (tempo, key, timeline), so a
        # later Mission change does not make it unanalyzable; the backing-sync check still runs.
        capture_path="upload" if sealed_span_take else "analysis",
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
