"""Boot an isolated Streamlit runtime and run one walk script. Not a product gate."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


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
    except Exception:
        pass


def wait_server(port: int, timeout_s: float = 120.0) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}", timeout=2)
            return True
        except Exception:
            time.sleep(2)
    return False


def main() -> int:
    if len(sys.argv) < 4:
        print("usage: _run_isolated_walk.py PORT DATA_DIR walk_script.py", flush=True)
        return 2
    port = int(sys.argv[1])
    data_dir = Path(sys.argv[2]).resolve()
    walk = sys.argv[3]
    if data_dir.exists():
        shutil.rmtree(data_dir, ignore_errors=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    kill_port(port)
    env = os.environ.copy()
    env["MUSIC_APP_DATA_DIR"] = str(data_dir)
    env["PYTHONUNBUFFERED"] = "1"
    log_path = data_dir / "streamlit.log"
    logf = open(log_path, "w", encoding="utf-8")
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "streamlit_music_practice_app.py",
            "--server.port",
            str(port),
            "--server.headless",
            "true",
            "--browser.gatherUsageStats",
            "false",
        ],
        cwd=str(ROOT),
        env=env,
        stdout=logf,
        stderr=logf,
    )
    print(f"streamlit pid={proc.pid} port={port} log={log_path}", flush=True)
    try:
        if not wait_server(port):
            print("server wait timeout", flush=True)
            print(f"streamlit_poll={proc.poll()}", flush=True)
            return 2
        print(f"pre_walk pid={proc.pid} poll={proc.poll()}", flush=True)
        rc = subprocess.call(
            [sys.executable, walk, f"http://127.0.0.1:{port}"],
            cwd=str(ROOT),
            env=env,
        )
        print(f"post_walk pid={proc.pid} poll={proc.poll()} walk_rc={rc}", flush=True)
        return rc
    finally:
        try:
            proc.kill()
        except Exception:
            pass
        kill_port(port)
        try:
            logf.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
