"""Home presentation policy; never clear musical state or unmount working widgets."""
PAGES_COLLAPSED = 'studio_sidebar_nav_collapsed'
LAST_PAGE = '_music_sidebar_policy_page'


def apply_page_defaults(session, page):
    page = str(page or 'home').strip().lower()
    if session.get(LAST_PAGE) != page:
        session[PAGES_COLLAPSED] = page != 'home'
        session[LAST_PAGE] = page
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
