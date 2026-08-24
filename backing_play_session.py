"""Ephemeral Backing play-session overrides — not durable song/generated/Mission state.

Lifecycle contract
==================

SOURCE / DEFAULT
    ↓ initialize ONCE for a new play session
CURRENT PLAY SESSION  ↔  USER WIDGETS
    ↓
CARD / BANNER / PLAYBACK

Rules:
- Same Backing session / Streamlit rerun: overrides remain.
- Browser refresh while still on that Backing play session: overrides remain
  (rehydrated from workspace ``_backing_play_session`` — short-lived, not catalog metadata).
- Leave Backing for another page: overrides expire; source identity may restore later.
- Return to Backing later: new play session seeded from source defaults.

``source_identity`` is stable (backing_page_sync_id) and must NOT include editable
BPM / style / meter / sections. Changing an override never changes source identity.
"""

from __future__ import annotations

import copy
import uuid
from typing import Any

BACKING_PLAY_SESSION_KEY = "_backing_play_session"
BACKING_PLAY_SESSION_EXPIRED_KEY = "_backing_play_session_expired"

_OVERRIDE_FIELDS = (
    "bpm",
    "groove",
    "meter",
    "meter_override",
    "scope",
    "single_section",
    "multi_sections",
    "loops",
)


def _ctx_launch_id(session: dict[str, Any]) -> str:
    try:
        from backing_context import BACKING_CONTEXT_KEY, BACKING_SESSION_LAUNCH_ID_BLOB_KEY

        raw = session.get(BACKING_CONTEXT_KEY)
        if isinstance(raw, dict):
            return str(raw.get(BACKING_SESSION_LAUNCH_ID_BLOB_KEY) or "").strip()
    except ImportError:
        pass
    return ""


def _mint_launch_id(session: dict[str, Any]) -> str:
    launch_id = uuid.uuid4().hex
    try:
        from backing_context import BACKING_CONTEXT_KEY, BACKING_SESSION_LAUNCH_ID_BLOB_KEY

        raw = session.get(BACKING_CONTEXT_KEY)
        if isinstance(raw, dict):
            raw = dict(raw)
            raw[BACKING_SESSION_LAUNCH_ID_BLOB_KEY] = launch_id
            session[BACKING_CONTEXT_KEY] = raw
    except ImportError:
        pass
    return launch_id


def resolve_backing_source_identity(session: dict[str, Any]) -> str:
    """Stable source identity for the active Backing play session (no editable knobs)."""
    try:
        from backing_context import backing_page_sync_id

        song_sid = str(
            session.get("_backing_page_bpm_sync_id")
            or session.get("_active_bpm_sync_id")
            or session.get("_backing_trace_sync_id")
            or ""
        ).strip()
        return str(backing_page_sync_id(session, song_sync_id=song_sid) or song_sid or "").strip()
    except ImportError:
        return ""


def _generated_source_bpm(session: dict[str, Any], ctx: Any | None = None) -> int:
    """Sealed generated Jam / Style Jam source BPM (never catalog / stale bag)."""
    if ctx is not None:
        try:
            ctx_bpm = int(getattr(ctx, "bpm", 0) or 0)
        except (TypeError, ValueError):
            ctx_bpm = 0
        if ctx_bpm > 0:
            return ctx_bpm
    entry_mode = ""
    if ctx is not None:
        entry_mode = str(getattr(ctx, "entry_mode", "") or "").strip()
    if not entry_mode:
        entry_mode = str(session.get("improv_entry_mode") or "").strip()
    candidates: list[Any] = []
    if entry_mode == "Jam Session Generator":
        candidates.extend(
            [
                session.get("improv_jam_bpm"),
                (session.get("improv_style_meta") or {}).get("bpm")
                if isinstance(session.get("improv_style_meta"), dict)
                else None,
            ]
        )
    else:
        candidates.extend(
            [
                session.get("improv_style_bpm"),
                (session.get("improv_style_meta") or {}).get("bpm")
                if isinstance(session.get("improv_style_meta"), dict)
                else None,
            ]
        )
    try:
        from music_workflow_state_store import get_active_workflow_pointer, get_workflow_blob

        ptr = get_active_workflow_pointer(session)
        owner = str(getattr(ptr, "workflow_owner", "") or "") if ptr else ""
        if owner in {"style_jam", "jam_session_generator"}:
            blob = get_workflow_blob(session, owner, str(getattr(ptr, "workflow_session_id", "") or ""))
            if blob is not None:
                candidates.insert(0, getattr(blob, "tempo_bpm", None))
    except Exception:
        pass
    for raw in candidates:
        try:
            val = int(raw or 0)
        except (TypeError, ValueError):
            val = 0
        if val > 0:
            return val
    return 0


def _source_defaults_from_session(session: dict[str, Any]) -> dict[str, Any]:
    bpm = 0
    groove = ""
    meter = "4/4"
    ctx_source = ""
    try:
        from backing_context import get_backing_context

        ctx = get_backing_context(session)
        if ctx is not None:
            ctx_source = str(getattr(ctx, "source", "") or "").strip()
    except ImportError:
        ctx = None
    # Catalog pick BPM must not seed generated Jam / Mission / SBI source defaults —
    # that made Jam Current 111 fight a Shape-of-You catalog 96 on refresh.
    if ctx_source not in {"entry_jam", "mission", "song_improv"}:
        try:
            from songs.music_source import catalog_transport_bpm_for_pick

            pick = str(session.get("active_catalog_pick_key") or "").strip()
            cat = catalog_transport_bpm_for_pick(session, pick) if pick else 0
            if int(cat or 0) > 0:
                bpm = int(cat)
        except Exception:
            pass
        for key in ("_backing_catalog_default_bpm", "_backing_source_default_bpm"):
            try:
                val = int(session.get(key) or 0)
            except (TypeError, ValueError):
                val = 0
            if val > 0:
                bpm = val
                break
    catalog_bpm = int(bpm or 0)
    try:
        from backing_context import get_backing_context

        ctx = get_backing_context(session)
        if ctx is not None:
            ctx_bpm = int(getattr(ctx, "bpm", 0) or 0)
            # Catalog/source default already known: ctx.bpm is display/current, not init.
            if catalog_bpm <= 0 and ctx_bpm > 0:
                bpm = ctx_bpm
            if ctx_source == "entry_jam":
                # FIRST 98→96 writer was preferring expired catalog bag.defaults (96)
                # over sealed generated ctx.bpm (98) while minting a NEW Jam session.
                jam_bpm = _generated_source_bpm(session, ctx)
                if jam_bpm > 0:
                    bpm = jam_bpm
                elif ctx_bpm > 0:
                    bpm = ctx_bpm
            elif ctx_source in {"mission", "song_improv"}:
                bag = get_backing_play_session(session)
                bag_identity = str((bag or {}).get("source_identity") or "").strip()
                live_identity = resolve_backing_source_identity(session)
                bag_def = 0
                try:
                    bag_def = int(((bag or {}).get("defaults") or {}).get("bpm") or 0)
                except (TypeError, ValueError):
                    bag_def = 0
                # Reuse bag defaults only for the SAME source identity; never a
                # leftover catalog bag when minting Mission/SBI after Shape of You.
                if (
                    bag_def > 0
                    and bag_identity
                    and live_identity
                    and bag_identity == live_identity
                    and not bool((bag or {}).get("expired"))
                ):
                    bpm = bag_def
                elif ctx_bpm > 0:
                    bpm = ctx_bpm
            groove = str(getattr(ctx, "style", "") or getattr(ctx, "groove", "") or "").strip()
            meter = str(getattr(ctx, "meter", "") or meter).strip() or meter
    except ImportError:
        pass
    if int(bpm or 0) <= 0:
        bpm = 100
    if not groove:
        groove = str(session.get("backing_groove_style") or "").strip()
    try:
        from songs.playback_defaults import normalize_groove_label

        if groove:
            groove = normalize_groove_label(groove)
    except ImportError:
        pass
    return {
        "bpm": int(bpm or 100),
        "groove": groove,
        "meter": meter or "4/4",
        "meter_override": False,
        "scope": "Full song",
        "single_section": "",
        "multi_sections": [],
        "loops": 2,
    }


def get_backing_play_session(session: dict[str, Any]) -> dict[str, Any] | None:
    raw = session.get(BACKING_PLAY_SESSION_KEY)
    return raw if isinstance(raw, dict) else None


def _source_init_bpm(session: dict[str, Any], ps: dict[str, Any] | None = None) -> int:
    """Read-only catalog/source default BPM (never a Current override)."""
    bag = ps if isinstance(ps, dict) else get_backing_play_session(session)
    ctx = None
    ctx_source = ""
    try:
        from backing_context import get_backing_context

        ctx = get_backing_context(session)
        if ctx is not None:
            ctx_source = str(getattr(ctx, "source", "") or "").strip()
    except Exception:
        pass
    # Generated Jam: sealed source BPM outranks catalog session keys (96).
    if ctx_source == "entry_jam":
        jam_bpm = _generated_source_bpm(session, ctx)
        if jam_bpm > 0:
            return jam_bpm
        try:
            val = int(((bag or {}).get("defaults") or {}).get("bpm") or 0)
        except (TypeError, ValueError):
            val = 0
        if val > 0:
            return val
        return 0
    if ctx_source in {"mission", "song_improv"}:
        try:
            val = int(((bag or {}).get("defaults") or {}).get("bpm") or 0)
        except (TypeError, ValueError):
            val = 0
        if val > 0:
            return val
        try:
            ctx_bpm = int(getattr(ctx, "bpm", 0) or 0) if ctx is not None else 0
        except (TypeError, ValueError):
            ctx_bpm = 0
        if ctx_bpm > 0:
            return ctx_bpm
        return 0
    for key in ("_backing_catalog_default_bpm", "_backing_source_default_bpm"):
        try:
            val = int(session.get(key) or 0)
        except (TypeError, ValueError):
            val = 0
        if val > 0:
            return val
    try:
        val = int(((bag or {}).get("defaults") or {}).get("bpm") or 0)
    except (TypeError, ValueError):
        val = 0
    if val > 0:
        return val
    try:
        ctx_bpm = int(getattr(ctx, "bpm", 0) or 0) if ctx is not None else 0
        if ctx_bpm > 0:
            return ctx_bpm
    except Exception:
        pass
    return 0


def _known_source_default_bpms(session: dict[str, Any], ps: dict[str, Any] | None = None) -> set[int]:
    """Catalog/source default tempos that must not reseal Current BPM."""
    out: set[int] = set()
    bag = ps if isinstance(ps, dict) else get_backing_play_session(session)
    ctx = None
    ctx_source = ""
    try:
        from backing_context import get_backing_context

        ctx = get_backing_context(session)
        if ctx is not None:
            ctx_source = str(getattr(ctx, "source", "") or "").strip()
    except Exception:
        pass
    candidates: list[Any] = [((bag or {}).get("defaults") or {}).get("bpm")]
    if ctx_source == "entry_jam":
        candidates.append(_generated_source_bpm(session, ctx))
        if ctx is not None:
            candidates.append(getattr(ctx, "bpm", None))
    elif ctx_source in {"mission", "song_improv"}:
        if ctx is not None:
            candidates.append(getattr(ctx, "bpm", None))
    else:
        candidates.extend(
            [
                session.get("_backing_catalog_default_bpm"),
                session.get("_backing_source_default_bpm"),
            ]
        )
        if ctx is not None:
            candidates.append(getattr(ctx, "bpm", None))
    for raw in candidates:
        try:
            val = int(raw or 0)
        except (TypeError, ValueError):
            val = 0
        if val > 0:
            out.add(val)
    init = _source_init_bpm(session, bag)
    if init > 0:
        out.add(init)
    return out


def _stale_widget_default_bpms(session: dict[str, Any], ps: dict[str, Any] | None = None) -> set[int]:
    """BPM values that leftover widgets may show but must not outrank Current.

    Includes this source's defaults PLUS foreign catalog pick BPM so a Shape-of-You
    96 slider cannot masquerade as a Jam user edit after source switch.
    """
    out = set(_known_source_default_bpms(session, ps))
    for key in ("_backing_catalog_default_bpm", "_backing_source_default_bpm"):
        try:
            val = int(session.get(key) or 0)
        except (TypeError, ValueError):
            val = 0
        if val > 0:
            out.add(val)
    try:
        from songs.music_source import catalog_transport_bpm_for_pick

        pick = str(session.get("active_catalog_pick_key") or "").strip()
        cat = catalog_transport_bpm_for_pick(session, pick) if pick else 0
        if int(cat or 0) > 0:
            out.add(int(cat))
    except Exception:
        pass
    return out


def _lock_bpm(session: dict[str, Any]) -> int:
    try:
        return int(session.get("_backing_current_bpm_lock") or 0)
    except (TypeError, ValueError):
        return 0


def _seed_source_bpm_slider_keys(session: dict[str, Any], bpm: int) -> None:
    """On a NEW play session, leftover widget keys must not become Current.

    Wipe leftover ``backing_track_bpm::*`` keys to source. Keep a live domain
    BPM that already differs from source so a pending capture can record it.
    """
    if int(bpm or 0) <= 0:
        return
    leftover = False
    source = int(bpm)
    try:
        domain = int(session.get("backing_track_bpm") or 0)
    except (TypeError, ValueError):
        domain = 0
    for key in list(session.keys()):
        if str(key).startswith("backing_track_bpm::"):
            try:
                val = int(session.get(key) or 0)
            except (TypeError, ValueError):
                val = 0
            if val > 0 and val != source:
                leftover = True
            session[key] = source
    source_defaults = _stale_widget_default_bpms(session)
    if leftover:
        keep = source
    elif domain > 0 and domain != source and domain not in source_defaults:
        keep = domain
    else:
        keep = source
    session["backing_track_bpm"] = keep
    session["bpm"] = keep
    try:
        from songs.bpm_state import BPM_WIDGET_KEY

        session[BPM_WIDGET_KEY] = keep
    except ImportError:
        pass
    try:
        from backing_context import backing_page_sync_id
        from songs.playback_defaults import backing_bpm_slider_widget_key

        sid = str(
            session.get("_backing_page_bpm_sync_id")
            or session.get("_backing_trace_sync_id")
            or session.get("_active_bpm_sync_id")
            or backing_page_sync_id(session, song_sync_id="")
            or ""
        ).strip()
        if sid:
            session[backing_bpm_slider_widget_key(sid)] = keep
    except ImportError:
        pass


def effective_backing_play_overrides(session: dict[str, Any]) -> dict[str, Any]:
    """Resolved playback knobs: source defaults overlaid with current play-session overrides."""
    ps = get_backing_play_session(session)
    defaults = dict((ps or {}).get("defaults") or _source_defaults_from_session(session))
    overrides = dict((ps or {}).get("overrides") or {}) if ps and not ps.get("expired") else {}
    out = dict(defaults)
    for key in _OVERRIDE_FIELDS:
        if key in overrides and overrides[key] not in (None, ""):
            out[key] = copy.deepcopy(overrides[key])
    return out


def _live_slider_bpm(session: dict[str, Any], *, sync_id: str = "") -> int:
    """Streamlit Quick BPM widget value for this Backing sync (same-rerun authority)."""
    domain = 0
    try:
        domain = int(session.get("backing_track_bpm") or 0)
    except (TypeError, ValueError):
        domain = 0
    try:
        from songs.playback_defaults import backing_bpm_slider_widget_key
    except ImportError:
        backing_bpm_slider_widget_key = None  # type: ignore[assignment]
    preferred: list[str] = []
    sid = str(
        sync_id
        or session.get("_backing_page_bpm_sync_id")
        or session.get("_backing_trace_sync_id")
        or session.get("_active_bpm_sync_id")
        or ""
    ).strip()
    if sid and backing_bpm_slider_widget_key is not None:
        preferred.append(backing_bpm_slider_widget_key(sid))
    try:
        from backing_context import backing_page_sync_id

        page_sid = str(backing_page_sync_id(session, song_sync_id=sid) or "").strip()
        if page_sid and backing_bpm_slider_widget_key is not None:
            key = backing_bpm_slider_widget_key(page_sid)
            if key not in preferred:
                preferred.append(key)
    except Exception:
        pass
    by_key: dict[str, int] = {}
    for key, raw in list(session.items()):
        if not str(key).startswith("backing_track_bpm::"):
            continue
        try:
            val = int(raw or 0)
        except (TypeError, ValueError):
            val = 0
        if val > 0:
            by_key[str(key)] = val
    # The page's real Quick BPM widget key always wins when present — unless it
    # is still sitting on source/default while domain Current already moved.
    source_defaults = _stale_widget_default_bpms(session)
    for key in preferred:
        val = int(by_key.get(key) or 0)
        if val <= 0:
            continue
        if domain and source_defaults and val in source_defaults and domain not in source_defaults:
            continue
        return val
    # When a sync_id is known, never inherit a foreign leftover slider key
    # (e.g. catalog 96 / prior jam 98 on a different sync id).
    if preferred:
        if domain > 0:
            return domain
        return 0
    for key, val in by_key.items():
        if key in preferred:
            continue
        if domain and source_defaults and val in source_defaults and domain not in source_defaults:
            continue
        if val > 0:
            return val
    if domain > 0:
        return domain
    return 0


def current_backing_play_bpm(session: dict[str, Any], *, default: int = 0, sync_id: str = "") -> int:
    """Authoritative Current BPM for card/banner/playback.

    Existing play session precedence:
    1. persisted play-session override
    2. current lock when it is a real user Current (not source default)
    3. live preferred widget when it is a non-default edit
    4. source/default only when there is no Current override
    """
    source_defaults = _stale_widget_default_bpms(session)
    source = _source_init_bpm(session)
    override_bpm = _play_session_current_bpm(session)
    slider_val = _live_slider_bpm(session, sync_id=sync_id)
    lock = _lock_bpm(session)

    if override_bpm > 0:
        # Leftover source-default slider (98) must never outrank a real Current
        # override (111). Only a non-default live edit may win.
        if (
            slider_val > 0
            and int(slider_val) != int(override_bpm)
            and slider_val not in source_defaults
        ):
            return slider_val
        return override_bpm
    if lock > 0 and lock not in source_defaults:
        return lock
    if slider_val > 0 and slider_val not in source_defaults:
        return slider_val
    if source > 0:
        return source
    if slider_val > 0:
        return slider_val
    return int(default or 0)


def promote_live_slider_bpm_to_current(session: dict[str, Any], *, sync_id: str = "") -> int:
    """Pre-widget: project Current BPM. Source default never reseals an existing Current.

    The first live 110→96 writer was this function capturing catalog 96 into
    ``overrides.bpm`` because the play-session bag had no override. Source 96 is
    initialization metadata only; it must not be written as Current on a rerun.
    """
    session["_backing_bpm_trace_phase"] = "promote"
    source_defaults = _stale_widget_default_bpms(session)
    source = _source_init_bpm(session)
    override = _play_session_current_bpm(session)
    lock = _lock_bpm(session)
    existing = _play_session_is_existing(session)
    slider = _live_slider_bpm(session, sync_id=sync_id)
    old_domain = session.get("backing_track_bpm")
    old_override = override

    # Bag loss: restore user Current from lock. Never restore source default.
    if override <= 0 and lock > 0 and lock not in source_defaults:
        capture_backing_play_session_overrides(session, bpm=lock)
        override = lock

    if override > 0:
        if slider > 0 and slider not in source_defaults:
            bpm = slider
            if bpm != override:
                capture_backing_play_session_overrides(session, bpm=bpm)
        else:
            bpm = override
    elif slider > 0 and slider not in source_defaults:
        # Same-run widget edit (Streamlit already wrote the triggering key).
        bpm = slider
        capture_backing_play_session_overrides(session, bpm=bpm)
    else:
        # NEW session / no user Current: initialize from source default.
        # Do not capture 96 as an override (96 is not a user edit).
        bpm = source or slider
        if bpm > 0:
            _seed_source_bpm_slider_keys(session, int(bpm))

    if bpm <= 0:
        return 0
    trace_bpm_write(
        session,
        fn="promote_live_slider_bpm_to_current",
        field="backing_track_bpm",
        old=old_domain,
        new=bpm,
        source=(
            f"override={old_override} lock={lock} slider={slider} "
            f"source={source} existing={existing}"
        ),
    )
    session["backing_track_bpm"] = int(bpm)
    session["bpm"] = int(bpm)
    session["_backing_current_bpm_lock"] = int(bpm)
    try:
        from songs.bpm_state import BPM_WIDGET_KEY

        session[BPM_WIDGET_KEY] = int(bpm)
    except ImportError:
        pass
    apply_backing_play_session_to_widgets(session)
    return int(bpm)


def _play_session_current_bpm(session: dict[str, Any]) -> int:
    """Authoritative Current BPM for an unexpired play session (override only)."""
    ps = get_backing_play_session(session)
    if ps is None or ps.get("expired"):
        return 0
    try:
        return int(((ps.get("overrides") or {}).get("bpm")) or 0)
    except (TypeError, ValueError):
        return 0


def _play_session_is_existing(session: dict[str, Any]) -> bool:
    ps = get_backing_play_session(session)
    return bool(ps) and not bool(ps.get("expired")) and bool(ps.get("play_session_id"))


def trace_bpm_write(
    session: dict[str, Any],
    *,
    fn: str,
    field: str,
    old: Any,
    new: Any,
    source: str,
    extra: dict[str, Any] | None = None,
) -> None:
    """Log one Current-BPM mutation for Pass 8 (110→96 hunter)."""
    try:
        old_i = int(old or 0)
    except (TypeError, ValueError):
        old_i = 0
    try:
        new_i = int(new or 0)
    except (TypeError, ValueError):
        new_i = 0
    if old_i == new_i:
        return
    try:
        from pathlib import Path
        import json
        import time

        ps = get_backing_play_session(session) or {}
        payload = {
            "t": time.time(),
            "kind": "write",
            "fn": fn,
            "field": field,
            "old": old_i,
            "new": new_i,
            "source": source,
            "identity": str(ps.get("source_identity") or resolve_backing_source_identity(session) or ""),
            "play_session_id": str(ps.get("play_session_id") or ""),
            "session_kind": "EXISTING" if _play_session_is_existing(session) else "NEW",
            "override_bpm": int((ps.get("overrides") or {}).get("bpm") or 0) or None,
            "dirty": bool((ps.get("overrides") or {}).get("bpm")),
            "phase": str(session.get("_backing_bpm_trace_phase") or ""),
        }
        if extra:
            payload.update(extra)
        path = Path("scripts/evidence-creative-backing/bpm-live-writes.jsonl")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, default=str) + "\n")
    except Exception:
        pass


def trace_backing_bpm(session: dict[str, Any], *, phase: str, extra: dict[str, Any] | None = None) -> None:
    """Append one live BPM lifecycle snapshot for Pass 8 diagnosis."""
    try:
        from pathlib import Path
        import json
        import time

        keys = {
            str(k): session.get(k)
            for k in list(session.keys())
            if str(k).startswith("backing_track_bpm")
        }
        payload = {
            "t": time.time(),
            "phase": phase,
            "sync_id": str(session.get("_backing_page_bpm_sync_id") or session.get("_active_bpm_sync_id") or ""),
            "domain": session.get("backing_track_bpm"),
            "bpm": session.get("bpm"),
            "slider_keys": keys,
            "play_bpm": current_backing_play_bpm(session, default=0),
            "overrides": dict((get_backing_play_session(session) or {}).get("overrides") or {}),
            "lock": session.get("_backing_current_bpm_lock"),
            "defaults_bpm": ((get_backing_play_session(session) or {}).get("defaults") or {}).get("bpm"),
            "expired": bool((get_backing_play_session(session) or {}).get("expired")),
            "identity": str((get_backing_play_session(session) or {}).get("source_identity") or ""),
            "play_session_id": str((get_backing_play_session(session) or {}).get("play_session_id") or ""),
            "session_kind": "EXISTING" if _play_session_is_existing(session) else "NEW",
        }
        if extra:
            payload.update(extra)
        path = Path("scripts/evidence-creative-backing/bpm-live-trace.jsonl")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, default=str) + "\n")
    except Exception:
        pass


def capture_backing_play_session_overrides(
    session: dict[str, Any],
    *,
    bpm: int | None = None,
    skip_bpm: bool = False,
) -> dict[str, Any]:
    """Read live Backing widgets into the current play-session override bag."""
    session["_backing_bpm_trace_phase"] = str(session.get("_backing_bpm_trace_phase") or "capture")
    existing = get_backing_play_session(session)
    expired = bool((existing or {}).get("expired"))
    if existing is None or expired:
        ps = _new_play_session(session, mint_launch=False, seed_sliders=False)
        if not expired:
            # Bag missing (identity flicker) must not drop Current BPM.
            try:
                keep = int(session.get("_backing_current_bpm_lock") or 0)
            except (TypeError, ValueError):
                keep = 0
            source_defaults = _known_source_default_bpms(session, ps)
            if keep > 0 and keep not in source_defaults:
                ov = dict(ps.get("overrides") or {})
                ov["bpm"] = keep
                ps["overrides"] = ov
                ps["current_bpm_lock"] = keep
    else:
        ps = existing
    overrides = dict(ps.get("overrides") or {})
    if skip_bpm:
        resolved_bpm = 0
    else:
        # Prefer the Streamlit Quick BPM widget key over domain backing_track_bpm —
        # on_change may not have synced domain yet when early capture runs.
        resolved_bpm = int(bpm or 0)
        if resolved_bpm <= 0:
            resolved_bpm = _live_slider_bpm(session)
        if resolved_bpm <= 0:
            try:
                resolved_bpm = int(session.get("backing_track_bpm") or 0)
            except (TypeError, ValueError):
                resolved_bpm = 0
    if resolved_bpm > 0:
        try:
            prev_override = int((overrides or {}).get("bpm") or 0)
        except (TypeError, ValueError):
            prev_override = 0
        try:
            default_bpm = int(((ps or {}).get("defaults") or {}).get("bpm") or 0)
        except (TypeError, ValueError):
            default_bpm = 0
        source_defaults = _stale_widget_default_bpms(session, ps)
        if default_bpm > 0:
            source_defaults.add(default_bpm)
        existing_session = _play_session_is_existing(session) or bool(ps.get("play_session_id"))
        # Implicit capture must not reseal Current to catalog default.
        # Catalog 96 is initialization metadata, not a user override.
        if bpm is None and resolved_bpm in source_defaults:
            if existing_session and prev_override > 0 and prev_override != resolved_bpm:
                resolved_bpm = prev_override
            elif prev_override <= 0:
                resolved_bpm = 0
        if resolved_bpm > 0:
            trace_bpm_write(
                session,
                fn="capture_backing_play_session_overrides",
                field="overrides.bpm",
                old=prev_override,
                new=resolved_bpm,
                source="explicit" if bpm is not None else "implicit_slider_or_domain",
                extra={"skip_bpm": skip_bpm, "source_defaults": sorted(source_defaults)},
            )
            overrides["bpm"] = resolved_bpm
            session["_backing_current_bpm_lock"] = resolved_bpm
            ps["current_bpm_lock"] = resolved_bpm
            session["backing_track_bpm"] = resolved_bpm
            session["bpm"] = resolved_bpm

    defaults = dict(ps.get("defaults") or {})
    default_groove = str(defaults.get("groove") or "").strip()
    default_meter = str(defaults.get("meter") or "4/4").strip() or "4/4"
    default_scope = str(defaults.get("scope") or "Full song").strip() or "Full song"
    try:
        from songs.playback_defaults import normalize_groove_label

        if default_groove:
            default_groove = normalize_groove_label(default_groove)
    except ImportError:
        pass

    groove = str(session.get("backing_groove_style") or "").strip()
    try:
        from songs.playback_defaults import normalize_groove_label

        if groove:
            groove = normalize_groove_label(groove)
    except ImportError:
        pass
    prev_groove = str(overrides.get("groove") or "").strip()
    try:
        from songs.playback_defaults import normalize_groove_label

        if prev_groove:
            prev_groove = normalize_groove_label(prev_groove)
    except ImportError:
        pass
    if groove:
        # Source/default groove is initialization metadata — not a Current override.
        if groove == default_groove:
            if prev_groove and prev_groove != groove:
                overrides["groove"] = prev_groove
            else:
                overrides.pop("groove", None)
        else:
            overrides["groove"] = groove

    meter = str(session.get("backing_time_signature") or "").strip()
    prev_meter = str(overrides.get("meter") or "").strip()
    meter_override_flag = bool(session.get("backing_time_signature_override"))
    if meter:
        if meter == default_meter and not meter_override_flag:
            if prev_meter and prev_meter != meter:
                overrides["meter"] = prev_meter
                overrides["meter_override"] = True
            else:
                overrides.pop("meter", None)
                overrides.pop("meter_override", None)
        else:
            overrides["meter"] = meter
            overrides["meter_override"] = True if meter != default_meter else meter_override_flag

    scope = str(session.get("backing_track_scope") or "").strip()
    prev_scope = str(overrides.get("scope") or "").strip()
    multi = session.get("backing_track_multi_sections")
    multi_list = [str(s) for s in multi if str(s).strip()] if isinstance(multi, list) else []
    prev_multi = overrides.get("multi_sections")
    if scope:
        is_default_scope = scope == default_scope and scope == "Full song" and not multi_list
        if is_default_scope:
            if prev_scope and prev_scope != scope:
                overrides["scope"] = prev_scope
                if isinstance(prev_multi, list):
                    overrides["multi_sections"] = list(prev_multi)
            else:
                overrides.pop("scope", None)
                overrides.pop("multi_sections", None)
                overrides.pop("single_section", None)
        else:
            overrides["scope"] = scope
            if isinstance(multi, list):
                overrides["multi_sections"] = multi_list
    single = str(session.get("backing_track_single_section") or "").strip()
    if single and str(overrides.get("scope") or scope or "") != "Full song":
        overrides["single_section"] = single
    try:
        loops = int(session.get("backing_track_loops") or 0)
    except (TypeError, ValueError):
        loops = 0
    if loops > 0:
        # Loops default is usually 2 — only seal when it differs or already overridden.
        default_loops = int(defaults.get("loops") or 2)
        prev_loops = overrides.get("loops")
        if loops != default_loops:
            overrides["loops"] = loops
        elif prev_loops not in (None, "", 0) and int(prev_loops) != loops:
            overrides["loops"] = int(prev_loops)
        elif loops == default_loops:
            overrides.pop("loops", None)
    ps["overrides"] = overrides
    ps["expired"] = False
    identity = resolve_backing_source_identity(session)
    if identity:
        ps["source_identity"] = identity
    if not ps.get("play_session_id"):
        ps["play_session_id"] = uuid.uuid4().hex
    session[BACKING_PLAY_SESSION_KEY] = ps
    session[BACKING_PLAY_SESSION_EXPIRED_KEY] = False
    # Keep sealed backing_context transport aligned with CURRENT play session so
    # reboot disk blobs don't remint from CPL/catalog source defaults.
    try:
        from backing_context import get_backing_context, set_backing_context

        live_ctx = get_backing_context(session)
        if live_ctx is not None and str(getattr(live_ctx, "source", "") or "") not in {
            "",
            "regular_song",
        }:
            stamped = apply_current_play_session_to_backing_context(
                session, live_ctx, previous=live_ctx
            )
            if stamped is not None:
                set_backing_context(
                    session,
                    stamped,
                    trace_caller="capture_backing_play_session_overrides:stamp_ctx",
                )
    except ImportError:
        pass
    return ps


def apply_backing_play_session_to_widgets(session: dict[str, Any]) -> None:
    """Project current play-session defaults+overrides onto Backing widget keys."""
    resolved = effective_backing_play_overrides(session)
    if resolved.get("bpm"):
        bpm = int(resolved["bpm"])
        source_defaults = _stale_widget_default_bpms(session)
        live = _live_slider_bpm(session)
        override = _play_session_current_bpm(session)
        # Live non-default widget (110) must not be resealed to Current/default.
        # Streamlit-restored source default (96) must be projected back to Current.
        if live > 0 and live not in source_defaults:
            bpm = live
        elif override > 0:
            bpm = override
        session["backing_track_bpm"] = bpm
        session["bpm"] = bpm
        try:
            from backing_context import backing_page_sync_id
            from songs.playback_defaults import backing_bpm_slider_widget_key

            # Seed every candidate widget identity for this play session so a
            # sync-id flicker cannot leave the visible slider on source 98/96
            # while Current is 111.
            page_sid = ""
            try:
                page_sid = str(backing_page_sync_id(session, song_sync_id="") or "").strip()
            except Exception:
                page_sid = ""
            sids = [
                page_sid,
                str(session.get("_backing_page_bpm_sync_id") or "").strip(),
                str(session.get("_backing_trace_sync_id") or "").strip(),
                str(session.get("_active_bpm_sync_id") or "").strip(),
                str((get_backing_play_session(session) or {}).get("source_identity") or "").strip(),
            ]
            written = False
            old = None
            for sid in sids:
                if not sid:
                    continue
                key = backing_bpm_slider_widget_key(sid)
                if old is None:
                    old = session.get(key)
                session[key] = bpm
                written = True
            if override > 0:
                for key in list(session.keys()):
                    if not str(key).startswith("backing_track_bpm::"):
                        continue
                    try:
                        val = int(session.get(key) or 0)
                    except (TypeError, ValueError):
                        val = 0
                    if val <= 0 or val == bpm:
                        session[key] = bpm
                    elif val in source_defaults:
                        session[key] = bpm
            if page_sid:
                session["_backing_page_bpm_sync_id"] = page_sid
                session["_backing_trace_sync_id"] = page_sid
                session["_active_bpm_sync_id"] = page_sid
            if written:
                trace_bpm_write(
                    session,
                    fn="apply_backing_play_session_to_widgets",
                    field="slider_key",
                    old=old,
                    new=bpm,
                    source="play_session_override" if override > 0 else "source_default_projection",
                )
        except ImportError:
            pass
        session["_backing_current_bpm_lock"] = bpm
        try:
            ps = get_backing_play_session(session)
            if ps is not None:
                ps = dict(ps)
                ps["current_bpm_lock"] = bpm
                session[BACKING_PLAY_SESSION_KEY] = ps
        except Exception:
            pass
    if resolved.get("groove"):
        session["backing_groove_style"] = str(resolved["groove"])
    if resolved.get("meter"):
        session["backing_time_signature"] = str(resolved["meter"])
    session["backing_time_signature_override"] = bool(resolved.get("meter_override"))
    if resolved.get("scope"):
        session["backing_track_scope"] = str(resolved["scope"])
    if resolved.get("single_section"):
        session["backing_track_single_section"] = str(resolved["single_section"])
    multi = resolved.get("multi_sections")
    if isinstance(multi, list):
        session["backing_track_multi_sections"] = list(multi)
    if resolved.get("loops"):
        session["backing_track_loops"] = int(resolved["loops"])


def _apply_defaults_to_widgets(session: dict[str, Any], defaults: dict[str, Any]) -> None:
    session["backing_track_bpm"] = int(defaults.get("bpm") or 100)
    session["bpm"] = int(defaults.get("bpm") or 100)
    try:
        from backing_context import backing_page_sync_id
        from songs.playback_defaults import backing_bpm_slider_widget_key

        sid = backing_page_sync_id(session, song_sync_id="")
        if sid:
            session[backing_bpm_slider_widget_key(sid)] = int(defaults.get("bpm") or 100)
    except ImportError:
        pass
    if defaults.get("groove"):
        session["backing_groove_style"] = str(defaults["groove"])
    session["backing_time_signature"] = str(defaults.get("meter") or "4/4")
    session["backing_time_signature_override"] = bool(defaults.get("meter_override"))
    session["backing_track_scope"] = str(defaults.get("scope") or "Full song")
    session["backing_track_single_section"] = str(defaults.get("single_section") or "")
    session["backing_track_multi_sections"] = list(defaults.get("multi_sections") or [])
    session["backing_track_loops"] = int(defaults.get("loops") or 2)
    session.pop("_pending_backing_track_bpm", None)


def _new_play_session(
    session: dict[str, Any],
    *,
    mint_launch: bool,
    seed_sliders: bool = True,
) -> dict[str, Any]:
    launch_id = _mint_launch_id(session) if mint_launch else (_ctx_launch_id(session) or uuid.uuid4().hex)
    defaults = _source_defaults_from_session(session)
    identity = resolve_backing_source_identity(session)
    prev = get_backing_play_session(session) or {}
    ps = {
        "play_session_id": uuid.uuid4().hex,
        "launch_id": launch_id,
        "source_identity": identity,
        "expired": False,
        "defaults": defaults,
        "overrides": {},
    }
    session[BACKING_PLAY_SESSION_KEY] = ps
    session[BACKING_PLAY_SESSION_EXPIRED_KEY] = False
    if seed_sliders:
        session.pop("_backing_current_bpm_lock", None)
    source_bpm = int(defaults.get("bpm") or 0)
    if seed_sliders and source_bpm > 0:
        _seed_source_bpm_slider_keys(session, source_bpm)
    trace_bpm_write(
        session,
        fn="_new_play_session",
        field="play_session_id",
        old=0,
        new=1,
        source=f"prev={prev.get('play_session_id') or ''} identity={identity}",
        extra={
            "new_play_session_id": ps["play_session_id"],
            "defaults_bpm": source_bpm,
            "seed_sliders": seed_sliders,
        },
    )
    return ps


def expire_backing_play_session(session: dict[str, Any]) -> None:
    """Leave-Backing: drop temporary Advanced/BPM/scope knobs; keep last source identity."""
    ps = get_backing_play_session(session) or {}
    defaults = dict(ps.get("defaults") or _source_defaults_from_session(session))
    _apply_defaults_to_widgets(session, defaults)
    ps = {
        "play_session_id": str(ps.get("play_session_id") or ""),
        "launch_id": str(ps.get("launch_id") or _ctx_launch_id(session) or ""),
        "source_identity": str(ps.get("source_identity") or resolve_backing_source_identity(session) or ""),
        "expired": True,
        "defaults": defaults,
        "overrides": {},
    }
    session[BACKING_PLAY_SESSION_KEY] = ps
    session[BACKING_PLAY_SESSION_EXPIRED_KEY] = True
    session.pop("_backing_current_bpm_lock", None)
    try:
        from backing_track_state import (
            BACKING_DIRTY_KEY,
            BACKING_USER_EDIT_INTENT_KEY,
            BACKING_WIDGETS_SEEDED_KEY,
            gather_backing_filters,
            write_canonical_backing_state,
        )

        session.pop(BACKING_DIRTY_KEY, None)
        session.pop(BACKING_USER_EDIT_INTENT_KEY, None)
        session.pop(BACKING_WIDGETS_SEEDED_KEY, None)
        write_canonical_backing_state(
            session,
            gather_backing_filters(session),
            reason="play_session_expire",
            local_edit=False,
        )
    except ImportError:
        session.pop("backing_track_state_dirty", None)
        session.pop("_backing_user_edit_intent", None)


def expire_backing_play_session_on_page_exit(
    session: dict[str, Any],
    *,
    previous_page: str,
    new_page: str,
) -> bool:
    prev = str(previous_page or "").strip().lower()
    nxt = str(new_page or "").strip().lower()
    if prev == "backing" and nxt != "backing":
        expire_backing_play_session(session)
        return True
    return False


def sync_backing_play_session_on_backing_page(session: dict[str, Any]) -> dict[str, Any]:
    """Enter/refresh Backing: keep this play session, or seed a new one after page exit.

    Browser refresh must NOT be treated as leaving the play session. Matching
    ``source_identity`` (or launch_id) with a non-expired bag rehydrates Current knobs.
    """
    ps = get_backing_play_session(session)
    launch_id = _ctx_launch_id(session)
    identity = resolve_backing_source_identity(session)
    expired = bool(session.get(BACKING_PLAY_SESSION_EXPIRED_KEY)) or bool((ps or {}).get("expired"))
    lock = _lock_bpm(session)
    source_defaults = _known_source_default_bpms(session, ps)
    prev_identity = str((ps or {}).get("source_identity") or "").strip()
    prev_launch = str((ps or {}).get("launch_id") or "").strip()
    live_launch = str(launch_id or "").strip()
    # Source change while an unexpired bag still exists must mint a new session —
    # never retarget catalog defaults/overrides onto a generated Jam identity.
    # Do NOT remint on sync-id string flicker when launch_id still matches
    # (browser refresh); that resealed Jam Current 111 back to source 98.
    identity_changed = bool(prev_identity and identity and prev_identity != identity)
    launch_same = bool(
        prev_launch
        and (prev_launch == live_launch or (not live_launch and bool(prev_launch)))
    )
    if ps and not expired and identity_changed and not launch_same:
        expired = True
        session[BACKING_PLAY_SESSION_EXPIRED_KEY] = True
        ps = dict(ps)
        ps["expired"] = True
        session[BACKING_PLAY_SESSION_KEY] = ps
    if ps and not expired:
        # Still in this Backing play session (rerun or browser refresh). Never mint
        # a new bag from source defaults — that reseals Current BPM/style/meter.
        if identity:
            ps = dict(ps)
            ps["source_identity"] = identity
            session[BACKING_PLAY_SESSION_KEY] = ps
        ps = recover_play_session_overrides_from_backing_context(session, ps) or ps
        apply_backing_play_session_to_widgets(session)
        try:
            from backing_context import get_backing_context, set_backing_context

            live_ctx = get_backing_context(session)
            if live_ctx is not None and str(getattr(live_ctx, "source", "") or "") not in {
                "",
                "regular_song",
            }:
                stamped = apply_current_play_session_to_backing_context(
                    session, live_ctx, previous=live_ctx
                )
                if stamped is not None:
                    set_backing_context(
                        session,
                        stamped,
                        trace_caller="sync_backing_play_session_on_backing_page:stamp_ctx",
                    )
        except ImportError:
            pass
        return ps
    # Missing bag on an unexpired Backing stay: restore user Current from lock.
    if not expired and lock > 0 and lock not in source_defaults:
        ps = _new_play_session(session, mint_launch=not bool(launch_id), seed_sliders=False)
        if launch_id:
            ps["launch_id"] = launch_id
        if identity:
            ps["source_identity"] = identity
        session[BACKING_PLAY_SESSION_KEY] = ps
        capture_backing_play_session_overrides(session, bpm=lock)
        apply_backing_play_session_to_widgets(session)
        return get_backing_play_session(session) or ps
    try:
        live_domain = int(session.get("backing_track_bpm") or 0)
    except (TypeError, ValueError):
        live_domain = 0
    source_guess = int((_source_defaults_from_session(session) or {}).get("bpm") or 0)
    had_leftover_keys = False
    for key in list(session.keys()):
        if not str(key).startswith("backing_track_bpm::"):
            continue
        try:
            val = int(session.get(key) or 0)
        except (TypeError, ValueError):
            val = 0
        if val > 0 and source_guess > 0 and val != source_guess:
            had_leftover_keys = True
            break
    ps = _new_play_session(session, mint_launch=not bool(launch_id))
    if launch_id:
        ps["launch_id"] = launch_id
        session[BACKING_PLAY_SESSION_KEY] = ps
    if identity:
        ps["source_identity"] = identity
        session[BACKING_PLAY_SESSION_KEY] = ps
    # Reboot / restore may remint an empty bag while sealed specialized ctx still
    # holds the visit's BPM/style — recover before projecting source defaults.
    ps = recover_play_session_overrides_from_backing_context(session, ps) or ps
    defaults = dict(ps.get("defaults") or {})
    default_bpm = int(defaults.get("bpm") or 0)
    if any(
        (ps.get("overrides") or {}).get(k) not in (None, "", [], 0)
        for k in _OVERRIDE_FIELDS
    ):
        apply_backing_play_session_to_widgets(session)
        try:
            from backing_context import get_backing_context, set_backing_context

            live_ctx = get_backing_context(session)
            if live_ctx is not None and str(getattr(live_ctx, "source", "") or "") not in {
                "",
                "regular_song",
            }:
                stamped = apply_current_play_session_to_backing_context(
                    session, live_ctx, previous=live_ctx
                )
                if stamped is not None:
                    set_backing_context(
                        session,
                        stamped,
                        trace_caller="sync_backing_play_session_on_backing_page:recover_stamp",
                    )
        except ImportError:
            pass
        return get_backing_play_session(session) or ps
    _apply_defaults_to_widgets(session, defaults)
    ctx_source = ""
    try:
        from backing_context import get_backing_context

        _ctx = get_backing_context(session)
        if _ctx is not None:
            ctx_source = str(getattr(_ctx, "source", "") or "").strip()
    except Exception:
        pass
    stale = _stale_widget_default_bpms(session, ps)
    # New generated-source sessions must initialize from sealed source BPM.
    # Do not restore leftover catalog/prior-jam domain (96/111) over 98/127.
    if (
        ctx_source != "entry_jam"
        and live_domain > 0
        and default_bpm > 0
        and live_domain != default_bpm
        and not had_leftover_keys
        and live_domain not in stale
    ):
        session["backing_track_bpm"] = live_domain
        session["bpm"] = live_domain
    return ps


def backing_play_session_has_override(session: dict[str, Any], field: str) -> bool:
    ps = get_backing_play_session(session)
    if ps is None or ps.get("expired"):
        return False
    overrides = ps.get("overrides")
    if not isinstance(overrides, dict):
        return False
    val = overrides.get(field)
    if val in (None, "", []):
        return False
    return True


def _normalize_groove_token(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        from songs.playback_defaults import normalize_groove_label

        return str(normalize_groove_label(raw) or raw).strip()
    except ImportError:
        return raw


def _groove_tokens_equivalent(a: Any, b: Any) -> bool:
    left = _normalize_groove_token(a).lower()
    right = _normalize_groove_token(b).lower()
    if not left or not right:
        return False
    if left == right:
        return True
    return left.replace(" groove", "") == right.replace(" groove", "")


def _meaningful_play_session_overrides(
    overrides: dict[str, Any] | None,
    defaults: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Drop empty / source-default echo overrides so recover/apply can refill."""
    ov = dict(overrides or {})
    defaults = dict(defaults or {})
    out: dict[str, Any] = {}
    try:
        def_bpm = int(defaults.get("bpm") or 0)
    except (TypeError, ValueError):
        def_bpm = 0
    try:
        bpm = int(ov.get("bpm") or 0)
    except (TypeError, ValueError):
        bpm = 0
    if bpm > 0 and (def_bpm <= 0 or bpm != def_bpm):
        out["bpm"] = bpm
    groove = str(ov.get("groove") or "").strip()
    def_groove = str(defaults.get("groove") or "").strip()
    if groove and not _groove_tokens_equivalent(groove, def_groove):
        out["groove"] = groove
    meter = str(ov.get("meter") or "").strip()
    def_meter = str(defaults.get("meter") or "4/4").strip() or "4/4"
    if meter and meter != def_meter:
        out["meter"] = meter
    if ov.get("meter_override") not in (None, "", False, 0):
        out["meter_override"] = ov.get("meter_override")
    scope = str(ov.get("scope") or "").strip()
    def_scope = str(defaults.get("scope") or "Full song").strip() or "Full song"
    multi = ov.get("multi_sections")
    multi_list = [str(s).strip() for s in multi if str(s).strip()] if isinstance(multi, list) else []
    if scope and not (scope == def_scope and scope == "Full song" and not multi_list):
        out["scope"] = scope
        if multi_list:
            out["multi_sections"] = multi_list
    single = str(ov.get("single_section") or "").strip()
    if single and str(out.get("scope") or scope or "") != "Full song":
        out["single_section"] = single
    try:
        loops = int(ov.get("loops") or 0)
    except (TypeError, ValueError):
        loops = 0
    try:
        def_loops = int(defaults.get("loops") or 2)
    except (TypeError, ValueError):
        def_loops = 2
    if loops > 0 and loops != def_loops:
        out["loops"] = loops
    return out


def _stamp_previous_play_transport(ctx: Any, previous: Any) -> None:
    if ctx is None or previous is None:
        return
    try:
        prev_src = str(getattr(previous, "source", "") or "").strip()
        live_src = str(getattr(ctx, "source", "") or "").strip()
    except Exception:
        return
    if not prev_src or not live_src or prev_src != live_src:
        return
    if prev_src in {"", "regular_song"}:
        return
    try:
        prev_bpm = int(getattr(previous, "bpm", 0) or 0)
    except (TypeError, ValueError):
        prev_bpm = 0
    if prev_bpm > 0:
        ctx.bpm = prev_bpm
    prev_style = str(
        getattr(previous, "style", "") or getattr(previous, "groove", "") or ""
    ).strip()
    if prev_style:
        ctx.style = prev_style
        if hasattr(ctx, "groove"):
            ctx.groove = str(getattr(previous, "groove", "") or prev_style).strip() or prev_style
    prev_meter = str(getattr(previous, "meter", "") or "").strip()
    if prev_meter and hasattr(ctx, "meter"):
        ctx.meter = prev_meter
    prev_scope = str(getattr(previous, "scope", "") or "").strip()
    if prev_scope:
        ctx.scope = prev_scope
    try:
        prev_loops = int(getattr(previous, "loops", 0) or 0)
    except (TypeError, ValueError):
        prev_loops = 0
    if prev_loops > 0:
        ctx.loops = prev_loops
    sections = getattr(previous, "sections", None)
    if isinstance(sections, list) and sections and hasattr(ctx, "sections"):
        ctx.sections = [str(s).strip() for s in sections if str(s).strip()]
    single = str(getattr(previous, "section", "") or "").strip()
    if single and hasattr(ctx, "section"):
        ctx.section = single


def recover_play_session_overrides_from_backing_context(
    session: dict[str, Any],
    ps: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """If the play-session bag lost overrides but sealed specialized ctx still
    carries the visit's transport, rebuild overrides from that ctx.

    Covers reboot races where shutdown autosave wiped the bag after disk seed,
    or restore reminted an empty bag before sync ran. Never invents overrides
    after a true leave (expired bag).

    Source-default echoes (e.g. groove=Pop when CPL default is Pop) do not count
    as a real Current play session — recover still refills from sealed ctx.
    """
    bag = ps if isinstance(ps, dict) else get_backing_play_session(session)
    if bag is None or bag.get("expired"):
        return bag
    defaults = dict(bag.get("defaults") or _source_defaults_from_session(session))
    overrides = dict(bag.get("overrides") or {})
    meaningful = _meaningful_play_session_overrides(overrides, defaults)
    # Complete Current visit already sealed — keep it.
    if meaningful.get("bpm") and meaningful.get("groove"):
        if meaningful != overrides:
            bag = dict(bag)
            bag["overrides"] = meaningful
            session[BACKING_PLAY_SESSION_KEY] = bag
        return bag
    try:
        from backing_context import get_backing_context

        ctx = get_backing_context(session)
    except ImportError:
        return bag
    if ctx is None or str(getattr(ctx, "source", "") or "") in {"", "regular_song"}:
        return bag
    recovered: dict[str, Any] = {}
    try:
        ctx_bpm = int(getattr(ctx, "bpm", 0) or 0)
    except (TypeError, ValueError):
        ctx_bpm = 0
    try:
        def_bpm = int(defaults.get("bpm") or 0)
    except (TypeError, ValueError):
        def_bpm = 0
    if ctx_bpm > 0 and (def_bpm <= 0 or ctx_bpm != def_bpm):
        recovered["bpm"] = ctx_bpm
    ctx_style = str(getattr(ctx, "style", "") or getattr(ctx, "groove", "") or "").strip()
    def_groove = str(defaults.get("groove") or "").strip()
    # Keep the sealed ctx label as-is (e.g. "Blues") — do not force catalog
    # "Blues groove" normalization that would diverge from the visit's style chip.
    if ctx_style and not _groove_tokens_equivalent(ctx_style, def_groove):
        recovered["groove"] = ctx_style
    ctx_meter = str(getattr(ctx, "meter", "") or "").strip()
    def_meter = str(defaults.get("meter") or "4/4").strip() or "4/4"
    if ctx_meter and ctx_meter != def_meter:
        recovered["meter"] = ctx_meter
    ctx_scope = str(getattr(ctx, "scope", "") or "").strip()
    def_scope = str(defaults.get("scope") or "Full song").strip() or "Full song"
    if ctx_scope and ctx_scope != def_scope:
        recovered["scope"] = ctx_scope
    try:
        ctx_loops = int(getattr(ctx, "loops", 0) or 0)
    except (TypeError, ValueError):
        ctx_loops = 0
    try:
        def_loops = int(defaults.get("loops") or 2)
    except (TypeError, ValueError):
        def_loops = 2
    if ctx_loops > 0 and ctx_loops != def_loops:
        recovered["loops"] = ctx_loops
    sections = getattr(ctx, "sections", None)
    if isinstance(sections, list) and sections and ctx_scope and ctx_scope != "Full song":
        recovered["multi_sections"] = [str(s).strip() for s in sections if str(s).strip()]
    single = str(getattr(ctx, "section", "") or "").strip()
    if single and ctx_scope and ctx_scope != "Full song":
        recovered["single_section"] = single
    # Meaningful partial overrides win over recovered sealed fields.
    merged = dict(recovered)
    merged.update(meaningful)
    if not merged:
        return bag
    bag = dict(bag)
    bag["overrides"] = merged
    if merged.get("bpm"):
        bag["current_bpm_lock"] = int(merged["bpm"])
        session["_backing_current_bpm_lock"] = int(merged["bpm"])
    bag["expired"] = False
    session[BACKING_PLAY_SESSION_KEY] = bag
    session[BACKING_PLAY_SESSION_EXPIRED_KEY] = False
    return bag


def apply_current_play_session_to_backing_context(
    session: dict[str, Any],
    ctx: Any,
    *,
    previous: Any | None = None,
) -> Any:
    """Stamp CURRENT (unexpired) play-session transport onto a rebuilt BackingContext.

    Source rebuilds (CPL / catalog / generator defaults) must not wipe temporary
    BPM / style / meter / loop / scope for the same Backing visit. Refresh and
    server reboot are the same play session — only a true leave expires the bag,
    after which source defaults correctly win.
    """
    if ctx is None:
        return ctx
    ps = get_backing_play_session(session)
    if ps is not None and ps.get("expired"):
        return ctx

    defaults = dict((ps or {}).get("defaults") or _source_defaults_from_session(session))
    overrides: dict[str, Any] = {}
    if ps is not None and isinstance(ps.get("overrides"), dict):
        overrides = dict(ps.get("overrides") or {})
    meaningful = _meaningful_play_session_overrides(overrides, defaults)

    # Prefer previous sealed specialized transport when the bag is missing,
    # empty, or only echoes source defaults (common reboot remint race).
    if previous is not None and not meaningful:
        _stamp_previous_play_transport(ctx, previous)
        return ctx

    # Partial bag: fill gaps from previous sealed visit, then stamp overrides.
    if previous is not None and meaningful:
        try:
            prev_src = str(getattr(previous, "source", "") or "").strip()
            live_src = str(getattr(ctx, "source", "") or "").strip()
        except Exception:
            prev_src = live_src = ""
        if prev_src and live_src and prev_src == live_src and prev_src not in {"", "regular_song"}:
            if "bpm" not in meaningful:
                try:
                    prev_bpm = int(getattr(previous, "bpm", 0) or 0)
                except (TypeError, ValueError):
                    prev_bpm = 0
                if prev_bpm > 0:
                    ctx.bpm = prev_bpm
            if "groove" not in meaningful:
                prev_style = str(
                    getattr(previous, "style", "") or getattr(previous, "groove", "") or ""
                ).strip()
                if prev_style:
                    ctx.style = prev_style
                    if hasattr(ctx, "groove"):
                        ctx.groove = (
                            str(getattr(previous, "groove", "") or prev_style).strip() or prev_style
                        )
            if "meter" not in meaningful:
                prev_meter = str(getattr(previous, "meter", "") or "").strip()
                if prev_meter and hasattr(ctx, "meter"):
                    ctx.meter = prev_meter
            if "scope" not in meaningful:
                prev_scope = str(getattr(previous, "scope", "") or "").strip()
                if prev_scope:
                    ctx.scope = prev_scope
            if "loops" not in meaningful:
                try:
                    prev_loops = int(getattr(previous, "loops", 0) or 0)
                except (TypeError, ValueError):
                    prev_loops = 0
                if prev_loops > 0:
                    ctx.loops = prev_loops

    if not meaningful:
        return ctx

    if meaningful.get("bpm") not in (None, "", 0):
        try:
            ctx.bpm = int(meaningful["bpm"])
        except (TypeError, ValueError):
            pass
    groove = str(meaningful.get("groove") or "").strip()
    if groove:
        ctx.style = groove
        if hasattr(ctx, "groove"):
            existing_groove = str(getattr(ctx, "groove", "") or "").strip()
            if not existing_groove or existing_groove.lower() in {
                "pop groove",
                "pop",
                groove.lower(),
            }:
                ctx.groove = groove
    meter = str(meaningful.get("meter") or "").strip()
    if meter and hasattr(ctx, "meter"):
        ctx.meter = meter
    scope = str(meaningful.get("scope") or "").strip()
    if scope:
        ctx.scope = scope
    if meaningful.get("loops") not in (None, "", 0):
        try:
            ctx.loops = int(meaningful["loops"])
        except (TypeError, ValueError):
            pass
    multi = meaningful.get("multi_sections")
    if isinstance(multi, list) and multi:
        sections = [str(s).strip() for s in multi if str(s).strip()]
        if sections and hasattr(ctx, "sections"):
            ctx.sections = sections
    single = str(meaningful.get("single_section") or "").strip()
    if single and hasattr(ctx, "section"):
        ctx.section = single
    return ctx


def play_session_blocks_canonical_seed(session: dict[str, Any]) -> bool:
    """True when ephemeral play-session knobs must win over canonical backing_track_state."""
    ps = get_backing_play_session(session)
    if ps is None or ps.get("expired"):
        return False
    overrides = ps.get("overrides")
    if not isinstance(overrides, dict) or not overrides:
        return False
    for key in _OVERRIDE_FIELDS:
        val = overrides.get(key)
        if val not in (None, "", []):
            return True
    return False


__all__ = [
    "BACKING_PLAY_SESSION_EXPIRED_KEY",
    "BACKING_PLAY_SESSION_KEY",
    "apply_backing_play_session_to_widgets",
    "apply_current_play_session_to_backing_context",
    "recover_play_session_overrides_from_backing_context",
    "backing_play_session_has_override",
    "capture_backing_play_session_overrides",
    "current_backing_play_bpm",
    "effective_backing_play_overrides",
    "promote_live_slider_bpm_to_current",
    "trace_backing_bpm",
    "expire_backing_play_session",
    "expire_backing_play_session_on_page_exit",
    "get_backing_play_session",
    "play_session_blocks_canonical_seed",
    "resolve_backing_source_identity",
    "sync_backing_play_session_on_backing_page",
]
