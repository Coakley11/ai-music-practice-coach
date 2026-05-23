"""Context-aware “What to do next” hints for studio pages."""

from __future__ import annotations

from typing import Any


def _tuner_in_use(session_state: dict, key_prefix: str) -> bool:
    return any(str(k).startswith(key_prefix) for k in session_state)


def guidance_for_practice(
    *,
    instrument: str,
    session_state: dict,
    full_song: bool,
    active_section: str | None,
    tuner_key_prefix: str = "practice_tuner",
) -> list[str]:
    if _tuner_in_use(session_state, tuner_key_prefix):
        lines = [
            "Play a long note and watch the tuner to keep the pitch centered.",
        ]
        if instrument == "Saxophone":
            lines.append(
                "For saxophone, hold one note for 5–10 seconds and keep the pitch steady."
            )
        elif instrument in ("Trumpet", "Clarinet"):
            lines.append(
                "For brass/reed, sustain one comfortable pitch and aim for steady center."
            )
        return lines[:3]

    lines = [
        "Open the **Chord Chart** expander to review the song.",
        "Use **Generated Music Notation / TAB** for a short practice exercise.",
        "Use **Tuner & Tone** to check pitch and tone before practicing.",
    ]
    if full_song:
        lines.append(
            "Select a **section** above to focus metronome, scales, and section tools."
        )
    else:
        lines.insert(2, "Use the **metronome** to lock in timing on the selected section.")
        lines.append(
            "Start slow and keep rhythm steady before increasing tempo."
        )
    return lines[:4]


def guidance_for_backing(*, has_audio: bool) -> list[str]:
    lines = [
        "Choose **Full Song** or a section, then press **Generate and Play**.",
        "Use **Quick BPM** to slow down or speed up without scrolling.",
        "Press **Stop Backing Track** when you want to stop playback.",
    ]
    if has_audio:
        lines.insert(0, "Audio is ready — adjust **Quick BPM** or section, then regenerate if needed.")
    return lines[:4]


def guidance_for_picker() -> list[str]:
    return [
        "Choose a song from the dropdown, then open **Practice** or **Backing Track**.",
        "Use **Practice** for charts, notation, metronome, and coach tools.",
        "Use **Backing Track** to hear a loop at your chosen tempo.",
    ]


def guidance_for_custom() -> list[str]:
    return [
        "Choose a style and key, click chords to build a section, then press **Finish Song**.",
        "Use **Open in Backing Track** when you are ready to practice your progression.",
        "Set BPM and groove on the backing page after you finish the form.",
    ]


def guidance_for_analysis(*, has_result: bool) -> list[str]:
    if has_result:
        return [
            "Review timing, pitch, and tone scores in the dashboard below.",
            "Try the practice plan suggestions on your next take.",
            "Upload another recording to compare progress.",
        ]
    return [
        "Upload a recording and run **AI coach analysis** for timing, pitch, tone, and feedback.",
        "Use a quiet room and one instrument at a time for clearer results.",
        "Solo practice takes work best; multitrack mode compares layers.",
    ]


def guidance_for_creative() -> list[str]:
    return [
        "Explore harmony and improvisation ideas for your active song key.",
        "Take one idea into **Practice** and loop it with the metronome.",
    ]


def guidance_for_multitrack() -> list[str]:
    return [
        "Record a take over your backing track or practice without playback.",
        "Enable the metronome during playback if you want a steady click.",
    ]


def guidance_for_log() -> list[str]:
    return [
        "Log sessions to track practice time and focus areas over weeks.",
    ]


def render_guidance_card(
    st: Any,
    lines: list[str],
    *,
    title: str = "What to do next",
) -> None:
    """Compact guidance card (markdown bullets inside styled wrapper)."""
    import html

    if not lines:
        return
    st.markdown('<div class="ui-guidance-card">', unsafe_allow_html=True)
    st.markdown(f'<p class="ui-guidance-title">{html.escape(title)}</p>', unsafe_allow_html=True)
    for line in lines:
        st.markdown(f"- {line}")
    st.markdown("</div>", unsafe_allow_html=True)
