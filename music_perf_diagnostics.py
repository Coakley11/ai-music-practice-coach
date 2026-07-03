"""Developer-only Music performance timing (``?dev=1``)."""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Any, Iterator

PERF_TRACE_KEY = "_music_perf_trace"
PERF_RUN_SEQ_KEY = "_music_perf_run_seq"


def _trace(st: Any) -> dict[str, Any]:
    raw = st.session_state.get(PERF_TRACE_KEY)
    if not isinstance(raw, dict):
        raw = {}
        st.session_state[PERF_TRACE_KEY] = raw
    return raw


def begin_run(st: Any, *, page_id: str = "") -> None:
    """Reset per-script-run timing rows."""
    run_seq = int(st.session_state.get("_script_run_seq") or 0)
    if st.session_state.get(PERF_RUN_SEQ_KEY) == run_seq:
        return
    st.session_state[PERF_RUN_SEQ_KEY] = run_seq
    st.session_state[PERF_TRACE_KEY] = {
        "run_seq": run_seq,
        "page_id": str(page_id or "").strip(),
        "spans": [],
        "totals": {},
    }


def record_span(st: Any, name: str, elapsed_ms: float, *, detail: str = "") -> None:
    if not name:
        return
    trace = _trace(st)
    spans: list[dict[str, Any]] = list(trace.get("spans") or [])
    spans.append(
        {
            "name": str(name),
            "ms": round(float(elapsed_ms), 2),
            "detail": str(detail or "").strip(),
        }
    )
    trace["spans"] = spans[-40:]
    totals = dict(trace.get("totals") or {})
    totals[str(name)] = round(float(totals.get(str(name), 0.0)) + float(elapsed_ms), 2)
    trace["totals"] = totals


@contextmanager
def perf_span(st: Any, name: str, *, detail: str = "") -> Iterator[None]:
    t0 = time.perf_counter()
    try:
        yield
    finally:
        record_span(st, name, (time.perf_counter() - t0) * 1000.0, detail=detail)


def merge_external_timings(st: Any, payload: dict[str, Any] | None) -> None:
    if not isinstance(payload, dict):
        return
    for key, val in payload.items():
        if isinstance(val, (int, float)):
            record_span(st, str(key), float(val))


def top_slow_paths(st: Any, *, limit: int = 12) -> list[tuple[str, float]]:
    trace = _trace(st)
    totals = trace.get("totals") if isinstance(trace.get("totals"), dict) else {}
    rows = [(str(k), float(v)) for k, v in totals.items()]
    rows.sort(key=lambda row: row[1], reverse=True)
    return rows[:limit]


def render_perf_sidebar(st: Any) -> None:
    try:
        from music_dev_ui import music_dev_mode_enabled
    except ImportError:
        return
    if not music_dev_mode_enabled(st=st):
        return

    trace = _trace(st)
    spans = trace.get("spans") if isinstance(trace.get("spans"), list) else []
    with st.sidebar.expander("Music performance (dev)", expanded=False):
        st.text(f"run_seq: {trace.get('run_seq', '')}")
        st.text(f"page: {trace.get('page_id', '') or '(unknown)'}")
        st.markdown("**Top slow paths**")
        slow = top_slow_paths(st)
        if not slow:
            st.caption("No spans recorded yet.")
        else:
            for name, ms in slow:
                st.text(f"{name}: {ms:.1f} ms")
        if spans:
            st.markdown("**Last spans**")
            for row in spans[-8:]:
                if not isinstance(row, dict):
                    continue
                label = str(row.get("name") or "")
                ms = float(row.get("ms") or 0.0)
                detail = str(row.get("detail") or "").strip()
                line = f"{label}: {ms:.1f} ms"
                if detail:
                    line += f" ({detail})"
                st.caption(line)
