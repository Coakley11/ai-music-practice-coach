"""Backing page melodies: which displays exist, which one may lead the page.

Four displays can sit under the Backing Lead Sheet:

* **Original Melody** -- the song's own synchronized melody. Today that is a Composition's composed melody; the
  hook :func:`original_melody_sections` also accepts a future, properly integrated synchronized melody for a
  Catalog or Custom song (``song_data["original_melody"]``, the same per-section event shape Composition uses).
  An arbitrary uploaded PDF is never an Original Melody. When open it always leads the page.
* **Practice Melody** -- the generated melody to play along with.
* **My Uploaded Melodies** -- the musician's own PDFs, read by hand. They never follow the music.
* **Lead Sheet**.

Practice Melody and My Uploaded Melodies are two **independent sections** (user, 2026-11-26, replacing the
2026-11-20 rule that they were two modes of one choice): either, both or neither can be open, and opening one never
closes, discards or replaces the other -- a generated lick and an uploaded exercise can be read side by side while
the same backing plays. Each has its own open button above them and its own close inside:

* Practice Melody: open = the song's (or jam's) ``practice_melody_library`` entry is shown on Backing. Pressing
  **Practice Melody** shows the melody that already exists for these settings, or makes the first one -- never a
  new one; only **Generate Another** does that. Collapsing its panel keeps the melody; **Remove Practice Melody**
  takes it off Backing until Practice Melody is pressed again (nothing is deleted: the alternatives and the kept
  melodies stay in the library).
* My Uploaded Melodies: open = :data:`UPLOADED_OPEN_KEY`. Its references are chosen per song and each one is its
  own collapsible panel. **Hide My Uploaded Melodies** closes the section and keeps the choice.

Practice Melody is drawn first (it has visual priority); the uploaded section follows it.

Page-follow priority (the one page controller in ``lead_sheet_page_follow`` applies it, unchanged):
Original Melody -> Practice Melody -> (any uploaded panel open: nothing moves) -> Lead Sheet -> nothing. So with
both open, the Practice Melody leads while it is expanded; collapse or remove it and the open uploaded page is the
one being read, so nothing scrolls under it.

An open uploaded panel is recognised by the controller from the page itself -- an open expander whose key starts
with :data:`UPLOADED_PANEL_KEY_PREFIX` -- so opening or closing one never needs a rerun and never touches audio.

Nothing here changes the song, the Practice Key, the instrument, Backing's settings or Key Cycling: a melody
choice is a reading choice. A key change or a Key Cycling step never opens or closes a section and never makes a
new melody.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Iterable, Mapping

#: The old single choice (2026-11-20). Read only to carry a session that had "uploaded" chosen over.
MODE_KEY = "backing_melody_mode"
MODE_PRACTICE = "practice"
MODE_UPLOADED = "uploaded"
MODES = (MODE_PRACTICE, MODE_UPLOADED)
MODE_LABELS = {MODE_PRACTICE: "Practice Melody", MODE_UPLOADED: "My Uploaded Melodies"}
#: The Practice page's own icons for the same two features (``music_feature_icons.FEATURE_ICONS``), so the
#: Backing buttons read exactly like Practice's "Generated Practice Melody" / "My Uploaded Melodies" panels.
MODE_ICON_CONCEPTS = {MODE_PRACTICE: "practice_melody_generated", MODE_UPLOADED: "practice_melody_uploaded"}
#: Set by a hand-off from elsewhere (Practice -> "Open on Backing Page"); applied before the sections are drawn.
PENDING_MODE_KEY = "_pending_backing_melody_mode"
#: Whether the My Uploaded Melodies section is open on Backing (this device's view; kept over a refresh).
UPLOADED_OPEN_KEY = "_backing_uploaded_section_open"
#: Button keys of the two section openers and the two closers.
OPEN_PRACTICE_BUTTON_KEY = "backing_melody_open_practice"
OPEN_UPLOADED_BUTTON_KEY = "backing_melody_open_uploaded"
REMOVE_PRACTICE_BUTTON_KEY = "backing_practice_melody_remove"
HIDE_UPLOADED_BUTTON_KEY = "backing_uploaded_section_hide"
#: Set when Practice Melody was pressed but this song / jam has no chords to write one over (its identity).
PRACTICE_UNAVAILABLE_KEY = "_backing_practice_melody_unavailable"

#: Per song: the uploaded references chosen for Backing ({owner identity: [document ids]}).
SELECTED_REFERENCES_KEY = "_backing_uploaded_reference_selection"
#: Widget key of the reference picker (one per song, so a song change never carries a choice across).
PICKER_KEY_PREFIX = "backing_upref_pick__"
#: The same choice on the Practice page. Both widgets only show and edit SELECTED_REFERENCES_KEY.
PRACTICE_PICKER_KEY_PREFIX = "practice_upref_pick__"
#: Panels to show open on Backing after "Open on Backing Page" on Practice: {"owner": identity, "ids": [...]}. Every
#: other visit starts with the panels closed: the first Backing draw marks it "shown", and the first run on any other
#: page then clears it (``note_studio_page``). Also cleared when Practice draws its panel again.
OPEN_FROM_PRACTICE_KEY = "_backing_uploaded_open_from_practice"
#: Each uploaded panel is ``st.expander(key=UPLOADED_PANEL_KEY_PREFIX + <id>)``; the controller looks for it.
UPLOADED_PANEL_KEY_PREFIX = "bk_upref_"
#: Practice page wording (user, 2026-11-26).
PRACTICE_PICKER_LABEL = "Choose sheet music to practice with Backing"
PRACTICE_PICKER_HELP = "Select one or more uploaded melodies to view while practicing with your backing track."
OPEN_ON_BACKING_TEXT = "Open on Backing Page"

__all__ = [
    "MODES",
    "MODE_KEY",
    "MODE_LABELS",
    "MODE_ICON_CONCEPTS",
    "mode_button_label",
    "MODE_PRACTICE",
    "MODE_UPLOADED",
    "OPEN_FROM_PRACTICE_KEY",
    "OPEN_ON_BACKING_TEXT",
    "OPEN_PRACTICE_BUTTON_KEY",
    "OPEN_UPLOADED_BUTTON_KEY",
    "HIDE_UPLOADED_BUTTON_KEY",
    "REMOVE_PRACTICE_BUTTON_KEY",
    "PRACTICE_PICKER_HELP",
    "PRACTICE_PICKER_LABEL",
    "PRACTICE_UNAVAILABLE_KEY",
    "UPLOADED_OPEN_KEY",
    "mark_open_from_practice_shown",
    "note_studio_page",
    "PENDING_MODE_KEY",
    "PRACTICE_PICKER_KEY_PREFIX",
    "SELECTED_REFERENCES_KEY",
    "UPLOADED_PANEL_KEY_PREFIX",
    "apply_pending_melody_mode",
    "open_practice_melody",
    "original_melody_sections",
    "owner_identity",
    "picker_key",
    "practice_picker_key",
    "remove_practice_melody",
    "render_active_song_reference_choice",
    "render_melody_section_buttons",
    "render_practice_reference_choice",
    "render_remove_practice_melody",
    "render_uploaded_references",
    "request_melody_mode",
    "selected_reference_ids",
    "set_selected_reference_ids",
    "set_uploaded_section_open",
    "uploaded_panel_key",
    "uploaded_section_open",
]


def _get(session: Any, key: str, default: Any = None) -> Any:
    try:
        return session.get(key, default)
    except Exception:
        return default


def _set(session: Any, key: str, value: Any) -> None:
    try:
        session[key] = value
    except Exception:
        pass


def _pop(session: Any, key: str) -> Any:
    try:
        return session.pop(key, None)
    except Exception:
        return None


def uploaded_section_open(session: Any) -> bool:
    """Whether My Uploaded Melodies is open on Backing. A session still carrying the old single choice set to
    "uploaded" counts as open (it had the section on screen)."""
    value = _get(session, UPLOADED_OPEN_KEY)
    if isinstance(value, bool):
        return value
    return str(_get(session, MODE_KEY) or "").strip() == MODE_UPLOADED


def set_uploaded_section_open(session: Any, value: bool) -> None:
    _set(session, UPLOADED_OPEN_KEY, bool(value))
    _pop(session, MODE_KEY)


def request_melody_mode(session: Any, mode: str) -> None:
    """Ask, from outside the Backing page, for that section to be open (applied before the sections are drawn).
    It never closes the other one."""
    if mode in MODES:
        _set(session, PENDING_MODE_KEY, mode)


def apply_pending_melody_mode(session: Any) -> str:
    """Call before drawing the sections: a pending request is applied once. Returns the section it asked for
    (``""`` when none). My Uploaded Melodies opens; Practice Melody needs nothing here -- its hand-off brings the
    melody, and that shows it."""
    pending = _pop(session, PENDING_MODE_KEY)
    if pending == MODE_UPLOADED:
        set_uploaded_section_open(session, True)
    return pending if pending in MODES else ""


def owner_identity(owner: Mapping[str, Any] | None) -> str:
    """One string for a song owner (``song_document_catalog.active_song_owner``): source + id."""
    if not owner:
        return ""
    parts = [str(owner.get(k) or "").strip() for k in ("source_type", "source_id")]
    ident = "|".join(p for p in parts if p)
    return ident or str(owner.get("song_title") or "").strip()


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", str(value or ""))[:80]


def picker_key(owner_ident: str) -> str:
    return PICKER_KEY_PREFIX + _slug(owner_ident)


def practice_picker_key(owner_ident: str) -> str:
    return PRACTICE_PICKER_KEY_PREFIX + _slug(owner_ident)


def uploaded_panel_key(document_id: str) -> str:
    return UPLOADED_PANEL_KEY_PREFIX + _slug(document_id)


def selected_reference_ids(session: Any, owner_ident: str, available: Iterable[str]) -> list[str]:
    """The song's chosen references that still exist, in the order they were chosen."""
    avail = [str(a) for a in available]
    table = _get(session, SELECTED_REFERENCES_KEY)
    chosen = table.get(owner_ident) if isinstance(table, dict) else None
    if not isinstance(chosen, list):
        return []
    return [d for d in (str(x) for x in chosen) if d in avail]


def set_selected_reference_ids(session: Any, owner_ident: str, ids: Iterable[str]) -> None:
    if not owner_ident:
        return
    table = _get(session, SELECTED_REFERENCES_KEY)
    table = dict(table) if isinstance(table, dict) else {}
    seen: list[str] = []
    for d in (str(x) for x in ids):
        if d and d not in seen:
            seen.append(d)
    table[owner_ident] = seen
    try:
        session[SELECTED_REFERENCES_KEY] = table
    except Exception:
        pass


def commit_reference_choice(
    session: Any, owner_ident: str, widget_key: str, available: Iterable[str], *, from_practice: bool = False
) -> None:
    """A picker changed: store its choice for this song. Choices whose document is not listed right now (a slow or
    partial library load) are kept; they only show once the document is back. Choosing on Practice also makes
    Backing open on My Uploaded Melodies the next time."""
    avail = [str(a) for a in available]
    picked = _get(session, widget_key)
    picked = [str(d) for d in picked if str(d) in avail] if isinstance(picked, (list, tuple)) else []
    table = _get(session, SELECTED_REFERENCES_KEY)
    before = table.get(owner_ident) if isinstance(table, dict) else None
    unlisted = [str(d) for d in before if str(d) not in avail] if isinstance(before, list) else []
    set_selected_reference_ids(session, owner_ident, picked + unlisted)
    if from_practice and picked:
        request_melody_mode(session, MODE_UPLOADED)


def _draw_reference_picker(
    st: Any, session: Any, *, owner_ident: str, rows: list, widget_key: str, label: str, from_practice: bool
) -> list[str]:
    """One multi-select over the song's references. The stored choice is the authority and is put into the widget
    before every draw, so a value left over from the other page or an old page snapshot never replaces it."""
    from song_document_catalog import summarize_document

    by_id = {str(r["document_id"]): r for r in rows}
    ids = list(by_id)
    shown = selected_reference_ids(session, owner_ident, ids)
    if _get(session, widget_key) != shown:
        try:
            session[widget_key] = list(shown)
        except Exception:
            pass
    labels = {d: summarize_document(by_id[d]) for d in ids}
    picked = st.multiselect(
        label, ids, key=widget_key, format_func=lambda d: labels.get(d, d),
        placeholder="Choose one or more of this song's uploaded melodies",
        on_change=commit_reference_choice, args=(session, owner_ident, widget_key, ids),
        kwargs={"from_practice": from_practice},
    )
    return [str(d) for d in (picked or []) if str(d) in by_id]


def open_in_backing(session: Any, owner_ident: str, ids: Iterable[str]) -> None:
    """Practice's "Open in Backing": My Uploaded Melodies, with the chosen panels open. A reading choice only."""
    request_melody_mode(session, MODE_UPLOADED)
    try:
        session[OPEN_FROM_PRACTICE_KEY] = {"owner": owner_ident, "ids": [str(d) for d in ids]}
    except Exception:
        pass


def panels_open_from_practice(session: Any, owner_ident: str) -> set[str]:
    stored = _get(session, OPEN_FROM_PRACTICE_KEY)
    if not isinstance(stored, Mapping) or str(stored.get("owner") or "") != owner_ident:
        return set()
    ids = stored.get("ids")
    return {str(d) for d in ids} if isinstance(ids, (list, tuple)) else set()


def mark_open_from_practice_shown(session: Any) -> None:
    """Backing drew the panels "Open in Backing" asked for: they belong to this visit only."""
    stored = _get(session, OPEN_FROM_PRACTICE_KEY)
    if isinstance(stored, Mapping) and not stored.get("shown"):
        try:
            session[OPEN_FROM_PRACTICE_KEY] = {**dict(stored), "shown": True}
        except Exception:
            pass


def note_studio_page(session: Any, page_id: str) -> None:
    """Every run, with the page being drawn. Leaving Backing ends the "Open in Backing" visit, so the next visit
    starts with every uploaded panel closed (one the musician closed must not come back open)."""
    if str(page_id or "") == "backing":
        return
    stored = _get(session, OPEN_FROM_PRACTICE_KEY)
    if isinstance(stored, Mapping) and stored.get("shown"):
        try:
            session.pop(OPEN_FROM_PRACTICE_KEY, None)
        except Exception:
            pass


def render_practice_reference_choice(st: Any, session: Any, *, owner: Mapping[str, Any], rows: list) -> bool:
    """Practice page: choose which of this song's references Backing shows. True when "Open on Backing Page" was
    pressed (the caller navigates)."""
    ident = owner_identity(owner)
    rows = [r for r in rows if str(r.get("document_id") or "")]
    if not ident or not rows:
        return False
    try:
        session.pop(OPEN_FROM_PRACTICE_KEY, None)
    except Exception:
        pass
    picked = _draw_reference_picker(
        st, session, owner_ident=ident, rows=rows, widget_key=practice_picker_key(ident),
        label=PRACTICE_PICKER_LABEL, from_practice=True,
    )
    st.caption(PRACTICE_PICKER_HELP)
    if not picked:
        return False
    if st.button(open_on_backing_label(), key=f"practice_upref_open__{_slug(ident)}"):
        open_in_backing(session, ident, picked)
        return True
    return False


def open_on_backing_label() -> str:
    """The Practice page's hand-off button: the Backing page's own headphones icon, then where it goes."""
    try:
        from music_feature_icons import feature_label
    except ImportError:
        return OPEN_ON_BACKING_TEXT
    return feature_label("backing", OPEN_ON_BACKING_TEXT)


def render_active_song_reference_choice(st: Any, session: Any) -> bool:
    """:func:`render_practice_reference_choice` for the active song; nothing is drawn while it has no references."""
    from song_document_catalog import active_song_owner, documents_for_owner

    owner = active_song_owner(session, st=st)
    return bool(owner) and render_practice_reference_choice(
        st, session, owner=owner, rows=documents_for_owner(owner, st=st)
    )


def _valid_events(events: Any) -> bool:
    if not isinstance(events, list) or not events:
        return False
    return all(isinstance(e, Mapping) and ("pitch" in e or "midi" in e or "rest" in e or "note" in e) for e in events)


def original_melody_sections(
    *,
    composition_doc: Mapping[str, Any] | None,
    song_data: Mapping[str, Any] | None,
) -> tuple[dict[str, list], str]:
    """The active song's synchronized Original Melody as ``({section label: [events]}, source)``.

    * A Composition: its composed melody (``composition_songs_bridge.composition_section_melody_events``).
    * Any other song: ``song_data["original_melody"]`` when it is a properly integrated, synchronized melody --
      ``{"synchronized": True, "sections": {label: [events]}}`` in the same event shape. Nothing else counts:
      no extraction, no transcription, and never an uploaded PDF.

    Returns ``({}, "")`` when the song has none.
    """
    if composition_doc:
        try:
            from composition_songs_bridge import composition_section_melody_events

            by_sec = composition_section_melody_events(dict(composition_doc))
        except Exception:
            by_sec = {}
        if by_sec:
            return dict(by_sec), "composition"
    om = (song_data or {}).get("original_melody") if isinstance(song_data, Mapping) else None
    if isinstance(om, Mapping) and om.get("synchronized") is True:
        secs = om.get("sections")
        if isinstance(secs, Mapping):
            out = {str(k): list(v) for k, v in secs.items() if _valid_events(v)}
            if out:
                return out, "song"
    return {}, ""


# ---- drawing (Backing page) ----------------------------------------------------------------------------------------

def mode_button_label(mode: str) -> str:
    """A mode's button text: the Practice page's icon for that feature, then the unchanged label."""
    text = MODE_LABELS.get(mode, mode)
    try:
        from music_feature_icons import feature_label
    except ImportError:
        return text
    return feature_label(MODE_ICON_CONCEPTS.get(mode, ""), text)


def _icon_label(concept: str, text: str) -> str:
    try:
        from music_feature_icons import feature_label
    except ImportError:
        return text
    return feature_label(concept, text)


def _action_label(action: str, text: str) -> str:
    try:
        from music_feature_icons import action_label
    except ImportError:
        return text
    return action_label(action, text)


def open_practice_melody(session: Any, identity: str, choose: Callable[..., Any] | None) -> bool:
    """**Practice Melody** pressed: show this song's / jam's melody, expanded -- the one that already exists for
    these settings, or the first one when there is none. Never a new alternative: ``choose()`` without arguments
    returns the current one (only Generate Another asks for another). False when there are no chords to write one
    over; the page then says so."""
    melody = None
    if identity and choose is not None:
        try:
            melody = choose()
        except Exception:
            melody = None
    if melody is None:
        _set(session, PRACTICE_UNAVAILABLE_KEY, str(identity or ""))
        return False
    _pop(session, PRACTICE_UNAVAILABLE_KEY)
    try:
        import practice_melody_library as library
        from melody_panel_visibility import PRACTICE, show

        library.show_on_backing(session, identity)
        show(session, PRACTICE, identity)
    except Exception:
        return False
    return True


def remove_practice_melody(session: Any, identity: str) -> None:
    """**Remove Practice Melody**: off the Backing page until Practice Melody is pressed again. Nothing is deleted --
    the song's alternatives and kept melodies stay in the library, and no uploaded reference, file or song changes."""
    try:
        import practice_melody_library as library

        library.hide_on_backing(session, identity)
    except Exception:
        pass
    try:
        from practice_melody_backing import BACKING_MELODY_SONG_IDENTITY_KEY, clear_backing_practice_melody

        if str(_get(session, BACKING_MELODY_SONG_IDENTITY_KEY) or "") == str(identity or ""):
            clear_backing_practice_melody(session)  # the copy handed over from Practice, shown for this song
    except Exception:
        pass
    _pop(session, PRACTICE_UNAVAILABLE_KEY)


def render_melody_section_buttons(
    st: Any, session: Any, *, identity: str, choose: Callable[..., Any] | None, practice_open: bool
) -> None:
    """The two openers, side by side (stacked on a phone). Each opens its own section and never closes the other; a
    section that is open shows its button highlighted. Pressing Practice Melody while it is open only expands it."""
    apply_pending_melody_mode(session)
    up_open = uploaded_section_open(session)
    cols = st.columns(2)
    with cols[0]:
        st.button(
            mode_button_label(MODE_PRACTICE), key=OPEN_PRACTICE_BUTTON_KEY, use_container_width=True,
            type="primary" if practice_open else "secondary",
            on_click=open_practice_melody, args=(session, identity, choose),
        )
    with cols[1]:
        st.button(
            mode_button_label(MODE_UPLOADED), key=OPEN_UPLOADED_BUTTON_KEY, use_container_width=True,
            type="primary" if up_open else "secondary",
            on_click=set_uploaded_section_open, args=(session, True),
        )
    if not practice_open and identity and str(_get(session, PRACTICE_UNAVAILABLE_KEY) or "") == identity:
        st.info("There is no structured chord/section data here yet, so a Practice Melody can't be made for it.")


def render_remove_practice_melody(st: Any, session: Any, identity: str) -> None:
    """Inside the Practice Melody panel. Collapsing the panel keeps the melody; this takes it off the page."""
    st.button(
        _action_label("cancel", "Remove Practice Melody"), key=REMOVE_PRACTICE_BUTTON_KEY,
        on_click=remove_practice_melody, args=(session, identity),
    )
    st.caption("Takes this melody off the Backing page; nothing is deleted. Press Practice Melody to bring it back.")


def _reference_title(row: Mapping[str, Any]) -> str:
    for k in ("title", "name", "filename"):
        v = str(row.get(k) or "").strip()
        if v:
            return v
    return "Reference"


def render_uploaded_references(st: Any, session: Any) -> int:
    """The My Uploaded Melodies section (only while it is open): pick any of the song's saved references, one
    collapsible panel each (closed, except the ones just sent here with Practice's "Open on Backing Page"), and Hide
    to close the section (the choice is kept). Returns how many panels are drawn. Read by hand only: no
    highlighting, no page following."""
    if not uploaded_section_open(session):
        return 0
    with st.container(border=True, key="bk_uploaded_section"):
        st.markdown(f"**{mode_button_label(MODE_UPLOADED)}**")
        drawn = _render_uploaded_references_body(st, session)
        st.button("Hide My Uploaded Melodies", key=HIDE_UPLOADED_BUTTON_KEY,
                  on_click=set_uploaded_section_open, args=(session, False))
    return drawn


def _render_uploaded_references_body(st: Any, session: Any) -> int:
    try:
        from song_document_catalog import active_song_owner, documents_for_owner
        from song_document_panel import render_song_document_reference
    except ImportError:
        return 0
    owner = active_song_owner(session, st=st)
    if not owner:
        st.caption("Open a song to use its uploaded melodies here.")
        return 0
    rows = [r for r in documents_for_owner(owner, st=st) if str(r.get("document_id") or "")]
    if not rows:
        st.caption(
            "No uploaded melodies for this song yet. Add PDFs or photos in Practice → Chart & Melody → My Uploaded "
            "Melodies; they appear here to read while the backing plays."
        )
        return 0
    ident = owner_identity(owner)
    by_id = {str(r["document_id"]): r for r in rows}
    picked = _draw_reference_picker(
        st, session, owner_ident=ident, rows=rows, widget_key=picker_key(ident),
        label="Uploaded melodies to show", from_practice=False,
    )
    if not picked:
        return 0
    st.caption(
        "Read these by hand. While one is open the page doesn't scroll by itself (unless a melody staff above is "
        "open and playing); close them all and the Lead Sheet follows the music again."
    )
    opened = panels_open_from_practice(session, ident)
    if opened:
        mark_open_from_practice_shown(session)
    for did in picked:
        row = by_id[did]
        label = _icon_label(MODE_ICON_CONCEPTS[MODE_UPLOADED], _reference_title(row))
        with st.expander(label, expanded=did in opened, key=uploaded_panel_key(did)):
            render_song_document_reference(st, row, namespace="bk_upref_doc_")
    return len(picked)
