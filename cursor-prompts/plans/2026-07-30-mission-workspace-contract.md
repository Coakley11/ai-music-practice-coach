# Creative Workspace Contract (long-term design)

**Last updated:** 2026-08-01  
**Status:** Items **1–7** live-accepted & frozen on live `dev` (Item 7 @ rev **319**, 2026-08-03); Item **8** pending — [plan](./plans/2026-08-02-phase1-creative-state-persistence-remaining.md).  
**Code:** `creative_workspace_persistence.py`, `improvisation_mission_persistence.py`, `music_persistent_state._PERSIST_KEYS`, `studio_page_persistence` creative/backing snapshots.

---

## Intent

The **entire Creative page** behaves like **one cloud document** per account. Refresh, reboot, or switching devices (e.g. Dell ↔ phone) must restore the same workspace—not regenerate educational content.

There is **one Creative workspace per account**. **Latest saved state wins** (no conflict resolution or version history for v1).

Mission Backing Jam is part of this same document (mission, motif, notation, transport).

---

## What the workspace must restore

| Area | Session / canonical keys (representative) |
|------|-------------------------------------------|
| Creative tab & analysis mode | `improv_intelligence_tab`, `creative_improv_intelligence_tab`, `creative_lab_analysis_mode` |
| Deep Harmonic Analyzer | `deep_harmony_lesson_step`, `improv_deep_harmony_dha_section_idx` |
| Harmony Map | `harmony_map_section`, `harmony_map_chord` |
| Phrase & Motif | `improv_motif`, `improv_motif_abc`, `improv_motif_tab`, `improv_motif_output_mode` |
| Mission selection | `improv_active_mission`, `improv_mission_pick` |
| Song / section / chord | `ii_selected_*`, `improv_mission_progression` |
| Generated Mission example | `improv_mission_example` (full blob) |
| Difficulty variant | `variant` inside example + `improv_mission_variant` |
| Mission Backing Jam | `improv_mission_practice_lick` + `backing_track_*` |
| AI Metrics | `improv_ai_metric_ids`, `analysis_criteria_locked` |
| Workspace stamp | `improv_mission_workspace_updated_at` |
| Creative canonical | `creative_session` |

---

## Single source of truth: motif

The stored **`motif` object** inside `improv_mission_example` / `improv_mission_practice_lick` / `improv_motif` is authoritative.

**Must render from motif (never regenerate the phrase on restore):**

- Notes and rhythm display  
- Sheet music (ABC)  
- Guitar TAB  
- Playback (ABC / abcjs)  
- Piano keyboard visualization  

Allowed on restore: **rebuild notation/TAB/display at current BPM or instrument** from the same motif.  
Forbidden on restore: new random phrase for the same saved example.

---

## Persistence architecture (do not fork)

1. **`_PERSIST_KEYS`** — Creative workspace keys in the cloud envelope.  
2. **Page snapshots** — `creative` + `backing` whitelists in `studio_page_persistence.py`.  
3. **`sync_creative_workspace_before_persist`** — before disk/cloud save; stamps `improv_mission_workspace_updated_at`.  
4. **`apply_cloud_creative_state_if_allowed`** — latest wins on restore.  
5. **`music_creative_cloud_drift`** — cross-device resync when cloud differs.

Do **not** introduce a separate Creative-only sync channel.

---

## Cross-device behavior

Laptop and phone are **two windows into the same Creative workspace**. Changes on either device appear on the other after sync.

---

## Official manual sign-off (copy-paste)

Complete on **Streamlit Cloud `dev`** with the **same account** on **two devices** (e.g. Dell + phone). Check every box before marking the architecture **frozen**.

```
Creative Workspace — Manual Acceptance Sign-off
Account: ______________________   Date: __________
Tester (devices): ________________________________

□ Refresh restores the same Creative tab.
□ Refresh restores the same analysis mode.
□ Deep Harmonic Analyzer restores the same lesson step and selected section.
□ Harmony Map restores the same selected chord and analysis.
□ Phrase & Motif restores the same generated motif.
□ Phrase & Motif restores the same ABC, notation, and TAB.
□ Mission restores the same generated example.
□ Harder / Easier / New Idea restore the exact same generated example (same motif notes).
□ Mission Backing Jam restores the same mission.
□ Mission Backing Jam restores the same generated notation.
□ Mission Backing Jam restores the same BPM.
□ Mission Backing Jam restores groove, meter, loop count, and transport settings.
□ Dell → Phone synchronization restores the exact same Creative workspace.
□ Phone → Dell synchronization restores the exact same Creative workspace.
□ Stored motif remains the Single Source of Truth (notation, TAB, MIDI, playback rebuild from the same stored object — never a new random phrase).

Sign-off: PASS / FAIL   Notes: _________________________________
```

When **all items pass**, set plan **Status** to **Frozen (signed off)** and treat future Creative features as **extensions to this contract only** (new keys, not new persistence paths).

---

## Future features (same workspace)

| Feature | Direction |
|---------|-----------|
| **Lick Library** | Entries reference saved `motif` blobs in workspace |
| **Composition Studio handoff** | Import motif + ABC as seed |
| **Practice Chord Coach** | Unified with `practice_chord_coach.py` + `chord_coach_insight` (2026-08-01 in progress) |

---

## Related plans

- [2026-07-30-creative-experience-polish-sprint.md](./2026-07-30-creative-experience-polish-sprint.md)  
- [2026-06-29-creative-backing-track-routing.md](./2026-06-29-creative-backing-track-routing.md)  
- [2026-07-29-flagship-coaching-quality-standard.md](./2026-07-29-flagship-coaching-quality-standard.md) — three-pillar educational checklist  
- [music-persistence-audit-2026-06-08.md](./music-persistence-audit-2026-06-08.md)
