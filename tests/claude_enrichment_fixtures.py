"""Shared offline fixtures for Claude enrichment tests. Nothing here touches the network."""

from __future__ import annotations

import json
from typing import Any

from music_coach_ami.claude_client import TransportError, TransportResult
from music_coach_ami.claude_settings import ClaudeSettings
from music_coach_ami.types import (
    CoachConstraints,
    CoachContext,
    CoachIntent,
    CoachRequest,
    CoachResponse,
    ExtractedEntities,
)

FAKE_KEY = "sk-ant-test-FAKEKEY-do-not-use-0000000000"

CHART = {
    "chart_available": True,
    "sections_in_practice_key": True,
    "chart_sections": {
        "Verse": ["Dm7", "G7", "Cmaj7", "Cmaj7"],
        "Chorus": ["Am7", "D7|G7", "Cmaj7"],
    },
    "practice_key": "C",
    "original_key": "C",
    "bpm": 100,
}


def make_settings(**overrides: Any) -> ClaudeSettings:
    base = dict(
        master_enabled=True,
        model="claude-sonnet-5-5",
        max_output_tokens=1500,
        effort="low",
        budget_usd=5.0,
        session_call_cap=10,
        timeout_s=20.0,
    )
    base.update(overrides)
    return ClaudeSettings(**base)


def make_req(*, intent: CoachIntent = CoachIntent.SONG_COACHING, chart: dict | None = None) -> CoachRequest:
    chart_snapshot = CHART if chart is None else chart
    return CoachRequest(
        raw_question="How should I practice the verse of this song?",
        normalized_question="how should i practice the verse of this song?",
        intent=intent,
        confidence=0.9,
        entities=ExtractedEntities(),
        constraints=CoachConstraints(),
        context=CoachContext(
            instrument="Saxophone",
            level="Intermediate",
            practice_focus="Chord changes",
            active_song_title="Autumn Leaves",
            active_song_pick_key="catalog:autumn",
            song_original_key="C",
            current_practice_key="C",
            active_section="Verse",
            tempo_bpm=100,
            extra={"chart_snapshot": chart_snapshot},
        ),
    )


def make_resp(*, section: str = "Verse", grounded: bool = True) -> CoachResponse:
    return CoachResponse(
        intent=CoachIntent.SONG_COACHING,
        direct_answer=f"For **Autumn Leaves**, practice **{section}** as the target for this question.",
        practice_steps=[
            f"Loop **4–8 bars** of **{section}** with a metronome or Backing.",
            "Start at **75 BPM** (~75% of 100) if transitions stumble.",
        ],
        suggested_next_action="Set Backing scope and log the session in Practice Log.",
        source_solver="SongCoachSolver",
        confidence=0.8,
        diagnostics={
            "song_grounded": grounded,
            "display_song_title": "Autumn Leaves",
            "resolved_section": section,
            "section_resolution": {"ok": True, "explicit": True, "section": section, "source": "explicit_question"},
        },
    )


GOOD_PAYLOAD = {
    "why_this_fits": "The {{section:Verse}} moves through {{chord:Dm7}} and {{chord:G7}}, so smooth changes matter most.",
    "guidance": [
        "Loop {{chord:Dm7}} to {{chord:G7}} slowly until the move feels automatic.",
        "Count the change aloud before you play it, starting at {{bpm:75}} BPM.",
    ],
    "listen_for": ["Whether the change lands on time before the next chord."],
}

USAGE = {
    "input_tokens": 1200,
    "output_tokens": 400,
    "cache_creation_input_tokens": 0,
    "cache_read_input_tokens": 0,
}


class FakeTransport:
    """Records calls; returns a canned result or raises a canned TransportError."""

    def __init__(
        self,
        payload: Any = None,
        *,
        text: str | None = None,
        stop_reason: str = "end_turn",
        usage: dict[str, int] | None = None,
        error: TransportError | None = None,
        request_id: str = "req_fake_001",
    ) -> None:
        self.payload = GOOD_PAYLOAD if payload is None else payload
        self.text = text
        self.stop_reason = stop_reason
        self.usage = dict(USAGE if usage is None else usage)
        self.error = error
        self.request_id = request_id
        self.calls: list[dict[str, Any]] = []

    def complete(self, **kwargs: Any) -> TransportResult:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        text = self.text if self.text is not None else json.dumps(self.payload)
        return TransportResult(
            text=text,
            usage=dict(self.usage),
            request_id=self.request_id,
            stop_reason=self.stop_reason,
            model=kwargs.get("model", ""),
        )

    def factory(self):
        return lambda _key: self
