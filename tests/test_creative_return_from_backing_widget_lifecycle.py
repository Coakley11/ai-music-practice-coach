"""AppTest — Return to Creative uses prepare_return + rerun hydrate (not direct-only)."""

from __future__ import annotations

import unittest
from typing import Any


LIFECYCLE_HARNESS = "streamlit_creative_lifecycle_harness.py"


class _SessionAdapter:
    def __init__(self, ss: Any) -> None:
        self._ss = ss

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self._ss[key]
        except (KeyError, TypeError, AttributeError):
            return default


@unittest.skipUnless(
    __import__("importlib").util.find_spec("streamlit.testing.v1") is not None,
    "streamlit.testing.v1 unavailable",
)
class TestCreativeReturnFromBackingWidgetLifecycle(unittest.TestCase):
    def test_return_to_creative_button_restores_style_jam_entry_mode(self) -> None:
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_file(LIFECYCLE_HARNESS, default_timeout=180)
        at.run(timeout=240)
        at.radio(key="improv_entry_mode").set_value("Style Jam Mode").run()
        at.run(timeout=120)
        if "improv_style_key" in at.session_state:
            at.selectbox(key="improv_style_key").set_value("E")
        gen = at.button(key="improv_gen_style")
        if gen is not None:
            gen.click().run()
            at.run(timeout=120)
        open_btn = at.button(key="improv_to_backing_jam")
        self.assertIsNotNone(open_btn)
        open_btn.click().run()
        at.run(timeout=120)
        ret = at.button(key="lc_return_creative")
        self.assertIsNotNone(ret)
        ret.click().run()
        at.run(timeout=120)
        ss = _SessionAdapter(at.session_state)
        self.assertEqual(str(ss.get("improv_entry_mode") or ""), "Style Jam Mode")
        self.assertEqual(str(ss.get("studio_page") or ""), "creative")


if __name__ == "__main__":
    unittest.main()
