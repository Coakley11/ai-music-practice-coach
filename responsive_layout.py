"""Shared responsive layout tokens for Music Practice Coach UI.

M1: phone breakpoints for global navigation.
M2: shared density/spacing tokens for chrome used across pages.
Later slices (M3–M7) should reuse these instead of inventing ad-hoc widths.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import TypeVar

T = TypeVar("T")

# Phone / compact layout — aligns with audit recommendation (~360–430 CSS px).
# Desktop quick-nav art (2-row) stays above this width.
PHONE_MAX_WIDTH_PX = 720

# Narrow phones — tighter type / icon-only history controls.
PHONE_NARROW_MAX_WIDTH_PX = 420

# Mobile M2 density tokens (CSS rem-ish values as strings for injection).
PHONE_DENSITY_GAP = "0.28rem"
PHONE_DENSITY_GAP_TIGHT = "0.18rem"
PHONE_DENSITY_PAD_CARD = "0.55rem 0.65rem"
PHONE_DENSITY_PAD_SECTION = "0.35rem 0.55rem"
PHONE_DENSITY_MARGIN_BLOCK = "0.35rem"
PHONE_DENSITY_TYPE_SM = "0.72rem"
PHONE_DENSITY_TYPE_XS = "0.66rem"
PHONE_DENSITY_TOUCH_MIN = "2.35rem"

# Marker value applied on phone body for diagnostics / tests.
MOBILE_DENSITY_SHELL = "m2-chrome-v1"

# Mobile M4: vertical-scroll compaction (pill grids, Composition/Custom density).
MOBILE_M4_SHELL = "m4-scroll-compact-v1"
# Mobile M5: Practice / Backing / Creative above-the-fold density.
MOBILE_M5_SHELL = "m5-fold-density-v1"
# Mobile M6: Creative sub-modes + Upload/Karaoke + Composition density.
MOBILE_M6_SHELL = "m6-tool-density-v1"
# Preferred phone pill/button grid width share (3-col ≈ 30–32%).
PHONE_PILL_GRID_MIN_PCT = 30
PHONE_PILL_GRID_FLEX = "1 1 30%"


def phone_media_query() -> str:
    return f"(max-width: {PHONE_MAX_WIDTH_PX}px)"


def phone_narrow_media_query() -> str:
    return f"(max-width: {PHONE_NARROW_MAX_WIDTH_PX}px)"


def wrap_phone_css(rules: str) -> str:
    """Wrap CSS rules in the shared phone media query."""
    body = str(rules or "").strip()
    if not body:
        return ""
    return f"@media {phone_media_query()} {{\n{body}\n}}\n"


def wrap_phone_narrow_css(rules: str) -> str:
    """Wrap CSS rules for very narrow phones (≤420px)."""
    body = str(rules or "").strip()
    if not body:
        return ""
    return f"@media {phone_narrow_media_query()} {{\n{body}\n}}\n"


def phone_density_css_vars() -> str:
    """CSS custom properties for shared phone density (inside a media block)."""
    return f"""
  --mpc-phone-gap: {PHONE_DENSITY_GAP};
  --mpc-phone-gap-tight: {PHONE_DENSITY_GAP_TIGHT};
  --mpc-phone-pad-card: {PHONE_DENSITY_PAD_CARD};
  --mpc-phone-pad-section: {PHONE_DENSITY_PAD_SECTION};
  --mpc-phone-margin-block: {PHONE_DENSITY_MARGIN_BLOCK};
  --mpc-phone-type-sm: {PHONE_DENSITY_TYPE_SM};
  --mpc-phone-type-xs: {PHONE_DENSITY_TYPE_XS};
  --mpc-phone-touch-min: {PHONE_DENSITY_TOUCH_MIN};
""".strip()


def iter_ui_rows(items: Sequence[T], cols_per_row: int = 4) -> Iterator[list[T]]:
    """Yield contiguous row chunks (row-major).

    Prefer this over ``st.columns(n)`` + ``cols[i % n]``, which becomes
    column-major when Streamlit stacks columns on phone widths.
    """
    seq = list(items or [])
    n = max(1, int(cols_per_row or 1))
    for start in range(0, len(seq), n):
        yield seq[start : start + n]
