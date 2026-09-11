"""Dedicated gate-12 oneshot: exact 17-gate preamble through pre-kill, then
conditional hard reboot only if Mission Backing is already on disk.

Usage:
  MUSIC_APP_DATA_DIR=<isolated> python scripts/_oneshot_gate12_reboot.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PORT = int(os.environ.get("GATE12_PORT") or "8588")
DATA_DIR = Path(os.environ.get("GATE12_DATA_DIR") or str(ROOT / "_runtime_g12_oneshot")).resolve()


def log(msg: str) -> None:
    print(str(msg).encode("ascii", "replace").decode("ascii"), flush=True)


def wait_server(port: int, timeout_s: float = 120.0) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}", timeout=2)
            return True
        except Exception:
            time.sleep(2)
    return False


def kill_port(port: int) -> None:
    try:
        subprocess.check_output(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue | "
                "ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }",
            ],
            text=True,
        )
    except Exception as exc:
        log(f"kill_port warn: {exc!r}")


def main() -> int:
    if DATA_DIR.exists():
        shutil.rmtree(DATA_DIR, ignore_errors=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    os.environ["MUSIC_APP_DATA_DIR"] = str(DATA_DIR)
    kill_port(PORT)
    env = os.environ.copy()
    env["MUSIC_APP_DATA_DIR"] = str(DATA_DIR)
    env["PYTHONUNBUFFERED"] = "1"
    log(f"start streamlit port={PORT} data={DATA_DIR}")
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "streamlit_music_practice_app.py",
            "--server.port",
            str(PORT),
            "--server.headless",
            "true",
            "--browser.gatherUsageStats",
            "false",
        ],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if not wait_server(PORT):
        log("server wait timeout")
        proc.kill()
        return 2
    url = f"http://127.0.0.1:{PORT}"
    log(f"walker {url}")
    args = [
        sys.executable,
        "scripts/_walk_core_workflows_embargo.py",
        url,
    ]
    if "--full" not in sys.argv:
        args.append("--until=12")
    rc = subprocess.call(args, cwd=str(ROOT), env=env)
    log(f"walker_rc={rc}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
