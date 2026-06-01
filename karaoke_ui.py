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
from collections.abc import Mapping, Sequence
from typing import Any, Callable, Iterable

import karaoke_mode as km

__all__ = (
    "render_karaoke_setlist_panel",
    "render_add_to_queue_button",
    "render_karaoke_status_pill",
    "render_karaoke_skip_controls",
    "render_karaoke_now_singing_banner",
    "render_karaoke_queue_preview",
    "render_karaoke_missing_lyrics_cta",
    "render_karaoke_transition_card",
    "lookup_pick_key_label",
    "build_karaoke_audio_bridge_script",
    "build_karaoke_countdown_script",
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

    Karaoke UI is voice-only: the button is suppressed for Piano /
    Guitar / Bass / Sax / Trumpet / Drums and every other non-Voice
    instrument so instrumentalists see the standard musician workflow
    without any karaoke clutter.

    Idempotent: a song already in the queue shows a calmer "In Setlist"
    state instead of allowing duplicate adds.
    """
    if not km.is_voice_mode(st.session_state):
        return False
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
    on_pick_song: Callable[[str], None] | None = None,
) -> None:
    """Render the Performance Setlist UI on the Song Selection page.

    Lets the user reorder / remove queued songs and start the karaoke
    session. ``navigate_to_backing`` is called when the user clicks
    "Start Karaoke Set" so the parent page can route to Backing Track.

    ``on_pick_song`` is invoked with the row's ``pick_key`` when the
    user clicks a song title in the setlist. This makes the clicked
    song the **active editing/viewing song** (lyrics editor, song
    card, backing defaults, karaoke preview all switch to it) without
    touching the queue order or any active karaoke session position -
    the user can prep multiple songs without re-arranging the set.
    Callers should typically wire this to ``apply_pick_key`` from
    ``songs.state`` so the rest of the app (Practice, Backing Track,
    Lyrics editor) follows along.

    Voice-only: when the active instrument is anything other than
    Voice / Vocals / Singer, the panel hides itself so instrumentalists
    don't see a karaoke setlist on their Song Selection page.
    """
    if not km.is_voice_mode(st.session_state):
        return
    queue = km.get_queue(st.session_state)
    pos, total = km.session_position(st.session_state)
    title = km.voice_wording("queue_section_title", voice=True)

    # Wrap the entire setlist in a keyed container so the karaoke-
    # themed CSS (deep purple background, magenta accents, neon-pink
    # active highlight) can scope to ``.st-key-karaoke_stage ...``.
    # Without this scope the dark vocal-stage styling would bleed onto
    # the regular musician buttons elsewhere on the page.
    stage = st.container(key="karaoke_stage")
    with stage:
        st.markdown(
            f'<div class="ui-karaoke-setlist">'
            f'<p class="ui-karaoke-setlist-kicker">'
            f'<span class="ui-karaoke-setlist-dot" aria-hidden="true"></span>'
            f"Vocal Performance"
            f"</p>"
            f'<p class="ui-karaoke-setlist-title">{html.escape(title)}'
            + (
                f' <small class="ui-karaoke-setlist-count">'
                f"({total} queued)"
                "</small>"
                if total
                else ""
            )
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

        st.caption(
            "Click a song to make it the active editing/viewing song "
            "(lyrics, song card, backing defaults switch to it). "
            "Queue order and karaoke state stay untouched."
        )

        # The "active editing/viewing" song = the master selection. We
        # surface a visual indicator next to whichever queue row matches
        # so the user always knows which row their edits will land on.
        session_active_pk = km.current_session_pick_key(st.session_state)
        selected_pk = ""
        try:
            selected_pk = str(
                (st.session_state.get("selected_song") or {}).get("pick_key") or ""
            )
        except Exception:
            selected_pk = ""

        for idx, pick_key in enumerate(queue):
            t, a = lookup_pick_key_label(
                pick_key,
                record_for_pick_key=record_for_pick_key,
                all_records=all_records,
            )
            is_now_singing = pick_key == session_active_pk
            is_editing = bool(selected_pk and pick_key == selected_pk)

            # Status markers: "Now Singing" (karaoke session) takes
            # priority over "Editing" (master selection) because
            # performing trumps previewing in the user's mental model.
            if is_now_singing:
                marker_text = "Now Singing"
                marker_cls = "marker-singing"
                wrap_state = "is-singing"
            elif is_editing:
                marker_text = "Editing"
                marker_cls = "marker-editing"
                wrap_state = "is-editing"
            else:
                marker_text = ""
                marker_cls = ""
                wrap_state = "is-idle"

            marker_html = (
                f'<span class="ui-karaoke-row-marker {marker_cls}">'
                f"{html.escape(marker_text)}"
                "</span>"
                if marker_text
                else ""
            )

            # Layout: queue # + title (wide) | up | down | remove.
            # Each column emits a tiny wrapper div *before* its button
            # so the CSS can target each control class precisely
            # (compact pick button vs. square icon controls) without
            # bleeding onto the action row at the bottom of the panel.
            c_pick, c_up, c_dn, c_rm = st.columns([8, 1, 1, 1])
            with c_pick:
                # Always emit the wrap so every row aligns vertically,
                # even when no marker pill is shown. The pill sits
                # above the button so the title text stays clean.
                st.markdown(
                    f'<div class="ui-karaoke-pick-wrap {wrap_state}" '
                    f'data-row="{idx}">{marker_html}</div>',
                    unsafe_allow_html=True,
                )
                # Queue index renders as a small monospaced badge so
                # the title reads as the dominant element of the row.
                pick_label = f"{idx + 1:>2}.  {t}  —  {a}"
                if st.button(
                    pick_label,
                    key=f"karaoke_pick_{idx}_{pick_key}",
                    use_container_width=True,
                    type="primary" if is_editing else "secondary",
                    help=(
                        "Make this the active editing/viewing song "
                        "(lyrics, song card, backing defaults switch to it). "
                        "Queue position stays unchanged."
                    ),
                    disabled=on_pick_song is None,
                ):
                    if on_pick_song is not None and not is_editing:
                        try:
                            on_pick_song(pick_key)
                        except Exception:
                            # Last-resort fallback: at minimum write
                            # the pick_key into session_state so the
                            # rest of the app sees the selection.
                            st.session_state["selected_song"] = {
                                "pick_key": pick_key,
                                "title": t,
                                "artist": a,
                            }
                        st.rerun()
            with c_up:
                st.markdown(
                    '<div class="ui-karaoke-ctrl-wrap" data-action="up"></div>',
                    unsafe_allow_html=True,
                )
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
                st.markdown(
                    '<div class="ui-karaoke-ctrl-wrap" data-action="down"></div>',
                    unsafe_allow_html=True,
                )
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
                st.markdown(
                    '<div class="ui-karaoke-ctrl-wrap" data-action="remove"></div>',
                    unsafe_allow_html=True,
                )
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

        cc_left, cc_right = st.columns([3, 4])
        with cc_left:
            cur_cd = km.countdown_enabled(st.session_state)
            new_cd = st.toggle(
                "Countdown before each song",
                value=cur_cd,
                key="karaoke_countdown_toggle",
                help="Show a 5-4-3-2-1 pre-roll before the backing track starts.",
            )
            if new_cd != cur_cd:
                st.session_state[km.KARAOKE_COUNTDOWN_KEY] = bool(new_cd)
        with cc_right:
            cur_seconds = km.countdown_seconds(st.session_state)
            new_seconds = st.slider(
                "Countdown length",
                min_value=1,
                max_value=10,
                value=cur_seconds,
                step=1,
                key="karaoke_countdown_seconds_slider",
                help="How long the pre-roll countdown lasts (in seconds).",
                disabled=not new_cd,
            )
            if int(new_seconds) != cur_seconds:
                st.session_state[km.KARAOKE_COUNTDOWN_SECONDS_KEY] = int(new_seconds)

        # Karaoke display options - chords toggle + lyric color picker.
        # Both write straight to session_state so the Backing Track
        # page picks them up on the next render with no extra plumbing.
        disp_left, disp_right = st.columns([3, 4])
        with disp_left:
            cur_show = km.show_chords_enabled(st.session_state)
            new_show = st.toggle(
                "Show chords while singing",
                value=cur_show,
                key="karaoke_show_chords_toggle",
                help=(
                    "When on, the chord strip is rendered under the lyrics "
                    "and the current chord highlights in sync with the "
                    "backing track. Turn off for a lyrics-only sing-along."
                ),
            )
            if bool(new_show) != cur_show:
                st.session_state[km.KARAOKE_SHOW_CHORDS_KEY] = bool(new_show)
        with disp_right:
            _color_options = ["white", "gold", "cyan", "cream"]
            _color_labels = {
                "white": "White (highest contrast)",
                "gold": "Soft gold",
                "cyan": "Cyan",
                "cream": "Warm cream",
            }
            cur_color = km.lyric_color(st.session_state)
            try:
                _idx = _color_options.index(cur_color)
            except ValueError:
                _idx = 0
            new_color = st.selectbox(
                "Lyric color",
                options=_color_options,
                index=_idx,
                format_func=lambda v: _color_labels.get(v, v.title()),
                key="karaoke_lyric_color_picker",
                help=(
                    "Color used for lyrics on the karaoke black screen. "
                    "Choose what's easiest to read from a distance."
                ),
            )
            if str(new_color) != cur_color:
                st.session_state[km.KARAOKE_LYRIC_COLOR_KEY] = str(new_color)

        if active:
            cur_t, cur_a = lookup_pick_key_label(
                session_active_pk or "",
                record_for_pick_key=record_for_pick_key,
                all_records=all_records,
            )
            st.caption(
                f"Karaoke set in progress · **{pos} of {total}** · "
                f"Now singing **{cur_t}** — {cur_a}"
            )


# ---------------------------------------------------------------------------
# Backing Track page: status pill + transition card
# ---------------------------------------------------------------------------


def render_karaoke_status_pill(st: Any) -> None:
    """Show a "Karaoke Set: 2 of 5" pill above the Backing Track player.

    Voice-only - non-voice instruments never see this pill even if a
    stale session is still active in session_state.
    """
    if not km.is_voice_mode(st.session_state):
        return
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

    Voice-only - the controls only render when the active instrument is
    Voice / Vocals / Singer so non-voice instruments never see karaoke
    skip/end buttons mid-page.

    The "Skip to next song" button label is the JS bridge's auto-click
    target (see :data:`KARAOKE_SKIP_BUTTON_TEXT`). The button is visible
    so the singer can skip manually at any time.
    """
    if not km.is_voice_mode(st.session_state):
        return
    if not km.is_karaoke_session_active(st.session_state):
        return
    nxt = km.next_session_pick_key(st.session_state)
    prv = km.previous_session_pick_key(st.session_state)
    if nxt:
        t, a = lookup_pick_key_label(
            nxt,
            record_for_pick_key=record_for_pick_key,
            all_records=all_records,
        )
        next_caption = f"Next: **{t}** — {a}"
    else:
        next_caption = "Last song in the setlist."

    c_prev, c_skip, c_end, _spacer = st.columns([2, 3, 2, 3])
    with c_prev:
        clicked_prev = st.button(
            "\u23EE  Previous song",
            key="karaoke_previous_song",
            use_container_width=True,
            help="Step back to the previous song in your karaoke set.",
            disabled=prv is None,
        )
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

    if clicked_prev:
        new_pk = km.regress_session(st.session_state)
        if new_pk:
            t2, _ = lookup_pick_key_label(
                new_pk,
                record_for_pick_key=record_for_pick_key,
                all_records=all_records,
            )
            st.session_state[km.KARAOKE_TRANSITION_LABEL_KEY] = f"Now Singing: {t2}"
        st.rerun()
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

    Voice-only - the banner suppresses (and silently drops any stale
    flag) when the active instrument isn't Voice / Vocals / Singer.

    Consumes the :data:`karaoke_mode.KARAOKE_TRANSITION_LABEL_KEY` flag
    so the banner only appears on the rerun immediately after a skip.
    """
    if not km.is_voice_mode(st.session_state):
        # Drop any stale label so it can't surface later when the user
        # flips back to Voice mode.
        st.session_state.pop(km.KARAOKE_TRANSITION_LABEL_KEY, None)
        return
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

    * The active instrument is Voice / Vocals / Singer (karaoke-only).
    * A karaoke session is active.
    * The audio of the current song fired the ``ended`` event (sticky
      flag :data:`karaoke_mode.KARAOKE_SONG_ENDED_KEY`).

    ``on_continue`` is invoked when the user clicks the prominent
    "Continue to next song" button.
    """
    if not km.is_voice_mode(st.session_state):
        return
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


# ---------------------------------------------------------------------------
# Pre-roll countdown JS (5-4-3-2-1 overlay before backing audio plays)
# ---------------------------------------------------------------------------


def build_karaoke_countdown_script(
    *,
    enabled: bool,
    seconds: int = 5,
) -> str:
    """Return a JS snippet that runs a 5-4-3-2-1 pre-roll inside the audio iframe.

    When ``enabled`` is ``True``:

    * The embedded audio is paused immediately on load.
    * A fullscreen overlay shows the countdown (5, 4, 3, 2, 1).
    * After the countdown ends, ``audio.play()`` is invoked.
    * A "Skip countdown" button inside the overlay starts playback at
      once and removes the overlay.

    The caller injects this snippet at the *top* of the audio-player
    initialisation block in :func:`live_follow_along_component_html`. It
    expects ``audio`` (the ``<audio>`` element) to be in scope.
    """
    if not enabled:
        return ""
    safe_seconds = max(1, min(10, int(seconds)))
    return f"""
      try {{
        const KARAOKE_COUNTDOWN_SECONDS = {safe_seconds};
        if (audio) {{
          try {{ audio.pause(); audio.currentTime = 0; }} catch (e) {{}}
          audio.autoplay = false;
        }}
        const overlay = document.createElement('div');
        overlay.className = 'karaoke-countdown-overlay';
        overlay.innerHTML = `
          <div class="karaoke-countdown-kicker">Get ready to sing</div>
          <div class="karaoke-countdown-number" id="karaokeCountNum">${{KARAOKE_COUNTDOWN_SECONDS}}</div>
          <button type="button" class="karaoke-countdown-skip" id="karaokeCountSkip">Skip countdown</button>
        `;
        document.body.appendChild(overlay);
        let remaining = KARAOKE_COUNTDOWN_SECONDS;
        let cancelled = false;
        const numEl = overlay.querySelector('#karaokeCountNum');
        const skipEl = overlay.querySelector('#karaokeCountSkip');
        const cleanup = () => {{
          try {{ overlay.remove(); }} catch (e) {{}}
        }};
        const startPlayback = () => {{
          cancelled = true;
          cleanup();
          if (audio) {{
            try {{ audio.play(); }} catch (e) {{
              console.warn('karaoke countdown play failed', e);
            }}
          }}
        }};
        if (skipEl) {{
          skipEl.addEventListener('click', startPlayback);
        }}
        const tick = () => {{
          if (cancelled) return;
          remaining -= 1;
          if (remaining <= 0) {{
            startPlayback();
            return;
          }}
          if (numEl) numEl.textContent = String(remaining);
          numEl && numEl.classList.remove('pulse');
          // re-trigger CSS animation
          void (numEl && numEl.offsetWidth);
          numEl && numEl.classList.add('pulse');
          window.setTimeout(tick, 1000);
        }};
        numEl && numEl.classList.add('pulse');
        window.setTimeout(tick, 1000);
      }} catch (err) {{
        console.warn('karaoke countdown failed', err);
        if (audio) {{ try {{ audio.play(); }} catch (e) {{}} }}
      }}
    """


# ---------------------------------------------------------------------------
# Queue preview shown on the Backing Track page during a karaoke set
# ---------------------------------------------------------------------------


def render_karaoke_queue_preview(
    st: Any,
    *,
    record_for_pick_key: Callable[[str], Mapping[str, Any] | None] | None = None,
    all_records: Sequence[Mapping[str, Any]] | None = None,
    max_upcoming: int = 3,
) -> None:
    """Render a compact "Now Singing / Next / 3rd" queue preview.

    Voice-only - hides immediately when the active instrument isn't
    Voice / Vocals / Singer. Designed to live above the chord chart
    on the Backing Track page so the singer always knows what's
    coming next.
    """
    if not km.is_voice_mode(st.session_state):
        return
    if not km.is_karaoke_session_active(st.session_state):
        return

    cur_pk = km.current_session_pick_key(st.session_state)
    upcoming = km.upcoming_session_pick_keys(st.session_state, limit=max_upcoming)
    pos, total = km.session_position(st.session_state)
    if not cur_pk and not upcoming:
        return

    ordinals = ("Next", "3rd", "4th", "5th", "6th")

    rows_html: list[str] = []

    def _row(label: str, pk: str, *, current: bool = False) -> str:
        t, a = lookup_pick_key_label(
            pk,
            record_for_pick_key=record_for_pick_key,
            all_records=all_records,
        )
        cls = "ui-karaoke-preview-row" + (" current" if current else "")
        return (
            f'<div class="{cls}">'
            f'<span class="ui-karaoke-preview-label">{html.escape(label)}</span>'
            f'<span class="ui-karaoke-preview-title">{html.escape(t)}</span>'
            f'<span class="ui-karaoke-preview-artist">{html.escape(a)}</span>'
            "</div>"
        )

    if cur_pk:
        rows_html.append(_row("Now Singing", cur_pk, current=True))
    for i, pk in enumerate(upcoming):
        label = ordinals[i] if i < len(ordinals) else f"#{pos + i + 1}"
        rows_html.append(_row(label, pk))

    header = f"Karaoke Setlist · {pos} of {total}"
    st.markdown(
        '<div class="ui-karaoke-preview">'
        f'<div class="ui-karaoke-preview-header">{html.escape(header)}</div>'
        + "".join(rows_html)
        + "</div>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Missing-lyrics CTA shown when the active karaoke song has no lyric data
# ---------------------------------------------------------------------------


def render_karaoke_missing_lyrics_cta(
    st: Any,
    *,
    song_data: Mapping[str, Any] | None,
    active_song_title: str | None = None,
    on_open_editor: Callable[[], None] | None = None,
) -> bool:
    """Show a friendly card when the active karaoke song has no lyrics.

    Returns ``True`` when the CTA was rendered (so the caller can skip
    rendering instrument-focused analysis below it). The CTA only
    appears in voice mode.

    ``on_open_editor`` is invoked when the user clicks the "Open Lyrics
    & Cues editor" button. The caller should navigate the user to the
    Song Selection / Lyrics editor page (or trigger an inline editor).
    """
    if not km.is_voice_mode(st.session_state):
        return False
    if not isinstance(song_data, Mapping):
        return False

    section_lyrics_user: dict = {}
    lyric_cues_user: dict = {}
    if hasattr(st, "session_state"):
        try:
            from songs.user_lyrics_runtime import (
                hydrate_user_lyrics_session,
                resolve_user_lyrics_and_cues,
            )

            _title = str(song_data.get("title", "") or "")
            _artist = str(song_data.get("artist", "") or "")
            hydrate_user_lyrics_session(st.session_state, title=_title, artist=_artist)
            section_lyrics_user, lyric_cues_user, _notes = resolve_user_lyrics_and_cues(
                st.session_state,
                title=_title,
                artist=_artist,
                song_data=dict(song_data),
            )
        except Exception:
            section_lyrics_user = {}
            lyric_cues_user = {}
    if isinstance(lyric_cues_user, Mapping) and any(
        (str(v) or "").strip() for v in lyric_cues_user.values()
    ):
        return False
    if isinstance(section_lyrics_user, Mapping) and any(
        (str(v) or "").strip() for v in section_lyrics_user.values()
    ):
        return False

    title = active_song_title or song_data.get("title") or "this song"
    st.markdown(
        '<div class="ui-karaoke-missing-lyrics">'
        '<div class="ui-karaoke-missing-icon">\U0001F3A4</div>'
        "<div>"
        '<p class="ui-karaoke-missing-kicker">No lyrics or cues yet</p>'
        f'<p class="ui-karaoke-missing-title">Add lyrics &amp; cues for {html.escape(str(title))}</p>'
        '<p class="ui-karaoke-missing-meta">Singer-friendly lyrics + phrasing cues unlock the full karaoke flow.</p>'
        "</div></div>",
        unsafe_allow_html=True,
    )
    if st.button(
        "\u270F\uFE0F  Open Lyrics & Cues editor",
        key="karaoke_open_lyrics_editor",
        type="primary",
    ):
        if on_open_editor:
            on_open_editor()
        else:
            # Fall back: jump the user back to Song Selection where the
            # Lyrics & Cues editor lives on the active song card, and
            # queue a scroll anchor so they land at the editor instead
            # of the top of the page.
            try:
                from studio_nav_history import navigate_studio_page
                from studio_scroll_anchors import (
                    ANCHOR_LYRICS_EDITOR,
                    set_pending_anchor,
                )

                set_pending_anchor(st.session_state, ANCHOR_LYRICS_EDITOR)
                navigate_studio_page(st.session_state, "picker")
            except Exception:
                # Last-resort legacy fallback so the button is never a no-op.
                st.session_state["studio_page"] = "picker"
            from picker_song_editor import open_picker_editor

            open_picker_editor(st.session_state, "Lyrics & Cues")
            try:
                st.rerun()
            except Exception:
                pass
    return True
