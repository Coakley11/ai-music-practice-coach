"""Practice coach overlay text for chord sections (no Streamlit UI)."""

from __future__ import annotations

import html
import re

__all__ = ["section_overlay_html"]


def _chart_section_role(section_name):
    name = str(section_name or "").lower()
    if "chorus" in name and "pre" not in name:
        return "chorus"
    if "pre" in name:
        return "pre"
    if "verse" in name or "main loop" in name:
        return "verse"
    if "bridge" in name:
        return "bridge"
    if "solo" in name:
        return "solo"
    if "intro" in name or "outro" in name or "ending" in name:
        return "gray"
    return "neutral"


def _chart_feel_label(style):
    return {
        "Pop groove": "Pop 8th-note feel",
        "Rock groove": "Rock 8th-note feel",
        "Jazz swing": "Swing feel",
        "Bossa nova": "Bossa feel",
        "Funk groove": "Funk syncopation",
        "Ballad": "Ballad feel",
        "Jewish groove": "Hora / klezmer dance feel",
    }.get(style or "Pop groove", style or "Pop groove")


def _backing_chord_color_tip(chords, instrument):
    family = _instrument_family(instrument) if "_instrument_family" in globals() else "general"
    for chord in chords:
        low = str(chord).lower()
        safe = html.escape(str(chord))
        if "add9" in low:
            return f"{safe} has an open add9 color; keep the 9th audible instead of burying it in a thick attack."
        if "maj7" in low:
            if family == "piano":
                return f"{safe} wants a lighter touch; voice the maj7 inside and let the top extension sing."
            if family == "guitar":
                return f"{safe} sounds best as a smaller grip; let the maj7 color ring instead of using a heavy full barre."
            return f"{safe} is a soft color chord; phrase into it gently and avoid over-accenting the 7th."
        if "sus" in low:
            return f"{safe} delays resolution; lean into the suspension, then release cleanly into the next bar."
        if "/" in str(chord):
            return f"{safe} is about bass motion; respect the written bass note when practicing the section."
        if "dim" in low or "m7b5" in low:
            return f"{safe} is passing tension; keep the line moving and resolve it clearly."
        if "7#9" in low or "7b9" in low or "13" in low:
            return f"{safe} adds dominant bite; make the tension rhythmic, then relax into the resolution."
    return ""


def section_overlay_html(
    instrument,
    focus,
    chords,
    section_name="",
    groove_style="",
    time_signature="4/4",
    bpm=100,
    level="Intermediate",
    song_title="",
    song_artist="",
):
    try:
        from musician_coaching import section_coaching_html

        plain = section_coaching_html(
            section_name=section_name or "",
            instrument=instrument or "",
            level=level or "Intermediate",
            groove_style=groove_style or "Pop groove",
            bpm=int(bpm or 100),
            chords=list(chords or []),
            focus=focus or "",
            title=song_title or "",
            artist=song_artist or "",
        )
        color_tip = _backing_chord_color_tip(chords, instrument)
        if color_tip:
            color_tip = _plain_color_tip(color_tip)
        return f"{plain} {color_tip}" if color_tip else plain
    except Exception:
        pass
    first = chords[0] if chords else "the first chord"
    second = chords[1] if len(chords) > 1 else first
    family = _instrument_family(instrument) if "_instrument_family" in globals() else "general"
    role = _chart_section_role(section_name)
    feel = _chart_feel_label(groove_style)
    color_tip = _backing_chord_color_tip(chords, instrument)
    focus_area = _focus_area(focus) if "_focus_area" in globals() else ""
    role_action = {
        "verse": "keep the part sparse and leave air around the melody",
        "pre": "increase motion so the chorus feels pulled forward",
        "chorus": "widen the register and make the downbeats more confident",
        "bridge": "change texture or register so the listener hears a new color",
        "solo": "answer the groove with short phrases, not constant notes",
        "gray": "set up or release the form without overcrowding it",
    }.get(role, "make the section function clear")
    if focus_area == "Rhythm":
        rhythm = _rhythm_guidance(
            instrument,
            section_name=section_name,
            groove_style=groove_style,
            time_signature=time_signature,
            bpm=bpm,
        )
        return rhythm["overlay"]
    if focus_area == "Dynamics":
        return _dynamics_guidance(instrument, section_name, first, second)["overlay"]

    if family == "guitar":
        if focus == "Melody":
            base = f"Lead: target chord tones from <strong>{html.escape(str(first))}</strong>, then slide/bend into <strong>{html.escape(str(second))}</strong>; {role_action}."
        else:
            base = f"Guitar: in this {feel}, use muted strokes in setup sections and open strums for lift; keep compact voicings for <strong>{html.escape(str(first))} to {html.escape(str(second))}</strong>."
    if family == "piano":
        base = f"Piano: left hand roots/fifths, right hand shells or spread voicings; connect <strong>{html.escape(str(first))} to {html.escape(str(second))}</strong> by nearest motion and {role_action}."
    elif family == "bass":
        base = f"Bass: lock to the kick, root on beat 1, fifth or octave on beat 3, then approach <strong>{html.escape(str(second))}</strong> chromatically when the section builds."
    elif family == "winds":
        base = f"{html.escape(str(instrument))}: breathe before the phrase, answer the melody sparingly, and target the 3rd/7th over <strong>{html.escape(str(first))}</strong>."
    elif family == "voice":
        base = f"Voice: place breath before bar 1, keep vowels focused through <strong>{html.escape(str(first))}</strong>, and save the strongest dynamic for chorus/hook arrivals."
    elif family != "guitar":
        base = f"Lock the first change <strong>{html.escape(str(first))} to {html.escape(str(second))}</strong> to the {feel} before adding fills."
    return f"{base} {color_tip}" if color_tip else base


def _plain_color_tip(color_tip: str) -> str:
    """Soften chord-jargon color tips for the default chart overlay."""
    t = str(color_tip or "")
    t = re.sub(r"<[^>]+>", "", t)
    low = t.lower()
    if "sus" in low and "delays" in low:
        return (
            "Hold the suspended chord for a moment to build tension, "
            "then let it resolve smoothly into the next chord."
        )
    if "maj7" in low:
        return "Use a lighter touch on the richer chords so they ring clearly."
    if "bass motion" in low or "slash" in low:
        return "Follow the lowest note of the chord when you change — it guides the progression."
    if "add9" in low:
        return "Let the top notes of the chord sing — avoid a heavy attack."
    return t[:200] if len(t) > 200 else t


def _instrument_family(instrument):
    if instrument in ["Saxophone", "Flute", "Trumpet", "Clarinet"]:
        return "winds"
    if instrument == "Voice":
        return "voice"
    if instrument == "Guitar":
        return "guitar"
    if instrument == "Piano":
        return "piano"
    if instrument == "Bass":
        return "bass"
    return "general"

def _focus_area(focus):
    text = str(focus or "").lower()
    if any(token in text for token in ["dynamic", "crescendo", "decrescendo", "loud", "soft", "intensity", "touch"]):
        return "Dynamics"
    if any(token in text for token in ["strum", "rhythm", "comp", "groove", "pocket", "syncopation", "left-hand", "left hand"]):
        return "Rhythm"
    if any(token in text for token in ["voicing", "voice leading", "inversion", "reharm", "harmony", "triad", "barre", "transition", "root motion"]):
        return "Harmony"
    if any(token in text for token in ["lead", "melody", "double stop", "phrasing", "articulation", "tone", "breath", "vibrato", "range", "endurance"]):
        return "Melody"
    if any(token in text for token in ["solo", "improv", "walking", "bebop", "scales", "guide tone"]):
        return "Improvisation"
    if "ear" in text or "pitch accuracy" in text:
        return "Ear Training"
    return "Technique"

def _section_role(section_name):
    name = str(section_name or "").lower()
    if "chorus" in name and "pre" not in name:
        return "chorus"
    if "verse" in name or "main loop" in name:
        return "verse"
    if "pre" in name:
        return "pre"
    if "bridge" in name:
        return "bridge"
    if "intro" in name:
        return "intro"
    if "outro" in name or "ending" in name:
        return "outro"
    if "solo" in name:
        return "solo"
    return "neutral"

def _section_dynamic_shape(section_name):
    role = _section_role(section_name)
    if role == "chorus":
        return "build into a stronger, more projected chorus sound without rushing"
    if role == "verse":
        return "stay softer and more restrained so the lyric/melody can lead"
    if role == "bridge":
        return "create contrast: either pull back dramatically or swell into the return"
    if role == "intro":
        return "start controlled and leave headroom for the first main section"
    if role == "outro":
        return "release intensity gradually while keeping time steady"
    if role == "pre":
        return "crescendo through the section so the next arrival feels earned"
    return "shape the phrase with a clear beginning, lift, and release"


def _rhythm_profile(time_signature="4/4", groove_style="", section_name="", bpm=100):
    text = f"{time_signature} {groove_style} {section_name}".lower()
    role = _section_role(section_name)
    if "6/8" in text:
        profile = {
            "feel": "6/8 pulse",
            "count": "Count `1-2-3 4-5-6`; feel two big beats per bar.",
            "accent": "Accent beat 1 and beat 4; keep the inner eighths flowing.",
            "guitar": "`D - U D - U` or arpeggiate bass-treble-treble twice per bar.",
            "piano": "Left hand lands on 1 and 4; right hand rolls broken chords across the six eighths with light pedal.",
            "bass": "Place roots on 1 and 4, then add a pickup into the next bar only after the pulse is steady.",
            "winds": "Phrase in two groups of three; breathe before beat 1 and avoid clipping beat 4.",
            "voice": "Speak the lyric in two large pulses, then sing with breath support through beat 4.",
        }
    elif "bossa" in text:
        profile = {
            "feel": "bossa syncopation",
            "count": "Count straight eighths but keep the accent light and off the heavy downbeat.",
            "accent": "Let syncopated upbeats answer the bass; do not over-accent every beat.",
            "guitar": "Use a soft bass note on 1/3 with upper-string upbeats: `Bass - up - up | Bass - up - up`.",
            "piano": "Left hand plays a light root/fifth pulse; right hand comps short offbeat shells with minimal pedal.",
            "bass": "Keep a gentle root-fifth pulse and make note length even.",
            "winds": "Use airy, connected phrases with light articulation on syncopated answers.",
            "voice": "Keep consonants light and float over the syncopation rather than punching it.",
        }
    elif "swing" in text or "shuffle" in text:
        profile = {
            "feel": "swing/shuffle feel",
            "count": "Count triplet-based eighths: `1-trip-let 2-trip-let`; long-short, not straight.",
            "accent": "Lean into 2 and 4, with relaxed offbeats.",
            "guitar": "Use a light shuffle: `D - dU D - dU`, muting lightly on 2 and 4.",
            "piano": "Comp short shells behind the beat; left hand can walk or play sparse roots.",
            "bass": "Walk quarter notes with clean approach tones into chord changes.",
            "winds": "Tongue lightly on offbeats and place guide tones on strong beats.",
            "voice": "Let the phrase sit behind the beat; avoid straightening the swing.",
        }
    elif "funk" in text:
        profile = {
            "feel": "funk syncopation",
            "count": "Count sixteenths: `1 e & a 2 e & a`; keep the hand moving constantly.",
            "accent": "Strong pocket on 1, crisp muted ghosts, and tight 2/4 backbeat awareness.",
            "guitar": "`x x U x | x U x U` muted sixteenths first, then open only the target accents.",
            "piano": "Use short stabs on syncopated sixteenths; leave space for bass and drums.",
            "bass": "Lock the first note to the kick, then keep ghost-note fills short and repeatable.",
            "winds": "Use short falls/stabs as answers, not continuous lines.",
            "voice": "Keep rhythmic diction tight and make consonants part of the groove.",
        }
    elif "rock" in text:
        profile = {
            "feel": "rock 8th-note drive",
            "count": "Count straight eighths: `1 & 2 & 3 & 4 &`.",
            "accent": "Accent 2 and 4; make chorus downbeats bigger than verse downbeats.",
            "guitar": "Verse: palm-muted downstrokes. Chorus: `D D U U D U` with stronger 2/4 accents.",
            "piano": "Left hand plays steady octaves or root-fifths; right hand hits chord accents on 2/4 or anticipation upbeats.",
            "bass": "Use eighth-note roots/fifths with consistent attack and longer chorus notes.",
            "winds": "Use concise riff answers and save sustained notes for section arrivals.",
            "voice": "Use clearer consonants in the verse and stronger projection into the chorus.",
        }
    elif "ballad" in text or bpm <= 76:
        profile = {
            "feel": "ballad pulse",
            "count": "Count subdivisions quietly so slow bars do not sag.",
            "accent": "Keep beat 1 grounded and let the phrase breathe toward beat 4.",
            "guitar": "Use arpeggiated bass-to-treble picking or soft `D - D U` strums with wide dynamic space.",
            "piano": "Left hand plays sparse roots/5ths; right hand places voicings after the beat with tasteful sustain.",
            "bass": "Use long, even notes and avoid fills until phrase endings.",
            "winds": "Use supported long tones and leave real silence between phrases.",
            "voice": "Keep the verse intimate; crescendo only into emotional arrivals.",
        }
    else:
        profile = {
            "feel": "straight 8th-note pop groove",
            "count": "Count `1 & 2 & 3 & 4 &` with steady subdivisions.",
            "accent": "Keep 2 and 4 alive; make section endings slightly more intentional.",
            "guitar": "`D D U - U D U`; mute one practice pass before adding chord changes.",
            "piano": "Left hand roots on 1/3; right hand light offbeat chord stabs or broken-chord eighths.",
            "bass": "Root on 1, fifth/octave on 3, then one approach into the next chord.",
            "winds": "Use two-bar phrases and land chord tones on strong beats.",
            "voice": "Speak rhythm first, then sing with clean pickups into each phrase.",
        }
    if role == "verse":
        profile["section_note"] = "Verse approach: play it lighter and simpler than the chorus."
    elif role == "chorus":
        profile["section_note"] = "Chorus approach: increase accent weight and rhythmic confidence."
    elif role == "bridge":
        profile["section_note"] = "Bridge approach: leave more space or change the pattern for contrast."
    elif role == "pre":
        profile["section_note"] = "Pre-chorus approach: add motion gradually so the chorus lands."
    else:
        profile["section_note"] = "Keep the groove consistent and make phrase endings clear."
    return profile


def _rhythm_guidance(instrument, *, section_name, groove_style, time_signature, bpm):
    family = _instrument_family(instrument)
    profile = _rhythm_profile(time_signature, groove_style, section_name, bpm)
    instrument_line = profile.get(family, profile["guitar"] if family == "guitar" else profile["piano"])
    overlay = (
        f"Rhythm: {html.escape(profile['feel'])}. {html.escape(profile['count'])} "
        f"{html.escape(profile['accent'])} {html.escape(instrument_line)} "
        f"{html.escape(profile['section_note'])}"
    )
    practice = (
        f"{profile['feel']}: {profile['count']} {profile['accent']} "
        f"For {instrument}, {instrument_line} {profile['section_note']}"
    )
    return {
        "feel": profile["feel"],
        "count": profile["count"],
        "accent": profile["accent"],
        "instrument": instrument_line,
        "section_note": profile["section_note"],
        "practice": practice,
        "overlay": overlay,
    }


def _dynamics_guidance(instrument, section_name, first_chord, second_chord):
    family = _instrument_family(instrument)
    shape = _section_dynamic_shape(section_name)
    lines = {
        "guitar": f"strum **{first_chord} -> {second_chord}** at p, mp, mf, then f; keep the same tempo while changing pick attack and accent weight",
        "piano": f"balance left-hand roots softer than right-hand color tones, then crescendo through **{first_chord} -> {second_chord}** without speeding up",
        "bass": f"play the same groove at three intensities; keep note length and attack consistent while changing volume",
        "winds": f"hold a supported crescendo into **{second_chord}**, then repeat with a clean decrescendo and identical pitch center",
        "voice": f"sing the phrase softly first, then crescendo into the emotional word while keeping breath support stable",
    }
    line = lines.get(family, f"shape **{first_chord} -> {second_chord}** from soft to strong, then back down without changing tempo")
    overlay = f"Dynamics: {html.escape(shape)}. {html.escape(line)}."
    return {"shape": shape, "practice": line, "overlay": overlay}
