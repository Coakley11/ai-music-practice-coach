"""The Backing card as the song's album cover (approved artwork), around the existing Backing widgets.

Presentation only. The Practice Key selector, BPM slider and Play / Stop control stay the same Streamlit
widgets with the same keys and callbacks; this module draws the artwork above them and the facts between
them. Off unless ``MUSIC_SONG_ART_CARDS`` is set (``song_card_art.song_art_cards_enabled``).
"""

from __future__ import annotations

from typing import Any, Mapping

import song_card_art as art

ART_KINDS = frozenset({"song", "custom", "composition"})


def backing_art_enabled(kind: str) -> bool:
    """Catalog, Custom and Composition cards have approved artwork; a Style Jam card keeps today's."""
    return art.song_art_cards_enabled() and str(kind or "") in ART_KINDS


def identity_for(kind: str, *, source_label: str = "", style: str = "") -> art.CardIdentity:
    source = {"custom": "Custom", "composition": "Composition"}.get(str(kind or ""), str(source_label or "Catalog"))
    return art.card_identity(source, style)


def render_backing_art_head(
    st: Any,
    identity: art.CardIdentity,
    *,
    title: str,
    artist: str = "",
    karaoke: bool = False,
) -> None:
    """The card's colors and frame (on the keyed container) and its artwork with title and artist."""
    status = "Now singing" if karaoke else ""
    st.markdown(
        art.card_style_tag(identity, container_key=art.BACKING_CONTAINER)
        + art.hero_html(identity, title=title, artist=artist, page="backing", status=status),
        unsafe_allow_html=True,
    )


def render_backing_art_chips(
    st: Any,
    identity: art.CardIdentity,
    *,
    groove: str,
    meter: str,
    written: str = "",
    written_label: str = "",
) -> None:
    st.markdown(
        art.backing_chips_html(identity, groove=groove, meter=meter, written=written, written_label=written_label),
        unsafe_allow_html=True,
    )


def catalog_card_facts(record: Mapping[str, Any]) -> dict[str, str]:
    """Title, artist and the catalog genre (the song's own genre decides its artwork, not the groove)."""
    return {
        "title": str(record.get("title") or "Active song"),
        "artist": str(record.get("artist") or ""),
        "style": str(record.get("genre") or ""),
    }
