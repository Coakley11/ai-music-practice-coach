"""The Original Key the current Backing owner's material was actually written in.

``BackingContext`` has no original-key field. ``key``, ``display_key`` and
``concert_key`` are all the *working* key for every Creative owner: a Mission
sets ``key = display_key = concert_key = practice``, and
``_live_backing_concert_keys`` answers ``(practice, practice, practice)``. Only
``regular_song`` happens to carry the song's own key in ``key`` -- and that is
the one source the Creative identity path never handles. So anything that read
``ctx.key`` for an Original Key printed the key the musician had chosen: Blue
Bossa (C minor) practised in A minor was announced as "Original Key: A minor".

What an owner *does* carry is a stable identity -- ``bound_pick_key``, else
``active_song_id``. That names the Catalog pick, the ``custom::`` progression or
the ``composition::`` document whose authoritative metadata holds the real
Original Key, so that is what this module resolves.

Three rules, from the Issue 74 brief:

* **No fuzzy identity.** The catalog pick is looked up as an exact
  ``catalog[genre][label]`` membership, never through ``resolve_pick_key`` /
  ``resolve_picker_catalog_selection``. Those repair near-misses, and a Blue
  Bossa pick spelled with an en dash instead of the catalog's own dash came
  back as *Say* in B flat. The label itself carries title *and* artist, so
  exact membership is the identity check; the owner's title is verified on top.
* **Unknown stays unknown.** When an identified Catalog / Custom / Composition
  owner cannot be resolved, this returns ``resolved=False`` and an empty key.
  Callers must present that as unknown. Substituting the Practice Key, or an
  invented "C", is the defect itself.
* **A generated jam is its own home.** Material generated in E flat has no
  earlier key, so for ``entry_jam`` the working key genuinely *is* the original
  and is returned as resolved.

Read-only with respect to musical state: it resolves catalog and composition
libraries into the session cache (what every other reader does) and writes no
key, pick or ownership anywhere.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

#: Owners whose material is generated in its working key, so that key is its home.
GENERATED_SOURCES = frozenset({"entry_jam"})

#: Owner titles that name a workflow rather than a song, so they cannot verify a
#: catalog row (``build_mission_context`` falls back to "Mission", SBI to
#: "Active song").
_PLACEHOLDER_TITLES = frozenset(
    {"", "mission", "active song", "song", "custom", "composition", "jam"}
)


@dataclass(frozen=True)
class OwnerOriginalKey:
    """One owner's Original Key, or a stated inability to establish it.

    ``key`` is empty unless ``resolved``. ``reason`` is for diagnostics and
    tests; no caller should render it.
    """

    key: str = ""
    source_kind: str = ""
    identity: str = ""
    title: str = ""
    resolved: bool = False
    reason: str = ""


def _unresolved(reason: str, *, kind: str = "", identity: str = "") -> OwnerOriginalKey:
    return OwnerOriginalKey(source_kind=kind, identity=identity, reason=reason)


def owner_identity(ctx: Any) -> str:
    """The stable pick identity this Backing owner is bound to ("" when none)."""
    return str(
        getattr(ctx, "bound_pick_key", "") or getattr(ctx, "active_song_id", "") or ""
    ).strip()


def _norm_title(raw: Any) -> str:
    return " ".join(str(raw or "").strip().casefold().split())


def _titles_agree(row: dict[str, Any], label: str, expected: str) -> bool:
    """Does the catalog row describe the song this owner says it is?

    The owner's title is the only song name a ``BackingContext`` carries, and a
    workflow placeholder ("Mission") cannot confirm anything -- for those the
    exact pick membership stands alone.
    """
    want = _norm_title(expected)
    if want in _PLACEHOLDER_TITLES:
        return True
    row_title = _norm_title(row.get("title"))
    if row_title and want == row_title:
        return True
    # The label is "<title> <dash> <artist>": accept the owner's title inside it.
    label_norm = _norm_title(label)
    return bool(row_title) and bool(label_norm) and want in label_norm


def _picker_catalog(session: Any) -> dict[str, Any]:
    try:
        from songs.music_source import (
            _catalog_picker_from_session,
            ensure_song_picker_catalog,
        )
    except ImportError:
        return {}
    try:
        cached = _catalog_picker_from_session(session)
        if isinstance(cached, dict) and cached:
            return cached
        resolved = ensure_song_picker_catalog(session)
        return resolved if isinstance(resolved, dict) else {}
    except Exception:
        return {}


def _catalog_original(session: Any, pick: str, expected_title: str) -> OwnerOriginalKey:
    try:
        from song_catalog.catalog import format_pick_key, parse_pick_key
    except ImportError:
        return _unresolved("catalog_module_unavailable", kind="catalog", identity=pick)
    candidate = pick
    if "::" in candidate:
        # Legacy "Genre::Label" picks are rewritten into canonical form by a
        # plain string split -- a format, not a lookup. Exact membership below
        # still decides whether the song is real.
        head, _sep, tail = candidate.partition("::")
        if head.strip() and tail.strip():
            candidate = format_pick_key(head.strip(), tail.strip())
    try:
        genre, label = parse_pick_key(candidate)
    except Exception:
        genre, label = "", ""
    genre = str(genre or "").strip()
    label = str(label or "").strip()
    if not genre or not label:
        # A legacy "Genre::Label" or bare title is not a canonical identity, and
        # repairing it is exactly the fuzzy step this must not take.
        return _unresolved("pick_not_canonical", kind="catalog", identity=pick)
    catalog = _picker_catalog(session)
    labels = catalog.get(genre) if isinstance(catalog, dict) else None
    row = labels.get(label) if isinstance(labels, dict) else None
    if not isinstance(row, dict):
        return _unresolved("pick_not_in_catalog", kind="catalog", identity=pick)
    key = str(row.get("key") or "").strip()
    if not key:
        return _unresolved("catalog_row_has_no_key", kind="catalog", identity=pick)
    if not _titles_agree(row, label, expected_title):
        return _unresolved("title_mismatch", kind="catalog", identity=pick)
    return OwnerOriginalKey(
        key=key,
        source_kind="catalog",
        identity=pick,
        title=str(row.get("title") or "").strip(),
        resolved=True,
        reason="catalog_row",
    )


def _custom_original(session: Any, pick: str) -> OwnerOriginalKey:
    try:
        from songs.music_source import (
            custom_original_key,
            custom_progression_for_pick_key,
        )
    except ImportError:
        return _unresolved("custom_module_unavailable", kind="custom", identity=pick)
    try:
        blob = custom_progression_for_pick_key(session, pick)
    except Exception:
        blob = None
    if not isinstance(blob, dict) or not blob:
        return _unresolved("custom_progression_not_found", kind="custom", identity=pick)
    try:
        key = str(custom_original_key(blob) or "").strip()
    except Exception:
        key = ""
    if not key:
        return _unresolved("custom_has_no_original_key", kind="custom", identity=pick)
    return OwnerOriginalKey(
        key=key,
        source_kind="custom",
        identity=pick,
        title=str(blob.get("name") or "").strip(),
        resolved=True,
        reason="custom_saved_original",
    )


def _composition_original(session: Any, pick: str) -> OwnerOriginalKey:
    try:
        from composition_songs_bridge import (
            composition_source_original_key,
            find_composition_document,
        )
    except ImportError:
        return _unresolved(
            "composition_module_unavailable", kind="composition", identity=pick
        )
    try:
        doc = find_composition_document(session, pick)
    except Exception:
        doc = None
    if not isinstance(doc, dict) or not doc:
        return _unresolved("composition_not_found", kind="composition", identity=pick)
    try:
        key = str(composition_source_original_key(doc) or "").strip()
    except Exception:
        key = ""
    if not key:
        return _unresolved(
            "composition_has_no_original_key", kind="composition", identity=pick
        )
    return OwnerOriginalKey(
        key=key,
        source_kind="composition",
        identity=pick,
        title=str(doc.get("title") or "").strip(),
        resolved=True,
        reason="composition_home_key",
    )


def resolve_original_key_for_pick(
    session: Any,
    pick: str,
    *,
    expected_title: str = "",
) -> OwnerOriginalKey:
    """The Original Key behind one stable pick identity, or an unresolved answer.

    The pick-only entry point, for callers that hold an identity rather than a
    ``BackingContext`` (the Mission -> Backing handoff seals from here).
    """
    pick = str(pick or "").strip()
    if not pick:
        return _unresolved("no_owner_identity")
    if pick.startswith(("custom::", "custom\x1f")):
        return _custom_original(session, pick)
    if pick.startswith(("composition::", "composition\x1f")):
        return _composition_original(session, pick)
    if pick.startswith("creative::"):
        # A jam workflow pick: no song owns it, so no song's Original Key.
        return _unresolved("creative_workflow_pick", identity=pick)
    return _catalog_original(session, pick, str(expected_title or "").strip())


def resolve_owner_original_key(session: Any, ctx: Any) -> OwnerOriginalKey:
    """The Original Key of the song this Backing owner is playing.

    Never the Practice Key: an owner whose authoritative key cannot be
    established comes back ``resolved=False`` so the surface can say so.
    """
    if ctx is None:
        return _unresolved("no_context")
    source = str(getattr(ctx, "source", "") or "").strip()
    working = str(
        getattr(ctx, "key", "") or getattr(ctx, "concert_key", "") or ""
    ).strip()
    if source in GENERATED_SOURCES:
        # Generated material: the key it was generated in is its home key.
        if not working:
            return _unresolved("generated_without_key", kind="generated")
        return OwnerOriginalKey(
            key=working,
            source_kind="generated",
            identity=owner_identity(ctx),
            title=str(getattr(ctx, "song_title", "") or "").strip(),
            resolved=True,
            reason="generated_working_key",
        )

    return resolve_original_key_for_pick(
        session,
        owner_identity(ctx),
        expected_title=str(getattr(ctx, "song_title", "") or "").strip(),
    )


__all__ = [
    "GENERATED_SOURCES",
    "OwnerOriginalKey",
    "owner_identity",
    "resolve_original_key_for_pick",
    "resolve_owner_original_key",
]
