"""Slice A evidence generator for Practice Melody.

Generates representative structured melodies for several real, materially
different Catalog songs at all three levels (Beginner/Intermediate/Advanced)
using ``practice_melody_generator.generate_practice_melody``, and writes:

  * one JSON file per (song, level) with the full structured melody, for
    manual inspection of notes/rhythm/measures/roles;
  * one short WAV file per (song, level) — a plain sine-tone render, purely
    as a lightweight way to *hear* the difference between levels and songs.
    This is a diagnostic aid only, not part of the Practice Melody data
    model or generation engine, and uses no extra dependencies beyond the
    standard library.
  * a combined ``report.md`` summarizing what was generated.

Run with:  python scripts/practice_melody_demo.py

Only chord symbols, key, tempo and section names are read from each song's
existing chart (the same data Practice/Backing already use) — no melody or
audio data belonging to the real songs is read, used, or referenced.
"""

from __future__ import annotations

import json
import math
import struct
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from practice_melody_generator import generate_practice_melody  # noqa: E402
from practice_melody_model import validate_practice_melody  # noqa: E402
from song_catalog.curated_songs import curated_song_records  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent / "evidence-practice-melody"

# Four materially different real Catalog songs: major/minor keys, pop/jazz/
# rock genres, slow ballad to uptempo bossa, and forms with real repeats
# (e.g. Perfect's Verse 1/2 share the same progression).
DEMO_SONGS: tuple[tuple[str, str], ...] = (
    ("Perfect", "Ed Sheeran"),
    ("Blue Bossa", "Kenny Dorham"),
    ("Hotel California", "Eagles"),
    ("Wonderwall", "Oasis"),
)

LEVELS: tuple[str, ...] = ("Beginner", "Intermediate", "Advanced")

SAMPLE_RATE = 22050
# WAV previews are a diagnostic listening aid only -- full-length charts
# (e.g. Hotel California's chart alone is 480 measures) would render to
# unwieldy multi-minute files, so previews are capped; the JSON output next
# to each WAV always has the complete, un-truncated structured melody.
MAX_PREVIEW_SECONDS = 40.0


def _slug(text: str) -> str:
    return "".join(c.lower() if c.isalnum() else "-" for c in text).strip("-")


def _midi_to_freq(midi: int) -> float:
    return 440.0 * (2.0 ** ((midi - 69) / 12.0))


def render_wav(melody, path: Path) -> None:
    """Plain sine-tone render of every sounding event, in order, with a short
    linear fade in/out on each note to avoid clicks. Tempo comes straight
    from the melody's own tempo_bpm so Beginner/Advanced differences in
    rhythmic density are audible, not just visible in the JSON."""
    seconds_per_beat = 60.0 / max(1.0, melody.tempo_bpm)
    max_samples = int(MAX_PREVIEW_SECONDS * SAMPLE_RATE)
    samples: list[float] = []
    done = False
    for section in melody.sections:
        if done:
            break
        for event in section.events:
            n = max(1, int(event.duration_beats * seconds_per_beat * SAMPLE_RATE))
            n = min(n, max_samples - len(samples))
            if n <= 0:
                done = True
                break
            if event.is_rest or event.midi is None:
                samples.extend([0.0] * n)
                continue
            freq = _midi_to_freq(event.midi)
            fade = max(1, min(n // 6, int(0.015 * SAMPLE_RATE)))
            for i in range(n):
                amp = 0.28
                if i < fade:
                    amp *= i / fade
                elif i > n - fade:
                    amp *= (n - i) / fade
                samples.append(amp * math.sin(2.0 * math.pi * freq * (i / SAMPLE_RATE)))
            if len(samples) >= max_samples:
                done = True
                break
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(SAMPLE_RATE)
        frames = b"".join(struct.pack("<h", max(-32767, min(32767, int(s * 32767)))) for s in samples)
        wav_file.writeframes(frames)


def _find_song(title: str, artist: str) -> dict:
    for record in curated_song_records():
        if record.get("title") == title and record.get("artist") == artist:
            return record
    raise KeyError(f"{title} / {artist} not found in curated_song_records()")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report_lines: list[str] = ["# Practice Melody — Slice A representative output\n"]

    for title, artist in DEMO_SONGS:
        record = _find_song(title, artist)
        sections = record.get("sections") or {}
        section_order = record.get("section_order") or list(sections.keys())
        key_center = record.get("key") or "C"
        extensions = record.get("extensions") or {}
        tempo_bpm = float(extensions.get("default_bpm") or 100)
        style = f"{record.get('genre') or ''} / {extensions.get('default_groove') or ''}".strip(" /")
        song_id = f"catalog:{_slug(title)}:{_slug(artist)}"

        report_lines.append(f"## {title} — {artist}")
        report_lines.append(
            f"key={key_center}  tempo={tempo_bpm:g} bpm  style={style!r}  "
            f"sections={list(sections.keys())}\n"
        )

        for level in LEVELS:
            melody = generate_practice_melody(
                song_id=song_id,
                song_title=f"{title} — {artist}",
                sections=sections,
                section_order=section_order,
                key_center=key_center,
                level=level,
                tempo_bpm=tempo_bpm,
                style=style,
            )
            problems = validate_practice_melody(melody)

            slug = f"{_slug(title)}-{_slug(level)}"
            json_path = OUT_DIR / f"{slug}.json"
            json_path.write_text(json.dumps(melody.to_dict(), indent=2), encoding="utf-8")

            wav_path = OUT_DIR / f"{slug}.wav"
            render_wav(melody, wav_path)

            sounding = [e for s in melody.sections for e in s.events if not e.is_rest]
            roles: dict[str, int] = {}
            for e in sounding:
                roles[e.tone_role] = roles.get(e.tone_role, 0) + 1
            repeats = [s.section_id for s in melody.sections if s.repeat_of]

            report_lines.append(
                f"- **{level}**: seed={melody.seed} notes={len(sounding)} "
                f"roles={roles} repeated_sections={repeats or 'none'} "
                f"structural_problems={problems or 'none'} -> `{json_path.name}`, `{wav_path.name}`"
            )
        report_lines.append("")

    report_path = OUT_DIR / "report.md"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"Wrote {report_path} and per-song JSON/WAV files to {OUT_DIR}")


if __name__ == "__main__":
    main()
