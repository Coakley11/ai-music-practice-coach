"""Home page destinations - where each card goes and what it is allowed to touch.

Home is a *signpost*. Arriving on it, or clicking through it, must never alter the
musician's authoritative musical state: the active song identity, the instrument,
the Practice/concert key, the written or shape key, backing ownership, or any
chart. Everything here therefore routes through the established contracts -
``app_ui.navigate_studio_page`` for the page, and
``studio_nav_history.apply_creative_history_destination`` for the Creative Lab
workspace - and nothing else.

The one exception is a Browse *view* filter: "Explore Jazz" ticks the Jazz genre
pill on the Songs page, which is the same page-local, user-owned filter the pills
themselves write. It selects nothing and activates no song.
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
    blurb="Open the Songs page with no filters applied.",
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
        creative_dest="creative::SBI",
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


def _apply_genre_filter(session_state: Any, genre: str) -> None:
    """Tick one Browse genre pill - the same page-local view filter the pills write."""
    try:
        from songs.picker_session import WORKSPACE_GENRE_FILTERS_KEY
    except ImportError:
        return
    current = [str(g) for g in (session_state.get(WORKSPACE_GENRE_FILTERS_KEY) or []) if g]
    if genre not in current:
        current.append(genre)
    session_state[WORKSPACE_GENRE_FILTERS_KEY] = current
    session_state["_genre_filters_user_touched"] = True


def apply_home_navigation(
    session_state: Any,
    destination: HomeDestination,
    *,
    navigate: Callable[[Any, str], bool] | None = None,
) -> bool:
    """Route a Home card click. Returns True when the page actually changed.

    Writes exactly three kinds of state and nothing else: the studio page (through
    the normal navigation entrypoint), the Creative Lab workspace selection, and
    an optional Browse genre view filter.
    """
    nav = navigate
    if nav is None:
        from app_ui import navigate_studio_page as _nav

        nav = _nav

    changed = bool(nav(session_state, destination.page))

    if destination.creative_dest:
        try:
            from studio_nav_history import apply_creative_history_destination

            apply_creative_history_destination(session_state, destination.creative_dest)
        except ImportError:
            pass

    if destination.genre:
        _apply_genre_filter(session_state, destination.genre)

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
