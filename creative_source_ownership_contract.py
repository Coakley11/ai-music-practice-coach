"""Creative / Backing source ownership contract (Pass 8+ human acceptance).

Separate owners — never mix title / chords / Practice Key across these:

1. GLOBAL_ACTIVE_SOURCE — catalog or custom after explicit activate
2. LAST_CUSTOM_SOURCE — last custom progression worked with (Custom page / SBI Custom)
3. SBI_SELECTED_SOURCE_TYPE — Active Source vs Custom Progression tab (survives refresh)
4. GENERATED_JAM_STATE / ENTRY_STYLE_JAM_STATE — independent Creative workspaces
5. CURRENT_BACKING_HANDOFF + temporary Backing play overrides

A refresh is not a source activation. Creative navigation is not activation.
Only explicit Set-as-Active / catalog pick commit activates Global Active Source.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Session keys (contract names)
GLOBAL_ACTIVE_SOURCE_KIND_KEY = "active_music_source"
LAST_CUSTOM_STATE_KEY = "_last_custom_song_state"
SBI_SELECTED_SOURCE_TYPE_KEY = "sbi_preview_source"
BACKING_HANDOFF_SOURCE_KEY = "_backing_explicit_handoff_source"


@dataclass(frozen=True)
class CreativeSourceSnapshot:
    """One coherent Creative source — title, key, chords must agree."""

    source_kind: str  # catalog | custom | mission | song_improv | entry_jam
    source_id: str
    title: str
    practice_key: str
    original_key: str = ""
    sections: dict[str, list[str]] = field(default_factory=dict)
    chords: tuple[str, ...] = ()
    owner: str = ""  # which contract bucket produced this


def resolve_global_active_snapshot(session: dict[str, Any]) -> CreativeSourceSnapshot | None:
    """Global Active Source — Songs / Practice / Missions / Motif / SBI Active."""
    try:
        from songs.music_source import (
            SOURCE_CUSTOM,
            custom_progression_is_active,
            is_custom_progression,
        )
    except ImportError:
        return None

    if custom_progression_is_active(session) or is_custom_progression(session):
        return _snapshot_from_custom(session, owner="global_active_custom")
    return _snapshot_from_catalog(session, owner="global_active_catalog")


def resolve_last_custom_snapshot(session: dict[str, Any]) -> CreativeSourceSnapshot | None:
    """Last Custom Source — Custom page and SBI → Custom Progression.

    LAST_CUSTOM identity memory outranks a blank/default live CPL ("My Progression").
    Live CPL wins only when it is a genuinely named Custom with material.
    """
    raw = session.get(LAST_CUSTOM_STATE_KEY)
    remembered = _snapshot_from_last_custom_raw(raw, owner="last_custom_snapshot")
    live = _snapshot_from_custom(session, owner="last_custom_live")
    if live is not None and _custom_snapshot_is_substantive(live):
        if remembered is None or live.source_id == remembered.source_id or live.title == remembered.title:
            return live
        if live.chords:
            return live
    if remembered is not None:
        return remembered
    if live is not None and live.source_id:
        return live
    return None


def _custom_snapshot_is_substantive(snap: CreativeSourceSnapshot) -> bool:
    title = str(snap.title or "").strip()
    if not title or title in {"My Progression", "My progression"}:
        return bool(snap.chords)
    return True


def _snapshot_from_last_custom_raw(
    raw: Any, *, owner: str
) -> CreativeSourceSnapshot | None:
    if not isinstance(raw, dict):
        return None
    active = raw.get("active") if isinstance(raw.get("active"), dict) else None
    if active is not None:
        try:
            from custom_progression_lab import written_home_key
            from songs.music_source import custom_pick_key_for
        except ImportError:
            written_home_key = None  # type: ignore[assignment]
            custom_pick_key_for = None  # type: ignore[assignment]
        try:
            pick = custom_pick_key_for(active) if custom_pick_key_for else ""
        except Exception:
            pick = str(raw.get("pick_key") or "").strip()
        pick = str(pick or "").strip() or "custom::unknown"
        try:
            home = (
                str(
                    (written_home_key(active) if written_home_key else None)
                    or active.get("original_key_center")
                    or "C"
                ).strip()
                or "C"
            )
        except Exception:
            home = str(active.get("original_key_center") or raw.get("custom_home_key") or "C").strip() or "C"
        title = str(active.get("name") or raw.get("name") or "My Progression").strip() or "My Progression"
        sections: dict[str, list[str]] = {}
        raw_secs = active.get("original_sections") or active.get("sections")
        if isinstance(raw_secs, dict):
            for name, chs in raw_secs.items():
                if not isinstance(chs, list):
                    continue
                cleaned: list[str] = []
                for c in chs:
                    if isinstance(c, dict):
                        sym = str(c.get("chord") or c.get("symbol") or "").strip()
                    else:
                        sym = str(c or "").strip()
                    if sym:
                        cleaned.append(sym)
                if cleaned:
                    sections[str(name)] = cleaned
        practice = str(raw.get("display_key") or home).strip() or home
        return CreativeSourceSnapshot(
            source_kind="custom",
            source_id=pick,
            title=title,
            practice_key=practice,
            original_key=home,
            sections=sections,
            chords=_flatten_chords(sections),
            owner=owner,
        )
    pick = str(raw.get("pick_key") or "").strip()
    title = str(
        (raw.get("selected_song") or {}).get("title")
        or raw.get("custom_progression_name")
        or raw.get("name")
        or ""
    ).strip()
    key = str(raw.get("display_key") or raw.get("custom_home_key") or "C").strip() or "C"
    if not pick and not title:
        return None
    return CreativeSourceSnapshot(
        source_kind="custom",
        source_id=pick or "custom::unknown",
        title=title or "My Progression",
        practice_key=key,
        original_key=str(raw.get("custom_home_key") or key).strip() or key,
        owner=owner,
    )



def resolve_sbi_snapshot(session: dict[str, Any]) -> CreativeSourceSnapshot | None:
    """SBI view: Active Source mirrors Global; Custom mirrors Last Custom."""
    try:
        from source_session_state import get_sbi_preview_source

        preview = get_sbi_preview_source(session)
    except ImportError:
        preview = str(session.get(SBI_SELECTED_SOURCE_TYPE_KEY) or "Active song").strip()
    if preview == "Custom progression":
        return resolve_last_custom_snapshot(session)
    return resolve_global_active_snapshot(session)


def resolve_creative_tool_snapshot(session: dict[str, Any]) -> CreativeSourceSnapshot | None:
    """Missions / Motif / Harmony — always Global Active Source."""
    return resolve_global_active_snapshot(session)


def snapshots_coherent(a: CreativeSourceSnapshot | None, b: CreativeSourceSnapshot | None) -> bool:
    if a is None or b is None:
        return a is b
    return (
        a.source_kind == b.source_kind
        and a.source_id == b.source_id
        and a.title == b.title
        and a.practice_key == b.practice_key
    )


def assert_creative_surfaces_coherent(session: dict[str, Any]) -> dict[str, Any]:
    """Diagnostics for harness: title / key / source must not diverge."""
    global_snap = resolve_global_active_snapshot(session)
    sbi = resolve_sbi_snapshot(session)
    return {
        "global": global_snap,
        "sbi": sbi,
        "coherent_with_sbi_active": (
            True
            if str(session.get(SBI_SELECTED_SOURCE_TYPE_KEY) or "") == "Custom progression"
            else snapshots_coherent(global_snap, sbi)
        ),
    }


def stamp_explicit_backing_handoff(session: dict[str, Any], source: str) -> None:
    """Explicit Creative → Backing handoff must outrank ordinary restore."""
    session[BACKING_HANDOFF_SOURCE_KEY] = str(source or "").strip()
    session["_backing_explicit_handoff_epoch"] = int(session.get("_backing_explicit_handoff_epoch") or 0) + 1


def consume_explicit_backing_handoff(session: dict[str, Any]) -> str:
    return str(session.get(BACKING_HANDOFF_SOURCE_KEY) or "").strip()


def clear_explicit_backing_handoff(session: dict[str, Any]) -> None:
    session.pop(BACKING_HANDOFF_SOURCE_KEY, None)


def _snapshot_from_catalog(session: dict[str, Any], *, owner: str) -> CreativeSourceSnapshot | None:
    pick = str(session.get("active_catalog_pick_key") or "").strip()
    sel = session.get("selected_song") if isinstance(session.get("selected_song"), dict) else {}
    if not pick and sel:
        pick = str(sel.get("pick_key") or "").strip()
    if not pick or pick.startswith("custom::"):
        return None
    title = str(sel.get("title") or session.get("song") or session.get("active_song_title") or "").strip()
    original = str(sel.get("key") or "").strip() or "C"
    practice = original
    try:
        from songs.practice_key_state import get_practice_concert_key

        practice = str(get_practice_concert_key(session, pick) or session.get("display_key") or original).strip() or original
    except ImportError:
        practice = str(session.get("display_key") or original).strip() or original
    sections = _sections_from_session(session)
    chords = _flatten_chords(sections)
    return CreativeSourceSnapshot(
        source_kind="catalog",
        source_id=pick,
        title=title or "Catalog song",
        practice_key=practice,
        original_key=original,
        sections=sections,
        chords=chords,
        owner=owner,
    )


def _snapshot_from_custom(session: dict[str, Any], *, owner: str) -> CreativeSourceSnapshot | None:
    try:
        from custom_progression_lab import (
            CPL_ACTIVE_KEY,
            default_active_progression,
            ensure_original_structure,
            written_home_key,
        )
        from songs.music_source import custom_pick_key_for
    except ImportError:
        return None
    active = ensure_original_structure(session.get(CPL_ACTIVE_KEY) or default_active_progression())
    pick = custom_pick_key_for(active)
    home = str(written_home_key(active) or active.get("original_key_center") or "C").strip() or "C"
    practice = home
    try:
        from songs.practice_key_state import get_practice_concert_key

        practice = str(get_practice_concert_key(session, pick, default=home) or home).strip() or home
    except ImportError:
        practice = str(session.get("display_key") or home).strip() or home
    title = str(active.get("name") or "My Progression").strip() or "My Progression"
    sections: dict[str, list[str]] = {}
    raw_secs = active.get("sections")
    if isinstance(raw_secs, dict):
        for name, chs in raw_secs.items():
            if isinstance(chs, list):
                sections[str(name)] = [str(c) for c in chs if str(c).strip()]
    return CreativeSourceSnapshot(
        source_kind="custom",
        source_id=pick,
        title=title,
        practice_key=practice,
        original_key=home,
        sections=sections,
        chords=_flatten_chords(sections),
        owner=owner,
    )


def _sections_from_session(session: dict[str, Any]) -> dict[str, list[str]]:
    for key in ("improv_song_concert_sections", "home_sections"):
        raw = session.get(key)
        if isinstance(raw, dict) and raw:
            return {
                str(n): [str(c) for c in chs if str(c).strip()]
                for n, chs in raw.items()
                if isinstance(chs, list)
            }
    return {}


def _flatten_chords(sections: dict[str, list[str]]) -> tuple[str, ...]:
    out: list[str] = []
    for chs in sections.values():
        out.extend(chs)
    return tuple(out)
