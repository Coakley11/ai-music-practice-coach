"""Streamlit / Starlette runtime compatibility — pin and preflight guard."""

from __future__ import annotations

import os
import re
import sys
from typing import Any

CERTIFY_STARLETTE_14_ENV = "MUSIC_CERTIFY_STARLETTE_14"
REQUIRED_STARLETTE_PIN = "1.3.1"
STREAMLIT_161_PREFIX = "1.61."
STARLETTE_INCOMPATIBLE_MIN = (1, 4, 0)


def _parse_version(raw: str) -> tuple[int, ...]:
    text = str(raw or "").strip()
    if not text or text == "unknown":
        return (0,)
    m = re.match(r"^(\d+(?:\.\d+)*)", text)
    if not m:
        return (0,)
    return tuple(int(p) for p in m.group(1).split("."))


def _version_at_least(v: tuple[int, ...], minimum: tuple[int, ...]) -> bool:
    n = max(len(v), len(minimum))
    va = v + (0,) * (n - len(v))
    mi = minimum + (0,) * (n - len(minimum))
    return va >= mi


def installed_dependency_versions() -> dict[str, str]:
    out = {
        "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    }
    for pkg in ("streamlit", "starlette", "uvicorn"):
        try:
            from importlib.metadata import version

            out[pkg] = version(pkg)
        except Exception:
            out[pkg] = "unknown"
    return out


def evaluate_starlette_streamlit_compatibility(
    versions: dict[str, str] | None = None,
) -> dict[str, Any]:
    versions = versions or installed_dependency_versions()
    st_ver = str(versions.get("streamlit") or "")
    star_ver = str(versions.get("starlette") or "")
    st_parts = _parse_version(st_ver)
    star_parts = _parse_version(star_ver)
    certified = str(os.environ.get(CERTIFY_STARLETTE_14_ENV) or "").strip() in {"1", "true", "yes"}
    streamlit_161 = st_ver.startswith(STREAMLIT_161_PREFIX) or st_parts[:2] == (1, 61)
    starlette_14_plus = _version_at_least(star_parts, STARLETTE_INCOMPATIBLE_MIN)
    incompatible = bool(streamlit_161 and starlette_14_plus and not certified)
    reason = ""
    if incompatible:
        reason = (
            "Streamlit 1.61.x is not compatible with Starlette >= 1.4.0 "
            "(GZipResponder thread_minimum_size). Pin starlette==1.3.1 in requirements.txt "
            f"or set {CERTIFY_STARLETTE_14_ENV}=1 after explicit certification."
        )
    return {
        "compatible": not incompatible,
        "reason": reason,
        "certified_starlette_14": certified,
        "streamlit_161": streamlit_161,
        "starlette_14_plus": starlette_14_plus,
        **versions,
    }


def format_dependency_versions_line(versions: dict[str, str] | None = None) -> str:
    v = versions or installed_dependency_versions()
    return (
        f"[dependency_versions] python={v.get('python')} "
        f"streamlit={v.get('streamlit')} "
        f"starlette={v.get('starlette')} "
        f"uvicorn={v.get('uvicorn')}"
    )


def log_dependency_versions(*, stream: Any | None = None) -> str:
    line = format_dependency_versions_line()
    targets = [stream] if stream is not None else [sys.stderr, sys.stdout]
    for target in targets:
        print(line, flush=True, file=target)
    return line


def enforce_runtime_compatibility(*, context: str = "startup") -> dict[str, Any]:
    """Log dependency versions; exit non-zero when an uncertified bad combo is installed."""
    eval_result = evaluate_starlette_streamlit_compatibility()
    log_dependency_versions()
    if not eval_result["compatible"]:
        msg = (
            f"[dependency_compatibility] FAIL context={context} "
            f"{eval_result.get('reason')}"
        )
        print(msg, flush=True, file=sys.stderr)
        print(msg, flush=True)
        raise SystemExit(1)
    return eval_result


def read_requirements_starlette_pin(requirements_path: str | None = None) -> str | None:
    from pathlib import Path

    path = Path(requirements_path or Path(__file__).resolve().parent / "requirements.txt")
    if not path.is_file():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            continue
        if stripped.lower().startswith("starlette"):
            return stripped
    return None


__all__ = [
    "CERTIFY_STARLETTE_14_ENV",
    "REQUIRED_STARLETTE_PIN",
    "enforce_runtime_compatibility",
    "evaluate_starlette_streamlit_compatibility",
    "format_dependency_versions_line",
    "installed_dependency_versions",
    "log_dependency_versions",
    "read_requirements_starlette_pin",
]


if __name__ == "__main__":
    enforce_runtime_compatibility(context="cli")
    print("dependency compatibility OK", flush=True)
