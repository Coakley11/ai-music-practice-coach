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


def valid_live_shape_widget_tonic(session_state: dict) -> str:
    """Return the Shape Key widget tonic when it is a real user/control value.

    Empty / missing widget is uninitialized. ``shape_tonic_only('')`` would
    otherwise collapse to ``C`` and look like a live pick.
    """
    raw = str(session_state.get(CAPO_SHAPE_WIDGET_KEY) or "").strip()
    if not raw:
        return ""
    tonic = shape_tonic_only(raw)
    if tonic in set(ENHARMONIC_MAJOR_KEYS):
        return tonic
    extras = set(shape_tonic_options(selected=tonic))
    return tonic if tonic in extras else ""


def live_capo_shape_source_id(session_state: dict) -> str:
    """Stable source identity for Shape Key seed vs live-user authority."""
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


def capo_shape_authoritative_reset(session_state: dict) -> bool:
    """True for this-run disk/cloud restore or a different source than last seed.

    Do **not** use ``_capo_on_shape_seeded == false`` or incomplete
    ``_music_restore_phase_complete`` — those stay false on long Songs/SBI
    paths and would destroy a live Shape Key pick.
    """
    if session_state.get("_cloud_workspace_restored_this_run"):
        return True
    if session_state.get("_music_disk_restore_this_run"):
        return True
    live = live_capo_shape_source_id(session_state)
    last = str(session_state.get(CAPO_SHAPE_SEED_SOURCE_KEY) or "").strip()
    return bool(live and last and live != last)


def apply_source_change_shape_home(session_state: dict, sounding: str) -> None:
    """On a new source, drop the previous source's Shape tonic.

    If canonical already differs from the leftover widget (new source home is
    already in session), leave it. If widget and canonical still share the old
    tonic, initialize from the new sounding tonic.
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
    widget_shape = str(session_state.get(CAPO_SHAPE_WIDGET_KEY) or "").strip()
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
            session_state[CAPO_SHAPE_WIDGET_KEY] = applied_shape
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
        session_state[CAPO_SHAPE_WIDGET_KEY] = shape


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
        session_state[CAPO_SHAPE_KEY] = default_shape_key_for_sounding(sounding)
    else:
        # Capo on: never overwrite a user Shape Key from Practice / Concert Key.
        session_state[CAPO_SHAPE_KEY] = shape_tonic_only(str(session_state.get(CAPO_SHAPE_KEY) or ""))
    return sounding


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
        if isinstance(meta, dict) and all(meta.get(k) == live_capo.get(k) for k in live_capo):
            return False
        # Prefer meta Capo-on Shape over a Capo-off / open-fret live wipe.
        if (
            isinstance(meta, dict)
            and meta.get(CAPO_ENABLED_KEY)
            and str(meta.get(CAPO_SHAPE_KEY) or "").strip()
            and not live_capo.get(CAPO_ENABLED_KEY)
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


def flush_capo_edits_to_cloud(st_module: Any) -> bool:
    """Persist capo canonical blob to cloud after sidebar widgets render.

    ``st_module`` must be the Streamlit module (``st``), not ``st.sidebar``.
    """
    try:
        from active_song_state import clear_active_song_local_edit
        from music_persistent_state import flush_active_song_edits_and_save

        ok = bool(flush_active_song_edits_and_save(st_module, reason="capo_widget"))
        if ok:
            clear_active_song_local_edit(st_module.session_state)
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
    sounding = sync_capo_from_practice_display_key(session_state, practice_display_key)
    ui.markdown(
        f'<p class="ui-sidebar-key-caption"><strong>Sounding Key:</strong> '
        f"{html.escape(sounding)}</p>",
        unsafe_allow_html=True,
    )
    # New run: widgets not yet created. Apply any deferred sync from last flush.
    session_state["_capo_widgets_instantiated_this_run"] = False
    if "_pending_capo_enabled_widget" in session_state:
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
            session_state[CAPO_SHAPE_WIDGET_KEY] = shape_seed
    try:
        from capo_refresh_trace import note_capo_refresh

        note_capo_refresh(session_state, phase="before_capo_checkbox")
    except Exception:
        pass
    session_state[CAPO_ENABLED_KEY] = ui.checkbox(
        "Capo Shape Mode",
        key=CAPO_ENABLED_WIDGET_KEY,
        help="Charts/TAB use grip shapes; backing audio stays in the sounding key.",
    )
    session_state["_capo_widgets_instantiated_this_run"] = True
    if not session_state.get(CAPO_ENABLED_KEY):
        # Widget Capo-off must not wipe player Capo when canonical meta still has
        # Capo ON + Shape (refresh race before widget seed lands).
        meta = session_state.get("active_song_state")
        meta_on = (
            isinstance(meta, dict)
            and bool(meta.get(CAPO_ENABLED_KEY))
            and str(meta.get(CAPO_SHAPE_KEY) or "").strip()
        )
        if meta_on:
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
        if persist_capo_to_canonical(session_state):
            flush_capo_edits_to_cloud(persist_st)
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
    live_user = promote_live_shape_widget_over_seed(session_state)
    pending_shape = str(session_state.get("_pending_capo_shape_key") or "").strip()
    if live_user:
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
    widget_shape = str(session_state.get(CAPO_SHAPE_WIDGET_KEY) or "").strip()
    # Seed is initialization / source-restore only. A valid live widget tonic
    # must not be overwritten merely because ``_capo_on_shape_seeded`` is false.
    seed_will_write = False
    if _should_seed_shape_widget_from_canonical(session_state):
        if cur_shape and (not widget_shape or widget_shape not in shape_opts or widget_shape != cur_shape):
            session_state[CAPO_SHAPE_WIDGET_KEY] = cur_shape
            seed_will_write = True
    elif widget_shape and widget_shape not in shape_opts:
        session_state[CAPO_SHAPE_WIDGET_KEY] = cur_shape
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
        key=CAPO_SHAPE_WIDGET_KEY,
        help="Tonic/root only. Charts inherit major/minor from Practice / Concert Key.",
    )
    _selectbox_return = session_state.get(CAPO_SHAPE_KEY)
    session_state[CAPO_SHAPE_KEY] = shape_tonic_only(str(session_state.get(CAPO_SHAPE_KEY) or cur_shape))
    session_state["_capo_on_shape_seeded"] = True
    remember_capo_shape_seed_source(session_state)
    if _shape_trace:
        try:
            from capo_refresh_trace import note_capo_refresh

            note_capo_refresh(
                session_state,
                phase="shape_select_post",
                selectbox_return=str(_selectbox_return or ""),
                canonical_after=str(session_state.get(CAPO_SHAPE_KEY) or ""),
                widget_after=str(session_state.get(CAPO_SHAPE_WIDGET_KEY) or ""),
            )
        except Exception:
            pass
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
    if persist_capo_to_canonical(session_state):
        flush_capo_edits_to_cloud(persist_st)


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
