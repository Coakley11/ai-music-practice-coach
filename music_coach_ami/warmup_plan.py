"""AMI adaptive warmups, Slice 1: the request, the plan, its durations, its revisions and its undo history.

A warmup is an ordered list of real exercises (``warmup_engine``) with a time budget. Everything is deterministic: the musician's words choose
the families, the level and the length; the notes come from the engines; the times come from the actual tempo, the notated length, the
number of plays and the rests between them.

State: one record per browser session under ``_ami_conv_warmup`` (purged with the rest of the conversation by ``session_scope``). It holds up
to ``MAX_VERSIONS`` complete plans, a cursor for undo / redo, which view is open ("whole plan" or one exercise) and whether the warmup is the
thing the conversation is currently about. The record is shaped as one warmup *session* that contains its exercises, so a later practice-log
step can store it as one entry; the practice log itself is not touched here.

Honest limits (said in the answers, not hidden): Slice 1 warmups are key- and instrument-based. They do not look at a song's chords, even
when the request names a song; a revision that is not one of the supported operations is refused in words and the warmup is left as it was.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections.abc import MutableMapping
from typing import Any

from music_coach_ami import warmup_engine as we
from music_coach_ami import warmup_chordline as wc
from music_coach_ami import warmup_song as ws
from music_coach_ami.session_scope import ensure_owner, owner_token
from music_coach_ami.types import CoachIntent, CoachResponse

STATE_KEY = "_ami_conv_warmup"
MAX_VERSIONS = 12
DEFAULT_MINUTES = 10
MIN_MINUTES, MAX_MINUTES = 2, 30
MAX_REPS = 6
SONG_FAMILIES = ("guide_tones", "chord_tones", "approach_notes")
FAMILY_CAP = {"long_tones": 3, "scale": 5, "intervals": 4, "articulation": 4, "guide_tones": 5, "chord_tones": 5, "approach_notes": 4, "bass_arpeggio": 4}   # variants a family can supply before plays are repeated instead
MAX_COMFORT_REPS = 3        # more plays of one exercise than this and another variant of the family is added instead
MAX_ITEMS = 12
TOLERANCE = 0.08            # a plan's total stays within 8% (or 20 s) of the requested length when the exercises allow it
LEVEL_UP = {"Beginner": "Intermediate", "Intermediate": "Advanced"}
LEVEL_DOWN = {"Advanced": "Intermediate", "Intermediate": "Beginner"}
KEY_SHIFTS = (0, 5, 7, 2, 10, 3)       # the same mode a fourth, a fifth, ... up: variants of a key-based exercise

_NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
                 "twelve": 12, "fifteen": 15, "twenty": 20, "twenty-five": 25, "thirty": 30}
_ORDINALS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10,
             "1st": 1, "2nd": 2, "3rd": 3, "4th": 4, "5th": 5, "6th": 6, "7th": 7, "8th": 8, "9th": 9, "10th": 10}

_FAMILY_WORDS: dict[str, str] = {
    r"long[\s-]?tones?": "long_tones", r"sustained\s+(?:notes?|tones?)": "long_tones", r"scales?|scalar": "scale",
    r"intervals?|interval\s+(?:work|training)|thirds|fourths|fifths|sixths|sevenths|octaves": "intervals",
    r"articulat\w*|tongu\w*|staccato|legato|slurs?|slurred|two[\s-]?note": "articulation",
    r"guide[\s-]?tones?": "guide_tones",
    r"arpeggios?|chord[\s-]?tones?": "chord_tones",
    r"approach(?:es)?(?:[\s-](?:notes?|tones?))?|enclosures?": "approach_notes",
}
_FAMILY_ANY = "|".join(f"(?:{p})" for p in _FAMILY_WORDS)


def _family_of(text: str) -> str:
    for pattern, family in _FAMILY_WORDS.items():
        if re.fullmatch(pattern, text.strip(), re.I):
            return family
    for pattern, family in _FAMILY_WORDS.items():
        if re.search(pattern, text, re.I):
            return family
    return ""


def _clean(value: object) -> str:
    return str(value or "").strip()


# ---------------------------------------------------------------- reading a request

_WARM = re.compile(r"\bwarm(?:ing)?[\s-]?(?:me\s+|us\s+|myself\s+)?ups?\b|\bwarm(?:ing)?\s+(?:me\s+|us\s+|myself\s+)?up\b", re.I)
_ASK_VERB = re.compile(r"\b(?:give|make|create|build|design|write|put\s+together|set\s+up|plan|prepare|show|need|want|get|generate|produce|"
                       r"i[’']?d\s+like|can\s+(?:i|you|we)|could\s+(?:i|you|we)|would\s+you|please|let[’']?s|start|build\s+me|do)\b", re.I)
_QUESTION_START = re.compile(r"^\s*(?:why|what(?:\s+is|[’']s)?|how\s+(?:do|does|long|often|should)|is\s+it|should\s+i|do\s+i|does)\b", re.I)
_EXERCISE_NOUN = re.compile(r"\b(?:exercises?|drills?|routine|patterns?|practice|work)\b", re.I)
_DRILL_PHRASE = re.compile(r"\b(?:long[\s-]?tones?|two[\s-]?note|articulation|tonguing)\b", re.I)
_DRILL_NOUN = re.compile(r"\b(?:exercises?|drills?|routine)\b", re.I)
_NOT_WARMUP_TOPIC = re.compile(r"\b(?:dorian|phrygian|lydian|mixolydian|aeolian|locrian|melodic\s+minor|harmonic\s+minor|modes?|guide[\s-]?tones?|chords?|chord\s+tones?|over\s+[a-g][#b]?\d?|over\s+(?:the|a|an|this|that)\b|patterns?|licks?|lines?|pentatonic|blues|"
                               r"the\s+same|same\s+\w+\s+with|progressions?|arpeggios?|bass|melody|solo|song)\b", re.I)
_UNVERIFIED_WORD = re.compile(r"\b(trombone|violin|viola|cello|guitar|bass|oboe|horn|bassoon|ukulele|banjo|recorder|voice|vocals?|singing|harp|tuba|"
                              r"euphonium|flugelhorn|piccolo|mandolin|harmonica|accordion|organ|keyboard|drums?)\b", re.I)
_INSTRUMENT = re.compile(r"\b(?:(soprano|alto|tenor|bari(?:tone)?)\s+sax(?:ophone)?|(sax(?:ophone)?)|(flute)|(piano)|(trumpet)|(clarinet)|(bass(?: guitar)?)(?!\s+trumpet))\b", re.I)
_LEVEL = [("Beginner", re.compile(r"\b(?:beginner|beginning|novice|easy|simple|basic|starter)\b", re.I)),
          ("Advanced", re.compile(r"\b(?:advanced|hard|difficult|challenging|expert)\b", re.I)),
          ("Intermediate", re.compile(r"\b(?:intermediate|medium|moderate)\b", re.I))]
_PROGRESSIVE = re.compile(r"\b(?:increasingly|progressively|gradually|steadily)\s+(?:more\s+)?(?:difficult|challenging|advanced|hard(?:er)?|wide(?:r)?|demanding)\b|"
                          r"\b(?:getting|growing|building)\s+(?:more\s+)?(?:difficult|challenging|harder|wider)\b", re.I)
_MINUTES = re.compile(r"\b(\d+(?:\.\d+)?|(?:" + "|".join(_NUMBER_WORDS) + r"))[\s-]*(?:minutes?|mins?)\b", re.I)
_HALF_HOUR = re.compile(r"\bhalf[\s-]?(?:an?\s+)?hour\b|\b30[\s-]?min", re.I)
_HOUR = re.compile(r"\b(?:an?|one|1)[\s-]?hour\b", re.I)
_KEY = re.compile(r"\bin\s+(?:the\s+key\s+of\s+)?([A-G](?:#|b|♯|♭)?)(?:\s*(major|minor|maj|min|m)\b)?(?=[\s.,!?;]|$)")
_NEG = re.compile(r"\b(?:no|without|skip|exclude|excluding|avoid|except|not\s+(?:any|the)|don[’']?t\s+(?:include|add|want|need|use|do|give)(?:\s+(?:me|any))?|"
                  r"do\s+not\s+(?:include|add|use)|leave\s+out|nothing\s+with|(?:but|and|or|plus)\s+not|instead\s+of|rather\s+than|other\s+than)\s+(?:any\s+|the\s+|more\s+|of\s+the\s+|the\s+)?"
                  r"(?:" + _FAMILY_ANY + r")(?:\s+(?:exercises?|drills?|work))?", re.I)
_INTERVAL_WORD = {"seconds": r"(?:diatonic\s+)?seconds|2nds", "thirds": r"thirds|third(?!\s+(?:one|exercise|item|drill|part)\b)|3rds", "fourths": r"fourths|fourth(?!\s+(?:one|exercise|item|drill|part)\b)|4ths", "fifths": r"fifths|fifth(?!\s+(?:one|exercise|item|drill|part)\b)|5ths",
                  "sixths": r"sixths|sixth(?!\s+(?:one|exercise|item|drill|part)\b)|6ths", "sevenths": r"sevenths|seventh(?!\s+(?:one|exercise|item|drill|part)\b)|7ths", "octaves": r"octaves?|8ves"}
_WIDER_THAN = re.compile(r"\b(?:wider|larger|bigger|greater|beyond|above|bigger\s+than|more\s+than)\s+(?:than\s+)?(?:just\s+)?(" + "|".join(_INTERVAL_WORD.values()) + r")\b", re.I)
_SONG_AWARE = re.compile(r"\b(?:solo(?:ing)?|improvis\w*|chord\s+(?:changes|progression|tones?)|the\s+changes|these\s+chords|guide[\s-]?tones?|"
                         r"over\s+(?:the\s+)?(?:chorus|verse|bridge|section|chart|changes)|the\s+chorus|this\s+song|the\s+song)\b", re.I)
_TONE_FOCUS = re.compile(r"\b(?:tone|sound|breath(?:ing)?|embouchure|intonation|centered|resonan\w*)\b", re.I)
_TECH_FOCUS = re.compile(r"\b(?:fingers?|finger\s+technique|fingering|dexterity|agility|technique|technical|speed|facility|evenness)\b", re.I)
_ARTIC_WORD = re.compile(r"\b(?:articulat\w*|tongu\w*|two[\s-]?note)\b", re.I)


def _number(text: str) -> float | None:
    t = text.lower()
    if t in _NUMBER_WORDS:
        return float(_NUMBER_WORDS[t])
    try:
        return float(t)
    except ValueError:
        return None


def _minutes_in(text: str) -> float | None:
    m = _MINUTES.search(text)
    if m:
        return _number(m.group(1))
    if _HALF_HOUR.search(text):
        return 30.0
    if _HOUR.search(text):
        return 60.0
    return None


def is_warmup_request(question: str) -> bool:
    """A request for a warmup, or for the warmup-style drills Slice 1 builds (long tones, two-note and articulation exercises)."""
    q = _clean(question)
    if not q:
        return False
    if is_song_request(q):
        return True
    low = q.lower()
    asks = bool(_ASK_VERB.search(low))
    if re.match(r"^\s*(?:please\s+)?(?:can\s+you\s+|could\s+you\s+)?warm\s+(?:me|us|myself)\s+up\b|^\s*(?:let.?s\s+)?warm\s+up\b", low):
        return True
    if _WARM.search(low):
        if _QUESTION_START.match(low) and not asks:
            return False
        if re.search(r"\b(?:why|benefits?|should\s+i|is\s+it\s+(?:good|important|necessary)|what\s+is)\b", low) and not re.search(r"\b(?:give|make|create|build|plan|need|want)\b", low):
            return False
        return asks or bool(_EXERCISE_NOUN.search(low)) or bool(_MINUTES.search(low))
    if _DRILL_PHRASE.search(low) and _DRILL_NOUN.search(low) and not _NOT_WARMUP_TOPIC.search(low) \
            and re.search(r"\b(?:give|make|create|build|write|need|want|show|get|generate|i[’']?d\s+like)\b", low):
        return not _QUESTION_START.match(low)
    return False


def parse_request(question: str) -> dict[str, Any]:
    """Everything the musician's words fix about the warmup. Empty / None fields are left to the page and to the defaults."""
    q = _clean(question)
    low = q.lower()
    out: dict[str, Any] = {"raw": q, "instrument_word": "", "sax_type_word": "", "unverified": "", "level": "", "minutes": None, "key": "", "families": [],
                           "excluded": [], "intervals": [], "artic": [], "focus": "", "song_aware": False, "derived_from": "", "progressive": False}
    m = _INSTRUMENT.search(q)
    if m:
        if m.group(1):
            out["sax_type_word"] = m.group(1).lower()
            out["instrument_word"] = "saxophone"
        else:
            word = (m.group(2) or m.group(3) or m.group(4) or m.group(5) or m.group(6) or m.group(7)).lower()
            out["instrument_word"] = "saxophone" if word.startswith("sax") else "bass" if word.startswith("bass") else word
    else:
        u = _UNVERIFIED_WORD.search(q)
        if u:
            out["unverified"] = u.group(1).lower()
    progressive = bool(_PROGRESSIVE.search(low))
    level_text = _PROGRESSIVE.sub(" ", low)
    for level, rx in _LEVEL:
        if rx.search(level_text):
            out["level"] = level
            break
    out["minutes"] = _minutes_in(low)
    km = _KEY.search(q)
    if km:
        tonic = km.group(1).replace("♯", "#").replace("♭", "b")
        mode = (km.group(2) or "").lower()
        out["key"] = tonic + ("m" if mode in ("minor", "min", "m") else "")
    # families: what is asked for, minus what is excluded
    excluded: list[str] = []
    stripped = low
    for nm in _NEG.finditer(low):
        fam = _family_of(nm.group(0))
        if fam and fam not in excluded:
            excluded.append(fam)
    stripped = _NEG.sub(" ", low)
    found: list[str] = []
    for pattern, family in _FAMILY_WORDS.items():
        if re.search(rf"\b(?:{pattern})\b", stripped, re.I) and family not in found:
            found.append(family)
    wider = _WIDER_THAN.search(stripped)
    if wider:
        base = next((i for i, pat in _INTERVAL_WORD.items() if re.fullmatch(pat, wider.group(1), re.I)), "")
        order = list(we.INTERVALS)
        if base:
            out["intervals"] = order[order.index(base) + 1: order.index(base) + 4]
        stripped = stripped[:wider.start()] + " intervals " + stripped[wider.end():]
        if "intervals" not in found and re.search(r"\bintervals?\b", low):
            found.append("intervals")
    for interval, pattern in _INTERVAL_WORD.items():
        if not wider and re.search(rf"\b(?:{pattern})\b", stripped, re.I) and "intervals" in found and interval not in out["intervals"]:
            out["intervals"].append(interval)
    if re.search(r"\btwo[\s-]?note\b", stripped):
        out["artic"].append("two_note")
    if re.search(r"\b(?:tongu\w*|repeated\s+notes?)\b", stripped) and "two_note" not in out["artic"]:
        out["artic"].append("repeated")
    if re.search(r"\bslur\w*\b", stripped) and re.search(r"\btongu\w*\b", stripped):
        out["artic"].append("slur_tongue")
    if re.search(r"\bstaccato\b|\blegato\b|\btenuto\b|\baccents?\b", stripped):
        out["artic"].append("contrast")
    out["artic"] = [a for i, a in enumerate(out["artic"]) if a not in out["artic"][:i]]
    focus = ""
    derived = ""
    if not found:
        if _TECH_FOCUS.search(stripped) and _TONE_FOCUS.search(stripped):
            found, focus, derived = ["long_tones", "scale", "intervals"], "technique", "tone and finger technique"
        elif _TECH_FOCUS.search(stripped):
            found, focus, derived = ["scale", "intervals", "articulation"], "technique", "finger technique"
            out["artic"] = out["artic"] or ["two_note"]
        elif _TONE_FOCUS.search(stripped):
            found, focus, derived = ["long_tones", "scale"], "tone", "tone"
    out["families"] = [f for f in found if f not in excluded]
    out["excluded"] = excluded
    out["focus"] = focus
    out["derived_from"] = derived
    out["song_aware"] = bool(_SONG_AWARE.search(low))
    out["progressive"] = progressive
    return out


# ---------------------------------------------------------------- reading a revision

OP_SHORTER, OP_LONGER, OP_MINUTES, OP_HARDER, OP_EASIER, OP_LEVEL = "shorter", "longer", "minutes", "harder", "easier", "level"
OP_REMOVE_FAMILY, OP_REMOVE_ITEM, OP_ADD_FAMILY, OP_MORE_FAMILY = "remove_family", "remove_item", "add_family", "more_family"
OP_ITEM_SLOWER, OP_ITEM_FASTER, OP_ITEM_TEMPO, OP_WHOLE_SLOWER, OP_WHOLE_FASTER = "item_slower", "item_faster", "item_tempo", "whole_slower", "whole_faster"
OP_INTERVAL, OP_NEXT, OP_PREV, OP_ALL, OP_GOTO, OP_UNDO, OP_REDO, OP_UNSUPPORTED = "interval", "next", "prev", "all", "goto", "undo", "redo", "unsupported"
OP_SECTION, OP_BARS, OP_TONES, OP_SMOOTH, OP_INSTRUMENT, OP_EXPLAIN = "section", "bars", "tones", "smooth", "instrument", "explain"
OP_ARP_START, OP_APPROACH_KIND, OP_ITEM_LEVEL = "arp_start", "approach_kind", "item_level"
SONG_OPS = {OP_SECTION, OP_BARS, OP_TONES, OP_SMOOTH, OP_EXPLAIN, OP_ARP_START, OP_APPROACH_KIND}

_UNDO = re.compile(r"^\s*(?:please\s+)?(?:undo|revert)(?:\s+(?:that|it|this|the\s+last\s+(?:change|one|edit)|my\s+last\s+change))?[\s.!]*$|^\s*go\s+back\s+to\s+(?:before|the\s+previous\s+version)[\s.!]*$", re.I)
_REDO = re.compile(r"^\s*(?:please\s+)?(?:redo|do\s+(?:that|it)\s+again|put\s+(?:that|it)\s+back)(?:\s+(?:that|it|this))?[\s.!]*$", re.I)
_NEXT = re.compile(r"^\s*(?:please\s+)?(?:next(?:\s+(?:exercise|one|item|drill))?|go\s+(?:on\s+)?to\s+the\s+next(?:\s+(?:exercise|one))?|move\s+on(?:\s+to\s+the\s+next(?:\s+exercise)?)?|"
                   r"continue|on\s+to\s+the\s+next(?:\s+exercise)?|show\s+(?:me\s+)?the\s+next\s+(?:exercise|one))[\s.!]*$", re.I)
_PREV = re.compile(r"^\s*(?:please\s+)?(?:previous(?:\s+(?:exercise|one|item))?|go\s+back(?:\s+to\s+the\s+previous(?:\s+exercise)?)?|back(?:\s+one)?|"
                   r"show\s+(?:me\s+)?the\s+previous\s+(?:exercise|one))[\s.!]*$", re.I)
_ALL = re.compile(r"\b(?:show|see|display|open|go\s+(?:back\s+)?to|return\s+to|back\s+to)\s+(?:me\s+)?(?:the\s+)?(?:whole|full|entire|complete|all\s+of\s+the|all)\s*(?:warm[\s-]?up|plan|list|exercises)?\b|"
                  r"\b(?:overview|whole\s+plan|full\s+plan)\b", re.I)
_GOTO = re.compile(r"\b(?:show|go\s+to|jump\s+to|open|take\s+me\s+to|start\s+(?:with|at)|play)\s+(?:me\s+)?(?:the\s+)?(?:exercise\s*#?\s*(\d+)|(\w+)\s+exercise|number\s+(\d+))\b", re.I)
_REF_NUM = re.compile(r"\b(?:exercise|number|no\.?|item|drill)\s*#?\s*(\d+)\b|#\s*(\d+)\b", re.I)
_REF_ORD = re.compile(r"\b(?:the\s+)?(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|last|1st|2nd|3rd|4th|5th|6th|7th|8th|9th|10th)\s+(?:exercise|one|item|drill|part)\b", re.I)
_ORD_WORD = r"(?:first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|last|1st|2nd|3rd|4th|5th|6th|7th|8th|9th|10th)"
_PRESERVE = re.compile(r"(?:[,;]\s*)?(?:\b(?:but|and|while|though)\s+)?\b(?:keep|leave|don[’']?t\s+(?:change|touch|alter)|do\s+not\s+(?:change|touch|alter))\s+"
                       r"(?:the\s+)?(?:" + _ORD_WORD + r"(?:\s+(?:exercise|one|item|drill|part))?|(?:exercise|number|item|drill)\s*#?\s*\d+)\s*(?:exactly\s+|just\s+)?"
                       r"(?:as\s+(?:it\s+is|is|they\s+are)|alone|the\s+same|unchanged|untouched)?", re.I)


def _preserved_ref(text: str) -> dict[str, Any]:
    m = re.search(_ORD_WORD, text, re.I)
    if m:
        w = m.group(0).lower()
        return {"index": -1 if w == "last" else _ORDINALS[w]}
    m = re.search(r"\d+", text)
    return {"index": int(m.group(0))} if m else {}


_VERB_REMOVE = r"(?:remove|drop|delete|take\s+out|get\s+rid\s+of|skip|cut|lose|ditch|leave\s+out|eliminate)"
_VERB_ADD = r"(?:add|include|put\s+in|throw\s+in|bring\s+in|work\s+in|insert)"
_SLOWER = re.compile(r"\b(?:slower|slow(?:\s+(?:it\s+)?down)?|more\s+slowly|reduce\s+the\s+tempo|lower\s+the\s+tempo)\b", re.I)
_FASTER = re.compile(r"\b(?:faster|quicker|speed(?:\s+(?:it\s+)?up)?|increase\s+the\s+tempo|raise\s+the\s+tempo)\b", re.I)
_BPM = re.compile(r"\b(\d{2,3})\s*(?:bpm|beats\s+per\s+minute)\b", re.I)
_OTHER_INTENT = re.compile(r"\b(?:patterns?|over|chords?|changes|song|blue\s+bossa|licks?|lines?|pentatonic|blues|improv\w*|progressions?|arpeggios?|bass|melody|solo|"
                           r"what\s+is|why|how)\b", re.I)
_WARMUP_TALK = re.compile(r"\bwarm[\s-]?up\b|\bexercises?\b|\bthe\s+(?:whole|entire|full)\s+(?:thing|plan)\b", re.I)


def ref_from(text: str) -> dict[str, Any]:
    """Which exercise a phrase points at: {'index': 2} (1-based, 'last' = -1), {'family': 'scale'} or {}."""
    m = _REF_NUM.search(text)
    if m:
        return {"index": int(m.group(1) or m.group(2))}
    m = _REF_ORD.search(text)
    if m:
        w = m.group(1).lower()
        return {"index": -1 if w == "last" else _ORDINALS[w]}
    m = re.search(r"\bthe\s+(" + _FAMILY_ANY + r")\b", text, re.I)
    if m:
        fam = _family_of(m.group(1))
        if fam:
            return {"family": fam}
    return {}


def parse_revision(question: str, section_names: tuple[str, ...] | list[str] = ()) -> dict[str, Any] | None:
    """The one change a message asks of the working warmup, or None when it is not about the warmup. Only meaningful while a warmup is active."""
    q = _clean(question)
    if not q:
        return None
    low = q.lower().rstrip(" .!?")
    if _UNDO.match(q):
        return {"op": OP_UNDO}
    if _REDO.match(q):
        return {"op": OP_REDO}
    if _NEXT.match(q):
        return {"op": OP_NEXT}
    if _PREV.match(q):
        return {"op": OP_PREV}
    gm = _GOTO.search(low)
    if gm:
        n = gm.group(1) or gm.group(3) or ""
        if not n and gm.group(2):
            n = str(_ORDINALS.get(gm.group(2).lower(), "")) or ("-1" if gm.group(2).lower() == "last" else "")
        if n:
            return {"op": OP_GOTO, "index": int(n)}
    if _ALL.search(low) and not re.search(r"\b(?:remove|drop|add|make|change)\b", low):
        return {"op": OP_ALL}
    preserved = [_preserved_ref(m.group(0)) for m in _PRESERVE.finditer(low)]
    low = _PRESERVE.sub(" ", low)             # "keep the first exactly as it is" says what NOT to touch; it must not pick the exercise to change
    ref = ref_from(low)
    if ref and ref in [x for x in preserved if x]:
        return {"op": OP_UNSUPPORTED}
    sop = song_revision(low, section_names)
    if sop is not None and not (sop["op"] == OP_INSTRUMENT and _asks_for_a_new_warmup_text(low)):
        return sop
    if _SPAN_CHORDS.search(question) and not ref:
        return None                       # a request about specific chords belongs to the exercise code, even when it says "exercise"
    adds = re.match(r"^\s*(?:please\s+|also\s+|and\s+|can\s+you\s+|could\s+you\s+)*(?:add|include|put\s+in|throw\s+in|bring\s+in|work\s+in|insert)\b", low)
    if _OTHER_INTENT.search(low) and not _WARMUP_TALK.search(low) and not ref and not (adds and not _SPAN_CHORDS.search(question)):
        return None                       # "give me a scale pattern over Blue Bossa" is not a change to the warmup
    fam_mention = [f for pattern, f in _FAMILY_WORDS.items() if re.search(rf"\b(?:{pattern})\b", low, re.I)]
    # removing
    m = re.search(rf"\b{_VERB_REMOVE}\b\s+(?:all\s+)?(?:of\s+)?(?:the\s+)?(.*)", low)
    if m and (ref or fam_mention):
        if ref.get("index"):
            return {"op": OP_REMOVE_ITEM, "index": ref["index"]}
        return {"op": OP_REMOVE_FAMILY, "family": ref.get("family") or fam_mention[0]}
    m = re.search(r"\b(?:no\s+more|without|stop\s+(?:the|doing))\s+(?:the\s+)?(" + _FAMILY_ANY + r")", low)
    if m:
        return {"op": OP_REMOVE_FAMILY, "family": _family_of(m.group(1))}
    # interval type
    iv = [i for i, p in _INTERVAL_WORD.items() if re.search(rf"\b(?:{p})\b", low)]
    if iv and re.search(r"\b(?:change|switch|make|turn|set|use|swap|replace)\b", low) and (re.search(r"\binterval", low) or ref.get("family") == "intervals" or ref.get("index")):
        return {"op": OP_INTERVAL, "interval": iv[0], "ref": ref}
    # level (for one named exercise, harder / easier is a faster / slower tempo: the one difficulty I can change on a single exercise)
    if re.search(r"\b(?:more\s+advanced|harder|more\s+difficult|more\s+challenging|step\s+it\s+up|challenge\s+me|advance\s+it|a\s+(?:bit|little)\s+harder|up\s+the\s+level|increase\s+the\s+difficulty)\b", low):
        return {"op": OP_ITEM_FASTER, "ref": ref, "challenge": True} if ref else {"op": OP_HARDER}
    if re.search(r"\b(?:easier|simpler|less\s+(?:advanced|difficult|challenging)|more\s+basic|a\s+(?:bit|little)\s+easier|decrease\s+the\s+difficulty|too\s+(?:hard|difficult))\b", low):
        return {"op": OP_ITEM_SLOWER, "ref": ref, "challenge": True} if ref else {"op": OP_EASIER}
    lm = re.search(r"\b(?:make|set|change)\s+(?:it|the\s+warm[\s-]?up)\s+(?:to\s+|a\s+|an\s+)?(beginner|intermediate|advanced)\b", low)
    if lm:
        return {"op": OP_LEVEL, "level": lm.group(1).capitalize()}
    # length
    mins = _minutes_in(low)
    if mins and re.search(r"\b(?:make|set|change|only|just|i\s+(?:have|only\s+have|got)|need|want|shorten|extend|cut|keep|to)\b", low) and not ref:
        return {"op": OP_MINUTES, "minutes": mins}
    if re.search(r"\b(?:shorter|shorten|less\s+time|cut\s+(?:it\s+)?down|trim|quicker\s+warm|briefer)\b", low) and not ref:
        return {"op": OP_SHORTER}
    if re.search(r"\b(?:longer|lengthen|extend|more\s+time|expand)\b", low) and not ref:
        return {"op": OP_LONGER}
    # tempo
    bm = _BPM.search(low)
    if bm and ref:
        return {"op": OP_ITEM_TEMPO, "ref": ref, "bpm": int(bm.group(1))}
    if _SLOWER.search(low) or _FASTER.search(low):
        slower = bool(_SLOWER.search(low))
        if ref:
            return {"op": OP_ITEM_SLOWER if slower else OP_ITEM_FASTER, "ref": ref}
        if re.search(r"\b(?:whole|entire|all|everything|it|the\s+warm[\s-]?up)\b", low):
            return {"op": OP_WHOLE_SLOWER if slower else OP_WHOLE_FASTER}
    # adding / more of a family
    m = re.search(rf"\b(?:{_VERB_ADD}|more)\b\s+(?:(?:some|a|an|more|extra|another)\s+)*(?:(?:\w+\s+){{0,2}})?({_FAMILY_ANY})", low)
    if m and (_WARMUP_TALK.search(low) or re.match(r"^\s*(?:please\s+|also\s+|and\s+|can\s+you\s+|could\s+you\s+)*(?:add|include|put\s+in|throw\s+in|bring\s+in|work\s+in|insert|more)\b", low)):
        fam = _family_of(m.group(1))
        if fam:
            return {"op": OP_MORE_FAMILY if re.search(r"\bmore\b|\bextra\b", low) else OP_ADD_FAMILY, "family": fam,
                    "artic": "two_note" if re.search(r"\btwo[\s-]?note\b", low) else ""}
    # anything else that is clearly about the warmup is refused in words (never guessed at)
    if _WARMUP_TALK.search(low) or ref or re.match(r"^(?:please\s+)?(?:now\s+|also\s+|and\s+)?(?:make|change|add|remove|drop|delete|take)\s+(?:it|this|that|them|everything)\b", low):
        return {"op": OP_UNSUPPORTED}
    try:                                  # an exercise-style change (accents, syncopation, fourths ...) is refused for a warmup, not guessed at
        from music_coach_ami.exercise_followup import is_exercise_followup
        from music_coach_ami.exercise_revision import is_revision_request

        if is_revision_request(question) or is_exercise_followup(question):
            return {"op": OP_UNSUPPORTED}
    except Exception:
        pass
    return None


# ---------------------------------------------------------------- song-aware requests (Slice 2a: guide tones over the active song's chart)

_GUIDE = re.compile(r"\bguide[\s-]?tones?\b", re.I)
_THIRDS_SEVENTHS = re.compile(r"\b(?:thirds?|3rds?)\s*(?:and|&|,|/)\s*(?:sevenths?|7ths?)\b|\b(?:sevenths?|7ths?)\s*(?:and|&|,|/)\s*(?:thirds?|3rds?)\b", re.I)
_SONG_SCOPE = re.compile(r"\b(?:chorus|choruses|whole\s+(?:song|tune|form|chorus)|entire\s+(?:song|tune|form)|full\s+(?:song|tune|form)|these\s+chords|the\s+chords|"
                         r"the\s+changes|chord\s+changes|(?:the\s+)?progression|the\s+tune|the\s+song|this\s+(?:song|tune)|the\s+head|the\s+form|the\s+bridge|"
                         r"section\s+\w+|\w\s+section|the\s+verse|the\s+chart|warm[\s-]?up)\b", re.I)
_SPAN_CHORDS = re.compile(r"\bii[\s-]?v\b|\b(?:first|last|next)\s+(?:two|three|2|3)\s+chords?\b|\bone\s+chord\b|\bover\s+[A-G][#b]?(?:maj|min|dim|aug|sus|m|M)?\d+\b|"
                          r"\b[A-G][#b]?(?:maj|min|dim|aug|sus|m|M)?\d*\s*(?:to|→|->|then)\s*[A-G][#b]?(?:maj|min|dim|aug|sus|m|M)?\d*\b")
_PRACTICE_ASK = re.compile(r"\b(?:give|make|create|build|design|write|prepare|show|need|want|get|generate|produce|practi[cs]e|work\s+on|play|drill|"
                           r"i[’']?d\s+like|can\s+(?:i|you|we)|could\s+(?:i|you|we)|would\s+you|please|let[’']?s|warm)\b", re.I)
_SECTION_WORD = r"(bridge|verse(?:\s*\d+)?|chorus(?:\s*\d+)?|head|intro|outro|pre-?chorus|solo\s+section|solo|section\s+[a-z0-9]+|[a-z0-9]\s+section|b\s*\(bridge\)|turnaround)"
_BAR_NUM = r"(\d+|" + "|".join(_NUMBER_WORDS) + r")"
_SMOOTH = re.compile(r"\b(?:smoother|smooth(?:er)?\s+(?:voice[\s-]?leading|movement|line|motion|connections?)|more\s+smoothly|less\s+(?:jumpy|leaping|angular)|fewer\s+leaps|"
                     r"voice[\s-]?lead\w*\s+(?:better|smoother|more\s+smoothly))\b", re.I)
_EXPLAIN = re.compile(r"\b(?:explain|why)\b", re.I)
_EXPLAIN_SUBJECT = re.compile(r"\b(?:notes?|work|works|line|chosen|choose|picked|guide|those|these|that)\b", re.I)
_CHANGE_VERB = re.compile(r"\b(?:change|switch|move|put|transpose|convert|swap)\b", re.I)
_CHORDLINE = re.compile(r"\barpeggios?\b|\bchord[\s-]?tones?\b|\bapproach(?:es|ing)?\b|\bapproach[\s-](?:notes?|tones?)\b|\benclosures?\b", re.I)
_SONG_SCOPE_STRICT = re.compile(_SONG_SCOPE.pattern.replace(r"|warm[\s-]?up", ""), re.I)
_WHOLE_SONG = re.compile(r"\b(?:the\s+)?(?:whole|entire|full|complete)\s+(?:song|tune|form|chorus|chart|progression)\b|\bwhole\s+thing\b", re.I)
_PREPARE_FOR = re.compile(r"\bprepare\s+(?:me|us)\s+for\s+(?:soloing|improvis\w*)", re.I)
_START_RE = re.compile(r"\b(?:start|begin)(?:ning)?\s+(?:each|every|all|the)?\s*(?:arpeggios?|one|chord|them)?s?\s*(?:on|with|from)\s+(?:the\s+)?(root|third|3rd|fifth|5th|seventh|7th)\b", re.I)
_APPROACH_KIND_RE = re.compile(r"\b(?:add|include|use|try|put\s+in|give\s+me|switch\s+to|change\s+to|make\s+(?:them|it))\s+(?:in\s+)?(?:some\s+|an?\s+|the\s+)?"
                               r"(chromatic\s+|diatonic\s+|double[\s-]chromatic\s+)?(approach(?:es)?(?:[\s-](?:notes?|tones?))?|enclosures?)(?:\s+(?:from\s+)?(below|above))?\b", re.I)
_NAMED_OVER = re.compile(r"\bover\s+(?:the\s+changes\s+(?:of|to|from)\s+)?((?:[A-Z0-9][\w'’&.\-]*)(?:\s+(?!(?:please|with|using|at|chorus|changes|tune|song|and|today|now)\b)[A-Za-z0-9][\w'’&.\-]*){0,6})")


def _num_of(text: str) -> int | None:
    n = _number(text)
    return int(n) if n is not None else None


def bars_spec(low: str) -> dict[str, Any] | None:
    """The bars a message asks for: {'first': n} | {'last': n} | {'range': (a, b)} | {'all': True} | None."""
    if re.search(r"\b(?:the\s+)?(?:whole|entire|full)\s+(?:section|chorus|form|thing|progression|chart)\b|\ball\s+(?:the\s+)?bars\b", low):
        return {"all": True}
    m = re.search(rf"\b(?:the\s+)?first\s+{_BAR_NUM}\s+bars?\b", low)
    if m and _num_of(m.group(1)):
        return {"first": _num_of(m.group(1))}
    m = re.search(rf"\b(?:the\s+)?last\s+{_BAR_NUM}\s+bars?\b", low)
    if m and _num_of(m.group(1)):
        return {"last": _num_of(m.group(1))}
    m = re.search(rf"\bbars?\s+{_BAR_NUM}\s*(?:to|through|thru|-|–|until)\s*{_BAR_NUM}\b", low)
    if m and _num_of(m.group(1)) and _num_of(m.group(2)):
        return {"range": (_num_of(m.group(1)), _num_of(m.group(2)))}
    return None


def section_word(low: str, *, verbs: bool) -> str:
    """The section the words name ('bridge', 'chorus', 'section b'), or ''. With ``verbs`` the phrase must follow 'only / just / use / switch to ...'."""
    if verbs:
        m = re.search(rf"\b(?:only|just|use|switch\s+to|change\s+to|go\s+to|move\s+to|try|do|practice|work\s+on|play|stay\s+(?:in|on)|focus\s+on)\s+(?:the\s+)?{_SECTION_WORD}\b", low)
    else:
        m = re.search(rf"\b(?:over|for|on|in|through|of)\s+(?:the\s+)?{_SECTION_WORD}\b", low)
    return m.group(1).strip() if m else ""


def tones_word(low: str, *, strict: bool) -> str:
    """'both' | 'thirds' | 'sevenths' | ''. With ``strict`` (a revision) the word must be used as an instruction ('thirds only', 'now practice the sevenths')."""
    if _THIRDS_SEVENTHS.search(low):
        return "both"
    if strict:
        t = re.search(r"\b(?:thirds|3rds)\s+only\b|\b(?:only|just)\s+(?:the\s+)?(?:thirds|3rds)\b|\b(?:now\s+)?(?:practice|play|do|use|switch\s+to|try|work\s+on|focus\s+on|go\s+to)\s+(?:the\s+)?(?:thirds|3rds)\b", low)
        s7 = re.search(r"\b(?:sevenths|7ths)\s+only\b|\b(?:only|just)\s+(?:the\s+)?(?:sevenths|7ths)\b|\b(?:now\s+)?(?:practice|play|do|use|switch\s+to|try|work\s+on|focus\s+on|go\s+to)\s+(?:the\s+)?(?:sevenths|7ths)\b", low)
        return "thirds" if t and not s7 else "sevenths" if s7 and not t else ""
    t = re.search(r"\b(?:thirds|3rds)\b", low)
    s7 = re.search(r"\b(?:sevenths|7ths)\b", low)
    return "thirds" if t and not s7 else "sevenths" if s7 and not t else ""


def song_request_info(question: str) -> dict[str, Any]:
    """What a message asks of a song-aware warmup (all read from the words; nothing is looked up here)."""
    q = _clean(question)
    low = q.lower()
    named = ""
    m = _NAMED_OVER.search(q)
    if m and m.group(1)[:1].isupper() and not _SPAN_CHORDS.search(q):
        named = m.group(1).strip(" .,!?;")
    found = sorted(((m.start(), f) for pat, f in _FAMILY_WORDS.items() if f in SONG_FAMILIES or True for m in [re.search(rf"\b(?:{pat})\b", low, re.I)] if m), key=lambda t: t[0])
    spoken = [f for _i, f in found]
    song_fams = [f for f in spoken if f in SONG_FAMILIES]
    return {"wants_song": is_song_request(q), "guide_explicit": bool(_GUIDE.search(low)), "section": section_word(low, verbs=False) or section_word(low, verbs=True),
            "bars": bars_spec(low), "tones": tones_word(low, strict=False), "named": named, "whole": bool(_WHOLE_SONG.search(low)), "song_families": song_fams, "spoken": spoken,
            "chord_start": _start_word(low), "approach_kind": _approach_kind(low)}


def _start_word(low: str) -> str:
    m = _START_RE.search(low)
    return {"root": "root", "third": "third", "3rd": "third", "fifth": "fifth", "5th": "fifth", "seventh": "seventh", "7th": "seventh"}[m.group(1).lower()] if m else ""


def _approach_kind(low: str) -> str:
    """'below' | 'above' | 'diatonic' | 'double' | 'enclosure' | '' for the approach the words ask for."""
    if re.search(r"\benclosures?\b", low):
        return "enclosure"
    if re.search(r"\bdouble[\s-]chromatic\b", low):
        return "double_above" if re.search(r"\babove\b", low) else "double"
    if re.search(r"\bdiatonic\s+approach", low):
        return "diatonic"
    if re.search(r"\bapproach\w*", low) or re.search(r"\bchromatic\b", low):
        if re.search(r"\bbelow\b", low) and not re.search(r"\babove\b", low):
            return "below"
        if re.search(r"\babove\b", low) and not re.search(r"\bbelow\b", low):
            return "above"
    return ""


def is_song_request(question: str) -> bool:
    """A request for a warmup or exercise built from the ACTIVE SONG's chords: 'warm me up for soloing over X', 'a guide-tone exercise over the chorus',
    'practice the thirds and sevenths of these chords'. Requests about specific chords or spans (ii-V, 'over Dm7') are not these."""
    q = _clean(question)
    low = q.lower()
    if not low or _QUESTION_START.match(low) or _SPAN_CHORDS.search(q):
        return False
    asks = bool(_PRACTICE_ASK.search(low))
    warm = bool(_WARM.search(low)) or bool(re.match(r"^\s*(?:please\s+)?(?:can\s+you\s+|could\s+you\s+)?warm\s+(?:me|us|myself)\s+up\b", low))
    if re.search(r"\b(?:why|benefits?|how\s+(?:do|does|should)|what\s+(?:is|are))\b", low) and not re.search(r"\b(?:give|make|create|build|prepare|practice)\b", low):
        return False
    guide, th7 = bool(_GUIDE.search(low)), bool(_THIRDS_SEVENTHS.search(low))
    scope = bool(_SONG_SCOPE.search(low))
    if warm and (_SONG_AWARE.search(low) or guide or th7 or _NAMED_OVER.search(q)):
        return True
    if guide and asks and (scope or warm):
        return True
    chordline = bool(_CHORDLINE.search(low))
    if warm and (chordline or _SONG_SCOPE_STRICT.search(low)):
        return True
    if re.search(r"\barpeggios?\s+exercises?\b", low) and asks and (_NAMED_OVER.search(q) or _SONG_SCOPE_STRICT.search(low)):
        return True
    if _PREPARE_FOR.search(low) or (guide and chordline and asks):
        return True
    if th7 and asks and re.search(r"\b(?:these\s+chords|the\s+chords|the\s+changes|chord\s+changes|progression|chorus|song|tune|head|bridge|section)\b", low):
        return True
    return False


def song_revision(low: str, section_names: tuple[str, ...] | list[str] = ()) -> dict[str, Any] | None:
    """A change that only makes sense for a song-aware warmup (or an instrument change), read from the words; None when the message is not one."""
    if _EXPLAIN.search(low) and _EXPLAIN_SUBJECT.search(low) and not re.search(r"\b(?:make|change|add|remove|drop|set)\b", low):
        return {"op": OP_EXPLAIN}
    sw = _start_word(low)
    if sw and re.search(r"\b(?:arpeggios?|each|every|all|them)\b", low):
        return {"op": OP_ARP_START, "start": sw}
    ak = _APPROACH_KIND_RE.search(low)
    if ak:
        kind = _approach_kind(low)
        if kind:
            return {"op": OP_APPROACH_KIND, "kind": kind}
    if _WHOLE_SONG.search(low) and re.search(r"\b(?:use|do|play|practice|go|switch|over|for|now|work|back|take|try)\b", low) and not re.search(r"\b(?:slower|faster|shorter|longer)\b", low):
        return {"op": OP_SECTION, "section": "__whole__"}
    spec = bars_spec(low)
    if spec and re.search(r"\b(?:just|only|use|do|play|practice|work\s+on|limit|restrict|go\s+back|the|first|last|bars?)\b", low) and not re.search(r"\b(?:exercise|exercises|minutes?)\b", low):
        return {"op": OP_BARS, "spec": spec}
    if section_names:
        named = ws.find_section(list(section_names), low)
        verbs = re.search(r"\b(?:only|just|use|switch\s+to|change\s+to|go\s+to|move\s+to|try|do|practice|work\s+on|play|stay\s+(?:in|on)|focus\s+on)\b", low)
        if named and (verbs or ws._norm(low) in {a for a in ws._aliases(named)} | {f"the {a}" for a in ws._aliases(named)}):
            return {"op": OP_SECTION, "section": named}
    sec = section_word(low, verbs=True)
    if sec:
        return {"op": OP_SECTION, "section": sec}
    if _SMOOTH.search(low):
        return {"op": OP_SMOOTH}
    tw = tones_word(low, strict=True)
    if tw:
        return {"op": OP_TONES, "tones": tw}
    if _CHANGE_VERB.search(low):
        tail = re.search(r"\bto\s+(?:a\s+|an\s+|the\s+)?(.+)$", low)
        im = _INSTRUMENT.search(tail.group(1)) if tail else None
        if im:
            sax_type = (im.group(1) or "").lower()
            word = "saxophone" if (im.group(1) or im.group(2)) else (im.group(3) or im.group(4) or im.group(5) or im.group(6) or "").lower()
            if word:
                return {"op": OP_INSTRUMENT, "instrument_word": word, "sax_type_word": sax_type}
    return None



def is_warmup_message(question: str) -> bool:
    """Used by the duplicate-send guard: warmup requests and revisions are new work every time they are sent."""
    return is_warmup_request(question) or (parse_revision(question) or {}).get("op") in {
        OP_NEXT, OP_PREV, OP_ALL, OP_GOTO, OP_SHORTER, OP_LONGER, OP_MINUTES, OP_HARDER, OP_EASIER, OP_LEVEL, OP_REMOVE_FAMILY, OP_REMOVE_ITEM,
        OP_ADD_FAMILY, OP_MORE_FAMILY, OP_ITEM_SLOWER, OP_ITEM_FASTER, OP_ITEM_TEMPO, OP_WHOLE_SLOWER, OP_WHOLE_FASTER, OP_INTERVAL,
        OP_SECTION, OP_BARS, OP_TONES, OP_SMOOTH, OP_INSTRUMENT, OP_EXPLAIN, OP_ARP_START, OP_APPROACH_KIND, OP_ITEM_LEVEL}


# ---------------------------------------------------------------- the plan


DEFAULT_FAMILIES = {"Beginner": ["long_tones", "scale", "articulation"], "Intermediate": ["long_tones", "scale", "intervals", "articulation"],
                    "Advanced": ["long_tones", "scale", "intervals", "articulation"]}
BASE_WEIGHT = {"bass_arpeggio": 1.4, "long_tones": 1.0, "scale": 1.3, "intervals": 1.2, "articulation": 1.0, "guide_tones": 1.4, "chord_tones": 1.4, "approach_notes": 1.3}
DEFAULT_SONG_FAMILIES = {"Beginner": ["guide_tones", "chord_tones"], "Intermediate": ["scale", "guide_tones", "chord_tones", "approach_notes"],
                         "Advanced": ["scale", "guide_tones", "chord_tones", "approach_notes"]}
PROGRESSIVE_INTERVALS = {"Beginner": ["thirds", "fourths"], "Intermediate": ["thirds", "fourths", "fifths"], "Advanced": ["thirds", "fourths", "fifths", "sixths"]}
DEFAULT_INTERVALS = {"Beginner": ["thirds"], "Intermediate": ["thirds", "fourths"], "Advanced": ["thirds", "fourths", "fifths"]}
DEFAULT_ARTIC = {"Beginner": ["repeated", "two_note"], "Intermediate": ["slur_tongue", "two_note", "repeated", "contrast"],
                 "Advanced": ["slur_tongue", "repeated", "contrast", "two_note"]}
FOCUS_BOOST = {"tone": ("long_tones",), "technique": ("scale", "intervals"), "articulation": ("articulation",), "improvisation": ("scale", "intervals"),
               "speed": ("scale", "intervals"), "scales": ("scale",), "intervals": ("intervals",), "melody": ("scale", "intervals"), "harmony": ("guide_tones", "chord_tones")}


def _focus_key(focus: str) -> str:
    from practice_focus_policy import category_for_focus
    category = category_for_focus(focus)
    if category in FOCUS_BOOST:
        return category
    low = _clean(focus).lower()
    for key in FOCUS_BOOST:
        if key in low:
            return key
    if "finger" in low or "tech" in low:
        return "technique"
    return ""


def _weights(spec: dict[str, Any]) -> dict[str, float]:
    w = {f: BASE_WEIGHT[f] for f in spec["families"]}
    boost = FOCUS_BOOST.get(spec.get("focus") or "", ())
    for f in boost:
        if f in w:
            w[f] *= 1.5
    for f, extra in (spec.get("more") or {}).items():
        if f in w:
            w[f] *= float(extra)
    if spec["level"] == "Advanced" and "long_tones" in w:
        w["long_tones"] *= 0.8
    return w


def _next_uid(spec: dict[str, Any]) -> str:
    spec["uid_counter"] = int(spec.get("uid_counter") or 0) + 1
    return f"i{spec['uid_counter']}"


def _items_of(spec: dict[str, Any], family: str) -> list[dict[str, Any]]:
    return [it for it in spec["items"] if it["family"] == family]


def _guide_combo(spec: dict[str, Any], variant: int, level: str | None = None) -> tuple[str, str, str]:
    """(tones, first tone, rhythm style) of guide-tone variant ``variant`` at the plan's (or the item's) level, after any 'thirds only' / 'sevenths only' choice."""
    table = ws.VARIANTS[level or spec["level"]]
    tones, first, style = table[int(variant) % len(table)]
    want = spec.get("tones") or ""
    if want in ("thirds", "sevenths"):
        tones, first = want, ""
    elif want == "both" and tones != "both":
        tones, first = "both", "auto"
    return tones, first, style


def _chord_combo(spec: dict[str, Any], variant: int, level: str | None = None) -> tuple[str, str, str, str]:
    table = wc.CHORD_VARIANTS[level or spec["level"]]
    direction, shape, start, art = table[int(variant) % len(table)]
    return direction, shape, (spec.get("chord_start") or start), art


def _approach_combo(spec: dict[str, Any], variant: int, level: str | None = None) -> tuple[str, str]:
    table = wc.APPROACH_VARIANTS[level or spec["level"]]
    kind, target = table[int(variant) % len(table)]
    return (spec.get("approach_kind") or kind), target


def _song_combo(spec: dict[str, Any], family: str, variant: int, level: str | None = None) -> tuple:
    return {"guide_tones": _guide_combo, "chord_tones": _chord_combo, "approach_notes": _approach_combo}[family](spec, variant, level)


def _variant_count(family: str, level: str) -> int:
    return len({"guide_tones": ws.VARIANTS, "chord_tones": wc.CHORD_VARIANTS, "approach_notes": wc.APPROACH_VARIANTS}[family][level])


def _dedupe_guide(spec: dict[str, Any]) -> None:
    """After a level or tones / start / approach-kind change two variants can mean the same music; keep the first of each."""
    seen: set[tuple] = set()
    kept = []
    for d in spec["items"]:
        if d["family"] in SONG_FAMILIES:
            combo = (d["family"], *_song_combo(spec, d["family"], d["params"].get("variant", 0), d.get("level")))
            if combo in seen:
                continue
            seen.add(combo)
        kept.append(d)
    spec["items"] = kept


def _new_item(spec: dict[str, Any], family: str) -> dict[str, Any] | None:
    """The next exercise of ``family`` (a new variant of what the family already has); None when the family has no more variants."""
    have = _items_of(spec, family)
    n = len(have)
    if n >= (spec.get("family_caps") or {}).get(family, FAMILY_CAP.get(family, 4)):
        return None
    if family == "intervals" and spec.get("widening") and n >= len(spec.get("intervals") or []):
        return None                       # a widening run ends at its widest interval; extra time becomes extra plays, never a narrower one again
    params: dict[str, Any] = {}
    if family in SONG_FAMILIES:
        own = {h.get("level") for h in have}
        fam_level = own.pop() if len(own) == 1 else None                 # a kind raised to a higher level keeps that level for the variants added to it
        taken = {_song_combo(spec, family, d["params"].get("variant", 0), d.get("level")) for d in have}
        v = next((i for i in range(_variant_count(family, fam_level or spec["level"])) if _song_combo(spec, family, i, fam_level) not in taken), None)
        if v is None:
            return None                    # every distinct way of playing the line at this level is already in the plan
        item = {"uid": _next_uid(spec), "family": family, "params": {"variant": v}, "tempo": None, "size": spec.get("size") or "full", "keep": n == 0}
        if fam_level:
            item["level"] = fam_level
        return item
    if family == "intervals":
        pool = spec.get("intervals") or DEFAULT_INTERVALS[spec["level"]]
        iv = pool[n % len(pool)]
        used = sum(1 for it in have if it["params"].get("interval") == iv)
        params = {"interval": iv, "variant": used}
    elif family == "articulation":
        pool = spec.get("artic") or DEFAULT_ARTIC[spec["level"]]
        pat = pool[n % len(pool)]
        used = sum(1 for it in have if it["params"].get("pattern") == pat)
        params = {"pattern": pat, "variant": used}
    else:
        params = {"variant": n}
    return {"uid": _next_uid(spec), "family": family, "params": params, "tempo": None, "size": spec.get("size") or "full", "keep": n == 0}


def _interval_pool(req: dict[str, Any], families: list[str], level: str, assumptions: list[str]) -> list[str]:
    """The intervals the musician named; or, for "increasingly difficult intervals", a widening run (each stated, none dropped to save time)."""
    named = [i for i in req["intervals"] if i in we.INTERVALS]
    if named or not req.get("progressive") or "intervals" not in families:
        return named
    run = list(PROGRESSIVE_INTERVALS[level])
    assumptions.append("The interval exercises get wider as the warmup goes on: " + ", ".join(run) + ".")
    return run


def _widening(req: dict[str, Any], families: list[str]) -> bool:
    return bool(req.get("progressive")) and "intervals" in families and not [i for i in req["intervals"] if i in we.INTERVALS]


def initial_items(spec: dict[str, Any]) -> None:
    """Start with one exercise per family (families the instrument can't use were already dropped)."""
    spec["items"] = []
    for f in spec["families"]:
        it = _new_item(spec, f)
        if it:
            spec["items"].append(it)
    # an explicit pair of intervals ("thirds and fourths") means one exercise each
    for f in ("intervals", "articulation"):
        pool = (spec.get("intervals") if f == "intervals" else spec.get("artic")) or []
        if f in spec["families"]:
            while len(_items_of(spec, f)) < len(pool):
                it = _new_item(spec, f)
                if not it:
                    break
                it["keep"] = True               # the musician named it ("thirds and fourths"), so it is not dropped to save time
                spec["items"].append(it)
    spec["items"] = _ordered(spec)


def _ordered(spec: dict[str, Any]) -> list[dict[str, Any]]:
    """Exercises in a sensible order: tone first, then fingers, then the mouth, then the harder shapes; a family's variants stay in sequence."""
    if spec.get("sax", {}).get("jazz_kind")=="plan":
        families=["guide_tones","chord_tones","approach_notes"]
        groups={f:[d for d in spec["items"] if d["family"]==f] for f in families}
        return [groups[f][i] for i in range(max((len(v) for v in groups.values()),default=0)) for f in families if i<len(groups[f])]
    rank = {"long_tones": 0, "scale": 1, "guide_tones": 2, "chord_tones": 2.5, "approach_notes": 2.8, "intervals": 3, "articulation": 4}
    pref = spec.get("order_pref") or []
    if pref:                                   # the musician named the exercises in an order: keep it
        rank = {f: float(i) for i, f in enumerate(pref)} | {f: 100.0 + r for f, r in rank.items() if f not in pref}
    return sorted(spec["items"], key=lambda it: (rank.get(it["family"], 9), spec["items"].index(it)))


def _shift_key(tonic: str, tonality: str, k: int) -> tuple[str, str]:
    return we.practical_key(*we.related_key(tonic, tonality, KEY_SHIFTS[k % len(KEY_SHIFTS)]))


def build_item(player: we.Player, spec: dict[str, Any], desc: dict[str, Any]) -> dict[str, Any]:
    """One rendered exercise: notes, staff, tempo and the time one play takes. Raises ``WarmupUnavailable`` if it can't be built correctly."""
    if spec.get("sax"):
        spec = copy.deepcopy(spec)
        spec["sax"] = copy.deepcopy(desc.get("sax_options", spec["sax"]))
        player = we.make_player(desc.get("sax_instrument", player.key), spec["concert_key"])
        spec["level"] = desc.get("sax_level", spec["level"])
        if desc.get("sax_song_sel"):
            spec["song_sel"] = copy.deepcopy(desc["sax_song_sel"])
    level = (desc.get("level") if desc["family"] in SONG_FAMILIES else None) or spec["level"]
    fam = desc["family"]
    params = dict(desc["params"])
    base_tonic, base_tonality = we.practical_key(*we.split_key(player.written_key))
    if fam in SONG_FAMILIES:
        tonic, tonality = base_tonic, base_tonality
    elif fam == "long_tones":
        tonic, tonality = base_tonic, base_tonality
    elif fam == "scale":
        tonic, tonality = _shift_key(base_tonic, base_tonality, int(params.get("variant") or 0))
    elif fam == "intervals":
        tonic, tonality = _shift_key(base_tonic, base_tonality, int(params.get("variant") or 0))
    else:
        tonic, tonality = _shift_key(base_tonic, base_tonality, int(params.get("variant") or 0))
    kwargs: dict[str, Any] = {"variant": int(params.get("variant") or 0), "size": desc.get("size") or "full"}
    if fam == "intervals":
        kwargs["interval"] = params["interval"]
    if fam == "articulation":
        kwargs["pattern"] = params["pattern"]
    if spec.get("sax") and desc.get("sax_snapshot"):
        from music_coach_ami.sax_conversation import restore
        built = restore(desc["sax_snapshot"])
    elif spec.get("sax", {}).get("jazz") and fam in SONG_FAMILIES:
        from music_coach_ami import jazz_engine, jazz_patterns
        sel=spec["song_sel"]
        built=jazz_engine.build(player,level,spec["song"],sel["section"],tuple(sel["bars"]) if sel.get("bars") else None,jazz_patterns.item_options(spec,desc))
    elif spec.get("sax", {}).get("chart_intervals") and fam in SONG_FAMILIES:
        from music_coach_ami import sax_chart_intervals as sci
        sel = spec["song_sel"]
        built = sci.build(player, level, spec["song"], sel["section"], tuple(sel["bars"]) if sel.get("bars") else None, spec["sax"])
    elif fam == "guide_tones":
        sel = spec["song_sel"]
        tones, first, style = _guide_combo(spec, int(params.get("variant") or 0))
        built = ws.build(player, level, spec["song"], sel["section"], tuple(sel["bars"]) if sel.get("bars") else None, tones=tones, first=first, style=style,
                         smooth=bool(spec.get("smooth")))
    elif fam == "chord_tones":
        sel = spec["song_sel"]
        direction, shape, start, art = _chord_combo(spec, int(params.get("variant") or 0), level)
        built = wc.build_chord_tones(player, level, spec["song"], sel["section"], tuple(sel["bars"]) if sel.get("bars") else None, direction=direction, shape=shape,
                                     start=start, art=art, smooth=bool(spec.get("smooth")))
    elif fam == "approach_notes":
        sel = spec["song_sel"]
        kind, target = _approach_combo(spec, int(params.get("variant") or 0), level)
        built = wc.build_approach(player, level, spec["song"], sel["section"], tuple(sel["bars"]) if sel.get("bars") else None, kind=kind, target=target,
                                  smooth=bool(spec.get("smooth")))
    elif player.key in ("soprano","alto","tenor","baritone") and spec.get("sax"):
        from music_coach_ami import sax_technique
        sax_options=copy.deepcopy(spec["sax"])
        if sax_options.get("intervals_from_plan"):
            sax_options["interval"]=params["interval"]
        built=sax_technique.built(player,level,tonic,tonality,sax_options,variant=kwargs["variant"])
        params["sax_recipe"]=sax_options["recipe"]
        if fam=="articulation":params["pattern"]=sax_options["pattern"]
        elif sax_options["recipe"]=="intervals":params["interval"]=sax_options["interval"]
        else:params.pop("interval",None)
    elif player.key == "bass":
        from music_coach_ami.bass_technique import warmup_built
        built = warmup_built(player, level, tonic, tonality, fam, **kwargs)
    else:
        built = we.BUILDERS[fam](player, level, tonic, tonality, **kwargs)
    if player.key in ("soprano","alto","tenor","baritone") and spec.get("sax"):
        from music_coach_ami import sax_technique
        if fam in SONG_FAMILIES and not desc.get("sax_snapshot") and not built.meta.get("jazz"):
            built=sax_technique.decorate(built,spec["sax"])
    if player.key == "bass":
        from music_coach_ami.bass_technique import certify
        certify(built, level, record=spec.get("bass_fingering",{}).get(desc["uid"],spec.get("bass_fingering",{}).get("*")))
    if spec.get("sax") and desc.get("sax_snapshot"):
        params["sax_recipe"] = spec["sax"]["recipe"]
        if fam == "intervals" and spec["sax"]["recipe"] != "intervals":
            params.pop("interval", None)
    scale = float(spec.get("tempo_scale") or 1.0)
    bpm = int(desc.get("tempo") or round(built.bpm * scale))
    bpm = max(36, min(160, bpm))
    abc, diag = we.render(player, built, tonic, tonality, title=built.title, bpm=bpm)
    if built.meta.get("jazz"):
        from music_coach_ami import jazz_engine
        checks=jazz_engine.verify(player,level,built,diag,spec["song"])
    elif built.meta.get("sax_chart"):
        from music_coach_ami import sax_chart_intervals as sci
        checks = sci.verify(player, level, built, diag, spec["song"])
    else:
        checks = (ws.verify(player, level, built, diag) if fam == "guide_tones" else wc.verify(player, level, built, diag) if fam in SONG_FAMILIES
                  else we.verify(player, level, built, tonic, tonality, diag, allowed_pcs=(sax_technique.allowed_pcs(spec["sax"]["recipe"]) if player.key in ("soprano","alto","tenor","baritone") and spec.get("sax") else None)))
    seconds = we.pass_seconds(built, bpm)
    if player.key=="bass":
        from music_coach_ami.bass_tab import timeline
        built.meta["bass_tab"]=timeline(built,level,bpm,abc)
    pitched = [n for n in built.notes if not n.rest]
    written = [n.midi for n in pitched]
    sax_data = {}
    if spec.get("sax"):
        from music_coach_ami.sax_conversation import snapshot
        sax_data = {"sax_snapshot": snapshot(built), "instrument": player.key, "instrument_label": player.label, "offset": player.offset,
                    "sax_options": copy.deepcopy(built.meta.get("sax_options", spec["sax"]))}
    return {
        **sax_data,
        "uid": desc["uid"], "family": fam, "params": params, "item_level": level, "title": built.title, "abc": abc, "bpm": bpm, "base_bpm": built.bpm,
        "tempo_override": desc.get("tempo"), "size": desc.get("size") or "full", "key": we.key_text(tonic, tonality), "tonic": tonic, "tonality": tonality,
        "bars": int(round(float(we.total_beats(built.notes) / we.BEATS_PER_BAR))), "pass_seconds": round(seconds, 2), "how": list(built.how),
        "listen": list(built.listen), "meta": dict(built.meta), "written_midi": written, "sounding_midi": [m - player.offset for m in written],
        "written_notes": [f"{n.spelled}{n.octave}" for n in pitched], "durations": [("rest_" if n.rest else "") + n.dur for n in built.notes],
        "articulations": [n.art for n in built.notes if not n.rest], "slur_groups": [n.slur for n in built.notes if not n.rest],
        "checks": checks, "range": [min(written), max(written)],
    }


def _total(rows: list[dict[str, Any]]) -> float:
    secs = 0.0
    for r in rows:
        secs += r["reps"] * r["pass_seconds"] + (r["reps"] - 1) * we.GAP_SECONDS
    return secs + max(0, len(rows) - 1) * we.TRANSITION_SECONDS


def allocate(rows: list[dict[str, Any]], weights: dict[str, float], target_s: float) -> None:
    """Set ``reps`` on every row so the plan's real playing time lands as close to ``target_s`` as the exercises allow."""
    if not rows:
        return
    fam_count: dict[str, int] = {}
    for r in rows:
        fam_count[r["family"]] = fam_count.get(r["family"], 0) + 1
    available = max(1.0, target_s - max(0, len(rows) - 1) * we.TRANSITION_SECONDS)
    wsum = sum(weights.get(r["family"], 1.0) / fam_count[r["family"]] for r in rows)
    for r in rows:
        share = available * (weights.get(r["family"], 1.0) / fam_count[r["family"]]) / wsum
        reps = round((share + we.GAP_SECONDS) / (r["pass_seconds"] + we.GAP_SECONDS))
        r["reps"] = int(max(1, min(MAX_REPS, reps)))
    for _ in range(80):                                       # nudge single exercises one play up or down while that gets closer
        cur = abs(_total(rows) - target_s)
        best: tuple[float, int, int] | None = None
        for i, r in enumerate(rows):
            for d in (1, -1):
                nr = r["reps"] + d
                if not (1 <= nr <= MAX_REPS):
                    continue
                r["reps"] = nr
                gap = abs(_total(rows) - target_s)
                r["reps"] -= d
                if gap < cur - 1e-6 and (best is None or gap < best[0]):
                    best = (gap, i, d)
        if best is None:
            break
        rows[best[1]]["reps"] += best[2]
    for r in rows:
        r["seconds"] = round(r["reps"] * r["pass_seconds"] + (r["reps"] - 1) * we.GAP_SECONDS, 1)


def build_plan(player: we.Player, spec: dict[str, Any], *, replan: bool = True) -> dict[str, Any]:
    """Render every exercise in ``spec`` and settle its length. With ``replan`` the number of exercises may grow or shrink to fit the time."""
    target_s = float(spec["minutes"]) * 60.0
    weights = _weights(spec)
    notes: list[str] = []
    for _ in range(MAX_ITEMS + 6):
        rows, bad = [], []
        for desc in spec["items"]:
            try:
                rows.append(build_item(player, spec, desc))
            except we.WarmupUnavailable as exc:
                bad.append((desc, str(exc)))
        for desc, why in bad:                                  # an exercise this player can't be given correctly is left out, and said so
            spec["items"] = [d for d in spec["items"] if d["uid"] != desc["uid"]]
            notes.append(f"Left out {we.FAMILY_LABEL[desc['family']].lower()} exercise ({why}).")
        if bad:
            if spec.get("sax", {}).get("chart_intervals") or spec.get("sax", {}).get("jazz"):
                raise we.WarmupUnavailable("; ".join(why for _, why in bad))
            continue
        if not rows:
            raise we.WarmupUnavailable("none of the requested exercises can be built correctly for this instrument and key")
        if spec.get("single_song"):
            for row in rows:
                row["reps"], row["seconds"] = 1, row["pass_seconds"]
            target_s = _total(rows)
            spec["minutes"] = target_s / 60.0
            break
        allocate(rows, weights, target_s)
        total = _total(rows)
        if not replan:
            break
        slack = max(20.0, TOLERANCE * target_s)
        busy = max(rows, key=lambda r: r["reps"])
        if busy["reps"] > MAX_COMFORT_REPS and len(rows) < MAX_ITEMS:       # playing one exercise many times is dull: add another variant instead
            it = _new_item(spec, busy["family"])
            if it:
                spec["items"].append(it)
                spec["items"] = _ordered(spec)
                continue
        if total < target_s - slack and len(rows) < MAX_ITEMS:
            fams = sorted(spec["families"], key=lambda f: len(_items_of(spec, f)) / max(0.1, weights.get(f, 1.0)))
            added = False
            for f in fams:
                it = _new_item(spec, f)
                if it:
                    spec["items"].append(it)
                    spec["items"] = _ordered(spec)
                    added = True
                    break
            if added:
                continue
        if total > target_s + slack and len(rows) > len(spec["families"]):
            extra = [d for d in spec["items"] if not d.get("keep")]
            if extra:
                victim = extra[-1]
                spec["items"] = [d for d in spec["items"] if d["uid"] != victim["uid"]]
                continue
        if total > target_s + slack and any(d.get("size") != "short" for d in spec["items"]):
            spec["size"] = "short"
            for d in spec["items"]:
                d["size"] = "short"
            continue
        break
    if not rows or any("reps" not in row for row in rows):
        raise we.WarmupUnavailable("the requested variants could not settle into a feasible timed plan; choose a shorter routine or fewer exercise families")
    plan = {"spec": copy.deepcopy(spec), "items": rows, "total_seconds": round(_total(rows), 1), "target_seconds": round(target_s, 1),
            "transition_seconds": 0 if spec.get("single_song") else we.TRANSITION_SECONDS, "gap_seconds": we.GAP_SECONDS, "notes": notes,
            "player": {"key": player.key, "label": player.label, "written_key": player.written_key, "concert_key": player.concert_key,
                       "offset": player.offset, "semitones": player.semitones},
            "level": spec["level"], "minutes": spec["minutes"]}
    plan["id"] = "wu-" + hashlib.sha1(json.dumps([[r["uid"], r["abc"], r["reps"]] for r in rows], sort_keys=True).encode("utf-8")).hexdigest()[:10]
    if player.key=="bass":
        plan["id"]="wu-"+hashlib.sha1(json.dumps([plan["id"],[r["meta"]["bass_tab"] for r in rows]],sort_keys=True).encode()).hexdigest()[:10]
    return plan


def _first_of_family(spec: dict[str, Any], family: str) -> dict[str, Any] | None:
    have = _items_of(spec, family)
    return have[0] if have else None


# ---------------------------------------------------------------- the player for a request


def _spec_for_ttype(ttype: str) -> str:
    from music_coach_ami.exercise_adapt import SPECS

    for key, spec in SPECS.items():
        if spec.ttype and spec.ttype == ttype:
            return key
    return ""


def resolve_player(req: dict[str, Any], session_ref: Any, ctx: Any, concert_key: str) -> tuple[we.Player | None, str, dict[str, Any]]:
    """(the player, '' or why not, facts about how it was resolved)."""
    from music_coach_ami.coach_instrument import resolve_coach_instrument
    from music_coach_ami.exercise_adapt import SPECS
    from music_coach_ami.instrument_realization import resolve_transposing_subtype

    facts: dict[str, Any] = {"sax_assumed": False}
    session = session_ref if isinstance(session_ref, MutableMapping) else {}
    word = req.get("instrument_word") or ""
    sax_word = req.get("sax_type_word") or ""
    if req.get("unverified"):
        return None, (f"I can't write warmups for {req['unverified']} yet — Slice 1 covers flute, piano, saxophones (soprano, alto, tenor, baritone), trumpet "
                      f"and clarinet, the instruments whose written and sounding pitch I can verify."), facts
    if not word:
        named = resolve_coach_instrument(session, question_entity="", ctx_instrument=_clean(getattr(ctx, "instrument", "")))
        word = _clean(named).lower()
        if not word:
            return None, ("Which instrument is the warmup for? Name it in your request (for example “a flute warmup” or “an alto saxophone warmup”) or choose "
                          "your instrument in the app."), facts
    key = "bass" if word in ("bass", "bass guitar", "electric bass") else ""
    if "sax" in word:
        if sax_word:
            key = {"soprano": "soprano", "alto": "alto", "tenor": "tenor", "bari": "baritone", "baritone": "baritone"}[sax_word]
        else:
            tt = resolve_transposing_subtype(session, "Saxophone")
            key = _spec_for_ttype(tt)
            if not key:
                key, facts["sax_assumed"] = "alto", True
            else:
                facts["sax_from_app"] = SPECS[key].label
    else:
        for k in SPECS:
            if k in word:
                key = k
                break
    if not key:
        return None, (f"I don't have a verified pitch table for “{word}” yet — Slice 1 covers flute, piano, saxophones, trumpet and clarinet."), facts
    try:
        return we.make_player(key, concert_key), "", facts
    except we.WarmupUnavailable as exc:
        return None, str(exc), facts


# ---------------------------------------------------------------- the working record


def _mutable(session_ref: Any) -> MutableMapping | None:
    from music_coach_ami.session_access import as_mutable_session

    s = as_mutable_session(session_ref)
    return s if isinstance(s, MutableMapping) else None


def _state(session: MutableMapping, *, create: bool = False) -> dict[str, Any] | None:
    ensure_owner(session)
    raw = session.get(STATE_KEY)
    if isinstance(raw, dict) and raw.get("owner") == owner_token(session):
        return raw
    if not create:
        return None
    fresh = {"owner": owner_token(session), "versions": [], "cursor": -1, "active": False, "view": {"mode": "plan", "index": 0}}
    session[STATE_KEY] = fresh
    return fresh


def current(session_ref: Any) -> dict[str, Any] | None:
    """The current version's plan when a warmup is the working context (the live record, not a copy)."""
    s = _mutable(session_ref)
    st = _state(s) if s is not None else None
    if not st or not st.get("active") or not (0 <= st["cursor"] < len(st["versions"])):
        return None
    return st["versions"][st["cursor"]]["plan"]


def is_active(session_ref: Any) -> bool:
    return current(session_ref) is not None


def deactivate(session_ref: Any) -> None:
    """Another exercise became the thing the conversation is about; keep the warmup record but stop answering revisions with it."""
    s = _mutable(session_ref)
    st = _state(s) if s is not None else None
    if st:
        st["active"] = False


def history(session_ref: Any) -> dict[str, Any]:
    s = _mutable(session_ref)
    st = _state(s) if s is not None else None
    if not st:
        return {"versions": 0, "cursor": -1, "can_undo": False, "can_redo": False, "active": False}
    n, c = len(st["versions"]), st["cursor"]
    return {"versions": n, "cursor": c, "can_undo": c > 0, "can_redo": 0 <= c < n - 1, "active": bool(st.get("active")), "view": dict(st.get("view") or {})}


def _push(session: MutableMapping, plan: dict[str, Any], label: str, *, fresh: bool = False) -> None:
    st = _state(session, create=True)
    if fresh:
        st["versions"], st["cursor"] = [], -1
    ver = {"vid": plan["id"], "plan": copy.deepcopy(plan), "label": _clean(label)[:160]}
    st["versions"] = st["versions"][: st["cursor"] + 1] + [ver]
    drop = max(0, len(st["versions"]) - MAX_VERSIONS)
    if drop:
        del st["versions"][:drop]
    st["cursor"] = len(st["versions"]) - 1
    st["active"] = True
    st["view"] = {"mode": "plan", "index": 0}


# ---------------------------------------------------------------- the answers


def _a(word: str) -> str:
    return ("an " if word[:1] in "aeiou" else "a ") + word


def _family_phrase(family: str, n: int) -> str:
    base = {"long_tones": "long tones", "scale": "scale", "intervals": "interval", "articulation": "articulation", "guide_tones": "guide-tone", "chord_tones": "chord-tone arpeggio", "approach_notes": "approach-note"}[family]
    if family == "long_tones":
        return "long tones" + (f" ({n} exercises)" if n != 1 else "")
    return f"{n} {base} exercise{'s' if n != 1 else ''}"


def _mmss(seconds: float) -> str:
    s = int(round(seconds))
    return f"{s // 60}:{s % 60:02d}"


def _minutes_text(seconds: float) -> str:
    return f"{seconds / 60:.1f}".rstrip("0").rstrip(".") + " min"


def _item_line(i: int, r: dict[str, Any], gap: int) -> str:
    plays = f"play it {r['reps']}×" if r["reps"] > 1 else "play it once"
    rest = f" with {gap} s rests" if r["reps"] > 1 else ""
    return (f"{i}. **{r['title']}** — {_mmss(r['seconds'])}. ♩ = {r['bpm']} · {r['bars']} bars · {r['pass_seconds']:.0f} s per play · {plays}{rest}.")


def _header(plan: dict[str, Any], label: str) -> str:
    p = plan["player"]
    key_note = f"written key {we.key_text(*we.practical_key(*we.split_key(p['written_key'])))}"
    if p["offset"] or p["semitones"]:
        key_note += f" (concert {we.key_text(*we.split_key(p['concert_key']))})"
    mins = f"{plan['target_seconds'] / 60:g}"
    n = len(plan["items"])
    head = (f"**Your {mins}-minute {plan['level']} {p['label'].lower()} warmup** — {n} exercise{'s' if n != 1 else ''}, {key_note}. "
            f"Planned playing time {_mmss(plan['total_seconds'])}.")
    if plan["spec"].get("single_song"):
        head = (f"**Your {plan['level']} {p['label'].lower()} song exercise** - one chart pass, {key_note}. "
                f"Playing time {_mmss(plan['total_seconds'])}.")
    song = plan["spec"].get("song")
    if song:
        sel = plan["spec"]["song_sel"]
        bars = f"bars {sel['bars'][0]}–{sel['bars'][1]} of " if sel.get("bars") else ""
        parts = ws.section_parts(song, sel["section"])
        where = sel["section"] if len(parts) == 1 else f"the whole form ({' + '.join(x[0] for x in parts)}, {parts[-1][2]} bars)"
        head += (f"\n\n**Built from “{song['title'] or 'the active song'}”** — {bars}{where}, in the song's Practice Key ({we.key_text(*we.split_key(song['practice_key']))}, concert pitch); "
                 f"the chord symbols above each staff are written for your instrument. One play is one pass through that part of the chart (chart revision `{song['hash']}`).")
    if plan["spec"].get("sax"):
        settings = [f"exercise {i+1}: {r.get('instrument_label',p['label'])}, {r['item_level']}, {r['bpm']} BPM" +
                    (f", {r['meta']['chart_section']}" if r.get('meta',{}).get('sax_chart') else "") for i,r in enumerate(plan["items"])]
        head += "\n\nItem settings: " + "; ".join(settings) + "."
    return head


def _nav(plan: dict[str, Any], view: dict[str, Any]) -> dict[str, Any]:
    n = len(plan["items"])
    idx = int(view.get("index") or 0)
    mode = view.get("mode") or "plan"
    return {"plan_id": plan["id"], "count": n, "mode": mode, "index": idx, "can_next": (mode == "plan" and n > 0) or (mode == "item" and idx < n - 1),
            "can_prev": mode == "item" and idx > 0, "can_all": mode == "item"}


def _plan_response(plan: dict[str, Any], *, lead: str = "", changed: list[str] | None = None, kept: str = "", view: dict[str, Any] | None = None,
                   session_ref: Any = None, assumptions: list[str] | None = None, history_info: dict[str, Any] | None = None) -> CoachResponse:
    if plan['spec'].get('fingering'):
        from music_coach_ami.fingering_instructor import practice_response
        return practice_response(plan, session_ref, lead)
    view = view or {"mode": "plan", "index": 0}
    gap = plan["gap_seconds"]
    steps: list[str] = ["**Practice**"]
    sections: list[str] = []
    items = plan["items"]
    if view.get("mode") == "item" and items:
        i = max(0, min(int(view.get("index") or 0), len(items) - 1))
        r = items[i]
        direct = f"**Exercise {i + 1} of {len(items)}: {r['title']}**\n\n{_header(plan, '')}"
        steps = ["**How to practice it**", *[f"- {h}" for h in r["how"]],
                 f"- **Time:** ♩ = {r['bpm']}, {r['bars']} bars is {r['pass_seconds']:.0f} seconds per play; play it {r['reps']} time{'s' if r['reps'] != 1 else ''} with "
                 f"{gap} seconds of rest between plays — {_mmss(r['seconds'])} in all."]
        listen = r["listen"]
        sections = [r["abc"]]
    else:
        direct = _header(plan, "")
        steps += [_item_line(i + 1, r, gap) for i, r in enumerate(items)]
        if plan["spec"].get("single_song"):
            steps.append("Play the selected chart timeline once, then rest before repeating on your own.")
        else:
            steps.append(f"Between exercises take about {plan['transition_seconds']} seconds to breathe and turn to the next one — that is included in the total.")
        listen = []
        sections = [r["abc"] for r in items]
    if lead:
        direct = lead.strip() + "\n\n" + direct
    if changed:
        direct += "\n\n**What changed:** " + "; ".join(changed) + "."
    if kept:
        direct += f"\n\n**Kept as it was:** {kept}"
    notes = list(assumptions or []) + list(plan.get("notes") or [])
    if notes:
        direct += "\n\n" + "\n".join(f"_{n}_" for n in notes)
    hist = history_info or history(session_ref)
    nxt = ("Say “next exercise” to work through them one at a time, or change the plan: “make it shorter”, “remove the long tones”, “add more articulation work”, "
           "“make the second exercise slower”, “change the interval exercise to fourths”, “undo that”.")
    if plan["spec"].get("single_song"):
        nxt = "Ask to make exercise 1 slower, explain the notes, change its starting chord tone, or undo the last change. Ask for a timed song warmup to set a duration."
    response = CoachResponse(
        intent=CoachIntent.SCALE_PRACTICE, direct_answer=direct, practice_steps=steps, what_to_listen_for=list(listen), suggested_next_action=nxt if view.get("mode") != "item" else
        "Say “next exercise” for the next one, “show the whole warmup” for the plan, or change it (“make this one slower”).",
        notation_abc=sections[0] if sections else "", notation_abc_sections=list(sections), source_solver="AdaptiveWarmup", confidence=0.9,
        diagnostics={"musical_idea_content": True, "warmup": True, "warmup_plan_id": plan["id"], "warmup_level": plan["level"], "warmup_minutes": plan["minutes"],
                     "warmup_total_seconds": plan["total_seconds"], "warmup_target_seconds": plan["target_seconds"], "warmup_version": hist.get("cursor", 0) + 1,
                     "warmup_versions": hist.get("versions", 1), "warmup_can_undo": hist.get("can_undo", False), "warmup_can_redo": hist.get("can_redo", False),
                     "warmup_nav": _nav(plan, view), "warmup_items": [_item_summary(r) for r in items],
                     "warmup_song_aware": bool(plan["spec"].get("song")), "warmup_view": dict(view),
                     "warmup_song": _song_summary(plan)})


    if plan["player"]["key"]=="bass":
        from music_coach_ami.bass_tab import sections as tab_sections
        selected=[items[max(0,min(int(view.get("index") or 0),len(items)-1))]] if view.get("mode")=="item" and items else items
        response.diagnostics["bass_tab_sections"]=tab_sections(selected)
    return response


def _song_summary(plan: dict[str, Any]) -> dict[str, Any]:
    song = plan["spec"].get("song")
    if not song:
        return {}
    sel = plan["spec"]["song_sel"]
    return {"title": song["title"], "hash": song["hash"], "section": sel["section"], "bars": sel.get("bars"), "practice_key": song["practice_key"], "meter": song["meter"],
            "source": song.get("source"), "tones": plan["spec"].get("tones") or "", "smooth": bool(plan["spec"].get("smooth")),
            "unsupported": [{"bar": p["bar"], "chord": p["concert"], "reason": p["reason"]} for r in plan["items"] if r["family"] in SONG_FAMILIES
                            for p in (r.get("meta") or {}).get("unsupported", [])][:12]}


_ROLE_WORD = {"3": "third", "7": "seventh", "6": "sixth"}


def _explain_guide(r: dict[str, Any]) -> list[str]:
    meta = r["meta"]
    lines = [f"**Why these notes work — {r['title']}**",
             "The third says whether a chord is major or minor and the seventh gives its color (dominant, major-seventh, half-diminished...). A line that lands on them at each change outlines the harmony itself, so you hear the chords even with nothing else playing.",
             ""]
    for p in meta["segments"]:
        where = f"bar {p['bar']}" + (f", beat {p['beat'] + 1:g}" if p["beat"] else "")
        if not p["supported"]:
            lines.append(f"- {where}: **{p['concert']}** — rests: {p['reason']}.")
            continue
        up = f" and the {_ROLE_WORD.get(p['upper_role'], 'seventh')} {p['upper']}" if p.get("upper") else ""
        conc = f" (concert {p['concert']}: {p['concert_third']}" + (f" and {p['concert_upper']}" if p.get("concert_upper") else "") + ")" if p["concert"] != p["written"] else ""
        extra = f" — {p['note']}" if p.get("note") else ""
        lines.append(f"- {where}: **{p['written']}** — the third {p['third']}{up}{conc}{extra}.")
    if meta["resolutions"]:
        lines += ["", "**Where one chord leads to the next:**"]
        for x in meta["resolutions"]:
            lines.append(f"- Bar {x['from_bar']} → {x['to_bar']}: the {_ROLE_WORD[x['from_role']]} of {x['from_chord']} ({x['from_note']}) moves a {x['step']} to the third of {x['to_chord']} ({x['to_note']}).")
    lines += ["", f"Voice-leading: the largest leap in this line is {meta['largest_leap']} semitones and the average {meta['mean_leap']} (say “make the movement smoother” to reduce it)."]
    return lines


def _explain_chordline(r: dict[str, Any]) -> list[str]:
    meta = r["meta"]
    approach = r["family"] == "approach_notes"
    lines = [f"**Why these notes work — {r['title']}**",
             ("Every note except the approach notes is a tone of the chord it sits under (root, third, fifth, seventh), so the line outlines each chord. "
              "An approach note is the one kind of note that is NOT a chord tone: it sits a step away from a target chord tone and resolves onto it exactly where the chart changes chord.")
             if approach else
             "Each bar plays the notes of that chord in turn (root, third, fifth, seventh, with a sixth chord's sixth in the seventh's place), so you are playing the chord itself, and the line connects smoothly into the next chord.",
             ""]
    for p in meta["segments"]:
        where = f"bar {p['bar']}" + (f", beat {p['beat'] + 1:g}" if p["beat"] else "")
        if not p["supported"]:
            lines.append(f"- {where}: **{p['concert']}** — rests: {p['reason']}.")
            continue
        tones = [f"{lab} {p[k]}" for lab, k in (("root", "root"), ("third", "third"), ("fifth", "fifth"), (_ROLE_WORD.get(p.get("upper_role"), "seventh"), "upper")) if p.get(k)]
        conc = f" (concert {p['concert']})" if p["concert"] != p["written"] else ""
        played = " ".join(n["name"] + ("*" if n["role"] == "approach" else "") for n in p["notes"])
        lines.append(f"- {where}: **{p['written']}**{conc} — chord tones: {', '.join(tones)}. You play: {played}" + (" (* = approach note)" if approach and "*" in played else ""))
    if approach:
        lines += ["", "**Each approach and what it resolves to:**"]
        for a in meta.get("approaches", []):
            word = {"R": "root", "3": "third", "5": "fifth", "7": "seventh", "6": "sixth"}.get(a["target_role"], a["target_role"])
            steps = " then ".join(f"{n} ({o:+d} semitone{'s' if abs(o) != 1 else ''} from the target)" for n, o in zip(a["approach"], a["offsets"]))
            lines.append(f"- Bar {a['from_bar']} → {a['to_bar']} (beat {a['to_beat'] + 1:g}): {a['from_chord']} → {a['to_chord']}: {steps} → the {word} {a['target']}"
                         + (" — back to the top of the form for the repeat" if a["loop_back"] else "") + (f". {a['note']}" if a.get("note") else "") + ".")
        for sk in meta.get("skipped_approaches", []):
            lines.append(f"- No approach into bar {sk['to_bar']} ({sk['to_chord']}): {sk['reason']}.")
    lines += ["", f"Voice-leading: the largest leap is {meta['largest_leap']} semitones and the average {meta['mean_leap']} (say “make the movement smoother” to reduce it)."]
    return lines


def _explain_text(plan: dict[str, Any], view: dict[str, Any]) -> str:
    """Why the notes work, from the chords and notes actually stored in this warmup (nothing is looked up or guessed)."""
    songs = [r for r in plan["items"] if r["family"] in SONG_FAMILIES]
    if not songs:
        r = plan["items"][max(0, min(int(view.get("index") or 0), len(plan["items"]) - 1))] if view.get("mode") == "item" else plan["items"][0]
        lines = [f"**Why these notes work — {r['title']}**", *[f"- {h}" for h in r["how"]], *[f"- {x}" for x in r["listen"]]]
        return "\n".join(lines) + "\n\n_This warmup isn't built from a song's chords; ask for “guide tones over the chorus” to get notes tied to a chart._"
    if view.get("mode") == "item" and plan["items"][min(int(view.get("index") or 0), len(plan["items"]) - 1)]["family"] in SONG_FAMILIES:
        picks = [plan["items"][min(int(view.get("index") or 0), len(plan["items"]) - 1)]]
    else:
        picks, seen = [], set()
        for r in songs:                                   # the whole plan: one explanation per kind of song exercise
            if r["family"] not in seen:
                seen.add(r["family"])
                picks.append(r)
    out: list[str] = []
    for r in picks:
        out += (_explain_guide(r) if r["family"] == "guide_tones" else _explain_chordline(r)) + [""]
    return "\n".join(out).rstrip()


def _item_summary(r: dict[str, Any]) -> dict[str, Any]:
    keys = ("uid", "family", "title", "bpm", "bars", "pass_seconds", "reps", "seconds", "key", "written_midi", "sounding_midi", "range", "abc", "params",
            "tempo_override", "size", "checks", "written_notes")
    return {k: copy.deepcopy(r.get(k)) for k in keys}


def _simple(direct: str, steps: list[str] | None = None, *, failed: str = "", plan: dict[str, Any] | None = None, session_ref: Any = None,
            extra: dict[str, Any] | None = None) -> CoachResponse:
    diag: dict[str, Any] = {"musical_idea_content": True, "warmup": True, "warmup_failed": bool(failed), "warmup_failure_reason": failed, **(extra or {})}
    if plan is not None:
        diag["warmup_plan_id"] = plan["id"]
        diag["warmup_nav"] = _nav(plan, (_state(_mutable(session_ref)) or {}).get("view") or {"mode": "plan", "index": 0}) if session_ref is not None else {}
    return CoachResponse(intent=CoachIntent.SCALE_PRACTICE, direct_answer=direct, practice_steps=list(steps or []), source_solver="AdaptiveWarmup",
                         confidence=0.9, diagnostics=diag)


_SONG_SUPPORTED = ("; for a song-aware warmup also “just the first four bars” (or “the last four bars”, “bars 5 to 8”), “only the bridge” (any section of the song), "
                   "“the whole song”, “use thirds only”, “now practice the sevenths”, “start each arpeggio on the third”, “add approaches from below”, “use an enclosure before the next chord”, "
                   "“make the arpeggio exercise more advanced”, “make the movement smoother”, “change it to tenor sax”, and “explain why those notes work”")
_SUPPORTED = ("make the whole warmup shorter or longer (or “make it 5 minutes”), more advanced or easier, remove the long tones (or any family, or “remove exercise 2”), "
              "add more articulation work (or a scale, interval or long-tone exercise), make one exercise slower or faster (“make the second exercise slower”, "
              "“set exercise 3 to 80 BPM”), change the interval exercise to thirds, fourths, fifths and so on, go through the exercises one at a time "
              "(“next exercise”, “previous exercise”, “show the whole warmup”), and “undo that” or “redo”")


def _unsupported(session_ref: Any, plan: dict[str, Any], reason: str = "") -> CoachResponse:
    more = _SONG_SUPPORTED if plan["spec"].get("song") else "; “change it to tenor sax” (or another instrument) rewrites every exercise for that instrument"
    return _simple((reason or "I can't make that change to the warmup in this first version.") + " The warmup is unchanged.",
                   [f"What I can change: {_SUPPORTED}{more}."], failed="unsupported", plan=plan, session_ref=session_ref)


# ---------------------------------------------------------------- creating a warmup


def _page_values(question: str, session_ref: Any, ami_ctx: dict[str, Any] | None) -> tuple[Any, dict[str, Any]]:
    from music_coach_ami.router import route_question

    req = route_question(question, session_ref if isinstance(session_ref, MutableMapping) else {}, ami_ctx=ami_ctx)
    return req.context, {"entities": req.entities}


def _song_refusal(why: str, offer_ordinary: bool = True) -> CoachResponse:
    tail = " If you'd like, ask for an ordinary warmup — for example “Give me a 10-minute warmup” — and I'll build that from your instrument, level and key." if offer_ordinary else ""
    return _simple(why + tail, failed="song_unavailable")


def _song_setup(question: str, ctx: Any, req: dict[str, Any], sinfo: dict[str, Any], assumptions: list[str]) -> tuple[dict[str, Any] | None, dict[str, Any] | None, CoachResponse | None, str]:
    """(song record, selection, an early answer, why a song-aware warmup could not be built when an ordinary one is still fine)."""
    explicit = bool(sinfo["guide_explicit"] or sinfo["song_families"] or set(req["families"]) & set(SONG_FAMILIES))
    song, why = ws.read_song(ctx)
    if song is None:
        if sinfo["named"] or explicit:
            who = f"“{sinfo['named']}”" if sinfo["named"] else "the song"
            return None, None, _song_refusal(f"I can't build a chord-aware exercise over {who} yet: {why}. Select the song you want to practice (or open its chart), then ask again — "
                                              "I only use the active song's chart and won't guess its chords."), ""
        return None, None, None, f"I couldn't read an active song's chart ({why})"
    if sinfo["named"]:
        other = ws.named_song_conflict(sinfo["named"], song)
        if other:
            return None, None, _song_refusal(f"You asked for “{other}”, but the active song is “{song['title'] or 'the current song'}”. I won't substitute one for the other: select or activate "
                                               f"“{other}” first, then ask again.", offer_ordinary=False), ""
    if ws.sph._beats_per_bar(song.get("meter") or "4/4") != 4:
        msg = f"this chart is in {song.get('meter')}; chord-aware warmups are written in 4/4 for now"
        return (None, None, _song_refusal(f"I can't build that yet: {msg}."), "") if explicit else (None, None, None, msg)
    asked = ws.find_section(song["order"], question) or sinfo["section"]
    if sinfo["whole"]:
        song2, how_w, why_w = ws.with_whole_form(song)
        if not how_w:
            return None, None, _song_refusal(f"I can't build the whole form: {why_w}.", offer_ordinary=False), ""
        parts = ws.whole_form(song)[0]
        if song2 is song:
            name, how = parts[0], "whole_named"
            assumptions.append(f"The whole form is the chart's own “{name}” section ({len(ws.section_slots(song, name))} bars).")
        else:
            song, name, how = song2, ws.WHOLE_FORM_NAME, "whole_form"
            assumptions.append(f"The whole form is the chart's sections in the order it lists them: {' + '.join(parts)} ({len(ws.section_slots(song, name))} bars). I haven't added or repeated anything the chart doesn't have.")
    else:
        name, how = ws.pick_section(song, asked)
    sel: dict[str, Any] = {"section": name, "how": how, "bars": None}
    n_bars = len(ws.section_slots(song, name))
    b = sinfo["bars"] or {}
    if b.get("first"):
        sel["bars"] = [1, min(n_bars, int(b["first"]))]
    elif b.get("last"):
        sel["bars"] = [max(1, n_bars - int(b["last"]) + 1), n_bars]
    elif b.get("range"):
        a, z = b["range"]
        if not (1 <= a <= z <= n_bars):
            return None, None, _song_refusal(f"{name} has {n_bars} bars, so bars {a}–{z} don't exist.", offer_ordinary=False), ""
        sel["bars"] = [a, z]
    if sel["bars"] == [1, n_bars]:
        sel["bars"] = None
    if how in ("whole_named", "whole_form"):
        pass
    elif asked and how in ("active_section", "not_an_intro"):
        assumptions.append(f"I couldn't find a section called “{asked}” in this chart ({', '.join(song['order'])}), so I used {name}.")
    elif how == "named" and ws._norm(sinfo["section"]) in ("chorus", "choruses", "head", "form") and ws._norm(name) != ws._norm(sinfo["section"]):
        assumptions.append(f"This chart has no section named “{sinfo['section']}”, so I used {name} as the chorus.")
    elif how == "chorus_is_active_section":
        assumptions.append(f"This chart has no section named “chorus”, so I used the section you have open as the chorus: {name}.")
    elif how == "not_an_intro":
        assumptions.append(f"The section you have open ({song['active_section']}) is an intro or ending, so I used {name} — say “only the bridge” (or any section of the song) to change it.")
    elif how == "active_section":
        assumptions.append(f"Section: {name}, the one you have open — say “only the bridge” (or any section of the song) to change it.")
    return song, sel, None, ""


def _song_feasibility(player: we.Player, song: dict[str, Any], sel: dict[str, Any]) -> str:
    """'' when a trustworthy guide-tone exercise can be written for this player and section; otherwise the reason, naming chords and bars."""
    try:
        segs, _lo, _hi = ws.build_timeline(song, sel["section"], tuple(sel["bars"]) if sel.get("bars") else None, player.offset, player.semitones)
    except ws.SongUnavailable as exc:
        return str(exc)
    bad = [x for x in segs if not x.ok]
    total = sum((x.beats for x in segs), ws.Fraction(0))
    good = sum((x.beats for x in segs if x.ok), ws.Fraction(0))
    if not good or good / total < ws.MIN_SUPPORTED_SHARE:
        return "too much of that part of the chart can't be written correctly — " + "; ".join(f"{x.chord} (bar {x.src_bar}): {x.reason}" for x in bad[:4])
    return ""



def create(question: str, session_ref: Any, ami_ctx: dict[str, Any] | None = None, request: dict[str, Any] | None = None) -> CoachResponse:
    session = _mutable(session_ref)
    if session is None:
        return _simple("I can't keep a warmup in this session.", failed="no_session")
    ctx, _ = _page_values(question, session, ami_ctx)
    req = request if request is not None else parse_request(question)       # ``request``: the rules' reading, completed by a validated interpretation
    assumptions: list[str] = []
    page_focus = _focus_key(_clean(getattr(ctx, "practice_focus", "")))
    if not req["families"] and not req["focus"] and page_focus == "harmony":
        req = {**req, "families": ["guide_tones", "chord_tones"], "focus_selected": True}
        assumptions.append("Your Harmony focus selects guide tones and arpeggios from the active song's chart.")
    sinfo = song_request_info(question)
    song = sel = None
    song_fallback = ""
    explicit_guide = bool(sinfo["guide_explicit"] or sinfo["song_families"] or set(req["families"]) & set(SONG_FAMILIES))
    if (sinfo["wants_song"] or explicit_guide) and sinfo["tones"] and set(req["families"]) <= {"intervals", "guide_tones"}:
        # in a song-aware request "thirds" / "sevenths" name the guide tones to practice, not an interval exercise
        req = {**req, "families": [f for f in req["families"] if f != "intervals"], "intervals": []}
    if sinfo["wants_song"] or explicit_guide:
        song, sel, early, song_fallback = _song_setup(question, ctx, req, sinfo, assumptions)
        if early is not None:
            return early
        if song is not None and req["families"] and not set(req["families"]) & set(SONG_FAMILIES):
            song_fallback, song, sel = "song-aware exercises (guide tones, arpeggios, approach notes) are included only when you ask for them", None, None
    # A plain song arpeggio request is one chart pass, not a default timed routine.
    single_song = bool(song is not None and req["minutes"] is None and (req["families"] == ["chord_tones"] or req.get("sax_single_song") and len(req["families"])==1)
                       and not _WARM.search(question) and not re.search(r"\bwarm\s+(?:me|us)\s+up\b", question, re.I))
    # length
    minutes = req["minutes"]
    if single_song:
        minutes, m_source = 0.0, "single_pass"
    elif minutes is None:
        minutes, m_source = float(DEFAULT_MINUTES), "default"
        assumptions.append(f"You didn't say how long, so I planned {DEFAULT_MINUTES} minutes.")
    else:
        m_source = "request"
        if minutes > MAX_MINUTES:
            return _simple(f"I keep warmups to {MAX_MINUTES} minutes at most — a longer one is really a practice session. Ask again with {MAX_MINUTES} minutes or fewer.",
                           failed="too_long")
        if minutes < MIN_MINUTES:
            assumptions.append(f"{minutes:g} minute{'s' if minutes != 1 else ''} is shorter than the shortest warmup I plan, so I used {MIN_MINUTES} minutes.")
            minutes = float(MIN_MINUTES)
    # level
    page_level = _clean(getattr(ctx, "level", ""))
    if req["level"]:
        level, l_source = req["level"], "request"
    elif page_level.capitalize() in we.LEVELS:
        level, l_source = page_level.capitalize(), "page"
        assumptions.append(f"Level: {level}, from your app setting — say “beginner” or “advanced” to change it.")
    else:
        level, l_source = "Intermediate", "default"
        assumptions.append("Level: Intermediate (no level was set) — say “beginner” or “advanced” to change it.")
    # key
    page_key = _clean(getattr(ctx, "current_practice_key", ""))
    if song is not None:
        concert, k_source = song["practice_key"], "song"
        if req["key"] and req["key"] != concert:
            assumptions.append(f"You named {we.key_text(*we.split_key(req['key']))}, but a song-aware warmup follows the song's own Practice Key, {we.key_text(*we.split_key(concert))}.")
    elif req["key"]:
        concert, k_source = req["key"], "request"
    elif page_key:
        concert, k_source = page_key, "practice_key"
    else:
        concert, k_source = "C", "default"
    player, why, facts = resolve_player(req, session, ctx, concert)
    if player is None:
        return _simple(why, failed="no_player")
    if facts.get("sax_assumed"):
        assumptions.append("Saxophone type: Alto — choose your saxophone in the app or say “tenor saxophone” to change it.")
    elif facts.get("sax_from_app"):
        assumptions.append(f"Saxophone: {facts['sax_from_app']}, from your app setting — say “tenor saxophone” (or another type) to change it.")
    if req["key"]:
        assumptions.append(f"Key: {we.key_text(*we.split_key(req['key']))} (concert pitch, as the Practice Key is).")
    if song is not None:
        why_not = _song_feasibility(player, song, sel)
        if why_not:
            if explicit_guide:
                return _song_refusal(f"I can't give you a trustworthy guide-tone exercise over {sel['section']} for {player.label}: {why_not}. I won't invent chord tones or drop harmonic time.")
            song_fallback, song, sel = why_not, None, None
    # families
    order_pref: list[str] = []
    mixed_default = False
    if song is not None and req["families"]:
        families = list(req["families"])
        order_pref = [f for f in sinfo["spoken"] if f in families]       # the exercises the musician named, in the order they named them
    elif song is not None and (sinfo["tones"] or sinfo["guide_explicit"]):
        families = ["guide_tones"]
    elif song is not None:
        families = list(DEFAULT_SONG_FAMILIES[level])
        mixed_default = True
        assumptions.append("Because you asked to be warmed up for soloing over a song, I mixed " + ", ".join(we.FAMILY_LABEL[f].lower() for f in families)
                           + " — say “only guide tones” or “just arpeggios” to narrow it, or name the exercises you want.")
    else:
        focus_families = {"tone": ["long_tones", "scale"], "technique": ["scale", "intervals", "articulation"],
                          "articulation": ["articulation", "scale"], "melody": ["scale", "intervals"]}
        families = list(req["families"]) or list(focus_families.get(page_focus, DEFAULT_FAMILIES[level]))
    if song is None and set(families) & set(SONG_FAMILIES):
        families = [f for f in families if f not in SONG_FAMILIES] or list(DEFAULT_FAMILIES[level])
    dropped: list[str] = []
    for f in list(families):
        reason = we.supports(player, f)
        if reason:
            families.remove(f)
            dropped.append(f"Left out {we.FAMILY_LABEL[f].lower()}: {reason}.")
    if not families:
        return _simple("; ".join(dropped).replace("Left out ", "I can't build that for this instrument — ") or "There's nothing I can build for that request.", failed="no_family")
    explicit = bool(req["families"]) and not req.get("focus_selected")
    focus = req["focus"] or _focus_key(_clean(getattr(ctx, "practice_focus", "")))
    if req["derived_from"]:
        chosen = [we.FAMILY_LABEL[f].lower() for f in req["families"] if f in we.FAMILY_LABEL]
        assumptions.append(f"You asked for {req['derived_from']} work, so I chose " + (", ".join(chosen[:-1]) + " and " + chosen[-1] if len(chosen) > 1 else "".join(chosen))
                           + (" (with two-note articulation)" if "articulation" in chosen else "") + ".")
    if req["excluded"]:
        assumptions.append("Left out, as you asked: " + ", ".join(we.FAMILY_LABEL[f].lower() for f in req["excluded"]) + ".")
    if not req["families"]:
        families = [f for f in families if f not in req["excluded"]]
    spec: dict[str, Any] = {
        "instrument": player.key, "level": level, "level_source": l_source, "minutes": minutes, "minutes_source": m_source, "concert_key": concert,
        "key_source": k_source, "families": families, "explicit": explicit, "excluded": list(req["excluded"]), "focus": focus,
        "intervals": _interval_pool(req, families, level, assumptions), "widening": _widening(req, families), "artic": list(req["artic"]), "more": dict(req.get("more") or {}), "tempo_scale": 1.0, "size": "full",
        "items": [], "uid_counter": 0, "song_aware_requested": bool(req["song_aware"]), "source_question": _clean(question)[:200],
        "song": song, "song_sel": sel, "tones": (sinfo["tones"] if song is not None else ""), "smooth": False,
        "chord_start": (sinfo["chord_start"] if song is not None else ""), "approach_kind": (sinfo["approach_kind"] if song is not None else ""), "order_pref": order_pref,
        "family_caps": ({"scale": 1} if mixed_default else {}),
    }
    if player.key in ("soprano","alto","tenor","baritone") and req.get("sax_settings"):
        spec["sax"]=copy.deepcopy(req["sax_settings"])
    if player.key=="bass" and req.get("bass_rules"):
        spec["bass_fingering"]={"*":{"rules":req["bass_rules"]}}
    if single_song:
        spec["single_song"] = True
    if mixed_default:
        spec["more"] = {**spec["more"], "scale": 0.4}                  # a short scale to start, not a third of the warmup
    initial_items(spec)
    try:
        plan = build_plan(player, spec)
    except we.WarmupUnavailable as exc:
        return _simple(f"I couldn't build that warmup correctly for {player.label} in {we.key_text(*we.split_key(player.written_key))}: {exc}.", failed="unavailable")
    _push(session, plan, question, fresh=True)
    lead = ""
    song_title = _clean(((ami_ctx or {}).get("active_song") or {}).get("title"))
    if song is not None:
        assumptions.append("Song-aware exercises use the active chart: guide tones, chord-tone arpeggios and approach notes are available.")
    elif song_fallback or req["song_aware"] or (song_title and song_title.lower() in question.lower()):
        why = song_fallback or "song-aware warmups currently cover guide tones only, and you didn't ask for them"
        lead = (f"_This warmup isn't tailored to a song's chords: {why}. It is built from your instrument, level and key. "
                "Ask for “guide tones over the chorus” to build one from the active song's chart._")
    resp = _plan_response(plan, lead=lead, assumptions=assumptions + dropped, session_ref=session)
    resp.diagnostics["warmup_song_aware_requested"] = bool(req["song_aware"])
    resp.diagnostics["warmup_spec"] = {k: spec[k] for k in ("instrument", "level", "minutes", "concert_key", "families", "explicit", "excluded", "focus")}
    return resp


# ---------------------------------------------------------------- revising a warmup


def _player_of(plan: dict[str, Any]) -> we.Player:
    p = plan["player"]
    return we.make_player(p["key"], p["concert_key"])


def _resolve_ref(items: list[dict[str, Any]], ref: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    if ref.get("index"):
        i = ref["index"]
        i = len(items) if i == -1 else i
        if not (1 <= i <= len(items)):
            return [], f"The warmup has {len(items)} exercises, so there is no exercise {ref['index']}."
        return [items[i - 1]], ""
    if ref.get("family"):
        hits = [d for d in items if d["family"] == ref["family"]]
        if not hits:
            return [], f"There's no {we.FAMILY_LABEL[ref['family']].lower()} exercise in this warmup."
        return hits, ""
    return [], ""


def _song_items_of(spec: dict[str, Any], ref: dict[str, Any]) -> list[dict[str, Any]]:
    """The song exercises a reference points at: 'exercise 2' (when that is one) or every exercise of a named kind ('the arpeggio exercise'); [] otherwise."""
    hits, err = _resolve_ref(spec["items"], ref)
    return list(hits) if (not err and hits and all(h["family"] in SONG_FAMILIES for h in hits) and (ref.get("family") or len(hits) == 1)) else []


def _index_of(plan: dict[str, Any], uid: str) -> int:
    return next((i + 1 for i, r in enumerate(plan["items"]) if r["uid"] == uid), 0)


def _contract(old: dict[str, Any], new: dict[str, Any], *, untouched_uids: set[str]) -> str:
    """Everything the musician did not ask to change is still exactly as it was: same notation for every untouched exercise."""
    old_by = {r["uid"]: r for r in old["items"]}
    new_by = {r["uid"]: r for r in new["items"]}
    for uid in untouched_uids:
        if uid in old_by and uid in new_by and old_by[uid]["abc"] != new_by[uid]["abc"]:
            return f"exercise {uid} changed although it wasn't asked to"
    return ""


def _rebuild(plan: dict[str, Any], spec: dict[str, Any], *, replan: bool) -> dict[str, Any]:
    return build_plan(_player_of(plan), spec, replan=replan)


def _retarget_reps_for_item(old_plan: dict[str, Any], new_plan: dict[str, Any], uid: "str | set[str]") -> None:
    """A tempo or level change on some exercises keeps each one's share of the time (fewer plays when it is slower) and leaves every other exercise's plays alone."""
    if new_plan["spec"].get("single_song"):
        return
    uids = {uid} if isinstance(uid, str) else set(uid)
    old_by = {r["uid"]: r for r in old_plan["items"]}
    for r in new_plan["items"]:
        if r["uid"] not in uids and r["uid"] in old_by:
            r["reps"] = old_by[r["uid"]]["reps"]
    for tgt in (r for r in new_plan["items"] if r["uid"] in uids and r["uid"] in old_by):
        old_share = old_by[tgt["uid"]]["seconds"]
        tgt["reps"] = min(range(1, MAX_REPS + 1), key=lambda k: abs(k * tgt["pass_seconds"] + (k - 1) * we.GAP_SECONDS - old_share))
    for r in new_plan["items"]:
        r["seconds"] = round(r["reps"] * r["pass_seconds"] + (r["reps"] - 1) * we.GAP_SECONDS, 1)
    new_plan["total_seconds"] = round(_total(new_plan["items"]), 1)


def _commit(session: MutableMapping, plan: dict[str, Any], label: str) -> None:
    plan["id"] = "wu-" + hashlib.sha1(json.dumps([[r["uid"], r["abc"], r["reps"], r["bpm"]] for r in plan["items"]], sort_keys=True).encode("utf-8")).hexdigest()[:10]
    _push(session, plan, label)


def revise(op: dict[str, Any], question: str, session_ref: Any, ami_ctx: dict[str, Any] | None = None) -> CoachResponse:
    session = _mutable(session_ref)
    st = _state(session) if session is not None else None
    plan0 = current(session_ref)
    if session is None or st is None or plan0 is None:
        return _simple("There's no warmup from this conversation to change yet. Ask for one first — for example “Give me a 10-minute flute warmup”.", failed="no_warmup")
    kind = op["op"]
    spec = copy.deepcopy(plan0["spec"])
    hist = history(session)

    # ----- history and views (no new version for a view)
    if kind == OP_UNDO:
        if not hist["can_undo"]:
            return _simple("There's nothing to undo — this is the first version of the warmup.", failed="nothing_to_undo", plan=plan0, session_ref=session)
        st["cursor"] -= 1
        st["view"] = {"mode": "plan", "index": 0}
        prev = st["versions"][st["cursor"]]
        return _plan_response(prev["plan"], lead=f"Undid your last change (“{st['versions'][st['cursor'] + 1]['label']}”). The warmup is back to the version before it.",
                              session_ref=session)
    if kind == OP_REDO:
        if not hist["can_redo"]:
            return _simple("There's nothing to redo.", failed="nothing_to_redo", plan=plan0, session_ref=session)
        st["cursor"] += 1
        st["view"] = {"mode": "plan", "index": 0}
        nxt = st["versions"][st["cursor"]]
        return _plan_response(nxt["plan"], lead=f"Redid “{nxt['label']}”.", session_ref=session)
    n = len(plan0["items"])
    view = dict(st.get("view") or {"mode": "plan", "index": 0})
    if kind in (OP_NEXT, OP_PREV, OP_ALL, OP_GOTO):
        if kind == OP_ALL:
            st["view"] = {"mode": "plan", "index": 0}
            return _plan_response(plan0, session_ref=session)
        if kind == OP_GOTO:
            i = op["index"]
            i = n if i == -1 else i
            if not (1 <= i <= n):
                return _simple(f"The warmup has {n} exercises, so there is no exercise {op['index']}.", failed="no_such_exercise", plan=plan0, session_ref=session)
            st["view"] = {"mode": "item", "index": i - 1}
        elif kind == OP_NEXT:
            if view["mode"] == "plan":
                st["view"] = {"mode": "item", "index": 0}
            elif view["index"] + 1 < n:
                st["view"] = {"mode": "item", "index": view["index"] + 1}
            else:
                st["view"] = {"mode": "plan", "index": 0}
                return _plan_response(plan0, lead="That was the last exercise — here is the whole warmup again.", session_ref=session)
        else:
            if view["mode"] != "item" or view["index"] == 0:
                st["view"] = {"mode": "plan", "index": 0}
                return _plan_response(plan0, lead="You're at the start — here is the whole warmup.", session_ref=session)
            st["view"] = {"mode": "item", "index": view["index"] - 1}
        return _plan_response(plan0, view=st["view"], session_ref=session)
    if kind == OP_UNSUPPORTED:
        return _unsupported(session, plan0)
    if kind == OP_EXPLAIN:
        return _plan_response(plan0, lead=_explain_text(plan0, view), view=view, session_ref=session)

    # ----- changes (a new version each)
    try:
        player = _player_of(plan0)
    except we.WarmupUnavailable as exc:
        return _unsupported(session, plan0, str(exc))
    changed: list[str] = []
    kept = ""
    replan = True
    touched: set[str] = set()
    tempo_uid = ""
    lvl_uids: set[str] = set()
    if kind in (OP_SHORTER, OP_LONGER, OP_MINUTES):
        if spec.get("single_song"):
            return _unsupported(session, plan0, "This song exercise plays one chart pass. Ask for a timed song warmup to set a duration.")
        old_m = float(spec["minutes"])
        if kind == OP_MINUTES:
            new_m = float(op["minutes"])
        elif kind == OP_SHORTER:
            new_m = max(float(MIN_MINUTES), float(round(old_m * 0.6)))
        else:
            new_m = min(float(MAX_MINUTES), float(round(old_m * 1.5)))
        if new_m > MAX_MINUTES:
            return _unsupported(session, plan0, f"I keep warmups to {MAX_MINUTES} minutes at most.")
        if new_m < MIN_MINUTES:
            new_m = float(MIN_MINUTES)
        if abs(new_m - old_m) < 1e-9:
            return _unsupported(session, plan0, f"The warmup is already {old_m:g} minutes{' — the shortest I plan' if old_m <= MIN_MINUTES else ''}.")
        spec["minutes"] = new_m
        changed.append(f"length {old_m:g} → {new_m:g} minutes")
        kept = "the level, the key, your tempo choices and every exercise's notes; only the number of plays (and, if needed, which variants are included) is re-planned."
    elif kind in (OP_HARDER, OP_EASIER, OP_LEVEL):
        old = spec["level"]
        new = (LEVEL_UP.get(old) if kind == OP_HARDER else LEVEL_DOWN.get(old) if kind == OP_EASIER else op["level"])
        if not new:
            return _unsupported(session, plan0, f"The warmup is already {old}" + (" — the top level I have, so there is nothing harder yet." if kind == OP_HARDER else " — the easiest level."))
        if new == old:
            return _unsupported(session, plan0, f"The warmup is already {old}.")
        spec["level"], spec["level_source"] = new, "revision"
        _dedupe_guide(spec)
        for d in spec["items"]:
            d["tempo"] = None
        spec["tempo_scale"] = 1.0
        spec["items"] = [d for d in spec["items"]]
        changed.append(f"level {old} → {new} (new tempos, ranges and rhythms for {new})")
        kept = "the instrument, the key, the length, and which kinds of exercise are included."
    elif kind == OP_REMOVE_FAMILY:
        fam = op["family"]
        if fam not in {d["family"] for d in spec["items"]}:
            return _unsupported(session, plan0, f"There are no {we.FAMILY_LABEL[fam].lower()} exercises in this warmup.")
        if len({d["family"] for d in spec["items"]}) == 1:
            return _unsupported(session, plan0, "That would remove the whole warmup.")
        gone = [d for d in spec["items"] if d["family"] == fam]
        spec["items"] = [d for d in spec["items"] if d["family"] != fam]
        spec["families"] = [f for f in spec["families"] if f != fam]
        spec["excluded"] = sorted(set(spec.get("excluded") or []) | {fam})
        changed.append(f"removed the {_family_phrase(fam, len(gone))}")
        kept = f"the other exercises exactly as they were; the warmup stays {spec['minutes']:g} minutes, so their plays are re-planned."
    elif kind == OP_REMOVE_ITEM:
        hits, err = _resolve_ref(spec["items"], {"index": op["index"]})
        if err:
            return _unsupported(session, plan0, err)
        if len(spec["items"]) == 1:
            return _unsupported(session, plan0, "That would remove the whole warmup.")
        d = hits[0]
        spec["items"] = [x for x in spec["items"] if x["uid"] != d["uid"]]
        if not _items_of(spec, d["family"]):
            spec["families"] = [f for f in spec["families"] if f != d["family"]]
        changed.append(f"removed exercise {op['index'] if op['index'] != -1 else len(plan0['items'])} ({we.FAMILY_LABEL[d['family']].lower()})")
        kept = f"the other exercises exactly as they were; the warmup stays {spec['minutes']:g} minutes, so their plays are re-planned."
    elif kind in (OP_ADD_FAMILY, OP_MORE_FAMILY):
        fam = op["family"]
        reason = we.supports(player, fam)
        if reason:
            return _unsupported(session, plan0, f"I can't add {we.FAMILY_LABEL[fam].lower()} for {player.label}: {reason}.")
        if fam not in spec["families"]:
            spec["families"].append(fam)
        spec["excluded"] = [f for f in spec.get("excluded") or [] if f != fam]
        if op.get("artic") and fam == "articulation":
            spec["artic"] = list(dict.fromkeys(["two_note", *(spec.get("artic") or [])]))
        spec["more"] = {**(spec.get("more") or {}), fam: float((spec.get("more") or {}).get(fam, 1.0)) * 1.6}
        it = _new_item(spec, fam)
        if it is None:
            return _unsupported(session, plan0, f"The warmup already has as many {we.FAMILY_LABEL[fam].lower()} exercises as I can vary.")
        if fam == "articulation" and op.get("artic"):
            it["params"]["pattern"] = "two_note"
        it["keep"] = True
        spec["items"].append(it)
        spec["items"] = _ordered(spec)
        changed.append(f"added {_a(we.FAMILY_LABEL[fam].lower())} exercise" + (" and gave that kind of exercise more of the time" if kind == OP_MORE_FAMILY else ""))
        touched.add(it["uid"])
        kept = f"every existing exercise's notes; the warmup stays {spec['minutes']:g} minutes, so the plays are re-planned."
    elif kind in (OP_ITEM_SLOWER, OP_ITEM_FASTER) and op.get("challenge") and _song_items_of(spec, op["ref"]):
        group = _song_items_of(spec, op["ref"])
        moves = []
        for d in group:
            cur = d.get("level") or spec["level"]
            new = LEVEL_UP.get(cur) if kind == OP_ITEM_FASTER else LEVEL_DOWN.get(cur)
            if new:
                moves.append((d, cur, new))
        if not moves:
            cur = group[0].get("level") or spec["level"]
            return _unsupported(session, plan0, f"The {we.FAMILY_LABEL[group[0]['family']].lower()} exercise{'s are' if len(group) > 1 else ' is'} already at {cur}, the "
                                                + ("top" if kind == OP_ITEM_FASTER else "easiest") + " level I have for " + ("them." if len(group) > 1 else "it."))
        keep_ids = {d["uid"] for d, _c, _n in moves}
        for d, _cur, new in moves:
            d["level"] = new
        _dedupe_guide(spec)
        keep_ids &= {d["uid"] for d in spec["items"]}
        touched |= keep_ids
        lvl_uids = set(keep_ids)
        replan = False
        for d, cur, new in moves:
            if d["uid"] in keep_ids:
                changed.append(f"exercise {_index_of(plan0, d['uid'])} ({we.FAMILY_LABEL[d['family']].lower()}) {cur} → {new}: its rhythm, tempo and shapes are the {new} ones, on the same chords")
        kept = "every other exercise exactly as it was; these keep about the same time by adjusting how many times you play them."
    elif kind in (OP_ITEM_SLOWER, OP_ITEM_FASTER, OP_ITEM_TEMPO):
        hits, err = _resolve_ref(spec["items"], op["ref"])
        if err:
            return _unsupported(session, plan0, err)
        if len(hits) != 1:
            names = ", ".join(f"exercise {_index_of(plan0, d['uid'])}" for d in hits)
            return _unsupported(session, plan0, f"More than one exercise matches ({names}). Say which one, for example “make exercise {_index_of(plan0, hits[0]['uid'])} slower”.")
        d = hits[0]
        row = next(r for r in plan0["items"] if r["uid"] == d["uid"])
        old_bpm = int(row["bpm"])
        if kind == OP_ITEM_TEMPO:
            new_bpm = int(op["bpm"])
        else:
            step = max(4, int(round(old_bpm * 0.1 / 2) * 2))
            new_bpm = old_bpm - step if kind == OP_ITEM_SLOWER else old_bpm + step
        if not (36 <= new_bpm <= 160):
            return _unsupported(session, plan0, f"♩ = {new_bpm} is outside the 36–160 range I write exercises in.")
        if new_bpm == old_bpm:
            return _unsupported(session, plan0, f"Exercise {_index_of(plan0, d['uid'])} is already at ♩ = {old_bpm}.")
        d["tempo"] = new_bpm
        touched.add(d["uid"])
        tempo_uid = d["uid"]
        replan = False
        changed.append(f"exercise {_index_of(plan0, d['uid'])} ({we.FAMILY_LABEL[d['family']].lower()}) ♩ = {old_bpm} → {new_bpm}"
                       + (" (a faster tempo is how I make a single exercise more challenging)" if op.get("challenge") and kind == OP_ITEM_FASTER else
                          " (a slower tempo is how I make a single exercise easier)" if op.get("challenge") else ""))
        kept = "every other exercise exactly as it was (notes, tempo and plays); this one keeps about the same time by adjusting how many times you play it."
    elif kind in (OP_WHOLE_SLOWER, OP_WHOLE_FASTER):
        f = 0.9 if kind == OP_WHOLE_SLOWER else 1.1
        new_scale = round(float(spec.get("tempo_scale") or 1.0) * f, 3)
        if not (0.5 <= new_scale <= 1.6):
            return _unsupported(session, plan0, "That's as far as I'll move the whole warmup's tempo.")
        spec["tempo_scale"] = new_scale
        changed.append(f"every exercise's tempo {'slower' if f < 1 else 'faster'} by about 10% (except any you set individually)")
        kept = "the notes, the keys, the exercises and the length."
    elif kind == OP_INTERVAL:
        ivs = [d for d in spec["items"] if d["family"] == "intervals"]
        if not ivs:
            return _unsupported(session, plan0, "There's no interval exercise in this warmup. Say “add an interval exercise” first.")
        target = ivs
        if op["ref"].get("index"):
            hits, err = _resolve_ref(spec["items"], {"index": op["ref"]["index"]})
            if err:
                return _unsupported(session, plan0, err)
            if hits[0]["family"] != "intervals":
                return _unsupported(session, plan0, f"Exercise {op['ref']['index']} isn't an interval exercise, so it can't be changed to {op['interval']}.")
            target = hits
        if len(target) > 1:
            names = ", ".join(f"exercise {_index_of(plan0, d['uid'])} ({d['params'].get('interval')})" for d in target)
            return _unsupported(session, plan0, f"There's more than one interval exercise ({names}). Say which one, for example “change exercise {_index_of(plan0, target[0]['uid'])} to {op['interval']}”.")
        d = target[0]
        old_iv = d["params"].get("interval")
        if old_iv == op["interval"]:
            return _unsupported(session, plan0, f"That exercise is already {op['interval']}.")
        d["params"] = {**d["params"], "interval": op["interval"]}
        spec["intervals"] = list(dict.fromkeys([op["interval"], *[x for x in (spec.get("intervals") or []) if x != old_iv]]))
        touched.add(d["uid"])
        replan = False
        changed.append(f"exercise {_index_of(plan0, d['uid'])} {old_iv} → {op['interval']}")
        kept = "every other exercise exactly as it was; this one keeps its tempo and about the same time."
    elif kind in SONG_OPS:
        song = spec.get("song")
        if not song:
            return _unsupported(session, plan0, "This warmup isn't built from a song's chords, so there are no bars, sections or guide tones to change. "
                                                "Ask for one first — for example “Give me a guide-tone warmup over the chorus”.")
        sel = dict(spec["song_sel"])
        n_bars = len(ws.section_slots(song, sel["section"]))
        guide_uids = {d["uid"] for d in spec["items"] if d["family"] in SONG_FAMILIES}
        touched |= guide_uids
        if kind == OP_SECTION:
            if op["section"] == "__whole__":
                song2, how_w, why_w = ws.with_whole_form(song)
                if not how_w:
                    return _unsupported(session, plan0, f"I can't build the whole form: {why_w}.")
                parts = ws.whole_form(song)[0]
                name, how = (parts[0], "named") if song2 is song else (ws.WHOLE_FORM_NAME, "named")
                spec["song"], song = song2, song2
            else:
                name, how = ws.pick_section(song, op["section"])
            if how not in ("named",):
                names = ", ".join(song["order"])
                return _unsupported(session, plan0, f"This chart has no section called “{op['section']}”. Its sections are: {names}.")
            if name == sel["section"] and not sel.get("bars"):
                return _unsupported(session, plan0, f"The warmup already uses {name}.")
            changed.append(f"section {sel['section']} → {name}")
            spec["song_sel"] = {"section": name, "how": "named", "bars": None}
        elif kind == OP_BARS:
            b = op["spec"]
            if b.get("all"):
                new_bars = None
            elif b.get("first"):
                new_bars = [1, min(n_bars, int(b["first"]))]
            elif b.get("last"):
                new_bars = [max(1, n_bars - int(b["last"]) + 1), n_bars]
            else:
                a, z = b["range"]
                if not (1 <= a <= z <= n_bars):
                    return _unsupported(session, plan0, f"{sel['section']} has {n_bars} bars, so bars {a}–{z} don't exist.")
                new_bars = [a, z]
            if new_bars == [1, n_bars]:
                new_bars = None
            if new_bars == sel.get("bars"):
                return _unsupported(session, plan0, "The warmup already uses exactly those bars.")
            old_t = f"bars {sel['bars'][0]}–{sel['bars'][1]}" if sel.get("bars") else f"all {n_bars} bars"
            new_t = f"bars {new_bars[0]}–{new_bars[1]}" if new_bars else f"all {n_bars} bars"
            changed.append(f"{sel['section']}: {old_t} → {new_t}")
            spec["song_sel"] = {**sel, "bars": new_bars}
        elif kind == OP_ARP_START:
            if not any(d["family"] == "chord_tones" for d in spec["items"]):
                return _unsupported(session, plan0, "There are no chord-tone arpeggio exercises in this warmup. Say “add arpeggios” first.")
            if (spec.get("chord_start") or "") == op["start"]:
                return _unsupported(session, plan0, f"The arpeggios already start on the {op['start']}.")
            spec["chord_start"] = op["start"]
            _dedupe_guide(spec)
            changed.append(f"every arpeggio now starts on the {op['start']} of its chord" + (" (where the chord has one)" if op["start"] in ("fifth", "seventh") else ""))
            touched = {d["uid"] for d in spec["items"] if d["family"] == "chord_tones"}
        elif kind == OP_APPROACH_KIND:
            if "approach_notes" not in spec["families"]:
                reason = we.supports(player, "approach_notes")
                if reason:
                    return _unsupported(session, plan0, f"I can't add approach notes for {player.label}: {reason}.")
                spec["families"].append("approach_notes")
                spec["excluded"] = [f for f in spec.get("excluded") or [] if f != "approach_notes"]
                it = _new_item(spec, "approach_notes")
                if it:
                    spec["items"].append(it)
                    spec["items"] = _ordered(spec)
                changed.append("added an approach-note exercise")
            if (spec.get("approach_kind") or "") == op["kind"] and not changed:
                return _unsupported(session, plan0, f"The approach-note exercises already use {wc.KIND_LABEL[op['kind']]}.")
            spec["approach_kind"] = op["kind"]
            _dedupe_guide(spec)
            changed.append(f"approach notes now use {wc.KIND_LABEL[op['kind']]}")
            touched = {d["uid"] for d in spec["items"] if d["family"] == "approach_notes"}
        elif kind == OP_TONES:
            if not any(d["family"] == "guide_tones" for d in spec["items"]):
                return _unsupported(session, plan0, "There are no guide-tone exercises in this warmup, so there is no third or seventh line to narrow. Say “add guide tones” first.")
            if (spec.get("tones") or "") == op["tones"]:
                return _unsupported(session, plan0, f"The guide-tone exercises already use {ws.TONES_LABEL[op['tones']]}.")
            spec["tones"] = op["tones"]
            _dedupe_guide(spec)
            changed.append(f"guide tones: {ws.TONES_LABEL[op['tones']]}" + (" only" if op["tones"] != "both" else ""))
            touched = {d["uid"] for d in spec["items"] if d["family"] == "guide_tones"}
        else:
            if spec.get("smooth"):
                return _unsupported(session, plan0, "The guide-tone line is already voice-led as smoothly as I can make it for this chart and register.")
            spec["smooth"] = True
            changed.append("voice-leading made smoother (smaller leaps between chords)")
        kept = ("the song, key, level, instrument and tempos you set, and every exercise this change doesn't apply to; the warmup stays "
                f"{spec['minutes']:g} minutes, so plays are re-planned.")
    elif kind == OP_INSTRUMENT:
        req_i = {"instrument_word": op["instrument_word"], "sax_type_word": op.get("sax_type_word") or "", "unverified": ""}
        newp, why_not, facts = resolve_player(req_i, session, None, spec["concert_key"])
        if newp is None:
            return _unsupported(session, plan0, why_not)
        if newp.key == spec["instrument"]:
            return _unsupported(session, plan0, f"The warmup is already for {newp.label}.")
        for f in {d["family"] for d in spec["items"]}:
            reason = we.supports(newp, f)
            if reason:
                return _unsupported(session, plan0, f"I can't move this warmup to {newp.label}: {reason}.")
        old_label = player.label
        spec["instrument"] = newp.key
        player = newp
        touched |= {d["uid"] for d in spec["items"]}
        changed.append(f"instrument {old_label} → {newp.label} (every exercise is rewritten in {newp.label}'s written pitch, in the same concert key)"
                       + (" — the saxophone type wasn't named, so I used Alto" if facts.get("sax_assumed") else ""))
        kept = "the level, the length, the song and section (if any), and which kinds of exercise are included."
    else:
        return _unsupported(session, plan0)

    old_by = {r["uid"]: r for r in plan0["items"]}
    try:
        plan1 = build_plan(player, spec, replan=replan)
    except we.WarmupUnavailable as exc:
        return _unsupported(session, plan0, f"I couldn't build that change correctly: {exc}.")
    if lvl_uids:
        _retarget_reps_for_item(plan0, plan1, lvl_uids)
    elif kind in (OP_ITEM_SLOWER, OP_ITEM_FASTER, OP_ITEM_TEMPO):
        _retarget_reps_for_item(plan0, plan1, tempo_uid)
    elif kind == OP_INTERVAL:
        uid = next(iter(touched))
        _retarget_reps_for_item(plan0, plan1, uid)
    # the contract: untouched exercises keep their notation (a level change touches all of them by design)
    size_changed = (plan0["spec"].get("size") or "full") != (plan1["spec"].get("size") or "full")
    if size_changed:
        changed.append("each exercise shortened to its brief version so the plan fits the time")
    if kind == OP_SMOOTH and all(a["abc"] == plan0_item["abc"] for a, plan0_item in zip(plan1["items"], plan0["items"])) and len(plan1["items"]) == len(plan0["items"]):
        leap = max([(r.get("meta") or {}).get("largest_leap", 0) for r in plan0["items"] if r["family"] == "guide_tones"] or [0])
        return _unsupported(session, plan0, f"The line is already as smooth as this chart and register allow (largest leap {leap} semitones).")
    if kind not in (OP_HARDER, OP_EASIER, OP_LEVEL, OP_WHOLE_SLOWER, OP_WHOLE_FASTER, OP_INSTRUMENT) and not size_changed:
        bad = _contract(plan0, plan1, untouched_uids={u for u in old_by if u not in touched})
        if bad:
            return _unsupported(session, plan0, f"I stopped because {bad}.")
    if kind == OP_SMOOTH:
        m0 = [(r.get("meta") or {}).get("mean_leap", 0) for r in plan0["items"] if r["family"] == "guide_tones"]
        m1 = [(r.get("meta") or {}).get("mean_leap", 0) for r in plan1["items"] if r["family"] == "guide_tones"]
        if m0 and m1:
            changed.append(f"average leap {sum(m0) / len(m0):.1f} → {sum(m1) / len(m1):.1f} semitones")
    if kind in (OP_SHORTER, OP_LONGER, OP_MINUTES, OP_REMOVE_FAMILY, OP_REMOVE_ITEM, OP_ADD_FAMILY, OP_MORE_FAMILY, OP_SECTION, OP_BARS, OP_TONES, OP_ARP_START, OP_APPROACH_KIND):
        gained = [r for r in plan1["items"] if r["uid"] not in old_by]
        dropped_ = [r for r in plan0["items"] if r["uid"] not in {x["uid"] for x in plan1["items"]}]
        if gained and kind in (OP_SHORTER, OP_LONGER, OP_MINUTES, OP_SECTION, OP_BARS, OP_TONES, OP_ARP_START, OP_APPROACH_KIND):
            changed.append(f"{len(gained)} exercise{'s' if len(gained) != 1 else ''} added to fill the time")
        if dropped_ and kind in (OP_TONES, OP_ARP_START, OP_APPROACH_KIND):
            changed.append(f"{len(dropped_)} exercise{'s' if len(dropped_) != 1 else ''} that became the same music as another {'were' if len(dropped_) != 1 else 'was'} merged into it")
        elif dropped_ and kind in (OP_SHORTER, OP_LONGER, OP_MINUTES, OP_SECTION, OP_BARS):
            changed.append(f"{len(dropped_)} exercise{'s' if len(dropped_) != 1 else ''} dropped to fit")
    changed.append(f"total playing time now {_mmss(plan1['total_seconds'])}")
    _commit(session, plan1, question)
    return _plan_response(plan1, changed=changed, kept=kept, session_ref=session)


# ---------------------------------------------------------------- entry points


_FRESH_WORDS = re.compile(r"\b(?:new|another|different|fresh|start\s+over|from\s+scratch|instead)\b", re.I)
_ADDITIVE = re.compile(r"\b(?:more|extra|another|add|also|additional)\b", re.I)
_STARTS_FRESH = re.compile(r"^\s*(?:please\s+)?(?:give|create|build|plan|design|generate|write|put\s+together|set\s+up)\b", re.I)
_VIEW_OR_HISTORY = {OP_UNDO, OP_REDO, OP_NEXT, OP_PREV, OP_ALL, OP_GOTO}


def _asks_for_a_new_warmup_text(low: str) -> bool:
    return bool(re.match(r"^\s*(?:please\s+)?(?:give|create|build|plan|design|generate|write|put\s+together|set\s+up)\b", low)) and not _ADDITIVE.search(low)


def _asks_for_a_new_warmup(question: str) -> bool:
    """While a warmup is open, 'make the whole warmup shorter' changes it and 'give me a 5-minute flute warmup' starts another."""
    req = parse_request(question)
    low = _clean(question).lower()
    if req["instrument_word"] or req["unverified"] or _FRESH_WORDS.search(low):
        return True
    return bool(_STARTS_FRESH.match(low)) and not _ADDITIVE.search(low)


def handle(question: str, session_ref: Any, ami_ctx: dict[str, Any] | None = None) -> CoachResponse | None:
    """The warmup answer for ``question``, or None when it isn't about warmups (the rest of AMI then answers)."""
    session = _mutable(session_ref)
    if session is None:
        return None
    ensure_owner(session)
    active = is_active(session)
    if active and current(session)["spec"].get("single"):
        if is_song_request(question) or (is_warmup_request(question) and _asks_for_a_new_warmup(question)):
            return create(question, session, ami_ctx)
        return None
    if not active and _WARM.search(question) and not _asks_for_a_new_warmup(question) and not is_song_request(question):
        guess = parse_revision(question)
        if guess is not None and guess["op"] not in (OP_UNSUPPORTED, OP_MINUTES, OP_ADD_FAMILY, OP_MORE_FAMILY):
            return _simple("There's no warmup from this conversation to change yet. Ask for one first — for example “Give me a 10-minute flute warmup” — and then "
                           "I can shorten it, make it harder, remove or add exercises, slow one down, and undo or redo each change.", failed="no_warmup")
    names = tuple((((current(session) or {}).get("spec") or {}).get("song") or {}).get("order") or ()) if active else ()
    op = parse_revision(question, names) if active else None
    if op is not None and op["op"] in SONG_OPS and not ((current(session) or {}).get("spec") or {}).get("song") and is_song_request(question):
        op = None                          # "practice the thirds and sevenths of these chords" while a non-song warmup is open starts a song-aware one
    if op is not None and op["op"] in _VIEW_OR_HISTORY:
        return revise(op, question, session, ami_ctx)
    if is_warmup_request(question) and not (op is not None and op["op"] != OP_UNSUPPORTED and not _asks_for_a_new_warmup(question)):
        return create(question, session, ami_ctx)
    if op is not None:
        return revise(op, question, session, ami_ctx)
    return None


def step_view(session_ref: Any, delta: int) -> CoachResponse | None:
    """The 'Next exercise' / 'Previous exercise' / 'Whole warmup' buttons: move the view (delta +1, -1, 0 = whole plan). No new version."""
    op = {"op": OP_NEXT if delta > 0 else OP_PREV if delta < 0 else OP_ALL}
    return revise(op, "next exercise", session_ref, None) if is_active(session_ref) else None
