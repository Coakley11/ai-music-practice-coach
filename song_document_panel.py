"""My Uploaded Melodies - the Practice-page panel for a song's own PDF references.

Slices 2 and 3: managing the documents, and reading one while you play.

The panel is deliberately small. It owns nothing but its own widgets: every document it
lists comes from ``song_document_catalog``, and the only session keys it writes begin
``song_doc_``. It never touches the Practice Key, the instrument, the active song or any
backing setting - picking a reference is a reading choice, not a musical one, and a key
*tag* on a document is the musician's note about the page, not an instruction to the app.

Reading a PDF in a Streamlit page has three plausible mechanisms and they are not equally
reliable. Rendering each page to an image server-side (PyMuPDF) works in every browser
including mobile Safari, gives real page-by-page navigation, and hands the browser a PNG
rather than a file, so no object URL and no private link ever exists. That is the primary
path. ``st.pdf`` is the fallback where PyMuPDF is missing, and a download button is the
last resort; none of the three exposes a storage URL.

Rerun cost is the other half of slice 3. Streamlit re-runs the whole script on every
interaction, so both the fetch and the page render are cached on the document's content
hash - a page is decoded once per (document, page, width), not once per click.
"""

from __future__ import annotations

from typing import Any

__all__ = ["render_song_documents_panel"]

KEY_PREFIX = "song_doc_"
SELECTED_KEY = f"{KEY_PREFIX}selected"
CONFIRM_KEY = f"{KEY_PREFIX}confirm_delete"
PAGE_KEY = f"{KEY_PREFIX}page"
UPLOAD_KEY = f"{KEY_PREFIX}upload"
NOTICE_KEY = f"{KEY_PREFIX}notice"

# Wide enough to read a stave on a laptop, small enough not to cost a megabyte a page.
_RENDER_WIDTH_DESKTOP = 1100


def _status_line(row: dict[str, Any]) -> tuple[str, str]:
    """``(severity, message)`` for where this document actually is.

    A document that only reached this device must say so. Showing "Saved" for a cloud
    upload that failed is the one thing this panel must never do.
    """
    from media_state import (
        DOCUMENT_STORAGE_CLOUD,
        DOCUMENT_STORAGE_FAILED,
        DOCUMENT_STORAGE_LOCAL_ONLY,
        DOCUMENT_STORAGE_MISSING,
    )

    status = str(row.get("storage_status") or "")
    detail = str(row.get("storage_error") or "").strip()
    if status == DOCUMENT_STORAGE_CLOUD:
        return "ok", "Saved to your private storage."
    if status == DOCUMENT_STORAGE_LOCAL_ONLY:
        extra = f" ({detail})" if detail and detail != "cloud_disabled" else ""
        return "warn", (
            "Saved on this device only - not yet copied to your private cloud "
            f"storage, so it will not follow you to another device yet{extra}."
        )
    if status == DOCUMENT_STORAGE_MISSING:
        return "error", "The file for this reference is missing from storage."
    if status == DOCUMENT_STORAGE_FAILED:
        return "error", f"This reference was not saved{f': {detail}' if detail else ''}."
    return "warn", "Save status unknown."


def _page_count(data: bytes, fallback: Any) -> int:
    try:
        import pymupdf

        with pymupdf.open(stream=data, filetype="pdf") as doc:
            return int(doc.page_count) or 1
    except Exception:
        try:
            return max(1, int(fallback))
        except Exception:
            return 1


def _render_page_png(data: bytes, page_index: int, width: int) -> bytes | None:
    """One page as a PNG, or ``None`` when PyMuPDF cannot be used."""
    try:
        import pymupdf

        with pymupdf.open(stream=data, filetype="pdf") as doc:
            index = max(0, min(int(page_index), doc.page_count - 1))
            page = doc.load_page(index)
            zoom = max(0.5, float(width) / max(1.0, page.rect.width))
            pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
            return pix.tobytes("png")
    except Exception:
        return None


def _cached_helpers(st: Any):
    """Build the cached fetch/render pair once, keyed on content rather than identity.

    ``document_id`` alone is not a safe cache key - a document can be replaced - so the
    SHA-256 the catalog already stores is part of every key.
    """

    @st.cache_data(show_spinner=False, max_entries=8)
    def fetch(document_id: str, digest: str) -> bytes | None:
        from song_document_catalog import load_song_document_bytes

        data, _err = load_song_document_bytes(document_id, st=st)
        return data

    @st.cache_data(show_spinner=False, max_entries=24)
    def render(document_id: str, digest: str, page_index: int, width: int) -> bytes | None:
        data = fetch(document_id, digest)
        if not data:
            return None
        return _render_page_png(data, page_index, width)

    @st.cache_data(show_spinner=False, max_entries=8)
    def pages(document_id: str, digest: str, fallback: int) -> int:
        data = fetch(document_id, digest)
        if not data:
            return max(1, int(fallback or 1))
        return _page_count(data, fallback)

    return fetch, render, pages


def _upload_form(st: Any, session: Any, owner: dict) -> None:
    from song_document_catalog import save_song_document

    with st.form(f"{KEY_PREFIX}form", clear_on_submit=True):
        files = st.file_uploader(
            "Add PDFs for this song",
            type=["pdf"],
            accept_multiple_files=True,
            key=UPLOAD_KEY,
            help="Licks, exercises, sheet music, handwritten pages, your own notes.",
        )
        cols = st.columns([2, 1, 1])
        name = cols[0].text_input(
            "Name (optional)", key=f"{KEY_PREFIX}new_title",
            placeholder="e.g. Bebop lick over ii-V",
        )
        instrument_tag = cols[1].text_input(
            "Instrument tag", key=f"{KEY_PREFIX}new_instrument",
            placeholder="Alto Sax",
        )
        key_tag = cols[2].text_input(
            "Key tag", key=f"{KEY_PREFIX}new_key", placeholder="Eb",
            help="A label on the document. It does not change your Practice Key.",
        )
        if not st.form_submit_button("Save to this song", use_container_width=True):
            return
        if not files:
            st.warning("Choose at least one PDF first.")
            return
        saved, failed, local_only = 0, [], 0
        for i, item in enumerate(files):
            try:
                data = item.getvalue()
            except Exception:
                data = None
            title = (name.strip() or getattr(item, "name", "") or "").strip()
            if len(files) > 1 and name.strip():
                title = f"{name.strip()} ({i + 1})"
            result = save_song_document(
                session, data, filename=getattr(item, "name", ""), title=title,
                instrument_tag=instrument_tag, key_tag=key_tag, st=st,
            )
            if result.get("ok"):
                saved += 1
                if result.get("storage_status") == "local_only":
                    local_only += 1
                st.session_state[SELECTED_KEY] = result["row"]["document_id"]
            else:
                failed.append((getattr(item, "name", "file"), result.get("error")))
        notice = []
        if saved:
            notice.append(("warn" if local_only else "ok",
                           f"Saved {saved} reference{'s' if saved != 1 else ''}"
                           + (f", {local_only} on this device only" if local_only else "")
                           + "."))
        for filename, error in failed:
            notice.append(("error", f"{filename}: {_explain(error)}"))
        st.session_state[NOTICE_KEY] = notice
        st.rerun()


def _explain(error: Any) -> str:
    return {
        "not_a_pdf": "that file is not a PDF.",
        "pdf_truncated": "that PDF looks incomplete - try uploading it again.",
        "document_too_large": "that file is too large.",
        "missing_document": "the file was empty.",
        "empty_document": "the file was empty.",
        "invalid_document_type": "that file could not be read.",
        "unknown_song": "open a song first, so the reference has somewhere to live.",
    }.get(str(error or ""), f"could not be saved ({error}).")


def _show_notice(st: Any) -> None:
    for severity, message in st.session_state.pop(NOTICE_KEY, []) or []:
        {"ok": st.success, "warn": st.warning, "error": st.error}.get(
            severity, st.info)(message)


def _manage(st: Any, row: dict) -> None:
    """Rename, retag and delete, for the one selected document."""
    from song_document_catalog import delete_song_document, rename_song_document, retag_song_document

    did = str(row.get("document_id") or "")
    with st.expander("Rename, tag or delete", expanded=False):
        cols = st.columns([2, 1, 1, 1])
        title = cols[0].text_input("Name", value=str(row.get("title") or ""),
                                   key=f"{KEY_PREFIX}edit_title_{did}")
        inst = cols[1].text_input("Instrument", value=str(row.get("instrument_tag") or ""),
                                  key=f"{KEY_PREFIX}edit_inst_{did}")
        ktag = cols[2].text_input("Key tag", value=str(row.get("key_tag") or ""),
                                  key=f"{KEY_PREFIX}edit_key_{did}")
        if cols[3].button("Save changes", key=f"{KEY_PREFIX}save_{did}",
                          use_container_width=True):
            ok = True
            if title.strip() and title.strip() != str(row.get("title") or ""):
                ok = bool(rename_song_document(did, title, st=st).get("ok")) and ok
            if (inst != str(row.get("instrument_tag") or "")
                    or ktag != str(row.get("key_tag") or "")):
                ok = bool(retag_song_document(
                    did, instrument_tag=inst, key_tag=ktag, st=st).get("ok")) and ok
            st.session_state[NOTICE_KEY] = [
                ("ok", "Updated.") if ok else ("error", "Could not save those changes.")
            ]
            st.rerun()

        st.caption("Deleting removes this reference and its file. It cannot be undone.")
        if st.session_state.get(CONFIRM_KEY) == did:
            confirm = st.columns(2)
            if confirm[0].button("Delete permanently", key=f"{KEY_PREFIX}del_yes_{did}",
                                 type="primary", use_container_width=True):
                result = delete_song_document(did, st=st)
                st.session_state[CONFIRM_KEY] = None
                st.session_state[SELECTED_KEY] = None
                st.session_state[NOTICE_KEY] = [
                    ("ok", "Deleted.") if result.get("ok")
                    else ("error", f"Could not delete: {result.get('error')}")
                ]
                st.rerun()
            if confirm[1].button("Keep it", key=f"{KEY_PREFIX}del_no_{did}",
                                 use_container_width=True):
                st.session_state[CONFIRM_KEY] = None
                st.rerun()
        elif st.button("Delete this reference", key=f"{KEY_PREFIX}del_{did}"):
            st.session_state[CONFIRM_KEY] = did
            st.rerun()


def _preview(st: Any, row: dict, *, compact: bool) -> None:
    """The document itself, a page at a time."""
    did = str(row.get("document_id") or "")
    digest = str(row.get("sha256") or "")
    fetch, render, pages = _cached_helpers(st)

    total = pages(did, digest, row.get("page_count") or 1)
    page = int(st.session_state.get(PAGE_KEY) or 0)
    page = max(0, min(page, total - 1))

    if total > 1:
        nav = st.columns([1, 2, 1])
        if nav[0].button("Previous", key=f"{KEY_PREFIX}prev", disabled=page <= 0,
                         use_container_width=True):
            st.session_state[PAGE_KEY] = page - 1
            st.rerun()
        nav[1].markdown(
            f"<div style='text-align:center;padding-top:0.45rem'>Page {page + 1} "
            f"of {total}</div>", unsafe_allow_html=True)
        if nav[2].button("Next", key=f"{KEY_PREFIX}next", disabled=page >= total - 1,
                         use_container_width=True):
            st.session_state[PAGE_KEY] = page + 1
            st.rerun()

    width = 760 if compact else _RENDER_WIDTH_DESKTOP
    png = render(did, digest, page, width)
    if png:
        st.image(png, use_container_width=True)
        return

    data = fetch(did, digest)
    if not data:
        st.error("That reference could not be loaded from storage.")
        return
    # No page renderer available: hand the browser the document itself. Still bytes,
    # still no storage URL.
    try:
        st.pdf(data, height=520 if compact else 760)
        return
    except Exception:
        pass
    st.info("This browser cannot display the PDF inline. Download it to read it.")
    st.download_button("Download this reference", data=data,
                       file_name=str(row.get("filename") or "reference.pdf"),
                       mime="application/pdf", key=f"{KEY_PREFIX}dl_{did}")


def render_song_documents_panel(st: Any, session: Any, *, compact: bool = False) -> None:
    """Draw the whole panel. Safe to call with no active song."""
    from song_document_catalog import (
        active_song_owner,
        documents_for_owner,
        summarize_document,
    )

    _show_notice(st)
    owner = active_song_owner(session, st=st)
    if not owner:
        st.info(
            "Open a song first. References are saved against the song they belong to, "
            "so a Catalog song and a Custom song of the same name keep their own."
        )
        return

    rows = documents_for_owner(owner, st=st)
    _upload_form(st, session, owner)

    if not rows:
        st.caption("No references saved for this song yet.")
        return

    labels = {str(r.get("document_id")): summarize_document(r) for r in rows}
    ids = list(labels)
    current = st.session_state.get(SELECTED_KEY)
    if current not in ids:
        current = ids[0]
    chosen = st.selectbox(
        "Saved references",
        ids,
        index=ids.index(current),
        format_func=lambda d: labels.get(d, d),
        key=f"{KEY_PREFIX}picker",
    )
    if chosen != st.session_state.get(SELECTED_KEY):
        st.session_state[SELECTED_KEY] = chosen
        st.session_state[PAGE_KEY] = 0

    row = next((r for r in rows if str(r.get("document_id")) == chosen), None)
    if row is None:
        return

    severity, message = _status_line(row)
    {"ok": st.caption, "warn": st.warning, "error": st.error}.get(
        severity, st.caption)(message)
    _manage(st, row)
    _preview(st, row, compact=compact)
