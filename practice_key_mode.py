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
FIXED_PRACTICE_KEY_FAMILY_ID = "fixed_practice_key_family_id"
PRACTICE_KEY_MODE_WIDGET_KEY = "practice_panel_practice_key_mode"
FIXED_PRACTICE_KEY_WIDGET_KEY = "practice_panel_fixed_practice_key"

MODE_STANDARD = "standard"
MODE_FIXED = "fixed"

FAMILY_OPTION_SEP = "|"

# (major spelling, relative-minor root spelling) — user-facing dropdown pairs.
KEY_FAMILY_CHOICES: list[tuple[str, str]] = [
    ("C", "A"),
    ("Db", "Bb"),
    ("C#", "A#"),
    ("D", "B"),
    ("Eb", "C"),
    ("D#", "C"),
    ("E", "C#"),
    ("E", "Db"),
    ("F", "D"),
    ("Gb", "Eb"),
    ("F#", "D#"),
    ("G", "E"),
    ("Ab", "F"),
    ("G#", "F"),
    ("A", "F#"),
    ("A", "Gb"),
    ("Bb", "G"),
    ("A#", "G"),
    ("B", "G#"),
    ("B", "Ab"),
]

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


def family_option_id(major: str, minor_root: str) -> str:
    return f"{major}{FAMILY_OPTION_SEP}{minor_root}"


def parse_family_option_id(option_id: str) -> tuple[str, str]:
    raw = str(option_id or "").strip()
    if FAMILY_OPTION_SEP in raw:
        major, minor_root = raw.split(FAMILY_OPTION_SEP, 1)
        return major.strip(), minor_root.strip()
    major = _major_family_anchor(raw)
    minor = relative_minor_of_major(major)
    minor_root, _ = split_chord(minor)
    return major, minor_root


def fixed_key_family_options() -> list[str]:
    return [family_option_id(major, minor_root) for major, minor_root in KEY_FAMILY_CHOICES]


def _default_family_option_id() -> str:
    return family_option_id("C", "A")


def _family_option_ids_for_major(major: str) -> list[str]:
    norm = normalize_root(_major_family_anchor(major))
    return [
        option_id
        for option_id in fixed_key_family_options()
        if normalize_root(parse_family_option_id(option_id)[0]) == norm
    ]


def normalize_stored_family_option_id(raw: str) -> str:
    """Map persisted family ids, labels, or anchors onto a canonical option id."""
    option = str(raw or "").strip()
    if not option:
        return ""
    if option in fixed_key_family_options():
        return option
    if FAMILY_OPTION_SEP in option:
        major, minor_root = option.split(FAMILY_OPTION_SEP, 1)
        major = major.strip()
        minor_root = minor_root.strip()
        candidate = family_option_id(major, minor_root)
        if candidate in fixed_key_family_options():
            return candidate
        return _family_option_id_for_major(major, prefer=major)
    if "/" in option or "major" in option.lower():
        anchor = fixed_key_family_anchor_from_label(option)
        return _family_option_id_for_major(anchor, prefer=anchor)
    return _family_option_id_for_major(option, prefer=option)


def _family_option_id_for_major(major: str, *, prefer: str = "") -> str:
    prefer = str(prefer or major or "").strip()
    matches = _family_option_ids_for_major(major)
    if prefer:
        for option_id in matches:
            if parse_family_option_id(option_id)[0] == prefer:
                return option_id
    if matches:
        return matches[0]
    return _default_family_option_id()


def resolve_family_option_id(session: dict[str, Any]) -> str:
    widget = str(session.get(FIXED_PRACTICE_KEY_WIDGET_KEY) or "").strip()
    if widget in fixed_key_family_options():
        return widget
    normalized_widget = normalize_stored_family_option_id(widget)
    if normalized_widget in fixed_key_family_options():
        return normalized_widget
    stored = str(session.get(FIXED_PRACTICE_KEY_FAMILY_ID) or "").strip()
    if stored in fixed_key_family_options():
        return stored
    normalized_stored = normalize_stored_family_option_id(stored)
    if normalized_stored in fixed_key_family_options():
        return normalized_stored
    canonical = get_fixed_practice_key(session)
    if canonical and not stored and not widget:
        return _family_option_id_for_major(canonical, prefer=canonical)
    return _default_family_option_id()


def practice_key_mode_label(mode: str) -> str:
    return _MODE_LABELS.get(str(mode or "").strip(), _MODE_LABELS[MODE_STANDARD])


def practice_key_mode_label_legacy(mode: str) -> str:
    return _MODE_LABELS_LEGACY.get(str(mode or "").strip(), _MODE_LABELS_LEGACY[MODE_STANDARD])


def ensure_practice_key_mode_defaults(session: dict[str, Any]) -> None:
    if PRACTICE_KEY_MODE_KEY not in session:
        session[PRACTICE_KEY_MODE_KEY] = MODE_STANDARD
        return
    if str(session.get(PRACTICE_KEY_MODE_KEY) or "").strip() not in {
        MODE_STANDARD,
        MODE_FIXED,
    }:
        session[PRACTICE_KEY_MODE_KEY] = MODE_STANDARD


def get_practice_key_mode(session: dict[str, Any]) -> str:
    ensure_practice_key_mode_defaults(session)
    return str(session.get(PRACTICE_KEY_MODE_KEY) or MODE_STANDARD).strip()


def is_fixed_practice_key_mode(session: dict[str, Any]) -> bool:
    return str(session.get(PRACTICE_KEY_MODE_KEY) or MODE_STANDARD).strip() == MODE_FIXED


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


def set_fixed_practice_key_family(session: dict[str, Any], option_id: str) -> None:
    """Persist canonical anchor + user-facing family spelling."""
    option = str(option_id or "").strip()
    if option not in fixed_key_family_options():
        option = _family_option_id_for_major(option, prefer=option)
    major, _minor_root = parse_family_option_id(option)
    anchor = _major_family_anchor(major)
    session[FIXED_PRACTICE_KEY_FAMILY_ID] = option
    session[FIXED_PRACTICE_KEY] = anchor
    session[FIXED_PRACTICE_KEY_WIDGET_KEY] = option


def set_fixed_practice_key(session: dict[str, Any], key: str) -> None:
    """Accept a family option id or a raw major anchor."""
    raw = str(key or "").strip()
    if FAMILY_OPTION_SEP in raw or raw in fixed_key_family_options():
        set_fixed_practice_key_family(session, raw)
        return
    set_fixed_practice_key_family(session, _family_option_id_for_major(raw, prefer=raw))


def set_practice_key_mode(session: dict[str, Any], mode: str) -> None:
    m = str(mode or MODE_STANDARD).strip()
    if m not in {MODE_STANDARD, MODE_FIXED}:
        m = MODE_STANDARD
    session[PRACTICE_KEY_MODE_KEY] = m
    session[PRACTICE_KEY_MODE_WIDGET_KEY] = m


def prepare_practice_key_mode_widgets(
    session: dict[str, Any],
    *,
    original_key: str = "",
) -> None:
    """Sync canonical practice-key mode into page widget keys before render."""
    _ = original_key
    hydrated = bool(session.get("_music_workspace_blob_hydrated"))
    restored = bool(session.get("_practice_key_mode_restored") or session.get("_music_authoritative_cloud_apply"))
    if hydrated or restored:
        if PRACTICE_KEY_MODE_KEY in session:
            session[PRACTICE_KEY_MODE_WIDGET_KEY] = str(session.get(PRACTICE_KEY_MODE_KEY) or MODE_STANDARD)
            if is_fixed_practice_key_mode(session):
                fam = normalize_stored_family_option_id(
                    str(
                        session.get(FIXED_PRACTICE_KEY_FAMILY_ID)
                        or session.get(FIXED_PRACTICE_KEY_WIDGET_KEY)
                        or ""
                    ).strip()
                )
                if fam:
                    session[FIXED_PRACTICE_KEY_FAMILY_ID] = fam
                    session[FIXED_PRACTICE_KEY_WIDGET_KEY] = fam
            return
    ensure_practice_key_mode_defaults(session)
    session[PRACTICE_KEY_MODE_WIDGET_KEY] = get_practice_key_mode(session)
    if is_fixed_practice_key_mode(session):
        fam = resolve_family_option_id(session)
        if fam:
            major, _ = parse_family_option_id(fam)
            session[FIXED_PRACTICE_KEY_FAMILY_ID] = fam
            session[FIXED_PRACTICE_KEY_WIDGET_KEY] = fam
            session[FIXED_PRACTICE_KEY] = _major_family_anchor(major)


def commit_practice_key_mode_widgets(session: dict[str, Any]) -> None:
    """Copy page widget values into canonical session keys after user edits."""
    widget_mode = str(session.get(PRACTICE_KEY_MODE_WIDGET_KEY) or "").strip()
    if widget_mode in {MODE_STANDARD, MODE_FIXED}:
        session[PRACTICE_KEY_MODE_KEY] = widget_mode
    if is_fixed_practice_key_mode(session):
        widget_family = str(session.get(FIXED_PRACTICE_KEY_WIDGET_KEY) or "").strip()
        if widget_family:
            set_fixed_practice_key_family(session, widget_family)


def persist_practice_key_mode(st_like: Any | None) -> None:
    """Force cloud/disk save so fixed mode survives refresh and reboot."""
    if st_like is None:
        return
    try:
        from music_persistent_state import APP_ID, build_music_disk_state, force_autosave

        force_autosave(
            st_like,
            APP_ID,
            build_state=build_music_disk_state,
            reason="practice_key_mode_change",
        )
        return
    except Exception:
        pass
    try:
        from songs.state import persist_music_local_state

        persist_music_local_state(st_like)
    except Exception:
        pass


def resolve_fixed_practice_concert_key(fixed_key: str, song_original_key: str) -> str:
    """Map a fixed key-family anchor onto the active song's major/minor mode."""
    if FAMILY_OPTION_SEP in str(fixed_key or ""):
        return resolve_fixed_practice_concert_key_for_family(fixed_key, song_original_key)
    fixed = _major_family_anchor(fixed_key)
    original = str(song_original_key or "C").strip() or "C"
    if key_mode(original) == "major":
        return fixed
    return relative_minor_of_major(fixed)


def resolve_fixed_practice_concert_key_for_family(
    option_id: str,
    song_original_key: str,
) -> str:
    """Resolve a song into the selected family, preserving the user's spelling."""
    return resolve_session_key_from_family(option_id, key_mode(song_original_key))


def resolve_session_key_from_family(key_family: str, musical_mode: str) -> str:
    """
    Canonical session tonal key from a fixed family + active object mode.

    ``musical_mode`` must be ``major`` or ``minor`` from the active song/progression/jam/mission —
    not inferred from the family label alone.
    """
    option_id = str(key_family or "").strip()
    if FAMILY_OPTION_SEP not in option_id:
        option_id = _family_option_id_for_major(option_id, prefer=option_id)
    major, minor_root = parse_family_option_id(option_id)
    mode = str(musical_mode or "major").strip().lower()
    if mode == "minor":
        return f"{minor_root}m"
    return major


def fixed_key_family_label(option_id: str) -> str:
    """User-facing family label, e.g. G major / E minor."""
    major, minor_root = parse_family_option_id(option_id)
    return f"{major} major / {minor_root} minor"


def fixed_key_family_label_for_session(session: dict[str, Any]) -> str:
    if not is_fixed_practice_key_mode(session):
        return ""
    return fixed_key_family_label(resolve_family_option_id(session))


def fixed_key_family_anchor_from_label(label_or_key: str) -> str:
    """Accept either a family label or a raw key and return the major anchor."""
    raw = str(label_or_key or "").strip()
    if "major" in raw.lower() and "/" in raw:
        raw = raw.split("/", 1)[0].strip().replace("major", "").strip()
    elif "/" in raw:
        raw = raw.split("/", 1)[0].strip()
    return _major_family_anchor(raw)


def _fixed_family_major_anchor(session: dict[str, Any]) -> str:
    option_id = resolve_family_option_id(session)
    major, _ = parse_family_option_id(option_id)
    return _major_family_anchor(major)


def resolve_fixed_practice_concert_key_for_session(
    session: dict[str, Any],
    song_original_key: str,
) -> str:
    """Resolve a source key through the active fixed family, preserving spelling."""
    option_id = resolve_family_option_id(session)
    try:
        from session_key_context import resolve_active_object_mode

        mode = resolve_active_object_mode(session, original_key=song_original_key)
    except ImportError:
        mode = key_mode(song_original_key)
    return resolve_session_key_from_family(option_id, mode)


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
        return resolve_fixed_practice_concert_key_for_session(session, original)
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
    return resolve_fixed_practice_concert_key_for_session(session, song_original_key)


def _apply_fixed_display_key_for_song(
    session: dict[str, Any],
    *,
    original_key: str,
) -> None:
    if not is_fixed_practice_key_mode(session):
        return
    try:
        from songs.key_state import BACKING_NEEDS_REGEN, invalidate_backing_cache, request_display_key

        resolved = resolve_fixed_practice_concert_key_for_session(session, original_key or "C")
        request_display_key(session, resolved)
        session[BACKING_NEEDS_REGEN] = True
        invalidate_backing_cache(session)
    except ImportError:
        pass


def on_practice_key_mode_change(
    session: dict[str, Any],
    *,
    original_key: str = "",
    st_like: Any | None = None,
) -> None:
    """Callback when the user toggles practice key behavior."""
    commit_practice_key_mode_widgets(session)
    if is_fixed_practice_key_mode(session) and not str(session.get(FIXED_PRACTICE_KEY_FAMILY_ID) or "").strip():
        set_fixed_practice_key_family(session, _default_family_option_id())
    if is_fixed_practice_key_mode(session):
        _apply_fixed_display_key_for_song(session, original_key=original_key)
    persist_practice_key_mode(st_like)


def on_practice_key_family_change(
    session: dict[str, Any],
    *,
    original_key: str = "",
    st_like: Any | None = None,
) -> None:
    """Callback when the user picks a fixed key family."""
    commit_practice_key_mode_widgets(session)
    _apply_fixed_display_key_for_song(session, original_key=original_key)
    persist_practice_key_mode(st_like)


def fixed_practice_key_status_line(session: dict[str, Any]) -> str:
    """Compact sidebar status when fixed mode is active."""
    if not is_fixed_practice_key_mode(session):
        return ""
    return f"Practice Key Family: {fixed_key_family_label_for_session(session)} (fixed)"


def fixed_key_family_summary_entry(session: dict[str, Any]) -> str:
    """Practice setup summary suffix when fixed mode is active."""
    if not is_fixed_practice_key_mode(session):
        return ""
    return f"Fixed Practice Key: {fixed_key_family_label_for_session(session)}"


def render_practice_key_behavior_panel(
    st_module: Any,
    session: dict[str, Any],
    *,
    original_key: str,
    display_key_options: list[str],
    on_mode_change: Any | None = None,
    on_family_change: Any | None = None,
) -> None:
    """Practice-page session setup — key behavior and optional fixed concert key."""
    _ = display_key_options
    prepare_practice_key_mode_widgets(session, original_key=original_key)
    st_module.markdown(
        f'<p class="ui-practice-key-behavior-label"><strong>{PRACTICE_KEY_BEHAVIOR_LABEL}</strong></p>',
        unsafe_allow_html=True,
    )
    st_module.radio(
        PRACTICE_KEY_BEHAVIOR_LABEL,
        options=[MODE_STANDARD, MODE_FIXED],
        format_func=practice_key_mode_label,
        key=PRACTICE_KEY_MODE_WIDGET_KEY,
        label_visibility="collapsed",
        on_change=on_mode_change,
    )
    if is_fixed_practice_key_mode(session):
        st_module.selectbox(
            "Practice Key Family",
            fixed_key_family_options(),
            key=FIXED_PRACTICE_KEY_WIDGET_KEY,
            format_func=fixed_key_family_label,
            help="Major songs use the major side; minor songs use the relative minor side.",
            on_change=on_family_change,
        )


def on_fixed_practice_concert_key_change(session: dict[str, Any], concert_key: str) -> None:
    """Legacy hook — display/concert key must not rewrite the selected key family."""
    _ = concert_key
    if not is_fixed_practice_key_mode(session):
        return


def disable_fixed_practice_key_mode(
    session: dict[str, Any],
    *,
    original_key: str = "",
    st_like: Any | None = None,
) -> None:
    """Quick-off from the sidebar: return to standard per-song key behavior."""
    if not is_fixed_practice_key_mode(session):
        return
    set_practice_key_mode(session, MODE_STANDARD)
    original = str(original_key or "").strip()
    try:
        from songs.key_state import BACKING_NEEDS_REGEN, invalidate_backing_cache, request_display_key

        if original:
            request_display_key(session, original)
        session[BACKING_NEEDS_REGEN] = True
        invalidate_backing_cache(session)
    except ImportError:
        pass
    persist_practice_key_mode(st_like)


__all__ = [
    "FIXED_PRACTICE_KEY",
    "FIXED_PRACTICE_KEY_FAMILY_ID",
    "FIXED_PRACTICE_KEY_WIDGET_KEY",
    "KEY_FAMILY_CHOICES",
    "PRACTICE_KEY_BEHAVIOR_LABEL",
    "PRACTICE_KEY_MODE_KEY",
    "PRACTICE_KEY_MODE_WIDGET_KEY",
    "MODE_FIXED",
    "MODE_STANDARD",
    "apply_fixed_mode_target",
    "commit_practice_key_mode_widgets",
    "disable_fixed_practice_key_mode",
    "ensure_practice_key_mode_defaults",
    "family_option_id",
    "normalize_stored_family_option_id",
    "fixed_key_family_anchor_from_label",
    "fixed_key_family_label",
    "fixed_key_family_label_for_session",
    "fixed_key_family_options",
    "fixed_key_family_summary_entry",
    "fixed_practice_key_status_line",
    "get_fixed_practice_key",
    "get_practice_key_mode",
    "is_fixed_practice_key_mode",
    "on_fixed_practice_concert_key_change",
    "on_practice_key_family_change",
    "on_practice_key_mode_change",
    "parse_family_option_id",
    "persist_practice_key_mode",
    "practice_key_mode_label",
    "practice_key_mode_label_legacy",
    "prepare_practice_key_mode_widgets",
    "render_practice_key_behavior_panel",
    "resolve_family_option_id",
    "resolve_fixed_practice_concert_key",
    "resolve_fixed_practice_concert_key_for_family",
    "resolve_session_key_from_family",
    "resolve_fixed_practice_concert_key_for_session",
    "resolve_practice_concert_key_for_song",
    "set_fixed_practice_key",
    "set_fixed_practice_key_family",
    "set_practice_key_mode",
]
