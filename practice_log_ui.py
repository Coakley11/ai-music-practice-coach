"""Practice Log page UI helpers — portfolio-ready layout."""

from __future__ import annotations

import html
from datetime import date, timedelta
from typing import Any, Callable

from practice_log_state import (
    FOCUS_AREAS,
    PRACTICE_TYPES,
    SECTIONS_PRACTICED,
    add_practice_log_entry,
    build_practice_log_prefill,
    compute_practice_log_summary,
    delete_practice_log_entry,
    filter_practice_log_entries,
    format_bpm_display,
    format_entry_keys_display,
    format_quick_save_success_message,
    is_guitar_instrument,
    load_entries,
    entry_key_display_parts,
    practice_key_field_label,
    reload_practice_log_entries,
    section_display_label,
    update_practice_log_entry,
)

_FILTER_WIDGET_KEYS: tuple[str, ...] = (
    "plog_filter_search",
    "plog_filter_window",
    "plog_filter_instrument",
    "plog_filter_focus",
    "plog_filter_type",
)

_DATE_WINDOWS: tuple[tuple[str, int | None], ...] = (
    ("All time", None),
    ("Last 7 days", 7),
    ("Last 30 days", 30),
    ("Last 90 days", 90),
)

_RATING_KEYS: tuple[tuple[str, str], ...] = (
    ("focus", "Focus"),
    ("confidence", "Confidence"),
    ("accuracy", "Accuracy"),
    ("groove_timing", "Groove / timing"),
    ("tone", "Tone"),
    ("difficulty", "Difficulty"),
)


def _parse_log_date(raw: Any) -> date | None:
    from practice_log_state import _parse_log_date as _parse

    return _parse({"date": raw} if not isinstance(raw, dict) else raw)


def _practice_log_dev_mode(st: Any, session_state: dict[str, Any]) -> bool:
    try:
        from suite_workspace import can_show_developer_tools

        if can_show_developer_tools(st=st):
            return True
    except ImportError:
        pass
    return bool(session_state.get("developer_mode"))


def _json_preview(value: Any, *, limit: int = 2400) -> str:
    import json

    try:
        text = json.dumps(value, indent=2, default=str)
    except Exception:
        text = repr(value)
    if len(text) > limit:
        return text[: limit - 3] + "..."
    return text


def render_practice_log_diagnostics(
    st: Any,
    session_state: dict[str, Any],
    *,
    entries: list[dict[str, Any]],
    filters: dict[str, Any],
    filtered: list[dict[str, Any]],
) -> None:
    if not _practice_log_dev_mode(st, session_state):
        return

    try:
        from practice_log_persistence import PRACTICE_LOG_PERSIST_VERSION, _local_path, _resolve_workspace_id
        from suite_deploy_probe import deploy_info
    except ImportError:
        return

    deploy = deploy_info()
    ws = _resolve_workspace_id(st=st)
    path = _local_path(st=st)
    trace = list(session_state.get("_practice_log_persist_trace") or [])
    last_save = next((row for row in reversed(trace) if row.get("phase") == "save"), {})
    last_load = next((row for row in reversed(trace) if row.get("phase") == "load"), {})

    try:
        from studio_history_cloud import cloud_block_reason, cloud_enabled
    except ImportError:
        cloud_enabled = lambda: False  # type: ignore[misc, assignment]
        cloud_block_reason = lambda: None  # type: ignore[misc, assignment]

    disk_count = 0
    if path.is_file():
        try:
            import json

            raw = json.loads(path.read_text(encoding="utf-8"))
            disk_count = len(raw) if isinstance(raw, list) else 0
        except Exception:
            disk_count = -1

    with st.expander("Practice Log persistence diagnostics (?dev=1)", expanded=False):
        st.caption(
            f"Deploy commit `{deploy.get('commit', 'unknown')}` · "
            f"persist `{PRACTICE_LOG_PERSIST_VERSION}`"
        )
        st.markdown("**Workspace / path**")
        st.text(f"workspace_id: {ws}")
        st.text(f"loaded_workspace_id: {session_state.get('_practice_log_loaded_workspace_id')}")
        st.text(f"before_restore_ws: {session_state.get('_practice_log_load_workspace_before_restore')}")
        st.text(f"after_restore_ws: {session_state.get('_practice_log_load_workspace_after_restore')}")
        st.text(f"local_path: {path}")
        st.text(f"entries_on_disk: {disk_count}")

        st.markdown("**Session counts**")
        st.text(f"session_state practice_log_entries: {len(session_state.get('practice_log_entries') or [])}")
        st.text(f"load_entries (canonical): {len(entries)}")
        st.text(f"filtered visible: {len(filtered)}")
        st.text(f"filters: {_json_preview(filters, limit=400)}")

        st.markdown("**Last save**")
        st.text(f"_practice_log_last_save_ok: {session_state.get('_practice_log_last_save_ok')}")
        st.text(f"session_id: {session_state.get('_practice_log_last_save_session_id')}")
        st.text(f"workspace_id: {session_state.get('_practice_log_last_save_workspace')}")
        st.text(f"local_path: {session_state.get('_practice_log_last_save_local_path')}")
        st.text(f"local_ok: {session_state.get('_practice_log_last_save_local_ok')}")
        st.text(f"local_error: {session_state.get('_practice_log_last_save_local_error')}")
        st.text(f"cloud_ok: {session_state.get('_practice_log_last_save_cloud')}")
        st.text(f"cloud_error: {session_state.get('_practice_log_last_save_cloud_error')}")

        st.markdown("**Cloud**")
        st.text(f"cloud_enabled: {cloud_enabled()}")
        st.text(f"cloud_block_reason: {cloud_block_reason()}")

        st.markdown("**UI action trace**")
        st.text(f"quick_log_clicked_at: {session_state.get('_practice_log_quick_log_clicked_at')}")
        st.text(f"quick_log_prefill: {_json_preview(session_state.get('_practice_log_quick_log_prefill'), limit=600)}")
        st.text(f"quick_log_error: {session_state.get('_practice_log_quick_log_error')}")
        st.text(f"show_quick_form: {session_state.get('_plog_show_quick_form')}")
        st.text(f"manual_save_clicked_at: {session_state.get('_practice_log_manual_save_clicked_at')}")
        st.text(f"manual_save_error: {session_state.get('_practice_log_manual_save_error')}")
        st.text(f"show_manual_form: {session_state.get('_plog_show_manual_form')}")
        st.text(f"last_load_at: {session_state.get('_practice_log_last_load_at')}")
        st.text(f"last_load_count: {session_state.get('_practice_log_last_load_count')}")

        st.markdown("**Last load trace**")
        st.code(_json_preview(last_load or {"note": "no load trace yet"}), language="json")
        st.markdown("**Last save trace**")
        st.code(_json_preview(last_save or {"note": "no save trace yet"}), language="json")

        if st.button("Reload Practice Log from disk/cloud", key="plog_reload_from_storage"):
            reloaded = reload_practice_log_entries(session_state, force=True)
            st.success(f"Reloaded {len(reloaded)} session(s) from storage.")
            st.rerun()

        if st.button("Force test practice log save", key="plog_force_test_save"):
            try:
                entry = add_practice_log_entry(
                    session_state,
                    {
                        "active_song": "Dev Test Entry",
                        "duration_minutes": 5,
                        "instrument": "Test",
                        "notes": "Force test save from diagnostics",
                        "practice_type": "other",
                    },
                )
                sid = str(entry.get("session_id") or "")
                reloaded = load_entries(session_state, force=True)
                persisted = any(str(row.get("session_id") or "") == sid for row in reloaded)
                if persisted:
                    st.success(f"Force test save persisted ({sid[:8]}…, {len(reloaded)} total).")
                else:
                    st.error(f"Force test save wrote session {sid[:8]}… but reload did not find it.")
            except Exception as exc:
                st.error(f"Force test save failed: {exc}")
            st.rerun()


def _utc_now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _try_add_practice_log_entry(
    st: Any,
    session_state: dict[str, Any],
    fields: dict[str, Any],
    *,
    on_saved: Any = None,
    ok_message: str | Callable[[dict[str, Any]], str] = "",
    error_session_key: str,
) -> bool:
    try:
        entry = add_practice_log_entry(session_state, fields)
        session_state.pop(error_session_key, None)
        if on_saved:
            on_saved(entry)
        message = ok_message(entry) if callable(ok_message) else ok_message
        _handle_save_result(st, session_state, ok_message=message)
        return True
    except Exception as exc:
        session_state[error_session_key] = str(exc)
        st.error(f"Could not save practice log: {exc}")
        return False


def _handle_save_result(st: Any, session_state: dict[str, Any], *, ok_message: str) -> None:
    if session_state.get("_practice_log_last_save_ok") is False:
        err = str(session_state.get("_practice_log_last_save_error") or "Save failed")
        st.error(f"Practice log could not be saved: {err}")
        return
    st.success(ok_message)
    st.rerun()


def render_summary_cards(st: Any, entries: list[dict[str, Any]], session_state: dict[str, Any]) -> None:
    summary = compute_practice_log_summary(entries, window_days=14, session_state=session_state)
    challenge = summary.get("repeated_challenge") or "—"
    if challenge and len(str(challenge)) > 48:
        challenge = str(challenge)[:45] + "…"
    next_focus = summary.get("suggested_next_focus") or "—"
    if next_focus and len(str(next_focus)) > 48:
        next_focus = str(next_focus)[:45] + "…"
    st.markdown(
        '<div class="ui-log-kpis">'
        f'<div class="ui-log-kpi"><p class="ui-log-kpi-label">Sessions this week</p>'
        f'<p class="ui-log-kpi-value">{summary.get("sessions_this_week", 0)}</p></div>'
        f'<div class="ui-log-kpi"><p class="ui-log-kpi-label">Minutes this week</p>'
        f'<p class="ui-log-kpi-value">{summary.get("minutes_this_week", 0)}</p></div>'
        f'<div class="ui-log-kpi"><p class="ui-log-kpi-label">Top song</p>'
        f'<p class="ui-log-kpi-value">{html.escape(str(summary.get("top_song") or "—"))}</p></div>'
        f'<div class="ui-log-kpi"><p class="ui-log-kpi-label">Top focus</p>'
        f'<p class="ui-log-kpi-value">{html.escape(str(summary.get("top_focus") or "—"))}</p></div>'
        f'<div class="ui-log-kpi"><p class="ui-log-kpi-label">Repeated challenge</p>'
        f'<p class="ui-log-kpi-value">{html.escape(str(challenge))}</p>'
        f'<p class="ui-log-kpi-sub">Next: {html.escape(str(next_focus))}</p></div>'
        "</div>",
        unsafe_allow_html=True,
    )


def submit_analyze_practice_to_ami(st: Any, session_state: dict[str, Any]) -> dict[str, Any]:
    """Build payload, cache in session, and send to Command Center."""
    from music_coach_context import build_source_state
    from practice_log_ami import build_practice_log_ami_payload
    from suite_analytical_question import (
        build_submit_context,
        submit_practice_log_analysis_handoff,
    )

    entries = load_entries(session_state)
    payload = build_practice_log_ami_payload(session_state, entries=entries, window_days=14)
    session_state["_practice_log_ami_payload"] = payload
    session_state["practice_log_ami_payload"] = payload

    question = (
        "Analyze my practice history. What patterns are showing up, what should I focus on next, "
        "and what should my next 30-minute session look like?"
    )
    ctx = build_submit_context(
        "music",
        "log",
        session_state,
        context_extra_builder=lambda: {
            **payload,
            "practice_log_summary": payload.get("practice_log_summary"),
            "recent_practice_history": payload.get("recent_sessions"),
            "practice_log_ami_payload": payload,
            "user_request": "analyze_practice",
            "routing_hint": "practice_history_analysis",
            "intent": "practice_history_analysis",
            "display_category": "analysis_handoff",
            "handoff_kind": "practice_log_analysis",
            "handoff_title": "Music Practice Log Analysis",
        },
    )
    try:
        from music_ami_context import build_music_applied_math_context, finalize_music_context_for_send

        full = build_music_applied_math_context("log", session_state, question=question)
        full.update(ctx)
        finalize_music_context_for_send(full, session_state, question=question, coach_page="log")
        ctx = full
    except Exception:
        pass

    source_state = None
    try:
        source_state = build_source_state("log", session_state)
    except Exception:
        pass

    return submit_practice_log_analysis_handoff(
        source_page="log",
        question=question,
        context=ctx,
        context_summary="Music Practice Log Analysis",
        source_state=source_state,
        session_state=session_state,
    )


def _rating_fields_form(st: Any, prefix: str, existing: dict[str, Any] | None = None) -> dict[str, int]:
    existing = existing or {}
    ratings: dict[str, int] = {}
    cols = st.columns(3)
    for idx, (key, label) in enumerate(_RATING_KEYS):
        default = 3
        try:
            default = int(existing.get(key, 3))
        except (TypeError, ValueError):
            pass
        with cols[idx % 3]:
            ratings[key] = st.slider(label, 1, 5, default, key=f"{prefix}_rating_{key}")
    return ratings


def _session_form_fields(
    st: Any,
    *,
    prefix: str,
    prefill: dict[str, Any],
    submit_label: str = "Save session",
) -> dict[str, Any] | None:
    form_instrument = str(prefill.get("instrument") or "")
    practice_key_label = practice_key_field_label(form_instrument)
    with st.form(f"{prefix}_practice_session_form"):
        c1, c2 = st.columns(2)
        with c1:
            active_song = st.text_input("Song", value=str(prefill.get("active_song") or ""))
            instrument = st.text_input("Instrument", value=form_instrument)
            display_key = st.text_input(practice_key_label, value=str(prefill.get("display_key") or ""))
            original_key = st.text_input("Original key", value=str(prefill.get("original_key") or ""))
            guitar_shape_key = ""
            if is_guitar_instrument(form_instrument):
                guitar_shape_key = st.text_input(
                    "Shape key",
                    value=str(prefill.get("guitar_shape_key") or ""),
                )
            bpm_val = prefill.get("bpm")
            bpm = st.number_input("BPM", min_value=0, max_value=240, value=int(bpm_val or 0), step=1)
        with c2:
            duration = st.slider("Duration (minutes)", 5, 180, int(prefill.get("duration_minutes") or 30), 5)
            section_practiced = st.selectbox(
                "Section practiced",
                list(SECTIONS_PRACTICED),
                index=_index_in(SECTIONS_PRACTICED, prefill.get("section_practiced"), default=0),
            )
            focus_area = st.selectbox(
                "Focus area",
                list(FOCUS_AREAS),
                index=_index_in(FOCUS_AREAS, prefill.get("focus_area"), default=0),
            )
            practice_type = st.selectbox(
                "Practice type",
                list(PRACTICE_TYPES),
                index=_index_in(PRACTICE_TYPES, prefill.get("practice_type"), default=0),
            )
            tags_raw = st.text_input("Tags (comma-separated)", value=", ".join(prefill.get("tags") or []))

        notes = st.text_area("Notes", value=str(prefill.get("notes") or ""))
        w1, w2 = st.columns(2)
        with w1:
            what_went_well = st.text_area("What went well", value=str(prefill.get("what_went_well") or ""))
        with w2:
            what_was_hard = st.text_area("What was hard", value=str(prefill.get("what_was_hard") or ""))
        next_step = st.text_input("Next step", value=str(prefill.get("next_step") or ""))
        st.markdown("**Session ratings (1–5)**")
        ratings = _rating_fields_form(st, prefix, prefill.get("ratings") if isinstance(prefill.get("ratings"), dict) else {})
        submitted = st.form_submit_button(submit_label, type="primary", use_container_width=True)

    if not submitted:
        return None
    tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
    return {
        "active_song": active_song,
        "song_id": prefill.get("song_id"),
        "artist": prefill.get("artist"),
        "instrument": instrument,
        "display_key": display_key,
        "original_key": original_key,
        "guitar_shape_key": guitar_shape_key or prefill.get("guitar_shape_key"),
        "capo_fret": prefill.get("capo_fret"),
        "bpm": bpm if bpm > 0 else None,
        "duration_minutes": duration,
        "section_practiced": section_practiced,
        "focus_area": focus_area,
        "practice_type": practice_type,
        "notes": notes,
        "what_went_well": what_went_well,
        "what_was_hard": what_was_hard,
        "next_step": next_step,
        "ratings": ratings,
        "tags": tags,
        "source_page": prefill.get("source_page"),
        "source_mode": practice_type,
        "level": prefill.get("level"),
        "genre": prefill.get("genre"),
        "groove": prefill.get("groove"),
    }


def _index_in(options: tuple[str, ...] | list[str], value: Any, *, default: int = 0) -> int:
    text = str(value or "").strip().lower()
    for idx, opt in enumerate(options):
        if str(opt).lower() == text:
            return idx
    return default


def render_quick_actions(
    st: Any,
    session_state: dict[str, Any],
    *,
    on_saved: Any = None,
) -> None:
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("⚡ Quick Save Practice Session", key="plog_quick_log_btn", use_container_width=True):
            session_state["_practice_log_quick_log_clicked_at"] = _utc_now_iso()
            session_state.pop("_plog_show_manual_form", None)
            session_state.pop("_plog_edit_session_id", None)
            prefill = build_practice_log_prefill(session_state)
            session_state["_practice_log_quick_log_prefill"] = {
                "active_song": prefill.get("active_song"),
                "instrument": prefill.get("instrument"),
                "duration_minutes": prefill.get("duration_minutes"),
                "practice_type": prefill.get("practice_type"),
                "source_page": prefill.get("source_page"),
                "bpm": prefill.get("bpm"),
                "bpm_source": prefill.get("bpm_source"),
                "section_name": prefill.get("section_name"),
            }
            fields = {
                **prefill,
                "notes": str(prefill.get("notes") or "").strip() or "Quick save — current setup",
            }
            if not _try_add_practice_log_entry(
                st,
                session_state,
                fields,
                on_saved=on_saved,
                ok_message=format_quick_save_success_message,
                error_session_key="_practice_log_quick_log_error",
            ):
                st.rerun()
    with c2:
        if st.button("✏️ Add Session Manually", key="plog_manual_log_btn", use_container_width=True):
            session_state["_practice_log_manual_open_clicked_at"] = _utc_now_iso()
            session_state["_plog_show_manual_form"] = True
            session_state.pop("_plog_show_quick_form", None)
            session_state.pop("_plog_edit_session_id", None)
            st.rerun()
    with c3:
        if st.button("🧠 Analyze My Practice", key="plog_analyze_ami_btn", use_container_width=True):
            result = submit_analyze_practice_to_ami(st, session_state)
            session_state["_last_analytical_question"] = result
            if result.get("duplicate"):
                st.info("Practice analysis was already sent recently. Open Command Center to continue.")
            else:
                st.success("Practice log sent to Command Center. Open Command Center for Music Coach analysis.")
            st.rerun()
    st.caption(
        "Quick Save uses your current song, instrument, key, BPM, and focus. "
        "Use Add Session Manually if you want to write detailed notes."
    )
    if session_state.get("_practice_log_quick_log_error"):
        st.error(f"Quick save failed: {session_state.get('_practice_log_quick_log_error')}")
    if session_state.get("_plog_show_quick_form"):
        st.caption("Tip: Quick Save saves immediately. Use Add Session Manually to edit fields first.")


def render_entry_forms(st: Any, session_state: dict[str, Any], *, on_saved: Any = None) -> None:
    edit_id = str(session_state.get("_plog_edit_session_id") or "").strip()
    if edit_id:
        entries = load_entries(session_state)
        existing = next((e for e in entries if e.get("session_id") == edit_id), None)
        if existing:
            st.markdown("#### Edit session")
            fields = _session_form_fields(st, prefix=f"edit_{edit_id[:8]}", prefill=existing, submit_label="Update session")
            if fields:
                try:
                    update_practice_log_entry(session_state, edit_id, fields)
                except Exception as exc:
                    st.error(f"Could not update session: {exc}")
                    return
                session_state.pop("_plog_edit_session_id", None)
                if on_saved:
                    on_saved(fields)
                _handle_save_result(st, session_state, ok_message="Session updated.")
            if st.button("Cancel edit", key="plog_cancel_edit"):
                session_state.pop("_plog_edit_session_id", None)
                st.rerun()
            return

    if session_state.get("_plog_show_quick_form"):
        st.markdown("#### Quick log — review before save")
        prefill = build_practice_log_prefill(session_state)
        fields = _session_form_fields(st, prefix="quick", prefill=prefill, submit_label="Save quick log")
        if fields:
            session_state["_practice_log_manual_save_clicked_at"] = _utc_now_iso()
            session_state.pop("_plog_show_quick_form", None)
            _try_add_practice_log_entry(
                st,
                session_state,
                fields,
                on_saved=on_saved,
                ok_message="Practice session logged.",
                error_session_key="_practice_log_manual_save_error",
            )

    if session_state.get("_plog_show_manual_form"):
        st.markdown("#### Add session manually")
        prefill = build_practice_log_prefill(session_state)
        prefill["active_song"] = ""
        fields = _session_form_fields(st, prefix="manual", prefill=prefill, submit_label="Save session")
        if fields:
            session_state["_practice_log_manual_save_clicked_at"] = _utc_now_iso()
            session_state.pop("_plog_show_manual_form", None)
            _try_add_practice_log_entry(
                st,
                session_state,
                fields,
                on_saved=on_saved,
                ok_message="Practice session logged.",
                error_session_key="_practice_log_manual_save_error",
            )


def _clear_practice_log_filters(session_state: dict[str, Any]) -> None:
    for key in _FILTER_WIDGET_KEYS:
        session_state.pop(key, None)


def render_filters(st: Any, entries: list[dict[str, Any]]) -> dict[str, Any]:
    inst_opts = ["All instruments"] + sorted({str(e.get("instrument") or "") for e in entries if e.get("instrument")})
    focus_opts = ["All focus areas"] + list(FOCUS_AREAS)
    type_opts = ["All types"] + list(PRACTICE_TYPES)
    window_labels = [label for label, _ in _DATE_WINDOWS]

    c1, c2, c3, c4, c5 = st.columns([1.4, 1, 1, 1, 1])
    with c1:
        search = st.text_input("Search", placeholder="Song, instrument, notes, tags…", key="plog_filter_search").strip()
    with c2:
        window_label = st.selectbox("Date range", window_labels, key="plog_filter_window")
    with c3:
        instrument = st.selectbox("Instrument", inst_opts, key="plog_filter_instrument")
    with c4:
        focus_area = st.selectbox("Focus area", focus_opts, key="plog_filter_focus")
    with c5:
        practice_type = st.selectbox("Practice type", type_opts, key="plog_filter_type")

    window_days = dict(_DATE_WINDOWS).get(window_label)
    return {
        "search": search,
        "window_days": window_days,
        "instrument": instrument,
        "focus_area": focus_area,
        "practice_type": practice_type,
    }


def render_session_list(
    st: Any,
    session_state: dict[str, Any],
    entries: list[dict[str, Any]],
    *,
    total_entries: int = 0,
) -> None:
    if not entries:
        if total_entries > 0:
            st.info("No practice sessions match these filters.")
            if st.button("Clear filters", key="plog_clear_filters"):
                _clear_practice_log_filters(session_state)
                st.rerun()
        else:
            st.info("No practice sessions yet. Log your first session above.")
        return

    for entry in entries[:120]:
        sid = str(entry.get("session_id") or "")
        song = html.escape(str(entry.get("active_song") or entry.get("song") or "Untitled"))
        instrument = html.escape(str(entry.get("instrument") or "—"))
        mins = int(entry.get("duration_minutes") or entry.get("minutes") or 0)
        log_date = _parse_log_date(entry.get("date"))
        date_label = log_date.strftime("%b %d, %Y") if log_date else html.escape(str(entry.get("date") or ""))
        focus = html.escape(str(entry.get("focus_area") or entry.get("focus") or ""))
        ptype = html.escape(str(entry.get("practice_type") or entry.get("mode") or ""))

        with st.expander(f"{date_label} · {song} · {mins} min · {instrument}", expanded=False):
            bpm_label = html.escape(format_bpm_display(entry))
            section_label = html.escape(section_display_label(entry))
            keys_line = " · ".join(
                f"**{html.escape(label)}:** {html.escape(value)}"
                for label, value in entry_key_display_parts(entry)
            )
            st.markdown(
                f"{keys_line}  \n"
                f"**BPM:** {bpm_label} · **Section:** {section_label}  \n"
                f"**Focus:** {focus} · **Type:** {ptype}"
            )
            if entry.get("notes") or entry.get("practice"):
                st.markdown(f"**Notes:** {entry.get('notes') or entry.get('practice')}")
            if entry.get("what_went_well"):
                st.markdown(f"**Went well:** {entry.get('what_went_well')}")
            if entry.get("what_was_hard"):
                st.markdown(f"**Hard:** {entry.get('what_was_hard')}")
            if entry.get("next_step"):
                st.markdown(f"**Next step:** {entry.get('next_step')}")
            ratings = entry.get("ratings") if isinstance(entry.get("ratings"), dict) else {}
            if ratings:
                parts = [f"{k.replace('_', ' ').title()}: {v}/5" for k, v in ratings.items()]
                st.markdown("**Ratings:** " + " · ".join(parts))
            tags = entry.get("tags") or []
            if tags:
                st.markdown("**Tags:** " + ", ".join(str(t) for t in tags))

            bc1, bc2 = st.columns(2)
            with bc1:
                if st.button("Edit", key=f"plog_edit_{sid}"):
                    session_state["_plog_edit_session_id"] = sid
                    st.rerun()
            with bc2:
                if st.button("Delete", key=f"plog_delete_{sid}"):
                    delete_practice_log_entry(session_state, sid)
                    st.success("Session deleted.")
                    st.rerun()


def render_practice_log_page(
    st: Any,
    session_state: dict[str, Any],
    *,
    on_saved: Any = None,
) -> list[dict[str, Any]]:
    """Main Practice Log page body. Returns filtered entries."""
    entries = load_entries(session_state)
    render_summary_cards(st, entries, session_state)
    render_quick_actions(st, session_state, on_saved=on_saved)
    render_entry_forms(st, session_state, on_saved=on_saved)

    with st.container(key="log_filter_panel", border=False):
        st.markdown('<p class="ui-log-section-title">Session history</p>', unsafe_allow_html=True)
        filters = render_filters(st, entries)
        filtered = filter_practice_log_entries(entries, filters, session_state=session_state)
        render_practice_log_diagnostics(
            st,
            session_state,
            entries=entries,
            filters=filters,
            filtered=filtered,
        )
        render_session_list(st, session_state, filtered, total_entries=len(entries))
    return filtered
