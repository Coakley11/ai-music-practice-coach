"""Pure mission alignment payloads for deferred Mission Backing handoffs."""

from __future__ import annotations

import hashlib
import json
from typing import Any

MISSION_PENDING_BACKING_ALIGNMENT_KEY = "_mission_pending_backing_alignment"


def mission_alignment_fingerprint(payload: dict[str, Any]) -> str:
    raw = json.dumps(
        {
            "mission_id": payload.get("mission_id"),
            "mission_session_id": payload.get("mission_session_id"),
            "section_label": payload.get("section_label"),
            "chord_symbol": payload.get("chord_symbol"),
            "chord_index": payload.get("chord_index"),
            "example_fp": payload.get("example_fingerprint"),
        },
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def build_mission_backing_alignment_payload(
    session: dict[str, Any],
    *,
    mission: str,
    cur_chord: str,
    section_label: str,
    chord_idx: int,
    song_title: str,
    song_pick_key: str = "",
    concert_key: str = "",
    display_key: str = "",
    concert_tonic: str = "",
    concert_mode: str = "",
    written_tonic: str = "",
    written_mode: str = "",
    example: Any | None = None,
    with_practice_lick: bool = False,
    return_route: str = "creative",
    backing_scope: str = "mission_chord",
) -> dict[str, Any]:
    """Capture authoritative mission UI state without mutating workflow."""
    mission_session_id = ""
    mission_id = str(mission or "").strip()
    try:
        from music_workflow_state_store import get_active_workflow_pointer, get_workflow_blob

        ptr = get_active_workflow_pointer(session)
        if ptr and str(ptr.workflow_owner or "") == "mission_jam":
            mission_session_id = str(ptr.workflow_session_id or "")
            blob = get_workflow_blob(session, ptr.workflow_owner, ptr.workflow_session_id)
            if blob is not None:
                mission_id = str(blob.mission_id or blob.mission_type or mission_id or mission)
                if not concert_tonic:
                    concert_tonic = str(blob.keys.practice_tonic or "")
                if not concert_mode:
                    concert_mode = str(blob.keys.practice_mode or "")
    except ImportError:
        pass

    pick = str(song_pick_key or session.get("active_catalog_pick_key") or session.get("song") or "").strip()
    concert = str(concert_key or session.get("concert_key") or "").strip()
    display = str(display_key or session.get("display_key") or "").strip()
    example_fp = ""
    example_notes: list[Any] = []
    example_midi: list[Any] = []
    example_mission = ""
    example_variant = ""
    example_section = ""
    example_artifact_id = ""
    example_abc = ""
    example_tab = ""
    example_display = ""
    example_rhythm = ""
    example_rhythm_key = ""
    example_rhythm_symbols: list[Any] = []
    if example is not None:
        motif = getattr(example, "motif", None) or {}
        if isinstance(motif, dict):
            example_notes = [str(n) for n in (motif.get("notes") or [])]
            example_midi = [int(m) for m in (motif.get("midi") or []) if str(m).strip() != ""]
            example_display = str(motif.get("display") or "")
            example_rhythm = str(motif.get("rhythm") or "")
            example_rhythm_key = str(motif.get("rhythm_key") or "")
            example_rhythm_symbols = [str(s) for s in (motif.get("rhythm_symbols") or [])]
        example_mission = str(getattr(example, "mission", "") or "")
        example_variant = str(getattr(example, "variant", "") or "")
        example_section = str(getattr(example, "section", "") or "")
        example_abc = str(getattr(example, "abc", "") or "")
        example_tab = str(getattr(example, "tab", "") or "")
        try:
            from improvisation_missions import motif_material_fingerprint

            example_fp = motif_material_fingerprint(motif if isinstance(motif, dict) else {})
        except ImportError:
            example_fp = str(getattr(example, "chord", "") or "")
        try:
            example_artifact_id = str(session.get("_mission_example_artifact_id") or "")
        except Exception:
            example_artifact_id = ""

    payload = {
        "song_pick_key": pick,
        "song_title": str(song_title or "").strip(),
        "mission_session_id": mission_session_id,
        "mission_id": mission_id,
        "section_label": str(section_label or "").strip(),
        "chord_symbol": str(cur_chord or "").strip(),
        "chord_display_label": f"{section_label} · {cur_chord}".strip(" ·"),
        "chord_index": int(chord_idx),
        "example_fingerprint": example_fp,
        "example_material_fp": example_fp,
        "example_artifact_id": example_artifact_id,
        "example_mission": example_mission,
        "example_variant": example_variant,
        "example_section": example_section or str(section_label or "").strip(),
        "example_abc": example_abc,
        "example_tab": example_tab,
        "example_display": example_display,
        "example_rhythm": example_rhythm,
        "example_rhythm_key": example_rhythm_key,
        "example_rhythm_symbols": example_rhythm_symbols,
        "example_notes": example_notes,
        "example_midi": example_midi,
        "concert_key": concert,
        "display_key": display,
        "concert_tonic": concert_tonic,
        "concert_mode": concert_mode,
        "written_tonic": written_tonic,
        "written_mode": written_mode,
        "with_practice_lick": bool(with_practice_lick),
        "backing_scope": backing_scope,
        "return_route": str(return_route or "creative").strip() or "creative",
    }
    payload["alignment_fingerprint"] = mission_alignment_fingerprint(payload)
    return payload


def apply_pending_mission_backing_alignment(session: dict[str, Any], alignment: dict[str, Any]) -> bool:
    """Apply queued alignment transactionally (pre-widget only)."""
    if not isinstance(alignment, dict) or not str(alignment.get("chord_symbol") or "").strip():
        return False
    try:
        from music_workflow_mutation import mutate_mission_handoff_aligned

        result = mutate_mission_handoff_aligned(
            session,
            mission=str(alignment.get("mission_id") or ""),
            cur_chord=str(alignment.get("chord_symbol") or ""),
            section_label=str(alignment.get("section_label") or ""),
            chord_idx=int(alignment.get("chord_index") or 0),
            example=None,
        )
        return bool(result.ok)
    except ImportError:
        return False


__all__ = [
    "MISSION_PENDING_BACKING_ALIGNMENT_KEY",
    "apply_pending_mission_backing_alignment",
    "build_mission_backing_alignment_payload",
    "mission_alignment_fingerprint",
]
