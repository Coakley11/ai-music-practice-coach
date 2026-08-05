"""Requirements pins and Streamlit/Starlette compatibility guard."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from music_dependency_compatibility import (
    CERTIFY_STARLETTE_14_ENV,
    REQUIRED_STARLETTE_PIN,
    enforce_runtime_compatibility,
    evaluate_starlette_streamlit_compatibility,
    read_requirements_starlette_pin,
)


class TestMusicDependencyCompatibility(unittest.TestCase):
    def test_requirements_pins_starlette_exact(self) -> None:
        pin = read_requirements_starlette_pin()
        self.assertEqual(pin, f"starlette=={REQUIRED_STARLETTE_PIN}")

    def test_streamlit_161_starlette_14_fails_without_certification(self) -> None:
        ev = evaluate_starlette_streamlit_compatibility(
            {"python": "3.14.6", "streamlit": "1.61.0", "starlette": "1.4.0", "uvicorn": "0.34.0"}
        )
        self.assertFalse(ev["compatible"])
        self.assertIn("1.3.1", ev["reason"])

    def test_streamlit_161_starlette_13_ok(self) -> None:
        ev = evaluate_starlette_streamlit_compatibility(
            {"python": "3.14.6", "streamlit": "1.61.0", "starlette": "1.3.1", "uvicorn": "0.34.0"}
        )
        self.assertTrue(ev["compatible"])

    def test_certified_starlette_14_allowed(self) -> None:
        with patch.dict("os.environ", {CERTIFY_STARLETTE_14_ENV: "1"}):
            ev = evaluate_starlette_streamlit_compatibility(
                {"python": "3.14.6", "streamlit": "1.61.0", "starlette": "1.4.0", "uvicorn": "0.34.0"}
            )
        self.assertTrue(ev["compatible"])

    def test_enforce_exits_on_bad_combo(self) -> None:
        with patch(
            "music_dependency_compatibility.evaluate_starlette_streamlit_compatibility",
            return_value={"compatible": False, "reason": "bad", "python": "3.14.6", "streamlit": "1.61.0", "starlette": "1.4.0", "uvicorn": "0"},
        ):
            with self.assertRaises(SystemExit):
                enforce_runtime_compatibility(context="test")


if __name__ == "__main__":
    unittest.main()
