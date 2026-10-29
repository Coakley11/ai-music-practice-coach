"""Take installation guard. Reads existing owners; never selects a source or starts audio."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TakeRequest:
    source: tuple
    practice_key: str
    mode: str
    cycle: tuple
    transport_generation: int
    prefetch: bool = False


def capture_take_request(session: Any, *, prefetch: bool = False) -> TakeRequest:
    from backing_owner_envelope import get_backing_owner_envelope
    from backing_transport_intent import transport_generation
    from backing_key_cycle import BACKING_KEY_CYCLE_SESSIONS_KEY, resolve_cycle_owner
    from songs.practice_key_state import get_practice_concert_key
    from music_theory import key_mode

    env = get_backing_owner_envelope(session)
    ctx = session.get("backing_context") or {}
    if not isinstance(ctx, dict):
        ctx = {}
    pick = str(ctx.get("bound_pick_key") or session.get("active_catalog_pick_key") or "")
    practice = get_practice_concert_key(
        session, pick_key=pick, default=str(env.practice_key if env else "")
    ) if pick else str(env.practice_key if env else session.get("concert_key") or "")
    import karaoke_mode as km

    singing = km.is_karaoke_session_active(session) and km.is_voice_mode(session)
    if singing:
        # Now Editing is independent of the performance being rendered.
        pick = str(km.current_session_pick_key(session) or "")
        practice = str(km.current_session_practice_key(session) or "")
    owner = resolve_cycle_owner(session)
    bag = session.get(BACKING_KEY_CYCLE_SESSIONS_KEY) or {}
    cycle = bag.get(owner) or {}
    position = () if prefetch else (
        cycle.get("position_seq"), cycle.get("current_playback_key"),
        cycle.get("offset_semitones"), cycle.get("pass_index"),
    )
    return TakeRequest(
        source=("karaoke", km.now_singing_entry_id(session), pick) if singing else (
            env.source if env else "", env.identity if env else "", env.epoch if env else 0,
            session.get("active_music_source"), pick,
            ctx.get("source"), ctx.get("active_song_id"), ctx.get("custom_revision_id"),
            session.get("_explicit_catalog_selection_epoch"),
            session.get("_explicit_custom_activation_epoch"),
        ),
        practice_key=practice,
        mode=key_mode(practice or "C"),
        cycle=(owner, cycle.get("cycle_id"), cycle.get("base_practice_key"),
               cycle.get("interval"), cycle.get("direction"),
               session.get("_kc_prefetch_gen"), *position),
        transport_generation=transport_generation(session),
        prefetch=prefetch,
    )


def take_install_allowed(session: Any, request: TakeRequest) -> bool:
    return isinstance(request, TakeRequest) and request == capture_take_request(session, prefetch=request.prefetch)
