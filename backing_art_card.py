"""The Backing card as the song's album cover (approved artwork), around the existing Backing widgets.

Presentation only. The Practice Key selector, BPM slider and Play / Stop control stay the same Streamlit
widgets with the same keys and callbacks; this module draws the artwork above them and the facts between
them. On by default; ``MUSIC_SONG_ART_CARDS=0`` brings back today's card (``song_card_art.song_art_cards_enabled``).
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


# What today's Backing record puts where an artist belongs when it has none.
_PLACEHOLDER_ARTISTS = frozenset({"", "catalog song", "composition", "composition song", "custom progression", "custom song", "song", "your progression"})
# Sources a record may put where its style belongs (Karaoke describes Custom / Composition entries this way).
_SOURCE_NAMES_AS_STYLE = frozenset({"custom", "custom progression", "composition", "composition song", "catalog", "song"})


def saved_style(session: Any, pick_key: str) -> str:
    """The style a Custom progression or a Composition is saved with on its own page, read now ("" if none)."""
    from song_identity_style import saved_song_style, song_source

    if song_source(pick_key) == "catalog":
        return ""
    return saved_song_style(session, pick_key)


def song_style_for_card(kind: str, *, session: Any, pick_key: str = "", record: Mapping[str, Any] | None = None) -> str:
    """The style that decides the card's artwork: the song's own saved style, never the Backing groove.

    Catalog: the catalog genre. Custom / Composition: the style saved on the Custom page / in Composition
    Studio, read fresh (a Backing play-session snapshot goes stale when the song is re-saved).
    """
    from song_identity_style import catalog_genre, saved_song_style

    rec = record or {}
    pk = str(pick_key or rec.get("pick_key") or "").strip()
    if kind in {"custom", "composition"}:
        return saved_song_style(session, pk) if pk else ""
    return catalog_genre(pk, title=str(rec.get("title") or ""), record=rec)


def catalog_card_facts(record: Mapping[str, Any], *, source_label: str = "", session: Any = None) -> dict[str, str]:
    """Title, artist and the catalog genre (the song's own genre decides its artwork, not the groove).

    The Backing record names its source where the artist belongs when it has no artist ("Catalog song");
    the catalog has the real one.
    """
    title = str(record.get("title") or "Active song")
    artist = str(record.get("artist") or "")
    genre = str(record.get("genre") or "")
    if artist.strip().lower() in _PLACEHOLDER_ARTISTS | {str(source_label or "").strip().lower()}:
        from song_identity_style import _catalog_row

        row = _catalog_row(title)
        artist = str(row.get("artist") or "")
        genre = str(row.get("genre") or genre)
    pick = str(record.get("pick_key") or "")
    if pick.startswith(("custom::", "composition::")) or genre.strip().lower() in _SOURCE_NAMES_AS_STYLE:
        genre = saved_style(session, pick) if session is not None else ""
    else:
        from song_identity_style import catalog_genre

        genre = catalog_genre(pick, title=title, record={"genre": genre}) or genre
    return {"title": title, "artist": artist, "style": genre}
