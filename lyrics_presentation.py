"""Shared presentation for Practice -> Lyrics (Composition, Custom and Catalog songs).

Presentation only. It reads the lyrics the user (or Composition Studio) already stored and
never changes the text, the section assignments or any saved data.

* ``lyrics_card_html`` -- the words, as the user wrote them: stanzas and line breaks kept.
* ``phrasing_guide_html`` -- an optional practice tool. It reports only what can be derived
  from the actual text (line lengths, breath planning, repeated lines) plus the user's own
  cues, and it never prints the lyrics a second time.
"""

from __future__ import annotations

import html
import re
from typing import Any, Mapping, Sequence

LYRICS_STYLES = """
<style>
.lyr-card{border:1px solid rgba(148,163,184,.35);border-radius:14px;background:#fff;
  box-shadow:0 6px 18px rgba(15,23,42,.06);padding:.85rem 1rem .6rem;margin:.55rem 0;}
.lyr-card.is-active{border-color:#6366f1;box-shadow:0 0 0 2px rgba(99,102,241,.18),0 6px 18px rgba(15,23,42,.06);}
.lyr-head{display:flex;align-items:center;justify-content:space-between;gap:.5rem;margin:0 0 .35rem;}
.lyr-title{margin:0;font-size:1.02rem;font-weight:800;color:#1e293b;letter-spacing:-.01em;}
.lyr-badge{font-size:.7rem;font-weight:800;letter-spacing:.04em;text-transform:uppercase;color:#4338ca;
  background:#eef2ff;border-radius:999px;padding:.1rem .5rem;white-space:nowrap;}
.lyr-stanza{margin:0 0 .7rem;}
.lyr-stanza:last-child{margin-bottom:.2rem;}
.lyr-line{margin:0;font-size:1.04rem;line-height:1.65;color:#0f172a;overflow-wrap:anywhere;}
.lyr-song{margin:.1rem 0 .25rem;font-size:.82rem;color:#64748b;}
.lyr-song strong{color:#334155;}
.lyr-guide{margin:.6rem 0;}
.lyr-guide-intro{margin:0 0 .45rem;font-size:.84rem;color:#64748b;line-height:1.5;}
.lyr-sec{border-left:3px solid #c7d2fe;background:#f8fafc;border-radius:0 10px 10px 0;padding:.5rem .75rem;margin:.5rem 0;}
.lyr-sec-name{font-weight:800;color:#1e293b;font-size:.95rem;}
.lyr-sec-meta{font-size:.76rem;color:#64748b;margin-left:.4rem;}
.lyr-note{margin:.3rem 0 0;font-size:.9rem;line-height:1.5;color:#334155;}
.lyr-note b{color:#1e293b;}
.lyr-cues{margin:.35rem 0 0;padding-left:1.1rem;font-size:.9rem;line-height:1.5;color:#334155;}
.lyr-empty{margin:.4rem 0;font-size:.9rem;color:#64748b;}
@media (max-width:480px){.lyr-card{padding:.7rem .8rem .5rem;}.lyr-line{font-size:1rem;}}
</style>
"""

_WORD_RE = re.compile(r"[A-Za-zÀ-ɏ']+")


def split_stanzas(text: str) -> list[list[str]]:
    """Group ``text`` into stanzas (blocks separated by blank lines), keeping every line."""
    stanzas: list[list[str]] = []
    current: list[str] = []
    for raw in str(text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw.strip()
        if line:
            current.append(line)
        elif current:
            stanzas.append(current)
            current = []
    if current:
        stanzas.append(current)
    return stanzas


def count_syllables(line: str) -> int:
    """Approximate syllables in a lyric line (shared heuristic with lyric alignment)."""
    try:
        from composition_lyrics_alignment import segment_word_into_syllables
    except ImportError:  # pragma: no cover - alignment module is always present
        return len(_WORD_RE.findall(line))
    total = 0
    for word in _WORD_RE.findall(line):
        total += max(1, len(segment_word_into_syllables(word)))
    return total


def _norm(line: str) -> str:
    return " ".join(_WORD_RE.findall(line.lower()))


def lyrics_card_html(
    sections: Mapping[str, str],
    *,
    song_title: str = "",
    active_section: str = "",
    section_icon: str = "\U0001F3B5",
    subtitle: str = "",
) -> str:
    """The lyrics, section by section, exactly as written (stanzas and line breaks kept)."""
    parts: list[str] = ['<div class="lyr-wrap">']
    if song_title:
        parts.append(
            f'<p class="lyr-song"><strong>{html.escape(song_title)}</strong>'
            f'{" &mdash; " + html.escape(subtitle) if subtitle else ""}</p>'
        )
    for name, text in (sections or {}).items():
        stanzas = split_stanzas(str(text or ""))
        if not stanzas:
            continue
        is_active = bool(active_section) and str(name) == str(active_section)
        parts.append(f'<section class="lyr-card{" is-active" if is_active else ""}">')
        parts.append(
            '<div class="lyr-head">'
            f'<h4 class="lyr-title">{html.escape(section_icon)} {html.escape(str(name))}</h4>'
            f'{"<span class=lyr-badge>Now practicing</span>" if is_active else ""}'
            "</div>"
        )
        for stanza in stanzas:
            parts.append('<div class="lyr-stanza">')
            for line in stanza:
                parts.append(f'<p class="lyr-line">{html.escape(line)}</p>')
            parts.append("</div>")
        parts.append("</section>")
    parts.append("</div>")
    return "".join(parts) if len(parts) > 2 else ""


def phrasing_insights(text: str) -> list[str]:
    """Plain-language notes derived only from ``text`` (never generic filler).

    Returns an empty list when the text offers nothing to say.
    """
    lines = [ln for stanza in split_stanzas(text) for ln in stanza]
    if not lines:
        return []
    notes: list[str] = []
    counts = [count_syllables(ln) for ln in lines]
    if len(lines) >= 2:
        longest = max(counts)
        shortest = min(counts)
        if longest - shortest >= 3:
            where = [i + 1 for i, c in enumerate(counts) if c == longest]
            names = ", ".join(str(i) for i in where[:3])
            noun = "Line" if len(where) == 1 else "Lines"
            notes.append(
                f"<b>Breath plan:</b> {noun} {html.escape(names)} "
                f"{'is' if len(where) == 1 else 'are'} the longest at about {longest} syllables "
                f"(the shortest has {shortest}). Breathe before "
                f"{'it' if len(where) == 1 else 'them'} and pace the phrase so it lands on the last word."
            )
    seen: dict[str, list[int]] = {}
    for i, ln in enumerate(lines):
        key = _norm(ln)
        if key:
            seen.setdefault(key, []).append(i + 1)
    repeats = [(idxs) for idxs in seen.values() if len(idxs) >= 2]
    if repeats:
        top = max(repeats, key=len)
        at = ", ".join(str(i) for i in top[:5])
        notes.append(
            f"<b>Repeated line:</b> lines {html.escape(at)} are the same words. "
            "Change the weight, dynamics or color each time so the repeat grows."
        )
    stanzas = split_stanzas(text)
    if len(stanzas) >= 2:
        sizes = [len(s) for s in stanzas]
        notes.append(
            f"<b>Phrase shape:</b> {len(stanzas)} phrases of {', '.join(str(n) for n in sizes)} "
            f"line{'s' if max(sizes) != 1 else ''}. Take a longer breath at each phrase break."
        )
    return notes


def phrasing_guide_html(
    section_lyrics: Mapping[str, str] | None,
    lyric_cues: Mapping[str, Any] | None,
    *,
    section_names: Sequence[str] | None = None,
    voice_mode: bool = False,
) -> str:
    """Optional phrasing tool: the user's own cues plus notes derived from the text.

    The lyrics themselves are not repeated here (the lyrics card above is the place to
    read them). A section with neither cues nor anything derivable is skipped, and a song
    with nothing at all gets a short, honest empty state instead of filler coaching.
    """
    names: list[str] = []
    for source in (section_names or [], list((section_lyrics or {}).keys()), list((lyric_cues or {}).keys())):
        for name in source:
            if str(name) not in names:
                names.append(str(name))

    blocks: list[str] = []
    for name in names:
        text = str((section_lyrics or {}).get(name, "") or "")
        raw_cues = (lyric_cues or {}).get(name) or []
        if isinstance(raw_cues, str):
            raw_cues = [raw_cues]
        cues = [str(c).strip() for c in raw_cues if str(c).strip()]
        notes = phrasing_insights(text)
        if not cues and not notes:
            continue
        lines = [ln for stanza in split_stanzas(text) for ln in stanza]
        meta = ""
        if lines:
            meta = (
                f'<span class="lyr-sec-meta">{len(lines)} line{"s" if len(lines) != 1 else ""} '
                f"&middot; about {sum(count_syllables(ln) for ln in lines)} syllables</span>"
            )
        body = [f'<div class="lyr-sec"><span class="lyr-sec-name">{html.escape(name)}</span>{meta}']
        if cues:
            body.append('<ul class="lyr-cues">' + "".join(f"<li>{html.escape(c)}</li>" for c in cues) + "</ul>")
        for note in notes:
            body.append(f'<p class="lyr-note">{note}</p>')
        body.append("</div>")
        blocks.append("".join(body))

    if not blocks:
        has_text = any(str(t or "").strip() for t in (section_lyrics or {}).values())
        msg = (
            "No phrasing cues yet. Add your own cues under Lyrics &amp; Cues; "
            "breath and repeat notes appear here once a section has more than a single short line."
            if has_text
            else "No lyrics or cues yet. Add lyrics (or your own cues) and phrasing notes will appear here."
        )
        return f'<div class="lyr-guide"><p class="lyr-empty">{msg}</p></div>'

    intro = (
        "Notes worked out from your own lyrics and cues. "
        + ("Plan your breaths before the long lines." if voice_mode else "Use them to plan breaths and phrase endings.")
    )
    return f'<div class="lyr-guide"><p class="lyr-guide-intro">{intro}</p>{"".join(blocks)}</div>'
