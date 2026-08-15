"""Workflow-specific musical ownership — key, progression, style isolated per Creative workflow."""

from __future__ import annotations

import copy
import hashlib
from typing import Any, Literal

WorkflowType = Literal[
    "song_based_improvisation",
    "style_jam",
    "jam_session_generator",
    "entry_jam",
    "mission_jam",
    "regular_catalog_backing",
    "regular_custom_backing",
]

WORKFLOW_MUSICAL_STATES_KEY = "_workflow_musical_states"
ACTIVE_WORKFLOW_OWNER_KEY = "_active_workflow_owner"
WORKFLOW_CONSISTENCY_DIAG_KEY = "_workflow_consistency_diag"

_ENTRY_TO_WORKFLOW = {
    "Song-Based Improvisation": "song_based_improvisation",
    "Style Jam Mode": "style_jam",
    "Jam Session Generator": "jam_session_generator",
}


def workflow_type_from_entry(entry: str) -> WorkflowType | None:
    text = str(entry or "").strip()
    wf = _ENTRY_TO_WORKFLOW.get(text)
    return wf  # type: ignore[return-value]


def workflow_type_from_backing_source(source: str, *, entry_mode: str = "") -> WorkflowType:
    src = str(source or "").strip()
    entry = str(entry_mode or "").strip()
    if src == "song_improv":
        return "song_based_improvisation"
    if src == "mission":
        return "mission_jam"
    if src == "custom_progression":
        return "regular_custom_backing"
    if src == "entry_jam":
        if entry == "Jam Session Generator":
            return "jam_session_generator"
        if entry == "Style Jam Mode":
            return "style_jam"
        return "entry_jam"
    return "regular_catalog_backing"


def _state_id_for_workflow(session: dict[str, Any], wf: WorkflowType) -> str:
    if wf == "song_based_improvisation":
        return str(session.get("active_catalog_pick_key") or session.get("song") or "song").strip() or "song"
    if wf == "jam_session_generator":
        jam = session.get("improv_jam_session")
        if isinstance(jam, dict) and jam.get("id"):
            return str(jam.get("id"))
        return str(session.get("improv_jam_style") or "jam_gen").strip() or "jam_gen"
    if wf == "style_jam":
        return str(session.get("improv_style") or "style_jam").strip() or "style_jam"
    return wf


def _tonic_mode_from_key_token(key: str) -> tuple[str, str]:
    from music_theory import key_is_minor, normalize_root, split_chord

    text = str(key or "C").strip() or "C"
    root, suffix = split_chord(text)
    tonic = normalize_root(root) or "C"
    mode = "minor" if key_is_minor(text) else "major"
    return tonic, mode


def capture_workflow_musical_state(session: dict[str, Any], wf: WorkflowType) -> dict[str, Any]:
    """Snapshot current session fields owned by a workflow."""
    entry = str(session.get("improv_entry_mode") or "").strip()
    blob: dict[str, Any] = {
        "workflow_type": wf,
        "session_id": _state_id_for_workflow(session, wf),
        "entry_mode": entry,
    }
    if wf == "song_based_improvisation":
        blob["display_key"] = str(session.get("display_key") or "").strip()
        blob["concert_key"] = str(session.get("concert_key") or "").strip()
        blob["sections"] = copy.deepcopy(session.get("improv_song_concert_sections") or {})
    elif wf == "style_jam":
        blob["tonic_key"] = str(session.get("improv_style_key") or "C").strip() or "C"
        blob["tonic"], blob["mode"] = _tonic_mode_from_key_token(blob["tonic_key"])
        blob["style"] = str(session.get("improv_style") or "").strip()
        blob["mood"] = str(session.get("improv_mood") or "").strip()
        blob["groove"] = str(session.get("improv_groove") or "").strip()
        blob["bpm"] = int(session.get("improv_style_bpm") or 110)
        blob["sections"] = copy.deepcopy(session.get("improv_generated_sections") or {})
    elif wf == "jam_session_generator":
        blob["tonic_key"] = str(session.get("improv_jam_key") or "C").strip() or "C"
        blob["tonic"], blob["mode"] = _tonic_mode_from_key_token(blob["tonic_key"])
        blob["style"] = str(session.get("improv_jam_style") or "").strip()
        blob["mood"] = str(session.get("improv_jam_mood") or "").strip()
        blob["groove"] = str(session.get("improv_groove") or "").strip()
        blob["bpm"] = int(session.get("improv_jam_bpm") or 110)
        jam = session.get("improv_jam_session")
        if isinstance(jam, dict):
            blob["jam_session"] = copy.deepcopy(jam)
            blob["sections"] = copy.deepcopy(jam.get("sections") or {})
    elif wf == "mission_jam":
        blob["display_key"] = str(session.get("display_key") or "").strip()
        blob["concert_key"] = str(session.get("concert_key") or "").strip()
        blob["sections"] = copy.deepcopy(session.get("improv_song_concert_sections") or {})
        blob["ii_selected_chord"] = str(session.get("ii_selected_chord") or "").strip()
        blob["ii_selected_section"] = str(session.get("ii_selected_section") or "").strip()
        blob["ii_selected_chord_index"] = int(session.get("ii_selected_chord_index") or 0)
        blob["improv_active_mission"] = str(session.get("improv_active_mission") or "").strip()
        blob["improv_mission_pick"] = str(session.get("improv_mission_pick") or "").strip()
        blob["improv_intelligence_tab"] = "Missions"
    blob["fingerprint"] = hashlib.sha256(repr(sorted(blob.items())).encode()).hexdigest()[:12]
    return blob


def save_workflow_snapshot(session: dict[str, Any], wf: WorkflowType) -> None:
    store = session.get(WORKFLOW_MUSICAL_STATES_KEY)
    if not isinstance(store, dict):
        store = {}
    store[wf] = capture_workflow_musical_state(session, wf)
    session[WORKFLOW_MUSICAL_STATES_KEY] = store


def _dev_workflow_restore_diag(session: dict[str, Any]) -> dict[str, Any]:
    d = session.get("_music_workflow_guarded_restore_diag")
    if not isinstance(d, dict):
        d = {}
        session["_music_workflow_guarded_restore_diag"] = d
    return d


def _guarded_snapshot_assign(
    session: dict[str, Any],
    key: str,
    value: Any,
    *,
    wf: WorkflowType,
    allowlist: frozenset[str],
) -> None:
    """Restore one legacy snapshot field — never mutate locked widget keys directly."""
    if key not in allowlist:
        _dev_workflow_restore_diag(session).setdefault("refused_keys", []).append(
            {"key": key, "workflow": wf, "reason": "not_in_allowlist"}
        )
        return
    try:
        from session_widget_safe import WIDGET_BOUND_KEYS, safe_session_assign, widgets_likely_instantiated
    except ImportError:
        session[key] = value
        return
    try:
        from creative_mission_config_persistence import MISSION_WIDGET_SESSION_KEYS
    except ImportError:
        MISSION_WIDGET_SESSION_KEYS = frozenset()  # type: ignore[misc,assignment]
    widget_bound = key in WIDGET_BOUND_KEYS or key in MISSION_WIDGET_SESSION_KEYS
    locked = widgets_likely_instantiated(session)
    if widget_bound and locked:
        safe_session_assign(session, key, value)
        blocked = session.setdefault("_music_workflow_pending_blocked_restore_keys", [])
        if isinstance(blocked, list):
            entry = {"key": key, "workflow": wf, "writer": "restore_workflow_snapshot"}
            if entry not in blocked:
                blocked.append(entry)
        try:
            import streamlit as st

            if st.query_params.get("dev"):
                _dev_workflow_restore_diag(session).setdefault("blocked_widget_keys", []).append(entry)
        except Exception:
            pass
        return
    if widget_bound:
        safe_session_assign(session, key, value)
    else:
        session[key] = value


WORKFLOW_SNAPSHOT_RESTORE_ALLOWLIST: dict[str, frozenset[str]] = {
    "song_based_improvisation": frozenset(
        {
            "display_key",
            "concert_key",
            "_pending_display_key",
            "improv_song_concert_sections",
            ACTIVE_WORKFLOW_OWNER_KEY,
        }
    ),
    "style_jam": frozenset(
        {
            "improv_entry_mode",
            "improv_style_key",
            "improv_style",
            "improv_mood",
            "improv_groove",
            "improv_style_bpm",
            "improv_generated_sections",
            "display_key",
            "concert_key",
            "_pending_display_key",
            ACTIVE_WORKFLOW_OWNER_KEY,
        }
    ),
    "jam_session_generator": frozenset(
        {
            "improv_entry_mode",
            "improv_jam_key",
            "improv_jam_style",
            "improv_jam_mood",
            "improv_jam_bpm",
            "improv_jam_session",
            "display_key",
            "concert_key",
            ACTIVE_WORKFLOW_OWNER_KEY,
        }
    ),
    "mission_jam": frozenset(
        {
            "display_key",
            "concert_key",
            "_pending_display_key",
            "improv_song_concert_sections",
            "ii_selected_chord",
            "ii_selected_section",
            "ii_selected_chord_index",
            "improv_active_mission",
            "improv_mission_pick",
            "improv_intelligence_tab",
            "creative_improv_intelligence_tab",
            ACTIVE_WORKFLOW_OWNER_KEY,
        }
    ),
}


def restore_workflow_snapshot(session: dict[str, Any], wf: WorkflowType) -> bool:
    store = session.get(WORKFLOW_MUSICAL_STATES_KEY)
    if not isinstance(store, dict):
        return False
    blob = store.get(wf)
    if not isinstance(blob, dict):
        return False
    allow = WORKFLOW_SNAPSHOT_RESTORE_ALLOWLIST.get(wf, frozenset())
    _guarded_snapshot_assign(session, ACTIVE_WORKFLOW_OWNER_KEY, wf, wf=wf, allowlist=allow)
    if wf == "song_based_improvisation":
        snap_sid = str(blob.get("session_id") or "").strip()
        live_sid = _state_id_for_workflow(session, wf)
        if snap_sid and live_sid and snap_sid != live_sid:
            try:
                from music_workflow_catalog_handoff import record_catalog_handoff_trace

                record_catalog_handoff_trace(
                    session,
                    "skip_stale_workflow_snapshot",
                    workflow=wf,
                    snapshot_session_id=snap_sid,
                    live_session_id=live_sid,
                )
            except ImportError:
                pass
            return False
        for k in ("display_key", "concert_key"):
            v = str(blob.get(k) or "").strip()
            if v:
                _guarded_snapshot_assign(session, k, v, wf=wf, allowlist=allow)
                _guarded_snapshot_assign(session, "_pending_display_key", v, wf=wf, allowlist=allow)
        sec = blob.get("sections")
        if isinstance(sec, dict) and sec:
            session["improv_song_concert_sections"] = copy.deepcopy(sec)
        return True
    if wf == "style_jam":
        _guarded_snapshot_assign(session, "improv_entry_mode", "Style Jam Mode", wf=wf, allowlist=allow)
        key = str(blob.get("tonic_key") or "C").strip() or "C"
        _guarded_snapshot_assign(session, "improv_style_key", key, wf=wf, allowlist=allow)
        _guarded_snapshot_assign(session, "improv_style", str(blob.get("style") or "").strip(), wf=wf, allowlist=allow)
        _guarded_snapshot_assign(session, "improv_mood", str(blob.get("mood") or "").strip(), wf=wf, allowlist=allow)
        _guarded_snapshot_assign(session, "improv_groove", str(blob.get("groove") or "").strip(), wf=wf, allowlist=allow)
        _guarded_snapshot_assign(session, "improv_style_bpm", int(blob.get("bpm") or 110), wf=wf, allowlist=allow)
        sec = blob.get("sections")
        if isinstance(sec, dict):
            session["improv_generated_sections"] = copy.deepcopy(sec)
        try:
            from creative_key_sync import apply_creative_concert_key, IMPROV_STYLE_KEY_TRACKER

            apply_creative_concert_key(session, key, source="workflow_restore_style_jam")
            session[IMPROV_STYLE_KEY_TRACKER] = key
        except ImportError:
            pass
        _guarded_snapshot_assign(session, "display_key", key, wf=wf, allowlist=allow)
        _guarded_snapshot_assign(session, "concert_key", key, wf=wf, allowlist=allow)
        _guarded_snapshot_assign(session, "_pending_display_key", key, wf=wf, allowlist=allow)
        return True
    if wf == "jam_session_generator":
        _guarded_snapshot_assign(session, "improv_entry_mode", "Jam Session Generator", wf=wf, allowlist=allow)
        key = str(blob.get("tonic_key") or "C").strip() or "C"
        _guarded_snapshot_assign(session, "improv_jam_key", key, wf=wf, allowlist=allow)
        _guarded_snapshot_assign(session, "improv_jam_style", str(blob.get("style") or "").strip(), wf=wf, allowlist=allow)
        _guarded_snapshot_assign(session, "improv_jam_mood", str(blob.get("mood") or "").strip(), wf=wf, allowlist=allow)
        _guarded_snapshot_assign(session, "improv_jam_bpm", int(blob.get("bpm") or 110), wf=wf, allowlist=allow)
        jam = blob.get("jam_session")
        if isinstance(jam, dict):
            session["improv_jam_session"] = copy.deepcopy(jam)
        try:
            from creative_key_sync import apply_creative_concert_key, IMPROV_JAM_KEY_TRACKER
            from generated_jam_key_context import activate_generated_jam_key_ownership

            apply_creative_concert_key(session, key, source="workflow_restore_jam_gen")
            session[IMPROV_JAM_KEY_TRACKER] = key
            activate_generated_jam_key_ownership(session, entry_mode="Jam Session Generator")
        except ImportError:
            _guarded_snapshot_assign(session, "display_key", key, wf=wf, allowlist=allow)
            _guarded_snapshot_assign(session, "concert_key", key, wf=wf, allowlist=allow)
        return True
    if wf == "mission_jam":
        _guarded_snapshot_assign(session, "improv_intelligence_tab", "Missions", wf=wf, allowlist=allow)
        _guarded_snapshot_assign(session, "creative_improv_intelligence_tab", "Missions", wf=wf, allowlist=allow)
        for k in ("display_key", "concert_key"):
            v = str(blob.get(k) or "").strip()
            if v:
                _guarded_snapshot_assign(session, k, v, wf=wf, allowlist=allow)
                _guarded_snapshot_assign(session, "_pending_display_key", v, wf=wf, allowlist=allow)
        sec = blob.get("sections")
        if isinstance(sec, dict) and sec:
            session["improv_song_concert_sections"] = copy.deepcopy(sec)
        for k in (
            "ii_selected_chord",
            "ii_selected_section",
            "improv_active_mission",
            "improv_mission_pick",
        ):
            v = blob.get(k)
            if v is not None and str(v).strip() != "":
                _guarded_snapshot_assign(session, k, v, wf=wf, allowlist=allow)
        if blob.get("ii_selected_chord_index") is not None:
            _guarded_snapshot_assign(
                session,
                "ii_selected_chord_index",
                int(blob.get("ii_selected_chord_index") or 0),
                wf=wf,
                allowlist=allow,
            )
        try:
            from generated_jam_key_context import deactivate_generated_jam_key_ownership

            deactivate_generated_jam_key_ownership(session, pre_widget=True)
        except ImportError:
            pass
        return True
    return False


def switch_workflow_owner(session: dict[str, Any], new_wf: WorkflowType) -> None:
    """Persist outgoing workflow, restore incoming — delegates to activate_workflow."""
    view = "Missions" if new_wf == "mission_jam" else ""
    try:
        from music_workflow_pending_activation import request_or_activate_workflow

        status = request_or_activate_workflow(
            session,
            target_owner=str(new_wf),
            activation_source="switch_workflow_owner",
            active_creative_view=view,
            navigation_intent="creative_missions" if new_wf == "mission_jam" else "",
        )
        if status in {"done", "queued"}:
            return
    except ImportError:
        pass
    try:
        from music_workflow_activation import activate_workflow_simple

        activate_workflow_simple(
            session,
            str(new_wf),
            activation_source="switch_workflow_owner",
            active_creative_view=view,
            navigation_intent="creative_missions" if new_wf == "mission_jam" else "",
        )
        return
    except ImportError:
        pass
    prev = str(session.get(ACTIVE_WORKFLOW_OWNER_KEY) or "").strip()
    if prev:
        save_workflow_snapshot(session, prev)  # type: ignore[arg-type]
    else:
        entry = str(session.get("improv_entry_mode") or "").strip()
        inferred = workflow_type_from_entry(entry)
        if inferred:
            save_workflow_snapshot(session, inferred)
    ok = restore_workflow_snapshot(session, new_wf)
    if new_wf == "mission_jam" and ok:
        try:
            from generated_jam_key_context import deactivate_generated_jam_key_ownership

            deactivate_generated_jam_key_ownership(session, pre_widget=True)
        except ImportError:
            pass
    if ok:
        session[ACTIVE_WORKFLOW_OWNER_KEY] = new_wf


def section_maps_equivalent(left: Any, right: Any) -> bool:
    """True when two section maps have the same labels and chord symbols in order."""
    if not isinstance(left, dict) or not isinstance(right, dict) or not left or not right:
        return False
    if set(left) != set(right):
        return False
    for name in left:
        a = [str(c).strip() for c in (left.get(name) or []) if str(c).strip()] if isinstance(left.get(name), list) else []
        b = [str(c).strip() for c in (right.get(name) or []) if str(c).strip()] if isinstance(right.get(name), list) else []
        if a != b:
            return False
    return True


def reclaim_stale_prior_song_practice_key_on_original_chart(session: dict[str, Any]) -> str:
    """If the live chart is still catalog-original pitch, leftover prior-song Practice Key must not own it.

    Example: Say in G → pick Hevenu (Dm chart copied, original_mode D minor) while practice_tonic
    stays G. Transposing that Dm chart as if it were in G yields G#m instead of C#m.
    """
    try:
        from music_theory import key_center_token, split_key_center
        from music_workflow_song_practice import resolve_song_practice_key_token, song_practice_blob
        from music_workflow_state_store import KeyAuthority, save_workflow_blob
    except ImportError:
        return ""
    song = song_practice_blob(session)
    if song is None or not isinstance(song.section_map, dict) or not song.section_map:
        return ""
    orig_token = key_center_token(song.keys.original_tonic, song.keys.original_mode)
    practice_token = resolve_song_practice_key_token(session)
    if not orig_token or not practice_token or practice_token == orig_token:
        return practice_token
    home = session.get("home_sections")
    if not isinstance(home, dict) or not home:
        return practice_token
    if not section_maps_equivalent(song.section_map, home):
        return practice_token
    ot, om = split_key_center(orig_token)
    song.keys = KeyAuthority(
        original_tonic=song.keys.original_tonic,
        original_mode=song.keys.original_mode,
        practice_tonic=ot,
        practice_mode=om,
        written_tonic=song.keys.written_tonic,
        written_mode=song.keys.written_mode,
        instrument=song.keys.instrument,
        transposition=getattr(song.keys, "transposition", "") or "",
        key_owner=song.keys.key_owner or "song_based_improvisation",
    )
    save_workflow_blob(session, song, source="reclaim_original_chart_practice_key")
    session["display_key"] = orig_token
    session["concert_key"] = orig_token
    session["_pending_display_key"] = orig_token
    session["improv_song_concert_sections"] = copy.deepcopy(song.section_map)
    return orig_token


def _section_maps_same_song(expected: dict[str, list[str]], actual: dict[str, list[str]]) -> bool:
    if not expected or not actual:
        return False
    overlap = [name for name in expected if name in actual]
    if not overlap:
        return False
    for name in overlap:
        want = expected[name][0] if expected[name] else ""
        got = actual[name][0] if actual[name] else ""
        if want and got and want != got:
            return False
    return True


def sync_song_improv_sections_to_practice_key(session: dict[str, Any]) -> dict[str, list[str]]:
    """Full catalog song sections transposed to current practice concert key."""
    try:
        from music_workflow_song_practice import resolve_song_practice_key_token, song_practice_blob
        from music_workflow_catalog_handoff import workflow_blob_matches_live_catalog_parent
        from songs.music_source import catalog_chart_sections_for_pick

        reclaim_stale_prior_song_practice_key_on_original_chart(session)
        practice = resolve_song_practice_key_token(session) or str(
            session.get("display_key") or session.get("concert_key") or ""
        ).strip()
        song = song_practice_blob(session)
        catalog_sections = catalog_chart_sections_for_pick(
            session, str(session.get("active_catalog_pick_key") or "")
        )
        if (
            song is not None
            and isinstance(song.section_map, dict)
            and song.section_map
            and workflow_blob_matches_live_catalog_parent(session, song)
        ):
            expected = catalog_sections
            original = ""
            sel = session.get("selected_song")
            if isinstance(sel, dict):
                original = str(sel.get("key") or "").strip()
            if catalog_sections and original and practice and original != practice:
                try:
                    from music_theory import transpose_sections_dict

                    expected = transpose_sections_dict(catalog_sections, original, practice)
                except ImportError:
                    expected = catalog_sections
            if not catalog_sections or _section_maps_same_song(expected, song.section_map):
                session["improv_song_concert_sections"] = copy.deepcopy(song.section_map)
                return copy.deepcopy(song.section_map)
    except ImportError:
        practice = str(session.get("display_key") or session.get("concert_key") or "").strip()
    if not practice:
        return {}
    try:
        from backing_context import _current_pick_key
        from songs.music_source import catalog_chart_sections_for_pick, resolve_catalog_song_for_pick
        from music_theory import transpose_sections_dict

        pick = _current_pick_key(session)
        selected, original_key = resolve_catalog_song_for_pick(session, pick)
        if not isinstance(selected, dict) or not selected:
            return {}
        original = str(selected.get("key") or selected.get("original_key") or original_key or "").strip()
        sections = catalog_chart_sections_for_pick(session, pick, selected=selected)
        if not sections:
            return {}
        base = {
            str(name): [str(c) for c in chords if str(c).strip()]
            for name, chords in sections.items()
            if isinstance(chords, list)
        }
        if not original or original == practice:
            out = base
        else:
            out = transpose_sections_dict(base, original, practice)
        session["improv_song_concert_sections"] = copy.deepcopy(out)
        return out
    except ImportError:
        return {}


def validate_workflow_consistency(session: dict[str, Any], ctx: Any | None = None) -> dict[str, Any]:
    """Detect label/progression/style owner mismatches for ?dev=1."""
    violations: list[str] = []
    wf = str(session.get(ACTIVE_WORKFLOW_OWNER_KEY) or "").strip()
    launch = str(session.get("_backing_launch_workflow") or "").strip()
    rendered = ""
    if ctx is not None:
        try:
            from workflow_musical_authority import workflow_type_from_backing_source

            rendered = workflow_type_from_backing_source(
                str(getattr(ctx, "source", "") or ""),
                entry_mode=str(getattr(ctx, "entry_mode", "") or ""),
            )
        except Exception:
            rendered = str(getattr(ctx, "source", "") or "")
    if launch and rendered and launch != rendered:
        if launch == "style_jam" and rendered == "jam_session_generator":
            violations.append("STYLE_JAM_OPENED_AS_GENERATOR")
        violations.append("BACKING_WORKFLOW_ROUTE_MISMATCH")
    practice = str(session.get("display_key") or session.get("concert_key") or "").strip()
    if ctx is not None and str(getattr(ctx, "source", "") or "") == "song_improv":
        prog = list(getattr(ctx, "progression", None) or [])
        if prog and practice:
            first = str(prog[0] or "")
            try:
                from music_theory import normalize_root, split_chord, key_is_minor

                pr = normalize_root(split_chord(practice)[0])
                cr = normalize_root(split_chord(first)[0])
                song_minor = key_is_minor(practice)
                chord_minor = "m" in first.lower() and "maj" not in first.lower()
                if song_minor != chord_minor and len(prog) >= 3:
                    violations.append("KEY_LABEL_PROGRESSION_MISMATCH")
            except ImportError:
                pass
    style = str(getattr(ctx, "style", "") or "") if ctx else ""
    if rendered in {"jam_session_generator", "style_jam"} and style:
        low = style.lower()
        if any(x in low for x in ("jewish", "hevenu", "ballad")) and "bossa" not in low:
            if str(session.get("improv_jam_style") or session.get("improv_style") or "").lower().find("jewish") < 0:
                violations.append("GENERATED_JAM_CATALOG_STYLE_LEAK")
    diag = {
        "launch_workflow": launch,
        "rendered_workflow": rendered,
        "active_owner": wf,
        "violations": violations,
        "consistent": not violations,
    }
    session[WORKFLOW_CONSISTENCY_DIAG_KEY] = diag
    return diag


__all__ = [
    "ACTIVE_WORKFLOW_OWNER_KEY",
    "WORKFLOW_CONSISTENCY_DIAG_KEY",
    "WORKFLOW_MUSICAL_STATES_KEY",
    "WorkflowType",
    "capture_workflow_musical_state",
    "reclaim_stale_prior_song_practice_key_on_original_chart",
    "restore_workflow_snapshot",
    "save_workflow_snapshot",
    "section_maps_equivalent",
    "switch_workflow_owner",
    "sync_song_improv_sections_to_practice_key",
    "validate_workflow_consistency",
    "workflow_type_from_backing_source",
    "workflow_type_from_entry",
]
