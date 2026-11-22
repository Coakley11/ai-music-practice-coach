"""Backing page melodies: which displays exist, which one may lead the page (user rules 2026-11-20).

Four displays can sit under the Backing Lead Sheet:

* **Original Melody** -- the song's own synchronized melody. Today that is a Composition's composed melody; the
  hook :func:`original_melody_sections` also accepts a future, properly integrated synchronized melody for a
  Catalog or Custom song (``song_data["original_melody"]``, the same per-section event shape Composition uses).
  An arbitrary uploaded PDF is never an Original Melody. When open it always leads the page.
* **Practice Melody** -- the generated melody to play along with.
* **My Uploaded Melodies** -- the musician's own PDFs, read by hand. They never follow the music.
* **Lead Sheet**.

Practice Melody and My Uploaded Melodies are two **modes** of one choice; only one is ever active, and only the
active mode's panels are drawn, so a hidden display can never take part in scrolling. Original Melody and the
Lead Sheet coexist with either mode.

Page-follow priority (the one page controller in ``lead_sheet_page_follow`` applies it):

* Practice Melody mode: Original Melody -> Practice Melody -> Lead Sheet -> nothing.
* My Uploaded Melodies mode: Original Melody -> (any uploaded panel open: nothing) -> Lead Sheet -> nothing.

An open uploaded panel is recognised by the controller from the page itself -- an open expander whose key starts
with :data:`UPLOADED_PANEL_KEY_PREFIX` -- so opening or closing one never needs a rerun and never touches audio.

Nothing here changes the song, the Practice Key, the instrument, Backing's settings or Key Cycling: a melody
choice is a reading choice.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

MODE_KEY = "backing_melody_mode"
MODE_PRACTICE = "practice"
MODE_UPLOADED = "uploaded"
MODES = (MODE_PRACTICE, MODE_UPLOADED)
MODE_LABELS = {MODE_PRACTICE: "Practice Melody", MODE_UPLOADED: "My Uploaded Melodies"}
#: Set by a hand-off from elsewhere (Practice -> Practice with Backing); applied before the widget exists.
PENDING_MODE_KEY = "_pending_backing_melody_mode"

#: Per song: the uploaded references chosen for Backing ({owner identity: [document ids]}).
SELECTED_REFERENCES_KEY = "_backing_uploaded_reference_selection"
#: Widget key of the reference picker (one per song, so a song change never carries a choice across).
PICKER_KEY_PREFIX = "backing_upref_pick__"
#: Each uploaded panel is ``st.expander(key=UPLOADED_PANEL_KEY_PREFIX + <id>)``; the controller looks for it.
UPLOADED_PANEL_KEY_PREFIX = "bk_upref_"

__all__ = [
    "MODES",
    "MODE_KEY",
    "MODE_LABELS",
    "MODE_PRACTICE",
    "MODE_UPLOADED",
    "PENDING_MODE_KEY",
    "SELECTED_REFERENCES_KEY",
    "UPLOADED_PANEL_KEY_PREFIX",
    "apply_pending_melody_mode",
    "melody_mode",
    "original_melody_sections",
    "owner_identity",
    "picker_key",
    "request_melody_mode",
    "selected_reference_ids",
    "set_selected_reference_ids",
    "uploaded_panel_key",
]


def _get(session: Any, key: str, default: Any = None) -> Any:
    try:
        return session.get(key, default)
    except Exception:
        return default


def melody_mode(session: Any) -> str:
    """The active mode; Practice Melody unless My Uploaded Melodies was chosen."""
    mode = str(_get(session, MODE_KEY) or "").strip()
    return mode if mode in MODES else MODE_PRACTICE


def request_melody_mode(session: Any, mode: str) -> None:
    """Ask for ``mode`` from outside the Backing page (applied before the selector is drawn)."""
    if mode in MODES:
        try:
            session[PENDING_MODE_KEY] = mode
        except Exception:
            pass


def apply_pending_melody_mode(session: Any) -> str:
    """Call before drawing the selector: a pending request wins once, then the mode is the widget's."""
    try:
        pending = session.pop(PENDING_MODE_KEY, None)
    except Exception:
        pending = None
    if pending in MODES:
        try:
            session[MODE_KEY] = pending
            session[f"_segmented_last::{MODE_KEY}"] = pending
        except Exception:
            pass
    return melody_mode(session)


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

def render_melody_mode_selector(st: Any, session: Any) -> str:
    """The Practice Melody / My Uploaded Melodies choice; returns the active mode."""
    apply_pending_melody_mode(session)
    try:
        from segmented_selector import render_segmented_selector

        picked = render_segmented_selector(
            st, session, label="Melody", options=list(MODES), key=MODE_KEY,
            format_func=lambda m: MODE_LABELS.get(m, m),
        )
    except ImportError:
        picked = st.radio("Melody", list(MODES), key=MODE_KEY, horizontal=True,
                          format_func=lambda m: MODE_LABELS.get(m, m), label_visibility="collapsed")
    return picked if picked in MODES else MODE_PRACTICE


def _reference_title(row: Mapping[str, Any]) -> str:
    for k in ("title", "name", "filename"):
        v = str(row.get(k) or "").strip()
        if v:
            return v
    return "Reference"


def render_uploaded_references(st: Any, session: Any) -> int:
    """My Uploaded Melodies mode: pick any of the song's saved references, one collapsible panel each (all start
    closed). Returns how many panels are drawn. Read by hand only: no highlighting, no page following."""
    try:
        from song_document_catalog import active_song_owner, documents_for_owner, summarize_document
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
    ids = list(by_id)
    chosen = selected_reference_ids(session, ident, ids)
    pk = picker_key(ident)
    current = _get(session, pk)
    if not isinstance(current, list) or any(str(c) not in ids for c in current):
        try:
            session[pk] = list(chosen)
        except Exception:
            pass
    labels = {d: summarize_document(by_id[d]) for d in ids}
    picked = st.multiselect(
        "Uploaded melodies to show", ids, key=pk, format_func=lambda d: labels.get(d, d),
        placeholder="Choose one or more of this song's uploaded melodies",
    )
    picked = [str(d) for d in (picked or []) if str(d) in by_id]
    set_selected_reference_ids(session, ident, picked)
    if not picked:
        return 0
    st.caption(
        "Read these by hand. While one is open the page doesn't scroll by itself (unless the Original Melody is "
        "open); close them all and the Lead Sheet follows the music again."
    )
    for did in picked:
        row = by_id[did]
        with st.expander(f"📄 {_reference_title(row)}", expanded=False, key=uploaded_panel_key(did)):
            render_song_document_reference(st, row, namespace="bk_upref_doc_")
    return len(picked)
