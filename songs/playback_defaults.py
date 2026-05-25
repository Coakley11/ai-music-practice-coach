"""Sync backing-track BPM and groove with the active song (catalog or CPL)."""

from __future__ import annotations

from typing import Any, Callable

from .bpm_state import (
    BPM_WIDGET_KEY,
    LAST_BPM_SONG,
    PENDING_BACKING_TRACK_BPM,
)

BACKING_GROOVE_KEY = "backing_groove_style"
LAST_PLAYBACK_GROOVE_SONG = "_last_playback_groove_song"
PENDING_BACKING_GROOVE = "_pending_backing_groove"
PRACTICE_GROOVE_KEY = "practice_groove_style"
LAST_BACKING_DEFAULTS_SONG_ID = "last_backing_defaults_song_id"
LAST_BPM_DEFAULTS_SONG_ID = LAST_BACKING_DEFAULTS_SONG_ID
ACTIVE_SONG_BPM_KEY = "active_song_bpm"
ACTIVE_PLAYBACK_SONG_ID_KEY = "active_playback_song_id"
_STUDIO_PAGE_SNAPSHOTS_KEY = "_studio_page_snapshots"

GROOVE_STYLE_CHOICES: tuple[str, ...] = (
    "Auto",
    "Pop groove",
    "Rock groove",
    "Jazz swing",
    "Bossa nova",
    "Funk groove",
    "Ballad",
)


def _heuristic_bpm_for_song_data(song_data: dict[str, Any] | None) -> int:
    """Fallback BPM when card metadata is unavailable."""
    song_data = song_data or {}
    ext = song_data.get("extensions") or {}
    if ext.get("default_bpm"):
        try:
            return int(ext["default_bpm"])
        except (TypeError, ValueError):
            pass
    title = (song_data.get("title") or "").lower()
    genre = str(song_data.get("genre") or "").lower()
    if "blue bossa" in title:
        return 100
    if "bossa" in title or "samba" in title:
        return 120
    if "how deep" in title:
        return 105
    if "shape of you" in title:
        return 96
    if "perfect" in title and "sheeran" in (song_data.get("artist") or "").lower():
        return 95
    if genre == "jazz":
        return 110
    return 100


def canonical_active_song_bpm(song_data: dict[str, Any] | None) -> int:
    """BPM shown on Active Song cards — extensions + catalog metadata."""
    song_data = song_data or {}
    try:
        from practice_studio import active_song_card_details

        details = active_song_card_details(song_data)
        bpm = details.get("bpm")
        if bpm is not None:
            return int(bpm)
    except Exception:
        pass
    return _heuristic_bpm_for_song_data(song_data)


def default_bpm_for_song_data(song_data: dict[str, Any] | None) -> int:
    """BPM from song metadata — matches Active Song card."""
    return canonical_active_song_bpm(song_data)


def active_song_sync_id(
    *,
    pick_key: str = "",
    playback_song_id: str,
    is_custom: bool = False,
) -> str:
    """Stable id for BPM default tracking — prefer catalog pick_key when available."""
    if pick_key and not is_custom:
        return f"pk::{pick_key}"
    return playback_song_id


def backing_bpm_slider_widget_key(sync_id: str) -> str:
    """Per-song slider key so Streamlit recreates the widget when the active song changes."""
    safe = str(sync_id).replace(":", "_").replace("/", "_").replace(" ", "_")
    return f"backing_track_bpm::{safe}"


def invalidate_backing_page_snapshots(st: Any) -> None:
    """Drop stored Backing Track page state so navigation cannot restore stale tempo."""
    store = st.session_state.get(_STUDIO_PAGE_SNAPSHOTS_KEY)
    if isinstance(store, dict):
        store.pop("backing", None)


def reset_playback_song_tracking(st: Any) -> None:
    """Force BPM/groove widgets to pick up the next active song's defaults."""
    from .meter_state import reset_backing_meter_tracking

    st.session_state.pop(LAST_BPM_SONG, None)
    st.session_state.pop(LAST_PLAYBACK_GROOVE_SONG, None)
    st.session_state.pop(LAST_BACKING_DEFAULTS_SONG_ID, None)
    st.session_state.pop("last_backing_bpm_song_id", None)
    st.session_state.pop(PENDING_BACKING_TRACK_BPM, None)
    st.session_state.pop(PENDING_BACKING_GROOVE, None)
    invalidate_backing_page_snapshots(st)
    reset_backing_meter_tracking(st)


def _set_bpm_tracking_ids(st: Any, sync_id: str, active_bpm: int) -> None:
    st.session_state[LAST_BACKING_DEFAULTS_SONG_ID] = sync_id
    st.session_state["last_backing_bpm_song_id"] = sync_id
    st.session_state[LAST_BPM_SONG] = sync_id
    st.session_state[ACTIVE_PLAYBACK_SONG_ID_KEY] = sync_id
    st.session_state[ACTIVE_SONG_BPM_KEY] = int(active_bpm)
    st.session_state[BPM_WIDGET_KEY] = int(active_bpm)
    st.session_state["bpm"] = int(active_bpm)
    st.session_state[backing_bpm_slider_widget_key(sync_id)] = int(active_bpm)


def prime_active_song_bpm(
    st: Any,
    *,
    sync_id: str,
    active_song_bpm: int,
) -> None:
    """Apply song BPM immediately on selection (before any BPM widgets render)."""
    from .key_state import invalidate_backing_cache

    invalidate_backing_cache(st)
    invalidate_backing_page_snapshots(st)
    _set_bpm_tracking_ids(st, sync_id, active_song_bpm)


_CANONICAL_BACKING_ID_KEY = "_canonical_active_backing_song_id"


def canonicalize_backing_defaults_for_song(
    st: Any,
    *,
    sync_id: str,
    active_song_bpm: int,
    active_song_groove: str,
    active_song_meter: str,
) -> dict[str, Any]:
    """Force-sync all backing widgets to the active song's defaults on song change.

    Runs **before** any backing widget renders. Single source of truth for the
    Backing Track page so the active-song-card BPM/style/meter always matches
    what the playback engine and chord-follow code consume.

    On song change (sync_id differs from the canonical tracker), this function:
      - Resets ``backing_track_bpm``, ``backing_groove_style``,
        ``backing_time_signature`` to song defaults.
      - Clears the meter override flag.
      - Resets the per-song BPM slider widget key.
      - Invalidates any cached backing audio + chord-follow timeline.
      - Drops page snapshots so back/forward navigation cannot restore stale values.

    Returns a dict with the canonical values and a ``did_reset`` flag.
    """
    from .key_state import BACKING_NEEDS_REGEN, invalidate_backing_cache
    from .meter import normalize_time_signature
    from .meter_state import (
        BACKING_METER_KEY,
        BACKING_METER_OVERRIDE_KEY,
        LAST_BACKING_METER_SONG,
    )

    norm_bpm = int(active_song_bpm)
    norm_groove = normalize_groove_label(active_song_groove)
    norm_meter = normalize_time_signature(active_song_meter)

    previous_id = st.session_state.get(_CANONICAL_BACKING_ID_KEY)
    did_reset = previous_id != sync_id

    if did_reset:
        invalidate_backing_cache(st)
        invalidate_backing_page_snapshots(st)
        _set_bpm_tracking_ids(st, sync_id, norm_bpm)
        st.session_state[LAST_PLAYBACK_GROOVE_SONG] = sync_id
        st.session_state[BACKING_GROOVE_KEY] = norm_groove
        st.session_state[BACKING_METER_KEY] = norm_meter
        st.session_state[BACKING_METER_OVERRIDE_KEY] = False
        st.session_state[LAST_BACKING_METER_SONG] = sync_id
        # Wipe any pending tweaks left over from the previous song so they
        # cannot re-apply on the next rerun.
        st.session_state.pop(PENDING_BACKING_TRACK_BPM, None)
        st.session_state.pop(PENDING_BACKING_GROOVE, None)
        st.session_state[BACKING_NEEDS_REGEN] = False
        st.session_state[_CANONICAL_BACKING_ID_KEY] = sync_id

    return {
        "sync_id": sync_id,
        "active_song_bpm": norm_bpm,
        "active_song_groove": norm_groove,
        "active_song_meter": norm_meter,
        "applied_bpm": int(st.session_state.get(BPM_WIDGET_KEY, norm_bpm)),
        "applied_groove": str(st.session_state.get(BACKING_GROOVE_KEY, norm_groove)),
        "applied_meter": str(st.session_state.get(BACKING_METER_KEY, norm_meter)),
        "did_reset": did_reset,
    }


def default_groove_for_song(
    song_data: dict[str, Any] | None,
    *,
    infer_fn: Callable[..., str],
) -> str:
    """Resolve groove label from song metadata (extensions + genre)."""
    song_data = song_data or {}
    ext = song_data.get("extensions") or {}
    if ext.get("default_groove"):
        return normalize_groove_label(str(ext["default_groove"]), song_data=song_data, infer_fn=infer_fn)
    genre = str(song_data.get("genre") or "")
    if genre == "Pop":
        return "Pop groove"
    if genre == "Rock":
        return "Rock groove"
    if genre == "Jazz":
        return "Jazz swing"
    if genre in ("Funk", "Soul"):
        return "Funk groove"
    inferred = infer_fn(song_data, "Auto")
    return normalize_groove_label(inferred, song_data=song_data, infer_fn=infer_fn)


def normalize_groove_label(
    groove: str,
    *,
    song_data: dict[str, Any] | None = None,
    infer_fn: Callable[..., str] | None = None,
) -> str:
    """Map metadata / inferred labels to ``GROOVE_STYLE_CHOICES`` values."""
    raw = str(groove or "").strip()
    if raw in GROOVE_STYLE_CHOICES:
        return raw
    low = raw.lower().replace("nova", "nova").replace("groove", "groove")
    if "bossa" in low or "samba" in low:
        return "Bossa nova"
    if "jazz" in low or "swing" in low:
        return "Jazz swing"
    if "rock" in low:
        return "Rock groove"
    if "funk" in low:
        return "Funk groove"
    if "soul" in low or "r&b" in low or "rnb" in low:
        return "Funk groove"
    if "ballad" in low:
        return "Ballad"
    if "pop" in low:
        return "Pop groove"
    if raw.lower() == "auto" and infer_fn and song_data is not None:
        return normalize_groove_label(infer_fn(song_data, "Auto"), song_data=song_data, infer_fn=infer_fn)
    for choice in GROOVE_STYLE_CHOICES:
        if choice.lower() == low:
            return choice
    return "Pop groove"


def apply_backing_defaults_for_song(
    st: Any,
    *,
    song_id: str,
    default_bpm: int,
    default_groove: str,
    song_data: dict[str, Any] | None = None,
    infer_fn: Callable[..., str] | None = None,
) -> tuple[int, str]:
    """
    When the active song changes, force backing BPM + groove to song defaults.
    Preserves manual tweaks when the song id is unchanged.
    """
    active_bpm = int(default_bpm)
    norm_groove = normalize_groove_label(
        default_groove,
        song_data=song_data,
        infer_fn=infer_fn,
    )
    pending_bpm = st.session_state.pop(PENDING_BACKING_TRACK_BPM, None)
    pending_groove = st.session_state.pop(PENDING_BACKING_GROOVE, None)
    song_changed = st.session_state.get(LAST_BACKING_DEFAULTS_SONG_ID) != song_id

    if song_changed:
        from .key_state import invalidate_backing_cache

        invalidate_backing_cache(st)
        invalidate_backing_page_snapshots(st)
        _set_bpm_tracking_ids(st, song_id, active_bpm)
        st.session_state[LAST_PLAYBACK_GROOVE_SONG] = song_id
        st.session_state[BACKING_GROOVE_KEY] = norm_groove
    elif pending_bpm is not None:
        st.session_state[BPM_WIDGET_KEY] = int(pending_bpm)
        st.session_state[backing_bpm_slider_widget_key(song_id)] = int(pending_bpm)
    elif BPM_WIDGET_KEY not in st.session_state:
        _set_bpm_tracking_ids(st, song_id, active_bpm)

    if not song_changed:
        if pending_groove is not None:
            st.session_state[BACKING_GROOVE_KEY] = normalize_groove_label(
                str(pending_groove),
                song_data=song_data,
                infer_fn=infer_fn,
            )
        elif BACKING_GROOVE_KEY not in st.session_state:
            st.session_state[BACKING_GROOVE_KEY] = norm_groove
        elif (
            str(st.session_state.get(BACKING_GROOVE_KEY, "")) == "Auto"
            and norm_groove != "Auto"
        ):
            st.session_state[BACKING_GROOVE_KEY] = norm_groove

    bpm = int(st.session_state.get(BPM_WIDGET_KEY, active_bpm))
    groove = str(st.session_state.get(BACKING_GROOVE_KEY, norm_groove))
    if groove == "Auto" and norm_groove != "Auto":
        st.session_state[BACKING_GROOVE_KEY] = norm_groove
        groove = norm_groove
    return bpm, groove


def sync_backing_groove_before_widget(
    st: Any,
    song_id: str,
    default_groove: str,
) -> str:
    """Apply pending groove or song-change defaults before the groove widget exists."""
    pending = st.session_state.pop(PENDING_BACKING_GROOVE, None)
    song_changed = st.session_state.get(LAST_PLAYBACK_GROOVE_SONG) != song_id

    if song_changed:
        st.session_state[LAST_PLAYBACK_GROOVE_SONG] = song_id
        st.session_state[BACKING_GROOVE_KEY] = str(default_groove)
    elif pending is not None:
        st.session_state[BACKING_GROOVE_KEY] = pending
    elif BACKING_GROOVE_KEY not in st.session_state:
        st.session_state[BACKING_GROOVE_KEY] = default_groove

    return str(st.session_state[BACKING_GROOVE_KEY])


def request_backing_groove(st: Any, groove: str) -> None:
    st.session_state[PENDING_BACKING_GROOVE] = str(groove)


def playback_song_id(
    *,
    is_custom: bool,
    song_title: str,
    song_artist: str,
    custom_name: str = "",
    custom_revision: str = "",
) -> str:
    if is_custom:
        rev = custom_revision or custom_name or "custom"
        return f"cpl::{rev}"
    return f"cat::{song_title}::{song_artist}"


def sync_playback_defaults_for_active_song(
    st: Any,
    *,
    song_id: str,
    default_bpm: int,
    default_groove: str,
    song_data: dict[str, Any] | None = None,
    infer_fn: Callable[..., str] | None = None,
    pick_key: str = "",
    is_custom: bool = False,
) -> tuple[int, str]:
    """Sync BPM + groove when the active song changes; preserve manual tweaks otherwise."""
    active_bpm = canonical_active_song_bpm(song_data) if song_data else int(default_bpm)
    sync_id = active_song_sync_id(
        pick_key=pick_key,
        playback_song_id=song_id,
        is_custom=is_custom,
    )
    bpm, groove = apply_backing_defaults_for_song(
        st,
        song_id=sync_id,
        default_bpm=active_bpm,
        default_groove=default_groove,
        song_data=song_data,
        infer_fn=infer_fn,
    )
    if st.session_state.get(LAST_BACKING_DEFAULTS_SONG_ID) == sync_id:
        if PRACTICE_GROOVE_KEY not in st.session_state:
            st.session_state[PRACTICE_GROOVE_KEY] = groove
    return bpm, groove


# Backward-compatible aliases (older import names / docs).
apply_backing_bpm_defaults = apply_backing_defaults_for_song
apply_song_bpm_defaults = sync_playback_defaults_for_active_song
sync_backing_bpm_from_song = sync_playback_defaults_for_active_song
get_song_default_bpm = canonical_active_song_bpm
get_song_default_groove = default_groove_for_song
normalize_groove_style = normalize_groove_label

__all__ = [
    "ACTIVE_PLAYBACK_SONG_ID_KEY",
    "ACTIVE_SONG_BPM_KEY",
    "BACKING_GROOVE_KEY",
    "BPM_WIDGET_KEY",
    "GROOVE_STYLE_CHOICES",
    "LAST_BACKING_DEFAULTS_SONG_ID",
    "LAST_BPM_DEFAULTS_SONG_ID",
    "LAST_BPM_SONG",
    "LAST_PLAYBACK_GROOVE_SONG",
    "PENDING_BACKING_GROOVE",
    "PENDING_BACKING_TRACK_BPM",
    "PRACTICE_GROOVE_KEY",
    "active_song_sync_id",
    "apply_backing_bpm_defaults",
    "apply_backing_defaults_for_song",
    "apply_song_bpm_defaults",
    "backing_bpm_slider_widget_key",
    "canonical_active_song_bpm",
    "canonicalize_backing_defaults_for_song",
    "default_bpm_for_song_data",
    "default_groove_for_song",
    "get_song_default_bpm",
    "get_song_default_groove",
    "invalidate_backing_page_snapshots",
    "normalize_groove_label",
    "normalize_groove_style",
    "playback_song_id",
    "prime_active_song_bpm",
    "request_backing_groove",
    "reset_playback_song_tracking",
    "sync_backing_bpm_from_song",
    "sync_backing_groove_before_widget",
    "sync_playback_defaults_for_active_song",
]
