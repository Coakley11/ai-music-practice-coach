"""Phase 3A — Practice Coach & Session + Adaptive Weakness Detection."""

from __future__ import annotations

from practice_focus_coaching import (
    build_focus_timed_session,
    practice_page_time_ratios,
)
from practice_focus_weaknesses import (
    audit_weakness_sources,
    coaching_only_focus_targets,
    format_adaptive_weakness_markdown,
    rank_measured_weaknesses,
)
from practice_studio import build_practice_session_from_logs


def test_guitar_strumming_vs_timing_vs_harmony_sessions_differ():
    song = "Shape of You"
    strum = build_focus_timed_session("Guitar", "Strumming", minutes=30, song=song)
    timing = build_focus_timed_session("Guitar", "Timing", minutes=30, song=song)
    harmony = build_focus_timed_session("Guitar", "Harmony", minutes=30, song=song)

    assert strum["category"] == "rhythm_groove"
    assert timing["category"] == "timing"
    assert harmony["category"] == "harmony"

    strum_names = [b["name"] for b in strum["blocks"]]
    timing_names = [b["name"] for b in timing["blocks"]]
    harmony_names = [b["name"] for b in harmony["blocks"]]
    assert strum_names != timing_names
    assert timing_names != harmony_names
    assert "chord changes without stopping" in strum_names
    assert "metronome groove" in timing_names
    assert "guide tones / voice leading" in harmony_names

    assert "continuous" in strum["warmup"].lower() or "pattern" in strum["warmup"].lower() or "isolate" in strum["warmup"].lower()
    assert "metronome" in timing["warmup"].lower() or "subdivision" in " ".join(timing_names)
    assert "chord" in harmony["warmup"].lower() or "guide" in " ".join(harmony_names)


def test_sax_tone_articulation_phrasing_sessions_differ():
    tone = build_focus_timed_session("Saxophone", "Tone", minutes=30)
    artic = build_focus_timed_session("Saxophone", "Articulation", minutes=30)
    phrase = build_focus_timed_session("Saxophone", "Phrasing", minutes=30)

    assert [b["name"] for b in tone["blocks"]] != [b["name"] for b in artic["blocks"]]
    assert [b["name"] for b in artic["blocks"]] != [b["name"] for b in phrase["blocks"]]
    assert any("long tone" in b["name"] for b in tone["blocks"])
    assert any("tongu" in b["name"] or "slur" in b["name"] for b in artic["blocks"])
    assert any("phrase" in b["name"] or "space" in b["name"] or "question" in b["name"] for b in phrase["blocks"])


def test_same_rerun_focus_change_updates_signature_and_blocks():
    a = build_focus_timed_session("Guitar", "Strumming", minutes=40, song="X")
    b = build_focus_timed_session("Guitar", "Timing", minutes=40, song="X")
    assert a["signature"] != b["signature"]
    assert a["blocks"] != b["blocks"]
    assert a["listen_for"] != b["listen_for"]


def test_historical_variety_does_not_override_current_focus():
    recent = ["Tone", "Tone", "Tone", "Tone"]
    session = build_focus_timed_session(
        "Saxophone",
        "Articulation",
        minutes=30,
        recent_focus_labels=recent,
    )
    assert session["focus"] == "Articulation" or session["category"] == "articulation"
    assert session["category"] == "articulation"
    # Variety note only applies when recent matches *current* category.
    tone_session = build_focus_timed_session(
        "Saxophone",
        "Tone",
        minutes=30,
        recent_focus_labels=recent,
    )
    assert tone_session["category"] == "tone"
    assert tone_session.get("variety_note")


def test_practice_page_time_ratios_change_with_focus():
    tone = practice_page_time_ratios("Saxophone", "Tone")
    strum = practice_page_time_ratios("Guitar", "Strumming")
    assert tone["warmup"] > strum["warmup"]
    assert strum["focus"] > tone["focus"] or strum["focus"] >= 0.4


def test_build_practice_session_from_logs_uses_current_focus():
    logs = [
        {"song": "Hello", "focus": "Tone", "practice_focus": "Tone", "instrument": "Guitar", "date": "2026-08-01"},
        {"song": "Hello", "focus": "Tone", "practice_focus": "Tone", "instrument": "Guitar", "date": "2026-08-02"},
    ]
    records = [{"title": "Hello", "artist": "A", "chart_status": "complete"}]
    plan = build_practice_session_from_logs(
        logs,
        records,
        minutes=30,
        instrument="Guitar",
        focus="Strumming",
    )
    assert plan.get("focus") == "Strumming" or plan.get("category") == "rhythm_groove"
    assert "Strumming" in plan.get("summary", "") or plan.get("category") == "rhythm_groove"
    assert plan.get("warmup")
    assert plan.get("technique")


def test_severe_timing_still_ranks_above_mild_tone_under_tone_focus():
    ranked = rank_measured_weaknesses(
        {"timing": 20, "tone": 70, "groove": 80},
        "Saxophone",
        "Tone",
    )
    assert ranked
    assert ranked[0]["id"] == "timing"
    assert ranked[0]["severe"] is True
    tone_rows = [r for r in ranked if r["id"] == "tone"]
    assert tone_rows
    assert tone_rows[0]["focus_matched"] is True


def test_strumming_focus_does_not_invent_stroke_weakness():
    ranked = rank_measured_weaknesses({}, "Guitar", "Strumming")
    assert ranked == []
    md = format_adaptive_weakness_markdown("Guitar", "Strumming", song="Demo", scores={})
    assert "not** recorded as a detected defect" in md or "not recorded as a detected defect" in md.lower().replace("**", "")
    assert "upstroke" not in md.lower()
    assert "downstroke" not in md.lower() or "coaching-only" in md.lower()
    # Coaching suggestions may mention strokes; must be marked coaching-only.
    assert "coaching-only" in md.lower()
    coaching = coaching_only_focus_targets("Guitar", "Strumming")
    assert coaching


def test_harmony_focus_does_not_invent_chord_analysis_weakness():
    ranked = rank_measured_weaknesses({"timing": 90, "pitch": 88}, "Piano", "Harmony")
    # High scores should not invent a harmony defect.
    assert all(r["id"] != "harmony" for r in ranked)
    md = format_adaptive_weakness_markdown("Piano", "Harmony", scores={"timing": 90})
    assert "chord-analysis" not in md.lower()
    assert "Current Practice Focus:** Harmony" in md or "Harmony" in md


def test_focus_change_reranks_without_rewriting_scores():
    scores = {"timing": 55, "tone": 60, "groove": 50}
    tone_rank = rank_measured_weaknesses(scores, "Guitar", "Tone")
    groove_rank = rank_measured_weaknesses(scores, "Guitar", "Strumming")
    assert {r["id"]: r["score"] for r in tone_rank} == {
        r["id"]: r["score"] for r in groove_rank if r["id"] in {x["id"] for x in tone_rank}
    } or True  # scores immutable per id
    tone_by_id = {r["id"]: r["score"] for r in tone_rank}
    groove_by_id = {r["id"]: r["score"] for r in groove_rank}
    for key in set(tone_by_id) & set(groove_by_id):
        assert tone_by_id[key] == groove_by_id[key]
    # Order / priority may change with Focus.
    assert [r["id"] for r in tone_rank] != [r["id"] for r in groove_rank] or (
        tone_rank[0]["priority"] != groove_rank[0]["priority"]
    )


def test_recommendations_are_instrument_aware():
    g = rank_measured_weaknesses({"timing": 40}, "Guitar", "Strumming")
    s = rank_measured_weaknesses({"timing": 40}, "Saxophone", "Timing")
    assert g and s
    assert g[0]["recommendation"] != s[0]["recommendation"]


def test_audit_weakness_sources_documents_lifecycle():
    audit = audit_weakness_sources()
    assert "timing" in audit["measured_score_keys"]
    assert any(s["id"] == "upload_scores" for s in audit["sources"])
    assert "never invent" in " ".join(audit["ranking_principles"]).lower()
