"""Streamlit-aware renderers for the YouTube integration.

Two public entry points:

* :func:`render_original_song_video_card` - lightweight "Watch original
  song" expander used inside the Active Song card on the Song Selection
  page. Always speaks plain-song language; instrument / level / focus
  do not affect it.

* :func:`render_practice_learning_video_panel` - the Practice-page
  "Optional YouTube reference" section. Lets the user tune instrument
  / level / focus and either generate a search URL or paste a specific
  override URL; the override embeds inline (lazy, only after the user
  expands the section).

Both renderers persist their override URL per song under a
``youtube_*_override::<slug>`` session key, so the user only has to
paste a custom link once.
"""

from __future__ import annotations

import html
from typing import Any

from youtube_links import (
    build_learning_search_url,
    build_original_song_search_url,
    describe_search_query,
    embed_url_for,
    focus_options_for_instrument,
    is_voice_instrument,
    is_youtube_url,
    practice_panel_kicker,
    thumbnail_url_for,
)

__all__ = (
    "render_original_song_video_card",
    "render_practice_learning_video_panel",
    "original_video_override_key",
    "practice_video_override_key",
)


# ---------------------------------------------------------------------------
# Persisted override keys (session_state)
# ---------------------------------------------------------------------------


def original_video_override_key(song_slug: str) -> str:
    """Session key holding the user's override URL for the original-song video."""
    return f"youtube_original_override::{song_slug}"


def practice_video_override_key(song_slug: str) -> str:
    """Session key holding the user's override URL for the Practice page video."""
    return f"youtube_practice_override::{song_slug}"


# ---------------------------------------------------------------------------
# Embed helper - lazy: only renders the iframe after the user clicks
# ---------------------------------------------------------------------------


def _render_embed(
    st: Any,
    *,
    embed: str,
    slug: str,
    panel: str,
) -> None:
    """Render the YouTube iframe lazily.

    A toggle inside the expander gates the iframe so the page never
    preloads a video the user did not ask for. The toggle state is
    persisted per ``panel`` (so the user's preference for the original-
    song embed does not bleed into the practice-page embed).
    """
    open_key = f"_yt_embed_open::{panel}::{slug}"
    is_open = bool(st.session_state.get(open_key, False))
    label = "Hide embedded player" if is_open else "Load embedded player"
    if st.button(label, key=f"_yt_embed_toggle::{panel}::{slug}"):
        st.session_state[open_key] = not is_open
        st.rerun()
    if not st.session_state.get(open_key, False):
        return
    st.markdown(
        f"""
<div class="ui-youtube-embed">
  <iframe src="{html.escape(embed)}"
          loading="lazy"
          frameborder="0"
          allow="accelerometer; encrypted-media; picture-in-picture"
          allowfullscreen></iframe>
</div>
""",
        unsafe_allow_html=True,
    )


def _link_button_html(label: str, url: str) -> str:
    """Render a YouTube-styled external link as an anchor button.

    Streamlit's ``st.link_button`` covers most cases; this returns a
    matching markup so the caption / kicker styling stays consistent
    when we want extra metadata around the link.
    """
    return (
        f'<a class="ui-youtube-link-btn" href="{html.escape(url)}" '
        'target="_blank" rel="noopener noreferrer">'
        f"{html.escape(label)}</a>"
    )


# ---------------------------------------------------------------------------
# Song Selection card: "Listen to / Watch the original song"
# ---------------------------------------------------------------------------


def render_original_song_video_card(
    st: Any,
    *,
    song_title: str,
    artist: str | None,
    song_slug: str,
    instrument: Any = None,
    expanded: bool = False,
) -> None:
    """Render the "Watch original song video" section on the Song Selection page.

    This card is intentionally simple - it asks the user once: "Would
    you like to hear / watch the original recording?" and offers one
    button (open YouTube in a new tab). When the user pastes a specific
    YouTube URL we also surface an inline embed (still lazy).
    """
    if not song_title:
        return

    override_key = original_video_override_key(song_slug)
    override_url = str(st.session_state.get(override_key, "") or "").strip()
    search_url = build_original_song_search_url(song_title, artist)

    voice_mode = is_voice_instrument(instrument)
    if voice_mode:
        header = "Sing-along reference"
        prompt = (
            "Would you like to hear the original recording or queue a "
            "karaoke version? Reference videos load only when you ask."
        )
    else:
        header = "Original song video"
        prompt = (
            "Would you like to hear or watch the original recording? "
            "The video only loads when you ask."
        )

    with st.expander(f"\U0001F3B5  {header}", expanded=expanded):
        st.caption(prompt)
        artist_label = f" — {artist}" if artist else ""
        st.markdown(
            f"**{html.escape(song_title)}**{html.escape(artist_label)}",
            unsafe_allow_html=False,
        )

        # Override input - user can paste a specific URL once.
        new_url = st.text_input(
            "Override YouTube URL (optional)",
            value=override_url,
            key=f"_yt_orig_url_input::{song_slug}",
            placeholder="https://www.youtube.com/watch?v=...",
            help="Paste a specific YouTube link to use that video instead of a search query.",
        )
        if new_url.strip() != override_url:
            st.session_state[override_key] = new_url.strip()
            override_url = new_url.strip()

        active_url = override_url if is_youtube_url(override_url) else search_url
        is_specific_video = bool(override_url) and is_youtube_url(override_url)

        if is_specific_video:
            embed = embed_url_for(override_url)
            thumb = thumbnail_url_for(override_url)
            if thumb:
                st.markdown(
                    f'<img class="ui-youtube-thumb" src="{html.escape(thumb)}" '
                    f'alt="YouTube preview thumbnail">',
                    unsafe_allow_html=True,
                )
            st.markdown(
                _link_button_html("\u25B6  Watch on YouTube", active_url),
                unsafe_allow_html=True,
            )
            if embed:
                _render_embed(st, embed=embed, slug=song_slug, panel="orig")
        else:
            st.caption(
                f"Searching: **{describe_search_query(song_title, artist, mode='original')}**"
            )
            st.markdown(
                _link_button_html(
                    "\u25B6  Watch original on YouTube" if not voice_mode
                    else "\U0001F3A4  Find a sing-along on YouTube",
                    active_url,
                ),
                unsafe_allow_html=True,
            )


# ---------------------------------------------------------------------------
# Practice page: instrument / level / focus-driven learning video panel
# ---------------------------------------------------------------------------


def render_practice_learning_video_panel(
    st: Any,
    *,
    song_title: str,
    artist: str | None,
    song_slug: str,
    instrument: str,
    level: str,
    focus: str | None = None,
    instrument_options: list[str] | None = None,
    level_options: list[str] | None = None,
    expanded: bool = False,
) -> None:
    """Render the Practice-page "Optional YouTube reference" panel.

    Changing the Instrument or Level inside this panel updates the
    global session keys (so every other page sees the same value -
    that's the app-wide instrument/level/focus sync rule). The Focus
    selector inside this panel is YouTube-search-specific (categories
    like "Chords" / "Improvisation" / "Strumming") and stays
    panel-local so it doesn't overwrite the more granular global
    Practice Focus (e.g. "Bebop Phrasing"). Voice mode pre-fills
    karaoke / lyric / vocal-performance focus options.
    """
    if not song_title:
        return

    # Always read the latest global values on entry so a change
    # elsewhere in the app (sidebar, another quick-control row) is
    # already reflected when this panel re-renders.
    try:
        from practice_setup_globals import (
            commit_widget_state_to_globals,
            get_active_instrument,
            get_active_level,
        )

        instrument = get_active_instrument(st.session_state) or instrument
        level = get_active_level(st.session_state) or level
    except ImportError:
        commit_widget_state_to_globals = None  # type: ignore[assignment]

    voice_mode = is_voice_instrument(instrument)
    header = practice_panel_kicker(instrument)

    inst_widget_key = f"_yt_practice_inst::{song_slug}"
    level_widget_key = f"_yt_practice_level::{song_slug}"
    focus_widget_key = f"_yt_practice_focus::{song_slug}"

    def _on_inst_change() -> None:
        if commit_widget_state_to_globals is None:
            return
        commit_widget_state_to_globals(
            st.session_state,
            instrument_widget_key=inst_widget_key,
        )

    def _on_level_change() -> None:
        if commit_widget_state_to_globals is None:
            return
        commit_widget_state_to_globals(
            st.session_state,
            level_widget_key=level_widget_key,
        )

    with st.expander(f"\U0001F4FA  {header}", expanded=expanded):
        if voice_mode:
            st.caption(
                "Karaoke, lyric, or vocal-performance videos matched to your "
                "current setup. Loads only after you ask."
            )
        else:
            st.caption(
                "Instrument / level / focus-aware learning videos for this song. "
                "The embedded player loads only after you click."
            )

        _opts_inst = list(instrument_options or [
            "Guitar",
            "Piano",
            "Saxophone",
            "Voice",
            "Bass",
            "Drums",
            "Trumpet",
        ])
        if instrument not in _opts_inst and instrument:
            _opts_inst = [instrument] + _opts_inst
        _opts_level = list(level_options or ["Beginner", "Intermediate", "Advanced"])

        # Pre-fill widget keys from the global values so the selectors
        # always render the current canonical Instrument / Level. This
        # is the "sync before render" half of the global-sync pattern.
        st.session_state[inst_widget_key] = (
            instrument if instrument in _opts_inst else _opts_inst[0]
        )
        st.session_state[level_widget_key] = (
            level if level in _opts_level else _opts_level[1]
        )

        c1, c2, c3 = st.columns([2, 2, 3])
        with c1:
            sel_instrument = st.selectbox(
                "Instrument",
                _opts_inst,
                key=inst_widget_key,
                on_change=_on_inst_change,
                help="Syncs across the whole app — sidebar, Practice, Backing Track, etc.",
            )
        with c2:
            sel_level = st.selectbox(
                "Level",
                _opts_level,
                key=level_widget_key,
                on_change=_on_level_change,
                help="Syncs across the whole app.",
            )
        with c3:
            focus_options = focus_options_for_instrument(sel_instrument)
            # Pre-select an option that loosely matches the active focus.
            default_idx = 0
            if focus:
                low = str(focus).strip().lower()
                for i, opt in enumerate(focus_options):
                    if opt.lower() == low or low in opt.lower() or opt.lower() in low:
                        default_idx = i
                        break
            # The YouTube Focus selector uses YouTube-search categories
            # (Chords / Strumming / Improvisation / ...) which are a
            # different set from the global Practice Focus, so it
            # stays panel-local on purpose.
            sel_focus = st.selectbox(
                "Focus",
                focus_options,
                index=default_idx,
                key=focus_widget_key,
                help="YouTube search filter — stays local to this video panel.",
            )

        # Persisted override URL (per-song).
        override_key = practice_video_override_key(song_slug)
        override_url = str(st.session_state.get(override_key, "") or "").strip()
        new_url = st.text_input(
            "Override YouTube URL (optional)",
            value=override_url,
            key=f"_yt_practice_url_input::{song_slug}",
            placeholder="https://www.youtube.com/watch?v=...",
            help="Paste a specific YouTube link to embed it directly instead of a search query.",
        )
        if new_url.strip() != override_url:
            st.session_state[override_key] = new_url.strip()
            override_url = new_url.strip()

        search_url = build_learning_search_url(
            song_title,
            artist,
            instrument=sel_instrument,
            level=sel_level,
            focus=sel_focus,
        )
        active_url = override_url if is_youtube_url(override_url) else search_url

        # Show the query summary so the user understands what we'll
        # search for if they click "Open YouTube".
        st.caption(
            "Searching: **"
            + describe_search_query(
                song_title,
                artist,
                instrument=sel_instrument,
                level=sel_level,
                focus=sel_focus,
                mode="learning",
            )
            + "**"
        )

        button_label = (
            "\U0001F3A4  Find karaoke / lyric video"
            if voice_mode and not is_youtube_url(override_url)
            else "\u25B6  Open on YouTube"
        )
        st.markdown(
            _link_button_html(button_label, active_url),
            unsafe_allow_html=True,
        )

        # Lazy embed when the user pasted a specific video URL.
        if is_youtube_url(override_url):
            embed = embed_url_for(override_url)
            thumb = thumbnail_url_for(override_url)
            if thumb:
                st.markdown(
                    f'<img class="ui-youtube-thumb" src="{html.escape(thumb)}" '
                    f'alt="YouTube preview thumbnail">',
                    unsafe_allow_html=True,
                )
            if embed:
                _render_embed(st, embed=embed, slug=song_slug, panel="practice")
