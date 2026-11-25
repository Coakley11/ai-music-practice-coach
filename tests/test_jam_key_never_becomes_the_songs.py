"""A jam's key on screen is never saved as the active song's Practice Key.

Browser 2026-11-25 (Dev 7909aa58 and this branch alike): Composition "Jazz tune" (D) active, a Style Jam in C on
Backing, then Practice: Jazz tune was in C. ``note_display_key_change`` saved every key on screen as the active
Composition's, the jam's included.
"""

from __future__ import annotations

import pytest

from songs.key_state import display_key_belongs_to_a_jam


def _ctx(source, entry="Style Jam Mode"):
    return {"source": source, "entry_mode": entry, "key": "C", "concert_key": "C"}


@pytest.mark.parametrize("page,source,entry,jam", [
    ("backing", "entry_jam", "Style Jam Mode", True),
    ("backing", "entry_jam", "Jam Session Generator", True),
    ("backing", "composition_song", "", False),
    ("practice", "entry_jam", "Style Jam Mode", False),
    ("songs", "", "", False),
])
def test_whose_key_is_on_screen(page, source, entry, jam):
    s = {"studio_page": page, "backing_context": _ctx(source, entry) if source else None, "improv_entry_mode": entry}
    assert display_key_belongs_to_a_jam(s) is jam


def test_the_creative_jam_page_owns_its_key():
    s = {"studio_page": "creative", "improv_entry_mode": "Style Jam Mode", "improv_intelligence_tab": "Entry & Jam"}
    assert display_key_belongs_to_a_jam(s)


def test_the_composition_save_asks_whose_key_it_is():
    """The only place a key on screen becomes the active Composition's (browser D1 proves the path end to end)."""
    import inspect

    import songs.key_state as ks

    src = inspect.getsource(ks.note_display_key_change)
    block = src[src.index("composition_song_is_active(st.session_state)") : src.index("commit_composition_owned_practice_key(st.session_state")]
    assert "not display_key_belongs_to_a_jam(st.session_state)" in block
