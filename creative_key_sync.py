"""Creative page concert-key sync — Style Jam / Jam Session → global practice key."""

from __future__ import annotations

import html
from typing import Any

from studio_page_state import CREATIVE_MAJOR_KEY_OPTIONS

IMPROV_STYLE_KEY_TRACKER = "_improv_style_key_tracker"
IMPROV_JAM_KEY_TRACKER = "_improv_jam_key_tracker"
CREATIVE_CONCERT_KEY_SOURCE = "_creative_concert_key_source"
PENDING_CAPO_SHAPE_KEY = "_pending_capo_shape_key"
PENDING_IMPROV_STYLE_KEY = "_pending_improv_style_key"
PENDING_IMPROV_JAM_KEY = "_pending_improv_jam_key"

CREATIVE_MAJOR_JAM_MODES: tuple[str, ...] = ("Style Jam Mode", "Jam Session Generator")
MISSION_BACKING_PRACTICE_KEY_WIDGET = "display_key_mission_backing"


def live_backing_source(session: dict[str, Any]) -> str:
    """Current rendered Backing owner, not remembered Creative-tab history."""
    try:
        from backing_context import get_backing_context

        ctx = get_backing_context(session)
        src = str(getattr(ctx, "source", "") or "").strip() if ctx is not None else ""
        if src:
            return src
    except ImportError:
        pass
    raw = session.get("backing_context")
    if isinstance(raw, dict):
        src = str(raw.get("source") or "").strip()
        if src:
            return src
    return str(session.get("_backing_explicit_handoff_source") or "").strip()


def resolve_practice_key_write_owner(session: dict[str, Any]) -> str:
    """Who receives a native sidebar Practice Key edit.

    While the rendered page is specialized Backing, the live backing source is
    the write owner. Leftover Creative / SBI / Missions tabs are navigation
    history and must not steal the key.
    """
    page = str(session.get("studio_page") or "").strip().lower()
    src = live_backing_source(session)
    if page == "backing":
        if src == "entry_jam":
            return "entry_jam"
        if src == "mission":
            return "mission"
        if src == "song_improv":
            return "song_improv"
        if src == "custom_progression":
            return "custom"
        return "catalog"
    tab = str(
        session.get("improv_intelligence_tab")
        or session.get("creative_improv_intelligence_tab")
        or ""
    ).strip()
    if page == "creative":
        entry = str(session.get("improv_entry_mode") or "").strip()
        if entry in CREATIVE_MAJOR_JAM_MODES:
            return "entry_jam"
        if tab == "Missions":
            return "mission"
        if tab in {
            "Song-Based Improvisation",
            "Phrase / Motif",
            "Harmony Map",
            "Live Coach",
        }:
            return "song_improv"
    if page == "custom":
        return "custom"
    return "catalog"


def generated_backing_owns_left_panel_key(session: dict[str, Any]) -> bool:
    """True when Backing is showing a generated Style Jam / Jam Generator session.

    The left-panel Practice / Concert Key then mutates the generated owner, not
    the catalog song Practice Key. A leftover SBI/catalog pointer must not hide this.
    """
    page = str(session.get("studio_page") or "").strip().lower()
    if page != "backing":
        return False
    return live_backing_source(session) == "entry_jam"


def mission_backing_owns_left_panel_key(session: dict[str, Any]) -> bool:
    """True when Backing is showing a Mission workspace.

    The left-panel Practice / Concert Key then mutates the Mission generation,
    not the catalog song Practice Key. Same-owner user edits are not H4 owner switches.
    """
    page = str(session.get("studio_page") or "").strip().lower()
    if page != "backing":
        return False
    return live_backing_source(session) == "mission"


def _emit_h6_mission_pk_trace(session: dict[str, Any], stage: str, **fields: Any) -> None:
    """Env-gated H6 native-path ordering dump. Writes only under MUSIC_APP_DATA_DIR."""
    try:
        import json
        import os
        import time
        from pathlib import Path

        data_dir = str(os.environ.get("MUSIC_APP_DATA_DIR") or "").strip()
        if not data_dir:
            return
        payload = {
            "t": time.time(),
            "stage": stage,
            "display_key": str(session.get("display_key") or ""),
            "improv_mission_concert_key": str(session.get("improv_mission_concert_key") or ""),
            "ii_selected_chord": str(session.get("ii_selected_chord") or ""),
            "show_written": bool(session.get("show_chart_in_instrument_key")),
            **fields,
        }
        path = Path(data_dir) / "_h6_mission_pk_tx.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, default=str) + "\n")
    except Exception:
        pass


def apply_specialized_mission_practice_key(session: dict[str, Any], new_key: str) -> str:
    """Atomic Mission Backing Practice Key write. Catalog maps are not touched."""
    new = str(new_key or "").strip()
    if not new:
        return ""
    if live_backing_source(session) != "mission":
        page = str(session.get("studio_page") or "").strip().lower()
        tab = str(
            session.get("improv_intelligence_tab")
            or session.get("creative_improv_intelligence_tab")
            or ""
        ).strip()
        if not (page == "backing" or (page == "creative" and tab == "Missions")):
            return ""
    try:
        from workflow_key_identity import normalize_user_practice_key_selection

        _tonic, _mode, new = normalize_user_practice_key_selection(new, default_mode="minor")
    except ImportError:
        pass
    pending_from = str(session.pop("_mission_pk_transpose_from", "") or "").strip()
    current = str(
        session.get("improv_mission_concert_key")
        or session.get("display_key")
        or session.get("concert_key")
        or ""
    ).strip()
    # Consume leftover from_key only when this visit has not already landed on
    # `new`. A second callback in the same rerun must not transpose twice.
    if current == new:
        from_key = new
    else:
        from_key = pending_from or current
    old_chord = str(session.get("ii_selected_chord") or "").strip()
    _emit_h6_mission_pk_trace(
        session,
        "B_specialized_mission_mutation_enter",
        from_key=from_key,
        to_key=new,
        old_selected_chord=old_chord,
    )
    session["display_key"] = new
    session["concert_key"] = new
    session["_pending_display_key"] = new
    session["improv_mission_concert_key"] = new
    # Do not assign display_key_mission_backing here. This helper runs from that
    # widget's on_change; writing the same key in-callback leaves the visible
    # input on the previous token (Bm) while session/persist already moved.
    # Queue a pre-widget mirror for the NEXT render instead.
    session["_pending_mission_practice_key"] = new
    session["_mission_practice_key_widget_mirror"] = new
    try:
        from songs.key_state import (
            clear_display_key_owner_transition,
            resolve_display_key_widget_owner_id,
        )

        current = str(resolve_display_key_widget_owner_id(session) or "").strip()
        if current.startswith("mission::"):
            clear_display_key_owner_transition(session)
    except Exception:
        session.pop("_display_key_owner_transition", None)
        session.pop("_specialized_practice_token_leaving", None)
        session.pop("_specialized_leave_catalog_pk", None)
        session.pop("_specialized_leave_catalog_pick", None)
    # Same-owner user edit: display_key is the Mission UI mirror, not a competing
    # catalog authority. Stamp the explicit sidebar source so freeze/merge cannot
    # keep the previous Mission generation (Cm) in the save envelope.
    try:
        from practice_setup_globals import record_global_control_change

        record_global_control_change(session, "display_key", "sidebar_on_change")
    except Exception:
        session["display_key_change_source"] = "sidebar_on_change"
    try:
        from active_song_state import ACTIVE_SONG_STATE_KEY

        meta = session.get(ACTIVE_SONG_STATE_KEY)
        if isinstance(meta, dict):
            meta = dict(meta)
            meta["display_key"] = new
            session[ACTIVE_SONG_STATE_KEY] = meta
    except ImportError:
        pass
    try:
        from dataclasses import replace

        from backing_context import get_backing_context, set_backing_context
        from music_theory import semitone_distance, transpose_chord

        ctx = get_backing_context(session)
        if ctx is not None and str(getattr(ctx, "source", "") or "") == "mission":
            prog = [str(c) for c in (ctx.progression or []) if str(c).strip()]
            steps = semitone_distance(from_key, new) if from_key and from_key != new else 0
            if steps:
                prog = [transpose_chord(c, steps, reference_key=new) for c in prog]
            ctx = replace(
                ctx,
                key=new,
                display_key=new,
                concert_key=new,
                progression=prog,
            )
            set_backing_context(session, ctx, trace_caller="apply_specialized_mission_practice_key")
        raw_ctx = session.get("backing_context")
        if isinstance(raw_ctx, dict) and str(raw_ctx.get("source") or "") == "mission":
            raw_ctx = dict(raw_ctx)
            raw_ctx["key"] = new
            raw_ctx["display_key"] = new
            raw_ctx["concert_key"] = new
            if from_key and from_key != new:
                try:
                    from music_theory import semitone_distance, transpose_chord

                    steps = semitone_distance(from_key, new)
                    prog = [str(c) for c in (raw_ctx.get("progression") or []) if str(c).strip()]
                    if steps and prog:
                        raw_ctx["progression"] = [
                            transpose_chord(c, steps, reference_key=new) for c in prog
                        ]
                except Exception:
                    pass
            session["backing_context"] = raw_ctx
    except Exception:
        pass
    if from_key and from_key != new:
        try:
            from improvisation_missions import transpose_stored_mission_example
            from music_theory import semitone_distance, transpose_chord

            if not old_chord:
                click0 = session.get("_mission_chord_click_authority")
                if isinstance(click0, dict):
                    old_chord = str(click0.get("chord") or "").strip()
                if not old_chord:
                    example = session.get("improv_mission_example")
                    if isinstance(example, dict):
                        old_chord = str(example.get("chord") or "").strip()
                if old_chord:
                    session["ii_selected_chord"] = old_chord
            transpose_stored_mission_example(session, from_key=from_key, to_key=new)
            steps = semitone_distance(from_key, new)
            if steps:
                for key in (
                    "ii_selected_chord",
                    "II_SELECTED_CHORD",
                    "_mission_backing_canonical_chord",
                    "ii_selected_chord_label",
                ):
                    raw = str(session.get(key) or "").strip()
                    if raw:
                        session[key] = transpose_chord(raw, steps, reference_key=new)
                click = session.get("_mission_chord_click_authority")
                if isinstance(click, dict) and str(click.get("chord") or "").strip():
                    click = dict(click)
                    click["chord"] = transpose_chord(
                        str(click.get("chord")), steps, reference_key=new
                    )
                    click["practice_key"] = new
                    session["_mission_chord_click_authority"] = click
                practice = session.get("improv_mission_practice_context")
                if isinstance(practice, dict) and str(practice.get("chord") or "").strip():
                    practice = dict(practice)
                    practice["chord"] = transpose_chord(
                        str(practice.get("chord")), steps, reference_key=new
                    )
                    practice["concert_key"] = new
                    session["improv_mission_practice_context"] = practice
        except Exception:
            pass
    try:
        from improvisation_mission_persistence import (
            _merge_mission_keys_into_creative_snapshot,
            mark_mission_workspace_dirty,
        )

        mark_mission_workspace_dirty(session)
        _merge_mission_keys_into_creative_snapshot(session)
    except ImportError:
        try:
            from improvisation_mission_persistence import mark_mission_workspace_dirty

            mark_mission_workspace_dirty(session)
        except ImportError:
            pass
    raw_ctx = session.get("backing_context") if isinstance(session.get("backing_context"), dict) else {}
    _emit_h6_mission_pk_trace(
        session,
        "C_live_workspace_after_mutation",
        from_key=from_key,
        to_key=new,
        new_selected_chord=str(session.get("ii_selected_chord") or ""),
        backing_concert=str(raw_ctx.get("concert_key") or raw_ctx.get("key") or ""),
        backing_source=str(raw_ctx.get("source") or ""),
    )
    _emit_h6_mission_pk_trace(
        session,
        "D_backing_context_after_mutation",
        backing_concert=str(raw_ctx.get("concert_key") or raw_ctx.get("key") or ""),
        backing_display=str(raw_ctx.get("display_key") or ""),
        backing_progression=(raw_ctx.get("progression") or [])[:8],
    )
    return new


def apply_specialized_jam_practice_key(session: dict[str, Any], new_key: str) -> str:
    """Atomic Jam Backing Practice Key write: jam owner first, then derived stores.

    Catalog / leftover SBI maps are not touched here.
    """
    new = str(new_key or "").strip()
    if not new or not generated_backing_owns_left_panel_key(session):
        return ""
    try:
        from workflow_key_identity import normalize_user_practice_key_selection

        _tonic, _mode, new = normalize_user_practice_key_selection(new, default_mode="major")
    except ImportError:
        pass
    jam_owner = "jam_session_generator"
    entry = str(session.get("improv_entry_mode") or "").strip()
    try:
        from backing_context import get_backing_context

        ctx = get_backing_context(session)
        entry = str(getattr(ctx, "entry_mode", "") or entry).strip()
    except Exception:
        pass
    if "Style Jam" in entry:
        jam_owner = "style_jam"
    widget_key = "improv_style_key" if jam_owner == "style_jam" else "improv_jam_key"
    jam_sid = ""
    session[widget_key] = new
    session["display_key"] = new
    session["concert_key"] = new
    session["_pending_display_key"] = new
    try:
        from h3_live_key_trace import emit_display_key_write

        emit_display_key_write(session, new, source="apply_specialized_jam_practice_key")
    except Exception:
        pass
    try:
        from generated_jam_key_context import GENERATED_JAM_KEY_CONTEXT_KEY
        from music_theory import key_center_token, split_key_center

        tonic, mode = split_key_center(new)
        token = key_center_token(tonic, mode)
        raw_jam = session.get(GENERATED_JAM_KEY_CONTEXT_KEY)
        raw_jam = dict(raw_jam) if isinstance(raw_jam, dict) else {}
        raw_jam["practice_tonic"] = tonic
        raw_jam["practice_mode"] = mode
        raw_jam["practice_key_token"] = token
        raw_jam["key_owner"] = jam_owner
        raw_jam["entry_mode"] = entry
        session[GENERATED_JAM_KEY_CONTEXT_KEY] = raw_jam
        session["_generated_jam_key_owner_active"] = True
        raw_ctx = session.get("backing_context")
        if isinstance(raw_ctx, dict) and str(raw_ctx.get("source") or "") == "entry_jam":
            raw_ctx = dict(raw_ctx)
            raw_ctx["key"] = token
            raw_ctx["display_key"] = token
            raw_ctx["concert_key"] = token
            session["backing_context"] = raw_ctx
    except Exception:
        token = new
    try:
        from generated_jam_key_change import (
            align_generated_workflow_pointer_for_key_edit,
            capture_generated_key_edit_intent,
            resolve_generated_workflow_session_id,
        )

        jam_sid = resolve_generated_workflow_session_id(session, jam_owner)
        try:
            import json
            import os
            import time

            data_dir = str(os.environ.get("MUSIC_APP_DATA_DIR") or "").strip()
            if data_dir:
                jam = session.get("improv_jam_session")
                with open(os.path.join(data_dir, "_jam_pk_apply.jsonl"), "a", encoding="utf-8") as fh:
                    fh.write(
                        json.dumps(
                            {
                                "ts": time.time(),
                                "jam_owner": jam_owner,
                                "jam_sid": jam_sid,
                                "stored": session.get("_jam_session_generator_session_id"),
                                "jam_id": (jam.get("id") if isinstance(jam, dict) else None),
                                "new": new,
                            }
                        )
                        + "\n"
                    )
        except Exception:
            pass
        align_generated_workflow_pointer_for_key_edit(
            session,
            jam_owner,
            session_id=jam_sid,
        )
        capture_generated_key_edit_intent(session, widget_key=widget_key)
    except ImportError:
        pass
    try:
        from music_workflow_mutation import update_active_practice_key

        mutation_source = (
            "on_improv_style_key_change" if jam_owner == "style_jam" else "on_improv_jam_key_change"
        )
        result = update_active_practice_key(
            session, new, source=mutation_source, transpose_progression=True
        )
        session["_jam_pk_mutation"] = {
            "ok": bool(getattr(result, "ok", False)),
            "error": str(getattr(result, "error_code", "") or ""),
            "sid": jam_sid,
        }
        from music_theory import split_key_center, transpose_sections_dict
        from music_workflow_state_store import get_workflow_blob, save_workflow_blob

        tonic, mode = split_key_center(new)
        sid = jam_sid
        if not sid:
            try:
                from generated_jam_key_change import resolve_generated_workflow_session_id

                sid = resolve_generated_workflow_session_id(session, jam_owner)
            except ImportError:
                jam = session.get("improv_jam_session")
                if isinstance(jam, dict):
                    sid = str(jam.get("id") or "").strip()
        blob = get_workflow_blob(session, jam_owner, sid) if sid else None
        live_tonic = str(getattr(getattr(blob, "keys", None), "practice_tonic", "") or "") if blob else ""
        session["_jam_pk_mutation"]["blob_tonic"] = live_tonic
        if blob is not None and live_tonic != tonic:
            keys = blob.keys
            old_token = f"{keys.practice_tonic}m" if str(keys.practice_mode or "") == "minor" else str(keys.practice_tonic or "C")
            blob.keys = type(keys)(
                original_tonic=keys.original_tonic,
                original_mode=keys.original_mode,
                practice_tonic=tonic,
                practice_mode=mode or "major",
                written_tonic=keys.written_tonic,
                written_mode=keys.written_mode,
                instrument=keys.instrument,
                transposition=keys.transposition,
                key_owner=jam_owner,
            )
            if blob.section_map:
                try:
                    blob.section_map = transpose_sections_dict(blob.section_map, old_token, new)
                except Exception:
                    pass
            save_workflow_blob(session, blob, source="sidebar_jam_backing_canonical")
            session["_jam_pk_mutation"]["fallback_blob"] = True
        if blob is not None:
            jam = session.get("improv_jam_session")
            if isinstance(jam, dict):
                jam = dict(jam)
                jam["key"] = str(blob.keys.practice_tonic or tonic or new)
                if blob.section_map:
                    jam["sections"] = dict(blob.section_map)
                session["improv_jam_session"] = jam
            try:
                from generated_workflow_artifact import rebuild_jam_owner_artifact_snapshot_from_canonical_blob

                rebuild_jam_owner_artifact_snapshot_from_canonical_blob(session)
            except ImportError:
                pass
            try:
                from backing_context import build_entry_jam_context, set_backing_context

                live_ctx = build_entry_jam_context(session)
                if live_ctx is not None and str(getattr(live_ctx, "source", "") or "") == "entry_jam":
                    set_backing_context(
                        session, live_ctx, trace_caller="apply_specialized_jam_practice_key"
                    )
            except Exception:
                pass
    except Exception as exc:
        session["_jam_pk_mutation"] = {"ok": False, "error": type(exc).__name__}
    return new

_SIDEBAR_USER_DISPLAY_KEY_SOURCES: frozenset[str] = frozenset(
    {
        "sidebar_on_change",
        "sidebar",
        "display_key_widget",
        "display_key_change",
        "user",
        "user_navigation",
    }
)

# Re-export for UI pickers.
CREATIVE_MAJOR_KEY_OPTIONS = CREATIVE_MAJOR_KEY_OPTIONS


def _key_steps_to_center(key_center: str) -> int:
    from music_theory import normalize_root, semitone_distance, split_chord

    root, _suffix = split_chord(str(key_center or "C"))
    target = normalize_root(root)
    return semitone_distance("C", target)


def creative_entry_concert_key(session: dict[str, Any]) -> str:
    """Selected concert key from Creative entry widgets, if any."""
    try:
        from workflow_key_identity import generated_workflow_owns_practice_key, resolve_active_workflow_key_identity

        if generated_workflow_owns_practice_key(session):
            ident = resolve_active_workflow_key_identity(session)
            if ident is not None:
                return ident.practice_key_token
    except ImportError:
        pass
    try:
        from practice_key_mode import is_fixed_practice_key_mode, resolve_practice_concert_key_for_song

        if is_fixed_practice_key_mode(session):
            return resolve_practice_concert_key_for_song(session, "C", fallback="C")
    except ImportError:
        pass
    entry = str(session.get("improv_entry_mode") or "").strip()
    if entry == "Style Jam Mode":
        return str(session.get("improv_style_key") or "").strip()
    if entry == "Jam Session Generator":
        return str(session.get("improv_jam_key") or "").strip()
    return ""


def _catalog_song_workflow_owns_practice_key(session: dict[str, Any]) -> bool:
    """Song-Based / Missions with an active catalog pick reclaim practice key from entry jam.

    Leftover Missions/SBI tabs must not win while specialized Jam Backing is live.
    """
    if live_backing_source(session) == "entry_jam":
        return False
    if resolve_practice_key_write_owner(session) == "entry_jam":
        return False
    tab = str(session.get("improv_intelligence_tab") or session.get("creative_improv_intelligence_tab") or "").strip()
    if tab in {
        "Missions",
        "Song-Based Improvisation",
        "Phrase / Motif",
        "Harmony Map",
        "Live Coach",
        "Metrics & AI",
    }:
        return True
    try:
        from music_workflow_state_store import get_active_workflow_pointer

        ptr = get_active_workflow_pointer(session)
        if ptr and ptr.workflow_owner in {"mission_jam", "song_based_improvisation"}:
            pick = str(session.get("active_catalog_pick_key") or session.get("_active_pick_key") or "").strip()
            if pick:
                return True
    except ImportError:
        pass
    return False


def entry_jam_practice_key_authority_active(session: dict[str, Any]) -> bool:
    """Style Jam / Jam Session own practice key only while those tools or their Backing are current."""
    if generated_backing_owns_left_panel_key(session):
        return True
    if _catalog_song_workflow_owns_practice_key(session):
        return False
    page = str(session.get("studio_page") or "").strip().lower()
    if page not in {"creative", "backing"}:
        return False
    entry = str(session.get("improv_entry_mode") or "").strip()
    if entry not in CREATIVE_MAJOR_JAM_MODES:
        try:
            from backing_context import get_backing_context

            ctx = get_backing_context(session)
            if ctx is None or str(ctx.source or "") != "entry_jam":
                return False
            entry = str(ctx.entry_mode or "").strip()
            if entry not in CREATIVE_MAJOR_JAM_MODES:
                return False
        except ImportError:
            return False
    if session.get("improv_generated_sections") or session.get("improv_jam_session"):
        return True
    if str(session.get("improv_jam_key") or session.get("improv_style_key") or "").strip():
        return True
    try:
        from generated_jam_key_context import generated_jam_owns_practice_key

        return bool(generated_jam_owns_practice_key(session))
    except ImportError:
        return False


def resolve_creative_tab_practice_key_token(session: dict[str, Any]) -> str:
    """Authoritative practice key when entry jam owns creative context."""
    if not entry_jam_practice_key_authority_active(session):
        return ""
    try:
        from workflow_key_identity import resolve_active_workflow_key_identity

        ident = resolve_active_workflow_key_identity(session)
        if ident is not None and ident.workflow_owner in {"style_jam", "jam_session_generator"}:
            return ident.practice_key_token
    except ImportError:
        pass
    try:
        from generated_jam_key_context import GENERATED_JAM_KEY_CONTEXT_KEY

        raw = session.get(GENERATED_JAM_KEY_CONTEXT_KEY)
        if isinstance(raw, dict):
            tok = str(raw.get("practice_key_token") or "").strip()
            if tok:
                return tok
            tonic = str(raw.get("practice_tonic") or "").strip()
            mode = str(raw.get("practice_mode") or "major").strip().lower() or "major"
            if tonic:
                from music_theory import key_center_token

                return key_center_token(tonic, mode)
    except ImportError:
        pass
    try:
        from music_theory import key_center_token, split_key_center

        entry_key = creative_entry_concert_key(session)
        if entry_key:
            tonic, mode = split_key_center(entry_key)
            return key_center_token(tonic, mode)
    except ImportError:
        pass
    entry_key = creative_entry_concert_key(session)
    if entry_key:
        try:
            from music_theory import key_center_token, split_key_center

            tonic, mode = split_key_center(entry_key)
            return key_center_token(tonic, mode)
        except ImportError:
            return entry_key
    return ""


def apply_entry_jam_authoritative_practice_key(session: dict[str, Any], *, source: str) -> str:
    """Push generated-jam Concert Key into jam widgets only — never the song Practice Key."""
    try:
        from generated_workflow_projection import project_generated_owner_from_active_blob

        project_generated_owner_from_active_blob(session, writer=f"apply_entry_jam:{source}")
    except ImportError:
        pass
    tok = resolve_creative_tab_practice_key_token(session)
    if not tok:
        return ""
    apply_creative_concert_key(session, tok, source=source)
    return tok


def retranspose_generated_sections(
    sections: dict[str, list[str]],
    *,
    from_key: str,
    to_key: str,
) -> dict[str, list[str]]:
    """Transpose Style Jam section dict when the user changes key."""
    if not sections or not from_key or not to_key or from_key == to_key:
        return sections
    from music_theory import transpose_chord

    delta = _key_steps_to_center(to_key) - _key_steps_to_center(from_key)
    if delta == 0:
        return sections
    out: dict[str, list[str]] = {}
    for label, chords in sections.items():
        if isinstance(chords, list):
            out[label] = [transpose_chord(str(c), delta, reference_key=to_key) for c in chords if str(c).strip()]
        else:
            out[label] = chords
    return out


def is_creative_catalog_pick_frozen(session: dict[str, Any]) -> bool:
    """True when Creative jam/style edits must not mutate the active catalog song."""
    page = str(session.get("studio_page") or "").strip().lower()
    if page == "backing":
        try:
            from backing_workflow_context import workflow_is_generated

            if workflow_is_generated(session):
                return True
        except ImportError:
            pass
    if page != "creative":
        return False
    entry = str(session.get("improv_entry_mode") or "").strip()
    if entry in CREATIVE_MAJOR_JAM_MODES:
        return True
    try:
        from creative_session_state import get_creative_session

        sess = get_creative_session(session)
        if sess is not None and sess.tool_type in {"entry_style_jam", "jam_session_generator"}:
            return True
    except ImportError:
        pass
    return False


def guard_creative_catalog_pick_before_edit(session: dict[str, Any], *, writer: str) -> str:
    """Record active catalog pick before a Creative widget edit; pin dropdown aliases."""
    pick = ""
    try:
        from songs.music_source import pin_catalog_pick_aliases, write_creative_catalog_guard_diag

        pick = pin_catalog_pick_aliases(session)
        before = str(session.get("song") or session.get("active_song_title") or pick or "").strip()
        snap = session.get("_catalog_before_creative_state")
        snap_pick = str(snap.get("pick_key") or "").strip() if isinstance(snap, dict) else ""
        write_creative_catalog_guard_diag(
            session,
            catalog_song_before_jam_edit=before or pick,
            catalog_snapshot_before_creative=snap_pick or pick,
        )
    except ImportError:
        pick = str(session.get("active_catalog_pick_key") or "").strip()
    return pick


def verify_creative_catalog_pick_after_edit(
    session: dict[str, Any],
    *,
    before_pick: str,
    writer: str,
) -> None:
    """Restore catalog pick if a Creative edit incorrectly mutated it."""
    try:
        from songs.music_source import (
            restore_frozen_catalog_pick_if_mutated,
            write_creative_catalog_guard_diag,
        )

        restore_frozen_catalog_pick_if_mutated(session, before_pick, writer=writer)
        after = str(session.get("song") or session.get("active_song_title") or "").strip()
        snap = session.get("_catalog_before_creative_state")
        snap_pick = str(snap.get("pick_key") or "").strip() if isinstance(snap, dict) else ""
        write_creative_catalog_guard_diag(
            session,
            catalog_song_after_jam_edit=after or str(session.get("active_catalog_pick_key") or "").strip(),
            catalog_snapshot_after_creative=snap_pick,
        )
    except ImportError:
        pass


def apply_creative_concert_key(
    session: dict[str, Any],
    concert_key: str,
    *,
    st_like: Any | None = None,
    source: str = "creative_style_jam",
) -> None:
    """Push Creative-selected key into the owning generated session — not the catalog song."""
    key = str(concert_key or "").strip()
    if not key:
        return
    jam_owns = False
    try:
        from workflow_key_identity import generated_workflow_owns_practice_key

        jam_owns = bool(generated_workflow_owns_practice_key(session))
    except ImportError:
        jam_owns = is_creative_major_jam_active(session)
    entry = str(session.get("improv_entry_mode") or "").strip()
    jam_entry = jam_owns or entry in CREATIVE_MAJOR_JAM_MODES
    try:
        if not jam_entry:
            from practice_key_mode import is_fixed_practice_key_mode, resolve_practice_concert_key_for_song

            if is_fixed_practice_key_mode(session):
                key = resolve_practice_concert_key_for_song(session, key, fallback=key)
    except ImportError:
        pass
    session[CREATIVE_CONCERT_KEY_SOURCE] = source
    try:
        from music_theory import key_center_token, split_key_center

        tonic, mode = split_key_center(key)
        key = key_center_token(tonic, mode)
    except ImportError:
        pass
    if jam_entry:
        if entry == "Jam Session Generator":
            session["improv_jam_key"] = key
        else:
            session["improv_style_key"] = key
        return
    session["concert_key"] = key
    if st_like is None:
        st_like = type("_St", (), {"session_state": session})()
    try:
        from songs.key_state import request_display_key

        request_display_key(st_like, key)
    except ImportError:
        session["_pending_display_key"] = key
    if not is_creative_catalog_pick_frozen(session):
        try:
            from active_song_state import mark_active_song_local_edit

            mark_active_song_local_edit(session)
        except ImportError:
            pass
    try:
        from songs.key_state import BACKING_NEEDS_REGEN, invalidate_backing_cache

        invalidate_backing_cache(st_like)
        session[BACKING_NEEDS_REGEN] = True
    except ImportError:
        pass
    if is_creative_major_jam_active(session):
        sanitize_creative_major_chart_keys(session, st_like=st_like)


def flush_pending_creative_major_keys(session: dict[str, Any]) -> None:
    """Apply queued Creative chart-key values before their widgets render."""
    try:
        from guitar_capo import CAPO_SHAPE_KEY
    except ImportError:
        CAPO_SHAPE_KEY = "guitar_capo_shape_key"

    pending_shape = session.pop(PENDING_CAPO_SHAPE_KEY, None)
    if pending_shape is not None:
        session[CAPO_SHAPE_KEY] = str(pending_shape).strip()

    pending_style = session.pop(PENDING_IMPROV_STYLE_KEY, None)
    if pending_style is not None:
        session["improv_style_key"] = str(pending_style).strip()

    pending_jam = session.pop(PENDING_IMPROV_JAM_KEY, None)
    if pending_jam is not None:
        session["improv_jam_key"] = str(pending_jam).strip()


def invalidate_creative_backing_context(session: dict[str, Any]) -> None:
    """Refresh Creative backing handoff after the generated session is fully updated.

    Drop any sealed owner snapshot first so Backing never validates a mix of
    old artifact identity and new widget/blob fields.
    """
    try:
        from generated_workflow_artifact import BACKING_OWNER_ARTIFACT_SNAPSHOT_KEY

        session.pop(BACKING_OWNER_ARTIFACT_SNAPSHOT_KEY, None)
    except ImportError:
        session.pop("_backing_owner_artifact_snapshot", None)
    try:
        from backing_context import (
            PENDING_BACKING_CONTEXT_APPLY,
            get_backing_context,
            refresh_backing_context_from_session,
            set_backing_context,
        )

        ctx = get_backing_context(session)
        if ctx is not None and ctx.source in {
            "entry_jam",
            "mission",
            "custom_progression",
            "song_improv",
        }:
            if ctx.source == "entry_jam":
                try:
                    from generated_workflow_artifact import seal_backing_handoff_snapshot_for_creative_open

                    seal_backing_handoff_snapshot_for_creative_open(session)
                except ImportError:
                    pass
            refreshed = refresh_backing_context_from_session(session)
            if refreshed is not None:
                set_backing_context(session, refreshed)
                session[PENDING_BACKING_CONTEXT_APPLY] = True
                session.pop("_backing_creative_chart_sections", None)
                try:
                    from creative_session_state import sync_creative_session_from_session

                    sync_creative_session_from_session(session)
                except ImportError:
                    pass
                return
    except ImportError:
        pass
    session.pop("_pending_backing_context_apply", None)
    session.pop("_backing_creative_chart_sections", None)


def sync_creative_key_change(
    session: dict[str, Any],
    new_key: str,
    *,
    previous_key: str = "",
    st_like: Any | None = None,
) -> None:
    """Retranspose generated chords and sync global concert key on key picker change."""
    prev = str(previous_key or session.get(IMPROV_STYLE_KEY_TRACKER) or "").strip()
    new = str(new_key or "").strip()
    if not new:
        return
    gen = session.get("improv_generated_sections")
    if isinstance(gen, dict) and gen and prev and prev != new:
        session["improv_generated_sections"] = retranspose_generated_sections(
            gen,
            from_key=prev,
            to_key=new,
        )
    apply_creative_concert_key(session, new, st_like=st_like)
    session[IMPROV_STYLE_KEY_TRACKER] = new
    meta = dict(session.get("improv_style_meta") or {})
    meta["key"] = new
    session["improv_style_meta"] = meta
    invalidate_creative_backing_context(session)


def sync_style_jam_legacy_after_authoritative_key(
    session: dict[str, Any],
    new_key: str,
    *,
    st_like: Any | None = None,
) -> None:
    """After update_active_practice_key — sync trackers only; do not re-transpose sections."""
    new = str(new_key or "").strip()
    if not new:
        return
    apply_creative_concert_key(session, new, st_like=st_like, source="style_jam_authoritative_key")
    session[IMPROV_STYLE_KEY_TRACKER] = new
    meta = dict(session.get("improv_style_meta") or {})
    meta["key"] = new
    session["improv_style_meta"] = meta
    invalidate_creative_backing_context(session)
    _apply_pending_backing_context_on_page(session, st_like=st_like)


def sync_creative_style_jam_meta(session: dict[str, Any]) -> None:
    """Keep improv_style_meta aligned with Style Jam widgets (widget values win)."""
    from songs.playback_defaults import normalize_groove_label

    groove_intensity = str(session.get("improv_groove") or "Medium").strip()
    entry = str(session.get("improv_entry_mode") or "").strip()
    if entry == "Jam Session Generator":
        style_name = str(session.get("improv_jam_style") or "").strip()
        mood_name = str(session.get("improv_jam_mood") or "Mellow").strip()
        key_name = str(session.get("improv_jam_key") or "").strip()
        bpm_val = int(session.get("improv_jam_bpm") or 110)
    else:
        style_name = str(session.get("improv_style") or session.get("improv_jam_style") or "").strip()
        mood_name = str(session.get("improv_mood") or session.get("improv_jam_mood") or "Mellow").strip()
        key_name = str(session.get("improv_style_key") or session.get("improv_jam_key") or "").strip()
        bpm_val = int(session.get("improv_style_bpm") or session.get("improv_jam_bpm") or 110)
    backing_style = normalize_groove_label(style_name or "Pop groove")
    session["improv_style_meta"] = {
        "style": style_name,
        "backing_style": backing_style,
        "bpm": bpm_val,
        "groove": groove_intensity,
        "groove_intensity": groove_intensity,
        "key": key_name,
        "mood": mood_name,
        "difficulty": str(session.get("improv_difficulty") or "Intermediate").strip(),
        "meter": str(session.get("improv_style_meter") or session.get("backing_time_signature") or "4/4").strip(),
        "entry_mode": entry,
    }
    try:
        from creative_session_state import sync_creative_session_from_session

        sync_creative_session_from_session(session)
    except ImportError:
        pass


def on_improv_jam_key_change() -> None:
    import streamlit as st

    before_pick = guard_creative_catalog_pick_before_edit(
        st.session_state, writer="on_improv_jam_key_change"
    )
    try:
        from generated_jam_key_change import capture_generated_key_edit_intent

        capture_generated_key_edit_intent(
            st.session_state,
            widget_key="improv_jam_key",
        )
    except ImportError:
        pass
    verify_creative_catalog_pick_after_edit(
        st.session_state, before_pick=before_pick, writer="on_improv_jam_key_change"
    )


def user_sidebar_display_key_authoritative(session: dict[str, Any]) -> bool:
    """True when the user explicitly set display_key — Creative projection must not overwrite."""
    try:
        from active_song_state import _display_key_override_valid_for_identity

        if _display_key_override_valid_for_identity(session):
            return True
    except ImportError:
        pass
    src = str(session.get("display_key_change_source") or "").strip()
    if src in _SIDEBAR_USER_DISPLAY_KEY_SOURCES:
        return True
    if src and "sidebar" in src.lower():
        return True
    return False


def live_mission_backing_practice_key_widget_token(session: dict[str, Any]) -> str:
    """Stable Mission Backing sidebar widget, plus leftover n_opts-suffixed keys."""
    tok = str(session.get(MISSION_BACKING_PRACTICE_KEY_WIDGET) or "").strip()
    if tok:
        return tok
    for key, val in list(session.items()):
        name = str(key or "")
        if name.startswith("display_key_mission_backing") and str(val or "").strip():
            return str(val).strip()
    return ""


def canonical_mission_practice_key(session: dict[str, Any]) -> str:
    """Mission Backing Practice Key authority. Widget tokens are not canonical."""
    tok = str(session.get("improv_mission_concert_key") or "").strip()
    if tok:
        return tok
    try:
        from backing_context import get_backing_context

        ctx = get_backing_context(session)
        if ctx is not None and str(getattr(ctx, "source", "") or "").strip() == "mission":
            return str(
                getattr(ctx, "concert_key", "") or getattr(ctx, "key", "") or ""
            ).strip()
    except ImportError:
        pass
    return str(session.get("display_key") or session.get("concert_key") or "").strip()


def mission_backing_projection_concert_and_written(
    session: dict[str, Any],
    *,
    transposing_type: str = "Alto saxophone (Eb)",
) -> tuple[str, str]:
    """Concert + Written projection for Mission Backing. Ignores a stale widget."""
    concert = canonical_mission_practice_key(session)
    written = ""
    if concert:
        try:
            from instrument_transposition import written_key_for_type

            written = str(written_key_for_type(concert, transposing_type) or "").strip()
        except ImportError:
            written = ""
    return concert, written


def seed_mission_backing_practice_key_widget(
    session: dict[str, Any],
    *,
    options: list[str] | None = None,
) -> str:
    """H4-style pre-widget mirror: stale leftover Bm is not a user edit.

    Same-owner user edits already ran in on_change (canonical == widget).
    Entering/rebounding Mission Backing with leftover display_key_mission_backing
    must seed from canonical BEFORE the selectbox instantiates.
    """
    canonical = canonical_mission_practice_key(session)
    pending = str(session.pop("_pending_mission_practice_key", "") or "").strip()
    want = pending or canonical
    if options:
        opts = [str(o).strip() for o in options if str(o).strip()]
        if want and want not in opts and canonical in opts:
            want = canonical
    widget = str(session.get(MISSION_BACKING_PRACTICE_KEY_WIDGET) or "").strip()
    prev = str(session.get("_mission_practice_key_widget_mirror") or "").strip()
    # Widget is a mirror. Canonical Cm + leftover Bm is never a new user edit.
    stale = bool(want and widget and widget != want)
    if want and (not widget or stale):
        session[MISSION_BACKING_PRACTICE_KEY_WIDGET] = want
        widget = want
        _emit_h6_mission_pk_trace(
            session,
            "seed_mission_widget_from_canonical",
            canonical=canonical,
            pending=pending,
            want=want,
            prev_mirror=prev,
            stale=stale,
        )
    session["_mission_practice_key_widget_mirror"] = widget or want
    return widget or want


def prepare_mission_backing_practice_key_widget(
    session: dict[str, Any],
    *,
    options: list[str] | None = None,
) -> str:
    """Pre-selectbox Mission mirror. Catalog pending/leave tokens are not authority."""
    canonical = canonical_mission_practice_key(session)
    seeded = seed_mission_backing_practice_key_widget(session, options=options)
    pending_display = str(session.get("_pending_display_key") or "").strip()
    widget = str(session.get(MISSION_BACKING_PRACTICE_KEY_WIDGET) or seeded or "").strip()
    want = canonical or seeded
    if options:
        opts = [str(o).strip() for o in options if str(o).strip()]
        if want and want not in opts and canonical in opts:
            want = canonical
    if pending_display and pending_display != canonical:
        _emit_h6_mission_pk_trace(
            session,
            "ignore_catalog_pending_on_mission_widget",
            canonical=canonical,
            pending_display=pending_display,
            widget=widget,
        )
    if want and widget != want:
        session[MISSION_BACKING_PRACTICE_KEY_WIDGET] = want
        widget = want
        _emit_h6_mission_pk_trace(
            session,
            "prepare_mission_widget_canonical_wins",
            canonical=canonical,
            want=want,
            pending_display=pending_display,
        )
    session["_mission_practice_key_widget_mirror"] = widget or want
    return widget or want


def _mode_locked_practice_key_options(session: dict[str, Any], live: str) -> list[str]:
    """Tonic changes; mode stays inherited from the current mission/song source."""
    from music_theory import coerce_key_to_mode, key_mode, practice_keys_for_mode

    token = str(live or session.get("display_key") or session.get("concert_key") or "C").strip() or "C"
    mode = ""
    try:
        from backing_context import get_backing_context

        ctx = get_backing_context(session)
        src_key = str(getattr(ctx, "key", "") or getattr(ctx, "concert_key", "") or "").strip() if ctx else ""
        if src_key:
            mode = key_mode(src_key)
    except Exception:
        mode = ""
    if not mode:
        mode = key_mode(token) or "major"
    try:
        token = coerce_key_to_mode(token, mode) or token
    except Exception:
        pass
    options = list(practice_keys_for_mode(mode))
    if token not in options:
        options = [token] + [k for k in options if k != token]
    return options


def _sidebar_key_options_including(session: dict[str, Any], key: str) -> list[str]:
    from music_theory import key_mode, practice_keys_for_mode

    live = str(key or session.get("display_key") or "").strip() or "C"
    try:
        from backing_context import get_backing_context

        ctx = get_backing_context(session)
        src = str(getattr(ctx, "source", "") or "").strip() if ctx is not None else ""
        if src in {"mission", "song_improv"}:
            return _mode_locked_practice_key_options(session, live)
    except ImportError:
        pass
    options = list(practice_keys_for_mode(key_mode(live)))
    if live not in options:
        options = [live] + options
    return options


def is_creative_major_jam_active(session: dict[str, Any]) -> bool:
    """True when Style Jam or Jam Session Generator owns major-key context."""
    try:
        from backing_context import get_backing_context

        ctx = get_backing_context(session)
        src = str(getattr(ctx, "source", "") or "").strip() if ctx is not None else ""
        # Mission / SBI Backing must keep the full major+minor Practice Key space.
        if src in {"mission", "song_improv"}:
            return False
    except ImportError:
        pass
    try:
        from creative_key_sync import entry_jam_practice_key_authority_active

        if entry_jam_practice_key_authority_active(session):
            return True
    except ImportError:
        pass
    try:
        from musical_context_authority import catalog_song_should_own_sidebar_practice_key, song_catalog_context_owns_practice_key

        if catalog_song_should_own_sidebar_practice_key(session) or song_catalog_context_owns_practice_key(session):
            return False
    except ImportError:
        pass
    tab = str(
        session.get("improv_intelligence_tab") or session.get("creative_improv_intelligence_tab") or ""
    ).strip()
    if tab in {
        "Missions",
        "Song-Based Improvisation",
        "Phrase / Motif",
        "Harmony Map",
        "Live Coach",
        "Metrics & AI",
    }:
        return False
    page = str(session.get("studio_page") or "").strip().lower()
    entry = str(session.get("improv_entry_mode") or "").strip()
    if page == "creative" and entry in CREATIVE_MAJOR_JAM_MODES:
        return True
    if page not in {"creative", "backing"}:
        return False
    try:
        from backing_context import active_creative_backing_context, get_backing_context

        ctx = get_backing_context(session)
        if ctx is not None and ctx.source == "regular_song":
            return False
        creative = active_creative_backing_context(session)
        if creative is not None and creative.source == "entry_jam":
            mode = str(creative.entry_mode or creative.mode_label or "").strip()
            if mode in CREATIVE_MAJOR_JAM_MODES:
                return True
            short = mode.replace(" Mode", "").replace(" Generator", "")
            if short in {"Style Jam", "Jam Session"}:
                return True
    except ImportError:
        pass
    if entry not in CREATIVE_MAJOR_JAM_MODES:
        return False
    return True


def to_major_key_preserve_spelling(key: str) -> str:
    """Strip minor quality while keeping the user's flat/sharp spelling family."""
    from music_theory import CHROMATIC, key_is_minor, normalize_root, reference_spelling_mode, spell_pitch_class, split_chord

    text = str(key or "C").strip() or "C"
    if text.lower().endswith(" minor"):
        text = text[: -len(" minor")].strip() or "C"
    if not key_is_minor(text):
        return text
    root, _suffix = split_chord(text)
    nr = normalize_root(root)
    if nr not in CHROMATIC:
        return text
    mode = reference_spelling_mode(text)
    return spell_pitch_class(CHROMATIC.index(nr), mode=mode)


def creative_major_shape_key_options(session: dict[str, Any], selected: str = "") -> list[str]:
    """Major-only shape/written key options for Creative jam contexts."""
    pick = to_major_key_preserve_spelling(str(selected or "").strip())
    options = list(CREATIVE_MAJOR_KEY_OPTIONS)
    if pick and pick not in options:
        return [pick] + options
    if pick:
        return [pick] + [k for k in options if k != pick]
    return options


def creative_complete_concert_key_options(session: dict[str, Any], selected: str = "") -> list[str]:
    """Generated Jam Concert Key options — complete {tonic, mode} identity, not tonic-only."""
    from music_theory import ENHARMONIC_MAJOR_KEYS, ENHARMONIC_MINOR_KEYS, key_center_token, split_key_center

    pick_raw = str(selected or "").strip()
    pick = ""
    if pick_raw:
        tonic, mode = split_key_center(pick_raw)
        pick = key_center_token(tonic, mode)
    options = list(ENHARMONIC_MAJOR_KEYS) + list(ENHARMONIC_MINOR_KEYS)
    if pick and pick not in options:
        return [pick] + options
    if pick:
        return [pick] + [k for k in options if k != pick]
    return options


def sanitize_creative_major_chart_keys(
    session: dict[str, Any],
    *,
    st_like: Any | None = None,
) -> None:
    """Keep Guitar Shape tonic-only. Do not collapse song Practice Key to major."""
    if not is_creative_major_jam_active(session):
        return
    _ = st_like
    try:
        from guitar_capo import CAPO_SHAPE_KEY
    except ImportError:
        CAPO_SHAPE_KEY = "guitar_capo_shape_key"

    shape = str(session.get(CAPO_SHAPE_KEY) or "").strip()
    if shape:
        try:
            from guitar_capo import shape_tonic_only

            session[PENDING_CAPO_SHAPE_KEY] = shape_tonic_only(shape)
        except ImportError:
            session[PENDING_CAPO_SHAPE_KEY] = to_major_key_preserve_spelling(shape)


def creative_sidebar_key_options(session: dict[str, Any]) -> list[str]:
    """Major key options for Creative jam — preserves user enharmonic spelling."""
    try:
        from practice_key_mode import is_fixed_practice_key_mode, resolve_practice_concert_key_for_song

        if is_fixed_practice_key_mode(session):
            return [to_major_key_preserve_spelling(resolve_practice_concert_key_for_song(session, "C"))]
    except ImportError:
        pass
    selected = to_major_key_preserve_spelling(
        str(creative_entry_concert_key(session) or session.get("concert_key") or "").strip()
    )
    options = list(CREATIVE_MAJOR_KEY_OPTIONS)
    if selected and selected not in options:
        return [selected] + options
    if selected:
        return [selected] + [k for k in options if k != selected]
    return options


def _sidebar_preserve_user_display_key_options(
    st: Any,
    session: dict[str, Any],
    *,
    trace_phase: str,
    **trace_fields: Any,
) -> list[str] | None:
    """When the user explicitly set display_key, skip Creative/backing projection."""
    if not user_sidebar_display_key_authoritative(session):
        return None
    live = str(session.get("display_key") or session.get("concert_key") or "").strip()
    if not live:
        return None
    session["concert_key"] = live
    options = _sidebar_key_options_including(session, live)
    try:
        from display_key_sidebar_persistence_trace import (
            record_display_key_sidebar_event,
            record_display_key_sidebar_stage,
        )

        record_display_key_sidebar_stage(
            session,
            "next_rerun_projection",
            caller=trace_phase,
            skipped_projection=True,
            **trace_fields,
        )
        record_display_key_sidebar_event(
            session,
            trace_phase,
            skipped_projection=True,
            stage="next_rerun_projection",
            **trace_fields,
        )
    except ImportError:
        pass
    return options


def prepare_backing_context_sidebar_display_key(st: Any, session: dict[str, Any]) -> list[str]:
    """Apply non-major Creative backing concert key before the sidebar widget."""
    from music_theory import key_mode, practice_keys_for_mode
    from songs.key_state import PENDING_DISPLAY_KEY, _apply_display_key_before_widget

    flush_pending_creative_major_keys(session)

    # Custom SBI / Custom progression Backing: LAST_CUSTOM sticky + home mode
    # (never Shape Dm via preserve_user after overlay clear).
    try:
        from source_session_state import (
            custom_sbi_owns_sidebar_practice_key,
            prepare_sbi_custom_sidebar_display_key,
        )

        page_now = str(session.get("studio_page") or "").strip().lower()
        # Only on Creative/Backing — leftover SBI Custom preview on Songs must not
        # re-project Custom E over sealed Shape Dm.
        if page_now in {"creative", "backing"} and custom_sbi_owns_sidebar_practice_key(session):
            return prepare_sbi_custom_sidebar_display_key(st, session)
    except ImportError:
        pass

    # Mission Backing: tonic changes, mode stays inherited from the mission/source.
    try:
        from backing_context import get_backing_context

        ctx_mission = get_backing_context(session)
        if ctx_mission is not None and str(getattr(ctx_mission, "source", "") or "").strip() == "mission":
            session.pop("_sbi_custom_sealed_catalog_pk", None)
            session.pop("_sbi_custom_sealed_catalog_pick", None)
            live = str(
                session.get("improv_mission_concert_key")
                or session.get("display_key")
                or session.get("concert_key")
                or getattr(ctx_mission, "key", "")
                or "C"
            ).strip() or "C"
            options = _mode_locked_practice_key_options(session, live)
            selected = live if live in options else options[0]
            _apply_display_key_before_widget(
                st, selected, source="mission_backing_mode_locked_keys"
            )
            session["concert_key"] = str(session.get("display_key") or selected)
            session["improv_mission_concert_key"] = str(session.get("display_key") or selected)
            session.pop(PENDING_DISPLAY_KEY, None)
            try:
                from workflow_key_identity import resolve_song_practice_key_identity

                song_ident = resolve_song_practice_key_identity(session)
                if song_ident is not None:
                    session["_sidebar_key_identity_label"] = song_ident.practice_label
            except ImportError:
                pass
            return options
    except Exception:
        pass

    # Sidebar Practice Key wins for subordinate Backing sources (mission / SBI).
    # Never restore a sealed song-identity key over an explicit user change.
    preserved_early = _sidebar_preserve_user_display_key_options(
        st,
        session,
        trace_phase="prepare_backing_context_sidebar:preserve_user_key_early",
    )
    if preserved_early is not None:
        jam_owns = False
        try:
            from workflow_key_identity import generated_workflow_owns_practice_key

            jam_owns = bool(generated_workflow_owns_practice_key(session))
        except ImportError:
            jam_owns = False
        if not jam_owns:
            session.pop(PENDING_DISPLAY_KEY, None)
            try:
                from backing_context import get_backing_context
                from workflow_key_identity import resolve_song_practice_key_identity

                ctx_lbl = get_backing_context(session)
                src_lbl = str(getattr(ctx_lbl, "source", "") or "").strip() if ctx_lbl else ""
                if src_lbl in {"mission", "song_improv"}:
                    song_ident = resolve_song_practice_key_identity(session)
                    if song_ident is not None:
                        session["_sidebar_key_identity_label"] = song_ident.practice_label
            except ImportError:
                pass
            return preserved_early
    try:
        from backing_context import get_backing_context
        from workflow_key_identity import (
            generated_workflow_owns_practice_key,
            resolve_practice_key_identity_for_ui,
            resolve_song_practice_key_identity,
        )

        ctx_early = get_backing_context(session)
        ctx_source_early = str(getattr(ctx_early, "source", "") or "").strip() if ctx_early else ""
        if ctx_source_early == "mission":
            live_before = str(session.get("display_key") or session.get("concert_key") or "").strip()
            user_auth = user_sidebar_display_key_authoritative(session)
            try:
                from music_workflow_song_practice import ensure_missions_parent_practice_key_hydrated

                ensure_missions_parent_practice_key_hydrated(session)
            except ImportError:
                pass
            # Re-check after hydrate — hydrate must not pin over a same-rerun sidebar edit.
            preserved_mission = _sidebar_preserve_user_display_key_options(
                st,
                session,
                trace_phase="prepare_backing_context_sidebar:preserve_after_mission_hydrate",
            )
            if preserved_mission is not None:
                session.pop(PENDING_DISPLAY_KEY, None)
                return preserved_mission
            # Same-rerun sidebar widget value is already in display_key before hydrate.
            # Restore it even when change_source is not yet marked authoritative.
            if live_before:
                session["display_key"] = live_before
                session["concert_key"] = live_before
                session.pop(PENDING_DISPLAY_KEY, None)
                session["_pending_display_key"] = live_before
            if user_auth and live_before:
                session.pop(PENDING_DISPLAY_KEY, None)
                return _sidebar_key_options_including(session, live_before)
            song_ident = resolve_song_practice_key_identity(session)
            if song_ident is not None:
                # Mission Backing is subordinate to live Practice Key — never let a
                # sealed song-blob Dm win after the user already chose Em this run.
                selected = live_before or song_ident.practice_key_token
                try:
                    from music_theory import key_mode

                    if live_before and key_mode(live_before) == str(song_ident.practice_mode or key_mode(live_before)):
                        selected = live_before
                except Exception:
                    if live_before:
                        selected = live_before
                if live_before:
                    selected = live_before
                options = _mode_locked_practice_key_options(session, selected)
                if selected not in options:
                    options = [selected] + options
                _apply_display_key_before_widget(
                    st, selected, source="mission_backing_live_practice_key"
                )
                session["concert_key"] = selected
                session.pop(PENDING_DISPLAY_KEY, None)
                session["_sidebar_key_identity_label"] = song_ident.practice_label
                try:
                    from music_source_ownership import trace_practice_key_owner

                    trace_practice_key_owner(
                        session,
                        phase="prepare_backing_mission_key",
                        extra={
                            "selected": selected,
                            "live_before": live_before,
                            "song_ident": song_ident.practice_key_token,
                            "source": "mission_backing_live_practice_key",
                        },
                    )
                except ImportError:
                    pass
                return options
        if ctx_source_early == "song_improv":
            # SBI Backing is subordinate to live Practice Key — do not force sealed identity.
            live_sbi = str(session.get("display_key") or session.get("concert_key") or "").strip()
            if live_sbi:
                options = _sidebar_key_options_including(session, live_sbi)
                session["concert_key"] = live_sbi
                _apply_display_key_before_widget(st, live_sbi, source="sbi_backing_live_practice_key")
                try:
                    song_ident = resolve_song_practice_key_identity(session)
                    if song_ident is not None:
                        session["_sidebar_key_identity_label"] = song_ident.practice_label
                except Exception:
                    pass
                return options
        if generated_workflow_owns_practice_key(session) or ctx_source_early == "entry_jam":
            ident = resolve_practice_key_identity_for_ui(session)
            jam_like = ctx_source_early == "entry_jam" or (
                ident is not None and ident.workflow_owner in {"style_jam", "jam_session_generator"}
            )
            if jam_like:
                if generated_backing_owns_left_panel_key(session):
                    pending_token = ""
                    try:
                        from music_workflow_pending_generated_key_edit import (
                            consume_pending_generated_key_edit,
                            peek_pending_generated_key_edit,
                        )

                        pending = peek_pending_generated_key_edit(session)
                        if pending:
                            pending_token = str(pending.get("selected_key_token") or "").strip()
                            consume_pending_generated_key_edit(session, st=st)
                            ident = resolve_practice_key_identity_for_ui(session)
                    except ImportError:
                        pending_token = ""
                    gen = ident
                    if gen is None or str(gen.workflow_owner or "") not in {
                        "style_jam",
                        "jam_session_generator",
                    }:
                        try:
                            from workflow_key_identity import resolve_active_workflow_key_identity

                            gen = resolve_active_workflow_key_identity(session)
                        except ImportError:
                            gen = ident
                    if gen is not None:
                        selected = pending_token or gen.practice_key_token
                        options = practice_keys_for_mode(gen.practice_mode)
                        if selected not in options:
                            options = [selected] + options
                        try:
                            from h3_live_key_trace import emit

                            emit(
                                session,
                                "prepare_backing_generated_apply",
                                selected=selected,
                                pending_token=pending_token,
                                gen_owner=str(getattr(gen, "workflow_owner", "") or ""),
                                gen_sid=str(getattr(gen, "workflow_session_id", "") or ""),
                                gen_token=str(getattr(gen, "practice_key_token", "") or ""),
                            )
                        except Exception:
                            pass
                        _apply_display_key_before_widget(
                            st, selected, source="generated_backing_concert_key"
                        )
                        session["concert_key"] = selected
                        session["_sidebar_key_identity_label"] = gen.practice_label
                        return options
                song_ident = resolve_song_practice_key_identity(session)
                if song_ident is not None:
                    selected = song_ident.practice_key_token
                    options = practice_keys_for_mode(song_ident.practice_mode)
                    if selected not in options:
                        options = [selected] + options
                    _apply_display_key_before_widget(
                        st, selected, source="song_practice_while_generated_jam"
                    )
                    session["_sidebar_key_identity_label"] = song_ident.practice_label
                    return options
                live = str(session.get("display_key") or session.get("concert_key") or "").strip()
                if live:
                    live_mode = key_mode(live)
                    options = practice_keys_for_mode(
                        "minor" if live_mode == "minor" else "major"
                    )
                    if live not in options:
                        options = [live] + options
                    return options
                if ident is not None:
                    return practice_keys_for_mode(ident.practice_mode)
                return practice_keys_for_mode("major")
    except ImportError:
        pass
    preserved = _sidebar_preserve_user_display_key_options(
        st,
        session,
        trace_phase="prepare_backing_context_sidebar:preserve_user_key",
    )
    if preserved is not None:
        session.pop(PENDING_DISPLAY_KEY, None)
        return preserved
    try:
        from backing_context import active_creative_backing_context, get_backing_context
        from backing_musical_state import resolve_current_backing_musical_state
        from creative_session_state import (
            creative_session_is_active,
            get_creative_session,
        )

        creative = active_creative_backing_context(session)
        ctx = get_backing_context(session)
        creative_sess = get_creative_session(session) if creative is None else None
    except ImportError:
        creative = None
        ctx = None
        creative_sess = None
        resolve_current_backing_musical_state = None  # type: ignore[assignment]
    pending = session.pop(PENDING_DISPLAY_KEY, None)
    resolver_key = ""
    ctx_source = str(getattr(ctx, "source", "") or "").strip() if ctx is not None else ""
    sbi_custom_preview = False
    try:
        from songs.practice_key_state import sbi_uses_custom_progression_preview

        sbi_custom_preview = sbi_uses_custom_progression_preview(session)
    except ImportError:
        pass
    # song_improv with custom:: bound pick is Custom SBI Backing — same PK owner as
    # custom_progression (LAST_CUSTOM), not Global Active catalog.
    bound_custom = False
    if ctx is not None:
        bound = str(
            getattr(ctx, "bound_pick_key", "") or getattr(ctx, "active_song_id", "") or ""
        ).strip()
        if ctx_source == "song_improv" and bound.startswith("custom::"):
            bound_custom = True
    if ctx_source == "custom_progression" or sbi_custom_preview or bound_custom:
        ctx_source = "custom_progression"
    if ctx_source == "regular_song":
        try:
            from backing_musical_state import resolve_current_backing_musical_state

            resolver_key = str(
                resolve_current_backing_musical_state(session).practice_concert_key or ""
            ).strip()
        except ImportError:
            resolver_key = str(
                getattr(ctx, "concert_key", None)
                or getattr(ctx, "display_key", None)
                or getattr(ctx, "key", None)
                or ""
            ).strip()
        # Sticky Practice Key for the live Catalog pick outranks a resealed
        # backing-context original (Bm) after leave→Practice→return (H2).
        try:
            from songs.practice_key_state import get_practice_concert_key, resolve_practice_source_pick

            sticky = str(
                get_practice_concert_key(session, resolve_practice_source_pick(session)) or ""
            ).strip()
            if sticky:
                resolver_key = sticky
        except ImportError:
            pass
    elif ctx_source == "custom_progression":
        home_key = ""
        if ctx is not None:
            home_key = str(getattr(ctx, "key", "") or "").strip()
        try:
            from custom_progression_lab import CPL_ACTIVE_KEY, cpl_draft_written_key, ensure_original_structure

            active = ensure_original_structure(session.get(CPL_ACTIVE_KEY) or {})
            home_key = cpl_draft_written_key(active) or home_key
        except ImportError:
            pass
        try:
            from practice_key_mode import is_fixed_practice_key_mode, resolve_practice_concert_key_for_song
            from songs.practice_key_state import resolve_settings_pick_for_write

            if is_fixed_practice_key_mode(session):
                pick = resolve_settings_pick_for_write(session)
                selected = resolve_practice_concert_key_for_song(
                    session,
                    home_key or "C",
                    pick_key=pick,
                    fallback=home_key or "C",
                )
            else:
                raise ImportError
        except ImportError:
            try:
                from backing_context import _live_backing_concert_keys

                _, _, resolver_key = _live_backing_concert_keys(session)
            except ImportError:
                resolver_key = str(
                    getattr(ctx, "concert_key", None)
                    or getattr(ctx, "display_key", None)
                    or getattr(ctx, "key", None)
                    or ""
                ).strip()
            try:
                from songs.practice_key_state import (
                    get_practice_concert_key,
                    resolve_settings_pick_for_write,
                )

                # Custom SBI / Custom progression backing: sticky on custom pick,
                # never Global Active catalog (Shape Dm must not win here).
                write_pick = str(resolve_settings_pick_for_write(session) or "").strip()
                saved = (
                    get_practice_concert_key(session, write_pick) if write_pick else ""
                )
            except ImportError:
                saved = ""
            live = str(session.get("display_key") or session.get("concert_key") or "").strip()
            # Prefer custom sticky/home over leftover catalog live (Shape Dm).
            selected = str(
                pending or saved or home_key or resolver_key or live or "C"
            ).strip() or "C"
    elif creative and resolve_current_backing_musical_state is not None:
        resolver_key = str(
            resolve_current_backing_musical_state(session).practice_concert_key or ""
        ).strip()
    elif (
        creative_sess is not None
        and creative_session_is_active(session)
        and str(session.get("active_music_source") or "").strip() != "catalog"
        and not (ctx is not None and str(getattr(ctx, "source", "") or "").strip() == "custom_progression")
    ):
        resolver_key = str(creative_sess.concert_key or creative_sess.display_key or "").strip()
    if ctx_source != "custom_progression":
        selected = str(
            pending
            or resolver_key
            or (creative_sess.concert_key if creative_sess and creative_session_is_active(session) else "")
            or session.get("concert_key")
            or session.get("display_key")
            or (creative.concert_key if creative else "")
            or "C"
        ).strip() or "C"
    try:
        from practice_key_mode import is_fixed_practice_key_mode, resolve_practice_concert_key_for_song
        from workflow_key_identity import fixed_practice_key_projection_blocked

        if is_fixed_practice_key_mode(session) and ctx_source != "custom_progression":
            if not fixed_practice_key_projection_blocked(session):
                selected = resolve_practice_concert_key_for_song(session, selected, fallback=selected)
    except ImportError:
        pass
    try:
        from workflow_key_identity import resolve_practice_key_identity_for_ui

        ident = resolve_practice_key_identity_for_ui(session)
        if ident is not None:
            selected = ident.practice_key_token
    except ImportError:
        pass
    list_mode = "major"
    try:
        from workflow_key_identity import resolve_practice_key_identity_for_ui

        ident_opts = resolve_practice_key_identity_for_ui(session)
        if ident_opts is not None:
            list_mode = ident_opts.practice_mode
    except ImportError:
        list_mode = key_mode(selected)
    options = practice_keys_for_mode(list_mode)
    if selected not in options:
        options = [selected] + options
    if ctx_source == "custom_progression":
        live = str(session.get("display_key") or session.get("concert_key") or "").strip()
        session["concert_key"] = selected
        if pending is not None or not live or live != selected:
            _apply_display_key_before_widget(st, selected, source="backing_context_concert")
            session["concert_key"] = selected
        return options
    if user_sidebar_display_key_authoritative(session):
        live = str(session.get("display_key") or session.get("concert_key") or "").strip()
        # Generated Style/Jam owners may still resolve identity; subordinate
        # mission / song_improv Backing must keep the live sidebar token.
        try:
            from workflow_key_identity import (
                active_workflow_owns_practice_key,
                generated_workflow_owns_practice_key,
                resolve_practice_key_identity_for_ui,
            )

            subordinate = ctx_source in {"mission", "song_improv"}
            if (
                not subordinate
                and active_workflow_owns_practice_key(session)
                and generated_workflow_owns_practice_key(session)
            ):
                ident = resolve_practice_key_identity_for_ui(session)
                if ident is not None:
                    live = ident.practice_key_token
        except ImportError:
            pass
        if live:
            options = _sidebar_key_options_including(session, live)
            session["concert_key"] = live
            try:
                from display_key_sidebar_persistence_trace import record_display_key_sidebar_event

                record_display_key_sidebar_event(
                    session,
                    "prepare_backing_context_sidebar:preserve_user_key",
                    skipped_projection=True,
                    resolver_key=resolver_key or None,
                    selected_would_have_been=selected,
                )
            except ImportError:
                pass
            return options
    _apply_display_key_before_widget(st, selected, source="backing_context_concert")
    session["concert_key"] = selected
    return options


def prepare_creative_sidebar_display_key(st: Any, session: dict[str, Any]) -> list[str]:
    """Apply Creative concert key before the sidebar Practice / Concert Key widget."""
    from songs.key_state import PENDING_DISPLAY_KEY, _apply_display_key_before_widget, display_key_options

    # Creative SBI → Custom: overlay LAST_CUSTOM sticky + home mode (not Shape).
    try:
        from source_session_state import custom_sbi_owns_sidebar_practice_key, prepare_sbi_custom_sidebar_display_key

        if custom_sbi_owns_sidebar_practice_key(session):
            return prepare_sbi_custom_sidebar_display_key(st, session)
    except ImportError:
        pass

    try:
        from source_session_state import clear_sbi_custom_sidebar_overlay_if_needed

        clear_sbi_custom_sidebar_overlay_if_needed(session)
    except ImportError:
        pass

    preserved = _sidebar_preserve_user_display_key_options(
        st,
        session,
        trace_phase="prepare_creative_sidebar:preserve_user_key",
    )
    if preserved is not None:
        session.pop(PENDING_DISPLAY_KEY, None)
        return preserved

    if generated_backing_owns_left_panel_key(session):
        from music_theory import key_mode, practice_keys_for_mode

        jam_tok = str(
            session.get("improv_jam_key")
            or session.get("improv_style_key")
            or session.get("display_key")
            or session.get("concert_key")
            or ""
        ).strip()
        if jam_tok:
            options = practice_keys_for_mode("minor" if key_mode(jam_tok) == "minor" else "major")
            if jam_tok not in options:
                options = [jam_tok] + options
            _apply_display_key_before_widget(st, jam_tok, source="generated_backing_jam_owner")
            session["concert_key"] = jam_tok
            session["display_key"] = jam_tok
            return options

    try:
        from sidebar_key_identity import resolve_sidebar_key_identity

        ident = resolve_sidebar_key_identity(session)
        try:
            from musical_context_authority import catalog_song_should_own_sidebar_practice_key

            catalog_owns = catalog_song_should_own_sidebar_practice_key(session)
        except ImportError:
            catalog_owns = ident.owner in {
                "song_based_improvisation",
                "mission_jam",
                "regular_catalog_backing",
                "regular_custom_backing",
            }
        if catalog_owns or ident.owner in {
            "song_based_improvisation",
            "mission_jam",
            "regular_catalog_backing",
            "regular_custom_backing",
        }:
            token = ident.selector_token
            options = display_key_options(token)
            if token not in options:
                options = [token] + options
            _apply_display_key_before_widget(st, token, source="catalog_song_sidebar_authority")
            session["concert_key"] = token
            session["_sidebar_key_identity_label"] = ident.label
            return options
    except ImportError:
        pass

    try:
        from musical_context_authority import catalog_song_should_own_sidebar_practice_key, resolve_authoritative_practice_key

        if catalog_song_should_own_sidebar_practice_key(session):
            pk = resolve_authoritative_practice_key(session)
            token = pk.practice_key_token
            options = display_key_options(token)
            if token not in options:
                options = [token] + options
            _apply_display_key_before_widget(st, token, source="catalog_song_sidebar_authority")
            session["concert_key"] = token
            return options
    except ImportError:
        pass

    try:
        from workflow_key_identity import generated_workflow_owns_practice_key, resolve_practice_key_identity_for_ui
        from backing_context import get_backing_context

        ctx_now = get_backing_context(session)
        ctx_is_jam = str(getattr(ctx_now, "source", "") or "") == "entry_jam"
        entry_now = str(session.get("improv_entry_mode") or "").strip()
        if generated_workflow_owns_practice_key(session) or ctx_is_jam or entry_now in {
            "Style Jam Mode",
            "Jam Session Generator",
        }:
            try:
                from generated_workflow_projection import project_generated_owner_from_active_blob

                project_generated_owner_from_active_blob(
                    session, writer="prepare_creative_sidebar", include_controls=False
                )
            except ImportError:
                pass
            ident = resolve_practice_key_identity_for_ui(session)
            from music_theory import key_mode, practice_keys_for_mode
            from workflow_key_identity import resolve_song_practice_key_identity

            if generated_backing_owns_left_panel_key(session):
                gen = ident
                if gen is None or str(gen.workflow_owner or "") not in {
                    "style_jam",
                    "jam_session_generator",
                }:
                    try:
                        from workflow_key_identity import resolve_active_workflow_key_identity

                        gen = resolve_active_workflow_key_identity(session)
                    except ImportError:
                        gen = ident
                if gen is not None:
                    token = gen.practice_key_token
                    options = practice_keys_for_mode(gen.practice_mode)
                    if token not in options:
                        options = [token] + options
                    _apply_display_key_before_widget(
                        st, token, source="generated_backing_concert_key"
                    )
                    session["concert_key"] = token
                    session["_sidebar_key_identity_label"] = gen.practice_label
                    return options

            song_ident = resolve_song_practice_key_identity(session)
            if song_ident is not None:
                token = song_ident.practice_key_token
                options = practice_keys_for_mode(song_ident.practice_mode)
                if token not in options:
                    options = [token] + options
                _apply_display_key_before_widget(
                    st, token, source="song_practice_while_generated_jam"
                )
                session["_sidebar_key_identity_label"] = song_ident.practice_label
                return options
            live = str(session.get("display_key") or session.get("concert_key") or "").strip()
            if live:
                live_mode = key_mode(live)
                options = practice_keys_for_mode(
                    "minor" if live_mode == "minor" else "major"
                )
                if live not in options:
                    options = [live] + options
                return options
            if ident is not None:
                token = ident.practice_key_token
                options = practice_keys_for_mode(ident.practice_mode)
                if token not in options:
                    options = [token] + options
                return options
            return display_key_options(live or "C")
    except ImportError:
        pass

    flush_pending_creative_major_keys(session)
    preserved = _sidebar_preserve_user_display_key_options(
        st,
        session,
        trace_phase="prepare_creative_sidebar:preserve_user_key",
    )
    if preserved is not None:
        session.pop(PENDING_DISPLAY_KEY, None)
        return preserved
    options = creative_sidebar_key_options(session)
    backing_key = ""
    try:
        from backing_context import active_creative_backing_context
        from backing_musical_state import resolve_current_backing_musical_state

        creative_ctx = active_creative_backing_context(session)
        if creative_ctx is not None:
            backing_key = str(
                resolve_current_backing_musical_state(session).practice_concert_key
                or creative_ctx.concert_key
                or creative_ctx.display_key
                or ""
            ).strip()
    except ImportError:
        pass
    pending = session.pop(PENDING_DISPLAY_KEY, None)
    selected = str(
        pending
        or backing_key
        or creative_entry_concert_key(session)
        or session.get("concert_key")
        or session.get("display_key")
        or ""
    ).strip()
    try:
        from practice_key_mode import is_fixed_practice_key_mode, resolve_practice_concert_key_for_song
        from workflow_key_identity import fixed_practice_key_projection_blocked

        if is_fixed_practice_key_mode(session) and not fixed_practice_key_projection_blocked(session):
            selected = resolve_practice_concert_key_for_song(session, "C", fallback=selected or "C")
    except ImportError:
        pass
    selected = to_major_key_preserve_spelling(selected)
    if user_sidebar_display_key_authoritative(session):
        live = str(session.get("display_key") or session.get("concert_key") or "").strip()
        try:
            from workflow_key_identity import generated_workflow_owns_practice_key, resolve_practice_key_identity_for_ui

            if generated_workflow_owns_practice_key(session):
                ident = resolve_practice_key_identity_for_ui(session)
                if ident is not None:
                    live = ident.practice_key_token
        except ImportError:
            pass
        if live:
            options = _sidebar_key_options_including(session, live)
            session["concert_key"] = live
            try:
                from display_key_sidebar_persistence_trace import record_display_key_sidebar_event

                record_display_key_sidebar_event(
                    session,
                    "prepare_creative_sidebar:preserve_user_key",
                    skipped_projection=True,
                    backing_key=backing_key or None,
                )
            except ImportError:
                pass
            return options
    if selected:
        if selected not in options:
            options = [selected] + [k for k in options if k != selected]
        _apply_display_key_before_widget(st, selected, source="creative_concert_key")
    elif session.get("display_key") not in options:
        _apply_display_key_before_widget(st, options[0], source="creative_default")
    session["concert_key"] = str(session.get("display_key") or options[0])
    entry = str(session.get("improv_entry_mode") or "").strip()
    if entry == "Style Jam Mode":
        session[PENDING_IMPROV_STYLE_KEY] = session["concert_key"]
    elif entry == "Jam Session Generator":
        session[PENDING_IMPROV_JAM_KEY] = session["concert_key"]
    sanitize_creative_major_chart_keys(session, st_like=st)
    post_sanitize = session.pop(PENDING_DISPLAY_KEY, None)
    if post_sanitize is not None:
        _apply_display_key_before_widget(st, str(post_sanitize), source="creative_sanitize")
    flush_pending_creative_major_keys(session)
    return options


def should_use_live_practice_key_sidebar(session: dict[str, Any]) -> bool:
    """Use session practice concert key instead of catalog original-key defaults."""
    try:
        from songs.music_source import cpl_session_is_active, custom_progression_is_active, is_custom_progression

        if is_custom_progression(session) or custom_progression_is_active(session) or cpl_session_is_active(session):
            return True
    except ImportError:
        pass
    page = str(session.get("studio_page") or "").strip().lower()
    # Catalog Songs / Practice after a specialized SBI Custom visit must not keep
    # leftover Song-Based Improvisation / song_improv backing as the sidebar PK
    # owner. That built Custom major options (C, D, E…) while Shape Original is Bm,
    # so the widget remounted to C and overwrote Shape sticky Dm.
    if page in {"picker", "songs", "practice"}:
        return False
    try:
        from backing_musical_state import should_skip_regular_song_defaults

        if should_skip_regular_song_defaults(session):
            return True
    except ImportError:
        pass
    try:
        from backing_context import catalog_or_custom_backing_is_authoritative, get_backing_context

        if catalog_or_custom_backing_is_authoritative(session):
            ctx = get_backing_context(session)
            if ctx is not None and ctx.source == "regular_song":
                return False
    except ImportError:
        pass
    if page == "creative":
        return True
    if page == "custom":
        return True
    if page == "backing":
        return True
    entry = str(session.get("improv_entry_mode") or "").strip()
    if entry in {"Style Jam Mode", "Jam Session Generator", "Song-Based Improvisation"}:
        return True
    return False


def _resolve_creative_entry_mode(session: dict[str, Any]) -> str:
    """Infer improv entry mode from widgets or active backing_context."""
    entry = str(session.get("improv_entry_mode") or "").strip()
    if entry:
        return entry
    try:
        from backing_context import get_backing_context

        ctx = get_backing_context(session)
        if ctx is None:
            return ""
        if ctx.source == "song_improv":
            return "Song-Based Improvisation"
        if ctx.source == "entry_jam":
            return str(ctx.entry_mode or "Style Jam Mode").strip()
    except ImportError:
        pass
    return ""


def _creative_song_owning_tab(session: dict[str, Any]) -> str:
    """Creative analysis tab that owns catalog/custom song Practice Key (not Style Jam)."""
    page = str(session.get("studio_page") or "").strip().lower()
    if page != "creative":
        return ""
    tab = str(
        session.get("improv_intelligence_tab")
        or session.get("creative_improv_intelligence_tab")
        or ""
    ).strip()
    if tab in {
        "Missions",
        "Song-Based Improvisation",
        "Phrase / Motif",
        "Harmony Map",
        "Live Coach",
    }:
        return tab
    return ""


def _creative_sidebar_key_sync_active(session: dict[str, Any]) -> bool:
    """True when sidebar key changes should retranspose Creative / backing handoff."""
    if is_creative_major_jam_active(session):
        return True
    if _creative_song_owning_tab(session):
        return True
    try:
        from backing_context import get_backing_context

        ctx = get_backing_context(session)
        if ctx is not None and ctx.source in {
            "entry_jam",
            "mission",
            "song_improv",
            "custom_progression",
        }:
            page = str(session.get("studio_page") or "").strip().lower()
            return page in {"creative", "backing"}
    except ImportError:
        pass
    return False


def _apply_pending_backing_context_on_page(session: dict[str, Any], *, st_like: Any | None = None) -> None:
    """Apply refreshed backing_context to widgets during the same rerun (Backing page)."""
    page = str(session.get("studio_page") or "").strip().lower()
    if page != "backing":
        return
    try:
        from backing_context import (
            PENDING_BACKING_CONTEXT_APPLY,
            apply_backing_context_to_session,
            get_backing_context,
        )
    except ImportError:
        return
    if not session.get(PENDING_BACKING_CONTEXT_APPLY):
        return
    ctx = get_backing_context(session)
    if ctx is None:
        return
    apply_backing_context_to_session(session, ctx, st_like=st_like, widget_safe=True)
    session.pop(PENDING_BACKING_CONTEXT_APPLY, None)


def sync_sidebar_creative_concert_key(session: dict[str, Any], *, st_like: Any | None = None) -> None:
    """Retranspose Creative progressions when sidebar Practice Concert Key changes."""
    new = str(session.get("display_key") or "").strip()
    if not new:
        return
    try:
        from backing_context import get_backing_context

        page = str(session.get("studio_page") or "").strip().lower()
        ctx = get_backing_context(session)
        if page == "backing" and ctx is not None and str(ctx.source or "") == "mission":
            apply_specialized_mission_practice_key(session, new)
            return
    except ImportError:
        pass
    try:
        from workflow_key_identity import normalize_user_practice_key_selection

        _tonic, _mode, new = normalize_user_practice_key_selection(
            new,
            default_mode="major",
        )
    except ImportError:
        pass
    try:
        from music_workflow_mutation import update_active_practice_key
        from music_workflow_state_store import get_active_workflow_pointer

        ptr = get_active_workflow_pointer(session)
        jam_backing = generated_backing_owns_left_panel_key(session)
        if jam_backing:
            apply_specialized_jam_practice_key(session, new)
            try:
                from jam_generator_live_runtime_trace import append_jam_sidebar_key_trace

                append_jam_sidebar_key_trace(
                    session,
                    "generated_backing_left_panel_key",
                    new_display_key=new,
                    workflow_owner=str(session.get("improv_entry_mode") or ""),
                    widget_key="improv_jam_key",
                )
            except ImportError:
                pass
            return
        if ptr and ptr.workflow_owner in {"style_jam", "jam_session_generator"}:
            # Creative page: global sidebar is catalog song Practice Key.
            try:
                from music_workflow_song_practice import ensure_song_practice_blob_for_active_song

                orig = ""
                selected = session.get("selected_song")
                if isinstance(selected, dict):
                    orig = str(selected.get("key") or "")
                ensure_song_practice_blob_for_active_song(
                    session, practice_key=new, original_key=orig
                )
            except ImportError:
                pass
            try:
                from jam_generator_live_runtime_trace import append_jam_sidebar_key_trace

                append_jam_sidebar_key_trace(
                    session,
                    "sidebar_song_practice_while_generated_owner",
                    new_display_key=new,
                    workflow_owner=str(ptr.workflow_owner or ""),
                    display_key=str(session.get("display_key") or ""),
                    improv_style_key=str(session.get("improv_style_key") or ""),
                )
            except ImportError:
                pass
            return
        # Custom SBI preview / Custom-bound song_improv backing: Practice Key sticky
        # belongs to LAST_CUSTOM — never the Global Active catalog (Shape) pick.
        # Only on Creative/Backing — leftover SBI Custom flags must not steal Songs writes.
        try:
            from songs.practice_key_state import (
                resolve_settings_pick_for_write,
                set_practice_concert_key,
                sbi_uses_custom_progression_preview,
            )
            from backing_context import get_backing_context as _get_bk_ctx

            _page_cus = str(session.get("studio_page") or "").strip().lower()
            _custom_owner = False
            try:
                from workflow_musical_authority import custom_owns_active_song_material

                _custom_owner = custom_owns_active_song_material(session)
            except ImportError:
                _custom_owner = False
            if _page_cus in {"creative", "backing"} or _custom_owner:
                try:
                    _ctx_cus = _get_bk_ctx(session)
                except Exception:
                    _ctx_cus = None
                _bound = str(
                    getattr(_ctx_cus, "bound_pick_key", "")
                    or getattr(_ctx_cus, "active_song_id", "")
                    or ""
                ).strip()
                _src = (
                    str(getattr(_ctx_cus, "source", "") or "").strip()
                    if _ctx_cus is not None
                    else ""
                )
                _write = str(resolve_settings_pick_for_write(session) or "").strip()
                _preview = bool(sbi_uses_custom_progression_preview(session))
                _custom_sbi = bool(
                    _preview
                    or _src == "custom_progression"
                    or (_src == "song_improv" and _bound.startswith("custom::"))
                    or _write.startswith("custom::")
                )
                if _custom_sbi or _preview:
                    pick = _write if _write.startswith("custom::") else _bound
                    if not pick.startswith("custom::"):
                        try:
                            from songs.music_source import LAST_CUSTOM_STATE_KEY, custom_pick_key_for
                            from custom_progression_lab import CPL_ACTIVE_KEY

                            snap = session.get(LAST_CUSTOM_STATE_KEY)
                            if isinstance(snap, dict) and isinstance(snap.get("active"), dict):
                                pick = str(custom_pick_key_for(snap["active"]) or "").strip()
                            if not pick.startswith("custom::"):
                                live_cpl = session.get(CPL_ACTIVE_KEY)
                                if isinstance(live_cpl, dict):
                                    pick = str(custom_pick_key_for(live_cpl) or "").strip()
                        except ImportError:
                            pick = ""
                    if pick.startswith("custom::"):
                        persist_last_custom = True
                        try:
                            from source_session_state import (
                                coerce_token_to_custom_home_mode,
                                sbi_custom_visit_is_local_only,
                            )

                            new = coerce_token_to_custom_home_mode(session, new)
                            persist_last_custom = not bool(
                                sbi_custom_visit_is_local_only(session)
                            )
                        except ImportError:
                            persist_last_custom = True
                        session["display_key"] = new
                        session["concert_key"] = new
                        session["_sbi_custom_visit_pk"] = new
                        session["_sbi_custom_last_visit_pk"] = new
                        if persist_last_custom:
                            set_practice_concert_key(session, new, pick_key=pick)
                            # Do not call on_global_display_key_change here — historically it
                            # re-wrote resolve_practice_source_pick (catalog Shape) and bled PK.
                            session["cpl_last_display_key"] = new
                        invalidate_creative_backing_context(session)
                        _apply_pending_backing_context_on_page(session, st_like=st_like)
                        return
                    # Preview is Custom but pick unresolved — never write catalog Shape.
                    if _preview:
                        session["concert_key"] = new
                        return
        except Exception:
            # Never let a backing-context failure fall through to catalog Shape writes
            # while SBI Custom preview is active.
            try:
                from songs.practice_key_state import sbi_uses_custom_progression_preview

                if sbi_uses_custom_progression_preview(session) and str(
                    session.get("studio_page") or ""
                ).strip().lower() in {"creative", "backing"}:
                    session["concert_key"] = new
                    return
            except Exception:
                pass
        if ptr and ptr.workflow_owner in {"song_based_improvisation", "mission_jam"}:
            _ptr_page = str(session.get("studio_page") or "").strip().lower()
            if _ptr_page not in {"creative", "backing"}:
                pass  # Songs/Practice: fall through to catalog sticky write
            else:
                try:
                    from song_practice_key_sidebar_change import (
                        finalize_sidebar_song_practice_key_after_mutation,
                        sidebar_song_practice_key_mutation_deferred,
                    )

                    if sidebar_song_practice_key_mutation_deferred(session):
                        return
                except ImportError:
                    pass
                result = update_active_practice_key(
                    session, new, source="sidebar_song_improv", transpose_progression=True
                )
                if not result.ok:
                    return
                try:
                    from song_practice_key_sidebar_change import finalize_sidebar_song_practice_key_after_mutation

                    finalize_sidebar_song_practice_key_after_mutation(session, new, st_like=st_like)
                except ImportError:
                    session["concert_key"] = new
                return
    except ImportError:
        pass
    try:
        from backing_context import get_backing_context

        ctx = get_backing_context(session)
        if ctx is not None and ctx.source == "custom_progression":
            session["concert_key"] = new
            try:
                from songs.practice_key_state import resolve_settings_pick_for_write, set_practice_concert_key

                # Must use settings write pick (LAST_CUSTOM), never Global Active catalog.
                set_practice_concert_key(
                    session,
                    new,
                    pick_key=resolve_settings_pick_for_write(session),
                )
            except ImportError:
                pass
            session["cpl_last_display_key"] = new
            invalidate_creative_backing_context(session)
            _apply_pending_backing_context_on_page(session, st_like=st_like)
            return
    except ImportError:
        pass
    entry = _resolve_creative_entry_mode(session)
    if entry and not str(session.get("improv_entry_mode") or "").strip():
        session["improv_entry_mode"] = entry
    try:
        from studio_page_state import resolve_improv_song_source

        if (
            entry == "Song-Based Improvisation"
            and resolve_improv_song_source(session) == "Custom progression"
            and str(session.get("studio_page") or "").strip().lower() in {"creative", "backing"}
        ):
            session["concert_key"] = new
            session["_sbi_custom_visit_pk"] = new
            session["_sbi_custom_last_visit_pk"] = new
            try:
                from songs.music_source import custom_progression_is_active
                from songs.practice_key_state import (
                    resolve_settings_pick_for_write,
                    set_practice_concert_key,
                )

                if custom_progression_is_active(session):
                    set_practice_concert_key(
                        session,
                        new,
                        pick_key=resolve_settings_pick_for_write(session),
                    )
                    session["cpl_last_display_key"] = new
            except ImportError:
                pass
            invalidate_creative_backing_context(session)
            _apply_pending_backing_context_on_page(session, st_like=st_like)
            return
    except ImportError:
        pass
    if entry == "Song-Based Improvisation" and str(session.get("studio_page") or "").strip().lower() in {
        "creative",
        "backing",
    }:
        try:
            from song_practice_key_sidebar_change import (
                finalize_sidebar_song_practice_key_after_mutation,
                sidebar_song_practice_key_mutation_deferred,
            )

            if sidebar_song_practice_key_mutation_deferred(session):
                return
        except ImportError:
            pass
        try:
            from music_workflow_song_practice import (
                ensure_song_practice_blob_for_active_song,
                song_based_blob_session_id,
            )
            from music_workflow_state_store import (
                ActiveWorkflowPointer,
                get_active_workflow_pointer,
                set_active_workflow_pointer,
            )

            old = str(session.get("concert_key") or "").strip() or new
            orig = ""
            selected = session.get("selected_song")
            if isinstance(selected, dict):
                orig = str(selected.get("key") or "")
            ensure_song_practice_blob_for_active_song(
                session, practice_key=old, original_key=orig
            )
            ptr = get_active_workflow_pointer(session)
            if ptr is None or str(ptr.workflow_owner or "") not in {
                "song_based_improvisation",
                "mission_jam",
            }:
                set_active_workflow_pointer(
                    session,
                    ActiveWorkflowPointer(
                        workflow_owner="song_based_improvisation",
                        workflow_session_id=song_based_blob_session_id(session),
                    ),
                    source="sidebar_song_improv",
                )
        except ImportError:
            pass
        mutation_ok = False
        try:
            from music_workflow_mutation import update_active_practice_key

            result = update_active_practice_key(
                session,
                new,
                source="sidebar_song_improv",
                transpose_progression=True,
            )
            mutation_ok = bool(result.ok)
        except ImportError:
            mutation_ok = False
        if not mutation_ok:
            session["concert_key"] = new
        try:
            from song_practice_key_sidebar_change import finalize_sidebar_song_practice_key_after_mutation

            finalize_sidebar_song_practice_key_after_mutation(session, new, st_like=st_like)
        except ImportError:
            session["concert_key"] = new
        return
    # Creative Missions / Motif / Live Coach / Harmony (no backing ctx yet): same
    # song-blob mutation Mission Backing uses, so caption + example follow sidebar.
    creative_tab = _creative_song_owning_tab(session)
    if creative_tab:
        try:
            from workflow_key_identity import (
                normalize_user_practice_key_selection,
                resolve_song_practice_key_identity,
            )

            ident = resolve_song_practice_key_identity(session)
            default_mode = str(ident.practice_mode if ident else "minor").strip().lower()
            if default_mode not in {"major", "minor"}:
                default_mode = "minor"
            _tonic, _mode, new = normalize_user_practice_key_selection(
                new, default_mode=default_mode
            )
            session["display_key"] = new
            session["concert_key"] = new
        except ImportError:
            pass
        try:
            from song_practice_key_sidebar_change import (
                finalize_sidebar_song_practice_key_after_mutation,
                sidebar_song_practice_key_mutation_deferred,
            )

            if sidebar_song_practice_key_mutation_deferred(session):
                return
        except ImportError:
            pass
        try:
            from music_workflow_song_practice import (
                ensure_song_practice_blob_for_active_song,
                mission_blob_session_id,
                song_based_blob_session_id,
            )
            from music_workflow_state_store import (
                ActiveWorkflowPointer,
                get_active_workflow_pointer,
                set_active_workflow_pointer,
            )

            owner = (
                "mission_jam"
                if creative_tab == "Missions"
                else "song_based_improvisation"
            )
            sid = (
                mission_blob_session_id(session)
                if owner == "mission_jam"
                else song_based_blob_session_id(session)
            )
            ptr = get_active_workflow_pointer(session)
            if ptr is None or str(ptr.workflow_owner or "") not in {
                "song_based_improvisation",
                "mission_jam",
            }:
                set_active_workflow_pointer(
                    session,
                    ActiveWorkflowPointer(workflow_owner=owner, workflow_session_id=sid),
                    source="sidebar_creative_song_tab",
                )
            old = str(session.get("concert_key") or "").strip() or new
            orig = ""
            selected = session.get("selected_song")
            if isinstance(selected, dict):
                orig = str(selected.get("key") or "")
            ensure_song_practice_blob_for_active_song(
                session, practice_key=old, original_key=orig
            )
        except ImportError:
            pass
        mutation_ok = False
        try:
            from music_workflow_mutation import update_active_practice_key

            result = update_active_practice_key(
                session,
                new,
                source="sidebar_song_improv",
                transpose_progression=True,
            )
            mutation_ok = bool(result.ok)
        except ImportError:
            mutation_ok = False
        if not mutation_ok:
            session["concert_key"] = new
            session["display_key"] = new
        try:
            from song_practice_key_sidebar_change import finalize_sidebar_song_practice_key_after_mutation

            finalize_sidebar_song_practice_key_after_mutation(session, new, st_like=st_like)
        except ImportError:
            session["concert_key"] = new
        return
    if not _creative_sidebar_key_sync_active(session):
        # Songs / Practice / non-Creative surfaces: still persist sticky Practice Key
        # for the Global Active catalog (or Custom GA) pick. Without this, Shape Dm
        # only lives in the widget and snaps back to Bm after visiting Custom.
        try:
            from songs.practice_key_state import (
                resolve_practice_source_pick,
                resolve_settings_pick_for_write,
                set_practice_concert_key,
            )

            pick = str(
                resolve_settings_pick_for_write(session)
                or resolve_practice_source_pick(session)
                or ""
            ).strip()
            if pick:
                # Songs sidebar path: user may restore catalog Original (Dm→Bm).
                set_practice_concert_key(
                    session,
                    new,
                    pick_key=pick,
                    allow_restore_original=True,
                )
                session["concert_key"] = new
                if not str(pick).startswith("custom::") and not str(pick).startswith("creative::"):
                    try:
                        from music_workflow_song_practice import (
                            ensure_song_practice_blob_for_active_song,
                        )

                        orig = ""
                        selected = session.get("selected_song")
                        if isinstance(selected, dict):
                            orig = str(selected.get("key") or "")
                        ensure_song_practice_blob_for_active_song(
                            session, practice_key=new, original_key=orig
                        )
                    except ImportError:
                        pass
        except Exception:
            pass
        return
    if entry in {"Style Jam Mode", "Jam Session Generator"}:
        # Generated Concert Key is the jam widget, not the global sidebar.
        try:
            from music_workflow_song_practice import ensure_song_practice_blob_for_active_song

            orig = ""
            selected = session.get("selected_song")
            if isinstance(selected, dict):
                orig = str(selected.get("key") or "")
            ensure_song_practice_blob_for_active_song(
                session, practice_key=new, original_key=orig
            )
        except ImportError:
            pass
        return


def on_sidebar_practice_concert_key_change() -> None:
    """Sidebar widget callback — global key change + Creative retransposition."""
    import streamlit as st

    from songs.key_state import mark_display_key_changed

    old_pk = str(st.session_state.get("concert_key") or "").strip()
    live_pk = str(st.session_state.get("display_key") or st.session_state.get("concert_key") or "").strip()
    write_owner = resolve_practice_key_write_owner(st.session_state)
    handler = {
        "entry_jam": "sync_sidebar_jam_owner",
        "mission": "sync_sidebar_mission_owner",
        "song_improv": "capture_sidebar_song_practice_key_edit_intent",
        "custom": "custom_workspace_practice_key",
        "catalog": "mark_display_key_changed_catalog",
    }.get(write_owner, "catalog")
    st.session_state["_practice_key_write_router"] = {
        "widget_key": "display_key",
        "old": old_pk,
        "new": live_pk,
        "studio_page": str(st.session_state.get("studio_page") or ""),
        "backing_source": live_backing_source(st.session_state),
        "write_owner": write_owner,
        "handler": handler,
        "catalog_owns": _catalog_song_workflow_owns_practice_key(st.session_state),
        "entry_jam_auth": entry_jam_practice_key_authority_active(st.session_state),
        "tab": str(
            st.session_state.get("improv_intelligence_tab")
            or st.session_state.get("creative_improv_intelligence_tab")
            or ""
        ),
        "handoff": str(st.session_state.get("_backing_explicit_handoff_source") or ""),
    }

    try:
        from song_practice_key_change_trace import collect_song_practice_key_snapshot

        collect_song_practice_key_snapshot(st.session_state, phase="sidebar_callback_before")
    except ImportError:
        pass
    if write_owner == "mission":
        _emit_h6_mission_pk_trace(
            st.session_state,
            "A_widget_callback_enters",
            old_practice_key=old_pk,
            new_practice_key=live_pk,
        )
        apply_specialized_mission_practice_key(st.session_state, live_pk)
    mark_display_key_changed(st)
    try:
        page_now = str(st.session_state.get("studio_page") or "").strip().lower()
        tab_now = str(
            st.session_state.get("improv_intelligence_tab")
            or st.session_state.get("creative_improv_intelligence_tab")
            or ""
        ).strip()
        live_pk = str(st.session_state.get("display_key") or st.session_state.get("concert_key") or "").strip()
        if live_pk:
            try:
                from backing_context import get_backing_context

                ctx_now = get_backing_context(st.session_state)
                src_now = str(getattr(ctx_now, "source", "") or "").strip() if ctx_now else ""
            except Exception:
                src_now = ""
            if (tab_now == "Missions" and page_now == "creative") or src_now == "mission":
                if write_owner != "mission":
                    apply_specialized_mission_practice_key(st.session_state, live_pk)
                st.session_state["improv_mission_concert_key"] = live_pk
                try:
                    from improvisation_mission_persistence import mark_mission_workspace_dirty

                    mark_mission_workspace_dirty(st.session_state)
                except ImportError:
                    pass
    except Exception:
        pass
    try:
        from jam_generator_live_runtime_trace import append_jam_sidebar_key_trace

        append_jam_sidebar_key_trace(
            st.session_state,
            "sidebar_practice_concert_key_callback_fired",
            display_key=str(st.session_state.get("display_key") or ""),
            concert_key=str(st.session_state.get("concert_key") or ""),
        )
    except ImportError:
        pass
    if write_owner not in {"entry_jam", "mission"} and not generated_backing_owns_left_panel_key(st.session_state):
        try:
            from song_practice_key_sidebar_change import capture_sidebar_song_practice_key_edit_intent

            capture_sidebar_song_practice_key_edit_intent(st.session_state)
        except ImportError:
            pass
    if write_owner == "mission":
        _emit_h6_mission_pk_trace(st.session_state, "E_persistence_preparation")
    else:
        sync_sidebar_creative_concert_key(st.session_state, st_like=st)
    try:
        from songs.practice_key_state import get_practice_concert_key, resolve_practice_source_pick

        pick = str(resolve_practice_source_pick(st.session_state) or "").strip()
        catalog_after = get_practice_concert_key(st.session_state, pick) if pick else ""
    except Exception:
        pick = ""
        catalog_after = ""
    router = st.session_state.get("_practice_key_write_router")
    if isinstance(router, dict):
        router = dict(router)
        jam_ctx = st.session_state.get("_generated_jam_key_context")
        jam_token = ""
        if isinstance(jam_ctx, dict):
            jam_token = str(jam_ctx.get("practice_key_token") or jam_ctx.get("practice_tonic") or "")
        raw_ctx = st.session_state.get("backing_context")
        ctx_key = ""
        if isinstance(raw_ctx, dict):
            ctx_key = str(raw_ctx.get("concert_key") or raw_ctx.get("key") or "")
        router["after"] = {
            "improv_jam_key": str(st.session_state.get("improv_jam_key") or ""),
            "display_key": str(st.session_state.get("display_key") or ""),
            "concert_key": str(st.session_state.get("concert_key") or ""),
            "jam_ctx": jam_token,
            "backing_context_key": ctx_key,
            "catalog_pick": pick,
            "catalog_practice_key": catalog_after,
        }
        st.session_state["_practice_key_write_router"] = router
    try:
        from jam_generator_live_runtime_trace import append_jam_sidebar_key_trace

        append_jam_sidebar_key_trace(
            st.session_state,
            "sidebar_callback_after_sync",
            display_key=str(st.session_state.get("display_key") or ""),
            concert_key=str(st.session_state.get("concert_key") or ""),
        )
    except ImportError:
        pass
    try:
        from song_practice_key_change_trace import collect_song_practice_key_snapshot

        collect_song_practice_key_snapshot(st.session_state, phase="sidebar_callback_after")
    except ImportError:
        pass


def on_improv_style_key_change() -> None:
    import streamlit as st

    before_pick = guard_creative_catalog_pick_before_edit(
        st.session_state, writer="on_improv_style_key_change"
    )
    try:
        from generated_jam_key_change import capture_generated_key_edit_intent

        capture_generated_key_edit_intent(
            st.session_state,
            widget_key="improv_style_key",
        )
    except ImportError:
        pass
    verify_creative_catalog_pick_after_edit(
        st.session_state, before_pick=before_pick, writer="on_improv_style_key_change"
    )


def on_improv_style_jam_setting_change() -> None:
    """BPM / groove / style / mood / difficulty change — refresh meta and invalidate backing handoff."""
    import streamlit as st

    before_pick = guard_creative_catalog_pick_before_edit(
        st.session_state, writer="on_improv_style_jam_setting_change"
    )
    try:
        from music_workflow_generated_session import commit_style_jam_control_settings

        commit_style_jam_control_settings(st.session_state)
    except ImportError:
        pass
    sync_creative_style_jam_meta(st.session_state)
    invalidate_creative_backing_context(st.session_state)
    verify_creative_catalog_pick_after_edit(
        st.session_state, before_pick=before_pick, writer="on_improv_style_jam_setting_change"
    )


def on_improv_jam_setting_change() -> None:
    """Jam Session BPM / mood change — refresh meta and invalidate backing handoff."""
    import streamlit as st

    before_pick = guard_creative_catalog_pick_before_edit(
        st.session_state, writer="on_improv_jam_setting_change"
    )
    try:
        from music_workflow_generated_session import commit_style_jam_control_settings

        commit_style_jam_control_settings(st.session_state)
    except ImportError:
        pass
    sync_creative_style_jam_meta(st.session_state)
    invalidate_creative_backing_context(st.session_state)
    verify_creative_catalog_pick_after_edit(
        st.session_state, before_pick=before_pick, writer="on_improv_jam_setting_change"
    )


def ensure_creative_analysis_mode_restored(session_state: dict[str, Any]) -> str:
    """Restore Creative analysis mode before the selectbox renders."""
    try:
        from creative_tab_tool_persistence import (
            canonical_creative_selector_value,
            project_startup_default_selector,
            selector_hydration_complete,
        )

        canon = canonical_creative_selector_value(session_state, "creative_lab_analysis_mode")
        if canon:
            if str(session_state.get("creative_lab_analysis_mode") or "").strip() != canon:
                session_state["creative_lab_analysis_mode"] = canon
            session_state["creative_lab_last_mode"] = canon
            return canon
        # Hydration-incomplete must not block the empty-startup default; it only
        # blocks promoting widget defaults into canonical persistence.
    except ImportError:
        pass
    last = str(session_state.get("creative_lab_last_mode") or "").strip()
    current = str(session_state.get("creative_lab_analysis_mode") or "").strip()
    if last and last != current:
        session_state["creative_lab_analysis_mode"] = last
        return last
    if current:
        session_state["creative_lab_last_mode"] = current
        return current
    if last:
        session_state["creative_lab_analysis_mode"] = last
        return last
    try:
        from creative_tab_tool_persistence import project_startup_default_selector, selector_hydration_complete

        if selector_hydration_complete(session_state):
            projected = project_startup_default_selector(
                session_state, "creative_lab_analysis_mode", "Deep Harmonic Analyzer"
            )
            if projected:
                return projected
    except ImportError:
        pass
    default = "Deep Harmonic Analyzer"
    session_state["creative_lab_analysis_mode"] = default
    session_state["creative_lab_last_mode"] = default
    return default


def persist_creative_analysis_mode(session_state: dict[str, Any]) -> str:
    """Persist Analysis Mode to a non-widget key before leaving Creative.

    Reads the widget-owned ``creative_lab_analysis_mode`` but never writes it back
    after the selectbox may have rendered in the same run.
    """
    mode = str(session_state.get("creative_lab_analysis_mode") or "").strip()
    if not mode:
        mode = str(session_state.get("creative_lab_last_mode") or "").strip()
    if mode:
        session_state["creative_lab_last_mode"] = mode
        session_state["_creative_mode_user_touched"] = True
    return mode


def on_creative_analysis_mode_change() -> None:
    import streamlit as st

    try:
        from creative_tab_tool_persistence import handle_user_creative_selector_change

        handle_user_creative_selector_change(st.session_state, "creative_lab_analysis_mode")
        return
    except ImportError:
        pass
    mode = str(st.session_state.get("creative_lab_analysis_mode") or "").strip()
    if mode:
        st.session_state["creative_lab_last_mode"] = mode
    st.session_state["_creative_mode_user_touched"] = True


def _chart_display_label(session: dict[str, Any]) -> str:
    instrument = str(session.get("instrument") or "")
    if instrument == "Guitar" and session.get("guitar_capo_enabled"):
        return "Guitar shape chart"
    try:
        from instrument_transposition import chart_in_instrument_key, is_transposing_instrument

        if is_transposing_instrument(instrument) and chart_in_instrument_key(session):
            return "Written chart"
    except ImportError:
        pass
    return "Chart"


def creative_progression_display(
    session: dict[str, Any],
    sections: dict[str, list[str]],
    *,
    concert_key: str = "",
) -> dict[str, str]:
    """Build concert + written/shape progression lines for Creative display."""
    from improvisation_intelligence import flatten_sections

    concert = str(
        concert_key or creative_entry_concert_key(session) or session.get("concert_key") or "C"
    ).strip()
    concert_line = " · ".join(flatten_sections(sections)[:32])
    try:
        from backing_context import _resolve_chart_display_key, sections_dict_for_chart_display

        chart_key = _resolve_chart_display_key(session, concert)
        chart_sections = sections_dict_for_chart_display(session, sections, concert_key=concert)
    except ImportError:
        chart_key = concert
        chart_sections = sections
    chart_line = " · ".join(flatten_sections(chart_sections)[:32])
    show_chart = bool(chart_line and (chart_key != concert or chart_line != concert_line))
    return {
        "concert_key": concert,
        "chart_key": chart_key if show_chart else "",
        "concert_line": concert_line,
        "chart_line": chart_line if show_chart else "",
        "chart_label": _chart_display_label(session) if show_chart else "",
    }


def render_creative_progression_block(
    st: Any,
    session: dict[str, Any],
    sections: dict[str, list[str]],
    *,
    concert_key: str = "",
) -> None:
    """Render concert progression and optional written/shape chart line."""
    display = creative_progression_display(session, sections, concert_key=concert_key)
    st.markdown(
        f'<p class="ui-creative-progression-preview">Practice concert key: '
        f"<strong>{html.escape(display['concert_key'])}</strong></p>",
        unsafe_allow_html=True,
    )
    if display["concert_line"]:
        st.markdown(
            f'<p class="ui-creative-progression-preview"><strong>Concert Practice Key Progression:</strong> '
            f"{html.escape(display['concert_line'])}</p>",
            unsafe_allow_html=True,
        )
    if display["chart_line"]:
        label = display["chart_label"] or "Written Key"
        key_note = f" ({html.escape(display['chart_key'])})" if display.get("chart_key") else ""
        st.markdown(
            f'<p class="ui-creative-progression-preview"><strong>Written Key Progression{key_note}:</strong> '
            f"{html.escape(display['chart_line'])}</p>",
            unsafe_allow_html=True,
        )
