"""Live-render regression: Finish Song exits + Custom-page Trial Backing.

Clicks the actual Streamlit Finish Song and Backing widgets, then asserts
visible text after the production double-hydrate/reconcile path.
"""

from __future__ import annotations

import unittest
from pathlib import Path


HARNESS = "streamlit_custom_page_finish_backing_harness.py"


def _all_text(at: object) -> str:
    chunks: list[str] = []
    for attr in ("markdown", "caption", "text", "title", "header", "subheader"):
        block = getattr(at, attr, None)
        if block is None:
            continue
        try:
            for item in block:
                chunks.append(str(getattr(item, "value", item) or ""))
        except Exception:
            chunks.append(str(block))
    try:
        for btn in at.button:
            chunks.append(str(getattr(btn, "label", "") or ""))
    except Exception:
        pass
    return "\n".join(chunks)


def _ss_get(ss: object, key: str, default: object = None) -> object:
    try:
        return ss[key]
    except Exception:
        return default


def _button_labels(at: object) -> list[str]:
    labels: list[str] = []
    try:
        for btn in at.button:
            labels.append(str(getattr(btn, "label", "") or ""))
    except Exception:
        pass
    return labels


@unittest.skipUnless(
    __import__("importlib").util.find_spec("streamlit.testing.v1") is not None,
    "streamlit.testing.v1 unavailable",
)
class TestCustomPageFinishBackingRender(unittest.TestCase):
    def test_finish_song_keeps_exits_and_backing_stays_trial(self) -> None:
        from streamlit.testing.v1 import AppTest

        from app_ui import nav_icon_button_label

        root = Path(__file__).resolve().parents[1]
        at = AppTest.from_file(str(root / HARNESS), default_timeout=120)
        at.run(timeout=180)

        finish = at.button(key="cpl_finish")
        self.assertIsNotNone(finish, "Finish Song widget must render on Custom page")
        finish.click().run(timeout=180)

        labels = _button_labels(at)
        songs_label = nav_icon_button_label("picker")
        practice_label = nav_icon_button_label("practice")
        self.assertIn(songs_label, labels)
        self.assertIn(practice_label, labels)
        self.assertTrue(any("Set as Active Song" in lab for lab in labels))
        self.assertIsNotNone(at.button(key="cpl_to_backing_finish"))
        self.assertIsNotNone(at.button(key="cpl_exit_picker_finish"))
        self.assertIsNotNone(at.button(key="cpl_exit_practice_finish"))

        visible = _all_text(at)
        self.assertNotIn("Practice / Concert Key B minor", visible)
        self.assertNotIn("Practice / Concert Key <strong>B minor</strong>", visible)
        self.assertIn("Trial Song", visible)
        self.assertIn("D major", visible)
        self.assertIn("Practice / Concert Key", visible)
        self.assertTrue(
            "D major" in visible and "Practice / Concert Key" in visible,
            visible,
        )

        backing = at.button(key="cpl_to_backing_finish")
        self.assertIsNotNone(backing)
        backing.click().run(timeout=180)

        visible = _all_text(at)
        labels = _button_labels(at)
        self.assertNotIn("Backing source: Catalog song · Shape of You", visible)
        self.assertNotIn("Return to Song Catalog", visible)
        self.assertFalse(any("Return to Song Catalog" in lab for lab in labels))
        self.assertIn("Custom progression", visible)
        self.assertIn("Trial Song", visible)
        self.assertTrue(
            any("Return to Custom Page" in lab for lab in labels),
            labels,
        )
        self.assertIn("BLUE_CARD source=custom_progression", visible)
        self.assertNotIn("BLUE_CARD source=regular_song", visible)
        self.assertIn("SIDEBAR_TITLE Trial Song", visible)
        self.assertIn("SIDEBAR_ORIGINAL D", visible)
        self.assertIn("SIDEBAR_PK D", visible)
        ss = at.session_state
        stages = list(_ss_get(ss, "_custom_finish_backing_stages") or [])
        self.assertTrue(stages, "harness must log owner/source keys at each stage")
        after = next(
            (
                row
                for row in reversed(stages)
                if row.get("stage") == "after_production_double_hydrate"
            ),
            {},
        )
        before = next(
            (
                row
                for row in reversed(stages)
                if row.get("stage") == "backing_before_production_hydrate"
            ),
            {},
        )
        self.assertEqual(after.get("ctx_source"), "custom_progression", after)
        self.assertIn("Trial Song", str(after.get("ctx_title") or ""), after)
        self.assertEqual(after.get("ga_source"), "catalog_song", {"before": before, "after": after})
        self.assertEqual(after.get("ga_song"), "Shape of You", after)
        self.assertEqual(str(_ss_get(ss, "active_music_source") or ""), "catalog_song")
        self.assertEqual(str(_ss_get(ss, "song") or ""), "Shape of You")


if __name__ == "__main__":
    unittest.main()
