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

__all__ = ["render_song_document_reference", "render_song_documents_panel"]

KEY_PREFIX = "song_doc_"
SELECTED_KEY = f"{KEY_PREFIX}selected"
CONFIRM_KEY = f"{KEY_PREFIX}confirm_delete"
PAGE_KEY = f"{KEY_PREFIX}page"
UPLOAD_KEY = f"{KEY_PREFIX}upload"
NOTICE_KEY = f"{KEY_PREFIX}notice"
PICKER_KEY = f"{KEY_PREFIX}picker"
#: The PDF page buttons: the words the musician sees, plus an invisible word joiner (see _preview).
PAGE_PREVIOUS_LABEL = "Previous\u2060"
PAGE_NEXT_LABEL = "Next\u2060"

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
    """One page as a PNG, or ``None`` when PyMuPDF cannot or should not render it.

    The zoom is capped by a pixel budget as well as by the requested width. A PDF may
    declare a page metres across, and rendering that at the width a laptop asked for
    would allocate gigabytes on the server - the one machine here that cannot simply
    refuse. A malformed page raises, and raising is handled: the caller falls back.
    """
    from upload_media import DOCUMENT_MAX_RENDER_PIXELS

    try:
        import pymupdf

        with pymupdf.open(stream=data, filetype="pdf") as doc:
            index = max(0, min(int(page_index), doc.page_count - 1))
            page = doc.load_page(index)
            page_w = max(1.0, float(page.rect.width))
            page_h = max(1.0, float(page.rect.height))
            zoom = max(0.2, float(width) / page_w)
            budget = (DOCUMENT_MAX_RENDER_PIXELS / (page_w * page_h)) ** 0.5
            zoom = min(zoom, max(0.1, budget))
            pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
            return pix.tobytes("png")
    except Exception:
        return None


def _render_image_jpeg(data: bytes, mime: str, width: int) -> bytes | None:
    """A photographed page drawn for reading: upright, undistorted, at most ``width`` wide and within the
    render budget. ``None`` when it cannot be drawn here (a HEIC photo without ``pillow-heif``, or an
    undecodable file); the caller falls back.

    Phones store a portrait page as a landscape image plus an EXIF "rotate" note, so the note is applied
    (``exif_transpose``) or the music lies on its side. The aspect ratio is never changed. The stored file
    is untouched - this is only the picture the reader sees.
    """
    import io

    from upload_media import DOCUMENT_MAX_RENDER_PIXELS, heif_support

    try:
        from PIL import Image, ImageOps
    except ImportError:
        return None
    if str(mime).lower() in ("image/heic", "image/heif") and not heif_support():
        return None
    try:
        with Image.open(io.BytesIO(data)) as im:
            if im.format == "JPEG":
                im.draft("RGB", (max(1, int(width)), max(1, int(width))))
            im = ImageOps.exif_transpose(im)
            if im.mode not in ("RGB", "L"):
                bg = Image.new("RGB", im.size, (255, 255, 255))
                rgba = im.convert("RGBA")
                bg.paste(rgba, mask=rgba.split()[-1])
                im = bg
            w, h = im.size
            scale = min(1.0, float(width) / max(1, w), (DOCUMENT_MAX_RENDER_PIXELS / max(1, w * h)) ** 0.5)
            if scale < 1.0:
                im = im.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS)
            buf = io.BytesIO()
            im.convert("RGB").save(buf, "JPEG", quality=88, optimize=True)
            return buf.getvalue()
    except Exception:
        return None


#: Reading size (2026-11-22, Slice 1): Fit shows the whole page; Large / Extra large draw it wider than the
#: screen and let it scroll sideways, so notation photographed on a phone can be read on a phone.
ZOOM_KEY = f"{KEY_PREFIX}zoom"
ZOOM_LEVELS = {"Fit": 1.0, "Large": 1.6, "Extra large": 2.2}


def _reader_slug(reader: str) -> str:
    import re as _re

    return _re.sub(r"[^A-Za-z0-9_-]", "_", str(reader or "main"))[-60:] or "main"


def _zoom_choice(st: Any, reader: str) -> float:
    if st.session_state.get(ZOOM_KEY + _reader_slug(reader)) not in ZOOM_LEVELS:
        st.session_state[ZOOM_KEY + _reader_slug(reader)] = "Fit"
    choice = st.radio("Reading size", list(ZOOM_LEVELS), key=ZOOM_KEY + _reader_slug(reader), horizontal=True,
                      label_visibility="collapsed")
    return float(ZOOM_LEVELS.get(str(choice), 1.0))


def _show_page_image(st: Any, img: bytes, zoom: float, reader: str) -> None:
    """Fit: the page fills the panel's width. Larger: it is drawn that much wider than the panel inside a
    box that scrolls sideways (and pinch-zoom still works on a phone). Never stretched out of shape."""
    if zoom <= 1.0:
        st.image(img, use_container_width=True)
        return
    box = f"{KEY_PREFIX}zoombox_{_reader_slug(reader)}"
    pct = int(round(zoom * 100))
    st.markdown(
        f"<style>.st-key-{box}{{overflow-x:auto!important;overflow-y:hidden;-webkit-overflow-scrolling:touch;}}"
        # Streamlit 1.61 puts the image block in a flex row, where it would shrink back to the panel's width: it
        # must not shrink, and only this outer block is widened (its inner container fills it, once).
        f".st-key-{box} [data-testid='stImage']"
        f"{{flex:0 0 auto!important;width:{pct}%!important;min-width:{pct}%!important;max-width:none!important;"
        f"align-self:flex-start!important;margin-left:0!important;}}"
        # Its wrapper centres it, which pushed the left part of a wider page out of reach of the scroll.
        f".st-key-{box} :has(> [data-testid='stImage'])"
        f"{{justify-content:flex-start!important;align-items:flex-start!important;}}"
        f".st-key-{box} [data-testid='stImageContainer']"
        f"{{flex:1 0 100%!important;width:100%!important;max-width:none!important;}}"
        f".st-key-{box} img{{width:100%!important;max-width:none!important;height:auto!important;}}</style>",
        unsafe_allow_html=True,
    )
    with st.container(key=box):
        st.image(img, use_container_width=True)


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

    @st.cache_data(show_spinner=False, max_entries=24)
    def render_image(document_id: str, digest: str, mime: str, width: int) -> bytes | None:
        data = fetch(document_id, digest)
        if not data:
            return None
        return _render_image_jpeg(data, mime, width)

    @st.cache_data(show_spinner=False, max_entries=8)
    def pages(document_id: str, digest: str, fallback: int) -> int:
        data = fetch(document_id, digest)
        if not data:
            return max(1, int(fallback or 1))
        return _page_count(data, fallback)

    return fetch, render, pages, render_image


def _upload_form(st: Any, session: Any, owner: dict) -> None:
    from song_document_catalog import save_song_document

    from upload_media import (
        DOCUMENT_MAX_SIZE_MB,
        UPLOAD_DOCUMENT_FILE_TYPES,
        document_limit_caption,
    )

    with st.form(f"{KEY_PREFIX}form", clear_on_submit=True):
        files = st.file_uploader(
            "Add sheet music for this song (PDF or photo)",
            type=list(UPLOAD_DOCUMENT_FILE_TYPES),
            accept_multiple_files=True,
            key=UPLOAD_KEY,
            # Streamlit prints its own size hint inside the drop zone, and without this it quotes
            # server.maxUploadSize - so the control said "500MB per file" while the real document
            # limit was 25, and now 50. Two contradictory numbers in one panel is worse than one
            # wrong one, and this is the only way to make Streamlit's own text agree with the rule.
            max_upload_size=DOCUMENT_MAX_SIZE_MB,
            help="Licks, exercises, sheet music, handwritten pages, your own notes.",
        )
        # The limit, before a file is chosen. It was stated nowhere, so a refusal looked arbitrary -
        # and the only size the musician could see anywhere was the 500 MB recording limit, which
        # has nothing to do with documents.
        st.caption(document_limit_caption())
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
        try:
            from music_feature_icons import action_label

            _save_label = action_label("save", "Save to this song")
        except ImportError:
            _save_label = "Save to this song"
        if not st.form_submit_button(_save_label, use_container_width=True):
            return
        if not files:
            st.warning("Choose at least one file first.")
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
                # The byte count travels with the failure: a size refusal must be able to say how
                # large the file actually was, and this loop is the last place that knows.
                failed.append((
                    getattr(item, "name", "file"),
                    result.get("error"),
                    len(data) if isinstance(data, (bytes, bytearray)) else 0,
                ))
        notice = []
        if saved:
            notice.append(("warn" if local_only else "ok",
                           f"Saved {saved} reference{'s' if saved != 1 else ''}"
                           + (f", {local_only} on this device only" if local_only else "")
                           + "."))
        for filename, error, size in failed:
            notice.append(("error", _explain_failure(filename, error, size)))
        st.session_state[NOTICE_KEY] = notice
        st.rerun()


def _explain_failure(filename: Any, error: Any, size_bytes: Any = 0) -> str:
    """One refusal the musician can act on.

    A size refusal gets BOTH numbers - their file's size and the configured limit - because
    "that file is too large." never said how large, what the limit was, or whether they were close.
    Everything else keeps its existing sentence, prefixed with the filename as before.
    """
    code = str(error or "")
    who = str(filename or "file")
    if code == "document_too_large":
        try:
            from upload_media import document_too_large_message

            return document_too_large_message(size_bytes, filename=who)
        except ImportError:
            pass
    return f"{who}: {_explain(code)}"


def _explain(error: Any) -> str:
    return {
        "not_a_pdf": "that file is not a PDF.",
        "unsupported_document_type": "that file is not a PDF or a JPEG, PNG or HEIC photo.",
        "image_unreadable": "that photo could not be read - it may be damaged or incomplete.",
        "image_too_many_pixels": "that photo has too many pixels to keep as a reference (over 50 megapixels).",
        "pdf_truncated": "that PDF looks incomplete - try uploading it again.",
        "document_too_large": "that file is too large.",
        "too_many_pages": "that PDF has too many pages to keep as a reference.",
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
    from music_feature_icons import action_label
    from song_document_catalog import delete_song_document, rename_song_document, retag_song_document

    did = str(row.get("document_id") or "")
    # Not an expander. This panel is already inside one, and nested expanders behave
    # badly: a checkbox in one does not toggle when its label is clicked, and a button
    # that sets session state and reruns leaves the state unchanged - both measured in
    # a real browser, both silent. A plain container has none of that and costs the
    # musician one less click.
    # Layout (user, 2026-11-26): the three fields together, Save directly beneath them (it saves exactly those),
    # and Delete apart in its own box with a destructive look -- never beside Save.
    with st.container(border=True):
        st.caption("Rename or tag")
        cols = st.columns([2, 1, 1])
        title = cols[0].text_input("Name", value=str(row.get("title") or ""),
                                   key=f"{KEY_PREFIX}edit_title_{did}")
        inst = cols[1].text_input("Instrument", value=str(row.get("instrument_tag") or ""),
                                  key=f"{KEY_PREFIX}edit_inst_{did}")
        ktag = cols[2].text_input("Key tag", value=str(row.get("key_tag") or ""),
                                  key=f"{KEY_PREFIX}edit_key_{did}")
        if st.button(action_label("save", "Save changes"), key=f"{KEY_PREFIX}save_{did}",
                     type="primary"):
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

    box = f"{KEY_PREFIX}danger_{_reader_slug(did)}"
    armed = str(st.session_state.get(CONFIRM_KEY) or "") == did
    # A red box. Before confirming, its one button (Delete) has a red outline; while confirming, "Yes, delete it"
    # is solid red and "Keep it" keeps the ordinary look.
    st.markdown(
        f"<style>.st-key-{box}{{border-color:rgba(220,38,38,.45)!important;}}"
        + ("" if armed else
           f".st-key-{box} [data-testid='stBaseButton-secondary']{{color:#b91c1c!important;"
           f"border-color:rgba(220,38,38,.55)!important;}}")
        + f".st-key-{box} [data-testid='stBaseButton-primary']{{background:#dc2626!important;"
        f"border-color:#dc2626!important;color:#fff!important;}}</style>",
        unsafe_allow_html=True,
    )
    with st.container(border=True, key=box):
        st.caption("Deleting removes this reference and its file. It cannot be undone.")
        # Two buttons rather than a tick box and a disabled button. A deletion should
        # take a deliberate second action either way, and a button is the control both
        # a person and a test can actually operate: Streamlit renders a checkbox as a
        # visually hidden input inside a label, and inside this nested expander a click
        # on that label does not toggle it - measured, not assumed, so the tick-box
        # version could never have been confirmed to work.
        if not armed:
            if st.button(action_label("delete", "Delete this reference"), key=f"{KEY_PREFIX}del_{did}"):
                st.session_state[CONFIRM_KEY] = did
                st.rerun()
        else:
            st.warning("Delete this reference permanently?")
            yes, no = st.columns(2)
            if yes.button(action_label("delete", "Yes, delete it"), key=f"{KEY_PREFIX}del_yes_{did}",
                          type="primary", use_container_width=True):
                result = delete_song_document(did, st=st)
                st.session_state[CONFIRM_KEY] = ""
                st.session_state[SELECTED_KEY] = None
                st.session_state[NOTICE_KEY] = [
                    ("ok", "Deleted.") if result.get("ok")
                    else ("error", f"Could not delete: {result.get('error')}")
                ]
                st.rerun()
            if no.button("Keep it", key=f"{KEY_PREFIX}del_no_{did}",
                         use_container_width=True):
                st.session_state[CONFIRM_KEY] = ""
                st.rerun()


def _preview(st: Any, row: dict, *, compact: bool, reader: str = "") -> None:
    """The document itself, a page at a time. ``reader`` gives one panel its own reading position and widget keys
    (still under this panel's prefix), so several references can be open at once."""
    did = str(row.get("document_id") or "")
    digest = str(row.get("sha256") or "")
    fetch, render, pages, render_image = _cached_helpers(st)
    mime = str(row.get("mime_type") or "application/pdf").strip().lower()
    base_width = 760 if compact else _RENDER_WIDTH_DESKTOP
    if mime.startswith("image/"):
        zoom = _zoom_choice(st, reader)
        img = render_image(did, digest, mime, int(base_width * zoom))
        if img:
            _show_page_image(st, img, zoom, reader)
            return
        data = fetch(did, digest)
        if not data:
            st.error("That reference could not be loaded from storage.")
            return
        if mime in ("image/jpeg", "image/png"):
            st.image(data, use_container_width=True)
            return
        # HEIC/HEIF that this server cannot decode: say so and hand the photo over, exactly as uploaded.
        st.info("This photo is in HEIC format, which cannot be shown here. Download it to view it.")
        st.download_button("Download this reference", data=data,
                           file_name=str(row.get("filename") or "reference.heic"),
                           mime=mime, key=f"{KEY_PREFIX}dl_{did}")
        return

    total = pages(did, digest, row.get("page_count") or 1)
    page = int(st.session_state.get(PAGE_KEY + reader) or 0)
    key_prefix = KEY_PREFIX + reader
    page = max(0, min(page, total - 1))

    if total > 1:
        nav = st.columns([1, 2, 1])
        # The labels read "Previous" / "Next" as before, followed by an invisible WORD JOINER (U+2060). On Backing, Key
        # Cycling's page script takes any button whose label is exactly "Previous" or "Next" as its own step control
        # and cancels the click (backing_key_cycle __kcStepBtnHandler label fallback), so without it a page turn during
        # a cycle stepped the key instead. The marker keeps the look unchanged and the label no longer exact.
        if nav[0].button(PAGE_PREVIOUS_LABEL, key=f"{key_prefix}prev", disabled=page <= 0,
                         use_container_width=True):
            st.session_state[PAGE_KEY + reader] = page - 1
            st.rerun()
        nav[1].markdown(
            f"<div style='text-align:center;padding-top:0.45rem'>Page {page + 1} "
            f"of {total}</div>", unsafe_allow_html=True)
        if nav[2].button(PAGE_NEXT_LABEL, key=f"{key_prefix}next", disabled=page >= total - 1,
                         use_container_width=True):
            st.session_state[PAGE_KEY + reader] = page + 1
            st.rerun()

    zoom = _zoom_choice(st, reader)
    png = render(did, digest, page, int(base_width * zoom))
    if png:
        _show_page_image(st, png, zoom, reader)
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
    from music_feature_icons import action_label as _dl_label

    st.download_button(_dl_label("download", "Download this reference"), data=data,
                       file_name=str(row.get("filename") or "reference.pdf"),
                       mime="application/pdf", key=f"{key_prefix}dl_{did}")


def render_song_document_reference(st: Any, row: dict, *, namespace: str, compact: bool = True) -> None:
    """One saved reference on its own (Backing's My Uploaded Melodies panels): its status line and its pages,
    with its own reading position, so several can be open at once. Read-only -- managing (rename, retag,
    delete) stays in the Practice page panel. A reference that cannot be loaded degrades to a message."""
    did = str(row.get("document_id") or "")
    severity, message = _status_line(row)
    if severity != "ok":
        {"warn": st.warning, "error": st.error}.get(severity, st.caption)(message)
    try:
        _preview(st, row, compact=compact, reader=f"::{namespace}{did}::")
    except Exception:
        st.error("That reference could not be shown. The others and the music are unaffected.")


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
    # Seed the widget's own state rather than passing ``index``. A keyed selectbox uses
    # what it has stored and ignores the index, and this list is rebuilt and reordered
    # whenever a document is added, renamed or removed - so the stored id can be one
    # that no longer exists.
    if st.session_state.get(PICKER_KEY) not in ids:
        st.session_state[PICKER_KEY] = current
    chosen = st.selectbox(
        "Saved references",
        ids,
        format_func=lambda d: labels.get(d, d),
        key=PICKER_KEY,
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
