"""Issue 64 slices 2 and 3: finding a saved Multitrack project, and saying what it is.

Three questions this answers, all of them about *saved* rows rather than the live
session, so every function here is pure and takes the row.

**What key is this project in?** Not "what does the sidebar say" - what the layers were
actually recorded in. Three honest answers: one key that every layer agrees on, several
keys when the musician moved between takes, or unknown for a row saved before the
identity contract existed. A project is never labelled with a key just because the
sidebar is showing that key now, and an unknown key is shown as unknown rather than
guessed from the project's Practice Key.

**Which projects belong to the song I am looking at?** By the stable source identity the
row already stores - ``activity_source_context.source_type`` + ``source_id`` - never by
title. A Catalog "Autumn Leaves" and a Composition of the same name are different songs
and must not find each other's recordings.

**Which of them do I show first?** Same song and same recorded key, then the same song
in another key, then rows whose identity is incomplete - which stay findable rather than
being hidden for being old.

Project identity is the ``multitrack_id``. Song and key are for searching and grouping;
several projects may share both and remain entirely separate.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

__all__ = [
    "KEY_STATUS_LEGACY",
    "KEY_STATUS_MIXED",
    "KEY_STATUS_SINGLE",
    "MATCH_LEGACY",
    "MATCH_OTHER_KEY",
    "MATCH_OTHER_SONG",
    "MATCH_SONG_AND_KEY",
    "describe_project",
    "find_projects_for_song",
    "group_projects_by_song_and_key",
    "layer_key_lines",
    "project_key_label",
    "project_key_status",
    "project_source",
]

KEY_STATUS_SINGLE = "single"
KEY_STATUS_MIXED = "mixed"
KEY_STATUS_LEGACY = "unknown"

MATCH_SONG_AND_KEY = "song_and_key"
MATCH_OTHER_KEY = "same_song_other_key"
MATCH_LEGACY = "incomplete_identity"
MATCH_OTHER_SONG = "other_song"

_RANK = {
    MATCH_SONG_AND_KEY: 0,
    MATCH_OTHER_KEY: 1,
    MATCH_LEGACY: 2,
    MATCH_OTHER_SONG: 3,
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _tracks(row: Mapping[str, Any]) -> list[dict]:
    raw = row.get("tracks")
    return [t for t in raw if isinstance(t, dict) and not t.get("deleted")] if isinstance(raw, list) else []


def _identity(row: Mapping[str, Any]) -> dict:
    raw = row.get("recording_identity")
    return dict(raw) if isinstance(raw, Mapping) else {}


def project_key_status(row: Mapping[str, Any]) -> tuple[str, list[str]]:
    """``(status, keys)`` for one saved project, from what its layers actually say.

    The per-layer stamps are the evidence. The project's ``practice_concert_key`` is
    deliberately *not* consulted: that is where the project is now, not where its takes
    were played, and treating them as the same is how a flute take in B flat ends up
    filed under A flat.
    """
    layer_keys = [
        _text(t.get("recording_concert_key")) for t in _tracks(row)
    ]
    stamped = [k for k in layer_keys if k]
    if not stamped:
        identity = _identity(row)
        from_identity = [
            _text(k) for k in (identity.get("recording_keys") or []) if _text(k)
        ]
        if not from_identity:
            single = _text(identity.get("recording_concert_key"))
            from_identity = [single] if single else []
        stamped = from_identity
    distinct = sorted({k for k in stamped if k})
    if not distinct:
        return KEY_STATUS_LEGACY, []
    if len(distinct) > 1:
        return KEY_STATUS_MIXED, distinct
    # One key stamped - but if some layers carry no stamp at all, say so rather than
    # claiming the whole project is in that key.
    if layer_keys and any(not k for k in layer_keys):
        return KEY_STATUS_MIXED, distinct
    return KEY_STATUS_SINGLE, distinct


def project_key_label(row: Mapping[str, Any]) -> str:
    """What to show a musician about this project's key. Never a guess."""
    status, keys = project_key_status(row)
    if status == KEY_STATUS_SINGLE:
        return keys[0]
    if status == KEY_STATUS_MIXED:
        known = ", ".join(keys)
        return f"Mixed keys ({known})" if known else "Mixed keys"
    return "Recording key unknown"


def layer_key_lines(row: Mapping[str, Any]) -> list[str]:
    """One line per recorded layer: its instrument and the key it was played in."""
    out: list[str] = []
    for track in _tracks(row):
        name = _text(track.get("instrument")) or _text(track.get("name")) or _text(track.get("slot")) or "Layer"
        key = _text(track.get("recording_concert_key"))
        out.append(f"{name} - {key}" if key else f"{name} - recording key unknown")
    return out


def project_source(row: Mapping[str, Any]) -> tuple[str, str]:
    """``(source_type, source_id)`` for the song this project belongs to, or ``("","")``."""
    ctx = row.get("activity_source_context")
    if isinstance(ctx, Mapping):
        source_type, source_id = _text(ctx.get("source_type")), _text(ctx.get("source_id"))
        if source_type and source_id:
            return source_type, source_id
    for track in _tracks(row):
        source_type = _text(track.get("recording_source_type"))
        source_id = _text(track.get("recording_source_id"))
        if source_type and source_id:
            return source_type, source_id
    identity = _identity(row)
    return _text(identity.get("source_type")), _text(identity.get("source_id"))


def _match_kind(row: Mapping[str, Any], owner: Mapping[str, str], concert_key: str) -> str:
    want_type, want_id = _text(owner.get("source_type")), _text(owner.get("source_id"))
    source_type, source_id = project_source(row)
    if not source_type or not source_id:
        # Saved before identity was recorded. Still findable - just not claimed as a
        # match for a specific song, because nothing in the row says it is one.
        return MATCH_LEGACY
    if not (want_type and want_id) or (source_type, source_id) != (want_type, want_id):
        return MATCH_OTHER_SONG
    status, keys = project_key_status(row)
    wanted = _text(concert_key)
    if status == KEY_STATUS_SINGLE and wanted and keys[0] == wanted:
        return MATCH_SONG_AND_KEY
    return MATCH_OTHER_KEY


def describe_project(row: Mapping[str, Any]) -> dict[str, Any]:
    """Everything the library needs to show about one saved project."""
    tracks = _tracks(row)
    status, keys = project_key_status(row)
    source_type, source_id = project_source(row)
    instruments: list[str] = []
    for track in tracks:
        name = _text(track.get("instrument"))
        if name and name not in instruments:
            instruments.append(name)
    has_backing = bool(
        _text(row.get("backing_storage_ref")) or _text(row.get("backing_local_path"))
    )
    return {
        "multitrack_id": _text(row.get("multitrack_id")),
        "title": _text(row.get("title")) or "Untitled project",
        "song": _text(row.get("song")),
        "source_type": source_type,
        "source_id": source_id,
        "key_status": status,
        "keys": keys,
        "key_label": project_key_label(row),
        "layer_count": len(tracks),
        "instruments": instruments,
        "layer_keys": layer_key_lines(row),
        "updated_at": _text(row.get("updated_at")),
        "has_backing": has_backing,
        "legacy_identity": not (source_type and source_id),
    }


def find_projects_for_song(
    rows: Iterable[Mapping[str, Any]],
    owner: Mapping[str, str] | None,
    concert_key: str = "",
    *,
    include_other_songs: bool = False,
) -> list[dict[str, Any]]:
    """Saved projects for this song, best match first.

    Ranked: this song in this recorded key, then this song in another key, then rows
    whose identity is incomplete. Projects for other songs are excluded unless asked
    for, because showing them under a song they do not belong to is how a musician
    opens the wrong recording.
    """
    owner = dict(owner or {})
    found: list[dict[str, Any]] = []
    for row in rows or []:
        if not isinstance(row, Mapping) or row.get("deleted"):
            continue
        kind = _match_kind(row, owner, concert_key)
        if kind == MATCH_OTHER_SONG and not include_other_songs:
            continue
        entry = describe_project(row)
        entry["match"] = kind
        found.append(entry)
    # Best band first, and newest first inside each band - which one sort cannot do,
    # because the two orders run in opposite directions.
    banded: list[dict[str, Any]] = []
    for band in sorted({e["match"] for e in found}, key=lambda m: _RANK.get(m, 9)):
        same = [e for e in found if e["match"] == band]
        same.sort(key=lambda e: e.get("updated_at") or "", reverse=True)
        banded.extend(same)
    return banded


def group_projects_by_song_and_key(
    rows: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Every saved project, grouped for an All Projects view.

    Grouped by song and recorded key; the group is a heading, never an identity. Two
    projects in the same group stay separate rows with their own ``multitrack_id``.
    """
    groups: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows or []:
        if not isinstance(row, Mapping) or row.get("deleted"):
            continue
        entry = describe_project(row)
        heading = entry["song"] or "Unknown song"
        bucket = (entry["source_type"], entry["source_id"] or heading, entry["key_label"])
        group = groups.setdefault(
            bucket,
            {"song": heading, "source_type": entry["source_type"],
             "source_id": entry["source_id"], "key_label": entry["key_label"],
             "projects": []},
        )
        group["projects"].append(entry)
    out = list(groups.values())
    for group in out:
        group["projects"].sort(key=lambda e: e.get("updated_at") or "", reverse=True)
        group["project_count"] = len(group["projects"])
    out.sort(key=lambda g: (g["song"].lower(), g["key_label"]))
    return out


# ---------------------------------------------------------------- the Project Library

def active_song_owner(session_state: Any) -> dict[str, str]:
    """``{source_type, source_id}`` for the song on screen, or ``{}`` when unsure.

    Fails closed, like the activity contract it borrows from: a song that cannot be
    named is not a song to file recordings against.
    """
    try:
        from song_coach_context import global_song_identity, source_owner

        owner = _text(source_owner(session_state))
        identity = _text(global_song_identity(session_state, owner))
    except Exception:
        return {}
    source, separator, pick = identity.partition("|")
    if not separator or not pick or source != owner:
        return {}
    return {"source_type": source, "source_id": pick}


def active_concert_key(session_state: Any) -> str:
    for key in ("display_key", "practice_concert_key", "concert_key"):
        try:
            value = _text(session_state.get(key))
        except Exception:
            value = ""
        if value:
            return value
    return ""


def rank_library_rows(rows: Sequence[Mapping[str, Any]], session_state: Any):
    """``(rows, note)`` with the current song's projects first.

    Library rows wrap the saved project in ``payload``; the ranking reads that and the
    original row objects are handed back untouched, so the list renderer and its load
    and delete actions keep working exactly as before.
    """
    listed = [r for r in (rows or []) if isinstance(r, Mapping)]
    owner = active_song_owner(session_state)
    key = active_concert_key(session_state)
    if not owner:
        return list(listed), ""
    by_id = {}
    for row in listed:
        payload = row.get("payload")
        if isinstance(payload, Mapping):
            by_id.setdefault(_text(payload.get("multitrack_id")), row)
    ordered = find_projects_for_song(
        [r.get("payload") for r in listed if isinstance(r.get("payload"), Mapping)],
        owner, key, include_other_songs=True,
    )
    out = [by_id[e["multitrack_id"]] for e in ordered if e["multitrack_id"] in by_id]
    seen = {id(r) for r in out}
    out.extend(r for r in listed if id(r) not in seen)
    matches = sum(1 for e in ordered if e["match"] == MATCH_SONG_AND_KEY)
    if matches:
        note = f"{matches} saved project(s) recorded in {key} for this song, shown first."
    else:
        note = "No saved project was recorded in this key for this song - listed by closest match."
    return out, note


def render_all_projects_view(st: Any, rows: Sequence[Mapping[str, Any]]) -> None:
    """Every saved project, grouped by song and recorded key, inside one expander."""
    payloads = [r.get("payload") for r in (rows or [])
                if isinstance(r, Mapping) and isinstance(r.get("payload"), Mapping)]
    if not payloads:
        return
    groups = group_projects_by_song_and_key(payloads)
    if not groups:
        return
    with st.expander(f"All projects ({sum(g['project_count'] for g in groups)})",
                     expanded=False):
        for group in groups:
            st.markdown(f"**{group['song']} - {group['key_label']}**")
            for entry in group["projects"]:
                instruments = ", ".join(entry["instruments"]) or "no recorded layers"
                backing = "backing saved" if entry["has_backing"] else "no backing saved"
                saved = (entry["updated_at"] or "")[:10]
                st.caption(
                    f"{entry['title']} - {entry['layer_count']} layer(s) - "
                    f"{instruments} - {backing}"
                    + (f" - saved {saved}" if saved else "")
                )
