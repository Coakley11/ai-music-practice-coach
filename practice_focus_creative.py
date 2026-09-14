"""Bind global Practice Focus to the current Creative source/workflow.

Practice Focus remains the musician-wide coaching selector
(``practice_setup_globals.focus``). Creative pages consume it as a bias
against the **current** Catalog / Custom / Composition / Mission / Jam
identity. They must not reuse a previous owner's song-card prose.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from practice_focus_context import PracticeFocusContext, resolve_practice_focus_context
from practice_setup_globals import get_active_focus


def _session_map(session: Any) -> Any:
    """Accept Streamlit SessionState as well as plain dicts.

    ``isinstance(st.session_state, dict)`` is False. Treating that as empty
    made Creative captions fall back to Piano / Voicings / Catalog song
    while the Focus widgets still showed the live selector.
    """
    if session is None:
        return {}
    if isinstance(session, Mapping):
        return session
    if hasattr(session, "get") and hasattr(session, "__getitem__"):
        return session
    return {}


def resolve_creative_source_binding(session: dict[str, Any] | None) -> dict[str, str]:
    """Current page's coaching owner — not a leftover preview or Global Active Songs pick."""
    ss = _session_map(session)
    entry = str(ss.get("improv_entry_mode") or "").strip()
    tab = str(ss.get("improv_intelligence_tab") or "").strip()
    page = str(ss.get("studio_page") or "").strip().lower()

    if page == "backing":
        try:
            from backing_context import get_backing_context

            bctx = get_backing_context(ss)
        except ImportError:
            bctx = None
        src = str(getattr(bctx, "source", "") or "").strip() if bctx is not None else ""
        if src == "entry_jam":
            jam_entry = str(getattr(bctx, "entry_mode", "") or entry).strip()
            if jam_entry == "Jam Session Generator":
                return {
                    "kind": "jam_generator",
                    "workflow": "Jam Generator Backing",
                    "identity": "Jam Session Generator",
                }
            return {
                "kind": "entry_jam",
                "workflow": "Style Jam Backing",
                "identity": "Entry Style Jam",
            }
        if src == "song_improv":
            kind = "catalog"
            try:
                from source_session_state import resolve_sbi_material_kind

                kind = str(resolve_sbi_material_kind(ss, ctx=bctx) or "catalog").strip().lower()
            except ImportError:
                kind = str(getattr(bctx, "sbi_material_kind", "") or "catalog").strip().lower()
            identity = str(getattr(bctx, "song_title", "") or "").strip()
            if kind == "custom":
                identity = identity or _custom_identity(ss)
                return {"kind": "custom", "workflow": "SBI Custom Backing", "identity": identity}
            if kind == "composition":
                identity = identity or _composition_identity(ss)
                return {
                    "kind": "composition",
                    "workflow": "SBI Composition Backing",
                    "identity": identity,
                }
            identity = identity or _catalog_identity(ss)
            return {"kind": "catalog", "workflow": "SBI Catalog Backing", "identity": identity}
        if src == "mission":
            return {
                "kind": "mission",
                "workflow": "Mission Backing",
                "identity": str(getattr(bctx, "song_title", "") or "Mission").strip(),
            }

    if entry == "Style Jam Mode":
        identity = str(ss.get("improv_style") or "Style Jam").strip() or "Style Jam"
        return {
            "kind": "entry_jam",
            "workflow": "Style Jam",
            "identity": identity,
        }
    if entry == "Jam Session Generator":
        identity = str(
            ss.get("improv_jam_style") or ss.get("improv_ensemble") or "Jam"
        ).strip() or "Jam"
        return {
            "kind": "jam_generator",
            "workflow": "Jam Generator",
            "identity": identity,
        }

    kind = "catalog"
    preview = ""
    try:
        from source_session_state import get_sbi_preview_source, resolve_sbi_material_kind

        preview = str(get_sbi_preview_source(ss) or "").strip()
        kind = str(resolve_sbi_material_kind(ss, owner=preview) or "catalog").strip().lower() or "catalog"
    except ImportError:
        kind = "catalog"

    if kind == "custom" and preview == "Custom progression":
        identity = _custom_identity(ss)
        workflow = "SBI Custom" if entry == "Song-Based Improvisation" else "Custom"
        if tab == "Missions":
            workflow = "Missions · Custom"
        return {"kind": "custom", "workflow": workflow, "identity": identity}
    if kind == "composition" and preview == "Composition":
        identity = _composition_identity(ss)
        workflow = "SBI Composition" if entry == "Song-Based Improvisation" else "Composition"
        if tab == "Missions":
            workflow = "Missions · Composition"
        return {"kind": "composition", "workflow": workflow, "identity": identity}

    identity = _catalog_identity(ss)
    workflow = "SBI Catalog" if entry == "Song-Based Improvisation" else "Catalog"
    if tab == "Missions":
        workflow = "Missions · Catalog"
    elif tab == "Harmony Map":
        workflow = "Harmony Map · Catalog"
    return {"kind": "catalog", "workflow": workflow, "identity": identity}


def _custom_identity(session: dict[str, Any]) -> str:
    try:
        from custom_progression_lab import CPL_ACTIVE_KEY, ensure_original_structure

        active = ensure_original_structure(session.get(CPL_ACTIVE_KEY) or {})
        name = str(active.get("name") or "").strip()
        if name:
            return name
    except Exception:
        pass
    return "Custom"


def _composition_identity(session: dict[str, Any]) -> str:
    title = str(session.get("composition_active_title") or "").strip()
    if title:
        return title
    try:
        from composition_songs_bridge import read_active_composition_title

        title = str(read_active_composition_title(session) or "").strip()
        if title:
            return title
    except Exception:
        pass
    return "Composition"


def _catalog_identity(session: dict[str, Any]) -> str:
    selected = session.get("selected_song") if isinstance(session.get("selected_song"), dict) else {}
    title = str((selected or {}).get("title") or session.get("song") or "").strip()
    return title or "Catalog song"


def resolve_creative_practice_focus(session: dict[str, Any] | None) -> dict[str, Any]:
    """Global Focus + current source binding. Coaching only — never source identity."""
    ss = _session_map(session)
    pf: PracticeFocusContext = resolve_practice_focus_context(ss)
    bind = resolve_creative_source_binding(ss)
    emphasis = list(pf.profile.creative_emphasis[:3]) if pf.profile.creative_emphasis else []
    suggestions = list(pf.profile.practice_suggestions[:3]) if pf.profile.practice_suggestions else []
    backing = list(pf.profile.backing_ideas[:2]) if pf.profile.backing_ideas else []
    success = list(pf.profile.evaluation_dimensions[:3]) if pf.profile.evaluation_dimensions else []
    feedback = list(pf.profile.terminology[:4]) if pf.profile.terminology else []
    return {
        "focus": pf.focus or get_active_focus(ss),
        "instrument": pf.instrument_display or pf.instrument,
        "category": pf.category,
        "kind": bind["kind"],
        "workflow": bind["workflow"],
        "identity": bind["identity"],
        "emphasis": emphasis,
        "suggestions": suggestions,
        "backing_ideas": backing,
        "success_criteria": success,
        "feedback_language": feedback,
        "prompt_block": pf.ami_prompt_block,
    }


def format_focus_surface_guidance(session: Any, surface: str) -> str:
    """Surface-specific Practice Focus coaching. Does not change musical identity."""
    ctx = resolve_creative_practice_focus(session)
    focus = str(ctx.get("focus") or "").strip()
    surface_l = str(surface or "").strip().lower()
    if surface_l in {"live_coach", "live"}:
        bits = list(ctx.get("suggestions") or [])[:2]
        extra = list(ctx.get("emphasis") or [])[:1]
        detail = " ".join(str(x) for x in (bits + extra) if str(x).strip())
        return f"{focus} — {detail}".strip(" —") if focus else detail
    if surface_l in {"missions", "mission"}:
        steps = list(ctx.get("suggestions") or [])[:2]
        success = list(ctx.get("success_criteria") or [])[:2]
        line = " ".join(str(x) for x in steps if str(x).strip())
        if success:
            line = f"{line} Success: {', '.join(str(s) for s in success)}.".strip()
        return f"{focus} — {line}".strip(" —") if focus else line
    if surface_l in {"harmony", "harmony_map", "deep_harmony"}:
        bits = list(ctx.get("emphasis") or ctx.get("suggestions") or [])[:2]
        detail = " ".join(str(x) for x in bits if str(x).strip())
        return f"{focus} — {detail}".strip(" —") if focus else detail
    if surface_l in {"motif", "phrase", "phrase / motif"}:
        bits = list(ctx.get("emphasis") or ctx.get("suggestions") or [])[:2]
        detail = " ".join(str(x) for x in bits if str(x).strip())
        return f"{focus} — apply this to the motif without changing key or pitches unless the focus is a designed musical transform.".strip() if not detail else f"{focus} — {detail}"
    if surface_l in {"backing", "backing_suggestions"}:
        bits = list(ctx.get("backing_ideas") or ctx.get("suggestions") or [])[:2]
        detail = " ".join(str(x) for x in bits if str(x).strip())
        return f"{focus} — {detail}".strip(" —") if focus else detail
    if surface_l in {"feedback", "feedback_language"}:
        terms = list(ctx.get("feedback_language") or [])[:4]
        return f"{focus} language: " + ", ".join(str(t) for t in terms if str(t).strip())
    return format_practice_focus_coaching_line(session)


def format_creative_practice_focus_caption(session: dict[str, Any] | None) -> str:
    ctx = resolve_creative_practice_focus(session)
    try:
        from music_feature_icons import feature_label

        head = feature_label("practice_focus", "Practice Focus")
    except ImportError:
        head = "Practice Focus"
    identity = str(ctx.get("identity") or "").strip()
    workflow = str(ctx.get("workflow") or "").strip()
    focus = str(ctx.get("focus") or "").strip() or "—"
    parts = [head, focus]
    if workflow:
        parts.append(workflow)
    if identity:
        parts.append(identity)
    line = " · ".join(parts)
    extra = ""
    emphasis = list(ctx.get("emphasis") or [])
    if emphasis:
        extra = " — " + "; ".join(str(x) for x in emphasis[:2])
    return f"{line}{extra}"


def format_practice_focus_coaching_line(session: Any) -> str:
    """One-line coaching overlay for generated Motif / Mission examples."""
    ctx = resolve_creative_practice_focus(session)
    focus = str(ctx.get("focus") or "").strip()
    suggestions = [str(x).strip() for x in (ctx.get("suggestions") or []) if str(x).strip()]
    emphasis = [str(x).strip() for x in (ctx.get("emphasis") or []) if str(x).strip()]
    detail = (suggestions[0] if suggestions else "") or (emphasis[0] if emphasis else "")
    if focus and detail:
        return f"{focus} — {detail}"
    return focus or detail


def apply_practice_focus_to_generated_motif(motif: dict[str, Any] | None, session: Any) -> dict[str, Any]:
    """Stamp current Practice Focus onto a generated motif without changing identity."""
    out = dict(motif or {})
    ss = _session_map(session)
    if session is None or not ss:
        return out
    try:
        live = str(ss.get("focus") or "").strip()
    except Exception:
        return out
    if not live:
        return out
    ctx = resolve_creative_practice_focus(session)
    focus = str(ctx.get("focus") or live).strip()
    if not focus:
        return out
    out["practice_focus"] = focus
    line = format_practice_focus_coaching_line(session)
    if line:
        prompt = str(out.get("variation_prompt") or "").strip()
        if line not in prompt:
            out["variation_prompt"] = f"{prompt} {line}".strip() if prompt else line
        out["practice_focus_coaching"] = line
    return out


def creative_focus_matches_source(
    session: dict[str, Any] | None,
    *,
    expected_kind: str,
    expected_identity: str = "",
) -> bool:
    bind = resolve_creative_source_binding(session)
    if str(bind.get("kind") or "") != str(expected_kind or "").strip().lower():
        return False
    want = str(expected_identity or "").strip()
    if not want:
        return True
    return str(bind.get("identity") or "").strip() == want
