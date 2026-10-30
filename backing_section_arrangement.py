"""Section-aware backing arrangement: what each section of a song plays.

The synth used to tell sections apart almost only by loudness (Funk: the
same kick / snare / 16th hats / bass line / stabs in every section, 8.5 dB
from intro to final chorus). This module decides, per bar, a *texture* --
which drums play, how dense the hats are, whether the keys stab, hold or thin
out, whether the bass plays its line or just roots -- from the song's own
section labels, and narrows the loudness spread so texture carries the energy.

* :func:`section_role` maps a section label to a role: exact names first, then
  a short list of controlled synonyms ("Middle Eight" is a bridge, "Chorus
  Prep" is a pre-chorus, never a chorus). Unknown labels are ``neutral``.
* :func:`build_plan` walks the rendered bars once: which section block a bar
  is in, the block's place in the song (first / last, which verse / chorus
  pass), and which loop of the song it is.
* :func:`bar_texture` gives the texture for one bar, or ``None`` for a
  ``neutral`` bar -- unlabelled practice loops and unknown labels render
  exactly as before. Pop, Rock and Funk change the most; Jazz and Bossa
  get light touches that keep their pocket.

The tempo, the chords and their timing never change: only who plays what.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

INTRO = "intro"
VERSE = "verse"
PRE = "pre"
CHORUS = "chorus"
REFRAIN = "refrain"
BRIDGE = "bridge"
INTERLUDE = "interlude"
SOLO = "solo"
BREAKDOWN = "breakdown"
OUTRO = "outro"
NEUTRAL = "neutral"

# Exact section names (numbering, "(...)" notes and "final" / "repeat"
# qualifiers removed first).
_EXACT = {
    "intro": INTRO,
    "introduction": INTRO,
    "verse": VERSE,
    "main loop": VERSE,
    "pre-chorus": PRE,
    "pre chorus": PRE,
    "prechorus": PRE,
    "chorus prep": PRE,
    "build": PRE,
    "build-up": PRE,
    "buildup": PRE,
    "lift": PRE,
    "chorus": CHORUS,
    "refrain": REFRAIN,
    "post-chorus": REFRAIN,
    "post chorus": REFRAIN,
    "hook": REFRAIN,
    "bridge": BRIDGE,
    "middle eight": BRIDGE,
    "middle 8": BRIDGE,
    "middle": BRIDGE,
    "interlude": INTERLUDE,
    "instrumental": INTERLUDE,
    "instrumental break": INTERLUDE,
    "link": INTERLUDE,
    "solo": SOLO,
    "breakdown": BREAKDOWN,
    "break": BREAKDOWN,
    "stop": BREAKDOWN,
    "outro": OUTRO,
    "ending": OUTRO,
    "coda": OUTRO,
    "fade": OUTRO,
    "fade out": OUTRO,
    "fade-out": OUTRO,
}

# Words that only say *which* pass of a section this is.
_PASS_WORDS = {"final", "last", "repeat", "reprise", "extension", "double", "big", "main", "full", "key", "change"}
_INSTRUMENT_WORDS = {
    "guitar", "sax", "saxophone", "piano", "organ", "synth", "harmonica", "trumpet", "horn",
    "horns", "fiddle", "violin", "banjo", "keys", "bass", "drum", "drums", "lead", "string", "strings",
}


def _normalize(part: str) -> str:
    low = re.sub(r"\([^)]*\)", " ", part.lower())
    low = re.sub(r"[^a-z0-9\- ]+", " ", low)
    words = [w for w in low.split() if w]
    # Trailing numbering: "Verse 3A", "Chorus 2", "Pre-Chorus 1", "Hora A".
    while words and re.fullmatch(r"\d+[a-z]?|[a-d]|[ivx]+", words[-1]) and len(words) > 1:
        words.pop()
    return " ".join(words)


def _part_role(part: str) -> str:
    name = _normalize(part)
    if not name:
        return NEUTRAL
    if name in _EXACT:
        return _EXACT[name]
    words = name.replace("-", " - ").split()
    plain = [w for w in words if w != "-"]
    core = [w for w in plain if w not in _PASS_WORDS]
    joined = " ".join(core)
    if joined in _EXACT and _EXACT[joined] in (CHORUS, REFRAIN, VERSE, BRIDGE, OUTRO, INTRO, PRE):
        return _EXACT[joined]  # "Final Chorus", "Chorus Repeat", "Last Verse"
    if plain and plain[0] == "pre" and "chorus" in plain:
        return PRE  # "Pre-Final Chorus"
    if "prep" in plain or any(w.startswith("build") for w in plain):
        return PRE  # "Chorus Prep", "Verse Build", "Final Build", "Gaga build-up"
    if "intro" in plain:
        return INTERLUDE if "return" in plain else INTRO  # "Sax Intro"; "Intro Riff Return"
    if "outro" in plain or "coda" in plain or "ending" in plain:
        return OUTRO  # "Outro Sax"
    if "solo" in plain or ("break" in plain and set(plain) & _INSTRUMENT_WORDS):
        return SOLO  # "Guitar Solo", "Guitar Break"
    if "breakdown" in plain or plain == ["vocal", "break"]:
        return BREAKDOWN
    if "instrumental" in plain or "interlude" in plain or ("riff" in plain and "return" in plain):
        return INTERLUDE
    if "middle" in plain and ("eight" in plain or "8" in plain):
        return BRIDGE
    return NEUTRAL


def section_role(section_name) -> str:
    """The arrangement role of a section label (``neutral`` when unknown).

    "Bridge / Oh Section" and "Final Chorus / Outro Build" take the role of the
    first part that has one.
    """
    for part in str(section_name or "").split("/"):
        role = _part_role(part)
        if role != NEUTRAL:
            return role
    return NEUTRAL


def grid_role(role: str) -> str:
    """The groove-profile grid a role borrows (a refrain plays the chorus grid)."""
    return CHORUS if role == REFRAIN else role


@dataclass(frozen=True)
class BarPlace:
    """Where one rendered bar sits in the song's form."""

    role: str
    block: int        # section block (run of bars with one label) within one pass of the song
    blocks: int       # blocks in one pass of the song
    bar: int          # bar within the block
    bars: int         # bars in the block
    role_pass: int    # 1-based: which block of this role (Verse 2 -> 2)
    role_blocks: int  # blocks of this role in one pass
    loop: int
    loops: int


def build_plan(chord_list, cycle_len: int) -> list[BarPlace]:
    """One :class:`BarPlace` per rendered bar (``chord_list`` = the song x loops)."""
    cycle_len = max(1, int(cycle_len))
    cycle = list(chord_list[:cycle_len])
    names = [str(e.get("section") or "") for e in cycle]
    starts = [i for i in range(len(names)) if i == 0 or names[i] != names[i - 1]]
    bounds = list(zip(starts, starts[1:] + [len(names)]))
    roles = [section_role(names[s]) for s, _e in bounds]
    passes, seen = [], {}
    for r in roles:
        seen[r] = seen.get(r, 0) + 1
        passes.append(seen[r])
    places: list[BarPlace] = []
    for bi, ((s, e), r) in enumerate(zip(bounds, roles)):
        for i in range(s, e):
            places.append(BarPlace(r, bi, len(bounds), i - s, e - s, passes[bi], seen[r], 0, 1))
    loops = max(1, -(-len(chord_list) // cycle_len))
    return [
        BarPlace(p.role, p.block, p.blocks, p.bar, p.bars, p.role_pass, p.role_blocks, idx // cycle_len, loops)
        for idx, p in ((idx, places[idx % cycle_len]) for idx in range(len(chord_list)))
    ]


@dataclass(frozen=True)
class SectionTexture:
    """What one bar plays. The defaults are the style's groove, unchanged."""

    role: str
    drums: str = "groove"   # groove | light (kick on 1 & 3, no ghosts) | hats | minimal | ending
    hats: str = "groove"    # groove | lighter | denser
    ghosts: bool = True
    open_hat_and4: bool = False
    comp: str = "groove"    # groove | sparse | sustain | full
    comp_extra_voice: bool = False
    pad: bool = False       # a quiet held chord an octave up (final chorus layer)
    bass: str = "groove"    # groove | roots | half
    bass_density: float = 1.0
    crash: bool = False     # crash on the downbeat (the ending hit)
    intensity: float = 1.0


_STRONG = {"Pop groove", "Pop", "Rock groove", "Funk groove"}
_LIGHT = {"Jazz swing", "Bossa nova"}
# How much of the old section loudness spread survives (1 = all of it).
_SPREAD = {"strong": 0.38, "moderate": 0.42, "light": 0.4}
_REF_INTENSITY = 0.92  # the "neutral" section level


def style_family(style: str) -> str:
    if style in _STRONG:
        return "strong"
    if style in _LIGHT:
        return "light"
    return "moderate"


def shape_intensity(intensity: float, style: str, texture: SectionTexture) -> float:
    """Narrow the section loudness spread around the neutral level, then apply the texture's trim."""
    k = _SPREAD[style_family(style)]
    shaped = _REF_INTENSITY * (max(1e-4, float(intensity)) / _REF_INTENSITY) ** k
    return shaped * texture.intensity


def bar_texture(style: str, place: BarPlace) -> SectionTexture | None:
    """The texture for one bar, or ``None`` (neutral: the groove exactly as before)."""
    role = place.role
    if role == NEUTRAL:
        return None
    fam = style_family(style)
    funk = style == "Funk groove"
    first, last = place.block == 0, place.block == place.blocks - 1
    multi = place.blocks > 1
    second_half = place.bar >= place.bars // 2
    final_loop = place.loop == place.loops - 1
    ending = role == OUTRO and last and final_loop and multi and place.bar == place.bars - 1
    T = SectionTexture

    if ending:
        return T(role, drums="ending", comp="sustain", bass="roots", crash=fam != "light" or style == "Jazz swing",
                 intensity=0.8)

    if role == INTRO:
        if fam == "light":
            if style == "Jazz swing":
                return T(role, comp="sparse", bass="half", intensity=0.96)
            return T(role, drums="light", bass_density=0.8, intensity=0.96)
        build_up = first and multi and place.loop == 0 and place.bars >= 4 and not second_half
        if fam == "strong":
            if build_up:
                return T(role, drums="hats", hats="lighter", comp="sustain", bass="roots", intensity=0.88)
            return T(role, drums="light", hats="groove" if funk else "lighter", ghosts=False,
                     comp="sparse", bass_density=0.7, intensity=0.92)
        if build_up:
            return T(role, drums="light", ghosts=False, comp="sustain", bass="roots", intensity=0.92)
        return T(role, drums="light", ghosts=False, comp="sustain", intensity=0.92)

    if role == VERSE:
        if fam == "strong" and place.role_pass >= 2:
            return T(role, open_hat_and4=place.bar % 2 == 1)  # Verse 2: same groove, a little air
        return T(role)

    if role == PRE:
        if fam == "light":
            return T(role)
        if second_half:
            return T(role, hats="denser" if not funk else "groove", comp="full")
        return T(role)

    if role in (CHORUS, REFRAIN):
        final = role == CHORUS and place.role_pass == place.role_blocks and place.role_blocks >= 2
        if fam == "light":
            return T(role)
        if role == REFRAIN:
            return T(role, intensity=1.06)
        return T(role, comp_extra_voice=True, pad=final, intensity=1.03 if final else 1.0)

    if role == BRIDGE:
        if fam == "light":
            return T(role, comp="sparse") if style == "Jazz swing" else T(role)
        if funk:
            return T(role, drums="light", ghosts=False, comp="sparse", bass_density=0.75)
        if fam == "strong":
            return T(role, drums="light", hats="lighter", ghosts=False, comp="sustain", bass="half")
        return T(role, hats="lighter", ghosts=False)

    if role == INTERLUDE:
        if fam == "light":
            return T(role)
        return T(role, comp="full", comp_extra_voice=fam == "strong")

    if role == SOLO:
        return T(role, comp="sparse")

    if role == BREAKDOWN:
        if fam == "light":
            return T(role, comp="sparse", bass="half" if style == "Jazz swing" else "groove")
        return T(role, drums="minimal", hats="lighter", comp="sustain", bass="roots", intensity=0.92)

    if role == OUTRO:
        if not (last and multi):
            return T(role)
        # The last section winds down: the groove first, then a thinner texture and a taper.
        pos = place.bar / max(1, place.bars - 1)
        taper = 1.0 - (0.22 if final_loop else 0.1) * pos
        if not second_half:
            return T(role, intensity=taper)
        if fam == "light":
            if style == "Jazz swing":
                return T(role, comp="sparse", bass="half", intensity=taper)
            return T(role, drums="light", intensity=taper)
        return T(role, drums="light", hats="lighter", ghosts=False, comp="sustain", bass="roots", intensity=taper)

    return T(role)


def _hat_grid(n: int) -> list[float]:
    return [i * 4.0 / n for i in range(n)]


def apply_to_grid(grid, texture: SectionTexture, pulses_per_bar: int) -> dict:
    """A copy of one bar's rhythm grid with the texture applied (drums, hats, comp rhythm, bass rhythm)."""
    out = {k: (list(v) if isinstance(v, (list, tuple)) else v) for k, v in dict(grid).items()}
    if pulses_per_bar != 4:
        return out  # odd meters keep their grid; textures still shape keys, bass and level
    kicks = list(out.get("kick_beats", []))
    hats = list(out.get("hat_beats", []))
    if texture.hats in ("lighter", "denser") and len(hats) in (4, 8, 16):
        n = len(hats) // 2 if texture.hats == "lighter" else len(hats) * 2
        out["hat_beats"] = _hat_grid(min(16, max(4, n)))
    if texture.drums == "light":
        out["kick_beats"] = [b for b in kicks if b in (0.0, 2.0)] or ([0.0] if kicks else [])
        out["ghost_snare"] = []
    elif texture.drums == "hats":
        out["kick_beats"], out["snare_beats"], out["ghost_snare"], out["cross_stick"] = [], [], [], []
    elif texture.drums == "minimal":
        out["kick_beats"] = [0.0] if kicks else []
        out["snare_beats"], out["ghost_snare"] = [], []
    elif texture.drums == "ending":
        out["kick_beats"] = [0.0] if kicks else []
        out["snare_beats"], out["ghost_snare"], out["cross_stick"], out["hat_beats"] = [], [], [], []
    if not texture.ghosts:
        out["ghost_snare"] = []
    if texture.comp == "sparse":
        out["comp_beats"] = list(out.get("comp_beats", []))[::2]
    if texture.bass == "half":
        out["bass_beats"] = [0.0, 2.0]
    return out


def add_top_voice(voicing: list[int], ceiling: int = 88) -> list[int]:
    """The voicing with its lowest note doubled an octave up (a fuller chorus chord)."""
    if not voicing:
        return voicing
    for note in sorted(voicing):
        up = note + 12
        if up not in voicing and up <= ceiling:
            return sorted(list(voicing) + [up])
    return list(voicing)
