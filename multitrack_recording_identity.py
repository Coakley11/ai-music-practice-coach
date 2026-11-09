"""Recording-time identity of a Multitrack export, and its Upload Analysis handoff.

A saved Multitrack export is a *historical fact*: it was played in one Concert Key, by a
player at one level, for one song, on a known set of instruments. The studio's current
sidebar Practice Key, level and Active Song may all have moved on since the take was
recorded, and an export saved weeks ago must never inherit today's selections.

So the identity is frozen while the layers are being recorded, travels inside the saved
export row, and Upload Analysis is seeded from that row alone. Nothing in this module
reads live studio UI state at handoff time.

What the identity deliberately does *not* claim: a mixed WAV is not a set of stems. The
recorded instruments are named so the coach knows what is sounding in the ensemble, and
``export_stem_info`` reports plainly that no isolated stem is available, so per-instrument
grading is never fabricated from one blended file.

Pure Python: no Streamlit import, so every rule here is unit-testable.
"""

from __future__ import annotations

from typing import Any, Mapping

# Session key holding the identity frozen when the first layer was recorded.
MT_RECORDING_IDENTITY_KEY = "mt_recording_identity"

# Field name carrying that identity inside a saved multitrack export row.
EXPORT_RECORDING_IDENTITY_FIELD = "recording_identity"

# Slots that are accompaniment rather than a recorded player.
_NON_PLAYER_SLOTS = {"backing"}

IDENTITY_SOURCE_RECORDING = "recording_time"
IDENTITY_SOURCE_SAVE = "save_time"
IDENTITY_SOURCE_LEGACY = "legacy_row"


# --------------------------------------------------------------------------- helpers


def _text(value: Any) -> str:
    return str(value or "").strip()


def _dedupe(values: Any) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in values or []:
        text = _text(item)
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def _slot_has_audio(tracks: Any, slot: str) -> bool:
    if not isinstance(tracks, Mapping):
        return False
    return bool(tracks.get(slot))


def _default_instrument_for_slot(slot: str, session_state: Mapping[str, Any] | None) -> str:
    try:
        from multitrack_layer_chords import default_layer_instrument

        return _text(default_layer_instrument(slot, session_state))
    except Exception:
        return ""


# ------------------------------------------------------- recorded layer instruments


def layer_instrument_for_slot(session_state: Mapping[str, Any] | None, slot: str) -> str:
    """The instrument one layer is charted for — the musician's pick, else the slot default."""
    slot = _text(slot)
    if not slot:
        return ""
    try:
        from multitrack_layer_chords import layer_instrument

        return _text(layer_instrument(session_state, slot))
    except Exception:
        return _default_instrument_for_slot(slot, session_state)


def recorded_slot_instruments(session_state: Mapping[str, Any] | None) -> dict[str, str]:
    """``slot -> instrument`` for the slots that actually hold a recorded layer."""
    ss = session_state or {}
    tracks = ss.get("mt_tracks")
    try:
        from multitrack_slots import MULTITRACK_SLOTS

        slots = list(MULTITRACK_SLOTS)
    except Exception:
        slots = list(tracks.keys()) if isinstance(tracks, Mapping) else []

    out: dict[str, str] = {}
    for slot in slots:
        slot = _text(slot)
        if not slot or not _slot_has_audio(tracks, slot):
            continue
        inst = layer_instrument_for_slot(ss, slot)
        if inst:
            out[slot] = inst
    return out


# ------------------------------------------------------------ freezing the identity


# What resolve_active_musical_key answers for a session that holds no song at all.
_RESOLVER_FALLBACK_KEY = "C"


def _has_song_context(session_state: Mapping[str, Any]) -> bool:
    """True when some song actually owns this session, so a resolved key means something."""
    for candidate in (
        "active_catalog_pick_key",
        "pick_key",
        "active_song_title",
        "active_song_id",
        "selected_song",
        "active_song_state",
    ):
        if session_state.get(candidate):
            return True
    return False


def _resolve_recording_concert_key(session_state: Mapping[str, Any]) -> str:
    """The sounding key the layers are being played in, as the Multitrack page resolves it.

    Returns ``""`` rather than a guess when the key cannot be established: an export that
    honestly says "key unknown" is worth more to the coach than one asserting a default.
    """
    resolved = ""
    try:
        from songs.key_state import resolve_active_musical_key

        ctx = resolve_active_musical_key(
            dict(session_state),
            instrument=_text(session_state.get("instrument")) or None,
            surface="multitrack",
        )
        resolved = _text(getattr(ctx, "practice_concert_key", ""))
    except Exception:
        resolved = ""

    # The resolver answers "C" for a session with no song. That is its fallback, not a key
    # the musician chose, so it is only trusted when some song actually owns the session.
    if resolved and (
        resolved != _RESOLVER_FALLBACK_KEY or _has_song_context(session_state)
    ):
        return resolved

    for candidate in ("concert_key", "practice_key", "practice_concert_key", "display_key"):
        key = _text(session_state.get(candidate))
        if key:
            return key
    # Only the resolver's songless fallback is left — report the key as unknown.
    return ""


def _resolve_player_level(session_state: Mapping[str, Any]) -> str:
    try:
        from practice_setup_globals import get_active_level

        level = _text(get_active_level(dict(session_state)))
        if level:
            return level
    except Exception:
        pass
    return _text(session_state.get("level"))


def _resolve_recording_focus(session_state: Mapping[str, Any]) -> list[str]:
    try:
        from recording_analysis_context import coerce_focus_list

        return list(
            coerce_focus_list(
                session_state.get("focus") or session_state.get("practice_focus")
            )
        )
    except Exception:
        focus = _text(session_state.get("focus") or session_state.get("practice_focus"))
        return [focus] if focus else []


def _resolve_song_source(session_state: Mapping[str, Any]) -> dict[str, str]:
    try:
        from recording_analysis_context import resolve_active_song_source

        song = resolve_active_song_source(dict(session_state))
        if isinstance(song, Mapping):
            return {
                "song_source_type": _text(song.get("song_source_type")),
                "song_source_id": _text(song.get("song_source_id")),
                "song_source_name": _text(song.get("song_source_name")),
                "song_artist": _text(song.get("song_artist")),
            }
    except Exception:
        pass
    return {
        "song_source_type": "",
        "song_source_id": "",
        "song_source_name": _text(session_state.get("active_song_title")),
        "song_artist": "",
    }


def freeze_recording_identity(
    session_state: dict[str, Any],
    *,
    force: bool = False,
) -> dict[str, Any]:
    """Freeze key / level / song / focus once, when the first layer is recorded.

    The *first* layer owns the Concert Key: that is the key the musician was hearing and
    playing in. Later sidebar key changes must not rewrite it, so this is idempotent
    unless ``force`` is passed. Instrument identity is intentionally **not** frozen here
    — layers keep arriving, so instruments are collected again at save time.
    """
    existing = session_state.get(MT_RECORDING_IDENTITY_KEY)
    if isinstance(existing, dict) and existing and not force:
        return dict(existing)

    identity: dict[str, Any] = {
        "identity_source": IDENTITY_SOURCE_RECORDING,
        "recording_concert_key": _resolve_recording_concert_key(session_state),
        "level": _resolve_player_level(session_state),
        "recording_focuses": _resolve_recording_focus(session_state),
        "primary_instrument": _text(session_state.get("instrument")),
        "bpm": session_state.get("multitrack_bpm") or session_state.get("backing_track_bpm"),
        "time_signature": _text(session_state.get("mt_time_signature")),
    }
    identity.update(_resolve_song_source(session_state))
    session_state[MT_RECORDING_IDENTITY_KEY] = dict(identity)
    return dict(identity)


def recording_identity_for_export(session_state: Mapping[str, Any] | None) -> dict[str, Any]:
    """The identity to store on a saved export row: frozen facts + the layers recorded.

    When no identity was frozen (a session that pre-dates this contract), the current
    studio state is read once here as a best effort and stamped ``save_time`` so readers
    can tell a recording-time key from a save-time guess.
    """
    ss = dict(session_state or {})
    frozen = ss.get(MT_RECORDING_IDENTITY_KEY)
    if isinstance(frozen, dict) and frozen:
        identity = dict(frozen)
    else:
        identity = {
            "identity_source": IDENTITY_SOURCE_SAVE,
            "recording_concert_key": _resolve_recording_concert_key(ss),
            "level": _resolve_player_level(ss),
            "recording_focuses": _resolve_recording_focus(ss),
            "primary_instrument": _text(ss.get("instrument")),
            "bpm": ss.get("multitrack_bpm") or ss.get("backing_track_bpm"),
            "time_signature": _text(ss.get("mt_time_signature")),
        }
        identity.update(_resolve_song_source(ss))

    slot_instruments = recorded_slot_instruments(ss)
    identity["slot_instruments"] = dict(slot_instruments)
    identity["instruments"] = _dedupe(slot_instruments.values())
    return identity


# ------------------------------------------------------------ reading a saved export


def _row_identity(row: Mapping[str, Any] | None) -> dict[str, Any]:
    raw = (row or {}).get(EXPORT_RECORDING_IDENTITY_FIELD)
    return dict(raw) if isinstance(raw, Mapping) else {}


def recorded_instruments_from_export(row: Mapping[str, Any] | None) -> list[str]:
    """The instruments actually recorded into this export.

    Order of authority: the identity saved with the export, then the per-slot instruments
    recorded in ``included_tracks``, then the canonical default for each slot name, and
    only last the single ``instrument`` field a legacy row carries. The backing track is
    never a recorded instrument.
    """
    row = dict(row or {})
    identity = _row_identity(row)

    named = _dedupe(identity.get("instruments"))
    if named:
        return named

    slot_map = identity.get("slot_instruments")
    if isinstance(slot_map, Mapping):
        named = _dedupe(slot_map.values())
        if named:
            return named

    from_tracks: list[str] = []
    included = row.get("included_tracks")
    if isinstance(included, list):
        for track in included:
            if not isinstance(track, Mapping):
                continue
            slot = _text(track.get("slot"))
            if slot.lower() in _NON_PLAYER_SLOTS:
                continue
            inst = _text(track.get("instrument")) or _default_instrument_for_slot(slot, None)
            if inst:
                from_tracks.append(inst)
    named = _dedupe(from_tracks)
    if named:
        return named

    legacy = _text(row.get("instrument"))
    return [legacy] if legacy else []


def export_stem_info(row: Mapping[str, Any] | None) -> dict[str, Any]:
    """What the coaching engine may honestly claim about this export's audio.

    A saved export is one mixed WAV. The individual layers are not stored beside it, so
    there is no isolated stem to grade: ``has_isolated_stems`` stays False and the
    recorded instruments are reported as ensemble content, not as gradable stems.
    """
    row = dict(row or {})
    instruments = recorded_instruments_from_export(row)
    included = row.get("included_tracks")
    included_count = len(included) if isinstance(included, list) else 0
    backing_in_mix = False
    if isinstance(included, list):
        backing_in_mix = any(
            isinstance(t, Mapping) and _text(t.get("slot")).lower() in _NON_PLAYER_SLOTS
            for t in included
        )
    if not backing_in_mix:
        mix_settings = row.get("mix_settings")
        if isinstance(mix_settings, Mapping):
            backing_in_mix = bool(mix_settings.get("include_backing_in_mix"))

    return {
        "has_isolated_stems": False,
        "source_separated": False,
        "uploaded_track_count": 1,
        "mixed_instrument_count": len(instruments),
        "recorded_instruments": list(instruments),
        "backing_in_mix": bool(backing_in_mix),
        "included_track_count": included_count,
        "mix_polyphony_limited_attribution": len(instruments) > 1 or bool(backing_in_mix),
        "stem_limitation": (
            "One mixed ensemble WAV — the recorded layers are not saved as isolated "
            "stems, so per-instrument grades cannot be separated from the blend."
        ),
    }


def _instrument_focus_defaults(
    instruments: list[str],
    identity: Mapping[str, Any],
) -> dict[str, list[str]]:
    """An independent starting Practice Focus per instrument — editable afterwards.

    Each instrument gets a focus drawn from *its own* option list rather than one shared
    value copied across the ensemble, so the focuses start genuinely independent. The
    instrument the player recorded as themselves keeps the focus they were working on.
    """
    try:
        from recording_analysis_context import (
            coerce_focus_list,
            focus_options_for_instrument_safe,
        )
    except Exception:
        return {inst: [] for inst in instruments}

    primary = _text(identity.get("primary_instrument"))
    recorded_focuses = list(coerce_focus_list(identity.get("recording_focuses")))

    out: dict[str, list[str]] = {}
    for inst in instruments:
        options = list(focus_options_for_instrument_safe(inst) or [])
        if inst == primary and recorded_focuses:
            kept = [f for f in recorded_focuses if not options or f in options]
            out[inst] = kept or ([options[0]] if options else [])
            continue
        out[inst] = [options[0]] if options else []
    return out


def upload_analysis_identity(row: Mapping[str, Any] | None) -> dict[str, Any]:
    """Everything Upload Analysis should show for this saved export, from the row alone.

    The returned ``song_source_*`` values are the export's own song, never the Active Song,
    and ``recording_concert_key`` is the key the take was played in, never the current
    sidebar Practice Key or the song's Original Key.
    """
    row = dict(row or {})
    identity = _row_identity(row)
    legacy = not identity

    try:
        from recording_analysis_context import (
            RECORDING_TYPE_MT_MIX,
            SONG_SOURCE_CATALOG,
            concert_key_choice_from_token,
        )
        from upload_analysis_modes import MULTITRACK_RECORDING
    except Exception:  # pragma: no cover - import-time safety only
        RECORDING_TYPE_MT_MIX = "Multitrack mix"
        SONG_SOURCE_CATALOG = "Catalog Song"
        MULTITRACK_RECORDING = "Multitrack recording"

        def concert_key_choice_from_token(token: Any) -> str:
            return _text(token)

    instruments = recorded_instruments_from_export(row)

    song_name = _text(identity.get("song_source_name")) or _text(
        row.get("song") or row.get("song_title")
    )
    song_type = _text(identity.get("song_source_type"))
    song_id = _text(identity.get("song_source_id")) or _text(row.get("active_song_id"))
    song_type_known = bool(song_type)
    if not song_type:
        # A legacy row never recorded which library owned the song. Default the *type*
        # to the neutral Catalog choice, but keep the export's own title authoritative
        # and lock identity, so the current Active Song cannot replace it.
        song_type = SONG_SOURCE_CATALOG

    key_token = _text(identity.get("recording_concert_key"))
    try:
        key_label = _text(concert_key_choice_from_token(key_token)) if key_token else ""
    except Exception:
        key_label = key_token

    return {
        "workflow": MULTITRACK_RECORDING,
        "recording_type": RECORDING_TYPE_MT_MIX,
        "export_id": _text(row.get("export_id")),
        "export_name": _text(row.get("export_name")),
        "multitrack_id": _text(row.get("multitrack_id")),
        "workspace_id": _text(row.get("workspace_id")) or "daniel",
        "song_source_type": song_type,
        "song_source_type_known": song_type_known,
        "song_source_id": song_id,
        "song_source_name": song_name,
        "song_artist": _text(identity.get("song_artist")),
        "recording_concert_key": key_token,
        "recording_concert_key_label": key_label,
        "recording_key_known": bool(key_token),
        "identity_source": _text(identity.get("identity_source"))
        or (IDENTITY_SOURCE_LEGACY if legacy else IDENTITY_SOURCE_SAVE),
        "level": _text(identity.get("level")),
        "instruments": instruments,
        "target_layer": instruments[0] if instruments else "",
        "instrument_focuses": _instrument_focus_defaults(instruments, identity),
        "bpm": identity.get("bpm") if identity.get("bpm") else row.get("bpm"),
        "time_signature": _text(identity.get("time_signature")),
        "duration_seconds": row.get("duration_seconds"),
        "legacy_metadata": legacy,
        "stems": export_stem_info(row),
    }


# --------------------------------------------------------- applying it to the session


def identity_gaps(identity: Mapping[str, Any] | None) -> list[str]:
    """Human-readable list of what an incomplete (legacy) export could not tell us."""
    identity = dict(identity or {})
    gaps: list[str] = []
    if not identity.get("recording_key_known"):
        gaps.append("the Concert Key it was recorded in")
    if not identity.get("level"):
        gaps.append("the player level at the time")
    if not identity.get("song_source_type_known"):
        gaps.append("which song library it came from")
    if not identity.get("instruments"):
        gaps.append("which instruments were recorded")
    return gaps


def apply_identity_to_upload_analysis(
    session_state: dict[str, Any],
    identity: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Seed Upload Analysis from one export's identity. Safe only before widgets exist.

    Writes the Multitrack workflow, the export's own song, the recorded Concert Key, the
    recording-time level, the recorded instruments and a per-instrument Practice Focus,
    and clears Creative Mission context — a multitrack mix is not a Mission take.
    """
    identity = dict(identity or {})
    if not identity:
        return {}

    try:
        from recording_analysis_context import (
            ANALYSIS_EVAL_INSTRUMENT_KEY,
            ANALYSIS_EVAL_INSTRUMENTS_KEY,
            ANALYSIS_IDENTITY_LOCKED_KEY,
            ANALYSIS_INSTRUMENT_FOCUSES_KEY,
            ANALYSIS_MISSION_CONSTRAINT_KEY,
            ANALYSIS_PLAYER_LEVEL_KEY,
            ANALYSIS_PRACTICE_FOCUS_KEY,
            ANALYSIS_PRACTICE_FOCUSES_KEY,
            ANALYSIS_RECORDING_CONCERT_KEY_KEY,
            ANALYSIS_SONG_SOURCE_ID_KEY,
            ANALYSIS_SONG_SOURCE_NAME_KEY,
            ANALYSIS_SONG_SOURCE_TYPE_KEY,
            ANALYSIS_TARGET_LAYER_KEY,
            coerce_concert_key_choice,
            instrument_focus_widget_key,
        )
    except Exception:  # pragma: no cover - import-time safety only
        return {}

    session_state["analysis_mode"] = identity["workflow"]
    session_state["analysis_recording_type"] = identity["recording_type"]

    # The export owns its song identity; lock it so active-song seeding cannot replace it.
    session_state[ANALYSIS_SONG_SOURCE_TYPE_KEY] = identity.get("song_source_type") or ""
    session_state[ANALYSIS_SONG_SOURCE_NAME_KEY] = identity.get("song_source_name") or ""
    session_state[ANALYSIS_SONG_SOURCE_ID_KEY] = identity.get("song_source_id") or ""
    session_state[ANALYSIS_IDENTITY_LOCKED_KEY] = True

    # Recorded Concert Key — not the song's Original Key, not today's sidebar key.
    key_token = _text(identity.get("recording_concert_key"))
    if key_token:
        try:
            session_state[ANALYSIS_RECORDING_CONCERT_KEY_KEY] = coerce_concert_key_choice(
                _text(identity.get("recording_concert_key_label")) or key_token
            )
        except Exception:
            session_state[ANALYSIS_RECORDING_CONCERT_KEY_KEY] = key_token

    level = _text(identity.get("level"))
    if level:
        session_state[ANALYSIS_PLAYER_LEVEL_KEY] = level

    instruments = _dedupe(identity.get("instruments"))
    if instruments:
        session_state[ANALYSIS_EVAL_INSTRUMENTS_KEY] = list(instruments)
        session_state[ANALYSIS_EVAL_INSTRUMENT_KEY] = instruments[0]
        session_state[ANALYSIS_TARGET_LAYER_KEY] = (
            _text(identity.get("target_layer")) or instruments[0]
        )

    focuses = identity.get("instrument_focuses")
    if isinstance(focuses, Mapping) and focuses:
        focus_map = {
            _text(inst): list(vals or [])
            for inst, vals in focuses.items()
            if _text(inst)
        }
        session_state[ANALYSIS_INSTRUMENT_FOCUSES_KEY] = focus_map
        # Each instrument's own control starts from its own value and stays editable.
        for inst, vals in focus_map.items():
            session_state[instrument_focus_widget_key(inst)] = list(vals)
        first = focus_map.get(instruments[0]) if instruments else []
        session_state[ANALYSIS_PRACTICE_FOCUSES_KEY] = list(first or [])
        session_state[ANALYSIS_PRACTICE_FOCUS_KEY] = (first or [""])[0]

    # A Multitrack mix is never a Creative Mission take.
    session_state[ANALYSIS_MISSION_CONSTRAINT_KEY] = ""
    session_state["analysis_sync_creative_mission"] = False

    stems = identity.get("stems")
    if isinstance(stems, Mapping):
        session_state["analysis_multitrack_stems"] = dict(stems)

    return dict(identity)


__all__ = [
    "EXPORT_RECORDING_IDENTITY_FIELD",
    "IDENTITY_SOURCE_LEGACY",
    "IDENTITY_SOURCE_RECORDING",
    "IDENTITY_SOURCE_SAVE",
    "MT_RECORDING_IDENTITY_KEY",
    "apply_identity_to_upload_analysis",
    "export_stem_info",
    "freeze_recording_identity",
    "identity_gaps",
    "layer_instrument_for_slot",
    "recorded_instruments_from_export",
    "recorded_slot_instruments",
    "recording_identity_for_export",
    "upload_analysis_identity",
]
