"""Upload Analysis metric inheritance — active AI Metrics + take-only additions."""

from __future__ import annotations

from typing import Any

ANALYSIS_INHERITED_AI_METRIC_IDS_KEY = "analysis_inherited_ai_metric_ids"
ANALYSIS_ADDITIONAL_TAKE_METRIC_IDS_KEY = "analysis_additional_take_metric_ids"
ANALYSIS_EFFECTIVE_METRIC_IDS_KEY = "analysis_effective_metric_ids"


def _dedupe_metric_ids(raw: Any) -> list[str]:
    try:
        from mission_analysis import MISSION_BY_ID
    except ImportError:
        MISSION_BY_ID = {}
    out: list[str] = []
    if not isinstance(raw, list):
        return out
    for x in raw:
        mid = str(x)
        if mid in MISSION_BY_ID and mid not in out:
            out.append(mid)
    return out


def active_improv_ai_metric_ids(session: dict[str, Any]) -> list[str]:
    """Global AI Metrics page selection (canonical when configured)."""
    ids = _dedupe_metric_ids(session.get("improv_ai_metric_ids"))
    if ids:
        return ids
    try:
        from creative_mission_config_persistence import (
            canonical_mission_config_value,
            mission_metrics_configured_in_canonical,
        )

        if mission_metrics_configured_in_canonical(session):
            return _dedupe_metric_ids(canonical_mission_config_value(session, "improv_ai_metric_ids"))
    except ImportError:
        pass
    return []


def compute_effective_upload_metric_ids(session: dict[str, Any]) -> list[str]:
    inherited = _dedupe_metric_ids(session.get(ANALYSIS_INHERITED_AI_METRIC_IDS_KEY))
    if not inherited:
        inherited = active_improv_ai_metric_ids(session)
    additional = _dedupe_metric_ids(session.get(ANALYSIS_ADDITIONAL_TAKE_METRIC_IDS_KEY))
    merged: list[str] = []
    for mid in inherited + additional:
        if mid not in merged:
            merged.append(mid)
    if session.get("analysis_sync_creative_mission", True):
        try:
            from mission_analysis import mission_ids_from_legacy

            legacy = str(session.get("improv_active_mission") or "")
            for mid in mission_ids_from_legacy(legacy):
                if mid not in merged:
                    merged.append(mid)
        except ImportError:
            pass
    return merged[:18]


def sync_effective_upload_metrics_to_session(session: dict[str, Any]) -> list[str]:
    effective = compute_effective_upload_metric_ids(session)
    session[ANALYSIS_EFFECTIVE_METRIC_IDS_KEY] = list(effective)
    session["analysis_ai_metric_ids"] = list(effective)
    session["analysis_mission_ids"] = list(effective)
    return effective


def seed_upload_metrics_from_mission_handoff(session: dict[str, Any]) -> list[str]:
    inherited = active_improv_ai_metric_ids(session)
    session[ANALYSIS_INHERITED_AI_METRIC_IDS_KEY] = list(inherited)
    session.setdefault(ANALYSIS_ADDITIONAL_TAKE_METRIC_IDS_KEY, [])
    if not isinstance(session.get(ANALYSIS_ADDITIONAL_TAKE_METRIC_IDS_KEY), list):
        session[ANALYSIS_ADDITIONAL_TAKE_METRIC_IDS_KEY] = []
    return sync_effective_upload_metrics_to_session(session)


def apply_additional_take_metrics(session: dict[str, Any], additional_ids: list[str]) -> list[str]:
    inherited = _dedupe_metric_ids(session.get(ANALYSIS_INHERITED_AI_METRIC_IDS_KEY))
    add = _dedupe_metric_ids(additional_ids)
    session[ANALYSIS_ADDITIONAL_TAKE_METRIC_IDS_KEY] = [
        mid for mid in add if mid not in inherited
    ]
    return sync_effective_upload_metrics_to_session(session)


__all__ = [
    "ANALYSIS_ADDITIONAL_TAKE_METRIC_IDS_KEY",
    "ANALYSIS_EFFECTIVE_METRIC_IDS_KEY",
    "ANALYSIS_INHERITED_AI_METRIC_IDS_KEY",
    "active_improv_ai_metric_ids",
    "apply_additional_take_metrics",
    "compute_effective_upload_metric_ids",
    "seed_upload_metrics_from_mission_handoff",
    "sync_effective_upload_metrics_to_session",
]
