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

ANALYSIS_HISTORY_FILE = Path("analysis_history.json")

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
    if not ANALYSIS_HISTORY_FILE.exists():
        return []
    try:
        data = json.loads(ANALYSIS_HISTORY_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_analysis_history(entries: list[dict[str, Any]]) -> None:
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
    }


def append_analysis_snapshot(
    result: dict[str, Any],
    *,
    ctx: dict[str, Any] | None = None,
) -> None:
    snap = analysis_snapshot_from_result(result, ctx=ctx)
    if not snap:
        return
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


def _aggregate_log_stats(logs: list[dict[str, Any]]) -> dict[str, Any]:
    if not logs:
        return {}
    songs = Counter(str(e.get("song") or "").strip() for e in logs if e.get("song"))
    instruments = Counter(str(e.get("instrument") or "").strip() for e in logs if e.get("instrument"))
    focuses = Counter(str(e.get("focus") or "").strip() for e in logs if e.get("focus"))
    genres = Counter(str(e.get("genre") or "").strip() for e in logs if e.get("genre"))
    levels = Counter(str(e.get("level") or "").strip() for e in logs if e.get("level"))
    ratings: list[tuple[date | None, float]] = []
    skill_mentions: Counter[str] = Counter()
    dated: list[tuple[date, dict[str, Any]]] = []

    for entry in logs:
        d = _parse_log_date(entry)
        if d:
            dated.append((d, entry))
        try:
            ratings.append((d, float(entry.get("rating", 0))))
        except (TypeError, ValueError):
            pass
        skill_mentions.update(_skill_mentions_from_text(str(entry.get("practice") or "")))

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
        "recent_songs": Counter(str(e.get("song") or "") for e in last_14 if e.get("song")),
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
    session_analysis: dict[str, Any] | None = None,
    all_song_records: list[dict[str, Any]] | None = None,
    session_minutes: int = 25,
) -> PracticeLogInsights:
    """Build coach-style insights from logs and recording analysis."""
    analysis_history = list(analysis_history or [])
    if session_analysis and session_analysis.get("ok"):
        snap = analysis_snapshot_from_result(session_analysis)
        if snap and not any(
            h.get("recorded_at") == snap.get("recorded_at") for h in analysis_history
        ):
            analysis_history = analysis_history + [snap]

    out = PracticeLogInsights()
    stats = _aggregate_log_stats(logs)
    trends = _score_trends(analysis_history)

    if not logs and not analysis_history:
        out.headline = "Start logging sessions and upload a take on **Upload Analysis** — your coach profile will grow from there."
        out.data_notes.append("No practice logs or saved recording analyses yet.")
        out.recommended_practice.append(
            "20 min: 5 min tuner/long tones · 5 min metronome on one chord · "
            "10 min one song section at slow tempo."
        )
        return out

    # --- Headline ---
    if stats.get("total"):
        top_song = stats["songs"].most_common(1)[0][0] if stats["songs"] else ""
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

    if trends.get("count"):
        out.patterns_detected.append(
            f"**{trends['count']}** AI coach analysis snapshot(s) on file."
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

    recent_snap = trends.get("recent") or {}
    if recent_snap.get("next_focus"):
        out.recommended_practice.append(f"- From your last recording: {recent_snap['next_focus']}")
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
