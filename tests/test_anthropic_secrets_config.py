"""Anthropic secrets resolution (SecretsDict-safe)."""

from __future__ import annotations

from anthropic_secrets_config import (
    ANTHROPIC_SECRETS_LOADER_VERSION,
    format_anthropic_secrets_diagnostics,
    resolve_anthropic_api_key,
)


class _SecretsLike:
    def __init__(self, data: dict) -> None:
        self._data = data

    def get(self, name: str, default=None):
        return self._data.get(name, default)

    def keys(self):
        return self._data.keys()

    def __getitem__(self, name: str):
        return self._data[name]

    def __iter__(self):
        return iter(self._data)


def test_resolve_from_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-env")
    key, probe = resolve_anthropic_api_key()
    assert key == "sk-ant-env"
    assert probe.resolved_source == "env"
    assert probe.anthropic_api_key_length_gt_0 is True


def test_resolve_from_secrets_get(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    class _St:
        secrets = _SecretsLike({"ANTHROPIC_API_KEY": "sk-ant-from-get"})

    monkeypatch.setitem(__import__("sys").modules, "streamlit", _St)
    key, probe = resolve_anthropic_api_key()
    assert key == "sk-ant-from-get"
    assert probe.resolved_source == "secrets"
    assert probe.streamlit_secrets_available is True


def test_resolve_from_secrets_bracket_only(monkeypatch):
    """Streamlit Cloud SecretsDict may not support .get with defaults."""

    class _BracketOnly:
        def get(self, name: str, default=None):
            raise TypeError("no get")

        def __getitem__(self, name: str):
            if name == "ANTHROPIC_API_KEY":
                return "sk-ant-bracket"
            raise KeyError(name)

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    class _St:
        secrets = _BracketOnly()

    monkeypatch.setitem(__import__("sys").modules, "streamlit", _St)
    key, probe = resolve_anthropic_api_key()
    assert key == "sk-ant-bracket"
    assert probe.anthropic_api_key_found is True


def test_missing_key_resolves_empty(monkeypatch):
    """No env var and no secrets configured — key resolves empty, never raises."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    class _St:
        secrets = _SecretsLike({})

    monkeypatch.setitem(__import__("sys").modules, "streamlit", _St)
    key, probe = resolve_anthropic_api_key()
    assert key == ""
    assert probe.resolved_source == "none"
    assert probe.anthropic_api_key_found is False
    assert probe.anthropic_api_key_length_gt_0 is False


def test_missing_key_no_streamlit_available(monkeypatch):
    """No env var and streamlit import itself fails — still resolves empty, not an error."""
    import builtins

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    real_import = builtins.__import__

    def _blocked_import(name, *args, **kwargs):
        if name == "streamlit":
            raise ModuleNotFoundError("no streamlit in this env")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _blocked_import)
    key, probe = resolve_anthropic_api_key()
    assert key == ""
    assert probe.streamlit_secrets_available is False
    assert "unavailable" in probe.secrets_error


def test_diagnostics_never_include_key():
    from anthropic_secrets_config import AnthropicSecretsProbe

    probe = AnthropicSecretsProbe(
        streamlit_secrets_available=True,
        anthropic_api_key_found=True,
        anthropic_api_key_length_gt_0=True,
        resolved_source="secrets",
        secrets_error="",
        loader_version=ANTHROPIC_SECRETS_LOADER_VERSION,
        top_level_secret_key_names=("ANTHROPIC_API_KEY", "suite_activity"),
        anthropic_key_name_in_secret_list=True,
    )
    text = "\n".join(format_anthropic_secrets_diagnostics(probe))
    assert "sk-ant-" not in text
    assert "ANTHROPIC_API_KEY found = true" in text


def test_lists_top_level_key_names_without_values(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    class _St:
        secrets = _SecretsLike(
            {"suite_activity": {"x": 1}, "ANTHROPIC_API_KEY": "sk-ant-hidden"}
        )

    monkeypatch.setitem(__import__("sys").modules, "streamlit", _St)
    _key, probe = resolve_anthropic_api_key()
    assert _key == "sk-ant-hidden"
    assert "ANTHROPIC_API_KEY" in probe.top_level_secret_key_names
    assert "sk-ant-hidden" not in format_anthropic_secrets_diagnostics(probe)
