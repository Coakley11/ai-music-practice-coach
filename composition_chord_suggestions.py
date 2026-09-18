"""Rule-based chord progression suggestions for Composition Studio (CS-B2)."""

from __future__ import annotations

from typing import Any

from custom_progression_lab import format_entries_bar_line
from music_theory import key_is_minor, semitone_distance, transpose_chord

SECTION_HARMONY_FEELINGS: tuple[tuple[str, str], ...] = (
    ("stable", "Stable — grounded and resolved"),
    ("uplifting", "Uplifting — opens up and lifts"),
    ("tense", "Tense — creates pull and anticipation"),
    ("reflective", "Reflective — inward and thoughtful"),
    ("energetic", "Energetic — driving forward"),
    ("melancholy", "Melancholy — bittersweet and emotional"),
)

DEFAULT_FEELING_BY_SECTION: dict[str, str] = {
    "Intro": "stable",
    "Verse": "reflective",
    "Pre-Chorus": "tense",
    "Chorus": "uplifting",
    "Bridge": "tense",
    "Solo": "energetic",
    "Interlude": "reflective",
    "Outro": "stable",
}

# Reference progressions in C major or A minor — transposed to the song key at runtime.
_PROGRESSION_LIBRARY: dict[str, list[dict[str, Any]]] = {
    "stable": [
        {
            "id": "stable_classic",
            "name": "Classic foundation",
            "ref_key": "C",
            "chords": ["C", "G", "Am", "F"],
            "why": "The familiar I–V–vi–IV shape feels safe and singable — a steady home base for verses or intros.",
        },
        {
            "id": "stable_plagal",
            "name": "Gentle cadence",
            "ref_key": "C",
            "chords": ["C", "F", "C", "G"],
            "why": "Plagal motion (I–IV) keeps the section grounded without dramatic tension.",
        },
        {
            "id": "stable_minor",
            "name": "Minor anchor",
            "ref_key": "Am",
            "chords": ["Am", "F", "C", "G"],
            "why": "A minor tonic with major lift on the IV — stable but emotionally shaded.",
        },
    ],
    "uplifting": [
        {
            "id": "uplift_open",
            "name": "Open lift",
            "ref_key": "C",
            "chords": ["C", "F", "G", "C"],
            "why": "Bright I–IV–V motion pushes forward — great for a chorus that opens up.",
        },
        {
            "id": "uplift_anthem",
            "name": "Anthem swell",
            "ref_key": "C",
            "chords": ["F", "G", "Am", "C"],
            "why": "Starts away from home and lands on I — classic emotional lift into the hook.",
        },
        {
            "id": "uplift_minor_lift",
            "name": "Minor to major lift",
            "ref_key": "Am",
            "chords": ["Am", "C", "G", "F"],
            "why": "Rises through relative major chords — bittersweet verse energy turning upward.",
        },
    ],
    "tense": [
        {
            "id": "tense_pull",
            "name": "Forward pull",
            "ref_key": "C",
            "chords": ["Am", "F", "Dm", "G"],
            "why": "vi–IV–ii–V creates forward motion and anticipation before a release.",
        },
        {
            "id": "tense_prechorus",
            "name": "Pre-chorus climb",
            "ref_key": "C",
            "chords": ["Am", "G", "F", "G"],
            "why": "Descending bass feel with repeated V — builds pressure before the chorus drops.",
        },
        {
            "id": "tense_bridge",
            "name": "Bridge contrast",
            "ref_key": "C",
            "chords": ["Dm", "G", "Em", "Am"],
            "why": "Starts on ii for fresh color — listeners feel they've traveled somewhere new.",
        },
    ],
    "reflective": [
        {
            "id": "reflective_intimate",
            "name": "Intimate verse",
            "ref_key": "Am",
            "chords": ["Am", "Em", "F", "C"],
            "why": "Gentle minor movement with space to breathe — ideal for storytelling verses.",
        },
        {
            "id": "reflective_wandering",
            "name": "Thoughtful drift",
            "ref_key": "C",
            "chords": ["C", "Em", "Am", "F"],
            "why": "Soft vi color keeps the section inward without losing the tonal center.",
        },
        {
            "id": "reflective_slow",
            "name": "Late-night feel",
            "ref_key": "Am",
            "chords": ["Am", "Dm", "G", "C"],
            "why": "Minor ii and a delayed return — contemplative and unhurried.",
        },
    ],
    "energetic": [
        {
            "id": "energy_drive",
            "name": "Driving groove",
            "ref_key": "C",
            "chords": ["C", "G", "F", "G"],
            "why": "Repeated V keeps momentum high — works for uptempo sections and solos.",
        },
        {
            "id": "energy_rock",
            "name": "Rock pulse",
            "ref_key": "C",
            "chords": ["C", "Bb", "F", "C"],
            "why": "♭VII adds rock energy without leaving the key for long.",
        },
        {
            "id": "energy_minor",
            "name": "Minor drive",
            "ref_key": "Am",
            "chords": ["Am", "G", "F", "E"],
            "why": "Harmonic minor touch on V — edgy and propulsive.",
        },
    ],
    "melancholy": [
        {
            "id": "melancholy_ballad",
            "name": "Ballad ache",
            "ref_key": "Am",
            "chords": ["Am", "F", "C", "G"],
            "why": "The classic sad-pop loop — tender, memorable, and emotionally direct.",
        },
        {
            "id": "melancholy_descent",
            "name": "Descending sigh",
            "ref_key": "Am",
            "chords": ["Am", "G", "F", "Em"],
            "why": "Stepwise bass descent feels like a emotional exhale.",
        },
        {
            "id": "melancholy_major",
            "name": "Bittersweet major",
            "ref_key": "C",
            "chords": ["C", "Am", "Em", "F"],
            "why": "Major tonic with heavy minor vi — hopeful on the surface, aching underneath.",
        },
    ],
}


def default_feeling_for_section(section: dict[str, Any]) -> str:
    label = str(section.get("label") or "Verse")
    return DEFAULT_FEELING_BY_SECTION.get(label, "stable")


def feeling_label(feeling_id: str) -> str:
    for fid, label in SECTION_HARMONY_FEELINGS:
        if fid == feeling_id:
            return label
    return feeling_id


def _transpose_symbols(symbols: list[str], ref_key: str, target_key: str) -> list[str]:
    steps = semitone_distance(ref_key, target_key)
    if steps == 0:
        return list(symbols)
    return [transpose_chord(sym, steps, reference_key=target_key) for sym in symbols]


def _pick_ref_key(target_key: str, recipe_ref: str) -> str:
    """Prefer minor reference recipes when the song is in a minor key."""
    if key_is_minor(target_key) and key_is_minor(recipe_ref):
        return recipe_ref
    if not key_is_minor(target_key) and not key_is_minor(recipe_ref):
        return recipe_ref
    if key_is_minor(target_key):
        return "Am" if recipe_ref == "C" else recipe_ref
    return "C" if recipe_ref == "Am" else recipe_ref


def symbols_to_entries(symbols: list[str]) -> list[dict[str, Any]]:
    return [{"chord": str(sym), "bars": 1} for sym in symbols if str(sym).strip()]


def _neighbor_harmony_symbols(doc: dict[str, Any], section: dict[str, Any]) -> list[str]:
    """Prior section's resolved chords (if any) — used for continuity-aware suggestions."""
    try:
        from composition_document import ordered_sections, harmony_edit_target
    except ImportError:
        return []

    sections = ordered_sections(doc)
    target_id = str(section.get("id") or "")
    prev_symbols: list[str] = []
    for sec in sections:
        sid = str(sec.get("id") or "")
        if sid == target_id:
            break
        _, edit = harmony_edit_target(doc, sid)
        chords = list((edit or {}).get("chords") or [])
        if chords:
            prev_symbols = [
                str(c.get("chord") or "").strip()
                for c in chords
                if isinstance(c, dict) and str(c.get("chord") or "").strip()
            ]
    return prev_symbols


def _continuity_recipe(
    doc: dict[str, Any],
    section: dict[str, Any],
    target_key: str,
) -> dict[str, Any] | None:
    """When a prior section has harmony, offer one lift/arrival idea that answers it."""
    prior = _neighbor_harmony_symbols(doc, section)
    if len(prior) < 2:
        return None
    label = str(section.get("label") or "")
    # Build a short answer progression from the last prior chord toward tonic / lift.
    last = prior[-1]
    tonic_ref = "Am" if key_is_minor(target_key) else "C"
    if label == "Chorus":
        # Aim for a strong I-centered lift after the verse.
        ref_chords = ["F", "G", "Am", "C"] if not key_is_minor(target_key) else ["F", "G", "Em", "Am"]
        why = (
            f"Answers the previous section ending on {last} with a lifting arrival — "
            "a classic Verse→Chorus handoff."
        )
        name = "Lift from previous section"
    elif label == "Bridge":
        ref_chords = ["Dm", "G", "Em", "Am"] if not key_is_minor(target_key) else ["Dm", "E", "Am", "G"]
        why = f"Contrasts the prior harmony (ending on {last}) with a fresher starting color."
        name = "Contrast after previous section"
    elif label in {"Verse", "Pre-Chorus"}:
        ref_chords = ["Am", "F", "C", "G"] if not key_is_minor(target_key) else ["Am", "G", "F", "E"]
        why = f"Keeps storytelling momentum after the prior section's {last} without stealing the hook."
        name = "Continue the story"
    else:
        return None

    symbols = _transpose_symbols(ref_chords, tonic_ref if not key_is_minor(target_key) else "Am", target_key)
    entries = symbols_to_entries(symbols)
    return {
        "id": f"continuity_{label.lower()}_{last}",
        "name": name,
        "why": why,
        "chords": entries,
        "line": format_entries_bar_line(entries),
        "feeling": "contextual",
        "context": "neighbor",
    }


def suggest_progressions(
    doc: dict[str, Any],
    section: dict[str, Any],
    feeling: str,
    *,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """Return progression ideas for a section, transposed to the Composition key.

    Uses canonical song-intent profile (style, concept, energy/BPM, section role,
    references) so Pop/Jazz/Rock/Bossa/Jewish produce materially different harmony.
    Descriptions are derived from the actual chord symbols after generation.
    """
    from composition_song_intent import (
        apply_feeling_chord_bias,
        apply_style_chord_color,
        build_song_intent_profile,
        describe_harmony_from_events,
        expand_harmonic_rhythm,
        style_harmony_recipes,
    )

    feeling = str(feeling or default_feeling_for_section(section)).strip().lower()
    profile = build_song_intent_profile(doc, section, harmony_feeling=feeling)
    target_key = str(profile.get("key_center") or "C")
    fam = str(profile.get("style_family") or "pop")

    # Style recipes first (actual vocabulary differences), then feeling library.
    style_recipes = style_harmony_recipes(fam, section_label=str(profile.get("section_label") or ""))
    feeling_recipes = list(_PROGRESSION_LIBRARY.get(feeling) or _PROGRESSION_LIBRARY["stable"])
    section_label = str(section.get("label") or profile.get("section_label") or "")
    if section_label == "Chorus" and feeling not in {"uplifting", "energetic"}:
        feeling_recipes = list(_PROGRESSION_LIBRARY.get("uplifting", [])) + feeling_recipes
    elif section_label == "Bridge":
        feeling_recipes = list(_PROGRESSION_LIBRARY.get("tense", [])) + feeling_recipes
    elif section_label == "Intro":
        feeling_recipes = list(_PROGRESSION_LIBRARY.get("stable", [])) + feeling_recipes
    elif section_label == "Outro":
        feeling_recipes = list(_PROGRESSION_LIBRARY.get("reflective", [])) + feeling_recipes
    elif section_label == "Pre-Chorus" and feeling not in {"tense", "energetic"}:
        feeling_recipes = list(_PROGRESSION_LIBRARY.get("tense", [])) + feeling_recipes
    elif section_label == "Verse" and feeling not in {"reflective", "stable"}:
        feeling_recipes = list(_PROGRESSION_LIBRARY.get("reflective", [])) + feeling_recipes

    # Prefer style recipes when they match mode; keep feeling recipes as fill.
    # Feeling library still contributes — later apply_feeling_chord_bias reshapes all.
    recipes: list[dict[str, Any]] = []
    for r in style_recipes:
        recipes.append(dict(r, context="style"))
    for r in feeling_recipes:
        recipes.append(dict(r, context="feeling"))

    # Concept flags can bias ordering (intimate → reflective; anthem → uplifting/energy).
    # Always keep style-context recipes ahead of feeling-library fill so Jazz≠Pop coloring of the same loop.
    flags = profile.get("flags") if isinstance(profile.get("flags"), dict) else {}

    def _recipe_rank(r: dict[str, Any]) -> tuple[int, int, int]:
        ctx = str(r.get("context") or "")
        # Style first, then matching feeling library, then other fill.
        if ctx == "style":
            style_first = 0
        elif ctx == "feeling":
            style_first = 1
        else:
            style_first = 2
        role_match = 0 if section_label and section_label in list(r.get("roles") or []) else 1
        lift_boost = 0
        if feeling in {"uplifting", "energetic"} or flags.get("anthem") or flags.get("uplifting"):
            lift_boost = 0 if "lift" in str(r.get("tag") or r.get("id") or "") else 1
        if feeling in {"melancholy", "reflective"} or flags.get("intimate") or flags.get("ballad"):
            if str(r.get("ref_key") or "") in {"Am", "A"}:
                lift_boost = min(lift_boost, 0)
            elif style_first >= 1:
                lift_boost = max(lift_boost, 1)
        if feeling == "tense":
            lift_boost = 0 if any(t in str(r.get("tag") or r.get("id") or "") for t in ("tense", "sub_dom", "secondary", "build")) else 1
        return (style_first, role_match, lift_boost)

    recipes = sorted(recipes, key=_recipe_rank)

    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    variant_i = 0

    # Melody-first: when an active melody exists, harmonize the FULL expanded
    # timeline only — do not offer short library progressions that would need
    # blind chord repeats to cover the section.
    try:
        from composition_document import section_melody_events
        from composition_melody_harmonize import harmonize_melody_to_progressions

        mel_events = section_melody_events(section)
    except Exception:
        mel_events = []
    if mel_events and limit >= 1:
        harms = list(
            harmonize_melody_to_progressions(
                mel_events,
                key=target_key,
                meter=str(profile.get("meter") or "4/4"),
                profile=profile,
                feeling=feeling,
                limit=max(1, int(limit)),
            )
        )
        if harms:
            return harms[: max(1, int(limit))]

    # Continuity from prior accepted harmony — all styles benefit from song coherence.
    continuity = _continuity_recipe(doc, section, target_key)
    if continuity and limit > 2:
        cont_syms = [str(c.get("chord") or "") for c in continuity.get("chords") or [] if isinstance(c, dict)]
        cont_syms = apply_style_chord_color(cont_syms, profile, variant=0)
        cont_syms = apply_feeling_chord_bias(cont_syms, profile, feeling=feeling, variant=0)
        cont_syms = expand_harmonic_rhythm(cont_syms, profile)
        cont_entries = symbols_to_entries(cont_syms)
        continuity = dict(continuity)
        continuity["chords"] = cont_entries
        continuity["line"] = format_entries_bar_line(cont_entries)
        continuity["why"] = describe_harmony_from_events(cont_entries, profile=profile)
        continuity["style_family"] = fam
        continuity["feeling"] = feeling
        continuity["intent_profile"] = {
            "style_family": fam,
            "song_style_family": profile.get("song_style_family"),
            "energy_tier": profile.get("energy_tier"),
            "section_goal": profile.get("section_goal"),
            "harmony_feeling": feeling,
        }
        out.append(continuity)
        seen.add(str(continuity.get("id") or ""))

    def _emit(recipe: dict[str, Any], *, allow_mode_mismatch: bool = False) -> bool:
        nonlocal variant_i
        rid = str(recipe.get("id") or "")
        if not rid or rid in seen:
            return False
        recipe_ref = str(recipe.get("ref_key") or "C")
        if not allow_mode_mismatch and key_is_minor(target_key) != key_is_minor(recipe_ref):
            return False
        seen.add(rid)
        ref_key = _pick_ref_key(target_key, recipe_ref)
        symbols = _transpose_symbols(list(recipe.get("chords") or []), ref_key, target_key)
        symbols = apply_style_chord_color(symbols, profile, variant=variant_i)
        symbols = apply_feeling_chord_bias(symbols, profile, feeling=feeling, variant=variant_i)
        symbols = expand_harmonic_rhythm(symbols, profile)
        # Concept: harmonic surprise on bridge variant
        if flags.get("harmonic_surprise") and str(profile.get("section_goal")) == "contrast" and len(symbols) >= 2:
            # Raise color on second chord if still plain triad.
            if "7" not in symbols[1] and "m" not in symbols[1]:
                symbols[1] = symbols[1] + "maj7"
        # Feeling-suffixed id so uplifting vs tense can both emit related recipes.
        emit_id = f"{rid}__{feeling}" if feeling else rid
        if emit_id in {str(x.get("id") or "") for x in out}:
            emit_id = f"{emit_id}_{variant_i}"
        entries = symbols_to_entries(symbols)
        why = describe_harmony_from_events(entries, profile=profile)
        out.append(
            {
                "id": emit_id,
                "name": str(recipe.get("name") or "Suggestion"),
                "why": why,
                "chords": entries,
                "line": format_entries_bar_line(entries),
                "feeling": feeling,
                "context": str(recipe.get("context") or "library"),
                "style_family": fam,
                "intent_profile": {
                    "style_family": fam,
                    "song_style_family": profile.get("song_style_family"),
                    "energy_tier": profile.get("energy_tier"),
                    "section_goal": profile.get("section_goal"),
                    "harmony_feeling": feeling,
                    "harmonic_complexity": profile.get("harmonic_complexity"),
                },
            }
        )
        variant_i += 1
        return True

    # For modal/klezmer/hasidic families, allow minor style recipes even in a
    # written major key — otherwise feeling-library fill crowds them out.
    allow_style_mode_flex = fam in {
        "jewish_klezmer",
        "jewish_modal",
        "jewish_hasidic",
        "jewish_israeli",
    }

    for recipe in recipes:
        flex = allow_style_mode_flex and str(recipe.get("context") or "") == "style"
        if _emit(recipe, allow_mode_mismatch=flex):
            if len(out) >= limit:
                break

    if len(out) < limit:
        for recipe in recipes:
            if _emit(recipe, allow_mode_mismatch=True):
                if len(out) >= limit:
                    break
    return out


def coach_line_for_section(
    doc: dict[str, Any],
    section: dict[str, Any],
    *,
    feeling: str = "",
) -> str:
    variant = str(section.get("label_variant") or section.get("label") or "this section")
    label = str(section.get("label") or "Section")
    feel = feeling_label(feeling or default_feeling_for_section(section))
    meta = doc.get("metadata") or {}
    genre = str(meta.get("style") or "your song")
    jobs = {
        "Intro": "set the mood before the story begins",
        "Verse": "carry the narrative without stealing the spotlight",
        "Pre-Chorus": "build tension right before the hook",
        "Chorus": "deliver the emotional peak people remember",
        "Bridge": "offer contrast — a new angle on the story",
        "Solo": "create space for expression over the groove",
        "Interlude": "give the listener a breath",
        "Outro": "wind down and leave a lasting impression",
    }
    job = jobs.get(label, "support this moment in the song")
    return (
        f"For <strong>{variant}</strong>, you're aiming for a <strong>{feel.split('—')[0].strip().lower()}</strong> feel. "
        f"In {genre}, this section should {job}. "
        f"Try a suggestion or write your own — then preview before you commit."
    )
