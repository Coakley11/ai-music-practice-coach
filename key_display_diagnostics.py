"""?dev=1 diagnostics for Original / Practice / Written / Shape key domains."""

from __future__ import annotations

from typing import Any


def _clean(text: object) -> str:
    return str(text or "").strip()


def build_key_display_diagnostics(session: dict[str, Any]) -> dict[str, Any]:
    """Trace authoritative spellings vs displayed labels for each key domain."""
    from music_theory import (
        chord_root_for_theory,
        display_key_label,
        normalize_root,
        split_key_center,
    )

    original_raw = ""
    practice_raw = _clean(session.get("display_key") or session.get("concert_key"))
    try:
        from songs.key_state import resolve_active_musical_key
        from songs.music_source import display_key_context

        original_raw, _ = display_key_context(session)
        ctx = resolve_active_musical_key(session)
    except Exception:
        ctx = None

    if ctx is not None:
        original_raw = _clean(getattr(ctx, "original_key", None) or original_raw)
        practice_raw = _clean(getattr(ctx, "practice_concert_key", None) or practice_raw)
        written_raw = _clean(getattr(ctx, "written_key", None))
        shape_raw = _clean(getattr(ctx, "shape_key", None))
        chart_raw = _clean(getattr(ctx, "chart_key", None))
        chart_mode = _clean(getattr(ctx, "chart_key_mode", None))
        source = _clean(getattr(ctx, "instrument", None))
    else:
        written_raw = ""
        shape_raw = ""
        chart_raw = ""
        chart_mode = ""
        source = ""

    def _row(raw: str, *, domain: str) -> dict[str, Any]:
        token = _clean(raw) or ""
        tonic, mode = split_key_center(token or "C")
        theory_pc = chord_root_for_theory(token or "C") if token else ""
        display = display_key_label(token) if token else ""
        respell_occurred = bool(token and theory_pc and normalize_root(tonic) == theory_pc and tonic != theory_pc)
        return {
            "domain": domain,
            "raw": token,
            "authoritative_tonic": tonic,
            "authoritative_mode": mode,
            "display_label": display,
            "pitch_class_normalized": theory_pc,
            "pitch_class_respelling_would_occur": respell_occurred,
        }

    meta = session.get("active_song_state")
    meta = meta if isinstance(meta, dict) else {}
    selected = session.get("selected_song")
    selected = selected if isinstance(selected, dict) else {}

    return {
        "active_song_source": _clean(session.get("active_music_source") or meta.get("music_source")),
        "pick_key": _clean(session.get("active_catalog_pick_key") or meta.get("pick_key") or selected.get("pick_key")),
        "selected_song_key_field": _clean(selected.get("key")),
        "canonical_display_key": _clean(meta.get("display_key")),
        "persistence_display_key": _clean(session.get("display_key")),
        "key_context_instrument": source,
        "chart_key_mode": chart_mode,
        "original": _row(original_raw, domain="original"),
        "practice_concert": _row(practice_raw, domain="practice_concert"),
        "written": _row(written_raw, domain="written"),
        "shape": _row(shape_raw, domain="guitar_shape"),
        "chart": _row(chart_raw, domain="chart"),
        "instrument": _clean(session.get("instrument")),
        "transposing_subtype": _clean(session.get("selected_transposing_instrument")),
        "show_chart_in_instrument_key": bool(session.get("show_chart_in_instrument_key")),
    }


def render_key_display_diagnostics(st: Any, session: dict[str, Any] | None = None) -> None:
    """Sidebar expander for ?dev=1 key-domain spelling traces."""
    ss = session if isinstance(session, dict) else st.session_state
    try:
        from music_dev_ui import music_dev_mode_enabled

        if not music_dev_mode_enabled(st=st):
            return
    except ImportError:
        if not bool(ss.get("developer_mode")):
            return
    diag = build_key_display_diagnostics(ss)
    with st.sidebar.expander("Key display diagnostics (?dev=1)", expanded=False):
        st.json(diag)


__all__ = [
    "build_key_display_diagnostics",
    "render_key_display_diagnostics",
]
