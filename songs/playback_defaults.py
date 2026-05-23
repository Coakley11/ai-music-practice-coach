"""Sync backing-track BPM and groove with the active song (catalog or CPL)."""

from __future__ import annotations

from typing import Any, Callable

from .bpm_state import (
    BPM_WIDGET_KEY,
    LAST_BPM_SONG,
    PENDING_BACKING_TRACK_BPM,
    sync_backing_bpm_before_widget,
)

BACKING_GROOVE_KEY = "backing_groove_style"
LAST_PLAYBACK_GROOVE_SONG = "_last_playback_groove_song"
PENDING_BACKING_GROOVE = "_pending_backing_groove"
PRACTICE_GROOVE_KEY = "practice_groove_style"
LAST_BACKING_DEFAULTS_SONG_ID = "last_backing_defaults_song_id"

GROOVE_STYLE_CHOICES: tuple[str, ...] = (
    "Auto",
    "Pop groove",
    "Rock groove",
    "Jazz swing",
    "Bossa nova",
    "Funk groove",
    "Ballad",
)


def default_bpm_for_song_data(song_data: dict[str, Any] | None) -> int:
    """BPM from song extensions — matches Active Song card metadata."""
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


def reset_playback_song_tracking(st: Any) -> None:
    """Force BPM/groove widgets to pick up the next active song's defaults."""
    st.session_state.pop(LAST_BPM_SONG, None)
    st.session_state.pop(LAST_PLAYBACK_GROOVE_SONG, None)
    st.session_state.pop(LAST_BACKING_DEFAULTS_SONG_ID, None)
    st.session_state.pop(PENDING_BACKING_TRACK_BPM, None)
    st.session_state.pop(PENDING_BACKING_GROOVE, None)


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
        st.session_state[LAST_BACKING_DEFAULTS_SONG_ID] = song_id
        st.session_state[LAST_BPM_SONG] = song_id
        st.session_state[LAST_PLAYBACK_GROOVE_SONG] = song_id
        st.session_state[BPM_WIDGET_KEY] = int(default_bpm)
        st.session_state[BACKING_GROOVE_KEY] = norm_groove
    elif pending_bpm is not None:
        st.session_state[BPM_WIDGET_KEY] = int(pending_bpm)
    elif BPM_WIDGET_KEY not in st.session_state:
        st.session_state[BPM_WIDGET_KEY] = int(default_bpm)

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

    bpm = int(st.session_state.get(BPM_WIDGET_KEY, default_bpm))
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
) -> tuple[int, str]:
    """Sync BPM + groove when the active song changes; preserve manual tweaks otherwise."""
    bpm, groove = apply_backing_defaults_for_song(
        st,
        song_id=song_id,
        default_bpm=int(default_bpm),
        default_groove=default_groove,
        song_data=song_data,
        infer_fn=infer_fn,
    )
    if st.session_state.get(LAST_BACKING_DEFAULTS_SONG_ID) == song_id:
        if PRACTICE_GROOVE_KEY not in st.session_state:
            st.session_state[PRACTICE_GROOVE_KEY] = groove
    return bpm, groove
