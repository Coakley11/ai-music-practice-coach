"""Harmonic span choice, presented so nothing meaningful is clipped (MC3.1).

The picker option keeps its compact one-line label (``chords · relationship · section ·
★ Recommended``). Under the picker the chosen span is repeated as a two-line card that
wraps on any width: the chord sequence on the first line, relationship · section ·
★ Recommended on the second — so a phone never hides the harmony or the recommendation.
"""

from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Any, Callable, Sequence

RECOMMENDED = "★ Recommended"


@dataclass(frozen=True)
class SpanChoice:
    chords: str  # "G♯m7|C♯7 → C♯m7|F♯7 → F♯m7|B7" (bar counts included when > 1)
    relationship: str  # "" when the analyzer is not confident — never invented
    section: str
    recommended: bool
    roman: str  # "" unless the roman path is confident

    @property
    def meta(self) -> str:
        parts = [p for p in (self.relationship, self.section) if p]
        if self.recommended:
            parts.append(RECOMMENDED)
        return " · ".join(parts)

    def label(self) -> str:
        """One-line picker label (unchanged format)."""
        return " · ".join(p for p in (self.chords, self.meta) if p)


def span_choice(
    span: Any,
    *,
    project: Callable[[str], str] | None = None,
    include_section: bool = True,
    recommended: bool = False,
    with_bars: bool = False,
) -> SpanChoice:
    proj = project or (lambda ch: ch)
    if with_bars:
        chords = " → ".join(
            f"{proj(ev.chord) or ev.chord} ({ev.bars} bars)" if int(getattr(ev, "bars", 1) or 1) > 1 else (proj(ev.chord) or ev.chord)
            for ev in getattr(span, "raw_events", ()) or ()
        )
    else:
        chords = " → ".join(proj(ch) or ch for ch in span.chords)
    roman = " – ".join(span.roman) if getattr(span, "roman_confident", False) else ""
    return SpanChoice(
        chords=chords,
        relationship=str(getattr(span, "relationship_label", "") or ""),
        section=str(span.section_label or "") if include_section else "",
        recommended=bool(recommended),
        roman=roman,
    )


def span_card_html(choice: SpanChoice) -> str:
    """Wrapping two-line card for the chosen span (all text escaped)."""
    meta = html.escape(choice.meta)
    roman = f'<div class="mc-span-roman">Roman numerals: {html.escape(choice.roman)}</div>' if choice.roman else ""
    return (
        '<div class="mc-span-card">'
        f'<div class="mc-span-chords">{html.escape(choice.chords)}</div>'
        + (f'<div class="mc-span-meta">{meta}</div>' if meta else "")
        + roman
        + "</div>"
    )


def span_heading(relationship_label: str, chords: Sequence[str]) -> str:
    """``Span: ii–V–I`` — or just the chord progression when no relationship is recognised."""
    rel = str(relationship_label or "").strip()
    return f"Span: {rel}" if rel else f"Span: {' → '.join(chords)}"


__all__ = ["RECOMMENDED", "SpanChoice", "span_card_html", "span_choice", "span_heading"]
