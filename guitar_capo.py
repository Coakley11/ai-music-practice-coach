"""Guitar capo mode — shape-key charts vs concert/sounding backing audio."""

from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Any

from music_theory import (
    key_mode,
    practice_keys_for_mode,
    semitone_distance,
    transpose_sections_dict,
)

CAPO_ENABLED_KEY = "guitar_capo_enabled"
CAPO_SOUNDING_KEY = "guitar_capo_sounding_key"
CAPO_SHAPE_KEY = "guitar_capo_shape_key"
CAPO_LAST_CONCERT_KEY = "guitar_capo_last_concert_key"

CAPO_PERSIST_KEYS: tuple[str, ...] = (
    CAPO_ENABLED_KEY,
    CAPO_SOUNDING_KEY,
    CAPO_SHAPE_KEY,
    CAPO_LAST_CONCERT_KEY,
)

_SHAPE_CANDIDATES: tuple[str, ...] = (
    "G",
    "E",
    "A",
    "D",
    "C",
    "Em",
    "Am",
    "Dm",
    "Bm",
    "Gm",
    "F",
)


def capo_fret_for_shape(sounding_key: str, shape_key: str) -> int:
    """Fret number so ``shape_key`` grips sound as ``sounding_key``."""
    return semitone_distance(shape_key, sounding_key)


def default_shape_key_for_sounding(sounding_key: str) -> str:
    """Lowest-fret friendly shape center (e.g. Cm → Em, capo 8)."""
    best_shape = "G"
    best_capo = 99
    for shape in _SHAPE_CANDIDATES:
        capo = capo_fret_for_shape(sounding_key, shape)
        if capo < best_capo:
            best_capo = capo
            best_shape = shape
    return best_shape


def capo_fields_from_session(session_state: dict) -> dict[str, Any]:
    """Capo blob fields for active_song_state / cloud persistence."""
    return {
        CAPO_ENABLED_KEY: bool(session_state.get(CAPO_ENABLED_KEY)),
        CAPO_SOUNDING_KEY: str(session_state.get(CAPO_SOUNDING_KEY) or "").strip(),
        CAPO_SHAPE_KEY: str(session_state.get(CAPO_SHAPE_KEY) or "").strip(),
        CAPO_LAST_CONCERT_KEY: str(session_state.get(CAPO_LAST_CONCERT_KEY) or "").strip(),
    }


def apply_capo_context_fields(session_state: dict, ctx: dict[str, Any]) -> None:
    """Hydrate live capo session keys from canonical/cloud context."""
    if CAPO_ENABLED_KEY in ctx:
        session_state[CAPO_ENABLED_KEY] = bool(ctx.get(CAPO_ENABLED_KEY))
    for key in (CAPO_SOUNDING_KEY, CAPO_SHAPE_KEY, CAPO_LAST_CONCERT_KEY):
        if key in ctx:
            val = str(ctx.get(key) or "").strip()
            if val:
                session_state[key] = val


def capo_written_display_key(session_state: dict) -> str | None:
    """Shape key used as written/practice display when capo mode is on (read-only)."""
    if not session_state.get(CAPO_ENABLED_KEY):
        return None
    shape = str(session_state.get(CAPO_SHAPE_KEY) or "").strip()
    return shape or None


def sync_capo_written_display_key(session_state: dict) -> None:
    """Deprecated no-op — do not mutate widget-backed ``display_key`` after render.

    Capo shape is derived via ``capo_written_display_key`` and ``resolve_practice_keys``.
    """
    return


def chart_bundle_transpose_key(
    *,
    instrument: str,
    capo_enabled: bool,
    concert_key: str,
    chart_key: str,
) -> str:
    """Key used to transpose catalog sections before capo shape split.

    When guitar capo is on, sections must stay in the *sounding* (practice display)
    key; ``build_capo_context`` applies the shape-key transpose once.
    """
    if str(instrument or "").strip() == "Guitar" and capo_enabled:
        return str(concert_key or chart_key or "C").strip() or "C"
    return str(chart_key or concert_key or "C").strip() or "C"


def sync_capo_from_practice_display_key(
    session_state: dict,
    practice_display_key: str,
) -> str:
    """Mirror Practice / Concert Key into capo sounding key (reference only)."""
    sounding = str(practice_display_key or "C").strip() or "C"
    session_state[CAPO_SOUNDING_KEY] = sounding
    last = str(session_state.get(CAPO_LAST_CONCERT_KEY) or "").strip()
    if last != sounding:
        session_state[CAPO_LAST_CONCERT_KEY] = sounding
        if not session_state.get(CAPO_ENABLED_KEY):
            session_state[CAPO_SHAPE_KEY] = sounding
    if not session_state.get(CAPO_ENABLED_KEY):
        session_state[CAPO_SHAPE_KEY] = sounding
    session_state.setdefault(CAPO_ENABLED_KEY, False)
    if CAPO_SHAPE_KEY not in session_state:
        session_state[CAPO_SHAPE_KEY] = default_shape_key_for_sounding(sounding)
    return sounding


def persist_capo_to_canonical(session_state: dict) -> bool:
    """Push capo state into active_song_state blob when values changed."""
    try:
        from active_song_state import (
            ACTIVE_SONG_STATE_KEY,
            gather_active_song_context,
            write_canonical_active_song_blob_only,
        )

        live = capo_fields_from_session(session_state)
        meta = session_state.get(ACTIVE_SONG_STATE_KEY)
        if isinstance(meta, dict) and all(meta.get(k) == live.get(k) for k in live):
            return False
        ctx = gather_active_song_context(session_state)
        write_canonical_active_song_blob_only(
            session_state,
            ctx,
            reason="capo_widget",
            local_edit=True,
        )
        return True
    except ImportError:
        return False


def flush_capo_edits_to_cloud(st_module: Any) -> bool:
    """Persist capo canonical blob to cloud after sidebar widgets render.

    ``st_module`` must be the Streamlit module (``st``), not ``st.sidebar``.
    """
    try:
        from active_song_state import clear_active_song_local_edit
        from music_persistent_state import flush_active_song_edits_and_save

        ok = bool(flush_active_song_edits_and_save(st_module, reason="capo_widget"))
        if ok:
            clear_active_song_local_edit(st_module.session_state)
        return ok
    except ImportError:
        return False


def init_capo_session_state(session_state: dict, *, concert_key: str) -> None:
    """Initialize capo session keys from the current practice display key."""
    sync_capo_from_practice_display_key(session_state, concert_key)


@dataclass
class CapoContext:
    enabled: bool
    sounding_key: str
    shape_key: str
    capo_fret: int
    sounding_sections: dict[str, list[str]]
    shape_sections: dict[str, list[str]]

    @property
    def capo_label(self) -> str:
        return format_capo_fret(self.capo_fret)


def format_capo_fret(fret: int) -> str:
    if fret <= 0:
        return "open (no capo)"
    n = int(fret)
    if n % 10 == 1 and n % 100 != 11:
        suffix = "st"
    elif n % 10 == 2 and n % 100 != 12:
        suffix = "nd"
    elif n % 10 == 3 and n % 100 != 13:
        suffix = "rd"
    else:
        suffix = "th"
    return f"{n}{suffix} fret"


def build_capo_context(
    session_state: dict,
    sections: dict[str, list[str]],
    *,
    concert_key: str,
    instrument: str,
) -> CapoContext:
    """Split chart (shape) vs backing (sounding) sections for guitar capo mode."""
    init_capo_session_state(session_state, concert_key=concert_key)
    if instrument != "Guitar" or not session_state.get(CAPO_ENABLED_KEY):
        return CapoContext(
            enabled=False,
            sounding_key=concert_key,
            shape_key=concert_key,
            capo_fret=0,
            sounding_sections=sections,
            shape_sections=sections,
        )

    sounding_key = str(session_state.get(CAPO_SOUNDING_KEY, concert_key))
    shape_key = str(
        session_state.get(
            CAPO_SHAPE_KEY,
            default_shape_key_for_sounding(sounding_key),
        )
    )
    if sounding_key != concert_key:
        sounding_sections = transpose_sections_dict(sections, concert_key, sounding_key)
    else:
        sounding_sections = sections
    shape_sections = transpose_sections_dict(
        sounding_sections,
        sounding_key,
        shape_key,
    )
    capo = capo_fret_for_shape(sounding_key, shape_key)
    return CapoContext(
        enabled=True,
        sounding_key=sounding_key,
        shape_key=shape_key,
        capo_fret=capo,
        sounding_sections=sounding_sections,
        shape_sections=shape_sections,
    )


def capo_status_banner_html(ctx: CapoContext) -> str:
    if not ctx.enabled:
        return ""
    capo_line = ctx.capo_label
    return (
        '<div class="ui-card soft" style="margin:0.75rem 0;border-left:4px solid #f59e0b;">'
        '<p class="ui-card-title">🎸 Capo shape mode</p>'
        f'<p class="ui-card-sub"><strong>Actual sounding key:</strong> {html.escape(ctx.sounding_key)} · '
        f"<strong>Guitar shape key:</strong> {html.escape(ctx.shape_key)} · "
        f"<strong>Capo:</strong> {html.escape(capo_line)}</p>"
        f'<p class="ui-card-sub"><strong>Backing track plays in:</strong> {html.escape(ctx.sounding_key)} '
        f"(concert / sounding) · <strong>Charts &amp; TAB shown as:</strong> "
        f"{html.escape(ctx.shape_key)} shapes</p>"
        "<p class=\"ui-card-sub\" style=\"font-size:0.82rem;color:#64748b;\">"
        "Capo mode is not global transpose — use <em>Practice / Concert Key</em> in the sidebar "
        "to move the whole song.</p></div>"
    )


def render_guitar_capo_sidebar(
    ui: Any,
    session_state: dict,
    *,
    practice_display_key: str,
    persist_st: Any,
) -> None:
    """Compact capo controls in the sidebar (guitar only)."""
    sounding = sync_capo_from_practice_display_key(session_state, practice_display_key)
    ui.markdown(
        f'<p class="ui-sidebar-key-caption"><strong>Sounding Key:</strong> '
        f"{html.escape(sounding)}</p>",
        unsafe_allow_html=True,
    )
    session_state[CAPO_ENABLED_KEY] = ui.checkbox(
        "Capo Shape Mode",
        value=bool(session_state.get(CAPO_ENABLED_KEY)),
        key="guitar_capo_enabled_widget",
        help="Charts/TAB use grip shapes; backing audio stays in the sounding key.",
    )
    if not session_state.get(CAPO_ENABLED_KEY):
        session_state[CAPO_SHAPE_KEY] = sounding
        ui.markdown(
            f'<p class="ui-sidebar-key-caption"><strong>Shape Key:</strong> '
            f"{html.escape(sounding)}</p>",
            unsafe_allow_html=True,
        )
        ui.markdown(
            '<p class="ui-sidebar-key-caption"><strong>Capo Fret:</strong> open (no capo)</p>',
            unsafe_allow_html=True,
        )
        persist_capo_to_canonical(session_state)
        flush_capo_edits_to_cloud(persist_st)
        return

    shape_opts = practice_keys_for_mode(key_mode(sounding))
    try:
        from creative_key_sync import (
            creative_major_shape_key_options,
            flush_pending_creative_major_keys,
            is_creative_major_jam_active,
            to_major_key_preserve_spelling,
        )
    except ImportError:
        to_major_key_preserve_spelling = lambda k: str(k or "C")  # type: ignore
        is_creative_major_jam_active = lambda _s: False  # type: ignore
        creative_major_shape_key_options = lambda _s, selected="": list(shape_opts)  # type: ignore
        flush_pending_creative_major_keys = lambda _s: None  # type: ignore
    flush_pending_creative_major_keys(session_state)
    cur_shape = to_major_key_preserve_spelling(
        str(session_state.get(CAPO_SHAPE_KEY, default_shape_key_for_sounding(sounding)))
    )
    if is_creative_major_jam_active(session_state):
        shape_opts = creative_major_shape_key_options(session_state, cur_shape)
    if cur_shape not in shape_opts:
        shape_opts = [cur_shape] + shape_opts
    session_state[CAPO_SHAPE_KEY] = ui.selectbox(
        "Shape Key",
        shape_opts,
        index=shape_opts.index(cur_shape) if cur_shape in shape_opts else 0,
        key="guitar_capo_shape_widget",
        help="Guitar fingering / written key — the grips you play.",
    )
    capo = capo_fret_for_shape(sounding, session_state[CAPO_SHAPE_KEY])
    ui.markdown(
        f'<p class="ui-sidebar-key-caption"><strong>Capo Fret:</strong> {capo}</p>',
        unsafe_allow_html=True,
    )
    persist_capo_to_canonical(session_state)
    flush_capo_edits_to_cloud(persist_st)


def render_guitar_capo_practice_panel(
    st: Any,
    session_state: dict,
    *,
    concert_key: str,
    sections: dict[str, list[str]],
    key_prefix: str,
) -> CapoContext:
    """Detailed capo helper on the Practice page (preview + status)."""
    ctx = build_capo_context(
        session_state,
        sections,
        concert_key=concert_key,
        instrument="Guitar",
    )
    st.markdown("#### Guitar capo helper")
    st.caption(
        "Shape key is what your fingers play; sounding key is what everyone hears "
        "(and what the backing track uses)."
    )
    if ctx.enabled:
        st.markdown(capo_status_banner_html(ctx), unsafe_allow_html=True)
        preview = []
        for _name, chs in ctx.shape_sections.items():
            preview.extend(chs[:4])
            if len(preview) >= 8:
                break
        if preview:
            st.write(
                "Shape chords (preview): `"
                + " | ".join(preview[:8])
                + "`"
            )
    else:
        st.info(
            "Enable **Capo Shape Mode** in the sidebar to show grip-friendly shapes "
            "while keeping the backing track in the sounding key."
        )
    return ctx
