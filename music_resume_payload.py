"""
Canonical Music resume envelopes for Command Center Continue cards.

Continue cards carry a typed payload that restores a specific task (song, key,
BPM, page, backing scope, creative setup, multitrack session, tone work, upload).
App Directory workstream entry uses soft URLs without embedding stale pick keys.
"""

from __future__ import annotations

import base64
import json
import re
from typing import Any, Literal

MUSIC_RESUME_PAYLOAD_VERSION = 1

MusicResumeKind = Literal[
    "practice",
    "backing",
    "creative",
    "multitrack",
    "tone",
    "upload",
    "analysis",
]

MUSIC_RESUME_KINDS: tuple[str, ...] = (
    "practice",
    "backing",
    "creative",
    "multitrack",
    "tone",
    "upload",
    "analysis",
)

MUSIC_WORKSTREAM_KINDS: tuple[str, ...] = (
    "song_practice",
    "backing",
    "creative",
    "upload",
    "multitrack",
    "tone",
)

_WORKSTREAM_PAGE: dict[str, str] = {
    "song_practice": "practice",
    "backing": "backing",
    "creative": "creative",
    "upload": "analysis",
    "multitrack": "multitrack",
    "tone": "practice",
}

_WORKSTREAM_LABELS: dict[str, str] = {
    "song_practice": "Song Practice",
    "backing": "Backing Track Work",
    "creative": "Creative Lab",
    "upload": "Upload Library",
    "multitrack": "Multitrack Recording",
    "tone": "Tone Development",
}

WORKSTREAM_PAGE = _WORKSTREAM_PAGE
WORKSTREAM_LABELS = _WORKSTREAM_LABELS


def normalize_resume_kind(raw: str | None) -> str:
    kind = str(raw or "").strip().lower()
    if kind in MUSIC_RESUME_KINDS:
        return kind
    page = kind
    page_map = {
        "practice": "practice",
        "backing": "backing",
        "creative": "creative",
        "custom": "creative",
        "multitrack": "multitrack",
        "analysis": "upload",
        "recording": "upload",
        "picker": "practice",
        "log": "practice",
    }
    return page_map.get(page, "practice")


def _resolve_workspace_id(*, st: Any | None = None, session: dict[str, Any] | None = None) -> str:
    try:
        from suite_workspace import get_active_workspace_id, resolve_workspace_id

        if st is not None:
            return normalize_workspace_id(get_active_workspace_id(st))
        if session is not None:
            ws = str(session.get("_suite_active_workspace_id") or session.get("workspace_id") or "").strip()
            if ws:
                return normalize_workspace_id(ws)
        return normalize_workspace_id(resolve_workspace_id())
    except ImportError:
        return "daniel"


def normalize_workspace_id(raw: str | None) -> str:
    try:
        from suite_workspace import normalize_workspace_id as _norm

        return _norm(raw)
    except ImportError:
        text = str(raw or "daniel").strip().lower() or "daniel"
        return re.sub(r"[^a-z0-9_]+", "_", text) or "daniel"


def _song_bits(session: dict[str, Any]) -> dict[str, str]:
    try:
        from songs.state import build_music_local_state

        state = build_music_local_state(type("St", (), {"session_state": session})())
    except Exception:
        sel = session.get("selected_song") or {}
        state = {
            "song": str(sel.get("title") or session.get("active_song_title") or session.get("song") or ""),
            "artist": str(sel.get("artist") or ""),
            "pick_key": str(session.get("active_catalog_pick_key") or sel.get("pick_key") or ""),
            "instrument": str(session.get("instrument") or ""),
            "display_key": str(session.get("display_key") or ""),
            "practice_focus_section": str(session.get("practice_focus_section") or ""),
            "studio_page": str(session.get("studio_page") or "practice"),
        }
    return {k: str(v or "").strip() for k, v in state.items()}


def _bpm_from_session(session: dict[str, Any]) -> int | None:
    for key in ("backing_track_bpm", "bpm", "active_song_bpm"):
        raw = session.get(key)
        if raw is None:
            continue
        try:
            val = int(raw)
            if val > 0:
                return val
        except (TypeError, ValueError):
            continue
    return None


def _backing_bits(session: dict[str, Any]) -> dict[str, Any]:
    bits: dict[str, Any] = {}
    try:
        from backing_track_state import gather_backing_filters, resolve_selected_section_names

        filters = gather_backing_filters(session)
        bits.update(filters)
        scope = str(filters.get("backing_track_scope") or "Full song")
        bits["backing_track_scope"] = scope
        sec_names: list[str] = []
        try:
            from backing_context import get_backing_context

            ctx = get_backing_context(session)
            if ctx is not None and ctx.sections:
                sec_names = list(ctx.sections)
        except Exception:
            pass
        if scope == "Selected sections" and not bits.get("backing_track_multi_sections"):
            bits["backing_track_multi_sections"] = resolve_selected_section_names(session, sec_names)
    except ImportError:
        bits["backing_track_scope"] = str(session.get("backing_track_scope") or "Full song")
        bits["backing_track_multi_sections"] = list(session.get("backing_track_multi_sections") or [])
        bits["backing_groove_style"] = str(session.get("backing_groove_style") or "")
        bits["backing_track_bpm"] = _bpm_from_session(session)
        bits["backing_track_loops"] = session.get("backing_track_loops")

    mood = ""
    intensity = ""
    style = str(bits.get("backing_groove_style") or session.get("backing_groove_style") or "").strip()
    try:
        from backing_musical_profile import resolve_backing_musical_profile_from_session

        prof = resolve_backing_musical_profile_from_session(session, style=style or "Auto")
        mood = str(prof.mood or "")
        intensity = str(prof.intensity or "")
        if not style or style == "Auto":
            style = str(prof.style or style)
    except Exception:
        pass

    try:
        from backing_context import get_backing_context

        ctx = get_backing_context(session)
        if ctx is not None:
            bits["backing_source"] = str(ctx.source or "")
            if not mood:
                mood = str(ctx.mood or "")
            if not intensity:
                intensity = str(ctx.groove_intensity or "")
            if ctx.sections and not bits.get("backing_track_multi_sections"):
                bits["backing_track_multi_sections"] = list(ctx.sections)
    except Exception:
        bits.setdefault("backing_source", "regular_song")

    bits["style"] = str(session.get("backing_groove_style") or style).strip() or style
    bits["mood"] = mood
    bits["intensity"] = intensity
    return bits


def _creative_bits(session: dict[str, Any]) -> dict[str, Any]:
    entry = str(session.get("improv_entry_mode") or "").strip()
    style = str(session.get("improv_style_key") or session.get("improv_style_meta", {}).get("style") or "").strip()
    if isinstance(session.get("improv_style_meta"), dict):
        meta = session["improv_style_meta"]
        style = style or str(meta.get("style") or meta.get("label") or "")
    progression = ""
    try:
        from backing_context import get_backing_context

        ctx = get_backing_context(session)
        if ctx is not None:
            progression = str(ctx.progression_label or " · ".join(ctx.progression[:4]) or "").strip()
            entry = entry or str(ctx.entry_mode or ctx.source or "")
            style = style or str(ctx.style or ctx.groove or "")
    except Exception:
        pass
    return {
        "improv_entry_mode": entry,
        "improv_style_key": style,
        "progression_label": progression,
        "concert_key": str(session.get("concert_key") or session.get("display_key") or ""),
    }


def _multitrack_bits(session: dict[str, Any]) -> dict[str, Any]:
    mt_id = str(
        session.get("multitrack_id")
        or session.get("_last_catalog_multitrack_id")
        or ""
    ).strip()
    title = str(session.get("multitrack_title") or session.get("active_song_title") or "").strip()
    song = _song_bits(session).get("song") or title
    return {"multitrack_id": mt_id, "multitrack_title": title or song, "song": song}


def _tone_bits(session: dict[str, Any]) -> dict[str, Any]:
    song_bits = _song_bits(session)
    return {
        "instrument": song_bits.get("instrument") or str(session.get("instrument") or ""),
        "display_key": song_bits.get("display_key") or str(session.get("display_key") or ""),
        "song": song_bits.get("song") or "",
        "tone_panel_open": bool(session.get("practice_tuner_panel_open")),
    }


def _upload_bits(session: dict[str, Any]) -> dict[str, Any]:
    song_bits = _song_bits(session)
    label = str(session.get("last_analysis_source_label") or "").strip()
    return {
        "song": song_bits.get("song") or "",
        "pick_key": song_bits.get("pick_key") or "",
        "upload_label": label,
        "studio_page": "analysis",
    }


def build_music_resume_payload(
    session: dict[str, Any],
    *,
    kind: str | None = None,
    workspace_id: str = "",
    st: Any | None = None,
) -> dict[str, Any]:
    """Capture a resumable task envelope from live session state."""
    song = _song_bits(session)
    page = str(session.get("studio_page") or song.get("studio_page") or "practice").strip()
    resolved_kind = normalize_resume_kind(kind or page)
    if page == "backing":
        resolved_kind = "backing"
    elif page in {"creative", "custom"}:
        resolved_kind = "creative"
    elif page == "multitrack":
        resolved_kind = "multitrack"
    elif page == "analysis":
        resolved_kind = "upload"

    ws = normalize_workspace_id(workspace_id or _resolve_workspace_id(st=st, session=session))
    payload: dict[str, Any] = {
        "version": MUSIC_RESUME_PAYLOAD_VERSION,
        "resume_kind": resolved_kind,
        "workspace_id": ws,
        "studio_page": _page_for_kind(resolved_kind, page),
        "song": song.get("song") or "",
        "artist": song.get("artist") or "",
        "pick_key": song.get("pick_key") or "",
        "instrument": song.get("instrument") or "",
        "display_key": song.get("display_key") or "",
        "practice_focus_section": song.get("practice_focus_section") or "",
        "bpm": _bpm_from_session(session),
    }

    if resolved_kind == "backing":
        backing = _backing_bits(session)
        payload.update(backing)
        payload["backing_groove_style"] = str(
            session.get("backing_groove_style") or backing.get("backing_groove_style") or backing.get("style") or ""
        ).strip()
        payload["studio_page"] = "backing"
    elif resolved_kind == "creative":
        payload.update(_creative_bits(session))
        payload["studio_page"] = "creative"
    elif resolved_kind == "multitrack":
        payload.update(_multitrack_bits(session))
        payload["studio_page"] = "multitrack"
    elif resolved_kind == "tone":
        payload.update(_tone_bits(session))
        payload["studio_page"] = "practice"
        payload["open_tone_panel"] = True
    elif resolved_kind in {"upload", "analysis"}:
        payload.update(_upload_bits(session))
        payload["resume_kind"] = "upload"
        payload["studio_page"] = "analysis"
    else:
        payload["studio_page"] = "practice"

    return payload


def _page_for_kind(kind: str, fallback: str) -> str:
    return {
        "practice": "practice",
        "backing": "backing",
        "creative": "creative",
        "multitrack": "multitrack",
        "tone": "practice",
        "upload": "analysis",
        "analysis": "analysis",
    }.get(kind, fallback or "practice")


def resume_key_for_payload(payload: dict[str, Any]) -> str:
    """Stable Continue card key — scoped by kind, not only pick_key."""
    kind = normalize_resume_kind(str(payload.get("resume_kind") or ""))
    ws = normalize_workspace_id(str(payload.get("workspace_id") or ""))
    pick = str(payload.get("pick_key") or "").strip()
    if kind == "backing":
        base = pick or str(payload.get("song") or "backing")
        return f"music:backing:{base}"
    if kind == "creative":
        entry = str(payload.get("improv_entry_mode") or payload.get("backing_source") or "creative")
        style = str(payload.get("improv_style_key") or payload.get("style") or "")
        token = re.sub(r"[^a-zA-Z0-9]+", "_", f"{entry}_{style}")[:48] or "creative"
        return f"music:creative:{token}"
    if kind == "multitrack":
        mt = str(payload.get("multitrack_id") or pick or "session")
        return f"music:multitrack:{mt}"
    if kind == "tone":
        inst = str(payload.get("instrument") or "instrument")
        dk = str(payload.get("display_key") or "key")
        return f"music:tone:{inst}:{dk}"
    if kind in {"upload", "analysis"}:
        base = pick or str(payload.get("upload_label") or payload.get("song") or "upload")
        return f"music:upload:{base}"
    base = pick or str(payload.get("song") or "practice")
    if ws != "daniel":
        return f"music:practice:{ws}:{base}"
    return f"song:{base}" if base else "music:practice:"


def legacy_resume_key_for_payload(payload: dict[str, Any]) -> str:
    """Backward-compatible suite_resume value for deep links."""
    kind = normalize_resume_kind(str(payload.get("resume_kind") or ""))
    pick = str(payload.get("pick_key") or "").strip()
    if kind == "backing":
        return f"backing:{pick}" if pick else "backing:"
    if pick:
        return f"song:{pick}"
    return str(resume_key_for_payload(payload))


def continue_card_title(payload: dict[str, Any]) -> str:
    kind = normalize_resume_kind(str(payload.get("resume_kind") or ""))
    song = str(payload.get("song") or "").strip()
    if kind == "backing":
        style = str(payload.get("style") or payload.get("backing_groove_style") or "Backing").strip()
        mood = str(payload.get("mood") or "").strip()
        intensity = str(payload.get("intensity") or "").strip()
        parts = [p for p in (style, mood, intensity) if p]
        label = " ".join(parts) if parts else "Backing Track"
        sections = _section_summary(payload)
        if sections:
            return f"Continue Backing Track — {label} — {sections}"
        return f"Continue Backing Track — {label}"
    if kind == "multitrack":
        title = str(payload.get("multitrack_title") or song or "Session").strip()
        return f"Continue Multitrack Recording — {title}"
    if kind == "tone":
        dk = str(payload.get("display_key") or "Concert key").strip()
        return f"Continue Tone Practice — {dk}"
    if kind == "creative":
        style = str(payload.get("improv_style_key") or payload.get("style") or "Creative").strip()
        prog = str(payload.get("progression_label") or "").strip()
        if prog:
            return f"Continue Creative Lab — {style} — {prog}"
        return f"Continue Creative Lab — {style}"
    if kind in {"upload", "analysis"}:
        label = str(payload.get("upload_label") or song or "Upload").strip()
        return f"Continue Upload — {label}"

    inst = str(payload.get("instrument") or "").strip()
    dk = str(payload.get("display_key") or "").strip()
    bpm = payload.get("bpm")
    head = f"Continue {song}" if song else "Continue Practice"
    bits: list[str] = []
    if inst:
        bits.append(inst)
    if dk:
        bits.append(f"Key: {dk}")
    if bpm:
        bits.append(f"{int(bpm)} BPM")
    if bits:
        return f"{head} — {' — '.join(bits)}"
    return head


def continue_card_subtitle(payload: dict[str, Any]) -> str:
    kind = normalize_resume_kind(str(payload.get("resume_kind") or ""))
    page = str(payload.get("studio_page") or "").strip()
    focus = str(payload.get("practice_focus_section") or "").strip()
    if kind == "backing":
        scope = str(payload.get("backing_track_scope") or "Full song")
        loops = payload.get("backing_track_loops")
        bpm = payload.get("backing_track_bpm") or payload.get("bpm")
        parts = [scope]
        sec = _section_summary(payload)
        if sec:
            parts.append(sec)
        if bpm:
            parts.append(f"{int(bpm)} BPM")
        if loops:
            parts.append(f"{int(loops)} loops")
        if page:
            parts.append(page)
        return " · ".join(str(p) for p in parts if p)
    if kind == "creative":
        entry = str(payload.get("improv_entry_mode") or "").strip()
        dk = str(payload.get("display_key") or payload.get("concert_key") or "").strip()
        parts = [p for p in (entry, dk, page or "creative") if p]
        return " · ".join(parts) or "Creative Lab"
    if kind == "multitrack":
        song = str(payload.get("song") or "").strip()
        return song or "Multitrack session"
    if kind == "tone":
        inst = str(payload.get("instrument") or "").strip()
        return inst or "Tone / tuner"
    if kind in {"upload", "analysis"}:
        return str(payload.get("upload_label") or payload.get("song") or "Upload workflow")
    parts = [p for p in (focus, page or "practice") if p]
    artist = str(payload.get("artist") or "").strip()
    if artist and not parts:
        return artist
    return " · ".join(parts) if parts else str(payload.get("artist") or "Practice")


def _section_summary(payload: dict[str, Any]) -> str:
    multi = payload.get("backing_track_multi_sections")
    if isinstance(multi, list) and multi:
        return " + ".join(str(s) for s in multi[:4] if str(s).strip())
    single = str(payload.get("backing_track_single_section") or payload.get("practice_focus_section") or "").strip()
    return single


def encode_payload_b64(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_payload_b64(raw: str) -> dict[str, Any]:
    text = str(raw or "").strip()
    if not text:
        return {}
    pad = "=" * (-len(text) % 4)
    try:
        decoded = base64.urlsafe_b64decode(text + pad)
        parsed = json.loads(decoded.decode("utf-8"))
        return parsed if isinstance(parsed, dict) else {}
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return {}


def payload_workspace_matches(payload: dict[str, Any], workspace_id: str) -> bool:
    expected = normalize_workspace_id(workspace_id)
    actual = normalize_workspace_id(str(payload.get("workspace_id") or ""))
    return bool(actual) and actual == expected


def filter_payloads_for_workspace(
    payloads: list[dict[str, Any]],
    workspace_id: str,
) -> list[dict[str, Any]]:
    ws = normalize_workspace_id(workspace_id)
    return [p for p in payloads if payload_workspace_matches(p, ws)]


def apply_music_resume_payload(
    session: dict[str, Any],
    payload: dict[str, Any],
    *,
    song_picker_catalog: dict | None = None,
    song_library: dict | None = None,
    st: Any | None = None,
) -> bool:
    """Apply a Continue-card payload to session state (after catalog load when needed)."""
    if not payload:
        return False
    active_ws = _resolve_workspace_id(st=st, session=session)
    if payload.get("workspace_id") and not payload_workspace_matches(payload, active_ws):
        return False

    kind = normalize_resume_kind(str(payload.get("resume_kind") or ""))
    pick = str(payload.get("pick_key") or "").strip()
    if pick and song_picker_catalog:
        try:
            from songs.state import apply_pick_key

            apply_pick_key(
                type("St", (), {"session_state": session})(),
                pick,
                song_picker_catalog,
                song_library=song_library,
                skip_activity_log=True,
            )
        except Exception:
            session["active_catalog_pick_key"] = pick
    elif pick:
        session["active_catalog_pick_key"] = pick

    song = str(payload.get("song") or "").strip()
    if song:
        session["song"] = song

    display_key = str(payload.get("display_key") or "").strip()
    if display_key:
        try:
            from songs.key_state import PENDING_DISPLAY_KEY

            session[PENDING_DISPLAY_KEY] = display_key
        except ImportError:
            session["display_key"] = display_key

    instrument = str(payload.get("instrument") or "").strip()
    if instrument:
        try:
            from practice_setup_globals import set_active_instrument

            set_active_instrument(session, instrument)
        except ImportError:
            session["instrument"] = instrument

    section = str(payload.get("practice_focus_section") or "").strip()
    if section:
        session["practice_focus_section"] = section

    bpm = payload.get("bpm") or payload.get("backing_track_bpm")
    if bpm is not None:
        try:
            session["bpm"] = int(bpm)
            session["backing_track_bpm"] = int(bpm)
        except (TypeError, ValueError):
            pass

    if kind == "backing":
        _apply_backing_payload(session, payload)
    elif kind == "creative":
        _apply_creative_payload(session, payload)
    elif kind == "multitrack":
        _apply_multitrack_payload(session, payload)
    elif kind == "tone":
        session["_suite_open_tone_panel"] = True
    elif kind in {"upload", "analysis"}:
        pass

    target = str(payload.get("studio_page") or _page_for_kind(kind, "practice"))
    try:
        from studio_nav_history import navigate_studio_page

        navigate_studio_page(session, target)
    except Exception:
        pass
    session["studio_page"] = target
    return True


def _apply_backing_payload(session: dict[str, Any], payload: dict[str, Any]) -> None:
    try:
        from backing_track_state import _apply_filters_to_session_keys, normalize_backing_scope

        filters = {
            "backing_track_scope": normalize_backing_scope(
                payload.get("backing_track_scope") or "Full song"
            ),
            "backing_track_single_section": payload.get("backing_track_single_section"),
            "backing_track_multi_sections": payload.get("backing_track_multi_sections"),
            "backing_track_loops": payload.get("backing_track_loops"),
            "backing_track_bpm": payload.get("backing_track_bpm") or payload.get("bpm"),
            "backing_groove_style": payload.get("backing_groove_style"),
            "backing_time_signature": payload.get("backing_time_signature"),
            "backing_time_signature_override": payload.get("backing_time_signature_override"),
        }
        _apply_filters_to_session_keys(session, {k: v for k, v in filters.items() if v is not None})
    except ImportError:
        for key in (
            "backing_track_scope",
            "backing_track_multi_sections",
            "backing_track_loops",
            "backing_groove_style",
        ):
            if payload.get(key) is not None:
                session[key] = payload[key]
        if payload.get("backing_track_bpm") or payload.get("bpm"):
            session["backing_track_bpm"] = payload.get("backing_track_bpm") or payload.get("bpm")


def _apply_creative_payload(session: dict[str, Any], payload: dict[str, Any]) -> None:
    entry = str(payload.get("improv_entry_mode") or "").strip()
    if entry:
        session["improv_entry_mode"] = entry
    style = str(payload.get("improv_style_key") or payload.get("style") or "").strip()
    if style:
        session["improv_style_key"] = style


def _apply_multitrack_payload(session: dict[str, Any], payload: dict[str, Any]) -> None:
    mt_id = str(payload.get("multitrack_id") or "").strip()
    if mt_id:
        session["multitrack_id"] = mt_id
        session["_last_catalog_multitrack_id"] = mt_id
        session["_pending_catalog_multitrack_id"] = mt_id


__all__ = (
    "MUSIC_RESUME_KINDS",
    "MUSIC_RESUME_PAYLOAD_VERSION",
    "MUSIC_WORKSTREAM_KINDS",
    "WORKSTREAM_LABELS",
    "WORKSTREAM_PAGE",
    "apply_music_resume_payload",
    "build_music_resume_payload",
    "continue_card_subtitle",
    "continue_card_title",
    "decode_payload_b64",
    "encode_payload_b64",
    "filter_payloads_for_workspace",
    "legacy_resume_key_for_payload",
    "normalize_resume_kind",
    "payload_workspace_matches",
    "resume_key_for_payload",
)
