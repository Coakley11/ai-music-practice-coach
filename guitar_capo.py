"""Guitar capo mode — shape-key charts vs concert/sounding backing audio."""

from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Any

from music_theory import (
    ENHARMONIC_MAJOR_KEYS,
    format_key_label_from_parts,
    key_center_token,
    semitone_distance,
    split_key_center,
    transpose_sections_dict,
)

CAPO_ENABLED_KEY = "guitar_capo_enabled"
CAPO_SOUNDING_KEY = "guitar_capo_sounding_key"
CAPO_SHAPE_KEY = "guitar_capo_shape_key"
CAPO_LAST_CONCERT_KEY = "guitar_capo_last_concert_key"
# Streamlit widget keys — must mirror canonical CAPO_* after restore.
CAPO_ENABLED_WIDGET_KEY = "guitar_capo_enabled_widget"
CAPO_SHAPE_WIDGET_KEY = "guitar_capo_shape_widget"

CAPO_PERSIST_KEYS: tuple[str, ...] = (
    CAPO_ENABLED_KEY,
    CAPO_SOUNDING_KEY,
    CAPO_SHAPE_KEY,
    CAPO_LAST_CONCERT_KEY,
)
# Last source identity the Shape Key control was seeded or committed for.
# Distinguishes a live same-source user pick from a new-source / restore reset.
CAPO_SHAPE_SEED_SOURCE_KEY = "_capo_shape_seed_source_id"
PARKED_CATALOG_GUITAR_SHAPE_KEY = "_parked_catalog_guitar_shape"

_SHAPE_TONIC_CANDIDATES: tuple[str, ...] = (
    "G",
    "E",
    "A",
    "D",
    "C",
    "F",
    "Bb",
    "Eb",
)


def shape_tonic_only(shape_key: str) -> str:
    """Shape Key control value — tonic/root only, never major/minor."""
    tonic, _mode = split_key_center(str(shape_key or "C").strip() or "C")
    return str(tonic or "C").strip() or "C"


def shape_tonic_options(*, selected: str = "") -> list[str]:
    """Tonic-only Shape Key picker (C, D, Eb, F#) — no C major / C minor pairs."""
    pick = shape_tonic_only(selected) if selected else ""
    options = list(ENHARMONIC_MAJOR_KEYS)
    if pick and pick not in options:
        return [pick] + options
    if pick:
        return [pick] + [k for k in options if k != pick]
    return options


def live_capo_shape_widget_key(session_state: dict) -> str:
    """Shape Key widget identity. Bumped on genuine Off so On remounts clean."""
    try:
        gen = int(session_state.get("_capo_shape_widget_gen") or 0)
    except (TypeError, ValueError):
        gen = 0
    if gen <= 0:
        return CAPO_SHAPE_WIDGET_KEY
    return f"{CAPO_SHAPE_WIDGET_KEY}_g{gen}"


def valid_live_shape_widget_tonic(session_state: dict) -> str:
    """Return the Shape Key widget tonic when it is a real user/control value.

    Empty / missing widget is uninitialized. ``shape_tonic_only('')`` would
    otherwise collapse to ``C`` and look like a live pick.
    """
    raw = str(session_state.get(live_capo_shape_widget_key(session_state)) or "").strip()
    if not raw:
        return ""
    tonic = shape_tonic_only(raw)
    if tonic in set(ENHARMONIC_MAJOR_KEYS):
        return tonic
    extras = set(shape_tonic_options(selected=tonic))
    return tonic if tonic in extras else ""


def live_capo_shape_source_id(session_state: dict) -> str:
    """Stable source identity for Shape Key seed vs live-user authority."""
    page = str(session_state.get("studio_page") or "").strip().lower()
    entry = str(session_state.get("improv_entry_mode") or "").strip()
    tab = str(session_state.get("improv_intelligence_tab") or "").strip()
    # Composition UUID owns Capo sounding whenever Composition is the active song —
    # do not let a lagged Catalog pick (Perfect G) win Sounding.
    try:
        from songs.music_source import composition_song_is_active

        if composition_song_is_active(session_state):
            try:
                from composition_session_state import get_active_document
                from composition_songs_bridge import composition_pick_key_for

                doc = get_active_document(session_state) or {}
                pick = composition_pick_key_for(doc) if isinstance(doc, dict) else ""
                if pick.startswith("composition::"):
                    return pick
            except Exception:
                pass
            live_pick = str(session_state.get("active_catalog_pick_key") or "").strip()
            if live_pick.startswith("composition::"):
                return live_pick
    except Exception:
        pass
    # Temporary SBI Custom must own Capo sounding whenever it owns the sidebar
    # Practice Key — not only when the SBI radio tab string matches a short allowlist.
    # Otherwise Perfect's pick-scoped C leaks into Sounding while the Trial card shows F.
    try:
        from source_session_state import custom_sbi_owns_sidebar_practice_key

        if custom_sbi_owns_sidebar_practice_key(session_state):
            custom_id = _custom_guitar_source_id(session_state)
            if custom_id:
                return custom_id
    except Exception:
        pass
    try:
        from backing_context import get_backing_context

        ctx = get_backing_context(session_state)
        src = str(getattr(ctx, "source", "") or "") if ctx is not None else ""
        if page == "backing" and src == "entry_jam":
            jam_entry = str(getattr(ctx, "entry_mode", "") or entry or "entry_jam").strip()
            return f"generated::jam::{jam_entry or 'entry_jam'}"
        if page == "backing" and src in {"custom_progression", "song_improv"}:
            kind = str(getattr(ctx, "sbi_material_kind", "") or "").strip().lower()
            try:
                from source_session_state import resolve_sbi_material_kind

                kind = str(resolve_sbi_material_kind(session_state, ctx=ctx) or kind).strip().lower()
            except Exception:
                pass
            if src == "custom_progression" or kind == "custom":
                custom_id = _custom_guitar_source_id(session_state)
                if custom_id:
                    return custom_id
    except Exception:
        pass
    if page == "custom" or (
        page == "creative"
        and entry == "Song-Based Improvisation"
        and str(session_state.get("sbi_preview_source") or "") == "Custom progression"
        and tab in {"", "Song-Based Improvisation", "Entry & Jam"}
    ):
        custom_id = _custom_guitar_source_id(session_state)
        if custom_id:
            return custom_id
    if entry in {"Style Jam Mode", "Jam Session Generator"} and (
        page in {"backing", "creative", ""} or tab in {"", "Entry & Jam"}
    ):
        return f"generated::jam::{entry}"
    try:
        from creative_key_sync import is_creative_major_jam_active

        if is_creative_major_jam_active(session_state):
            return f"generated::jam::{entry or 'Jam Session Generator'}"
    except Exception:
        pass
    try:
        from active_song_state import gather_active_song_context

        ctx = gather_active_song_context(session_state) or {}
        pick = str(ctx.get("pick_key") or "").strip()
        if pick:
            return pick
        src = str(ctx.get("music_source") or "").strip()
        title = str(ctx.get("custom_progression_name") or "").strip()
        if src or title:
            return f"{src}:{title}"
    except Exception:
        pass
    return str(
        session_state.get("active_catalog_pick_key") or session_state.get("song") or ""
    ).strip()


def _custom_guitar_source_id(session_state: dict) -> str:
    try:
        from custom_progression_lab import CPL_ACTIVE_KEY
        from songs.music_source import custom_pick_key_for

        active = session_state.get(CPL_ACTIVE_KEY) or {}
        pick = str(custom_pick_key_for(active) or "").strip()
        if pick.startswith("custom::"):
            return pick
    except Exception:
        pass
    try:
        from creative_source_ownership_contract import resolve_last_custom_snapshot

        snap = resolve_last_custom_snapshot(session_state)
        pick = str(getattr(snap, "source_id", "") or "").strip() if snap else ""
        if pick.startswith("custom::"):
            return pick
    except Exception:
        pass
    return ""


def _non_catalog_guitar_owner(live_id: str) -> bool:
    live = str(live_id or "").strip()
    return live.startswith("generated::jam") or live.startswith("custom::")


def owner_guitar_concert_key(session_state: dict, fallback: str = "C") -> str:
    """Concert/sounding key for the live Guitar owner — never leftover Catalog G."""
    live = str(live_capo_shape_source_id(session_state) or "").strip()
    fb = str(fallback or "C").strip() or "C"
    if live.startswith("generated::jam"):
        try:
            from backing_context import get_backing_context

            ctx = get_backing_context(session_state)
            jam_tok = ""
            try:
                from backing_practice_key_control import jam_generator_authoritative_concert_key

                jam_tok = str(jam_generator_authoritative_concert_key(session_state) or "").strip()
            except Exception:
                jam_tok = ""
            if not jam_tok:
                jam_tok = str(
                    session_state.get("_pending_improv_jam_key")
                    or session_state.get("improv_jam_key")
                    or getattr(ctx, "concert_key", "")
                    or session_state.get("improv_style_key")
                    or ""
                ).strip()
            if jam_tok:
                return jam_tok
        except Exception:
            pass
        jam_tok = str(
            session_state.get("_pending_improv_jam_key")
            or session_state.get("improv_jam_key")
            or session_state.get("improv_style_key")
            or ""
        ).strip()
        if jam_tok:
            return jam_tok
        try:
            from creative_key_sync import creative_entry_concert_key

            tok = str(creative_entry_concert_key(session_state) or "").strip()
            if tok:
                return tok
        except Exception:
            pass
    if live.startswith("custom::"):
        try:
            from songs.practice_key_state import get_practice_concert_key

            saved = str(get_practice_concert_key(session_state, live, default="") or "").strip()
            if saved:
                return saved
        except Exception:
            pass
        try:
            from source_session_state import resolve_sbi_custom_practice_key

            saved = str(resolve_sbi_custom_practice_key(session_state) or "").strip()
            if saved:
                return saved
        except Exception:
            pass
        concert = str(session_state.get("concert_key") or session_state.get("display_key") or "").strip()
        if concert:
            return concert
    # Composition UUID Practice Key before any Catalog leftover (Perfect G).
    composition_pick = ""
    if live.startswith("composition::"):
        composition_pick = live
    else:
        try:
            from songs.music_source import composition_song_is_active

            if composition_song_is_active(session_state):
                composition_pick = str(session_state.get("active_catalog_pick_key") or "").strip()
                if not composition_pick.startswith("composition::"):
                    try:
                        from composition_session_state import get_active_document
                        from composition_songs_bridge import composition_pick_key_for

                        doc = get_active_document(session_state) or {}
                        composition_pick = (
                            composition_pick_key_for(doc) if isinstance(doc, dict) else ""
                        )
                    except Exception:
                        composition_pick = ""
        except Exception:
            composition_pick = ""
    if composition_pick.startswith("composition::") or live.startswith("composition::"):
        try:
            from composition_songs_bridge import (
                find_composition_document,
                resolve_composition_canonical_keys,
            )
            from composition_session_state import get_active_document

            pick_for_doc = composition_pick if composition_pick.startswith("composition::") else live
            doc = find_composition_document(session_state, pick_for_doc)
            if not isinstance(doc, dict):
                doc = get_active_document(session_state) or {}
            if isinstance(doc, dict) and doc:
                _home, saved = resolve_composition_canonical_keys(session_state, doc)
                if saved:
                    return str(saved)
        except Exception:
            pass
    pick = str(session_state.get("active_catalog_pick_key") or "").strip()
    if pick and not pick.startswith("custom::") and not pick.startswith("composition::"):
        try:
            from songs.practice_key_state import get_practice_concert_key

            saved = str(get_practice_concert_key(session_state, pick, default="") or "").strip()
            if saved:
                return saved
        except Exception:
            pass
    return fb


def isolate_jam_from_catalog_guitar_shape(session_state: dict) -> None:
    """Keep Capo Shape Mode sticky across Catalog / Custom / Composition / Jam.

    Shape Mode is user-controlled. Owner transitions must not uncheck it or
    replace the selected shape tonic. Update the seed source id so later
    restores still know which owner is live.
    """
    if session_state.get(CAPO_ENABLED_KEY):
        remember_capo_shape_seed_source(session_state)
        return
    live = str(live_capo_shape_source_id(session_state) or "").strip()
    isolated = _non_catalog_guitar_owner(live)
    if not isolated:
        parked = session_state.get(PARKED_CATALOG_GUITAR_SHAPE_KEY)
        if isinstance(parked, dict) and live and live == str(parked.get("pick") or "").strip():
            session_state[CAPO_ENABLED_KEY] = bool(parked.get("enabled"))
            if parked.get("shape"):
                session_state[CAPO_SHAPE_KEY] = parked.get("shape")
            if parked.get("seed"):
                session_state[CAPO_SHAPE_SEED_SOURCE_KEY] = parked.get("seed")
            session_state.pop(PARKED_CATALOG_GUITAR_SHAPE_KEY, None)
        return
    remember_capo_shape_seed_source(session_state)


def capo_shape_authoritative_reset(session_state: dict) -> bool:
    """True for this-run disk/cloud restore or a different source than last seed.

    Do **not** use ``_capo_on_shape_seeded == false`` or incomplete
    ``_music_restore_phase_complete`` — those stay false on long Songs/SBI
    paths and would destroy a live Shape Key pick.
    """
    if session_state.get("_capo_shape_manual_on_reset"):
        return True
    if session_state.get("_cloud_workspace_restored_this_run"):
        return True
    if session_state.get("_music_disk_restore_this_run"):
        return True
    live = live_capo_shape_source_id(session_state)
    last = str(session_state.get(CAPO_SHAPE_SEED_SOURCE_KEY) or "").strip()
    return bool(live and last and live != last)


def apply_source_change_shape_home(session_state: dict, sounding: str) -> None:
    """On a new source, keep Shape tonic while Shape Mode is on.

    Manual Off releases the sticky tonic. While ON, owner changes only update
    the seed source id so later hydrates do not look like a fresh On event.
    """
    this_run_restore = bool(
        session_state.get("_cloud_workspace_restored_this_run")
        or session_state.get("_music_disk_restore_this_run")
    )
    if this_run_restore:
        return
    live_id = live_capo_shape_source_id(session_state)
    last_id = str(session_state.get(CAPO_SHAPE_SEED_SOURCE_KEY) or "").strip()
    if not (live_id and last_id and live_id != last_id):
        return
    if session_state.get(CAPO_ENABLED_KEY):
        # Shape Mode ON: keep the guitarist's tonic. Mode/capo follow sounding.
        remember_capo_shape_seed_source(session_state)
        return
    session_state.pop("_pending_capo_shape_key", None)
    leftover_widget = valid_live_shape_widget_tonic(session_state)
    canonical = shape_tonic_only(str(session_state.get(CAPO_SHAPE_KEY) or "").strip())
    new_home = shape_tonic_only(sounding)
    meta = session_state.get("active_song_state")
    meta_pick = str(meta.get("pick_key") or "").strip() if isinstance(meta, dict) else ""
    meta_shape = (
        shape_tonic_only(str(meta.get(CAPO_SHAPE_KEY) or "").strip())
        if isinstance(meta, dict)
        else ""
    )
    if meta_pick == live_id and meta_shape and leftover_widget and meta_shape != leftover_widget:
        session_state[CAPO_SHAPE_KEY] = meta_shape
    elif leftover_widget and canonical and leftover_widget != canonical:
        pass
    elif new_home and leftover_widget and leftover_widget != new_home:
        session_state[CAPO_SHAPE_KEY] = new_home
    session_state.pop("_capo_on_shape_seeded", None)


def remember_capo_shape_seed_source(session_state: dict) -> None:
    live = live_capo_shape_source_id(session_state)
    if live:
        session_state[CAPO_SHAPE_SEED_SOURCE_KEY] = live


def promote_live_shape_widget_over_seed(session_state: dict) -> str:
    """Same-source live widget tonic outranks an ordinary initialization seed.

    Returns the promoted tonic, or ``''`` when the widget must not win
    (absent, invalid, uninitialized source, or an authoritative reset).
    """
    tonic = valid_live_shape_widget_tonic(session_state)
    if not tonic:
        return ""
    if capo_shape_authoritative_reset(session_state):
        return ""
    last = str(session_state.get(CAPO_SHAPE_SEED_SOURCE_KEY) or "").strip()
    if not last:
        # Control has not been bound to a source yet — leftover browser C
        # must not beat a restored canonical Shape.
        return ""
    session_state[CAPO_SHAPE_KEY] = tonic
    session_state.pop("_pending_capo_shape_key", None)
    return tonic


def _should_seed_shape_widget_from_canonical(session_state: dict) -> bool:
    """Seed only when uninitialized or an authoritative source/restore reset."""
    if capo_shape_authoritative_reset(session_state):
        return True
    last = str(session_state.get(CAPO_SHAPE_SEED_SOURCE_KEY) or "").strip()
    if not last:
        return True
    return not bool(valid_live_shape_widget_tonic(session_state))


def shape_chart_key_for_concert(concert_key: str, shape_key: str) -> str:
    """Musician-facing chart key: Shape tonic + canonical Practice/Concert mode.

    ``C major + Shape D → D`` (D major). ``F# minor + Shape D → Dm``.
    Does not change concert audio or song mode.
    """
    _tonic, mode = split_key_center(str(concert_key or "C").strip() or "C")
    if mode not in {"major", "minor"}:
        mode = "major"
    return key_center_token(shape_tonic_only(shape_key), mode)


def shape_chart_label_for_concert(concert_key: str, shape_key: str) -> str:
    """Human label for charts, e.g. 'D minor' or 'D major'."""
    token = shape_chart_key_for_concert(concert_key, shape_key)
    tonic, mode = split_key_center(token)
    return format_key_label_from_parts(tonic, mode)


def capo_fret_for_shape(sounding_key: str, shape_key: str) -> int:
    """Fret number so ``shape_key`` grips sound as ``sounding_key``."""
    return semitone_distance(shape_tonic_only(shape_key), sounding_key)


def default_shape_key_for_sounding(sounding_key: str) -> str:
    """Lowest-fret friendly shape tonic (mode is inherited from sounding key)."""
    best_shape = "G"
    best_capo = 99
    for shape in _SHAPE_TONIC_CANDIDATES:
        capo = capo_fret_for_shape(sounding_key, shape)
        if capo < best_capo:
            best_capo = capo
            best_shape = shape
    return best_shape


def capo_fields_from_session(session_state: dict) -> dict[str, Any]:
    """Capo blob fields for active_song_state / cloud persistence."""
    return {
        CAPO_ENABLED_KEY: bool(session_state.get(CAPO_ENABLED_KEY)),
        CAPO_SOUNDING_KEY: str(session_state.get(CAPO_SOUNDING_KEY) or "").strip(),
        CAPO_SHAPE_KEY: str(session_state.get(CAPO_SHAPE_KEY) or "").strip(),
        CAPO_LAST_CONCERT_KEY: str(session_state.get(CAPO_LAST_CONCERT_KEY) or "").strip(),
    }


def apply_capo_context_fields(session_state: dict, ctx: dict[str, Any]) -> None:
    """Hydrate live capo session keys from canonical/cloud context."""
    if CAPO_ENABLED_KEY in ctx:
        session_state[CAPO_ENABLED_KEY] = bool(ctx.get(CAPO_ENABLED_KEY))
    for key in (CAPO_SOUNDING_KEY, CAPO_SHAPE_KEY, CAPO_LAST_CONCERT_KEY):
        if key in ctx:
            val = str(ctx.get(key) or "").strip()
            if val:
                session_state[key] = shape_tonic_only(val) if key == CAPO_SHAPE_KEY else val
    applied_shape = shape_tonic_only(str(session_state.get(CAPO_SHAPE_KEY) or "").strip())
    shape_wkey = live_capo_shape_widget_key(session_state)
    widget_shape = str(session_state.get(shape_wkey) or "").strip()
    # Authoritative reset = this-run disk/cloud restore or a different source.
    # Incomplete ``_music_restore_phase_complete`` must NOT count: it stays
    # false on long Songs/SBI paths and would pop the seed flag every rerun,
    # then overwrite a live Shape Key pick (widget C) with canonical B.
    reset = capo_shape_authoritative_reset(session_state)
    if reset and applied_shape and applied_shape != widget_shape:
        session_state.pop("_capo_on_shape_seeded", None)
        if session_state.get("_capo_widgets_instantiated_this_run"):
            session_state["_pending_capo_shape_key"] = applied_shape
        else:
            session_state[shape_wkey] = applied_shape
    else:
        promote_live_shape_widget_over_seed(session_state)
    sync_capo_widgets_from_canonical(session_state)


def sync_capo_widgets_from_canonical(session_state: dict) -> None:
    """Align Capo Streamlit widget keys with canonical Capo session fields.

    ``checkbox(value=..., key=...)`` ignores ``value`` once ``key`` exists, so a stale
    False widget can overwrite restored ``guitar_capo_enabled=True`` and persist the wipe.

    After Capo sidebar widgets are instantiated in this run, Streamlit rejects further
    writes to those keys — queue a pending hydrate for the next run instead.

    Never queue ``enabled=False`` after instantiate: that pending is applied at the
    start of the next run and stomps a user Capo-ON click before the checkbox renders.
    """
    enabled = bool(session_state.get(CAPO_ENABLED_KEY))
    shape = shape_tonic_only(str(session_state.get(CAPO_SHAPE_KEY) or "").strip())
    live_widget = valid_live_shape_widget_tonic(session_state)
    reset = capo_shape_authoritative_reset(session_state)
    last_source = str(session_state.get(CAPO_SHAPE_SEED_SOURCE_KEY) or "").strip()
    if session_state.get("_capo_widgets_instantiated_this_run"):
        if enabled:
            session_state["_pending_capo_enabled_widget"] = True
        if live_widget and not reset and last_source:
            session_state.pop("_pending_capo_shape_key", None)
        elif shape:
            session_state["_pending_capo_shape_key"] = shape
        return
    prior_enabled_widget = session_state.get(CAPO_ENABLED_WIDGET_KEY)
    session_state[CAPO_ENABLED_WIDGET_KEY] = enabled
    if shape:
        if (
            live_widget
            and live_widget != shape
            and not reset
            and prior_enabled_widget is True
            and last_source
        ):
            return
        session_state[live_capo_shape_widget_key(session_state)] = shape


def capo_written_display_key(session_state: dict) -> str | None:
    """Shape chart key (tonic + concert mode) when capo mode is on (read-only)."""
    if not session_state.get(CAPO_ENABLED_KEY):
        return None
    shape = str(session_state.get(CAPO_SHAPE_KEY) or "").strip()
    if not shape:
        return None
    concert = str(
        session_state.get("display_key")
        or session_state.get("concert_key")
        or session_state.get(CAPO_SOUNDING_KEY)
        or "C"
    ).strip() or "C"
    return shape_chart_key_for_concert(concert, shape)


def sync_capo_written_display_key(session_state: dict) -> None:
    """Deprecated no-op — do not mutate widget-backed ``display_key`` after render.

    Capo shape is derived via ``capo_written_display_key`` and ``resolve_practice_keys``.
    """
    return


def chart_bundle_transpose_key(
    *,
    instrument: str,
    capo_enabled: bool,
    concert_key: str,
    chart_key: str,
) -> str:
    """Key used to transpose catalog sections before capo shape split.

    When guitar capo is on, sections must stay in the *sounding* (practice display)
    key; ``build_capo_context`` applies the shape-key transpose once.
    """
    if str(instrument or "").strip() == "Guitar" and capo_enabled:
        return str(concert_key or chart_key or "C").strip() or "C"
    return str(chart_key or concert_key or "C").strip() or "C"


def sync_capo_from_practice_display_key(
    session_state: dict,
    practice_display_key: str,
) -> str:
    """Mirror Practice / Concert Key into capo sounding key (reference only).

    When Capo Shape Mode is on, Shape Key is player-owned and must survive Practice Key
    changes and browser refresh. When Capo is off, Shape follows sounding for charts.
    """
    sounding = str(practice_display_key or "C").strip() or "C"
    session_state[CAPO_SOUNDING_KEY] = sounding
    last = str(session_state.get(CAPO_LAST_CONCERT_KEY) or "").strip()
    if last != sounding:
        session_state[CAPO_LAST_CONCERT_KEY] = sounding
    session_state.setdefault(CAPO_ENABLED_KEY, False)
    if not session_state.get(CAPO_ENABLED_KEY):
        # Capo off: charts follow sounding. Keep Shape aligned to sounding for display.
        session_state[CAPO_SHAPE_KEY] = shape_tonic_only(sounding)
    elif CAPO_SHAPE_KEY not in session_state or not str(session_state.get(CAPO_SHAPE_KEY) or "").strip():
        session_state[CAPO_SHAPE_KEY] = shape_tonic_only(sounding)
    else:
        # Capo on: never overwrite a user Shape Key from Practice / Concert Key.
        session_state[CAPO_SHAPE_KEY] = shape_tonic_only(str(session_state.get(CAPO_SHAPE_KEY) or ""))
    return sounding


def apply_genuine_shape_mode_user_transition(
    session_state: dict,
    *,
    now_enabled: bool,
    sounding: str,
    this_run_restore: bool = False,
) -> dict[str, bool]:
    """Apply a real Capo Shape Mode checkbox change. Hydrate/rerun is not Off/On.

    Genuine Off releases the sticky tonic and drops the unmounted Shape widget
    leftover so the next On cannot remount C. Genuine On initializes Shape Key
    from the current sounding tonic (open capo).
    """
    prev = session_state.get("_capo_enabled_committed")
    user_clicked = bool(session_state.get("_capo_shape_mode_on_change_this_run")) or bool(
        session_state.get("_capo_shape_mode_user_intent")
    )
    genuine_manual_off = (
        user_clicked and bool(prev) and not now_enabled and not this_run_restore
    )
    genuine_manual_on = (
        user_clicked
        and now_enabled
        and not bool(prev)
        and not this_run_restore
    )
    if genuine_manual_off:
        session_state["_capo_genuine_user_off"] = True
        session_state.pop("_capo_shape_manual_on_reset", None)
        try:
            gen = int(session_state.get("_capo_shape_widget_gen") or 0)
        except (TypeError, ValueError):
            gen = 0
        old_key = live_capo_shape_widget_key(session_state)
        session_state["_capo_shape_widget_gen"] = gen + 1
        session_state.pop(old_key, None)
        session_state.pop(CAPO_SHAPE_WIDGET_KEY, None)
        session_state.pop("_pending_capo_shape_key", None)
        cleared = shape_tonic_only(sounding)
        session_state[CAPO_SHAPE_KEY] = cleared
        meta = session_state.get("active_song_state")
        if isinstance(meta, dict):
            meta[CAPO_ENABLED_KEY] = False
            meta[CAPO_SHAPE_KEY] = cleared
    if genuine_manual_on:
        session_state.pop("_capo_genuine_user_off", None)
        home = shape_tonic_only(sounding)
        session_state[CAPO_SHAPE_KEY] = home
        session_state[live_capo_shape_widget_key(session_state)] = home
        session_state["_pending_capo_shape_key"] = home
        session_state["_capo_shape_manual_on_reset"] = True
        session_state.pop("_capo_on_shape_seeded", None)
    session_state["_capo_enabled_committed"] = now_enabled
    session_state.pop("_capo_shape_mode_on_change_this_run", None)
    session_state.pop("_capo_shape_mode_user_intent", None)
    return {
        "genuine_manual_off": genuine_manual_off,
        "genuine_manual_on": genuine_manual_on,
    }


def persist_capo_to_canonical(session_state: dict) -> bool:
    """Push capo state into active_song_state blob when values changed."""
    try:
        from music_restore_phase import authoritative_restore_in_progress

        # Refresh hydrate can briefly paint Capo off / Shape=C before canonical
        # Capo lands — never persist that wipe over Bb during restore.
        if authoritative_restore_in_progress(session_state):
            return False
    except ImportError:
        pass
    try:
        from active_song_state import (
            ACTIVE_SONG_STATE_KEY,
            gather_active_song_context,
            write_canonical_active_song_blob_only,
        )

        live_capo = capo_fields_from_session(session_state)
        meta = session_state.get(ACTIVE_SONG_STATE_KEY)
        genuine_off = bool(session_state.get("_capo_genuine_user_off")) or (
            str(session_state.get("_capo_shape_mode_user_intent") or "") == "off"
        )
        if (
            isinstance(meta, dict)
            and all(meta.get(k) == live_capo.get(k) for k in live_capo)
            and not genuine_off
        ):
            return False
        # Prefer meta Capo-on Shape over a Capo-off / open-fret live wipe.
        if (
            isinstance(meta, dict)
            and meta.get(CAPO_ENABLED_KEY)
            and str(meta.get(CAPO_SHAPE_KEY) or "").strip()
            and not live_capo.get(CAPO_ENABLED_KEY)
            and not session_state.get("_capo_genuine_user_off")
            and str(session_state.get("_capo_shape_mode_user_intent") or "") != "off"
        ):
            return False
        # Capo is player context — bind Capo fields onto the *live* active identity.
        # Never stamp Capo onto a stale meta pick (e.g. Country Roads) while the
        # sidebar still shows Love Story; that poisons Backing restore PK→A.
        live = gather_active_song_context(session_state)
        live_pick = str(live.get("pick_key") or "").strip()
        meta_pick = (
            str(meta.get("pick_key") or "").strip() if isinstance(meta, dict) else ""
        )
        if live_pick:
            ctx = dict(live)
        elif isinstance(meta, dict) and meta_pick:
            ctx = dict(meta)
        else:
            ctx = dict(live) if live else (dict(meta) if isinstance(meta, dict) else {})
        ctx.update(live_capo)
        write_canonical_active_song_blob_only(
            session_state,
            ctx,
            reason="capo_widget",
            local_edit=True,
        )
        return True
    except ImportError:
        return False


def _seal_temporary_sbi_custom_before_capo_save(session_state: dict) -> None:
    """Keep Capo saves from remounting Active over temporary SBI Custom on disk.

    Capo full-saves can capture a remounted Active radio and wipe Trial on refresh
    while Shape Mode is on. When Custom owns the sidebar Practice Key, seal the
    Custom preview + restore stamp before/after the envelope is gathered.

    Also clear leftover ``_sbi_follow_active_after_explicit_catalog`` (Catalog Perfect
    pick). Persisting that flag with Active remounts is what made C4 refresh land
    Catalog Perfect C/open instead of Trial F/capo 5.
    """
    try:
        from source_session_state import (
            RESTORE_SBI_CUSTOM_SOURCE_KEY,
            SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY,
            SBI_PREVIEW_SOURCE_KEY,
            SBI_SONG_SOURCE_CUSTOM,
            clear_sbi_follow_active_after_explicit_catalog,
            custom_sbi_owns_sidebar_practice_key,
        )

        if not custom_sbi_owns_sidebar_practice_key(session_state):
            # Still seal when Capo live source id is already the Custom UUID.
            live = str(live_capo_shape_source_id(session_state) or "").strip()
            if not live.startswith("custom::"):
                return
        # Direct writes — set_sbi_preview_source may refuse Capo vias after Active leave.
        session_state[SBI_PREVIEW_SOURCE_KEY] = SBI_SONG_SOURCE_CUSTOM
        session_state["improv_song_source"] = SBI_SONG_SOURCE_CUSTOM
        session_state[RESTORE_SBI_CUSTOM_SOURCE_KEY] = True
        session_state["_last_improv_song_source"] = SBI_SONG_SOURCE_CUSTOM
        session_state["_improv_song_source_user_touched"] = True
        try:
            clear_sbi_follow_active_after_explicit_catalog(session_state)
        except Exception:
            session_state.pop(SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY, None)
        try:
            from active_song_transition import mark_temporary_workflow_owner

            mark_temporary_workflow_owner(session_state, "sbi_custom")
        except Exception:
            pass
        blob = session_state.get("creative_workspace_state")
        if not isinstance(blob, dict):
            blob = {}
            session_state["creative_workspace_state"] = blob
        blob[SBI_PREVIEW_SOURCE_KEY] = SBI_SONG_SOURCE_CUSTOM
        blob["improv_song_source"] = SBI_SONG_SOURCE_CUSTOM
        blob[RESTORE_SBI_CUSTOM_SOURCE_KEY] = True
        blob["_last_improv_song_source"] = SBI_SONG_SOURCE_CUSTOM
        blob.pop(SBI_FOLLOW_ACTIVE_AFTER_EXPLICIT_CATALOG_KEY, None)
        try:
            from creative_workspace_persistence import mark_creative_workspace_dirty

            mark_creative_workspace_dirty(session_state)
        except Exception:
            pass
    except Exception:
        pass


def flush_capo_edits_to_cloud(st_module: Any) -> bool:
    """Persist capo canonical blob to cloud after sidebar widgets render.

    ``st_module`` must be the Streamlit module (``st``), not ``st.sidebar``.
    """
    try:
        from active_song_state import clear_active_song_local_edit
        from music_persistent_state import flush_active_song_edits_and_save

        # Sidebar runs before main remounts Active over Trial. Seal Custom first so
        # Capo saves (the only reliable flush while Capo Mode is ON) keep Trial.
        try:
            _seal_temporary_sbi_custom_before_capo_save(st_module.session_state)
        except Exception:
            pass
        ok = bool(flush_active_song_edits_and_save(st_module, reason="capo_widget"))
        if ok:
            clear_active_song_local_edit(st_module.session_state)
            try:
                _seal_temporary_sbi_custom_before_capo_save(st_module.session_state)
            except Exception:
                pass
        return ok
    except ImportError:
        return False


def init_capo_session_state(session_state: dict, *, concert_key: str) -> None:
    """Initialize capo session keys from the current practice display key."""
    try:
        from active_song_state import ACTIVE_SONG_STATE_KEY

        meta = session_state.get(ACTIVE_SONG_STATE_KEY)
        if isinstance(meta, dict) and meta.get(CAPO_ENABLED_KEY):
            apply_capo_context_fields(session_state, meta)
            return
    except ImportError:
        pass
    if session_state.get(CAPO_ENABLED_KEY) and str(session_state.get(CAPO_SHAPE_KEY) or "").strip():
        sync_capo_widgets_from_canonical(session_state)
        return
    sync_capo_from_practice_display_key(session_state, concert_key)
    sync_capo_widgets_from_canonical(session_state)


@dataclass
class CapoContext:
    enabled: bool
    sounding_key: str
    shape_key: str
    capo_fret: int
    sounding_sections: dict[str, list[str]]
    shape_sections: dict[str, list[str]]

    @property
    def capo_label(self) -> str:
        return format_capo_fret(self.capo_fret)


def format_capo_fret(fret: int) -> str:
    if fret <= 0:
        return "open (no capo)"
    n = int(fret)
    if n % 10 == 1 and n % 100 != 11:
        suffix = "st"
    elif n % 10 == 2 and n % 100 != 12:
        suffix = "nd"
    elif n % 10 == 3 and n % 100 != 13:
        suffix = "rd"
    else:
        suffix = "th"
    return f"{n}{suffix} fret"


def build_capo_context(
    session_state: dict,
    sections: dict[str, list[str]],
    *,
    concert_key: str,
    instrument: str,
) -> CapoContext:
    """Split chart (shape) vs backing (sounding) sections for guitar capo mode."""
    init_capo_session_state(session_state, concert_key=concert_key)
    if instrument != "Guitar" or not session_state.get(CAPO_ENABLED_KEY):
        return CapoContext(
            enabled=False,
            sounding_key=concert_key,
            shape_key=concert_key,
            capo_fret=0,
            sounding_sections=sections,
            shape_sections=sections,
        )

    sounding_key = str(session_state.get(CAPO_SOUNDING_KEY, concert_key))
    shape_tonic = shape_tonic_only(
        str(
            session_state.get(
                CAPO_SHAPE_KEY,
                default_shape_key_for_sounding(sounding_key),
            )
        )
    )
    session_state[CAPO_SHAPE_KEY] = shape_tonic
    shape_key = shape_chart_key_for_concert(concert_key or sounding_key, shape_tonic)
    if sounding_key != concert_key:
        sounding_sections = transpose_sections_dict(sections, concert_key, sounding_key)
    else:
        sounding_sections = sections
    shape_sections = transpose_sections_dict(
        sounding_sections,
        sounding_key,
        shape_key,
    )
    capo = capo_fret_for_shape(sounding_key, shape_key)
    return CapoContext(
        enabled=True,
        sounding_key=sounding_key,
        shape_key=shape_key,
        capo_fret=capo,
        sounding_sections=sounding_sections,
        shape_sections=shape_sections,
    )


def capo_status_banner_html(ctx: CapoContext) -> str:
    if not ctx.enabled:
        return ""
    capo_line = ctx.capo_label
    return (
        '<div class="ui-card soft" style="margin:0.75rem 0;border-left:4px solid #f59e0b;">'
        '<p class="ui-card-title">🎸 Capo shape mode</p>'
        f'<p class="ui-card-sub"><strong>Actual sounding key:</strong> {html.escape(ctx.sounding_key)} · '
        f"<strong>Guitar shape key:</strong> {html.escape(shape_tonic_only(ctx.shape_key))} · "
        f"<strong>Capo:</strong> {html.escape(capo_line)}</p>"
        f'<p class="ui-card-sub"><strong>Backing track plays in:</strong> {html.escape(ctx.sounding_key)} '
        f"(concert / sounding) · <strong>Charts in:</strong> "
        f"{html.escape(shape_chart_label_for_concert(ctx.sounding_key, ctx.shape_key))}</p>"
        "<p class=\"ui-card-sub\" style=\"font-size:0.82rem;color:#64748b;\">"
        "Capo mode is not global transpose — use <em>Practice / Concert Key</em> in the sidebar "
        "to move the whole song.</p></div>"
    )


def render_guitar_capo_sidebar(
    ui: Any,
    session_state: dict,
    *,
    practice_display_key: str,
    persist_st: Any,
) -> None:
    """Compact capo controls in the sidebar (guitar only)."""
    isolate_jam_from_catalog_guitar_shape(session_state)
    sounding_src = owner_guitar_concert_key(
        session_state,
        fallback=str(practice_display_key or "C").strip() or "C",
    )
    sounding = sync_capo_from_practice_display_key(session_state, sounding_src)
    ui.markdown(
        f'<p class="ui-sidebar-key-caption"><strong>Sounding Key:</strong> '
        f"{html.escape(sounding)}</p>",
        unsafe_allow_html=True,
    )
    # New run: widgets not yet created. Apply any deferred sync from last flush.
    session_state["_capo_widgets_instantiated_this_run"] = False
    genuine_off_pending = bool(session_state.get("_capo_genuine_user_off")) or (
        str(session_state.get("_capo_shape_mode_user_intent") or "") == "off"
    )
    if genuine_off_pending:
        # Stale Capo-ON remount metadata must not beat a genuine manual Off.
        session_state.pop("_pending_capo_enabled_widget", None)
        session_state[CAPO_ENABLED_WIDGET_KEY] = False
        session_state[CAPO_ENABLED_KEY] = False
    elif "_pending_capo_enabled_widget" in session_state:
        session_state[CAPO_ENABLED_WIDGET_KEY] = bool(
            session_state.pop("_pending_capo_enabled_widget")
        )
    # Seed widget keys from canonical before render (never pass value= with key=).
    # After refresh, Capo canonical is restored before this sidebar runs — widgets
    # must match that player context before Streamlit instantiates them.
    if CAPO_ENABLED_WIDGET_KEY not in session_state:
        session_state[CAPO_ENABLED_WIDGET_KEY] = bool(session_state.get(CAPO_ENABLED_KEY))
    apply_source_change_shape_home(session_state, sounding)
    if bool(session_state.get(CAPO_ENABLED_KEY)):
        shape_seed = shape_tonic_only(str(session_state.get(CAPO_SHAPE_KEY) or "").strip())
        if shape_seed and _should_seed_shape_widget_from_canonical(session_state):
            session_state[live_capo_shape_widget_key(session_state)] = shape_seed
    try:
        from capo_refresh_trace import note_capo_refresh

        note_capo_refresh(session_state, phase="before_capo_checkbox")
    except Exception:
        pass

    def _on_capo_shape_mode_user_change() -> None:
        session_state["_capo_shape_mode_on_change_this_run"] = True
        enabled_now = bool(session_state.get(CAPO_ENABLED_WIDGET_KEY))
        session_state["_capo_shape_mode_user_intent"] = "on" if enabled_now else "off"
        if not enabled_now:
            session_state["_capo_genuine_user_off"] = True
            session_state[CAPO_ENABLED_KEY] = False
            session_state["_capo_enabled_committed"] = False
            session_state.pop("_pending_capo_enabled_widget", None)
            meta = session_state.get("active_song_state")
            if isinstance(meta, dict):
                meta[CAPO_ENABLED_KEY] = False
                cleared = shape_tonic_only(
                    str(session_state.get(CAPO_SOUNDING_KEY) or sounding or "C")
                )
                meta[CAPO_SHAPE_KEY] = cleared
                session_state[CAPO_SHAPE_KEY] = cleared
            persist_capo_to_canonical(session_state)
            try:
                from source_session_state import custom_sbi_owns_sidebar_practice_key
                from music_persistent_state import force_save_music_state

                if custom_sbi_owns_sidebar_practice_key(session_state):
                    _seal_temporary_sbi_custom_before_capo_save(session_state)
                else:
                    force_save_music_state(persist_st, reason="capo_shape_mode_off")
            except Exception:
                flush_capo_edits_to_cloud(persist_st)
        else:
            session_state.pop("_capo_genuine_user_off", None)

    session_state[CAPO_ENABLED_KEY] = ui.checkbox(
        "Capo Shape Mode",
        key=CAPO_ENABLED_WIDGET_KEY,
        help="Charts/TAB use grip shapes; backing audio stays in the sounding key.",
        on_change=_on_capo_shape_mode_user_change,
    )
    session_state["_capo_widgets_instantiated_this_run"] = True
    this_run_restore = bool(
        session_state.get("_cloud_workspace_restored_this_run")
        or session_state.get("_music_disk_restore_this_run")
    )
    now_enabled = bool(session_state.get(CAPO_ENABLED_KEY))
    transition = apply_genuine_shape_mode_user_transition(
        session_state,
        now_enabled=now_enabled,
        sounding=sounding,
        this_run_restore=this_run_restore,
    )
    genuine_manual_off = bool(transition.get("genuine_manual_off"))
    genuine_manual_on = bool(transition.get("genuine_manual_on"))
    if not session_state.get(CAPO_ENABLED_KEY):
        # Widget Capo-off must not wipe player Capo when canonical meta still has
        # Capo ON + Shape (refresh race before widget seed lands).
        meta = session_state.get("active_song_state")
        meta_on = (
            isinstance(meta, dict)
            and bool(meta.get(CAPO_ENABLED_KEY))
            and str(meta.get(CAPO_SHAPE_KEY) or "").strip()
        )
        live_id = str(live_capo_shape_source_id(session_state) or "")
        foreign_catalog_meta = False
        if isinstance(meta, dict):
            meta_pick = str(meta.get("pick_key") or "").strip()
            if meta_pick and live_id and meta_pick != live_id and _non_catalog_guitar_owner(live_id):
                foreign_catalog_meta = True
        if (
            meta_on
            and not genuine_manual_off
            and str(session_state.get("_capo_shape_mode_user_intent") or "") != "off"
            and not session_state.get("_capo_genuine_user_off")
            and session_state.get("_capo_enabled_committed") is not False
            and not _non_catalog_guitar_owner(live_id)
            and not foreign_catalog_meta
        ):
            try:
                from capo_refresh_trace import note_capo_refresh

                note_capo_refresh(
                    session_state,
                    phase="capo_off_blocked_meta_still_on",
                    reason="preserve_canonical_shape",
                )
            except Exception:
                pass
            apply_capo_context_fields(session_state, meta if isinstance(meta, dict) else {})
            session_state["_pending_capo_enabled_widget"] = True
            session_state.pop("_capo_on_shape_seeded", None)
            session_state.pop(CAPO_SHAPE_SEED_SOURCE_KEY, None)
            # Show canonical Capo this frame; next run checkbox seeds ON.
            shape_now = shape_tonic_only(str(session_state.get(CAPO_SHAPE_KEY) or ""))
            chart_label = shape_chart_label_for_concert(sounding, shape_now)
            capo = capo_fret_for_shape(sounding, shape_now)
            ui.markdown(
                f'<p class="ui-sidebar-key-caption"><strong>Shape Key:</strong> '
                f"{html.escape(shape_now)} "
                f"<span style=\"opacity:.75\">(restoring Capo Shape Mode…)</span></p>",
                unsafe_allow_html=True,
            )
            ui.markdown(
                f'<p class="ui-sidebar-key-caption"><strong>Charts in</strong> '
                f"{html.escape(chart_label)}</p>",
                unsafe_allow_html=True,
            )
            ui.markdown(
                f'<p class="ui-sidebar-key-caption"><strong>Capo Fret:</strong> {capo}</p>',
                unsafe_allow_html=True,
            )
            try:
                persist_st.rerun()
            except Exception:
                pass
            return

        session_state[CAPO_SHAPE_KEY] = shape_tonic_only(sounding)
        # Capo-off clears the one-shot Shape seed so the next Capo-ON re-seeds
        # from canonical (refresh / restore) without stomping later user picks.
        session_state.pop("_capo_on_shape_seeded", None)
        session_state.pop(CAPO_SHAPE_SEED_SOURCE_KEY, None)
        # Do not sync_capo_widgets_from_canonical here. Widgets already show Capo off;
        # queuing ``_pending_capo_enabled_widget=False`` after instantiate stomps the
        # next user Capo-ON click (widget key rewritten before the checkbox renders).
        ui.markdown(
            f'<p class="ui-sidebar-key-caption"><strong>Shape Key:</strong> '
            f"{html.escape(shape_tonic_only(sounding))} "
            f"<span style=\"opacity:.75\">(follows sounding while Capo is off)</span></p>",
            unsafe_allow_html=True,
        )
        ui.markdown(
            '<p class="ui-sidebar-key-caption"><strong>Capo Fret:</strong> open (no capo)</p>',
            unsafe_allow_html=True,
        )
        if persist_capo_to_canonical(session_state) or genuine_manual_off or session_state.get(
            "_capo_genuine_user_off"
        ):
            flush_capo_edits_to_cloud(persist_st)
            if genuine_manual_off or session_state.get("_capo_genuine_user_off"):
                try:
                    from source_session_state import custom_sbi_owns_sidebar_practice_key
                    from music_persistent_state import force_save_music_state

                    if custom_sbi_owns_sidebar_practice_key(session_state):
                        _seal_temporary_sbi_custom_before_capo_save(session_state)
                    else:
                        force_save_music_state(persist_st, reason="capo_shape_mode_off")
                except Exception:
                    pass
        return

    try:
        from creative_key_sync import flush_pending_creative_major_keys
    except ImportError:
        flush_pending_creative_major_keys = lambda _s: None  # type: ignore
    this_run_restore = bool(
        session_state.get("_cloud_workspace_restored_this_run")
        or session_state.get("_music_disk_restore_this_run")
    )
    live_id = live_capo_shape_source_id(session_state)
    last_id = str(session_state.get(CAPO_SHAPE_SEED_SOURCE_KEY) or "").strip()
    source_changed = bool(live_id and last_id and live_id != last_id)
    if source_changed and not this_run_restore:
        session_state.pop("_pending_capo_shape_key", None)
    flush_pending_creative_major_keys(session_state)
    # Live same-source widget (e.g. user just picked C) outranks pending/canonical
    # seed (e.g. B) before the selectbox is instantiated.
    live_user = "" if genuine_manual_on else promote_live_shape_widget_over_seed(session_state)
    pending_shape = str(session_state.get("_pending_capo_shape_key") or "").strip()
    if genuine_manual_on:
        pending_shape = shape_tonic_only(sounding)
        session_state.pop("_pending_capo_shape_key", None)
        session_state[CAPO_SHAPE_KEY] = pending_shape
        session_state[live_capo_shape_widget_key(session_state)] = pending_shape
    elif live_user:
        pending_shape = ""
        session_state.pop("_pending_capo_shape_key", None)
    elif pending_shape and source_changed and not this_run_restore:
        pending_shape = ""
        session_state.pop("_pending_capo_shape_key", None)
    elif pending_shape:
        session_state[CAPO_SHAPE_KEY] = shape_tonic_only(pending_shape)
        session_state.pop("_pending_capo_shape_key", None)
    cur_shape = shape_tonic_only(
        str(session_state.get(CAPO_SHAPE_KEY) or default_shape_key_for_sounding(sounding))
    )
    shape_opts = shape_tonic_options(selected=cur_shape)
    shape_wkey = live_capo_shape_widget_key(session_state)
    widget_shape = str(session_state.get(shape_wkey) or "").strip()
    # Seed is initialization / source-restore only. A valid live widget tonic
    # must not be overwritten merely because ``_capo_on_shape_seeded`` is false.
    seed_will_write = False
    if _should_seed_shape_widget_from_canonical(session_state):
        if cur_shape and (not widget_shape or widget_shape not in shape_opts or widget_shape != cur_shape):
            session_state[shape_wkey] = cur_shape
            seed_will_write = True
    elif widget_shape and widget_shape not in shape_opts:
        session_state[shape_wkey] = cur_shape
        seed_will_write = True
    _shape_trace = str(__import__("os").environ.get("CAPO_SHAPE_TRACE") or "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    if _shape_trace:
        try:
            from capo_refresh_trace import note_capo_refresh

            note_capo_refresh(
                session_state,
                phase="shape_select_pre",
                widget_before=widget_shape,
                cur_shape=cur_shape,
                pending_shape=pending_shape,
                seed_shape=False,
                live_user_promoted=str(live_user or ""),
                authoritative_reset=capo_shape_authoritative_reset(session_state),
                seed_will_write=seed_will_write,
                seeded_flag=bool(session_state.get("_capo_on_shape_seeded")),
            )
        except Exception:
            pass
    session_state[CAPO_SHAPE_KEY] = ui.selectbox(
        "Shape Key",
        shape_opts,
        key=shape_wkey,
        help="Tonic/root only. Charts inherit major/minor from Practice / Concert Key.",
    )
    _selectbox_return = session_state.get(CAPO_SHAPE_KEY)
    session_state[CAPO_SHAPE_KEY] = shape_tonic_only(str(session_state.get(CAPO_SHAPE_KEY) or cur_shape))
    session_state["_capo_on_shape_seeded"] = True
    remember_capo_shape_seed_source(session_state)
    session_state.pop("_capo_shape_manual_on_reset", None)
    if _shape_trace:
        try:
            from capo_refresh_trace import note_capo_refresh

            note_capo_refresh(
                session_state,
                phase="shape_select_post",
                selectbox_return=str(_selectbox_return or ""),
                canonical_after=str(session_state.get(CAPO_SHAPE_KEY) or ""),
                widget_after=str(session_state.get(shape_wkey) or ""),
            )
        except Exception:
            pass
    ui.markdown(
        f'<p class="ui-sidebar-key-caption"><strong>Shape Key:</strong> '
        f"{html.escape(str(session_state.get(CAPO_SHAPE_KEY) or ''))}</p>",
        unsafe_allow_html=True,
    )
    chart_label = shape_chart_label_for_concert(sounding, session_state[CAPO_SHAPE_KEY])
    ui.markdown(
        f'<p class="ui-sidebar-key-caption"><strong>Charts in</strong> {html.escape(chart_label)}</p>',
        unsafe_allow_html=True,
    )
    capo = capo_fret_for_shape(sounding, session_state[CAPO_SHAPE_KEY])
    ui.markdown(
        f'<p class="ui-sidebar-key-caption"><strong>Capo Fret:</strong> {capo}</p>',
        unsafe_allow_html=True,
    )
    # While temporary SBI Custom owns Capo sounding, Capo Mode ON must still
    # flush — Capo saves are the durable write path and must seal Trial first.
    try:
        from source_session_state import custom_sbi_owns_sidebar_practice_key

        owns_custom = bool(custom_sbi_owns_sidebar_practice_key(session_state))
    except Exception:
        owns_custom = False
    live_id = str(live_capo_shape_source_id(session_state) or "").strip()
    # Seal whenever Capo sounding is already the Custom UUID — owns_custom can
    # briefly be False when the Song Source radio remounts as Active mid-run.
    preview_custom = str(session_state.get("sbi_preview_source") or "").strip() == "Custom progression"
    restore_custom = bool(session_state.get("_restore_sbi_custom_source"))
    must_seal_custom = live_id.startswith("custom::") and (
        owns_custom or preview_custom or restore_custom
    )
    if must_seal_custom:
        _seal_temporary_sbi_custom_before_capo_save(session_state)
        session_state["_capo_custom_owner_sealed_id"] = live_id
        # Capo renders after the SBI Custom Practice Key widget. Building the
        # envelope through live st.session_state raises StreamlitAPIException when
        # sync paths touch display_key_sbi_custom. Build from a plain dict so the
        # Temporary Custom owner stamp can land on disk before refresh (C4).
        try:
            from music_persistent_state import APP_ID, build_music_disk_state
            from suite_user_persistence import save_user_state

            persist_capo_to_canonical(session_state)
            plain = {k: session_state[k] for k in list(session_state.keys())}
            _seal_temporary_sbi_custom_before_capo_save(plain)
            plain["_suite_pending_save_reason"] = "capo_seal_temporary_custom"
            plain.pop("_music_commit_error", None)

            class _PlainSt:
                session_state = plain

            state = build_music_disk_state(_PlainSt())
            if bool(save_user_state(APP_ID, state)):
                session_state["_suite_persist_last_save_reason"] = "capo_seal_temporary_custom"
                session_state["_suite_persist_last_save_disk"] = True
                session_state["_music_force_save_ok"] = True
                session_state.pop("_music_force_save_blocked_reason", None)
                cws = plain.get("creative_workspace_state")
                if isinstance(cws, dict):
                    session_state["creative_workspace_state"] = cws
        except Exception:
            try:
                from music_persistent_state import force_save_music_state

                force_save_music_state(persist_st, reason="capo_seal_temporary_custom")
            except Exception:
                flush_capo_edits_to_cloud(persist_st)
        _seal_temporary_sbi_custom_before_capo_save(session_state)
    elif not owns_custom and not live_id.startswith("custom::"):
        session_state.pop("_capo_custom_owner_sealed_id", None)

    if (not must_seal_custom) and (
        persist_capo_to_canonical(session_state) or genuine_manual_on
    ):
        flush_capo_edits_to_cloud(persist_st)
        if genuine_manual_on:
            try:
                from music_persistent_state import force_save_music_state

                _seal_temporary_sbi_custom_before_capo_save(session_state)
                force_save_music_state(persist_st, reason="capo_shape_mode_on")
                _seal_temporary_sbi_custom_before_capo_save(session_state)
            except Exception:
                pass


def render_guitar_capo_practice_panel(
    st: Any,
    session_state: dict,
    *,
    concert_key: str,
    sections: dict[str, list[str]],
    key_prefix: str,
) -> CapoContext:
    """Detailed capo helper on the Practice page (preview + status)."""
    ctx = build_capo_context(
        session_state,
        sections,
        concert_key=concert_key,
        instrument="Guitar",
    )
    st.markdown("#### Guitar capo helper")
    st.caption(
        "Shape key is what your fingers play; sounding key is what everyone hears "
        "(and what the backing track uses)."
    )
    if ctx.enabled:
        st.markdown(capo_status_banner_html(ctx), unsafe_allow_html=True)
        preview = []
        for _name, chs in ctx.shape_sections.items():
            preview.extend(chs[:4])
            if len(preview) >= 8:
                break
        if preview:
            st.write(
                "Shape chords (preview): `"
                + " | ".join(preview[:8])
                + "`"
            )
    else:
        st.info(
            "Enable **Capo Shape Mode** in the sidebar to show grip-friendly shapes "
            "while keeping the backing track in the sounding key."
        )
    return ctx
