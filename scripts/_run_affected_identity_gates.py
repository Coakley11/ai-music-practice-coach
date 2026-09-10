"""Rerun browser gates directly affected by Composition ensure leave-stamp order.

Skips authority / PK-E / full source-identity stress when those paths still
block on live Catalog/Custom radio (unchanged). Fresh Streamlit on :8501 only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import _run_all_identity_gates as gates  # noqa: E402
import _run_remaining_identity_gates as rem  # noqa: E402

EV = gates.EV


def main() -> int:
    product = gates.sha()
    results: list[dict] = []
    summary_path = EV / f"gate_summary_affected_{product}.json"

    rem.start_fresh_streamlit_8501()
    results.append(gates.run_gate("songs_hub_acceptance", "_songs_hub_acceptance_gate.py"))

    rem.start_fresh_streamlit_8501()
    results.append(
        gates.run_gate(
            "focused_comp_20",
            "_focused_custom_comp_gates.py",
            {"FOCUSED_GATE": "comp", "FOCUSED_COMP_CYCLES": "20"},
        )
    )

    rem.start_fresh_streamlit_8501()
    results.append(
        gates.run_gate(
            "focused_comp_to_custom_20",
            "_focused_comp_to_custom_gate.py",
            {"FOCUSED_LEAVE_CYCLES": "20"},
        )
    )

    results.append(rem.run_related_units(product))

    summary = {
        "sha": product,
        "mode": "affected_after_ensure_leave_stamp_reorder",
        "skipped_unchanged_paths": [
            "authority_fresh",
            "authority_restored",
            "practice_key_e",
            "source_identity_verify",
        ],
        "results": results,
        "all_ok": all(r.get("ok") for r in results),
        "recovery": False,
        "ensure_songs_allow_reload": "0",
        "parent_full_package_sha": "106b072",
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)
    print(f"GATES_EXIT={0 if summary['all_ok'] else 1}", flush=True)
    return 0 if summary["all_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
