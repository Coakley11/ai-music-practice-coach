"""UI helpers for Vocal Performance / Karaoke Mode.

This module renders the user-facing parts of karaoke mode while keeping
the underlying state machine in :mod:`karaoke_mode`. The rendering
helpers accept ``ALL_SONG_RECORDS`` as a parameter (rather than importing
the catalog directly) so this module stays decoupled from the main app
and is safe to import from any page.

Layering:

* :mod:`karaoke_mode`  - pure state + queue logic, no Streamlit imports.
* :mod:`karaoke_ui`    - Streamlit-aware rendering helpers (this module).
* ``streamlit_music_practice_app.py`` calls into both.
"""

from __future__ import annotations

import html
from typing import Any, Callable, Iterable

import karaoke_mode as km

__all__ = (
    "render_karaoke_setlist_panel",
    "render_add_to_queue_button",
    "render_karaoke_status_pill",
    "render_karaoke_skip_controls",
    "render_karaoke_now_singing_banner",
    "render_karaoke_transition_card",
    "lookup_pick_key_label",
    "build_karaoke_audio_bridge_script",
    "KARAOKE_SKIP_BUTTON_TEXT",
)


# Stable label text the JS audio-ended bridge searches for in the parent
# DOM. Keep this constant so the bridge and the button stay in sync.
KARAOKE_SKIP_BUTTON_TEXT = "Skip to next song"


# ---------------------------------------------------------------------------
# Pick-key -> "Title — Artist" resolver
# ---------------------------------------------------------------------------


def lookup_pick_key_label(
    pick_key: str,
    *,
    record_for_pick_key: Callable[[Iterable[dict], str], dict | None],
    all_records: Iterable[dict],
) -> tuple[str, str]:
    """Resolve a pick_key to ``(title, artist)``.

    Falls back to ``parse_pick_key``-style label parsing if the catalog
    lookup fails (e.g. catalog reload after queue was saved).
    """
    rec = record_for_pick_key(all_records, pick_key) if pick_key else None
    if rec:
        return (str(rec.get("title", "") or ""), str(rec.get("artist", "") or ""))
    # Best-effort fallback: pick_key is "genre\x1ftitle — artist"
    label = pick_key.split("\x1f", 1)[-1] if "\x1f" in pick_key else pick_key
    if " — " in label:
        title, artist = label.split(" — ", 1)
        return (title.strip(), artist.strip())
    return (label, "")


# ---------------------------------------------------------------------------
# "Add to Karaoke Queue" button (used inside the active-song card actions)
# ---------------------------------------------------------------------------


def render_add_to_queue_button(
    st: Any,
    *,
    pick_key: str,
    title: str = "",
    artist: str = "",
    key_suffix: str = "active",
    use_container_width: bool = True,
) -> bool:
    """Render an "Add to Karaoke Queue" button. Returns ``True`` if clicked.

    Idempotent: a song already in the queue shows a calmer "In Setlist"
    state instead of allowing duplicate adds.
    """
    already = km.is_in_queue(st.session_state, pick_key)
    if already:
        label = "In Karaoke Setlist"
    else:
        label = "Add to Karaoke Set"
    clicked = st.button(
        label,
        key=f"karaoke_add_{key_suffix}",
        use_container_width=use_container_width,
        disabled=already,
        type="primary" if not already else "secondary",
        help=(
            "Already queued for this karaoke set."
            if already
            else f"Queue '{title}' for your karaoke performance setlist."
        ),
    )
    if clicked and not already:
        km.add_to_queue(st.session_state, pick_key)
        if title:
            st.toast(f"Added '{title}' to the karaoke setlist.", icon="🎤")
    return bool(clicked)


# ---------------------------------------------------------------------------
# Setlist panel for the Song Selection page
# ---------------------------------------------------------------------------


def render_karaoke_setlist_panel(
    st: Any,
    *,
    record_for_pick_key: Callable[[Iterable[dict], str], dict | None],
    all_records: Iterable[dict],
    navigate_to_backing: Callable[[], None] | None = None,
) -> None:
    """Render the Performance Setlist UI on the Song Selection page.

    Lets the user reorder / remove queued songs and start the karaoke
    session. ``navigate_to_backing`` is called when the user clicks
    "Start Karaoke Set" so the parent page can route to Backing Track.
    """
    queue = km.get_queue(st.session_state)
    pos, total = km.session_position(st.session_state)
    title = km.voice_wording("queue_section_title", voice=True)

    st.markdown(
        f'<div class="ui-karaoke-setlist">'
        f'<p class="ui-karaoke-setlist-kicker">Vocal Performance</p>'
        f'<p class="ui-karaoke-setlist-title">{html.escape(title)}'
        + (f' <small style="font-weight:600;opacity:0.75;color:#831843;">({total} queued)</small>' if total else "")
        + "</p>",
        unsafe_allow_html=True,
    )

    if not queue:
        st.markdown(
            '<p class="ui-karaoke-setlist-empty">'
            + html.escape(km.voice_wording("queue_empty_caption", voice=True))
            + "</p></div>",
            unsafe_allow_html=True,
        )
        return

    active_pk = km.current_session_pick_key(st.session_state)
    for idx, pick_key in enumerate(queue):
        t, a = lookup_pick_key_label(
            pick_key,
            record_for_pick_key=record_for_pick_key,
            all_records=all_records,
        )
        is_active = pick_key == active_pk
        row_cls = "ui-karaoke-row ui-karaoke-row-active" if is_active else "ui-karaoke-row"
        meta_marker = "  (Now Singing)" if is_active else ""
        st.markdown(
            f'<div class="{row_cls}">'
            f'<span class="ui-karaoke-row-num">{idx + 1}.</span>'
            f'<span class="ui-karaoke-row-title">{html.escape(t)}</span>'
            f'<span class="ui-karaoke-row-artist">— {html.escape(a)}{html.escape(meta_marker)}</span>'
            "</div>",
            unsafe_allow_html=True,
        )
        c_up, c_dn, c_rm, _spacer = st.columns([1, 1, 1, 5])
        with c_up:
            if st.button(
                "↑",
                key=f"karaoke_up_{idx}_{pick_key}",
                use_container_width=True,
                disabled=idx == 0,
                help="Move earlier in the setlist",
            ):
                km.move_in_queue(st.session_state, pick_key, -1)
                st.rerun()
        with c_dn:
            if st.button(
                "↓",
                key=f"karaoke_dn_{idx}_{pick_key}",
                use_container_width=True,
                disabled=idx == len(queue) - 1,
                help="Move later in the setlist",
            ):
                km.move_in_queue(st.session_state, pick_key, +1)
                st.rerun()
        with c_rm:
            if st.button(
                "✕",
                key=f"karaoke_rm_{idx}_{pick_key}",
                use_container_width=True,
                help="Remove from setlist",
            ):
                km.remove_from_queue(st.session_state, pick_key)
                st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

    # Setlist actions
    active = km.is_karaoke_session_active(st.session_state)
    c_start, c_stop, c_clear, c_auto = st.columns([2, 2, 2, 3])
    with c_start:
        if st.button(
            km.voice_wording("start_session_button", voice=True),
            key="karaoke_start_session",
            disabled=active or not queue,
            type="primary",
            use_container_width=True,
        ):
            started = km.start_session(st.session_state)
            if started and navigate_to_backing is not None:
                navigate_to_backing()
            st.rerun()
    with c_stop:
        if st.button(
            km.voice_wording("stop_session_button", voice=True),
            key="karaoke_stop_session",
            disabled=not active,
            use_container_width=True,
        ):
            km.stop_session(st.session_state)
            st.rerun()
    with c_clear:
        if st.button(
            "Clear Setlist",
            key="karaoke_clear_queue",
            use_container_width=True,
            disabled=not queue,
        ):
            km.clear_queue(st.session_state)
            st.rerun()
    with c_auto:
        current_auto = km.auto_advance_enabled(st.session_state)
        new_auto = st.toggle(
            "Auto-advance between songs",
            value=current_auto,
            key="karaoke_auto_advance_toggle",
            help="When a song finishes, automatically load the next karaoke song.",
        )
        if new_auto != current_auto:
            st.session_state[km.KARAOKE_AUTO_ADVANCE_KEY] = bool(new_auto)

    if active:
        cur_t, cur_a = lookup_pick_key_label(
            active_pk or "",
            record_for_pick_key=record_for_pick_key,
            all_records=all_records,
        )
        st.caption(
            f"Karaoke set in progress · **{pos} of {total}** · Now singing **{cur_t}** — {cur_a}"
        )


# ---------------------------------------------------------------------------
# Backing Track page: status pill + transition card
# ---------------------------------------------------------------------------


def render_karaoke_status_pill(st: Any) -> None:
    """Show a "Karaoke Set: 2 of 5" pill above the Backing Track player."""
    if not km.is_karaoke_session_active(st.session_state):
        return
    pos, total = km.session_position(st.session_state)
    if total <= 0:
        return
    st.markdown(
        f'<span class="ui-karaoke-now-singing">Karaoke Set · '
        f"Song {pos} of {total}</span>",
        unsafe_allow_html=True,
    )


def render_karaoke_skip_controls(
    st: Any,
    *,
    record_for_pick_key: Callable[[Iterable[dict], str], dict | None],
    all_records: Iterable[dict],
) -> None:
    """Render Skip / End controls above the player during a karaoke set.

    The "Skip to next song" button label is the JS bridge's auto-click
    target (see :data:`KARAOKE_SKIP_BUTTON_TEXT`). The button is visible
    so the singer can skip manually at any time.
    """
    if not km.is_karaoke_session_active(st.session_state):
        return
    nxt = km.next_session_pick_key(st.session_state)
    if nxt:
        t, a = lookup_pick_key_label(
            nxt,
            record_for_pick_key=record_for_pick_key,
            all_records=all_records,
        )
        next_caption = f"Next: **{t}** — {a}"
    else:
        next_caption = "Last song in the setlist."

    c_skip, c_end, _spacer = st.columns([3, 2, 5])
    with c_skip:
        clicked_skip = st.button(
            f"\u23ED  {KARAOKE_SKIP_BUTTON_TEXT}",
            key="karaoke_skip_to_next",
            use_container_width=True,
            help="Advance to the next song in your karaoke set.",
            disabled=nxt is None,
        )
    with c_end:
        clicked_end = st.button(
            "End karaoke set",
            key="karaoke_inline_end_set",
            use_container_width=True,
            help="Stop the karaoke session (your setlist stays saved).",
        )
    st.caption(next_caption)

    if clicked_skip:
        new_pk = km.advance_session(st.session_state)
        if new_pk:
            t2, _ = lookup_pick_key_label(
                new_pk,
                record_for_pick_key=record_for_pick_key,
                all_records=all_records,
            )
            st.session_state[km.KARAOKE_TRANSITION_LABEL_KEY] = f"Now Singing: {t2}"
        else:
            st.session_state[km.KARAOKE_TRANSITION_LABEL_KEY] = "Karaoke set complete"
        st.rerun()
    if clicked_end:
        km.stop_session(st.session_state)
        st.rerun()


def render_karaoke_now_singing_banner(st: Any) -> None:
    """One-shot "Now Singing: <title>" banner shown right after a transition.

    Consumes the :data:`karaoke_mode.KARAOKE_TRANSITION_LABEL_KEY` flag
    so the banner only appears on the rerun immediately after a skip.
    """
    label = st.session_state.pop(km.KARAOKE_TRANSITION_LABEL_KEY, None)
    if not label:
        return
    st.markdown(
        f'<span class="ui-karaoke-now-singing">{html.escape(label)}</span>',
        unsafe_allow_html=True,
    )


def render_karaoke_transition_card(
    st: Any,
    *,
    record_for_pick_key: Callable[[Iterable[dict], str], dict | None],
    all_records: Iterable[dict],
    on_continue: Callable[[], None],
) -> None:
    """Render the "Next Song" transition card after audio ends.

    Only shows when:

    * A karaoke session is active.
    * The audio of the current song fired the ``ended`` event (sticky
      flag :data:`karaoke_mode.KARAOKE_SONG_ENDED_KEY`).

    ``on_continue`` is invoked when the user clicks the prominent
    "Continue to next song" button.
    """
    if not km.is_karaoke_session_active(st.session_state):
        return
    if not st.session_state.get(km.KARAOKE_SONG_ENDED_KEY):
        return

    nxt = km.next_session_pick_key(st.session_state)
    pos, total = km.session_position(st.session_state)
    if nxt:
        t, a = lookup_pick_key_label(
            nxt,
            record_for_pick_key=record_for_pick_key,
            all_records=all_records,
        )
        kicker = "Next on your setlist"
        title = t
        meta = f"{a} · Song {min(pos + 1, total)} of {total}"
    else:
        kicker = "Setlist complete"
        title = "End of karaoke set"
        meta = f"Played {total} of {total} songs"

    st.markdown(
        f'<div class="ui-karaoke-transition">'
        f'<div class="ui-karaoke-transition-icon">\U0001F3A4</div>'
        f"<div>"
        f'<p class="ui-karaoke-transition-kicker">{html.escape(kicker)}</p>'
        f'<p class="ui-karaoke-transition-title">{html.escape(title)}</p>'
        f'<p class="ui-karaoke-transition-meta">{html.escape(meta)}</p>'
        "</div></div>",
        unsafe_allow_html=True,
    )

    if nxt is not None:
        c1, c2 = st.columns([3, 2])
        with c1:
            # NOTE: button label must contain "Continue to next song" so the
            # JS bridge in `build_karaoke_audio_bridge_script` can locate
            # and auto-click it after a short delay (auto-advance mode).
            if st.button(
                "▶  Continue to next song",
                key="karaoke_continue_next",
                type="primary",
                use_container_width=True,
            ):
                on_continue()
                st.rerun()
        with c2:
            if st.button(
                "End karaoke set",
                key="karaoke_end_set",
                use_container_width=True,
            ):
                km.stop_session(st.session_state)
                st.rerun()
    else:
        if st.button(
            "Return to Song Selection",
            key="karaoke_finished_return",
            type="primary",
        ):
            km.stop_session(st.session_state)
            st.rerun()


# ---------------------------------------------------------------------------
# JS bridge: auto-click the "Continue" button after audio ends
# ---------------------------------------------------------------------------


def build_karaoke_audio_bridge_script(
    *,
    auto_advance: bool,
    delay_ms: int = 4000,
    continue_button_text: str = KARAOKE_SKIP_BUTTON_TEXT,
) -> str:
    """Return a JS snippet to splice into the live-follow-along component.

    The snippet does three things when the embedded audio finishes:

    1. Writes a sticky ``karaoke_song_ended = true`` flag into the parent
       window's ``sessionStorage`` so reloads still know the song ended.
    2. Updates the user-facing detail line so the singer sees "Track
       ended - next song loading...".
    3. If ``auto_advance`` is enabled, schedules a click on the parent's
       "Continue to next song" Streamlit button after ``delay_ms``.

    The caller (``live_follow_along_component_html``) is responsible for
    invoking this snippet from inside the existing ``audio.addEventListener
    ("ended", ...)`` callback.
    """
    auto = "true" if auto_advance else "false"
    btn_text = continue_button_text.replace("'", "\\'")
    return f"""
      try {{
        const KARAOKE_AUTO = {auto};
        const KARAOKE_DELAY_MS = {int(delay_ms)};
        const KARAOKE_BUTTON_TEXT = '{btn_text}';
        try {{ window.parent.sessionStorage.setItem('karaoke_song_ended', '1'); }} catch (e) {{}}
        if (typeof detailEl !== 'undefined' && detailEl) {{
          detailEl.textContent = KARAOKE_AUTO
            ? 'Track ended - loading next song in your karaoke set...'
            : 'Track ended. Press Continue to advance to the next song.';
        }}
        if (KARAOKE_AUTO) {{
          window.setTimeout(() => {{
            try {{
              const parentDoc = window.parent.document;
              const buttons = parentDoc.querySelectorAll('button');
              for (const b of buttons) {{
                if ((b.textContent || '').indexOf(KARAOKE_BUTTON_TEXT) !== -1) {{
                  b.click();
                  break;
                }}
              }}
            }} catch (err) {{
              console.warn('karaoke auto-advance failed', err);
            }}
          }}, KARAOKE_DELAY_MS);
        }}
      }} catch (err) {{
        console.warn('karaoke audio bridge failed', err);
      }}
    """
