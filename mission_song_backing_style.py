"""Resolve Mission Jam backing style from authoritative song metadata (not session defaults)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

StyleSource = Literal["song_metadata", "explicit_user_override", "fallback"]

MISSION_JAM_STYLE_OVERRIDE_KEY = "mission_jam_style_user_override"
MISSION_JAM_STYLE_RESOLUTION_KEY = "_mission_jam_style_resolution"
MISSION_JAM_STYLE_PICK_KEY = "_mission_jam_style_bound_pick_key"

NEUTRAL_FALLBACK_STYLE = "Song Default"
NEUTRAL_FALLBACK_GROOVE = "Auto"

_JAZZ_SWING = "jazz swing"


@dataclass(frozen=True)
class MissionJamStyleResolution:
    style: str
    groove: str
    bpm: int | None
    meter: str
    source: StyleSource
    pick_key: str
    song_title: str
    prior_session_groove: str
    prior_session_style: str
    stale_replaced: bool
    fallback_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _infer_groove_fn(song_data: dict[str, Any], fallback: str) -> str:
    genre = str(song_data.get("genre") or "").strip()
    if genre == "Jazz":
        return "Jazz swing"
    if genre == "Jewish":
        return "Jewish groove"
    return fallback


def _song_row_for_mission(session: dict[str, Any]) -> tuple[dict[str, Any], str, str]:
    """Return (song_data, song_source_type, pick_key)."""
    pick_key = str(
        session.get("active_catalog_pick_key") or session.get("_active_pick_key") or ""
    ).strip()
    try:
        from songs.music_source import (
            cpl_session_is_active,
            custom_song_context_from_session,
            is_custom_progression,
            resolve_catalog_song_for_pick,
        )

        if is_custom_progression(session) or cpl_session_is_active(session):
            _, title, song_data = custom_song_context_from_session(session)
            return song_data if isinstance(song_data, dict) else {}, "custom", pick_key or title
        selected, _original_key = resolve_catalog_song_for_pick(session, pick_key)
        song_data = selected if isinstance(selected, dict) else {}
        if song_data.get("extensions") or song_data.get("sections"):
            return song_data, "catalog", pick_key
        lib = song_data.get("library_record") if isinstance(song_data.get("library_record"), dict) else {}
        if lib:
            return lib, "catalog", pick_key
        return song_data, "catalog", pick_key
    except ImportError:
        return {}, "catalog", pick_key


def _canonical_from_song_data(song_data: dict[str, Any]) -> tuple[str, str, int | None, str]:
    ext = song_data.get("extensions") if isinstance(song_data.get("extensions"), dict) else {}
    try:
        from songs.playback_defaults import (
            canonical_active_song_bpm,
            default_groove_for_song,
            normalize_groove_label,
        )

        groove = default_groove_for_song(song_data, infer_fn=_infer_groove_fn)
        groove = normalize_groove_label(groove, song_data=song_data, infer_fn=_infer_groove_fn)
        bpm = canonical_active_song_bpm(song_data)
    except ImportError:
        groove = str(ext.get("default_groove") or NEUTRAL_FALLBACK_GROOVE).strip()
        bpm = int(ext.get("default_bpm") or 100) if ext.get("default_bpm") else None
    meter = str(ext.get("time_signature") or song_data.get("meter") or "4/4").strip() or "4/4"
    style = str(ext.get("default_style") or groove or NEUTRAL_FALLBACK_STYLE).strip()
    if not groove or groove.lower() == "auto":
        if ext.get("default_groove"):
            groove = str(ext["default_groove"]).strip()
    has_meta = bool(ext.get("default_groove") or ext.get("default_bpm") or song_data.get("genre"))
    if not has_meta and not song_data.get("sections"):
        return NEUTRAL_FALLBACK_STYLE, NEUTRAL_FALLBACK_GROOVE, bpm, meter
    return style, groove, bpm, meter


def _read_user_override(session: dict[str, Any], pick_key: str) -> dict[str, Any] | None:
    raw = session.get(MISSION_JAM_STYLE_OVERRIDE_KEY)
    if not isinstance(raw, dict) or not raw.get("active"):
        return None
    if str(raw.get("pick_key") or "").strip() != pick_key:
        return None
    return raw


def resolve_mission_jam_backing_style(session: dict[str, Any]) -> MissionJamStyleResolution:
    song_data, _source_type, pick_key = _song_row_for_mission(session)
    title = str(song_data.get("title") or session.get("song") or "").strip()
    prior_groove = str(
        session.get("improv_groove") or session.get("backing_groove_style") or ""
    ).strip()
    prior_style = str(session.get("improv_style") or session.get("improv_jam_style") or "").strip()

    override = _read_user_override(session, pick_key)
    if override:
        return MissionJamStyleResolution(
            style=str(override.get("style") or override.get("groove") or prior_style),
            groove=str(override.get("groove") or override.get("style") or prior_groove),
            bpm=int(override["bpm"]) if override.get("bpm") is not None else None,
            meter=str(override.get("meter") or "4/4"),
            source="explicit_user_override",
            pick_key=pick_key,
            song_title=title,
            prior_session_groove=prior_groove,
            prior_session_style=prior_style,
            stale_replaced=False,
        )

    style, groove, bpm, meter = _canonical_from_song_data(song_data)
    source: StyleSource = "song_metadata"
    fallback_reason = ""
    if style == NEUTRAL_FALLBACK_STYLE and groove == NEUTRAL_FALLBACK_GROOVE:
        source = "fallback"
        fallback_reason = "missing_song_style_metadata"

    stale = False
    if prior_style.lower() == _JAZZ_SWING and groove.lower() != _JAZZ_SWING:
        stale = True
    if prior_groove.lower() == _JAZZ_SWING and groove.lower() != _JAZZ_SWING:
        stale = True
    if pick_key and session.get(MISSION_JAM_STYLE_PICK_KEY) not in (None, pick_key):
        stale = True

    return MissionJamStyleResolution(
        style=style,
        groove=groove,
        bpm=bpm,
        meter=meter,
        source=source,
        pick_key=pick_key,
        song_title=title,
        prior_session_groove=prior_groove,
        prior_session_style=prior_style,
        stale_replaced=stale,
        fallback_reason=fallback_reason,
    )


def set_mission_jam_style_user_override(
    session: dict[str, Any],
    *,
    style: str,
    groove: str,
    bpm: int | None = None,
    meter: str = "4/4",
    pick_key: str | None = None,
) -> None:
    pk = pick_key or str(
        session.get("active_catalog_pick_key") or session.get("_active_pick_key") or ""
    ).strip()
    session[MISSION_JAM_STYLE_OVERRIDE_KEY] = {
        "active": True,
        "pick_key": pk,
        "style": str(style or "").strip(),
        "groove": str(groove or style or "").strip(),
        "bpm": bpm,
        "meter": str(meter or "4/4"),
    }


def clear_mission_jam_style_user_override(session: dict[str, Any]) -> None:
    session.pop(MISSION_JAM_STYLE_OVERRIDE_KEY, None)


def use_song_style_for_mission_jam(session: dict[str, Any]) -> MissionJamStyleResolution:
    clear_mission_jam_style_user_override(session)
    return sync_mission_style_from_song(session, force=True)


def sync_mission_style_from_song(session: dict[str, Any], *, force: bool = False) -> MissionJamStyleResolution:
    resolved = resolve_mission_jam_backing_style(session)
    session[MISSION_JAM_STYLE_RESOLUTION_KEY] = resolved.to_dict()
    if resolved.source == "explicit_user_override" and not force:
        return resolved

    # Ephemeral Backing play-session / user dirty knobs own Current Style/Meter.
    # Do not reseal song metadata over a live Advanced Settings change.
    if not force:
        try:
            from backing_play_session import (
                backing_play_session_has_override,
                play_session_blocks_canonical_seed,
            )
            from backing_track_state import is_backing_user_dirty

            if (
                play_session_blocks_canonical_seed(session)
                or is_backing_user_dirty(session)
                or backing_play_session_has_override(session, "groove")
                or backing_play_session_has_override(session, "meter")
            ):
                return resolved
        except ImportError:
            pass

    session[MISSION_JAM_STYLE_PICK_KEY] = resolved.pick_key
    if resolved.groove:
        session["improv_groove"] = resolved.groove
        session["backing_groove_style"] = resolved.groove
    if resolved.style:
        session["improv_style"] = resolved.style
        session["improv_jam_style"] = resolved.style
    if resolved.bpm is not None:
        session["improv_style_bpm"] = int(resolved.bpm)
    if resolved.meter:
        session["improv_style_meter"] = resolved.meter
        session["backing_time_signature"] = resolved.meter

    meta = session.get("improv_style_meta")
    if not isinstance(meta, dict):
        meta = {}
    meta = dict(meta)
    if resolved.bpm is not None:
        meta["bpm"] = int(resolved.bpm)
    if resolved.groove:
        meta["groove"] = resolved.groove
    if resolved.style:
        meta["style"] = resolved.style
    if resolved.meter:
        meta["meter"] = resolved.meter
    session["improv_style_meta"] = meta
    return resolved


def on_mission_song_pick_changed(session: dict[str, Any]) -> None:
    """Drop stale overrides when the active song changes."""
    pk = str(session.get("active_catalog_pick_key") or session.get("_active_pick_key") or "").strip()
    bound = str(session.get(MISSION_JAM_STYLE_PICK_KEY) or "").strip()
    if bound and pk and bound != pk:
        clear_mission_jam_style_user_override(session)
    sync_mission_style_from_song(session)


__all__ = [
    "MISSION_JAM_STYLE_OVERRIDE_KEY",
    "MISSION_JAM_STYLE_RESOLUTION_KEY",
    "NEUTRAL_FALLBACK_GROOVE",
    "NEUTRAL_FALLBACK_STYLE",
    "MissionJamStyleResolution",
    "clear_mission_jam_style_user_override",
    "on_mission_song_pick_changed",
    "resolve_mission_jam_backing_style",
    "set_mission_jam_style_user_override",
    "sync_mission_style_from_song",
    "use_song_style_for_mission_jam",
]
