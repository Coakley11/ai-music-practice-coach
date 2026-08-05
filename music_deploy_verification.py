"""Deploy identity, preflight, and source scans for Streamlit Cloud verification."""

from __future__ import annotations

import inspect
import logging
import os
import re
from pathlib import Path
from typing import Any

log = logging.getLogger("music_deploy")

SESSION_DEPLOY_SHA_KEY = "_studio_ui_release_sha"
SESSION_DEPLOY_BRANCH_KEY = "_music_deploy_branch"
SESSION_DEPLOY_FULL_SHA_KEY = "_music_deploy_full_sha"
SESSION_DEPLOY_IDENTITY_KEY = "_music_deploy_identity"
SESSION_DEPLOY_PREFLIGHT_KEY = "_music_deploy_preflight"
SESSION_LATE_MISSIONS_SCAN_KEY = "_music_late_missions_activation_scan"

# Missions widget hotfix — bump when superseded by a newer required deploy.
REQUIRED_MISSIONS_HOTFIX_SHA = "f16c670"
REQUIRED_MISSIONS_HOTFIX_PREFIX = REQUIRED_MISSIONS_HOTFIX_SHA[:7]


def _repo_root() -> Path:
    return Path(__file__).resolve().parent


def resolve_deploy_full_sha() -> str:
    from suite_deploy_marker import resolve_git_commit_full

    return resolve_git_commit_full()


def resolve_deploy_identity() -> dict[str, str]:
    from suite_deploy_marker import resolve_git_branch, resolve_git_commit_short

    full = resolve_deploy_full_sha()
    short = resolve_git_commit_short()
    if full != "unknown" and len(full) >= 7 and short == "unknown":
        short = full[:12]
    branch = resolve_git_branch()
    source = "env" if any(os.environ.get(k) for k in ("STREAMLIT_GIT_COMMIT", "GIT_COMMIT", "COMMIT_SHA")) else "git"
    return {
        "branch": branch,
        "sha_short": short,
        "sha_full": full,
        "source": source,
        "required_missions_hotfix": REQUIRED_MISSIONS_HOTFIX_PREFIX,
    }


def ensure_session_deploy_identity(session: dict[str, Any]) -> dict[str, str]:
    ident = resolve_deploy_identity()
    session[SESSION_DEPLOY_SHA_KEY] = ident["sha_short"]
    session[SESSION_DEPLOY_BRANCH_KEY] = ident["branch"]
    session[SESSION_DEPLOY_FULL_SHA_KEY] = ident["sha_full"]
    session[SESSION_DEPLOY_IDENTITY_KEY] = ident
    session[SESSION_LATE_MISSIONS_SCAN_KEY] = scan_late_missions_activation_in_source()
    session[SESSION_DEPLOY_PREFLIGHT_KEY] = evaluate_deploy_preflight(ident, session[SESSION_LATE_MISSIONS_SCAN_KEY])
    return ident


def log_deploy_startup() -> None:
    ident = resolve_deploy_identity()
    scan = scan_late_missions_activation_in_source()
    pre = evaluate_deploy_preflight(ident, scan)
    msg = (
        "music_deploy_startup branch=%s sha=%s full=%s required=%s preflight=%s late_missions=%s "
        "improv_ui=%s workflow_auth=%s pending_activation=%s"
    )
    paths = module_runtime_paths()
    log.info(
        msg,
        ident["branch"],
        ident["sha_short"],
        ident["sha_full"],
        REQUIRED_MISSIONS_HOTFIX_PREFIX,
        pre.get("status"),
        scan.get("present"),
        paths.get("improvisation_intelligence_ui"),
        paths.get("workflow_musical_authority"),
        paths.get("music_workflow_pending_activation"),
    )
    print(  # noqa: T201 — visible in Streamlit Cloud logs
        f"[music_deploy] branch={ident['branch']} sha={ident['sha_short']} "
        f"required={REQUIRED_MISSIONS_HOTFIX_PREFIX} preflight={pre.get('status')} "
        f"late_missions_activation={scan.get('present')}",
        flush=True,
    )


def module_runtime_paths() -> dict[str, str]:
    out: dict[str, str] = {}
    for mod_name in (
        "improvisation_intelligence_ui",
        "workflow_musical_authority",
        "music_workflow_pending_activation",
    ):
        try:
            mod = __import__(mod_name)
            out[mod_name] = str(getattr(mod, "__file__", "") or "")
        except ImportError:
            out[mod_name] = "missing"
    return out


def _extract_function_body(source_text: str, func_name: str) -> str:
    match = re.search(rf"^def {re.escape(func_name)}\(", source_text, re.MULTILINE)
    if not match:
        return ""
    start = match.start()
    rest = source_text[start:]
    lines = rest.splitlines()
    if not lines:
        return ""
    body_lines = [lines[0]]
    base_indent = len(lines[0]) - len(lines[0].lstrip())
    for line in lines[1:]:
        if line.strip() == "":
            body_lines.append(line)
            continue
        indent = len(line) - len(line.lstrip())
        if indent <= base_indent and line.lstrip().startswith("def "):
            break
        body_lines.append(line)
    return "\n".join(body_lines)


def scan_late_missions_activation_in_source() -> dict[str, Any]:
    """True if loaded improvisation_intelligence_ui still activates workflow inside _tab_missions."""
    try:
        import improvisation_intelligence_ui as improv_ui

        path = Path(getattr(improv_ui, "__file__", "") or "")
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
    except Exception as exc:
        return {"present": True, "error": str(exc), "path": "", "findings": ["import_failed"]}
    body = _extract_function_body(text, "_tab_missions")
    findings: list[str] = []
    patterns = (
        ("switch_workflow_owner", r"switch_workflow_owner\s*\("),
        ("restore_workflow_snapshot", r"restore_workflow_snapshot\s*\("),
        ("activate_workflow_missions_tab", r"activate_workflow\s*\("),
        ("activate_workflow_simple_missions", r"activate_workflow_simple\s*\("),
    )
    for label, pat in patterns:
        if body and re.search(pat, body):
            findings.append(label)
    try:
        import workflow_musical_authority as wma

        wma_path = Path(getattr(wma, "__file__", "") or "")
        wma_text = wma_path.read_text(encoding="utf-8") if wma_path.is_file() else ""
        if 'restore_workflow_snapshot(session, "song_based_improvisation")' in wma_text:
            findings.append("mission_jam_song_based_fallback")
    except Exception:
        pass
    pending_ok = False
    try:
        import music_workflow_pending_activation  # noqa: F401

        pending_ok = True
    except ImportError:
        findings.append("missing_music_workflow_pending_activation")
    return {
        "present": bool(findings),
        "findings": findings,
        "path": str(path),
        "pending_activation_module": pending_ok,
        "_tab_missions_line": inspect.getsourcelines(improv_ui._tab_missions)[1] if hasattr(improv_ui, "_tab_missions") else None,
    }


def evaluate_deploy_preflight(
    ident: dict[str, str] | None = None,
    scan: dict[str, Any] | None = None,
    *,
    required_sha: str = REQUIRED_MISSIONS_HOTFIX_PREFIX,
) -> dict[str, Any]:
    ident = ident or resolve_deploy_identity()
    scan = scan or scan_late_missions_activation_in_source()
    sha = str(ident.get("sha_short") or ident.get("sha_full") or "").strip()
    sha7 = sha[:7] if sha else ""
    full = str(ident.get("sha_full") or "").strip()
    full7 = full[:7] if full else ""
    matches = sha7 == required_sha or full7 == required_sha or sha.startswith(required_sha)
    if not matches:
        return {
            "status": "NOT_RUN — REQUIRED BUILD NOT DEPLOYED",
            "required_sha": required_sha,
            "actual_sha": sha or full or "unknown",
            "branch": ident.get("branch", ""),
            "late_missions_activation": scan.get("present"),
        }
    if scan.get("present"):
        return {
            "status": "FAIL — STALE SOURCE ON REQUIRED SHA",
            "required_sha": required_sha,
            "actual_sha": sha or full,
            "branch": ident.get("branch", ""),
            "late_missions_activation": True,
            "findings": scan.get("findings"),
        }
    return {
        "status": "OK",
        "required_sha": required_sha,
        "actual_sha": sha or full,
        "branch": ident.get("branch", ""),
        "late_missions_activation": False,
    }


def missions_smoke_allowed(session: dict[str, Any]) -> bool:
    pre = session.get(SESSION_DEPLOY_PREFLIGHT_KEY) or evaluate_deploy_preflight()
    return str(pre.get("status") or "") == "OK"


def render_dev_deploy_verification_panel(st: Any, session: dict[str, Any]) -> None:
    try:
        dev = bool(st.query_params.get("dev"))
    except Exception:
        dev = bool(session.get("developer_mode"))
    if not dev:
        return
    ident = session.get(SESSION_DEPLOY_IDENTITY_KEY) or ensure_session_deploy_identity(session)
    scan = session.get(SESSION_LATE_MISSIONS_SCAN_KEY) or scan_late_missions_activation_in_source()
    pre = session.get(SESSION_DEPLOY_PREFLIGHT_KEY) or evaluate_deploy_preflight(ident, scan)
    paths = module_runtime_paths()
    st.sidebar.markdown("---")
    st.sidebar.markdown("**Deploy verification**")
    st.sidebar.code(
        "\n".join(
            [
                f"branch: {ident.get('branch')}",
                f"sha: {ident.get('sha_short')}",
                f"full: {ident.get('sha_full')}",
                f"required: {REQUIRED_MISSIONS_HOTFIX_PREFIX}",
                f"preflight: {pre.get('status')}",
                f"late_missions_in_tab: {scan.get('present')}",
                f"findings: {scan.get('findings')}",
                f"_tab_missions @ line: {scan.get('_tab_missions_line')}",
                f"pending_module: {scan.get('pending_activation_module')}",
            ]
        )
    )
    for name, p in paths.items():
        st.sidebar.caption(f"`{name}` → `{p}`")


__all__ = [
    "REQUIRED_MISSIONS_HOTFIX_SHA",
    "ensure_session_deploy_identity",
    "evaluate_deploy_preflight",
    "log_deploy_startup",
    "missions_smoke_allowed",
    "module_runtime_paths",
    "render_dev_deploy_verification_panel",
    "scan_late_missions_activation_in_source",
]
