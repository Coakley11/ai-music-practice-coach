"""Developer diagnostics for Streamlit widget callback registration."""

from __future__ import annotations

import hashlib
import inspect
import logging
from typing import Any

_LOG = logging.getLogger("music.widget_callback")


def _callback_qualname(fn: Any) -> str:
    return str(getattr(fn, "__qualname__", getattr(fn, "__name__", repr(fn))))


def _source_hash(fn: Any) -> str:
    try:
        src = inspect.getsource(fn)
    except (OSError, TypeError):
        src = repr(fn)
    return hashlib.sha256(src.encode("utf-8", errors="replace")).hexdigest()[:12]


def log_widget_callback_registration(
    *,
    widget_key: str,
    callback: Any,
    args: tuple[Any, ...] = (),
    kwargs: dict[str, Any] | None = None,
) -> None:
    kw = dict(kwargs or {})
    try:
        sig = inspect.signature(callback)
        params = sig.parameters
        accepts_var_kw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())
        missing = [k for k in kw if k not in params and not accepts_var_kw]
        if missing:
            _LOG.warning(
                "[widget_callback_registration] widget_key=%s callback=%s signature=%s "
                "kwargs_keys=%s MISMATCH missing=%s",
                widget_key,
                _callback_qualname(callback),
                sig,
                sorted(kw.keys()),
                missing,
            )
        else:
            _LOG.info(
                "[widget_callback_registration] widget_key=%s callback_module=%s callback_name=%s "
                "callback_signature=%s args_count=%s kwargs_keys=%s source_hash=%s",
                widget_key,
                str(getattr(callback, "__module__", "") or ""),
                _callback_qualname(callback),
                sig,
                len(args),
                sorted(kw.keys()),
                _source_hash(callback),
            )
    except (TypeError, ValueError) as exc:
        _LOG.warning(
            "[widget_callback_registration] widget_key=%s callback=%s inspect_failed=%s",
            widget_key,
            _callback_qualname(callback),
            exc,
        )


def log_widget_callback_enter(*, widget_key: str, callback: Any, run_id: str = "") -> None:
    _LOG.info(
        "[widget_callback_enter] widget_key=%s callback_name=%s run_id=%s",
        widget_key,
        _callback_qualname(callback),
        run_id or "—",
    )


def validate_callback_kwargs(callback: Any, kwargs: dict[str, Any] | None) -> list[str]:
    kw = dict(kwargs or {})
    try:
        sig = inspect.signature(callback)
    except (TypeError, ValueError):
        return list(kw.keys())
    params = sig.parameters
    accepts_var_kw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())
    if accepts_var_kw:
        return []
    return [k for k in kw if k not in params]


__all__ = [
    "log_widget_callback_enter",
    "log_widget_callback_registration",
    "validate_callback_kwargs",
]
