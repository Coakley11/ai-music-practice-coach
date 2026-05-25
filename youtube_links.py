"""YouTube link helpers for the practice studio.

Two integration tiers are supported:

1. **Song Selection** - a simple "Watch the original song" link that uses
   only the song's title + artist. Instrument / level / focus do not
   affect this URL; it always points at the original recording.

2. **Practice page** - an "Optional YouTube reference" link that adds
   the active **instrument**, **level**, and **focus** as search terms.
   For the Voice / Vocals / Singer instrument we prioritise lyric and
   karaoke videos instead of instrumental tutorials.

Both tiers respect an optional per-song **override URL** so the user
can paste a specific YouTube link and the app will surface that link
(and embed it when it is a full youtu.be / youtube.com video URL).

The module is pure: no Streamlit imports, no network calls. It only
builds well-formed URLs that the UI layer renders.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote_plus, urlparse, parse_qs

__all__ = (
    "VOICE_INSTRUMENT_ALIASES",
    "DEFAULT_FOCUS_BY_INSTRUMENT",
    "VOICE_FOCUS_OPTIONS",
    "is_voice_instrument",
    "build_original_song_search_url",
    "build_learning_search_url",
    "practice_panel_kicker",
    "is_youtube_url",
    "extract_video_id",
    "embed_url_for",
    "thumbnail_url_for",
    "focus_options_for_instrument",
    "describe_search_query",
)


VOICE_INSTRUMENT_ALIASES: frozenset[str] = frozenset(
    {"voice", "vocals", "vocal", "singer", "sing", "karaoke"}
)


# Per-instrument focus suggestions for the Practice-page selector.
# These are concise and musically meaningful; the active session focus
# is pre-selected when the panel opens.
DEFAULT_FOCUS_BY_INSTRUMENT: dict[str, tuple[str, ...]] = {
    "Guitar": (
        "Chords",
        "Strumming",
        "Fingerpicking",
        "Rhythm",
        "Soloing",
        "Improvisation",
        "Technique",
        "Live performance",
    ),
    "Piano": (
        "Chords",
        "Voicings",
        "Accompaniment",
        "Rhythm",
        "Improvisation",
        "Soloing",
        "Pedal & dynamics",
        "Live performance",
    ),
    "Saxophone": (
        "Improvisation",
        "Soloing",
        "Phrasing",
        "Tone & long tones",
        "Articulation",
        "Live performance",
    ),
    "Bass": (
        "Bass line",
        "Groove lock",
        "Slap & technique",
        "Walking bass",
        "Soloing",
        "Live performance",
    ),
    "Drums": (
        "Groove",
        "Fills",
        "Independence",
        "Live performance",
    ),
    "Trumpet": (
        "Improvisation",
        "Soloing",
        "Phrasing",
        "Tone & range",
        "Articulation",
    ),
    "Other": (
        "Chords",
        "Rhythm",
        "Improvisation",
        "Soloing",
        "Technique",
    ),
}


# Voice mode uses karaoke-flavoured focus options instead of instrumental
# language. These are surfaced when ``is_voice_instrument(...)`` is true.
VOICE_FOCUS_OPTIONS: tuple[str, ...] = (
    "Karaoke",
    "Lyric video",
    "Vocal performance",
    "Phrasing",
    "Breath control",
    "Live performance",
    "Cover version",
)


def is_voice_instrument(instrument: Any) -> bool:
    """``True`` when the instrument should use karaoke/lyric search wording."""
    return str(instrument or "").strip().lower() in VOICE_INSTRUMENT_ALIASES


def focus_options_for_instrument(instrument: str | None) -> list[str]:
    """Return the focus selector options for a given instrument."""
    if is_voice_instrument(instrument):
        return list(VOICE_FOCUS_OPTIONS)
    return list(
        DEFAULT_FOCUS_BY_INSTRUMENT.get(
            str(instrument or "").strip(),
            DEFAULT_FOCUS_BY_INSTRUMENT["Other"],
        )
    )


# ---------------------------------------------------------------------------
# URL builders
# ---------------------------------------------------------------------------


def _clean(text: Any) -> str:
    """Strip whitespace + collapse internal whitespace runs to a single space."""
    if text is None:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip()


def _search_url(query: str) -> str:
    """Build a YouTube search results URL from a free-text query string."""
    return f"https://www.youtube.com/results?search_query={quote_plus(query)}"


def build_original_song_search_url(
    song_title: str,
    artist: str | None = None,
    *,
    prefer_official: bool = True,
) -> str:
    """Build a YouTube search URL for the original recording of a song.

    Always title-first, then artist. When ``prefer_official`` is ``True``
    (default) the word ``official`` is appended so YouTube ranks the
    primary recording / music video higher.
    """
    parts: list[str] = []
    title = _clean(song_title)
    if title:
        parts.append(title)
    art = _clean(artist)
    if art:
        parts.append(art)
    if prefer_official:
        parts.append("official")
    query = " ".join(parts) if parts else "music"
    return _search_url(query)


def _level_modifier(level: str | None) -> str:
    """Translate a practice level into a YouTube-friendly search modifier."""
    low = str(level or "").strip().lower()
    if low == "beginner":
        return "beginner easy"
    if low == "advanced":
        return "advanced lesson"
    # Intermediate (or anything else) -> no extra modifier so the title +
    # focus terms still drive ranking.
    return ""


def build_learning_search_url(
    song_title: str,
    artist: str | None = None,
    *,
    instrument: str | None = None,
    level: str | None = None,
    focus: str | None = None,
) -> str:
    """Build a YouTube search URL tuned to instrument / level / focus.

    Voice mode (instrument is Voice / Vocals / Singer / Karaoke) builds a
    karaoke / lyric / vocal-performance query instead of an instrumental
    tutorial query.
    """
    title = _clean(song_title) or "music"
    art = _clean(artist)
    focus_clean = _clean(focus)
    inst_clean = _clean(instrument)
    voice_mode = is_voice_instrument(inst_clean)

    bits: list[str] = [title]
    if art:
        bits.append(art)

    if voice_mode:
        focus_low = focus_clean.lower()
        if "lyric" in focus_low:
            bits.append("lyrics")
        elif "karaoke" in focus_low or not focus_clean:
            bits.append("karaoke")
        elif "performance" in focus_low or "live" in focus_low:
            bits.append("live performance")
        elif "cover" in focus_low:
            bits.append("cover")
        else:
            bits.append("karaoke")
            if focus_clean:
                bits.append(focus_clean)
    else:
        if inst_clean:
            bits.append(inst_clean)
        if focus_clean:
            bits.append(focus_clean)
        level_mod = _level_modifier(level)
        if level_mod:
            bits.append(level_mod)
        bits.append("tutorial")

    return _search_url(" ".join(b for b in bits if b))


def describe_search_query(
    song_title: str,
    artist: str | None = None,
    *,
    instrument: str | None = None,
    level: str | None = None,
    focus: str | None = None,
    mode: str = "learning",
) -> str:
    """Human-readable summary of the query about to be sent to YouTube.

    Used by the UI to show "Searching: Piano Man · Billy Joel · Piano ·
    Voicings · Intermediate" before the user opens the link.
    """
    parts: list[str] = []
    title = _clean(song_title)
    if title:
        parts.append(title)
    art = _clean(artist)
    if art:
        parts.append(art)
    if mode != "original":
        if is_voice_instrument(instrument):
            parts.append("Voice / Karaoke")
        elif instrument:
            parts.append(_clean(instrument))
        if focus:
            parts.append(_clean(focus))
        if level and not is_voice_instrument(instrument):
            parts.append(_clean(level))
    return " · ".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# YouTube URL parsing + embed helpers
# ---------------------------------------------------------------------------


_YOUTUBE_HOSTS = (
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
)


def is_youtube_url(url: str | None) -> bool:
    """``True`` when ``url`` looks like a YouTube link."""
    if not url:
        return False
    try:
        parsed = urlparse(str(url).strip())
    except Exception:
        return False
    return parsed.scheme in ("http", "https") and parsed.netloc.lower() in _YOUTUBE_HOSTS


def extract_video_id(url: str | None) -> str | None:
    """Return the 11-character YouTube video id for an arbitrary YouTube URL.

    Supports:

    * ``https://www.youtube.com/watch?v=<id>``
    * ``https://youtu.be/<id>``
    * ``https://www.youtube.com/embed/<id>``
    * ``https://www.youtube.com/shorts/<id>``
    * ``https://music.youtube.com/watch?v=<id>``

    Returns ``None`` for non-video URLs (e.g. search results pages or
    bare hostnames).
    """
    if not url:
        return None
    try:
        parsed = urlparse(str(url).strip())
    except Exception:
        return None
    host = parsed.netloc.lower()
    if host not in _YOUTUBE_HOSTS:
        return None
    # youtu.be/<id>
    if host == "youtu.be":
        vid = parsed.path.strip("/").split("/", 1)[0]
        return vid if _looks_like_video_id(vid) else None
    # /watch?v=<id>
    if parsed.path == "/watch":
        params = parse_qs(parsed.query)
        vid = (params.get("v") or [""])[0]
        return vid if _looks_like_video_id(vid) else None
    # /embed/<id> or /shorts/<id> or /v/<id>
    path = parsed.path.strip("/")
    for prefix in ("embed/", "shorts/", "v/"):
        if path.startswith(prefix):
            vid = path[len(prefix) :].split("/", 1)[0]
            return vid if _looks_like_video_id(vid) else None
    return None


def _looks_like_video_id(value: str) -> bool:
    """YouTube IDs are 11 chars from a URL-safe base64 alphabet."""
    return bool(re.fullmatch(r"[A-Za-z0-9_-]{11}", value or ""))


def embed_url_for(url: str | None) -> str | None:
    """Return a privacy-friendly ``youtube-nocookie.com/embed/<id>`` URL.

    Returns ``None`` when the input is not a recognisable single-video
    URL (e.g. a search results page) - the caller should fall back to
    the "Open on YouTube" button in that case.
    """
    vid = extract_video_id(url)
    if not vid:
        return None
    return f"https://www.youtube-nocookie.com/embed/{vid}"


def thumbnail_url_for(url: str | None) -> str | None:
    """Return YouTube's auto-generated ``hqdefault.jpg`` thumbnail URL."""
    vid = extract_video_id(url)
    if not vid:
        return None
    return f"https://img.youtube.com/vi/{vid}/hqdefault.jpg"


def practice_panel_kicker(instrument: Any) -> str:
    """Return the section heading used on the Practice page YouTube panel."""
    if is_voice_instrument(instrument):
        return "Karaoke Reference"
    return "Optional YouTube Reference"
