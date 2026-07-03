"""Global practice key mode — standard (per-song) vs fixed key family."""

from __future__ import annotations

from typing import Any

from music_theory import (
    COMMON_KEYS,
    coerce_key_to_mode,
    key_is_minor,
    key_mode,
    normalize_root,
    relative_major_of_minor,
    relative_minor_of_major,
    split_chord,
)

PRACTICE_KEY_MODE_KEY = "practice_key_mode"
FIXED_PRACTICE_KEY = "fixed_practice_key"

MODE_STANDARD = "standard"
MODE_FIXED = "fixed"

PRACTICE_KEY_BEHAVIOR_LABEL = "Key behavior for this practice session"

_MODE_LABELS = {
    MODE_STANDARD: "Use each song's original/default key",
    MODE_FIXED: "Use one key family for this practice session",
}

# Legacy sidebar labels (tests / compatibility).
_MODE_LABELS_LEGACY = {
    MODE_STANDARD: "Standard (Follow Song Key)",
    MODE_FIXED: "Fixed Practice Key",
}


def practice_key_mode_label(mode: str) -> str:
    return _MODE_LABELS.get(str(mode or "").strip(), _MODE_LABELS[MODE_STANDARD])


def practice_key_mode_label_legacy(mode: str) -> str:
    return _MODE_LABELS_LEGACY.get(str(mode or "").strip(), _MODE_LABELS_LEGACY[MODE_STANDARD])


def ensure_practice_key_mode_defaults(session: dict[str, Any]) -> None:
    if str(session.get(PRACTICE_KEY_MODE_KEY) or "").strip() not in {
        MODE_STANDARD,
        MODE_FIXED,
    }:
        session[PRACTICE_KEY_MODE_KEY] = MODE_STANDARD


def get_practice_key_mode(session: dict[str, Any]) -> str:
    ensure_practice_key_mode_defaults(session)
    return str(session.get(PRACTICE_KEY_MODE_KEY) or MODE_STANDARD).strip()


def is_fixed_practice_key_mode(session: dict[str, Any]) -> bool:
    return get_practice_key_mode(session) == MODE_FIXED


def get_fixed_practice_key(session: dict[str, Any]) -> str:
    return str(session.get(FIXED_PRACTICE_KEY) or "").strip()


def _major_family_anchor(key: str) -> str:
    raw = str(key or "C").strip() or "C"
    if key_is_minor(raw):
        raw = relative_major_of_minor(raw)
    major = coerce_key_to_mode(raw, "major")
    root, _ = split_chord(major)
    norm = normalize_root(root)
    for candidate in COMMON_KEYS:
        if normalize_root(candidate) == norm:
            return candidate
    return "C"


def set_fixed_practice_key(session: dict[str, Any], key: str) -> None:
    anchor = _major_family_anchor(key)
    if anchor:
        session[FIXED_PRACTICE_KEY] = anchor


def set_practice_key_mode(session: dict[str, Any], mode: str) -> None:
    m = str(mode or MODE_STANDARD).strip()
    if m not in {MODE_STANDARD, MODE_FIXED}:
        m = MODE_STANDARD
    session[PRACTICE_KEY_MODE_KEY] = m


def resolve_fixed_practice_concert_key(fixed_key: str, song_original_key: str) -> str:
    """Map a fixed key-family anchor onto the active song's major/minor mode."""
    fixed = _major_family_anchor(fixed_key)
    original = str(song_original_key or "C").strip() or "C"
    if key_mode(original) == "major":
        return fixed
    return relative_minor_of_major(fixed)


def fixed_key_family_options() -> list[str]:
    """Major-family anchors, shown as major / relative-minor families."""
    return list(COMMON_KEYS)


def fixed_key_family_label(key: str) -> str:
    """User-facing family label, e.g. C / A minor."""
    major = _major_family_anchor(key)
    minor = relative_minor_of_major(major)
    minor_root, _ = split_chord(minor)
    return f"{major} / {minor_root} minor"


def fixed_key_family_anchor_from_label(label_or_key: str) -> str:
    """Accept either a family label or a raw key and return the major anchor."""
    raw = str(label_or_key or "").strip()
    if "/" in raw:
        raw = raw.split("/", 1)[0].strip()
    return _major_family_anchor(raw)


def resolve_practice_concert_key_for_song(
    session: dict[str, Any],
    song_original_key: str,
    *,
    pick_key: str = "",
    fallback: str = "",
) -> str:
    """Effective practice concert key for one song — honors fixed mode when enabled."""
    original = str(song_original_key or fallback or "C").strip() or "C"
    if is_fixed_practice_key_mode(session):
        fixed = _major_family_anchor(get_fixed_practice_key(session) or session.get("display_key") or "C")
        set_fixed_practice_key(session, fixed)
        if fixed:
            return resolve_fixed_practice_concert_key(fixed, original)
    try:
        from songs.practice_key_state import get_practice_concert_key

        pk = str(pick_key or "").strip()
        saved = get_practice_concert_key(session, pk) if pk else ""
        if saved:
            return saved
    except ImportError:
        pass
    fb = str(fallback or "").strip()
    return fb or original


def apply_fixed_mode_target(
    session: dict[str, Any],
    target: str,
    song_original_key: str,
) -> str:
    """When fixed mode is on, replace a standard-mode target with the family key."""
    if not is_fixed_practice_key_mode(session):
        return str(target or "").strip() or str(song_original_key or "C").strip() or "C"
    fixed = _major_family_anchor(get_fixed_practice_key(session) or target or "C")
    set_fixed_practice_key(session, fixed)
    anchor = fixed or str(target or session.get("display_key") or "").strip()
    if not anchor:
        anchor = str(song_original_key or "C").strip() or "C"
    return resolve_fixed_practice_concert_key(anchor, song_original_key)


def on_practice_key_mode_change(
    session: dict[str, Any],
    *,
    original_key: str = "",
    st_like: Any | None = None,
) -> None:
    """Callback when the user toggles practice key behavior."""
    mode = get_practice_key_mode(session)
    if mode == MODE_FIXED:
        anchor = _major_family_anchor(get_fixed_practice_key(session) or session.get("display_key") or original_key or "C")
        set_fixed_practice_key(session, anchor)
        try:
            from songs.key_state import BACKING_NEEDS_REGEN, invalidate_backing_cache, request_display_key

            resolved = resolve_fixed_practice_concert_key(anchor, original_key or anchor)
            request_display_key(session, resolved)
            session[BACKING_NEEDS_REGEN] = True
            invalidate_backing_cache(session)
        except ImportError:
            pass
    if st_like is not None:
        try:
            from songs.state import persist_music_local_state

            persist_music_local_state(st_like)
        except Exception:
            pass


def fixed_practice_key_status_line(session: dict[str, Any]) -> str:
    """Compact sidebar status when fixed mode is active."""
    if not is_fixed_practice_key_mode(session):
        return ""
    key = _major_family_anchor(
        get_fixed_practice_key(session)
        or str(session.get("display_key") or "").strip()
        or "C"
    )
    return f"Practice key family: {fixed_key_family_label(key)} (fixed)"


def fixed_key_family_summary_entry(session: dict[str, Any]) -> str:
    """Practice setup summary suffix when fixed mode is active."""
    if not is_fixed_practice_key_mode(session):
        return ""
    key = get_fixed_practice_key(session) or str(session.get("display_key") or "").strip() or "C"
    return f"Fixed Practice Key: {fixed_key_family_label(key)}"


def render_practice_key_behavior_panel(
    st_module: Any,
    session: dict[str, Any],
    *,
    original_key: str,
    display_key_options: list[str],
    on_mode_change: Any | None = None,
    on_concert_key_change: Any | None = None,
) -> None:
    """Practice-page session setup — key behavior and optional fixed concert key."""
    ensure_practice_key_mode_defaults(session)
    st_module.markdown(
        f'<p class="ui-practice-key-behavior-label"><strong>{PRACTICE_KEY_BEHAVIOR_LABEL}</strong></p>',
        unsafe_allow_html=True,
    )
    st_module.radio(
        PRACTICE_KEY_BEHAVIOR_LABEL,
        options=[MODE_STANDARD, MODE_FIXED],
        format_func=practice_key_mode_label,
        key=PRACTICE_KEY_MODE_KEY,
        label_visibility="collapsed",
        on_change=on_mode_change,
    )
    if is_fixed_practice_key_mode(session):
        current = _major_family_anchor(get_fixed_practice_key(session) or session.get("display_key") or original_key or "C")
        set_fixed_practice_key(session, current)
        st_module.selectbox(
            "Practice Key Family",
            fixed_key_family_options(),
            key=FIXED_PRACTICE_KEY,
            format_func=fixed_key_family_label,
            help="Major songs use the major side; minor songs use the relative minor side.",
            on_change=on_concert_key_change,
        )


def on_fixed_practice_concert_key_change(session: dict[str, Any], concert_key: str) -> None:
    """Persist the fixed-family anchor when the user edits Practice / Concert Key."""
    if not is_fixed_practice_key_mode(session):
        return
    key = _major_family_anchor(concert_key or session.get(FIXED_PRACTICE_KEY) or session.get("display_key") or "C")
    if key:
        set_fixed_practice_key(session, key)


__all__ = [
    "FIXED_PRACTICE_KEY",
    "fixed_key_family_anchor_from_label",
    "fixed_key_family_label",
    "fixed_key_family_options",
    "fixed_key_family_summary_entry",
    "MODE_FIXED",
    "MODE_STANDARD",
    "PRACTICE_KEY_MODE_KEY",
    "apply_fixed_mode_target",
    "ensure_practice_key_mode_defaults",
    "get_fixed_practice_key",
    "get_practice_key_mode",
    "is_fixed_practice_key_mode",
    "on_fixed_practice_concert_key_change",
    "PRACTICE_KEY_BEHAVIOR_LABEL",
    "fixed_practice_key_status_line",
    "on_practice_key_mode_change",
    "practice_key_mode_label",
    "practice_key_mode_label_legacy",
    "render_practice_key_behavior_panel",
    "resolve_fixed_practice_concert_key",
    "resolve_practice_concert_key_for_song",
    "set_fixed_practice_key",
    "set_practice_key_mode",
]
