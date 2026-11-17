"""The shared selectable-button control: same keys, labels and callbacks; never empty."""
from __future__ import annotations

import unittest
from pathlib import Path

import segmented_selector as sel

ROOT = Path(__file__).resolve().parents[1]


class FakeSt:
    def __init__(self, returns=None, has_control=True, required_ok=True):
        self.session_state: dict = {}
        self.returns = returns
        self.calls = []
        self.required_ok = required_ok
        if not has_control:
            self.segmented_control = None

    def markdown(self, *a, **k):
        pass

    def segmented_control(self, label, options, **kw):  # noqa: D401 - mimics Streamlit
        if "required" in kw and not self.required_ok:
            raise TypeError("required")
        self.calls.append(("segmented", label, list(options), kw))
        return self.returns(self.session_state) if callable(self.returns) else self.returns

    def radio(self, label, options, **kw):
        self.calls.append(("radio", label, list(options), kw))
        return self.session_state.get(kw["key"]) or options[0]


OPTS = ["Song-Based Improvisation", "Style Jam Mode", "Jam Session Generator"]


class Behaviour(unittest.TestCase):
    def test_returns_the_click_and_keeps_key_labels_and_callback(self):
        st = FakeSt(returns="Style Jam Mode")
        cb = object()
        fmt = lambda v: "🎷 " + v  # noqa: E731
        got = sel.render_segmented_selector(st, st.session_state, label="Mode", options=OPTS,
                                            key="improv_entry_mode", format_func=fmt, on_change=cb)
        self.assertEqual(got, "Style Jam Mode")
        kind, _label, opts, kw = st.calls[0]
        self.assertEqual(kind, "segmented")
        self.assertEqual(opts, OPTS)
        self.assertEqual(kw["key"], "improv_entry_mode")
        self.assertIs(kw["format_func"], fmt)
        self.assertIs(kw["on_change"], cb)
        self.assertTrue(kw["required"])

    def test_never_empty_a_deselect_keeps_the_last_choice(self):
        st = FakeSt(returns="Jam Session Generator")
        sel.render_segmented_selector(st, st.session_state, label="M", options=OPTS, key="k")
        st.returns = None
        self.assertEqual(sel.render_segmented_selector(st, st.session_state, label="M", options=OPTS, key="k"),
                         "Jam Session Generator")

    def test_first_render_is_seeded_so_a_segment_is_selected(self):
        st = FakeSt(returns=lambda ss: ss.get("k"))
        self.assertEqual(sel.render_segmented_selector(st, st.session_state, label="M", options=OPTS, key="k"), OPTS[0])
        self.assertEqual(st.session_state["k"], OPTS[0])

    def test_two_bars_do_not_share_memory(self):
        st = FakeSt(returns="Style Jam Mode")
        sel.render_segmented_selector(st, st.session_state, label="A", options=OPTS, key="a")
        st.returns = "Verse"
        sel.render_segmented_selector(st, st.session_state, label="B", options=["Full Song", "Verse"], key="b")
        self.assertEqual(st.session_state[sel.memory_key("a")], "Style Jam Mode")
        self.assertEqual(st.session_state[sel.memory_key("b")], "Verse")

    def test_a_stale_stored_value_falls_back_to_a_real_option(self):
        st = FakeSt(returns=lambda ss: ss.get("k"))
        st.session_state["k"] = "Bridge 3 (gone)"
        self.assertEqual(sel.render_segmented_selector(st, st.session_state, label="M", options=OPTS, key="k"), OPTS[0])

    def test_older_streamlit_without_required_still_works(self):
        st = FakeSt(returns="Style Jam Mode", required_ok=False)
        self.assertEqual(sel.render_segmented_selector(st, st.session_state, label="M", options=OPTS, key="k"),
                         "Style Jam Mode")

    def test_without_segmented_control_it_is_the_old_radio(self):
        st = FakeSt(has_control=False)
        sel.render_segmented_selector(st, st.session_state, label="M", options=OPTS, key="k")
        self.assertEqual(st.calls[0][0], "radio")

    def test_css_is_scoped_to_the_widget_and_wraps(self):
        css = sel.selector_css("backing_track_scope")
        self.assertIn(".st-key-backing_track_scope", css)
        self.assertIn("flex-wrap: wrap", css)


class TheThreeBarsUseIt(unittest.TestCase):
    def test_creative_entry_modes(self):
        src = (ROOT / "improvisation_intelligence_ui.py").read_text(encoding="utf-8")
        i = src.index('key="improv_entry_mode"')
        self.assertIn("render_segmented_selector(", src[i - 400:i])
        self.assertIn("format_func=creative_tool_display_label", src[i:i + 200])

    def test_practice_section_focus(self):
        src = (ROOT / "app_ui.py").read_text(encoding="utf-8")
        i = src.index("def render_section_jump_bar(")
        body = src[i:src.index("\ndef ", i + 10)]
        self.assertIn("render_segmented_selector(", body)
        self.assertNotIn("st.radio(", body)

    def test_backing_playback_scope(self):
        src = (ROOT / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
        i = src.index('key="backing_track_scope"')
        self.assertIn("render_segmented_selector(", src[i - 400:i])
        self.assertIn("on_change=_on_backing_filter_change", src[i:i + 200])


if __name__ == "__main__":
    unittest.main()
