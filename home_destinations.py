"""Home page destinations - where each card goes and what it is allowed to touch.

Home is a *signpost*. Arriving on it, or clicking through it, must never alter the
musician's authoritative musical state: the active song identity, the instrument,
the Practice/concert key, the written or shape key, backing ownership, or any
chart. Everything here therefore routes through the established contracts -
``app_ui.navigate_studio_page`` for the page, and
``studio_nav_history.apply_creative_history_destination`` for the Creative Lab
workspace - and nothing else.

Home discovery requests establish an intentional Catalog browsing view. Search,
genres and favorites are reset for that request without committing a music source.
Key Cycling requests expanded controls without arming playback.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

HOME_PAGE_ID = "home"

#: Session keys Home must never write. Enforced by tests/test_home_destinations.py.
PROTECTED_STATE_KEYS: frozenset[str] = frozenset(
    {
        "selected_song",
        "active_catalog_pick",
        "active_catalog_pick_key",
        "active_song_state",
        "active_music_source",
        "song_picker_active_source",
        "explicit_catalog_pick_committed",
        "pending_matching_song_dropdown",
        "instrument",
        "display_key",
        "concert_key",
        "concert_practice_key",
        "custom_home_key",
        "chart_in_instrument_key",
        "selected_transposing_instrument",
        "capo_fret",
        "backing_owner",
        "backing_context",
        "sections",
        "song_sections",
    }
)


@dataclass(frozen=True)
class HomeDestination:
    """One Home card. ``page`` is always a real studio page id."""

    key: str
    page: str
    title: str
    blurb: str
    kicker: str = ""
    cta: str = "Open"
    #: Creative Lab workspace, e.g. ``creative::Missions`` or ``creative::SBI``.
    creative_dest: str = ""
    #: Browse genre pill to tick on the Songs page (view filter only).
    genre: str = ""


# Hero - the two things a musician most often wants on arrival.
HERO_ACTIONS: tuple[HomeDestination, ...] = (
    HomeDestination(
        key="hero_practice",
        page="practice",
        title="Start practicing",
        blurb="Open the practice workspace.",
        cta="Start practicing",
    ),
    HomeDestination(
        key="hero_songs",
        page="picker",
        title="Find a song",
        blurb="Browse the catalog.",
        cta="Find a song",
    ),
)

# "What would you like to do?" - the four main journeys.
JOURNEY_CARDS: tuple[HomeDestination, ...] = (
    HomeDestination(
        key="journey_practice",
        page="practice",
        kicker="Build confidence",
        title="Practice & improve",
        blurb="Make every practice session count - songs, notation, guided exercises and technique.",
        cta="Open Practice",
    ),
    HomeDestination(
        key="journey_backing",
        page="backing",
        kicker="Find your groove",
        title="Play with backing tracks",
        blurb="Rehearse with musical accompaniment and shape the feel, tempo and sections.",
        cta="Open Backing",
    ),
    HomeDestination(
        key="journey_multitrack",
        page="multitrack",
        kicker="Hear your progress",
        title="Record & multitrack",
        blurb="Layer your parts, listen more closely, and build a performance one take at a time.",
        cta="Open Multitrack",
    ),
    HomeDestination(
        key="journey_composer",
        page="composer",
        kicker="Follow an idea",
        title="Create & compose",
        blurb="Write your own songs, shape harmony and explore fresh musical directions.",
        cta="Open Composition",
    ),
)

# "Let the music lead" - genre doorways into Browse.
DISCOVER_CARDS: tuple[HomeDestination, ...] = (
    HomeDestination(
        key="discover_pop",
        page="picker",
        kicker="The songs you love",
        title="Explore Pop",
        blurb="Discover familiar songs and make them your own.",
        cta="Explore Pop songs",
        genre="Pop",
    ),
    HomeDestination(
        key="discover_jazz",
        page="picker",
        kicker="The art of improvisation",
        title="Explore Jazz",
        blurb="Explore harmony, standards and new ideas.",
        cta="Explore Jazz songs",
        genre="Jazz",
    ),
)

BROWSE_ALL = HomeDestination(
    key="discover_all",
    page="picker",
    title="Browse entire catalog",
    blurb="Browse every song in the catalog.",
    cta="Browse entire catalog",
)

# "More ways to grow" - the remaining workflows, each to its own workspace.
MORE_CARDS: tuple[HomeDestination, ...] = (
    HomeDestination(
        key="more_missions",
        page="creative",
        title="Missions & exercises",
        blurb="Practice with a purpose.",
        cta="Open Missions",
        creative_dest="creative::Missions",
    ),
    HomeDestination(
        key="more_sbi",
        page="creative",
        title="Song-Aware Coaching",
        blurb="Improvise in song context.",
        cta="Open Song-Aware Coaching",
        creative_dest="creative::Song-Aware Coaching",
    ),
    HomeDestination(
        key="more_keycycle",
        page="backing",
        title="Key Cycling",
        blurb="Build fluency in more keys.",
        cta="Open Key Cycling",
    ),
    HomeDestination(
        key="more_custom",
        page="custom",
        title="Custom Progressions",
        blurb="Shape your own harmony.",
        cta="Open Custom Progressions",
    ),
    HomeDestination(
        key="more_analysis",
        page="analysis",
        title="Upload Analysis",
        blurb="Reflect on a recording.",
        cta="Open Upload Analysis",
    ),
    HomeDestination(
        key="more_log",
        page="log",
        title="Practice Log",
        blurb="See how far you have come.",
        cta="Open Practice Log",
    ),
)


def all_destinations() -> tuple[HomeDestination, ...]:
    """Every navigable card on Home, in render order."""
    return HERO_ACTIONS + JOURNEY_CARDS + DISCOVER_CARDS + (BROWSE_ALL,) + MORE_CARDS


def destination_by_key(key: str) -> HomeDestination | None:
    want = str(key or "").strip()
    for dest in all_destinations():
        if dest.key == want:
            return dest
    return None



def apply_home_navigation(
    session_state: Any,
    destination: HomeDestination,
    *,
    navigate: Callable[[Any, str], bool] | None = None,
) -> bool:
    """Route a Home card click. Returns True when the page actually changed.

    Changes route, tool-selection and browsing-view state. Explicit clicks also
    clear automatic-rerun diagnostics. Musical ownership and keys are preserved.
    """
    nav = navigate
    if nav is None:
        from app_ui import navigate_studio_page as _nav

        nav = _nav

    # A fresh button press is new intent, even when it repeats a destination.
    # Otherwise the third Home -> Songs visit has the same restore fingerprint
    # and the automatic-rerun guard mistakes deliberate navigation for a loop.
    from music_rerun_loop_guard import clear_rerun_loop_block
    clear_rerun_loop_block(session_state)
    changed = bool(nav(session_state, destination.page))

    if destination.creative_dest:
        from studio_nav_history import apply_creative_history_destination, clear_creative_history_seal
        clear_creative_history_seal(session_state)
        session_state.pop("_pending_history_creative_dest", None)
        apply_creative_history_destination(session_state, destination.creative_dest)
        # Commit the real tool selectors so the next Creative hydration cannot
        # restore a previous tool over this explicit Home request.
        if destination.key == "more_sbi":
            from studio_page_state import request_song_aware_coaching
            request_song_aware_coaching(session_state, reason="home_song_aware_coaching")
        else:
            from creative_tab_tool_persistence import commit_creative_selector_to_canonical
            for field, value in (
                ("creative_lab_analysis_mode", "Improvisation Intelligence"),
                ("creative_lab_last_mode", "Improvisation Intelligence"),
                ("improv_intelligence_tab", destination.creative_dest.split("::", 1)[1]),
            ):
                commit_creative_selector_to_canonical(session_state, field, value, reason="home_navigation")

    if destination.page == "picker":
        # This is a view request, never a source-selection intent.
        session_state["_home_catalog_browse"] = True
        session_state["_home_catalog_request"] = destination.genre or "all"
    if destination.key == "more_keycycle":
        session_state["_home_open_key_cycle"] = True

    return changed


__all__ = (
    "HOME_PAGE_ID",
    "PROTECTED_STATE_KEYS",
    "HomeDestination",
    "HERO_ACTIONS",
    "JOURNEY_CARDS",
    "DISCOVER_CARDS",
    "BROWSE_ALL",
    "MORE_CARDS",
    "all_destinations",
    "destination_by_key",
    "apply_home_navigation",
)
