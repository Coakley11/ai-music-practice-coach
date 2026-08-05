"""Resolve deployed git commit/branch (local git, Streamlit Cloud env, Heroku-style vars)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent

_COMMIT_ENV_KEYS = (
    "STREAMLIT_GIT_COMMIT",
    "GIT_COMMIT",
    "COMMIT_SHA",
    "SOURCE_COMMIT",
    "SOURCE_VERSION",
    "HEROKU_SLUG_COMMIT",
)


def resolve_git_commit_short() -> str:
    full = resolve_git_commit_full()
    if full and full != "unknown":
        return full[:12]
    return "unknown"


def resolve_git_commit_full() -> str:
    for name in _COMMIT_ENV_KEYS:
        val = str(os.environ.get(name) or "").strip()
        if val:
            return val
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            timeout=2,
            cwd=str(_REPO_ROOT),
        )
        full = out.decode().strip()
        return full or "unknown"
    except Exception:
        return "unknown"


def resolve_git_branch() -> str:
    for name in ("STREAMLIT_GIT_BRANCH", "GIT_BRANCH", "BRANCH_NAME"):
        val = str(os.environ.get(name) or "").strip()
        if val:
            return val
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            stderr=subprocess.DEVNULL,
            timeout=2,
            cwd=str(_REPO_ROOT),
        )
        branch = out.decode().strip()
        return branch or "unknown"
    except Exception:
        return "unknown"


__all__ = ["resolve_git_branch", "resolve_git_commit_full", "resolve_git_commit_short"]
