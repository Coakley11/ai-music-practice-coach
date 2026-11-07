"""Test helper: what the recorded pianist plays, so the arranger's rendered tests can check it too.

Today's comping is watched through ``_add_tone``, ``_add_comp_chord`` and ``add_piano_note``; the recorded
pianist plays through the sampled instrument instead, which those watchers never see.
"""

from __future__ import annotations

from contextlib import contextmanager
from unittest import mock

import backing_pianist as pn
import backing_sampled_instrument as si


def on() -> bool:
    """The new pianist is playing (either voice)."""
    return bool(pn.mode())


@contextmanager
def recorded_notes():
    """Every note the recorded piano plays: (start_sec, held_sec, midi)."""
    notes: list[tuple[float, float, int]] = []
    real = si.SampledInstrument.add_note

    def add_note(self, bus, sr, start_sec, held_sec, midi, *args, **kwargs):
        if self.folder.name == pn.PIANO_PACK.name:
            notes.append((float(start_sec), float(held_sec), int(midi)))
        return real(self, bus, sr, start_sec, held_sec, midi, *args, **kwargs)

    with mock.patch.object(si.SampledInstrument, "add_note", add_note):
        yield notes


def chords(notes, *, spread: float = 0.08) -> list[tuple[float, float, tuple[int, ...]]]:
    """Notes struck together (a hand's roll and humanising included) as (start_sec, held_sec, midis)."""
    out: list[list] = []
    for t, d, m in sorted(notes):
        if out and t - out[-1][0] <= spread:
            out[-1][2].append(m)
            out[-1][1] = max(out[-1][1], d)
        else:
            out.append([t, d, [m]])
    return [(t, d, tuple(sorted(ms))) for t, d, ms in out]
