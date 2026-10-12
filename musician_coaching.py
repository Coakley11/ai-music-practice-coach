"""Musician-facing song summary and practice coaching (not chart encoding).

Answers: "How should I play this song on my instrument at my level?"
Catalog ``arrangement_notes`` stay in extensions for internal/dev use only.
"""

from __future__ import annotations

import html
import re
from typing import Any

from music_theory import friendly_note_name
from song_coaching import _instrument_key, build_song_coaching


def _friendly_chord(chord: str) -> str:
    """Apply friendly note spelling to the root of a chord symbol."""
    s = str(chord or "").strip()
    if len(s) >= 2 and s[1] in ("#", "b"):
        root, suffix = s[:2], s[2:]
    elif s:
        root, suffix = s[0], s[1:]
    else:
        return s
    return friendly_note_name(root) + suffix


_INSTRUMENT_LABELS = {
    "piano": "Piano",
    "guitar": "Guitar",
    "bass": "Bass",
    "voice": "Voice",
    "saxophone": "Saxophone",
    "trumpet": "Trumpet",
    "flute": "Flute",
    "general": "your instrument",
}

# Phrases that mark catalog notes as developer/chart documentation.
_DEV_NOTE_MARKERS = (
    "transposed from",
    "one list item",
    "one chart bar",
    "playback bar",
    "half-bar split",
    "pipe token",
    "reference:",
    "am→",
    "am->",
    "→",
    "``",
    "list item = one",
    "reference chart",
    "catalog key",
)

# Theory/authoring labels that must not appear as user-facing coaching.
_THEORY_JARGON_MARKERS = (
    "dominant 7th",
    "suspended voicing",
    "tempo creep",
    "maj7 /",
    "ii–v",
    "ii-v",
    "half-diminished",
    "chromatic passing",
    "slash chords /",
    "pop ballad comping",
    "harmonic color:",
    "study harmonic",
)


def format_key_for_musicians(practice_key: str) -> str:
    """Display key in plain language (practice / concert key only)."""
    k = str(practice_key or "C").strip() or "C"
    low = k.lower()
    if low.endswith("m") and len(k) > 1 and not low.endswith("maj"):
        root = k[:-1] if k.endswith("m") else k
        return f"{root} minor"
    return f"{k} major"


_CHORD_IN_PROSE = re.compile(
    r"(?<![A-Za-z0-9#])"
    r"([A-G](?:#|b)?"
    r"(?:maj7|maj9|m7b5|m7|m9|sus4|sus2|7sus4|7|dim|aug|add9|11|13|m)?"
    r"(?:/[A-G](?:#|b)?)?)"
    r"(?![A-Za-z0-9])"
)


def adapt_text_to_practice_key(
    text: str,
    *,
    catalog_key: str,
    practice_key: str,
) -> str:
    """Rewrite catalog-key chord spellings and key names for the active practice key."""
    raw = str(text or "").strip()
    if not raw:
        return raw
    cat = str(catalog_key or "").strip()
    practice = str(practice_key or "").strip()
    if not cat or not practice:
        return raw
    try:
        from music_theory import semitone_distance, transpose_chord

        steps = semitone_distance(cat, practice)
    except Exception:
        return raw
    if steps == 0:
        return raw

    def _repl(match: re.Match[str]) -> str:
        token = match.group(1)
        try:
            return transpose_chord(token, steps, reference_key=practice)
        except Exception:
            return token

    out = _CHORD_IN_PROSE.sub(_repl, raw)

    cat_fmt = format_key_for_musicians(cat)
    practice_fmt = format_key_for_musicians(practice)
    for old, new in (
        (cat_fmt, practice_fmt),
        (f"{cat} major", practice_fmt),
        (f"{cat} minor", practice_fmt),
        (cat, practice),
    ):
        if old and old != new and old in out:
            out = out.replace(old, new)

    return out


def transpose_lyric_cue(
    text: str,
    *,
    catalog_key: str,
    practice_key: str,
) -> str:
    """Transpose chord symbols embedded in a lyric/coaching cue line."""
    return adapt_text_to_practice_key(
        text, catalog_key=catalog_key, practice_key=practice_key
    )


def transpose_lyric_cues(
    cues: dict[str, list[str]],
    *,
    catalog_key: str,
    practice_key: str,
) -> dict[str, list[str]]:
    """Return a copy of lyric cues with chord spellings moved to the chart key.

    ``practice_key`` must match the key shown on the active chart (written key
    for transposing instruments, capo shape key for guitar, otherwise concert).
    """
    if not cues:
        return {}
    try:
        from music_theory import semitone_distance

        if semitone_distance(catalog_key, practice_key) == 0:
            return dict(cues)
    except Exception:
        return dict(cues)
    out: dict[str, list[str]] = {}
    for section, lines in cues.items():
        out[section] = [
            transpose_lyric_cue(
                str(line),
                catalog_key=catalog_key,
                practice_key=practice_key,
            )
            for line in (lines or [])
            if str(line).strip()
        ]
    return out


def musician_facing_chart_key(
    *,
    chart_key: str,
    instrument: str = "",
    capo_enabled: bool = False,
    shape_key: str = "",
) -> str:
    """Key spellings on the chart — single source of truth for musician-facing text."""
    if str(instrument or "").strip() == "Guitar" and capo_enabled:
        return str(shape_key or chart_key or "C").strip() or "C"
    return str(chart_key or "C").strip() or "C"


def is_internal_arrangement_note(text: str) -> bool:
    """True when catalog arrangement_notes are chart/dev documentation."""
    low = str(text or "").lower()
    if not low.strip():
        return False
    if any(m in low for m in ("pipe token", "one chart bar", "playback bar", "transposed from")):
        return True
    if "→" in low and ("am" in low or "reference" in low):
        return True
    hits = sum(1 for m in _DEV_NOTE_MARKERS if m in low)
    return hits >= 2 or ("transposed from" in low and "bpm" in low)


def is_theory_jargon(text: str) -> bool:
    """True when copy reads like chart analysis, not a teacher."""
    low = str(text or "").lower()
    return any(m in low for m in _THEORY_JARGON_MARKERS)


def _first_sentence(text: str, *, max_len: int = 160) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""
    for sep in (". ", "! ", "? "):
        if sep in raw:
            raw = raw.split(sep, 1)[0] + sep.strip()
            break
    if not raw.endswith((".", "!", "?")):
        raw = raw.rstrip(".") + "."
    if len(raw) > max_len:
        raw = raw[: max_len - 1].rsplit(" ", 1)[0] + "…"
    return raw


def musician_harmony_blurb(
    record: dict[str, Any],
    sections: dict[str, list[str]],
    *,
    instrument: str = "",
    level: str = "Intermediate",
    practice_key: str | None = None,
) -> str:
    """One musician-facing harmony/listening line — never theory catalog tags."""
    title = str(record.get("title") or "")
    artist = str(record.get("artist") or "")
    catalog_key = str(record.get("key") or "")
    pk = str(practice_key or catalog_key or "C")
    try:
        from song_performance_coaching import harmony_blurb_for_song

        tip = harmony_blurb_for_song(
            title,
            instrument=instrument,
            level=level,
            artist=artist or None,
            catalog_key=catalog_key,
            practice_key=pk,
        )
        if tip:
            return tip
    except Exception:
        pass

    chords = [str(c).strip() for chs in sections.values() for c in (chs or []) if str(c).strip()]
    low = " ".join(chords).lower()
    if "sus" in low:
        return "Listen for the gentle pull of suspended chords before they resolve."
    if any("/" in c for c in chords):
        return "Follow the bass notes when chords change—they connect each phrase naturally."
    if "maj7" in low or "maj9" in low:
        return "Let the warm chord colors shine through a light, unhurried touch."
    if any(
        re.search(r"(?<![a-z])7(?!#|b|\d|sus)", c, re.I)
        and "maj7" not in c.lower()
        and "m7" not in c.lower()
        for c in chords
    ):
        return "Notice how some chords lean forward with tension, then relax into the next change."
    if "m7" in low:
        return "Keep the groove relaxed—the minor chords want space, not force."
    return "Let the harmony support the melody without crowding it."


def musician_challenge_blurb(
    record: dict[str, Any],
    sections: dict[str, list[str]],
    *,
    instrument: str = "",
    level: str = "Intermediate",
    coaching: dict[str, str] | None = None,
    practice_key: str | None = None,
) -> str:
    """One clear performance challenge in plain language."""
    title = str(record.get("title") or "")
    artist = str(record.get("artist") or "")
    catalog_key = str(record.get("key") or "")
    pk = str(practice_key or catalog_key or "C")
    try:
        from song_performance_coaching import challenge_blurb_for_song

        tip = challenge_blurb_for_song(
            title,
            instrument=instrument,
            level=level,
            artist=artist or None,
            catalog_key=catalog_key,
            practice_key=pk,
        )
        if tip:
            return tip
    except Exception:
        pass

    raw = str((coaching or {}).get("biggest_challenge") or "").strip()
    if raw and not is_theory_jargon(raw) and not is_internal_arrangement_note(raw):
        return _first_sentence(raw)

    section_names = [str(s) for s in (sections or {}).keys()]
    if any("chorus" in s.lower() for s in section_names):
        return "Save your biggest sound for the chorus—don't spend it all in the verse."
    if any("/" in str(c) for chs in sections.values() for c in (chs or [])):
        return "Keep bass-led chord changes smooth and unhurried."
    return "Keep the chord changes smooth without rushing."


def build_musician_summary_meta(
    record: dict[str, Any],
    *,
    practice_key: str,
    time_signature: str = "4/4",
    bpm: int | None = None,
) -> dict[str, str]:
    """Simple metadata lines for cards and chart headers."""
    ext = record.get("extensions") or {}
    genre = str(record.get("genre") or "Pop").strip()
    tempo = int(bpm or ext.get("default_bpm") or 100)
    meter = str(time_signature or ext.get("time_signature") or "4/4").strip()
    return {
        "key": format_key_for_musicians(practice_key),
        "tempo": f"{tempo} BPM",
        "time_signature": meter,
        "genre": genre,
    }


def musician_summary_paragraph(
    record: dict[str, Any],
    sections: dict[str, list[str]],
    *,
    practice_key: str,
    instrument: str = "",
    level: str = "Intermediate",
) -> str:
    """Short blurb for Active Song card — no transpose/encoding jargon."""
    title = str(record.get("title") or "this song")
    artist = str(record.get("artist") or "")
    meta = build_musician_summary_meta(record, practice_key=practice_key)

    try:
        from song_performance_coaching import instructor_lesson_opener, practice_focus_for_song

        opener = instructor_lesson_opener(
            title, instrument=instrument, level=level, artist=artist,
            catalog_key=str(record.get("key") or ""),
            practice_key=practice_key,
        )
        if opener:
            meta_line = (
                f"You're working in {meta['key']} at {meta['tempo']} "
                f"({meta['time_signature']}, {meta['genre']})."
            )
            return f"{opener} {meta_line}"
    except Exception:
        pass

    coaching = build_song_coaching(
        record,
        sections,
        instrument=instrument,
        level=level,
        practice_key=practice_key,
    )
    what = str(coaching.get("what_matters") or "").strip()
    what = re.sub(r"\*\*", "", what)
    section_names = [s for s in (sections or {}).keys() if str(s).strip()]
    form_hint = ""
    if section_names:
        try:
            from practice_studio import _build_section_flow, practice_ordered_section_names

            labels = practice_ordered_section_names(
                sections,
                section_names=record.get("section_order"),
            )
            form_hint = _build_section_flow(labels)
        except Exception:
            form_hint = " → ".join(section_names[:6])
    lines = [
        f"You're working in {meta['key']} at {meta['tempo']} ({meta['time_signature']}, {meta['genre']}).",
    ]
    if what:
        lines.append(what)
    elif form_hint:
        lines.append(
            f"The form moves through {form_hint} — learn one section at a time with the metronome."
        )
    else:
        lines.append(
            f"Take {title} section by section: lock the groove first, then polish chord changes."
        )
    return " ".join(lines)


def practice_focus_plain(
    record: dict[str, Any],
    sections: dict[str, list[str]],
    *,
    level: str = "Intermediate",
    instrument: str = "",
    practice_key: str | None = None,
) -> str:
    """Scan-friendly practice focus in plain English."""
    title = str(record.get("title") or "")
    artist = str(record.get("artist") or "")
    try:
        from song_performance_coaching import practice_focus_for_song

        curated = practice_focus_for_song(
            title,
            instrument=instrument,
            level=level,
            artist=artist,
            catalog_key=str(record.get("key") or ""),
            practice_key=str(practice_key or record.get("key") or "C"),
        )
        if curated:
            return curated
    except Exception:
        pass

    coaching = build_song_coaching(
        record,
        sections,
        instrument=instrument,
        level=level,
        practice_key=practice_key,
    )
    tip = str(coaching.get("instrument_tip") or "").strip()
    level_norm = (level or "Intermediate").strip().lower()
    bits: list[str] = []
    if level_norm.startswith("beg"):
        bits.extend(["steady tempo", "easy chord shapes", "smooth changes"])
    elif level_norm.startswith("adv"):
        bits.extend(["expression", "dynamics", "your own interpretation"])
    else:
        bits.extend(["steady rhythm", "clean transitions", "musical feel"])
    if tip:
        short = tip.split(".")[0].strip()
        if short and len(short) < 80:
            bits.insert(0, short)
    out: list[str] = []
    for b in bits:
        if b and b not in out:
            out.append(b)
        if len(out) >= 4:
            break
    return " · ".join(out) if out else "steady rhythm · smooth chord changes"


def humanize_lyric_cue(
    text: str,
    *,
    title: str = "",
    section_name: str = "",
    artist: str = "",
    catalog_key: str = "",
    practice_key: str = "",
) -> str:
    """Rewrite theory-heavy catalog cues into plain coaching language."""
    raw = str(text or "").strip()
    if not raw:
        return raw
    if catalog_key and practice_key:
        raw = transpose_lyric_cue(
            raw, catalog_key=catalog_key, practice_key=practice_key
        )
    low = raw.lower()
    replacements = (
        (r"left hand roots?/fifths?", "Play the root of each chord in your left hand"),
        (r"right hand shells?", "Use simple chord shapes in your right hand"),
        (r"verse loop:.*", "The verse repeats the same chord pattern — focus on steady rhythm and smooth transitions."),
        (r"i7[–\-].*", "The verse repeats the same chord pattern — focus on steady rhythm and smooth transitions."),
        (r"g#sus4 delays resolution", "Hold the suspended chord briefly to build tension, then resolve smoothly into the next chord."),
        (r"half-bar bass walk", "The bass line moves quickly between chords — practice slowly until the changes feel natural."),
        (r"maj7 / maj9 colors?", "Listen for the richer chord colors and keep your touch light"),
        (r"slash-chord voice leading", "Watch the bass notes when chords change — they tell the story of the progression"),
    )
    out = raw
    for pattern, repl in replacements:
        if re.search(pattern, low):
            return repl
    if "|" in out or ":2" in out or "chart bar" in low:
        return "Follow the chord chart and keep a relaxed, steady feel in this section."
    return out


def plain_section_harmony_tip(
    section_name: str,
    chords: list[str],
    *,
    title: str = "",
    artist: str = "",
    catalog_key: str = "",
    practice_key: str = "",
) -> str:
    """Section harmony hint without Roman numerals or theory codes."""
    if title:
        try:
            from song_performance_coaching import harmony_tip_for_song

            tip = harmony_tip_for_song(
                title,
                section_name,
                artist=artist or None,
                catalog_key=catalog_key or None,
                practice_key=practice_key or None,
            )
            if tip:
                return tip
        except Exception:
            pass
    role = str(section_name or "").lower()
    n_changes = len({str(c) for c in chords if str(c).strip()})
    if "chorus" in role:
        return (
            "This is the lift of the song — play with a little more energy and let the melody shine on top."
        )
    if "bridge" in role:
        return (
            "This section adds contrast. Change your texture or dynamics so it feels fresh before returning to the main theme."
        )
    if "verse" in role:
        if n_changes <= 4:
            return (
                "The verse repeats a familiar pattern. Once the chords feel easy, focus on groove and leaving space for the vocal."
            )
        return (
            "Keep the verse lighter than the chorus — steady rhythm and relaxed dynamics help the story come through."
        )
    if any(t in role for t in ("intro", "outro", "instrumental", "solo")):
        return (
            "Set the mood here — don't rush. Match the feel of the recording and treat this as a setup or landing for the song."
        )
    if any("/" in str(c) for c in chords):
        return (
            "Some chords use a different bass note — follow the lowest note you hear and connect each change smoothly."
        )
    return (
        "Work this section slowly with a metronome, then loop it until the chord changes feel automatic."
    )


def _section_role(section_name: str) -> str:
    low = str(section_name or "").lower()
    if "chorus" in low and "pre" not in low:
        return "chorus"
    if "pre" in low and "chorus" in low:
        return "pre"
    if "verse" in low:
        return "verse"
    if "bridge" in low:
        return "bridge"
    if any(t in low for t in ("solo", "instrumental")):
        return "solo"
    if "intro" in low:
        return "intro"
    if "outro" in low or "ending" in low:
        return "outro"
    return "neutral"


def _guide_tone_info(chords: list[str]) -> tuple[str, str, str]:
    """Compute guide-tone text from actual chords. Returns (gt_list, first_vl, vl_chain)."""
    try:
        from music_theory import guide_tones_for_chord, guide_tone_voice_leading
    except ImportError:
        return "", "", ""
    unique: list[str] = []
    seen: set[str] = set()
    for c in chords:
        cleaned = str(c).split("|")[0].strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            unique.append(cleaned)
    if not unique:
        return "", "", ""
    parts = []
    for ch in unique[:4]:
        root, third, seventh = guide_tones_for_chord(ch)
        if seventh:
            parts.append(f"{_friendly_chord(ch)}: {friendly_note_name(third)} and {friendly_note_name(seventh)}")
        elif third:
            parts.append(f"{_friendly_chord(ch)}: {friendly_note_name(third)}")
    gt_list = "; ".join(parts) if parts else ""
    vl = guide_tone_voice_leading(unique[:6])
    vl_steps = [e["voice_lead"] for e in vl if e["voice_lead"]]
    first_vl = vl_steps[0] if vl_steps else ""
    vl_chain = ", ".join(vl_steps[:4]) if vl_steps else ""
    return gt_list, first_vl, vl_chain


def _focus_coaching_overlay(
    *,
    focus: str,
    family: str,
    level_norm: str,
    chords: list[str],
    section_name: str,
) -> str:
    """Return a focus-specific coaching sentence, or empty string if focus is generic."""
    low = str(focus or "").lower()
    chord_names = ", ".join(_friendly_chord(c) for c in chords[:4]) if chords else "the chords"

    if "pentatonic" in low or "scale" in low:
        roots = []
        try:
            from music_theory import guide_tones_for_chord
            seen: set[str] = set()
            for c in chords[:4]:
                cleaned = str(c).split("|")[0].strip()
                if cleaned and cleaned not in seen:
                    seen.add(cleaned)
                    r, _, _ = guide_tones_for_chord(cleaned)
                    roots.append(friendly_note_name(r))
        except ImportError:
            pass
        root_hint = f" (roots: {', '.join(roots)})" if roots else ""
        if level_norm.startswith("beg"):
            return f" Practice the pentatonic scale slowly over {chord_names}{root_hint}. Start on the root of each chord, play three notes up, and come back down."
        if level_norm.startswith("adv"):
            return f" Try different pentatonic choices over each chord in this section{root_hint}. Match the pentatonic to the chord quality and target chord tones on strong beats."
        return f" Use the pentatonic scale to create short melodic phrases over {chord_names}. Land on the 3rd or root at each chord change{root_hint}."

    if "guide tone" in low or "guide-tone" in low:
        gt_list, first_vl, vl_chain = _guide_tone_info(chords)
        if level_norm.startswith("beg"):
            base = f" Find the 3rd and 7th of each chord and play them as whole notes."
            if gt_list:
                base += f" Here are the guide tones: {gt_list}."
            if first_vl:
                base += f" Notice how {first_vl} — the 7th moves by step to the next chord's 3rd."
            return base
        if level_norm.startswith("adv"):
            base = " Map a guide-tone line through this section connecting 3rds and 7ths with minimal motion. Add chromatic approaches and enclosures around each guide tone."
            if vl_chain:
                base += f" Voice-leading path: {vl_chain}."
            return base
        base = f" Connect the 3rds and 7ths between chords to create a smooth guide-tone melody through this section."
        if gt_list:
            base += f" Guide tones: {gt_list}."
        if first_vl:
            base += f" Start with: {first_vl}."
        return base

    if "tone" in low and "guide" not in low:
        if family in ("saxophone", "trumpet", "flute"):
            if level_norm.startswith("beg"):
                return " Start with long tones on comfortable notes in this key — keep air steady and pitch centered before adding any melody."
            if level_norm.startswith("adv"):
                return " Focus on tone consistency across all registers in this section — match the color of your sound in the low range to the upper range."
            return " Play this section slowly with sustained notes, focusing on air support and even tone through each phrase."
        if family == "piano":
            return " Focus on touch: play this section with a warm, even tone, adjusting key weight to match the dynamic level of each phrase."
        if family == "guitar":
            return " Focus on clean, buzzing-free tone through each chord change — let notes ring fully before moving to the next chord."
        return " Focus on producing a centered, even tone through this section before adding speed or complexity."

    if "articulation" in low:
        if family in ("saxophone", "trumpet", "flute"):
            if level_norm.startswith("beg"):
                return " Tongue each note cleanly with a gentle 'ta' — keep the air flowing between attacks."
            if level_norm.startswith("adv"):
                return " Vary articulation through this section: legato connections within phrases, crisp tonguing at phrase starts, and ghosted notes for rhythmic interest."
            return " Alternate between slurred and tongued patterns in this section — keep the tone quality consistent regardless of articulation."
        if family == "guitar":
            return " Focus on clean picking or plucking attacks — vary between legato hammer-ons and crisp alternate picking for musical variety."
        if family == "piano":
            return " Shape the touch of each note: use legato fingering through melodic lines and staccato accents on rhythmic figures."
        return " Focus on clean, intentional attacks in this section — each note should start clearly without harshness."

    if any(p in low for p in ("rhythm", "timing", "groove", "syncopat")):
        if level_norm.startswith("beg"):
            return " Count out loud while playing this section. Place chord changes exactly on beat 1 and keep a steady pulse."
        if level_norm.startswith("adv"):
            return " Push the rhythmic interest: add syncopation, anticipate chord changes by an eighth note, and vary the accent pattern through the phrase."
        return " Lock into the groove with a metronome — place chord changes precisely and keep subdivisions even through the section."

    if "dynamic" in low:
        if level_norm.startswith("beg"):
            return " Play this section twice: once softly, once at full volume. Notice how the music feels different at each dynamic level."
        if level_norm.startswith("adv"):
            return " Shape the dynamic arc of this section — build toward the highest-energy moment and ease back afterward. Use crescendo and decrescendo within phrases."
        return " Plan where this section should be soft and where it should open up. Make the volume change gradual and musical."

    if "breath" in low or "endurance" in low:
        if family in ("saxophone", "trumpet", "flute"):
            return " Mark breath spots on the chart before playing. Take full breaths at phrase ends; don't sneak air in the middle of a musical line."
        return ""

    if "bebop" in low:
        gt_list, first_vl, _ = _guide_tone_info(chords)
        if level_norm.startswith("beg"):
            base = f" Play the scale over {chord_names} with a swing feel. Add one chromatic passing tone between the root and 7th of each chord."
            if gt_list:
                base += f" Guide tones to target: {gt_list}."
            return base
        if level_norm.startswith("adv"):
            base = " Run bebop scale lines through this section, keeping chord tones on downbeats. Add enclosures around guide tones and vary rhythmic groupings."
            if first_vl:
                base += f" Try enclosing the 3rd at the {first_vl} voice-leading point."
            return base
        base = f" Practice eighth-note lines over {chord_names} that place chord tones on beats 1 and 3."
        if gt_list:
            base += f" Target these guide tones: {gt_list}."
        return base

    return ""


def section_coaching_html(
    *,
    section_name: str,
    instrument: str,
    level: str,
    groove_style: str,
    bpm: int,
    chords: list[str],
    focus: str = "",
    title: str = "",
    artist: str = "",
    catalog_key: str = "",
    practice_key: str = "",
) -> str:
    """Per-section coach overlay in plain English."""
    curated = ""
    if title:
        try:
            from song_performance_coaching import section_coaching_for_song

            curated = section_coaching_for_song(
                title,
                section_name=section_name,
                instrument=instrument,
                level=level,
                artist=artist or None,
                catalog_key=catalog_key or None,
                practice_key=practice_key or None,
            ) or ""
        except Exception:
            pass

    family = _instrument_key(instrument)
    role = _section_role(section_name)
    level_norm = (level or "Intermediate").strip().lower()
    feel = groove_style or "Pop groove"
    first = html.escape(_friendly_chord(chords[0])) if chords else "the first chord"

    if family == "guitar":
        if level_norm.startswith("beg"):
            body = (
                f"Use a simple down-up strum at {bpm} BPM. Change chords on time even if you only strum once per bar. "
                f"A capo can make {first} easier to finger — check the key display above."
            )
        elif level_norm.startswith("adv"):
            body = (
                f"Shape the {feel} with accents on beats 2 and 4. Vary dynamics by section and add fills only "
                "in open spaces — never over the vocal."
            )
        else:
            body = (
                f"Keep a steady {feel} strum. Practice the move into {first} until it is one motion, "
                "then loop the whole section with the metronome."
            )
    elif family == "piano":
        if level_norm.startswith("beg"):
            body = (
                "Play the root of each chord in your left hand. Use two- or three-note shapes in your right hand "
                "and move as little as possible between chords. Pedal lightly — change pedal on each new chord."
            )
        elif level_norm.startswith("adv"):
            body = (
                "Voice chords for clarity: keep the melody note on top, use inner movement between changes, "
                "and ride the sustain pedal musically (half-pedal on ballads)."
            )
        else:
            body = (
                "Left hand: roots or root-and-fifth. Right hand: comfortable chord grips that connect by nearest note. "
                f"Match the {feel} pulse at {bpm} BPM."
            )
    elif family in ("saxophone", "trumpet", "flute"):
        if level_norm.startswith("beg"):
            body = (
                "Long tones first in this key, then simple quarter-note rhythms on chord roots. "
                "Plan breaths at phrase ends — mark them on the chart."
            )
        elif level_norm.startswith("adv"):
            body = (
                "Phrase in musical sentences, not endless notes. Use varied articulation for character, "
                "leave space between ideas, and shape dynamics toward the peak of each phrase."
            )
        else:
            body = (
                "Phrase in sentences, not endless notes. Use tonguing for clarity, leave space, "
                "and swell slightly toward the peak of each phrase."
            )
    elif family == "voice":
        if level_norm.startswith("beg"):
            body = (
                "Speak the lyric in rhythm before singing. Mark where to breathe. "
                "Keep your voice relaxed and don't push for volume yet."
            )
        elif level_norm.startswith("adv"):
            body = (
                "Shape each phrase emotionally: vary vowel color, use controlled vibrato on sustained notes, "
                "and plan dynamic contrast between verse intimacy and chorus projection."
            )
        else:
            body = (
                "Speak the lyric in rhythm before singing. Mark breaths, keep vowels forward, "
                "and stay softer in verses until the chorus asks for more."
            )
    elif family == "bass":
        if level_norm.startswith("beg"):
            body = (
                f"Play the root of each chord on beat 1 with a steady pulse. "
                f"Keep note length even before adding movement."
            )
        elif level_norm.startswith("adv"):
            body = (
                f"Lock with the kick on {feel}. Connect chords with approach tones or walking lines; "
                "shape the bass line as a melodic voice, not just root support."
            )
        else:
            body = (
                f"Lock with the kick on {feel}. Root on beat 1, connect to the next chord with a smooth step or slide."
            )
    else:
        body = (
            f"Stay in time with the {feel} at {bpm} BPM. Learn {first} first, then link pairs of bars."
        )

    focus_overlay = _focus_coaching_overlay(
        focus=focus,
        family=family,
        level_norm=level_norm,
        chords=chords,
        section_name=section_name,
    )

    role_tail = {
        "chorus": " Open up dynamically here.",
        "verse": " Stay relaxed — support the vocal.",
        "bridge": " Change color so the return feels exciting.",
        "intro": " Set tempo and mood; don't overplay.",
        "outro": " Wind down gradually; let the last chord ring.",
        "solo": " Short phrases; leave gaps.",
    }.get(role, "")

    if curated:
        return f"{curated}{focus_overlay}"
    return f"{body}{focus_overlay}{role_tail}"


def _focus_practice_line(
    focus: str, instrument: str, level: str,
    chords: list[str] | None = None,
) -> str:
    """Focus prompt for the Practice Coach markdown tab, with concrete chord content when available."""
    low = str(focus or "").lower()
    if not low:
        return ""
    family = _instrument_key(instrument)
    lv = (level or "Intermediate").strip().lower()

    gt_list = first_vl = vl_chain = ""
    root_names = ""
    if chords:
        gt_list, first_vl, vl_chain = _guide_tone_info(chords)
        try:
            from music_theory import guide_tones_for_chord
            seen: set[str] = set()
            roots: list[str] = []
            for c in chords[:6]:
                cleaned = str(c).split("|")[0].strip()
                if cleaned and cleaned not in seen:
                    seen.add(cleaned)
                    r, _, _ = guide_tones_for_chord(cleaned)
                    roots.append(friendly_note_name(r))
            root_names = ", ".join(roots) if roots else ""
        except ImportError:
            pass

    if "pentatonic" in low or "scale" in low:
        root_hint = f" Chord roots: {root_names}." if root_names else ""
        if lv.startswith("beg"):
            return f"**Today's focus — Pentatonics** — Play the minor pentatonic slowly over each chord root. Three notes up, three notes back.{root_hint}"
        if lv.startswith("adv"):
            return f"**Today's focus — Pentatonics** — Superimpose different pentatonic choices over each chord quality and target chord tones on strong beats.{root_hint}"
        return f"**Today's focus — Pentatonics** — Use the pentatonic scale to build short melodic phrases, landing on the 3rd or root at each chord change.{root_hint}"

    if "guide tone" in low or "guide-tone" in low:
        if lv.startswith("beg"):
            base = "**Today's focus — Guide Tones** — Find the 3rd and 7th of each chord and hold them as whole notes."
            if gt_list:
                base += f" Here are the guide tones: {gt_list}."
            if first_vl:
                base += f" Notice how {first_vl} — the 7th resolves by step to the next chord's 3rd."
            return base
        if lv.startswith("adv"):
            base = "**Today's focus — Guide Tones** — Map a guide-tone line through the whole song with chromatic approaches and enclosures around each target."
            if vl_chain:
                base += f" Voice-leading path: {vl_chain}."
            return base
        base = "**Today's focus — Guide Tones** — Connect the 3rds and 7ths between chords to create a smooth guide-tone melody through each section."
        if gt_list:
            base += f" Guide tones: {gt_list}."
        if first_vl:
            base += f" Start with: {first_vl}."
        return base

    if "tone" in low and "guide" not in low:
        if family in ("saxophone", "trumpet", "flute"):
            return "**Today's focus — Tone** — Start with long tones in this key. Keep air steady, pitch centered, and match tone color across registers."
        if family == "piano":
            return "**Today's focus — Tone** — Play with a warm, even touch. Adjust key weight to match the dynamic level of each phrase."
        if family == "guitar":
            return "**Today's focus — Tone** — Play cleanly through each chord change — let notes ring fully before moving."
        return "**Today's focus — Tone** — Produce a centered, even tone through each section before adding speed."

    if "articulation" in low:
        if family in ("saxophone", "trumpet", "flute"):
            return "**Today's focus — Articulation** — Alternate slurred and tongued patterns. Keep tone quality consistent regardless of articulation style."
        if family == "guitar":
            return "**Today's focus — Articulation** — Vary between legato hammer-ons and crisp alternate picking for musical contrast."
        return "**Today's focus — Articulation** — Shape each note's attack intentionally — clean starts without harshness."

    if any(p in low for p in ("rhythm", "timing", "groove", "syncopat")):
        if lv.startswith("beg"):
            return "**Today's focus — Rhythm** — Count out loud while playing. Place chord changes exactly on beat 1 with the metronome."
        if lv.startswith("adv"):
            return "**Today's focus — Rhythm** — Add syncopation, anticipate chord changes by an eighth note, and vary accent patterns through phrases."
        return "**Today's focus — Rhythm** — Lock into the groove with a metronome — keep subdivisions even through each section."

    if "dynamic" in low:
        if lv.startswith("beg"):
            return "**Today's focus — Dynamics** — Play each section twice: once softly, once full volume. Notice how the music changes."
        if lv.startswith("adv"):
            return "**Today's focus — Dynamics** — Shape the dynamic arc of each section — build toward peaks and ease back. Use crescendo and decrescendo within phrases."
        return "**Today's focus — Dynamics** — Plan where each section should be soft and where it opens up. Make the volume change gradual."

    if "bebop" in low:
        if lv.startswith("beg"):
            base = "**Today's focus — Bebop Phrasing** — Add one chromatic passing tone between the root and 7th of each chord in a swing feel."
            if gt_list:
                base += f" Target these guide tones: {gt_list}."
            return base
        if lv.startswith("adv"):
            base = "**Today's focus — Bebop Phrasing** — Run bebop scale lines keeping chord tones on downbeats. Add enclosures and vary rhythmic groupings."
            if first_vl:
                base += f" Try enclosing the 3rd at the {first_vl} voice-leading point."
            return base
        base = "**Today's focus — Bebop Phrasing** — Play eighth-note lines that place chord tones on beats 1 and 3. Add a chromatic approach to each chord's 3rd."
        if gt_list:
            base += f" Target: {gt_list}."
        return base

    if "breath" in low or "endurance" in low:
        if family in ("saxophone", "trumpet", "flute"):
            return "**Today's focus — Breath Support** — Mark breath spots before playing. Take full breaths at phrase ends, never mid-line."
        return ""

    if any(p in low for p in ("strum", "barre", "double stop", "triad")):
        return f"**Today's focus — {focus}** — Isolate this technique in every section before playing through at full tempo."

    if any(p in low for p in ("harmony", "chord", "voicing", "voice leading", "inversion", "comping")):
        return f"**Today's focus — {focus}** — Apply this harmonic concept through each section, connecting smoothly between chord changes."

    if any(p in low for p in ("improv", "solo", "lead guitar")):
        return f"**Today's focus — {focus}** — Use this song's changes as your improvisation vehicle. Start with short phrases and build."

    if "ear" in low and "training" in low:
        return "**Today's focus — Ear Training** — Sing each chord root before playing it. Try to hear the next chord change before it arrives."

    if "fingerstyle" in low:
        return "**Today's focus — Fingerstyle** — Apply fingerpicking patterns through each section, keeping a steady bass-note pulse."

    if "walking" in low and "bass" in low:
        return "**Today's focus — Walking Bass** — Build a quarter-note walking line connecting chord roots with scale tones and chromatic approaches."

    if "phrasing" in low:
        return "**Today's focus — Phrasing** — Shape each musical sentence with a clear beginning, peak, and resolution. Leave space between ideas."

    return ""


def coaching_markdown_teacher(
    block: dict[str, str],
    record: dict[str, Any],
    *,
    instrument: str,
    level: str,
    practice_key: str,
    sections: dict[str, list[str]] | None = None,
    focus: str = "",
) -> str:
    """Practice Coach tab — teacher voice, practice key only."""
    meta = build_musician_summary_meta(record, practice_key=practice_key)
    inst_label = _INSTRUMENT_LABELS.get(_instrument_key(instrument), instrument or "your instrument")
    tip = str(block.get("instrument_tip") or "").strip()
    practice = str(block.get("practice_next") or "").strip()
    perf = str(block.get("performance_next") or "").strip()
    challenge = str(block.get("biggest_challenge") or "").strip()
    what = re.sub(r"\*\*", "", str(block.get("what_matters") or "").strip())

    title = str(record.get("title") or "")
    artist = str(record.get("artist") or "")

    all_chords: list[str] = []
    if sections:
        seen: set[str] = set()
        for chord_list in sections.values():
            for c in chord_list:
                cs = str(c).strip()
                if cs and cs not in seen:
                    seen.add(cs)
                    all_chords.append(cs)

    try:
        from song_performance_coaching import masterclass_lesson_markdown

        masterclass = masterclass_lesson_markdown(
            title,
            instrument=instrument,
            level=level,
            artist=artist,
            sections=sections,
            catalog_key=str(record.get("key") or ""),
            practice_key=practice_key,
        )
        if masterclass:
            meta = build_musician_summary_meta(record, practice_key=practice_key)
            inst_label = _INSTRUMENT_LABELS.get(_instrument_key(instrument), instrument or "your instrument")
            header = (
                f"**Key** — {meta['key']} · **Tempo** — {meta['tempo']} · "
                f"**Time** — {meta['time_signature']} · **Genre** — {meta['genre']} · "
                f"**Level** — {level} · **Instrument** — {inst_label}"
            )
            focus_line = _focus_practice_line(focus, instrument, level, chords=all_chords)
            if focus_line:
                return f"#### Your practice plan\n\n{header}\n\n{masterclass}\n\n{focus_line}"
            return f"#### Your practice plan\n\n{header}\n\n{masterclass}"
    except Exception:
        pass

    try:
        from song_performance_coaching import teacher_intro_for_song

        teacher_open = teacher_intro_for_song(
            title,
            instrument=instrument,
            level=level,
            artist=artist,
            catalog_key=str(record.get("key") or ""),
            practice_key=practice_key,
        )
    except Exception:
        teacher_open = ""

    lines = [
        "#### Your practice plan",
        f"**Key** — {meta['key']} · **Tempo** — {meta['tempo']} · **Time** — {meta['time_signature']} · **Genre** — {meta['genre']}",
        f"**Level** — {level} · **Instrument** — {inst_label}",
    ]
    if teacher_open:
        lines.append(f"**Before you play** — {teacher_open}")
    if what:
        lines.append(f"**What makes this song work** — {what}")
    if challenge:
        lines.append(f"**Watch out for** — {challenge}")
    if tip:
        lines.append(f"**On {inst_label}** — {tip}")
    if practice:
        lines.append(f"**Try next in the practice room** — {practice}")
    if perf:
        lines.append(f"**When you're performance-ready** — {perf}")

    scale = str(block.get("primary_scale") or "").strip()
    improv = str(block.get("improv_approach") or "").strip()
    if scale and level.strip().lower().startswith("adv"):
        lines.append(f"**Optional improv** — {improv or scale}")

    focus_line = _focus_practice_line(focus, instrument, level, chords=all_chords)
    if focus_line:
        lines.append(focus_line)

    return "\n\n".join(lines)


def header_subtitle_for_chart(
    record: dict[str, Any],
    *,
    practice_key: str,
    instrument: str,
    level: str,
    sections: dict[str, list[str]] | None,
    show_internal_notes: bool = False,
) -> str:
    """Lead sheet subtitle — musician summary, not raw arrangement_notes."""
    ext = record.get("extensions") or {}
    raw_notes = str(ext.get("arrangement_notes") or "").strip()
    if show_internal_notes and raw_notes:
        return raw_notes
    return musician_summary_paragraph(
        record,
        sections or {},
        practice_key=practice_key,
        instrument=instrument,
        level=level,
    )
