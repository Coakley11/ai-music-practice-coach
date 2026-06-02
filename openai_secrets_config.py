"""Resolve OpenAI API key from Streamlit secrets (SecretsDict-safe) or env."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from suite_storage_config import _coerce_str, _mapping_get

# Bump when loader logic changes (visible in sidebar diagnostics).
OPENAI_SECRETS_LOADER_VERSION = "openai-secrets-v2-secretsdict"

_PRIMARY_SECRET_NAME = "OPENAI_API_KEY"


@dataclass(frozen=True)
class OpenAISecretsProbe:
    """Safe diagnostics — never exposes secret values."""

    streamlit_secrets_available: bool
    openai_api_key_found: bool
    openai_api_key_length_gt_0: bool
    resolved_source: str  # none | env | secrets
    secrets_error: str
    loader_version: str = OPENAI_SECRETS_LOADER_VERSION
    # Hints when the primary name is missing (values never shown).
    nested_openai_section_found: bool = False
    nested_openai_section_has_key: bool = False


def _empty_probe(*, secrets_error: str = "") -> OpenAISecretsProbe:
    return OpenAISecretsProbe(
        streamlit_secrets_available=False,
        openai_api_key_found=False,
        openai_api_key_length_gt_0=False,
        resolved_source="none",
        secrets_error=secrets_error,
    )


def _read_primary_from_secrets_root(root: Any) -> tuple[str, bool]:
    """Return (value, present) for top-level OPENAI_API_KEY only."""
    present = False
    raw: Any = None
    if root is None:
        return "", False
    try:
        if hasattr(root, "get"):
            try:
                raw = root.get(_PRIMARY_SECRET_NAME)
                if raw is not None:
                    present = True
            except Exception:
                raw = None
    except Exception:
        pass
    if raw is None:
        try:
            raw = root[_PRIMARY_SECRET_NAME]
            present = True
        except Exception:
            raw = None
    if raw is None and hasattr(root, _PRIMARY_SECRET_NAME):
        try:
            raw = getattr(root, _PRIMARY_SECRET_NAME)
            present = True
        except Exception:
            raw = None
    return _coerce_str(raw), present


def _nested_openai_hints(root: Any) -> tuple[bool, bool]:
    """Detect [openai] section mistakes without using them for resolution."""
    block: Any = None
    try:
        block = root.get("openai") if hasattr(root, "get") else None
    except Exception:
        block = None
    if block is None:
        try:
            block = root["openai"]
        except Exception:
            block = None
    if block is None:
        return False, False
    nested_val = _mapping_get(block, "OPENAI_API_KEY", "api_key", "key")
    return True, bool(nested_val)


def probe_openai_secrets() -> OpenAISecretsProbe:
    """Inspect how OPENAI_API_KEY would resolve (never returns the key)."""
    env_val = os.environ.get(_PRIMARY_SECRET_NAME, "").strip()
    if env_val:
        return OpenAISecretsProbe(
            streamlit_secrets_available=False,
            openai_api_key_found=True,
            openai_api_key_length_gt_0=True,
            resolved_source="env",
            secrets_error="",
        )

    try:
        import streamlit as st  # noqa: WPS433

        root = st.secrets
        value, present = _read_primary_from_secrets_root(root)
        nested_found, nested_has = _nested_openai_hints(root)
        return OpenAISecretsProbe(
            streamlit_secrets_available=True,
            openai_api_key_found=present,
            openai_api_key_length_gt_0=bool(value),
            resolved_source="secrets" if value else "none",
            secrets_error="",
            nested_openai_section_found=nested_found,
            nested_openai_section_has_key=nested_has,
        )
    except Exception as exc:
        return _empty_probe(secrets_error=f"st.secrets unavailable: {exc}")


def resolve_openai_api_key() -> tuple[str, OpenAISecretsProbe]:
    """Return (api_key, probe). Key is empty when not configured."""
    env_val = os.environ.get(_PRIMARY_SECRET_NAME, "").strip()
    if env_val:
        probe = OpenAISecretsProbe(
            streamlit_secrets_available=False,
            openai_api_key_found=True,
            openai_api_key_length_gt_0=True,
            resolved_source="env",
            secrets_error="",
        )
        return env_val, probe

    try:
        import streamlit as st  # noqa: WPS433

        root = st.secrets
        value, present = _read_primary_from_secrets_root(root)
        nested_found, nested_has = _nested_openai_hints(root)
        value = value.strip()
        probe = OpenAISecretsProbe(
            streamlit_secrets_available=True,
            openai_api_key_found=present,
            openai_api_key_length_gt_0=bool(value),
            resolved_source="secrets" if value else "none",
            secrets_error="",
            nested_openai_section_found=nested_found,
            nested_openai_section_has_key=nested_has,
        )
        return value, probe
    except Exception as exc:
        return "", _empty_probe(secrets_error=f"st.secrets unavailable: {exc}")


def format_openai_secrets_diagnostics(probe: OpenAISecretsProbe) -> list[str]:
    """Human-readable lines for sidebar (no secret values)."""
    lines = [
        f"st.secrets available = {str(probe.streamlit_secrets_available).lower()}",
        f"OPENAI_API_KEY found = {str(probe.openai_api_key_found).lower()}",
        f"OPENAI_API_KEY length > 0 = {str(probe.openai_api_key_length_gt_0).lower()}",
        f"loader = {probe.loader_version} · source = {probe.resolved_source}",
    ]
    if probe.secrets_error:
        lines.append(f"secrets note = {probe.secrets_error}")
    if (
        probe.streamlit_secrets_available
        and not probe.openai_api_key_length_gt_0
        and probe.nested_openai_section_found
    ):
        lines.append(
            "hint = found [openai] section; move key to top-level "
            f'{_PRIMARY_SECRET_NAME} = "..."'
        )
    elif (
        probe.streamlit_secrets_available
        and not probe.openai_api_key_length_gt_0
        and probe.nested_openai_section_has_key
    ):
        lines.append(
            "hint = nested [openai] has a key but app expects top-level "
            f"{_PRIMARY_SECRET_NAME}"
        )
    return lines
