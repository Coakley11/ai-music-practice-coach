"""The Backing card as the song's album cover (approved artwork), around the existing Backing widgets.

Presentation only. The Practice Key selector, BPM slider and Play / Stop control stay the same Streamlit
widgets with the same keys and callbacks; this module draws the artwork above them and the facts between
them. On by default; ``MUSIC_SONG_ART_CARDS=0`` brings back today's card (``song_card_art.song_art_cards_enabled``).
"""

from __future__ import annotations

from typing import Any, Mapping

import song_card_art as art

ART_KINDS = frozenset({"song", "custom", "composition"})
# Creative handoffs that play a real song: a Mission or Song-Based Improvisation wears that song's card.
# Style Jam / Jam Session Generator ("entry_jam") keep today's card.
ART_CREATIVE_SOURCES = frozenset({"mission", "song_improv"})


def backing_art_enabled(kind: str, *, creative_source: str = "") -> bool:
    """Catalog, Custom and Composition cards have approved artwork, and so do Missions and SBI (their song's);
    a Style Jam card keeps today's."""
    if not art.song_art_cards_enabled():
        return False
    kind = str(kind or "")
    if kind == "creative":
        return str(creative_source or "") in ART_CREATIVE_SOURCES
    return kind in ART_KINDS


def creative_owner_pick(session: Any, ctx: Any) -> str:
    """The pick key of the song a Mission or SBI backing plays, read now.

    Mission: the Mission's current owner song (the sealed ``bound_pick_key`` can be stale after the song
    changed). SBI: the song it was opened with, Custom when its owner says Custom.
    """
    source = str(getattr(ctx, "source", "") or "")
    bound = str(getattr(ctx, "bound_pick_key", "") or getattr(ctx, "active_song_id", "") or "").strip()
    pick = ""
    if source == "mission":
        try:
            from mission_owner_contract import resolve_mission_owner_context

            pick = str(resolve_mission_owner_context(session).underlying_pick or "").strip()
        except Exception:
            pick = ""
        return pick or bound
    pick = bound
    if source == "song_improv":
        kind = ""
        try:
            from source_session_state import resolve_sbi_material_kind

            kind = str(resolve_sbi_material_kind(session, ctx=ctx) or "")
        except Exception:
            kind = ""
        if kind == "custom" and not pick.startswith("custom::"):
            try:
                from custom_progression_lab import CPL_ACTIVE_KEY
                from songs.music_source import custom_pick_key_for

                active = session.get(CPL_ACTIVE_KEY)
                if isinstance(active, dict):
                    pick = str(custom_pick_key_for(active) or pick)
            except Exception:
                pass
    return pick


def creative_identity(session: Any, ctx: Any) -> tuple[art.CardIdentity, str, str]:
    """(identity, title, artist) for a Mission / SBI card: the song's own source and saved style, never the groove."""
    from song_identity_style import saved_song_style, song_source

    pick = creative_owner_pick(session, ctx)
    source = song_source(pick) if pick else "catalog"
    style = saved_song_style(session, pick) if pick else ""
    title = str(getattr(ctx, "song_title", "") or "").strip()
    artist = ""
    if source == "catalog":
        facts = catalog_card_facts({"title": title, "pick_key": pick}, session=session)
        title, artist = facts["title"], facts["artist"]
        style = style or facts["style"]
    label = {"custom": "Custom", "composition": "Composition"}.get(source, "Catalog")
    return art.card_identity(label, style), title or "Active song", artist


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
    status: str = "",
    bars: list[str] | tuple[str, ...] = (),
    bars_note: str = "",
) -> None:
    """The card's colors and frame (on the keyed container) and its artwork with title and artist.

    A Mission shows its target chord or 2/3-chord span in the card's chord strip (``bars``)."""
    status = "Now singing" if karaoke else status
    st.markdown(
        art.card_style_tag(identity, container_key=art.BACKING_CONTAINER)
        + art.hero_html(identity, title=title, artist=artist, page="backing", status=status, bars=bars, bars_note=bars_note),
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
    written_instrument: str = "",
) -> None:
    st.markdown(
        art.backing_chips_html(
            identity, groove=groove, meter=meter, written=written, written_label=written_label,
            written_instrument=written_instrument,
        ),
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
