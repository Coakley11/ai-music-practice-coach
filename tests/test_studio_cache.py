"""Smoke tests for session-scoped studio caches."""

from studio_cache import session_cache_get_or_set


def test_session_cache_get_or_set_reuses_value():
    state: dict = {}
    calls = {"n": 0}

    def factory():
        calls["n"] += 1
        return {"value": calls["n"]}

    first = session_cache_get_or_set(state, "demo", ("sig",), factory)
    second = session_cache_get_or_set(state, "demo", ("sig",), factory)
    assert first == second
    assert calls["n"] == 1


def test_session_cache_misses_on_new_signature():
    state: dict = {}
    a = session_cache_get_or_set(state, "demo", ("a",), lambda: 1)
    b = session_cache_get_or_set(state, "demo", ("b",), lambda: 2)
    assert a == 1
    assert b == 2
