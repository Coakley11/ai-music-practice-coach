"""Key authority for Mission Recording → Upload Analysis.

Three different keys exist and must not be confused:

* **original / saved song key** — catalog metadata of the song ("Autumn Leaves is in B minor");
* **Mission Practice / Concert key** — the *sounding* key the Mission was practised and recorded in
  ("A minor"); this is what the backing, the take and the analysis use, and it is sealed with the take;
* **written key** — instrument-facing notation (a Bb clarinet in A minor concert reads B minor); it is a
  projection of the concert key per instrument, never a source of truth.

For a Mission take the concert key is captured when the take is handed off and travels in the pending
envelope (``sealed_analysis_context.key_authority``), so it stays authoritative after the Mission's
Practice Key changes, in a fresh session, or on another device. Takes recorded before this existed fall
back to what the envelope already carried (the sealed span's Practice Key, or the sealed Mission context).
"""

from __future__ import annotations

from typing import Any


def _token(value: Any) -> str:
    return str(value or "").strip()


def capture_key_authority(session: dict[str, Any]) -> dict[str, Any]:
    """The keys the Mission take is being recorded with (call in the session that recorded it)."""
    original = concert = chart = written = instrument = ""
    source = "mission"
    try:
        from songs.key_state import resolve_active_musical_key

        active = resolve_active_musical_key(session)
        original = _token(active.original_key)
        concert = _token(active.practice_concert_key)
        chart = _token(active.chart_key)
        written = _token(active.written_key)
        instrument = _token(active.instrument)
    except Exception:
        concert = _token(session.get("concert_key") or session.get("display_key"))
    try:
        from mission_span_take import analysis_span_take

        span_take = analysis_span_take(session)
    except ImportError:
        span_take = None
    if span_take and isinstance(span_take.get("span"), dict):
        span = span_take["span"]  # a 2/3-chord take: its sealed span is the Mission's key
        concert = _token(span.get("practice_key")) or concert
        chart = _token(span.get("chart_key")) or chart
        source = "span"
    return {"original_key": original, "concert_key": concert, "chart_key": chart, "written_key": written,
            "instrument": instrument, "source": source}


def derive_key_authority_from_envelope(env: dict[str, Any]) -> dict[str, Any]:
    """Older envelopes: the best sealed evidence they already carry."""
    span = ((env.get("span_take") or {}).get("span") or {}) if isinstance(env.get("span_take"), dict) else {}
    if span.get("practice_key"):
        return {"concert_key": _token(span["practice_key"]), "chart_key": _token(span.get("chart_key")),
                "original_key": "", "source": "span", "derived": True}
    seal = env.get("recording_seal") if isinstance(env.get("recording_seal"), dict) else {}
    if seal.get("display_key"):
        return {"concert_key": _token(seal["display_key"]), "chart_key": "", "original_key": "",
                "source": "seal", "derived": True}
    return {}


def concert_choice(token: str) -> str:
    """The Upload setup selectbox label for a concert key token (``Am`` → ``A minor``)."""
    from recording_analysis_context import coerce_concert_key_choice, concert_key_choice_from_token

    return coerce_concert_key_choice(concert_key_choice_from_token(_token(token)))


def seed_recording_concert_key(session: dict[str, Any], key_authority: dict[str, Any] | None = None) -> str:
    """Make the take's concert key the Upload Analysis "Concert Key of this recording" (returns the token)."""
    from recording_analysis_context import ANALYSIS_RECORDING_CONCERT_KEY_KEY

    authority = key_authority if key_authority is not None else capture_key_authority(session)
    token = _token((authority or {}).get("concert_key"))
    if token:
        session[ANALYSIS_RECORDING_CONCERT_KEY_KEY] = concert_choice(token)
    return token


def sealed_key_authority(session: dict[str, Any]) -> dict[str, Any]:
    """Key authority of a take restored from its envelope ({} for a live take)."""
    try:
        from mission_practice_context import sealed_take_analysis_context
    except ImportError:
        return {}
    block = sealed_take_analysis_context(session).get("key_authority")
    return block if isinstance(block, dict) and block.get("concert_key") else {}


def analysis_display_key(ctx: dict[str, Any], fallback: Any) -> str:
    """The key the analyzer works in: a Mission take's concert key (sealed with the take), else ``fallback``
    (the live chart key, as for every other analysis)."""
    authority = ctx.get("mission_key_authority") if isinstance(ctx, dict) else None
    token = _token(authority.get("concert_key")) if isinstance(authority, dict) else ""
    return token or _token(fallback)


__all__ = [
    "analysis_display_key",
    "capture_key_authority",
    "concert_choice",
    "derive_key_authority_from_envelope",
    "seed_recording_concert_key",
    "sealed_key_authority",
]
