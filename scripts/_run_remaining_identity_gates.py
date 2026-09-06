"""Remaining identity gates after historical authority/PK-E at unchanged tip.

Skips authority_fresh / authority_restored / practice_key_e when those already
passed at HEAD. Fresh Streamlit + isolated workspaces per gate. Only targets
music-practice Streamlit on :8501 (does not kill other local Streamlit ports).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import _run_all_identity_gates as gates  # noqa: E402

EV = gates.EV


def _kill_music_streamlit_8501() -> None:
    """Stop only streamlit_music_practice_app bound to port 8501."""
    if sys.platform.startswith("win"):
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" |"
                " Where-Object {"
                "   $_.CommandLine -match 'streamlit run streamlit_music_practice_app'"
                "   -and $_.CommandLine -match '8501'"
                " } |"
                " ForEach-Object { Stop-Process -Id $_.ProcessId -Force"
                " -ErrorAction SilentlyContinue }",
            ],
            check=False,
        )
    else:
        subprocess.run(
            ["pkill", "-f", "streamlit run streamlit_music_practice_app.py.*8501"],
            check=False,
        )
    time.sleep(2)


def start_fresh_streamlit_8501() -> None:
    _kill_music_streamlit_8501()
    log_fh = gates.STREAMLIT_LOG.open("w", encoding="utf-8")
    gates._STREAMLIT_PROC = subprocess.Popen(
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
    if not gates.wait_http():
        raise RuntimeError("Fresh Streamlit failed to become ready on :8501")
    print(f"[streamlit] fresh pid={gates._STREAMLIT_PROC.pid}", flush=True)


def run_related_units(product: str) -> dict:
    out = EV / f"units_related_{product}.txt"
    tests = [
        "tests/test_session_widget_safe.py",
        "tests/test_creative_experience_polish.py",
        "tests/test_backing_source_navigation.py",
        "tests/test_source_identity_qa_fixes.py",
        "tests/test_songs_hub_source_ownership_ui.py",
        "tests/test_source_authority_coherence.py",
        "tests/test_music_source_ownership.py",
    ]
    print(f"[gate] START units_related sha={product} out={out.name}", flush=True)
    t0 = time.time()
    with out.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(f"# gate=units_related sha={product} started={time.strftime('%Y-%m-%dT%H:%M:%S')}\n")
        fh.flush()
        proc = subprocess.Popen(
            [sys.executable, "-m", "pytest", "-q", "--tb=line", *tests],
            cwd=str(ROOT),
            stdout=fh,
            stderr=subprocess.STDOUT,
            text=True,
            env={**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"},
        )
        rc = proc.wait()
        elapsed = time.time() - t0
        fh.write(f"\n# gate_exit={rc} elapsed_s={elapsed:.1f}\n")
    print(f"[gate] DONE units_related rc={rc} elapsed_s={elapsed:.1f}", flush=True)
    return {
        "label": "units_related",
        "sha": product,
        "rc": rc,
        "elapsed_s": round(elapsed, 1),
        "out": str(out.name),
        "ok": rc == 0,
        "fresh_streamlit": False,
        "recovery": False,
    }


def main() -> int:
    product = gates.sha()
    expected = "91e6735"
    if not product.startswith(expected[:7]):
        print(f"[FAIL] tip sha={product} expected {expected} — refuse remaining package", flush=True)
        return 2

    # Historical authority / PK-E at this tip (do not recombine other SHAs).
    for label in ("authority_fresh", "authority_restored", "practice_key_e"):
        path = EV / f"{label}_{product}.txt"
        if not path.exists():
            print(f"[FAIL] missing historical {path.name}; rerun full package", flush=True)
            return 2
        text = path.read_text(encoding="utf-8", errors="replace")
        if "gate_exit=0" not in text:
            print(f"[FAIL] historical {path.name} not green; rerun that gate", flush=True)
            return 2
        print(f"[hist] keep {path.name} gate_exit=0", flush=True)

    results: list[dict] = []
    summary_path = EV / f"gate_summary_remaining_{product}.json"

    # Overwrite interrupted verify evidence with a fresh run from scratch.
    start_fresh_streamlit_8501()
    results.append(
        gates.run_gate(
            "source_identity_verify",
            "_source_identity_browser_verify.py",
            {"VERIFY_STRESS_CYCLES": "20"},
        )
    )

    start_fresh_streamlit_8501()
    results.append(gates.run_gate("songs_hub_acceptance", "_songs_hub_acceptance_gate.py"))

    start_fresh_streamlit_8501()
    results.append(
        gates.run_gate(
            "focused_comp_20",
            "_focused_custom_comp_gates.py",
            {"FOCUSED_GATE": "comp", "FOCUSED_COMP_CYCLES": "20"},
        )
    )

    start_fresh_streamlit_8501()
    results.append(
        gates.run_gate(
            "focused_comp_to_custom_20",
            "_focused_comp_to_custom_gate.py",
            {"FOCUSED_LEAVE_CYCLES": "20"},
        )
    )

    results.append(run_related_units(product))

    summary = {
        "sha": product,
        "mode": "remaining_after_historical_authority_pk",
        "historical_kept": ["authority_fresh", "authority_restored", "practice_key_e"],
        "results": results,
        "all_ok": all(r.get("ok") for r in results),
        "recovery": False,
        "ensure_songs_allow_reload": "0",
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)
    print(f"GATES_EXIT={0 if summary['all_ok'] else 1}", flush=True)
    return 0 if summary["all_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
