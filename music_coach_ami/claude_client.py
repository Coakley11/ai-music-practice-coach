"""Thin Anthropic transport. The only module that imports the anthropic SDK (lazily)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class TransportResult:
    text: str
    usage: dict[str, int] = field(default_factory=dict)
    request_id: str = ""
    stop_reason: str = ""
    model: str = ""


class TransportError(Exception):
    """billed is 'no' only when the request provably never reached inference; otherwise 'unknown'."""

    def __init__(self, kind: str, *, error_type: str = "", billed: str = "unknown") -> None:
        super().__init__(kind)
        self.kind = kind
        self.error_type = error_type
        self.billed = billed


class ClaudeTransport(Protocol):
    def complete(
        self,
        *,
        model: str,
        system: str,
        user: str,
        schema: dict[str, Any],
        max_output_tokens: int,
        effort: str,
        timeout_s: float,
    ) -> TransportResult: ...


_USAGE_FIELDS = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")


class AnthropicTransport:
    """No SDK-level retries: a hidden retry would be a hidden second charge."""

    def __init__(self, api_key: str) -> None:
        try:
            import anthropic  # noqa: WPS433
        except ImportError:
            raise TransportError("sdk_unavailable", error_type="ImportError", billed="no") from None
        self._sdk = anthropic
        self._client = anthropic.Anthropic(api_key=api_key, max_retries=0)

    def complete(
        self,
        *,
        model: str,
        system: str,
        user: str,
        schema: dict[str, Any],
        max_output_tokens: int,
        effort: str,
        timeout_s: float,
    ) -> TransportResult:
        sdk = self._sdk
        try:
            response = self._client.with_options(timeout=timeout_s).messages.create(
                model=model,
                max_tokens=max_output_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
            )
        except (sdk.AuthenticationError, sdk.PermissionDeniedError, sdk.NotFoundError, sdk.BadRequestError) as exc:
            raise TransportError("client_error", error_type=type(exc).__name__, billed="no") from None
        except sdk.RateLimitError as exc:
            raise TransportError("rate_limit", error_type=type(exc).__name__, billed="no") from None
        except sdk.APITimeoutError as exc:
            raise TransportError("timeout", error_type=type(exc).__name__) from None
        except sdk.APIConnectionError as exc:
            raise TransportError("connection", error_type=type(exc).__name__) from None
        except sdk.APIStatusError as exc:
            raise TransportError("server", error_type=type(exc).__name__) from None
        except Exception as exc:  # noqa: BLE001 - never let SDK internals escape with request details
            raise TransportError("other", error_type=type(exc).__name__) from None

        text = next((b.text for b in response.content if getattr(b, "type", "") == "text"), "")
        usage_obj = getattr(response, "usage", None)
        usage = {name: int(getattr(usage_obj, name, 0) or 0) for name in _USAGE_FIELDS}
        return TransportResult(
            text=text,
            usage=usage,
            request_id=str(getattr(response, "_request_id", "") or ""),
            stop_reason=str(getattr(response, "stop_reason", "") or ""),
            model=str(getattr(response, "model", "") or model),
        )
