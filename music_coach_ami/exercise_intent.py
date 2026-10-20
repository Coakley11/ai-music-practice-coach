"""Rule-based exercise-intent parser and engine routing for AMI musical-idea requests.

natural language → ``ExerciseIntent`` (this module) → context (``exercise_context``) → engine
(``exercise_bridge`` for Mission/Motif vocabulary, AMI's own generators otherwise).

Routing is decided by *musical intent*, never by the word "pattern" alone:

* Mission-only vocabulary (guide tones, chord tones, blues with both thirds) always goes to the bridge;
* pentatonic / blues *lines, licks, phrases, motifs* go to the bridge, and so does an *exercise* or
  *pattern* that is anchored to a chord ("over this chord", "over E7");
* a bare "pentatonic/blues pattern", interval patterns (1-3-2-4, thirds ...), sequences, piano-role
  requests, bass lines and section-relative licks stay on AMI's existing generators.
"""

from __future__ import annotations

import re
from typing import Any

from music_coach_ami.exercise_model import (
    ROUTE_BRIDGE,
    ROUTE_LEGACY,
    VOCAB_BLUES,
    VOCAB_CHORD_TONES,
    VOCAB_DEGREE_PATTERN,
    VOCAB_GUIDE_TONES,
    VOCAB_PENTATONIC,
    ExerciseIntent,
)

_GENERATION_VERBS = ("give me", "show me", "write", "make me", "generate", "create", "play me")
_SPAN_VERBS = _GENERATION_VERBS + ("connect",)

_FORM_WORDS = ("line", "lick", "phrase", "motif", "exercise", "riff", "idea", "melody", "improvisation", "pattern")
_PHRASE_FORMS = {"line", "lick", "phrase", "motif", "riff", "melody", "idea", "improvisation"}

_GUIDE_RE = re.compile(r"\bguide[- ]?tones?\b", re.I)
# Other ways to ask for guide tones; they only mean "guide tones" when the request is about several chords.
_GUIDE_SYNONYM_RE = re.compile(
    r"\b(?:thirds?|3rds?)\s*(?:and|&|to|with)\s*(?:the\s+)?(?:sevenths?|7ths?)\b"
    r"|\b(?:sevenths?|7ths?)\s*(?:and|&|to|with)\s*(?:the\s+)?(?:thirds?|3rds?)\b|\bvoice[- ]?leading\b",
    re.I,
)

_NUMBER_WORDS = {"two": 2, "2": 2, "three": 3, "3": 3}
_SPAN_COUNT_RE = re.compile(
    r"\b(?:next|following|upcoming|these|those|the|this|current|selected|last)\s+(two|three|2|3)\s+(?:consecutive\s+)?(?:chords?|changes)\b"
    r"|\b(two|three|2|3)[- ](?:consecutive[- ])?chords?\b",
    re.I,
)
_DASH = r"[\s\-\u2013\u2014]*"
_II_V_I_RE = re.compile(rf"\bii{_DASH}v{_DASH}i\b|\b2{_DASH}5{_DASH}1\b", re.I)
_II_V_RE = re.compile(rf"\bii{_DASH}v\b(?!{_DASH}i\b)|\b2{_DASH}5\b(?!{_DASH}1\b)", re.I)
_V_I_RE = re.compile(r"\bV[\-\u2013\u2014]I\b")
# "through these chords", "over the changes", "across this progression", "connect ..."
_SPAN_THROUGH_RE = re.compile(
    r"\b(?:through|across|along|over)\s+(?:all\s+)?(?:of\s+)?(?:these|those|the|this|my|current|selected)\s+(?:\w+\s+)?(?:chords|changes|progression|harmony)\b"
    r"|\b(?:chord[- ]to[- ]chord|between (?:the )?chords)\b",
    re.I,
)
_CONNECT_RE = re.compile(r"\bconnect(?:s|ing)?\b", re.I)
_CHORD_TONE_RE = re.compile(r"\bchord[- ]?tones?\b", re.I)
_BLUES_RE = re.compile(r"\bblues\b", re.I)
_PENT_RE = re.compile(r"\bpentatonic\b", re.I)

_FLAT3 = r"(?:flat(?:ted)?\s*(?:3rd|third|3)|minor\s*(?:3rd|third)|\bb3\b|♭3|♭\s*3rd)"
_NAT3 = r"(?:(?:major|natural|nat\.?)\s*(?:3rd|third|3)|♮3|\bnat3\b)"
_BOTH_THIRDS_RE = re.compile(rf"{_FLAT3}.{{0,28}}{_NAT3}|{_NAT3}.{{0,28}}{_FLAT3}|\bboth (?:the )?(?:flat |minor |major )?thirds\b", re.I)

_HARMONY_ANCHOR_RE = re.compile(
    r"\bover (?:this|the|that|my|these|current|the current)\b[^.?!]{0,16}\b(?:chord|chords|harmony|changes|progression|ii[- ]?v)\b"
    r"|\bover (?:this|the) (?:current )?(?:chord|harmony)\b|\bover the changes\b",
    re.I,
)
_CHORD_SYMBOL = r"[A-G](?:#|b)?(?:maj|min|m|dim|aug|sus|add|ø|°|\+|-)?\d*(?:[#b]\d+)*(?:/[A-G](?:#|b)?)?"
_OVER_CHORD_RE = re.compile(rf"\bover\s+({_CHORD_SYMBOL})(?![A-Za-z])")
_KEY_IN_RE = re.compile(r"\bin\s+(?:the\s+key\s+of\s+)?([A-G](?:#|b)?)\s*(major|minor|maj|min|m)?(?![A-Za-z])")
_KEY_IN_LOWER_RE = re.compile(r"\bin\s+(?:the\s+key\s+of\s+)?([a-g](?:#|b)?)\s+(major|minor)\b", re.I)
_COLL_RE = re.compile(
    r"(?:\b([A-G](?:#|b)?)\s*[- ]?(major|minor|maj|min)?\s+)?(blues|pentatonic)\b(?:\s+scale)?", re.I
)
_QUALIFIED_COLL_RE = re.compile(r"\b(major|minor)\s+(blues|pentatonic)\b", re.I)
_LENGTH_RE = re.compile(r"\b(\d{1,2}|one|two|three|four|eight|twelve|sixteen)[- ]bars?\b", re.I)

_LEVEL_WORDS = (
    (re.compile(r"\b(very easy|super easy|easy|simple|beginner)\b", re.I), "Beginner"),
    (re.compile(r"\b(difficult|hard|advanced|challenging)\b", re.I), "Advanced"),
    (re.compile(r"\bintermediate\b", re.I), "Intermediate"),
)

_ARTICULATION_RE = re.compile(r"\b(staccato|legato|slurred?|slurs?|accent(?:ed|s)?|tongued|marcato|tenuto|portato)\b", re.I)
_DYNAMICS_RE = re.compile(r"\b(crescendo|decrescendo|diminuendo|piano|forte|mezzo|dynamics?|louder|softer|swell)\b|\b(?:pp|mp|mf|ff)\b", re.I)


def _clean(value: object) -> str:
    return str(value or "").strip()


def detect_span_request(question: str) -> dict[str, Any] | None:
    """A request about several consecutive chords, as structure: length (0 = not stated), relationship, the words used.

    ``numbered`` / ``relationship`` requests are explicit ("the next two chords", "this ii-V-I"); an unnumbered one
    ("through these chords", "connect the thirds and sevenths") asks for a span without saying how long.
    """
    text = _clean(question)
    m_rel = _II_V_I_RE.search(text)
    if m_rel:
        return {"length": 3, "relationship": "ii_V_I", "cue": m_rel.group(0), "numbered": True}
    m_count = _SPAN_COUNT_RE.search(text)
    count = _NUMBER_WORDS[(m_count.group(1) or m_count.group(2)).lower()] if m_count else 0
    m_two = _II_V_RE.search(text)
    if m_two:
        return {"length": 2, "relationship": "ii_V", "cue": m_two.group(0), "numbered": True}
    m_cad = _V_I_RE.search(text)
    if m_cad:
        return {"length": 2, "relationship": "V_I", "cue": m_cad.group(0), "numbered": True}
    if m_count:
        return {"length": count, "relationship": "", "cue": m_count.group(0), "numbered": True}
    m = _SPAN_THROUGH_RE.search(text) or _CONNECT_RE.search(text)
    if m:
        return {"length": 0, "relationship": "", "cue": m.group(0), "numbered": False}
    return None


def is_span_exercise_request(question: str) -> bool:
    """A guide-tone request across several chords ("guide-tone line through these chords", "connect the thirds and sevenths")."""
    text = _clean(question)
    low = text.lower()
    if not any(v in low for v in _SPAN_VERBS):
        return False
    if not (_GUIDE_RE.search(text) or _GUIDE_SYNONYM_RE.search(text)):
        return False
    return detect_span_request(text) is not None


def mission_vocabulary(question: str) -> str:
    """The Mission/Motif vocabulary the question names (first match wins), or ''."""
    text = _clean(question)
    if _GUIDE_RE.search(text):
        return VOCAB_GUIDE_TONES
    if _GUIDE_SYNONYM_RE.search(text) and detect_span_request(text) is not None:
        return VOCAB_GUIDE_TONES
    if _CHORD_TONE_RE.search(text):
        return VOCAB_CHORD_TONES
    if _BLUES_RE.search(text):
        return VOCAB_BLUES
    if _PENT_RE.search(text):
        return VOCAB_PENTATONIC
    return ""


def _form(low: str) -> str:
    for word in _FORM_WORDS:
        for m in re.finditer(rf"\b{word}s?\b", low):
            if word == "line" and re.search(r"\b(?:bass|base)[- ]?$", low[: m.start()]):
                continue
            return word
    return ""


def is_exercise_request(question: str) -> bool:
    """A generation request that names Mission vocabulary and a musical object ("blues line")."""
    low = _clean(question).lower()
    if is_span_exercise_request(question):
        return True
    if not any(v in low for v in _GENERATION_VERBS):
        return False
    if not mission_vocabulary(question):
        return False
    return bool(_form(low))


def _length_bars(low: str) -> int | None:
    m = _LENGTH_RE.search(low)
    if not m:
        return None
    word = m.group(1).lower()
    table = {"one": 1, "two": 2, "three": 3, "four": 4, "eight": 8, "twelve": 12, "sixteen": 16}
    try:
        return max(1, min(32, table[word] if word in table else int(word)))
    except ValueError:
        return None


def _collection_from_text(question: str, vocabulary: str) -> tuple[str, str, str]:
    """(collection label, tonic named with it, mode named with it). Any part may be ''."""
    if vocabulary not in (VOCAB_BLUES, VOCAB_PENTATONIC):
        return "", "", ""
    kind = "blues" if vocabulary == VOCAB_BLUES else "pentatonic"
    tonic = mode = ""
    for m in _COLL_RE.finditer(question):
        if m.group(3).lower() != kind:
            continue
        raw_tonic = _clean(m.group(1))
        # Only an upper-case letter is a tonic: "a blues line" is an article, "A blues" a key.
        if raw_tonic and raw_tonic[0].isupper():
            tonic = raw_tonic[0].upper() + raw_tonic[1:]
            word = _clean(m.group(2)).lower()
            if word:
                mode = "minor" if word.startswith("min") else "major"
        break
    q = _QUALIFIED_COLL_RE.search(question)
    if q and q.group(2).lower() == kind:
        mode = q.group(1).lower()
    label = f"{mode} {kind}" if mode else ""
    return label, tonic, mode


def _key_from_text(question: str, tonic: str, mode: str) -> str:
    if tonic:
        return tonic + ("m" if mode == "minor" else "")
    m = _KEY_IN_RE.search(question)
    if m:
        word = _clean(m.group(2)).lower()
        return m.group(1) + ("m" if word in ("minor", "min", "m") else "")
    m = _KEY_IN_LOWER_RE.search(question)  # "in a minor": after "in" a lower-case letter is a key
    if m:
        tonic = m.group(1)[0].upper() + m.group(1)[1:]
        return tonic + ("m" if m.group(2).lower() == "minor" else "")
    return ""


def _level_override(low: str) -> str:
    for rx, label in _LEVEL_WORDS:
        if rx.search(low):
            return label
    return ""


def parse_exercise_intent(question: str, idea: Any = None, *, requested_section: str = "") -> ExerciseIntent:
    """Parse ``question`` (and the already-resolved ``MusicalIdeaRequest``) into an ``ExerciseIntent``."""
    text = _clean(question)
    low = text.lower()
    vocab = mission_vocabulary(text)
    form = _form(low)
    both = bool(_BOTH_THIRDS_RE.search(text))
    collection, coll_tonic, coll_mode = _collection_from_text(text, vocab) if vocab else ("", "", "")
    if both and vocab in ("", VOCAB_PENTATONIC) and _BLUES_RE.search(text):
        vocab = VOCAB_BLUES
    explicit_key = _key_from_text(text, coll_tonic, coll_mode)
    chord_m = _OVER_CHORD_RE.search(text)
    explicit_chord = chord_m.group(1) if chord_m else ""
    if vocab == VOCAB_BLUES and both:
        # Only the major blues collection holds both the flat and the natural 3rd.
        collection = "major blues"
    art = _ARTICULATION_RE.search(text)
    dyn = _DYNAMICS_RE.search(text)
    level = _level_override(low) or _clean(getattr(idea, "difficulty", "")).capitalize()
    bars = _length_bars(low)  # only a length the user actually named (the resolver adds a default)

    try:  # structured articulation / dynamics request (Slice 3); the words themselves stay in *_request below
        from music_coach_ami.exercise_expression import has_rules, parse_expression

        expr = parse_expression(low)
        expr.pop("spans", None)
        expression = expr if has_rules(expr) else {}
    except ImportError:
        expression = {}
    explicit: dict[str, str] = {}
    if vocab:
        explicit["vocabulary"] = "user"
    if collection:
        explicit["collection"] = "user"
    if both:
        explicit["both_thirds"] = "user"
    if explicit_key:
        explicit["key"] = "user"
    if explicit_chord:
        explicit["chord"] = "user"
    if level:
        explicit["level"] = "user"
    if bars:
        explicit["length_bars"] = "user"
    if getattr(idea, "rhythm", ""):
        explicit["rhythm"] = "user"
    if form:
        explicit["form"] = "user"
    if art:
        explicit["articulation"] = "user"
    if dyn:
        explicit["dynamics"] = "user"

    route, reason = route_exercise(
        vocab=vocab, form=form, both_thirds=both, low=low, explicit_chord=explicit_chord, idea=idea,
        requested_section=requested_section,
    )
    scope = "section" if (requested_section or getattr(idea, "song_relative", False)) else "single_chord"
    span = detect_span_request(text) if vocab else None
    span_length, span_relationship, span_cue, span_unsupported = 0, "", "", ""
    if span and (vocab == VOCAB_GUIDE_TONES or span["numbered"]):
        # An explicit request for several chords is never answered with one chord: it is built across the span, or the
        # reason it cannot be is said (see exercise_span).
        scope = "span"
        span_length, span_relationship, span_cue = int(span["length"]), str(span["relationship"]), str(span["cue"])
        explicit["scope"] = "user"
        if vocab != VOCAB_GUIDE_TONES:
            span_unsupported = (
                f"{vocab.replace('_', ' ')} lines across several chords are not available yet; "
                "multi-chord exercises are guide-tone lines for now"
            )
        elif explicit_chord:
            span_unsupported = f"a chord named in the request ({explicit_chord}) cannot be combined with a span of the song's chords"
        route, reason = ROUTE_BRIDGE, (
            span_unsupported or f"guide-tone line across {span_length or 'the selected'} chords uses the span Mission engine"
        )
    return ExerciseIntent(
        raw_question=text,
        vocabulary=vocab or VOCAB_DEGREE_PATTERN,
        collection=collection,
        both_thirds=both,
        form=form,
        scope=scope,
        explicit_key=explicit_key,
        explicit_chord=explicit_chord,
        level_override=level,
        length_bars=bars,
        rhythm_request=_clean(getattr(idea, "rhythm", "")),
        articulation_request=art.group(1).lower() if art else "",
        dynamics_request=dyn.group(0).lower() if dyn else "",
        expression=expression,
        span_length=span_length,
        span_relationship=span_relationship,
        span_cue=span_cue,
        span_unsupported=span_unsupported,
        engine_route=route,
        route_reason=reason,
        explicit_fields=explicit,
    )


def route_exercise(
    *, vocab: str, form: str, both_thirds: bool, low: str, explicit_chord: str, idea: Any, requested_section: str
) -> tuple[str, str]:
    """(engine route, reason). See the module docstring for the rules."""
    if not vocab:
        return ROUTE_LEGACY, "no Mission/Motif vocabulary named"
    object_type = _clean(getattr(idea, "object_type", ""))
    if _clean(getattr(idea, "interval_pattern", "")):
        return ROUTE_LEGACY, "interval pattern stays on AMI's pattern generator"
    if object_type in {"sequence", "bass_line", "accompaniment"} or _clean(getattr(idea, "piano_role", "")):
        return ROUTE_LEGACY, f"{object_type or 'piano-role'} request stays on AMI's own generators"
    mission_only = vocab in (VOCAB_GUIDE_TONES, VOCAB_CHORD_TONES) or both_thirds
    section_relative = bool(requested_section) or bool(getattr(idea, "song_relative", False))
    if section_relative and not mission_only:
        return ROUTE_LEGACY, "section-relative lick stays on AMI's section generator"
    if mission_only:
        why = "guide/chord-tone vocabulary" if vocab in (VOCAB_GUIDE_TONES, VOCAB_CHORD_TONES) else "both thirds in blues"
        return ROUTE_BRIDGE, f"{why} exists only in the Mission/Motif engines"
    anchored = bool(explicit_chord) or bool(_HARMONY_ANCHOR_RE.search(low))
    if form in _PHRASE_FORMS:
        return ROUTE_BRIDGE, f"{vocab} {form} uses the Mission phrase vocabulary"
    if anchored:
        return ROUTE_BRIDGE, f"{vocab} {form or 'exercise'} anchored to a chord uses the Mission phrase vocabulary"
    return ROUTE_LEGACY, f"generic {vocab} {form or 'exercise'} keeps AMI's degree-pattern meaning"
