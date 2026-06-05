"""Portfolio demo state loaders — music practice coach. Presentation only."""

from __future__ import annotations

from song_catalog import resolve_pick_key
from songs.state import apply_pick_key

import portfolio_polish as pp

DEMO_SONG = "Across the Universe — The Beatles"


def load_practice_demo(st, song_picker_catalog, song_library, records) -> None:
    """Load curated demo song and open Practice page."""
    pick_key = resolve_pick_key(
        DEMO_SONG,
        song_picker_catalog=song_picker_catalog,
        records=records,
    )
    if pick_key:
        apply_pick_key(st, pick_key, song_picker_catalog, song_library=song_library)
    st.session_state["studio_page"] = "practice"
    st.session_state["practice_focus_section"] = "Verse"
    st.session_state["instrument"] = "Guitar"
    pp.mark_demo_applied(st, "practice")


def apply_auto_demo(st, song_picker_catalog, song_library, records) -> None:
    if pp.is_demo_mode(st) and not pp.demo_applied(st, "practice"):
        load_practice_demo(st, song_picker_catalog, song_library, records)
