"""Explicit Mission owner contract — one context while Missions / Mission Backing own.

Mission Practice Key, written transposition, progression, and Mission Backing
handoff resolve from this contract. Stale Jam / SBI preview / Original-key
residue must not reconstruct Mission identity.

Concert Practice vs Written Key are never interchangeable:
- Practice / Concert / Sounding = concert pitch
- Written / chart = derived display only (e.g. Bb Clarinet F → G)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MISSION_OWNER = "mission"
BACKING_HANDOFF_SOURCE_KEY = "_backing_explicit_handoff_source"
MISSION_RETURN_DESTINATION_KEY = "_music_mission_canonical_return_destination"

# Explicit Mission → Backing key envelope (never overload a generic ``key``).
HANDOFF_ORIGINAL_KEY = "_mission_backing_handoff_original_key"
HANDOFF_PRACTICE_KEY = "_mission_backing_handoff_practice_key"
HANDOFF_SOUNDING_KEY = "_mission_backing_handoff_sounding_key"
HANDOFF_WRITTEN_KEY = "_mission_backing_handoff_written_key"
HANDOFF_DIAG_PATH = Path(__file__).resolve().parent / "scripts" / "evidence-creative-backing" / "_mission_backing_handoff_diag.jsonl"


def _tok(raw: Any) -> str:
    return str(raw or "").strip().split()[0] if str(raw or "").strip() else ""


def _mission_handoff_diag(event: str, payload: dict[str, Any]) -> None:
    """Append one JSON line for Mission → Backing Practice Key debugging."""
    try:
        HANDOFF_DIAG_PATH.parent.mkdir(parents=True, exist_ok=True)
        row = {"event": event, **payload}
        with HANDOFF_DIAG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, default=str) + "\n")
    except Exception:
        pass


def _charts_on(session: dict[str, Any]) -> bool:
    try:
        from instrument_transposition import chart_in_instrument_key

        return bool(chart_in_instrument_key(session))
    except ImportError:
        return bool(session.get("show_chart_in_instrument_key"))


def _written_of(session: dict[str, Any], concert: str) -> str:
    concert = _tok(concert)
    if not concert:
        return ""
    try:
        from effective_practice_context import musician_facing_chart_key

        return _tok(musician_facing_chart_key(session, concert) or "")
    except ImportError:
        pass
    try:
        from instrument_transposition import written_key_for_type

        inst = str(session.get("instrument") or "").strip()
        sax = str(session.get("sax_type") or "").strip()
        return _tok(written_key_for_type(concert, sax or inst) or "")
    except ImportError:
        return concert


def _is_written_pollution(session: dict[str, Any], candidate: str, concert_hint: str = "") -> bool:
    """True when candidate is Bb-written (e.g. G) for a different concert Practice (F)."""
    cand = _tok(candidate)
    if not cand or not _charts_on(session):
        return False
    hint = _tok(concert_hint)
    if hint and cand == hint:
        return False
    if hint:
        written = _written_of(session, hint)
        if written and cand == written and cand != hint:
            return True
    # No hint: reject display_key when it matches written-of(concert_key) and differs.
    concert = _tok(session.get("concert_key") or session.get("practice_concert_key") or "")
    if concert and cand != concert:
        written = _written_of(session, concert)
        if written and cand == written:
            return True
    sticky = _tok(_sticky_mission_practice(session) or "")
    if sticky and cand != sticky:
        written = _written_of(session, sticky)
        if written and cand == written:
            return True
    return False


def _cpl_practice_and_original(session: dict[str, Any]) -> tuple[str, str]:
    """Custom Active Practice + Original when Custom owns Global Active."""
    try:
        from custom_progression_lab import CPL_ACTIVE_KEY
        from songs.music_source import custom_progression_is_active

        if not custom_progression_is_active(session):
            return "", ""
        active = session.get(CPL_ACTIVE_KEY)
        if not isinstance(active, dict):
            return "", ""
        return _tok(active.get("practice_key") or ""), _tok(active.get("original_key_center") or "")
    except ImportError:
        return "", ""


def _sticky_mission_practice(session: dict[str, Any]) -> str:
    """Underlying Trial/catalog saved Practice — never Original, never written chart."""
    try:
        from songs.practice_key_state import get_practice_concert_key, resolve_practice_source_pick
        from songs.music_source import custom_progression_is_active, custom_pick_key_for
        from custom_progression_lab import CPL_ACTIVE_KEY

        sticky = ""
        cpl_pk, cpl_orig = _cpl_practice_and_original(session)
        if custom_progression_is_active(session):
            active = session.get(CPL_ACTIVE_KEY)
            custom_pick = ""
            if isinstance(active, dict):
                custom_pick = str(custom_pick_key_for(active) or "").strip()
            if custom_pick.startswith("custom::"):
                sticky = str(get_practice_concert_key(session, custom_pick) or "").strip()
        if not sticky:
            pick = str(resolve_practice_source_pick(session) or "").strip()
            if pick:
                sticky = str(get_practice_concert_key(session, pick) or "").strip()
        # CPL sealed Practice outranks Original-echo by_source (Trial F vs D).
        # Empty session.original_key must not disable this — use CPL Original.
        original = _tok(session.get("original_key") or "") or cpl_orig
        sticky_tok = _tok(sticky)
        if cpl_pk and original and sticky_tok == original and cpl_pk != original:
            sticky_tok = cpl_pk
            sticky = cpl_pk
        elif cpl_pk and not sticky_tok:
            sticky_tok = cpl_pk
            sticky = cpl_pk
        if not sticky_tok:
            return ""
        live_concert = _tok(
            session.get("concert_key")
            or session.get("practice_concert_key")
            or session.get("improv_mission_concert_key")
            or ""
        )
        # Sticky that only echoes Original must lose to live Practice (Trial D/F).
        if original and sticky_tok == original and live_concert and live_concert != sticky_tok:
            if not (_charts_on(session) and live_concert == _written_of(session, sticky_tok)):
                return live_concert
        # Reject sticky that is only the Bb written chart of live concert Practice.
        if live_concert and sticky_tok != live_concert:
            written = _written_of(session, live_concert)
            if written and sticky_tok == written:
                return live_concert
        # Sidebar display Practice outranks Original-echo sticky when charts leave
        # display_key as concert (not written).
        display = _tok(session.get("display_key") or "")
        if original and sticky_tok == original and display and display != sticky_tok:
            hint = live_concert or display
            written_of_hint = _written_of(session, hint) if hint else ""
            if not (written_of_hint and display == written_of_hint and display != hint):
                return display
        return sticky
    except ImportError:
        pass
    return ""


def _live_concert_practice_only(session: dict[str, Any]) -> str:
    """Session concert Practice fields — never written display_key when charts ON."""
    sticky = _sticky_mission_practice(session)
    for key in ("concert_key", "practice_concert_key", "improv_mission_concert_key"):
        raw = _tok(session.get(key) or "")
        if not raw:
            continue
        if _is_written_pollution(session, raw, sticky or ""):
            continue
        return raw
    display = _tok(session.get("display_key") or "")
    if display and not _is_written_pollution(session, display, sticky or ""):
        if _charts_on(session) and sticky and display != _tok(sticky):
            # Charts ON: display_key is ambiguous — do not outrank sticky.
            return ""
        if not _charts_on(session):
            return display
        # Charts ON but no sticky: still reject pure written-looking values vs concert_key.
        concert = _tok(session.get("concert_key") or "")
        if concert and display != concert and display == _written_of(session, concert):
            return ""
        if not concert:
            return ""
        return display
    return ""


def resolve_mission_handoff_concert_practice(
    session: dict[str, Any],
    *,
    concert_practice_key: str = "",
) -> str:
    """Concert Practice for Mission Backing handoff.

    Priority during explicit Mission Backing ownership:
    1. Explicit / click-intent concert Practice
    2. Sealed handoff Practice (if already stamped this launch)
    3. Sticky underlying Trial/catalog Practice
    4. Live concert_* session fields (never written display/chart)
    """
    explicit = _tok(concert_practice_key)
    if explicit and not _is_written_pollution(session, explicit, ""):
        return explicit
    # Live Mission Backing: durable user Practice commit outranks a stale launch seal
    # (F→E must not reseal F when stamp_mission_backing_handoff runs again).
    try:
        if live_backing_owner_is_mission(session):
            from creative_key_sync import _mission_user_commit_token

            user = _tok(_mission_user_commit_token(session) or "")
            if user and not _is_written_pollution(session, user, ""):
                sealed_now = _tok(session.get(HANDOFF_PRACTICE_KEY) or "")
                if not sealed_now or user != sealed_now:
                    return user
    except ImportError:
        pass
    try:
        from music_workflow_mission_backing_click import peek_mission_backing_click_intent

        intent = peek_mission_backing_click_intent(session)
        if intent:
            intent_concert = _tok(intent.get("concert_key") or "")
            if intent_concert and not _is_written_pollution(session, intent_concert, ""):
                return intent_concert
    except ImportError:
        pass
    sealed = _tok(session.get(HANDOFF_PRACTICE_KEY) or "")
    if sealed and not _is_written_pollution(session, sealed, ""):
        return sealed
    sticky = _tok(_sticky_mission_practice(session) or "")
    if sticky:
        return sticky
    live = _live_concert_practice_only(session)
    if live:
        return live
    return ""


@dataclass(frozen=True)
class MissionOwnerContext:
    """Snapshot of the Mission-owned workspace."""

    underlying_pick: str
    underlying_title: str
    mission_pick: str
    section_label: str
    concert_chord: str
    practice_key: str
    written_key: str
    instrument: str
    backing_handoff: str
    return_destination: str


def missions_surface_owns(session: dict[str, Any]) -> bool:
    """True while Creative Missions tab or Mission Backing owns the visit."""
    try:
        from creative_key_sync import mission_owns_left_panel_key

        if mission_owns_left_panel_key(session):
            return True
    except ImportError:
        pass
    page = str(session.get("studio_page") or "").strip().lower()
    tab = str(
        session.get("improv_intelligence_tab")
        or session.get("creative_improv_intelligence_tab")
        or ""
    ).strip()
    if page == "creative" and tab == "Missions":
        return True
    return live_backing_owner_is_mission(session)


def live_backing_owner_is_mission(session: dict[str, Any]) -> bool:
    """Current Backing envelope owner is Mission (not leftover mission flags)."""
    try:
        from backing_owner_envelope import OWNER_MISSION, live_backing_owner

        if live_backing_owner(session) == OWNER_MISSION:
            return True
    except ImportError:
        pass
    try:
        from backing_context import get_backing_context

        ctx = get_backing_context(session)
        if ctx is not None and str(getattr(ctx, "source", "") or "").strip() == MISSION_OWNER:
            return True
    except ImportError:
        pass
    handoff = str(session.get(BACKING_HANDOFF_SOURCE_KEY) or "").strip()
    if handoff == MISSION_OWNER and str(session.get("studio_page") or "").strip().lower() == "backing":
        return True
    return False


def resolve_mission_underlying_practice_key(session: dict[str, Any]) -> str:
    """Practice Key from the underlying active song owner — not Original / Jam / SBI preview.

    Catalog sticky and custom:: sticky both qualify. Stale ``improv_mission_concert_key``
    equal to Original while sticky Practice differs must lose.

    Written / chart keys (Bb Clarinet G for concert F) must never win Practice.
    """
    # Explicit Mission Backing handoff Practice outranks polluted live fields
    # during launch. After open, sticky/user Practice edits outrank a stale seal.
    if mission_backing_handoff_pending(session) or live_backing_owner_is_mission(session):
        sealed = _tok(session.get(HANDOFF_PRACTICE_KEY) or "")
        sticky_now = _tok(_sticky_mission_practice(session) or "")
        original_now = _tok(session.get("original_key") or "")
        if not original_now:
            try:
                from custom_progression_lab import CPL_ACTIVE_KEY

                active = session.get(CPL_ACTIVE_KEY)
                if isinstance(active, dict):
                    original_now = _tok(active.get("original_key_center") or "")
            except ImportError:
                pass
        if sealed and sticky_now and sticky_now != sealed:
            # Original-echo sticky (D) must not beat launch seal Practice (F).
            if original_now and sticky_now == original_now:
                return sealed
            # Disagreeing sticky must not beat a sealed Mission Backing launch unless
            # the pick has an explicit, durable user Practice override — i.e. a real
            # edit made *after* this Mission opened. Without that marker, a Catalog
            # song's untouched pre-Mission sticky (stamp_mission_backing_handoff never
            # writes catalog sticky, only custom::) is indistinguishable from a genuine
            # edit; R2: that untouched residue must not reclaim the Mission's key.
            try:
                from songs.practice_key_state import (
                    catalog_pick_has_user_practice_key_override,
                    resolve_practice_source_pick,
                )

                pick_now = str(resolve_practice_source_pick(session) or "").strip()
                if not (pick_now and catalog_pick_has_user_practice_key_override(session, pick_now)):
                    return sealed
            except ImportError:
                return sealed
            # Genuine post-open Practice Key edit (durable override marker) — sticky wins.
        elif sealed:
            return sealed
        else:
            handoff = resolve_mission_handoff_concert_practice(session)
            if handoff:
                return handoff

    pick = ""
    saved = ""
    try:
        from songs.practice_key_state import get_practice_concert_key, resolve_practice_source_pick
        from songs.music_source import custom_progression_is_active, custom_pick_key_for
        from custom_progression_lab import CPL_ACTIVE_KEY

        # Prefer sticky Practice over a user-commit that merely echoes Original Key
        # (Original Key widget can stamp _pk_user_commit_token=D while sticky is F).
        sticky_before_user = _tok(_sticky_mission_practice(session) or "")

        try:
            from creative_key_sync import _mission_user_commit_token

            user = _tok(_mission_user_commit_token(session) or "")
        except ImportError:
            user = ""
        if user:
            # Written chart must never be treated as a Practice user commit.
            if _is_written_pollution(session, user, sticky_before_user):
                user = ""
            orig_tok = _tok(session.get("original_key") or "")
            if user and sticky_before_user and orig_tok and user == orig_tok and sticky_before_user != user:
                return sticky_before_user
            if user and not (sticky_before_user and orig_tok and user == orig_tok):
                return user
            # else: fall through to sticky / live
        elif sticky_before_user:
            return sticky_before_user

        # Custom Global Active outranks a leftover catalog pick while Missions owns.
        if custom_progression_is_active(session):
            active = session.get(CPL_ACTIVE_KEY)
            custom_pick = ""
            if isinstance(active, dict):
                custom_pick = str(custom_pick_key_for(active) or "").strip()
            if not custom_pick.startswith("custom::"):
                custom_pick = str(session.get("active_catalog_pick_key") or "").strip()
                if not custom_pick.startswith("custom::"):
                    custom_pick = ""
            if custom_pick.startswith("custom::"):
                saved = str(get_practice_concert_key(session, custom_pick) or "").strip()
                if saved:
                    return saved
            # Custom GA: never fall through to leftover catalog Say/Perfect sticky.
            try:
                from source_session_state import resolve_sbi_custom_practice_key

                custom_pk = _tok(resolve_sbi_custom_practice_key(session) or "")
                if custom_pk and not _is_written_pollution(session, custom_pk, sticky_before_user):
                    return custom_pk
            except ImportError:
                pass
            live_custom = _live_concert_practice_only(session)
            if live_custom:
                return live_custom
            # Still Custom GA with no sticky — stop before catalog pick resolution.
            saved = ""
            pick = ""
        else:
            pick = str(resolve_practice_source_pick(session) or "").strip()
            if pick:
                saved = str(get_practice_concert_key(session, pick) or "").strip()
    except ImportError:
        pick = str(session.get("active_catalog_pick_key") or "").strip()
        store = session.get("practice_key_by_source")
        if isinstance(store, dict) and pick:
            saved = str(store.get(pick) or "").strip()

    if saved:
        return saved

    # Live concert Practice only — never written display_key when charts ON.
    live = _live_concert_practice_only(session)
    if live:
        return live

    # Mission Backing sealed concert, then leftover mission token last.
    try:
        from backing_context import get_backing_context

        ctx = get_backing_context(session)
        if ctx is not None and str(getattr(ctx, "source", "") or "").strip() == MISSION_OWNER:
            ctx_key = _tok(getattr(ctx, "concert_key", "") or getattr(ctx, "key", "") or "")
            hint = saved or _tok(_sticky_mission_practice(session) or "")
            if ctx_key and not _is_written_pollution(session, ctx_key, hint):
                return ctx_key
            if ctx_key:
                return ctx_key
    except ImportError:
        pass

    leftover = _tok(session.get("improv_mission_concert_key") or "")
    if leftover and not _is_written_pollution(session, leftover, saved or ""):
        return leftover
    return ""


def resolve_mission_written_key(session: dict[str, Any], practice_key: str = "") -> str:
    """Written Key from Mission Practice Key + instrument (charts ON)."""
    concert = str(practice_key or resolve_mission_underlying_practice_key(session) or "").strip()
    if not concert:
        return ""
    written = _written_of(session, concert)
    return written or concert


def stamp_mission_backing_handoff(
    session: dict[str, Any],
    *,
    concert_practice_key: str = "",
) -> None:
    """Explicit Mission → Backing owner. Outranks leftover entry_jam / SBI / Catalog.

    Seals four distinct key fields — Original, Practice/Concert, Sounding, Written.
    Written / display / chart must never be written into Practice or sounding.
    Opening Mission Backing must not create a new ``_pk_user_commit_token``.
    """
    commit_before = str(session.get("_pk_user_commit_token") or "")
    cpl_pk, cpl_orig = _cpl_practice_and_original(session)
    original = _tok(session.get("original_key") or "") or cpl_orig
    practice = ""
    written = ""
    try:
        practice = resolve_mission_handoff_concert_practice(
            session, concert_practice_key=concert_practice_key
        )
        # Click/live may already be Original-echo D while CPL still seals Trial F.
        if (
            cpl_pk
            and original
            and practice
            and _tok(practice) == original
            and cpl_pk != original
        ):
            practice = cpl_pk
        # Last resort: sticky even if polluted live fields emptied practice.
        if not practice:
            practice = _tok(_sticky_mission_practice(session) or "")
        if not practice:
            practice = _tok(session.get("concert_key") or session.get("practice_concert_key") or "")
            if _is_written_pollution(session, practice, ""):
                practice = ""
        written = resolve_mission_written_key(session, practice) if practice else ""
        if practice and written and _tok(written) == _tok(practice) and _charts_on(session):
            written = _written_of(session, practice) or written
    except Exception as exc:
        _mission_handoff_diag(
            "stamp_mission_backing_handoff_resolve_error",
            {"error": repr(exc), "explicit": _tok(concert_practice_key)},
        )
        practice = _tok(concert_practice_key) or _tok(_sticky_mission_practice(session) or "") or practice
        written = _tok(written) or practice

    _mission_handoff_diag(
        "stamp_mission_backing_handoff_before_seal",
        {
            "original": original,
            "practice_resolved": practice,
            "written_resolved": written,
            "explicit_concert": _tok(concert_practice_key),
            "display_key": _tok(session.get("display_key") or ""),
            "concert_key": _tok(session.get("concert_key") or ""),
            "sticky": _tok(_sticky_mission_practice(session) or ""),
            "improv_mission_concert_key": _tok(session.get("improv_mission_concert_key") or ""),
            "pk_commit_before": commit_before,
            "pick": _tok(session.get("active_catalog_pick_key") or ""),
        },
    )

    if practice:
        # Seal explicit envelope — distinct fields, no overloaded generic key.
        session[HANDOFF_ORIGINAL_KEY] = original
        session[HANDOFF_PRACTICE_KEY] = practice
        session[HANDOFF_SOUNDING_KEY] = practice
        session[HANDOFF_WRITTEN_KEY] = written or practice
        session["improv_mission_concert_key"] = practice
        session["concert_key"] = practice
        # Practice widget / sounding identity stays concert; written is chart-only.
        # Do not assign written G into display_key here — Backing chart path owns that.
        try:
            from songs.practice_key_state import (
                get_practice_concert_key,
                resolve_practice_source_pick,
                set_practice_concert_key,
            )

            pick = str(resolve_practice_source_pick(session) or "").strip()
            if pick.startswith("custom::"):
                saved = _tok(get_practice_concert_key(session, pick) or "")
                # Seal sticky from concert Practice when missing, Original-echo,
                # or written-chart pollution (Bb G for concert F).
                polluted = bool(
                    saved
                    and practice
                    and saved != practice
                    and _is_written_pollution(session, saved, practice)
                )
                if (
                    not saved
                    or (original and saved == original and practice != original)
                    or polluted
                ):
                    set_practice_concert_key(
                        session,
                        practice,
                        pick_key=pick,
                        allow_restore_original=True,
                    )
        except Exception:
            pass

    # Always stamp owner flags — even if key seal failed — so navigation proceeds.
    session["improv_mission_backing_handoff"] = True
    session[BACKING_HANDOFF_SOURCE_KEY] = MISSION_OWNER
    session[MISSION_RETURN_DESTINATION_KEY] = "mission"
    session.pop("_backing_released_specialized_context", None)
    # Leftover Jam / SBI entry must not steal the open-backing classifier.
    try:
        from creative_source_ownership_contract import stamp_explicit_backing_handoff

        stamp_explicit_backing_handoff(session, MISSION_OWNER)
    except ImportError:
        session["_backing_explicit_handoff_epoch"] = int(session.get("_backing_explicit_handoff_epoch") or 0) + 1

    # Slice 4 — seal Mission owner envelope early (before open_backing rebuild).
    try:
        from backing_owner_envelope import OWNER_MISSION, stamp_backing_owner_envelope

        owner = resolve_mission_owner_context(session)
        pick = _tok(owner.underlying_pick or session.get("active_catalog_pick_key") or "")
        title = _tok(owner.underlying_title or "") or _tok(
            session.get("song") or session.get("active_song_title") or ""
        )
        stamp_backing_owner_envelope(
            session,
            source=OWNER_MISSION,
            identity=pick,
            title=title or "Mission",
            original_key=original,
            practice_key=practice or _tok(owner.practice_key or ""),
            sounding_key=practice or _tok(owner.practice_key or ""),
            written_key=written or practice or _tok(owner.written_key or ""),
            instrument=_tok(owner.instrument or session.get("instrument") or ""),
            return_destination=OWNER_MISSION,
        )
    except ImportError:
        pass

    commit_after = str(session.get("_pk_user_commit_token") or "")
    _mission_handoff_diag(
        "stamp_mission_backing_handoff_after_seal",
        {
            "original": session.get(HANDOFF_ORIGINAL_KEY),
            "practice": session.get(HANDOFF_PRACTICE_KEY),
            "sounding": session.get(HANDOFF_SOUNDING_KEY),
            "written": session.get(HANDOFF_WRITTEN_KEY),
            "improv_mission_concert_key": session.get("improv_mission_concert_key"),
            "concert_key": session.get("concert_key"),
            "display_key": session.get("display_key"),
            "pk_commit_before": commit_before,
            "pk_commit_after": commit_after,
            "false_pk_commit": commit_before != commit_after,
        },
    )


def mission_backing_handoff_pending(session: dict[str, Any]) -> bool:
    """True when a fresh Mission Backing launch is in flight."""
    if bool(session.get("improv_mission_backing_handoff")):
        return True
    if str(session.get(BACKING_HANDOFF_SOURCE_KEY) or "").strip() == MISSION_OWNER:
        # Only while leaving Creative or already on Backing with Mission owner.
        page = str(session.get("studio_page") or "").strip().lower()
        if page in {"creative", "backing"}:
            return True
    try:
        from music_workflow_mission_backing_click import peek_mission_backing_click_intent

        if peek_mission_backing_click_intent(session):
            return True
    except ImportError:
        pass
    return False


def return_to_mission_eligible(session: dict[str, Any]) -> bool:
    """Return to Mission only while current Backing owner is Mission."""
    return live_backing_owner_is_mission(session)


def clear_mission_return_eligibility(session: dict[str, Any]) -> None:
    """Drop Mission return destination after leave / non-Mission backing."""
    session.pop(MISSION_RETURN_DESTINATION_KEY, None)
    if str(session.get(BACKING_HANDOFF_SOURCE_KEY) or "").strip() == MISSION_OWNER:
        session.pop(BACKING_HANDOFF_SOURCE_KEY, None)
    session.pop("improv_mission_backing_handoff", None)
    session.pop(HANDOFF_ORIGINAL_KEY, None)
    session.pop(HANDOFF_PRACTICE_KEY, None)
    session.pop(HANDOFF_SOUNDING_KEY, None)
    session.pop(HANDOFF_WRITTEN_KEY, None)


def resolve_mission_owner_context(session: dict[str, Any]) -> MissionOwnerContext:
    """One explicit Mission context for UI / handoff / tests."""
    practice = resolve_mission_underlying_practice_key(session)
    written = resolve_mission_written_key(session, practice)
    pick = ""
    title = ""
    try:
        from songs.practice_key_state import resolve_practice_source_pick
        from songs.music_source import custom_progression_is_active, custom_pick_key_for
        from custom_progression_lab import CPL_ACTIVE_KEY

        if custom_progression_is_active(session):
            active = session.get(CPL_ACTIVE_KEY)
            if isinstance(active, dict):
                pick = str(custom_pick_key_for(active) or "").strip()
                title = str(active.get("name") or active.get("title") or "").strip()
        if not pick:
            pick = str(resolve_practice_source_pick(session) or "").strip()
    except ImportError:
        pick = str(session.get("active_catalog_pick_key") or "").strip()
    if not title:
        sel = session.get("selected_song") if isinstance(session.get("selected_song"), dict) else {}
        title = str(
            (sel or {}).get("title")
            or session.get("song")
            or session.get("active_song_title")
            or ""
        ).strip()
    chord = str(
        session.get("improv_selected_chord")
        or session.get("improv_mission_selected_chord")
        or ""
    ).strip()
    section = str(session.get("improv_selected_section") or "Progression").strip()
    mission = str(
        session.get("improv_mission_pick") or session.get("improv_active_mission") or ""
    ).strip()
    return MissionOwnerContext(
        underlying_pick=pick,
        underlying_title=title,
        mission_pick=mission,
        section_label=section,
        concert_chord=chord,
        practice_key=practice,
        written_key=written,
        instrument=str(session.get("instrument") or "").strip(),
        backing_handoff=str(session.get(BACKING_HANDOFF_SOURCE_KEY) or "").strip(),
        return_destination=str(session.get(MISSION_RETURN_DESTINATION_KEY) or "").strip(),
    )


__all__ = (
    "MISSION_OWNER",
    "BACKING_HANDOFF_SOURCE_KEY",
    "MISSION_RETURN_DESTINATION_KEY",
    "HANDOFF_ORIGINAL_KEY",
    "HANDOFF_PRACTICE_KEY",
    "HANDOFF_SOUNDING_KEY",
    "HANDOFF_WRITTEN_KEY",
    "MissionOwnerContext",
    "missions_surface_owns",
    "live_backing_owner_is_mission",
    "resolve_mission_handoff_concert_practice",
    "resolve_mission_underlying_practice_key",
    "resolve_mission_written_key",
    "stamp_mission_backing_handoff",
    "mission_backing_handoff_pending",
    "return_to_mission_eligible",
    "clear_mission_return_eligibility",
    "resolve_mission_owner_context",
)
