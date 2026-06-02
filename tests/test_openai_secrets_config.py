"""OpenAI secrets resolution (SecretsDict-safe)."""

from __future__ import annotations

from openai_secrets_config import (
    OPENAI_SECRETS_LOADER_VERSION,
    format_openai_secrets_diagnostics,
    resolve_openai_api_key,
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


class _AttrSecrets:
    OPENAI_API_KEY = "sk-test-from-attr"


def test_resolve_from_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env")
    key, probe = resolve_openai_api_key()
    assert key == "sk-env"
    assert probe.resolved_source == "env"
    assert probe.openai_api_key_length_gt_0 is True


def test_resolve_from_secrets_get(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    class _St:
        secrets = _SecretsLike({"OPENAI_API_KEY": "sk-from-get"})

    monkeypatch.setitem(__import__("sys").modules, "streamlit", _St)
    key, probe = resolve_openai_api_key()
    assert key == "sk-from-get"
    assert probe.resolved_source == "secrets"
    assert probe.streamlit_secrets_available is True


def test_resolve_from_secrets_bracket_only(monkeypatch):
    """Streamlit Cloud SecretsDict may not support .get with defaults."""

    class _BracketOnly:
        def get(self, name: str, default=None):
            raise TypeError("no get")

        def __getitem__(self, name: str):
            if name == "OPENAI_API_KEY":
                return "sk-bracket"
            raise KeyError(name)

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    class _St:
        secrets = _BracketOnly()

    monkeypatch.setitem(__import__("sys").modules, "streamlit", _St)
    key, probe = resolve_openai_api_key()
    assert key == "sk-bracket"
    assert probe.openai_api_key_found is True


def test_diagnostics_never_include_key():
    from openai_secrets_config import OpenAISecretsProbe

    probe = OpenAISecretsProbe(
        streamlit_secrets_available=True,
        openai_api_key_found=True,
        openai_api_key_length_gt_0=True,
        resolved_source="secrets",
        secrets_error="",
        loader_version=OPENAI_SECRETS_LOADER_VERSION,
        top_level_secret_key_names=("OPENAI_API_KEY", "suite_activity"),
        openai_key_name_in_secret_list=True,
    )
    text = "\n".join(format_openai_secrets_diagnostics(probe))
    assert "sk-" not in text
    assert "OPENAI_API_KEY found = true" in text
    assert "deploy code marker" in text


def test_lists_top_level_key_names_without_values(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    class _St:
        secrets = _SecretsLike(
            {"suite_activity": {"x": 1}, "OPENAI_API_KEY": "sk-hidden"}
        )

    monkeypatch.setitem(__import__("sys").modules, "streamlit", _St)
    _key, probe = resolve_openai_api_key()
    assert _key == "sk-hidden"
    assert "OPENAI_API_KEY" in probe.top_level_secret_key_names
    assert "sk-hidden" not in format_openai_secrets_diagnostics(probe)
