"""Which grooves Multitrack offers, what "Auto" actually resolved to, and where 6/8 is a fallback.

Issue 77C. The Multitrack page offered seven options from a list written into the page:

    Auto, Pop groove, Rock groove, Jazz swing, Bossa nova, Funk groove, Ballad

while the backing engine genuinely plays eleven. **Blues groove** was missing - measured, the engine
has its own blues bass, comping, drum and swing branches, and ``infer_groove_style`` already
resolves a blues song to it - so a musician playing a blues heard a real blues groove under Auto and
could neither see that nor ask for it. The Jewish styles were missing the same way. The canonical
list already exists as ``songs.playback_defaults.GROOVE_STYLE_CHOICES``; this module hands it to the
page and answers the two honesty questions that come with it.

**What did Auto choose?** "Auto" alone tells the musician nothing. The resolution is shown beside it
("Auto - Blues groove") *without changing the stored value*: the session still holds "Auto", so the
choice stays automatic and follows the song, and the musician can still pick Blues groove outright.
When the song carries no evidence of a style, the engine's final fallback is Pop groove - that is a
default, not an inference, and it is described as one rather than announced as a genre.

**6/8.** Measured per style: in 4/4 every option in the shared list produces its own rhythmic
pattern, but in 6/8 several fall back to the Pop pattern (Rock, Jazz swing, Bossa nova, Funk, Blues
groove, Klezmer groove and Jewish ballad did at the time of writing; Ballad, Jewish groove and
Jewish hora have their own). Rather than hardcode that, :func:`meter_fallback_note` asks the engine
itself and says so only when it is true - so the interface cannot promise a distinctive groove the
engine is not going to play, and the note disappears by itself if 6/8 support is added later.

No audio is rendered here and no engine behaviour is changed: this module reads the vocabulary,
reads the pattern tables, and writes English.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

#: Fallback vocabulary if the shared constant cannot be imported. Kept identical to
#: ``songs.playback_defaults.GROOVE_STYLE_CHOICES`` so the page degrades to the same list.
_FALLBACK_CHOICES: tuple[str, ...] = (
    "Auto",
    "Pop groove",
    "Rock groove",
    "Jazz swing",
    "Bossa nova",
    "Funk groove",
    "Blues groove",
    "Ballad",
    "Jewish groove",
    "Jewish hora",
    "Klezmer groove",
    "Jewish ballad",
)

AUTO = "Auto"


def groove_options() -> list[str]:
    """Every groove the musician may choose, from the application's shared definition."""
    try:
        from songs.playback_defaults import GROOVE_STYLE_CHOICES

        choices = [str(c) for c in GROOVE_STYLE_CHOICES if str(c).strip()]
        if choices:
            return choices
    except ImportError:
        pass
    return list(_FALLBACK_CHOICES)


def normalize_selection(value: Any, options: Sequence[str] | None = None) -> str:
    """Keep a previously saved selection working.

    Every option the page used to offer is in the shared list, so an existing choice survives
    unchanged. A value from somewhere else entirely - or from a future list - falls back to Auto
    rather than crashing the selector, which is what an out-of-range value does to ``st.selectbox``.
    """
    choices = list(options) if options is not None else groove_options()
    text = str(value or "").strip()
    if text in choices:
        return text
    for choice in choices:                      # tolerate case drift in older saved values
        if choice.lower() == text.lower():
            return choice
    return AUTO


# --------------------------------------------------------------------------------------------
# what Auto resolved to
# --------------------------------------------------------------------------------------------
def _style_evidence(song_data: Mapping[str, Any] | None) -> str:
    """Why a style could be inferred for this song, or "" when nothing says.

    Mirrors what ``backing_audio.infer_groove_style`` looks at, without repeating its decisions:
    an explicit default groove, a genre, or a style word in the title/artist/composer. Pop groove
    is that function's *last resort*, so "no evidence" is the difference between an inference and a
    default - and the musician is told which they are getting.
    """
    data = song_data or {}
    ext = data.get("extensions") if isinstance(data.get("extensions"), Mapping) else {}
    if str(ext.get("default_groove") or "").strip():
        return "the song's own setting"
    if str(data.get("genre") or "").strip():
        return "the song's genre"
    text = " ".join(
        str(data.get(k) or "") for k in ("title", "artist", "composer")
    ).lower()
    for word in ("ballad", "bossa", "samba", "jobim", "blues", "swing", "funk", "rock",
                 "klezmer", "hora"):
        if word in text:
            return "the song's title"
    return ""


def resolved_auto_style(song_data: Mapping[str, Any] | None) -> tuple[str, str]:
    """``(style, evidence)`` for Auto: what the engine will play, and why it chose it.

    ``evidence`` is "" when nothing about the song implies a style, in which case ``style`` is the
    engine's default rather than a judgement about the music.
    """
    try:
        from backing_audio import infer_groove_style

        style = str(infer_groove_style(dict(song_data or {}), AUTO) or "").strip()
    except Exception:
        return "", ""
    return style, _style_evidence(song_data)


def auto_label(song_data: Mapping[str, Any] | None) -> str:
    """What the Auto option says on screen.

    "Auto - Blues groove" when the song genuinely implies one; neutral wording when it does not, so
    a song with no stated genre is never given one it has not earned.
    """
    style, evidence = resolved_auto_style(song_data)
    if not style:
        return AUTO
    if not evidence:
        return f"{AUTO} — standard groove unless the song says otherwise"
    return f"{AUTO} — {style}"


def groove_label(value: Any, song_data: Mapping[str, Any] | None = None) -> str:
    """Display text for one option. Only Auto differs from its stored value."""
    text = str(value or "")
    return auto_label(song_data) if text == AUTO else text


# --------------------------------------------------------------------------------------------
# where 6/8 only has a fallback
# --------------------------------------------------------------------------------------------
def style_has_own_pattern(style: str, time_signature: str = "4/4") -> bool | None:
    """Does the engine play this style differently from Pop in this meter?

    ``None`` when it cannot be determined (the engine's pattern table is not importable), so a
    caller can stay silent rather than guess. Asked of the engine instead of hardcoded, so this
    stops claiming a limitation the moment one is fixed.
    """
    name = str(style or "").strip()
    if not name or name == AUTO:
        return None
    try:
        from backing_audio import _style_patterns
    except Exception:
        return None
    try:
        mine = _style_patterns(name, time_signature=time_signature)
        pop = _style_patterns("Pop groove", time_signature=time_signature)
    except Exception:
        return None
    if name == "Pop groove":
        return True
    return mine != pop


def meter_fallback_note(style: str, time_signature: str = "4/4") -> str:
    """One honest sentence when the engine has no distinct pattern for this style in this meter.

    Empty when the style is played properly, when it cannot be checked, or for Auto. Measured
    examples in 6/8: Rock, Jazz swing, Bossa nova, Funk, Blues groove, Klezmer groove and Jewish
    ballad fall back to the Pop pattern, while Ballad, Jewish groove and Jewish hora do not.
    """
    own = style_has_own_pattern(style, time_signature)
    if own is not False:
        return ""
    return (
        f"In {time_signature} the backing engine has no distinct **{style}** rhythm and plays its "
        "standard pattern instead. The chords, tempo and feel settings still apply; the groove's "
        "own drum and bass figures do not."
    )


__all__ = [
    "AUTO",
    "auto_label",
    "groove_label",
    "groove_options",
    "meter_fallback_note",
    "normalize_selection",
    "resolved_auto_style",
    "style_has_own_pattern",
]
