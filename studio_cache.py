"""Session-scoped caches for expensive studio derivations.

Uses ``st.session_state`` buckets (not ``st.cache_data``) so caches respect
live widget state and invalidate naturally when signature keys change.
"""

from __future__ import annotations

import copy
from typing import Any, Callable, Hashable, TypeVar

T = TypeVar("T")


def _bucket(session_state: dict, namespace: str) -> dict:
    key = f"_studio_cache_{namespace}"
    store = session_state.get(key)
    if not isinstance(store, dict):
        store = {}
        session_state[key] = store
    return store


def session_cache_get(session_state: dict, namespace: str, sig: Hashable) -> Any | None:
    return _bucket(session_state, namespace).get(sig)


def session_cache_set(
    session_state: dict,
    namespace: str,
    sig: Hashable,
    value: Any,
    *,
    max_entries: int = 10,
) -> Any:
    store = _bucket(session_state, namespace)
    store[sig] = value
    while len(store) > max_entries:
        store.pop(next(iter(store)))
    return value


def session_cache_get_or_set(
    session_state: dict,
    namespace: str,
    sig: Hashable,
    factory: Callable[[], T],
    *,
    max_entries: int = 10,
    copy_result: bool = False,
) -> T:
    hit = session_cache_get(session_state, namespace, sig)
    if hit is not None:
        return copy.deepcopy(hit) if copy_result else hit
    built = factory()
    session_cache_set(session_state, namespace, sig, built, max_entries=max_entries)
    return copy.deepcopy(built) if copy_result else built


def invalidate_session_cache(session_state: dict, namespace: str | None = None) -> None:
    if namespace is None:
        for key in list(session_state.keys()):
            if str(key).startswith("_studio_cache_"):
                session_state.pop(key, None)
        return
    session_state.pop(f"_studio_cache_{namespace}", None)


def sections_tuple_signature(sections: dict[str, list[str]]) -> tuple[tuple[str, tuple[str, ...]], ...]:
    return tuple(
        (name, tuple(str(c) for c in chords))
        for name, chords in sorted(sections.items())
    )
