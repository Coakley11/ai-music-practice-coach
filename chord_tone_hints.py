"""Chord Tone Hints: the characteristic notes of a chord symbol, spelled, under the chord name.

A hint names what a symbol adds beyond its plain triad -- 6ths, 7ths, 9ths,
11ths, 13ths, suspensions, altered 5ths and altered extensions -- as note names
spelled on their own letters (C7(b9): Bb (b7), Db (b9); Cdim7: Gb (b5), Bbb (bb7)).
Plain major / minor triads get none. At most three per chord, one per chord in a
split bar.

The 3rd is named only where the chord's other notes would suggest the opposite
quality: a dominant 7#9 (the #9 sounds like a minor 3rd, so the major 3rd is
shown) and a minor-major 7th (the major 7th suggests major, so the b3 is shown).
Everywhere else the chord name already says major or minor.

Tones come from :func:`song_coach_harmony.chord_facts` -- the app's one chord
reader -- and only from what the symbol states: no 9th because the backing piano
happens to voice one. Hints are computed from the chord *displayed*, so Practice
Key, Key Cycling and written-key charts need nothing extra.

:func:`apply_chord_tone_hints` adds (or removes) the hint line on any rendered
chord grid -- Live Backing, Key Cycling, Practice -- after each
``<div class='chord-symbol'>``. It is idempotent, and the chord-symbol markup (which
follow-along highlighting reads) is left exactly as it was.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Any, Mapping

# Session preference (persisted like the Strings toggle).
CHORD_TONE_HINTS_KEY = "chord_tone_hints_on"
MAX_HINTS = 3

_LABEL = {
    "2nd": "2", "minor 3rd": "♭3", "3rd": "3", "4th": "4", "♭5": "♭5", "♯5": "♯5", "♭6": "♭6",
    "6th": "6", "°7th": "𝄫7", "7th": "♭7", "major 7th": "7", "♭9": "♭9", "9th": "9", "♯9": "♯9",
    "11th": "11", "♯11": "♯11", "♭13": "♭13", "13th": "13",
}
_DEGREE = {
    "2nd": 2, "minor 3rd": 3, "3rd": 3, "4th": 4, "♭5": 5, "♯5": 5, "♭6": 6, "6th": 6, "°7th": 7,
    "7th": 7, "major 7th": 7, "♭9": 9, "9th": 9, "♯9": 9, "11th": 11, "♯11": 11, "♭13": 13, "13th": 13,
}
_ALTERED = frozenset({"♭5", "♯5", "♭6", "♭9", "♯9", "♯11", "♭13"})
_SUS = frozenset({"2nd", "4th"})
_EXTENSION = frozenset({"9th", "11th", "13th"})
_SEVENTH_OR_SIXTH = frozenset({"7th", "major 7th", "°7th", "6th"})
_UNUSUAL = frozenset({"Cb", "Fb", "E#", "B#"})


@dataclass(frozen=True)
class ToneHint:
    name: str     # spelled for display: "B♭", "B𝄫", "F𝄪"
    label: str    # interval: "♭7", "9", "♯11", "𝄫7"
    sounds: str   # plain name when the spelling is unusual ("A" for B𝄫), else ""
    degree: int

    def text(self) -> str:
        return f"{self.name} ({self.label})"


def pretty_note(name: str) -> str:
    """``Bbb`` -> ``B𝄫``, ``F##`` -> ``F𝄪``, ``Eb`` -> ``E♭``, ``C#`` -> ``C♯``."""
    name = str(name or "")
    if not name:
        return name
    acc = name[1:].replace("bb", "𝄫").replace("##", "𝄪").replace("b", "♭").replace("#", "♯")
    return name[0].upper() + acc


def _sounds(name: str, pc: int) -> str:
    if not name or not (name[1:] in ("bb", "##") or name in _UNUSUAL):
        return ""
    from music_theory import spell_pitch_class

    return pretty_note(spell_pitch_class(int(pc) % 12, mode="flat" if "b" in name[1:] else "sharp"))


def _rank(role: str, roles: set[str]) -> int | None:
    """Selection priority (lower first), or None when the tone is not a hint."""
    if role == "♭5" and "°7th" in roles:
        return 4  # dim7: the 'dim' already says b5; the bb7 tells dim7 from dim -- name it first
    if role in _ALTERED:
        return 0
    if role in _SUS and not ({"3rd", "minor 3rd"} & roles):
        return 1
    if role == "3rd" and "♯9" in roles:
        return 2  # 7#9: the #9 sounds like a minor 3rd -- name the major 3rd
    if role in _EXTENSION:
        return 3
    if role in _SEVENTH_OR_SIXTH:
        return 3 if role == "°7th" else 4
    if role == "minor 3rd" and "major 7th" in roles:
        return 5  # m(maj7): the major 7th suggests major -- name the b3
    return None


def tone_hints(symbol: Any, *, max_tones: int = MAX_HINTS) -> tuple[ToneHint, ...]:
    """The 1-3 characteristic tones of ``symbol``, lowest interval first (``()`` for triads / N.C.)."""
    from song_coach_harmony import chord_facts

    text = str(symbol or "").strip().replace("♭", "b").replace("♯", "#")
    if not text or text in ("%", "…") or text.upper().startswith("N.C"):
        return ()
    try:
        facts = chord_facts(text)
    except Exception:
        return ()
    if facts is None:
        return ()
    tones = [t for t in facts.tones if t.role in _LABEL and t.name]
    roles = {t.role for t in tones}
    ranked = []
    for t in tones:
        r = _rank(t.role, roles)
        if r is not None:
            # Within a rank the higher extension says more (13 before 11 before 9).
            ranked.append((r, -_DEGREE[t.role], t))
    ranked.sort(key=lambda x: (x[0], x[1]))
    chosen = [t for _r, _d, t in ranked[: max(0, int(max_tones))]]
    chosen.sort(key=lambda t: (_DEGREE[t.role], _LABEL[t.role]))
    return tuple(
        ToneHint(pretty_note(t.name), _LABEL[t.role], _sounds(t.name, t.pc), _DEGREE[t.role]) for t in chosen
    )


def hints_enabled(session: Mapping[str, Any] | None) -> bool:
    try:
        return bool((session or {}).get(CHORD_TONE_HINTS_KEY))
    except Exception:
        return False


# ----------------------------------------------------------------- HTML

# One line, never wrapping: a long line ends in "…" with the full text on hover, so a
# block never grows by more than this line. Class-based (one <style> block per grid)
# so a 200-bar sheet does not repeat the rule in every cell.
HINTS_STYLE = (
    ".chord-tone-hints{font-size:0.68rem;line-height:1.15;min-height:1.15em;margin-top:2px;"
    "color:#64748b;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-weight:500;"
    "letter-spacing:0;}"
    ".chord-tone-hints.split{display:flex;gap:0.2rem;}"
    ".chord-tone-hints.split>span{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}"
)
# Lead sheets carry the hint lines always, hidden until the page says otherwise: the
# switch then flips one attribute on the sheet's document (see player_switch_html)
# instead of re-rendering the sheet -- re-rendering re-creates the sheet's audio player,
# which stopped the music. Hidden lines take no space: off looks exactly as before.
SHEET_ATTR = "data-cth"
_SHEET_STYLE = HINTS_STYLE + f"html:not([{SHEET_ATTR}='1']) .chord-tone-hints{{display:none !important;}}"
# A sheet loaded later (new take, Key Cycling swap) picks the current state up at once.
_SHEET_INIT = (
    "<script>try{if(window.parent&&window.parent.__cthOn)"
    f"document.documentElement.setAttribute('{SHEET_ATTR}','1');}}catch(e){{}}</script>"
)

_HINTS_RE = re.compile(r"<div class='chord-tone-hints[^']*'[^>]*>.*?</div>", re.S)
_STYLE_RE = re.compile(r"<style data-cth='[^']*'>.*?</style>(?:<script>try\{if\(window\.parent&&window\.parent\.__cthOn\).*?</script>)?", re.S)
_SYMBOL_RE = re.compile(r"(<div class='chord-symbol'>)(.*?)(</div>)", re.S)
_SUB_RE = re.compile(r"<span class='sub-chord[^']*'[^>]*?style='([^']*)'>(.*?)</span>", re.S)
_SEP_RE = re.compile(r"<span class='sub-sep'>(.*?)</span>", re.S)
_TAG_RE = re.compile(r"<[^>]+>")


def _hint_span(h: ToneHint) -> str:
    tip = f" title='{html.escape(h.text() + ' — sounds ' + h.sounds, quote=True)}'" if h.sounds else ""
    return f"<span class='cth'{tip}>{html.escape(h.text())}</span>"


def hint_row_html(symbol_inner_html: str) -> str:
    """The hint line for one ``chord-symbol`` div's inner HTML (an empty line keeps the row height)."""
    subs = _SUB_RE.findall(symbol_inner_html)
    if subs:
        parts = []
        seps = _SEP_RE.findall(symbol_inner_html)
        for i, (style, inner) in enumerate(subs):
            if i and i - 1 < len(seps):
                parts.append(f"<span aria-hidden='true' style='visibility:hidden'>{seps[i - 1]}</span>")
            chord = html.unescape(_TAG_RE.sub("", inner)).strip()
            one = tone_hints(chord, max_tones=1)
            # The same proportional width as the chord above, so each hint sits under its chord.
            parts.append(f"<span style='{style}'>{_hint_span(one[0]) if one else '&nbsp;'}</span>")
        return f"<div class='chord-tone-hints split'>{''.join(parts)}</div>"
    chord = html.unescape(_TAG_RE.sub("", symbol_inner_html)).strip()
    hints = tone_hints(chord)
    title = f" title='{html.escape(', '.join(h.text() for h in hints), quote=True)}'" if hints else ""
    body = ", ".join(_hint_span(h) for h in hints) or "&nbsp;"
    return f"<div class='chord-tone-hints'{title}>{body}</div>"


def strip_chord_tone_hints(chart_html: str) -> str:
    return _STYLE_RE.sub("", _HINTS_RE.sub("", str(chart_html or "")))


def apply_chord_tone_hints(chart_html: str, enabled: bool) -> str:
    """``chart_html`` with a visible hint line after every chord symbol (``enabled``) or with none."""
    text = strip_chord_tone_hints(chart_html)
    if not enabled or "chord-symbol" not in text:
        return text
    rows = _SYMBOL_RE.sub(lambda m: m.group(0) + hint_row_html(m.group(2)), text)
    return f"<style data-cth='page'>{HINTS_STYLE}</style>" + rows


def sheet_with_chord_tone_hints(chart_html: str, available: bool = True) -> str:
    """A lead sheet carrying hint lines that the page shows or hides (``available`` False: none)."""
    text = strip_chord_tone_hints(chart_html)
    if not available or "chord-symbol" not in text:
        return text
    rows = _SYMBOL_RE.sub(lambda m: m.group(0) + hint_row_html(m.group(2)), text)
    return f"<style data-cth='sheet'>{_SHEET_STYLE}</style>{_SHEET_INIT}" + rows


# The switch's channel: a zero-height component (chord_tone_hints_component/index.html)
# built like the card transport. It carries the switch's choice to the app and keeps the
# open lead sheets on the saved choice.
CTH_CHANNEL_KEY = "chord_tone_hints_channel"
CTH_CONSUMED_KEY = "_chord_tone_hints_channel_consumed"
_channel = None


def render_switch_channel(enabled: bool) -> None:
    """Mount the channel (Backing, lead sheet open). ``enabled`` is the saved choice."""
    global _channel
    if _channel is None:
        from pathlib import Path

        import streamlit.components.v1 as components

        _channel = components.declare_component(
            "chord_tone_hints_channel", path=str(Path(__file__).resolve().parent / "chord_tone_hints_component")
        )
    _channel(enabled=bool(enabled), key=CTH_CHANNEL_KEY, default=None)


def take_switch_choice(session: Any) -> bool | None:
    """Apply the switch's newest choice (read at the start of the run it caused), once.

    Returns the new value when it changed the saved preference (the caller saves the
    workspace then), else ``None``.
    """
    try:
        raw = session.get(CTH_CHANNEL_KEY)
    except Exception:
        return None
    if not isinstance(raw, dict) or not raw.get("nonce"):
        return None
    token = f"{raw.get('session') or ''}:{raw.get('nonce')}"
    if session.get(CTH_CONSUMED_KEY) == token:
        return None
    session[CTH_CONSUMED_KEY] = token
    on = bool(raw.get("on"))
    if bool(session.get(CHORD_TONE_HINTS_KEY)) == on:
        return None
    session[CHORD_TONE_HINTS_KEY] = on
    return on


# ----------------------------------------------------------------- the player switch

_SWITCH_STYLE = (
    ".cth-switch{display:inline-flex;align-items:center;gap:8px;font:600 13px/1.2 system-ui,-apple-system,"
    "'Segoe UI',sans-serif;color:#334155;background:#fff;border:1px solid #cbd5e1;border-radius:999px;"
    "padding:5px 11px 5px 6px;cursor:pointer;white-space:nowrap;flex:0 0 auto;}"
    ".cth-switch:hover{border-color:#94a3b8;}"
    ".cth-switch:focus-visible{outline:2px solid #2563eb;outline-offset:2px;}"
    ".cth-track{width:30px;height:18px;border-radius:999px;background:#cbd5e1;position:relative;"
    "transition:background .15s;flex:0 0 auto;}"
    ".cth-knob{position:absolute;top:2px;left:2px;width:14px;height:14px;border-radius:50%;background:#fff;"
    "box-shadow:0 1px 2px rgba(0,0,0,.3);transition:left .15s;}"
    f"html[{SHEET_ATTR}='1'] .cth-track{{background:#16a34a;}}"
    f"html[{SHEET_ATTR}='1'] .cth-knob{{left:14px;}}"
    "@media (prefers-reduced-motion: reduce){.cth-track,.cth-knob{transition:none;}}"
)

_SWITCH_SCRIPT = (
    "<script>(function(){const P=window.parent;const root=document.documentElement;"
    "function sync(){const on=root.getAttribute('" + SHEET_ATTR + "')==='1';"
    "document.querySelectorAll('.cth-switch').forEach(function(b){b.setAttribute('aria-checked',on?'true':'false');});}"
    "try{if(P&&P.__cthOn)root.setAttribute('" + SHEET_ATTR + "','1');}catch(e){}"
    "sync();"
    "document.querySelectorAll('.cth-switch').forEach(function(b){b.addEventListener('click',function(){"
    "const on=root.getAttribute('" + SHEET_ATTR + "')!=='1';"
    "if(on)root.setAttribute('" + SHEET_ATTR + "','1');else root.removeAttribute('" + SHEET_ATTR + "');"
    "try{P.__cthOn=on;P.__cthPending=on;}catch(e){}"
    "try{if(typeof P.__cthSave==='function')P.__cthSave(on);}catch(e){}"
    "sync();});});"
    "try{new MutationObserver(sync).observe(root,{attributes:true,attributeFilter:['" + SHEET_ATTR + "']});}catch(e){}"
    "})();</script>"
)


def player_switch_html() -> str:
    """The "Chord Tone Hints" switch for the Live Follow-Along Player header.

    It shows or hides the hint lines in this player's sheet at once and hands the choice to
    the channel (:func:`render_switch_channel`), which saves it in one quiet re-run -- the
    player itself is not re-rendered. Its look follows the sheet's ``data-cth`` attribute,
    so it always matches what is shown.
    """
    return (
        f"<style>{_SWITCH_STYLE}</style>"
        "<button type='button' class='cth-switch' role='switch' aria-checked='false' "
        "title='Show the notes that give each chord its colour (7ths, 9ths, altered tones) under the chord names'>"
        "<span class='cth-track' aria-hidden='true'><span class='cth-knob'></span></span>"
        "<span class='cth-label'>Chord Tone Hints</span></button>"
        + _SWITCH_SCRIPT
    )
