"""Chart provenance: stale saved copies of a CATALOG chart never override the catalog.

Saved state keeps full chart copies (``selected_song``, ``catalog_session``,
``improv_song_concert_sections`` ...).  When the canonical catalog entry is later
corrected, an old verbatim copy must not win, but user-edited, custom,
composition and mission/creative charts must stay untouched.

Provenance recorded going forward on a catalog snapshot::

    chart_origin     = "catalog"
    catalog_revision = <fingerprint of the catalog sections this copy was made from>

Rules (``classify_snapshot``):

1. Snapshot has no sections, or equals the canonical chart       -> ``same`` (stamp).
2. Snapshot is not a catalog chart of THIS song (custom / composition / mission /
   creative / explicit edit marker / identity mismatch / non-catalog source)
                                                                 -> ``keep``.
3. Snapshot carries provenance: its sections still fingerprint to the recorded
   ``catalog_revision`` (unmodified since stamped) but the catalog moved on
                                                                 -> ``refresh``;
   sections no longer match the recorded revision (edited)       -> ``keep``.
4. Legacy snapshot (no provenance), catalog pick key of the same song, no marker
                                                                 -> ``refresh``.
   Ambiguous legacy snapshot (no pick key AND no title)          -> ``keep`` + log.

User edits live in ``user_chart_overrides.json`` and are already merged into the
canonical record, so canonical (the refresh target) includes them.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
from typing import Any

_log = logging.getLogger(__name__)

CHART_ORIGIN_KEY = "chart_origin"
CATALOG_REVISION_KEY = "catalog_revision"
ORIGIN_CATALOG = "catalog"
PROVENANCE_LOG_KEY = "_chart_provenance_log"

_PICK_SEP = "\x1f"
_CHART_FIELDS = ("sections", "chart_versions", "section_order")
_EDIT_MARKER_KEYS = ("user_edited", "user_override", "edited_level", "arrangement_customized")
_MISSION_MARKER_KEYS = (
    "mission_type",
    "mission_chord",
    "mission_span_take",
    "mission_practice_context",
    "optional_mission_example_only",
    "improv_active_mission",
)

# Only these containers hold catalog chart snapshots; other dicts that merely carry
# a pick key plus sections (analysis/mission contexts) are never touched.
_SNAPSHOT_CONTAINER_KEYS = frozenset(
    {
        "selected_song",
        "catalog_session",
        "_last_catalog_song_state",
        "_catalog_before_custom_state",
        "_catalog_before_creative_state",
    }
)

SAME = "same"
REFRESH = "refresh"
KEEP = "keep"


def chart_fingerprint(sections: Any) -> str:
    """Stable fingerprint of an ordered section map ('' when empty)."""
    if not isinstance(sections, dict) or not sections:
        return ""
    items = [
        [str(name), [str(c).strip() for c in (chords or [])]]
        for name, chords in sections.items()
        if isinstance(chords, (list, tuple))
    ]
    if not items:
        return ""
    return hashlib.sha1(json.dumps(items, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def _norm(text: Any) -> str:
    return " ".join(str(text or "").strip().lower().split())


def _is_catalog_pick(pick: str) -> bool:
    return bool(pick) and _PICK_SEP in pick and not pick.startswith(("custom::", "composition::"))


def classify_snapshot(
    snapshot: dict[str, Any],
    canonical: dict[str, Any],
    *,
    pick_key: str = "",
) -> tuple[str, str]:
    """Return (action, reason) for a stored copy against its canonical catalog row."""
    snap_secs = snapshot.get("sections")
    canon_secs = canonical.get("sections")
    if not isinstance(snap_secs, dict) or not snap_secs:
        return KEEP, "no_sections"
    if not isinstance(canon_secs, dict) or not canon_secs:
        return KEEP, "canonical_has_no_sections"
    snap_fp = chart_fingerprint(snap_secs)
    canon_fp = chart_fingerprint(canon_secs)
    if snap_fp == canon_fp:
        return SAME, "equal"

    origin = _norm(snapshot.get(CHART_ORIGIN_KEY))
    if origin and origin != ORIGIN_CATALOG:
        return KEEP, f"origin_{origin}"
    for mk in _EDIT_MARKER_KEYS:
        if snapshot.get(mk):
            return KEEP, f"edit_marker_{mk}"
    for mk in _MISSION_MARKER_KEYS:
        if snapshot.get(mk):
            return KEEP, f"mission_marker_{mk}"
    src = _norm(snapshot.get("source_type") or snapshot.get("source_kind") or snapshot.get("music_source"))
    if src and src != "catalog":
        return KEEP, f"source_{src}"

    snap_pick = str(snapshot.get("pick_key") or "").strip()
    if snap_pick.startswith(("custom::", "composition::")):
        return KEEP, "non_catalog_pick_key"
    if snap_pick and pick_key and snap_pick != pick_key:
        return KEEP, "pick_key_mismatch"
    c_title = _norm(canonical.get("title"))
    c_artist = _norm(canonical.get("artist"))
    s_title = _norm(snapshot.get("title"))
    s_artist = _norm(snapshot.get("artist"))
    if s_title and c_title and s_title != c_title:
        return KEEP, "title_mismatch"
    if s_artist and c_artist and s_artist != c_artist:
        return KEEP, "artist_mismatch"

    recorded = str(snapshot.get(CATALOG_REVISION_KEY) or "").strip()
    if origin == ORIGIN_CATALOG and recorded:
        if recorded == snap_fp:
            return REFRESH, "provenance_unmodified_old_revision"
        return KEEP, "provenance_sections_modified_since_stamp"

    # Legacy snapshot (no provenance).
    if _is_catalog_pick(snap_pick):
        return REFRESH, "legacy_catalog_pick_no_edit_marker"
    if _is_catalog_pick(pick_key) and (s_title or s_artist):
        return REFRESH, "legacy_identity_matches_active_catalog_pick"
    return KEEP, "legacy_ambiguous"


def _log_event(session: dict[str, Any] | None, event: dict[str, Any]) -> None:
    _log.info("chart_provenance %s", event)
    if isinstance(session, dict):
        try:
            rows = session.setdefault(PROVENANCE_LOG_KEY, [])
            if isinstance(rows, list):
                rows.append(event)
                del rows[:-20]
        except Exception:
            pass


def stamp_catalog_provenance(snapshot: dict[str, Any], canonical: dict[str, Any]) -> dict[str, Any]:
    out = dict(snapshot)
    out[CHART_ORIGIN_KEY] = ORIGIN_CATALOG
    out[CATALOG_REVISION_KEY] = chart_fingerprint(canonical.get("sections"))
    return out


def reconcile_snapshot(
    snapshot: Any,
    canonical: dict[str, Any] | None,
    *,
    where: str = "",
    pick_key: str = "",
    session: dict[str, Any] | None = None,
    stamp: bool = True,
) -> Any:
    """Return ``snapshot`` refreshed from ``canonical`` when it is a stale catalog copy."""
    if not isinstance(snapshot, dict) or not isinstance(canonical, dict) or not canonical:
        return snapshot
    action, reason = classify_snapshot(snapshot, canonical, pick_key=pick_key)
    if action == SAME:
        if not stamp or canonical.get("user_override"):
            return snapshot  # user-edited canonical is not a pristine catalog revision
        stamped = stamp_catalog_provenance(snapshot, canonical)
        return snapshot if stamped == snapshot else stamped
    if action == KEEP:
        if reason in ("legacy_ambiguous", "provenance_sections_modified_since_stamp"):
            _log_event(session, {"where": where, "action": KEEP, "reason": reason,
                                 "title": snapshot.get("title")})
        return snapshot
    out = dict(snapshot)
    old_fp = chart_fingerprint(snapshot.get("sections"))
    for field in _CHART_FIELDS:
        if canonical.get(field):
            out[field] = copy.deepcopy(canonical[field])
        elif field != "sections":
            out.pop(field, None)
    if canonical.get("user_override"):
        out.pop(CHART_ORIGIN_KEY, None)
        out.pop(CATALOG_REVISION_KEY, None)
    else:
        out = stamp_catalog_provenance(out, canonical)
    _log_event(session, {"where": where, "action": REFRESH, "reason": reason,
                         "title": snapshot.get("title"), "old": old_fp,
                         "new": chart_fingerprint(canonical.get("sections"))})
    return out


def heal_session_chart_copies(
    session: dict[str, Any],
    canonical: dict[str, Any],
    pick_key: str,
    *,
    where: str = "",
) -> bool:
    """Refresh stale copies of THIS pick's catalog chart held in the session."""
    changed = False
    replaced: dict[str, dict[str, Any]] = {}

    def _swap_in(cur: dict[str, Any], new: dict[str, Any]) -> None:
        old_fp = chart_fingerprint(cur.get("sections"))
        if old_fp and old_fp != chart_fingerprint(new.get("sections")):
            replaced[old_fp] = new["sections"]

    def _fix(container: dict[str, Any], key: str) -> None:
        nonlocal changed
        cur = container.get(key)
        if not isinstance(cur, dict) or not cur:
            return
        cur_pick = str(cur.get("pick_key") or "").strip()
        if cur_pick and cur_pick != pick_key:
            return
        new = reconcile_snapshot(
            cur, canonical, where=where, pick_key=pick_key, session=session, stamp=False
        )
        if new is not cur and new != cur:
            _swap_in(cur, new)
            container[key] = new
            changed = True

    _fix(session, "selected_song")
    _fix(session, "_last_catalog_song_state")
    cat = session.get("catalog_session")
    if isinstance(cat, dict):
        cat_local = dict(cat)
        _fix(cat_local, "selected_song")
        cat_changed = cat_local != cat
        if str(cat_local.get("pick_key") or "").strip() == pick_key:
            new_cat = reconcile_snapshot(
                cat_local, canonical, where=where, pick_key=pick_key, session=session, stamp=False
            )
            if new_cat is not cat_local and new_cat != cat_local:
                _swap_in(cat_local, new_cat)
                cat_local = new_cat
                cat_changed = True
        if cat_changed:
            session["catalog_session"] = cat_local
            changed = True
    for bare in ("improv_song_concert_sections", "home_sections"):
        cur = session.get(bare)
        fp = chart_fingerprint(cur)
        if fp and fp in replaced:
            session[bare] = copy.deepcopy(replaced[fp])
            changed = True
    return changed


def _canonical_for_pick(pick_key: str) -> dict[str, Any] | None:
    try:
        from song_catalog.catalog import load_song_catalog, record_for_pick_key

        records = load_song_catalog()[3]
        rec = record_for_pick_key(records, pick_key)
        return rec if isinstance(rec, dict) else None
    except Exception:
        return None


def reconcile_payload_chart_copies(payload: Any, *, where: str = "payload") -> int:
    """In-place: refresh/stamp every catalog chart copy inside a saved/cloud state blob.

    A dict is treated as a catalog snapshot when it has ``sections`` and a
    catalog pick key.  Bare section maps (``improv_song_concert_sections`` /
    ``home_sections``) follow a refresh of a snapshot with the identical old
    chart.  Returns the number of snapshot charts replaced.
    """
    if not isinstance(payload, (dict, list)):
        return 0
    cache: dict[str, dict[str, Any] | None] = {}
    replaced: dict[str, dict[str, Any]] = {}
    count = 0

    def canon(pick: str) -> dict[str, Any] | None:
        if pick not in cache:
            cache[pick] = _canonical_for_pick(pick)
        return cache[pick]

    def walk(node: Any, key: str = "") -> None:
        nonlocal count
        if isinstance(node, list):
            for item in node:
                walk(item, "")
            return
        if not isinstance(node, dict):
            return
        for k, val in list(node.items()):
            if isinstance(val, (dict, list)):
                walk(val, str(k))
        if key not in _SNAPSHOT_CONTAINER_KEYS:
            return
        pick = str(node.get("pick_key") or "").strip()
        if _is_catalog_pick(pick) and isinstance(node.get("sections"), dict) and node["sections"]:
            row = canon(pick)
            if row:
                new = reconcile_snapshot(node, row, where=where, pick_key=pick)
                if new is not node and new != node:
                    old_fp = chart_fingerprint(node.get("sections"))
                    if old_fp != chart_fingerprint(new.get("sections")):
                        replaced[old_fp] = new["sections"]
                        count += 1
                    node.clear()
                    node.update(new)

    walk(payload)

    def swap(node: Any) -> None:
        if isinstance(node, list):
            for item in node:
                swap(item)
        elif isinstance(node, dict):
            for bare in ("improv_song_concert_sections", "home_sections"):
                fp = chart_fingerprint(node.get(bare))
                if fp and fp in replaced:
                    node[bare] = copy.deepcopy(replaced[fp])
            for val in node.values():
                if isinstance(val, (dict, list)):
                    swap(val)

    if replaced:
        swap(payload)
    return count


__all__ = [
    "CATALOG_REVISION_KEY",
    "CHART_ORIGIN_KEY",
    "KEEP",
    "REFRESH",
    "SAME",
    "chart_fingerprint",
    "classify_snapshot",
    "heal_session_chart_copies",
    "reconcile_payload_chart_copies",
    "reconcile_snapshot",
    "stamp_catalog_provenance",
]
