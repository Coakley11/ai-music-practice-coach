"""Canonical Composition song-intent / style profile (SSOT for Chords + Melody).

VISION / SONG SETTINGS / USER INTENT
            ↓
build_song_intent_profile(doc, section, ...)
            ↓
     CHORDS + MELODY
"""

from __future__ import annotations

from typing import Any

STYLE_FAMILIES: tuple[str, ...] = (
    "pop",
    "rock",
    "jazz",
    "bossa",
    "blues",
    "soul",
    "folk",
    "country",
    "electronic",
    "classical",
    "jewish_pop",
    "jewish_israeli",
    "jewish_hasidic",
    "jewish_klezmer",
    "jewish_modal",
    "other",
)

_GENRE_TO_FAMILY: dict[str, str] = {
    "pop": "pop",
    "rock": "rock",
    "jazz": "jazz",
    "bossa": "bossa",
    "bossa nova": "bossa",
    "blues": "blues",
    "soul/r&b": "soul",
    "soul": "soul",
    "r&b": "soul",
    "folk": "folk",
    "country": "country",
    "hip-hop": "pop",
    "electronic": "electronic",
    "classical": "classical",
    "jewish": "jewish_pop",
    "other": "other",
}

# UI label → style family. "Let my description decide" resolves via free text.
JEWISH_DIRECTION_TO_FAMILY: dict[str, str] = {
    "Contemporary Jewish pop": "jewish_pop",
    "Israeli pop": "jewish_israeli",
    "Hasidic / dance": "jewish_hasidic",
    "Traditional / modal": "jewish_modal",
    "Klezmer-influenced": "jewish_klezmer",
    "Ballad": "jewish_pop",
    "Let my description decide": "",
}


def _blob(*parts: Any) -> str:
    return " ".join(str(p or "").strip().lower() for p in parts if str(p or "").strip())


def jewish_direction_from_doc(doc: dict[str, Any] | None) -> str:
    """Read persisted Jewish direction; empty when genre is not Jewish."""
    if not isinstance(doc, dict):
        return ""
    meta = doc.get("metadata") if isinstance(doc.get("metadata"), dict) else {}
    genre = str(meta.get("style") or "").strip()
    if genre != "Jewish":
        return ""
    direction = str(meta.get("jewish_direction") or "").strip()
    if not direction:
        seed = ((doc.get("origin") or {}).get("seed_payload") or {}) if isinstance(doc.get("origin"), dict) else {}
        direction = str(seed.get("jewish_direction") or "").strip()
    return direction


def normalize_style_family(
    genre: str,
    *,
    concept: str = "",
    references: str = "",
    notes: str = "",
    jewish_direction: str = "",
) -> str:
    """Map UI genre + optional Jewish direction + free text to a generation style family.

    Jewish direction is guidance only when Genre is Jewish. Freeform notes can still
    nudge a section toward modal/klezmer color without changing the song genre.
    Non-Jewish genres ignore jewish_direction entirely (no stale bleed).
    """
    g = str(genre or "").strip().lower()
    family = _GENRE_TO_FAMILY.get(g, "other")
    text = _blob(concept, references, notes)

    # Explicit genre wins for first-class styles (do not let free text steal Bossa→Jazz etc.)
    if g == "bossa":
        return "bossa"
    if g == "jazz":
        return "jazz"
    if g == "rock":
        return "rock"
    if g == "pop":
        return "pop"

    if family == "jewish_pop" or g == "jewish":
        direction = str(jewish_direction or "").strip()
        mapped = JEWISH_DIRECTION_TO_FAMILY.get(direction, "")
        if mapped:
            # Direction is primary; freeform may still pull toward modal/klezmer on a section.
            free_nudge = _jewish_substyle(text) if text else ""
            if free_nudge and free_nudge != mapped and any(
                w in text for w in ("traditional", "modal", "klezmer", "freygish", "ahava")
            ):
                return free_nudge
            if direction == "Ballad":
                return "jewish_pop"
            return mapped
        return _jewish_substyle(text)

    # Free-text bossa/jazz only when genre is Other / empty.
    if g in {"", "other"} and ("bossa" in text or "nova" in text):
        return "bossa"
    if g in {"", "other", "pop"} and "jazz" in text:
        return "jazz"
    return family if family in STYLE_FAMILIES else "other"


def _jewish_substyle(text: str) -> str:
    """Distinguish Jewish directions from free text / references."""
    if any(w in text for w in ("klezmer", "freylekh", "hora", "bulgar", "doina")):
        return "jewish_klezmer"
    if any(w in text for w in ("hasidic", "chassidic", "nigun", "simcha", "wedding dance")):
        return "jewish_hasidic"
    if any(w in text for w in ("ahava rabbah", "freygish", "phrygian dominant", "hijaz", "modal jewish", "traditional")):
        return "jewish_modal"
    if any(w in text for w in ("israeli", "tel aviv", "mizrahi", "hebrew pop", "israel")):
        return "jewish_israeli"
    if any(w in text for w in ("contemporary jewish", "jewish pop", "modern jewish", "camp song")):
        return "jewish_pop"
    if "ballad" in text:
        return "jewish_pop"
    return "jewish_pop"


def parse_creative_flags(concept: str = "", references: str = "", notes: str = "", remember: str = "") -> dict[str, bool]:
    """Single intent parser for freeform creative text."""
    blob = _blob(concept, references, notes, remember)
    return {
        "intimate": any(w in blob for w in ("intimate", "quiet", "soft", "whisper", "close", "bedroom")),
        "anthem": any(w in blob for w in ("anthem", "celebrat", "big ", "huge", "stadium", "crowd", "shout")),
        "love": any(w in blob for w in ("love", "romantic", "romance", "heart")),
        "uplifting": any(w in blob for w in ("uplift", "hope", "bright", "joyful", "happy", "celebrat")),
        "reflective": any(w in blob for w in ("reflect", "thoughtful", "introspective", "narrative")),
        "dramatic": any(w in blob for w in ("dramatic", "intense", "cinematic", "epic")),
        "driving": any(w in blob for w in ("driving", "upbeat", "energetic", "fast groove", "high energy")),
        "ballad": any(w in blob for w in ("ballad", "slow song", "slow and", "tender")),
        "singable": any(w in blob for w in ("easy to sing", "singable", "sing along", "crowd sing")),
        "piano": any(w in blob for w in ("piano", "billy joel", "elton", "keys-driven", "keyboard")),
        "guitar": any(w in blob for w in ("guitar", "strum", "acoustic guitar", "electric guitar")),
        "build_chorus": any(w in blob for w in ("bigger in the chorus", "build to chorus", "chorus bigger")),
        "harmonic_surprise": any(w in blob for w in ("harmonic surprise", "unexpected chord", "surprise in the bridge")),
        "story": any(w in blob for w in ("story song", "narrative", "storytelling", "piano-driven story")),
    }


def parse_reference_attributes(references: str) -> dict[str, Any]:
    """Translate artist/song references into attributes — never copy songs."""
    blob = _blob(references)
    attrs: dict[str, Any] = {
        "piano_driven": False,
        "guitar_driven": False,
        "functional_harmony": False,
        "rich_harmony": False,
        "narrative_phrasing": False,
        "ballad_bias": False,
        "rhythmic_bias": False,
        "labels": [],
    }
    if not blob:
        return attrs

    piano_artists = ("billy joel", "elton john", "carole king", "bruce hornsby", "ben folds")
    guitar_artists = ("john mayer", "eric clapton", "tom petty", "oasis", "foo fighters")
    jazz_artists = ("miles", "coltrane", "bill evans", "herbie hancock", "jobim", "getz")
    bossa_artists = ("jobim", "gilberto", "bossa")
    rock_artists = ("springsteen", "u2", "foo fighters", "queen", "rolling stones")

    if any(a in blob for a in piano_artists) or "piano" in blob:
        attrs["piano_driven"] = True
        attrs["functional_harmony"] = True
        attrs["narrative_phrasing"] = True
        attrs["labels"].append("piano-driven narrative")
    if any(a in blob for a in guitar_artists) or "guitar" in blob:
        attrs["guitar_driven"] = True
        attrs["labels"].append("guitar-forward")
    if any(a in blob for a in jazz_artists):
        attrs["rich_harmony"] = True
        attrs["labels"].append("jazz-color harmony")
    if any(a in blob for a in bossa_artists):
        attrs["rich_harmony"] = True
        attrs["labels"].append("bossa color")
    if any(a in blob for a in rock_artists):
        attrs["rhythmic_bias"] = True
        attrs["labels"].append("rock drive")
    if "ballad" in blob:
        attrs["ballad_bias"] = True
    return attrs


def energy_tier(energy_label: str, *, bpm: int = 96, flags: dict[str, bool] | None = None) -> str:
    flags = flags or {}
    e = str(energy_label or "").lower()
    if flags.get("ballad") or flags.get("intimate") or "ballad" in e or "slow" in e or "intimate" in e:
        tier = "low"
    elif flags.get("driving") or flags.get("anthem") or "driving" in e or "high energy" in e:
        tier = "high"
    else:
        tier = "medium"
    if bpm and int(bpm) <= 75 and tier == "medium":
        tier = "low"
    elif bpm and int(bpm) >= 140 and tier == "medium":
        tier = "high"
    return tier


def section_goal(section_label: str) -> str:
    label = str(section_label or "Verse")
    return {
        "Intro": "invite",
        "Verse": "story",
        "Pre-Chorus": "build",
        "Chorus": "hook_peak",
        "Bridge": "contrast",
        "Solo": "express",
        "Interlude": "breathe",
        "Outro": "resolve",
        "Breakdown": "groove",
    }.get(label, "support")


def build_song_intent_profile(
    doc: dict[str, Any],
    section: dict[str, Any] | None = None,
    *,
    melody_feel: str = "",
    melody_style: str = "",
    remember: str = "",
    melody_notes: str = "",
    harmony_feeling: str = "",
) -> dict[str, Any]:
    """Single canonical profile consumed by Chords and Melody generators."""
    meta = doc.get("metadata") if isinstance(doc.get("metadata"), dict) else {}
    g = doc.get("global") if isinstance(doc.get("global"), dict) else {}
    wf = doc.get("workflow") if isinstance(doc.get("workflow"), dict) else {}
    origin = doc.get("origin") if isinstance(doc.get("origin"), dict) else {}
    seed = origin.get("seed_payload") if isinstance(origin.get("seed_payload"), dict) else {}

    genre = str(meta.get("style") or seed.get("genre") or "Pop").strip()
    concept = str(meta.get("description") or origin.get("seed_summary") or "").strip()
    mood = str(meta.get("mood") or "").strip()
    energy = str(meta.get("energy") or seed.get("energy") or "").strip()
    references = str(meta.get("references") or seed.get("references") or "").strip()
    jewish_direction = ""
    if genre == "Jewish":
        jewish_direction = str(meta.get("jewish_direction") or seed.get("jewish_direction") or "").strip()
    bpm = int(g.get("bpm") or 96)
    meter = str(g.get("time_signature") or "4/4")
    key_center = str(g.get("original_key_center") or "C")
    key_label = str(g.get("original_key_label") or key_center)

    sec = section if isinstance(section, dict) else {}
    sec_label = str(sec.get("label") or "Verse")
    sec_variant = str(sec.get("label_variant") or sec_label)
    harm = sec.get("harmony") if isinstance(sec.get("harmony"), dict) else {}
    mel_intent: dict[str, Any] = {}
    mel = sec.get("melody") if isinstance(sec.get("melody"), dict) else {}
    if isinstance(mel.get("intent"), dict):
        mel_intent = mel["intent"]

    rem = str(remember or mel_intent.get("remember") or "").strip()
    jot = str(melody_notes or mel_intent.get("hum_notes") or "").strip()
    m_feel = str(melody_feel or mel_intent.get("feel") or "").strip().lower()
    m_style = str(melody_style or mel_intent.get("style") or "simple").strip().lower()
    h_feel = str(harmony_feeling or harm.get("feeling") or "").strip().lower()

    flags = parse_creative_flags(concept, references, jot, rem)
    if jewish_direction == "Ballad":
        flags["ballad"] = True
    ref_attrs = parse_reference_attributes(references)
    if ref_attrs.get("piano_driven"):
        flags["piano"] = True
    if ref_attrs.get("guitar_driven"):
        flags["guitar"] = True
    if ref_attrs.get("ballad_bias"):
        flags["ballad"] = True

    # Song-wide family from genre + Jewish direction (stable across sections).
    song_family = normalize_style_family(
        genre,
        concept=concept,
        references=references,
        notes="",
        jewish_direction=jewish_direction,
    )
    # Section freeform may nudge Jewish songs (e.g. bridge "more traditional/modal").
    if genre == "Jewish" and jot:
        family = normalize_style_family(
            genre,
            concept=concept,
            references=references,
            notes=jot,
            jewish_direction=jewish_direction,
        )
    else:
        family = song_family

    tier = energy_tier(energy, bpm=bpm, flags=flags)
    goal = section_goal(sec_label)

    complexity = {
        "pop": 0.35,
        "rock": 0.4,
        "jazz": 0.85,
        "bossa": 0.75,
        "blues": 0.55,
        "soul": 0.6,
        "folk": 0.3,
        "country": 0.35,
        "electronic": 0.45,
        "classical": 0.5,
        "jewish_pop": 0.4,
        "jewish_israeli": 0.45,
        "jewish_hasidic": 0.5,
        "jewish_klezmer": 0.7,
        "jewish_modal": 0.75,
        "other": 0.4,
    }.get(family, 0.4)
    if flags.get("anthem"):
        complexity = min(1.0, complexity + 0.05)
    if flags.get("intimate") or flags.get("singable"):
        complexity = max(0.2, complexity - 0.1)
    if ref_attrs.get("rich_harmony"):
        complexity = min(1.0, complexity + 0.15)

    extension_bias = (
        0.8
        if family in {"jazz", "bossa", "soul"}
        else (0.55 if family.startswith("jewish_") and family != "jewish_pop" else 0.25)
    )
    chromatic = 0.7 if family in {"jazz", "jewish_klezmer", "jewish_modal"} else (0.45 if family == "rock" else 0.2)
    melodic_density = 0.35 if tier == "low" else (0.75 if tier == "high" else 0.55)
    if flags.get("intimate"):
        melodic_density = max(0.25, melodic_density - 0.15)
    if flags.get("driving") or flags.get("anthem"):
        melodic_density = min(0.9, melodic_density + 0.15)
    syncopation = 0.7 if family in {"bossa", "jazz", "soul", "jewish_hasidic"} else (0.45 if family == "rock" else 0.3)
    hook_repetition = (
        0.75 if family in {"pop", "jewish_pop", "rock"} or flags.get("singable") or flags.get("anthem") else 0.45
    )
    if goal == "hook_peak":
        hook_repetition = min(1.0, hook_repetition + 0.15)
    if goal == "story":
        hook_repetition = max(0.25, hook_repetition - 0.1)

    return {
        "genre": genre,
        "style_family": family,
        "song_style_family": song_family,
        "jewish_direction": jewish_direction if genre == "Jewish" else "",
        "song_concept": concept,
        "mood": mood,
        "energy": energy,
        "energy_tier": tier,
        "references": references,
        "reference_attrs": ref_attrs,
        "flags": flags,
        "bpm": bpm,
        "meter": meter,
        "key_center": key_center,
        "key_label": key_label,
        "progression_style": str(g.get("progression_style") or ""),
        "groove_style": str(g.get("groove_style") or ""),
        "instrumental": bool(wf.get("skip_lyrics")),
        "section_label": sec_label,
        "section_variant": sec_variant,
        "section_goal": goal,
        "harmony_feeling": h_feel,
        "melody_feel": m_feel,
        "melody_style": m_style,
        "listener_memory": rem,
        "melody_notes": jot,
        "harmonic_complexity": round(complexity, 2),
        "extension_bias": round(extension_bias, 2),
        "chromatic_color": round(chromatic, 2),
        "melodic_density": round(melodic_density, 2),
        "syncopation": round(syncopation, 2),
        "hook_repetition": round(hook_repetition, 2),
    }


_STYLE_HARMONY_RECIPES: dict[str, list[dict[str, Any]]] = {
    "pop": [
        {"id": "pop_hook", "name": "Pop hook loop", "ref_key": "C", "chords": ["C", "G", "Am", "F"], "tag": "diatonic_hook", "roles": ["Chorus", "Outro"]},
        {"id": "pop_chorus_lift", "name": "Chorus lift", "ref_key": "C", "chords": ["F", "G", "Am", "C"], "tag": "lift", "roles": ["Chorus", "Pre-Chorus"]},
        {"id": "pop_minor_color", "name": "Emotional vi color", "ref_key": "C", "chords": ["Am", "F", "C", "G"], "tag": "vi_color", "roles": ["Verse", "Bridge"]},
        {"id": "pop_verse_story", "name": "Verse story loop", "ref_key": "C", "chords": ["C", "Am", "F", "G"], "tag": "story", "roles": ["Verse", "Intro"]},
        {"id": "pop_pre_build", "name": "Pre-chorus climb", "ref_key": "C", "chords": ["Am", "Em", "F", "G"], "tag": "build", "roles": ["Pre-Chorus"]},
        {"id": "pop_bridge_turn", "name": "Bridge turn", "ref_key": "C", "chords": ["Em", "Am", "F", "G"], "tag": "contrast", "roles": ["Bridge"]},
    ],
    "rock": [
        {"id": "rock_bvii", "name": "Rock bVII drive", "ref_key": "C", "chords": ["C", "Bb", "F", "C"], "tag": "bVII", "roles": ["Chorus", "Bridge"]},
        {"id": "rock_iv", "name": "I-IV punch", "ref_key": "C", "chords": ["C", "F", "C", "G"], "tag": "iv_drive", "roles": ["Verse", "Chorus"]},
        {"id": "rock_mix", "name": "Modal mixture", "ref_key": "C", "chords": ["C", "Eb", "F", "Bb"], "tag": "mixture", "roles": ["Bridge", "Chorus"]},
        {"id": "rock_verse", "name": "Rock verse grind", "ref_key": "C", "chords": ["C", "G", "F", "C"], "tag": "story", "roles": ["Verse", "Intro"]},
        {"id": "rock_pre", "name": "Rock pre push", "ref_key": "C", "chords": ["F", "G", "Bb", "C"], "tag": "build", "roles": ["Pre-Chorus"]},
    ],
    "jazz": [
        {"id": "jazz_251", "name": "ii-V-I turnaround", "ref_key": "C", "chords": ["Dm7", "G7", "Cmaj7", "A7"], "tag": "ii_v", "roles": ["Chorus", "Outro"]},
        {"id": "jazz_rhythm", "name": "Rhythm changes flavor", "ref_key": "C", "chords": ["Cmaj7", "A7", "Dm7", "G7"], "tag": "secondary_dom", "roles": ["Chorus", "Bridge"]},
        {"id": "jazz_sub", "name": "Tritone color", "ref_key": "C", "chords": ["Dm7", "Db7", "Cmaj7", "Em7"], "tag": "sub_dom", "roles": ["Bridge", "Chorus"]},
        {"id": "jazz_verse", "name": "Jazz verse walk", "ref_key": "C", "chords": ["Cmaj7", "Em7", "Dm7", "G7"], "tag": "story", "roles": ["Verse", "Intro"]},
        {"id": "jazz_pre", "name": "Jazz pre tension", "ref_key": "C", "chords": ["Em7", "A7", "Dm7", "G7"], "tag": "build", "roles": ["Pre-Chorus"]},
        {"id": "jazz_simple", "name": "Clear functional jazz", "ref_key": "C", "chords": ["Cmaj7", "Fmaj7", "Dm7", "G7"], "tag": "functional", "roles": ["Verse", "Chorus"]},
        {"id": "jazz_bridge_only", "name": "Bridge surprise turn", "ref_key": "C", "chords": ["Fmaj7", "F#dim7", "Cmaj7/G", "G7"], "tag": "contrast", "roles": ["Bridge"]},
    ],
    "bossa": [
        {"id": "bossa_maj7", "name": "Bossa maj7 color", "ref_key": "C", "chords": ["Cmaj7", "Am7", "Dm7", "G7"], "tag": "maj7_cycle", "roles": ["Chorus", "Verse"]},
        {"id": "bossa_smooth", "name": "Smooth ii-V color", "ref_key": "C", "chords": ["Fmaj7", "Em7", "A7", "Dm7"], "tag": "ii_v_color", "roles": ["Chorus", "Bridge"]},
        {"id": "bossa_6_9", "name": "6/9 warmth", "ref_key": "C", "chords": ["C6", "Am7", "Dm7", "G9"], "tag": "extensions", "roles": ["Verse", "Chorus"]},
        {"id": "bossa_verse", "name": "Bossa verse sway", "ref_key": "C", "chords": ["Cmaj7", "Dm7", "Em7", "A7"], "tag": "story", "roles": ["Verse", "Intro"]},
        {"id": "bossa_pre", "name": "Bossa pre lift", "ref_key": "C", "chords": ["Dm7", "G7", "Em7", "A7"], "tag": "build", "roles": ["Pre-Chorus"]},
        {"id": "bossa_simple", "name": "Lyrical bossa", "ref_key": "C", "chords": ["Cmaj7", "Fmaj7", "Dm7", "G7"], "tag": "lyrical", "roles": ["Verse", "Outro"]},
    ],
    "blues": [
        {"id": "blues_quick", "name": "Blues move", "ref_key": "C", "chords": ["C7", "F7", "C7", "G7"], "tag": "dom_blues"},
        {"id": "blues_turn", "name": "Blues turnaround", "ref_key": "C", "chords": ["C7", "A7", "Dm7", "G7"], "tag": "blues_turn"},
    ],
    "soul": [
        {"id": "soul_1564", "name": "Soul circle", "ref_key": "C", "chords": ["Cmaj7", "Am7", "Dm7", "G7"], "tag": "soul_circle"},
        {"id": "soul_minor", "name": "Soul minor lift", "ref_key": "Am", "chords": ["Am7", "Dm7", "G7", "Cmaj7"], "tag": "soul_minor"},
    ],
    "jewish_pop": [
        {"id": "jewish_pop_hook", "name": "Contemporary Jewish pop", "ref_key": "C", "chords": ["C", "G", "Am", "F"], "tag": "diatonic_hook", "roles": ["Chorus"]},
        {"id": "jewish_pop_lift", "name": "Singable lift", "ref_key": "C", "chords": ["F", "G", "C", "Am"], "tag": "lift", "roles": ["Chorus", "Pre-Chorus"]},
        {"id": "jewish_pop_verse", "name": "Jewish pop verse", "ref_key": "C", "chords": ["C", "Am", "F", "G"], "tag": "story", "roles": ["Verse", "Intro"]},
        {"id": "jewish_pop_bridge", "name": "Jewish pop bridge", "ref_key": "C", "chords": ["Am", "Em", "F", "G"], "tag": "contrast", "roles": ["Bridge"]},
    ],
    "jewish_israeli": [
        {"id": "israeli_pop", "name": "Israeli pop color", "ref_key": "Am", "chords": ["Am", "G", "F", "E"], "tag": "israeli", "roles": ["Chorus", "Verse"]},
        {"id": "israeli_lift", "name": "Major lift refrain", "ref_key": "C", "chords": ["C", "Em", "F", "G"], "tag": "lift", "roles": ["Chorus"]},
        {"id": "israeli_bridge", "name": "Israeli bridge turn", "ref_key": "Am", "chords": ["Dm", "Am", "E", "Am"], "tag": "contrast", "roles": ["Bridge"]},
    ],
    "jewish_hasidic": [
        {"id": "hasidic_dance", "name": "Dance-oriented loop", "ref_key": "Am", "chords": ["Am", "Dm", "E", "Am"], "tag": "dance", "roles": ["Chorus", "Verse"]},
        {"id": "hasidic_lift", "name": "Major release", "ref_key": "C", "chords": ["C", "G", "Am", "E"], "tag": "release", "roles": ["Chorus"]},
        {"id": "hasidic_bridge", "name": "Hasidic contrast", "ref_key": "Am", "chords": ["Dm", "E", "Am", "G"], "tag": "contrast", "roles": ["Bridge"]},
    ],
    "jewish_klezmer": [
        {"id": "klezmer_freygish", "name": "Freygish / Ahava color", "ref_key": "Am", "chords": ["Am", "Bb", "E", "Am"], "tag": "freygish", "roles": ["Chorus", "Verse"]},
        {"id": "klezmer_moda", "name": "Modal dance turn", "ref_key": "Am", "chords": ["Am", "Dm", "E7", "Am"], "tag": "modal_turn", "roles": ["Chorus", "Bridge"]},
        {"id": "klezmer_bridge", "name": "Klezmer bridge", "ref_key": "Am", "chords": ["Dm", "Bb", "E", "Am"], "tag": "contrast", "roles": ["Bridge"]},
    ],
    "jewish_modal": [
        {"id": "modal_descend", "name": "Modal descent", "ref_key": "Am", "chords": ["Am", "G", "F", "E"], "tag": "modal", "roles": ["Verse", "Chorus"]},
        {"id": "modal_plagal", "name": "Modal plagal color", "ref_key": "Am", "chords": ["Am", "Dm", "Am", "E"], "tag": "plagal_modal", "roles": ["Verse", "Bridge"]},
        {"id": "modal_lift", "name": "Modal lift", "ref_key": "Am", "chords": ["Am", "F", "E", "Am"], "tag": "lift", "roles": ["Chorus"]},
    ],
}


def style_harmony_recipes(style_family: str, *, section_label: str = "") -> list[dict[str, Any]]:
    fam = str(style_family or "pop")
    if fam in _STYLE_HARMONY_RECIPES:
        recipes = list(_STYLE_HARMONY_RECIPES[fam])
    elif fam.startswith("jewish_"):
        recipes = list(_STYLE_HARMONY_RECIPES.get(fam) or _STYLE_HARMONY_RECIPES["jewish_pop"])
    elif fam in {"folk", "country", "classical", "electronic", "other"}:
        recipes = list(_STYLE_HARMONY_RECIPES["pop"])
    else:
        recipes = list(_STYLE_HARMONY_RECIPES.get("pop", []))

    label = str(section_label or "").strip()
    if not label:
        return recipes

    preferred = [r for r in recipes if label in list(r.get("roles") or [])]
    others = [r for r in recipes if r not in preferred]
    # Prefer role-matched recipes, then the rest — keeps song vocabulary, changes emphasis.
    return preferred + others


def _ensure_quality(sym: str, suffix: str) -> str:
    if any(x in sym for x in ("maj7", "m7", "7", "9", "6", "dim", "aug", "sus")):
        return sym
    if sym.endswith("m"):
        if suffix in {"7", "9", "m7"}:
            return f"{sym}7" if not sym.endswith("7") else sym
        return sym
    return sym + suffix


def apply_style_chord_color(symbols: list[str], profile: dict[str, Any], *, variant: int = 0) -> list[str]:
    """Light, variant-aware coloring — tendency, not caricature."""
    fam = str(profile.get("style_family") or "pop")
    out = [str(s) for s in symbols]
    if not out:
        return out
    ext = float(profile.get("extension_bias") or 0)
    goal = str(profile.get("section_goal") or "")
    variant = int(variant) % 3

    # Only color a subset of chords so Jazz/Bossa aren't uniformly "every chord extended".
    if fam in {"jazz", "bossa", "soul"} or ext >= 0.6:
        colored = []
        for i, sym in enumerate(out):
            # Variant 0: lighter (tonic/arrival color only); 1: every other; 2: richer.
            should = (
                (variant == 0 and i in {0, len(out) - 1})
                or (variant == 1 and i % 2 == 1)
                or (variant == 2)
            )
            if not should:
                colored.append(sym)
                continue
            if fam == "bossa":
                # Smooth colorful — maj7 / m7 / occasional 9 color.
                if not sym.endswith("m") and "m7" not in sym:
                    colored.append(_ensure_quality(sym, "maj7" if i % 2 == 0 else "9"))
                else:
                    colored.append(_ensure_quality(sym, "m7"))
            elif not sym.endswith("m"):
                colored.append(_ensure_quality(sym, "maj7" if fam != "blues" else "7"))
            else:
                colored.append(_ensure_quality(sym, "m7"))
        out = colored

    if goal == "build" and len(out) >= 3 and variant != 0:
        if fam in {"jazz", "bossa", "pop", "soul"} and "7" not in out[-2]:
            out[-2] = _ensure_quality(out[-2], "7")
    return out


def expand_harmonic_rhythm(symbols: list[str], profile: dict[str, Any]) -> list[str]:
    """Tempo/energy can change harmonic rhythm (not just playback BPM)."""
    tier = str(profile.get("energy_tier") or "medium")
    bpm = int(profile.get("bpm") or 96)
    goal = str(profile.get("section_goal") or "")
    out = list(symbols)
    if not out:
        return out
    if (tier == "high" or bpm >= 140) and len(out) <= 4:
        mid = out[1:-1] if len(out) > 2 else out
        out = [out[0]] + mid + mid + [out[-1]]
        out = out[:8]
    elif (tier == "low" or bpm <= 75) and len(out) >= 4 and goal in {"story", "invite", "resolve"}:
        out = [out[0], out[len(out) // 3], out[(2 * len(out)) // 3], out[-1]]
    if goal == "build" and len(out) >= 3:
        out = out + [out[-1]]
    return out


def apply_feeling_chord_bias(
    symbols: list[str],
    profile: dict[str, Any],
    *,
    feeling: str = "",
    variant: int = 0,
) -> list[str]:
    """Materially reshape a progression from harmony feeling — still style-aware.

    Feeling modifies the style vocabulary; it does not replace the style family.
    """
    out = [str(s) for s in symbols if str(s).strip()]
    if not out:
        return out
    feel = str(feeling or profile.get("harmony_feeling") or "").strip().lower()
    fam = str(profile.get("style_family") or "pop")
    variant = int(variant) % 3
    key = str(profile.get("key_center") or "C")

    def _to_minor(sym: str) -> str:
        if sym.endswith("m") or "m7" in sym or "min" in sym.lower():
            return sym
        if any(x in sym for x in ("maj7", "7", "9", "6")):
            root = sym.split("maj")[0].split("7")[0].split("9")[0].split("6")[0]
            return root + "m7" if fam in {"jazz", "bossa", "soul"} else root + "m"
        return sym + "m"

    def _add_dom(sym: str) -> str:
        if "7" in sym and "maj7" not in sym:
            return sym
        if sym.endswith("m") and "m7" not in sym:
            return sym + "7"
        if "maj7" in sym:
            return sym.replace("maj7", "7")
        return _ensure_quality(sym, "7")

    def _root_only(sym: str) -> str:
        s = str(sym or "")
        for tok in ("maj7", "m7b5", "m7", "sus4", "sus", "dim7", "dim", "aug", "9", "7", "6"):
            s = s.replace(tok, "")
        return s or sym

    def _force_maj7(sym: str) -> str:
        root = _root_only(sym)
        if root.endswith("m"):
            root = root[:-1]
        return root + "maj7"

    def _force_sus(sym: str) -> str:
        return _root_only(sym).rstrip("m") + "sus4"

    if feel in {"uplifting", "energetic"}:
        # Brighter arrival / rising energy — major color and clearer V→I pressure.
        if len(out) >= 1 and not out[-1].endswith("m") and "dim" not in out[-1]:
            out[-1] = _force_maj7(out[-1]) if fam in {"jazz", "bossa", "soul"} else _root_only(out[-1]).rstrip("m")
        if len(out) >= 2:
            # Brighten a mid/penultimate minor into major lift when style allows.
            if out[0].endswith("m") or "m7" in out[0]:
                root = _root_only(out[0]).rstrip("m")
                out[0] = root + ("maj7" if fam in {"jazz", "bossa", "soul"} else "")
            out[-2] = _add_dom(_root_only(out[-2]).rstrip("m") if fam in {"pop", "rock", "folk"} else out[-2])
        if variant >= 1 and len(out) >= 3:
            out[1] = _force_maj7(out[1]) if fam in {"jazz", "bossa"} else _root_only(out[1]).rstrip("m")
    elif feel in {"tense"}:
        # Dominant pressure / unresolved motion.
        mid = max(1, len(out) // 2)
        out[mid] = _add_dom(out[mid])
        if len(out) >= 3:
            # Secondary-dominant / unresolved cadence color.
            if fam in {"jazz", "bossa"}:
                out[-2] = _add_dom(_root_only(out[-2]).rstrip("m"))  # force V7-ish approach
                if "sus" not in out[-1]:
                    out[-1] = _add_dom(out[-1]) if "maj7" not in out[-1] else out[-1].replace("maj7", "7")
            else:
                out[-1] = _force_sus(out[-1])
        elif len(out) >= 2 and fam in {"pop", "rock"}:
            out[-1] = _force_sus(out[-1])
    elif feel in {"melancholy", "reflective"}:
        # Minor / softer color.
        if variant == 0:
            out[0] = _to_minor(out[0])
        elif variant == 1 and len(out) >= 3:
            out[1] = _to_minor(out[1])
        else:
            out[min(2, len(out) - 1)] = _to_minor(out[min(2, len(out) - 1)])
        if fam in {"jazz", "bossa", "soul"} and variant == 2:
            out[-1] = _ensure_quality(_to_minor(out[-1]).replace("m7", "m"), "m7")
        # Soften a bright final into minor color on variant 0.
        if variant == 0 and ("maj7" in out[-1] or (not out[-1].endswith("m") and "7" in out[-1])):
            out[-1] = _to_minor(out[-1])
        elif variant == 0 and not out[-1].endswith("m") and "7" not in out[-1]:
            out[-1] = _to_minor(out[-1])
    elif feel in {"stable"}:
        # Clearer tonic grounding — strip some chromatic extras on variant 0.
        if variant == 0:
            cleaned = []
            for sym in out:
                if "dim" in sym or "sus" in sym:
                    cleaned.append(sym.replace("sus4", "").replace("dim7", "m").replace("dim", "m") or sym)
                else:
                    cleaned.append(sym)
            out = cleaned
        # Prefer landing on tonic-like last chord without alteration.
        if out and "b" in out[-1][1:2] and fam == "rock":
            pass  # keep rock color
    _ = key
    return out


def describe_harmony_from_events(
    entries: list[dict[str, Any]] | list[str],
    *,
    profile: dict[str, Any] | None = None,
) -> str:
    """Musician-readable description derived from the actual chord symbols."""
    symbols: list[str] = []
    for item in entries or []:
        if isinstance(item, dict):
            sym = str(item.get("chord") or "").strip()
        else:
            sym = str(item or "").strip()
        if sym:
            symbols.append(sym)
    if not symbols:
        return "No chords to describe yet."

    parts: list[str] = [f"Moves {' → '.join(symbols)}"]
    has_dom = any(s.endswith("7") and "maj7" not in s and "m7" not in s for s in symbols)
    has_7 = any(("7" in s or "9" in s or "6" in s) for s in symbols)
    has_bvii = any(s.startswith(("Bb", "Ab", "Eb")) for s in symbols)
    ii_v = False
    for i in range(len(symbols) - 1):
        a, b = symbols[i], symbols[i + 1]
        if ("m7" in a or (a.endswith("m") and "maj" not in a)) and (
            b.endswith("7") and "maj7" not in b and "m7" not in b
        ):
            ii_v = True
            break
    if ii_v:
        parts.append("includes ii–V motion")
    if has_dom and not ii_v:
        parts.append("uses dominant seventh color")
    if has_7 and not has_dom:
        parts.append("leans on seventh / extended color")
    if has_bvii:
        parts.append("brings in bVII rock/modal color")
    if len(set(symbols)) < len(symbols):
        parts.append("repeats a short harmonic cell")
    if profile:
        fam = str(profile.get("style_family") or "")
        goal = str(profile.get("section_goal") or "")
        if fam:
            parts.append(f"shaped for a {fam.replace('_', ' ')} feel")
        if goal == "hook_peak":
            parts.append("aimed at a chorus-style arrival")
        elif goal == "build":
            parts.append("builds pressure toward the next section")
        elif goal == "contrast":
            parts.append("opens a contrasting bridge color")
    text = parts[0]
    for p in parts[1:]:
        text = f"{text}; {p}"
    return text[0].upper() + text[1:] + "."


def style_melody_bias(profile: dict[str, Any]) -> dict[str, Any]:
    """Compact melody shaping bias derived from the song profile."""
    fam = str(profile.get("style_family") or "pop")
    return {
        "prefer_chord_tones": fam in {"jazz", "bossa", "soul", "jewish_klezmer", "jewish_modal"},
        "prefer_extensions": float(profile.get("extension_bias") or 0) >= 0.55,
        "syncopate": float(profile.get("syncopation") or 0) >= 0.5,
        "repeat_hook": float(profile.get("hook_repetition") or 0) >= 0.65,
        "density": float(profile.get("melodic_density") or 0.5),
        "wider_leaps": fam in {"rock", "jazz"} or str(profile.get("section_goal")) == "hook_peak",
        "smooth_contour": fam in {"bossa", "pop", "jewish_pop"}
        or bool((profile.get("flags") or {}).get("intimate")),
        "modal_flavor": fam in {"jewish_klezmer", "jewish_modal", "jewish_hasidic"},
    }
