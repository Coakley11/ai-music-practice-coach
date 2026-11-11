"""Apply pending Upload / Multitrack history loads before page widgets render."""

from __future__ import annotations

from typing import Any


def apply_pending_studio_history(session_state: dict[str, Any], *, page: str, st: Any | None = None) -> None:
    if page == "analysis":
        try:
            from media_multitrack_export_catalog import apply_pending_multitrack_export_analysis
            from upload_history import FLASH_KEY as UPLOAD_FLASH_KEY

            ok, _ = apply_pending_multitrack_export_analysis(session_state, st=st)
            if ok:
                session_state[UPLOAD_FLASH_KEY] = (
                    session_state.get("analysis_multitrack_export_loaded_label")
                    or "Loaded multitrack export for analysis."
                )
        except Exception:
            pass
        try:
            from upload_history import FLASH_KEY as UPLOAD_FLASH_KEY
            from upload_history import PENDING_LOAD_KEY, apply_pending_upload_history

            if not session_state.get(PENDING_LOAD_KEY):
                return
            if apply_pending_upload_history(session_state):
                session_state[UPLOAD_FLASH_KEY] = "Loaded saved upload analysis."
                try:
                    from analysis_session_persistence import save_analysis_session
                    from music_persistent_state import force_save_music_state

                    if st is not None:
                        save_analysis_session(session_state, st=st)
                        force_save_music_state(st, reason="history_load")
                except Exception:
                    pass
        except Exception:
            pass
        return

    if page == "multitrack":
        try:
            from media_multitrack_catalog import (
                PENDING_CATALOG_LOAD_ID_KEY,
                apply_pending_multitrack_catalog_load,
            )

            if session_state.get(PENDING_CATALOG_LOAD_ID_KEY):
                apply_pending_multitrack_catalog_load(session_state, st=st)
                # Issue 64 G26: the load above restores the key the project's layers
                # were recorded in and leaves it as a one-shot handoff. It cannot be
                # applied *here*: this bootstrap runs after the sidebar has already
                # drawn its Practice Key widget for this run, and Streamlit refuses to
                # change a widget's value once it exists - measured, as
                # ``display_key:StreamlitAPIException``. Consuming it here also threw the
                # handoff away before the one place that can apply it ever saw it.
                #
                # So ask for one more run instead. At the top of that run no widget
                # exists yet, the handoff applies cleanly, and the sidebar draws the
                # restored key straight away rather than on the musician's next click.
                # The handoff is one-shot, so this cannot loop.
                try:
                    from multitrack_project_key_restore import RESTORED_DISPLAY_KEY

                    if st is not None and str(
                        session_state.get(RESTORED_DISPLAY_KEY) or ""
                    ).strip():
                        st.rerun()
                except ImportError:
                    pass
                return
        except Exception:
            pass
        try:
            from multitrack_history import FLASH_KEY as MT_FLASH_KEY
            from multitrack_history import PENDING_LOAD_KEY, apply_pending_multitrack_history

            if not session_state.get(PENDING_LOAD_KEY):
                return
            info = apply_pending_multitrack_history(session_state)
            if info is None:
                return
            msg = "Loaded project."
            if info.get("metadata_only_layers"):
                msg += f" {info['metadata_only_layers']} layer(s) need audio re-upload (metadata restored)."
            if info.get("restored_layers"):
                msg += f" {info['restored_layers']} layer audio restored."
            if info.get("mixed_restored"):
                msg += " Mix preview restored."
            session_state[MT_FLASH_KEY] = msg
            try:
                from music_persistent_state import force_save_music_state

                if st is not None:
                    force_save_music_state(st, reason="history_load")
            except Exception:
                pass
        except Exception:
            pass
