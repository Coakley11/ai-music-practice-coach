"""Offline ownership evidence for Creative/Backing pass-5 blockers (no Streamlit UI)."""

from __future__ import annotations

import json
from pathlib import Path

from custom_progression_lab import format_key_label
from guitar_capo import shape_chart_key_for_concert, shape_tonic_only
from music_workflow_mutation import (
    _invalidate_mission_chord_dependent_session,
    mutate_mission_chord_selection,
)
from music_workflow_pending_song_practice_key_edit import overlay_destination_practice_key
from source_session_state import resolve_sbi_preview


OUT = Path(__file__).resolve().parent


def _shape_of_you_session() -> dict:
    pick = "Pop::Shape of You — Ed Sheeran"
    return {
        "active_catalog_pick_key": pick,
        "display_key": "Dm",
        "concert_key": "Dm",
        "practice_key_by_source": {pick: "Bm"},  # intentional stale store
        "guitar_capo_enabled": True,
        "guitar_capo_shape_key": "E",
        "instrument": "Guitar",
        "selected_song": {
            "title": "Shape of You",
            "artist": "Ed Sheeran",
            "key": "Bm",
            "pick_key": pick,
            "bpm": 82,
        },
        "catalog_session": {
            "pick_key": pick,
            "display_key": "Bm",
            "original_key": "Bm",
            "selected_song": {"title": "Shape of You", "key": "Bm"},
            "sections": {"Verse": ["Bm", "Em", "G", "A"]},
        },
        "improv_song_concert_sections": {"Verse": ["Bm", "Em", "G", "A"]},
        "home_sections": {"Verse": ["Bm", "Em", "G", "A"]},
    }


def main() -> None:
    session = _shape_of_you_session()
    evidence: dict = {"cases": {}}

    # A/B — Song card Shape tonic + SBI Practice Dm
    overlay = overlay_destination_practice_key(session)
    preview = resolve_sbi_preview(session)
    evidence["cases"]["A_song_card_shape"] = {
        "original": "Bm",
        "practice": session["display_key"],
        "shape_control": shape_tonic_only("E"),
        "shape_not_major_label": shape_tonic_only("E") != format_key_label("E"),
        "charts": shape_chart_key_for_concert("Dm", "E"),
        "bad_format_would_say": format_key_label("E"),
    }
    evidence["cases"]["B_sbi"] = {
        "overlay": overlay,
        "preview_key": preview.get("display_key"),
        "store_healed": session.get("practice_key_by_source"),
        "first_chords": {
            k: (v[:3] if isinstance(v, list) else v)
            for k, v in list((preview.get("sections") or {}).items())[:2]
        },
    }

    # D — Mission chord clears stale Em example; key stays Dm
    from improvisation_missions import MISSION_EXAMPLE_KEY

    session[MISSION_EXAMPLE_KEY] = {
        "chord": "Dm",
        "mission": "Chord Tones",
        "motif": {"_concert_chord": "Dm", "notes": ["D", "F", "A"]},
    }
    before_keys = (session["display_key"], session["concert_key"])
    _invalidate_mission_chord_dependent_session(session, new_chord="Am")
    mutate_mission_chord_selection(
        session, chord="Am", section="Verse", chord_index=1, chord_label="Am"
    )
    evidence["cases"]["D_mission_am"] = {
        "example_cleared": MISSION_EXAMPLE_KEY not in session,
        "keys_before": before_keys,
        "keys_after": (session.get("display_key"), session.get("concert_key")),
        "selected": session.get("ii_selected_chord"),
    }

    # F — Shape E → Ebm reprojects
    from improvisation_missions import ChordCoachInsight, MissionExample, refresh_mission_example

    insight = ChordCoachInsight(
        chord="Dm",
        scales=[],
        scale_suggestions=[],
        chord_tones=["D", "F", "A"],
        tensions=[],
        avoid_notes=[],
        target_notes=[],
        motif_idea="",
        resolve_hint="",
        instrument_tips=[],
    )
    example = MissionExample(
        mission="Chord Tones",
        variant="normal",
        chord="Dm",
        section="Verse",
        song_title="Shape of You",
        display_key="Em",
        instrument="Guitar",
        level="Intermediate",
        focus="Improvisation",
        motif={
            "notes": ["E", "G", "B"],
            "display": "E – G – B",
            "_concert_notes": ["D", "F", "A"],
            "_concert_chord": "Dm",
            "_projected_display_key": "Em",
        },
        abc="",
        tab="",
        piano_html="",
        why="",
        practice_steps=[],
        insight=insight,
        show_tab=False,
        show_piano=False,
        concert_key="Dm",
    )
    example.display_key = "Ebm"
    refreshed = refresh_mission_example(example, instrument="Guitar", bpm=96, song_concert_key="Dm")
    evidence["cases"]["F_shape_reproject"] = {
        "concert_notes": list((refreshed.motif or {}).get("_concert_notes") or []),
        "projected_notes": list((refreshed.motif or {}).get("notes") or []),
        "projected_key": (refreshed.motif or {}).get("_projected_display_key"),
        "practice_key_unchanged": "Dm",
    }

    # I — Style/Meter live card preference
    from unittest.mock import MagicMock

    from backing_context import BackingContext
    from backing_context_ui import render_backing_creative_context_card

    ctx = BackingContext(
        source="mission",
        source_label="Mission",
        active_song_id="m1",
        song_title="Mission",
        key="Dm",
        display_key="Dm",
        concert_key="Dm",
        style="Pop groove",
        groove="Pop groove",
        meter="4/4",
        bpm=96,
        source_signature="m1",
    )
    st = MagicMock()
    render_backing_creative_context_card(
        st,
        ctx,
        {
            "backing_groove_style": "Blues",
            "backing_time_signature": "3/4",
            "instrument": "Guitar",
            "display_key": "Dm",
            "concert_key": "Dm",
        },
        applied_bpm=96,
        applied_groove="Pop groove",
        applied_meter="4/4",
        practice_key="Dm",
    )
    html_out = " ".join(str(c.args[0]) for c in st.markdown.call_args_list if c.args)
    evidence["cases"]["I_style_meter_card"] = {
        "has_blues": "Blues" in html_out,
        "has_34": "3/4" in html_out,
        "snippet": html_out[html_out.find("Practice concert key") : html_out.find("Practice concert key") + 220]
        if "Practice concert key" in html_out
        else html_out[:220],
    }

    out_path = OUT / "pass5_ownership_evidence.json"
    out_path.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    text_path = OUT / "pass5_ownership_evidence.txt"
    lines = ["Creative/Backing pass-5 ownership evidence", ""]
    for name, payload in evidence["cases"].items():
        lines.append(f"## {name}")
        lines.append(json.dumps(payload, indent=2))
        lines.append("")
    text_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out_path}")
    print(f"wrote {text_path}")


if __name__ == "__main__":
    main()
