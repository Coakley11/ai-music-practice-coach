"""Run one identity gate with UTF-8 evidence logging (avoids PowerShell UTF-16)."""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / "scripts" / "_source_identity_browser_evidence"
EV.mkdir(exist_ok=True)


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: _run_gate_batch.py <label> <script> [args...]", flush=True)
        return 2
    label = sys.argv[1]
    script = sys.argv[2]
    args = sys.argv[3:]
    sha = (
        subprocess.check_output(["git", "rev-parse", "--short=7", "HEAD"], cwd=str(ROOT))
        .decode()
        .strip()
    )
    out = EV / f"{label}_{sha}.txt"
    env = os.environ.copy()
    env.setdefault("ENSURE_SONGS_ALLOW_RELOAD", "0")
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    cmd = [sys.executable, "-u", str(ROOT / "scripts" / script), *args]
    print(f"[gate] label={label} sha={sha} out={out.name} cmd={cmd}", flush=True)
    t0 = time.time()
    with out.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(f"# gate={label} sha={sha} started={time.strftime('%Y-%m-%dT%H:%M:%S')}\n")
        fh.flush()
        proc = subprocess.Popen(
            cmd,
            cwd=str(ROOT),
            env=env,
            stdout=fh,
            stderr=subprocess.STDOUT,
            text=True,
        )
        rc = proc.wait()
        elapsed = time.time() - t0
        fh.write(f"\n# gate_exit={rc} elapsed_s={elapsed:.1f}\n")
    print(f"[gate] done label={label} rc={rc} elapsed_s={elapsed:.1f}", flush=True)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
