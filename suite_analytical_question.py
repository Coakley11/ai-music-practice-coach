"""
Cross-app "Analyze with Applied Math" — shared payload, submit, and deep links.

Source apps (Baseball, NBA, Investment) log ``analytical_question`` events;
Command Center surfaces Continue cards targeting Applied Intelligence.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import copy
import uuid
from datetime import datetime, timezone
from collections.abc import Callable
from typing import Any

from activity_time import format_eastern_time_label, parse_activity_timestamp, utc_now_iso

log = logging.getLogger(__name__)

AMI_SIDEBAR_DEPLOY_LABEL = "Applied Math question sender live"
AMI_SIDEBAR_DEPLOY_VERSION = "2026-06-08-return-insight-restore-v12"
_CTX_JSON_SUBTITLE_LIMIT = 8000
_CONTEXT_ITEM_TYPE = "analytical_question_context"
PRACTICE_LOG_ANALYSIS_TITLE = "Practice Analysis"
PRACTICE_LOG_ANALYSIS_CONTINUE_PRIORITY = 65
ANALYTICAL_QUESTION_CONTINUE_PRIORITY = 64
ANALYTICAL_QUESTION_BUTTON_LABEL = "Continue in Applied Mathematics →"
_SEND_COOLDOWN_SECONDS = 120

_AMI_COACH_SUBMIT_FEEDBACK_KEY = "_music_coach_submit_feedback"
MUSIC_COACH_SUBMIT_DIAG_KEY = "_music_coach_ami_submit_diag"

_SOURCE_AREA: dict[str, str] = {
    "baseball": "sports",
    "nba": "sports",
    "investment": "forecasting",
    "music": "music",
}

_SOURCE_LABELS: dict[str, str] = {
    "baseball": "Baseball",
    "nba": "NBA",
    "investment": "Investment",
    "music": "Music",
}

_SOURCE_APP_ID_ALIASES: dict[str, str] = {
    "music": "music",
    "music practice coach": "music",
    "music coach": "music",
    "music practice": "music",
    "baseball": "baseball",
    "baseball stat app": "baseball",
    "nba": "nba",
    "nba playoff companion": "nba",
    "investment": "investment",
    "investment portfolio analyzer": "investment",
}


def normalize_source_app_id(
    source_app: str,
    context: dict[str, Any] | None = None,
) -> str:
    """Map display labels and context values to canonical suite app ids."""
    raw = str(source_app or "").strip().lower()
    if raw in _SOURCE_APP_ID_ALIASES:
        return _SOURCE_APP_ID_ALIASES[raw]
    if raw in _SOURCE_LABELS:
        return raw
    if context and isinstance(context, dict):
        ctx_raw = str(context.get("source_app") or "").strip().lower()
        if ctx_raw in _SOURCE_APP_ID_ALIASES:
            return _SOURCE_APP_ID_ALIASES[ctx_raw]
        if ctx_raw in _SOURCE_LABELS:
            return ctx_raw
        if "music" in ctx_raw and "math" not in ctx_raw:
            return "music"
    if "music" in raw and "math" not in raw:
        return "music"
    return raw

_MUSIC_COACH_PLACEHOLDERS: dict[str, str] = {
    "practice": "e.g. How should I practice this song?",
    "backing": "e.g. How do I use Backing Track Studio?",
    "custom": "e.g. What scale works over this progression?",
    "karaoke": "e.g. How do I use Karaoke mode?",
}

# Only these keys may appear in user-facing context output.
_PUBLIC_CONTEXT_KEYS = (
    "source_app",
    "page",
    "workflow",
    "players",
    "player",
    "player_a",
    "player_b",
    "team",
    "opponent",
    "metrics",
    "league_format",
    "draft_format",
    "draft_round",
    "current_pick",
    "health_score",
    "portfolio_value",
    "expected_return",
    "volatility",
    "objective",
    "portfolio_preset",
    "holdings",
    "macro_summary",
    "win_probability",
    "series_probability",
    "trend_summary",
    "trend_window",
    "comparison_stats",
    "comparison_differences",
    "stat_gap",
    "player",
    "draft_projection",
    "historical_snapshot",
    "table_summary",
    "filters_applied",
    "sharpe_ratio",
    "max_drawdown",
    "risk_level",
    "rebalance_drift",
    "target_weights",
    "current_weights",
    "macro_outlook",
    "model_assumptions",
    "experience_mode",
    "games_remaining",
    "rate_needed",
    "matchup_advantages",
    "injury_summary",
    "key_players",
    "series_record",
    "rebalance_recommendation",
    "total_drift",
    "historical_comparison",
    "draft_snapshot",
    "roster",
    "recommended_players",
    "sleepers",
    "scoring_settings",
    "ami_guidance",
    "projection",
    "watchlist",
)

_CONTEXT_LABELS = {
    "source_app": "Source app",
    "page": "Page",
    "workflow": "Workflow",
    "players": "Players",
    "player": "Player",
    "player_a": "Player A",
    "player_b": "Player B",
    "team": "Team",
    "opponent": "Opponent",
    "metrics": "Metric(s)",
    "league_format": "League",
    "draft_format": "Draft format",
    "draft_round": "Draft round",
    "current_pick": "Current pick",
    "health_score": "Health score",
    "portfolio_value": "Portfolio value",
    "expected_return": "Expected return",
    "volatility": "Volatility",
    "objective": "Goal",
    "portfolio_preset": "Portfolio preset",
    "holdings": "Holdings",
    "macro_summary": "Macro outlook",
    "win_probability": "Win probability",
    "series_probability": "Series probability",
    "trend_summary": "Trend summary",
    "trend_window": "Trend window",
    "comparison_stats": "Comparison stats",
    "comparison_differences": "Key differences",
    "stat_gap": "Stat gap",
    "draft_projection": "Draft projection",
    "historical_snapshot": "Historical snapshot",
    "table_summary": "Table summary",
    "filters_applied": "Filters",
    "sharpe_ratio": "Sharpe ratio",
    "max_drawdown": "Max drawdown",
    "risk_level": "Risk level",
    "rebalance_drift": "Weight drift",
    "target_weights": "Target weights",
    "current_weights": "Current weights",
    "macro_outlook": "Macro outlook",
    "model_assumptions": "Model assumptions",
    "experience_mode": "Experience mode",
    "games_remaining": "Games remaining",
    "rate_needed": "Rate needed",
    "matchup_advantages": "Matchup advantages",
    "injury_summary": "Injury summary",
    "key_players": "Key players",
    "series_record": "Series record",
    "rebalance_recommendation": "Rebalance recommendation",
    "total_drift": "Total drift",
    "historical_comparison": "Historical comparison",
}


def default_area_for_source(source_app: str) -> str:
    return _SOURCE_AREA.get(str(source_app or "").strip(), "abstract")


def source_app_label(source_app: str) -> str:
    key = str(source_app or "").strip().lower()
    if key == "music":
        return "Music Practice Coach"
    return _SOURCE_LABELS.get(key, key.replace("_", " ").title())


def is_practice_log_analysis_context(context: dict[str, Any] | None) -> bool:
    ctx = dict(context or {})
    return (
        str(ctx.get("user_request") or "") == "analyze_practice"
        or str(ctx.get("intent") or "") in {"practice_history_analysis", "practice_log_analysis"}
        or str(ctx.get("display_category") or "") == "analysis_handoff"
        or str(ctx.get("handoff_kind") or "") == "practice_log_analysis"
    )


def is_practice_log_analysis_payload(payload: dict[str, Any] | None) -> bool:
    """True for Practice Analysis resume/handoff payloads (context or top-level flags)."""
    data = dict(payload or {})
    if str(data.get("handoff_kind") or "") == "practice_log_analysis":
        return True
    ctx = data.get("context") if isinstance(data.get("context"), dict) else {}
    return is_practice_log_analysis_context(ctx)


def source_question_card_title(
    source_app: str,
    context: dict[str, Any] | None = None,
) -> str:
    """Normalized Continue / activity title for cross-app questions."""
    ctx = dict(context or {})
    app = normalize_source_app_id(source_app, ctx)
    if is_practice_log_analysis_context(ctx):
        return PRACTICE_LOG_ANALYSIS_TITLE
    if app == "music":
        return "Music Coach question from Music"
    label = _SOURCE_LABELS.get(app, app.replace("_", " ").title())
    if app in {"baseball", "nba", "investment"}:
        return f"Applied Math question from {label}"
    return f"Question from {label}"


def music_coach_question_placeholder(source_page: str) -> str:
    page = str(source_page or "").strip().lower()
    return _MUSIC_COACH_PLACEHOLDERS.get(
        page,
        "e.g. What notes are in C minor?",
    )


NBA_INSIGHT_EXAMPLE_QUESTIONS: tuple[str, ...] = (
    "Is the Knicks' fourth-quarter scoring trend meaningful?",
    "Which player matchup matters most tonight?",
    "Is this playoff series shifting momentum?",
    "Are the Knicks relying too much on Brunson?",
    "What is the biggest risk for this team tonight?",
    "Which lineup has the best advantage?",
)


def nba_insight_question_placeholder(source_page: str) -> str:
    _ = source_page
    return f"e.g. {NBA_INSIGHT_EXAMPLE_QUESTIONS[0]}"


def _normalize_question(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def _player_name(raw: Any) -> str:
    return str(raw or "").split(" (")[0].strip()


def question_dedupe_fingerprint(
    question: str,
    *,
    source_app: str = "",
    source_page: str = "",
    context: dict[str, Any] | None = None,
) -> str:
    """Stable id for dedupe — same app, page, question, and key entities → same card."""
    ctx = dict(context or {})
    parts = [
        str(source_app or "").strip().lower(),
        str(source_page or "").strip().lower(),
        _normalize_question(question),
    ]
    for key in (
        "workflow",
        "player",
        "player_a",
        "player_b",
        "team",
        "metrics",
        "players",
        "holdings",
        "health_score",
    ):
        val = ctx.get(key)
        if val is None or val == "":
            continue
        if isinstance(val, list):
            parts.append(",".join(sorted(str(v).lower() for v in val)))
        else:
            parts.append(str(val).lower())
    blob = "|".join(parts)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


def question_id(
    question: str,
    *,
    source_app: str = "",
    source_page: str = "",
    context: dict[str, Any] | None = None,
) -> str:
    return question_dedupe_fingerprint(
        question,
        source_app=source_app,
        source_page=source_page,
        context=context,
    )


def _safe_widget_suffix(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", str(text or "page"))[:48]


def merge_analytical_context(base: dict[str, Any], extra: dict[str, Any] | None) -> dict[str, Any]:
    """Deep-merge page extractor output into base context."""
    out = dict(base or {})
    for key, val in dict(extra or {}).items():
        if val is None or val == "":
            continue
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            merged = dict(out[key])
            merged.update(val)
            out[key] = merged
        else:
            out[key] = val
    return out


def _parse_context_from_resume_subtitle(subtitle: str) -> dict[str, Any]:
    text = str(subtitle or "")
    if "__ctx_json__:" not in text:
        return {}
    _, _, blob = text.partition("\n__ctx_json__:")
    try:
        raw = json.loads(blob.strip())
        return raw if isinstance(raw, dict) else {}
    except json.JSONDecodeError:
        return {}


def generate_practice_analysis_run_id() -> str:
    """Unique id for each Analyze My Practice run — Continue must load this report."""
    return uuid.uuid4().hex[:16]


def clean_analytical_question_display(text: str) -> str:
    """Strip embedded storage JSON from user-facing question text."""
    cleaned = str(text or "").strip()
    if "__ctx_json__:" in cleaned:
        cleaned = cleaned.split("\n__ctx_json__:", 1)[0].strip()
    return cleaned


def format_practice_analysis_updated_label(generated_at: str) -> str:
    """Human-readable updated timestamp for Command Center cards (America/New_York, ET)."""
    raw = str(generated_at or "").strip()
    if not raw:
        return ""
    dt = parse_activity_timestamp(raw)
    if dt is None:
        return raw[:19].replace("T", " ")
    return format_eastern_time_label(dt)


def _practice_log_top_song(payload: dict[str, Any]) -> str:
    ctx = dict(payload.get("context") or {})
    pl = ctx.get("practice_log_summary") if isinstance(ctx.get("practice_log_summary"), dict) else {}
    by_song = pl.get("practice_time_by_song") if isinstance(pl.get("practice_time_by_song"), dict) else {}
    if by_song:
        top_key = max(by_song, key=lambda k: int(by_song.get(k) or 0))
        return str(top_key or "").strip()
    songs = pl.get("most_practiced_songs")
    if isinstance(songs, list) and songs:
        return str(songs[0] or "").strip()
    if isinstance(songs, str) and songs.strip():
        return songs.strip()
    return ""


def _practice_log_instrument_label(payload: dict[str, Any]) -> str:
    ctx = dict(payload.get("context") or {})
    pl = ctx.get("practice_log_summary") if isinstance(ctx.get("practice_log_summary"), dict) else {}
    by_inst = pl.get("practice_time_by_instrument") if isinstance(pl.get("practice_time_by_instrument"), dict) else {}
    if not by_inst:
        return ""
    items = [(str(k), int(v or 0)) for k, v in by_inst.items() if str(k).strip()]
    if not items:
        return ""
    items.sort(key=lambda row: -row[1])
    total = sum(mins for _, mins in items) or 1
    try:
        from practice_history_synthesis import format_instrument_display_name

        fmt = lambda key: format_instrument_display_name(key, payload={"practice_log_summary": pl})
    except Exception:
        fmt = lambda key: str(key).replace("_", " ").title()
    if len(items) == 1:
        return fmt(items[0][0])
    top_key, top_mins = items[0]
    if top_mins / total >= 0.6:
        return fmt(top_key)
    return "Multiple instruments"


def practice_log_analysis_instrument_song_line(payload: dict[str, Any]) -> str:
    """Legacy detail line — prefer practice_log_analysis_card_subtitle."""
    parts: list[str] = []
    top_song = _practice_log_top_song(payload)
    if top_song:
        parts.append(top_song)
    inst = _practice_log_instrument_label(payload)
    if inst:
        parts.append(inst)
    return " · ".join(parts)


def practice_log_analysis_card_subtitle(payload: dict[str, Any]) -> str:
    """Command Center card subtitle — top song, instrument summary, ET updated time."""
    generated = str(
        payload.get("report_generated_at")
        or (payload.get("context") or {}).get("report_generated_at")
        or ""
    ).strip()
    parts: list[str] = []
    top_song = _practice_log_top_song(payload)
    if top_song:
        parts.append(top_song)
    inst = _practice_log_instrument_label(payload)
    if inst:
        parts.append(inst)
    updated = format_practice_analysis_updated_label(generated)
    if updated:
        parts.append(f"Updated {updated}")
    if parts:
        return " · ".join(parts)
    ctx = dict(payload.get("context") or {})
    pl = ctx.get("practice_log_summary") if isinstance(ctx.get("practice_log_summary"), dict) else {}
    count = int(pl.get("session_count") or 0)
    mins = int(pl.get("total_minutes") or 0)
    if count > 0:
        return f"{count} session(s), {mins} min logged — review patterns and next focus"
    return "Practice history analysis from Music Practice Coach"


def practice_log_analysis_resume_subtitle(payload: dict[str, Any]) -> str:
    """Clean CC resume subtitle — no raw __ctx_json__ blob."""
    return practice_log_analysis_card_subtitle(payload)


def _build_practice_log_activity_metrics(
    payload: dict[str, Any],
    *,
    extra_metrics: dict[str, Any],
    action_url: str,
) -> dict[str, Any]:
    """Metrics bundle for practice_log_analysis activity rows and current state."""
    analysis_run_id = str(payload.get("analysis_run_id") or "").strip()
    report_generated_at = str(payload.get("report_generated_at") or "").strip()
    ctx = dict(payload.get("context") or {})
    metrics = metrics_for_applied_math_resume(payload)
    metrics.update(extra_metrics)
    metrics["source_app"] = "music"
    metrics["display_category"] = "analysis_handoff"
    metrics["handoff_kind"] = "practice_log_analysis"
    metrics["handoff_title"] = PRACTICE_LOG_ANALYSIS_TITLE
    metrics["activity_event"] = "practice_log_analysis"
    metrics["analysis_type"] = "practice_history_analysis"
    metrics["resume_key"] = str(payload.get("resume_key") or "").strip()
    metrics["activity_sort_at"] = report_generated_at or utc_now_iso()
    metrics["report_date"] = (report_generated_at or utc_now_iso())[:10]
    metrics["continue_action_url"] = action_url
    metrics["saved_item_title"] = PRACTICE_LOG_ANALYSIS_TITLE
    metrics["saved_item_payload"] = {
        "analysis_type": "practice_history_analysis",
        "title": PRACTICE_LOG_ANALYSIS_TITLE,
        "analysis_run_id": analysis_run_id,
        "report_generated_at": report_generated_at,
        "progress_report": ctx.get("progress_report"),
        "practice_history_payload": ctx.get("practice_history_payload"),
        "log_page_summary": ctx.get("log_page_summary"),
        "recent_sessions": ctx.get("recent_sessions"),
        "tone_history": ctx.get("tone_history"),
        "upload_analysis_summary": ctx.get("upload_analysis_summary"),
        "multitrack_export_summary": ctx.get("multitrack_export_summary"),
        "raw_audio_excluded": ctx.get("raw_audio_excluded", True),
        "base64_excluded": ctx.get("base64_excluded", True),
        "blob_fields_excluded": ctx.get("blob_fields_excluded", True),
    }
    return metrics


def _store_practice_analysis_context_blob(payload: dict[str, Any]) -> bool:
    """Persist latest practice analysis context by run id and stable question id."""
    analysis_run_id = str(payload.get("analysis_run_id") or "").strip()
    qid = str(payload.get("question_id") or "").strip()
    if not analysis_run_id and not qid:
        return False
    blob = {
        "question": payload.get("question"),
        "question_id": qid,
        "analysis_run_id": analysis_run_id,
        "report_generated_at": payload.get("report_generated_at"),
        "source_app": payload.get("source_app"),
        "source_page": payload.get("source_page"),
        "quant_area": payload.get("quant_area"),
        "context": dict(payload.get("context") or {}),
        "source_state": dict(payload.get("source_state") or {}),
        "handoff_kind": "practice_log_analysis",
    }
    title = str(payload.get("display_title") or PRACTICE_LOG_ANALYSIS_TITLE)[:200]
    try:
        from suite_account import remember_saved_item

        store_apps: list[str] = ["applied_intelligence"]
        src_app = str(payload.get("source_app") or "").strip().lower()
        if src_app and src_app not in store_apps:
            store_apps.append(src_app)
        ok = False
        for app_name in store_apps:
            if analysis_run_id:
                remember_saved_item(
                    app_name,
                    _CONTEXT_ITEM_TYPE,
                    analysis_run_id,
                    title=title,
                    payload=blob,
                )
                ok = True
            if qid:
                remember_saved_item(
                    app_name,
                    _CONTEXT_ITEM_TYPE,
                    qid,
                    title=title,
                    payload=blob,
                )
                ok = True
        return ok
    except Exception as exc:
        log.warning("remember_saved_item failed for practice analysis context: %s", exc)
        return False


def _stage_practice_analysis_instant_insight(payload: dict[str, Any]) -> str:
    """Store a fresh instant insight keyed by analysis_run_id for AMI Continue."""
    ctx = dict(payload.get("context") or {})
    question = str(payload.get("question") or "").strip()
    analysis_run_id = str(payload.get("analysis_run_id") or ctx.get("analysis_run_id") or "").strip()
    if not question or not analysis_run_id:
        return ""
    try:
        from applied_math_return_insight import store_applied_math_insight
        from music_ami_instant_solver import solve_instant_music_insight

        solved = solve_instant_music_insight(question, ctx)
        if not solved:
            return ""
        route, result = solved
        insight_id = f"pa:{analysis_run_id}"
        store_applied_math_insight(
            {
                "insight_id": insight_id,
                "question_id": payload.get("question_id"),
                "analysis_run_id": analysis_run_id,
                "report_generated_at": payload.get("report_generated_at"),
                "question": PRACTICE_LOG_ANALYSIS_TITLE,
                "conclusion": result.short_answer,
                "source_app": payload.get("source_app") or "music",
                "source_page": payload.get("source_page") or "log",
                "problem_type": route.problem_type,
                "canonical_instant": True,
                "context_snapshot": {
                    "analysis_run_id": analysis_run_id,
                    "report_generated_at": payload.get("report_generated_at"),
                    "progress_report": ctx.get("progress_report"),
                    "practice_history_payload": ctx.get("practice_history_payload"),
                },
            },
            source_state=dict(payload.get("source_state") or {}),
        )
        return insight_id
    except Exception as exc:
        log.warning("_stage_practice_analysis_instant_insight failed: %s", exc)
        return ""


def _store_question_context_blob(payload: dict[str, Any]) -> bool:
    """Persist full context server-side keyed by question_id (survives URL truncation)."""
    qid = str(payload.get("question_id") or "").strip()
    if not qid:
        return False
    blob = {
        "question": payload.get("question"),
        "question_id": qid,
        "source_app": payload.get("source_app"),
        "source_page": payload.get("source_page"),
        "quant_area": payload.get("quant_area"),
        "context": dict(payload.get("context") or {}),
        "source_state": dict(payload.get("source_state") or {}),
    }
    title = str(
        payload.get("display_title")
        or payload.get("handoff_title")
        or payload.get("question")
        or "Applied Math question"
    )[:200]
    try:
        from suite_account import remember_saved_item

        store_apps: list[str] = ["applied_intelligence"]
        src_app = str(payload.get("source_app") or "").strip().lower()
        if src_app and src_app not in store_apps:
            store_apps.append(src_app)
        for app_name in store_apps:
            remember_saved_item(
                app_name,
                _CONTEXT_ITEM_TYPE,
                qid,
                title=title,
                payload=blob,
            )
        return True
    except Exception as exc:
        log.warning("remember_saved_item failed for analytical context: %s", exc)
        return False


def persist_question_context_blob(payload: dict[str, Any]) -> None:
    """Public wrapper: persist question send snapshot (context + source_state) by question_id."""
    _store_question_context_blob(payload)


def load_analytical_question_context(question_id: str) -> dict[str, Any]:
    """Load full context blob by question_id from saved items or resume subtitle."""
    return load_analytical_question_payload(question_id).get("context") or {}


def load_analytical_question_payload(
    question_id: str,
    *,
    analysis_run_id: str = "",
) -> dict[str, Any]:
    """Load full question blob (context + source_state) by run id or question_id."""
    run_id = str(analysis_run_id or "").strip()
    if run_id:
        payload = _load_context_blob_by_key(run_id)
        if payload:
            return payload
    qid = str(question_id or "").strip()
    if not qid:
        return {}
    payload = _load_context_blob_by_key(qid)
    if payload:
        return payload
    resume_key = f"ai:question:{qid}"
    try:
        from suite_storage_supabase import load_active_resume_items

        for row in load_active_resume_items(limit=40):
            if str(row.get("app") or "") != "applied_intelligence":
                continue
            if str(row.get("item_key") or "") != resume_key:
                continue
            ctx = _parse_context_from_resume_subtitle(str(row.get("subtitle") or ""))
            if ctx:
                return {"context": ctx, "question_id": qid}
    except Exception:
        pass
    return {}


def _load_context_blob_by_key(item_key: str) -> dict[str, Any]:
    """Load analytical question context blob from saved items by item_key."""
    key = str(item_key or "").strip()
    if not key:
        return {}
    search_apps = ["applied_intelligence"]
    try:
        from suite_account import load_saved_items

        for app_name in search_apps:
            rows = load_saved_items(app=app_name, item_type=_CONTEXT_ITEM_TYPE, limit=80)
            for row in rows:
                if str(row.get("item_key") or "") == key:
                    payload = row.get("payload")
                    if isinstance(payload, dict):
                        return copy.deepcopy(payload)
        for app_name in ("investment", "baseball", "nba", "music"):
            if app_name in search_apps:
                continue
            rows = load_saved_items(app=app_name, item_type=_CONTEXT_ITEM_TYPE, limit=80)
            for row in rows:
                if str(row.get("item_key") or "") == key:
                    payload = row.get("payload")
                    if isinstance(payload, dict):
                        return copy.deepcopy(payload)
    except Exception as exc:
        log.warning("load_saved_items failed for question context: %s", exc)
    return {}


def load_analytical_question_source_state(
    question_id: str,
    *,
    analysis_run_id: str = "",
) -> dict[str, Any]:
    """Load page-restore snapshot saved at question send time."""
    payload = load_analytical_question_payload(question_id, analysis_run_id=analysis_run_id)
    ss = payload.get("source_state")
    return dict(ss) if isinstance(ss, dict) else {}


def hydrate_applied_intelligence_session(st: Any, *, metrics: dict[str, Any] | None = None) -> None:
    """Map URL params / resume metrics into Applied Intelligence session keys."""
    ss = st.session_state

    def _qp(name: str) -> str:
        try:
            raw = st.query_params.get(name)
        except Exception:
            return ""
        if raw is None:
            return ""
        if isinstance(raw, list):
            return str(raw[0] or "").strip()
        return str(raw).strip()

    m = dict(metrics or {})
    analysis_run_id = str(
        m.get("analysis_run_id")
        or _qp("suite_practice_analysis_run_id")
        or ""
    ).strip()
    ami_insight = str(m.get("ami_insight") or _qp("suite_ami_insight") or "").strip()
    question = clean_analytical_question_display(
        str(m.get("question") or _qp("suite_ai_question") or "").strip()
    )
    qid = str(m.get("question_id") or m.get("dedupe_fingerprint") or _qp("suite_ai_question_id") or "").strip()
    source_app = str(m.get("source_app") or _qp("suite_ai_source_app") or "").strip()
    source_page = str(m.get("source_page") or _qp("suite_ai_source_page") or "").strip()
    area = str(m.get("quant_area") or m.get("area") or _qp("suite_ai_area") or "").strip()
    page = str(m.get("page") or _qp("suite_page") or "Solve a Problem").strip()

    ctx: dict[str, Any] = {}
    source_state: dict[str, Any] = {}
    hydrate_source = "none"

    # Run-id first: latest Practice Analysis report for this Continue click.
    if analysis_run_id:
        blob_payload = load_analytical_question_payload("", analysis_run_id=analysis_run_id)
        blob_ctx = blob_payload.get("context") if isinstance(blob_payload.get("context"), dict) else {}
        if blob_ctx:
            ctx = copy.deepcopy(blob_ctx)
            hydrate_source = "analysis_run_id_blob"
        blob_ss = blob_payload.get("source_state") if isinstance(blob_payload.get("source_state"), dict) else {}
        if blob_ss:
            source_state = copy.deepcopy(blob_ss)

    # Blob-first: full context by question_id before metrics/URL (avoids truncated deep links).
    if not ctx and qid:
        blob_payload = load_analytical_question_payload(qid)
        blob_ctx = blob_payload.get("context") if isinstance(blob_payload.get("context"), dict) else {}
        if blob_ctx:
            ctx = copy.deepcopy(blob_ctx)
            hydrate_source = "question_id_blob"
        blob_ss = blob_payload.get("source_state") if isinstance(blob_payload.get("source_state"), dict) else {}
        if blob_ss:
            source_state = copy.deepcopy(blob_ss)

    metrics_ctx: dict[str, Any] = {}
    if isinstance(m.get("context"), dict):
        metrics_ctx = copy.deepcopy(m["context"])
    elif m.get("context_json"):
        try:
            parsed = json.loads(str(m["context_json"]))
            if isinstance(parsed, dict):
                metrics_ctx = parsed
        except json.JSONDecodeError:
            pass
    if metrics_ctx:
        if not ctx:
            ctx = metrics_ctx
            hydrate_source = "metrics"
        else:
            for key, val in metrics_ctx.items():
                if key not in ctx or not ctx.get(key):
                    ctx[key] = val

    if not ctx:
        raw_ctx = _qp("suite_ai_context")
        if raw_ctx:
            try:
                parsed = json.loads(raw_ctx)
                if isinstance(parsed, dict):
                    ctx = parsed
                    hydrate_source = "url_query"
            except json.JSONDecodeError:
                pass

    if question:
        ss["_suite_ai_question"] = question
        ss["ps_library_problem"] = question
    if qid:
        ss["_suite_ai_question_id"] = qid
    if analysis_run_id:
        ss["_suite_practice_analysis_run_id"] = analysis_run_id
    if ami_insight:
        ss["_suite_ami_insight"] = ami_insight
    if source_app:
        ss["_suite_ai_source_app"] = source_app
    if source_page:
        ss["_suite_ai_source_page"] = source_page
    if area:
        ss["_suite_ai_area"] = area
    if page:
        ss["_suite_ai_page"] = page
    if ctx:
        ss["_suite_ai_context"] = json.dumps(ctx, ensure_ascii=False)
    if source_state:
        ss["_suite_ai_source_state"] = copy.deepcopy(source_state)
    ss["_suite_ai_hydrate_source"] = hydrate_source
    ss["_suite_ai_hydrate_analysis_run_id"] = analysis_run_id
    ss["_suite_ai_hydrate_ami_insight"] = ami_insight


def _format_context_value(key: str, val: Any) -> str:
    if key == "trend_summary" and isinstance(val, dict):
        parts = []
        for sub, label in (
            ("stat", "metric"),
            ("direction", "direction"),
            ("slope", "slope"),
            ("r2", "R²"),
            ("delta", "change"),
            ("latest", "latest"),
            ("previous", "previous"),
            ("summary", "summary"),
        ):
            v = val.get(sub)
            if v is not None and str(v).strip() != "":
                parts.append(f"{label}={v}")
        return "; ".join(parts)
    if isinstance(val, dict):
        inner = ", ".join(f"{k}: {v}" for k, v in list(val.items())[:6] if v is not None and str(v).strip())
        return inner
    if isinstance(val, list):
        return ", ".join(str(v) for v in val[:8] if str(v).strip())
    return str(val).strip()


def format_context_lines(context: dict[str, Any] | None) -> list[str]:
    """Human-readable context — whitelist only, no raw widget keys."""
    ctx = dict(context or {})
    lines: list[str] = []
    for key in _PUBLIC_CONTEXT_KEYS:
        val = ctx.get(key)
        if val is None or val == "":
            continue
        text = _format_context_value(key, val)
        if not text:
            continue
        label = _CONTEXT_LABELS.get(key, key.replace("_", " ").title())
        lines.append(f"{label}: {text}")
    return lines[:16]


def analytical_question_continue_copy(payload: dict[str, Any]) -> tuple[str, str, str]:
    """Return (title, subtitle, button_label) for Command Center Continue cards."""
    ctx = payload.get("context") if isinstance(payload.get("context"), dict) else {}
    app = normalize_source_app_id(str(payload.get("source_app") or ""), ctx)
    question = str(payload.get("question") or "").strip()
    if is_practice_log_analysis_payload(payload):
        card_payload = {
            "source_app": payload.get("source_app") or app,
            "context": ctx,
            "report_generated_at": payload.get("report_generated_at") or ctx.get("report_generated_at"),
        }
        subtitle = practice_log_analysis_card_subtitle(card_payload)
        return (PRACTICE_LOG_ANALYSIS_TITLE, subtitle, "Continue Practice Log Analysis →")
    title = source_question_card_title(app, ctx)
    if app == "music":
        return (title, question, "Continue with Music Coach →")
    return (title, question, ANALYTICAL_QUESTION_BUTTON_LABEL)


def analytical_question_storage_subtitle(payload: dict[str, Any]) -> str:
    """Resume-item subtitle for storage/rebuild — question only on CC cards; context stays in metrics/URL."""
    ctx = dict(payload.get("context") or {})
    if is_practice_log_analysis_payload(payload):
        return practice_log_analysis_resume_subtitle(payload)
    question = str(payload.get("question") or "").strip()
    ctx_json = json.dumps(ctx, ensure_ascii=False) if ctx else ""
    if ctx_json:
        return f"{question}\n__ctx_json__:{ctx_json[:_CTX_JSON_SUBTITLE_LIMIT]}"
    return question


def metrics_for_applied_math_resume(payload: dict[str, Any]) -> dict[str, Any]:
    """Metrics bundle for deep links into Applied Intelligence."""
    ctx = dict(payload.get("context") or {})
    ctx_lines = format_context_lines(ctx)
    analysis_run_id = str(payload.get("analysis_run_id") or ctx.get("analysis_run_id") or "").strip()
    saved_item_key = analysis_run_id or payload.get("question_id")
    metrics = {
        "question": clean_analytical_question_display(str(payload.get("question") or "")) or payload.get("question"),
        "question_id": payload.get("question_id"),
        "source_app": payload.get("source_app"),
        "source_page": payload.get("source_page"),
        "context_summary": payload.get("context_summary"),
        "context_display": " · ".join(ctx_lines),
        "context": ctx,
        "quant_area": payload.get("quant_area"),
        "context_json": json.dumps(ctx, ensure_ascii=False),
        "dedupe_fingerprint": payload.get("question_id"),
        "saved_item_type": _CONTEXT_ITEM_TYPE,
        "saved_item_key": saved_item_key,
    }
    if analysis_run_id:
        metrics["analysis_run_id"] = analysis_run_id
        metrics["report_generated_at"] = payload.get("report_generated_at") or ctx.get("report_generated_at")
    if str(payload.get("ami_insight") or "").strip():
        metrics["ami_insight"] = str(payload.get("ami_insight") or "").strip()
    try:
        from suite_workspace import get_active_workspace_id

        metrics["workspace_id"] = get_active_workspace_id()
    except ImportError:
        pass
    return metrics


def _resume_upsert_succeeded(result: Any) -> bool:
    if isinstance(result, dict):
        return str(result.get("write_mode") or "") not in {"", "skipped"}
    return bool(result)


def _upsert_applied_intelligence_resume(
    payload: dict[str, Any],
    *,
    action_url: str,
) -> bool:
    title, _, _ = analytical_question_continue_copy(payload)
    subtitle = analytical_question_storage_subtitle(payload)
    resume_key = str(payload.get("resume_key") or "").strip()
    if not resume_key:
        return False
    try:
        from suite_storage_supabase import upsert_resume_item

        result = upsert_resume_item(
            "applied_intelligence",
            resume_key,
            title=title,
            subtitle=subtitle,
            action_url=action_url,
        )
        return _resume_upsert_succeeded(result)
    except Exception as exc:
        log.warning("suite_storage_supabase upsert_resume_item failed: %s", exc)
    try:
        from suite_storage import upsert_resume_item

        result = upsert_resume_item(
            "applied_intelligence",
            resume_key,
            title=title,
            subtitle=subtitle,
            action_url=action_url,
        )
        return _resume_upsert_succeeded(result)
    except Exception as exc:
        log.warning("suite_storage upsert_resume_item failed: %s", exc)
    return False


def _upsert_music_practice_log_resume(
    payload: dict[str, Any],
    *,
    action_url: str,
) -> bool:
    """Keep one current Music Practice Log Analysis resume card on the music app."""
    resume_key = str(payload.get("resume_key") or "").strip()
    if not resume_key:
        return False
    subtitle = analytical_question_storage_subtitle(payload)
    try:
        from suite_storage_supabase import upsert_resume_item

        result = upsert_resume_item(
            "music",
            resume_key,
            title=PRACTICE_LOG_ANALYSIS_TITLE,
            subtitle=subtitle,
            action_url=action_url,
        )
        return _resume_upsert_succeeded(result)
    except Exception as exc:
        log.warning("suite_storage_supabase music resume upsert failed: %s", exc)
    try:
        from suite_storage import upsert_resume_item

        result = upsert_resume_item(
            "music",
            resume_key,
            title=PRACTICE_LOG_ANALYSIS_TITLE,
            subtitle=subtitle,
            action_url=action_url,
        )
        return _resume_upsert_succeeded(result)
    except Exception as exc:
        log.warning("suite_storage music resume upsert failed: %s", exc)
    return False


def build_question_payload(
    *,
    source_app: str,
    source_page: str,
    question: str,
    context: dict[str, Any] | None = None,
    context_summary: str = "",
    quant_area: str = "",
    source_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    q = str(question or "").strip()
    if not q:
        raise ValueError("question is required")
    app = str(source_app or "").strip()
    page = str(source_page or "").strip()
    area = str(quant_area or "").strip() or default_area_for_source(app)
    ctx = dict(context or {})
    ctx.setdefault("source_app", source_app_label(app))
    ctx.setdefault("page", _display_page_name(app, page))
    summary = str(context_summary or "").strip()
    if not summary:
        summary = _short_context_summary(ctx)
    qid = question_id(q, source_app=app, source_page=page, context=ctx)
    ctx_display = format_context_lines(ctx)
    return {
        "question": q,
        "question_id": qid,
        "source_app": app,
        "source_page": page,
        "context_summary": summary,
        "context": ctx,
        "context_display": " · ".join(ctx_display),
        "quant_area": area,
        "resume_key": f"ai:question:{qid}",
        "source_state": dict(source_state or {}),
    }


def _display_page_name(source_app: str, page: str) -> str:
    p = str(page or "").strip()
    if p == "Trend Value":
        return "Trends"
    return p


def _short_context_summary(ctx: dict[str, Any]) -> str:
    workflow = str(ctx.get("workflow") or "").strip()
    if workflow:
        players = ctx.get("players")
        if isinstance(players, list) and players:
            return f"{workflow} · {', '.join(str(p) for p in players[:3])}"
        return workflow
    if ctx.get("player"):
        return str(ctx["player"])
    if ctx.get("team"):
        return str(ctx["team"])
    return str(ctx.get("page") or "Current page")


def build_applied_math_resume_url(
    payload: dict[str, Any],
    *,
    base_url: str = "",
    extra_metrics: dict[str, Any] | None = None,
) -> str:
    from suite_deep_links import build_resume_action_url

    metrics = metrics_for_applied_math_resume(payload)
    if extra_metrics:
        metrics.update(extra_metrics)
    metrics["source_app"] = normalize_source_app_id(
        str(payload.get("source_app") or ""),
        dict(payload.get("context") or {}),
    )
    return build_resume_action_url(
        "applied_intelligence",
        resume_key=str(payload.get("resume_key") or ""),
        page="Solve a Problem",
        metrics=metrics,
        base_url=base_url,
    )


def _recent_duplicate_send(
    session_state: dict[str, Any] | None,
    fingerprint: str,
) -> bool:
    if not session_state:
        return False
    last = session_state.get("_ami_last_send")
    if not isinstance(last, dict):
        return False
    if str(last.get("question_id") or "") != fingerprint:
        return False
    ts = parse_activity_timestamp(str(last.get("submitted_at") or ""))
    if ts is None:
        return False
    age = (datetime.now(timezone.utc) - ts).total_seconds()
    return age < _SEND_COOLDOWN_SECONDS


def submit_analytical_question(
    *,
    source_app: str,
    source_page: str,
    question: str,
    context: dict[str, Any] | None = None,
    context_summary: str = "",
    quant_area: str = "",
    source_state: dict[str, Any] | None = None,
    session_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Log event on source app and upsert Applied Intelligence resume item."""
    payload = build_question_payload(
        source_app=source_app,
        source_page=source_page,
        question=question,
        context=context,
        context_summary=context_summary,
        quant_area=quant_area,
        source_state=source_state,
    )
    action_url = build_applied_math_resume_url(payload)
    duplicate = _recent_duplicate_send(session_state, payload["question_id"])
    if not duplicate:
        metrics = metrics_for_applied_math_resume(payload)
        metrics["source_app"] = normalize_source_app_id(
            str(payload.get("source_app") or ""),
            dict(payload.get("context") or {}),
        )
        if metrics["source_app"] == "music":
            summary = f"Asked Music Coach: {payload['question'][:80]}"
        else:
            summary = f"Asked Applied Math: {payload['question'][:80]}"
        try:
            from suite_activity_client import record_activity

            record_activity(
                payload["source_app"],
                "analytical_question",
                page=payload["source_page"],
                metrics=metrics,
                summary=summary,
            )
        except Exception as exc:
            log.warning("record_activity failed for analytical_question: %s", exc)
    _upsert_applied_intelligence_resume(payload, action_url=action_url)
    ss = payload.get("source_state")
    refresh_blob = not duplicate or (
        str(payload.get("source_app") or "").strip().lower() == "investment"
        and isinstance(ss, dict)
        and bool(ss.get("entity_params"))
    )
    if refresh_blob:
        _store_question_context_blob(payload)
    if session_state is not None:
        session_state["_ami_last_send"] = {
            "question_id": payload["question_id"],
            "question": payload["question"],
            "source_app": payload["source_app"],
            "submitted_at": utc_now_iso(),
        }
    card_title, card_subtitle, _ = analytical_question_continue_copy(payload)
    return {
        **payload,
        "action_url": action_url,
        "continue_title": card_title,
        "continue_subtitle": card_subtitle,
        "duplicate": duplicate,
        "submitted_at": utc_now_iso(),
    }


def submit_practice_log_analysis_handoff(
    *,
    source_page: str,
    question: str,
    context: dict[str, Any] | None = None,
    context_summary: str = "",
    source_state: dict[str, Any] | None = None,
    session_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Structured Practice Log analysis handoff — Continue card, not Recent AMI Questions."""
    ctx = dict(context or {})
    analysis_run_id = str(ctx.get("analysis_run_id") or generate_practice_analysis_run_id())
    report_generated_at = str(ctx.get("report_generated_at") or utc_now_iso())
    ctx["analysis_run_id"] = analysis_run_id
    ctx["report_generated_at"] = report_generated_at
    ctx.setdefault("display_category", "analysis_handoff")
    ctx.setdefault("analysis_handoff", True)
    ctx.setdefault("user_request", "analyze_practice")
    ctx.setdefault("analysis_type", "practice_history_analysis")
    ctx.setdefault("intent", "practice_history_analysis")
    ctx.setdefault("handoff_kind", "practice_log_analysis")
    ctx.setdefault("handoff_title", PRACTICE_LOG_ANALYSIS_TITLE)
    payload = build_question_payload(
        source_app="music",
        source_page=source_page,
        question=question,
        context=ctx,
        context_summary=context_summary or "Music Practice Log Analysis",
        source_state=source_state,
    )
    payload["resume_key"] = f"ai:practice_log_analysis:{payload['question_id']}"
    payload["display_title"] = PRACTICE_LOG_ANALYSIS_TITLE
    payload["handoff_kind"] = "practice_log_analysis"
    payload["analysis_run_id"] = analysis_run_id
    payload["report_generated_at"] = report_generated_at

    context_blob_stored = _store_practice_analysis_context_blob(payload)
    insight_id = _stage_practice_analysis_instant_insight(payload)
    if insight_id:
        payload["ami_insight"] = insight_id

    extra_metrics: dict[str, Any] = {
        "analysis_run_id": analysis_run_id,
        "report_generated_at": report_generated_at,
    }
    if insight_id:
        extra_metrics["ami_insight"] = insight_id
    action_url = build_applied_math_resume_url(payload, extra_metrics=extra_metrics)
    clean_subtitle = practice_log_analysis_resume_subtitle(payload)

    duplicate = _recent_duplicate_send(session_state, payload["question_id"])
    record_trace: dict[str, Any] = {}
    activity_recorded = False
    handoff_error = ""
    metrics = _build_practice_log_activity_metrics(
        payload,
        extra_metrics=extra_metrics,
        action_url=action_url,
    )
    try:
        from suite_activity_client import last_record_trace, record_activity

        record_activity(
            "music",
            "practice_log_analysis",
            page=source_page,
            metrics=metrics,
            summary=PRACTICE_LOG_ANALYSIS_TITLE,
            resume_key=payload["resume_key"],
            resume_title=PRACTICE_LOG_ANALYSIS_TITLE,
            resume_subtitle=clean_subtitle,
            action_url=action_url,
        )
        record_trace = last_record_trace()
        activity_recorded = bool(record_trace.get("recorded"))
        if not activity_recorded:
            handoff_error = str(record_trace.get("error") or "record_activity did not persist")
    except Exception as exc:
        handoff_error = str(exc)
        log.warning("record_activity failed for practice_log_analysis: %s", exc)
    resume_upsert_ok = _upsert_applied_intelligence_resume(payload, action_url=action_url)
    music_resume_ok = _upsert_music_practice_log_resume(payload, action_url=action_url)
    if not resume_upsert_ok and not handoff_error:
        handoff_error = "Command Center resume item was not written"
    if not music_resume_ok and not handoff_error:
        handoff_error = "Music resume item was not updated"
    if not context_blob_stored and not handoff_error:
        handoff_error = "Practice analysis context blob was not stored"
    if not insight_id and not handoff_error:
        handoff_error = "Instant insight was not stored for Continue"
    handoff_success = resume_upsert_ok and music_resume_ok and context_blob_stored and bool(insight_id)
    if session_state is not None:
        session_state["_ami_last_send"] = {
            "question_id": payload["question_id"],
            "question": payload["question"],
            "source_app": "music",
            "handoff_kind": "practice_log_analysis",
            "analysis_run_id": analysis_run_id,
            "submitted_at": utc_now_iso(),
        }
        session_state["_practice_log_ami_handoff"] = payload
    card_title, card_subtitle, _ = analytical_question_continue_copy(payload)
    return {
        **payload,
        "action_url": action_url,
        "continue_title": card_title,
        "continue_subtitle": card_subtitle,
        "duplicate": duplicate,
        "submitted_at": utc_now_iso(),
        "handoff_success": handoff_success,
        "activity_recorded": activity_recorded,
        "resume_upsert_ok": resume_upsert_ok,
        "music_resume_ok": music_resume_ok,
        "context_blob_stored": context_blob_stored,
        "insight_id": insight_id,
        "analysis_run_id": analysis_run_id,
        "record_trace": record_trace,
        "handoff_error": handoff_error,
    }


def build_submit_context(
    source_app: str,
    source_page: str,
    session_state: dict[str, Any],
    *,
    context_extra_builder: Callable[[], dict[str, Any] | None] | None = None,
    context_extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Fresh context at Send time — page hooks may run after sidebar render."""
    ctx, _ = build_context_from_session(source_app, source_page, session_state)
    extra: dict[str, Any] | None = None
    if context_extra_builder is not None:
        try:
            extra = context_extra_builder()
        except Exception:
            log.exception("AMI context builder failed for %s (%s)", source_app, source_page)
    elif context_extra:
        extra = context_extra
    if extra:
        ctx = merge_analytical_context(ctx, extra)
    return ctx


def _restore_routed_insight_render_flags(session_state: dict[str, Any]) -> None:
    """Re-arm same-page insight render after duplicate submit or sidebar cooldown."""
    try:
        from applied_math_return_insight import SESSION_PENDING_KEY
    except ImportError:
        SESSION_PENDING_KEY = "_ami_pending_insight"
    pending = session_state.get(SESSION_PENDING_KEY)
    if isinstance(pending, dict) and pending.get("canonical_instant"):
        session_state["_ami_submit_render_insight_this_run"] = True
        session_state["_ami_force_insight_render"] = True


def _record_music_coach_send(
    session_state: dict[str, Any],
    *,
    question_id: str,
    question: str,
    source_app: str,
    result_path: str,
) -> None:
    session_state["_ami_last_send"] = {
        "question_id": question_id,
        "question": question,
        "source_app": source_app,
        "submitted_at": utc_now_iso(),
        "result_path": result_path,
    }


def _render_music_coach_submit_dev_panel(ui: Any, session_state: dict[str, Any]) -> None:
    """Compact dev routing panel for the last Music Coach submit (?dev=1)."""
    diag = session_state.get(MUSIC_COACH_SUBMIT_DIAG_KEY)
    if not isinstance(diag, dict) or not diag:
        ui.caption("Music Coach AMI: no submit diagnostics yet this session.")
        return
    with ui.expander("Music Coach AMI routing (?dev=1)", expanded=True):
        ui.markdown(
            f"**result_path:** `{diag.get('result_path')}` · "
            f"**coach_intent:** `{diag.get('coach_intent')}` · "
            f"**solver:** `{diag.get('solver') or '—'}` · "
            f"**staged:** `{diag.get('insight_staged')}` · "
            f"**markdown:** `{diag.get('insight_markdown_rendered')}` · "
            f"**staff:** `{diag.get('notation_staff_rendered')}`"
        )
        try:
            from applied_math_return_insight import MUSIC_COACH_RENDER_TRACE_KEY

            trace = session_state.get(MUSIC_COACH_RENDER_TRACE_KEY)
        except ImportError:
            trace = None
        if trace:
            ui.caption("Render trace (last run)")
            ui.json(trace)
        try:
            from applied_math_return_insight import MUSIC_COACH_LIFECYCLE_TRACE_KEY

            life = session_state.get(MUSIC_COACH_LIFECYCLE_TRACE_KEY)
            if life:
                ui.caption("Lifecycle trace (?dev=1)")
                ui.json(life)
        except ImportError:
            pass
        ui.json(diag)


def _execute_coach_question_submit(
    st: Any,
    ui: Any,
    session_state: dict[str, Any],
    *,
    question_raw: str,
    source_app: str,
    source_page: str,
    page_suffix: str,
    send_gen: int,
    surface_tag: str = "sidebar",
    context: dict[str, Any] | None = None,
    context_extra_builder: Callable[[], dict[str, Any] | None] | None = None,
    source_state_builder: Callable[[], dict[str, Any] | None] | None = None,
    context_summary: str = "",
    developer_mode: bool = False,
    on_after_send: Callable[[], None] | None = None,
) -> dict[str, Any] | None:
    """Music Coach send: routed AMI pipeline first, else legacy Command Center handoff."""
    q = str(question_raw or "").strip()
    if not q:
        ui.warning("Enter a question first.")
        return None

    submit_ctx = build_submit_context(
        source_app,
        source_page,
        session_state,
        context_extra_builder=context_extra_builder,
        context_extra=context,
    )
    submit_ctx = dict(submit_ctx)
    submit_ctx["question"] = q

    submit_source_state: dict[str, Any] | None = None
    if source_state_builder is not None:
        try:
            submit_source_state = source_state_builder()
        except Exception:
            log.exception("AMI source_state builder failed for %s (%s)", source_app, source_page)

    coach_page = str(submit_ctx.get("coach_page") or source_page).strip()
    try:
        from music_ami_pages import promote_music_ami_context_at_send

        promote_music_ami_context_at_send(
            submit_ctx,
            session_state,
            source_page=coach_page,
            question=q,
        )
    except ImportError:
        pass

    pre_payload = build_question_payload(
        source_app=source_app,
        source_page=source_page,
        question=q,
        context=submit_ctx,
        context_summary=context_summary,
        source_state=submit_source_state,
    )
    question_id = str(pre_payload.get("question_id") or "")

    if _recent_duplicate_send(session_state, question_id):
        last = session_state.get("_ami_last_send")
        last_path = ""
        if isinstance(last, dict):
            last_path = str(last.get("result_path") or "")
        try:
            from applied_math_return_insight import SESSION_PENDING_KEY
        except ImportError:
            SESSION_PENDING_KEY = "_ami_pending_insight"
        pending = session_state.get(SESSION_PENDING_KEY)
        routed_pending = isinstance(pending, dict) and pending.get("canonical_instant")
        if last_path == "routed_coach" or routed_pending:
            _restore_routed_insight_render_flags(session_state)
            dup_msg = (
                "That question was already sent recently. Your Music Coach insight is shown below."
            )
            ui.info(dup_msg)
            session_state[_AMI_COACH_SUBMIT_FEEDBACK_KEY] = {
                "kind": "info",
                "message": dup_msg,
                "result_path": "routed_coach",
            }
            if developer_mode:
                _render_music_coach_submit_dev_panel(ui, session_state)
            st.rerun()
            return {"duplicate": True, "routed": True}
        dup_msg = (
            "That question was already sent recently. Open Command Center to continue with the Music Coach."
            if last_path == "legacy_fallback"
            else "That question was already sent recently. See your insight below or open Command Center."
        )
        ui.info(dup_msg)
        session_state[_AMI_COACH_SUBMIT_FEEDBACK_KEY] = {
            "kind": "info",
            "message": "Duplicate send skipped.",
            "result_path": last_path or "duplicate",
        }
        return {"duplicate": True, "routed": False}

    try:
        from music_coach_ami.pipeline import run_coach_submit
        from music_coach_ami.submit_diagnostics import build_music_coach_submit_diagnostics
        from music_coach_ami.submit_integration import stage_routed_music_coach_insight

        coach_req, coach_resp = run_coach_submit(q, session_state, ami_ctx=submit_ctx)
    except ImportError:
        coach_req = None
        coach_resp = None

    if coach_resp is not None and coach_req is not None:
        diag = build_music_coach_submit_diagnostics(
            coach_req,
            coach_resp,
            result_path="routed_coach",
        )
        session_state[MUSIC_COACH_SUBMIT_DIAG_KEY] = diag
        stage_routed_music_coach_insight(
            st,
            session_state,
            question=q,
            source_page=source_page,
            coach_req=coach_req,
            coach_resp=coach_resp,
            diagnostics=diag,
            question_id=question_id,
            source_state=submit_source_state,
        )
        try:
            from applied_math_return_insight import SESSION_PENDING_KEY
        except ImportError:
            SESSION_PENDING_KEY = "_ami_pending_insight"
        pending = session_state.get(SESSION_PENDING_KEY)
        diag = {
            **diag,
            "notation_abc_present": bool(getattr(coach_resp, "notation_abc", None)),
            "insight_staged": isinstance(pending, dict) and bool(
                pending.get("conclusion") or pending.get("question")
            ),
            "duplicate_suppressed": False,
        }
        st.session_state[MUSIC_COACH_SUBMIT_DIAG_KEY] = diag
        _record_music_coach_send(
            session_state,
            question_id=question_id,
            question=q,
            source_app=source_app,
            result_path="routed_coach",
        )
        try:
            from applied_math_return_insight import record_music_coach_lifecycle_trace

            record_music_coach_lifecycle_trace(
                st,
                phase="coach_submit_staged",
                result_path="routed_coach",
                coach_intent=diag.get("coach_intent"),
                solver=diag.get("solver"),
                insight_id=str((pending or {}).get("insight_id") or "") if isinstance(pending, dict) else None,
                insight_staged=diag.get("insight_staged"),
                preserve_flag=bool(session_state.get("_ami_insight_return_preserve")),
            )
        except ImportError:
            pass
        session_state[_AMI_COACH_SUBMIT_FEEDBACK_KEY] = {
            "kind": "success",
            "message": "Music Coach insight is ready below.",
            "result_path": "routed_coach",
            "surface": surface_tag,
        }
        session_state["_last_analytical_question"] = {
            **pre_payload,
            "routed_coach": True,
            "duplicate": False,
        }
        session_state[f"_ami_send_gen_{source_app}_{page_suffix}"] = send_gen + 1
        if isinstance(pending, dict) and (pending.get("conclusion") or pending.get("question")):
            ui.success("Music Coach insight is ready below.")
        else:
            ui.warning(
                "Music Coach answered your question, but the insight could not be staged for display. "
                "Try again or check ?dev=1 diagnostics."
            )
        if on_after_send is not None:
            try:
                on_after_send()
            except Exception:
                log.exception("on_after_send hook failed for music coach (%s)", source_page)
        if developer_mode:
            _render_music_coach_submit_dev_panel(ui, session_state)
        st.rerun()
        return {"routed": True, "duplicate": False, "question_id": question_id}

    from music_coach_ami.router import route_question

    fallback_req = coach_req if coach_req is not None else route_question(q, session_state, ami_ctx=submit_ctx)
    try:
        from music_coach_ami.submit_diagnostics import build_music_coach_submit_diagnostics

        session_state[MUSIC_COACH_SUBMIT_DIAG_KEY] = build_music_coach_submit_diagnostics(
            fallback_req,
            None,
            result_path="legacy_fallback",
        )
    except ImportError:
        pass

    result = submit_analytical_question(
        source_app=source_app,
        source_page=source_page,
        question=q,
        context=submit_ctx,
        context_summary=context_summary,
        source_state=submit_source_state,
        session_state=session_state,
    )
    session_state["_last_analytical_question"] = result
    session_state[f"_ami_send_gen_{source_app}_{page_suffix}"] = send_gen + 1
    session_state[_AMI_COACH_SUBMIT_FEEDBACK_KEY] = {
        "kind": "success",
        "message": "Question sent to Command Center. Open Command Center to continue with the Music Coach.",
        "result_path": "legacy_fallback",
        "surface": surface_tag,
    }
    _record_music_coach_send(
        session_state,
        question_id=str(result.get("question_id") or question_id),
        question=q,
        source_app=source_app,
        result_path="legacy_fallback",
    )
    if result.get("duplicate"):
        ui.info("That question was already sent recently. Open Command Center to continue with the Music Coach.")
    else:
        ui.success(
            "Question sent to Command Center. Open Command Center to continue with the Music Coach."
        )
    if on_after_send is not None and not result.get("duplicate"):
        try:
            on_after_send()
        except Exception:
            log.exception("on_after_send hook failed for %s (%s)", source_app, source_page)
    if developer_mode:
        _render_music_coach_submit_dev_panel(ui, session_state)
    st.rerun()
    return {**result, "routed": False}


def _stage_music_instant_insight(
    st: Any,
    session_state: dict[str, Any],
    *,
    question: str,
    source_app: str,
    source_page: str,
    submit_ctx: dict[str, Any],
    submit_source_state: dict[str, Any] | None,
    pre_payload: dict[str, Any],
    action_url_pre: str = "",
) -> bool:
    """Legacy instant-insight staging (solve_instant_music_insight → pending card)."""
    try:
        from applied_math_return_insight import (
            build_return_insight_payload,
            stage_pending_insight,
            store_applied_math_insight,
        )
        from music_ami_instant_solver import solve_instant_music_insight
    except ImportError:
        return False

    solved = solve_instant_music_insight(question, dict(submit_ctx))
    if not solved:
        return False
    route, result = solved
    payload = build_return_insight_payload(
        question=question,
        source_app=source_app,
        source_page=source_page,
        question_id=str(pre_payload.get("question_id") or ""),
        route=route,
        result=result,
        context=submit_ctx,
    )
    insight = payload.to_dict()
    insight["canonical_instant"] = True
    store_applied_math_insight(
        insight,
        source_state=submit_source_state,
        st=st,
    )
    stage_pending_insight(st, insight, return_context=submit_source_state)
    session_state["_ami_music_instant_canonical"] = {
        "insight_id": insight.get("insight_id"),
        "question_id": pre_payload.get("question_id"),
    }
    session_state["_ami_submit_render_insight_this_run"] = True
    session_state["_ami_last_submit_source_page"] = source_page
    return True


def render_analyze_with_applied_math_sidebar(
    st: Any,
    *,
    source_app: str,
    source_page: str,
    context: dict[str, Any] | None = None,
    context_extra_builder: Callable[[], dict[str, Any] | None] | None = None,
    source_state_builder: Callable[[], dict[str, Any] | None] | None = None,
    context_summary: str = "",
    default_question: str = "",
    developer_mode: bool = False,
    session_state: dict[str, Any] | None = None,
    on_after_send: Callable[[], None] | None = None,
) -> None:
    """Always-visible sidebar block: question → Command Center → Applied Intelligence."""
    ss = session_state if session_state is not None else st.session_state
    page_suffix = _safe_widget_suffix(source_page)
    send_gen = int(ss.get(f"_ami_send_gen_{source_app}_{page_suffix}") or 0)
    question_key = f"ami_question_{source_app}_{page_suffix}_{send_gen}"
    submit_key = f"ami_submit_{source_app}_{page_suffix}"

    is_music = str(source_app or "").strip().lower() == "music"
    is_nba = str(source_app or "").strip().lower() == "nba"
    if is_music:
        st.sidebar.markdown("### Ask the Music Coach")
        st.sidebar.caption(
            "Get help with practice, theory, navigation, backing tracks, karaoke, or this app."
        )
        submit_label = "Ask the Music Coach"
    elif is_nba:
        st.sidebar.markdown("### Get Basketball Insight")
        st.sidebar.caption(
            "Ask an NBA or playoff question about the team, matchup, or page you're viewing."
        )
        submit_label = "Get NBA Insight"
    else:
        st.sidebar.markdown("### Analyze with Applied Math")
        st.sidebar.caption("Ask a math question about what you are viewing.")
        submit_label = "Send to Command Center"

    last = ss.get("_ami_last_send")
    fb = ss.get(_AMI_COACH_SUBMIT_FEEDBACK_KEY)
    if (
        isinstance(last, dict)
        and last.get("source_app") == source_app
        and _recent_duplicate_send(ss, str(last.get("question_id") or ""))
    ):
        result_path = str(last.get("result_path") or (fb or {}).get("result_path") or "")
        if is_music and result_path == "routed_coach":
            st.sidebar.success("Music Coach insight is ready below.")
        elif is_music:
            st.sidebar.success(
                "Question sent to Command Center. Open Command Center to continue with the Music Coach."
            )
        elif is_nba:
            st.sidebar.success(
                "NBA insight request saved. Open Command Center when you're ready to review it."
            )
        else:
            st.sidebar.success(
                "Question sent to Command Center. Open Command Center to continue in Applied Intelligence."
            )

    question = st.sidebar.text_area(
        "Question",
        value=str(ss.get(question_key) or default_question or "").strip(),
        placeholder=(
            music_coach_question_placeholder(source_page)
            if is_music
            else (
                nba_insight_question_placeholder(source_page)
                if is_nba
                else "e.g. Is this trend meaningful statistically?"
            )
        ),
        height=88,
        key=question_key,
        label_visibility="visible",
    )

    if st.sidebar.button(
        submit_label,
        key=submit_key,
        use_container_width=True,
        type="primary",
    ):
        q = str(question or "").strip()
        if not q:
            st.sidebar.warning("Enter a question first.")
        elif is_music:
            submit_source_state: dict[str, Any] | None = None
            if source_state_builder is not None:
                try:
                    submit_source_state = source_state_builder()
                except Exception:
                    log.exception("AMI source_state builder failed for %s (%s)", source_app, source_page)
            _execute_coach_question_submit(
                st,
                st.sidebar,
                ss,
                question_raw=q,
                source_app=source_app,
                source_page=source_page,
                page_suffix=page_suffix,
                send_gen=send_gen,
                surface_tag="sidebar",
                context=context,
                context_extra_builder=context_extra_builder,
                source_state_builder=source_state_builder,
                context_summary=context_summary,
                developer_mode=developer_mode,
                on_after_send=on_after_send,
            )
        else:
            submit_ctx = build_submit_context(
                source_app,
                source_page,
                ss,
                context_extra_builder=context_extra_builder,
                context_extra=context,
            )
            submit_source_state = None
            if source_state_builder is not None:
                try:
                    submit_source_state = source_state_builder()
                except Exception:
                    log.exception("AMI source_state builder failed for %s (%s)", source_app, source_page)
            result = submit_analytical_question(
                source_app=source_app,
                source_page=source_page,
                question=q,
                context=submit_ctx,
                context_summary=context_summary,
                source_state=submit_source_state,
                session_state=ss,
            )
            ss["_last_analytical_question"] = result
            ss[f"_ami_send_gen_{source_app}_{page_suffix}"] = send_gen + 1
            dup_msg = (
                "That NBA insight was already requested recently. Open Command Center to review it."
                if is_nba
                else "That question was already sent recently. Open Command Center to continue in Applied Intelligence."
            )
            ok_msg = (
                "NBA insight request saved. Open Command Center when you're ready to review it."
                if is_nba
                else "Question sent to Command Center. Open Command Center to continue in Applied Intelligence."
            )
            if result.get("duplicate"):
                st.sidebar.info(dup_msg)
            else:
                st.sidebar.success(ok_msg)
            if on_after_send is not None and not result.get("duplicate"):
                try:
                    on_after_send()
                except Exception:
                    log.exception("on_after_send hook failed for %s (%s)", source_app, source_page)
            st.rerun()

    if is_music and developer_mode:
        _render_music_coach_submit_dev_panel(st.sidebar, ss)

    if developer_mode:
        st.sidebar.caption(f"🛠 {AMI_SIDEBAR_DEPLOY_LABEL} · {AMI_SIDEBAR_DEPLOY_VERSION}")
    st.sidebar.divider()


def render_applied_math_sidebar_entry(
    st: Any,
    *,
    source_app: str,
    source_page: str,
    session_state: dict[str, Any] | None = None,
    context_extra: dict[str, Any] | None = None,
    context_extra_builder: Callable[[], dict[str, Any] | None] | None = None,
    source_state_builder: Callable[[], dict[str, Any] | None] | None = None,
    developer_mode: bool = False,
    on_after_send: Callable[[], None] | None = None,
    **kwargs: Any,
) -> None:
    """Render AMI sidebar near the top; log and surface failures in Developer Mode."""
    if context_extra_builder is None:
        legacy_builder = kwargs.pop("context_builder", None)
        if callable(legacy_builder):
            context_extra_builder = legacy_builder
    kwargs.pop("context", None)
    if kwargs:
        log.debug("render_applied_math_sidebar_entry ignored legacy kwargs: %s", sorted(kwargs))
    ss = session_state if session_state is not None else getattr(st, "session_state", {})
    try:
        builder = context_extra_builder
        if builder is None and context_extra is not None:
            frozen_extra = context_extra

            def builder() -> dict[str, Any] | None:
                return frozen_extra

        render_analyze_with_applied_math_sidebar(
            st,
            source_app=source_app,
            source_page=source_page,
            context_extra_builder=builder,
            source_state_builder=source_state_builder,
            context_summary="",
            developer_mode=developer_mode,
            session_state=ss,
            on_after_send=on_after_send,
        )
    except Exception as exc:
        log.exception("Applied Math sidebar failed for %s (%s)", source_app, source_page)
        if developer_mode:
            st.sidebar.warning(
                f"Applied Math sidebar failed: {type(exc).__name__}: {exc}"
            )


def build_context_from_session(
    source_app: str,
    source_page: str,
    session_state: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    """Clean human context from session — no raw widget keys."""
    app = str(source_app or "").strip()
    app_label = source_app_label(app)
    page_display = _display_page_name(app, source_page)
    ctx: dict[str, Any] = {
        "source_app": app_label,
        "page": page_display,
    }
    summary = page_display

    if app == "baseball":
        low_page = source_page.lower()
        if "draft" in low_page:
            ctx["workflow"] = "Fantasy draft"
            fmt = str(
                session_state.get("draft_format")
                or session_state.get("draft_lab_scoring_type")
                or session_state.get("draft_lab_format")
                or ""
            ).strip()
            if fmt:
                ctx["league_format"] = fmt
                ctx["draft_format"] = fmt
            room = session_state.get("draft_room_state") or {}
            if isinstance(room, dict):
                idx = int(room.get("current_pick_index") or 0)
                num_teams = int(room.get("num_teams") or session_state.get("draft_num_teams") or 12)
                if idx >= 0 and num_teams > 0:
                    ctx["current_pick"] = idx + 1
                    ctx["draft_round"] = (idx // num_teams) + 1
            dq = session_state.get("draft_queue") or []
            if isinstance(dq, list) and dq:
                ctx["player"] = _player_name(dq[0])
                ctx["players"] = [_player_name(x) for x in dq[:4]]
            summary = f"Draft · round {ctx.get('draft_round', '?')}"
        elif source_page == "Comparison Tool":
            ctx["workflow"] = "Player comparison"
            pa = session_state.get("sig_player_a_clean")
            pb = session_state.get("sig_player_b_clean")
            if pa and pb:
                ctx["player_a"] = _player_name(pa)
                ctx["player_b"] = _player_name(pb)
                ctx["players"] = [ctx["player_a"], ctx["player_b"]]
                summary = f"{ctx['player_a']} vs {ctx['player_b']}"
        elif source_page == "Trend Value":
            multi = session_state.get("trend_players_multi") or []
            multi_names = [_player_name(x) for x in multi if x][:6]
            plot_stat = str(session_state.get("trend_plot_stat") or "").strip()
            dash_stats = session_state.get("single_trend_dashboard_stats") or []
            metrics: list[str] = []
            if plot_stat:
                metrics.append(plot_stat)
            if isinstance(dash_stats, list):
                for s in dash_stats:
                    s_str = str(s).strip()
                    if s_str and s_str not in metrics:
                        metrics.append(s_str)
            if len(multi_names) >= 2:
                ctx["workflow"] = "Player trend comparison"
                ctx["players"] = multi_names
                if metrics:
                    ctx["metrics"] = metrics[:6]
                summary = f"{' vs '.join(multi_names[:2])} · {metrics[0] if metrics else 'trends'}"
            else:
                ctx["workflow"] = "Player trend analysis"
                pl = session_state.get("single_trend_dashboard_player")
                if pl:
                    ctx["player"] = _player_name(pl)
                    ctx["players"] = [ctx["player"]]
                if metrics:
                    ctx["metrics"] = metrics[:6]
                summary = f"{ctx.get('player', 'Player')} · {', '.join(metrics[:3]) if metrics else 'trends'}"
                trend_dir = session_state.get("_ami_trend_direction") or session_state.get("trend_direction_label")
                if trend_dir:
                    ctx["trend_summary"] = {"direction": str(trend_dir), "stat": metrics[0] if metrics else ""}
                ami_trend = session_state.get("_ami_trend_summary")
                if isinstance(ami_trend, dict) and ami_trend:
                    ctx["trend_summary"] = {**dict(ctx.get("trend_summary") or {}), **ami_trend}
                lag = session_state.get("trend_lag")
                if lag is not None:
                    ctx["trend_window"] = f"{lag} seasons"
        elif "trade" in low_page:
            ctx["workflow"] = "Trade analysis"
            acquire = session_state.get("pending_trade_acquire_players") or []
            away = session_state.get("pending_trade_away_players") or []
            if isinstance(acquire, list) and acquire:
                ctx["players"] = [_player_name(x) for x in acquire[:4]]
            if isinstance(away, list) and away:
                ctx["player_a"] = _player_name(away[0]) if away else ""
                ctx["player_b"] = _player_name(acquire[0]) if acquire else ""
        elif "lineup" in low_page or "fantasy" in low_page:
            ctx["workflow"] = "Fantasy lineup"
    elif app == "nba":
        page_label = re.sub(r"^[^\w]+", "", str(source_page or "").strip()).strip() or page_display
        ctx["page"] = page_label
        low_page = page_label.lower()
        if "live" in low_page or "game" in low_page:
            ctx["workflow"] = "Live game analysis"
        elif "playoff" in low_page or "bracket" in low_page:
            ctx["workflow"] = "Playoff series outlook"
        elif "matchup" in low_page or "injury" in low_page:
            ctx["workflow"] = "Matchup intelligence"
        else:
            ctx["workflow"] = "NBA analysis"
        team = session_state.get("_nba_persist_team") or session_state.get("favorite_team")
        if team:
            ctx["team"] = str(team)
            summary = str(team)
        pst = session_state.get("playoff_team_state")
        if isinstance(pst, dict):
            opp = str(pst.get("current_opponent") or pst.get("opponent") or "").strip()
            if opp and opp not in ("TBD", "None"):
                ctx["opponent"] = opp
            series_prob = pst.get("series_win_probability") or pst.get("series_prob")
            if series_prob is not None:
                try:
                    ctx["series_probability"] = f"{float(series_prob):.0f}%"
                except (TypeError, ValueError):
                    ctx["series_probability"] = str(series_prob)
        live_prob = session_state.get("live_win_prob_display") or session_state.get("_last_win_prob")
        if live_prob is not None and ("live" in low_page or "game" in low_page):
            try:
                ctx["win_probability"] = f"{float(live_prob):.0f}%"
            except (TypeError, ValueError):
                ctx["win_probability"] = str(live_prob)
    elif app == "investment":
        tab = str(session_state.get("investment_active_tab") or source_page or "").strip()
        if tab:
            ctx["page"] = tab
        if "health" in tab.lower():
            ctx["workflow"] = "Portfolio health review"
        elif "macro" in tab.lower():
            ctx["workflow"] = "Macro analysis"
        elif "frontier" in tab.lower() or "scenario" in tab.lower():
            ctx["workflow"] = "Scenario analysis"
        else:
            ctx["workflow"] = "Portfolio analysis"
        summary = tab or page_display
        health = session_state.get("health_result")
        if health is not None:
            score = getattr(health, "score", None)
            if score is None and isinstance(health, dict):
                score = health.get("score")
            if score is not None:
                ctx["health_score"] = round(float(score), 1) if isinstance(score, (int, float)) else score
        objective = str(
            session_state.get("portfolio_objective")
            or session_state.get("investment_objective")
            or ""
        ).strip()
        if objective:
            ctx["objective"] = objective
        preset = str(session_state.get("portfolio_preset") or session_state.get("asset_preset") or "").strip()
        if preset:
            ctx["portfolio_preset"] = preset
        pv = session_state.get("sidebar_portfolio_value")
        if pv:
            ctx["portfolio_value"] = f"${int(float(pv)):,}"
        try:
            from components.macro_engine import macro_assumption_summary

            summary_text = macro_assumption_summary()
            if summary_text:
                ctx["macro_summary"] = summary_text
                ctx["macro_outlook"] = summary_text
        except Exception:
            pass
        er = session_state.get("portfolio_expected_return") or session_state.get("expected_return_pct")
        vol = session_state.get("portfolio_volatility") or session_state.get("volatility_pct")
        if er is not None:
            try:
                ctx["expected_return"] = f"{float(er):.1f}%"
            except (TypeError, ValueError):
                ctx["expected_return"] = str(er)
        if vol is not None:
            try:
                ctx["volatility"] = f"{float(vol):.1f}%"
            except (TypeError, ValueError):
                ctx["volatility"] = str(vol)
        hr = session_state.get("health_result")
        if hr is not None and hasattr(hr, "expected_return"):
            try:
                ctx.setdefault("expected_return", f"{float(hr.expected_return):.1f}%")
            except Exception:
                pass
        if hr is not None and hasattr(hr, "volatility"):
            try:
                ctx.setdefault("volatility", f"{float(hr.volatility):.1f}%")
            except Exception:
                pass
        tickers: list[str] = []
        df = session_state.get("holdings_df")
        try:
            import pandas as pd

            if isinstance(df, pd.DataFrame) and "Ticker" in df.columns:
                tickers = [str(t).strip() for t in df["Ticker"].dropna().tolist()[:8] if str(t).strip()]
        except Exception:
            pass
        if tickers:
            ctx["holdings"] = tickers
            summary = f"{summary} · {', '.join(tickers[:4])}"
        inv_extra = session_state.get("_ami_investment_context")
        if isinstance(inv_extra, dict) and inv_extra:
            for k, v in inv_extra.items():
                if v is not None and v != "":
                    ctx[k] = v
        hr_obj = session_state.get("health_result")
        if hr_obj is not None:
            for attr, key in (
                ("sharpe", "sharpe_ratio"),
                ("max_drawdown", "max_drawdown"),
                ("risk_level", "risk_level"),
            ):
                val = getattr(hr_obj, attr, None) if not isinstance(hr_obj, dict) else hr_obj.get(attr)
                if val is not None and val != "":
                    ctx[key] = val
    elif app == "music":
        try:
            from music_coach_context import (
                coach_page_display_name,
                resolve_coach_source_page,
            )

            coach_page = resolve_coach_source_page(session_state)
            ctx["page"] = coach_page_display_name(coach_page)
            ctx["workflow"] = "Music practice coach"
            song = session_state.get("selected_song")
            if isinstance(song, dict):
                title = str(song.get("title") or "").strip()
                artist = str(song.get("artist") or "").strip()
                if title:
                    ctx["song"] = f"{title} — {artist}" if artist else title
            instrument = str(session_state.get("instrument") or "").strip()
            if instrument:
                ctx["instrument"] = instrument
            display_key = str(session_state.get("display_key") or "").strip()
            if display_key:
                ctx["display_key"] = display_key
            section = str(session_state.get("practice_focus_section") or "").strip()
            if section:
                ctx["practice_section"] = section
            summary = ctx.get("song") or ctx["page"]
        except Exception:
            ctx["workflow"] = "Music practice coach"
            summary = page_display

    return ctx, summary


def render_music_coach_sidebar_entry(
    st: Any,
    *,
    source_page: str,
    session_state: dict[str, Any] | None = None,
    context_extra_builder: Callable[[], dict[str, Any] | None] | None = None,
    source_state_builder: Callable[[], dict[str, Any] | None] | None = None,
    developer_mode: bool = False,
    on_after_send: Callable[[], None] | None = None,
) -> None:
    """Music Practice Coach sidebar — Ask the Music Coach (not Applied Math wording)."""
    render_applied_math_sidebar_entry(
        st,
        source_app="music",
        source_page=source_page,
        session_state=session_state,
        context_extra_builder=context_extra_builder,
        source_state_builder=source_state_builder,
        developer_mode=developer_mode,
        on_after_send=on_after_send,
    )


def render_music_coach_page_entry(
    st: Any,
    *,
    source_page: str,
    session_state: dict[str, Any] | None = None,
    context_extra_builder: Callable[[], dict[str, Any] | None] | None = None,
    source_state_builder: Callable[[], dict[str, Any] | None] | None = None,
    developer_mode: bool = False,
    on_after_send: Callable[[], None] | None = None,
) -> None:
    """Practice page main-panel Music Coach ask box (same routed submit path as sidebar)."""
    ss = session_state if session_state is not None else st.session_state
    page_suffix = _safe_widget_suffix(source_page)
    send_gen = int(ss.get(f"_ami_send_gen_music_{page_suffix}") or 0)
    question_key = f"ami_question_music_page_{page_suffix}_{send_gen}"

    with st.expander("Ask the Music Coach", expanded=False):
        st.caption("Practice, theory, app navigation, backing, karaoke, or Creative — same coach as the sidebar.")
        question = st.text_area(
            "Question",
            value=str(ss.get(question_key) or "").strip(),
            placeholder=music_coach_question_placeholder(source_page),
            height=88,
            key=question_key,
            label_visibility="collapsed",
        )
        if st.button(
            "Ask the Music Coach",
            key=f"ami_submit_music_page_{page_suffix}",
            use_container_width=True,
            type="primary",
        ):
            _execute_coach_question_submit(
                st,
                st,
                ss,
                question_raw=str(question or ""),
                source_app="music",
                source_page=source_page,
                page_suffix=page_suffix,
                send_gen=send_gen,
                surface_tag="page",
                context_extra_builder=context_extra_builder,
                source_state_builder=source_state_builder,
                developer_mode=developer_mode,
                on_after_send=on_after_send,
            )

    if developer_mode:
        _render_music_coach_submit_dev_panel(st, ss)


def render_pending_music_coach_insight(
    st: Any,
    *,
    studio_page: str = "",
    developer_mode: bool = False,
) -> bool:
    """Canonical same-page render for staged routed Music Coach insights."""
    import app_ui as _app_ui

    if _app_ui._MUSIC_INSIGHT_RENDERED_THIS_EXEC:
        return False
    ss = st.session_state if hasattr(st, "session_state") else st
    try:
        from applied_math_return_insight import (
            MUSIC_COACH_RENDER_TRACE_KEY,
            SESSION_PENDING_KEY,
            _pending_insight_valid,
        )
        from music_coach_context import resolve_coach_source_page
    except ImportError:
        return False

    pending = _pending_insight_valid(st)
    if not pending:
        return False

    studio = str(studio_page or ss.get("studio_page") or "practice").strip()
    coach = resolve_coach_source_page(ss if isinstance(ss, dict) else dict(ss))
    rendered = False
    for page in (coach, studio):
        if not page:
            continue
        if render_suite_applied_math_insight(st, source_app="music", source_page=page):
            rendered = True
            _app_ui._MUSIC_INSIGHT_RENDERED_THIS_EXEC = True
            break

    diag = ss.get(MUSIC_COACH_SUBMIT_DIAG_KEY)
    if isinstance(diag, dict):
        diag = dict(diag)
        diag["insight_rendered_on_page"] = bool(ss.get("_music_coach_diag_insight_rendered"))
        diag["insight_markdown_rendered"] = bool(ss.get("_music_coach_insight_markdown_rendered"))
        diag["notation_abc_render_attempted"] = bool(
            ss.get("_music_coach_notation_abc_render_attempted")
        )
        diag["notation_staff_rendered"] = bool(ss.get("_music_coach_notation_staff_rendered"))
        ss[MUSIC_COACH_SUBMIT_DIAG_KEY] = diag

    if developer_mode and not rendered:
        staged = bool(pending) and str((diag or {}).get("result_path") or "") == "routed_coach"
        if staged or pending.get("canonical_instant"):
            trace = ss.get(MUSIC_COACH_RENDER_TRACE_KEY) or {}
            st.warning(
                "Routed Music Coach insight is staged but was not rendered on this page. "
                f"Scope/trace: `{trace.get('render_blocked_reason') or trace.get('scope_skip_reason') or 'unknown'}`"
            )
    return rendered


def render_suite_applied_math_insight(
    st: Any,
    *,
    source_app: str = "",
    source_page: str = "",
) -> bool:
    """Source apps: show pending Applied Math insight card on eligible pages."""
    try:
        from applied_math_return_insight import render_suite_applied_math_insight_for_page

        return render_suite_applied_math_insight_for_page(
            st,
            source_app=source_app,
            source_page=source_page,
        )
    except Exception:
        return False
