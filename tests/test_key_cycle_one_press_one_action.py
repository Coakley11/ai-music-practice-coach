"""One press of Next, Previous or Pause is one action, however late its events are handled.

Browser diagnosis 2026-11-18 (navdiag_fix_1 / navdiag_dev_1, 390 px, dev 3e5ace51 and the KC candidate):
a press reaches the page as pointerdown, (mousedown,) click. Next/Previous stepped on pointerdown and
ignored the rest of the press only within 1200 ms of it; Pause ignored repeats only within 500 ms. A press
held a little longer, or a click handled late on a busy phone, therefore counted twice: one Next with
1.5 s between press and release moved two keys on both builds (server jumped E -> F#). A press is now
recognised by its identity -- its own events belong to it however late they come -- not by a time window.

The real bridge runs on a test origin with the console's real buttons; presses are dispatched as the
browser dispatches them. Counted: navigation steps (the navigator's sequence) and Pause/Resume actions.
"""
from __future__ import annotations

import json
import unittest

import backing_key_cycle as kc
from tests.test_key_cycle_pause_reports_sounding_key import _RUNNING, _silent_wav

_PARENT = (
    '<html><body>'
    + ''.join(f'<span class="ui-key-cycle-chip" data-key="{k}"></span>' for k in ("Bm", "Em", "Am", "Dm", "Gm", "Cm"))
    + '<div class="st-key-backing_key_cycle_prev_btn"><button><p>Previous</p></button></div>'
    + '<div class="st-key-backing_key_cycle_pause_btn"><button><p>Pause</p></button></div>'
    + '<div class="st-key-backing_key_cycle_advance_btn"><button><p>Next</p></button></div>'
    + '<div id="elsewhere" style="height:40px"></div>'
    + '<iframe id="kc-bridge"></iframe></body></html>'
)
_SEL = {"next": ".st-key-backing_key_cycle_advance_btn button", "prev": ".st-key-backing_key_cycle_prev_btn button",
        "pause": ".st-key-backing_key_cycle_pause_btn button"}

# One press as the browser dispatches it. ``hold`` ms between press and release, either a real wait
# (other tasks run) or a long task (``busy``: nothing else runs, as on a saturated page). ``click_after``
# ms between release and click (a touch tap's click comes in a later task). ``up_outside``: released
# off the button (no click follows). ``probe``: pointerdown + mousedown + element.click() in one task,
# the way the Mission real-app probe presses.
_PRESS_JS = r"""async (a) => {
  const b = document.querySelector(a.sel);
  const o = (x) => Object.assign({bubbles: true, cancelable: true, composed: true, button: 0, pointerId: a.pid || 1,
                                  pointerType: a.kind === 'touch' ? 'touch' : 'mouse', isPrimary: true}, x || {});
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  const spin = (ms) => { const e = performance.now() + ms; while (performance.now() < e) {} };
  if (a.kind === 'keyboard') {
    b.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true, cancelable: true}));
    if (a.click_too) b.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, detail: 0}));
    b.dispatchEvent(new KeyboardEvent('keyup', {key: 'Enter', bubbles: true, cancelable: true}));
    return true;
  }
  if (a.kind === 'kbclick') {  // Enter on a focused button: keydown, its click, keyup
    b.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true, cancelable: true}));
    b.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, detail: 0}));
    b.dispatchEvent(new KeyboardEvent('keyup', {key: 'Enter', bubbles: true, cancelable: true}));
    return true;
  }
  if (a.kind === 'code') { window.__kcPressCycleTransport(); return true; }  // the Lead Sheet's Pause/Resume
  b.dispatchEvent(new PointerEvent('pointerdown', o()));
  if (a.kind === 'mouse' || a.kind === 'probe') b.dispatchEvent(new MouseEvent('mousedown', o()));
  if (a.busy) spin(a.hold || 0); else if (a.hold) await wait(a.hold);
  if (a.kind === 'probe') { b.click(); return true; }
  const up = a.up_outside ? document.getElementById('elsewhere') : b;
  up.dispatchEvent(new PointerEvent('pointerup', o()));
  if (a.kind === 'mouse') up.dispatchEvent(new MouseEvent('mouseup', o()));
  if (a.up_outside || a.no_click) return true;
  if (a.click_after) await wait(a.click_after);
  b.dispatchEvent(new MouseEvent('click', o({detail: 1})));
  return true;
}"""
_COUNT_JS = """() => ({steps: Number((window.__kcNav || {}).seq || 0), pauses: Number(window.__kcPauseApplies || 0),
                       reports: (window.__reports || []).length, streamlit: Number(window.__streamlitClicks || 0)})"""
# The card's command channel (how Python hears of a console Pause/Resume) and the Streamlit button's own
# click handler (a click reaching it toggles the cycle in Python a second time).
_STUBS_JS = """() => { window.__reports = []; window.__streamlitClicks = 0;
  window.__backingTransportReportWin = window;
  window.__backingTransportReport = (kind) => { window.__reports.push(kind); return true; };
  document.querySelector('.st-key-backing_key_cycle_pause_btn button')
    .addEventListener('click', () => { window.__streamlitClicks += 1; }); }"""

# name -> list of presses (each a _PRESS_JS argument with ``ctl`` and ``gap`` ms before it)
_SCENARIOS = {
    "next_quick_mouse": [dict(ctl="next", kind="mouse", hold=60)],
    "next_slow_release_long_task": [dict(ctl="next", kind="mouse", hold=1500, busy=True)],
    "next_held_5s": [dict(ctl="next", kind="mouse", hold=5000)],
    "next_touch_click_late": [dict(ctl="next", kind="touch", hold=80, click_after=1500)],
    "next_probe_style_slow": [dict(ctl="next", kind="probe", hold=1500, busy=True)],
    "next_three_quick_presses": [dict(ctl="next", kind="mouse", hold=40),
                                 dict(ctl="next", kind="mouse", hold=40, gap=250),
                                 dict(ctl="next", kind="mouse", hold=40, gap=250)],
    "next_keyboard": [dict(ctl="next", kind="kbclick")],
    "next_released_off_then_keyboard": [dict(ctl="next", kind="mouse", hold=60, up_outside=True),
                                        dict(ctl="next", kind="kbclick", gap=300)],
    "next_touch_left_open_then_keyboard": [dict(ctl="next", kind="touch", hold=80, no_click=True),
                                           dict(ctl="next", kind="kbclick", gap=300)],
    "prev_quick_mouse": [dict(ctl="prev", kind="mouse", hold=60)],
    "prev_slow_release_long_task": [dict(ctl="prev", kind="mouse", hold=1500, busy=True)],
    "pause_quick_mouse": [dict(ctl="pause", kind="mouse", hold=60)],
    "pause_slow_release_long_task": [dict(ctl="pause", kind="mouse", hold=2000, busy=True)],
    "pause_touch_click_late": [dict(ctl="pause", kind="touch", hold=80, click_after=2000)],
    "pause_two_presses": [dict(ctl="pause", kind="mouse", hold=60), dict(ctl="pause", kind="mouse", hold=60, gap=900)],
    "pause_touch_left_open_then_lead_sheet": [dict(ctl="pause", kind="touch", hold=80, no_click=True),
                                              dict(ctl="pause", kind="code", gap=900)],
    "pause_keyboard_enter": [dict(ctl="pause", kind="keyboard", click_too=True)],
}


def _run_scenarios() -> dict:
    try:
        from playwright import sync_api
    except Exception:  # pragma: no cover - browser tooling not installed
        raise unittest.SkipTest("playwright not installed")
    wav = _silent_wav()
    bridge = kc.cycle_persistent_player_bridge_html(cmd_json=json.dumps(_RUNNING))

    def handle(route):
        if route.request.url.endswith(".wav"):
            route.fulfill(status=200, body=wav, headers={"Content-Type": "audio/wav", "Content-Length": str(len(wav))})
        else:
            route.fulfill(status=200, content_type="text/html", body=_PARENT)

    out, errors = {}, []
    with sync_api.sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--autoplay-policy=no-user-gesture-required"])
        try:
            page = browser.new_page()
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.route("http://kc.test/**", handle)
            page.goto("http://kc.test/app/")
            page.evaluate("(html) => { document.getElementById('kc-bridge').srcdoc = html; }", bridge)
            page.wait_for_function("() => typeof window.__kcStepBtnHandler === 'function'"
                                   " && typeof window.__kcPauseBtnHandler === 'function' && window.__kcCaptureBound",
                                   timeout=15000)
            page.wait_for_timeout(1500)
            page.evaluate(_STUBS_JS)
            for name, presses in _SCENARIOS.items():
                before = page.evaluate(_COUNT_JS)
                for pr in presses:
                    page.wait_for_timeout(int(pr.get("gap", 0)))
                    page.evaluate(_PRESS_JS, dict(pr, sel=_SEL[pr["ctl"]]))
                page.wait_for_timeout(700)  # past every remaining window, so the next scenario starts clean
                after = page.evaluate(_COUNT_JS)
                out[name] = {k: after[k] - before[k] for k in after}
            out["_end_bound"] = page.evaluate("() => !!window.__kcGestureEndBound")
        finally:
            browser.close()
    out["_errors"] = errors
    return out


class OnePressIsOneAction(unittest.TestCase):
    got: dict = {}

    @classmethod
    def setUpClass(cls) -> None:
        cls.got = _run_scenarios()

    def _is(self, name: str, steps: int, pauses: int = 0) -> None:
        # Every console Pause/Resume reaches Python once, through the card channel, never also
        # through the Streamlit button.
        want = {"steps": steps, "pauses": pauses, "reports": pauses, "streamlit": 0}
        self.assertEqual(self.got[name], want, (name, self.got))

    def test_no_page_errors(self) -> None:
        self.assertEqual(self.got["_errors"], [], self.got["_errors"])

    def test_the_press_end_listeners_run_in_the_page(self) -> None:
        # Installed by eval in the page's main world; a script error there would be swallowed.
        self.assertTrue(self.got.get("_end_bound"), self.got)

    # Next
    def test_a_quick_next_steps_once(self) -> None:
        self._is("next_quick_mouse", 1)

    def test_a_next_released_after_a_long_task_steps_once(self) -> None:
        self._is("next_slow_release_long_task", 1)

    def test_a_next_held_for_5_s_steps_once(self) -> None:
        self._is("next_held_5s", 1)

    def test_a_tapped_next_whose_click_comes_late_steps_once(self) -> None:
        self._is("next_touch_click_late", 1)

    def test_a_scripted_press_and_click_in_one_slow_task_steps_once(self) -> None:
        self._is("next_probe_style_slow", 1)

    def test_three_quick_genuine_presses_step_three_times(self) -> None:
        self._is("next_three_quick_presses", 3)

    def test_a_keyboard_next_steps_once(self) -> None:
        self._is("next_keyboard", 1)

    def test_a_press_released_off_the_button_does_not_swallow_the_next_keyboard_press(self) -> None:
        self._is("next_released_off_then_keyboard", 2)

    def test_a_touch_press_that_never_clicked_does_not_swallow_a_keyboard_next(self) -> None:
        self._is("next_touch_left_open_then_keyboard", 2)

    # Previous
    def test_a_quick_previous_steps_once(self) -> None:
        self._is("prev_quick_mouse", 1)

    def test_a_previous_released_after_a_long_task_steps_once(self) -> None:
        self._is("prev_slow_release_long_task", 1)

    # Pause
    def test_a_quick_pause_toggles_once(self) -> None:
        self._is("pause_quick_mouse", 0, 1)

    def test_a_pause_released_after_a_long_task_toggles_once(self) -> None:
        self._is("pause_slow_release_long_task", 0, 1)

    def test_a_tapped_pause_whose_click_comes_late_toggles_once(self) -> None:
        self._is("pause_touch_click_late", 0, 1)

    def test_two_genuine_pause_presses_toggle_twice(self) -> None:
        self._is("pause_two_presses", 0, 2)

    def test_the_lead_sheet_resume_works_after_a_touch_press_that_never_clicked(self) -> None:
        self._is("pause_touch_left_open_then_lead_sheet", 0, 2)

    def test_a_keyboard_pause_toggles_once(self) -> None:
        self._is("pause_keyboard_enter", 0, 1)


if __name__ == "__main__":
    unittest.main()
