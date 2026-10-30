"""Local JSONL usage ledger with reserve/settle accounting. Every failure mode refuses the API call."""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import ROUND_CEILING, Decimal
from pathlib import Path
from typing import Any

from music_coach_ami.claude_settings import PRICING_USD_PER_MTOK, ClaudeSettings

LEDGER_ENV = "AMI_CLAUDE_LEDGER_PATH"
LEDGER_VERSION = 1
INFLIGHT_WINDOW_S = 120.0
LOCK_TIMEOUT_S = 10.0

_RECORD_TYPES = frozenset({"reserve", "settle", "release"})
_PROCESS_LOCK = threading.RLock()


class LedgerError(RuntimeError):
    """Ledger cannot be trusted (unreadable, corrupt, locked, unwritable). Callers must not spend."""


class BudgetRefused(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class Reservation:
    rid: str
    session_id: str
    fingerprint: str
    worst_case_micro_usd: int


@dataclass(frozen=True)
class LedgerState:
    committed_micro_usd: int
    settled_micro_usd: int
    session_calls: int
    total_calls: int
    inflight_same_fingerprint: bool
    unresolved: int


def ledger_path() -> Path:
    override = os.environ.get(LEDGER_ENV, "").strip()
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[1] / "data" / "ami_claude_usage.jsonl"


def new_session_id() -> str:
    return uuid.uuid4().hex[:16]


def micro_to_usd(micro: int) -> float:
    return round(micro / 1_000_000, 6)


def _price(model: str) -> Mapping[str, Decimal]:
    prices = PRICING_USD_PER_MTOK.get(model)
    if prices is None:
        raise LedgerError("unpriced_model")
    return prices


def _token_count(usage: Mapping[str, Any], key: str) -> int:
    value = usage.get(key, 0)
    if value is None:
        return 0
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"bad_usage_{key}")
    return max(0, int(value))


def compute_cost_micro_usd(model: str, usage: Mapping[str, Any]) -> int:
    """Exact cost in micro-USD (USD per MTok equals micro-USD per token), rounded up."""
    prices = _price(model)
    total = (
        _token_count(usage, "input_tokens") * prices["input"]
        + _token_count(usage, "output_tokens") * prices["output"]
        + _token_count(usage, "cache_read_input_tokens") * prices["cache_read"]
        + _token_count(usage, "cache_creation_input_tokens") * prices["cache_write"]
    )
    return int(total.quantize(Decimal(1), rounding=ROUND_CEILING))


def estimate_worst_case_micro_usd(model: str, *, prompt_chars: int, max_output_tokens: int) -> int:
    """Upper bound: one input token per two characters, plus the full output allowance (thinking included)."""
    prices = _price(model)
    input_tokens_ub = (max(0, prompt_chars) + 1) // 2 + 200
    total = input_tokens_ub * prices["input"] + max(0, max_output_tokens) * prices["output"]
    return int(total.quantize(Decimal(1), rounding=ROUND_CEILING))


def _try_lock(fh: Any) -> None:
    if os.name == "nt":
        import msvcrt  # noqa: WPS433

        fh.seek(0)
        msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl  # noqa: WPS433

        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock(fh: Any) -> None:
    try:
        if os.name == "nt":
            import msvcrt  # noqa: WPS433

            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl  # noqa: WPS433

            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass


@contextmanager
def _ledger_lock(path: Path) -> Iterator[None]:
    lock_path = path.with_name(path.name + ".lock")
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        fh = open(lock_path, "a+b")
    except OSError as exc:
        raise LedgerError("lock_open_failed") from exc
    try:
        with _PROCESS_LOCK:
            deadline = time.monotonic() + LOCK_TIMEOUT_S
            while True:
                try:
                    _try_lock(fh)
                    break
                except OSError:
                    if time.monotonic() > deadline:
                        raise LedgerError("lock_timeout") from None
                    time.sleep(0.02)
            try:
                yield
            finally:
                _unlock(fh)
    finally:
        fh.close()


def _read_records(path: Path) -> list[dict[str, Any]]:
    try:
        path.stat()
    except FileNotFoundError:
        return []
    except OSError as exc:
        raise LedgerError("stat_failed") from exc
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise LedgerError("read_failed") from exc
    if raw and not raw.endswith("\n"):
        raise LedgerError("truncated_tail")
    records: list[dict[str, Any]] = []
    for n, line in enumerate(raw.splitlines(), 1):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except ValueError as exc:
            raise LedgerError(f"corrupt_line_{n}") from exc
        if (
            not isinstance(rec, dict)
            or rec.get("v") != LEDGER_VERSION
            or rec.get("type") not in _RECORD_TYPES
            or not isinstance(rec.get("rid"), str)
            or not isinstance(rec.get("ts_epoch"), (int, float))
        ):
            raise LedgerError(f"invalid_record_{n}")
        cost_key = {"reserve": "worst_case_micro_usd", "settle": "cost_micro_usd"}.get(rec["type"])
        if cost_key is not None:
            cost = rec.get(cost_key)
            if isinstance(cost, bool) or not isinstance(cost, int) or cost < 0:
                raise LedgerError(f"invalid_cost_line_{n}")
        records.append(rec)
    return records


def _summarize(
    records: list[dict[str, Any]],
    *,
    session_id: str,
    fingerprint: str,
    now: float,
) -> LedgerState:
    reserves: dict[str, dict[str, Any]] = {}
    resolutions: dict[str, dict[str, Any]] = {}
    for rec in records:
        rid = rec["rid"]
        if rec["type"] == "reserve":
            if rid in reserves:
                raise LedgerError("duplicate_reservation")
            reserves[rid] = rec
        else:
            if rid in resolutions:
                raise LedgerError("double_resolution")
            resolutions[rid] = rec
    if set(resolutions) - set(reserves):
        raise LedgerError("orphan_resolution")

    committed = settled = session_calls = total_calls = unresolved = 0
    inflight = False
    for rid, rec in reserves.items():
        res = resolutions.get(rid)
        if res is None:
            unresolved += 1
            committed += rec["worst_case_micro_usd"]
            total_calls += 1
            if rec.get("sid") == session_id:
                session_calls += 1
                if rec.get("fp") == fingerprint and (now - rec["ts_epoch"]) < INFLIGHT_WINDOW_S:
                    inflight = True
        elif res["type"] == "settle":
            committed += res["cost_micro_usd"]
            settled += res["cost_micro_usd"]
            total_calls += 1
            if rec.get("sid") == session_id:
                session_calls += 1
    return LedgerState(committed, settled, session_calls, total_calls, inflight, unresolved)


def _append(path: Path, record: dict[str, Any]) -> None:
    line = (json.dumps(record, separators=(",", ":"), sort_keys=True) + "\n").encode("utf-8")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "ab") as fh:
            fh.write(line)
            fh.flush()
            os.fsync(fh.fileno())
    except OSError as exc:
        raise LedgerError("append_failed") from exc


def _stamp(now: float) -> dict[str, Any]:
    return {
        "v": LEDGER_VERSION,
        "ts": datetime.fromtimestamp(now, tz=timezone.utc).isoformat(timespec="seconds"),
        "ts_epoch": round(now, 3),
    }


def reserve_budget(
    settings: ClaudeSettings,
    *,
    session_id: str,
    fingerprint: str,
    intent: str,
    model: str,
    worst_case_micro_usd: int,
    now: float | None = None,
) -> Reservation:
    """Atomically check budget, per-session cap and in-flight duplicates, then record the reservation."""
    path = ledger_path()
    clock = time.time() if now is None else now
    with _ledger_lock(path):
        state = _summarize(_read_records(path), session_id=session_id, fingerprint=fingerprint, now=clock)
        if state.inflight_same_fingerprint:
            raise BudgetRefused("duplicate_inflight")
        if state.session_calls >= settings.session_call_cap:
            raise BudgetRefused("session_call_cap")
        if state.committed_micro_usd + worst_case_micro_usd > settings.budget_micro_usd:
            raise BudgetRefused("budget_exhausted")
        rid = uuid.uuid4().hex
        _append(
            path,
            {
                **_stamp(clock),
                "type": "reserve",
                "rid": rid,
                "sid": session_id,
                "fp": fingerprint,
                "intent": intent,
                "model": model,
                "worst_case_micro_usd": int(worst_case_micro_usd),
            },
        )
    return Reservation(rid, session_id, fingerprint, int(worst_case_micro_usd))


def _require_unresolved(records: list[dict[str, Any]], reservation: Reservation, now: float) -> None:
    _summarize(records, session_id=reservation.session_id, fingerprint=reservation.fingerprint, now=now)
    if not any(r["type"] == "reserve" and r["rid"] == reservation.rid for r in records):
        raise LedgerError("unknown_reservation")
    if any(r["type"] != "reserve" and r["rid"] == reservation.rid for r in records):
        raise LedgerError("already_resolved")


def settle(
    reservation: Reservation,
    *,
    model: str,
    usage: Mapping[str, Any],
    request_id: str,
    status: str,
    violations: tuple[str, ...] = (),
    force_cost_micro_usd: int | None = None,
    now: float | None = None,
) -> int:
    """Record actual (or conservative worst-case) cost. Returns cost in micro-USD."""
    path = ledger_path()
    clock = time.time() if now is None else now
    cost = force_cost_micro_usd if force_cost_micro_usd is not None else compute_cost_micro_usd(model, usage)
    with _ledger_lock(path):
        _require_unresolved(_read_records(path), reservation, clock)
        _append(
            path,
            {
                **_stamp(clock),
                "type": "settle",
                "rid": reservation.rid,
                "model": model,
                "request_id": str(request_id or "")[:80],
                "status": status,
                "violations": list(violations)[:12],
                "usage": {
                    k: _token_count(usage, k)
                    for k in (
                        "input_tokens",
                        "output_tokens",
                        "cache_creation_input_tokens",
                        "cache_read_input_tokens",
                    )
                },
                "cost_micro_usd": int(cost),
            },
        )
    return int(cost)


def release(reservation: Reservation, *, status: str, error_type: str = "", now: float | None = None) -> None:
    """The call was provably not billed (rejected before inference)."""
    path = ledger_path()
    clock = time.time() if now is None else now
    with _ledger_lock(path):
        _require_unresolved(_read_records(path), reservation, clock)
        _append(
            path,
            {**_stamp(clock), "type": "release", "rid": reservation.rid, "status": status, "error_type": error_type[:60]},
        )


def usage_summary(settings: ClaudeSettings, session_id: str) -> dict[str, Any]:
    """Dev-panel snapshot. Reports ok=False (never raises) when the ledger cannot be trusted."""
    path = ledger_path()
    try:
        with _ledger_lock(path):
            state = _summarize(_read_records(path), session_id=session_id, fingerprint="", now=time.time())
    except LedgerError as exc:
        return {"ok": False, "error": str(exc), "budget_usd": settings.budget_usd}
    return {
        "ok": True,
        "budget_usd": settings.budget_usd,
        "committed_usd": micro_to_usd(state.committed_micro_usd),
        "settled_usd": micro_to_usd(state.settled_micro_usd),
        "remaining_usd": micro_to_usd(max(0, settings.budget_micro_usd - state.committed_micro_usd)),
        "session_calls": state.session_calls,
        "session_call_cap": settings.session_call_cap,
        "total_calls": state.total_calls,
        "unresolved_reservations": state.unresolved,
    }
