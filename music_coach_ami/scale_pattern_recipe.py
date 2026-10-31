"""AMI M1c: the recipe behind a scale-pattern exercise, and the plain-language requests that change it.

A scale pattern is fully described by a small ``Recipe``: the interval shape (scale steps, thirds, fourths ...), how dense the rhythm is,
whether chromatic approach notes are added, how syncopated the rhythm is, and whether chord changes are anticipated. Every revision
changes only the recipe fields it names; the notation is then regenerated from the recipe by the deterministic engines, so an
instruction about the notes cannot move the rhythm and an instruction about the rhythm cannot move the pitch order.

Difficulty is a deterministic walk through the recipe (``advance`` / ``ease``). Its first steps are exactly the M1d ladder (Beginner,
Intermediate, Advanced, Advanced+, Advanced++); after that it adds chromatic approaches and syncopation, and never throws away the
interval shape the player chose.

No music is generated here and nothing is sent anywhere: this module is parsing and bookkeeping.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, replace
from typing import Any

# (shape, tier) -> the engines' interval-cell name (musical_idea_engine._degree_cycle)
CELLS: dict[tuple[str, int], str] = {
    ("scalar", 0): "1-2-3-4", ("scalar", 1): "1-3-2-4",
    ("thirds", 0): "thirds", ("thirds", 1): "thirds_triad", ("thirds", 2): "thirds_stack",
    ("fourths", 0): "fourths", ("fourths", 1): "fourths_step", ("fourths", 2): "fourths_stack",
    ("fifths", 0): "fifths", ("fifths", 1): "fifths_step",
    ("mixed", 0): "thirds_fourths",
}
MAX_TIER = {"scalar": 1, "thirds": 2, "fourths": 2, "fifths": 1, "mixed": 0}
WIDTH_ORDER = ("scalar", "thirds", "fourths", "fifths")     # "wider intervals" walks this list
SHAPE_NAME = {"scalar": "scale steps", "thirds": "diatonic thirds", "fourths": "diatonic fourths", "fifths": "diatonic fifths",
              "mixed": "thirds and fourths combined"}
CELL_TEXT = {
    ("scalar", 0): "each cell runs up four neighbouring scale notes (1-2-3-4)",
    ("scalar", 1): "each cell plays scale degrees 1-3-2-4",
    ("thirds", 0): "each cell jumps a diatonic third (1-3), then the next cell starts one scale step higher",
    ("thirds", 1): "each cell outlines a triad shape in thirds (1-3-5-3)",
    ("thirds", 2): "each cell stacks thirds up through the seventh (1-3-5-7)",
    ("fourths", 0): "each cell jumps a diatonic fourth (1-4), then the next cell starts one scale step higher",
    ("fourths", 1): "each cell plays a fourth and steps back inside it (1-4-2-5)",
    ("fourths", 2): "each cell stacks fourths (1-4-7) and returns to the fourth (1-4-7-4)",
    ("fifths", 0): "each cell jumps a diatonic fifth (1-5)",
    ("fifths", 1): "each cell plays a fifth and steps (1-5-2-6)",
    ("mixed", 0): "each cell combines a third, a fourth and a falling third (1-3-6-4)",
}
UNITS = ("quarter", "eighth", "sixteenth")


@dataclass(frozen=True)
class Recipe:
    level: str = "advanced"          # beginner | intermediate | advanced
    subdivision: str = "eighth"      # quarter | eighth | sixteenth (others are kept as the engine reports them)
    shape: str = "scalar"
    tier: int = 0
    approach: str = "none"           # none | below | above | both (from the side the line arrives)
    approach_density: int = 0        # 0 none | 1 strong beats | 2 every beat
    syncopation: int = 0             # 0 straight | 1 light | 2 full
    displaced: bool = False          # the pattern starts one subdivision late
    anticipation: bool = False       # explicit harmonic anticipation of the next chord (chord-following only)

    def cell(self) -> str:
        return CELLS.get((self.shape, self.tier), CELLS[("scalar", 0)])

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def score(self) -> int:
        """A deterministic difficulty number: every step ``advance`` takes raises it, every step ``ease`` takes lowers it."""
        return (("beginner", "intermediate", "advanced").index(self.level) + (1 if self.subdivision == "sixteenth" else 0)
                + self.tier + (WIDTH_ORDER.index(self.shape) if self.shape in WIDTH_ORDER else 2)
                + (self.approach_density if self.has_chromatic() else 0) + self.syncopation + (1 if self.displaced else 0)
                + (1 if self.anticipation else 0))

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> "Recipe":
        names = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in dict(raw or {}).items() if k in names})

    @property
    def pristine(self) -> bool:
        """Nothing beyond the M1d ladder has been asked for."""
        return self.shape == "scalar" and self.approach == "none" and not self.syncopation and not self.displaced and not self.anticipation

    def has_chromatic(self) -> bool:
        return self.approach != "none" and self.approach_density > 0

    def label(self) -> str:
        """A short name for the exercise's level. The pristine ladder keeps the M1d names exactly."""
        if self.pristine:
            if self.subdivision == "quarter":
                return "Beginner"
            if self.subdivision == "sixteenth":
                return "Advanced++"
            if self.tier >= 1:
                return "Advanced+"
            return "Advanced" if self.level == "advanced" else "Intermediate"
        parts = [self.level.capitalize(), SHAPE_NAME.get(self.shape, self.shape)]
        if self.tier:
            parts[-1] += f" (level {self.tier + 1})"
        parts.append(f"{self.subdivision} notes")
        if self.has_chromatic():
            parts.append("chromatic approaches" + (" on every beat" if self.approach_density > 1 else ""))
        if self.syncopation:
            parts.append("syncopated" if self.syncopation > 1 else "lightly syncopated")
        if self.displaced:
            parts.append("displaced")
        if self.anticipation:
            parts.append("chord anticipations")
        return " · ".join(parts)


def recipe_from_idea(idea: Any, unit: str) -> Recipe:
    """The recipe an M1d pattern was generated with (``unit`` is the engine's own note value for it)."""
    from music_coach_ami.musical_idea_engine import _level

    pat = str(getattr(idea, "interval_pattern", "") or "").strip().lower()
    shape, tier = "scalar", 0
    if pat in ("1-3-2-4", "1-3-4-2"):
        tier = 1
    elif pat in ("thirds", "broken_thirds"):
        shape = "thirds"
    elif pat in ("thirds_triad", "thirds_stack"):
        shape, tier = "thirds", 1 if pat == "thirds_triad" else 2
    elif pat in ("fourths", "fourths_step", "fourths_stack"):
        shape, tier = "fourths", {"fourths": 0, "fourths_step": 1, "fourths_stack": 2}[pat]
    elif pat in ("fifths", "fifths_step"):
        shape, tier = "fifths", 0 if pat == "fifths" else 1
    elif pat == "thirds_fourths":
        shape = "mixed"
    return Recipe(level=_level(idea), subdivision=unit or "eighth", shape=shape, tier=tier)


# ---------------------------------------------------------------- difficulty: a deterministic walk through the recipe


def _step_density(r: Recipe) -> tuple[Recipe, str] | None:
    if r.subdivision in UNITS and r.subdivision != "quarter":
        return None
    return replace(r, subdivision="eighth", level="intermediate" if r.level == "beginner" else r.level), "eighth notes instead of quarter notes"


def _step_level(r: Recipe) -> tuple[Recipe, str] | None:
    return (replace(r, level="advanced"), "advanced level") if r.level != "advanced" else None


def _step_tier(r: Recipe) -> tuple[Recipe, str] | None:
    if r.tier >= MAX_TIER.get(r.shape, 0):
        return None
    nxt = replace(r, tier=r.tier + 1)
    return nxt, f"a more varied {SHAPE_NAME[r.shape].replace('diatonic ', '')} cell — {CELL_TEXT[(nxt.shape, nxt.tier)]}"


def _step_sixteenth(r: Recipe) -> tuple[Recipe, str] | None:
    return (replace(r, subdivision="sixteenth"), "sixteenth notes") if r.subdivision == "eighth" else None


def _step_approach(r: Recipe) -> tuple[Recipe, str] | None:
    if r.has_chromatic():
        return None
    return replace(r, approach="both", approach_density=1), "chromatic approach notes before strong-beat chord tones"


def _step_sync1(r: Recipe) -> tuple[Recipe, str] | None:
    return (replace(r, syncopation=1), "light syncopation") if r.syncopation < 1 else None


def _step_density2(r: Recipe) -> tuple[Recipe, str] | None:
    return (replace(r, approach_density=2), "chromatic approaches on every beat") if r.has_chromatic() and r.approach_density < 2 else None


def _step_sync2(r: Recipe) -> tuple[Recipe, str] | None:
    return (replace(r, syncopation=2), "full syncopation") if r.syncopation == 1 else None


def _step_displaced(r: Recipe) -> tuple[Recipe, str] | None:
    return (replace(r, displaced=True), "rhythmic displacement (the pattern starts an eighth late)") if not r.displaced and r.syncopation else None


_UP = (_step_density, _step_level, _step_tier, _step_sixteenth, _step_approach, _step_sync1, _step_density2, _step_sync2, _step_displaced)


def advance(r: Recipe) -> tuple[Recipe, str] | None:
    """The next harder recipe and what it added, or ``None`` at the top. The interval shape is never replaced."""
    for fn in _UP:
        got = fn(r)
        if got is not None:
            return got
    return None


def _down_displaced(r: Recipe) -> tuple[Recipe, str] | None:
    return (replace(r, displaced=False), "rhythmic displacement taken out") if r.displaced else None


def _down_sync(r: Recipe) -> tuple[Recipe, str] | None:
    return (replace(r, syncopation=r.syncopation - 1), "less syncopation") if r.syncopation else None


def _down_density2(r: Recipe) -> tuple[Recipe, str] | None:
    return (replace(r, approach_density=1), "approaches back to strong beats only") if r.has_chromatic() and r.approach_density > 1 else None


def _down_approach(r: Recipe) -> tuple[Recipe, str] | None:
    return (replace(r, approach="none", approach_density=0), "chromatic approaches taken out") if r.has_chromatic() else None


def _down_anticipation(r: Recipe) -> tuple[Recipe, str] | None:
    return (replace(r, anticipation=False), "chord anticipations taken out") if r.anticipation else None


def _down_sixteenth(r: Recipe) -> tuple[Recipe, str] | None:
    return (replace(r, subdivision="eighth"), "back to eighth notes") if r.subdivision == "sixteenth" else None


def _down_tier(r: Recipe) -> tuple[Recipe, str] | None:
    return (replace(r, tier=r.tier - 1), "a simpler interval cell") if r.tier > 0 else None


def _down_shape(r: Recipe) -> tuple[Recipe, str] | None:
    if r.shape == "scalar":
        return None
    if r.shape == "mixed":
        return replace(r, shape="thirds", tier=0), "back to diatonic thirds"
    i = WIDTH_ORDER.index(r.shape)
    return replace(r, shape=WIDTH_ORDER[i - 1], tier=0), f"narrower intervals ({SHAPE_NAME[WIDTH_ORDER[i - 1]]})"


def _down_level(r: Recipe) -> tuple[Recipe, str] | None:
    if r.level == "advanced":
        return replace(r, level="intermediate"), "intermediate level"
    return None


def _down_quarter(r: Recipe) -> tuple[Recipe, str] | None:
    if r.subdivision == "eighth" and r.level != "beginner":
        return replace(r, subdivision="quarter", level="beginner"), "quarter notes (beginner)"
    return None


_DOWN = (_down_displaced, _down_sync, _down_density2, _down_approach, _down_anticipation, _down_sixteenth, _down_tier, _down_shape, _down_level,
         _down_quarter)
_DOWN_NOTES = (_down_approach, _down_tier, _down_shape)


def advance_candidates(r: Recipe) -> list[tuple[Recipe, str]]:
    """Every harder recipe one step away, in the order ``advance`` would take them. A step that the instrument's range can't hold is skipped
    by the caller, which then tries the next one — the chosen interval shape is still never replaced."""
    return [got for fn in _UP if (got := fn(r)) is not None]


def ease_candidates(r: Recipe) -> list[tuple[Recipe, str]]:
    return [got for fn in _DOWN if (got := fn(r)) is not None]


def ease(r: Recipe, *, notes_only: bool = False) -> tuple[Recipe, str] | None:
    for fn in (_DOWN_NOTES if notes_only else _DOWN):
        got = fn(r)
        if got is not None:
            return got
    return None


def widen(r: Recipe) -> tuple[Recipe, str] | None:
    """Wider intervals: a more varied cell of the same shape first, then the next wider shape."""
    if r.shape == "mixed":
        return replace(r, shape="fourths", tier=0), "fourths"
    got = _step_tier(r)
    if got is not None and r.shape != "scalar":
        return got
    if r.shape in WIDTH_ORDER and WIDTH_ORDER.index(r.shape) + 1 < len(WIDTH_ORDER):
        nxt = WIDTH_ORDER[WIDTH_ORDER.index(r.shape) + 1]
        return replace(r, shape=nxt, tier=0), SHAPE_NAME[nxt]
    return None


def narrow(r: Recipe) -> tuple[Recipe, str] | None:
    return _down_tier(r) or _down_shape(r)


# ---------------------------------------------------------------- requests


@dataclass(frozen=True)
class PatternChange:
    """What the player asked for, in the order it is applied. ``ops`` are (name, argument) pairs; ``unsupported`` names anything asked
    for that the engines cannot do (the whole request is then declined, nothing half-applied)."""
    ops: tuple[tuple[str, str], ...] = ()
    unsupported: tuple[str, ...] = ()
    expression: dict[str, Any] | None = None     # an accompanying articulation request ("... and add accents")
    bare_accent: bool = False                    # "accents" with no target: applied to the downbeats, and the answer says so
    notes: tuple[str, ...] = ()                  # disclosures the answer must make ("jazz vocabulary" is only chromatic approaches so far)
    raw: str = ""


_STOP_FIRST = re.compile(r"^(?:why|what|which|how|when|where|who|is|are|does|do|did|can(?!\s+you)|could(?!\s+you)|would(?!\s+you)|should|explain|tell|describe)\b")
_GENERATE = re.compile(r"\b(?:give me|show me|write me|write|generate|create|make me|play me)\s+(?:an?\s+|some\s+)?(?!(?:more|less|another)\b)")
_NEW_SCOPE = re.compile(r"\b(?:over|through|for)\s+(?:the\s+)?(?:[a-z][a-z' ]{2,}\bsection\b|chorus|verse|bridge|chord changes|changes|chords|[a-g][#b]?(?:maj|min|m|dim|aug)?\d*)\b")
_ANAPHORA = re.compile(r"\b(?:it|that|this|them|these|those|the (?:exercise|pattern|line|phrase|notes|rhythm|intervals|melody|idea))\b")
_VERB = re.compile(r"^(?:(?:please|can you|could you|would you|now|then|and|also|ok|okay)[, ]+)*(?:make|change|turn|switch|convert|use|using|add|put|apply|try|give|keep|let'?s|remove|take|drop|simplify|simplifying|replace|play|set|go|increase|reduce|widen|narrow|displace|syncopate|include|insert|work|get|approach|anticipate|approaching|enclose)\b")

_SHAPE = re.compile(r"\b(thirds?|fourths?|fifths?|stepwise|scalar|scale steps?|steps?|seconds|diatonic steps?)\b")
_MIXED = re.compile(r"\b(?:thirds? and fourths?|fourths? and thirds?|mix(?:ed|ture)? of (?:thirds|fourths)|combin\w+ (?:of )?(?:thirds|fourths))\b")
_WIDER = re.compile(r"\b(?:wider|larger|bigger|greater|widen\w*)\s*(?:intervals?)?\b|\bintervals?\b.{0,20}\b(?:wider|larger|bigger|widen\w*)\b|\bjump(?:s|ing)? (?:more|further)\b")
_NARROWER = re.compile(r"\b(?:narrower|smaller|tighter|closer)\s+intervals?\b|\bintervals?\b.{0,20}\b(?:narrower|smaller|tighter|closer)\b|\bnarrow\w*\b.{0,16}\bintervals?\b")
_INTERVAL_ADV = re.compile(r"\bmore\s+(?:advanced|difficult|challenging|complex|interesting|sophisticated|varied)\s+interval\w*\b|\binterval\s+pattern\b.*\bmore\s+(?:advanced|difficult|complex)\b")
_SIMPLIFY_NOTES = re.compile(r"\b(?:simplif\w+|simpler|easier|reduce|fewer)\b.{0,16}\bnotes?\b|\bsimplif\w+\s+(?:the\s+)?(?:pitches|intervals?)\b|\bsimpler\s+(?:pitches|intervals)\b")
_APPROACH = re.compile(r"\bchromatic\w*\b|\bapproach(?:es|ed|ing)?\b|\benclosures?\b|\bbebop\b|\bjazz(?:y)?\s+(?:vocabulary|vocab|language|lines?|licks?|sound|feel|flavou?r)\b|\bjazzier\b")
_APPROACH_BELOW = re.compile(r"\b(?:from|a half step|half-step|semitone)\s*(?:below|underneath|beneath)\b|\bbelow\b|\bunderneath\b|\bfrom the bottom\b|\bfrom under\b")
_APPROACH_ABOVE = re.compile(r"\bfrom\s+(?:above|over|the top)\b|\babove\b|\bfrom on top\b")
_APPROACH_OFF = re.compile(r"\b(?:remove|no|without|drop|take (?:away|out)|get rid of|delete|lose|less|fewer|strip)\b.{0,24}(?:chromatic\w*|approach\w*)\b|\b(?:chromatic\w*|approach\w*)\b.{0,14}\b(?:off|away|out)\b|\bnot (?:so )?chromatic\b|\bless chromatic\b")
_APPROACH_MORE = re.compile(r"\bmore\s+(?:chromatic\w*|approach\w*)\b|\bchromatic\w*\b.{0,20}\b(?:more|heavier|stronger)\b|\bmake (?:it|the line|that) (?:more )?chromatic\b|\bevery beat\b|\bmore (?:advanced )?jazz\w*\b|\bjazzier\b")
_SYNC = re.compile(r"\bsyncopat\w*\b|\boff-?beats?\b|\boff beat\b|\bpush(?:ed|ing)?\b.{0,12}\bbeat\b")
_SYNC_LESS = re.compile(r"\b(?:less|fewer|not so|straighter?|straighten\w*|remove|no|without|drop|simpl\w+|plain|even|regular)\b.{0,24}\b(?:syncopat\w*|off-?beats?|rhythm\w*|displace\w*)\b|\bstraight(?:en)?\b|\bstraight rhythm\b|\bundo the syncopation\b")
_SYNC_MORE = re.compile(r"\bmore\s+(?:syncopat\w*|off-?beats?|rhythmic\w*|rhythmically)\b|\bsyncopat\w*\b.{0,16}\b(?:more|heavier)\b|\brhythmically\s+(?:advanced|complex|interesting|sophisticated|difficult|challenging)\b|\bmore\s+(?:advanced|complex|interesting|sophisticated|difficult|challenging)\s+rhythm\w*\b")
_DISPLACE = re.compile(r"\bdisplac\w*\b|\bshift(?:ed|ing)?\b.{0,18}\b(?:rhythm|pattern|line|notes)\b.{0,12}\b(?:late|later|over|by an eighth|offbeat)\b|\bstart(?:ing)?\s+(?:it\s+)?(?:an eighth|a beat|late|offbeat|off the beat)\b")
_NEW_RHYTHM = re.compile(r"\b(?:change|vary|alter|new|different|another|switch)\s+(?:up\s+)?(?:the\s+)?rhythm\w*\b|\bdifferent rhythm\b|\bkeep\b.{0,12}\bnotes?\b.{0,16}\b(?:change|different|new)\b.{0,10}\brhythm\b|\bsame notes?\b.{0,24}\brhythm\b")
_ANTICIPATE = re.compile(r"\banticipat\w*\b")
_HARDER = re.compile(r"\b(?:harder|tougher|more (?:advanced|difficult|challenging|complex)|increase the difficulty|up the difficulty)\b")
_EASIER = re.compile(r"\b(?:easier|simpler|less (?:difficult|complex|busy|advanced)|more basic|reduce the difficulty)\b")
_KEEP_TEMPO = re.compile(r"\bwithout (?:changing|changing) the tempo\b|\bsame tempo\b|\bkeep(?:ing)? the tempo\b|\bwithout (?:slowing|speeding)\b")
_KEEP_RHYTHM = re.compile(r"\b(?:keep|same|retain|preserve)\s+(?:the\s+)?rhythm\b|\bsame rhythm\b")

_UNSUPPORTED: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("sixths, sevenths or octaves", re.compile(r"\b(?:sixths?|sevenths?|octaves?|ninths?|tenths?|tritones?)\b")),
    ("slurs", re.compile(r"\b(?:slurs?|slurred|legato)\b")),
    ("dynamics", re.compile(r"\b(?:crescendo|decrescendo|diminuendo|dynamics?|louder|softer|quieter|forte|piano|pianissimo|fortissimo)\b")),
    ("triplets", re.compile(r"\btriplets?\b|\bswing eighths?\b")),
    ("a different instrument", re.compile(r"\b(?:for|on)\s+(?:a\s+|an\s+|the\s+|my\s+)?(?:(?:alto|tenor|soprano|baritone|bari|bb|eb)\s+)?(?:flute|clarinet|sax\w*|trumpet|trombone|violin|guitar|piano|oboe|horn)\b")),
    ("a different section", re.compile(r"\b(?:apply|use|move|transfer|play|try)\b.{0,16}\b(?:to|on|in)\b.{0,10}\b(?:the\s+)?(?:chorus|verse|bridge|intro|outro|section)\b|\bapply\s+(?:it|that|this)\s+to\b")),
)


def _norm(question: str) -> str:
    return re.sub(r"\s+", " ", str(question or "").lower().replace("’", "'")).strip(" .!?,;:")


def _is_revision(low: str) -> bool:
    if not low or len(low.split()) > 22 or _STOP_FIRST.match(low):
        return False
    comparative = re.match(r"^(?:(?:please|can you|could you|now|then|and|also)[, ]+)*(?:give|show)\s+me\s+(?:a\s+|an\s+)?(?:more|less|even more|much more)\b", low)
    if _GENERATE.search(low) and not comparative and not _ANAPHORA.search(low):
        return False          # "give me an advanced scale pattern over Blue Bossa" is a new request, not a revision
    if _NEW_SCOPE.search(low) and not (_ANAPHORA.search(low) or comparative):
        return False
    return bool(_ANAPHORA.search(low) or _VERB.match(low) or comparative or len(low.split()) <= 4)


def parse_pattern_change(question: str) -> PatternChange | None:
    """Recognise a request to change a scale pattern's intervals, approach notes, rhythm or difficulty. ``None`` when the sentence is not one
    (the caller then lets the rest of AMI handle it)."""
    raw = str(question or "").strip()
    low = _norm(raw)
    if not _is_revision(low):
        return None
    ops: list[tuple[str, str]] = []
    # accompanying expression ("... and add accents") is split off and applied afterwards through the existing expression engine
    from music_coach_ami.exercise_expression import has_rules, parse_expression

    expr = parse_expression(low)
    expr.pop("spans", None)
    expression = expr if has_rules(expr) else None
    bare_accent = False
    if expression is None and re.search(r"\baccents?\b", low):
        expression, bare_accent = parse_expression("accent the downbeats"), True
        expression.pop("spans", None)
    unsupported = [name for name, rx in _UNSUPPORTED if rx.search(low)]
    # a bare shape word is only a shape change next to a verb or an anaphor: "fourths" / "in thirds" / "change it to fourths"
    # ---- intervals
    mixed = _MIXED.search(low)
    shape_words = [] if mixed else list(dict.fromkeys(m.group(1) for m in _SHAPE.finditer(low)))
    shape_words = [w for w in shape_words if not (w in ("steps", "step", "seconds") and not re.search(r"\b(?:scale steps?|stepwise|seconds|steps)\b", low))]
    if mixed:
        ops.append(("shape", "mixed"))
    for w in shape_words:
        key = {"third": "thirds", "thirds": "thirds", "fourth": "fourths", "fourths": "fourths", "fifth": "fifths", "fifths": "fifths"}.get(w, "scalar")
        if key == "scalar" and not re.search(r"\b(?:back to|return to|go back to|use|change|switch|make)\b|\bstepwise\b|\bscale steps?\b", low):
            continue
        ops.append(("shape", key))
        break
    if not ops and _INTERVAL_ADV.search(low):
        ops.append(("interval_advance", ""))
    elif not ops and _WIDER.search(low) and "interval" in low:
        ops.append(("wider", ""))
    elif not ops and _NARROWER.search(low):
        ops.append(("narrower", ""))
    elif not ops and _SIMPLIFY_NOTES.search(low):
        ops.append(("simplify_notes", ""))
    # ---- chromatic approaches
    if _APPROACH.search(low):
        if _APPROACH_OFF.search(low):
            ops.append(("approach_off", ""))
        elif _APPROACH_MORE.search(low):
            ops.append(("approach_more", ""))
        else:
            below, above = bool(_APPROACH_BELOW.search(low)), bool(_APPROACH_ABOVE.search(low))
            ops.append(("approach", "below" if below and not above else "above" if above and not below else "both"))
    # ---- rhythm
    if _ANTICIPATE.search(low):
        ops.append(("anticipate", "off" if re.search(r"\b(?:remove|no|without|drop|undo|stop|less)\b.{0,16}anticipat", low) else "on"))
    if _DISPLACE.search(low):
        ops.append(("displace", "off" if re.search(r"\b(?:remove|no|without|drop|undo|stop|less|straighten)\b.{0,16}displac", low) else "on"))
    elif _SYNC_LESS.search(low) and (_SYNC.search(low) or "rhythm" in low or "straight" in low):
        ops.append(("sync_less", ""))
    elif _SYNC_MORE.search(low) or _SYNC.search(low):
        ops.append(("sync_more", ""))
    elif _NEW_RHYTHM.search(low) and not any(o[0] in ("sync_more", "sync_less") for o in ops):
        ops.append(("new_rhythm", ""))
    # ---- plain difficulty (only when nothing more specific was asked)
    if not ops:
        if _HARDER.search(low) and not _EASIER.search(low):
            ops.append(("harder", ""))
        elif _EASIER.search(low) and not _HARDER.search(low):
            ops.append(("easier", ""))
    if not ops and "sixths, sevenths or octaves" not in unsupported and "triplets" not in unsupported:
        return None           # accents, slurs, dynamics, another instrument or section ... belong to the paths that already answer them
    notes = ("jazz_vocabulary",) if re.search(r"\bjazz\w*\b|\bbebop\b|\benclosures?\b", low) else ()
    return PatternChange(ops=tuple(ops), unsupported=tuple(unsupported), expression=expression, bare_accent=bare_accent, notes=notes, raw=raw)


def keeps_rhythm(question: str) -> bool:
    return bool(_KEEP_RHYTHM.search(_norm(question)))


# ---------------------------------------------------------------- applying a request to a recipe


def apply_ops(recipe: Recipe, ops: tuple[tuple[str, str], ...], *, chord_following: bool) -> tuple[Recipe, list[str], str]:
    """(new recipe, what changed in words, "" | why nothing could be done). Ops are applied in order."""
    changes: list[str] = []
    cur = recipe
    for name, arg in ops:
        before = cur
        said = ""
        if name == "shape":
            if arg == cur.shape and cur.tier == 0:
                return recipe, [], f"The pattern is already in {SHAPE_NAME[arg]}."
            cur = replace(cur, shape=arg, tier=0)
            said = f"the pattern now moves in {SHAPE_NAME[arg]}"
        elif name == "interval_advance":
            got = _step_tier(cur) or widen(cur)
            if got is None:
                return recipe, [], "The interval shape is already the most varied I build."
            cur, said = got[0], f"a more advanced interval shape — {got[1]}"
        elif name == "wider":
            got = widen(cur)
            if got is None:
                return recipe, [], "These are already the widest intervals I build (fifths)."
            cur, said = got[0], f"wider intervals — {got[1]}"
        elif name in ("narrower", "simplify_notes"):
            got = ease(cur, notes_only=True) if name == "simplify_notes" else narrow(cur)
            if got is None:
                return recipe, [], ("The notes are already as simple as I can make them — plain scale steps with no chromatic approaches." if name == "simplify_notes"
                                    else "These are already the narrowest intervals I build (scale steps).")
            cur, said = got[0], (f"simplified the notes: {got[1]}" if name == "simplify_notes" else got[1])
        elif name == "approach":
            if cur.has_chromatic() and cur.approach == arg:
                return recipe, [], "The line already has chromatic approach notes like that."
            cur = replace(cur, approach=arg, approach_density=max(1, cur.approach_density))
            said = {"below": "chromatic approaches from below", "above": "chromatic approaches from above"}.get(arg, "chromatic approaches")
        elif name == "approach_more":
            if not cur.has_chromatic():
                cur = replace(cur, approach="both", approach_density=1)
                said = "chromatic approaches"
            elif cur.approach_density < 2:
                cur = replace(cur, approach_density=2)
                said = "chromatic approaches on every beat"
            else:
                return recipe, [], "The line already has a chromatic approach on every beat — that is as chromatic as I build."
        elif name == "approach_off":
            if not cur.has_chromatic():
                return recipe, [], "There are no chromatic approach notes to remove."
            cur, said = replace(cur, approach="none", approach_density=0), "removed the chromatic approaches"
        elif name == "anticipate":
            if not chord_following:
                return recipe, [], ("A key-based pattern has no chord changes to anticipate. Ask for a pattern over the chord changes "
                                    "(“Give me an advanced scale pattern over the chord changes of …”) and I can anticipate them.")
            if (arg == "on") == cur.anticipation:
                return recipe, [], "The chord changes are already anticipated." if arg == "on" else "There are no anticipations to remove."
            cur, said = replace(cur, anticipation=arg == "on"), "chord anticipations" if arg == "on" else "removed the chord anticipations"
        elif name == "displace":
            if (arg == "on") == cur.displaced:
                return recipe, [], "The rhythm is already displaced." if arg == "on" else "The rhythm isn't displaced."
            cur, said = replace(cur, displaced=arg == "on"), "rhythmic displacement" if arg == "on" else "removed the displacement"
        elif name == "sync_more":
            if cur.syncopation >= 2 and cur.displaced:
                return recipe, [], "The rhythm is already as syncopated as I build it (fully syncopated and displaced)."
            if cur.syncopation < 2:
                cur, said = replace(cur, syncopation=cur.syncopation + 1), "light syncopation" if cur.syncopation == 0 else "full syncopation"
            else:
                cur, said = replace(cur, displaced=True), "rhythmic displacement on top of the syncopation"
        elif name == "sync_less":
            if not cur.syncopation and not cur.displaced:
                return recipe, [], "The rhythm is already straight."
            cur = replace(cur, displaced=False) if cur.displaced else replace(cur, syncopation=cur.syncopation - 1)
            said = "less syncopation"
        elif name == "new_rhythm":
            order = [(0, False), (1, False), (2, False), (2, True)]
            pos = order.index((cur.syncopation, cur.displaced)) if (cur.syncopation, cur.displaced) in order else 0
            nxt = order[(pos + 1) % len(order)]
            cur, said = replace(cur, syncopation=nxt[0], displaced=nxt[1]), (
                "a straight rhythm" if nxt == (0, False) else "light syncopation" if nxt == (1, False) else "full syncopation" if nxt == (2, False)
                else "syncopation with displacement")
        elif name == "harder":
            got = advance(cur)
            if got is None:
                return recipe, [], "This is already the hardest pattern I build — fully syncopated and displaced, with chromatic approaches on every beat."
            cur, said = got
        elif name == "easier":
            got = ease(cur)
            if got is None:
                return recipe, [], "This is already the easiest scale pattern I build (Beginner), so I haven't changed it."
            cur, said = got[0], f"simplified: {got[1]}"
        if cur == before:
            return recipe, [], "That doesn't change anything about the pattern."
        changes.append(said)
    return cur, changes, ""
