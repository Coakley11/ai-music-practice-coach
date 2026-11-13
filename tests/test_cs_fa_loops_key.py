"""composer_play_loops is the Chords transport slider key; the hum panel must not assign it."""
import inspect
import unittest


class TestPlayLoopsKey(unittest.TestCase):
    def test_hum_panel_does_not_assign_slider_key(self) -> None:
        import composition_studio_page as page

        src = inspect.getsource(page._render_hum_sing_panel)
        self.assertNotIn('session_state["composer_play_loops"]', src)

    def test_assignment_after_slider_raises_so_hazard_is_real(self) -> None:
        from streamlit.testing.v1 import AppTest

        def app():
            import streamlit as st

            st.slider("Loops", 1, 4, 2, key="composer_play_loops")
            if st.session_state.get("_bad"):
                st.session_state["composer_play_loops"] = 1

        at = AppTest.from_function(app, default_timeout=30)
        at.run()
        at.slider(key="composer_play_loops").set_value(3).run()
        self.assertFalse(at.exception)
        at.session_state["_bad"] = True
        at.run()
        self.assertTrue(at.exception)
