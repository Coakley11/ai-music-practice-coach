"""Developer-only Claude enrichment settings. Everything is OFF unless explicitly enabled."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

DEFAULT_MODEL = "claude-sonnet-5-5"

# USD per million tokens == micro-USD per token. Verified against the Anthropic pricing page 2026-10-29.
PRICING_AS_OF = "2026-10-29"
PRICING_USD_PER_MTOK: dict[str, dict[str, Decimal]] = {
    "claude-sonnet-5-5": {
        "input": Decimal("2.00"),
        "output": Decimal("10.00"),
        "cache_read": Decimal("0.10"),
        "cache_write": Decimal("2.50"),
    },
}

HARD_BUDGET_CEILING_USD = 5.0
HARD_SESSION_CALL_CEILING = 50
_EFFORTS = frozenset({"low", "medium", "high"})
_TRUE = frozenset({"1", "true", "yes", "on"})


@dataclass(frozen=True)
class ClaudeSettings:
    master_enabled: bool
    model: str
    max_output_tokens: int
    effort: str
    budget_usd: float
    session_call_cap: int
    timeout_s: float

    @property
    def model_priced(self) -> bool:
        return self.model in PRICING_USD_PER_MTOK

    @property
    def budget_micro_usd(self) -> int:
        return int(round(self.budget_usd * 1_000_000))


def _secret_value(name: str) -> str:
    env = os.environ.get(name, "").strip()
    if env:
        return env
    try:
        import streamlit as st  # noqa: WPS433

        root = st.secrets
        try:
            value = root[name]
        except Exception:
            value = root.get(name) if hasattr(root, "get") else None
        if isinstance(value, Mapping):
            return ""
        return "" if value is None else str(value).strip()
    except Exception:
        return ""


def _as_bool(raw: str) -> bool:
    return raw.strip().lower() in _TRUE


def _as_float(raw: str, default: float, lo: float, hi: float) -> float:
    try:
        return min(hi, max(lo, float(raw)))
    except (TypeError, ValueError):
        return default


def _as_int(raw: str, default: int, lo: int, hi: int) -> int:
    try:
        return min(hi, max(lo, int(float(raw))))
    except (TypeError, ValueError):
        return default


def load_claude_settings() -> ClaudeSettings:
    effort = _secret_value("AMI_CLAUDE_EFFORT").lower() or "low"
    return ClaudeSettings(
        master_enabled=_as_bool(_secret_value("AMI_CLAUDE_ENABLED")),
        model=_secret_value("AMI_CLAUDE_MODEL") or DEFAULT_MODEL,
        max_output_tokens=_as_int(_secret_value("AMI_CLAUDE_MAX_OUTPUT_TOKENS"), 1500, 256, 4000),
        effort=effort if effort in _EFFORTS else "low",
        budget_usd=_as_float(
            _secret_value("AMI_CLAUDE_BUDGET_USD"),
            HARD_BUDGET_CEILING_USD,
            0.0,
            HARD_BUDGET_CEILING_USD,
        ),
        session_call_cap=_as_int(
            _secret_value("AMI_CLAUDE_SESSION_CALL_CAP"), 10, 0, HARD_SESSION_CALL_CEILING
        ),
        timeout_s=_as_float(_secret_value("AMI_CLAUDE_TIMEOUT_S"), 20.0, 5.0, 60.0),
    )


def enrichment_gate(settings: ClaudeSettings, session_state: Any) -> tuple[bool, str]:
    """Config and developer gates only. Key, budget and ledger checks happen later and fail closed."""
    if not settings.master_enabled:
        return False, "disabled_by_config"
    if session_state.get("_ami_claude_dev_mode") is not True:
        return False, "not_developer_mode"
    if session_state.get("ami_claude_dev_enabled") is not True:
        return False, "dev_toggle_off"
    if not settings.model_priced:
        return False, "unpriced_model"
    return True, "enabled"
