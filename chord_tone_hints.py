"""Chord Tone Hints: the notes of a chord symbol, spelled, under the chord name, by level.

Spelling comes from the chord's own structure, never the key signature (A7: C♯ E G;
C♯7: E♯ G♯ B; Aaug: C♯ E♯).

- **Beginner:** every non-root chord tone the symbol states, lowest first, names only
  ("C♯ E G"). No invented 7th, and never hidden: the line wraps instead.
- **Intermediate:** up to three tones with degrees, guide tones first: the 3rd (or the
  suspension), the 7th or 6th, then alterations, then the highest extension (A7: C♯ (3),
  G (♭7); A: C♯ (3); Aaug: C♯ (3), E♯ (♯5)).
- **Advanced:** up to four tones with degrees. Alterations, then extensions, then the 7th
  or 6th (A13: G (♭7), B (9), F♯ (13)). The 3rd only where the chord's other notes suggest
  the opposite quality: a 7♯9 and a minor-major 7th. Plain triads get none. Where the 7th
  steps down to the next chord's 3rd (the guide-tone line of ii–V–I), the 7th's hint says
  where it goes: Dm7 → G7 shows "C (♭7)↘B" (see :func:`voice_leading`), on the bar right
  before the change.

A suspension takes the 3rd's place and is named at every level, because it defines the
chord. A split bar has room for one tone per chord at Intermediate and Advanced (its most
defining one); Beginner keeps the full list. ``7alt`` names the notes the symbol implies
plus an "alt" marker, since which altered tensions to play is the player's choice.

Tones come from :func:`song_coach_harmony.chord_facts` -- the app's one chord reader --
and only from what the symbol states. Three of the reader's habits are corrected here,
not in the reader: an altered 5th replaces the natural 5th, a "4th" beside a 3rd is an
11th, and ``7alt`` does not list every possible tension as if the symbol required it.

Hints are computed from the chord *displayed*, so Practice Key, Key Cycling and
written-key charts need nothing extra. A capo Shape chart is the exception: its cells
show shapes, and the hints name the sounding chord (``sounding_steps``).

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
LEVELS = ("Beginner", "Intermediate", "Advanced")
DEFAULT_LEVEL = "Intermediate"
_MAX_TONES = {"Intermediate": 3, "Advanced": 4}
ALT_MARKER = "alt"
_ALT_TIP = "Altered dominant: the 5th and 9th are altered, and the player chooses how"

_LABEL = {
    "2nd": "2", "minor 3rd": "♭3", "3rd": "3", "4th": "4", "5th": "5", "♭5": "♭5", "♯5": "♯5", "♭6": "♭6",
    "6th": "6", "°7th": "𝄫7", "7th": "♭7", "major 7th": "7", "♭9": "♭9", "9th": "9", "♯9": "♯9",
    "11th": "11", "♯11": "♯11", "♭13": "♭13", "13th": "13",
}
_DEGREE = {
    "2nd": 2, "minor 3rd": 3, "3rd": 3, "4th": 4, "5th": 5, "♭5": 5, "♯5": 5, "♭6": 6, "6th": 6, "°7th": 7,
    "7th": 7, "major 7th": 7, "♭9": 9, "9th": 9, "♯9": 9, "11th": 11, "♯11": 11, "♭13": 13, "13th": 13,
}
_ALTERED = frozenset({"♭5", "♯5", "♭6", "♭9", "♯9", "♯11", "♭13"})
_SUS = frozenset({"2nd", "4th"})
_EXTENSION = frozenset({"9th", "11th", "13th"})
_SEVENTH_OR_SIXTH = frozenset({"7th", "major 7th", "°7th", "6th"})
_THIRDS = frozenset({"3rd", "minor 3rd"})
_UNUSUAL = frozenset({"Cb", "Fb", "E#", "B#"})
_ALT_RE = re.compile(r"alt", re.I)
_DIM_MAJ7_RE = re.compile(r"(?:dim|°|o)\(?(?:maj|M|Δ)7")


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


def normalize_level(level: Any) -> str:
    text = str(level or "").strip().title()
    return text if text in LEVELS else DEFAULT_LEVEL


def hints_level(session: Mapping[str, Any] | None) -> str:
    """The proficiency level the hints follow (the sidebar's Level)."""
    try:
        return normalize_level((session or {}).get("level"))
    except Exception:
        return DEFAULT_LEVEL


@dataclass(frozen=True)
class _Tone:
    role: str
    name: str
    pc: int


def _clean_text(symbol: Any) -> str:
    return str(symbol or "").strip().replace("♭", "b").replace("♯", "#")


def _facts(symbol: Any):
    from song_coach_harmony import chord_facts

    text = _clean_text(symbol)
    if not text or text in ("%", "…") or text.upper().startswith("N.C"):
        return None
    try:
        return chord_facts(text)
    except Exception:
        return None


def is_altered_dominant(symbol: Any) -> bool:
    """``A7alt``: the symbol leaves the altered tensions to the player."""
    facts = _facts(symbol)
    return bool(facts and _ALT_RE.search(facts.symbol))


def _chord_tones(facts) -> list[_Tone]:
    """The chord's non-root tones, with the reader's habits corrected for hints."""
    from song_coach_harmony import spell_from_root

    tones = [t for t in facts.tones if t.role in _LABEL and t.name]
    roles = {t.role for t in tones}
    alt = bool(_ALT_RE.search(facts.symbol))
    out: list[_Tone] = []
    for t in tones:
        role, name, pc = t.role, t.name, t.pc
        if role == "5th" and (alt or roles & {"♭5", "♯5"}):
            continue  # an altered 5th replaces the natural one
        if alt and role in ("♭9", "♯9", "♭13"):
            continue  # possibilities, not what the symbol requires
        if role == "4th" and roles & _THIRDS:
            role = "11th"  # beside a 3rd it is an extension, not a suspension
        if role == "°7th" and _DIM_MAJ7_RE.search(facts.symbol):
            role, name, pc = "major 7th", spell_from_root(facts.root, 11, 6), (facts.root_pc + 11) % 12
        out.append(_Tone(role, name, pc))
    return out


def _high_first(tones: list[_Tone]) -> list[_Tone]:
    return sorted(tones, key=lambda t: (-_DEGREE[t.role], _LABEL[t.role]))


# Which alteration says most about the chord (user, 2026-11-10): altered 9ths, then altered
# 5ths, then #11 / b13. Decides which survive a level's limit (A7(b9#11) at Intermediate keeps
# the b9); the line itself is always shown lowest first.
_ALTERATION_RANK = {"♭9": 0, "♯9": 1, "♭5": 2, "♯5": 3, "♯11": 4, "♭13": 5, "♭6": 5}


def _characteristic_first(tones: list[_Tone]) -> list[_Tone]:
    return sorted(tones, key=lambda t: (_ALTERATION_RANK.get(t.role, 9), -_DEGREE[t.role]))


def _defining_rank(role: str, roles: set[str]) -> int | None:
    """The one tone a split bar has room for (lower first), or None when the tone is not a hint."""
    if role == "♭5" and "°7th" in roles:
        return 4  # dim7: the 'dim' already says b5; the bb7 tells dim7 from dim -- name it first
    if role in _ALTERED:
        return 0
    if role in _SUS and not (_THIRDS & roles):
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


def _most_defining(tones: list[_Tone]) -> list[_Tone]:
    roles = {t.role for t in tones}
    ranked = [(r, -_DEGREE[t.role], _LABEL[t.role], t) for t in tones if (r := _defining_rank(t.role, roles)) is not None]
    ranked.sort(key=lambda x: x[:3])
    return [ranked[0][3]] if ranked else []


def _level_choice(tones: list[_Tone], level: str) -> list[_Tone]:
    """Intermediate's and Advanced's tones, in the approved order, up to the level's limit."""
    roles = {t.role for t in tones}
    of = lambda names: [t for t in tones if t.role in names]  # noqa: E731
    altered = _characteristic_first(of(_ALTERED))
    sus = of(_SUS) if not (_THIRDS & roles) else []
    seventh = of(_SEVENTH_OR_SIXTH)
    extensions = _high_first(of(_EXTENSION))
    thirds = of(_THIRDS)
    sharp_nine = "♯9" in roles and "3rd" in roles
    settles_quality = sharp_nine or ("minor 3rd" in roles and "major 7th" in roles)
    if level == "Intermediate":
        # Guide tones first (user, 2026-11-10): the 3rd (or the suspension in its place) and the 7th or
        # 6th are how a player finds the harmony, so they come before any alteration. A triad names its
        # 3rd; then alterations, highest first, then the highest extension.
        order = thirds + sus + seventh + altered + extensions[:1]
    else:
        # 7#9: the 3rd stays beside the #9 that hides it, however many other alterations there are.
        order = of({"♯9"}) + of({"3rd"}) + altered if sharp_nine else list(altered)
        order += sus + extensions + seventh + (thirds if settles_quality else [])
    chosen: list[_Tone] = []
    for t in order:
        if t not in chosen:
            chosen.append(t)
    return chosen[: _MAX_TONES[level]]


def tone_hints(symbol: Any, *, level: str = DEFAULT_LEVEL, single: bool = False) -> tuple[ToneHint, ...]:
    """The tones of ``symbol`` for ``level``, lowest first (``()`` when it has none to name).

    ``single``: a split bar's cell. Beginner keeps its full list; the other levels name the
    most defining tone (a 7alt has only its marker there, see :func:`is_altered_dominant`).
    """
    facts = _facts(symbol)
    if facts is None:
        return ()
    level = normalize_level(level)
    tones = _chord_tones(facts)
    if level == "Beginner":
        chosen = tones
    elif single:
        chosen = [] if _ALT_RE.search(facts.symbol) else _most_defining(tones)
    else:
        chosen = _level_choice(tones, level)
    chosen = sorted(chosen, key=lambda t: (_DEGREE[t.role], _LABEL[t.role]))
    return tuple(ToneHint(pretty_note(t.name), _LABEL[t.role], _sounds(t.name, t.pc), _DEGREE[t.role]) for t in chosen)


@dataclass(frozen=True)
class VoiceLeading:
    """The 7th of one chord stepping down to the 3rd of the next (ii–V–I's guide-tone line)."""
    from_name: str  # the 7th, spelled by its own chord: "C"
    to_name: str    # the next chord's 3rd, spelled by that chord: "B"
    to_label: str   # its degree in the next chord: "3" or "♭3"
    next_symbol: str

    def tip(self, label: str) -> str:
        third = "minor 3rd" if self.to_label == "♭3" else "3rd"
        return f"Voice leading: {self.from_name} ({label}) moves down to {self.to_name}, the {third} of {self.next_symbol}"


def _same_chord(a: Any, b: Any) -> bool:
    return _clean_text(a).replace(" ", "") == _clean_text(b).replace(" ", "")


def voice_leading(symbol: Any, next_symbol: Any) -> VoiceLeading | None:
    """Where the 7th of ``symbol`` goes when ``next_symbol`` follows: down a half or whole step to its 3rd.

    That is the strongest line through a progression (Dm7 → G7: C → B; G7 → Cmaj7: F → E;
    A7 → D: G → F♯), so it is the one an Advanced hint names. None when either is not a chord,
    when the chord has no 7th, when the next chord is the same one, or when the 7th does not step
    down to the next 3rd (a common tone or a leap is not named).
    """
    if not next_symbol or _same_chord(symbol, next_symbol):
        return None
    here, there = _facts(symbol), _facts(next_symbol)
    if here is None or there is None:
        return None
    seventh = next((t for t in _chord_tones(here) if t.role in ("7th", "major 7th", "°7th")), None)
    third = next((t for t in _chord_tones(there) if t.role in _THIRDS), None)
    if seventh is None or third is None or (seventh.pc - third.pc) % 12 not in (1, 2):
        return None
    return VoiceLeading(pretty_note(seventh.name), pretty_note(third.name), _LABEL[third.role],
                        str(next_symbol).strip())


def hints_enabled(session: Mapping[str, Any] | None) -> bool:
    try:
        return bool((session or {}).get(CHORD_TONE_HINTS_KEY))
    except Exception:
        return False


# ----------------------------------------------------------------- HTML

# Class-based (one <style> block per grid) so a 200-bar sheet does not repeat the rule in
# every cell. A line wraps between tones, never inside one, so a narrow phone cell still
# shows every tone. A split bar's single tones have only part of a cell: they end in "…"
# with the full text on hover, except Beginner's full lists ("full"), which wrap too.
HINTS_STYLE = (
    ".chord-tone-hints{font-size:0.68rem;line-height:1.15;min-height:1.15em;margin-top:2px;"
    "color:#64748b;white-space:normal;font-weight:500;letter-spacing:0;}"
    ".chord-tone-hints .cth{white-space:nowrap;}"
    ".chord-tone-hints.split{display:flex;gap:0.2rem;}"
    ".chord-tone-hints.split>span{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}"
    ".chord-tone-hints.split.full>span{overflow:visible;white-space:normal;}"
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


_SEVENTH_LABELS = frozenset({"♭7", "7", "𝄫7"})
VL_MARK = "↘"


def _shown(h: ToneHint, level: str, vl: VoiceLeading | None = None) -> str:
    if level == "Beginner":
        return h.name
    if vl is not None and h.label in _SEVENTH_LABELS:
        # "↘" (moves down to), not "→": the chart already draws "→" between a split bar's chords.
        return f"{h.text()}{VL_MARK}{vl.to_name}"
    return h.text()


def _hint_span(h: ToneHint, level: str, vl: VoiceLeading | None = None) -> str:
    shown = _shown(h, level, vl)
    tips = []
    if h.sounds:
        tips.append(f"{shown} — sounds {h.sounds}")
    leads = vl is not None and level != "Beginner" and h.label in _SEVENTH_LABELS
    if leads:
        tips.append(vl.tip(h.label))
    tip = f" title='{html.escape(' · '.join(tips), quote=True)}'" if tips else ""
    cls = "cth cth-vl" if leads else "cth"
    return f"<span class='{cls}'{tip}>{html.escape(shown)}</span>"


def _sounding_chord(chord: str, steps: int, reference_key: str | None) -> str:
    """The chord that sounds when the cell shows a capo shape ``steps`` semitones below it."""
    if not steps or _facts(chord) is None:
        return chord
    try:
        from music_theory import transpose_chord

        return str(transpose_chord(chord, int(steps), reference_key=reference_key) or chord)
    except Exception:
        return chord


def _line_parts(chord: str, level: str, single: bool, next_chord: str | None = None) -> tuple[list[str], str]:
    """(the line's spans, its plain text) for one chord; ``next_chord`` follows it (Advanced voice leading)."""
    hints = tone_hints(chord, level=level, single=single)
    # A split bar's cell has room for one tone: no voice-leading arrow there.
    vl = voice_leading(chord, next_chord) if level == "Advanced" and not single and next_chord else None
    spans = [_hint_span(h, level, vl) for h in hints]
    words = [_shown(h, level, vl) for h in hints]
    if is_altered_dominant(chord):
        spans.append(f"<span class='cth cth-alt' title='{html.escape(_ALT_TIP, quote=True)}'>{ALT_MARKER}</span>")
        words.append(ALT_MARKER)
    return spans, (" " if level == "Beginner" else ", ").join(words)


def hint_row_html(
    symbol_inner_html: str,
    *,
    level: str = DEFAULT_LEVEL,
    sounding_steps: int = 0,
    reference_key: str | None = None,
    next_chord: str | None = None,
) -> str:
    """The hint line for one ``chord-symbol`` div's inner HTML (an empty line keeps the row height).

    ``next_chord``: the next different chord of the chart, as it sounds (already moved by
    ``sounding_steps``); Advanced names where this chord's 7th leads into it.
    """
    level = normalize_level(level)
    sep = " " if level == "Beginner" else ", "
    subs = _SUB_RE.findall(symbol_inner_html)
    if subs:
        parts = []
        seps = _SEP_RE.findall(symbol_inner_html)
        for i, (style, inner) in enumerate(subs):
            if i and i - 1 < len(seps):
                parts.append(f"<span aria-hidden='true' style='visibility:hidden'>{seps[i - 1]}</span>")
            chord = _sounding_chord(html.unescape(_TAG_RE.sub("", inner)).strip(), sounding_steps, reference_key)
            spans, _text = _line_parts(chord, level, True)
            # The same proportional width as the chord above, so each hint sits under its chord.
            parts.append(f"<span style='{style}'>{sep.join(spans) or '&nbsp;'}</span>")
        cls = "chord-tone-hints split full" if level == "Beginner" else "chord-tone-hints split"
        return f"<div class='{cls}'>{''.join(parts)}</div>"
    chord = _sounding_chord(html.unescape(_TAG_RE.sub("", symbol_inner_html)).strip(), sounding_steps, reference_key)
    spans, text = _line_parts(chord, level, False, next_chord)
    title = f" title='{html.escape(text, quote=True)}'" if text else ""
    return f"<div class='chord-tone-hints'{title}>{sep.join(spans) or '&nbsp;'}</div>"


def _cell_chords(symbol_inner_html: str) -> list[str]:
    """The chords one ``chord-symbol`` cell shows, in order (a split bar has several)."""
    subs = _SUB_RE.findall(symbol_inner_html)
    inners = [inner for _style, inner in subs] if subs else [symbol_inner_html]
    return [html.unescape(_TAG_RE.sub("", inner)).strip() for inner in inners]


def _next_chords(cells: list[list[str]]) -> list[str | None]:
    """For each cell, the chord its last chord moves into, or None while the chord is held.

    ``%`` and N.C. cells are skipped (a "%" bar repeats the written chord before it, so that
    written chord is the bar before the change). A chord written out again in the next bar is
    held, so only the bar right before the change leads into it.
    """
    flat = [(i, c) for i, chords in enumerate(cells) for c in chords if _facts(c) is not None]
    out: list[str | None] = [None] * len(cells)
    for p, (i, c) in enumerate(flat):
        nxt = flat[p + 1][1] if p + 1 < len(flat) else None
        out[i] = None if nxt is None or _same_chord(nxt, c) else nxt  # the cell's last chord decides
    return out


def _with_hint_lines(text: str, level: str, *, sounding_steps: int = 0, reference_key: str | None = None) -> str:
    """``text`` with a hint line after every chord symbol; Advanced lines know the chord that follows."""
    matches = list(_SYMBOL_RE.finditer(text))
    nexts: list[str | None] = [None] * len(matches)
    if normalize_level(level) == "Advanced" and matches:
        cells = [[_sounding_chord(c, sounding_steps, reference_key) for c in _cell_chords(m.group(2))] for m in matches]
        nexts = _next_chords(cells)
    out, pos = [], 0
    for m, nxt in zip(matches, nexts):
        out.append(text[pos:m.end()])
        out.append(hint_row_html(m.group(2), level=level, sounding_steps=sounding_steps,
                                 reference_key=reference_key, next_chord=nxt))
        pos = m.end()
    out.append(text[pos:])
    return "".join(out)


def strip_chord_tone_hints(chart_html: str) -> str:
    return _STYLE_RE.sub("", _HINTS_RE.sub("", str(chart_html or "")))


def apply_chord_tone_hints(
    chart_html: str,
    enabled: bool,
    *,
    level: str = DEFAULT_LEVEL,
    sounding_steps: int = 0,
    reference_key: str | None = None,
) -> str:
    """``chart_html`` with a visible hint line after every chord symbol (``enabled``) or with none.

    ``sounding_steps``: the chart's cells show capo shapes that many semitones below what
    sounds, and the hints name the sounding chord (spelled for ``reference_key``).
    """
    text = strip_chord_tone_hints(chart_html)
    if not enabled or "chord-symbol" not in text:
        return text
    rows = _with_hint_lines(text, level, sounding_steps=sounding_steps, reference_key=reference_key)
    return f"<style data-cth='page'>{HINTS_STYLE}</style>" + rows


def sheet_with_chord_tone_hints(chart_html: str, available: bool = True, *, level: str = DEFAULT_LEVEL) -> str:
    """A lead sheet carrying hint lines that the page shows or hides (``available`` False: none).

    Lines are rebuilt from the chords the sheet displays, so a stored sheet can be brought
    up to the current level by passing it through here again.
    """
    text = strip_chord_tone_hints(chart_html)
    if not available or "chord-symbol" not in text:
        return text
    rows = _with_hint_lines(text, level)
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
        "title='Show chord notes under the chord names, matched to your level'>"
        "<span class='cth-track' aria-hidden='true'><span class='cth-knob'></span></span>"
        "<span class='cth-label'>Chord Tone Hints</span></button>"
        + _SWITCH_SCRIPT
    )
