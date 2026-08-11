"""Detect and compose two-feature comparison answers from canonical AppKnowledge."""

from __future__ import annotations

import re
from typing import Any

from music_coach_ami.app_knowledge import CREATIVE_COMPARISONS, FEATURES, compare_features

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


def _when_short(when_to_use: str) -> str:
    text = str(when_to_use or "").strip()
    if text.lower().startswith("when "):
        return text[5:].strip().rstrip(".")
    return text.rstrip(".")


def _match_feature_in_fragment(fragment: str) -> str:
    frag = str(fragment or "").lower().strip()
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
    parts = [
        f"**{fa.display_name}**",
        fa.purpose,
        f"Use it when { _when_short(fa.when_to_use).lower() }.",
        "",
        f"**{fb.display_name}**",
        fb.purpose,
        f"Use it when { _when_short(fb.when_to_use).lower() }.",
        "",
        "**Main difference**",
        main,
        "",
        f"**Use {fa.display_name} when** {_when_short(fa.when_to_use).lower()}.",
        f"**Use {fb.display_name} when** {_when_short(fb.when_to_use).lower()}.",
    ]
    if pair_key == "missions_vs_live_coach":
        parts.append(
            "You can use **Missions** to define the task, then **Live Coach** while practicing "
            "when you want immediate guidance."
        )
    if pair_key == "entry_jam_vs_jam" and "entry" in str(low or "").lower():
        parts.insert(
            4,
            "**Entry & Jam** is the Creative workflow area that contains tools like **Style Jam** "
            "and **Jam Session Generator** — not the same kind of thing as a single generator mode.",
        )
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
    return {
        "body": body,
        "feature_a": a,
        "feature_b": b,
        "pair_key": pair_key,
        "suggested_next_action": (
            f"Try **{FEATURES[a].display_name}** or **{FEATURES[b].display_name}** "
            f"based on whether you need {_when_short(FEATURES[a].when_to_use).lower()} "
            f"or {_when_short(FEATURES[b].when_to_use).lower()}."
        ),
    }


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
            "feedback on my recording",
            "feedback on recording",
            "get feedback",
            "analyze myself",
            "upload analysis",
            "already recorded",
        )
    )


def resolve_recording_navigation_feature(low: str) -> str:
    """Prefer multitrack vs upload for recording-related navigation."""
    text = str(low or "").lower()
    if upload_analysis_intent_in_question(text) and not multitrack_intent_in_question(text):
        return "upload_analysis"
    if multitrack_intent_in_question(text):
        return "multitrack"
    if "feedback" in text and "record" in text:
        return "upload_analysis"
    return ""


def compose_ambiguous_record_yourself_answer() -> str:
    up = FEATURES["upload_analysis"]
    mt = FEATURES["multitrack"]
    return (
        "You have two real recording paths in the studio:\n\n"
        f"**For a quick single take you want analyzed:** **{up.display_name}** can capture live audio "
        "or accept a file, then run coach analysis on that take.\n\n"
        f"**For building or layering recordings:** **{mt.display_name}** ({mt.navigation_path}) "
        "lets you record or upload separate instrument slots, align them, and mix them together."
    )
