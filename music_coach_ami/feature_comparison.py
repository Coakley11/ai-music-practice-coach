"""Detect and compose two-feature comparison answers from canonical AppKnowledge."""

from __future__ import annotations

import re
from typing import Any

from music_coach_ami.app_knowledge import CREATIVE_COMPARISONS, FEATURES, compare_features
from music_coach_ami.song_editing_knowledge import is_practice_key_editing_semantics_question

# Longest alias phrases first within each feature.
_FEATURE_ALIAS_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "jam_session_generator",
        (
            "jam session generator",
            "jam generator",
        ),
    ),
        (
            "style_jam",
            (
                "entry & jam style mode",
                "entry style jam",
                "style jam mode",
                "style jam",
            ),
        ),
    (
        "live_coach",
        ("live coach",),
    ),
    (
        "missions",
        ("missions", "mission"),
    ),
    (
        "backing",
        ("backing track studio", "backing track", "backing"),
    ),
    (
        "upload_analysis",
        ("upload & analysis", "upload analysis", "upload analysis", "upload"),
    ),
    (
        "multitrack",
        (
            "multitrack recorder",
            "multitrack",
            "multi track",
            "multi-track",
        ),
    ),
    (
        "harmony_map",
        ("harmony map",),
    ),
    (
        "creative",
        (
            "entry & jam",
            "entry and jam",
            "improvisation studio",
            "creative studio",
        ),
    ),
    (
        "practice",
        ("practice key", "practice workspace"),
    ),
    (
        "songs",
        ("editing song chords", "edit song chords", "song chords", "chord chart edit"),
    ),
)

_PAIR_KEYS: dict[frozenset[str], str] = {
    frozenset({"missions", "live_coach"}): "missions_vs_live_coach",
    frozenset({"backing", "jam_session_generator"}): "backing_vs_jam",
    frozenset({"missions", "jam_session_generator"}): "missions_vs_jam",
    frozenset({"upload_analysis", "live_coach"}): "upload_vs_live_coach",
    frozenset({"style_jam", "jam_session_generator"}): "style_jam_vs_jam",
    frozenset({"creative", "jam_session_generator"}): "entry_jam_vs_jam",
    frozenset({"multitrack", "upload_analysis"}): "multitrack_vs_upload",
    frozenset({"practice", "songs"}): "practice_key_vs_chord_edit",
}

_CREATIVE_COMPARISON_PAIRS = frozenset(
    {
        frozenset({"style_jam", "jam_session_generator"}),
        frozenset({"creative", "jam_session_generator"}),
        frozenset({"missions", "jam_session_generator"}),
    }
)

_COMPARISON_MARKERS = (
    "difference between",
    "different between",
    "compare ",
    " compared with ",
    " compared to ",
    " vs ",
    " versus ",
    "should i use",
    "which is better",
    "which should i use",
    " or ",
)


def _normalize_when_clause(when_to_use: str) -> str:
    """Return a natural 'best for' fragment without duplicated when/during/you want."""
    text = str(when_to_use or "").strip().rstrip(".")
    low = text.lower()
    for prefix in (
        "when you want ",
        "when you need ",
        "when ",
        "during ",
    ):
        if low.startswith(prefix):
            text = text[len(prefix) :].strip()
            low = text.lower()
    if low.startswith("you want "):
        text = text[9:].strip()
        low = text.lower()
    if low.startswith("to "):
        text = text[3:].strip()
        low = text.lower()
    return text.rstrip(".")


def _best_for_phrase(when_to_use: str, *, purpose: str = "") -> str:
    clause = _normalize_when_clause(when_to_use)
    low = clause.lower()
    if low.startswith("improvise freely with a generated harmonic setting"):
        clause = "open-ended improvisation over a newly generated harmonic setting"
    elif low.startswith("improvise freely"):
        clause = "open-ended improvisation over a generated harmonic setting"
    elif low.startswith("improvise"):
        clause = f"open-ended {clause}"
    elif low.startswith("a structured challenge"):
        clause = "structured practice challenges on your active song"
    elif low.startswith("during creative practice when you want in-the-moment targets"):
        clause = "in-the-moment targets while you play"
    elif not clause and purpose:
        clause = purpose.strip().rstrip(".")
    return clause.rstrip(".")


def _find_it_line(feat: object) -> str:
    path = str(getattr(feat, "navigation_path", "") or "").strip()
    if not path:
        return ""
    return f"**Find it:** {path}"


def _feature_comparison_block(feat: object) -> list[str]:
    lines = [f"**{feat.display_name}**", str(feat.purpose).strip()]
    best = _best_for_phrase(str(getattr(feat, "when_to_use", "") or ""), purpose=str(feat.purpose or ""))
    if best:
        lines.append(f"**Best for:** {best}.")
    find_it = _find_it_line(feat)
    if find_it:
        lines.append(find_it)
    return lines


def _comparison_best_choice(pair_key: str, fa: object, fb: object) -> str:
    templates = {
        "missions_vs_live_coach": (
            "Choose **Missions** if you want a structured assignment; "
            "choose **Live Coach** if you want immediate guidance while playing."
        ),
        "style_jam_vs_jam": (
            "Choose **Style Jam** when style, mood, and groove matter; "
            "choose **Jam Session Generator** when you want a fresh progression to explore."
        ),
        "backing_vs_jam": (
            "Choose **Backing Track Studio** to loop your current song; "
            "choose **Jam Session Generator** for a newly generated chart."
        ),
        "entry_jam_vs_jam": (
            "Open **Creative → Entry & Jam** for jam tools; use **Jam Session Generator** "
            "when you want a standalone generated progression."
        ),
        "multitrack_vs_upload": (
            "Choose **Multitrack** to layer parts; choose **Upload & Analysis** "
            "when you want feedback on one finished take."
        ),
    }
    if pair_key in templates:
        return templates[pair_key]
    return (
        f"Choose **{fa.display_name}** or **{fb.display_name}** based on which job "
        f"matches what you need right now."
    )


def _normalize_match_fragment(fragment: str) -> str:
    text = str(fragment or "").lower().strip()
    text = re.sub(r"'s\b", "s", text)
    text = text.replace("'", "")
    text = re.sub(r"\bsongs\b", "song", text)
    return text


def _match_feature_in_fragment(fragment: str) -> str:
    frag = _normalize_match_fragment(fragment)
    if not frag:
        return ""
    best_fid = ""
    best_len = 0
    for fid, phrases in _FEATURE_ALIAS_GROUPS:
        for phrase in phrases:
            if phrase in frag and len(phrase) > best_len:
                best_fid = fid
                best_len = len(phrase)
    return best_fid


def _split_comparison_halves(low: str) -> tuple[str, str] | None:
    text = low.strip()
    m = re.search(
        r"difference between\s+(.+?)\s+and\s+(.+?)(?:\?|$)",
        text,
        flags=re.I,
    )
    if m:
        return m.group(1).strip(), m.group(2).strip()
    m = re.search(
        r"(?:should i use|which is better(?: for this)?,?|which should i use)\s+(.+?)\s+or\s+(.+?)(?:\?|$)",
        text,
        flags=re.I,
    )
    if m:
        return m.group(1).strip(), m.group(2).strip()
    m = re.search(r"(.+?)\s+vs\.?\s+(.+?)(?:\?|$)", text, flags=re.I)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    m = re.search(
        r"(?:compare|compared with|compared to)\s+(.+?)\s+(?:with|to)\s+(.+?)(?:\?|$)",
        text,
        flags=re.I,
    )
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return None


def extract_comparison_feature_pair(low: str) -> tuple[str, str] | None:
    """Return two distinct feature_ids if the question is an explicit A-vs-B comparison."""
    text = str(low or "").lower()
    if not any(m in text for m in _COMPARISON_MARKERS) and " vs " not in text:
        return None
    halves = _split_comparison_halves(text)
    if halves:
        left, right = halves
        a = _match_feature_in_fragment(left)
        b = _match_feature_in_fragment(right)
        if a and b and a != b:
            return a, b
    # Fallback: pick two best distinct matches anywhere in the question.
    hits: list[tuple[int, str]] = []
    for fid, phrases in _FEATURE_ALIAS_GROUPS:
        for phrase in phrases:
            if phrase in text:
                hits.append((len(phrase), fid))
                break
    hits.sort(key=lambda x: (-x[0], x[1]))
    seen: list[str] = []
    for _, fid in hits:
        if fid not in seen:
            seen.append(fid)
        if len(seen) >= 2:
            return seen[0], seen[1]
    return None


def is_feature_comparison_question(low: str) -> bool:
    if is_practice_key_editing_semantics_question(low):
        return False
    return extract_comparison_feature_pair(low) is not None


def is_creative_feature_comparison(low: str) -> bool:
    pair = extract_comparison_feature_pair(low)
    return bool(pair and frozenset(pair) in _CREATIVE_COMPARISON_PAIRS)


def _pair_key_for(a: str, b: str) -> str:
    return _PAIR_KEYS.get(frozenset({a, b}), "")


def compose_feature_comparison(fid_a: str, fid_b: str, *, low: str = "") -> str:
    fa = FEATURES.get(fid_a)
    fb = FEATURES.get(fid_b)
    if not fa or not fb:
        return ""
    pair_key = _pair_key_for(fid_a, fid_b)
    main = compare_features(pair_key) if pair_key else ""
    if not main:
        main = fa.distinctions or fb.distinctions or (
            f"**{fa.display_name}** and **{fb.display_name}** solve different jobs in the studio."
        )
    parts: list[str] = []
    parts.extend(_feature_comparison_block(fa))
    parts.append("")
    if pair_key == "entry_jam_vs_jam" and "entry" in str(low or "").lower():
        parts.append(
            "**Entry & Jam** is the Creative workflow area that contains jam tools such as "
            "**Style Jam** and **Jam Session Generator**."
        )
        parts.append("")
    parts.extend(_feature_comparison_block(fb))
    parts.extend(["", "**Main difference**", main])
    return "\n".join(parts)


def try_comparison_response(low: str) -> dict[str, Any] | None:
    pair = extract_comparison_feature_pair(low)
    if not pair:
        return None
    a, b = pair
    body = compose_feature_comparison(a, b, low=low)
    if not body:
        return None
    pair_key = _pair_key_for(a, b)
    fa = FEATURES[a]
    fb = FEATURES[b]
    return {
        "body": body,
        "feature_a": a,
        "feature_b": b,
        "pair_key": pair_key,
        "suggested_next_action": _comparison_best_choice(pair_key, fa, fb),
    }


def _practice_log_phrases_match(text: str) -> bool:
    return any(
        p in text
        for p in (
            "log my practice",
            "practice log",
            "log practice",
            "log today's session",
            "log todays session",
            "keep track of my practice",
            "track what i practiced",
            "record what i practiced",
            "record what i practice",
            "save a practice session",
            "how do i log",
            "where do i log",
        )
    )


def practice_log_intent_in_question(low: str) -> bool:
    """Record/log practice history — not audio capture."""
    return _practice_log_phrases_match(str(low or "").lower())


def audio_recording_intent_in_question(low: str) -> bool:
    """Single-part audio capture — not practice logging or multitrack layering."""
    text = str(low or "").lower()
    if _practice_log_phrases_match(text):
        return False
    if multitrack_intent_in_question(text):
        return False
    if any(
        p in text
        for p in (
            "record myself",
            "recording of myself",
            "audio recording",
            "record a take",
            "record myself playing",
            "make a recording",
            "make an audio recording",
            "record my playing",
            "can i record myself",
        )
    ):
        return True
    if "record" not in text:
        return False
    if any(p in text for p in ("what i practiced", "what i practice", "practice log")):
        return False
    return any(
        p in text
        for p in (
            "myself",
            "my playing",
            "a take",
            "audio",
            "flute",
            "guitar",
            "piano",
            "sax",
            "vocals",
            "playing",
        )
    )


def is_ambiguous_single_audio_recording_question(low: str) -> bool:
    text = str(low or "").lower()
    return (
        audio_recording_intent_in_question(text)
        and not upload_analysis_intent_in_question(text)
        and not multitrack_intent_in_question(text)
    )


def multitrack_intent_in_question(low: str) -> bool:
    text = str(low or "").lower()
    if any(
        p in text
        for p in (
            "multitrack",
            "multi track",
            "multi-track",
            "overdub",
            "record layers",
            "layer recordings",
            "record several parts",
            "record another part",
            "add another part",
            "then add another",
            "record one part",
            "one part and then",
            "harmony part over",
            "upload one track and record",
            "upload one layer",
            "mute one track",
            "mute one part",
            "mute one recorded",
            "mute one layer",
            "solo one track",
            "solo one part",
            "volume of one layer",
            "line up two recordings",
            "align ",
            "several parts of myself",
            "multiple parts",
            "layer several",
            "record several parts",
            "record multiple",
            "overdub",
            "overdub another",
            "record a harmony",
            "loop the chorus while",
            "without a backing track",
            "play back all of my recorded",
            "play back all my recorded",
            "upload one track and record another",
            "upload one layer and record",
        )
    ):
        return True
    if "mixer" in text and "record" in text:
        return True
    if "layers" in text and any(p in text for p in ("record", "upload", "mute", "solo")):
        return True
    return False


def upload_analysis_intent_in_question(low: str) -> bool:
    text = str(low or "").lower()
    return any(
        p in text
        for p in (
            "analyze my take",
            "analyze a recording",
            "analyze the take",
            "feedback on my recording",
            "feedback on recording",
            "get feedback",
            "analyze myself",
            "upload analysis",
            "already recorded",
            "record myself and get feedback",
            "record myself playing and get feedback",
            "record a take and have",
            "have the app analyze",
        )
    )


def resolve_recording_navigation_feature(low: str) -> str:
    """Prefer practice log vs multitrack vs upload for recording-related navigation."""
    text = str(low or "").lower()
    if practice_log_intent_in_question(text):
        return "practice_log"
    if multitrack_intent_in_question(text):
        return "multitrack"
    if upload_analysis_intent_in_question(text):
        return "upload_analysis"
    if re.search(r"\bwhere\b", text) and any(
        p in text for p in ("make an audio recording", "audio recording")
    ):
        return "upload_analysis"
    if audio_recording_intent_in_question(text):
        return ""
    if "feedback" in text and "record" in text:
        return "upload_analysis"
    return ""


def compose_ambiguous_record_yourself_answer() -> str:
    up = FEATURES["upload_analysis"]
    mt = FEATURES["multitrack"]
    return (
        "**For a single take:** **Upload & Analysis** — record live or upload a file, "
        "then analyze the take.\n\n"
        "**For several layers/overdubs:** **Multitrack** — record or upload separate parts "
        "and mix them together.\n\n"
        "**Find them:**\n"
        f"- **Upload & Analysis:** {up.navigation_path}\n"
        f"- **Multitrack:** {mt.navigation_path}\n\n"
        "If you just want to record yourself once, start with **Upload & Analysis**. "
        "If you want to build multiple parts, use **Multitrack**."
    )
