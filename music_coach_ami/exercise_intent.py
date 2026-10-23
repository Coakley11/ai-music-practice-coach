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
    TECHNIQUE_BEBOP,
    TECHNIQUE_CHROMATIC_APPROACH,
    TECHNIQUE_COMPOSITE,
    TECHNIQUE_ENCLOSURE,
    TECHNIQUE_TARGET_TONE,
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
    r"\b(?:next|following|upcoming|these|those|the|this|current|selected|last|first)\s+(two|three|2|3)\s+(?:consecutive\s+)?(?:chords?|changes)\b"
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
_CHROMATIC_APPROACH_RE = re.compile(
    r"\bchromatic(?:ally)?\s+approach(?:es|ing)?\b|\bchromatic\s+approach[- ]?notes?\b"
    r"|\bapproach(?:es|ing)?\b[^.?!]{0,40}\bchromatic(?:ally)?\b",
    re.I,
)
# "a chord-tone pattern with approach notes": a technique only when nothing else gives "approach notes" another job
# (Slice 3 uses them as a note role: "staccato approach notes", "make the approach notes lighter")
_APPROACH_NOTES_RE = re.compile(r"\bapproach[- ]?(?:notes?|tones?)\b", re.I)
_NEXT_CHORD_RE = re.compile(r"\b(?:the\s+)?next\s+(?:chord|change)\b", re.I)
_ENCLOSURE_RE = re.compile(r"\benclosures?\b|\benclos(?:e|es|ed|ing)\b", re.I)
_BEBOP_RE = re.compile(r"\bbe-?bop\b", re.I)
# Stage 2: which chord tone the line must land on, how it moves, how hard, and where.
_TONE_ALT = r"root|1st|first|third|3rd|fifth|5th|seventh|7th"
_TONE_WORDS = {"root": "root", "1st": "root", "first": "root", "third": "third", "3rd": "third", "fifth": "fifth",
               "5th": "fifth", "seventh": "seventh", "7th": "seventh"}
_TARGET_TONE_RE = re.compile(
    rf"\b(?:target(?:s|ing|ed)?|resolv(?:e|es|ing)\s+(?:to|onto|into)|land(?:s|ing)?\s+on|lead(?:s|ing)?\s+(?:to|into))\s+"
    rf"(?:the\s+)?(?:chord'?s?\s+)?({_TONE_ALT})\b",
    re.I,
)
# Stage 3: composite requests. Which tone a technique aims at ("approach the seventh", "enclosure around the third", "to the
# next chord's third") and where it sits across chords ("of each chord", "the next chord's third").
_TECH_TONE_RE = re.compile(
    rf"\b(?:approach(?:es|ing)?|enclos(?:e|es|ing|ure|ures)|around|toward|towards|to|into)\s+(?:the\s+)?(?:next\s+chord'?s?\s+|chord'?s?\s+)?({_TONE_ALT})\b",
    re.I,
)
_NEXT_TONE_RE = re.compile(rf"\bnext\s+chord'?s?\s+({_TONE_ALT})\b|\b({_TONE_ALT})\s+of\s+the\s+next\s+chord\b", re.I)
_EACH_CHORD_RE = re.compile(r"\b(?:each|every)\s+(?:of\s+the\s+)?chord(?:'?s)?\b|\bat\s+(?:each|every)\s+(?:chord\s+)?change\b", re.I)
# Stage 3b: an enclosure inside the first chord that then resolves into the next ("in the first chord", "start with an enclosure"),
# the tone the resolution lands on, and a "chromatic" bebop line.
_FIRST_CHORD_RE = re.compile(
    r"\b(?:in|within|inside|during|over|around)\s+the\s+first\s+chord\b|\bfirst[- ]chord\b"
    r"|\b(?:start|begin)(?:s|ning)?\s+with\s+an?\s+enclosure\b",
    re.I,
)
_RESOLVE_NEXT_TONE_RE = re.compile(
    rf"\b(?:resolv\w*|lead\w*|land\w*|go(?:es|ing)?|arriv\w*|move\w*)\s+(?:in)?to\s+the\s+({_TONE_ALT})\s+of\s+the\s+next\s+chord\b", re.I)
_ENCLOSE_TONE_RE = re.compile(rf"\b(?:enclos(?:e|es|ing|ure|ures)\s+(?:around|of)|around|enclos(?:e|es|ing))\s+(?:the\s+)?({_TONE_ALT})\b", re.I)
_CHROMATIC_WORD_RE = re.compile(r"\bchromatic(?:ally)?\b", re.I)
_DIRECTION_RE = re.compile(r"\b(ascending|descending|upward|downward|rising|falling)\b", re.I)
_EASIER_RE = re.compile(r"\b(?:easier|simpler)\b", re.I)
_HARDER_RE = re.compile(r"\b(?:harder|more (?:advanced|difficult|challenging))\b", re.I)
_REGISTER_RE = re.compile(r"\b(low(?:er)?|high(?:er)?)\s+register\b", re.I)

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
# "..., then resolve into Cmaj7": the chord the line resolves into (a span of the song's chords starting at the named one)
_CHORD_BEFORE_THEN_RE = re.compile(rf"({_CHORD_SYMBOL})(?![A-Za-z])\s*,?\s+(?i:and\s+)?(?i:then|followed by)\b")
_THEN_CHORD_RE = re.compile(rf"\b(?i:then|and then|followed by)\s+(?:(?i:resolv(?:e|es|ing))\s+)?(?i:into|onto|to)\s+({_CHORD_SYMBOL})(?![A-Za-z])")
# "the third of G7" / "3rd of Dm7": the chord named after a chord-tone word (chord symbols are case-sensitive)
_TONE_OF_CHORD_RE = re.compile(rf"\b(?i:{_TONE_ALT})\s+(?i:of)\s+(?:(?i:the)\s+)?({_CHORD_SYMBOL})(?![A-Za-z])")
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
    m_each = _EACH_CHORD_RE.search(text)
    m_then = _THEN_CHORD_RE.search(text)
    if m_then:
        return {"length": 2, "relationship": "", "cue": m_then.group(0), "numbered": True}
    m_next = _NEXT_CHORD_RE.search(text)
    if m_each and not m_next:
        return {"length": 0, "relationship": "", "cue": m_each.group(0), "numbered": False}
    if m_next:
        # The current chord plus the requested next chord is a two-chord span.
        return {"length": 2, "relationship": "", "cue": m_next.group(0), "numbered": True}
    m = _SPAN_THROUGH_RE.search(text) or _CONNECT_RE.search(text)
    if m:
        return {"length": 0, "relationship": "", "cue": m.group(0), "numbered": False}
    return None


def _chord_anchored(text: str) -> bool:
    """A chord is named ("over G7", "the third of G7") or the request points at the current chord / changes."""
    return bool(_OVER_CHORD_RE.search(text) or _TONE_OF_CHORD_RE.search(text) or _HARMONY_ANCHOR_RE.search(text))


def target_tone_of(question: str) -> str:
    """The chord tone the request names as its target ("targeting the third" -> "third"), or ""."""
    m = _TARGET_TONE_RE.search(_clean(question))
    return _TONE_WORDS[m.group(1).lower()] if m else ""


def target_tone_for(question: str, technique: str) -> tuple[str, str]:
    """(tone, destination). Once a technique is named, "approach the seventh" / "around the third" / "the next chord's third"
    also name the target; destination is "next" or "each" when the request says where it sits across chords."""
    text = _clean(question)
    tone = target_tone_of(text)
    destination = ""
    m_next = _NEXT_TONE_RE.search(text)
    if m_next:
        destination = "next"
        tone = tone or _TONE_WORDS[(m_next.group(1) or m_next.group(2)).lower()]
    if _EACH_CHORD_RE.search(text):
        destination = destination or "each"
    if not tone and technique:
        m = _TECH_TONE_RE.search(text)
        if m:
            tone = _TONE_WORDS[m.group(1).lower()]
    return tone, destination


def _technique(question: str) -> str:
    text = _clean(question)
    found = []
    approach_notes = bool(_APPROACH_NOTES_RE.search(text)) and not (
        _ARTICULATION_RE.search(text) or _DYNAMICS_RE.search(text) or _BLUES_RE.search(text) or _PENT_RE.search(text)
        or _GUIDE_RE.search(text) or re.search(r"\b(?:light|lighter|heavy|heavier|quiet|quieter)\b", text, re.I)
    )
    if _CHROMATIC_APPROACH_RE.search(text) or approach_notes:
        found.append(TECHNIQUE_CHROMATIC_APPROACH)
    if _ENCLOSURE_RE.search(text):
        found.append(TECHNIQUE_ENCLOSURE)
    # "bebop" alone has always meant AMI's own bebop scale practice; it is Mission vocabulary only over a named chord
    if _BEBOP_RE.search(text) and (_chord_anchored(text) or detect_span_request(text) is not None):
        found.append(TECHNIQUE_BEBOP)
    if len(found) > 1:
        return TECHNIQUE_COMPOSITE
    if found:
        return found[0]
    return TECHNIQUE_TARGET_TONE if target_tone_of(text) else ""


def is_span_exercise_request(question: str) -> bool:
    """A supported-vocabulary generation request across several chords."""
    text = _clean(question)
    low = text.lower()
    if not (any(v in low for v in _SPAN_VERBS) or _IMPERATIVE_RE.match(low)):
        return False
    span = detect_span_request(text)
    if span is None:
        return False
    return bool(mission_vocabulary(text) or _technique(text))


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


# Stage 3b: a request that is the technique itself ("Target the third of each chord.", "Enclose the third of G7, ...")
_IMPERATIVE_RE = re.compile(r"^\s*(?:(?:target|enclose|approach)\s+the\b|(?:start|begin)\s+with\s+an?\s+enclosure\b)", re.I)
_TECHNIQUE_VERBS = _GENERATION_VERBS + ("make a ", "make an ", "build me", "build a ", "build an ", "approach the ", "enclose the ")


def is_technique_exercise_request(question: str) -> bool:
    """Stage 2: "make an easier pattern targeting the third", "create an ascending enclosure exercise"."""
    low = _clean(question).lower()
    return (any(v in low for v in _TECHNIQUE_VERBS) or bool(_IMPERATIVE_RE.match(low))) and bool(_technique(question))


def is_exercise_request(question: str) -> bool:
    """A generation request that names Mission vocabulary and a musical object ("blues line")."""
    low = _clean(question).lower()
    if is_span_exercise_request(question) or is_technique_exercise_request(question):
        return True
    if not any(v in low for v in _GENERATION_VERBS):
        return False
    if not mission_vocabulary(question) and not _technique(question):
        return False
    return bool(_form(low) or _technique(question))


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
    technique = _technique(text)
    if vocab == VOCAB_CHORD_TONES and _PENT_RE.search(text) and technique in (TECHNIQUE_CHROMATIC_APPROACH, TECHNIQUE_ENCLOSURE):
        vocab = VOCAB_PENTATONIC   # "a pentatonic framework but approach the chord tones chromatically": the chord tones are the targets
    explicit_vocabulary = bool(vocab)
    if not vocab and technique:
        # Approaches and enclosures resolve to chord tones.  Keep that pitch
        # vocabulary distinct from the requested technique.
        vocab = VOCAB_CHORD_TONES
    form = _form(low)
    both = bool(_BOTH_THIRDS_RE.search(text))
    collection, coll_tonic, coll_mode = _collection_from_text(text, vocab) if vocab else ("", "", "")
    if both and vocab in ("", VOCAB_PENTATONIC) and _BLUES_RE.search(text):
        vocab = VOCAB_BLUES
    explicit_key = _key_from_text(text, coll_tonic, coll_mode)
    chord_m = _OVER_CHORD_RE.search(text)
    explicit_chord = chord_m.group(1) if chord_m else ""
    tone_chord = _TONE_OF_CHORD_RE.search(text)
    if not explicit_chord and tone_chord and technique:
        explicit_chord = tone_chord.group(1)       # "the third of G7": the chord is G7
    target_tone, destination = target_tone_for(text, technique)
    if not target_tone and technique and tone_chord:
        target_tone = _TONE_WORDS[re.match(rf"(?i)({_TONE_ALT})", tone_chord.group(0)).group(1).lower()]
    then_m = _THEN_CHORD_RE.search(text)
    # Stage 3b: an enclosure inside the first chord, resolving into the next one
    inner_enclosure, inner_tone, resolve_tone = False, "", ""
    if technique == TECHNIQUE_ENCLOSURE:
        named_first = bool(then_m and tone_chord and not _NEXT_TONE_RE.search(text))
        if _FIRST_CHORD_RE.search(text) or named_first:
            inner_enclosure = True
            enc_m = _ENCLOSE_TONE_RE.search(text)
            if enc_m:
                inner_tone = _TONE_WORDS[enc_m.group(1).lower()]
            elif tone_chord:
                inner_tone = _TONE_WORDS[re.match(rf"(?i)({_TONE_ALT})", tone_chord.group(0)).group(1).lower()]
            res_m = _RESOLVE_NEXT_TONE_RE.search(text)
            if res_m:
                resolve_tone = _TONE_WORDS[res_m.group(1).lower()]
            target_tone, destination = inner_tone or target_tone, ""   # the tone it encloses; "where" is the first chord
    span_chords: tuple = ()
    if then_m and technique and not (inner_enclosure and not tone_chord):
        before = _CHORD_BEFORE_THEN_RE.search(text)
        first = explicit_chord or (tone_chord.group(1) if tone_chord else "") or (before.group(1) if before else "")
        if first:
            span_chords = (first, then_m.group(1))
    direction_m = _DIRECTION_RE.search(text)
    direction = ""
    if direction_m:
        direction = "ascending" if direction_m.group(1).lower() in ("ascending", "upward", "rising") else "descending"
    difficulty_request = "harder" if _HARDER_RE.search(text) else ("easier" if _EASIER_RE.search(text) else "")
    register_m = _REGISTER_RE.search(text)
    register_request = register_m.group(1).lower()[:3] if register_m else ""
    register_request = {"low": "low", "hig": "high"}.get(register_request, "")
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
    if explicit_vocabulary:
        explicit["vocabulary"] = "user"
    if technique:
        explicit["technique"] = "user"
    if target_tone:
        explicit["target_tone"] = "user"
    if inner_enclosure:
        explicit["inner_enclosure"] = "user"
    if direction:
        explicit["direction"] = "user"
    if difficulty_request:
        explicit["difficulty"] = "user"
    if register_request:
        explicit["register"] = "user"
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
    if technique and vocab == VOCAB_PENTATONIC and route == ROUTE_LEGACY:
        # a technique named with a pentatonic pitch vocabulary is never answered by AMI's plain pentatonic pattern (which has
        # no approaches or enclosures): it goes to the Mission bridge, which builds it or says what is not available
        route, reason = ROUTE_BRIDGE, "pentatonic with a technique uses the Mission phrase vocabulary"
    scope = "section" if (requested_section or getattr(idea, "song_relative", False)) else "single_chord"
    span = detect_span_request(text) if (vocab or technique) else None
    span_length, span_relationship, span_cue, span_unsupported = 0, "", "", ""
    if span:
        # An explicit request for several chords is never answered with one chord: it is built across the span, or the
        # reason it cannot be is said (see exercise_span).
        scope = "span"
        span_length, span_relationship, span_cue = int(span["length"]), str(span["relationship"]), str(span["cue"])
        explicit["scope"] = "user"
        if vocab == VOCAB_BLUES:
            span_unsupported = (
                "blues exercises across several chords are not supported by the span Mission engine; "
                "blues exercises remain single-chord for now"
            )
        elif explicit_chord and not span_chords:
            span_unsupported = f"a chord named in the request ({explicit_chord}) cannot be combined with a span of the song's chords"
        route, reason = ROUTE_BRIDGE, (
            span_unsupported
            or f"{technique or vocab} across {span_length or 'the selected'} chords uses the span Mission engine"
        )
    return ExerciseIntent(
        raw_question=text,
        vocabulary=vocab or VOCAB_DEGREE_PATTERN,
        collection=collection,
        both_thirds=both,
        form=form,
        technique=technique,
        target_tone=target_tone,
        target_destination=destination,
        span_chords=span_chords,
        target_chord=tone_chord.group(1) if (tone_chord and (target_tone or inner_enclosure)) else "",
        inner_enclosure=inner_enclosure,
        inner_tone=inner_tone,
        resolve_tone=resolve_tone,
        chromatic_flavor=bool(technique == TECHNIQUE_BEBOP and _CHROMATIC_WORD_RE.search(text)),
        direction=direction,
        difficulty_request=difficulty_request,
        register_request=register_request,
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
