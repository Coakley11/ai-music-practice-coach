"""Per-lane Practice-Key authority for Song-Based Improvisation source switching.

SBI offers three lanes -- Active song, Custom progression, Composition -- and
each is a distinct musical context with its own Original and Practice Key:

* Active song   -> the global active source's own pick-scoped Practice Key.
* Custom        -> My Progression's own Custom store (``display_key_sbi_custom``).
* Composition   -> the Composition UUID's own store (``display_key_sbi_composition``).

The sidebar ``display_key`` is an *output* of whichever lane is selected, never
the authority for the lane clicked next. Before this module, the Custom and
Composition lanes both rendered through that shared key, and global reconcilers
read it back as the active song's Practice Key: Custom's D showed on the
Composition lane, and a lane's key was written into Perfect's own store when
the musician returned to "Active song".

Switching lanes is a preview, not a global activation: nothing here writes the
global owner's Practice Key.
"""

from __future__ import annotations

from typing import Any

LANE_ACTIVE = "Active song"
LANE_CUSTOM = "Custom progression"
LANE_COMPOSITION = "Composition"
SBI_LANES = (LANE_ACTIVE, LANE_CUSTOM, LANE_COMPOSITION)

#: Sidebar widget for the Composition lane. Separate from ``display_key`` so the
#: browser never re-commits a Composition preview key into the global widget.
COMPOSITION_LANE_WIDGET = "display_key_sbi_composition"

#: Preview-local Practice Keys for the current Creative session, per lane:
#: ``{lane: {"pick": <source pick>, "key": <token>}}``. A temporary SBI preview
#: edit lives here -- never in the source's durable ``practice_key_by_source``
#: entry, which only that source's own global lifecycle may write. Cleared when
#: the musician leaves (and re-enters) Creative; a refresh inside Creative keeps
#: it, like the rest of the in-progress preview.
PREVIEW_LANE_KEYS = "_sbi_preview_lane_practice_keys"

_LANE_OWNER = {LANE_CUSTOM: "custom", LANE_COMPOSITION: "composition"}


def preview_lane_key(session: dict[str, Any], lane: str, pick: str = "") -> str:
    """This Creative session's preview key for ``lane`` ("" when none)."""
    store = session.get(PREVIEW_LANE_KEYS)
    if not isinstance(store, dict):
        return ""
    entry = store.get(lane)
    if not isinstance(entry, dict):
        return ""
    stored_pick = str(entry.get("pick") or "").strip()
    if pick and stored_pick and stored_pick != str(pick).strip():
        return ""
    return str(entry.get("key") or "").strip()


def set_preview_lane_key(session: dict[str, Any], lane: str, pick: str, key: str) -> None:
    tok = str(key or "").strip()
    if not tok:
        return
    store = session.get(PREVIEW_LANE_KEYS)
    store = dict(store) if isinstance(store, dict) else {}
    store[lane] = {"pick": str(pick or "").strip(), "key": tok}
    session[PREVIEW_LANE_KEYS] = store


def clear_sbi_preview_lane_keys(session: dict[str, Any]) -> None:
    """End of the Creative session: drop every temporary SBI preview key.

    Only preview-local state is cleared. A source's own durable Practice Key --
    including a Custom or Composition that is the global owner -- is untouched,
    and so are that global owner's Custom widget keys.
    """
    preview_keys = set(all_preview_lane_keys(session))
    session.pop(PREVIEW_LANE_KEYS, None)
    session.pop(COMPOSITION_LANE_WIDGET, None)
    owner = ""
    try:
        from source_session_state import global_music_source_owner

        owner = global_music_source_owner(session)
    except Exception:
        owner = ""
    if owner != "custom":
        session.pop("_sbi_custom_visit_pk", None)
        session.pop("display_key_sbi_custom", None)
    # The Custom lane's sidebar left its preview key in the shared display
    # output. Put the global owner's own key back there so nothing downstream
    # reads the ended experiment as the owner's choice. The owner's stored
    # Practice Key itself is only read.
    live = {str(session.get(k) or "").strip() for k in ("display_key", "concert_key")}
    if preview_keys & live:
        own = global_owner_practice_key(session)
        if own:
            session["display_key"] = own
            session["concert_key"] = own
            session.pop("_pending_display_key", None)


def restore_global_owner_display_on_creative_exit(session: dict[str, Any]) -> str:
    """Leaving Creative for an ordinary page: show the global song's own key again.

    A jam's or preview lane's working key is only that workflow's output. Left
    in display_key it read as the global song's Practice Key on Practice / Songs
    (Perfect showed the Style Jam's F#). The owner's stored key is only read.
    """
    own = global_owner_practice_key(session)
    if not own:
        return ""
    live = {str(session.get(k) or "").strip() for k in ("display_key", "concert_key")}
    if live != {own}:
        session["display_key"] = own
        session["concert_key"] = own
        session.pop("_pending_display_key", None)
    return own


def all_preview_lane_keys(session: dict[str, Any]) -> list[str]:
    store = session.get(PREVIEW_LANE_KEYS)
    if not isinstance(store, dict):
        return []
    out = []
    for entry in store.values():
        if isinstance(entry, dict) and str(entry.get("key") or "").strip():
            out.append(str(entry["key"]).strip())
    return out


def global_owner_practice_key(session: dict[str, Any]) -> str:
    """The global owner's own saved Practice Key, else its Original (read only)."""
    pick = str(session.get("active_catalog_pick_key") or "").strip()
    stored = ""
    if pick:
        try:
            from songs.practice_key_state import get_practice_concert_key

            stored = str(get_practice_concert_key(session, pick, default="") or "").strip()
        except ImportError:
            stored = ""
    if stored:
        return stored
    sel = session.get("selected_song") if isinstance(session.get("selected_song"), dict) else {}
    return str((sel or {}).get("key") or "").strip()


def selected_sbi_lane(session: dict[str, Any]) -> str:
    """The SBI lane on screen right now, or "" when no SBI lane is displayed."""
    page = str(session.get("studio_page") or "").strip().lower()
    if page == "backing":
        # An explicit SBI Backing session carries its lane with it.
        try:
            from backing_context import get_backing_context

            ctx = get_backing_context(session)
        except Exception:
            ctx = None
        if ctx is not None and str(getattr(ctx, "source", "") or "") == "song_improv":
            owner = str(getattr(ctx, "sbi_source_owner", "") or "").strip()
            if owner in SBI_LANES:
                return owner
        return ""
    if page != "creative":
        return ""
    try:
        from source_session_state import sbi_custom_preview_surface_displayed

        if not sbi_custom_preview_surface_displayed(session):
            return ""
    except ImportError:
        return ""
    entry = str(session.get("improv_entry_mode") or "").strip()
    if entry and "Song-Based" not in entry:
        return ""
    for key in ("_pending_improv_song_source", "PENDING_IMPROV_SONG_SOURCE", "improv_song_source"):
        val = str(session.get(key) or "").strip()
        if val in SBI_LANES:
            return val
    return ""


def foreign_sbi_lane(session: dict[str, Any]) -> str:
    """A selected Custom/Composition lane that is only a preview, else "".

    When that lane's source is also the global owner it is not foreign: the
    lane and the global source are the same context and share one store.
    """
    lane = selected_sbi_lane(session)
    owner_kind = _LANE_OWNER.get(lane)
    if not owner_kind:
        return ""
    try:
        from source_session_state import global_music_source_owner

        if global_music_source_owner(session) == owner_kind:
            return ""
    except ImportError:
        pass
    return lane


def composition_lane_keys(session: dict[str, Any]) -> tuple[str, str, str]:
    """(pick, Original, Practice) of the Composition the lane previews."""
    try:
        from composition_session_state import get_active_document
        from composition_songs_bridge import (
            composition_pick_key_for,
            resolve_composition_canonical_keys,
        )
    except ImportError:
        return "", "", ""
    try:
        doc = get_active_document(session) or {}
    except Exception:
        doc = {}
    if not isinstance(doc, dict) or not doc:
        return "", "", ""
    pick = str(composition_pick_key_for(doc) or "").strip()
    original, practice = resolve_composition_canonical_keys(session, doc)
    original = str(original or "").strip()
    practice = str(practice or original).strip() or original
    # A temporary edit made on this lane in the current Creative session wins
    # over the Composition's own durable key -- only while it is a preview.
    if _composition_is_not_global(session):
        local = preview_lane_key(session, LANE_COMPOSITION, pick)
        if local:
            practice = local
    return pick, original, practice


def _composition_is_not_global(session: dict[str, Any]) -> bool:
    try:
        from source_session_state import global_music_source_owner

        return global_music_source_owner(session) != "composition"
    except Exception:
        return False


def composition_lane_preview(session: dict[str, Any]) -> dict[str, Any]:
    """Card data for the Composition lane: the document's real progression."""
    try:
        from composition_session_state import get_active_document
        from workflow_musical_authority import (
            resolve_composition_concert_sections_at_practice_key,
        )

        from composition_songs_bridge import resolve_composition_canonical_keys

        doc = get_active_document(session) or {}
        # Projected at the Composition's own durable key; re-projected below
        # when this Creative session holds a different preview key.
        sections = resolve_composition_concert_sections_at_practice_key(session) or {}
        _orig, durable = resolve_composition_canonical_keys(session, doc)
        durable = str(durable or _orig or "").strip()
    except Exception:
        doc, sections, durable = {}, {}, ""
    pick, original, practice = composition_lane_keys(session)
    if sections and durable and practice and practice != durable:
        try:
            from music_theory import transpose_sections_dict

            sections = transpose_sections_dict(sections, durable, practice)
        except Exception:
            pass
    return {
        "title": str((doc or {}).get("title") or "Composition"),
        "pick_key": pick,
        "original_key": original,
        "display_key": practice,
        "sections": sections,
    }


def composition_lane_owns_sidebar(session: dict[str, Any]) -> bool:
    return foreign_sbi_lane(session) == LANE_COMPOSITION and bool(composition_lane_keys(session)[0])


def prepare_composition_lane_sidebar(session: dict[str, Any]) -> tuple[list[str], str]:
    """Seed the Composition lane widget from Composition's own store.

    Returns (options, Original). Writes only the lane widget -- never
    ``display_key`` / ``concert_key`` / another source's store. The widget is
    re-asserted whenever it differs, so the browser is sent the value on the
    run that mounts it.
    """
    from songs.key_state import display_key_options

    _pick, original, practice = composition_lane_keys(session)
    options = list(display_key_options(original) or [original])
    if practice and practice not in options:
        options = [practice] + [k for k in options if k != practice]
    if practice and str(session.get(COMPOSITION_LANE_WIDGET) or "").strip() != practice:
        session[COMPOSITION_LANE_WIDGET] = practice
    return options, original


def commit_composition_lane_practice_key(session: dict[str, Any], token: str) -> str:
    """The musician changed the Composition lane key during a preview.

    Recorded as this Creative session's preview key only. The Composition's own
    durable Practice Key belongs to its global lifecycle and is not written.
    """
    tok = str(token or "").strip()
    pick, _original, _practice = composition_lane_keys(session)
    if not tok or not pick:
        return ""
    set_preview_lane_key(session, LANE_COMPOSITION, pick, tok)
    return tok


def lane_original_key_for_sidebar(session: dict[str, Any]) -> str:
    """Original Key the sidebar caption must show for a foreign Composition lane."""
    if not composition_lane_owns_sidebar(session):
        return ""
    return composition_lane_keys(session)[1]


def _jam_workflow_pick(owner: str) -> str:
    try:
        from songs.practice_key_state import CREATIVE_JAM_SESSION_PICK, CREATIVE_STYLE_JAM_PICK
    except ImportError:
        return ""
    return {
        "jam_session_generator": CREATIVE_JAM_SESSION_PICK,
        "style_jam": CREATIVE_STYLE_JAM_PICK,
    }.get(str(owner or ""), "")


def jam_key_was_chosen(session: dict[str, Any], owner: str) -> bool:
    """True once this jam workflow has its own key: a musician's edit (kept on
    the workflow's ``creative::`` pick) or material generated in some key."""
    pick = _jam_workflow_pick(owner)
    if pick:
        try:
            from songs.practice_key_state import get_practice_concert_key

            if str(get_practice_concert_key(session, pick, default="") or "").strip():
                return True
        except ImportError:
            pass
    if owner == "jam_session_generator":
        jam = session.get("improv_jam_session")
        return bool(isinstance(jam, dict) and jam.get("sections"))
    if owner == "style_jam":
        return bool(session.get("improv_generated_sections"))
    return False


def jam_working_key_for_entry(session: dict[str, Any], entry_mode: str) -> str:
    """The working key of *this* jam: Style Jam's own key or the Generator's own.

    Never "improv_jam_key or improv_style_key": that handed a Style Jam the
    Generator's key (and vice versa) whenever the other jam's widget value was
    still in session.
    """
    entry = str(entry_mode or "").strip()
    if "Style Jam" in entry:
        return str(session.get("improv_style_key") or "").strip()
    if entry == "Jam Session Generator":
        return str(session.get("improv_jam_key") or "").strip()
    return ""


def default_jam_working_key(session: dict[str, Any]) -> str:
    """The key a never-used jam starts in: the global song's current Practice Key
    (full tonic + mode, e.g. ``Bm`` for a B-minor song) -- not a hard-coded Eb/G."""
    return global_owner_practice_key(session)


__all__ = [
    "COMPOSITION_LANE_WIDGET",
    "PREVIEW_LANE_KEYS",
    "clear_sbi_preview_lane_keys",
    "preview_lane_key",
    "set_preview_lane_key",
    "LANE_ACTIVE",
    "LANE_COMPOSITION",
    "LANE_CUSTOM",
    "commit_composition_lane_practice_key",
    "composition_lane_keys",
    "composition_lane_owns_sidebar",
    "composition_lane_preview",
    "foreign_sbi_lane",
    "lane_original_key_for_sidebar",
    "prepare_composition_lane_sidebar",
    "selected_sbi_lane",
]
