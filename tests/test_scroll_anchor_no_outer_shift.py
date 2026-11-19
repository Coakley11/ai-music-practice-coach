"""P0 2026-11-19: a queued page anchor must scroll Streamlit's page scroller only, never shift the whole app.

The user's browser (and a local reproduction at 1500 / 1366 px) showed a strip of music at the top of the
screen and blank white below it for the rest of the song, with no wheel or scrollbar able to bring the page
back. Cause: after Play the Backing page queues ANCHOR_BACKING_FOLLOW_ALONG; the one-shot script called
``scrollIntoView({block: 'start'})`` while the Lead Sheet was still mounting, the anchor could not reach the top
of stMain, and the browser scrolled the next box up -- ``stAppViewContainer`` (overflow hidden) -- shifting the
sidebar and the page together, permanently. The script now scrolls stMain to the anchor (clamped to what it can
scroll) and undoes any shift of stMain's ancestors.
"""
from __future__ import annotations

import studio_scroll_anchors as ssa


class _Slot:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _FakeSt:
    def __init__(self, anchor: str) -> None:
        self.session_state = {ssa.PENDING_SCROLL_ANCHOR_KEY: anchor}
        self.html = ""

    def container(self, key=None):
        return _Slot()


def _script(anchor: str = ssa.ANCHOR_BACKING_FOLLOW_ALONG) -> str:
    import streamlit.components.v1 as components

    fake = _FakeSt(anchor)
    captured: dict[str, str] = {}
    orig = components.html
    try:
        components.html = lambda body, height=0, **kw: captured.setdefault("body", body)  # type: ignore[assignment]
        ssa.render_pending_scroll_script(fake)
    finally:
        components.html = orig  # type: ignore[assignment]
    return captured.get("body", "")


def test_the_page_anchor_scrolls_stmain_not_its_ancestors() -> None:
    js = _script()
    assert js, "a queued anchor renders its script"
    assert 'doc.querySelector(\'[data-testid="stMain"]\')' in js
    assert "sc.scrollTo({ top: Math.max(0, Math.min(top, max)), behavior: 'smooth' })" in js
    # scrollIntoView only for an element outside stMain (a non-Streamlit host), and never 'start' -- the call that
    # shifted stAppViewContainer.
    assert "block: 'start'" not in js
    assert js.count("scrollIntoView(") == 1
    assert "} else {\n                  el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });" in js


def test_an_existing_shift_of_the_app_is_undone() -> None:
    js = _script()
    assert "for (let n = sc && sc.parentElement; n && n !== doc.documentElement; n = n.parentElement) {" in js
    assert "if (n.scrollTop) n.scrollTop = 0;" in js
    assert "unshift(doc, sc);" in js


def test_nothing_queued_renders_no_script() -> None:
    fake = _FakeSt("")
    fake.session_state = {}
    ssa.render_pending_scroll_script(fake)  # no exception, no script
