"""Remove duplicated backing/coach blocks from main app; import from modules."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
path = ROOT / "streamlit_music_practice_app.py"
lines = path.read_text(encoding="utf-8").splitlines(keepends=True)

import_block = """
from backing_audio import (
    backing_bytes_to_float,
    bass_note,
    chord_notes,
    generate_backing_track,
    infer_groove_style,
    pcm16_wav_bytes_from_float,
    synthesize_chords_to_numpy,
    wav_bytes_from_float,
)
from coach_overlay import section_overlay_html as _section_overlay

"""

# Ranges to delete (1-based inclusive), bottom to top to preserve indices
delete_ranges = [
    (4006, 4008),  # wav_bytes_from_float tail if partial
    (3527, 4003),  # infer_groove through backing_bytes_to_float
    (576, 659),    # chord head through bass_note
    (1617, 1660),  # _section_overlay
    (1593, 1614),  # _backing_chord_color_tip - keep if overlay deleted? overlay imports from coach
]

# More precise: delete only what's fully moved
delete_ranges = [
    (4006, 4008),
    (3994, 4003),
    (3972, 3991),
    (3951, 3969),
    (3815, 3948),
    (3527, 3560),
    (3759, 3812),
    (3751, 3756),
    (3717, 3748),
    (3709, 3714),
    (3694, 3706),
    (3668, 3691),
    (3664, 3665),
    (3645, 3661),
    (3626, 3642),
    (3604, 3623),
    (3591, 3601),
    (3567, 3588),
    (3563, 3564),
    (1617, 1660),
    (1593, 1614),
    (576, 659),
]

# Simpler: two big deletes + overlay + backing_chord tip stays in main for _inline_harmonic? 
# _backing_chord_color_tip used by _section_overlay only - deleted with overlay
# _inline_harmonic and others still use _chart_section_role in main app

delete_ranges = [
    (4006, 4008),
    (3527, 4003),
    (1617, 1660),
    (576, 659),
]

for a, b in sorted(delete_ranges, reverse=True):
    del lines[a - 1 : b]

# Insert import after songs.key_state import (line ~110)
insert_after = "from songs.key_state import mark_display_key_changed\n"
text = "".join(lines)
if "from backing_audio import" not in text:
    if insert_after in text:
        text = text.replace(insert_after, insert_after + import_block, 1)
    else:
        raise SystemExit("insert anchor not found")

path.write_text(text, encoding="utf-8")
print("Patched streamlit_music_practice_app.py")
