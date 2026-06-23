"""Backing-track generation helpers — timing profile and audio prep caches."""

from __future__ import annotations

import base64
import html
import time
from dataclasses import asdict, dataclass, field
from typing import Any

from studio_cache import session_cache_get, session_cache_get_or_set

BACKING_TIMING_TRACE_KEY = "_backing_timing_trace"

__all__ = (
    "BACKING_TIMING_TRACE_KEY",
    "BackingGenProfile",
    "clear_backing_timing_trace",
    "prepare_wav_b64",
    "profile_elapsed_ms",
    "record_backing_timing_event",
    "render_backing_generation_debug",
)


@dataclass
class BackingGenProfile:
    """Timing breakdown for one generate pass (developer diagnostics)."""

    events_ms: float = 0.0
    timeline_ms: float = 0.0
    synthesis_ms: float = 0.0
    b64_ms: float = 0.0
    total_ms: float = 0.0
    cache_hit_wav: bool = False
    cache_hit_timeline: bool = False
    cache_hit_b64: bool = False
    bar_count: int = 0
    wav_kb: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row["extra"] = dict(self.extra)
        return row


def prepare_wav_b64(session_state: dict, signature: tuple, wav: bytes) -> tuple[str, float, bool]:
    """Encode WAV to base64 once; cache in session for fast Play reruns."""
    if session_cache_get(session_state, "backing_wav_b64", signature) is not None:
        return str(session_cache_get(session_state, "backing_wav_b64", signature)), 0.0, True
    t0 = time.perf_counter()
    encoded = base64.b64encode(wav).decode("ascii")
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    session_cache_get_or_set(
        session_state,
        "backing_wav_b64",
        signature,
        lambda: encoded,
        max_entries=8,
    )
    return encoded, elapsed_ms, False


def profile_elapsed_ms(start: float) -> float:
    return (time.perf_counter() - start) * 1000.0


def clear_backing_timing_trace(session_state: dict[str, Any]) -> None:
    session_state.pop(BACKING_TIMING_TRACE_KEY, None)


def record_backing_timing_event(
    session_state: dict[str, Any],
    event: str,
    *,
    signature: tuple | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Record a named backing perf event for ?dev=1 (monotonic ms since generate_start)."""
    trace = session_state.setdefault(BACKING_TIMING_TRACE_KEY, {})
    if not isinstance(trace, dict):
        trace = {}
        session_state[BACKING_TIMING_TRACE_KEY] = trace
    now_ms = time.perf_counter() * 1000.0
    start_ms = float(trace.get("generate_start_ms") or 0.0)
    if event == "generate_start" or not start_ms:
        start_ms = now_ms
        trace["generate_start_ms"] = start_ms
    row: dict[str, Any] = {
        "at_ms": now_ms,
        "since_generate_start_ms": max(0.0, now_ms - start_ms),
    }
    if signature is not None:
        row["signature"] = repr(signature)
    if extra:
        row.update(extra)
    trace[event] = row
    trace["last_event"] = event
    return row


def _format_timing_trace(trace: dict[str, Any]) -> list[str]:
    order = ("generate_start", "generate_complete", "audio_load_complete", "play_start")
    lines: list[str] = []
    for name in order:
        row = trace.get(name)
        if not isinstance(row, dict):
            continue
        delta = row.get("since_generate_start_ms")
        suffix = f" (+{float(delta):.0f} ms)" if delta is not None else ""
        lines.append(f"- **{name}**{suffix}")
        if row.get("session_cache_hit"):
            lines.append("  - session WAV cache hit")
        if row.get("module_cache_hit_wav"):
            lines.append("  - module WAV cache hit")
        if row.get("module_cache_hit_timeline"):
            lines.append("  - module timeline cache hit")
        if row.get("module_cache_hit_b64"):
            lines.append("  - b64 cache hit")
    last = trace.get("last_event")
    if last and last not in order:
        lines.append(f"- last event: `{last}`")
    return lines


def render_backing_generation_debug(
    st: Any,
    *,
    profile: dict | None,
    developer_mode: bool = False,
) -> None:
    """Developer expander for last backing generation timing profile."""
    timing_trace = st.session_state.get(BACKING_TIMING_TRACE_KEY)
    if not developer_mode or (not profile and not timing_trace):
        return
    with st.expander("Developer Debug: Backing generation", expanded=False):
        if profile:
            st.markdown(
                "\n".join(
                    [
                        f"- Timeline build: **{profile.get('timeline_ms', 0):.1f} ms**"
                        + (" (cache hit)" if profile.get("cache_hit_timeline") else ""),
                        f"- Synthesis: **{profile.get('synthesis_ms', 0):.1f} ms**"
                        + (" (cache hit)" if profile.get("cache_hit_wav") else ""),
                        f"- Base64 prep: **{profile.get('b64_ms', 0):.1f} ms**"
                        + (" (cache hit)" if profile.get("cache_hit_b64") else ""),
                        f"- Total: **{profile.get('total_ms', 0):.1f} ms**",
                        f"- Bars rendered: **{profile.get('bar_count', 0)}**",
                        f"- WAV size: **{profile.get('wav_kb', 0):.0f} KB**",
                    ]
                )
            )
        if isinstance(timing_trace, dict) and timing_trace:
            st.markdown("**Timing trace (monotonic from generate_start)**")
            st.markdown("\n".join(_format_timing_trace(timing_trace)))
