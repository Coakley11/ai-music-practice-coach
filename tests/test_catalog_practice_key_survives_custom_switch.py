"""A user-committed Catalog Practice Key is durable across a Custom switch.

Proven sequence that regressed: Girl from Ipanema (Original F) with an
explicitly chosen Practice Key G, then Catalog -> Custom. ``set_custom_source``
calls ``forget_catalog_visit_practice_key``, which cleared *every* non-custom
entry in ``practice_key_by_source`` regardless of whether the user had chosen
it. Once the entry was gone, returning to the song re-derived Original F.

Visit residue must still be forgettable, so these pin both directions.
"""

from __future__ import annotations

from songs.music_source import forget_catalog_visit_practice_key
from songs.practice_key_state import (
    PRACTICE_KEY_BY_SOURCE_KEY,
    catalog_pick_has_user_practice_key_override,
    get_practice_concert_key,
    mark_practice_key_user_override,
    set_practice_concert_key,
)

IPANEMA = "Jazz\x1fThe Girl from Ipanema — Antonio Carlos Jobim"
RESIDUE = "Pop\x1fSay — John Mayer"
CUSTOM_PICK = "custom::trial-song-uuid"


def _session_leaving_catalog_for_custom() -> dict:
    """Catalog pick live, a custom song becoming Global Active."""
    return {
        "active_catalog_pick_key": IPANEMA,
        "studio_page": "custom",
        "active_music_source": "custom_progression",
    }


def test_overridden_catalog_key_survives_forget_catalog_visit() -> None:
    session = _session_leaving_catalog_for_custom()
    set_practice_concert_key(session, "G", pick_key=IPANEMA)
    mark_practice_key_user_override(session, IPANEMA)
    set_practice_concert_key(session, "D", pick_key=CUSTOM_PICK)

    assert get_practice_concert_key(session, IPANEMA, default="") == "G"

    forget_catalog_visit_practice_key(session)

    # The user's explicit choice is parked, exactly like a Custom entry.
    assert get_practice_concert_key(session, IPANEMA, default="") == "G"
    assert catalog_pick_has_user_practice_key_override(session, IPANEMA)
    # Custom keeps its own key; no foreign value crossed owners.
    assert get_practice_concert_key(session, CUSTOM_PICK, default="") == "D"


def test_non_overridden_catalog_residue_is_still_forgotten() -> None:
    """The cleanup must keep working for an uncommitted visit value."""
    session = _session_leaving_catalog_for_custom()
    set_practice_concert_key(session, "G", pick_key=RESIDUE)
    # Deliberately no mark_practice_key_user_override for RESIDUE.

    assert get_practice_concert_key(session, RESIDUE, default="") == "G"

    forget_catalog_visit_practice_key(session)

    assert get_practice_concert_key(session, RESIDUE, default="") == ""


def test_mixed_store_forgets_only_the_unowned_catalog_entry() -> None:
    session = _session_leaving_catalog_for_custom()
    set_practice_concert_key(session, "G", pick_key=IPANEMA)
    mark_practice_key_user_override(session, IPANEMA)
    set_practice_concert_key(session, "A", pick_key=RESIDUE)
    set_practice_concert_key(session, "D", pick_key=CUSTOM_PICK)

    forget_catalog_visit_practice_key(session)

    store = session.get(PRACTICE_KEY_BY_SOURCE_KEY) or {}
    assert store.get(IPANEMA) == "G"
    assert RESIDUE not in store
    assert store.get(CUSTOM_PICK) == "D"


def test_catalog_g_then_custom_d_then_catalog_restores_g() -> None:
    """Catalog G -> Custom D -> Catalog must restore G, not Original F."""
    session = _session_leaving_catalog_for_custom()
    set_practice_concert_key(session, "G", pick_key=IPANEMA)
    mark_practice_key_user_override(session, IPANEMA)

    # Leaving Catalog for Custom.
    set_practice_concert_key(session, "D", pick_key=CUSTOM_PICK)
    forget_catalog_visit_practice_key(session)

    # While Custom is active, the Catalog key stays parked.
    assert get_practice_concert_key(session, IPANEMA, default="") == "G"
    assert get_practice_concert_key(session, CUSTOM_PICK, default="") == "D"

    # Returning to Catalog resolves the parked key, never Original F.
    session["active_music_source"] = "catalog_song"
    session["active_catalog_pick_key"] = IPANEMA
    restored = get_practice_concert_key(session, IPANEMA, default="")
    assert restored == "G"
    assert restored != "F"
