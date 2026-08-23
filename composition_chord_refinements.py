"""Structured chord-refinement proposals for Composition Studio.

Local musical transforms only — never silently mutate the composition.
Each proposal is Preview / Use this / Dismiss.
"""

from __future__ import annotations

from typing import Any

from custom_progression_lab import format_entries_bar_line, normalize_chord_symbol
from music_theory import key_is_minor, split_chord, transpose_chord

from composition_chord_suggestions import symbols_to_entries, _transpose_symbols

CHORD_REFINEMENT_INTENTS: tuple[tuple[str, str], ...] = (
    ("happier", "Make this happier"),
    ("darker", "Make it darker"),
    ("more_tension", "More tension"),
    ("more_resolution", "Stronger resolution"),
    ("surprise", "Surprise chord"),
    ("stronger_lift", "Stronger lift"),
    ("simpler", "Simplify"),
    ("more_emotional", "More emotional"),
)


def refinement_intent_label(intent_id: str) -> str:
    for iid, label in CHORD_REFINEMENT_INTENTS:
        if iid == intent_id:
            return label
    return str(intent_id or "Refine")


def _entry_symbols(entries: list[dict[str, Any]] | None) -> list[str]:
    out: list[str] = []
    for entry in entries or []:
        if isinstance(entry, dict):
            sym = str(entry.get("chord") or "").strip()
        else:
            sym = str(entry or "").strip()
        if sym:
            out.append(normalize_chord_symbol(sym) or sym)
    return out


def _entries_from_symbols(symbols: list[str], template: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    if template and len(template) == len(symbols):
        out: list[dict[str, Any]] = []
        for sym, old in zip(symbols, template):
            row = dict(old) if isinstance(old, dict) else {"chord": sym, "bars": 1}
            row["chord"] = sym
            out.append(row)
        return out
    return symbols_to_entries(symbols)


def _make_majorish(sym: str) -> str:
    root, suffix = split_chord(str(sym or "C"))
    suf = str(suffix or "")
    low = suf.lower()
    if low.startswith("m") and not low.startswith("maj") and not low.startswith("min"):
        # Am → A, Am7 → Amaj7-ish keep as A7 for brightness, Em7 → E
        if "7" in low and "maj" not in low:
            return f"{root}"
        return root
    if "dim" in low or "ø" in low or "m7b5" in low:
        return root
    return sym


def _make_minorish(sym: str) -> str:
    root, suffix = split_chord(str(sym or "C"))
    suf = str(suffix or "")
    low = suf.lower()
    if low.startswith("m") and not low.startswith("maj"):
        return sym
    if "maj7" in low:
        return f"{root}m7"
    if "7" in low and not low.startswith("m"):
        return f"{root}m7"
    if "sus" in low or "add" in low:
        return f"{root}m"
    return f"{root}m"


def _add_extension(sym: str, *, kind: str) -> str:
    root, suffix = split_chord(str(sym or "C"))
    suf = str(suffix or "")
    low = suf.lower()
    if kind == "7":
        if "7" in low or "9" in low:
            return sym
        if low.startswith("m") and not low.startswith("maj"):
            return f"{root}m7"
        if "maj" in low:
            return f"{root}maj7"
        return f"{root}7"
    if kind == "add9":
        if "add9" in low or "9" in low:
            return sym
        return f"{root}{suf}add9" if suf else f"{root}add9"
    if kind == "sus4":
        if "sus" in low:
            return sym
        return f"{root}sus4"
    return sym


def _tonic_for_key(key: str) -> str:
    text = str(key or "C").strip() or "C"
    if key_is_minor(text):
        root, _ = split_chord(text if text.endswith("m") else f"{text}m")
        return f"{root}m"
    root, _ = split_chord(text.rstrip("m") if text.endswith("m") else text)
    return root


def _dominant_for_key(key: str) -> str:
    tonic = _tonic_for_key(key)
    # Move up a fifth from tonic root.
    root, _ = split_chord(tonic)
    return transpose_chord(root, 7, reference_key=key)


def _subdominant_for_key(key: str) -> str:
    tonic = _tonic_for_key(key)
    root, _ = split_chord(tonic)
    return transpose_chord(root, 5, reference_key=key)


def propose_chord_refinement(
    doc: dict[str, Any],
    section: dict[str, Any],
    intent: str,
    *,
    entries: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Return a proposed progression change without mutating ``doc``."""
    g = doc.get("global") or {}
    key = str(g.get("original_key_center") or "C")
    intent = str(intent or "").strip().lower()
    source_entries = list(entries if entries is not None else (section.get("chords") or []))
    symbols = _entry_symbols(source_entries)
    if len(symbols) < 1:
        return None

    label = str(section.get("label") or "Section")
    proposed = list(symbols)
    explanation = ""
    name = refinement_intent_label(intent)

    if intent == "happier":
        # Brighten the last chord (or majority of minor color).
        idx = len(proposed) - 1
        before = proposed[idx]
        proposed[idx] = _make_majorish(before)
        if proposed[idx] == before and len(proposed) >= 2:
            proposed[0] = _make_majorish(proposed[0])
        explanation = (
            f"Brightening the end toward a major color opens the harmony — "
            f"a happier landing for {label.lower()}."
        )
    elif intent == "darker":
        idx = len(proposed) - 1
        before = proposed[idx]
        proposed[idx] = _make_minorish(before)
        explanation = (
            f"Turning the last chord darker (major → minor color) adds emotional weight "
            f"without rewriting the whole {label.lower()}."
        )
    elif intent == "surprise":
        # Borrowed iv / ♭VI flavor on the last chord.
        tonic_root, _ = split_chord(_tonic_for_key(key))
        if key_is_minor(key):
            surprise = transpose_chord(tonic_root, 8, reference_key=key)  # ♭VI area approx
            surprise = _make_majorish(surprise)
        else:
            surprise = f"{tonic_root}m"  # borrowed iv of relative — use parallel minor tonic
            # Prefer ♭VII rock surprise for major keys
            surprise = transpose_chord(tonic_root, 10, reference_key=key)
        proposed[-1] = surprise
        explanation = (
            "Swapping the last chord for an unexpected neighbor adds a borrowed-color surprise "
            "before the section turns over."
        )
    elif intent == "more_tension":
        dom = _dominant_for_key(key)
        proposed[-1] = _add_extension(dom, kind="7")
        explanation = (
            f"Ending on a dominant ({proposed[-1]}) creates pull — tension that wants to resolve "
            f"into the next section."
        )
    elif intent == "more_resolution":
        tonic = _tonic_for_key(key)
        proposed[-1] = tonic
        explanation = (
            f"Landing on the home chord ({tonic}) gives a clearer sense of arrival and rest."
        )
    elif intent == "stronger_lift":
        # Start on IV or move first chord up a step of energy.
        sub = _subdominant_for_key(key)
        proposed[0] = sub
        if len(proposed) >= 2:
            proposed[-1] = _tonic_for_key(key)
        explanation = (
            f"Opening on {sub} and aiming home creates lift — useful when {label.lower()} "
            "needs to feel like it opens up."
        )
    elif intent == "simpler":
        cleaned: list[str] = []
        for sym in proposed:
            root, suffix = split_chord(sym)
            low = str(suffix or "").lower()
            if low.startswith("m") and not low.startswith("maj"):
                cleaned.append(f"{root}m")
            else:
                cleaned.append(root)
        proposed = cleaned
        explanation = "Stripping extensions back to simple triads keeps the harmony clear and singable."
    elif intent == "more_emotional":
        idx = min(1, len(proposed) - 1)
        proposed[idx] = _add_extension(proposed[idx], kind="add9")
        if len(proposed) >= 3:
            proposed[-2] = _make_minorish(proposed[-2]) if not key_is_minor(key) else proposed[-2]
        explanation = (
            "A touch of add9 color (and a softer inner chord) makes the progression feel more emotional "
            "without changing its overall shape."
        )
    else:
        return None

    if proposed == symbols:
        # Force a small audible difference when transform no-ops.
        if intent in {"happier", "darker", "surprise"} and proposed:
            proposed[-1] = _add_extension(proposed[-1], kind="7")
            explanation = (explanation or "A small color change") + " A seventh adds noticeable color."

    entries_out = _entries_from_symbols(proposed, source_entries)
    return {
        "id": f"refine_{intent}_{label.lower()}",
        "intent": intent,
        "name": name,
        "why": explanation.strip(),
        "chords": entries_out,
        "line": format_entries_bar_line(entries_out),
        "source_line": format_entries_bar_line(source_entries),
        "mutates": False,
    }
