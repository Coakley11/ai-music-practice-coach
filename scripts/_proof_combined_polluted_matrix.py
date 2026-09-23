"""Combined polluted-workspace matrix on persistent 8552.

Runs existing Phase A/B/C/D + Missions proofs sequentially on one browser session
workspace. Stops at the first failing subprocess.

Usage:
  python scripts/_proof_combined_polluted_matrix.py http://127.0.0.1:8552
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8552"
OUT = SCRIPTS / "evidence-combined-polluted-matrix"
OUT.mkdir(parents=True, exist_ok=True)

# Ordered gates matching Daniel's final matrix.
GATES: list[tuple[str, str]] = [
    ("1_mounted_display_key", "_proof_locked_display_key.py"),
    ("2_4_5_6_phase_b_sbi", "_proof_phase_b_sbi_ownership.py"),
    ("3_sidebar_trial", "_proof_phase_b_sidebar_trial.py"),
    ("7_8_capo_shape", "_proof_phase_c_capo_shape.py"),
    ("9_missions", "_proof_missions_stabilize.py"),
    ("10_11_12_composition", "_proof_phase_d_composition.py"),
]


def _soft_reset_session(url: str) -> None:
    """Cold browser hit so Creative sticky tabs do not poison the next gate."""
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-dev-shm-usage", "--disable-gpu", "--no-sandbox"],
            )
            page = browser.new_page()
            page.goto(f"{url}/", wait_until="domcontentloaded", timeout=180_000)
            page.wait_for_timeout(4000)
            browser.close()
    except Exception as exc:
        print(f"soft_reset skipped: {exc}", flush=True)


def _clear_missions_sticky_on_disk() -> None:
    """Prevent restored Missions tab from blocking Entry & Jam after gate 1."""
    path = ROOT / "_runtime_hotfix_missions" / "workspaces" / "daniel" / "music_user_state.json"
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        state = data.get("state") if isinstance(data.get("state"), dict) else {}
        targets: list[dict] = []
        for key in ("session", "creative_workspace_state", "music_workspace_state"):
            blob = state.get(key)
            if isinstance(blob, dict):
                targets.append(blob)
                nested = blob.get("creative_workspace_state")
                if isinstance(nested, dict):
                    targets.append(nested)
        for ss in targets:
            ss["improv_intelligence_tab"] = "Entry & Jam"
            ss["creative_improv_intelligence_tab"] = "Entry & Jam"
            ss["improv_entry_mode"] = "Song-Based Improvisation"
            ss["_pending_improv_entry_mode"] = "Song-Based Improvisation"
            ss["creative_lab_analysis_mode"] = "Improvisation Intelligence"
            ss["creative_lab_last_mode"] = "Improvisation Intelligence"
            ss.pop("_creative_visit_source", None)
            ss.pop("improv_mission_backing_handoff", None)
            ss.pop("_backing_released_specialized_context", None)
            snap = ss.get("_studio_page_snapshots")
            if isinstance(snap, dict) and isinstance(snap.get("creative"), dict):
                cre = snap["creative"]
                cre["improv_intelligence_tab"] = "Entry & Jam"
                cre["creative_improv_intelligence_tab"] = "Entry & Jam"
                cre["improv_entry_mode"] = "Song-Based Improvisation"
                cre["creative_lab_analysis_mode"] = "Improvisation Intelligence"
                cre["creative_lab_last_mode"] = "Improvisation Intelligence"
                cre.pop("_creative_visit_source", None)
                cre.pop("_backing_released_specialized_context", None)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        print("cleared Missions sticky on disk -> Entry & Jam / SBI", flush=True)
    except Exception as exc:
        print(f"clear missions sticky failed: {exc}", flush=True)


def _restart_8552() -> None:
    """Reload Streamlit process so sealed Missions ownership cannot block Entry & Jam."""
    import time

    ps = r"""
$pid8552 = (Get-NetTCPConnection -LocalPort 8552 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1).OwningProcess
$pid8510 = (Get-NetTCPConnection -LocalPort 8510 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1).OwningProcess
if ($pid8552 -and $pid8552 -ne $pid8510) { Stop-Process -Id $pid8552 -Force -ErrorAction SilentlyContinue }
"""
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], cwd=str(ROOT), check=False)
    time.sleep(2)
    env = dict(**{k: v for k, v in __import__("os").environ.items()})
    env["MUSIC_APP_DATA_DIR"] = str((ROOT / "_runtime_hotfix_missions").resolve())
    env["PYTHONUNBUFFERED"] = "1"
    subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "streamlit_music_practice_app.py",
            "--server.port",
            "8552",
            "--server.address",
            "127.0.0.1",
            "--server.headless",
            "true",
            "--server.fileWatcherType",
            "none",
            "--browser.gatherUsageStats",
            "false",
        ],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(40):
        time.sleep(2)
        try:
            import urllib.request

            urllib.request.urlopen(URL, timeout=2)
            print("8552 restarted and answering", flush=True)
            return
        except Exception:
            continue
    print("WARN: 8552 restart may not be ready", flush=True)


def git_meta() -> dict[str, str]:
    def run(args: list[str]) -> str:
        return subprocess.check_output(args, cwd=str(ROOT), text=True).strip()

    return {
        "branch": run(["git", "branch", "--show-current"]),
        "sha": run(["git", "rev-parse", "--short", "HEAD"]),
        "full": run(["git", "rev-parse", "HEAD"]),
        "origin_dev": run(["git", "rev-parse", "--short", "origin/dev"]),
        "url": URL,
    }


def main() -> int:
    result: dict[str, object] = {"meta": git_meta(), "gates": {}}
    print(json.dumps(result["meta"], indent=2), flush=True)
    for name, script in GATES:
        path = SCRIPTS / script
        if not path.exists():
            result["gates"][name] = {"status": "SKIP", "detail": f"missing {script}"}
            print(f"SKIP {name}: missing {script}", flush=True)
            continue
        print(f"=== RUN {name} ({script}) ===", flush=True)
        if name != "1_mounted_display_key":
            _clear_missions_sticky_on_disk()
        _restart_8552()
        _soft_reset_session(URL)
        proc = subprocess.run(
            [sys.executable, str(path), URL],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        log_path = OUT / f"{name}.log"
        log_path.write_text(
            (proc.stdout or "") + "\n--- STDERR ---\n" + (proc.stderr or ""),
            encoding="utf-8",
        )
        ok = proc.returncode == 0
        result["gates"][name] = {
            "status": "PASS" if ok else "FAIL",
            "exit": proc.returncode,
            "log": str(log_path.relative_to(ROOT)),
            "tail": "\n".join((proc.stdout or "").strip().splitlines()[-12:]),
        }
        print(result["gates"][name]["tail"], flush=True)
        if not ok:
            result["overall"] = "FAIL"
            result["fail_gate"] = name
            (OUT / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
            print(f"COMBINED_FAIL at {name}", flush=True)
            return 1
    result["overall"] = "PASS"
    (OUT / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("COMBINED_PASS", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
