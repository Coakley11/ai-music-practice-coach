"""Deploy identity, preflight, and source scans for Streamlit Cloud verification."""

from __future__ import annotations

import inspect
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any

log = logging.getLogger("music_deploy")

SESSION_DEPLOY_SHA_KEY = "_studio_ui_release_sha"
SESSION_DEPLOY_BRANCH_KEY = "_music_deploy_branch"
SESSION_DEPLOY_FULL_SHA_KEY = "_music_deploy_full_sha"
SESSION_DEPLOY_IDENTITY_KEY = "_music_deploy_identity"
SESSION_DEPLOY_PREFLIGHT_KEY = "_music_deploy_preflight"
SESSION_LATE_MISSIONS_SCAN_KEY = "_music_late_missions_activation_scan"
SESSION_ARTIFACT_FREEZE_SCAN_KEY = "_music_late_artifact_freeze_scan"

# Missions widget hotfix — any deploy at or after these SHAs is acceptable when scans pass.
REQUIRED_MISSIONS_HOTFIX_SHA = "f16c670"
REQUIRED_MISSIONS_HOTFIX_PREFIX = REQUIRED_MISSIONS_HOTFIX_SHA[:7]
ACCEPTED_DEPLOY_SHA_PREFIXES: tuple[str, ...] = (
    "f16c670",
    "b945264",
    "c8131fd",
    "a112506",
    "b3826fc",
    "da64329",
    "04a8c1b",
    "cf8d8ed",
    "eeb53c0",
    "64b4173",
    "21d0c32",
    "8bba3b8",
    "f047ff0",
)

_PROCESS_DEPLOY_LOGGED = False


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
    session[SESSION_ARTIFACT_FREEZE_SCAN_KEY] = scan_late_artifact_freeze_in_source()
    session[SESSION_DEPLOY_PREFLIGHT_KEY] = evaluate_deploy_preflight(
        ident,
        session[SESSION_LATE_MISSIONS_SCAN_KEY],
        artifact_scan=session[SESSION_ARTIFACT_FREEZE_SCAN_KEY],
    )
    return ident


def _audio_stack_versions() -> dict[str, str]:
    out: dict[str, str] = {"python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"}
    for mod_name, label in (
        ("librosa", "librosa"),
        ("numba", "numba"),
        ("llvmlite", "llvmlite"),
    ):
        try:
            mod = __import__(mod_name)
            out[label] = str(getattr(mod, "__version__", "unknown"))
        except ImportError:
            out[label] = "missing"
    return out


def _sha_matches_accepted_deploy(sha: str, full: str) -> bool:
    for token in (sha, full, sha[:7], full[:7]):
        t = str(token or "").strip()
        if not t:
            continue
        for prefix in ACCEPTED_DEPLOY_SHA_PREFIXES:
            if t.startswith(prefix) or prefix.startswith(t[:7]):
                return True
    try:
        import subprocess

        head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            timeout=2,
            cwd=str(_repo_root()),
        ).decode().strip()
        if head and (full == head or sha == head[:12] or head.startswith(sha[:7])):
            return True
    except Exception:
        pass
    return False


def scan_late_artifact_freeze_in_source() -> dict[str, Any]:
    """Detect direct session global-key mutation inside freeze_global_keys_for_creative_artifact_save."""
    try:
        import creative_artifact_global_key_guard as guard

        path = Path(getattr(guard, "__file__", "") or "")
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
    except Exception as exc:
        return {"present": True, "error": str(exc), "findings": ["import_failed"]}
    body = _extract_function_body(text, "freeze_global_keys_for_creative_artifact_save")
    findings: list[str] = []
    if re.search(r"session\s*\[\s*field\s*\]\s*=", body):
        findings.append("session_field_assignment")
    for key in ("display_key", "concert_key"):
        if re.search(rf'session\s*\[\s*["\']{key}["\']\s*\]\s*=', body):
            findings.append(f"session_{key}_assignment")
    return {
        "present": bool(findings),
        "findings": findings,
        "path": str(path),
    }


def emit_deploy_startup_log(*, force: bool = False) -> None:
    """Unconditional process-start log for Streamlit Cloud (visible before auth/UI)."""
    global _PROCESS_DEPLOY_LOGGED
    if _PROCESS_DEPLOY_LOGGED and not force:
        return
    _PROCESS_DEPLOY_LOGGED = True
    ident = resolve_deploy_identity()
    scan_m = scan_late_missions_activation_in_source()
    scan_a = scan_late_artifact_freeze_in_source()
    pre = evaluate_deploy_preflight(ident, scan_m, artifact_scan=scan_a)
    paths = module_runtime_paths()
    audio = _audio_stack_versions()
    line = (
        f"[music_deploy] branch={ident.get('branch')} "
        f"sha={ident.get('sha_full') or ident.get('sha_short')} "
        f"required={REQUIRED_MISSIONS_HOTFIX_PREFIX} "
        f"preflight={pre.get('status')} "
        f"python={audio.get('python')} "
        f"librosa={audio.get('librosa')} "
        f"numba={audio.get('numba')} "
        f"llvmlite={audio.get('llvmlite')} "
        f"late_missions_activation={scan_m.get('present')} "
        f"late_artifact_freeze={scan_a.get('present')} "
        f"modules={paths}"
    )
    print(line, flush=True, file=sys.stderr)
    print(line, flush=True)
    log.info("emit_deploy_startup_log %s", line)


def log_deploy_startup() -> None:
    emit_deploy_startup_log(force=True)


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


def scan_mission_backing_handoff_in_source() -> dict[str, Any]:
    """Fail if Mission Backing click path still mutates alignment in loaded source."""
    try:
        import improvisation_intelligence_ui as improv_ui

        path = Path(getattr(improv_ui, "__file__", "") or "")
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
    except Exception as exc:
        return {"present": True, "error": str(exc), "path": "", "findings": ["import_failed"]}
    body = _extract_function_body(text, "_open_mission_backing")
    if not body:
        tab_body = _extract_function_body(text, "_tab_missions")
        match = re.search(r"def _open_mission_backing\(", tab_body)
        if match:
            body = _extract_function_body(tab_body[match.start() :], "_open_mission_backing")
    findings: list[str] = []
    if body and re.search(r"ensure_mission_handoff_aligned\s*\(", body):
        findings.append("mutable_ensure_mission_handoff_aligned_in_open_mission_backing")
    defer_branch = "build_mission_backing_alignment_payload" in body if body else False
    return {
        "present": bool(findings),
        "findings": findings,
        "path": str(path),
        "defer_branch_present": defer_branch,
        "_open_mission_backing_line": inspect.getsourcelines(improv_ui._open_mission_backing)[1]
        if hasattr(improv_ui, "_open_mission_backing")
        else None,
    }


def function_source_verification() -> list[dict[str, Any]]:
    """Loaded module paths and source hashes for hotfix-critical functions."""
    import hashlib

    specs = (
        ("improvisation_intelligence_ui", "_open_mission_backing"),
        ("mission_workflow_context", "ensure_mission_handoff_aligned"),
        ("music_workflow_mutation", "commit_staged_workflow"),
        ("music_workflow_mutation", "_fail_mutation"),
        ("music_workflow_mutation", "_restore_legacy_snapshot"),
        ("improvisation_missions", "ensure_mission_sheet_music_authority"),
        ("improvisation_missions", "rebuild_mission_outputs"),
    )
    rows: list[dict[str, Any]] = []
    for mod_name, func_name in specs:
        row: dict[str, Any] = {"module": mod_name, "function": func_name}
        try:
            mod = __import__(mod_name)
            row["path"] = str(getattr(mod, "__file__", "") or "")
            path = Path(row["path"])
            text = path.read_text(encoding="utf-8") if path.is_file() else ""
            body = _extract_function_body(text, func_name)
            if not body and func_name == "_open_mission_backing":
                tab_body = _extract_function_body(text, "_tab_missions")
                match = re.search(r"def _open_mission_backing\(", tab_body)
                if match:
                    body = _extract_function_body(tab_body[match.start() :], "_open_mission_backing")
            row["line"] = inspect.getsourcelines(getattr(mod, func_name))[1] if hasattr(mod, func_name) else None
            row["source_hash"] = hashlib.sha256(body.encode()).hexdigest()[:12] if body else ""
            if func_name == "_open_mission_backing":
                row["defer_branch"] = "build_mission_backing_alignment_payload" in body
                row["mutable_align_call"] = "ensure_mission_handoff_aligned" in body
            if func_name == "_restore_legacy_snapshot":
                row["canonical_only_when_locked"] = "rollback_canonical_only" in body or "canonical_only" in body
        except Exception as exc:
            row["error"] = str(exc)
        rows.append(row)
    return rows


def evaluate_deploy_preflight(
    ident: dict[str, str] | None = None,
    scan: dict[str, Any] | None = None,
    *,
    artifact_scan: dict[str, Any] | None = None,
    backing_scan: dict[str, Any] | None = None,
    required_sha: str = REQUIRED_MISSIONS_HOTFIX_PREFIX,
) -> dict[str, Any]:
    ident = ident or resolve_deploy_identity()
    scan = scan or scan_late_missions_activation_in_source()
    artifact_scan = artifact_scan or scan_late_artifact_freeze_in_source()
    backing_scan = backing_scan or scan_mission_backing_handoff_in_source()
    sha = str(ident.get("sha_short") or ident.get("sha_full") or "").strip()
    full = str(ident.get("sha_full") or "").strip()
    matches = _sha_matches_accepted_deploy(sha, full)
    if scan.get("present") or artifact_scan.get("present") or backing_scan.get("present"):
        return {
            "status": "FAIL — STALE SOURCE",
            "required_sha": required_sha,
            "actual_sha": sha or full,
            "branch": ident.get("branch", ""),
            "late_missions_activation": scan.get("present"),
            "late_artifact_freeze": artifact_scan.get("present"),
            "late_mission_backing_handoff": backing_scan.get("present"),
            "findings": (scan.get("findings") or [])
            + (artifact_scan.get("findings") or [])
            + (backing_scan.get("findings") or []),
        }
    if not matches:
        return {
            "status": "MISMATCH — UNKNOWN SHA",
            "required_sha": required_sha,
            "actual_sha": sha or full or "unknown",
            "branch": ident.get("branch", ""),
            "late_missions_activation": False,
            "late_artifact_freeze": False,
        }
    return {
        "status": "OK",
        "required_sha": required_sha,
        "actual_sha": sha or full,
        "branch": ident.get("branch", ""),
        "late_missions_activation": False,
        "late_artifact_freeze": False,
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
    art = session.get(SESSION_ARTIFACT_FREEZE_SCAN_KEY) or scan_late_artifact_freeze_in_source()
    backing = scan_mission_backing_handoff_in_source()
    pre = session.get(SESSION_DEPLOY_PREFLIGHT_KEY) or evaluate_deploy_preflight(
        ident, scan, artifact_scan=art, backing_scan=backing
    )
    paths = module_runtime_paths()
    fn_verify = function_source_verification()
    audio = _audio_stack_versions()
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
                f"python: {audio.get('python')}",
                f"librosa: {audio.get('librosa')} numba: {audio.get('numba')}",
                f"late_missions_in_tab: {scan.get('present')}",
                f"late_artifact_freeze: {art.get('present')}",
                f"late_mission_backing: {backing.get('present')}",
                f"findings: {scan.get('findings')} {art.get('findings')} {backing.get('findings')}",
                f"_tab_missions @ line: {scan.get('_tab_missions_line')}",
                f"_open_mission_backing @ line: {backing.get('_open_mission_backing_line')}",
            ]
        )
    )
    for row in fn_verify[:6]:
        st.sidebar.caption(
            f"`{row.get('module')}.{row.get('function')}` hash=`{row.get('source_hash')}` "
            f"defer={row.get('defer_branch')} mutable_align={row.get('mutable_align_call')}"
        )
    for name, p in paths.items():
        st.sidebar.caption(f"`{name}` → `{p}`")


__all__ = [
    "REQUIRED_MISSIONS_HOTFIX_SHA",
    "ACCEPTED_DEPLOY_SHA_PREFIXES",
    "ensure_session_deploy_identity",
    "emit_deploy_startup_log",
    "evaluate_deploy_preflight",
    "log_deploy_startup",
    "missions_smoke_allowed",
    "module_runtime_paths",
    "render_dev_deploy_verification_panel",
    "function_source_verification",
    "scan_mission_backing_handoff_in_source",
    "scan_late_missions_activation_in_source",
]
