"""Shared responsive layout tokens for Music Practice Coach UI.

M1 introduces phone breakpoints for global navigation. Later slices (M2–M7)
should reuse these constants instead of inventing new ad-hoc widths.
"""

from __future__ import annotations

# Phone / compact layout — aligns with audit recommendation (~360–430 CSS px).
# Desktop quick-nav art (2-row) stays above this width.
PHONE_MAX_WIDTH_PX = 720

# Narrow phones — tighter type / icon-only history controls.
PHONE_NARROW_MAX_WIDTH_PX = 420


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
