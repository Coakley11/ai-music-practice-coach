"""Process-lifetime backing WAV/timeline caches (survive Streamlit script reruns).

The main Streamlit script re-executes top-to-bottom each run. A plain
``_BACKING_WAV_CACHE = {}`` in that file would wipe neighbor prefetch between
Play and Key-cycle CONTINUE_PLAY. Imported module globals persist for the
server process lifetime.
"""

from __future__ import annotations

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


__all__ = [
    "BACKING_CACHE_MAX",
    "BACKING_TIMELINE_CACHE",
    "BACKING_WAV_CACHE",
    "BACKING_WAV_EXECUTOR",
    "BACKING_WAV_FUTURES",
    "evict_oldest",
]
