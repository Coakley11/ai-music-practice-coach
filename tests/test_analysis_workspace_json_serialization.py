"""Regression: workspace JSON after Upload analysis must stay plain-serializable.

Upload AI leaves live ``AudioFeatures`` on ``last_analysis_result``. That object may
remain in live session state, but durable Music payloads (including page snapshots
and Creative/Multitrack saves) must not carry it.
"""

from __future__ import annotations

import copy
import json
from typing import Any

import numpy as np

from analysis_session_persistence import (
    sanitize_analysis_in_page_snapshots,
    sanitize_analysis_result_for_persist,
)
from music_persistent_state import build_music_disk_state
from recording_analysis import AudioFeatures
from studio_page_persistence import capture_page_snapshot, flush_current_page_snapshot


def find_non_jsonable(obj: Any, path: str = "$") -> list[tuple[str, str, str]]:
    """Recursive diagnostic: (path, type_name, preview) for plain json.dumps failures."""
    bad: list[tuple[str, str, str]] = []

    def _walk(value: Any, cur: str) -> None:
        if value is None or isinstance(value, (bool, int, float, str)):
            return
        if isinstance(value, dict):
            for k, v in value.items():
                _walk(v, f"{cur}.{k}")
            return
        if isinstance(value, (list, tuple)):
            for i, v in enumerate(value):
                _walk(v, f"{cur}[{i}]")
            return
        try:
            json.dumps(value)
        except TypeError:
            preview = repr(value)
            if len(preview) > 120:
                preview = preview[:117] + "..."
            bad.append((cur, type(value).__name__, preview))

    _walk(obj, path)
    return bad


def assert_json_serializable(payload: Any, *, label: str = "payload") -> None:
    try:
        json.dumps(payload)
    except TypeError as exc:
        details = "\n".join(f"  {p} -> {t}: {prev}" for p, t, prev in find_non_jsonable(payload)[:25])
        raise AssertionError(f"{label} is not JSON serializable: {exc}\n{details}") from exc


def _blank_features() -> AudioFeatures:
    return AudioFeatures(
        duration=2.0,
        sr=22050,
        tempo=90.0,
        beat_times=np.linspace(0, 2, 8),
        beat_interval_cv=0.05,
        tempo_drift_pct=1.0,
        onset_times=np.linspace(0, 2, 12),
        onset_strength_mean=1.0,
        onset_density=1.2,
        groove_tightness=0.5,
        pitch_median_hz=440.0,
        pitch_note="A4",
        pitch_cents_std=18.0,
        pitch_sharp_bias=1.0,
        voiced_ratio=0.8,
        rms=np.ones(16) * 0.1,
        dyn_range=0.04,
        dyn_flatness=0.4,
        spectral_centroid_mean=1600.0,
        zcr_mean=0.03,
        energy_curve=np.linspace(0.05, 0.1, 8),
        waveform_peaks=[0.4] * 8,
        waveform_times=[i * 0.1 for i in range(8)],
        highlight_regions=[],
        raw={},
    )


def _post_upload_analysis_session() -> dict[str, Any]:
    focuses = {
        "Flute": ["Tone", "Phrasing", "Articulation"],
        "Piano": ["Comping", "Voicing"],
    }
    practice_focuses = ["Tone", "Phrasing", "Articulation"]
    criteria_ids = ["phrase_structure", "scale_connection", "timing_groove", "articulation"]
    criteria_labels = ["Phrase structure", "Scale/mode usage", "Timing/groove", "Articulation"]
    snapshot = {
        "instruments": ["Flute", "Piano"],
        "instrument_focuses": focuses,
        "practice_focuses": practice_focuses,
        "practice_focus": "Tone",
        "evaluating_criteria_ids": criteria_ids,
        "evaluating_criteria_labels": criteria_labels,
        "sections": {},
        "target_chords": [],
        "song_source_type": "exercise",
        "mission_parameters": {"mode": "upload"},
    }
    result = {
        "ok": True,
        "features": _blank_features(),
        "scores": {
            "timing": np.int64(70),
            "pitch": np.float64(65.5),
            "technique": 60,
            "groove": 72,
            "musicality": 68,
            "confidence": 70,
            "tone": 66,
        },
        "categories": {
            "timing": {"title": "Timing", "findings": ["ok"], "tips": ["tip"], "score": 70},
        },
        "practice_plan": ["drill"],
        "coach_summary": "Summary",
        "instruments": ["Flute"],
        "instrument_focuses": focuses,
        "practice_focuses": practice_focuses,
        "practice_focus": "Tone",
        "evaluating_criteria_ids": criteria_ids,
        "evaluating_criteria_labels": criteria_labels,
        "analysis_context_snapshot": snapshot,
        "musical_metrics": {"scale_adherence": np.float64(70.0)},
        "mission_results": [
            {
                "id": "phrase_structure",
                "label": "Phrase structure",
                "score": 70,
                "went_well": "usable",
                "improve_to": "space",
                "tips": ["tip"],
            }
        ],
    }
    return {
        "studio_page": "analysis",
        "creative_lab_analysis_mode": "Creative Lab",
        "last_analysis_result": result,
        "last_analysis_source_label": "take.wav",
        "analysis_practice_focuses": practice_focuses,
        "analysis_instrument_focuses": focuses,
        "analysis_eval_instruments": ["Flute", "Piano"],
        "analysis_effective_metric_ids": criteria_ids,
        "analysis_context_snapshot": snapshot,
        "last_analysis_context_snapshot": snapshot,
        "instrument": "Flute",
    }


class _FakeSt:
    def __init__(self, session_state: dict) -> None:
        self.session_state = session_state


def test_sanitize_strips_audiofeatures_and_numpy_scalars() -> None:
    raw = {
        "ok": True,
        "features": _blank_features(),
        "scores": {"timing": np.int64(71), "pitch": np.float64(66.25)},
        "instrument_focuses": {"Flute": ["Tone", "Phrasing"]},
    }
    clean = sanitize_analysis_result_for_persist(raw)
    assert isinstance(clean["features"], dict)
    assert "waveform_peaks" in clean["features"]
    assert type(clean["scores"]["timing"]) is int
    assert type(clean["scores"]["pitch"]) is float
    assert clean["instrument_focuses"]["Flute"] == ["Tone", "Phrasing"]
    assert_json_serializable(clean, label="sanitized analysis result")


def test_dirty_analysis_snapshot_sanitized_for_disk() -> None:
    """Pre-existing dirty snapshot (AudioFeatures) must be cleaned at build time."""
    ss = _post_upload_analysis_session()
    dirty = {
        "analysis": {
            "last_analysis_result": copy.deepcopy(ss["last_analysis_result"]),
            "analysis_mode": "Single recording",
        }
    }
    assert find_non_jsonable(dirty), "fixture must start non-serializable"
    cleaned = sanitize_analysis_in_page_snapshots(dirty)
    assert_json_serializable(cleaned, label="sanitized snapshots")
    feat = cleaned["analysis"]["last_analysis_result"]["features"]
    assert isinstance(feat, dict)
    assert "waveform_peaks" in feat


def test_capture_page_snapshot_sanitizes_analysis_result() -> None:
    ss = _post_upload_analysis_session()
    # Live session still holds AudioFeatures
    assert isinstance(ss["last_analysis_result"]["features"], AudioFeatures)

    snap = capture_page_snapshot(ss, "analysis")
    assert_json_serializable(snap, label="analysis page snapshot")
    assert isinstance(ss["last_analysis_result"]["features"], AudioFeatures)
    assert isinstance(snap["last_analysis_result"]["features"], dict)
    assert snap["last_analysis_result"]["instrument_focuses"]["Flute"] == [
        "Tone",
        "Phrasing",
        "Articulation",
    ]


def test_build_music_disk_state_after_upload_analysis_is_json_safe() -> None:
    ss = _post_upload_analysis_session()
    # Simulate leaving Analysis with a dirty snapshot already stored (pre-fix sessions).
    ss["_studio_page_snapshots"] = {
        "analysis": {
            "last_analysis_result": copy.deepcopy(ss["last_analysis_result"]),
            "analysis_mode": "Single recording",
        }
    }
    payload = build_music_disk_state(_FakeSt(ss))
    assert_json_serializable(payload, label="full music disk state")

    # Section-by-section isolation (schema may grow; all top-level must dump).
    assert isinstance(payload, dict)
    for key, section in payload.items():
        assert_json_serializable(section, label=f"section {key}")

    session = payload.get("session") or {}
    snap = (session.get("_studio_page_snapshots") or {}).get("analysis") or {}
    feat = (snap.get("last_analysis_result") or {}).get("features")
    assert isinstance(feat, dict)
    focuses = (session.get("last_analysis_result") or {}).get("instrument_focuses")
    assert focuses == {
        "Flute": ["Tone", "Phrasing", "Articulation"],
        "Piano": ["Comping", "Voicing"],
    }
    # Live session still has runtime features for UI.
    assert isinstance(ss["last_analysis_result"]["features"], AudioFeatures)


def test_multitrack_flush_and_creative_selector_paths_after_analysis() -> None:
    """Both unrelated save triggers must succeed after Upload analysis populates state."""
    ss = _post_upload_analysis_session()
    flush_current_page_snapshot(ss)  # captures sanitized analysis snapshot

    # Multitrack workspace flush path: open Multitrack, flush, build.
    ss["studio_page"] = "multitrack"
    ss["mt_tracks"] = {}
    flush_current_page_snapshot(ss)
    mt_payload = build_music_disk_state(_FakeSt(ss))
    assert_json_serializable(mt_payload, label="after Multitrack flush")

    # Creative selector cloud-save path: change selector-related state, build.
    ss["studio_page"] = "creative"
    ss["creative_lab_analysis_mode"] = "Song Analysis"
    flush_current_page_snapshot(ss)
    creative_payload = build_music_disk_state(_FakeSt(ss))
    assert_json_serializable(creative_payload, label="after Creative selector change")

    # Multifocus structure must remain lists/dicts (not stringified).
    for payload in (mt_payload, creative_payload):
        result = (payload.get("session") or {}).get("last_analysis_result") or {}
        assert result["instrument_focuses"]["Flute"] == ["Tone", "Phrasing", "Articulation"]
        assert result["practice_focuses"] == ["Tone", "Phrasing", "Articulation"]
        assert isinstance(result["practice_focuses"], list)


def test_multifocus_structure_survives_snapshot_workspace_reload() -> None:
    ss = _post_upload_analysis_session()
    flush_current_page_snapshot(ss)
    payload = build_music_disk_state(_FakeSt(ss))
    blob = json.loads(json.dumps(payload))  # plain dumps — no default=str
    focuses = blob["session"]["last_analysis_result"]["instrument_focuses"]
    assert focuses == {
        "Flute": ["Tone", "Phrasing", "Articulation"],
        "Piano": ["Comping", "Voicing"],
    }
    analysis_snap = blob["session"]["_studio_page_snapshots"]["analysis"]["last_analysis_result"]
    assert analysis_snap["instrument_focuses"]["Piano"] == ["Comping", "Voicing"]
