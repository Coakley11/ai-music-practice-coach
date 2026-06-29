"""Multitrack Export Library UI — compact rows near Step 4."""

from __future__ import annotations

import html
import io
from typing import Any

from media_multitrack_export_catalog import (
    delete_multitrack_export_entry,
    export_catalog_diagnostics,
    export_row_summary,
    list_multitrack_exports,
    load_export_for_playback,
    playback_label_for_export,
    save_multitrack_export_from_session,
    send_export_to_upload_analysis,
    suggest_export_name,
)
from media_state import migrate_multitrack_export


def _dev_mode(st: Any, session_state: dict[str, Any]) -> bool:
    try:
        from suite_workspace import can_show_developer_tools

        if can_show_developer_tools(st=st):
            return True
    except ImportError:
        pass
    return bool(session_state.get("developer_mode"))


def render_step4_save_export_panel(
    st_module: Any,
    session_state: dict[str, Any],
    *,
    song_title: str,
    track_items_for_mix: list[dict[str, Any]],
    include_backing: bool,
    backing_volume: float,
) -> None:
    """Save Export controls shown when a mixed WAV exists in session."""
    mixed = session_state.get("mixed_track_wav")
    if not mixed:
        return

    st_module.markdown("---")
    default_name = suggest_export_name(song_title=song_title)
    export_name = st_module.text_input(
        "Export name",
        value=default_name,
        key="mt_export_save_name",
    )
    if st_module.button("Save Export", key="mt_export_save_btn", type="primary", use_container_width=True):
        ok, eid, err = save_multitrack_export_from_session(
            session_state,
            mixed,
            export_name=str(export_name or ""),
            song_title=song_title,
            track_items=track_items_for_mix,
            include_backing=include_backing,
            backing_volume=backing_volume,
            st=st_module,
        )
        if ok:
            st_module.success("Export saved to your Export Library.")
            st_module.rerun()
        else:
            st_module.error(f"Could not save export: {err or 'unknown error'}")


def render_multitrack_export_library(
    st_module: Any,
    session_state: dict[str, Any],
    *,
    song_title: str = "",
) -> None:
    rows = list_multitrack_exports(st=st_module, song_title=song_title or "")
    if song_title:
        all_rows = list_multitrack_exports(st=st_module)
        if not rows and all_rows:
            rows = all_rows

    st_module.markdown("---")
    st_module.markdown("##### Export Library")
    if not rows:
        st_module.caption("No saved exports yet — create a mix above and tap **Save Export**.")
        return

    for row in rows[:20]:
        row = migrate_multitrack_export(row)
        eid = str(row.get("export_id") or "")
        summary = export_row_summary(row)
        playback = playback_label_for_export(row, st=st_module)

        with st_module.expander(f"{summary} · {html.escape(playback)}"):
            st_module.markdown(f"**Export:** {html.escape(str(row.get('export_name') or '—'))}")
            song = str(row.get("song") or row.get("song_title") or "—")
            st_module.markdown(f"**Song:** {html.escape(song)}")
            st_module.markdown(
                f"**Tracks:** {int(row.get('track_count') or 0)} · "
                f"**Format:** {html.escape(str(row.get('format') or 'wav').upper())} · "
                f"**Playback:** {html.escape(playback)}"
            )
            included = row.get("included_tracks") if isinstance(row.get("included_tracks"), list) else []
            if included:
                names = ", ".join(html.escape(str(t.get("name") or "")) for t in included[:8] if isinstance(t, dict))
                if names:
                    st_module.markdown(f"**Included:** {names}")

            bc1, bc2, bc3, bc4 = st_module.columns(4)
            with bc1:
                if st_module.button("Play", key=f"mt_export_play_{eid}"):
                    data, err, _ = load_export_for_playback(eid, st=st_module)
                    if data:
                        st_module.audio(io.BytesIO(data), format="audio/wav")
                    else:
                        st_module.warning(f"Audio unavailable: {err or 'missing file'}")
            with bc2:
                dl_cache_key = f"_mt_export_dl_cache_{eid}"
                if st_module.button("Download", key=f"mt_export_dl_{eid}"):
                    data_dl, err_dl, _ = load_export_for_playback(eid, st=st_module)
                    if data_dl:
                        session_state[dl_cache_key] = data_dl
                    else:
                        session_state.pop(dl_cache_key, None)
                        st_module.warning(f"Audio unavailable: {err_dl or 'missing file'}")
                cached = session_state.get(dl_cache_key)
                if cached:
                    st_module.download_button(
                        "Download WAV",
                        cached,
                        file_name=f"{str(row.get('export_name') or 'export').replace(' ', '_')}.wav",
                        mime="audio/wav",
                        key=f"mt_export_dl_file_{eid}",
                        use_container_width=True,
                    )
            with bc3:
                if st_module.button("Send to Upload Analysis", key=f"mt_export_analyze_{eid}"):
                    ok, err = send_export_to_upload_analysis(session_state, eid, st=st_module)
                    if ok:
                        try:
                            from studio_nav_history import navigate_studio_page

                            navigate_studio_page(session_state, "analysis")
                        except ImportError:
                            session_state["studio_page"] = "analysis"
                        st_module.rerun()
                    else:
                        st_module.warning(f"Could not prepare analysis: {err or 'missing audio'}")
            with bc4:
                if st_module.button("Delete", key=f"mt_export_del_{eid}"):
                    if delete_multitrack_export_entry(st_module, eid, row=row):
                        st_module.success("Export deleted.")
                        st_module.rerun()
                    else:
                        st_module.error("Delete failed.")

    if _dev_mode(st_module, session_state):
        diag = export_catalog_diagnostics(session_state, st=st_module)
        with st_module.expander("Export library diagnostics (?dev=1)", expanded=False):
            for key, val in diag.items():
                st_module.markdown(f"**{key}:** `{html.escape(str(val))}`")
