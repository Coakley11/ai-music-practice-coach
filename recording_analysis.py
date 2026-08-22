"""AI-style recording analysis pipeline (librosa features + coach narratives).

Designed for future extension: real pitch/onset models, chord ID, BPM tracking, live mic.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from typing import Any

import numpy as np

try:
    import librosa
except ImportError:
    librosa = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Future hooks (swap implementations without changing the UI contract)
# ---------------------------------------------------------------------------

def detect_pitch_track(y: np.ndarray, sr: int) -> dict[str, Any]:
    """Placeholder for dedicated pitch/onset/BPM backends."""
    return _pyin_features(y, sr)


def detect_onsets(y: np.ndarray, sr: int) -> np.ndarray:
    if librosa is None:
        return np.array([])
    return librosa.onset.onset_detect(y=y, sr=sr, units="time")


def estimate_bpm(y: np.ndarray, sr: int) -> tuple[float | None, np.ndarray]:
    if librosa is None:
        return None, np.array([])
    tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
    tempo_f = float(np.asarray(tempo).flatten()[0])
    beat_times = librosa.frames_to_time(beats, sr=sr)
    return tempo_f, beat_times


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------


@dataclass
class AudioFeatures:
    duration: float
    sr: int
    tempo: float | None
    beat_times: np.ndarray
    beat_interval_cv: float
    tempo_drift_pct: float
    onset_times: np.ndarray
    onset_strength_mean: float
    onset_density: float
    groove_tightness: float
    pitch_median_hz: float | None
    pitch_note: str | None
    pitch_cents_std: float | None
    pitch_sharp_bias: float
    voiced_ratio: float
    rms: np.ndarray
    dyn_range: float
    dyn_flatness: float
    spectral_centroid_mean: float
    zcr_mean: float
    energy_curve: np.ndarray
    waveform_peaks: list[float]
    waveform_times: list[float]
    highlight_regions: list[dict[str, Any]] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


def _load_audio(audio_bytes: bytes, filename: str) -> tuple[np.ndarray, int, str]:
    suffix = "." + filename.split(".")[-1].lower() if "." in filename else ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name
    y, sr = librosa.load(tmp_path, sr=None, mono=True)
    return y, int(sr), tmp_path


def _intonation_stats_from_f0(f0: np.ndarray, *, min_run: int = 6) -> dict[str, Any]:
    """Compute within-note intonation stats from a pyin-like f0 track (NaNs = unvoiced)."""
    out: dict[str, Any] = {
        "pitch_median_hz": None,
        "pitch_note": None,
        "pitch_cents_std": None,
        "pitch_sharp_bias": 0.0,
        "voiced_ratio": 0.0,
        "pitch_melody_range_cents": None,
        "pitch_note_segment_count": 0,
    }
    voiced_mask = ~np.isnan(f0)
    voiced = f0[voiced_mask]
    if len(voiced) < 12:
        return out
    median_hz = float(np.median(voiced))
    global_cents = 1200 * np.log2(voiced / np.maximum(median_hz, 1e-6))
    out["pitch_median_hz"] = median_hz
    try:
        out["pitch_note"] = str(librosa.hz_to_note(median_hz)) if librosa is not None else None
    except Exception:
        out["pitch_note"] = None
    out["pitch_melody_range_cents"] = float(np.std(global_cents))
    out["voiced_ratio"] = float(len(voiced) / max(1, len(f0)))

    local_stds: list[float] = []
    local_biases: list[float] = []
    run: list[float] = []

    def _flush(segment: list[float]) -> None:
        if len(segment) < min_run:
            return
        arr = np.asarray(segment, dtype=float)
        local_med = float(np.median(arr))
        if local_med <= 0:
            return
        cents = 1200 * np.log2(arr / local_med)
        local_stds.append(float(np.std(cents)))
        local_biases.append(float(np.mean(cents)))

    for hz, is_v in zip(f0, voiced_mask):
        if is_v and not np.isnan(hz):
            run.append(float(hz))
        else:
            _flush(run)
            run = []
    _flush(run)

    out["pitch_note_segment_count"] = int(len(local_stds))
    if local_stds:
        out["pitch_cents_std"] = float(np.mean(local_stds))
        out["pitch_sharp_bias"] = float(np.mean(local_biases))
    else:
        out["pitch_cents_std"] = float(min(35.0, np.std(global_cents) * 0.15))
        out["pitch_sharp_bias"] = float(np.mean(global_cents) * 0.1)
    return out


def _pyin_features(y: np.ndarray, sr: int) -> dict[str, Any]:
    """Pitch features that measure *intonation stability*, not melodic range."""
    out: dict[str, Any] = {
        "pitch_median_hz": None,
        "pitch_note": None,
        "pitch_cents_std": None,
        "pitch_sharp_bias": 0.0,
        "voiced_ratio": 0.0,
        "pitch_melody_range_cents": None,
        "pitch_note_segment_count": 0,
    }
    try:
        f0, _, _ = librosa.pyin(
            y,
            fmin=librosa.note_to_hz("C2"),
            fmax=librosa.note_to_hz("C7"),
        )
        return _intonation_stats_from_f0(np.asarray(f0, dtype=float))
    except Exception:
        return out


def extract_audio_features(y: np.ndarray, sr: int) -> AudioFeatures:
    duration = float(len(y) / max(1, sr))
    tempo, beat_times = estimate_bpm(y, sr)
    beat_times = np.asarray(beat_times, dtype=float)

    beat_ivals = np.diff(beat_times) if len(beat_times) > 2 else np.array([0.5])
    beat_interval_cv = float(np.std(beat_ivals) / max(np.mean(beat_ivals), 1e-6))

    half = max(1, len(beat_times) // 2)
    tempo_drift_pct = 0.0
    if len(beat_times) > 4:
        first_iv = np.mean(np.diff(beat_times[:half]))
        second_iv = np.mean(np.diff(beat_times[half:]))
        if first_iv > 0:
            tempo_drift_pct = float((first_iv - second_iv) / first_iv * 100)

    onset_times = detect_onsets(y, sr)
    onset_density = float(len(onset_times) / max(duration, 0.1))

    try:
        oenv = librosa.onset.onset_strength(y=y, sr=sr)
        onset_strength_mean = float(np.mean(oenv))
    except Exception:
        onset_strength_mean = 0.0

    groove_tightness = 0.5
    if len(beat_times) > 2 and len(onset_times) > 2:
        # How often onsets land near beats (within 80 ms)
        near = 0
        for ot in onset_times:
            if np.min(np.abs(beat_times - ot)) < 0.08:
                near += 1
        groove_tightness = float(near / max(len(onset_times), 1))

    pitch = detect_pitch_track(y, sr)
    rms = librosa.feature.rms(y=y)[0]
    dyn_range = float(np.percentile(rms, 90) - np.percentile(rms, 10))
    dyn_flatness = float(1.0 - min(1.0, dyn_range / 0.08))

    try:
        cent = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
        spectral_centroid_mean = float(np.mean(cent))
    except Exception:
        spectral_centroid_mean = 0.0

    zcr = librosa.feature.zero_crossing_rate(y)[0]
    zcr_mean = float(np.mean(zcr))

    n_peaks = 320
    hop = max(1, len(y) // n_peaks)
    peaks = [float(np.max(np.abs(y[i : i + hop]))) for i in range(0, len(y), hop)][:n_peaks]
    times = [float(i / sr) for i in range(0, len(y), hop)][:n_peaks]
    max_peak = max(peaks) if peaks else 1.0
    waveform_peaks = [p / max_peak for p in peaks]
    energy_curve = rms[: min(len(rms), 64)]

    regions = _detect_highlight_regions(
        y,
        sr,
        beat_times,
        onset_times,
        rms,
        pitch.get("pitch_cents_std"),
    )

    return AudioFeatures(
        duration=duration,
        sr=sr,
        tempo=tempo,
        beat_times=beat_times,
        beat_interval_cv=beat_interval_cv,
        tempo_drift_pct=tempo_drift_pct,
        onset_times=onset_times,
        onset_strength_mean=onset_strength_mean,
        onset_density=onset_density,
        groove_tightness=groove_tightness,
        pitch_median_hz=pitch.get("pitch_median_hz"),
        pitch_note=pitch.get("pitch_note"),
        pitch_cents_std=pitch.get("pitch_cents_std"),
        pitch_sharp_bias=pitch.get("pitch_sharp_bias", 0.0),
        voiced_ratio=pitch.get("voiced_ratio", 0.0),
        rms=rms,
        dyn_range=dyn_range,
        dyn_flatness=dyn_flatness,
        spectral_centroid_mean=spectral_centroid_mean,
        zcr_mean=zcr_mean,
        energy_curve=energy_curve,
        waveform_peaks=waveform_peaks,
        waveform_times=times,
        highlight_regions=regions,
        raw={
            "beat_count": int(len(beat_times)),
            "onset_count": int(len(onset_times)),
        },
    )


def _detect_highlight_regions(
    y: np.ndarray,
    sr: int,
    beat_times: np.ndarray,
    onset_times: np.ndarray,
    rms: np.ndarray,
    pitch_cents_std: float | None,
) -> list[dict[str, Any]]:
    """Coarse issue markers for timeline UI (future: ML onset alignment)."""
    regions: list[dict[str, Any]] = []
    duration = len(y) / max(1, sr)

    if len(beat_times) > 6:
        ivals = np.diff(beat_times)
        med = float(np.median(ivals))
        for i, iv in enumerate(ivals):
            if iv < med * 0.88:
                t0 = float(beat_times[i])
                regions.append(
                    {
                        "start": t0,
                        "end": min(duration, t0 + 1.2),
                        "label": "Rushing pocket",
                        "severity": "medium",
                        "kind": "timing",
                    }
                )
            elif iv > med * 1.12:
                t0 = float(beat_times[i])
                regions.append(
                    {
                        "start": t0,
                        "end": min(duration, t0 + 1.2),
                        "label": "Dragging pocket",
                        "severity": "low",
                        "kind": "timing",
                    }
                )

    if len(rms) > 8:
        frame_t = librosa.frames_to_time(np.arange(len(rms)), sr=sr)
        rms_n = (rms - np.min(rms)) / max(np.ptp(rms), 1e-9)
        quiet = np.where(rms_n < 0.15)[0]
        if len(quiet) > 2:
            idx = int(quiet[len(quiet) // 2])
            regions.append(
                {
                    "start": float(frame_t[max(0, idx - 1)]),
                    "end": float(frame_t[min(len(frame_t) - 1, idx + 2)]),
                    "label": "Low energy / hesitant",
                    "severity": "low",
                    "kind": "musicality",
                }
            )

    if pitch_cents_std and pitch_cents_std > 55 and duration > 4:
        regions.append(
            {
                "start": duration * 0.35,
                "end": duration * 0.65,
                "label": "Pitch drift zone",
                "severity": "medium",
                "kind": "pitch",
            }
        )

    return regions[:8]


# ---------------------------------------------------------------------------
# Scoring + coach copy
# ---------------------------------------------------------------------------


def _clamp_score(v: float) -> int:
    return int(max(12, min(96, round(v))))


def compute_performance_scores(f: AudioFeatures, instrument: str) -> dict[str, int]:
    timing = 78.0
    timing -= min(35, f.beat_interval_cv * 120)
    timing -= min(15, abs(f.tempo_drift_pct) * 0.4)
    timing += f.groove_tightness * 18

    pitch = 70.0
    if f.pitch_cents_std is not None:
        pitch -= min(40, f.pitch_cents_std * 0.65)
        pitch += min(12, f.voiced_ratio * 15)
        pitch -= min(10, abs(f.pitch_sharp_bias) * 0.25)

    groove = 68.0 + f.groove_tightness * 28 - min(20, f.beat_interval_cv * 80)

    musicality = 62.0
    musicality += min(22, f.dyn_range * 400)
    musicality -= f.dyn_flatness * 18
    musicality += min(10, f.onset_density * 3)

    confidence = 60.0
    if len(f.energy_curve) > 4:
        tail = float(np.mean(f.energy_curve[len(f.energy_curve) // 2 :]))
        head = float(np.mean(f.energy_curve[: len(f.energy_curve) // 2]))
        if tail > head * 1.08:
            confidence += 14
        elif tail < head * 0.85:
            confidence -= 12
    confidence += min(12, f.onset_strength_mean * 2)

    tone = 65.0
    tone += min(15, (f.spectral_centroid_mean / 4000) * 10)
    if instrument.lower() in ("guitar", "piano"):
        tone -= min(12, f.zcr_mean * 40)

    technique = (timing * 0.25 + pitch * 0.2 + groove * 0.2 + tone * 0.2 + confidence * 0.15)

    return {
        "timing": _clamp_score(timing),
        "pitch": _clamp_score(pitch),
        "technique": _clamp_score(technique),
        "groove": _clamp_score(groove),
        "musicality": _clamp_score(musicality),
        "confidence": _clamp_score(confidence),
        "tone": _clamp_score(tone),
    }


def _timing_analysis(f: AudioFeatures, ctx: dict[str, Any]) -> dict[str, Any]:
    findings: list[str] = []
    tips: list[str] = []
    bpm_hint = int(ctx.get("practice_bpm") or f.tempo or 80)

    if f.beat_interval_cv > 0.14:
        findings.append("Beat spacing is uneven — rhythm may rush or drag between measures.")
    else:
        findings.append("Core pulse is fairly steady across the take.")

    if f.tempo_drift_pct > 6:
        findings.append("Second half trends slightly faster — common when energy rises into chorus.")
        tips.append(f"Loop chorus entrances at {max(50, bpm_hint - 18)} BPM with one-bar count-in.")
    elif f.tempo_drift_pct < -6:
        findings.append("Tempo relaxes as the take goes on — watch dragging in transitions.")
        tips.append("Practice with metronome on beats 2 & 4 only to lock groove without over-tensing.")

    if f.groove_tightness < 0.35:
        findings.append("Attacks don't always line up with the beat grid — subdivision control can tighten.")
        from analysis_coach_quality import instrument_family

        fam = instrument_family(str(ctx.get("instrument") or ""))
        if fam == "guitar":
            tips.append("Strumming subdivision exercise: 8ths on one chord, mute between downbeats.")
        else:
            tips.append("Subdivision exercise: even 8ths on one pitch, rest on beats 2 and 4.")
    elif f.groove_tightness > 0.55:
        findings.append("Strong groove feel — attacks align well with the pulse.")

    if f.onset_density > 3.2:
        from analysis_coach_quality import instrument_family as _fam

        if _fam(str(ctx.get("instrument") or "")) == "guitar":
            findings.append("High attack density — check for rushed fills or inconsistent strumming.")
        else:
            findings.append("High attack density — check for rushed fills or crowded phrases.")
    elif f.onset_density < 0.6:
        findings.append("Sparse attacks — long sustains or very soft articulation detected.")

    if ctx.get("sections"):
        from analysis_coach_quality import has_song_form_context

        if has_song_form_context(ctx):
            sec_names = list(ctx["sections"].keys())
            if any("chorus" in s.lower() for s in sec_names):
                findings.append(
                    "Chorus entrances are a common rush point — compare your downbeat to the metronome."
                )
    tips.append(f"Try slower metronome practice at {max(55, bpm_hint - 20)} BPM, then notch up 4 BPM per clean pass.")

    return {
        "title": "Timing / Rhythm",
        "findings": findings,
        "tips": tips,
    }


def _pitch_analysis(f: AudioFeatures, instrument: str, ctx: dict[str, Any]) -> dict[str, Any]:
    findings: list[str] = []
    tips: list[str] = []
    dk = str(ctx.get("display_key") or "C")
    from analysis_coach_quality import instrument_family

    fam = instrument_family(instrument)

    if f.pitch_note:
        findings.append(
            f"Estimated center pitch: {f.pitch_note} (voiced {f.voiced_ratio * 100:.0f}% of frames)."
        )
    else:
        findings.append("Pitch contour was unclear — try a brighter tone or less room noise.")

    if f.pitch_cents_std is not None:
        # pitch_cents_std is within-note stability (not melodic range).
        if f.pitch_cents_std < 28:
            findings.append("Note-level intonation is relatively stable — good targeting within held notes.")
        elif f.pitch_cents_std < 52:
            findings.append(
                "Moderate within-note pitch movement — light vibrato or mild drift on sustains."
            )
        else:
            findings.append("Within-note pitch wavers — intonation drifts under sustain.")

    if f.pitch_sharp_bias > 12:
        findings.append("High register tendency: notes lean sharp on average within holds.")
        tips.append("Long-tone exercise: descend into the target pitch; do not push up into it.")
    elif f.pitch_sharp_bias < -12:
        findings.append("Sustains trend flat — support often drops at the end of the note.")
        if fam == "flute":
            tips.append("Keep a steady air stream through the release — support from the core.")
        elif fam in ("saxophone", "clarinet", "trumpet", "trombone"):
            tips.append("Keep air speed through the end of the note — support from the core.")
        elif fam == "voice":
            tips.append("Keep breath support through the release — do not collapse at the end of the vowel.")
        else:
            tips.append("Support the end of each sustain — pitch often drops when energy fades.")

    if fam == "voice":
        findings.append("Vocal pitch is often strongest in the middle register — warm up there first.")
        tips.append("Voice sustain exercise: 5-note scale in key, hold beat 4 of each bar.")
    elif fam == "flute":
        findings.append(
            "Flute intonation: prioritize steady air stream, embouchure stability, and consistent aperture."
        )
        tips.append("Long tones with a tuner/drone — match pitch, then add gentle vibrato only after center is steady.")
    elif fam == "clarinet":
        findings.append("Clarinet intonation: watch embouchure firmness and air speed across the break.")
        tips.append("Long tones across the break — keep air speed even, avoid biting for sharp notes.")
    elif fam == "saxophone":
        findings.append("Sax intonation: check embouchure and reed response on long tones.")
        tips.append("Long tones with steady air — avoid pinching the reed to chase pitch.")
    elif fam == "trumpet":
        findings.append("Brass intonation: center each pitch with steady air before adding volume.")
        tips.append("Long tones on middle C–G — buzz freely, then match the mouthpiece pitch on the horn.")
    elif fam == "guitar":
        tips.append("When harmony context exists, target chord tones — root on 1, 3rd on 3, 7th on 4.")

    tips.append(f"Ear training: sing then play {dk} major scale roots against a drone.")

    return {"title": "Pitch / Intonation", "findings": findings, "tips": tips}


def _technique_analysis(f: AudioFeatures, instrument: str) -> dict[str, Any]:
    findings: list[str] = []
    tips: list[str] = []
    from analysis_coach_quality import instrument_family

    fam = instrument_family(instrument)

    if fam == "guitar":
        findings.append("Chord clarity: listen for muted strings on changes — common when transitions rush.")
        if f.zcr_mean > 0.08:
            findings.append("Noisy transients — may indicate scraping or incomplete muting.")
        tips.extend(
            [
                "Slow chord transition loop: 2 chords, 4 strums each, zero buzz.",
                "Alternate picking on one string — match onset strength left vs right.",
            ]
        )
    elif fam == "piano":
        findings.append("Check hand synchronization — melody vs comping should not fight rhythmically.")
        if f.dyn_flatness > 0.7:
            findings.append("Voicings may be dynamically even — bring out top voice or bass pulse.")
        tips.extend(
            [
                "Rhythm comping: LH whole notes, RH Charleston pattern at 70 BPM.",
                "Dynamic balance: practice one phrase pp → mf → p over 4 bars.",
            ]
        )
    elif fam == "flute":
        findings.append(
            "Flute articulation: keep tonguing clean and consistent — not every note equally accented."
        )
        tips.extend(
            [
                "Long-tone pitch/tone drill: 8 beats per note with steady air and stable embouchure.",
                "Tongued vs legato scale pattern — same notes, contrast the attacks.",
                "Register transition loop: low–middle–high on one scale degree with matched tone.",
            ]
        )
    elif fam == "clarinet":
        findings.append("Clarinet articulation: consistent tongue and air across the break.")
        tips.extend(
            [
                "Long tones across the break — same attack, same release, same pitch center.",
                "Phrase shaping: crescendo into bar 3, release on bar 4.",
            ]
        )
    elif fam == "saxophone":
        findings.append("Sax articulation: note attacks should be consistent — shape accents with intention.")
        tips.extend(
            [
                "Long tones 60s — same attack, same release, same pitch.",
                "Phrase shaping: crescendo into bar 3, release on bar 4.",
            ]
        )
    elif fam in ("trumpet", "trombone"):
        findings.append("Brass articulation: match tongue and air so attacks stay centered.")
        tips.extend(
            [
                "Long tones with steady air — release without collapsing the embouchure.",
                "Phrase shaping: crescendo into bar 3, release on bar 4.",
            ]
        )
    elif fam == "voice":
        findings.append("Breath support drives pitch stability and resonance.")
        tips.extend(
            [
                "Phrase loop: speak rhythm, sing on 'mah', add words last.",
                "Resonance: hum into mask, then open vowel on same pitch.",
            ]
        )
    else:
        findings.append(
            f"General technique scan for {instrument} — focus on clean attacks and releases."
        )
        tips.append("Record 30s, rest 30s, record again — compare second take for consistency.")

    if f.onset_strength_mean < 0.8:
        findings.append("Soft attacks — increase definition if you want clearer rhythm.")
    elif f.onset_strength_mean > 2.5:
        findings.append("Strong attacks — good energy; ensure they're not ahead of the beat.")

    return {"title": "Technique", "findings": findings, "tips": tips}


def _musicality_analysis(f: AudioFeatures) -> dict[str, Any]:
    findings: list[str] = []
    tips: list[str] = []

    if f.dyn_flatness > 0.65:
        findings.append("Dynamics stay relatively flat — phrases could breathe more.")
        tips.append("Map one phrase: start mp, peak mf on beat 3, release on 4.")
    else:
        findings.append("Dynamic contrast is present — musical shaping is developing.")

    if f.groove_tightness > 0.5:
        findings.append("Strong groove feel — listener senses the pocket.")
    else:
        findings.append("Groove is emerging — tighten rhythm before adding more notes.")

    if len(f.energy_curve) > 4:
        tail = float(np.mean(f.energy_curve[len(f.energy_curve) // 2 :]))
        head = float(np.mean(f.energy_curve[: len(f.energy_curve) // 2]))
        if tail > head * 1.1:
            findings.append("Energy builds through the take — confidence grows after the intro.")
        elif tail < head * 0.9:
            findings.append("Energy tapers — performance may sound hesitant in later sections.")

    tips.append("Musicality drill: play the same 4 bars at three dynamic levels without changing tempo.")

    return {"title": "Musicality / Expression", "findings": findings, "tips": tips}


def build_practice_plan(
    scores: dict[str, int],
    ctx: dict[str, Any],
    f: AudioFeatures,
) -> list[str]:
    from analysis_coach_quality import (
        dedupe_recommendations,
        has_song_form_context,
        instrument_family,
    )

    dk = str(ctx.get("display_key") or "C")
    inst = str(ctx.get("instrument") or "Instrument")
    fam = instrument_family(inst)
    song_form = has_song_form_context(ctx)
    weakest = sorted(scores.items(), key=lambda x: x[1])[:3]
    plan: list[str] = []
    bpm = int(f.tempo or ctx.get("practice_bpm") or 80)
    slow = max(55, bpm - 22)

    rtype = str(ctx.get("recording_type") or "").strip().lower().replace("_", " ")
    labels = list(ctx.get("evaluating_criteria_labels") or [])
    practice_focus = str(ctx.get("focus") or "").strip()
    mission = str(ctx.get("mission_type") or ctx.get("mission_constraint") or "").strip()
    if mission:
        plan.append(
            f"Mission check: replay the take and mark where you left the '{mission}' constraint; "
            f"fix those bars first."
        )
    if labels:
        plan.append(
            f"Criteria drill ({labels[0]}): one 8-bar loop focusing only on that emphasis @ {slow} BPM."
        )
    _pfs = [str(x).strip() for x in (ctx.get("practice_focuses") or ctx.get("focuses") or []) if str(x).strip()]
    if not _pfs and practice_focus:
        _pfs = [practice_focus]
    if _pfs:
        _pf_txt = (
            _pfs[0]
            if len(_pfs) == 1
            else (" and ".join(_pfs) if len(_pfs) == 2 else (", ".join(_pfs[:-1]) + f", and {_pfs[-1]}"))
        )
        plan.append(f"Practice Focuses ({_pf_txt}): short intentional block before free playing.")
    if "practice take" in rtype:
        plan.append(f"Diagnostic loop: isolate the weakest 2 bars and repeat @ {slow} BPM until clean.")
    elif "backing" in rtype:
        plan.append(
            f"Lock with backing: play only downbeats for 8 bars @ {slow} BPM, then restore the phrase."
        )
    elif "mission" in rtype:
        plan.append(
            f"Mission constraint loop: stay inside the mission rule for 8 bars @ {slow} BPM, then widen expression."
        )
    elif "multitrack layer" in rtype:
        stem_count = int(ctx.get("comparison_stem_count") or ctx.get("uploaded_track_count") or 1)
        if stem_count >= 2:
            plan.append(
                "Layer role drill: mute other stems and check entrances/releases against the form."
            )
        else:
            plan.append(
                "Practice entrances/releases against a click or project reference track "
                "(no other stems were uploaded for this Layer take)."
            )
    elif "multitrack mix" in rtype:
        plan.append("Mix cohesion drill: listen for balance/groove clashes before re-recording a layer.")

    plan.append(f"{dk} major scale @ {slow} BPM — 2 octaves, even subdivisions.")
    for name, _ in weakest:
        if name == "timing":
            plan.append(f"Metronome loop: weakest section @ {slow} BPM, 4-bar phrases.")
        elif name == "pitch":
            if song_form:
                plan.append(f"Chord-tone targeting in {dk}: root–3rd–5th–7th over first 4 song chords.")
            else:
                plan.append(f"Tuner/drone long tones in {dk}: center each note before connecting the scale.")
        elif name == "groove":
            if fam == "guitar":
                plan.append("Subdivision exercise: clap 8ths, mute on 2 & 4, then play on guitar.")
            else:
                plan.append("Subdivision exercise: clap 8ths, rest on 2 & 4, then play the phrase.")
        elif name == "technique":
            if fam == "guitar":
                plan.append(f"{inst} transition loop — 2 chords, 2 bars each, zero buzz.")
            elif fam == "flute":
                plan.append("Flute breath-controlled phrase loop — 4 bars tongued, 4 bars legato, same air.")
            elif fam in ("saxophone", "clarinet", "trumpet", "trombone"):
                plan.append(f"{inst} long-tone + articulation loop — same pitch, contrast attacks.")
            elif fam == "piano":
                plan.append("Piano two-hand sync loop — LH whole notes, RH even 8ths for 8 bars.")
            else:
                plan.append(f"{inst} clean-attack loop — 8 notes, matched starts and releases.")
        elif name == "musicality":
            plan.append("Dynamics map: one 8-bar phrase at pp / mf / f without tempo change.")

    if song_form:
        sections = ctx.get("sections") or {}
        for sec in sections:
            if "chorus" in sec.lower():
                plan.append(f"Chorus transition loop with backing track @ {slow + 8} BPM.")
                break
        plan.append("Ear training: sing the root of each chord before playing the section.")
        if ctx.get("song"):
            plan.append(f"Backing track recommendation: replay {ctx['song']} section-by-section.")
    else:
        plan.append("Ear training: sing each scale degree against a drone before playing it.")
        plan.append("Exercise loop: one octave ascending/descending with intentional phrase shape.")

    return dedupe_recommendations(plan, limit=8)


def _apply_context_emphasis_to_categories(
    categories: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Augment category findings/tips with recording context without changing scores."""
    out = {k: {**v, "findings": list(v.get("findings") or []), "tips": list(v.get("tips") or [])} for k, v in categories.items()}
    rtype = str(ctx.get("recording_type") or "").lower().replace("_", " ")
    labels = [str(x).lower() for x in (ctx.get("evaluating_criteria_labels") or [])]
    mission = str(ctx.get("mission_type") or ctx.get("mission_constraint") or "").strip()
    focus = str(ctx.get("focus") or "").strip()
    _ctx_focuses = [
        str(x).strip()
        for x in (ctx.get("practice_focuses") or ctx.get("focuses") or [])
        if str(x).strip()
    ]
    if not _ctx_focuses and focus:
        _ctx_focuses = [focus]

    if "backing" in rtype and "groove" in out:
        out["groove"]["findings"].insert(
            0,
            "Over-backing context: judge pocket and entrances relative to the accompaniment grid.",
        )
        out["groove"]["tips"].insert(
            0,
            "Mute yourself for 2 bars, hear the backing pocket, then re-enter on beat 1.",
        )
    if "practice take" in rtype and "technique" in out:
        out["technique"]["findings"].insert(
            0,
            "Practice-take lens: treat rough spots as diagnostic signals, not performance flaws.",
        )
    if "multitrack mix" in rtype and "musicality" in out:
        out["musicality"]["findings"].insert(
            0,
            "Mix context: musical shape includes how layers interact, not only one voice.",
        )
    if "multitrack layer" in rtype and "timing" in out:
        out["timing"]["findings"].insert(
            0,
            "Layer context: timing is judged against the arrangement role of this part.",
        )
    if mission and "musicality" in out:
        out["musicality"]["findings"].insert(
            0,
            f"Mission '{mission}': evaluate constraint compliance before free expression notes.",
        )
        out["musicality"]["tips"].insert(
            0,
            f"Replay and mark bars that leave the '{mission}' rule; repair those first.",
        )
    if _ctx_focuses and "confidence" in out:
        if len(_ctx_focuses) >= 2:
            try:
                from recording_analysis_context import format_focus_list

                focus_txt = format_focus_list(_ctx_focuses)
            except Exception:
                focus_txt = ", ".join(_ctx_focuses[:-1]) + f", and {_ctx_focuses[-1]}"
            out["confidence"]["tips"].insert(
                0,
                f"Keep your Practice Focuses — {focus_txt} — visible for the next intentional take.",
            )
        else:
            out["confidence"]["tips"].insert(
                0,
                f"Keep Practice Focus ({_ctx_focuses[0]}) visible on the stand for the next intentional take.",
            )

    # Map Evaluating Criteria onto category emphasis with criterion-specific depth
    # (baseline scores stay; observations/tips deepen for the requested criteria).
    criteria_map = {
        "phras": "musicality",
        "melodic": "musicality",
        "motif": "musicality",
        "rhythm": "timing",
        "timing": "timing",
        "groove": "groove",
        "tone": "tone",
        "pitch": "pitch",
        "inton": "pitch",
        "articul": "technique",
        "technique": "technique",
        "express": "musicality",
        "improvis": "musicality",
        "chord-tone": "pitch",
        "chord tone": "pitch",
        "guide-tone": "pitch",
        "guide tone": "pitch",
        "voice lead": "musicality",
        "scale": "pitch",
        "mode": "pitch",
        "dynamic": "musicality",
    }
    criterion_deep_dives = {
        "phras": (
            "Phrasing deep-dive: shape start/middle/end of each phrase; leave intentional space.",
            "Loop 4 bars and mark breath/space points before replaying for phrase arc.",
        ),
        "melodic": (
            "Melodic development deep-dive: track how motifs return, sequence, or contrast.",
            "Take one 2-bar cell and develop it across the form before inventing new material.",
        ),
        "motif": (
            "Motif development deep-dive: vary rhythm/interval while keeping the cell recognizable.",
            "State the motif, then sequence it up/down a step for 8 bars.",
        ),
        "chord-tone": (
            "Chord-tone targeting deep-dive: land chord tones (esp. 3rds/7ths) on strong beats.",
            "Over each chord, outline root–3rd–5th–7th before freer lines.",
        ),
        "chord tone": (
            "Chord-tone targeting deep-dive: land chord tones (esp. 3rds/7ths) on strong beats.",
            "Over each chord, outline root–3rd–5th–7th before freer lines.",
        ),
        "guide-tone": (
            "Guide-tone targeting deep-dive: connect 3rds/7ths smoothly across changes.",
            "Walk only guide tones through the progression, then ornament lightly.",
        ),
        "guide tone": (
            "Guide-tone targeting deep-dive: connect 3rds/7ths smoothly across changes.",
            "Walk only guide tones through the progression, then ornament lightly.",
        ),
        "voice lead": (
            "Voice-leading deep-dive: prefer small intervals when chord tones change.",
            "Connect each chord's 3rd/7th by half/whole step before wider leaps.",
        ),
        "rhythm": (
            "Rhythmic diversity deep-dive: vary subdivision density and placement, not only notes.",
            "Alternate 8ths / syncopation / rests across consecutive 2-bar cells.",
        ),
        "dynamic": (
            "Dynamics deep-dive: plan crescendo/decrescendo inside phrases, not only loudness spikes.",
            "Play the same line pp → mf → f without changing pitches.",
        ),
        "articul": (
            "Articulation deep-dive: contrast legato vs detached attacks with intention.",
            "Alternate tongued/legato 8ths on one scale pattern for 8 bars.",
        ),
        "tone": (
            "Instrument tone deep-dive: keep color consistent through phrase peaks and soft endings.",
            "Sustain long tones at three dynamics, matching timbre at each level.",
        ),
        "groove": (
            "Timing/groove deep-dive: place attacks relative to the pocket, not only average tempo.",
            "Play with click on 2 & 4; feel backbeat before adding fills.",
        ),
        "scale": (
            "Scale/mode usage deep-dive: choose tones that fit chord function, not scale-run autopilot.",
            "For each chord, name the parent scale/mode then play only chord tones + one approach.",
        ),
        "mode": (
            "Scale/mode usage deep-dive: choose tones that fit chord function, not scale-run autopilot.",
            "For each chord, name the parent scale/mode then play only chord tones + one approach.",
        ),
    }
    for label in labels:
        placed = False
        for needle, cat in criteria_map.items():
            if needle in label and cat in out:
                deep = None
                for key, pair in criterion_deep_dives.items():
                    if key in label:
                        deep = pair
                        break
                finding, tip = deep or (
                    f"Evaluating Criteria emphasis ({label}): deepen coaching on this category while keeping all baseline scores.",
                    f"Next take: one intentional loop focusing on {label} only.",
                )
                out[cat]["findings"].insert(0, finding)
                out[cat]["tips"].insert(0, tip)
                placed = True
                break
        if not placed and "musicality" in out:
            out["musicality"]["findings"].insert(
                0,
                f"Evaluating Criteria emphasis ({label}): prioritize this lens in observations and next steps.",
            )
            out["musicality"]["tips"].insert(
                0,
                f"Next take: one intentional loop focusing on {label} only.",
            )

    # Player level shapes coaching language only — never rewrite measured scores.
    level = str(ctx.get("level") or "").strip().lower()
    if "beginner" in level and "confidence" in out:
        out["confidence"]["tips"].insert(
            0,
            "Beginner coaching: celebrate clear wins, then assign one tiny measurable next step.",
        )
    elif "advanced" in level and "musicality" in out:
        out["musicality"]["findings"].insert(
            0,
            "Advanced coaching: expect clearer intent, stronger story arc, and tighter harmonic choices.",
        )
    elif "intermediate" in level and "technique" in out:
        out["technique"]["tips"].insert(
            0,
            "Intermediate coaching: keep fundamentals solid while stretching one musical risk per take.",
        )

    return out


def build_coach_summary(
    scores: dict[str, int],
    categories: dict[str, dict[str, Any]],
    ctx: dict[str, Any] | None = None,
) -> tuple[str, str, str, str]:
    ranked = sorted(scores.items(), key=lambda x: x[1])
    weakest_name, weakest_score = ranked[0]
    strongest_name, strongest_score = ranked[-1]

    label_map = {
        "timing": "timing & rhythm",
        "pitch": "pitch & intonation",
        "technique": "technique",
        "groove": "groove",
        "musicality": "musicality",
        "confidence": "confidence",
        "tone": "tone",
    }
    weak_l = label_map.get(weakest_name, weakest_name)
    strong_l = label_map.get(strongest_name, strongest_name)

    summary = (
        f"Your {strong_l} is the brightest spot in this take (score {strongest_score}/100). "
        f"Biggest growth edge: {weak_l} (score {weakest_score}/100). "
        "Overall you're building real musical habits — the coach read is based on pulse, pitch, "
        "dynamics, and attack clarity from this recording."
    )
    ctx = ctx or {}
    try:
        from recording_analysis_context import coach_emphasis_notes

        snap = ctx.get("analysis_context_snapshot")
        if not isinstance(snap, dict):
            snap = {
                "recording_type": ctx.get("recording_type"),
                "practice_focus": ctx.get("focus"),
                "practice_focuses": list(ctx.get("practice_focuses") or ctx.get("focuses") or []),
                "instrument_focuses": dict(ctx.get("instrument_focuses") or {}),
                "target_layer": ctx.get("target_layer"),
                "evaluating_criteria_labels": ctx.get("evaluating_criteria_labels") or [],
                "evaluating_criteria_ids": ctx.get("mission_ids") or [],
                "mission_type": ctx.get("mission_type"),
                "mission_constraint": ctx.get("mission_constraint"),
                "instruments": ctx.get("instruments") or ([ctx.get("instrument")] if ctx.get("instrument") else []),
                "level": ctx.get("level"),
                "song_source_name": ctx.get("song"),
                "song_source_type": ctx.get("song_source_type"),
            }
        emphasis = coach_emphasis_notes(snap)
        if emphasis:
            # Keep baseline summary; append context-aware coaching stance.
            summary = summary + " " + " ".join(
                note.replace("**", "") for note in emphasis[:3]
            )
    except Exception:
        pass

    biggest = categories.get(weakest_name, {}).get("findings", ["Keep practicing with intention."])[0]
    improved = (
        f"{strong_l.title()} — score {strongest_score}/100"
    )
    focus = categories.get(weakest_name, {}).get("tips", ["Loop one section slowly with metronome."])[0]

    # Prefer Evaluating Criteria / Practice Focus for next_focus when present
    labels = list(ctx.get("evaluating_criteria_labels") or [])
    practice_focus = str(ctx.get("focus") or "").strip()
    if labels:
        focus = (
            f"Deepen work on {labels[0]} while protecting your gains in {strong_l}."
        )
    elif practice_focus:
        _pfs = [str(x).strip() for x in (ctx.get("practice_focuses") or ctx.get("focuses") or []) if str(x).strip()]
        if not _pfs and practice_focus:
            _pfs = [practice_focus]
        _pf_txt = (
            _pfs[0] if len(_pfs) == 1 else
            (" and ".join(_pfs) if len(_pfs) == 2 else (", ".join(_pfs[:-1]) + f", and {_pfs[-1]}"))
        )
        focus = f"Keep your Practice Focuses on {_pf_txt}: one slow intentional loop, then one musical phrase."
    return summary, biggest, improved, focus


def analyze_recording(
    audio_bytes: bytes,
    filename: str,
    ctx: dict[str, Any],
) -> dict[str, Any]:
    """Full coach analysis for a single recording."""
    if librosa is None:
        return {
            "ok": False,
            "message": "Recording analysis requires **librosa** and **soundfile**. Install from requirements.txt.",
        }

    try:
        y, sr, _ = _load_audio(audio_bytes, filename)
        features = extract_audio_features(y, sr)
        instrument = str(ctx.get("instrument") or "Piano")
        scores = compute_performance_scores(features, instrument)

        categories = {
            "timing": {**_timing_analysis(features, ctx), "score": scores["timing"]},
            "pitch": {**_pitch_analysis(features, instrument, ctx), "score": scores["pitch"]},
            "technique": {**_technique_analysis(features, instrument), "score": scores["technique"]},
            "musicality": {**_musicality_analysis(features), "score": scores["musicality"]},
            "groove": {
                "title": "Groove / Feel",
                "findings": [
                    f"Groove tightness estimate: {features.groove_tightness * 100:.0f}% of attacks near beat.",
                    "Strong pocket = listener trusts the time.",
                ],
                "tips": ["Play with the metronome on 2 & 4; feel the backbeat before adding fills."],
                "score": scores["groove"],
            },
            "confidence": {
                "title": "Confidence / Energy",
                "findings": [
                    "Confidence inferred from energy trajectory and attack strength across the take.",
                ],
                "tips": ["Record two takes back-to-back — second take often sounds more assured."],
                "score": scores["confidence"],
            },
            "tone": {
                "title": "Tone Quality",
                "findings": [
                    f"Brightness (spectral centroid): {features.spectral_centroid_mean:.0f} Hz avg.",
                ],
                "tips": ["Aim for consistent tone color through the phrase, not only the first note."],
                "score": scores["tone"],
            },
        }
        categories = _apply_context_emphasis_to_categories(categories, ctx)

        practice_plan = build_practice_plan(scores, ctx, features)
        summary, biggest, improved, next_focus = build_coach_summary(scores, categories, ctx)

        mission_ids = list(ctx.get("mission_ids") or [])
        mission_block: dict[str, Any] = {}
        if mission_ids:
            from mission_analysis import analyze_improvisation_missions

            mission_block = analyze_improvisation_missions(
                y,
                sr,
                features,
                ctx,
                mission_ids,
                custom_goal=str(ctx.get("custom_goal") or ""),
                performance_scores=scores,
            )

        result_payload = {
            "ok": True,
            "recording_type": ctx.get("recording_type", "practice"),
            "filename": filename,
            "duration": features.duration,
            "tempo": features.tempo,
            "beat_count": int(len(features.beat_times)),
            "features": features,
            "scores": scores,
            "categories": categories,
            "practice_plan": practice_plan,
            "coach_summary": summary,
            "biggest_issue": biggest,
            "most_improved": improved,
            "next_focus": next_focus,
            "instrument": instrument,
            "instruments": list(ctx.get("instruments") or ([instrument] if instrument else [])),
            "level": ctx.get("level"),
            "song": ctx.get("song"),
            "focus": ctx.get("focus"),
            "style_label": ctx.get("style_label"),
            "time_signature": ctx.get("time_signature"),
            "workflow": ctx.get("workflow"),
            "evaluating_criteria_ids": list(ctx.get("mission_ids") or ctx.get("evaluating_criteria_ids") or []),
            "evaluating_criteria_labels": list(ctx.get("evaluating_criteria_labels") or []),
            "song_source_type": ctx.get("song_source_type"),
            "song_source_id": ctx.get("song_source_id"),
            "song_source_name": ctx.get("song") or ctx.get("song_source_name"),
            "mission_type": ctx.get("mission_type"),
            "mission_parameters": dict(ctx.get("mission_parameters") or {}),
        }
        if isinstance(ctx.get("analysis_context_snapshot"), dict):
            result_payload["analysis_context_snapshot"] = dict(ctx["analysis_context_snapshot"])
        result_payload.update(mission_block)
        return result_payload
    except Exception as e:
        return {"ok": False, "message": f"Could not analyze recording: {e}"}


def analyze_multitrack(
    tracks: list[dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any]:
    """Compare multiple uploaded layers (timing, balance, ensemble)."""
    if librosa is None:
        return {
            "ok": False,
            "multitrack": True,
            "message": "Multitrack analysis requires librosa.",
        }
    if len(tracks) < 2:
        return {
            "ok": False,
            "multitrack": True,
            "message": "Upload at least two tracks for multitrack stem comparison.",
        }

    layer_features: list[dict[str, Any]] = []
    for tr in tracks:
        name = str(tr.get("name") or "Track")
        data = tr.get("bytes")
        fname = str(tr.get("filename") or "track.wav")
        if not data:
            continue
        y, sr, _ = _load_audio(data, fname)
        f = extract_audio_features(y, sr)
        layer_features.append({"name": name, "instrument": tr.get("instrument", ""), "features": f})

    if len(layer_features) < 2:
        return {
            "ok": False,
            "multitrack": True,
            "message": "Need two valid audio layers for stem comparison.",
        }

    findings: list[str] = []
    tips: list[str] = []

    ref = layer_features[0]["features"]
    ref_onsets = ref.onset_times
    for layer in layer_features[1:]:
        f = layer["features"]
        if len(ref_onsets) > 2 and len(f.onset_times) > 2:
            # Mean onset phase offset vs reference
            offsets = []
            for ot in f.onset_times[: min(40, len(f.onset_times))]:
                offsets.append(float(np.min(np.abs(ref_onsets - ot))))
            mean_off = float(np.mean(offsets)) if offsets else 0.0
            if mean_off > 0.09:
                findings.append(
                    f"{layer['name']} timing differs from {layer_features[0]['name']} "
                    f"(~{mean_off * 1000:.0f} ms average onset gap)."
                )
            else:
                findings.append(
                    f"{layer['name']} and {layer_features[0]['name']} are rhythmically well locked."
                )

        rms_bal = float(np.mean(f.rms)) / max(float(np.mean(ref.rms)), 1e-9)
        if rms_bal < 0.55:
            findings.append(f"{layer['name']} sits quietly in the mix — may sound buried.")
        elif rms_bal > 1.6:
            findings.append(f"{layer['name']} dominates the blend — check balance vs other parts.")

    tips.append("Mix check: solo each layer, then A/B with drums or click.")
    tips.append("Ensemble drill: record rhythm section first, overdub melody after 2 clean passes.")

    scores = {
        "ensemble": _clamp_score(72 - 5 * max(0, len(findings) - 2)),
        "balance": _clamp_score(70),
        "sync": _clamp_score(68),
    }

    rtype = str(ctx.get("recording_type") or "").lower().replace("_", " ")
    if "layer" in rtype:
        summary = (
            "Multitrack Layer coach read: evaluate this part's timing, role, and support of the arrangement. "
            "Tighten entrances/releases that sit off the grid."
        )
        findings.insert(
            0,
            "Layer evaluation: judge this stem in relation to its musical role, not as a solo recital.",
        )
    else:
        summary = (
            "Multitrack Mix coach read: comparing onset alignment, balance, and groove cohesion across layers. "
            "Tighten anything that consistently sits ahead of the grid."
        )
        findings.insert(
            0,
            "Mix evaluation: treat this as an ensemble arrangement, not one isolated instrument.",
        )
    labels = list(ctx.get("evaluating_criteria_labels") or [])
    if labels:
        findings.insert(0, f"Evaluating Criteria emphasis: {', '.join(labels)}.")

    instrument_focuses = ctx.get("instrument_focuses")
    if isinstance(instrument_focuses, dict):
        cleaned_map: dict[str, list[str]] = {}
        for k, v in instrument_focuses.items():
            inst = str(k).strip()
            if not inst:
                continue
            if isinstance(v, (list, tuple)):
                focuses = [str(x).strip() for x in v if str(x).strip()]
            else:
                focuses = [str(v).strip()] if str(v).strip() else []
            # Deduplicate while preserving order.
            seen: set[str] = set()
            ordered: list[str] = []
            for foc in focuses:
                if foc not in seen:
                    seen.add(foc)
                    ordered.append(foc)
            cleaned_map[inst] = ordered
        instrument_focuses = cleaned_map
    else:
        instrument_focuses = {}

    practice_focuses = ctx.get("practice_focuses") or ctx.get("focuses") or []
    if not isinstance(practice_focuses, list):
        practice_focuses = [str(practice_focuses).strip()] if str(practice_focuses).strip() else []
    practice_focuses = [str(x).strip() for x in practice_focuses if str(x).strip()]
    focus = str(ctx.get("focus") or (practice_focuses[0] if practice_focuses else "")).strip()

    def _fmt(focuses: list[str]) -> str:
        if not focuses:
            return ""
        if len(focuses) == 1:
            return focuses[0]
        if len(focuses) == 2:
            return f"{focuses[0]} and {focuses[1]}"
        return ", ".join(focuses[:-1]) + f", and {focuses[-1]}"

    if "layer" in rtype:
        target = str(
            ctx.get("target_layer")
            or ctx.get("instrument")
            or ((ctx.get("instruments") or [None])[0])
            or ""
        ).strip()
        layer_focuses = list(instrument_focuses.get(target) or practice_focuses or [])
        if not layer_focuses and focus:
            layer_focuses = [focus]
        if layer_focuses:
            practice_focuses = list(layer_focuses)
            focus = layer_focuses[0]
            tips.insert(
                0,
                f"Layer Practice Focuses ({target or 'selected part'} → {_fmt(layer_focuses)}): "
                "judge this stem against all of those intended roles.",
            )
            findings.insert(
                0,
                f"Target-layer Practice Focuses are {_fmt(layer_focuses)}"
                + (f" for {target}" if target else "")
                + ".",
            )
    elif instrument_focuses:
        mapped = "; ".join(
            f"{inst} → {_fmt(foc_list)}" if foc_list else f"{inst} → (none)"
            for inst, foc_list in instrument_focuses.items()
        )
        tips.insert(
            0,
            f"Instrument Practice Focuses — {mapped}. "
            "Coach each selected part toward its own intended goals.",
        )
        findings.insert(
            0,
            f"Multitrack Mix retains per-instrument Practice Focus mapping: {mapped}.",
        )
    elif practice_focuses:
        tips.insert(
            0,
            f"Practice Focuses ({_fmt(practice_focuses)}): keep the next arrangement take aligned with those goals.",
        )
    elif focus:
        tips.insert(0, f"Practice Focus ({focus}): keep the next arrangement take aligned with that goal.")

    return {
        "ok": True,
        "multitrack": True,
        "layers": [lf["name"] for lf in layer_features],
        "findings": findings,
        "tips": tips,
        "scores": scores,
        "coach_summary": summary,
        "recording_type": ctx.get("recording_type"),
        "workflow": ctx.get("workflow"),
        "instruments": list(ctx.get("instruments") or []),
        "evaluating_criteria_labels": labels,
        "focus": focus,
        "practice_focuses": list(practice_focuses),
        "instrument_focuses": dict(instrument_focuses),
    }


def analysis_context_from_app(
    *,
    song: str,
    song_data: dict[str, Any],
    display_key: str,
    sections: dict[str, list[str]],
    target_chords: list[str],
    instrument: str,
    level: str,
    focus: str,
    recording_type: str = "practice",
) -> dict[str, Any]:
    ext = song_data.get("extensions") or {}
    return {
        "song": song,
        "artist": song_data.get("artist", ""),
        "display_key": display_key,
        "sections": sections,
        "target_chords": target_chords,
        "instrument": instrument,
        "level": level,
        "focus": focus,
        "recording_type": recording_type,
        "practice_bpm": ext.get("default_bpm"),
        "genre": song_data.get("genre", ""),
        "time_signature": ext.get("time_signature") or song_data.get("time_signature", ""),
        "style_label": song_data.get("genre", "") or ext.get("style", ""),
    }
