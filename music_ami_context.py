"""Music Practice Coach AMI context — cache, build, classify, finalize at send."""

from __future__ import annotations

import copy
import re
from typing import Any

from music_coach_context import (
    APP_ID,
    COACH_PAGE_DISPLAY,
    coach_page_display_name,
    resolve_coach_source_page,
)

_AMI_MUSIC_SNAPSHOT_KEY = "_ami_music_snapshot"
_AMI_PAGE_CACHE_SIGS = "_ami_music_page_cache_sigs"
_AMI_CONTEXT_BY_PAGE = "_ami_context_by_page"

_STALE_SONG_FOCUS_KEYS = (
    "question_song",
    "question_song_row",
    "song_focus",
    "section_focus_named",
)

_PRACTICE_INTENT_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "practice_plan",
        (
            "what should i practice",
            "what should i do",
            "practice next",
            "practice plan",
            "what to practice",
            "this week",
            "how much time",
            "how long should",
            "minutes should",
            "minutes to practice",
            "time should i spend",
            "time on",
            "focus on today",
            "what should i focus",
            "practice this song",
            "practice the song",
            "have to practice",
        ),
    ),
    (
        "chord_transition",
        ("chord change", "chord changes", "chord transition", "transition between", "improve these chords"),
    ),
    ("section_focus", ("chorus", "verse", "bridge", "pre-chorus", "section", "drill", "loop this")),
    ("tempo_key", ("tempo", "bpm", "too fast", "too slow", "what key")),
    (
        "skill_technique",
        ("technique", "what technique", "learn before", "what should i learn", "skill should"),
    ),
    ("difficulty", ("too difficult", "too hard", "too easy", "my level", "difficult for", "within my level")),
    ("backing_track", ("backing track", "groove", "play along")),
    ("lyrics_cues", ("lyrics", "lyric", "when do i come in", "memorize", "cue")),
)


def _song_title(raw: Any) -> str:
    if isinstance(raw, dict):
        return str(raw.get("title") or raw.get("name") or "").strip()
    return str(raw or "").strip()


def _compact_song(song: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(song, dict) or not song:
        return {}
    out: dict[str, Any] = {}
    for key in ("pick_key", "title", "artist", "genre", "bpm", "key", "default_key", "sections"):
        val = song.get(key)
        if val is not None and val != "":
            out[key] = copy.deepcopy(val) if key == "sections" else val
    return out


def _should_skip_music_cache(session: dict[str, Any], coach_page: str, sig: tuple[Any, ...]) -> bool:
    store = session.get(_AMI_PAGE_CACHE_SIGS)
    if not isinstance(store, dict):
        store = {}
    prev = store.get(coach_page)
    if prev == sig:
        return True
    store[coach_page] = sig
    session[_AMI_PAGE_CACHE_SIGS] = store
    return False


def _active_instrument_for_ami(session_state: dict[str, Any], song_ctx: dict[str, Any]) -> str:
    try:
        from practice_setup_globals import get_active_instrument

        inst = str(get_active_instrument(session_state) or "").strip()
        if inst:
            return inst
    except ImportError:
        pass
    return str(song_ctx.get("instrument") or session_state.get("instrument") or "").strip()


def _active_level_for_ami(session_state: dict[str, Any], song_ctx: dict[str, Any]) -> str:
    try:
        from practice_setup_globals import get_active_level

        level = str(get_active_level(session_state) or "").strip()
        if level:
            return level
    except ImportError:
        pass
    return str(song_ctx.get("level") or session_state.get("level") or "").strip()


def gather_practice_ami_snapshot(
    session_state: dict[str, Any],
    *,
    include_practice_logs: bool = True,
) -> dict[str, Any]:
    """JSON-safe practice + active song context for AMI."""
    try:
        from active_song_state import gather_active_song_context
    except ImportError:
        gather_active_song_context = None  # type: ignore[assignment,misc]

    try:
        from practice_state import gather_practice_filters
    except ImportError:
        gather_practice_filters = None  # type: ignore[assignment,misc]

    song_ctx = gather_active_song_context(session_state) if gather_active_song_context else {}
    practice = gather_practice_filters(session_state) if gather_practice_filters else {}
    song = song_ctx.get("selected_song") if isinstance(song_ctx.get("selected_song"), dict) else {}
    if not song:
        raw = session_state.get("selected_song")
        song = raw if isinstance(raw, dict) else {}

    bpm = song.get("bpm") or session_state.get("active_song_bpm")
    try:
        from songs.playback_defaults import canonical_active_song_bpm

        if bpm is None and song:
            bpm = canonical_active_song_bpm(song)
    except ImportError:
        pass

    sections: list[str] = []
    if isinstance(song.get("sections"), list):
        sections = [str(s) for s in song["sections"] if str(s).strip()][:12]

    history: list[dict[str, Any]] = []
    practice_log_summary: dict[str, Any] = {}
    practice_log_ami_payload: dict[str, Any] = {}
    tone_history: dict[str, Any] = {}
    if include_practice_logs:
        try:
            from practice_log_ami import build_practice_log_ami_payload
            from practice_log_state import load_entries

            entries = load_entries(session_state)
            practice_log_ami_payload = build_practice_log_ami_payload(
                session_state,
                entries=entries,
                window_days=14,
            )
            practice_log_summary = dict(practice_log_ami_payload.get("practice_log_summary") or {})
            recent = practice_log_ami_payload.get("recent_sessions")
            if isinstance(recent, list):
                history = [dict(x) for x in recent[:8] if isinstance(x, dict)]
        except Exception:
            log = session_state.get("practice_log_entries") or session_state.get("practice_history")
            if isinstance(log, list):
                history = [dict(x) for x in log[:8] if isinstance(x, dict)]

    try:
        from media_persistence import build_media_ami_payload

        media_payload = build_media_ami_payload(None, window_days=30)
        tone_history = dict(media_payload.get("tone_history") or {})
    except Exception:
        tone_history = {}

    snap: dict[str, Any] = {
        "coach_page": "practice",
        "pick_key": str(song_ctx.get("pick_key") or song.get("pick_key") or session_state.get("active_catalog_pick_key") or ""),
        "title": _song_title(song),
        "artist": str(song.get("artist") or "").strip(),
        "genre": str(song.get("genre") or "").strip(),
        "display_key": str(session_state.get("display_key") or song_ctx.get("display_key") or "").strip(),
        "bpm": int(bpm) if bpm is not None else None,
        "instrument": _active_instrument_for_ami(session_state, song_ctx),
        "level": _active_level_for_ami(session_state, song_ctx),
        "focus": str(song_ctx.get("focus") or session_state.get("focus") or "").strip(),
        "practice_mode": str(practice.get("last_practice_mode") or session_state.get("last_practice_mode") or "").strip(),
        "practice_focus_section": str(
            practice.get("practice_focus_section") or session_state.get("practice_focus_section") or ""
        ).strip(),
        "practice_groove_style": str(
            practice.get("practice_groove_style") or session_state.get("practice_groove_style") or ""
        ).strip(),
        "practice_minutes": practice.get("practice_minutes"),
        "practice_notation_lines": practice.get("practice_notation_lines"),
        "practice_notation_difficulty": practice.get("practice_notation_difficulty"),
        "sections": sections,
        "recent_practice_history": history,
        "practice_log_summary": practice_log_summary,
        "practice_log_ami_payload": practice_log_ami_payload,
        "tone_history": tone_history,
        "studio_page": str(session_state.get("studio_page") or "practice"),
    }
    return {k: v for k, v in snap.items() if v is not None and v != "" and v != []}


def cache_music_ami_context(
    session_state: dict[str, Any],
    *,
    coach_page: str | None = None,
) -> dict[str, Any]:
    """Cache lightweight AMI snapshot when song/practice inputs change (sig skip)."""
    page = str(coach_page or resolve_coach_source_page(session_state)).strip() or "practice"
    try:
        from global_active_song_state import prepare_global_active_song

        prepare_global_active_song(session_state)
    except ImportError:
        pass

    if page == "practice":
        snap = gather_practice_ami_snapshot(session_state)
    else:
        snap = {"coach_page": page, **gather_practice_ami_snapshot(session_state)}

    sig = (
        page,
        snap.get("pick_key"),
        snap.get("display_key"),
        snap.get("practice_focus_section"),
        snap.get("instrument"),
        snap.get("level"),
        snap.get("practice_groove_style"),
        snap.get("practice_mode"),
    )
    action = "built"
    if _should_skip_music_cache(session_state, page, sig):
        cached = session_state.get(_AMI_MUSIC_SNAPSHOT_KEY)
        if isinstance(cached, dict) and cached.get("practice_snapshot"):
            action = "skipped_unchanged"
            return {"cache_action": action, "coach_page": page}

    session_state[_AMI_MUSIC_SNAPSHOT_KEY] = {
        "coach_page": page,
        "practice_snapshot": snap,
        "cached_at": snap.get("pick_key"),
    }
    by_page = session_state.get(_AMI_CONTEXT_BY_PAGE)
    if not isinstance(by_page, dict):
        by_page = {}
    by_page[page] = copy.deepcopy(session_state[_AMI_MUSIC_SNAPSHOT_KEY])
    session_state[_AMI_CONTEXT_BY_PAGE] = by_page
    return {"cache_action": action, "coach_page": page, "pick_key": snap.get("pick_key")}


def extract_song_title_from_question(question: str) -> str:
    """Pull a song title from free-text when the user names it explicitly."""
    q = str(question or "").strip()
    if not q:
        return ""
    m = re.search(r'"([^"]{2,80})"', q)
    if m:
        return m.group(1).strip()
    m = re.search(r"'([^']{2,80})'", q)
    if m:
        return m.group(1).strip()
    for pat in (
        r"(?:song|track)\s+(.+?)(?:\?|$)",
        r"practice\s+(?:the\s+)?(.+?)\s+(?:chorus|verse|bridge|section)",
    ):
        m = re.search(pat, q, flags=re.I)
        if m:
            title = m.group(1).strip().strip("?.,")
            if 2 <= len(title) <= 80:
                return title
    return ""


def extract_section_from_question(question: str) -> str:
    q = str(question or "").lower()
    for sec in ("chorus", "verse", "bridge", "pre-chorus", "intro", "outro", "solo"):
        if sec in q:
            return sec.title() if sec != "pre-chorus" else "Pre-Chorus"
    return ""


_TRANSPOSE_PHRASES: tuple[str, ...] = (
    "instead of",
    "transpose",
    "transposing",
    "move up a half step",
    "move up a whole step",
    "move down a half step",
    "move down a whole step",
    "half step up",
    "whole step up",
    "what notes",
    "what note",
    "notes would i",
    "notes do i",
    "notes should i",
    "convert this key",
    "key conversion",
)

_SIMILAR_SONG_PHRASES: tuple[str, ...] = (
    "songs similar to",
    "similar to",
    "songs like",
    "song like",
    "recommend songs",
    "what songs can i practice",
    "songs can i practice",
    "songs to practice that are similar",
    "songs can i practice that are similar",
    "what should i play after",
    "similar repertoire",
    "songs in the same style",
    "other songs like",
)

_MUSIC_THEORY_PHRASES: tuple[str, ...] = (
    "music theory",
    "what scale",
    "which scale",
    "what mode",
    "interval",
    "chord theory",
    "why does this chord",
    "roman numeral",
    "harmonic function",
    "circle of fifths",
)


def _is_transposition_question(low: str) -> bool:
    if re.search(r"\bin\s+[a-g][#b]?\s+instead\s+of\s+[a-g]", low):
        return True
    if re.search(r"\bplay\b.+\bin\s+[a-g][#b]?\s+instead\s+of", low):
        return True
    if any(p in low for p in _TRANSPOSE_PHRASES):
        return True
    if re.search(r"\btranspose\b", low) and any(
        p in low for p in ("key", "note", "chord", "sax", "horn", "trumpet")
    ):
        return True
    if re.search(r"\bwhat\s+key\s+should\s+i\s+(play|use)\b", low) and any(
        p in low for p in ("alto", "tenor", "sax", "trumpet", "clarinet", "instead", "convert")
    ):
        return True
    return False


def _is_similar_songs_question(low: str) -> bool:
    if any(p in low for p in _SIMILAR_SONG_PHRASES):
        return True
    if re.search(r"\bsongs?\b.+\bsimilar\b", low) or re.search(r"\bsimilar\b.+\bsongs?\b", low):
        return True
    if "recommend" in low and "song" in low:
        return True
    return False


def _is_music_theory_question(low: str) -> bool:
    if any(p in low for p in _MUSIC_THEORY_PHRASES):
        return True
    if re.search(r"\bwhat\s+(scale|mode|chord)\b", low) and not re.search(r"\bpractice\b", low):
        return True
    return False


def detect_music_send_intent(question: str, coach_page: str = "") -> str:
    """Classify Music Coach AMI send intent from question text."""
    q = str(question or "").strip()
    low = q.lower()
    if not low:
        return "music_general"
    page = str(coach_page or "").strip().lower()

    if any(
        p in low
        for p in (
            "analyze my practice",
            "analyze my practice history",
            "practice history analysis",
            "practice log analysis",
            "patterns in my practice",
            "what patterns are showing",
            "am i avoiding",
        )
    ):
        return "practice_history_analysis"
    if page == "log" and any(p in low for p in ("analyze", "pattern", "history", "trend", "avoid")):
        return "practice_history_analysis"

    if _is_transposition_question(low):
        return "music_transposition"
    if _is_similar_songs_question(low):
        return "similar_songs"
    if _is_music_theory_question(low):
        return "music_theory"

    if re.search(r"\b\d{1,3}\s*minutes?\b", low) and any(
        p in low for p in ("practice", "song", "session", "today", "do")
    ):
        return "practice_plan"
    if "what should i do" in low and any(p in low for p in ("practice", "song", "minutes", "session")):
        return "practice_plan"
    if page == "backing" or page == "karaoke":
        if any(p in low for p in ("tempo", "bpm", "too fast", "too slow")):
            return "tempo_key"
        if any(p in low for p in ("loop", "section", "verse", "chorus")):
            return "section_focus"
        if "lyric" in low or "memorize" in low or "cue" in low:
            return "lyrics_cues"
        return "backing_track"
    if page == "custom":
        if "voicing" in low or "progression" in low or "ii" in low or "chord" in low:
            return "chord_transition"
        return "progression_analysis"
    for intent, phrases in _PRACTICE_INTENT_RULES:
        if intent == "practice_plan" and (
            _is_similar_songs_question(low)
            or _is_transposition_question(low)
            or _is_music_theory_question(low)
        ):
            continue
        if any(p in low for p in phrases):
            return intent
    if extract_song_title_from_question(q):
        return "named_song"
    return "music_general"


def _clear_stale_song_context(ctx: dict[str, Any], question: str) -> None:
    named = extract_song_title_from_question(question)
    if not named:
        for key in _STALE_SONG_FOCUS_KEYS:
            ctx.pop(key, None)
        return
    focus = str(ctx.get("question_song") or ctx.get("song_focus") or "").strip().lower()
    if focus and focus != named.lower():
        for key in _STALE_SONG_FOCUS_KEYS:
            ctx.pop(key, None)


def attach_question_song_to_context(ctx: dict[str, Any], question: str, session_state: dict[str, Any]) -> None:
    """Bind question-named song/section; keep active song as fallback anchor."""
    _clear_stale_song_context(ctx, question)
    named = extract_song_title_from_question(question)
    section = extract_section_from_question(question)
    snap = ctx.get("practice_snapshot") if isinstance(ctx.get("practice_snapshot"), dict) else {}
    active = ctx.get("active_song") if isinstance(ctx.get("active_song"), dict) else snap

    if named:
        ctx["question_song"] = named
        if active and _song_title(active).lower() == named.lower():
            ctx["song_focus"] = active
        else:
            ctx["song_focus"] = {"title": named}
    elif active and _song_title(active):
        ctx.setdefault("question_song", _song_title(active))
        ctx.setdefault("song_focus", active)

    if section:
        ctx["section_focus_named"] = section
        ctx.setdefault("practice_focus_section", section)


def finalize_music_context_for_send(
    ctx: dict[str, Any],
    session_state: dict[str, Any],
    *,
    question: str = "",
    coach_page: str = "",
) -> None:
    """Promote cached music snapshot and route by question intent at send time."""
    page = str(coach_page or ctx.get("coach_page") or resolve_coach_source_page(session_state)).strip()
    q = str(question or ctx.get("question") or "").strip()

    cached = session_state.get(_AMI_MUSIC_SNAPSHOT_KEY)
    if not isinstance(cached, dict) or not cached.get("practice_snapshot"):
        cache_music_ami_context(session_state, coach_page=page)
        cached = session_state.get(_AMI_MUSIC_SNAPSHOT_KEY)

    if isinstance(cached, dict):
        snap = cached.get("practice_snapshot")
        if isinstance(snap, dict):
            ctx["practice_snapshot"] = copy.deepcopy(snap)
            ctx["pick_key"] = snap.get("pick_key") or ctx.get("pick_key")
            if snap.get("title"):
                ctx["active_song"] = {
                    "title": snap.get("title"),
                    "artist": snap.get("artist"),
                    "genre": snap.get("genre"),
                    "pick_key": snap.get("pick_key"),
                    "bpm": snap.get("bpm"),
                    "sections": snap.get("sections"),
                }
            for key in (
                "instrument",
                "level",
                "focus",
                "display_key",
                "practice_focus_section",
                "practice_groove_style",
                "practice_mode",
                "practice_minutes",
                "bpm",
                "genre",
            ):
                if snap.get(key) is not None and snap.get(key) != "":
                    ctx[key] = snap[key]

    # Fresh Practice Key on submit rerun — never keep a stale cached display_key.
    try:
        from music_coach_ami.chart_context_reader import resolve_live_coach_practice_key

        live_key, pk_trace = resolve_live_coach_practice_key(session_state, ami_ctx=ctx)
        if live_key:
            ctx["display_key"] = live_key
            snap_out = ctx.get("practice_snapshot")
            if isinstance(snap_out, dict):
                snap_out = dict(snap_out)
                snap_out["display_key"] = live_key
                ctx["practice_snapshot"] = snap_out
            ctx["practice_key_trace"] = pk_trace
    except ImportError:
        live = str(session_state.get("display_key") or session_state.get("concert_key") or "").strip()
        if live:
            ctx["display_key"] = live

    # Live instrument / level / focus / section must beat a stale AMI cache snapshot.
    # Otherwise Bass→Piano (same wording) fingerprints as a duplicate of the prior send.
    live_song: dict[str, Any] = {}
    try:
        from active_song_state import gather_active_song_context

        live_song = gather_active_song_context(session_state) or {}
    except Exception:
        live_song = {}
    live_instrument = _active_instrument_for_ami(session_state, live_song)
    live_level = _active_level_for_ami(session_state, live_song)
    live_focus = str(live_song.get("focus") or session_state.get("focus") or "").strip()
    live_section = str(
        session_state.get("practice_focus_section")
        or session_state.get("ii_selected_section")
        or live_song.get("practice_focus_section")
        or ""
    ).strip()
    snap_live = ctx.get("practice_snapshot")
    if isinstance(snap_live, dict):
        snap_live = dict(snap_live)
    else:
        snap_live = {}
    if live_instrument:
        ctx["instrument"] = live_instrument
        snap_live["instrument"] = live_instrument
    if live_level:
        ctx["level"] = live_level
        snap_live["level"] = live_level
    if live_focus:
        ctx["focus"] = live_focus
        snap_live["focus"] = live_focus
    if live_section:
        ctx["practice_focus_section"] = live_section
        snap_live["practice_focus_section"] = live_section
    if snap_live:
        ctx["practice_snapshot"] = {**(ctx.get("practice_snapshot") or {}), **snap_live}

    intent = detect_music_send_intent(q, page)
    ctx["routing_hint"] = intent
    ctx["problem_type_hint"] = intent
    ctx["intent"] = intent
    ctx["coach_page"] = page
    ctx["source_page"] = page

    if q:
        attach_question_song_to_context(ctx, q, session_state)

    if intent == "section_focus" and ctx.get("section_focus_named"):
        ctx["practice_focus_section"] = ctx["section_focus_named"]


def build_music_applied_math_context(
    coach_page: str,
    session_state: dict[str, Any],
    *,
    question: str = "",
) -> dict[str, Any]:
    """Full AMI context package for Music Coach send and Command Center."""
    page = str(coach_page or "").strip() or resolve_coach_source_page(session_state)
    cache_trace = cache_music_ami_context(session_state, coach_page=page)
    snap = gather_practice_ami_snapshot(session_state)
    song = _compact_song(snap if snap.get("title") else session_state.get("selected_song"))

    ctx: dict[str, Any] = {
        "source_app": "Music",
        "app_id": APP_ID,
        "page": coach_page_display_name(page),
        "coach_page": page,
        "source_page": page,
        "workflow": "Music practice coach",
        "pick_key": snap.get("pick_key") or song.get("pick_key"),
        "active_song": song or {"title": snap.get("title"), "artist": snap.get("artist")},
        "practice_snapshot": snap,
        "instrument": snap.get("instrument"),
        "level": snap.get("level"),
        "skill_level": snap.get("level"),
        "focus": snap.get("focus"),
        "display_key": snap.get("display_key"),
        "practice_focus_section": snap.get("practice_focus_section"),
        "practice_groove_style": snap.get("practice_groove_style"),
        "practice_mode": snap.get("practice_mode"),
        "bpm": snap.get("bpm"),
        "genre": snap.get("genre"),
        "sections": snap.get("sections"),
        "recent_practice_history": snap.get("recent_practice_history"),
        "practice_log_summary": snap.get("practice_log_summary"),
        "practice_log_ami_payload": snap.get("practice_log_ami_payload"),
        "recent_sessions": (snap.get("practice_log_ami_payload") or {}).get("recent_sessions")
        if isinstance(snap.get("practice_log_ami_payload"), dict)
        else None,
        "cache_build_action": cache_trace.get("cache_action"),
    }
    if song.get("title"):
        artist = str(song.get("artist") or "").strip()
        ctx["song"] = f"{song['title']} — {artist}" if artist else song["title"]

    # Overlay live Practice Key even when snapshot/cache still holds the prior key.
    try:
        from music_coach_ami.chart_context_reader import resolve_live_coach_practice_key

        live_key, pk_trace = resolve_live_coach_practice_key(session_state, ami_ctx=ctx)
        if live_key:
            ctx["display_key"] = live_key
            snap_live = ctx.get("practice_snapshot")
            if isinstance(snap_live, dict):
                snap_live = dict(snap_live)
                snap_live["display_key"] = live_key
                ctx["practice_snapshot"] = snap_live
            ctx["practice_key_trace"] = pk_trace
    except ImportError:
        pass

    if str(question or "").strip():
        finalize_music_context_for_send(ctx, session_state, question=question, coach_page=page)

    return {k: v for k, v in ctx.items() if v is not None and v != "" and v != []}


def build_music_send_pipeline_diagnostics(ctx: dict[str, Any], session_state: dict[str, Any]) -> dict[str, Any]:
    from music_ami_pages import build_music_send_diagnostics

    q = str(ctx.get("question") or "")
    diag = build_music_send_diagnostics(ctx, question=q)
    diag["cache_build_action"] = ctx.get("cache_build_action") or session_state.get("_ami_last_cache_action")
    return diag
