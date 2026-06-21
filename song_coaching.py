"""Concise song-specific coaching — curated first, lightweight fallback."""

from __future__ import annotations

import re
from typing import Any

CoachingBlock = dict[str, str]

_INSTRUMENT_ALIASES = {
    "piano": "piano",
    "keyboard": "piano",
    "keys": "piano",
    "guitar": "guitar",
    "bass": "bass",
    "voice": "voice",
    "vocal": "voice",
    "singer": "voice",
    "saxophone": "saxophone",
    "sax": "saxophone",
    "trumpet": "trumpet",
    "flute": "flute",
}


def _norm_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(title or "").lower())


def _instrument_key(instrument: str) -> str:
    low = str(instrument or "").strip().lower()
    for needle, key in _INSTRUMENT_ALIASES.items():
        if needle in low:
            return key
    return "general"


def _pick_tip(tips: dict[str, str], instrument: str) -> str:
    key = _instrument_key(instrument)
    return tips.get(key) or tips.get("general") or ""


# Curated coaching — expand over time.
CURATED_COACHING: dict[str, CoachingBlock] = {
    "perfect": {
        "what_matters": "Let the loop breathe — the song lives on feel and space, not flashy fills.",
        "biggest_challenge": "Rushing the downbeats; the vocal needs room between phrases.",
        "instrument_tips": {
            "piano": "Keep the left hand simple (root–5th or root–octave) and let ring sustain carry the emotion.",
            "guitar": "Fingerpick the pattern lightly; accent beats 2 and 4, not every thumb stroke.",
            "voice": "Sing slightly behind the beat on verses; open up on the chorus without pushing volume.",
            "general": "Less notes, more sustain — the arrangement is already full.",
        },
        "practice_next": "Loop Verse → Pre-Chorus → Chorus at 70% tempo until transitions feel effortless.",
        "performance_next": "Start softer than you think; build one dynamic step per chorus, not all at once.",
        "primary_scale": "G major pentatonic",
        "improv_approach": "For fills, use G major pentatonic and land on chord tones at section changes.",
    },
    "shallow": {
        "what_matters": "The duet feel — conversational phrasing matters more than perfect pitch bends.",
        "biggest_challenge": "Over-singing the chorus; the lyric needs intimacy before power.",
        "instrument_tips": {
            "piano": "Arpeggiate the progression; keep the top voice singing the lyric rhythm in your RH.",
            "guitar": "Strum lightly or pick the bass note on 1; leave space for the vocal.",
            "voice": "Treat verses like speech — short breaths, consonants soft, vowels forward.",
            "general": "Match the ballad pulse; don't let tempo creep upward when energy rises.",
        },
        "practice_next": "Practice chorus entry alone: last line of pre-chorus → first chorus lyric in one breath.",
        "performance_next": "Pick one moment to go full voice; everything else stays conversational.",
        "primary_scale": "G major (song key)",
        "improv_approach": "Use G major pentatonic in verses; outline chord 3rds over the chorus lift.",
    },
    "hotelcalifornia": {
        "what_matters": "The laid-back 12/8 (or compound) feel — the groove IS the song.",
        "biggest_challenge": "Playing the iconic progression too busy; the hypnotic repeat is the point.",
        "instrument_tips": {
            "piano": "Roll LH bass on beats 1 and 4; RH comp sparse — think two notes per bar max.",
            "guitar": "Practice the arpeggio pattern without vocals until thumb independence is automatic.",
            "bass": "Anchor the root on 1; leave space on 2–3 for the kick to breathe.",
            "general": "Lock tempo with a metronome on the dotted-quarter pulse, not eighth notes.",
        },
        "practice_next": "Play the main progression 8× with metronome — no solos, no fills, just groove.",
        "performance_next": "Hold back on verses; save melodic interest for the solo section or final chorus.",
        "primary_scale": "B minor pentatonic",
        "improv_approach": "For soloing, B minor pentatonic with occasional major 3rd on the Bm chord.",
    },
    "allofme": {
        "what_matters": "Jazz-pop turnaround clarity — the ii–V–I motion in the A section defines the song.",
        "biggest_challenge": "Rushing the turnaround; each chord needs a full beat of weight.",
        "instrument_tips": {
            "piano": "Shell voicings in LH (root + 7th); add 3rd in RH on beats 2 and 4.",
            "guitar": "Use shell grips or three-note voicings — avoid full barre strums every beat.",
            "voice": "Scat the root motion on 'la' before adding lyrics — feel the cycle first.",
        },
        "practice_next": "Loop the A-section turnaround 4× slowly, naming roots out loud.",
        "performance_next": "Keep verse dynamics medium-soft; let the bridge lift feel earned.",
        "primary_scale": "Ab major",
        "improv_approach": "Ab major pentatonic on I sections; target 3rds through the ii–V–I turns.",
    },
    "californication": {
        "what_matters": "Muted, funky verse groove vs open chorus — the contrast carries the song.",
        "biggest_challenge": "Letting the chorus strum get heavier than the vocal can sit on top of.",
        "instrument_tips": {
            "guitar": "Verse: palm-muted eighths; Chorus: open chords on the downbeat only.",
            "bass": "Verse: root-fifth octaves; Chorus: lock with kick on 1 and 3.",
            "voice": "Stay intimate on verses — the lyric is narrative, not arena belting.",
        },
        "practice_next": "Practice verse groove 8 bars, then switch articulation (not tempo) for chorus.",
        "performance_next": "One clean dynamic jump at the first chorus — avoid gradual creep.",
        "primary_scale": "A minor pentatonic",
        "improv_approach": "A minor pentatonic for fills; add C major pentatonic color on the chorus lift.",
    },
    "lovestory": {
        "what_matters": "Fairytale lift in the chorus — the melody arc is the emotional payoff.",
        "biggest_challenge": "Tension in the voice before the chorus; don't peak too early in verses.",
        "instrument_tips": {
            "piano": "Broken chords in verse; fuller block chords only when the melody jumps.",
            "guitar": "Capo-friendly open shapes — keep strum pattern constant, change intensity not pattern.",
            "voice": "Light chest in verse; mix into head voice on the highest chorus notes.",
        },
        "practice_next": "Map one breath plan for the chorus hook — mark where you inhale.",
        "performance_next": "Hold the final chorus note with support, not volume.",
        "primary_scale": "D major",
        "improv_approach": "D major pentatonic for any fills; stay diatonic unless the chart adds color chords.",
    },
    "youvegotafriendinme": {
        "what_matters": "Bouncy, friendly swing — the song should feel like a conversation with a friend.",
        "biggest_challenge": "Making it too stiff; the lilt on offbeats sells the Pixar charm.",
        "instrument_tips": {
            "piano": "Light staccato LH; bounce RH chords on beats 2 and 4.",
            "guitar": "Alternate bass–strum pattern; keep it light and singalong-ready.",
            "voice": "Smile while singing — it changes vowel shape and fixes a 'flat' delivery.",
        },
        "practice_next": "Clap the groove while speaking the verse lyric in rhythm.",
        "performance_next": "Invite the audience in — softer is fine; clarity beats power.",
        "primary_scale": "C major",
        "improv_approach": "C major pentatonic for any short fills between phrases.",
    },
    "turnthelightsbackon": {
        "what_matters": "Emotional build — the song earns its climax through patience in early sections.",
        "biggest_challenge": "Showing all your emotion in verse one; save arc for the bridge and final chorus.",
        "instrument_tips": {
            "piano": "Start with sparse LH; add inner voices only after the first chorus.",
            "guitar": "Fingerpick verses; switch to gentle strum when drums would enter.",
            "voice": "Under-sing the opening; let the lyric story carry before adding weight.",
        },
        "practice_next": "Mark three dynamic levels (soft / medium / full) on your chart before playing.",
        "performance_next": "Plan one still moment before the final chorus — silence sells the return.",
        "primary_scale": "Song key major pentatonic",
        "improv_approach": "Use major pentatonic in the song key; target chord 3rds when harmony shifts.",
    },
    "say": {
        "what_matters": "The R&B pocket — laid-back 16th feel with vocal runs on top, not competing with it.",
        "biggest_challenge": "Over-playing fills that step on the vocal melisma.",
        "instrument_tips": {
            "piano": "Syncopated comping — hit chords on the 'and' of 2 and 4, not every downbeat.",
            "guitar": "Clean muted chops in verse; chord stabs in chorus.",
            "voice": "Practice runs slowly with a metronome — rhythm first, speed second.",
        },
        "practice_next": "Loop the main groove at 80% tempo with minimal voicings.",
        "performance_next": "Leave holes for ad-libs; the band supports, doesn't compete.",
        "primary_scale": "Minor pentatonic in song key",
        "improv_approach": "Minor pentatonic for verse feel; outline chord tones when harmony changes.",
    },
}


def lookup_curated(title: str) -> CoachingBlock | None:
    raw = CURATED_COACHING.get(_norm_title(title))
    if not raw:
        return None
    return dict(raw)


def _extract_key_root(label: str) -> str | None:
    m = re.match(r"^([A-G](?:#|b)?)", str(label or "").strip())
    return m.group(1) if m else None


def _infer_scale_kind(primary_scale: str, catalog_key: str) -> str:
    """Return 'minor', 'major', or 'major_pentatonic'."""
    low = str(primary_scale or "").lower()
    if "minor" in low:
        return "minor"
    if "pentatonic" in low:
        return "major_pentatonic"
    if "major" in low:
        return "major"
    ck = str(catalog_key or "C")
    if ck.lower().endswith("m") and len(ck) > 1:
        return "minor"
    return "major_pentatonic"


def _primary_scale_for_practice_key(practice_key: str, kind: str) -> str:
    pk = str(practice_key or "C").strip() or "C"
    if kind == "minor":
        return f"{pk} minor pentatonic"
    if kind == "major":
        return f"{pk} major"
    return f"{pk} major pentatonic"


def _remap_improv_key_text(text: str, old_root: str | None, practice_key: str) -> str:
    """Swap catalog-root scale mentions for the practice/chart key."""
    improv = str(text or "").strip()
    pk = str(practice_key or "C").strip() or "C"
    if not improv:
        return improv
    low = improv.lower()
    if "song key" in low:
        out = re.sub(r"\bthe song key\b", pk, improv, flags=re.I)
        out = re.sub(r"\bsong key\b", pk, out, flags=re.I)
        return out
    if not old_root or old_root == pk:
        return improv
    replacements = (
        (rf"\b{re.escape(old_root)}\s+major\s+pentatonic", f"{pk} major pentatonic"),
        (rf"\b{re.escape(old_root)}\s+minor\s+pentatonic", f"{pk} minor pentatonic"),
        (rf"\b{re.escape(old_root)}\s+major\b", f"{pk} major"),
        (rf"\b{re.escape(old_root)}\b", pk),
    )
    out = improv
    for pattern, repl in replacements:
        out = re.sub(pattern, repl, out, flags=re.I)
    return out


def _apply_practice_key_to_block(
    block: CoachingBlock,
    *,
    practice_key: str,
    catalog_key: str,
) -> CoachingBlock:
    """Rewrite scale/improv coaching to match the chart key the player reads."""
    pk = str(practice_key or "").strip()
    if not pk:
        return block
    catalog = str(catalog_key or "C").strip() or "C"
    out = dict(block)
    primary_raw = str(block.get("primary_scale") or "")
    improv_raw = str(block.get("improv_approach") or "")
    kind = _infer_scale_kind(primary_raw, catalog)
    out["primary_scale"] = _primary_scale_for_practice_key(pk, kind)
    old_root = _extract_key_root(primary_raw) or _extract_key_root(catalog)
    if improv_raw:
        out["improv_approach"] = _remap_improv_key_text(improv_raw, old_root, pk)
    else:
        out["improv_approach"] = (
            f"Use {out['primary_scale']}; target chord tones when harmony shifts."
        )
    what = str(out.get("what_matters") or "")
    if catalog != pk and catalog in what:
        out["what_matters"] = what.replace(f"**{catalog}**", f"**{pk}**", 1).replace(
            catalog, pk, 1
        )
    elif pk and "feel in" in what.lower():
        out["what_matters"] = re.sub(
            r"(feel in\s+\*\*)([^*]+)(\*\*)",
            rf"\g<1>{pk}\3",
            what,
            count=1,
            flags=re.I,
        )
    return out


def _fallback_coaching(
    record: dict[str, Any],
    sections: dict[str, list[str]],
    *,
    instrument: str = "",
    level: str = "Intermediate",
    practice_key: str | None = None,
) -> CoachingBlock:
    title = str(record.get("title") or "this song")
    genre = str(record.get("genre") or "Pop")
    key = str(practice_key or record.get("key") or "C")
    ext = record.get("extensions") or {}
    groove = str(ext.get("default_groove") or genre)
    section_names = [str(s) for s in (sections or {}).keys() if str(s).strip()]
    has_chorus = any("chorus" in s.lower() for s in section_names)
    chords_flat = [str(c).strip() for chs in sections.values() for c in (chs or []) if str(c).strip()]
    has_slash = any("/" in c for c in chords_flat)

    what = f"Lock the {groove.lower()} feel in **{key}** — that's what makes **{title}** sound like itself."
    if has_chorus:
        challenge = "Rushing into the chorus before the verse has settled."
    elif has_slash:
        challenge = "Losing the bass line on slash-chord changes."
    else:
        challenge = "Clean section transitions without tempo creep."

    tips = {
        "piano": "LH steady on roots; RH stays out of the vocal's way.",
        "guitar": "Keep the strum/pick pattern steady — change intensity before changing pattern.",
        "voice": "Speak the lyric in rhythm before singing; mark breath spots.",
        "general": f"Match the {genre} feel before adding your own interpretation.",
    }
    practice = (
        f"Loop one hard section 4× with metronome at **{level}** tempo."
        if level != "Advanced"
        else "Record one pass, then fix one timing and one tone issue."
    )
    perf = "Plan one dynamic contrast (soft verse → fuller chorus) and stick to it."
    pent = f"{key} major pentatonic" if "m" not in key.lower() else f"{key} minor pentatonic"
    improv = f"Start with {pent}; target chord tones when the harmony changes."

    return {
        "what_matters": what,
        "biggest_challenge": challenge,
        "instrument_tips": tips,
        "practice_next": practice,
        "performance_next": perf,
        "primary_scale": pent,
        "improv_approach": improv,
    }


def build_song_coaching(
    record: dict[str, Any],
    sections: dict[str, list[str]] | None = None,
    *,
    instrument: str = "",
    level: str = "Intermediate",
    practice_key: str | None = None,
) -> CoachingBlock:
    """Return a coaching block with instrument tip resolved."""
    sections = sections or {}
    catalog_key = str(record.get("key") or "C")
    block = lookup_curated(str(record.get("title") or "")) or _fallback_coaching(
        record,
        sections,
        instrument=instrument,
        level=level,
        practice_key=practice_key,
    )
    if practice_key:
        block = _apply_practice_key_to_block(
            block,
            practice_key=practice_key,
            catalog_key=catalog_key,
        )
    tips = block.get("instrument_tips")
    if isinstance(tips, dict):
        block = dict(block)
        block["instrument_tip"] = _pick_tip(tips, instrument)
    else:
        block = dict(block)
        block["instrument_tip"] = str(tips or "")
    return block


def coaching_practice_focus(block: CoachingBlock) -> str:
    """One-line focus for the Active Song card."""
    what = str(block.get("what_matters") or "").strip()
    if len(what) > 120:
        what = what[:117] + "…"
    return what or "Song-specific feel and clean section transitions"


def coaching_markdown(block: CoachingBlock) -> str:
    """Five-part coaching section for Practice page."""
    tip = str(block.get("instrument_tip") or "").strip()
    scale = str(block.get("primary_scale") or "").strip()
    improv = str(block.get("improv_approach") or "").strip()
    lines = [
        "#### Song coach",
        f"**What matters most** — {block.get('what_matters', '—')}",
        f"**Biggest challenge** — {block.get('biggest_challenge', '—')}",
        f"**Instrument tip** — {tip or '—'}",
        f"**Practice next** — {block.get('practice_next', '—')}",
        f"**Performance next** — {block.get('performance_next', '—')}",
    ]
    if scale or improv:
        parts = [p for p in (scale, improv) if p]
        lines.append(f"**Improv (1–2 ideas)** — {' '.join(parts[:2])}")
    return "\n\n".join(lines)


def coaching_scale_summary(block: CoachingBlock) -> str:
    """Cap scale advice to 1–2 ideas for the Scales expander."""
    scale = str(block.get("primary_scale") or "").strip()
    improv = str(block.get("improv_approach") or "").strip()
    if scale and improv:
        return f"**Song improv:** {improv} (start with **{scale}**)."
    if improv:
        return f"**Song improv:** {improv}"
    if scale:
        return f"**Song scale:** {scale}"
    return ""
