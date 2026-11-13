"""M3: a two-bar count-in before a fresh Backing start.

The card's Play (and a Resume that restarts a changed selection) arms it in the browser; the first Backing
player that starts from the top is held at 0:00 until it can play, then two bars of clicks at the selected tempo
and meter sound and the take starts on what would be the next downbeat. Resume never arms it, so a paused take
just continues. Key Cycling (its own dual-buffer start) and Karaoke (its own countdown) are left alone.

The clicks are Web Audio in the page; the take is not changed, so its follow timeline, the highlight and every
cached take stay exactly as they are (the player sits at 0:00 = bar 1 during the count-in).
"""

from __future__ import annotations

from typing import Any

COUNT_IN_BARS = 2
# The choice (a plain session key, never a widget key: Streamlit drops / resets an unrendered widget's value)
# and the Advanced-settings toggle that edits it.
COUNT_IN_SETTING_KEY = "backing_count_in_on"
COUNT_IN_WIDGET_KEY = "backing_count_in_widget"


def count_in_enabled(session: Any) -> bool:
    """On unless the person switched it off (Advanced playback settings)."""
    try:
        return bool((session or {}).get(COUNT_IN_SETTING_KEY, True))
    except Exception:
        return True


def set_count_in_enabled(session: Any, on: bool) -> None:
    """The toggle's on_change: record the choice where no widget cleanup can reach it."""
    session[COUNT_IN_SETTING_KEY] = bool(on)


def count_in_spec(*, bpm: Any, time_signature: Any, bars: int = COUNT_IN_BARS) -> dict[str, Any] | None:
    """What the browser needs to count in: pulses per bar, pulse length, compound grouping.

    4/4 = 4 quarter clicks a bar; 3/4 = 3; 6/8 = 6 eighth clicks a bar with the dotted-quarter pulses (1 and 4)
    marked, the bar's first click accented in every meter. Same grid as songs.meter.meter_timing, which the
    renderer uses for the take itself.
    """
    try:
        from songs.meter import meter_timing

        b = int(round(float(bpm)))
        if b <= 0:
            return None
        t = meter_timing(b, str(time_signature or "4/4"))
    except Exception:
        return None
    return {
        "bars": int(bars),
        "pulses": int(t.pulses_per_bar),
        "pulse_sec": float(t.pulse_sec),
        "bar_sec": float(t.bar_sec),
        "compound": bool(t.compound),
        "bpm": int(b),
        "meter": str(t.time_signature),
    }


def backing_count_in_for_card(session: Any, *, karaoke: bool, cycle_active: bool) -> dict[str, Any] | None:
    """The count-in the card arms on Play, or None (off, Karaoke, Key Cycling, no tempo)."""
    if karaoke or cycle_active or not count_in_enabled(session):
        return None
    s = session or {}
    return count_in_spec(bpm=s.get("backing_track_bpm") or s.get("bpm"), time_signature=s.get("backing_time_signature") or "4/4")
