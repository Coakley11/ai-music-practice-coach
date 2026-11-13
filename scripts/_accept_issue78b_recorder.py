"""Issue 78B acceptance: measure what the shared-clock recorder really schedules and captures.

The component is loaded as the top document (the pattern ``tests/test_mc4_recorder_component_browser``
uses), media requests are routed, and Chromium's fake capture device supplies a deterministic
microphone. ``AudioBufferSourceNode.prototype.start`` and ``OscillatorNode.prototype.start`` are
instrumented before each Record, so every gate below compares three independent things:

  * what the component *claims* in the take's timing payload,
  * what was *actually* scheduled on the AudioContext, and
  * what is *in* the returned WAV.

A gate only passes when those agree. Nothing here is proof of acoustic latency: it measures the
scheduling clock and the captured file. Real microphone, real instrument and listening acceptance
are separate and are reported as pending.

Usage:  python scripts/_accept_issue78b_recorder.py [--keep-open]
"""

from __future__ import annotations

import base64
import io
import json
import math
import struct
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from playwright.sync_api import sync_playwright
except Exception as exc:  # pragma: no cover
    print(f"playwright is required: {exc}")
    raise SystemExit(2)

HTML = (ROOT / "mission_recorder_component" / "index.html").read_text(encoding="utf-8")
BASE = "http://localhost:4998"  # localhost is a secure context; nothing listens, every request is routed

# One sample at 48 kHz is 0.0208 ms. Anything inside a sample is exact as far as the clock goes.
SAMPLE_MS_48K = 1000.0 / 48000.0

INSTRUMENT = """
window.__sched = [];
(() => {
  const B = AudioBufferSourceNode.prototype.start;
  AudioBufferSourceNode.prototype.start = function (when, offset) {
    try {
      window.__sched.push({ kind: "buffer", when: Number(when), offset: offset === undefined ? null : Number(offset),
                            now: this.context.currentTime, sr: this.context.sampleRate,
                            duration: this.buffer ? this.buffer.duration : null });
    } catch (e) {}
    return B.apply(this, arguments);
  };
  const O = OscillatorNode.prototype.start;
  OscillatorNode.prototype.start = function (when) {
    try {
      window.__sched.push({ kind: "click", when: Number(when), freq: this.frequency.value,
                            now: this.context.currentTime, sr: this.context.sampleRate });
    } catch (e) {}
    return O.apply(this, arguments);
  };
})();
window.__sent = [];
window.addEventListener("message", (e) => {
  if (e.data && e.data.isStreamlitMessage && e.data.type === "streamlit:setComponentValue")
    window.__sent.push(e.data.value);
});
"""


def wav_bytes(seconds: float, sr: int = 44100, hz: float = 440.0, amp: int = 8000) -> bytes:
    """A plain 16-bit mono WAV the routed media handler can serve."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        n = int(seconds * sr)
        w.writeframes(b"".join(struct.pack("<h", int(amp * math.sin(2 * math.pi * hz * i / sr))) for i in range(n)))
    return buf.getvalue()


class Gates:
    def __init__(self) -> None:
        self.rows: list[tuple[bool, str, str]] = []

    def check(self, ok: bool, name: str, detail: str = "") -> bool:
        self.rows.append((bool(ok), name, detail))
        print(f"  {'PASS' if ok else 'FAIL'}  {name}{('  ' + detail) if detail else ''}")
        return bool(ok)

    @property
    def failed(self) -> list[tuple[bool, str, str]]:
        return [r for r in self.rows if not r[0]]

    def report(self) -> int:
        n = len(self.rows)
        bad = self.failed
        print()
        print(f"{n - len(bad)}/{n} gates passed")
        for _, name, detail in bad:
            print(f"  FAILED: {name}  {detail}")
        return 1 if bad else 0


class Harness:
    def __init__(self, pw, keep_open: bool = False) -> None:
        self.browser = pw.chromium.launch(
            headless=not keep_open,
            args=["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
                  "--autoplay-policy=no-user-gesture-required"],
        )
        self.media: dict[str, bytes] = {}
        self.ctx = self.browser.new_context(permissions=["microphone"])
        self.page = self.ctx.new_page()
        self.page.add_init_script(INSTRUMENT)

        def handler(route):
            path = route.request.url[len(BASE):]
            if path == "/index.html":
                return route.fulfill(status=200, content_type="text/html", body=HTML)
            data = self.media.get(path)
            if data is None:
                return route.fulfill(status=404, body="gone")
            return route.fulfill(status=200, content_type="audio/wav", body=data)

        self.page.route(BASE + "/**", handler)
        self.page.goto(BASE + "/index.html")
        self.page.wait_for_function("() => typeof window.__recorderState === 'function'")

    def close(self) -> None:
        self.ctx.close()
        self.browser.close()

    # -- driving the component
    def render(self, **args) -> None:
        base = {
            "require_backing": False, "disabled": False, "disabled_reason": "", "ready_text": "",
            "backing_fp": "", "backing_url": "", "backing_duration_sec": 0.0, "monitors": [],
            "count_in_beats": 0, "count_in_bpm": 0, "count_in_beats_per_bar": 4,
            "load_nonce": 1, "acked_instance": "", "constraints": {},
        }
        base.update(args)
        self.page.evaluate("(a) => window.postMessage({type: 'streamlit:render', args: a}, '*')", base)

    def state(self) -> dict:
        return self.page.evaluate("() => window.__recorderState()")

    def wait_ready(self, timeout: int = 20000) -> None:
        self.page.wait_for_function(
            "() => !document.getElementById('rec').disabled", timeout=timeout
        )

    def clear_probe(self) -> None:
        self.page.evaluate("() => { window.__sched = []; window.__sent = []; }")

    def record(self, seconds: float) -> dict:
        """One full Record -> wait -> Stop, returning the scheduled log and the take."""
        self.clear_probe()
        self.page.click("#rec")
        self.page.wait_for_function(
            "() => document.getElementById('rec').textContent.includes('Stop')", timeout=15000
        )
        self.page.wait_for_timeout(int(seconds * 1000))
        self.page.click("#rec")
        self.page.wait_for_function(
            "() => window.__sent.some((v) => v && v.take_id)", timeout=20000
        )
        sched = self.page.evaluate("() => window.__sched")
        take = self.page.evaluate("() => window.__sent.filter((v) => v && v.take_id).pop()")
        return {"sched": sched, "take": take}

    def monitor(self, path: str, seconds: float, *, hz: float = 440.0, **extra) -> dict:
        """Register a monitor asset and return the payload entry describing it."""
        self.media[path] = wav_bytes(seconds, hz=hz)
        entry = {"id": path, "fp": path + f":{seconds}", "url": path,
                 "start_delay_sec": 0.0, "buffer_offset_sec": 0.0, "volume": 1.0}
        entry.update(extra)
        return entry


def decode_wav(b64: str) -> tuple[int, list[float]]:
    raw = base64.b64decode(b64)
    with wave.open(io.BytesIO(raw), "rb") as w:
        sr = w.getframerate()
        frames = w.readframes(w.getnframes())
    vals = struct.unpack("<%dh" % (len(frames) // 2), frames)
    return sr, [v / 32768.0 for v in vals]


def rms(values) -> float:
    if not values:
        return 0.0
    return math.sqrt(sum(v * v for v in values) / len(values))


def buffers(sched) -> list[dict]:
    return [e for e in sched if e["kind"] == "buffer"]


def clicks(sched) -> list[dict]:
    return [e for e in sched if e["kind"] == "click"]


def run(keep_open: bool = False) -> int:
    g = Gates()
    with sync_playwright() as pw:
        h = Harness(pw, keep_open=keep_open)
        try:
            # ---------------------------------------------------------------- 1. three monitors, no count-in
            print("\n[1] Three monitors, count-in None - the case the original 160 ms spread came from")
            mons = [h.monitor("/m/a.wav", 4.0, hz=330.0), h.monitor("/m/b.wav", 4.0, hz=440.0),
                    h.monitor("/m/c.wav", 4.0, hz=550.0)]
            h.render(monitors=mons, load_nonce=1)
            h.page.wait_for_function("() => window.__recorderState().bk.state === 'ready'", timeout=25000)
            st = h.state()
            g.check(st["armed"] == 3, "all three monitors are armed before Record is offered", f"armed={st['armed']}")
            g.check(not h.page.locator("#rec").is_disabled(), "Record is enabled once every monitor decoded")

            r = h.record(2.0)
            bufs = buffers(r["sched"])
            t = r["take"]["timing"]
            g.check(len(bufs) == 3, "every monitor was scheduled", f"{len(bufs)} sources")
            whens = [b["when"] for b in bufs]
            spread_ms = (max(whens) - min(whens)) * 1000.0
            g.check(spread_ms <= SAMPLE_MS_48K, "the three monitors start at one instant",
                    f"spread={spread_ms:.4f} ms")
            leads_ms = [(b["when"] - b["now"]) * 1000.0 for b in bufs]
            g.check(min(leads_ms) > 0, "nothing is scheduled in the past", f"min lead={min(leads_ms):.1f} ms")
            g.check(min(leads_ms) >= 200.0, "the scheduling lead is a real margin, not a hope",
                    f"min lead={min(leads_ms):.1f} ms")
            sr = t["sample_rate"]
            music_when = t["music_start_frame"] / sr
            g.check(abs(music_when - min(whens)) * 1000.0 <= SAMPLE_MS_48K,
                    "the claimed musical zero is the instant the monitors really started",
                    f"claim={music_when:.6f}s scheduled={min(whens):.6f}s")
            g.check(t["count_in_sec"] == 0, "no count-in means no count-in", f"count_in_sec={t['count_in_sec']}")
            g.check(len(clicks(r["sched"])) == 0, "no clicks were scheduled")
            g.check(t["monitor_count"] == 3, "the take records how many parts were playing",
                    f"monitor_count={t['monitor_count']}")

            # ---------------------------------------------------------------- 2. the capture itself
            print("\n[2] What is actually in the take")
            take_sr, samples = decode_wav(r["take"]["wav_b64"])
            g.check(take_sr == sr, "the WAV's rate is the rate the timing reports", f"{take_sr} Hz")
            g.check(take_sr >= 44100, "capture is at a music rate, not a speech rate", f"{take_sr} Hz")
            dur = len(samples) / take_sr
            g.check(abs(dur - t["dry_duration_sec"]) < 0.01,
                    "the reported duration is the duration of the file", f"{dur:.3f}s vs {t['dry_duration_sec']:.3f}s")
            g.check(rms(samples) > 1e-4, "the microphone signal is present in the take", f"rms={rms(samples):.5f}")
            # Chromium's fake capture device emits a repeating beep with silence between, so a
            # quiet first 50 ms says nothing about trimming. What does say something is the frame
            # count: every frame from capture start to Stop has to be in the file.
            armed_for = (t["stop_click_ms"] - t["capture_start_ms"]) / 1000.0
            g.check(t["dry_duration_sec"] >= armed_for - 0.02,
                    "every frame from capture start to Stop is in the take, none trimmed",
                    f"captured {t['dry_duration_sec']:.3f}s, armed {armed_for:.3f}s")
            first_signal = next((i for i, v in enumerate(samples) if abs(v) > 0.01), None)
            g.check(first_signal is not None and first_signal / take_sr < 1.2,
                    "signal appears early in the take, within the fake device's own beep period",
                    f"first signal at {0 if first_signal is None else first_signal / take_sr:.3f}s")
            # Same caveat as the head: the fake device is silent between beeps, and which beep the
            # take ends inside is luck. Capture running for the whole take is shown by signal in
            # both halves - if the worklet had stopped early the second half would be empty.
            half = len(samples) // 2
            g.check(rms(samples[:half]) > 1e-4 and rms(samples[half:]) > 1e-4,
                    "the microphone was captured throughout, not only at the start",
                    f"halves rms={rms(samples[:half]):.5f} / {rms(samples[half:]):.5f}")
            g.check(t["capture_first_frame"] is not None, "the capture's first frame is known")

            # ---------------------------------------------------------------- 3. count-in, one bar
            print("\n[3] Count-in 1 bar at 120 bpm (4 beats = 2.000 s)")
            h.render(monitors=mons, count_in_beats=4, count_in_bpm=120, count_in_beats_per_bar=4, load_nonce=1)
            h.wait_ready()
            r3 = h.record(3.0)
            c3, b3 = clicks(r3["sched"]), buffers(r3["sched"])
            t3 = r3["take"]["timing"]
            g.check(len(c3) == 4, "four clicks for one bar of 4/4", f"{len(c3)} clicks")
            if len(c3) == 4:
                gaps = [(c3[i + 1]["when"] - c3[i]["when"]) * 1000.0 for i in range(3)]
                g.check(all(abs(x - 500.0) < 1.0 for x in gaps), "the clicks are one beat apart at 120 bpm",
                        "gaps=" + ", ".join(f"{x:.2f}ms" for x in gaps))
                g.check(c3[0]["freq"] > c3[1]["freq"], "beat one is accented",
                        f"{c3[0]['freq']} vs {c3[1]['freq']} Hz")
            if c3 and b3:
                offset_ms = (min(b["when"] for b in b3) - c3[0]["when"]) * 1000.0
                g.check(abs(offset_ms - 2000.0) < 1.0,
                        "the music starts exactly one bar after the first click", f"{offset_ms:.2f} ms")
            g.check(abs(t3["count_in_sec"] - 2.0) < 1e-9, "the take reports the count-in it was given",
                    f"count_in_sec={t3['count_in_sec']}")
            if c3:
                claim = t3["count_in_start_frame"] / t3["sample_rate"]
                g.check(abs(claim - c3[0]["when"]) * 1000.0 <= SAMPLE_MS_48K,
                        "the claimed count-in start is where the first click really was",
                        f"claim={claim:.6f}s scheduled={c3[0]['when']:.6f}s")
            g.check(t3["music_offset_sec"] > t3["count_in_offset_sec"],
                    "musical zero is after the count-in inside the take",
                    f"music={t3['music_offset_sec']:.3f}s count-in={t3['count_in_offset_sec']:.3f}s")
            g.check(abs((t3["music_offset_sec"] - t3["count_in_offset_sec"]) - 2.0) < 0.002,
                    "the gap between them inside the take is the count-in's own length",
                    f"{t3['music_offset_sec'] - t3['count_in_offset_sec']:.4f}s")
            g.check(abs((t3["scheduled_music_offset_sec"] - t3["scheduled_count_in_offset_sec"]) - 2.0) < 0.002,
                    "and the same on the scheduling clock, so the two sets are not mixed",
                    f"{t3['scheduled_music_offset_sec'] - t3['scheduled_count_in_offset_sec']:.4f}s")
            lat = (t3["output_latency_sec"] or 0) + (t3["input_latency_sec"] or 0)
            g.check(abs((t3["music_offset_sec"] - t3["scheduled_music_offset_sec"]) - lat) < 1e-9,
                    "the latency-compensated offset is the scheduled one plus the measured latency",
                    f"latency={lat * 1000:.1f} ms")
            _, s3 = decode_wav(r3["take"]["wav_b64"])
            g.check(len(s3) / t3["sample_rate"] > 2.0,
                    "the take is longer than its count-in, so the playing is in there",
                    f"{len(s3) / t3['sample_rate']:.2f}s")

            # ---------------------------------------------------------------- 4. count-in, two bars
            print("\n[4] Count-in 2 bars at 90 bpm (8 beats = 5.333 s)")
            h.render(monitors=mons, count_in_beats=8, count_in_bpm=90, count_in_beats_per_bar=4, load_nonce=1)
            h.wait_ready()
            r4 = h.record(0.6)
            c4, b4 = clicks(r4["sched"]), buffers(r4["sched"])
            t4 = r4["take"]["timing"]
            g.check(len(c4) == 8, "eight clicks for two bars", f"{len(c4)} clicks")
            want = 8 * 60.0 / 90.0
            g.check(abs(t4["count_in_sec"] - want) < 1e-6, "the count-in is 8 beats at 90 bpm",
                    f"{t4['count_in_sec']:.4f}s vs {want:.4f}s")
            if c4 and b4:
                offset_ms = (min(b["when"] for b in b4) - c4[0]["when"]) * 1000.0
                g.check(abs(offset_ms - want * 1000.0) < 1.5,
                        "the music starts exactly two bars after the first click", f"{offset_ms:.2f} ms")
            if len(c4) == 8:
                accents = [i for i, c in enumerate(c4) if c["freq"] > 1000]
                g.check(accents == [0, 4], "both bars are accented on their first beat", f"accents at {accents}")
            g.check(r4["take"]["wav_b64"] != "", "stopping during the count-in still returns the take")

            # ---------------------------------------------------------------- 5. three-four
            print("\n[5] A 3/4 count-in counts three, not four")
            h.render(monitors=mons[:1], count_in_beats=3, count_in_bpm=120, count_in_beats_per_bar=3, load_nonce=1)
            h.wait_ready()
            r5 = h.record(0.4)
            c5 = clicks(r5["sched"])
            g.check(len(c5) == 3, "three clicks", f"{len(c5)} clicks")
            g.check(abs(r5["take"]["timing"]["count_in_sec"] - 1.5) < 1e-9, "1.5 s of count-in at 120 bpm")

            # ---------------------------------------------------------------- 6. Align
            print("\n[6] Align places each monitor where the mix will put it")
            aligned = [
                h.monitor("/m/p.wav", 4.0, hz=330.0, start_delay_sec=0.5, buffer_offset_sec=0.0),
                h.monitor("/m/z.wav", 4.0, hz=440.0, start_delay_sec=0.0, buffer_offset_sec=0.0),
                h.monitor("/m/n.wav", 4.0, hz=550.0, start_delay_sec=0.0, buffer_offset_sec=0.5),
            ]
            h.render(monitors=aligned, load_nonce=2)
            h.page.wait_for_function("() => window.__recorderState().bk.state === 'ready'", timeout=25000)
            h.wait_ready()
            r6 = h.record(1.0)
            b6 = buffers(r6["sched"])
            t6 = r6["take"]["timing"]
            g.check(len(b6) == 3, "all three aligned monitors were scheduled", f"{len(b6)}")
            if len(b6) == 3:
                zero = t6["music_start_frame"] / t6["sample_rate"]
                rel = sorted(round((b["when"] - zero) * 1000.0, 3) for b in b6)
                g.check(rel[0] <= SAMPLE_MS_48K and rel[1] <= SAMPLE_MS_48K,
                        "a zero and a negative Align both start at musical zero", f"starts at {rel} ms")
                g.check(abs(rel[2] - 500.0) < 0.05, "a +0.5 s Align starts half a second later",
                        f"{rel[2]:.3f} ms")
                offs = sorted(b["offset"] or 0.0 for b in b6)
                g.check(abs(offs[2] - 0.5) < 1e-9,
                        "a -0.5 s Align skips half a second INTO the layer instead of moving nothing",
                        f"offsets={offs}")
                g.check(offs[0] == 0.0 and offs[1] == 0.0, "the other two are played from their start")

            # ---------------------------------------------------------------- 7. no monitors at all
            print("\n[7] The first layer: nothing to play along with")
            h.render(monitors=[], count_in_beats=4, count_in_bpm=120, load_nonce=1)
            h.wait_ready()
            g.check(not h.page.locator("#rec").is_disabled(),
                    "Record is available with no monitors - a first layer can be recorded")
            r7 = h.record(1.0)
            t7 = r7["take"]["timing"]
            g.check(len(buffers(r7["sched"])) == 0, "nothing was scheduled to play")
            g.check(len(clicks(r7["sched"])) == 4, "the count-in still happened", f"{len(clicks(r7['sched']))} clicks")
            g.check(t7["music_offset_sec"] is not None,
                    "musical zero is still measured with no backing to measure against",
                    f"music_offset_sec={t7['music_offset_sec']}")
            g.check(t7["backing_offset_sec"] is None,
                    "and it does not pretend there was a backing", f"backing_offset_sec={t7['backing_offset_sec']}")
            g.check(t7["monitor_count"] == 0, "monitor_count is honest", f"{t7['monitor_count']}")
            _, s7 = decode_wav(r7["take"]["wav_b64"])
            g.check(rms(s7) > 1e-4, "the take still captured the microphone", f"rms={rms(s7):.5f}")

            # ---------------------------------------------------------------- 8. repeat / retry
            print("\n[8] Record again: a second take, cleanly")
            h.render(monitors=mons, count_in_beats=4, count_in_bpm=120, load_nonce=1)
            h.wait_ready()
            first = h.record(0.8)
            second = h.record(0.8)
            g.check(first["take"]["take_id"] != second["take"]["take_id"],
                    "each take has its own id, so one cannot be mistaken for the other")
            g.check(len(buffers(second["sched"])) == 3,
                    "the second take scheduled its monitors again, not stale sources",
                    f"{len(buffers(second['sched']))}")
            g.check(len(clicks(second["sched"])) == 4, "and counted in again")
            t8a, t8b = first["take"]["timing"], second["take"]["timing"]
            g.check(abs(t8a["count_in_sec"] - t8b["count_in_sec"]) < 1e-9,
                    "the count-in is the same on both takes")
            g.check(t8b["capture_first_frame"] > t8a["capture_first_frame"],
                    "the second capture starts later on the same clock, as it must",
                    f"{t8a['capture_first_frame']} -> {t8b['capture_first_frame']}")

            # ---------------------------------------------------------------- 9. drift over a longer take
            print("\n[9] A longer take does not drift")
            h.render(monitors=mons[:1], load_nonce=1)
            h.wait_ready()
            r9 = h.record(6.0)
            t9 = r9["take"]["timing"]
            sr9, s9 = decode_wav(r9["take"]["wav_b64"])
            file_dur = len(s9) / sr9
            g.check(abs(file_dur - t9["dry_duration_sec"]) < 0.005,
                    "the file is exactly as long as the frame count says", f"{file_dur:.4f}s")
            g.check(file_dur > 5.5, "six seconds of recording produced six seconds of audio",
                    f"{file_dur:.2f}s")
            g.check(abs(file_dur - t9["wall_sec"]) < 0.6,
                    "the captured length tracks wall-clock time, so no frames were dropped",
                    f"file={file_dur:.2f}s wall={t9['wall_sec']:.2f}s")
            if len(buffers(r9["sched"])) == 1:
                zero9 = t9["music_start_frame"] / t9["sample_rate"]
                g.check(abs(zero9 - buffers(r9["sched"])[0]["when"]) * 1000.0 <= SAMPLE_MS_48K,
                        "musical zero still agrees with the schedule on a long take")

            # ---------------------------------------------------------------- 10. a missing monitor
            print("\n[10] A monitor that cannot be loaded does not produce a half-armed take")
            broken = [h.monitor("/m/a.wav", 4.0), {"id": "gone", "fp": "gone", "url": "/m/missing.wav",
                                                   "start_delay_sec": 0.0, "buffer_offset_sec": 0.0, "volume": 1.0}]
            h.render(monitors=broken, load_nonce=7)
            h.page.wait_for_function("() => window.__recorderState().bk.state === 'failed'", timeout=30000)
            g.check(h.page.locator("#rec").is_disabled(),
                    "Record is refused while one of the parts is missing")
            text = h.page.locator("#status").inner_text()
            g.check("could not be loaded" in text, "and it says so plainly", json.dumps(text[:90]))
            g.check(h.state()["armed"] == 0, "nothing is left armed", f"armed={h.state()['armed']}")

            # ---------------------------------------------------------------- 11. capture constraints
            print("\n[11] The capture safeguards are the shared ones")
            from mission_music_capture import MUSIC_CAPTURE_CONSTRAINTS

            h.render(monitors=mons[:1], constraints=dict(MUSIC_CAPTURE_CONSTRAINTS), load_nonce=1)
            h.wait_ready()
            r11 = h.record(0.6)
            s11 = r11["take"]["timing"].get("settings") or {}
            g.check(s11.get("noiseSuppression") is not True,
                    "noise suppression is not on - it pulls down sustained notes",
                    f"noiseSuppression={s11.get('noiseSuppression')}")
            g.check(s11.get("autoGainControl") is not True,
                    "automatic gain control is not on", f"autoGainControl={s11.get('autoGainControl')}")
            g.check(s11.get("echoCancellation") is not True,
                    "echo cancellation is not on", f"echoCancellation={s11.get('echoCancellation')}")
            g.check(r11["take"]["timing"]["sample_rate"] >= 44100,
                    "the capture rate is a music rate", f"{r11['take']['timing']['sample_rate']} Hz")
        finally:
            if not keep_open:
                h.close()
    return g.report()


if __name__ == "__main__":
    raise SystemExit(run(keep_open="--keep-open" in sys.argv))
