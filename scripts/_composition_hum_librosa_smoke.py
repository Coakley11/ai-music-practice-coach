"""E2E smoke: Composition hum transcription with librosa + count-in offset."""

from __future__ import annotations

import io
import math
import struct
import wave

from composition_hum_transcription import hum_analysis_available, transcribe_hum_audio
from composition_sync_transport import count_in_seconds


def _sine_wav(
    notes: list[tuple[float, float, float]],
    *,
    sr: int = 22050,
    lead_silence_sec: float = 0.0,
    amplitude: float = 0.55,
) -> bytes:
    """notes: (freq_hz, start_sec_after_lead, duration_sec)."""
    total = lead_silence_sec + max((s + d for _, s, d in notes), default=0.0) + 0.2
    n = int(sr * total)
    samples = [0.0] * n
    amp = max(0.1, min(0.9, float(amplitude)))
    for freq, start, dur in notes:
        a0 = int((lead_silence_sec + start) * sr)
        a1 = min(n, a0 + int(dur * sr))
        for i in range(a0, a1):
            t = (i - a0) / float(sr)
            env = min(1.0, t * 25.0) * min(1.0, max(0.0, (dur - t) * 25.0))
            samples[i] += amp * env * math.sin(2.0 * math.pi * freq * t)
    peak = max(abs(s) for s in samples) or 1.0
    pcm = [int(max(-1.0, min(1.0, s / peak)) * 32000) for s in samples]
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(struct.pack("<" + "h" * len(pcm), *pcm))
    return buf.getvalue()


def main() -> None:
    assert hum_analysis_available(), "librosa must be importable"
    bpm = 120
    meter = "4/4"
    cin = count_in_seconds(bpm=bpm, meter=meter, bars=1)
    assert abs(cin - 2.0) < 1e-6, cin

    # Count-in region silent; clear sustained tones after it so pyin locks F0.
    # C4=261.63 (beat 0), E4=329.63 (~beat 2), G4=392.00 (~beat 4)
    wav = _sine_wav(
        [
            (261.63, 0.05, 0.95),
            (329.63, 1.10, 0.90),
            (392.00, 2.15, 0.90),
        ],
        lead_silence_sec=cin,
        amplitude=0.72,
    )
    result = transcribe_hum_audio(
        wav,
        bpm=bpm,
        meter=meter,
        key="C",
        count_in_bars=1,
    )
    print("status:", result.get("status"))
    print("message:", result.get("message"))
    print("count_in_sec:", result.get("count_in_sec"))
    print("available:", result.get("available"))
    events = list(result.get("events") or [])
    pitched = [e for e in events if not e.get("is_rest")]
    print("pitched_count:", len(pitched))
    for e in pitched[:8]:
        print(
            " event",
            e.get("pitch"),
            "midi",
            e.get("midi"),
            "beat",
            e.get("beat"),
            "dur",
            e.get("duration_beats"),
        )

    assert result.get("status") != "unavailable", result
    assert pitched, result
    raw_beat = pitched[0].get("beat")
    first_beat = float(0.0 if raw_beat is None else raw_beat)
    assert first_beat <= 0.51, f"expected first note near beat 0, got {first_beat}"
    first_pc = int(pitched[0].get("midi") or 0) % 12
    assert first_pc == 0, f"expected C pitch class, got midi {pitched[0].get('midi')}"
    print("SMOKE_OK first_beat=", first_beat, "first_midi=", pitched[0].get("midi"))


if __name__ == "__main__":
    main()
