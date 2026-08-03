"""Resolve Item 5 certification fetch source from run-scoped hydration evidence (read-only)."""

from __future__ import annotations

from typing import Any


def _run_seq(session: dict[str, Any]) -> int:
    try:
        return int(session.get("_script_run_seq") or 0)
    except (TypeError, ValueError):
        return 0


def _is_network_fetch_source(src: str) -> bool:
    s = str(src or "").strip().lower()
    if not s:
        return False
    if s == "network":
        return True
    if "session_cache" in s or s == "cache":
        return False
    return "network" in s


def _trace_current_run(trace: dict[str, Any], run_seq: int) -> bool:
    trace_run = trace.get("startup_run_seq")
    if trace_run is None:
        return True
    try:
        return int(trace_run) == run_seq
    except (TypeError, ValueError):
        return False


def resolve_item5_fetch_evidence(session: dict[str, Any]) -> dict[str, Any]:
    """Authoritative startup hydration beats later session-cache lookups (current run only)."""
    run_seq = _run_seq(session)
    later_lookup_fetch_sources: list[dict[str, Any]] = []

    for key in ("_music_last_cloud_fetch_source", "_suite_last_cloud_fetch_source"):
        val = str(session.get(key) or "").strip()
        if val:
            later_lookup_fetch_sources.append({"session_key": key, "fetch_source": val})

    initial_fetch_source: str | None = None
    initial_fetched_revision: int | None = None
    authoritative_hydration_source: str | None = None
    authoritative_hydration_run_id: str | None = None
    hydration_event_seq: int | None = None

    try:
        from mission_backing_handoff_persistence import MISSION_BACKING_REFRESH_HYDRATION_TRACE_KEY

        trace = session.get(MISSION_BACKING_REFRESH_HYDRATION_TRACE_KEY)
        if isinstance(trace, dict) and _trace_current_run(trace, run_seq):
            authoritative_hydration_source = (
                "mission_backing_handoff_persistence.MISSION_BACKING_REFRESH_HYDRATION_TRACE_KEY"
            )
            authoritative_hydration_run_id = str(trace.get("hydration_run_id") or f"trace-run-{run_seq}")
            fs = str(trace.get("fetch_source") or "").strip()
            if fs:
                initial_fetch_source = fs
            rev = trace.get("fetched_revision")
            if rev is not None:
                try:
                    initial_fetched_revision = int(rev)
                except (TypeError, ValueError):
                    pass
            steps = trace.get("steps")
            if isinstance(steps, list):
                hydration_event_seq = len(steps)
    except ImportError:
        pass

    try:
        from music_page_cloud_durability_trace import PAGE_CLOUD_DURABILITY_TRACE_KEY

        bucket = session.get(PAGE_CLOUD_DURABILITY_TRACE_KEY)
        if isinstance(bucket, dict):
            fh = bucket.get("fresh_hydration")
            if isinstance(fh, dict):
                fs = str(fh.get("fetch_source") or "").strip()
                used_cache = bool(fh.get("used_session_cache"))
                later_lookup_fetch_sources.append(
                    {
                        "session_key": "PAGE_CLOUD_DURABILITY_TRACE.fresh_hydration",
                        "fetch_source": fs,
                        "used_session_cache": used_cache,
                    }
                )
                if not used_cache and _is_network_fetch_source(fs):
                    if not initial_fetch_source or not _is_network_fetch_source(initial_fetch_source):
                        initial_fetch_source = "network" if fs == "network" else fs
                        authoritative_hydration_source = (
                            authoritative_hydration_source
                            or "music_page_cloud_durability_trace.fresh_hydration"
                        )
                        authoritative_hydration_run_id = authoritative_hydration_run_id or f"fresh-hydration-run-{run_seq}"
                    if initial_fetched_revision is None and fh.get("revision") is not None:
                        try:
                            initial_fetched_revision = int(fh["revision"])
                        except (TypeError, ValueError):
                            pass
            lcf = bucket.get("last_cloud_fetch")
            if isinstance(lcf, dict):
                later_lookup_fetch_sources.append(
                    {"session_key": "PAGE_CLOUD_DURABILITY_TRACE.last_cloud_fetch", **lcf}
                )
    except ImportError:
        pass

    selected: str | None = None
    selection_reason = "no_hydration_evidence"

    if initial_fetch_source and _is_network_fetch_source(initial_fetch_source):
        selected = "network"
        selection_reason = "authoritative_current_run_startup_network_hydration"
    elif initial_fetch_source:
        selected = initial_fetch_source
        selection_reason = "initial_startup_fetch_non_network"
    elif later_lookup_fetch_sources:
        selected = str(later_lookup_fetch_sources[0].get("fetch_source") or "").strip() or None
        selection_reason = "fallback_later_session_lookup_only"

    return {
        "authoritative_hydration_source": authoritative_hydration_source,
        "authoritative_hydration_run_id": authoritative_hydration_run_id,
        "startup_run_seq": run_seq,
        "hydration_event_seq": hydration_event_seq,
        "initial_startup_fetch_source": initial_fetch_source,
        "initial_startup_fetched_revision": initial_fetched_revision,
        "later_lookup_fetch_sources": later_lookup_fetch_sources,
        "selected_certification_fetch_source": selected,
        "selection_reason": selection_reason,
    }


def infer_item5_session_start_kind(session: dict[str, Any], *, certification_network: bool) -> str:
    """Deprecated wrapper — use classify_item5_session_start."""
    from phase1_item5_session_lifecycle import classify_item5_session_start

    return str(
        classify_item5_session_start(session, certification_network=certification_network).get(
            "session_start_kind"
        )
        or "unknown"
    )


__all__ = [
    "infer_item5_session_start_kind",
    "resolve_item5_fetch_evidence",
]
