"""Phase B — supportive music-coach copy for the Practice Log page (not Command Center)."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from practice_log_insights import (
    PracticeLogInsights,
    _aggregate_log_stats,
    _parse_log_date,
    _score_trends,
    generate_practice_log_insights,
)


@dataclass
class PracticeLogCoachView:
    """Simple coach layout for the Practice Log page."""

    practice_summary: str = ""
    after_save_summary: str = ""
    improvement_notes: list[str] = field(default_factory=list)
    recommended_next_session: list[str] = field(default_factory=list)
    recording_reviews: list[str] = field(default_factory=list)
    suggested_songs: list[str] = field(default_factory=list)


def describe_practice_session(entry: dict[str, Any]) -> str:
    """One supportive sentence about a single logged session."""
    song = str(entry.get("active_song") or entry.get("song") or "your song").strip()
    try:
        mins = int(entry.get("duration_minutes") or entry.get("minutes") or 0)
    except (TypeError, ValueError):
        mins = 0
    minutes = str(mins) if mins > 0 else "a short"
    instrument = str(entry.get("instrument") or "your instrument").strip()
    focus = str(entry.get("focus_area") or entry.get("focus") or "").strip()
    mode = str(entry.get("practice_type") or entry.get("mode") or "").strip()
    sections = int(entry.get("section_count") or 0)
    section_label = str(entry.get("section_practiced") or "").strip()

    line = f"You practiced **{song}** for **{minutes}** minutes on **{instrument}**"
    focus_bits: list[str] = []
    if focus and focus.lower() not in {"general", "any", ""}:
        focus_bits.append(f"**{focus}**")
    if mode and mode.lower() not in {"song practice", "song work", ""}:
        focus_bits.append(f"{mode.lower()}")
    if section_label and section_label not in {"unspecified", ""}:
        focus_bits.append(f"**{section_label}**")
    elif sections > 0:
        focus_bits.append(f"about **{sections}** section(s)")
    if focus_bits:
        line += ", focused on " + ", ".join(focus_bits)
    line += "."

    notes = str(entry.get("notes") or entry.get("practice") or "").strip()
    if notes:
        excerpt = notes if len(notes) <= 200 else notes[:197] + "…"
        line += f' You wrote: “{excerpt}”'
    went_well = str(entry.get("what_went_well") or "").strip()
    if went_well:
        excerpt = went_well if len(went_well) <= 120 else went_well[:117] + "…"
        line += f" What went well: {excerpt}"
    return line


def _minutes_by_period(dated: list[tuple[date, dict[str, Any]]], *, days: int) -> int:
    today = date.today()
    start = today - timedelta(days=days - 1)
    return sum(int(e.get("minutes") or 0) for d, e in dated if start <= d <= today)


def _days_since_instrument(
    dated: list[tuple[date, dict[str, Any]]], instrument: str
) -> int | None:
    today = date.today()
    last: date | None = None
    for d, e in dated:
        if str(e.get("instrument") or "").strip() == instrument:
            if last is None or d > last:
                last = d
    if last is None:
        return None
    return (today - last).days


def _build_improvement_notes(
    logs: list[dict[str, Any]],
    stats: dict[str, Any],
    *,
    analysis_history: list[dict[str, Any]],
) -> list[str]:
    notes: list[str] = []
    if not stats:
        notes.append("Log a few sessions — your coach will spot patterns after two or three entries.")
        return notes

    today = date.today()
    dated: list[tuple[date, dict[str, Any]]] = list(stats.get("dated") or [])
    songs: Counter[str] = stats.get("songs") or Counter()
    instruments: Counter[str] = stats.get("instruments") or Counter()

    if songs:
        top_song, count = songs.most_common(1)[0]
        recent_on_song = stats.get("recent_songs", Counter()).get(top_song, 0)
        if count >= 3:
            notes.append(
                f"You have practiced **{top_song}** {count} times in your log"
                + (f" ({recent_on_song} time(s) in the last two weeks)." if recent_on_song else ".")
            )
        if count >= 4 and (stats.get("avg_rating") or 0) >= 6.5:
            notes.append(
                f"**{top_song}** is moving from learning toward performance-ready — "
                "try a slow full run-through next."
            )

    last_14 = stats.get("last_14_count", 0)
    if last_14 >= 3:
        notes.append(f"You have been consistent this week — **{last_14}** session(s) in the last 14 days.")
    elif last_14 == 0 and stats.get("total", 0) > 0:
        notes.append("You have not logged a session in the last two weeks — a short warmup can restart momentum.")

    if len(dated) >= 4:
        recent_min = _minutes_by_period(dated, days=14)
        prior_start = today - timedelta(days=27)
        prior_end = today - timedelta(days=14)
        prior_min = sum(
            int(e.get("minutes") or 0)
            for d, e in dated
            if prior_start <= d < prior_end
        )
        if recent_min > prior_min + 10:
            notes.append("Your practice time is increasing compared with the previous two weeks.")
        elif prior_min > recent_min + 15 and recent_min > 0:
            notes.append("Practice time dipped recently — schedule one focused 20-minute block to stay steady.")

    for inst, _count in instruments.most_common(3):
        gap = _days_since_instrument(dated, inst)
        if gap is not None and gap >= 5 and inst:
            notes.append(f"You have not logged **{inst}** in **{gap}** days — balance your routine if you still play it.")

    trends = _score_trends(analysis_history)
    if trends.get("has_trend"):
        improving = [
            k for k, v in (trends.get("deltas") or {}).items() if v >= 5
        ]
        if improving:
            labels = ", ".join(k.replace("_", " ") for k in improving[:2])
            notes.append(f"Your recordings suggest **{labels}** is improving compared with earlier takes.")

    if not notes:
        notes.append("Keep logging after each session — small patterns become clear quickly.")
    return notes[:6]


def _build_recording_reviews(analysis_history: list[dict[str, Any]]) -> list[str]:
    if not analysis_history:
        return [
            "When you upload audio on **Upload Analysis**, your coach can compare takes and suggest what to fix next."
        ]

    by_song: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in analysis_history:
        song = str(row.get("song") or "").strip()
        if song:
            by_song[song].append(row)

    reviews: list[str] = []
    for song, takes in sorted(by_song.items(), key=lambda kv: kv[1][-1].get("date", "")):
        takes = sorted(takes, key=lambda x: str(x.get("recorded_at") or x.get("date") or ""))
        latest = takes[-1]
        kind = "multitrack" if latest.get("multitrack") else "recording"
        reviews.append(f"You uploaded a **{kind}** of **{song}** — open **Upload Analysis** to review it again.")

        if latest.get("coach_summary"):
            excerpt = str(latest["coach_summary"])[:220]
            if len(str(latest["coach_summary"])) > 220:
                excerpt += "…"
            reviews.append(f"Latest coach note: {excerpt}")

        if latest.get("next_focus"):
            reviews.append(f"Still worth working on: {latest['next_focus']}")

        if len(takes) >= 2:
            prev, cur = takes[-2], takes[-1]
            prev_scores = prev.get("scores") or {}
            cur_scores = cur.get("scores") or {}
            improved: list[str] = []
            slipped: list[str] = []
            for key in set(prev_scores) | set(cur_scores):
                try:
                    delta = float(cur_scores.get(key, 0)) - float(prev_scores.get(key, 0))
                except (TypeError, ValueError):
                    continue
                label = key.replace("_", " ")
                if delta >= 8:
                    improved.append(label)
                elif delta <= -8:
                    slipped.append(label)
            if improved:
                reviews.append(
                    f"Compared with your earlier **{song}** take, **{', '.join(improved[:2])}** improved."
                )
            if slipped:
                reviews.append(
                    f"Compared with your earlier take, keep steady work on **{', '.join(slipped[:2])}**."
                )
            if not improved and not slipped and latest.get("most_improved"):
                reviews.append(f"Since your last upload: {latest['most_improved']}")

        if len(reviews) >= 8:
            break

    return reviews[:6]


def _verified_override_titles() -> set[str]:
    try:
        from song_catalog.user_overrides import load_overrides_document

        doc = load_overrides_document()
        out: set[str] = set()
        for entry in (doc.get("overrides") or {}).values():
            if isinstance(entry, dict) and entry.get("title"):
                out.add(str(entry["title"]).strip().lower())
        return out
    except Exception:
        return set()


def _simplify_recommendations(
    insights: PracticeLogInsights,
    *,
    stats: dict[str, Any],
    verified_titles: set[str],
) -> list[str]:
    recs: list[str] = []
    top_song = ""
    if stats.get("songs"):
        top_song = stats["songs"].most_common(1)[0][0]

    if top_song:
        recs.append(f"Continue **{top_song}** next session — pick one weak section and loop it slowly.")
        if top_song.lower() in verified_titles:
            recs.append(
                f"You edited chords for **{top_song}** — practice with your **verified chart** on Song Selection."
            )
        focuses = stats.get("focuses") or Counter()
        if focuses.get("Chord Transitions", 0) or "transition" in " ".join(insights.weak_areas).lower():
            recs.append(f"Spend **10 minutes** on the chorus transition in **{top_song}**, then try a full run-through.")
        elif focuses.get("Scales", 0) >= 2:
            recs.append("Balance scale work with one musical section at performance tempo.")
        else:
            recs.append("Try one full run-through at a comfortable tempo before adding new material.")

    for item in insights.recommended_practice[:3]:
        plain = item.lstrip("- ").strip()
        if plain and plain not in recs:
            recs.append(plain)

    recent = insights.progress_summary[:1]
    for line in recent:
        if "next" in line.lower() or "focus" in line.lower():
            recs.append(line)
            break

    if not recs:
        recs.append("Log your next session, then spend 15 minutes on one section you almost know by heart.")
    return recs[:5]


def _simplify_song_suggestions(insights: PracticeLogInsights) -> list[str]:
    out: list[str] = []
    for item in insights.suggested_songs[:4]:
        out.append(item.lstrip("- ").strip())
    if not out:
        out.append("Pick a song in your usual genre on **Song Selection** — one step harder than your comfort zone.")
    return out


def build_practice_log_coach_view(
    logs: list[dict[str, Any]],
    *,
    analysis_history: list[dict[str, Any]] | None = None,
    all_song_records: list[dict[str, Any]] | None = None,
    session_minutes: int = 30,
    highlight_entry: dict[str, Any] | None = None,
) -> PracticeLogCoachView:
    """Build the Phase B coach view from logs and recording history."""
    analysis_history = list(analysis_history or [])
    stats = _aggregate_log_stats(logs)
    insights = generate_practice_log_insights(
        logs,
        analysis_history=analysis_history,
        all_song_records=all_song_records,
        session_minutes=session_minutes,
        instrument=str(
            (highlight_entry or {}).get("instrument")
            or (logs[-1].get("instrument") if logs else "")
            or ""
        ).strip(),
        focus=str(
            (highlight_entry or {}).get("practice_focus")
            or (highlight_entry or {}).get("focus")
            or ""
        ).strip(),
    )
    verified = _verified_override_titles()

    view = PracticeLogCoachView()

    if highlight_entry:
        view.after_save_summary = describe_practice_session(highlight_entry)

    if logs:
        latest = highlight_entry or max(
            logs,
            key=lambda e: (_parse_log_date(e) or date.min, str(e.get("song") or "")),
        )
        view.practice_summary = describe_practice_session(latest)
    elif analysis_history:
        snap = analysis_history[-1]
        song = snap.get("song") or "your last take"
        view.practice_summary = (
            f"Your latest activity is a recording review on **{song}** — "
            "log a written session too so your coach can connect both."
        )
    else:
        view.practice_summary = (
            "Log today's practice below — your coach will summarize the session and suggest what to do next."
        )

    view.improvement_notes = _build_improvement_notes(logs, stats, analysis_history=analysis_history)
    view.recording_reviews = _build_recording_reviews(analysis_history)
    view.recommended_next_session = _simplify_recommendations(
        insights, stats=stats, verified_titles=verified
    )
    view.suggested_songs = _simplify_song_suggestions(insights)

    return view


def maybe_enhance_coach_view_with_openai(
    view: PracticeLogCoachView,
    *,
    api_key: str,
    logs: list[dict[str, Any]],
    analysis_history: list[dict[str, Any]],
) -> PracticeLogCoachView:
    """Optional polish — keeps section structure, does not invent songs."""
    if not api_key or not api_key.strip():
        return view
    try:
        from openai import OpenAI
    except ImportError:
        return view

    payload = {
        "practice_summary": view.practice_summary,
        "improvement_notes": view.improvement_notes,
        "recommended_next_session": view.recommended_next_session,
        "recording_reviews": view.recording_reviews,
        "suggested_songs": view.suggested_songs,
    }
    prompt = (
        "You are a warm private music teacher. Rewrite the JSON fields in friendly second-person prose. "
        "Keep the same lists and meaning. Be specific and encouraging — never generic 'good job'. "
        "Do not invent songs not in the data. Return valid JSON with the same keys.\n\n"
        f"Logs sample: {json.dumps(logs[-8:], default=str)[:3000]}\n"
        f"Analysis sample: {json.dumps(analysis_history[-4:], default=str)[:2000]}\n"
        f"Draft: {json.dumps(payload, default=str)}"
    )
    try:
        client = OpenAI(api_key=api_key.strip())
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You return only JSON matching the draft keys. Concise coaching tone.",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=900,
            temperature=0.55,
        )
        text = (resp.choices[0].message.content or "").strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1]
            if text.startswith("json"):
                text = text[4:]
        data = json.loads(text)
        if isinstance(data, dict):
            view.practice_summary = str(data.get("practice_summary") or view.practice_summary)
            for key in (
                "improvement_notes",
                "recommended_next_session",
                "recording_reviews",
                "suggested_songs",
            ):
                val = data.get(key)
                if isinstance(val, list) and val:
                    setattr(view, key, [str(x) for x in val[:6]])
    except Exception:
        pass
    return view


def render_practice_log_coach_ui(st_module: Any, view: PracticeLogCoachView) -> None:
    """Render Phase B coach sections (simple, not a heavy dashboard)."""
    if view.after_save_summary:
        st_module.markdown(
            '<div class="ui-card soft" style="margin-bottom:.85rem;">'
            '<div class="ui-card-title">✅ Practice saved</div>'
            f"<p>{view.after_save_summary}</p></div>",
            unsafe_allow_html=True,
        )

    if view.practice_summary:
        st_module.markdown(
            '<div class="ui-card soft"><div class="ui-card-title">📝 Practice summary</div>'
            f"<p>{view.practice_summary}</p></div>",
            unsafe_allow_html=True,
        )

    if view.improvement_notes:
        st_module.markdown(
            '<div class="ui-card soft"><div class="ui-card-title">📈 Improvement notes</div></div>',
            unsafe_allow_html=True,
        )
        for line in view.improvement_notes:
            st_module.markdown(f"- {line}")

    if view.recommended_next_session:
        st_module.markdown(
            '<div class="ui-card soft"><div class="ui-card-title">🎯 Recommended next session</div></div>',
            unsafe_allow_html=True,
        )
        for line in view.recommended_next_session:
            st_module.markdown(f"- {line}")

    if view.recording_reviews:
        st_module.markdown(
            '<div class="ui-card soft"><div class="ui-card-title">🎙️ Uploads & recording review</div></div>',
            unsafe_allow_html=True,
        )
        for line in view.recording_reviews:
            st_module.markdown(f"- {line}")
        if st_module.button(
            "Open Upload Analysis",
            key="coach_goto_upload_analysis",
            use_container_width=False,
        ):
            from studio_nav_history import navigate_studio_page

            navigate_studio_page(st_module.session_state, "analysis")
            st_module.rerun()

    if view.suggested_songs:
        st_module.markdown(
            '<div class="ui-card soft"><div class="ui-card-title">🎵 Suggested songs</div></div>',
            unsafe_allow_html=True,
        )
        for line in view.suggested_songs:
            st_module.markdown(f"- {line}")
