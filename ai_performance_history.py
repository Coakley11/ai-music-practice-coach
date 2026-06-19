"""Unified AI performance analysis history (all recording coach runs)."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from music_workspace_paths import music_data_path

SOURCE_METRICS_UPLOAD = "Metrics & AI Upload Analysis"
SOURCE_UPLOAD = "Upload Analysis"
SOURCE_MULTITRACK = "Multitrack Analysis"
SOURCE_BACKING = "Backing Track Practice"
SOURCE_ENSEMBLE = "Ensemble / Multitrack"


def _performance_history_path() -> Path:
    return music_data_path("ai_performance_history")


def _legacy_analysis_path() -> Path:
    return music_data_path("analysis_history")


def _legacy_mission_path() -> Path:
    return music_data_path("mission_analysis_history")


def _criteria_labels_from_ids(ids: list[str]) -> list[str]:
    try:
        from mission_analysis import MISSION_BY_ID

        return [MISSION_BY_ID[mid].label for mid in ids if mid in MISSION_BY_ID]
    except Exception:
        return []


def _aggregate_coach_voice(result: dict[str, Any]) -> tuple[str, str]:
    missions = result.get("mission_results") or []
    if not missions:
        return "", ""
    strongest = max(missions, key=lambda m: int(m.get("score") or 0))
    weakest = min(missions, key=lambda m: int(m.get("score") or 0))
    went = str(strongest.get("went_well") or strongest.get("summary") or "")
    improve = str(weakest.get("improve_to") or weakest.get("summary") or "")
    return went, improve


def build_performance_record(
    result: dict[str, Any],
    *,
    ctx: dict[str, Any] | None = None,
    source: str = SOURCE_UPLOAD,
) -> dict[str, Any] | None:
    if not result.get("ok"):
        return None
    ctx = ctx or {}
    is_mt = bool(result.get("multitrack"))
    scores = dict(result.get("scores") or {})
    ranked = sorted(scores.items(), key=lambda x: x[1]) if scores else []
    weakest = ranked[0][0] if ranked else ""
    strongest = ranked[-1][0] if ranked else ""

    mission_ids = list(
        result.get("mission_ids")
        or ctx.get("mission_ids")
        or []
    )
    criteria_labels = _criteria_labels_from_ids(mission_ids)
    if not criteria_labels:
        criteria_labels = [
            str(m.get("label") or "")
            for m in (result.get("mission_results") or [])
            if m.get("label")
        ]

    went_well, improve_to = _aggregate_coach_voice(result)
    if not went_well and result.get("mission_strongest"):
        went_well = str(result.get("mission_strongest"))
    if not improve_to and result.get("mission_weakest"):
        improve_to = str(result.get("mission_weakest"))

    recommendations: list[str] = []
    if result.get("mission_next_recommendation"):
        recommendations.append(str(result["mission_next_recommendation"]))
    recommendations.extend(
        str(t) for t in (result.get("practice_plan") or result.get("tips") or [])[:5]
    )
    for m in result.get("mission_results") or []:
        for tip in (m.get("tips") or [])[:2]:
            if tip and tip not in recommendations:
                recommendations.append(str(tip))

    return {
        "recorded_at": datetime.now().isoformat(timespec="seconds"),
        "date": date.today().isoformat(),
        "source": source or SOURCE_UPLOAD,
        "analysis_type": "multitrack" if is_mt else "single",
        "multitrack": is_mt,
        "recording_type": result.get("recording_type") or ctx.get("recording_type", "practice"),
        "filename": result.get("filename", ""),
        "duration": result.get("duration"),
        "tempo": result.get("tempo"),
        "song": result.get("song") or ctx.get("song", ""),
        "instrument": result.get("instrument") or ctx.get("instrument", ""),
        "level": result.get("level") or ctx.get("level", ""),
        "focus": result.get("focus") or ctx.get("focus", ""),
        "display_key": str(ctx.get("display_key") or ""),
        "criteria_ids": mission_ids,
        "criteria_labels": criteria_labels,
        "scores": scores,
        "weakest_category": weakest,
        "strongest_category": strongest,
        "coach_summary": str(result.get("coach_summary") or result.get("mission_coach_summary") or ""),
        "biggest_issue": str(
            result.get("biggest_issue")
            or (result.get("findings") or [""])[0]
            if result.get("findings")
            else ""
        ),
        "next_focus": str(result.get("next_focus") or ""),
        "most_improved": str(result.get("most_improved") or ""),
        "went_well": went_well,
        "improve_to": improve_to,
        "recommendations": recommendations[:8],
        "next_practice": str(
            result.get("mission_next_recommendation")
            or result.get("next_focus")
            or ""
        ),
        "practice_plan": list(result.get("practice_plan") or [])[:6],
        "ensemble_notes": list(result.get("ensemble_notes") or result.get("findings") or [])[:4],
        "mission_ids": mission_ids,
        "mission_results": [
            {
                "id": m.get("id"),
                "label": m.get("label"),
                "score": m.get("score"),
                "summary": m.get("summary"),
                "went_well": m.get("went_well"),
                "improve_to": m.get("improve_to"),
                "tips": list(m.get("tips") or [])[:4],
            }
            for m in (result.get("mission_results") or [])
        ],
        "mission_strongest": str(result.get("mission_strongest") or ""),
        "mission_weakest": str(result.get("mission_weakest") or ""),
        "mission_coach_summary": str(result.get("mission_coach_summary") or ""),
        "mission_next_recommendation": str(result.get("mission_next_recommendation") or ""),
        "overall_improv_score": int(result.get("overall_improv_score") or 0),
        "musical_metrics": dict(result.get("musical_metrics") or {}),
    }


def _legacy_analysis_rows() -> list[dict[str, Any]]:
    legacy_path = _legacy_analysis_path()
    if not legacy_path.is_file():
        return []
    try:
        data = json.loads(legacy_path.read_text(encoding="utf-8"))
        rows = data if isinstance(data, list) else []
    except Exception:
        return []
    out: list[dict[str, Any]] = []
    for row in rows:
        rec = dict(row)
        rec.setdefault("source", SOURCE_UPLOAD)
        rec.setdefault("analysis_type", "multitrack" if row.get("multitrack") else "single")
        if not rec.get("criteria_labels") and rec.get("mission_results"):
            rec["criteria_labels"] = [
                str(m.get("label") or "") for m in rec["mission_results"] if m.get("label")
            ]
        out.append(rec)
    return out


def _legacy_mission_rows() -> list[dict[str, Any]]:
    legacy_path = _legacy_mission_path()
    if not legacy_path.is_file():
        return []
    try:
        data = json.loads(legacy_path.read_text(encoding="utf-8"))
        rows = data if isinstance(data, list) else []
    except Exception:
        return []
    out: list[dict[str, Any]] = []
    for row in rows:
        mids = [str(m.get("id") or "") for m in row.get("missions") or []]
        labels = [str(m.get("label") or "") for m in row.get("missions") or []]
        out.append(
            {
                "recorded_at": row.get("recorded_at") or f"{row.get('date', '')}T12:00:00",
                "date": row.get("date") or "",
                "source": SOURCE_METRICS_UPLOAD,
                "analysis_type": "single",
                "multitrack": False,
                "recording_type": "practice",
                "filename": row.get("filename", ""),
                "song": row.get("song", ""),
                "instrument": row.get("instrument", ""),
                "level": row.get("level", ""),
                "focus": row.get("focus", ""),
                "criteria_ids": mids,
                "criteria_labels": labels,
                "mission_ids": mids,
                "mission_results": [
                    {
                        "id": m.get("id"),
                        "label": m.get("label"),
                        "score": m.get("score"),
                    }
                    for m in row.get("missions") or []
                ],
                "musical_metrics": dict(row.get("musical_metrics") or {}),
                "scores": {},
            }
        )
    return out


def _dedupe_records(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in sorted(rows, key=lambda r: str(r.get("recorded_at") or "")):
        key = "|".join(
            [
                str(row.get("recorded_at") or ""),
                str(row.get("source") or ""),
                str(row.get("filename") or ""),
                str(row.get("song") or ""),
                str(row.get("overall_improv_score") or ""),
            ]
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def load_performance_history() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    history_path = _performance_history_path()
    if history_path.exists():
        try:
            data = json.loads(history_path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                rows = data
        except Exception:
            rows = []
    if rows:
        return rows[-120:]
    merged = _dedupe_records(_legacy_analysis_rows() + _legacy_mission_rows())
    if merged:
        save_performance_history(merged)
    return merged[-120:]


def save_performance_history(entries: list[dict[str, Any]]) -> None:
    path = _performance_history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(entries[-120:], indent=2),
        encoding="utf-8",
    )


def append_performance_record(
    result: dict[str, Any],
    *,
    ctx: dict[str, Any] | None = None,
    source: str = SOURCE_UPLOAD,
) -> dict[str, Any] | None:
    record = build_performance_record(result, ctx=ctx, source=source)
    if not record:
        return None
    history = load_performance_history()
    history.append(record)
    save_performance_history(history)
    return record


def resolve_analysis_source(session_state: dict) -> str:
    from mission_analysis_ui import (
        ANALYSIS_RETURN_TO_METRICS,
        is_analysis_criteria_locked,
    )

    if session_state.get(ANALYSIS_RETURN_TO_METRICS) or is_analysis_criteria_locked(
        session_state
    ):
        return SOURCE_METRICS_UPLOAD
    rt = str(session_state.get("analysis_recording_type") or "").lower()
    if "backing" in rt:
        return SOURCE_BACKING
    return SOURCE_UPLOAD
