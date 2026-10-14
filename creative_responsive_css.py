"""MC3.1 — responsive layout for Creative › Phrase / Motif and Missions.

Scoped to the Creative button groups and cards only (``.st-key-…`` containers), so no other
page changes. On a phone the action rows become two-up grids (Streamlit otherwise stacks
every button full-width), with comfortable 44 px touch targets; desktop keeps its rows.
The span card and the Mission heading wrap instead of clipping.
"""

from __future__ import annotations

# Button groups (st.container keys) that become 2-up grids on a phone.
BUTTON_GROUPS: tuple[str, ...] = (
    "improv_motif_gen_actions",
    "improv_motif_transforms",
    "improv_motif_pattern_actions",
    "improv_motif_output_actions",
    "improv_span_motif_actions",
    "improv_span_motif_develop",
    "improv_mission_gen_actions",
    "improv_mission_transforms",
    "improv_span_mission_actions",
)

PHONE_MAX_WIDTH_PX = 640


def creative_responsive_css() -> str:
    groups_block = ",\n".join(
        f'  .st-key-{g} [data-testid="stHorizontalBlock"]' for g in BUTTON_GROUPS
    )
    groups_col = ",\n".join(
        f'  .st-key-{g} [data-testid="stColumn"]' for g in BUTTON_GROUPS
    )
    groups_btn = ",\n".join(f"  .st-key-{g} .stButton > button" for g in BUTTON_GROUPS)
    return f"""
<style>
/* Harmonic span card: full chords, relationship, section and ★ Recommended always readable. */
.mc-span-card {{
  border: 1px solid rgba(124, 58, 237, 0.25);
  border-radius: 10px;
  padding: 0.45rem 0.7rem;
  margin: 0.15rem 0 0.6rem 0;
  max-width: 100%;
  box-sizing: border-box;
  overflow-wrap: anywhere;
  word-break: normal;
}}
.mc-span-card .mc-span-chords {{ font-weight: 700; line-height: 1.35; }}
.mc-span-card .mc-span-meta {{ font-size: 0.86rem; opacity: 0.85; line-height: 1.35; }}
.mc-span-card .mc-span-roman {{ font-size: 0.8rem; opacity: 0.75; }}
/* Mission / Span heading above the example: wraps, never pushed off the left edge. */
.mc-mission-head {{
  max-width: 100%;
  box-sizing: border-box;
  overflow-wrap: anywhere;
  margin: 0.1rem 0 0.5rem 0;
  line-height: 1.4;
}}
.mc-mission-head .mc-mission-head-chords {{ opacity: 0.8; font-weight: 400; }}

@media (max-width: {PHONE_MAX_WIDTH_PX}px) {{
{groups_block} {{
    display: flex !important;
    flex-direction: row !important;
    flex-wrap: wrap !important;
    gap: 0.45rem !important;
  }}
{groups_col} {{
    flex: 1 1 calc(50% - 0.45rem) !important;
    width: calc(50% - 0.45rem) !important;
    min-width: calc(50% - 0.45rem) !important;
    max-width: 100% !important;
  }}
{groups_btn} {{
    min-height: 2.75rem !important;
    white-space: normal !important;
    line-height: 1.2 !important;
    padding: 0.35rem 0.5rem !important;
  }}
  .mc-span-card {{ padding: 0.4rem 0.55rem; }}
}}
</style>
"""


__all__ = ["BUTTON_GROUPS", "PHONE_MAX_WIDTH_PX", "creative_responsive_css"]
