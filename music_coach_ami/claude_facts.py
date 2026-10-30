"""Verified active-song facts handed to Claude. Built only from the AMI chart snapshot and grounded response."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any

from music_coach_ami.claude_brief import build_brief
from music_coach_ami.claude_pitch import PitchReference, build_pitch_reference
from music_coach_ami.types import CoachIntent, CoachRequest, CoachResponse

PROMPT_VERSION = "song-enrich-v3"
_MAX_EXISTING_ANSWER_CHARS = 1800
_MAX_CHORDS_PER_SECTION = 32
_MAX_SECTIONS_WITHOUT_TARGET = 6
_MAX_SECTION_NAMES = 12
_BPM_IN_TEXT = re.compile(r"(\d{2,3})\s*BPM", re.I)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()


def _norm_label(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(text or "").lower())


_CHART_TOKEN = re.compile(r"^(?P<chord>[A-G][^:\s]*)(?::\d+(?:\.\d+)?p?)?$")


def split_chord_entry(entry: Any) -> list[str]:
    """Chart slots may hold 'Dm7', 'Dm7|G7', 'Dm7 G7' or beat-annotated 'G:3.5' / 'C:0.5p'.

    Returns bare chord symbols only; durations, pickup markers and non-chord tokens (rests, N.C.) are dropped.
    """
    chords: list[str] = []
    for tok in re.split(r"[\s|]+", str(entry or "").strip()):
        match = _CHART_TOKEN.match(tok)
        if match and not (chords and chords[-1] == match.group("chord")):
            chords.append(match.group("chord"))
    return chords


@dataclass(frozen=True)
class FactSheet:
    song_title: str
    section: str
    sections: tuple[tuple[str, tuple[str, ...]], ...]
    section_names: tuple[str, ...]
    practice_key: str
    original_key: str
    tempo_bpm: int | None
    allowed_bpm: tuple[int, ...]
    instrument: str
    level: str
    practice_focus: str
    existing_answer: str
    pitch_ref: PitchReference = field(default_factory=PitchReference)
    brief: dict[str, Any] = field(default_factory=dict)

    def allowed_chords(self) -> frozenset[str]:
        return frozenset(c for _name, chords in self.sections for c in chords)

    def allowed_keys(self) -> frozenset[str]:
        return frozenset(_norm(k) for k in (self.practice_key, self.original_key) if k)

    def allowed_sections(self) -> frozenset[str]:
        names = list(self.section_names) + [self.section] + [n for n, _c in self.sections]
        return frozenset(_norm(n) for n in names if n)

    def facts_json(self) -> str:
        return json.dumps(
            {
                "song_title": self.song_title,
                "target_section": self.section or None,
                "chords_by_section": {name: list(chords) for name, chords in self.sections},
                "all_section_names": list(self.section_names),
                "practice_key": self.practice_key,
                "original_key": self.original_key,
                "tempo_bpm": self.tempo_bpm,
                "instrument": self.instrument,
                "level": self.level,
                "practice_focus": self.practice_focus,
                "pitch_reference": self.pitch_ref.as_fact(),
                "coaching_brief": self.brief,
            },
            ensure_ascii=False,
            sort_keys=True,
        )

    def fingerprint(self, model: str) -> str:
        blob = json.dumps(
            [PROMPT_VERSION, model, self.facts_json(), self.existing_answer], ensure_ascii=False
        )
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:24]


def _existing_answer_text(resp: CoachResponse) -> str:
    parts = [resp.direct_answer, *resp.practice_steps, resp.suggested_next_action]
    text = "\n".join(str(p).strip() for p in parts if str(p or "").strip())
    return text[:_MAX_EXISTING_ANSWER_CHARS]


def build_fact_sheet(req: CoachRequest, resp: CoachResponse) -> tuple[FactSheet | None, str]:
    """Return (facts, 'ok') or (None, skip_reason). Never guesses: unverified context means no enrichment."""
    if req.intent != CoachIntent.SONG_COACHING:
        return None, "intent_not_supported"
    diag = resp.diagnostics if isinstance(resp.diagnostics, dict) else {}
    title = str(diag.get("display_song_title") or "").strip()
    if not diag.get("song_grounded") or not title:
        return None, "not_song_grounded"

    section_res = diag.get("section_resolution")
    if isinstance(section_res, dict) and section_res.get("ambiguous"):
        return None, "section_ambiguous"

    chart = req.context.extra.get("chart_snapshot") if isinstance(req.context.extra, dict) else None
    if not isinstance(chart, dict) or not chart.get("chart_available"):
        return None, "no_verified_chart"
    if not chart.get("sections_in_practice_key"):
        return None, "chart_not_in_practice_key"
    chart_sections = chart.get("chart_sections")
    if not isinstance(chart_sections, dict) or not chart_sections:
        return None, "no_verified_chart"

    by_label = {_norm_label(name): str(name) for name in chart_sections}
    section_label = ""
    target_name = ""
    try:
        from music_coach_ami.song_grounding import musician_facing_section_label, resolved_section_for_header

        wanted_raw = resolved_section_for_header(req, resp)
        # "Full Song" and similar labels mean no specific target section.
        wanted_display = musician_facing_section_label(wanted_raw) if wanted_raw else ""
    except Exception:
        wanted_raw = wanted_display = ""
    if wanted_display:
        target_name = by_label.get(_norm_label(wanted_raw)) or by_label.get(_norm_label(wanted_display)) or ""
        if not target_name:
            return None, "section_not_in_chart"
        section_label = target_name

    def _chords(name: str) -> tuple[str, ...]:
        tokens: list[str] = []
        for entry in chart_sections.get(name) or []:
            for chord in split_chord_entry(entry):
                if not tokens or tokens[-1] != chord:
                    tokens.append(chord)
        return tuple(tokens[:_MAX_CHORDS_PER_SECTION])

    if target_name:
        sections = ((target_name, _chords(target_name)),)
    else:
        sections = tuple((str(n), _chords(str(n))) for n in list(chart_sections)[:_MAX_SECTIONS_WITHOUT_TARGET])
    if not any(chords for _n, chords in sections):
        return None, "no_verified_chart"

    tempo_raw = chart.get("bpm") or req.context.tempo_bpm
    try:
        tempo = int(tempo_raw) if tempo_raw else None
    except (TypeError, ValueError):
        tempo = None
    existing = _existing_answer_text(resp)
    bpms = {int(m) for m in _BPM_IN_TEXT.findall(existing)}
    if tempo:
        bpms.add(tempo)

    practice_key = str(chart.get("practice_key") or req.context.current_practice_key or "").strip()
    original_key = str(chart.get("original_key") or req.context.song_original_key or "").strip()
    all_chords = tuple(dict.fromkeys(c for _n, chords in sections for c in chords))
    instrument = str(req.context.instrument or "").strip()
    level = str(req.context.level or "").strip()
    focus = str(req.context.practice_focus or "").strip()
    extra = req.context.extra if isinstance(req.context.extra, dict) else {}
    pitch_ref = build_pitch_reference(
        instrument,
        extra.get("session_ref"),
        keys=tuple(dict.fromkeys(k for k in (practice_key, original_key) if k)),
        chords=all_chords,
    )
    brief = build_brief(
        song_title=title,
        section=section_label,
        instrument=instrument,
        level=level,
        practice_focus=focus,
        chords=all_chords,
    )

    return (
        FactSheet(
            song_title=title,
            section=section_label,
            sections=sections,
            section_names=tuple(str(n) for n in list(chart_sections)[:_MAX_SECTION_NAMES]),
            practice_key=practice_key,
            original_key=original_key,
            tempo_bpm=tempo,
            allowed_bpm=tuple(sorted(bpms)),
            instrument=instrument,
            level=level,
            practice_focus=focus,
            existing_answer=existing,
            pitch_ref=pitch_ref,
            brief=brief,
        ),
        "ok",
    )
