"""Stop only a verified, task-owned Streamlit/process — never broad filename kills.

Cross-session rule: never Stop-Process / taskkill merely because a process is
python.exe, Streamlit, Chromium, or runs streamlit_music_practice_app.py.
Interactive human 8510 and other worktrees must stay untouched.

Verify before stop:
  - exact PID
  - listening port (when applicable)
  - command line contains this worktree root and the expected port
Optional: creation-time floor when the caller tracked start.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path
from typing import Any

# Human interactive key-cycle server — never targeted by automation in this tree.
PROTECTED_PORTS = frozenset({8510})

ROOT = Path(__file__).resolve().parents[1]
_ROOT_NEEDLE = str(ROOT).replace("/", "\\").lower()


def _norm(s: str) -> str:
    return (s or "").replace("/", "\\").lower()


def _cim_process(pid: int) -> dict[str, Any] | None:
    if not sys.platform.startswith("win"):
        return None
    try:
        out = subprocess.check_output(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"$p = Get-CimInstance Win32_Process -Filter \"ProcessId={int(pid)}\" "
                "-ErrorAction SilentlyContinue; if (-not $p) {{ '' }} else {{ "
                "\"$($p.ProcessId)|$($p.CreationDate)|$($p.CommandLine)\" }}",
            ],
            text=True,
            errors="replace",
            timeout=30,
        ).strip()
    except Exception:
        return None
    if not out or "|" not in out:
        return None
    parts = out.split("|", 2)
    if len(parts) < 3:
        return None
    return {
        "pid": int(parts[0]),
        "creation": parts[1],
        "command_line": parts[2],
    }


def _listeners_on_port(port: int) -> list[int]:
    if not sys.platform.startswith("win"):
        return []
    try:
        out = subprocess.check_output(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"@(Get-NetTCPConnection -LocalPort {int(port)} -State Listen "
                "-ErrorAction SilentlyContinue | Select-Object -ExpandProperty "
                "OwningProcess -Unique) -join ','",
            ],
            text=True,
            errors="replace",
            timeout=30,
        ).strip()
    except Exception:
        return []
    if not out:
        return []
    pids: list[int] = []
    for tok in out.split(","):
        tok = tok.strip()
        if tok.isdigit():
            pids.append(int(tok))
    return sorted(set(pids))


def process_matches_owned_server(
    *,
    pid: int,
    port: int,
    worktree: Path | None = None,
    command_line: str | None = None,
    created_after: str | None = None,
) -> tuple[bool, str]:
    """Return (ok, reason). Requires worktree path + port in the command line."""
    if port in PROTECTED_PORTS:
        return False, f"refused: port {port} is protected (interactive human server)"
    info = _cim_process(pid)
    if info is None:
        return False, f"pid {pid} not found"
    cmd = command_line if command_line is not None else str(info.get("command_line") or "")
    needle = _norm(str(worktree or ROOT))
    cl = _norm(cmd)
    if needle not in cl:
        return False, f"pid {pid}: command line is not this worktree"
    # Port must appear as a server.port argument or :PORT token — avoid bare substrings
    # like matching 851 inside 18510 by requiring boundary-ish forms.
    port_s = str(int(port))
    port_ok = (
        f"--server.port {port_s}" in cl
        or f"--server.port', '{port_s}" in cl
        or f"--server.port\", \"{port_s}" in cl
        or f"--server.port,{port_s}" in cl.replace(" ", "")
        or f":{port_s}" in cl
        or f"port {port_s}" in cl
    )
    if not port_ok:
        return False, f"pid {pid}: command line does not show port {port}"
    if "streamlit" not in cl and "uvicorn" not in cl:
        return False, f"pid {pid}: not a streamlit/uvicorn command line"
    if created_after:
        # CreationDate from CIM is comparable as string in MS format when both CIM.
        cre = str(info.get("creation") or "")
        if cre and cre < created_after:
            return False, f"pid {pid}: creation {cre} older than task start {created_after}"
    return True, "ok"


def stop_owned_pid(pid: int, *, port: int, worktree: Path | None = None) -> dict[str, Any]:
    """Stop one PID only after ownership checks. Never broad-matches by filename."""
    ok, reason = process_matches_owned_server(pid=pid, port=port, worktree=worktree)
    result: dict[str, Any] = {"pid": pid, "port": port, "stopped": False, "reason": reason}
    if not ok:
        return result
    if sys.platform.startswith("win"):
        # /T only on the verified PID (children of this process), not a name scan.
        cp = subprocess.run(
            ["taskkill", "/PID", str(int(pid)), "/F", "/T"],
            check=False,
            capture_output=True,
            text=True,
        )
        result["stopped"] = cp.returncode == 0
        result["taskkill_code"] = cp.returncode
    else:
        subprocess.run(["kill", "-9", str(int(pid))], check=False)
        result["stopped"] = True
    return result


def stop_owned_listener_on_port(
    port: int,
    *,
    worktree: Path | None = None,
    owned_pid: int | None = None,
) -> list[dict[str, Any]]:
    """
    Free *port* only for listeners that verify as this worktree's server.

    If owned_pid is set, only that PID is considered (must also listen / match).
    Refuses PROTECTED_PORTS (8510).
    """
    if port in PROTECTED_PORTS:
        return [
            {
                "pid": None,
                "port": port,
                "stopped": False,
                "reason": f"refused: port {port} is protected (interactive human server)",
            }
        ]
    results: list[dict[str, Any]] = []
    candidates = _listeners_on_port(port)
    if owned_pid is not None:
        if owned_pid not in candidates and candidates:
            results.append(
                {
                    "pid": owned_pid,
                    "port": port,
                    "stopped": False,
                    "reason": f"owned_pid {owned_pid} is not listening on {port} "
                    f"(listeners={candidates})",
                }
            )
            return results
        candidates = [owned_pid] if owned_pid in candidates or not candidates else []
        if owned_pid and owned_pid not in candidates:
            # Process may exist but not show as listener yet / already dead — still verify cmd.
            candidates = [owned_pid]
    if not candidates:
        return [{"pid": None, "port": port, "stopped": False, "reason": "no listener"}]
    for pid in candidates:
        results.append(stop_owned_pid(pid, port=port, worktree=worktree))
    time.sleep(0.5)
    return results


def kill_port_safe(port: int, *, owned_pid: int | None = None) -> list[dict[str, Any]]:
    """Drop-in replacement for legacy kill_port() helpers in this worktree."""
    return stop_owned_listener_on_port(port, worktree=ROOT, owned_pid=owned_pid)


__all__ = [
    "PROTECTED_PORTS",
    "ROOT",
    "kill_port_safe",
    "process_matches_owned_server",
    "stop_owned_listener_on_port",
    "stop_owned_pid",
]
