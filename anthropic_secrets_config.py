"""Resolve Anthropic API key from Streamlit secrets (SecretsDict-safe) or env."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from suite_storage_config import _coerce_str, _mapping_get

# Bump when loader logic changes (visible in sidebar diagnostics).
ANTHROPIC_SECRETS_LOADER_VERSION = "anthropic-secrets-v1-keys-scan"

_PRIMARY_SECRET_NAME = "ANTHROPIC_API_KEY"


@dataclass(frozen=True)
class AnthropicSecretsProbe:
    """Safe diagnostics — never exposes secret values."""

    streamlit_secrets_available: bool
    anthropic_api_key_found: bool
    anthropic_api_key_length_gt_0: bool
    resolved_source: str  # none | env | secrets
    secrets_error: str
    loader_version: str = ANTHROPIC_SECRETS_LOADER_VERSION
    top_level_secret_key_names: tuple[str, ...] = ()
    anthropic_key_name_in_secret_list: bool = False
    nested_anthropic_section_found: bool = False
    nested_anthropic_section_has_key: bool = False


def _empty_probe(*, secrets_error: str = "") -> AnthropicSecretsProbe:
    return AnthropicSecretsProbe(
        streamlit_secrets_available=False,
        anthropic_api_key_found=False,
        anthropic_api_key_length_gt_0=False,
        resolved_source="none",
        secrets_error=secrets_error,
    )


def _safe_top_level_secret_key_names(root: Any, *, limit: int = 24) -> tuple[str, ...]:
    """List secret key names only — never values."""
    if root is None:
        return ()
    names: list[str] = []
    try:
        if hasattr(root, "keys"):
            names.extend(str(k) for k in root.keys())
    except Exception:
        pass
    if not names:
        try:
            names.extend(str(k) for k in iter(root))
        except Exception:
            pass
    if not names and hasattr(root, "_secrets"):
        try:
            raw = getattr(root, "_secrets", None)
            if isinstance(raw, Mapping):
                names.extend(str(k) for k in raw.keys())
        except Exception:
            pass
    deduped: list[str] = []
    seen: set[str] = set()
    for name in names:
        low = name.lower()
        if low in seen:
            continue
        seen.add(low)
        deduped.append(name)
    return tuple(sorted(deduped)[:limit])


def _secret_name_exists(root: Any, name: str) -> bool:
    if root is None:
        return False
    try:
        if isinstance(root, Mapping) and name in root:
            return True
    except Exception:
        pass
    try:
        for key in root:
            if str(key) == name:
                return True
    except Exception:
        pass
    try:
        root[name]
        return True
    except KeyError:
        pass
    except Exception:
        pass
    return hasattr(root, name)


def _read_primary_from_secrets_root(root: Any) -> tuple[str, bool]:
    """Return (value, present) for top-level ANTHROPIC_API_KEY only."""
    if root is None:
        return "", False
    value = _mapping_get(root, _PRIMARY_SECRET_NAME)
    if not value:
        try:
            value = _coerce_str(root[_PRIMARY_SECRET_NAME])
        except Exception:
            value = ""
    present = _secret_name_exists(root, _PRIMARY_SECRET_NAME) or bool(value)
    return value, present


def _nested_anthropic_hints(root: Any) -> tuple[bool, bool]:
    """Detect [anthropic] section mistakes without using them for resolution."""
    block: Any = None
    try:
        block = root.get("anthropic") if hasattr(root, "get") else None
    except Exception:
        block = None
    if block is None:
        try:
            block = root["anthropic"]
        except Exception:
            block = None
    if block is None:
        return False, False
    nested_val = _mapping_get(block, "ANTHROPIC_API_KEY", "api_key", "key")
    return True, bool(nested_val)


def _probe_from_secrets_root(root: Any) -> AnthropicSecretsProbe:
    value, present = _read_primary_from_secrets_root(root)
    nested_found, nested_has = _nested_anthropic_hints(root)
    key_names = _safe_top_level_secret_key_names(root)
    value = value.strip()
    return AnthropicSecretsProbe(
        streamlit_secrets_available=True,
        anthropic_api_key_found=present,
        anthropic_api_key_length_gt_0=bool(value),
        resolved_source="secrets" if value else "none",
        secrets_error="",
        top_level_secret_key_names=key_names,
        anthropic_key_name_in_secret_list=_PRIMARY_SECRET_NAME in key_names,
        nested_anthropic_section_found=nested_found,
        nested_anthropic_section_has_key=nested_has,
    )


def probe_anthropic_secrets() -> AnthropicSecretsProbe:
    """Inspect how ANTHROPIC_API_KEY would resolve (never returns the key)."""
    env_val = os.environ.get(_PRIMARY_SECRET_NAME, "").strip()
    if env_val:
        return AnthropicSecretsProbe(
            streamlit_secrets_available=False,
            anthropic_api_key_found=True,
            anthropic_api_key_length_gt_0=True,
            resolved_source="env",
            secrets_error="",
        )

    try:
        import streamlit as st  # noqa: WPS433

        return _probe_from_secrets_root(st.secrets)
    except Exception as exc:
        return _empty_probe(secrets_error=f"st.secrets unavailable: {exc}")


def resolve_anthropic_api_key() -> tuple[str, AnthropicSecretsProbe]:
    """Return (api_key, probe). Key is empty when not configured."""
    env_val = os.environ.get(_PRIMARY_SECRET_NAME, "").strip()
    if env_val:
        probe = AnthropicSecretsProbe(
            streamlit_secrets_available=False,
            anthropic_api_key_found=True,
            anthropic_api_key_length_gt_0=True,
            resolved_source="env",
            secrets_error="",
        )
        return env_val, probe

    try:
        import streamlit as st  # noqa: WPS433

        probe = _probe_from_secrets_root(st.secrets)
        value, _present = _read_primary_from_secrets_root(st.secrets)
        return value.strip(), probe
    except Exception as exc:
        return "", _empty_probe(secrets_error=f"st.secrets unavailable: {exc}")


def format_anthropic_secrets_diagnostics(probe: AnthropicSecretsProbe) -> list[str]:
    """Human-readable lines for sidebar (no secret values)."""
    lines = [
        f"st.secrets available = {str(probe.streamlit_secrets_available).lower()}",
        f"ANTHROPIC_API_KEY found = {str(probe.anthropic_api_key_found).lower()}",
        f"ANTHROPIC_API_KEY length > 0 = {str(probe.anthropic_api_key_length_gt_0).lower()}",
        f"loader = {probe.loader_version} · source = {probe.resolved_source}",
    ]
    if probe.top_level_secret_key_names:
        lines.append(
            "top-level secret key names = "
            + ", ".join(probe.top_level_secret_key_names)
        )
    elif probe.streamlit_secrets_available:
        lines.append("top-level secret key names = (none visible to app)")
    if probe.streamlit_secrets_available:
        lines.append(
            "ANTHROPIC_API_KEY in secret key list = "
            f"{str(probe.anthropic_key_name_in_secret_list).lower()}"
        )
    if probe.secrets_error:
        lines.append(f"secrets note = {probe.secrets_error}")
    if (
        probe.streamlit_secrets_available
        and not probe.anthropic_api_key_length_gt_0
        and not probe.anthropic_key_name_in_secret_list
        and probe.top_level_secret_key_names
    ):
        lines.append(
            f"hint = no top-level {_PRIMARY_SECRET_NAME}; check exact spelling in Secrets"
        )
    if (
        probe.streamlit_secrets_available
        and not probe.anthropic_api_key_length_gt_0
        and probe.nested_anthropic_section_found
    ):
        lines.append(
            "hint = found [anthropic] section; move key to top-level "
            f'{_PRIMARY_SECRET_NAME} = "..."'
        )
    elif (
        probe.streamlit_secrets_available
        and not probe.anthropic_api_key_length_gt_0
        and probe.nested_anthropic_section_has_key
    ):
        lines.append(
            "hint = nested [anthropic] has a key but app expects top-level "
            f"{_PRIMARY_SECRET_NAME}"
        )
    return lines
