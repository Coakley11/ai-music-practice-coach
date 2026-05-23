"""Concert pitch vs written key for transposing instruments (saxophone focus)."""

from __future__ import annotations

from music_theory import CHROMATIC, normalize_root, split_chord, transpose_chord

SAXOPHONE_TYPES: tuple[str, ...] = (
    "Alto saxophone (Eb)",
    "Tenor saxophone (Bb)",
    "Soprano saxophone (Bb)",
    "Baritone saxophone (Eb)",
)

SAX_TYPE_SESSION_KEY = "saxophone_type"


def _transpose_key_center(key: str, steps: int) -> str:
    root, suffix = split_chord(str(key or "C"))
    nr = normalize_root(root)
    if nr not in CHROMATIC:
        return str(key)
    new_root = CHROMATIC[(CHROMATIC.index(nr) + steps) % 12]
    return new_root + suffix


def sax_written_key_steps(sax_type: str) -> int:
    """Semitone shift from concert key to written key on the chart."""
    low = str(sax_type or "").lower()
    if "tenor" in low or "soprano" in low:
        return 2
    if "alto" in low or "baritone" in low or "bari" in low:
        return -3
    return -3


def written_key_for_saxophone(concert_key: str, sax_type: str) -> str:
    return _transpose_key_center(concert_key, sax_written_key_steps(sax_type))


def is_transposing_instrument(instrument: str) -> bool:
    return str(instrument or "").strip() == "Saxophone"


def sax_transposition_blurb(concert_key: str, sax_type: str) -> str:
    written = written_key_for_saxophone(concert_key, sax_type)
    if "alto" in sax_type.lower() or "baritone" in sax_type.lower():
        inst = "Eb instrument"
        example = (
            f"If the song is in **{concert_key}** concert, you read and finger it in **{written}**."
        )
    else:
        inst = "Bb instrument"
        example = (
            f"If the song is in **{concert_key}** concert, you read and finger it in **{written}**."
        )
    return (
        f"You selected **{sax_type}**. This is an **{inst}**. {example} "
        "Charts below can show chords in your written key."
    )


def effective_chart_key(
    concert_key: str,
    instrument: str,
    session_state: dict,
    *,
    use_written_for_sax: bool = True,
) -> tuple[str, str]:
    """Return (chart_key, mode_label) where mode_label is 'concert' or 'written'."""
    if use_written_for_sax and is_transposing_instrument(instrument):
        sax_type = session_state.get(SAX_TYPE_SESSION_KEY) or SAXOPHONE_TYPES[0]
        return written_key_for_saxophone(concert_key, sax_type), "written"
    return concert_key, "concert"
