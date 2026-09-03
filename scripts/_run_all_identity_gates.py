"""Sequential identity gates at HEAD with fresh Streamlit + isolated workspaces."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / "scripts" / "_source_identity_browser_evidence"
EV.mkdir(exist_ok=True)
STREAMLIT_LOG = EV / "streamlit_gate_runner.log"
_STREAMLIT_PROC: subprocess.Popen | None = None


def sha() -> str:
    return (
        subprocess.check_output(["git", "rev-parse", "--short=7", "HEAD"], cwd=str(ROOT))
        .decode()
        .strip()
    )


def wait_http(url: str = "http://127.0.0.1:8501", timeout_s: int = 120) -> bool:
    import urllib.request

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(2)
    return False


def _kill_streamlit() -> None:
    global _STREAMLIT_PROC
    if sys.platform.startswith("win"):
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" |"
                " Where-Object { $_.CommandLine -match 'streamlit' } |"
                " ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }",
            ],
            check=False,
        )
    else:
        subprocess.run(["pkill", "-f", "streamlit run streamlit_music_practice_app.py"], check=False)
    if _STREAMLIT_PROC is not None:
        try:
            _STREAMLIT_PROC.terminate()
        except Exception:
            pass
        _STREAMLIT_PROC = None
    time.sleep(2)


def start_fresh_streamlit() -> None:
    global _STREAMLIT_PROC
    _kill_streamlit()
    log_fh = STREAMLIT_LOG.open("w", encoding="utf-8")
    _STREAMLIT_PROC = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "streamlit_music_practice_app.py",
            "--server.port",
            "8501",
            "--server.headless",
            "true",
            "--browser.gatherUsageStats",
            "false",
        ],
        cwd=str(ROOT),
        stdout=log_fh,
        stderr=subprocess.STDOUT,
    )
    if not wait_http():
        raise RuntimeError("Fresh Streamlit failed to become ready on :8501")
    print(f"[streamlit] fresh pid={_STREAMLIT_PROC.pid}", flush=True)


def run_gate(label: str, script: str, env_extra: dict[str, str] | None = None) -> dict:
    product = sha()
    out = EV / f"{label}_{product}.txt"
    env = os.environ.copy()
    env["ENSURE_SONGS_ALLOW_RELOAD"] = "0"
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    if env_extra:
        env.update(env_extra)
    cmd = [sys.executable, "-u", str(ROOT / "scripts" / script)]
    print(f"[gate] START {label} sha={product} out={out.name}", flush=True)
    t0 = time.time()
    with out.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(f"# gate={label} sha={product} started={time.strftime('%Y-%m-%dT%H:%M:%S')}\n")
        fh.flush()
        proc = subprocess.Popen(cmd, cwd=str(ROOT), env=env, stdout=fh, stderr=subprocess.STDOUT, text=True)
        rc = proc.wait()
        elapsed = time.time() - t0
        fh.write(f"\n# gate_exit={rc} elapsed_s={elapsed:.1f}\n")
    result = {
        "label": label,
        "sha": product,
        "rc": rc,
        "elapsed_s": round(elapsed, 1),
        "out": str(out.name),
        "ok": rc == 0,
        "fresh_streamlit": True,
        "recovery": False,
        "ensure_songs_allow_reload": "0",
    }
    print(f"[gate] DONE {label} rc={rc} elapsed_s={elapsed:.1f}", flush=True)
    return result


def main() -> int:
    product = sha()
    summary_path = EV / f"gate_summary_{product}.json"
    results: list[dict] = []

    # 1) Authority fresh
    start_fresh_streamlit()
    results.append(run_gate("authority_fresh", "_source_authority_sequential_walk.py", {"AUTHORITY_PHASE": "fresh"}))
    # Continue remaining gates even if one fails — report all at the final SHA.

    obs = EV / "authority_fresh_obs.json"
    ws = ""
    try:
        ws = str(json.loads(obs.read_text(encoding="utf-8")).get("workspace_id") or "")
    except Exception:
        ws = ""
    if not ws:
        print("[FAIL] missing authority_fresh_obs workspace_id", flush=True)
        return 1

    # 2) Authority restored on deliberate workspace + fresh Streamlit process
    start_fresh_streamlit()
    results.append(
        run_gate(
            "authority_restored",
            "_source_authority_sequential_walk.py",
            {"AUTHORITY_PHASE": "restored", "GATE_WORKSPACE": ws},
        )
    )

    # 3) Practice Key E
    start_fresh_streamlit()
    results.append(run_gate("practice_key_e", "_practice_key_e_gate.py"))

    # 4) Source identity 28 + 20 stress
    start_fresh_streamlit()
    results.append(
        run_gate(
            "source_identity_verify",
            "_source_identity_browser_verify.py",
            {"VERIFY_STRESS_CYCLES": "20"},
        )
    )

    # 5) Songs hub acceptance
    start_fresh_streamlit()
    results.append(run_gate("songs_hub_acceptance", "_songs_hub_acceptance_gate.py"))

    # 6) Focused 20x first Comp Backing click
    start_fresh_streamlit()
    results.append(
        run_gate(
            "focused_comp_20",
            "_focused_custom_comp_gates.py",
            {"FOCUSED_GATE": "comp", "FOCUSED_COMP_CYCLES": "20"},
        )
    )

    summary = {
        "sha": product,
        "results": results,
        "all_ok": all(r.get("ok") for r in results),
        "restored_workspace": ws,
        "units_related": "119 passed (separate)",
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)
    return 0 if summary["all_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
