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


# ---------------------------------------------------------------------------
# Manual alignment editing  (Stage 3)
# ---------------------------------------------------------------------------

def reassign_syllable(
    alignment: dict[str, Any],
    event_idx: int,
    syllable_index: int,
    events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Change the syllable assigned to a single melody event.

    Returns a modified copy.  Rejects assignment to rest events when
    *events* is supplied for validation.  Does not change alignment status.
    """
    a = copy.deepcopy(alignment)
    assignments = a.get("event_assignments") or []
    if event_idx < 0 or event_idx >= len(assignments):
        return a
    if events and event_idx < len(events):
        ev = events[event_idx]
        if bool(ev.get("is_rest") or str(ev.get("pitch") or "").lower() == "rest"):
            return a
    syllables = a.get("syllables") or []
    if syllable_index < 0 or syllable_index >= len(syllables):
        return a
    assignments[event_idx] = {"syllable_index": syllable_index, "type": "syllable"}
    return a


def set_melisma(
    alignment: dict[str, Any],
    event_idx: int,
    source_syllable_index: int,
    events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Mark *event_idx* as a melisma continuation of *source_syllable_index*.

    Returns a modified copy.  Rejects assignment to rest events.
    """
    a = copy.deepcopy(alignment)
    assignments = a.get("event_assignments") or []
    if event_idx < 0 or event_idx >= len(assignments):
        return a
    if events and event_idx < len(events):
        ev = events[event_idx]
        if bool(ev.get("is_rest") or str(ev.get("pitch") or "").lower() == "rest"):
            return a
    assignments[event_idx] = {"syllable_index": source_syllable_index, "type": "melisma"}
    return a


def clear_assignment(
    alignment: dict[str, Any],
    event_idx: int,
) -> dict[str, Any]:
    """Set an event to unassigned.  Returns a modified copy."""
    a = copy.deepcopy(alignment)
    assignments = a.get("event_assignments") or []
    if event_idx < 0 or event_idx >= len(assignments):
        return a
    cur = assignments[event_idx]
    if cur.get("type") == "rest":
        return a
    assignments[event_idx] = {"syllable_index": -1, "type": "unassigned"}
    return a


def split_syllable(
    alignment: dict[str, Any],
    syllable_idx: int,
    split_position: int,
) -> dict[str, Any]:
    """Split the syllable at *syllable_idx* into two at character *split_position*.

    Adjusts all ``syllable_index`` references in ``event_assignments`` and
    recalculates word metadata (``word_syllable_count``, ``position_in_word``,
    ``is_word_end``) for affected syllables.  Returns a modified copy.
    """
    a = copy.deepcopy(alignment)
    syllables = a.get("syllables") or []
    if syllable_idx < 0 or syllable_idx >= len(syllables):
        return a
    syl = syllables[syllable_idx]
    text = syl["text"]
    if split_position <= 0 or split_position >= len(text):
        return a

    left = dict(syl, text=text[:split_position], is_word_end=False)
    right = dict(syl, text=text[split_position:])
    right["position_in_word"] = left["position_in_word"] + 1
    syllables[syllable_idx] = left
    syllables.insert(syllable_idx + 1, right)

    _repair_word_metadata(syllables, syl["word_index"])

    for asn in a.get("event_assignments") or []:
        si = asn.get("syllable_index", -1)
        if si > syllable_idx:
            asn["syllable_index"] = si + 1
    return a


def merge_syllables(
    alignment: dict[str, Any],
    syllable_idx: int,
) -> dict[str, Any]:
    """Merge syllable at *syllable_idx* with the next one.

    Both must belong to the same word.  Concatenates text, recalculates
    word metadata, and adjusts all ``syllable_index`` references.
    Returns a modified copy.
    """
    a = copy.deepcopy(alignment)
    syllables = a.get("syllables") or []
    if syllable_idx < 0 or syllable_idx + 1 >= len(syllables):
        return a
    left = syllables[syllable_idx]
    right = syllables[syllable_idx + 1]
    if left["word_index"] != right["word_index"]:
        return a

    merged = dict(left, text=left["text"] + right["text"])
    merged["is_word_end"] = right.get("is_word_end", True)
    merged["is_line_end"] = right.get("is_line_end", False) or left.get("is_line_end", False)
    syllables[syllable_idx] = merged
    syllables.pop(syllable_idx + 1)

    _repair_word_metadata(syllables, left["word_index"])

    for asn in a.get("event_assignments") or []:
        si = asn.get("syllable_index", -1)
        if si == syllable_idx + 1:
            asn["syllable_index"] = syllable_idx
            if asn.get("type") == "syllable":
                pass
        elif si > syllable_idx + 1:
            asn["syllable_index"] = si - 1
    return a


def _repair_word_metadata(
    syllables: list[dict[str, Any]],
    word_index: int,
) -> None:
    """Recalculate ``word_syllable_count``, ``position_in_word``, and
    ``is_word_end`` for every syllable belonging to *word_index*."""
    word_syls = [s for s in syllables if s["word_index"] == word_index]
    count = len(word_syls)
    for pos, s in enumerate(word_syls):
        s["word_syllable_count"] = count
        s["position_in_word"] = pos
        s["is_word_end"] = pos == count - 1


def validate_alignment_for_confirm(
    alignment: dict[str, Any],
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Check an alignment for problems before confirmation.

    Returns a list of ``{"level": "warning"|"error", "message": str}``.
    """
    issues: list[dict[str, Any]] = []
    assignments = alignment.get("event_assignments") or []
    syllables = alignment.get("syllables") or []

    if not assignments:
        issues.append({"level": "error", "message": "No event assignments exist."})
        return issues

    rest_assigned = 0
    unassigned_pitched = 0
    assigned_count = 0
    for i, asn in enumerate(assignments):
        atype = asn.get("type", "unassigned")
        si = asn.get("syllable_index", -1)
        ev = events[i] if i < len(events) else {}
        is_rest = bool(ev.get("is_rest") or str(ev.get("pitch") or "").lower() == "rest")

        if atype in ("syllable", "melisma") and is_rest:
            rest_assigned += 1
        if atype == "unassigned" and not is_rest:
            unassigned_pitched += 1
        if atype == "syllable":
            assigned_count += 1

    if rest_assigned:
        issues.append({
            "level": "error",
            "message": f"{rest_assigned} rest{'s' if rest_assigned != 1 else ''} "
                       f"{'have' if rest_assigned != 1 else 'has'} a syllable assigned. "
                       "Rests cannot carry lyrics.",
        })

    if assigned_count == 0 and syllables:
        issues.append({
            "level": "error",
            "message": "No syllables are assigned to melody notes.",
        })

    remaining = len(syllables) - assigned_count
    if remaining > 0:
        issues.append({
            "level": "warning",
            "message": f"{remaining} syllable{'s' if remaining != 1 else ''} "
                       f"{'are' if remaining != 1 else 'is'} not assigned to any note.",
        })

    if unassigned_pitched and assigned_count > 0:
        issues.append({
            "level": "warning",
            "message": f"{unassigned_pitched} pitched note{'s' if unassigned_pitched != 1 else ''} "
                       f"{'have' if unassigned_pitched != 1 else 'has'} no syllable.",
        })

    return issues


def restore_confirmed_snapshot(alignment: dict[str, Any]) -> dict[str, Any]:
    """Create a new provisional alignment from the confirmed snapshot.

    Preserves the snapshot itself so confirmation history is not lost.
    Returns a modified copy, or the original unchanged if no snapshot exists.
    """
    snapshot = alignment.get("confirmed_snapshot")
    if not isinstance(snapshot, dict):
        return alignment

    a = copy.deepcopy(alignment)
    a["syllables"] = copy.deepcopy(snapshot.get("syllables") or [])
    a["event_assignments"] = copy.deepcopy(snapshot.get("event_assignments") or [])
    a["melody_fingerprint"] = snapshot.get("melody_fingerprint", "")
    a["lyrics_fingerprint"] = snapshot.get("lyrics_fingerprint", "")
    a["status"] = "provisional"
    a["warnings"] = ["Restored from previous confirmed alignment for revision."]
    return a


def describe_staleness(alignment: dict[str, Any]) -> str:
    """Human-readable explanation of what changed to make the alignment stale."""
    if alignment.get("status") != "stale":
        return ""

    mel_changed = bool(
        alignment.get("current_melody_fingerprint")
        and alignment.get("confirmed_melody_fingerprint")
        and alignment["current_melody_fingerprint"] != alignment["confirmed_melody_fingerprint"]
    )
    lyr_changed = bool(
        alignment.get("current_lyrics_fingerprint")
        and alignment.get("confirmed_lyrics_fingerprint")
        and alignment["current_lyrics_fingerprint"] != alignment["confirmed_lyrics_fingerprint"]
    )

    if not mel_changed and not lyr_changed:
        mel_changed = bool(
            alignment.get("current_melody_fingerprint")
            and alignment.get("melody_fingerprint")
            and alignment["current_melody_fingerprint"] != alignment["melody_fingerprint"]
        )
        lyr_changed = bool(
            alignment.get("current_lyrics_fingerprint")
            and alignment.get("lyrics_fingerprint")
            and alignment["current_lyrics_fingerprint"] != alignment["lyrics_fingerprint"]
        )

    if mel_changed and lyr_changed:
        return "Both melody and lyrics have changed since this alignment was created."
    if mel_changed:
        return "The melody has changed since this alignment was created."
    if lyr_changed:
        return "The lyrics have changed since this alignment was created."
    return "The alignment is marked stale."


# ---------------------------------------------------------------------------
# Synchronized lyric highlighting — syllable timeline
# ---------------------------------------------------------------------------

def alignment_syllable_timeline(
    alignment: dict[str, Any],
    events: list[dict[str, Any]],
    *,
    bpm: int,
    count_in_sec: float = 0.0,
) -> list[dict[str, Any]]:
    """Build a timed syllable list for karaoke-style highlighting.

    Each entry: ``{"text": str, "start_sec": float, "end_sec": float,
    "syllable_index": int, "is_melisma": bool}``.

    Only syllable and melisma assignments produce entries; rests and
    unassigned notes are skipped.
    """
    syllables = list(alignment.get("syllables") or [])
    assignments = list(alignment.get("event_assignments") or [])
    if not syllables or not assignments or not events:
        return []

    beat_sec = 60.0 / max(40.0, float(bpm or 96))
    offset = max(0.0, float(count_in_sec))

    timeline: list[dict[str, Any]] = []
    for ev_i, asgn in enumerate(assignments):
        atype = str(asgn.get("type") or "")
        if atype not in ("syllable", "melisma"):
            continue
        syl_idx = int(asgn.get("syllable_index", -1))
        if syl_idx < 0 or syl_idx >= len(syllables):
            continue
        if ev_i >= len(events):
            continue

        ev = events[ev_i] if isinstance(events[ev_i], dict) else {}
        try:
            start_beat = float(ev.get("beat") or 0.0)
        except (TypeError, ValueError):
            start_beat = 0.0
        dur_beats = max(0.05, float(ev.get("duration_beats") or 1.0))
        start_sec = offset + start_beat * beat_sec
        end_sec = start_sec + dur_beats * beat_sec

        syl = syllables[syl_idx]
        text = str(syl.get("text") or "") if isinstance(syl, dict) else str(syl)

        timeline.append({
            "text": text,
            "start_sec": round(start_sec, 4),
            "end_sec": round(end_sec, 4),
            "syllable_index": syl_idx,
            "is_melisma": atype == "melisma",
        })

    return _merge_melisma_spans(timeline)


def _merge_melisma_spans(
    timeline: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Extend syllable spans to cover their following melisma notes."""
    if not timeline:
        return timeline
    merged: list[dict[str, Any]] = []
    for entry in timeline:
        if entry["is_melisma"] and merged and merged[-1]["syllable_index"] == entry["syllable_index"]:
            merged[-1]["end_sec"] = entry["end_sec"]
        else:
            merged.append(dict(entry))
    return merged
