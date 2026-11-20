"""Home presentation policy; never clear musical state or unmount working widgets."""
PAGES_COLLAPSED = 'studio_sidebar_nav_collapsed'
LAST_PAGE = '_music_sidebar_policy_page'


def apply_page_defaults(session, page):
    """Resolve whether the sidebar PAGES list shows collapsed, and own that state.

    This is the single authority for ``studio_sidebar_nav_collapsed``; the only other
    writers are the user's own controls (the ``◀`` collapse triangle and the
    "Pages" expand buttons), which this function must never override.

    Navigating does not change the user's choice: expanded stays expanded and a
    manual collapse stays collapsed while moving among non-Home pages. Home is the
    one exception - arriving at Home always opens the list - and an ordinary rerun
    on the page we are already on changes nothing at all.
    """
    page = str(page or 'home').strip().lower()
    if session.get(LAST_PAGE) != page:
        session[LAST_PAGE] = page
        if page == 'home':
            session[PAGES_COLLAPSED] = False
        elif PAGES_COLLAPSED not in session:
            # First non-Home page of the session and the user has expressed no
            # preference yet: start collapsed, as the studio always has.
            session[PAGES_COLLAPSED] = True
    return bool(session.get(PAGES_COLLAPSED, page != 'home'))


def home_sidebar_css(page):
    # Keep controls mounted with their original widget keys. Streamlit's widget
    # cleanup therefore cannot delete hidden Instrument/Level/Key/Focus values.
    if str(page).strip().lower() == 'home':
        return '<style>.st-key-music_working_sidebar {display:none !important;}</style>'
    return ''


class SidebarTarget:
    """Supply a scoped sidebar to existing control renderers without altering st."""
    def __init__(self, st, sidebar):
        self._st = st
        self.sidebar = sidebar

    def __getattr__(self, name):
        return getattr(self._st, name)
