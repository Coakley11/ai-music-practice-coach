"""Source / Practice Key / card coherence contract for Songs + Backing.

Invalid combinations must fail tests and browser walks — never papered over
with isolated label overrides.
"""

from __future__ import annotations

from typing import Any


def collect_source_authority_snapshot(session: dict[str, Any]) -> dict[str, Any]:
    """Capture ownership + Practice Key fields for one sequential step."""
    from songs.music_source import (
        SOURCE_CATALOG,
        SOURCE_COMPOSITION,
        SOURCE_CUSTOM,
        composition_song_is_active,
        custom_progression_is_active,
        explicit_music_source_choice,
        is_composition_song,
        is_custom_progression,
        source_ownership_snapshot,
    )
    from songs.practice_key_state import get_practice_concert_key, resolve_practice_source_pick

    snap = source_ownership_snapshot(session)
    pick = str(snap.get("pick") or "").strip()
    stored_pk = get_practice_concert_key(session, pick) if pick else ""
    live_dk = str(session.get("display_key") or "").strip()
    live_ck = str(session.get("concert_key") or "").strip()
    ctx_source = ""
    ctx_title = ""
    ctx_concert = ""
    try:
        from backing_context import get_backing_context

        ctx = get_backing_context(session)
        if ctx is not None:
            ctx_source = str(ctx.source or "").strip()
            ctx_title = str(ctx.song_title or "").strip()
            ctx_concert = str(ctx.concert_key or "").strip()
    except Exception:
        pass
    owner = ""
    if composition_song_is_active(session) or is_composition_song(session):
        owner = SOURCE_COMPOSITION
    elif custom_progression_is_active(session) or is_custom_progression(session):
        owner = SOURCE_CUSTOM
    else:
        owner = SOURCE_CATALOG
    return {
        **snap,
        "owner": owner,
        "explicit": explicit_music_source_choice(session),
        "display_key": live_dk,
        "concert_key": live_ck,
        "stored_practice_key": stored_pk,
        "settings_pick": resolve_practice_source_pick(session),
        "backing_ctx_source": ctx_source,
        "backing_ctx_title": ctx_title,
        "backing_ctx_concert": ctx_concert,
        "pending_catalog": bool(session.get("_pending_catalog_from_picker_switch")),
        "force_composition_backing": bool(session.get("_force_composition_backing_open")),
        "pending_display_key": str(session.get("_pending_display_key") or "").strip(),
    }


def coherence_violations(
    session: dict[str, Any],
    *,
    card_source: str = "",
    card_practice_key: str = "",
    card_title: str = "",
    sidebar_practice_key: str = "",
    body_text: str = "",
) -> list[str]:
    """Return human-readable invalid combinations (empty = coherent)."""
    from songs.music_source import (
        SOURCE_CATALOG,
        SOURCE_COMPOSITION,
        SOURCE_CUSTOM,
        composition_song_is_active,
        custom_progression_is_active,
        is_composition_song,
        is_custom_progression,
    )

    violations: list[str] = []
    snap = collect_source_authority_snapshot(session)
    pick = str(snap.get("pick") or "")
    owner = str(snap.get("owner") or "")
    explicit = str(snap.get("explicit") or "")
    radio = str(snap.get("radio") or "")
    body = str(body_text or "")

    if owner == SOURCE_CATALOG or explicit == SOURCE_CATALOG or radio.endswith("Catalog"):
        if card_source.lower().startswith("custom"):
            violations.append("catalog_active_with_custom_card")
        if pick.startswith("custom::") and explicit == SOURCE_CATALOG:
            # Pending restore may briefly keep pick; still invalid if card is Custom.
            if card_source.lower().startswith("custom"):
                violations.append("catalog_explicit_custom_pick_card")

    if owner == SOURCE_COMPOSITION or composition_song_is_active(session):
        if "· Custom" in body or "· Custom" in str(card_title):
            violations.append("composition_owner_with_custom_suffix")
        if "Edit chords in" in body and "Custom Progression Lab" in body:
            violations.append("composition_page_has_custom_lab_copy")
        if card_source.lower().startswith("custom"):
            violations.append("composition_active_with_custom_card")
        if pick.startswith("custom::"):
            violations.append("composition_owner_with_custom_pick")

    if owner == SOURCE_CUSTOM or custom_progression_is_active(session):
        if pick.startswith("composition::"):
            violations.append("custom_active_with_composition_pick")
        if card_source.lower().startswith("composition"):
            violations.append("custom_active_with_composition_card")

    side = str(sidebar_practice_key or snap.get("display_key") or "").strip()
    card_pk = str(card_practice_key or "").strip()
    if side and card_pk:
        side_tok = side.split()[0].replace("♯", "#").replace("♭", "b")
        card_tok = card_pk.split()[0].replace("♯", "#").replace("♭", "b")
        if side_tok and card_tok and side_tok != card_tok:
            violations.append("sidebar_key_ne_card_practice_key")

    if pick.startswith("composition::") and owner == SOURCE_CUSTOM:
        violations.append("owner_namespace_ne_pick_namespace")
    if pick.startswith("custom::") and owner == SOURCE_COMPOSITION:
        violations.append("owner_namespace_ne_pick_namespace")

    ctx_src = str(snap.get("backing_ctx_source") or "")
    if ctx_src == "composition_song" and card_source.lower().startswith("custom"):
        violations.append("backing_owner_ne_visible_card_source")
    if ctx_src == "custom_progression" and card_source.lower().startswith("composition"):
        violations.append("backing_owner_ne_visible_card_source")

    return violations
