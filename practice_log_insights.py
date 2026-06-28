"""AI-style insights from practice logs and recording analysis history."""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from practice_studio import build_practice_session_from_logs

ANALYSIS_HISTORY_FILE = Path("analysis_history.json")  # legacy; prefer ai_performance_history

_SKILL_KEYWORDS: dict[str, tuple[str, ...]] = {
    "timing": ("timing", "tempo", "rush", "drag", "groove", "metronome", "rhythm", "pocket"),
    "pitch": ("pitch", "intonation", "sharp", "flat", "in tune", "out of tune"),
    "tone": ("tone", "timbre", "long tone", "long-tone", "sound quality", "breath support"),
    "transitions": ("transition", "change", "switch chord", "chord change"),
    "scales": ("scale", "modes", "arpeggio", "pattern"),
    "strumming": ("strum", "strumming", "picking pattern", "rhythm guitar"),
    "chord clarity": ("buzz", "mute", "fret buzz", "chord clarity", "clean chord"),
}

_INSTRUMENT_FOCUS_HINTS: dict[str, dict[str, str]] = {
    "Guitar": {
        "low_scales": "Add 5–8 minutes of scale or triad work — your logs lean toward rhythm and chords.",
        "low_transitions": "Chord transitions are worth a dedicated slow loop this week.",
    },
    "Saxophone": {
        "low_tone": "Long tones should stay in your warmup — recording feedback points to tone consistency.",
    },
    "Voice": {
        "low_pitch": "Warm up with pitch-focused exercises before lyric-heavy work.",
    },
}


@dataclass
class PracticeLogInsights:
    """Structured coach output for the Practice Log page."""

    headline: str = ""
    progress_summary: list[str] = field(default_factory=list)
    patterns_detected: list[str] = field(default_factory=list)
    weak_areas: list[str] = field(default_factory=list)
    recommended_practice: list[str] = field(default_factory=list)
    suggested_songs: list[str] = field(default_factory=list)
    long_term_trends: list[str] = field(default_factory=list)
    data_notes: list[str] = field(default_factory=list)


def load_analysis_history() -> list[dict[str, Any]]:
    """Load unified AI performance history (all coach analysis sources)."""
    try:
        from ai_performance_history import load_performance_history

        return load_performance_history()
    except Exception:
        if not ANALYSIS_HISTORY_FILE.exists():
            return []
        try:
            data = json.loads(ANALYSIS_HISTORY_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:
            return []


def save_analysis_history(entries: list[dict[str, Any]]) -> None:
    try:
        from ai_performance_history import save_performance_history

        save_performance_history(entries)
    except Exception:
        ANALYSIS_HISTORY_FILE.write_text(
            json.dumps(entries[-80:], indent=2),
            encoding="utf-8",
        )


def analysis_snapshot_from_result(
    result: dict[str, Any],
    *,
    ctx: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Serializable summary for practice-log insights (no audio features)."""
    if not result.get("ok"):
        return None
    ctx = ctx or {}
    scores = dict(result.get("scores") or {})
    ranked = sorted(scores.items(), key=lambda x: x[1]) if scores else []
    weakest = ranked[0][0] if ranked else ""
    strongest = ranked[-1][0] if ranked else ""
    is_mt = bool(result.get("multitrack"))
    return {
        "date": date.today().isoformat(),
        "recorded_at": datetime.now().isoformat(timespec="seconds"),
        "multitrack": is_mt,
        "recording_type": result.get("recording_type") or ctx.get("recording_type", "practice"),
        "filename": result.get("filename", ""),
        "song": result.get("song") or ctx.get("song", ""),
        "instrument": result.get("instrument") or ctx.get("instrument", ""),
        "level": result.get("level") or ctx.get("level", ""),
        "focus": result.get("focus") or ctx.get("focus", ""),
        "scores": scores,
        "weakest_category": weakest,
        "strongest_category": strongest,
        "coach_summary": str(result.get("coach_summary") or ""),
        "biggest_issue": str(result.get("biggest_issue") or result.get("findings", [""])[0] if result.get("findings") else ""),
        "next_focus": str(result.get("next_focus") or ""),
        "most_improved": str(result.get("most_improved") or ""),
        "practice_plan": list(
            result.get("practice_plan") or result.get("tips") or []
        )[:6],
        "ensemble_notes": list(
            result.get("ensemble_notes") or result.get("findings") or []
        )[:4],
        "mission_ids": list(result.get("mission_ids") or []),
        "mission_results": [
            {
                "id": m.get("id"),
                "label": m.get("label"),
                "score": m.get("score"),
                "summary": m.get("summary"),
            }
            for m in (result.get("mission_results") or [])
        ],
        "mission_strongest": str(result.get("mission_strongest") or ""),
        "mission_weakest": str(result.get("mission_weakest") or ""),
        "mission_coach_summary": str(result.get("mission_coach_summary") or ""),
        "mission_next_recommendation": str(result.get("mission_next_recommendation") or ""),
        "overall_improv_score": int(result.get("overall_improv_score") or 0),
    }


def append_analysis_snapshot(
    result: dict[str, Any],
    *,
    ctx: dict[str, Any] | None = None,
    source: str | None = None,
    session_state: dict[str, Any] | None = None,
) -> None:
    try:
        from ai_performance_history import (
            SOURCE_UPLOAD,
            append_performance_record,
            resolve_analysis_source,
        )

        if source is None and session_state is not None:
            source = resolve_analysis_source(session_state)
        if source is None:
            source = SOURCE_UPLOAD
        append_performance_record(result, ctx=ctx, source=source)
        return
    except Exception:
        pass
    snap = analysis_snapshot_from_result(result, ctx=ctx)
    if not snap:
        return
    if source:
        snap["source"] = source
    history = load_analysis_history()
    history.append(snap)
    save_analysis_history(history)


def _parse_log_date(entry: dict[str, Any]) -> date | None:
    raw = str(entry.get("date") or "").strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw[:10], fmt).date()
        except ValueError:
            continue
    return None


def _skill_mentions_from_text(text: str) -> Counter[str]:
    low = (text or "").lower()
    counts: Counter[str] = Counter()
    for skill, words in _SKILL_KEYWORDS.items():
        for w in words:
            if w in low:
                counts[skill] += 1
    return counts


def _entry_song(entry: dict[str, Any]) -> str:
    return str(entry.get("active_song") or entry.get("song") or "").strip()


def _entry_notes(entry: dict[str, Any]) -> str:
    return str(entry.get("notes") or entry.get("practice") or "").strip()


def _entry_minutes(entry: dict[str, Any]) -> int:
    try:
        return int(entry.get("duration_minutes") or entry.get("minutes") or 0)
    except (TypeError, ValueError):
        return 0


def _entry_focus(entry: dict[str, Any]) -> str:
    return str(entry.get("focus_area") or entry.get("focus") or "").strip()


def _aggregate_log_stats(logs: list[dict[str, Any]]) -> dict[str, Any]:
    if not logs:
        return {}
    songs = Counter(_entry_song(e) for e in logs if _entry_song(e))
    instruments = Counter(str(e.get("instrument") or "").strip() for e in logs if e.get("instrument"))
    focuses = Counter(_entry_focus(e) for e in logs if _entry_focus(e))
    genres = Counter(str(e.get("genre") or "").strip() for e in logs if e.get("genre"))
    levels = Counter(str(e.get("level") or "").strip() for e in logs if e.get("level"))
    hard_parts = Counter(
        str(e.get("what_was_hard") or "").strip().lower()
        for e in logs
        if str(e.get("what_was_hard") or "").strip()
    )
    ratings: list[tuple[date | None, float]] = []
    skill_mentions: Counter[str] = Counter()
    dated: list[tuple[date, dict[str, Any]]] = []

    for entry in logs:
        d = _parse_log_date(entry)
        if d:
            dated.append((d, entry))
        rating_val = entry.get("rating")
        ratings_dict = entry.get("ratings") if isinstance(entry.get("ratings"), dict) else {}
        if rating_val is None and ratings_dict.get("confidence") is not None:
            try:
                rating_val = float(ratings_dict["confidence"]) * 2
            except (TypeError, ValueError):
                rating_val = None
        try:
            ratings.append((d, float(rating_val or 0)))
        except (TypeError, ValueError):
            pass
        skill_mentions.update(_skill_mentions_from_text(_entry_notes(entry)))
        skill_mentions.update(_skill_mentions_from_text(str(entry.get("what_was_hard") or "")))

    dated.sort(key=lambda x: x[0])
    today = date.today()
    last_14 = [e for d, e in dated if (today - d).days <= 14]
    last_30 = [e for d, e in dated if (today - d).days <= 30]

    rating_vals = [r for _, r in ratings if r > 0]
    recent_ratings = [r for d, r in ratings if d and (today - d).days <= 30 and r > 0]
    older_ratings = [r for d, r in ratings if d and (today - d).days > 30 and r > 0]

    return {
        "total": len(logs),
        "songs": songs,
        "instruments": instruments,
        "focuses": focuses,
        "genres": genres,
        "levels": levels,
        "skill_mentions": skill_mentions,
        "last_14_count": len(last_14),
        "last_30_count": len(last_30),
        "dated": dated,
        "recent_ratings": recent_ratings,
        "older_ratings": older_ratings,
        "avg_rating": sum(rating_vals) / len(rating_vals) if rating_vals else None,
        "recent_songs": Counter(_entry_song(e) for e in last_14 if _entry_song(e)),
        "hard_parts": hard_parts,
    }


def _score_trends(history: list[dict[str, Any]]) -> dict[str, Any]:
    singles = [h for h in history if h.get("scores") and not h.get("multitrack")]
    if len(singles) < 2:
        return {"has_trend": False, "deltas": {}, "recent": singles[-1] if singles else None}
    recent = singles[-3:]
    older = singles[:-3][-3:] if len(singles) > 3 else singles[:1]
    keys = set()
    for snap in recent + older:
        keys.update(snap.get("scores", {}).keys())
    deltas: dict[str, float] = {}
    for key in keys:
        r_vals = [float(s["scores"].get(key, 0)) for s in recent if s.get("scores")]
        o_vals = [float(s["scores"].get(key, 0)) for s in older if s.get("scores")]
        if r_vals and o_vals:
            deltas[key] = (sum(r_vals) / len(r_vals)) - (sum(o_vals) / len(o_vals))
    return {
        "has_trend": True,
        "deltas": deltas,
        "recent": recent[-1],
        "count": len(singles),
    }


def _parse_iso_date(raw: str) -> date | None:
    raw = str(raw or "").strip()[:10]
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _mission_rows_from_analysis_history(
    analysis_history: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build mission trend rows from unified performance history."""
    rows: list[dict[str, Any]] = []
    for snap in analysis_history:
        missions = snap.get("mission_results") or []
        if not missions and snap.get("criteria_ids"):
            missions = [
                {"id": mid, "label": lbl, "score": 0}
                for mid, lbl in zip(
                    snap.get("criteria_ids") or [],
                    snap.get("criteria_labels") or [],
                )
            ]
        if not missions:
            continue
        rows.append(
            {
                "date": snap.get("date") or "",
                "recorded_at": snap.get("recorded_at") or "",
                "song": snap.get("song") or "",
                "instrument": snap.get("instrument") or "",
                "level": snap.get("level") or "",
                "focus": snap.get("focus") or "",
                "source": snap.get("source") or "",
                "missions": [
                    {
                        "id": m.get("id"),
                        "label": m.get("label"),
                        "score": m.get("score"),
                    }
                    for m in missions
                ],
            }
        )
    return rows


def _mission_history_stats(history: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate mission/metric scores from mission_analysis_history.json."""
    if not history:
        return {"has_data": False}

    today = date.today()
    recent_rows = [
        h
        for h in history
        if (d := _parse_iso_date(str(h.get("date") or ""))) and (today - d).days <= 14
    ]
    older_rows = [
        h
        for h in history
        if (d := _parse_iso_date(str(h.get("date") or ""))) and 14 < (today - d).days <= 60
    ]

    def _mission_scores(rows: list[dict[str, Any]]) -> dict[str, list[int]]:
        by_id: dict[str, list[int]] = {}
        for row in rows:
            for m in row.get("missions") or []:
                mid = str(m.get("id") or "")
                if not mid:
                    continue
                by_id.setdefault(mid, []).append(int(m.get("score") or 0))
        return by_id

    recent_scores = _mission_scores(recent_rows or history[-5:])
    older_scores = _mission_scores(older_rows or history[: max(1, len(history) - 5)])

    deltas: dict[str, float] = {}
    for mid, vals in recent_scores.items():
        if not vals:
            continue
        r_avg = sum(vals) / len(vals)
        o_vals = older_scores.get(mid) or []
        o_avg = sum(o_vals) / len(o_vals) if o_vals else r_avg
        deltas[mid] = r_avg - o_avg

    song_counts: Counter[str] = Counter()
    inst_counts: Counter[str] = Counter()
    focus_counts: Counter[str] = Counter()
    level_counts: Counter[str] = Counter()
    for row in history:
        if row.get("song"):
            song_counts[str(row["song"])] += 1
        if row.get("instrument"):
            inst_counts[str(row["instrument"])] += 1
        if row.get("focus"):
            focus_counts[str(row["focus"])] += 1
        if row.get("level"):
            level_counts[str(row["level"])] += 1

    latest = history[-1] if history else {}
    latest_missions = {
        str(m.get("id") or ""): int(m.get("score") or 0)
        for m in (latest.get("missions") or [])
    }

    return {
        "has_data": True,
        "count": len(history),
        "recent_count": len(recent_rows),
        "deltas": deltas,
        "latest": latest,
        "latest_missions": latest_missions,
        "song_counts": song_counts,
        "inst_counts": inst_counts,
        "focus_counts": focus_counts,
        "level_counts": level_counts,
    }


def _mission_label(mid: str) -> str:
    try:
        from mission_analysis import MISSION_BY_ID

        spec = MISSION_BY_ID.get(mid)
        if spec:
            return spec.label
    except Exception:
        pass
    return mid.replace("_", " ").title()


def _build_mission_narrative(
    mission_stats: dict[str, Any],
    *,
    top_song: str = "",
    timing_improving: bool = False,
) -> str:
    """One-paragraph coach story from mission metric trends."""
    if not mission_stats.get("has_data"):
        return ""

    deltas = mission_stats.get("deltas") or {}
    improving = sorted(
        ((mid, d) for mid, d in deltas.items() if d >= 5),
        key=lambda x: -x[1],
    )
    weak = sorted(
        ((mid, d) for mid, d in deltas.items() if d <= -3),
        key=lambda x: x[1],
    )
    latest = mission_stats.get("latest") or {}
    song = top_song or str(latest.get("song") or "")
    parts: list[str] = []

    if mission_stats.get("recent_count", 0) >= 2:
        parts.append("Over the last two weeks")
    else:
        parts.append("From your recent metric analyses")

    if improving:
        labels = [_mission_label(mid) for mid, _ in improving[:2]]
        if song:
            parts.append(
                f", your **{', '.join(labels)}** improved on **{song}**"
            )
        else:
            parts.append(f", your **{', '.join(labels)}** are trending up")
        if timing_improving:
            parts.append(", and **timing** scores are trending upward")
    elif weak:
        wlabel = _mission_label(weak[0][0])
        parts.append(f", **{wlabel}** still needs focused reps")
    else:
        parts.append(", your mission scores are holding steady")

    latest_missions = mission_stats.get("latest_missions") or {}
    if latest_missions:
        weakest_mid = min(latest_missions, key=lambda k: latest_missions[k])
        weakest_score = latest_missions[weakest_mid]
        if weakest_score < 72 and not weak:
            parts.append(
                f", but **{_mission_label(weakest_mid)}** is still inconsistent ({weakest_score}%)"
            )
        elif weak and not improving:
            parts.append(
                f", but **{_mission_label(weak[0][0])}** is still inconsistent"
            )

    rec = ""
    weak_label = _mission_label(weak[0][0]) if weak else ""
    if weak and "motif" in weak_label.lower():
        section = "Verse"
        rec = (
            f"Next, practice one motif over the **{section}** at 80 BPM and upload another take."
        )
    elif weak:
        rec = (
            f"Next, loop one section at a slower tempo and target **{weak_label}** — "
            "then upload another take."
        )
    elif improving:
        rec = "Next, keep the same tempo and push the same skills on a harder section or chorus."
    else:
        rec = "Next, pick one mission metric, practice it for 10 minutes, and upload a fresh take."

    return "".join(parts) + f". {rec}"


def _category_label(name: str) -> str:
    return {
        "timing": "timing & rhythm",
        "pitch": "pitch & intonation",
        "technique": "technique",
        "groove": "groove",
        "musicality": "musicality",
        "confidence": "confidence",
        "tone": "tone",
    }.get(name, name.replace("_", " "))


def generate_practice_log_insights(
    logs: list[dict[str, Any]],
    *,
    analysis_history: list[dict[str, Any]] | None = None,
    mission_history: list[dict[str, Any]] | None = None,
    session_analysis: dict[str, Any] | None = None,
    all_song_records: list[dict[str, Any]] | None = None,
    session_minutes: int = 25,
) -> PracticeLogInsights:
    """Build coach-style insights from logs and recording analysis."""
    analysis_history = list(analysis_history or [])
    mission_history = _mission_rows_from_analysis_history(analysis_history)
    mission_stats = _mission_history_stats(mission_history)

    criteria_worked: Counter[str] = Counter()
    for row in analysis_history:
        for lbl in row.get("criteria_labels") or []:
            if lbl:
                criteria_worked[str(lbl)] += 1
        for m in row.get("mission_results") or []:
            if m.get("label"):
                criteria_worked[str(m["label"])] += 1
    if session_analysis and session_analysis.get("ok"):
        snap = analysis_snapshot_from_result(session_analysis)
        if snap and not any(
            h.get("recorded_at") == snap.get("recorded_at") for h in analysis_history
        ):
            analysis_history = analysis_history + [snap]

    out = PracticeLogInsights()
    stats = _aggregate_log_stats(logs)
    trends = _score_trends(analysis_history)

    if not logs and not analysis_history and not mission_stats.get("has_data"):
        out.headline = "Start logging sessions and upload a take on **Upload Analysis** — your coach profile will grow from there."
        out.data_notes.append("No practice logs or saved recording analyses yet.")
        out.recommended_practice.append(
            "20 min: 5 min tuner/long tones · 5 min metronome on one chord · "
            "10 min one song section at slow tempo."
        )
        return out

    # --- Headline ---
    top_song = ""
    if stats.get("songs"):
        top_song = stats["songs"].most_common(1)[0][0]
    elif mission_stats.get("song_counts"):
        top_song = mission_stats["song_counts"].most_common(1)[0][0]

    timing_improving = bool(
        trends.get("has_trend") and (trends.get("deltas") or {}).get("timing", 0) >= 4
    )
    mission_story = _build_mission_narrative(
        mission_stats,
        top_song=top_song,
        timing_improving=timing_improving,
    )
    if mission_story:
        out.headline = mission_story
    elif stats.get("total"):
        if top_song and stats.get("recent_songs", Counter()).get(top_song, 0) >= 2:
            out.headline = f"You have practiced **{top_song}** several times recently — good depth on that tune."
        elif stats.get("last_14_count", 0) >= 4:
            out.headline = "Strong practice streak lately — you're building consistent habits."
        else:
            out.headline = "Here's what your practice history is telling your personal coach."
    elif trends.get("recent"):
        out.headline = "Your uploaded recordings are shaping these recommendations."

    # --- Progress summary ---
    recent_r = stats.get("recent_ratings") or []
    older_r = stats.get("older_ratings") or []
    if len(recent_r) >= 2 and len(older_r) >= 2:
        if sum(recent_r) / len(recent_r) > sum(older_r) / len(older_r) + 0.4:
            out.progress_summary.append(
                "Self-ratings are trending up — you may be feeling more confident in recent sessions."
            )
    elif len(recent_r) >= 3 and sum(recent_r) / len(recent_r) >= 7:
        out.progress_summary.append("Recent sessions are rated highly — keep the same warmup structure.")

    if mission_stats.get("has_data"):
        m_deltas = mission_stats.get("deltas") or {}
        for mid, delta in sorted(m_deltas.items(), key=lambda x: -x[1])[:3]:
            if delta >= 4:
                out.progress_summary.append(
                    f"Mission metric **{_mission_label(mid)}** is improving (+{delta:.0f} pts vs earlier takes)."
                )
        latest_m = mission_stats.get("latest") or {}
        if latest_m.get("song"):
            out.progress_summary.append(
                f"Latest metric analysis on **{latest_m['song']}** "
                f"({latest_m.get('instrument', '')}, {latest_m.get('level', '')}, {latest_m.get('focus', '')})."
            )

    if trends.get("has_trend"):
        deltas = trends["deltas"]
        improving = [k for k, v in deltas.items() if v >= 4]
        for cat in improving[:3]:
            out.progress_summary.append(
                f"Your **{_category_label(cat)}** appears to be improving based on recent recording analyses."
            )
        recent_snap = trends.get("recent") or {}
        if recent_snap.get("most_improved"):
            out.progress_summary.append(f"Latest take highlight: {recent_snap['most_improved']}.")
        if recent_snap.get("coach_summary"):
            excerpt = recent_snap["coach_summary"][:220]
            if len(recent_snap["coach_summary"]) > 220:
                excerpt += "…"
            out.progress_summary.append(excerpt)

    if stats.get("songs"):
        repeat = stats["songs"].most_common(1)[0]
        if repeat[1] >= 3:
            out.progress_summary.append(
                f"You've returned to **{repeat[0]}** {repeat[1]} times — familiarity is building."
            )

    if not out.progress_summary:
        out.progress_summary.append(
            "Keep logging after each session — patterns become clearer after a few entries."
        )

    # --- Patterns ---
    if stats.get("total"):
        out.patterns_detected.append(f"**{stats['total']}** logged session(s) total.")
        if stats.get("last_14_count"):
            out.patterns_detected.append(
                f"**{stats['last_14_count']}** session(s) in the last 14 days."
            )
        for label, counter, title in (
            ("song", stats.get("songs"), "Most practiced songs"),
            ("instrument", stats.get("instruments"), "Instruments"),
            ("focus", stats.get("focuses"), "Practice focuses"),
        ):
            if counter:
                top = counter.most_common(4)
                lines = ", ".join(f"**{name}** ({n})" for name, n in top if name)
                if lines:
                    out.patterns_detected.append(f"{title}: {lines}.")

    if criteria_worked:
        crit_line = ", ".join(
            f"**{name}** ({n})" for name, n in criteria_worked.most_common(6) if name
        )
        if crit_line:
            out.patterns_detected.append(f"Skills/metrics you've worked on: {crit_line}.")

    sources = Counter(str(h.get("source") or "Analysis") for h in analysis_history)
    if sources:
        src_line = ", ".join(f"**{s}** ({n})" for s, n in sources.most_common(4) if s)
        if src_line:
            out.patterns_detected.append(f"Analysis sources: {src_line}.")

    if mission_stats.get("has_data"):
        out.patterns_detected.append(
            f"**{mission_stats['count']}** scored improvisation/metric run(s) in history."
        )

    if trends.get("count"):
        out.patterns_detected.append(
            f"**{trends['count']}** AI coach recording analysis(es) on file."
        )
        inst_from_analysis = Counter(
            str(h.get("instrument") or "") for h in analysis_history if h.get("instrument")
        )
        if inst_from_analysis:
            top_i = inst_from_analysis.most_common(1)[0]
            out.patterns_detected.append(
                f"Recording analyses mostly on **{top_i[0]}** ({top_i[1]} take(s))."
            )

    # --- Weak areas ---
    focus_ctr: Counter[str] = stats.get("focuses") or Counter()
    skill_m: Counter[str] = stats.get("skill_mentions") or Counter()
    top_inst = (stats.get("instruments") or Counter()).most_common(1)
    inst_name = top_inst[0][0] if top_inst else ""

    strumming_hits = skill_m.get("strumming", 0) + focus_ctr.get("Strumming", 0) + focus_ctr.get("Rhythm Guitar", 0)
    scales_hits = skill_m.get("scales", 0) + focus_ctr.get("Scales", 0)
    if strumming_hits >= 2 and scales_hits <= 0:
        out.weak_areas.append(
            "You are spending a lot of time on strumming, but less on scales — balance with 5–8 min scalar work."
        )
    if scales_hits >= 2 and strumming_hits == 0 and inst_name == "Guitar":
        out.weak_areas.append(
            "Scale work is showing up often — add rhythm-guitar or groove time for performance readiness."
        )

    for skill, count in skill_m.most_common(3):
        if count >= 2:
            out.weak_areas.append(
                f"Your written logs mention **{skill}** often — treat it as an active growth area."
            )

    hard_parts: Counter[str] = stats.get("hard_parts") or Counter()
    for part, count in hard_parts.most_common(2):
        if part:
            label = part[:80] + ("…" if len(part) > 80 else "")
            out.weak_areas.append(f"Repeated challenge in your log: **{label}** ({count}×).")

    recent_next_steps = [
        str(e.get("next_step") or "").strip()
        for e in sorted(logs, key=lambda x: str(x.get("date") or ""), reverse=True)
        if str(e.get("next_step") or "").strip()
    ]

    if mission_stats.get("has_data"):
        m_deltas = mission_stats.get("deltas") or {}
        declining_m = sorted(
            ((mid, d) for mid, d in m_deltas.items() if d <= -4),
            key=lambda x: x[1],
        )
        for mid, delta in declining_m[:2]:
            out.weak_areas.append(
                f"Mission **{_mission_label(mid)}** has dipped ({delta:+.0f} vs earlier metric runs)."
            )
        latest_missions = mission_stats.get("latest_missions") or {}
        for mid, score in sorted(latest_missions.items(), key=lambda x: x[1])[:2]:
            if score < 68:
                out.weak_areas.append(
                    f"Latest take: **{_mission_label(mid)}** scored {score}% — worth a focused loop."
                )

    if trends.get("has_trend"):
        deltas = trends["deltas"]
        declining = sorted(
            ((k, v) for k, v in deltas.items() if v <= -4),
            key=lambda x: x[1],
        )
        for cat, delta in declining[:2]:
            out.weak_areas.append(
                f"**{_category_label(cat).title()}** has dipped in recent analyses ({delta:+.0f} vs earlier takes)."
            )
        recent_snap = trends.get("recent") or {}
        if recent_snap.get("biggest_issue"):
            out.weak_areas.append(f"Latest recording: {recent_snap['biggest_issue']}")
        if recent_snap.get("weakest_category"):
            w = recent_snap["weakest_category"]
            score = (recent_snap.get("scores") or {}).get(w)
            if score is not None:
                out.weak_areas.append(
                    f"Recording coach flagged **{_category_label(w)}** (score {score}/100)."
                )

    if inst_name == "Guitar" and focus_ctr.get("Chord Transitions", 0) == 0:
        if trends.get("has_trend") and trends["deltas"].get("technique", 0) >= 3:
            out.progress_summary.append("Your guitar chord transitions are improving.")
        elif skill_m.get("transitions", 0) >= 1 or skill_m.get("chord clarity", 0) >= 1:
            out.weak_areas.append(
                "Chord transitions and clarity show up in your notes — slow loop two chords per bar."
            )

    hints = _INSTRUMENT_FOCUS_HINTS.get(inst_name, {})
    if inst_name == "Saxophone" and (
        skill_m.get("tone", 0) >= 1
        or (trends.get("recent") or {}).get("weakest_category") == "tone"
    ):
        out.weak_areas.append(hints.get("low_tone", "Long tones should stay in your warmup."))

    if not out.weak_areas:
        out.weak_areas.append(
            "No major weak spots flagged yet — consider uploading a take on Upload Analysis for objective feedback."
        )

    # --- Recommended practice (20–30 min) ---
    if recent_next_steps:
        out.recommended_practice.append(f"- Your last next step: {recent_next_steps[0]}")

    plan = build_practice_session_from_logs(
        logs,
        all_song_records or [],
        minutes=session_minutes,
    )
    if plan:
        block_mins = max(5, session_minutes // 5)
        out.recommended_practice.append(
            f"**~{session_minutes} min personalized plan** (from your log history):"
        )
        for key, icon in (
            ("warmup", "Warmup"),
            ("technique", "Technique"),
            ("main", "Main"),
            ("challenge", "Challenge"),
            ("cooldown", "Cooldown"),
        ):
            if plan.get(key):
                out.recommended_practice.append(f"- {icon} ({block_mins}+ min): {plan[key]}")

    latest_mission_row = mission_stats.get("latest") or {}
    if latest_mission_row.get("song"):
        weak_m = sorted(
            (m for m in (latest_mission_row.get("missions") or [])),
            key=lambda x: int(x.get("score") or 0),
        )
        if weak_m:
            w = weak_m[0]
            out.recommended_practice.append(
                f"- On **{latest_mission_row['song']}**: 10 min looping one section at ~80% tempo "
                f"targeting **{w.get('label', _mission_label(str(w.get('id', ''))))}**, then upload another take."
            )

    recent_snap = trends.get("recent") or {}
    if recent_snap.get("next_focus"):
        out.recommended_practice.append(f"- From your last recording: {recent_snap['next_focus']}")
    if recent_snap.get("mission_next_recommendation"):
        out.recommended_practice.append(
            f"- {recent_snap['mission_next_recommendation']}"
        )
    if recent_snap.get("practice_plan"):
        for item in recent_snap["practice_plan"][:3]:
            out.recommended_practice.append(f"- {item}")

    if skill_m.get("timing", 0) >= 1 or (trends.get("recent") or {}).get("weakest_category") == "timing":
        out.recommended_practice.append(
            "- **Rhythm stability:** metronome at −20 BPM, one section, 4-bar loops; "
            "then notch up 4 BPM only when clean."
        )
        out.recommended_practice.append(
            "- **Section transitions:** play last 2 bars of previous section + first 2 of the next."
        )
    elif not any("transition" in s.lower() for s in out.recommended_practice):
        out.recommended_practice.append(
            "- You may want to focus next on rhythm stability and smoother section transitions."
        )

    # --- Suggested songs / exercises ---
    records = all_song_records or []
    practiced_titles = {str(e.get("song") or "").strip() for e in logs}
    if records:
        genre_top = (stats.get("genres") or Counter()).most_common(1)
        genre_pref = genre_top[0][0] if genre_top else ""
        candidates = [
            r
            for r in records
            if r.get("chart_status") != "placeholder"
            and r.get("title") not in practiced_titles
        ]
        if genre_pref:
            genre_match = [r for r in candidates if r.get("genre") == genre_pref]
            candidates = genre_match or candidates
        for r in candidates[:4]:
            title = r.get("title", "")
            artist = r.get("artist", "")
            why = "new to your log" if title not in practiced_titles else "revisit"
            out.suggested_songs.append(f"**{title}** — {artist} ({why})")
        if stats.get("songs"):
            revisit = stats["songs"].most_common(1)[0][0]
            if revisit:
                out.suggested_songs.append(
                    f"**{revisit}** — deepen one weak section with Upload Analysis before adding new tunes."
                )

    if recent_snap.get("practice_plan"):
        for item in recent_snap["practice_plan"][:2]:
            if item not in out.suggested_songs:
                out.suggested_songs.append(f"Exercise from last analysis: {item}")

    if not out.suggested_songs:
        out.suggested_songs.append("Pick any song from Song Selection that matches your current genre and level.")

    # --- Long-term trends ---
    if trends.get("has_trend"):
        for cat, delta in sorted(trends["deltas"].items(), key=lambda x: -x[1])[:4]:
            label = _category_label(cat).title()
            if delta >= 5:
                out.long_term_trends.append(f"**{label}** — improving")
            elif delta <= -5:
                out.long_term_trends.append(f"**{label}** — needs focused work")
            else:
                out.long_term_trends.append(f"**{label}** — holding steady")
    else:
        out.long_term_trends.append("Upload a few takes over time to unlock timing/tone trend lines.")

    if recent_r and older_r:
        if sum(recent_r) / len(recent_r) >= sum(older_r) / len(older_r):
            out.long_term_trends.append("Session confidence (self-rating) — improving or stable")
        else:
            out.long_term_trends.append("Session confidence (self-rating) — room to rebuild momentum")

    if inst_name == "Guitar":
        if trends.get("deltas", {}).get("technique", 0) >= 3:
            out.long_term_trends.append("Chord transitions — getting smoother")
        elif skill_m.get("transitions", 0):
            out.long_term_trends.append("Chord transitions — still a priority")
    if (trends.get("recent") or {}).get("weakest_category") == "tone":
        out.long_term_trends.append("Tone consistency — needs work")
    elif trends.get("deltas", {}).get("tone", 0) >= 4:
        out.long_term_trends.append("Tone consistency — improving")

    if not logs:
        out.data_notes.append("Insights lean on recording analysis — add practice log entries for richer patterns.")
    if not analysis_history and not session_analysis:
        out.data_notes.append(
            "Run **Upload Analysis** on a take to connect timing, pitch, and tone feedback here."
        )
    if not mission_stats.get("has_data"):
        out.data_notes.append(
            "Use **Improvisation Intelligence → Metrics & AI** to score mission criteria and build metric trends."
        )
    elif logs or analysis_history:
        out.data_notes.append(
            "Insights combine written logs and unified AI performance history "
            "(Upload Analysis, Metrics & AI, multitrack, and more)."
        )

    return out


def insights_to_markdown(insights: PracticeLogInsights) -> str:
    """Plain markdown fallback."""
    parts = [f"### {insights.headline}\n" if insights.headline else ""]
    sections = (
        ("Progress Summary", insights.progress_summary),
        ("Patterns Detected", insights.patterns_detected),
        ("Weak Areas", insights.weak_areas),
        ("Recommended Next Practice", insights.recommended_practice),
        ("Suggested Songs / Exercises", insights.suggested_songs),
        ("Long-Term Trend", insights.long_term_trends),
    )
    for title, items in sections:
        if items:
            parts.append(f"\n## {title}\n")
            for item in items:
                parts.append(f"- {item}\n")
    return "".join(parts)


def maybe_enhance_insights_with_openai(
    insights: PracticeLogInsights,
    *,
    api_key: str,
    logs: list[dict[str, Any]],
    analysis_history: list[dict[str, Any]],
) -> PracticeLogInsights:
    """Optional natural-language polish when an OpenAI key is set."""
    if not api_key or not api_key.strip():
        return insights
    try:
        from openai import OpenAI
    except ImportError:
        return insights

    brief_logs = logs[-12:]
    brief_analysis = analysis_history[-5:]
    prompt = {
        "role": "user",
        "content": (
            "You are a warm, expert private music teacher. Given structured practice data, "
            "rewrite the coach sections in friendly second-person prose. Keep all six section headings "
            "and use bullet lists. Do not invent songs not in the data.\n\n"
            f"Logs sample: {json.dumps(brief_logs, default=str)[:4000]}\n"
            f"Analysis sample: {json.dumps(brief_analysis, default=str)[:3000]}\n"
            f"Draft insights: {insights_to_markdown(insights)}"
        ),
    }
    try:
        client = OpenAI(api_key=api_key.strip())
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You write concise, encouraging music practice coaching copy.",
                },
                prompt,
            ],
            max_tokens=1200,
            temperature=0.6,
        )
        text = (resp.choices[0].message.content or "").strip()
        if not text:
            return insights
        parsed = _parse_openai_sections(text)
        if parsed:
            insights.headline = parsed.get("headline", insights.headline)
            for key in (
                "progress_summary",
                "patterns_detected",
                "weak_areas",
                "recommended_practice",
                "suggested_songs",
                "long_term_trends",
            ):
                if parsed.get(key):
                    setattr(insights, key, parsed[key])
    except Exception:
        pass
    return insights


def _parse_openai_sections(text: str) -> dict[str, Any]:
    """Best-effort parse of markdown sections from OpenAI output."""
    section_map = {
        "progress summary": "progress_summary",
        "patterns detected": "patterns_detected",
        "weak areas": "weak_areas",
        "recommended next practice": "recommended_practice",
        "suggested songs": "suggested_songs",
        "suggested songs / exercises": "suggested_songs",
        "long-term trend": "long_term_trends",
        "long term trend": "long_term_trends",
    }
    out: dict[str, Any] = {"headline": ""}
    current = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            title = re.sub(r"^#+\s*", "", stripped).lower()
            current = section_map.get(title)
            if not out["headline"] and current is None:
                out["headline"] = stripped.lstrip("#").strip()
            continue
        if stripped.startswith("- ") and current:
            out.setdefault(current, []).append(stripped[2:].strip())
        elif stripped and current is None and not out["headline"]:
            out["headline"] = stripped
    return out


def render_practice_log_insights_ui(st_module: Any, insights: PracticeLogInsights) -> None:
    """Render the six coach sections on the Practice Log page."""
    if insights.headline:
        st_module.markdown(
            '<div class="ui-card soft"><div class="ui-card-title">🧠 Your practice coach</div>'
            f"<p>{insights.headline}</p></div>",
            unsafe_allow_html=True,
        )
    sections = (
        ("📈 Progress Summary", insights.progress_summary),
        ("🔍 Patterns Detected", insights.patterns_detected),
        ("⚠️ Weak Areas", insights.weak_areas),
        ("🎯 Recommended Next Practice", insights.recommended_practice),
        ("🎵 Suggested Songs / Exercises", insights.suggested_songs),
        ("📊 Long-Term Trend", insights.long_term_trends),
    )
    for title, items in sections:
        if not items:
            continue
        with st_module.expander(
            title,
            expanded=title.startswith("📈") or title.startswith("🎯"),
        ):
            for item in items:
                st_module.markdown(f"- {item}")
    if insights.data_notes:
        st_module.caption(" · ".join(insights.data_notes))
