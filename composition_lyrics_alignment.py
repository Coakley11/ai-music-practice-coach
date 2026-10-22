"""Lyrics-to-melody alignment engine for Composition Studio.

Pure functions — no Streamlit, no AI calls, no side-effects.
All state lives in the Composition document at ``section["lyrics_alignment"]``.

Alignment statuses:
    unaligned   — no mapping created yet
    provisional — estimated mapping awaiting user review
    confirmed   — user explicitly approved the alignment
    stale       — lyrics or melody changed since confirmation
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALIGNMENT_STATUSES = ("unaligned", "provisional", "confirmed", "stale")

_VOWELS = set("aeiouyAEIOUY")
_VOWEL_PATTERN = re.compile(r"[aeiouy]+", re.IGNORECASE)
_WORD_SPLIT = re.compile(r"(\s+)")
_CONTRACTION = re.compile(r"(\w+)'(\w+)", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Syllable segmentation
# ---------------------------------------------------------------------------

def _is_silent_e(word: str, pos: int) -> bool:
    """Heuristic: trailing 'e' after a consonant is usually silent."""
    if pos != len(word) - 1:
        return False
    if word[pos].lower() != "e":
        return False
    if pos == 0:
        return False
    return word[pos - 1].lower() not in _VOWELS


def segment_word_into_syllables(word: str) -> list[str]:
    """Split a single word into approximate syllables using vowel clusters.

    This is a heuristic suitable for English song lyrics.  It intentionally
    errs on the side of *fewer* syllables (merge rather than split) so the
    user's manual correction step has less to fix.  The output is never
    linguistically exact — it is labeled *provisional*.
    """
    if not word or not word.strip():
        return []
    clean = word.strip()
    if len(clean) <= 2:
        return [clean]

    vowel_runs: list[tuple[int, int]] = []
    for m in _VOWEL_PATTERN.finditer(clean):
        s, e = m.start(), m.end()
        if _is_silent_e(clean, e - 1) and vowel_runs:
            continue
        vowel_runs.append((s, e))

    if not vowel_runs:
        return [clean]
    if len(vowel_runs) == 1:
        return [clean]

    syllables: list[str] = []
    for i, (vs, ve) in enumerate(vowel_runs):
        if i == 0:
            start = 0
        else:
            prev_ve = vowel_runs[i - 1][1]
            gap = clean[prev_ve:vs]
            if len(gap) <= 1:
                start = prev_ve
            else:
                start = prev_ve + len(gap) // 2
        if i == len(vowel_runs) - 1:
            end = len(clean)
        else:
            next_vs = vowel_runs[i + 1][0]
            gap_after = clean[ve:next_vs]
            if len(gap_after) <= 1:
                end = next_vs
            else:
                end = ve + len(gap_after) // 2
        syllables.append(clean[start:end])

    if not syllables:
        return [clean]
    return syllables


def tokenize_lyrics(text: str) -> list[dict[str, Any]]:
    """Break lyric text into syllable tokens preserving word structure.

    Returns a list of syllable dicts::

        {"text": "love", "word_index": 1, "position_in_word": 0,
         "word_syllable_count": 1, "is_word_end": True}
    """
    if not text or not text.strip():
        return []

    syllables: list[dict[str, Any]] = []
    word_index = 0
    for line_index, line in enumerate(text.splitlines() or [text]):
        line_start = len(syllables)
        words = re.findall(r"[A-Za-z'’à-ÿ]+(?:[-‐][A-Za-z'’]+)*|[^\s]+", line)
        for word in words:
            parts: list[str] = []
            explicitly_hyphenated = "-" in word or "‐" in word
            if explicitly_hyphenated:
                sub_words = re.split(r"[-‐]", word)
                for sw in sub_words:
                    parts.extend(segment_word_into_syllables(sw))
            else:
                parts = segment_word_into_syllables(word)
            if not parts:
                parts = [word]
            uncertain = len(parts) > 1 and not explicitly_hyphenated
            for pi, part in enumerate(parts):
                syllables.append({
                    "text": part,
                    "word_index": word_index,
                    "position_in_word": pi,
                    "word_syllable_count": len(parts),
                    "is_word_end": pi == len(parts) - 1,
                    "line_index": line_index,
                    "is_line_end": False,
                    "segmentation_uncertain": uncertain,
                })
            word_index += 1
        if len(syllables) > line_start:
            syllables[-1]["is_line_end"] = True
    return syllables


# ---------------------------------------------------------------------------
# Fingerprints
# ---------------------------------------------------------------------------

def melody_fingerprint(
    events: list[dict[str, Any]],
    phrases: list[dict[str, Any]] | None = None,
) -> str:
    """Deterministic fingerprint of melody events for staleness detection.

    Captures pitch, duration, rest status, and ordering.  Instrument
    transposition and Practice Key do not affect these values because
    they are the composition's authoritative (Original Key) events.
    """
    canonical: list[tuple[Any, ...]] = []
    for ev in (events or []):
        if not isinstance(ev, dict):
            continue
        pitch = str(ev.get("pitch") or "C4")
        dur = round(float(ev.get("duration_beats") or 1.0), 4)
        rest = bool(ev.get("is_rest") or pitch.lower() == "rest")
        beat = round(float(ev.get("beat") if ev.get("beat") is not None else 0.0), 4)
        measure = int(ev.get("measure") or 1)
        # Persisted IDs are ownership metadata, not musical content.  Only
        # structural markers belong in the fingerprint so an ID regeneration
        # does not make an otherwise unchanged alignment stale.
        phrase_marker = (
            ev.get("phrase_index"),
            bool(ev.get("phrase_start")),
            bool(ev.get("phrase_end")),
        )
        canonical.append((pitch, dur, rest, beat, measure, phrase_marker))
    phrase_structure = []
    for phrase in phrases or []:
        if not isinstance(phrase, dict):
            continue
        phrase_structure.append(" ".join(str(phrase.get("notes") or "").split()))
    raw = json.dumps(
        {"events": canonical, "phrases": phrase_structure},
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def lyrics_fingerprint(text: str) -> str:
    """Deterministic fingerprint of lyrics text for staleness detection."""
    # Spaces within a line are cosmetic; line boundaries carry phrase intent.
    normalized = "\n".join(" ".join(line.split()) for line in (text or "").splitlines())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Alignment data model
# ---------------------------------------------------------------------------

def empty_alignment() -> dict[str, Any]:
    """Return a blank lyrics_alignment structure."""
    return {
        "status": "unaligned",
        "syllables": [],
        "event_assignments": [],
        "melody_fingerprint": "",
        "lyrics_fingerprint": "",
        "confirmed_at": None,
        "confirmed_melody_fingerprint": None,
        "confirmed_lyrics_fingerprint": None,
        "confirmed_snapshot": None,
        "current_melody_fingerprint": None,
        "current_lyrics_fingerprint": None,
        "warnings": [],
    }


def get_alignment(section: dict[str, Any]) -> dict[str, Any]:
    """Read the alignment from a section, creating a blank if absent."""
    alignment = section.get("lyrics_alignment")
    if not isinstance(alignment, dict):
        return empty_alignment()
    for key, default in empty_alignment().items():
        alignment.setdefault(key, default)
    return alignment


def set_alignment(section: dict[str, Any], alignment: dict[str, Any]) -> None:
    """Write alignment data to a section dict."""
    section["lyrics_alignment"] = alignment


# ---------------------------------------------------------------------------
# Alignment engine
# ---------------------------------------------------------------------------

def _classify_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Tag each event with index and rest/pitched status."""
    result = []
    for i, ev in enumerate(events or []):
        if not isinstance(ev, dict):
            continue
        is_rest = bool(ev.get("is_rest") or str(ev.get("pitch") or "").lower() == "rest")
        dur = float(ev.get("duration_beats") or 1.0)
        result.append({
            "index": i,
            "is_rest": is_rest,
            "duration_beats": dur,
            "pitch": str(ev.get("pitch") or "C4"),
            "beat": float(ev.get("beat") or 0),
            "measure": int(ev.get("measure") or 1),
            "phrase_start": bool(ev.get("phrase_start")),
            "phrase_end": bool(ev.get("phrase_end")),
        })
    return result


def _is_long_note(dur: float, meter: str = "4/4") -> bool:
    """Heuristic: a note longer than one beat is 'long' and may sustain a syllable."""
    return dur >= 2.0


def align_lyrics_to_melody(
    lyrics_text: str,
    events: list[dict[str, Any]],
    *,
    meter: str = "4/4",
    phrases: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Create a provisional syllable-to-note alignment.

    Strategy (left-to-right with musical heuristics):
    1. Tokenize lyrics into syllables.
    2. Walk pitched notes, assigning one syllable per note.
    3. Rests get type "rest" — no syllable assigned.
    4. When syllables run out, remaining notes in the same phrase get
       "melisma" extending the last assigned syllable. Notes after a
       phrase-ending rest remain unassigned rather than inventing a melisma.
    5. When notes run out but syllables remain, flag a mismatch warning.
    6. Long notes following a syllable assignment are marked as potential
       sustain points (but still get the next syllable if available).

    Returns a complete alignment dict ready for ``set_alignment()``.
    """
    syllables = tokenize_lyrics(lyrics_text)
    classified = _classify_events(events)
    mel_fp = melody_fingerprint(events, phrases)
    lyr_fp = lyrics_fingerprint(lyrics_text)

    if not syllables and not classified:
        alignment = empty_alignment()
        alignment["melody_fingerprint"] = mel_fp
        alignment["lyrics_fingerprint"] = lyr_fp
        return alignment

    if not syllables:
        assignments = []
        for cev in classified:
            if cev["is_rest"]:
                assignments.append({"syllable_index": -1, "type": "rest"})
            else:
                assignments.append({"syllable_index": -1, "type": "unassigned"})
        return {
            "status": "provisional",
            "syllables": [],
            "event_assignments": assignments,
            "melody_fingerprint": mel_fp,
            "lyrics_fingerprint": lyr_fp,
            "confirmed_at": None,
            "confirmed_melody_fingerprint": None,
            "confirmed_lyrics_fingerprint": None,
            "warnings": ["No lyrics available for alignment."],
        }

    if not classified:
        return {
            "status": "provisional",
            "syllables": syllables,
            "event_assignments": [],
            "melody_fingerprint": mel_fp,
            "lyrics_fingerprint": lyr_fp,
            "confirmed_at": None,
            "confirmed_melody_fingerprint": None,
            "confirmed_lyrics_fingerprint": None,
            "warnings": ["No melody events available for alignment."],
        }

    assignments: list[dict[str, Any]] = []
    syl_cursor = 0
    last_assigned_syl = -1
    warnings: list[str] = []
    if any(bool(s.get("segmentation_uncertain")) for s in syllables):
        warnings.append(
            "Automatic syllable splitting is provisional for one or more words. "
            "Review the sung syllables for musical accuracy."
        )

    for cev in classified:
        if cev["is_rest"]:
            assignments.append({"syllable_index": -1, "type": "rest"})
            # A full-beat rest after the lyric phrase has ended is a musical
            # boundary. Do not carry the last syllable across it onto later
            # untexted notes.
            if cev["duration_beats"] >= 1.0 and (
                syl_cursor >= len(syllables)
                or (
                    last_assigned_syl >= 0
                    and bool(syllables[last_assigned_syl].get("is_line_end"))
                )
            ):
                last_assigned_syl = -1
            continue

        if cev.get("phrase_start") and syl_cursor >= len(syllables):
            last_assigned_syl = -1

        if syl_cursor < len(syllables):
            assignments.append({
                "syllable_index": syl_cursor,
                "type": "syllable",
            })
            last_assigned_syl = syl_cursor
            syl_cursor += 1
        else:
            if last_assigned_syl >= 0:
                assignments.append({
                    "syllable_index": last_assigned_syl,
                    "type": "melisma",
                })
            else:
                assignments.append({"syllable_index": -1, "type": "unassigned"})

    remaining_syllables = len(syllables) - syl_cursor
    if remaining_syllables > 0:
        warnings.append(
            f"{remaining_syllables} syllable{'s' if remaining_syllables != 1 else ''} "
            f"could not be assigned — the melody has fewer pitched notes than lyric syllables. "
            f"Consider extending the melody or editing the lyrics."
        )

    melisma_count = sum(1 for a in assignments if a["type"] == "melisma")
    if melisma_count > 0:
        warnings.append(
            f"{melisma_count} note{'s' if melisma_count != 1 else ''} assigned as melisma "
            f"(syllable held across multiple notes). Review for musical accuracy."
        )
    unassigned_count = sum(1 for a in assignments if a["type"] == "unassigned")
    if unassigned_count > 0:
        warnings.append(
            f"{unassigned_count} pitched note{'s' if unassigned_count != 1 else ''} "
            "remain without lyrics after a phrase break."
        )

    return {
        "status": "provisional",
        "syllables": syllables,
        "event_assignments": assignments,
        "melody_fingerprint": mel_fp,
        "lyrics_fingerprint": lyr_fp,
        "confirmed_at": None,
        "confirmed_melody_fingerprint": None,
        "confirmed_lyrics_fingerprint": None,
        "confirmed_snapshot": None,
        "current_melody_fingerprint": None,
        "current_lyrics_fingerprint": None,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Confirmation and staleness
# ---------------------------------------------------------------------------

def confirm_alignment(
    alignment: dict[str, Any],
    *,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Mark the current alignment as user-confirmed.

    Records the melody and lyrics fingerprints at confirmation time
    so future changes can be detected as stale.
    """
    if timestamp is None:
        import datetime
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    alignment["status"] = "confirmed"
    alignment["confirmed_at"] = timestamp
    alignment["confirmed_melody_fingerprint"] = alignment.get("melody_fingerprint", "")
    alignment["confirmed_lyrics_fingerprint"] = alignment.get("lyrics_fingerprint", "")
    alignment["confirmed_snapshot"] = {
        "syllables": copy.deepcopy(alignment.get("syllables") or []),
        "event_assignments": copy.deepcopy(alignment.get("event_assignments") or []),
        "melody_fingerprint": alignment.get("melody_fingerprint", ""),
        "lyrics_fingerprint": alignment.get("lyrics_fingerprint", ""),
        "confirmed_at": timestamp,
    }
    alignment["current_melody_fingerprint"] = None
    alignment["current_lyrics_fingerprint"] = None
    alignment["warnings"] = [w for w in alignment.get("warnings", []) if "Review" not in w]
    return alignment


def check_staleness(
    alignment: dict[str, Any],
    current_events: list[dict[str, Any]],
    current_lyrics: str,
    current_phrases: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Check whether a provisional or confirmed alignment has become stale.

    Compares current melody/lyrics fingerprints against the confirmed
    fingerprints.  If either has changed, marks the alignment stale and
    adds appropriate warnings.  Does NOT destroy the confirmed mapping —
    it remains as a reference for realignment.
    """
    status = str(alignment.get("status") or "unaligned")
    if status not in {"provisional", "confirmed"}:
        return alignment

    current_mel_fp = melody_fingerprint(current_events, current_phrases)
    current_lyr_fp = lyrics_fingerprint(current_lyrics)
    if status == "confirmed":
        baseline_mel = alignment.get("confirmed_melody_fingerprint", "")
        baseline_lyr = alignment.get("confirmed_lyrics_fingerprint", "")
    else:
        baseline_mel = alignment.get("melody_fingerprint", "")
        baseline_lyr = alignment.get("lyrics_fingerprint", "")

    melody_changed = bool(baseline_mel and current_mel_fp != baseline_mel)
    lyrics_changed = bool(baseline_lyr and current_lyr_fp != baseline_lyr)

    if not melody_changed and not lyrics_changed:
        return alignment

    alignment["status"] = "stale"
    warnings = [
        str(w) for w in (alignment.get("warnings") or [])
        if "has changed since this alignment" not in str(w)
    ]
    if melody_changed:
        warnings.append(
            "Melody has changed since this alignment was created. "
            "The syllable-to-note mapping may no longer be accurate."
        )
    if lyrics_changed:
        warnings.append(
            "Lyrics have changed since this alignment was created. "
            "The syllable assignments may no longer match the current text."
        )
    alignment["current_melody_fingerprint"] = current_mel_fp
    alignment["current_lyrics_fingerprint"] = current_lyr_fp
    alignment["warnings"] = warnings
    return alignment


# ---------------------------------------------------------------------------
# ABC lyric line generation
# ---------------------------------------------------------------------------

def alignment_to_abc_w_lines(
    alignment: dict[str, Any],
    events: list[dict[str, Any]],
    *,
    meter: str = "4/4",
) -> str:
    """Generate ABC ``w:`` lyric lines from an alignment.

    ABC lyric syntax (per abcjs / ABC standard 2.1):
        - Syllable tokens separated by spaces
        - Hyphen after a syllable: next syllable is part of the same word
        - ``_`` : extend the preceding syllable across another note (melisma)
        - ``*`` : skip an untexted note without extending a syllable
        - ``|`` : barline alignment marker
        - A rest in the melody has no lyric token (rests are skipped by
          ``w:`` in standard ABC — the lyric line only addresses notes)

    Returns a string like ``w: I love- New York-`` ready to append after
    the ABC music line.  Returns ``""`` if no alignment data exists.
    """
    syllables = alignment.get("syllables") or []
    assignments = alignment.get("event_assignments") or []

    if not syllables or not assignments:
        return ""

    from composition_hum_transcription import parse_meter
    num, _den = parse_meter(meter)
    bar_len = float(num)

    tokens: list[str] = []
    beats_in_bar = 0.0

    for i, asn in enumerate(assignments):
        ev = events[i] if i < len(events) else {}
        dur = float(ev.get("duration_beats") or 1.0)
        is_rest = bool(ev.get("is_rest") or str(ev.get("pitch") or "").lower() == "rest")

        if is_rest:
            beats_in_bar += dur
            if beats_in_bar >= bar_len - 1e-6:
                tokens.append("|")
                beats_in_bar = 0.0
            continue

        atype = asn.get("type", "unassigned")
        syl_idx = asn.get("syllable_index", -1)

        if atype == "syllable" and 0 <= syl_idx < len(syllables):
            syl = syllables[syl_idx]
            text = syl["text"]
            if not syl.get("is_word_end", True):
                text += "-"
            tokens.append(text)
        elif atype == "melisma":
            tokens.append("_")
        else:
            tokens.append("*")

        beats_in_bar += dur
        if beats_in_bar >= bar_len - 1e-6:
            tokens.append("|")
            beats_in_bar = 0.0

    if tokens and tokens[-1] == "|":
        tokens = tokens[:-1]

    if not tokens:
        return ""
    return "w: " + " ".join(tokens)


def build_abc_with_lyrics(
    abc_without_lyrics: str,
    alignment: dict[str, Any],
    events: list[dict[str, Any]],
    *,
    meter: str = "4/4",
) -> str:
    """Append ``w:`` lyric lines to an existing ABC string.

    If alignment is empty or unaligned, returns the ABC unchanged.
    This is a non-destructive wrapper — it does not modify the original
    ABC generation pipeline.
    """
    if not alignment or alignment.get("status") not in {"provisional", "confirmed"}:
        return abc_without_lyrics

    w_line = alignment_to_abc_w_lines(alignment, events, meter=meter)
    if not w_line:
        return abc_without_lyrics

    return abc_without_lyrics.rstrip() + "\n" + w_line


# ---------------------------------------------------------------------------
# Section-level convenience
# ---------------------------------------------------------------------------

def _section_alignment_inputs(
    section: dict[str, Any],
) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    """Return accepted lyrics plus authoritative melody data for a section."""
    lyrics_block = section.get("lyrics") or {}
    lyrics_text = str(lyrics_block.get("raw_text") or "")
    if not lyrics_text.strip():
        lines = lyrics_block.get("lines") or []
        lyrics_text = "\n".join(str(line) for line in lines)
    melody_block = section.get("melody") or {}
    events = list(melody_block.get("events") or [])
    phrases = list(melody_block.get("phrases") or [])
    return lyrics_text, events, phrases


def refresh_section_alignment_status(section: dict[str, Any]) -> bool:
    """Mark a stored mapping stale when its authoritative inputs changed.

    Returns True only when the stored alignment record was changed. The event
    assignments themselves are preserved so a confirmed mapping remains
    recoverable for the future manual editor.
    """
    stored = section.get("lyrics_alignment")
    if not isinstance(stored, dict):
        return False
    before = alignment_to_json(stored)
    lyrics_text, events, phrases = _section_alignment_inputs(section)
    check_staleness(stored, events, lyrics_text, phrases)
    return alignment_to_json(stored) != before


def align_section(
    section: dict[str, Any],
    *,
    meter: str = "4/4",
) -> dict[str, Any]:
    """Create a provisional alignment for a section's current lyrics and melody.

    Reads lyrics from ``section["lyrics"]["raw_text"]`` and melody from
    ``section["melody"]["events"]``.  Does not overwrite a confirmed
    alignment — call ``realign_section`` for that.
    """
    lyrics_text, events, phrases = _section_alignment_inputs(section)

    existing = get_alignment(section)
    if existing.get("status") in {"provisional", "confirmed", "stale"}:
        return check_staleness(existing, events, lyrics_text, phrases)

    alignment = align_lyrics_to_melody(lyrics_text, events, meter=meter, phrases=phrases)
    set_alignment(section, alignment)
    return alignment


def realign_section(
    section: dict[str, Any],
    *,
    meter: str = "4/4",
) -> dict[str, Any]:
    """Force a new provisional alignment, preserving the previous confirmed record."""
    lyrics_text, events, phrases = _section_alignment_inputs(section)
    existing = get_alignment(section)

    alignment = align_lyrics_to_melody(lyrics_text, events, meter=meter, phrases=phrases)
    snapshot = existing.get("confirmed_snapshot")
    has_confirmed_record = bool(
        isinstance(snapshot, dict)
        or existing.get("status") == "confirmed"
        or existing.get("confirmed_at")
        or existing.get("confirmed_melody_fingerprint")
        or existing.get("confirmed_lyrics_fingerprint")
    )
    if has_confirmed_record:
        if not isinstance(snapshot, dict):
            snapshot = {
                "syllables": copy.deepcopy(existing.get("syllables") or []),
                "event_assignments": copy.deepcopy(existing.get("event_assignments") or []),
                "melody_fingerprint": existing.get("confirmed_melody_fingerprint")
                or existing.get("melody_fingerprint", ""),
                "lyrics_fingerprint": existing.get("confirmed_lyrics_fingerprint")
                or existing.get("lyrics_fingerprint", ""),
                "confirmed_at": existing.get("confirmed_at"),
            }
        alignment["confirmed_snapshot"] = copy.deepcopy(snapshot)
    set_alignment(section, alignment)
    return alignment


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def alignment_to_json(alignment: dict[str, Any]) -> str:
    """Serialize alignment to a JSON string for persistence."""
    return json.dumps(alignment, separators=(",", ":"), sort_keys=True)


def alignment_from_json(data: str) -> dict[str, Any]:
    """Deserialize alignment from a JSON string."""
    try:
        result = json.loads(data)
        if not isinstance(result, dict):
            return empty_alignment()
        for key, default in empty_alignment().items():
            result.setdefault(key, default)
        return result
    except (json.JSONDecodeError, TypeError):
        return empty_alignment()


def section_alignment_is_compatible(section: dict[str, Any]) -> bool:
    """Check if a section from an older schema (no lyrics_alignment) is safe.

    Returns True always — older documents without alignment data are
    fully compatible; the alignment is simply absent/unaligned.
    """
    return True
