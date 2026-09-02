"""Inert Key Cycle Practice preview — visual placeholder only.

FUTURE FEATURE. Not part of Creative/Backing stabilization acceptance.
Do not implement transport, temporary playback keys, or persistence here.

See ``cursor-prompts/plans/2026-09-02-key-cycle-practice.md``.
"""

from __future__ import annotations

from typing import Any

KEY_CYCLE_PREVIEW_TITLE = "Key Cycle Practice"
KEY_CYCLE_PREVIEW_STATUS = "Preview — not active yet"
KEY_CYCLE_PREVIEW_OPTIONS: tuple[str, ...] = ("Off", "Half steps", "Whole steps")
KEY_CYCLE_PREVIEW_DEFAULT = "Off"

# Names the real engine must never collide with until that feature is implemented.
KEY_CYCLE_ENGINE_SESSION_KEYS: frozenset[str] = frozenset(
    {
        "key_cycle_enabled",
        "key_cycle_mode",
        "key_cycle_interval",
        "base_practice_key",
        "cycle_playback_key",
        "cycle_semitone_offset",
        "cycle_mode",
        "chart_spelling_preferences",
        "key_cycle_session",
    }
)


def render_key_cycle_practice_preview(st: Any) -> None:
    """Render a disabled visual placeholder under Backing Advanced Settings.

    Must not write session state, persist keys, Practice Key, source ownership,
    scope/loops, transport, or audio/chart transposition.
    """
    options_html = "".join(
        (
            f'<span class="ui-key-cycle-preview-option'
            f'{" is-default" if opt == KEY_CYCLE_PREVIEW_DEFAULT else ""}">'
            f"{opt}</span>"
        )
        for opt in KEY_CYCLE_PREVIEW_OPTIONS
    )
    st.markdown(
        '<style>'
        ".ui-key-cycle-preview{opacity:.72;margin:.75rem 0 .25rem;pointer-events:none;}"
        ".ui-key-cycle-preview-status{font-size:.85rem;margin:.15rem 0 .4rem;}"
        ".ui-key-cycle-preview-options{display:flex;flex-wrap:wrap;gap:.4rem;margin:.2rem 0 .35rem;}"
        ".ui-key-cycle-preview-option{border:1px solid rgba(127,127,127,.45);border-radius:999px;"
        "padding:.15rem .7rem;font-size:.85rem;}"
        ".ui-key-cycle-preview-option.is-default{font-weight:600;}"
        ".ui-key-cycle-preview-help{font-size:.8rem;opacity:.9;margin:.15rem 0 0;}"
        "</style>"
        f'<div class="ui-key-cycle-preview" aria-disabled="true">'
        f"<p class=\"ui-backing-inline-label\">{KEY_CYCLE_PREVIEW_TITLE}</p>"
        f'<p class="ui-key-cycle-preview-status">{KEY_CYCLE_PREVIEW_STATUS}</p>'
        f'<div class="ui-key-cycle-preview-options">{options_html}</div>'
        f"<p class=\"ui-key-cycle-preview-help\">Coming soon — Off / Half steps / Whole steps. "
        f"Does not change Practice Key, playback, charts, or Backing ownership.</p>"
        f"</div>",
        unsafe_allow_html=True,
    )


def key_cycle_preview_writes_session() -> bool:
    """Preview renderer never owns session keys."""
    return False
