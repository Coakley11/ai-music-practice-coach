"""Process-lifetime backing WAV/timeline caches (survive Streamlit script reruns).

The main Streamlit script re-executes top-to-bottom each run. A plain
``_BACKING_WAV_CACHE = {}`` in that file would wipe neighbor prefetch between
Play and Key-cycle CONTINUE_PLAY. Imported module globals persist for the
server process lifetime.
"""

from __future__ import annotations

import hashlib
from concurrent.futures import Future, ThreadPoolExecutor

BACKING_WAV_CACHE: dict = {}
BACKING_TIMELINE_CACHE: dict = {}
BACKING_CACHE_MAX = 12

# Neighbor-key audio synthesis (``generate_backing_track``) is the single most
# expensive step in Key Cycle prefetch — observed 5-15s+ per target key. Running
# it inline inside the ``run_every=2`` prefetch fragment blocks that session's
# single script-run thread, so ordinary clicks (Play, Open lead sheet, the Key
# cycling On/Off radio itself) appear to hang for as long as synthesis is in
# flight. Offloading the synthesis call to a background thread keeps every
# fragment tick fast; the fragment only submits/polls a Future here and does
# the (cheap) bookkeeping + any ``st.*`` calls back on the main thread once the
# result is ready. One worker keeps behavior close to the previous serial
# one-target-per-tick order; imported-module scope keeps the pool alive across
# Streamlit script reruns (see module docstring above).
BACKING_WAV_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="kc-wav-synth")
BACKING_WAV_FUTURES: dict[object, Future] = {}


def evict_oldest(cache: dict) -> None:
    while len(cache) > BACKING_CACHE_MAX:
        try:
            first_key = next(iter(cache))
        except StopIteration:
            return
        cache.pop(first_key, None)


def install_when_done(signature, fut: Future) -> None:
    """Put a Key Cycle neighbor WAV in the cache the moment its synthesis ends.

    The prefetch fragment used to move a finished job into the cache only on
    its next tick. Once the cycle stepped on, that tick never came, and the
    stepped-to key's own run discarded the finished job (another take
    request) and synthesized the same arrangement again: 12-48 s per key.
    The cache is keyed by the arrangement signature, so the WAV is the one
    that run would render. A job that was cancelled or replaced installs
    nothing.
    """

    def _done(f: Future, sig=signature) -> None:
        try:
            if f.cancelled() or BACKING_WAV_FUTURES.get(sig) is not f:
                return
            wav = f.result()
        except Exception:
            return
        if wav and sig not in BACKING_WAV_CACHE:
            BACKING_WAV_CACHE[sig] = wav
            try:
                evict_oldest(BACKING_WAV_CACHE)
            except RuntimeError:
                pass

    fut.add_done_callback(_done)


def _pitch_class(symbol: str) -> int | None:
    from music_theory import NOTE_TO_MIDI, normalize_root

    s = str(symbol or "").strip()
    if not s:
        return None
    midi = NOTE_TO_MIDI.get(s, NOTE_TO_MIDI.get(normalize_root(s)))
    return None if midi is None else int(midi) % 12


def backing_chord_digest(sections, key: str = "", selected=()) -> str:
    """Short hash of the chords a backing WAV is rendered from (before performance feel).

    The WAV signature names the song, key, tempo and bar counts; without the chords an
    edited progression of the same length replayed the old take. Roots and slash basses are
    hashed as pitch classes relative to ``key``, so a respelling (Db / C#) or the Key Cycling
    prefetch, which transposes the same chart from another key, gives the same digest.
    Only ``selected`` sections count (all when empty), in name order.
    """
    from chord_subdivisions import hit_underlying_chord, is_hit_token, parse_subdivisions
    from music_theory import split_chord

    key_pc = _pitch_class(split_chord(str(key or "C"))[0]) or 0
    want = {str(s) for s in selected or ()}
    parts: list[str] = []
    for name in sorted(sections or {}, key=str):
        if want and str(name) not in want:
            continue
        row: list[str] = []
        for tok in (sections or {}).get(name) or ():
            raw = str((tok.get("chord") if isinstance(tok, dict) else tok) or "").strip()
            hit = is_hit_token(raw)
            cells: list[str] = []
            for sub in parse_subdivisions(hit_underlying_chord(raw) if hit else raw):
                head, _, slash = sub.chord.partition("/")
                root, suffix = split_chord(head)
                root_pc = _pitch_class(root)
                if root_pc is None:
                    cell = sub.chord.lower()
                else:
                    cell = f"{(root_pc - key_pc) % 12}{suffix}"
                    if slash:
                        bass_pc = _pitch_class(slash)
                        cell += f"/{(bass_pc - key_pc) % 12}" if bass_pc is not None else f"/{slash}"
                cells.append(f"{cell}:{sub.weight:g}{'p' if sub.push else ''}")
            row.append("|".join(cells) + (".hit" if hit else ""))
        parts.append(f"{name}=" + ",".join(row))
    return hashlib.sha1("\n".join(parts).encode("utf-8")).hexdigest()[:12]


__all__ = [
    "BACKING_CACHE_MAX",
    "BACKING_TIMELINE_CACHE",
    "BACKING_WAV_CACHE",
    "BACKING_WAV_EXECUTOR",
    "BACKING_WAV_FUTURES",
    "backing_chord_digest",
    "evict_oldest",
]
