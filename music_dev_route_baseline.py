"""?dev=1 route timing baselines — compare current run vs last run on same route."""

from __future__ import annotations

import time
from typing import Any

from music_dev_nav import _COUNTERS_KEY
from music_dev_perf import _PERF_KEY, _enabled

_BASELINES_KEY = "_music_dev_route_baselines"
_ROUTE_HISTORY_KEY = "_music_dev_route_history"
_ACTIVE_ROUTE_KEY = "_music_dev_route_active"
_ROUTE_T0_KEY = "_music_dev_route_t0"


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(float(v) for v in values)
    if len(ordered) == 1:
        return ordered[0]
    k = (len(ordered) - 1) * (pct / 100.0)
    f = int(k)
    c = min(f + 1, len(ordered) - 1)
    if f == c:
        return ordered[f]
    return ordered[f] + (ordered[c] - ordered[f]) * (k - f)


def route_perf_begin(session: dict[str, Any], route_id: str, *, st_module: Any | None = None) -> None:
    if not _enabled(session, st_module):
        return
    session[_ACTIVE_ROUTE_KEY] = str(route_id)
    session[_ROUTE_T0_KEY] = time.perf_counter()
    session[_PERF_KEY] = []
    session[_COUNTERS_KEY] = {}


def route_perf_end(session: dict[str, Any], route_id: str, *, st_module: Any | None = None) -> None:
    if not _enabled(session, st_module):
        return
    if str(session.get(_ACTIVE_ROUTE_KEY) or "") != str(route_id):
        return
    t0 = float(session.get(_ROUTE_T0_KEY) or 0.0)
    wall_ms = (time.perf_counter() - t0) * 1000.0 if t0 else 0.0
    spans = session.get(_PERF_KEY) if isinstance(session.get(_PERF_KEY), list) else []
    counters = dict(session.get(_COUNTERS_KEY) or {})
    span_total = sum(float(s.get("ms") or 0) for s in spans if isinstance(s, dict) and "ms" in s)
    record = {
        "route_id": route_id,
        "wall_ms": round(wall_ms, 2),
        "span_ms": round(span_total, 2),
        "spans": spans[-12:],
        "counters": counters,
    }
    baselines = session.setdefault(_BASELINES_KEY, {})
    if isinstance(baselines, dict):
        prev = baselines.get(route_id)
        if isinstance(prev, dict):
            record["prev_wall_ms"] = prev.get("wall_ms")
            record["prev_span_ms"] = prev.get("span_ms")
        baselines[route_id] = record
    history = session.setdefault(_ROUTE_HISTORY_KEY, {})
    if isinstance(history, dict):
        samples = history.setdefault(route_id, [])
        if isinstance(samples, list):
            samples.append(float(record["wall_ms"]))
            if len(samples) > 24:
                del samples[: len(samples) - 24]
            record["p50_ms"] = _percentile(samples, 50)
            record["p95_ms"] = _percentile(samples, 95)
            record["samples_n"] = len(samples)
    session.pop(_ACTIVE_ROUTE_KEY, None)
    session.pop(_ROUTE_T0_KEY, None)


def render_route_baseline_caption(st_module: Any, session: dict[str, Any], *, route_id: str) -> None:
    if not _enabled(session, st_module):
        return
    baselines = session.get(_BASELINES_KEY)
    if not isinstance(baselines, dict):
        return
    rec = baselines.get(route_id)
    if not isinstance(rec, dict):
        return
    prev_w = rec.get("prev_wall_ms")
    wall = rec.get("wall_ms")
    delta = ""
    if prev_w is not None and wall is not None:
        try:
            delta = f" (Δ {float(wall) - float(prev_w):+.0f}ms vs last run)"
        except (TypeError, ValueError):
            delta = ""
    counters = rec.get("counters") or {}
    ctr = ", ".join(f"{k}={v}" for k, v in sorted(counters.items()) if v)
    st_module.caption(
        f"DEV route · **{route_id}** · wall **{wall}ms** · spans **{rec.get('span_ms')}ms**{delta}"
        + (f" · p50 **{rec.get('p50_ms')}ms** p95 **{rec.get('p95_ms')}ms**" if rec.get("p50_ms") is not None else "")
        + (f" · {ctr}" if ctr else "")
    )
