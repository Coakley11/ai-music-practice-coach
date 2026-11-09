"""Which Backing sound each instrument is using in *this* server, for the developer line in Advanced settings.

The recorded instruments are switched on by the server's environment (``MUSIC_DRUM_KIT_V2``, ``MUSIC_UPRIGHT_BASS``,
``MUSIC_PIANO_V2``, ``MUSIC_ROCK_GUITAR``), so a deployed app can only be checked from inside it. Each entry is
read from the instrument's own module, which also falls back when its sample pack is missing, so the line shows
what actually plays, not merely what was asked for.
"""

from __future__ import annotations

import os

_SWITCHES = ("MUSIC_DRUM_KIT_V2", "MUSIC_UPRIGHT_BASS", "MUSIC_PIANO_V2", "MUSIC_ROCK_GUITAR", "MUSIC_BACKING_LOUDNESS")


def sound_engine_status() -> list[tuple[str, str]]:
    """(instrument, what plays) for drums, upright bass, piano, Rock guitar and the master."""
    rows: list[tuple[str, str]] = []
    try:
        import backing_drum_kit as dk
        import backing_drum_samples as ds

        token = ds.pack_token()
        rows.append(("Drums", f"recorded kit ({token})" if dk.drum_kit_enabled() and token != "synth" else
                     ("synthesized (kit switched on, pack missing)" if dk.drum_kit_enabled() else "synthesized")))
    except Exception as e:  # noqa: BLE001
        rows.append(("Drums", f"unknown ({type(e).__name__})"))
    try:
        import backing_bass_voice as bv

        m = bv.upright_mode()
        rows.append(("Upright bass", {"recorded": "recorded (Jazz swing)", "model": "modelled (pack missing or asked for)"}.get(m, "synthesized")))
    except Exception as e:  # noqa: BLE001
        rows.append(("Upright bass", f"unknown ({type(e).__name__})"))
    try:
        import backing_pianist as bp

        m = bp.mode()
        rows.append(("Piano", {"recorded": "Steinway pianist", "varied": "varied comping, synthesized piano"}.get(m, "synthesized")))
    except Exception as e:  # noqa: BLE001
        rows.append(("Piano", f"unknown ({type(e).__name__})"))
    try:
        import backing_rock_guitar as rg

        rows.append(("Rock guitar", "recorded (Rock groove)" if rg.enabled() else "off"))
    except Exception as e:  # noqa: BLE001
        rows.append(("Rock guitar", f"unknown ({type(e).__name__})"))
    try:
        import backing_loudness as ld

        rows.append(("Master", f"loudness-matched ({ld.target_lufs():g} LUFS)" if ld.loudness_mode() else "peak-normalised"))
    except ImportError:
        rows.append(("Master", "peak-normalised"))
    return rows


def sound_engine_line() -> str:
    return " · ".join(f"{name}: {what}" for name, what in sound_engine_status())


def switch_values() -> dict[str, str]:
    """The raw switches as this server sees them ("" when unset)."""
    return {k: str(os.environ.get(k) or "") for k in _SWITCHES}
