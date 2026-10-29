"""The Backing card's key / BPM / transport row stays put through Play, Pause, Resume, Stop.

Browser acceptance (Just the Two of Us, 1500 / 1280 / 1024 / 820 / 390 px):
- Stop + Pause wrapped onto two lines (and "Paused" onto a third) inside the
  row's fixed 76 px, so the frame grew to 110-163 px: key and BPM re-centred
  27-43 px lower and the Pause / Stop buttons were cut off.
- With the sidebar open a 1024 px window left the columns 96-177 px wide; the
  row only stacked below a 720 px *window*, so the key row overflowed at idle.
- The first rerun after a restore removed the inline "Welcome back" notice,
  pulling the whole card up 56-72 px (and remounting the blocks above it).
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRANSPORT = (ROOT / "backing_transport_component" / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "app_ui.py").read_text(encoding="utf-8")


def test_transport_stays_on_one_line() -> None:
    assert "#wrap { display: flex; flex-wrap: nowrap;" in TRANSPORT
    assert "flex-wrap: wrap" not in TRANSPORT
    # No fixed minimum widths that force a second line in a narrow column.
    assert "min-width: 210px" not in TRANSPORT and "min-width: 120px" not in TRANSPORT
    # The phone rule that made each button 100 % wide (one per line) is gone.
    assert "#btn, #pz { width: 100%" not in TRANSPORT


def test_backing_track_suffix_drops_when_two_buttons_share_the_line() -> None:
    assert 'body[data-pair="1"] .ext { display: none; }' in TRANSPORT
    assert 'document.body.dataset.pair = showPz ? "1" : "";' in TRANSPORT
    assert "setLabel(btn, state === \"stopped\" ? LABEL_PLAY : LABEL_STOP);" in TRANSPORT
    assert "setLabel(pz, state === \"paused\" ? LABEL_RESUME : LABEL_PAUSE);" in TRANSPORT
    # Full label stays the accessible name.
    assert 'el.setAttribute("aria-label", label);' in TRANSPORT


def test_paused_hint_never_adds_a_line() -> None:
    assert 'body[data-pair="1"] #hint { position: absolute;' in TRANSPORT
    assert 'aria-live="polite"' in TRANSPORT


def test_row_stacks_by_the_main_column_width() -> None:
    assert '[data-testid="stMainBlockContainer"]:has(.st-key-backing_card_controls) {' in CSS
    assert "container: backing-main / inline-size;" in CSS
    assert "@container backing-main (max-width: 800px) {" in CSS
    i = CSS.index("@container backing-main (max-width: 800px) {")
    block = CSS[i:i + 1600]
    assert "height: 184px !important;" in block and "flex-direction: column;" in block


def test_transport_column_has_a_fixed_width_in_one_row() -> None:
    i = CSS.index('[data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(3) {')
    rule = CSS[i:i + 200]
    assert "flex: 0 0 224px !important;" in rule


class _St:
    def __init__(self, state: dict) -> None:
        self.session_state = state
        self.calls: list[tuple[str, str]] = []

    def warning(self, msg):
        self.calls.append(("warning", msg))

    def success(self, msg):
        self.calls.append(("success", msg))

    def toast(self, msg, icon=None):
        self.calls.append(("toast", msg))


def test_restore_notice_is_a_toast_not_a_page_block() -> None:
    import suite_user_persistence as sp

    st = _St({sp._SESSION_CLOUD_BANNER_KEY: True})
    sp.show_persistence_messages(st)
    assert st.calls == [("toast", sp.SUITE_SESSION_RESTORE_WELCOME_MESSAGE)]

    st = _St({sp._SESSION_BANNER_KEY: "Reset to defaults"})
    sp.show_persistence_messages(st)
    assert st.calls == [("toast", "Reset to defaults")]

    # A problem with the saved state still needs reading in place.
    st = _St({sp._SESSION_INVALID_WARN_KEY: "Saved settings were invalid"})
    sp.show_persistence_messages(st)
    assert st.calls == [("warning", "Saved settings were invalid")]


APP = (ROOT / "streamlit_music_practice_app.py").read_text(encoding="utf-8")


def test_card_and_banner_slots_keep_the_last_render_during_a_run() -> None:
    # st.empty() blanked the card (and the "Backing source" banner) until the
    # run reached them -- seconds while Play synthesized -- so the page jumped
    # 300-500 px and back. A container keeps the previous children until replaced.
    i = APP.index("def _create_backing_card_slots()")
    body = APP[i:i + 1200]
    assert "head = st.container()" in body and "head = st.empty()" not in body
    assert "_backing_banner_slot = st.container()" in APP
    assert "_backing_banner_slot = st.empty()" not in APP


def test_scroll_script_never_adds_a_gap_above_the_page() -> None:
    anchors = (ROOT / "studio_scroll_anchors.py").read_text(encoding="utf-8")
    assert '<script data-studio-scroll-anchor="1">' in anchors
    i = CSS.index('[data-testid="stElementContainer"]:has(> iframe[srcdoc*="data-studio-scroll-anchor"]) {')
    rule = CSS[i:i + 220]
    assert "position: absolute !important;" in rule
    # Out of flow, still rendered: never display:none (its timer must run).
    assert "display: none" not in rule
