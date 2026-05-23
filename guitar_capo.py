"""Guitar capo mode — shape-key charts vs concert/sounding backing audio."""

from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Any

from music_theory import (
    PRACTICE_KEYS,
    display_key_options,
    semitone_distance,
    transpose_sections_dict,
)

CAPO_ENABLED_KEY = "guitar_capo_enabled"
CAPO_SOUNDING_KEY = "guitar_capo_sounding_key"
CAPO_SHAPE_KEY = "guitar_capo_shape_key"
CAPO_LAST_CONCERT_KEY = "guitar_capo_last_concert_key"

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


def init_capo_session_state(session_state: dict, *, concert_key: str) -> None:
    session_state.setdefault(CAPO_ENABLED_KEY, False)
    last = session_state.get(CAPO_LAST_CONCERT_KEY)
    if last != concert_key:
        session_state[CAPO_LAST_CONCERT_KEY] = concert_key
        session_state[CAPO_SOUNDING_KEY] = concert_key
        if CAPO_SHAPE_KEY not in session_state:
            session_state[CAPO_SHAPE_KEY] = default_shape_key_for_sounding(concert_key)
    session_state.setdefault(CAPO_SOUNDING_KEY, concert_key)
    if CAPO_SHAPE_KEY not in session_state:
        session_state[CAPO_SHAPE_KEY] = default_shape_key_for_sounding(
            session_state[CAPO_SOUNDING_KEY]
        )


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
        "Capo mode is not global transpose — use <em>Practice / Display Key</em> in the sidebar "
        "to move the whole song.</p></div>"
    )


def render_guitar_capo_sidebar(st: Any, session_state: dict, *, concert_key: str) -> None:
    """Compact capo controls in the sidebar (guitar only)."""
    init_capo_session_state(session_state, concert_key=concert_key)
    st.markdown(
        '<p class="ui-key-global-hint">Guitar capo — shape chords vs sounding key</p>',
        unsafe_allow_html=True,
    )
    session_state[CAPO_ENABLED_KEY] = st.checkbox(
        "Capo shape mode",
        value=bool(session_state.get(CAPO_ENABLED_KEY)),
        key="guitar_capo_enabled_widget",
        help="Charts/TAB use grip shapes; backing audio stays in the sounding key.",
    )
    if not session_state.get(CAPO_ENABLED_KEY):
        st.caption("Off — charts follow Practice / Display Key like other instruments.")
        return

    key_opts = display_key_options(concert_key)
    c1, c2 = st.columns(2)
    with c1:
        session_state[CAPO_SOUNDING_KEY] = st.selectbox(
            "Sounding key",
            key_opts,
            index=key_opts.index(session_state.get(CAPO_SOUNDING_KEY, concert_key))
            if session_state.get(CAPO_SOUNDING_KEY, concert_key) in key_opts
            else 0,
            key="guitar_capo_sounding_widget",
        )
    with c2:
        shape_opts = list(PRACTICE_KEYS)
        cur_shape = str(session_state.get(CAPO_SHAPE_KEY, default_shape_key_for_sounding(concert_key)))
        if cur_shape not in shape_opts:
            shape_opts = [cur_shape] + shape_opts
        session_state[CAPO_SHAPE_KEY] = st.selectbox(
            "Shape key",
            shape_opts,
            index=shape_opts.index(cur_shape) if cur_shape in shape_opts else 0,
            key="guitar_capo_shape_widget",
        )
    capo = capo_fret_for_shape(
        session_state[CAPO_SOUNDING_KEY],
        session_state[CAPO_SHAPE_KEY],
    )
    st.caption(
        f"Capo **{capo}** · backing = **{session_state[CAPO_SOUNDING_KEY]}** · "
        f"charts = **{session_state[CAPO_SHAPE_KEY]}** shapes"
    )


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
            "Enable **Capo shape mode** in the sidebar to show grip-friendly shapes "
            "while keeping the backing track in the sounding key."
        )
    return ctx
