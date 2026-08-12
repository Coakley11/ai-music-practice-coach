"""Music Coach semantic fingerprint + context-aware duplicate identity."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from applied_math_return_insight import SESSION_PENDING_KEY
from music_coach_ami.semantic_fingerprint import (
    music_coach_fingerprint_diff,
    music_coach_semantic_dimensions,
    music_coach_semantic_fingerprint,
)
from suite_analytical_question import (
    MUSIC_COACH_SUBMIT_DIAG_KEY,
    _AMI_COACH_SUBMIT_FEEDBACK_KEY,
    _execute_coach_question_submit,
    question_dedupe_fingerprint,
    utc_now_iso,
)


QUESTION = "Give me a good bass line to use for this song."
CHORDS_DB = ["Dbmaj7", "C7", "Fm7", "Ebm7", "Ab7", "Dbmaj7"]


def _base_ctx(**overrides) -> dict:
    ctx = {
        "coach_page": "practice",
        "display_key": "C",
        "instrument": "Bass",
        "level": "Beginner",
        "focus": "Walking Bass",
        "pick_key": "just_the_two_of_us",
        "practice_focus_section": "Verse",
        "active_song": {"title": "Just the Two of Us", "key": "Db", "pick_key": "just_the_two_of_us"},
        "chart_sections": {"Verse": list(CHORDS_DB)},
        "practice_snapshot": {
            "title": "Just the Two of Us",
            "display_key": "C",
            "pick_key": "just_the_two_of_us",
            "practice_focus_section": "Verse",
            "instrument": "Bass",
            "level": "Beginner",
            "focus": "Walking Bass",
        },
    }
    ctx.update(overrides)
    return ctx


class SemanticFingerprintUnitTests(unittest.TestCase):
    def test_identical_context_same_fingerprint(self) -> None:
        a = music_coach_semantic_fingerprint(QUESTION, _base_ctx())
        b = music_coach_semantic_fingerprint(QUESTION, _base_ctx())
        self.assertEqual(a, b)
        self.assertEqual(len(a), 12)

    def test_instrument_change_new_fingerprint(self) -> None:
        bass = music_coach_semantic_fingerprint(QUESTION, _base_ctx(instrument="Bass"))
        piano = music_coach_semantic_fingerprint(QUESTION, _base_ctx(instrument="Piano"))
        self.assertNotEqual(bass, piano)
        diff = music_coach_fingerprint_diff(
            music_coach_semantic_dimensions(QUESTION, _base_ctx(instrument="Bass")),
            music_coach_semantic_dimensions(QUESTION, _base_ctx(instrument="Piano")),
        )
        self.assertIn("instrument", diff)

    def test_level_focus_key_song_section_capo_explicit(self) -> None:
        base = music_coach_semantic_fingerprint(QUESTION, _base_ctx())
        self.assertNotEqual(base, music_coach_semantic_fingerprint(QUESTION, _base_ctx(level="Advanced")))
        self.assertNotEqual(base, music_coach_semantic_fingerprint(QUESTION, _base_ctx(focus="Phrasing")))
        self.assertNotEqual(base, music_coach_semantic_fingerprint(QUESTION, _base_ctx(display_key="Eb")))
        self.assertNotEqual(
            base,
            music_coach_semantic_fingerprint(
                QUESTION,
                _base_ctx(pick_key="other_song", active_song={"title": "Song B", "pick_key": "other_song"}),
            ),
        )
        self.assertNotEqual(
            base,
            music_coach_semantic_fingerprint(QUESTION, _base_ctx(practice_focus_section="Bridge")),
        )
        self.assertNotEqual(
            base,
            music_coach_semantic_fingerprint(
                QUESTION,
                _base_ctx(guitar_capo_enabled=True, guitar_capo_shape_key="G"),
            ),
        )
        easy = music_coach_semantic_fingerprint("Give me a very easy bass line for this song.", _base_ctx())
        self.assertNotEqual(base, easy)
        high = music_coach_semantic_fingerprint(
            "Give me a high-register bass line for this song.",
            _base_ctx(),
        )
        self.assertNotEqual(base, high)

    def test_music_question_id_uses_semantic_fingerprint(self) -> None:
        fp = music_coach_semantic_fingerprint(QUESTION, _base_ctx(instrument="Piano"))
        qid = question_dedupe_fingerprint(QUESTION, source_app="music", source_page="practice", context=_base_ctx(instrument="Piano"))
        self.assertEqual(fp, qid)
        # Non-music apps keep generic behavior (same wording → same id ignoring instrument).
        other_a = question_dedupe_fingerprint(QUESTION, source_app="nba", source_page="home", context={"instrument": "Bass"})
        other_b = question_dedupe_fingerprint(QUESTION, source_app="nba", source_page="home", context={"instrument": "Piano"})
        self.assertEqual(other_a, other_b)


class SemanticDedupeSubmitTests(unittest.TestCase):
    def _submit(self, ss: dict, *, instrument: str, level: str = "Beginner", focus: str = "Walking Bass", key: str = "C"):
        st = MagicMock()
        st.session_state = ss
        st.rerun = MagicMock()
        ui = MagicMock()

        def _extra():
            return _base_ctx(
                instrument=instrument,
                level=level,
                focus=focus,
                display_key=key,
                practice_snapshot={
                    "title": "Just the Two of Us",
                    "display_key": key,
                    "pick_key": "just_the_two_of_us",
                    "practice_focus_section": "Verse",
                    "instrument": instrument,
                    "level": level,
                    "focus": focus,
                },
            )

        with patch("suite_analytical_question.submit_analytical_question") as mock_cc, patch(
            "applied_math_return_insight.store_applied_math_insight",
            return_value="ins-sem",
        ), patch(
            "applied_math_return_insight.stage_pending_insight",
        ):
            out = _execute_coach_question_submit(
                st,
                ui,
                ss,
                question_raw=QUESTION,
                source_app="music",
                source_page="practice",
                page_suffix="practice",
                send_gen=int(ss.get("_ami_send_gen_music_practice") or 0),
                context_extra_builder=_extra,
                developer_mode=True,
            )
        return out, ui, mock_cc

    def test_bass_then_piano_then_guitar_then_true_duplicate(self) -> None:
        ss: dict = {
            "display_key": "C",
            "concert_key": "C",
            "original_key": "Db",
            "instrument": "Bass",
            "level": "Beginner",
            "focus": "Walking Bass",
            "improv_song_concert_sections": {"Verse": list(CHORDS_DB)},
            "_ami_send_gen_music_practice": 0,
        }

        out1, ui1, mock1 = self._submit(ss, instrument="Bass")
        self.assertTrue(out1 and out1.get("routed") and not out1.get("duplicate"))
        mock1.assert_not_called()
        fb1 = ss.get(_AMI_COACH_SUBMIT_FEEDBACK_KEY) or {}
        self.assertEqual(fb1.get("result_path"), "routed_coach")
        qid1 = (ss.get("_ami_last_send") or {}).get("question_id")

        ss["instrument"] = "Piano"
        out2, ui2, mock2 = self._submit(ss, instrument="Piano")
        self.assertTrue(out2 and out2.get("routed") and not out2.get("duplicate"))
        mock2.assert_not_called()
        qid2 = (ss.get("_ami_last_send") or {}).get("question_id")
        self.assertNotEqual(qid1, qid2)
        diag2 = ss.get(MUSIC_COACH_SUBMIT_DIAG_KEY) or {}
        self.assertFalse(diag2.get("duplicate"))
        self.assertIn("instrument", diag2.get("semantic_dimensions_changed") or [])

        ss["instrument"] = "Guitar"
        out3, ui3, mock3 = self._submit(ss, instrument="Guitar")
        self.assertTrue(out3 and out3.get("routed") and not out3.get("duplicate"))
        mock3.assert_not_called()
        qid3 = (ss.get("_ami_last_send") or {}).get("question_id")
        self.assertNotEqual(qid2, qid3)

        # Exact repeat — same Guitar context — should suppress.
        out4, ui4, mock4 = self._submit(ss, instrument="Guitar")
        self.assertTrue(out4 and out4.get("duplicate"))
        mock4.assert_not_called()
        info_msgs = " ".join(str(c.args[0]) for c in ui4.info.call_args_list if c.args)
        self.assertIn("same music settings", info_msgs.lower())
        self.assertNotIn("Command Center", info_msgs)
        fb4 = ss.get(_AMI_COACH_SUBMIT_FEEDBACK_KEY) or {}
        self.assertEqual(fb4.get("result_path"), "routed_coach")

    def test_key_and_level_changes_are_not_duplicates(self) -> None:
        ss: dict = {
            "display_key": "C",
            "instrument": "Bass",
            "level": "Beginner",
            "focus": "Walking Bass",
            "improv_song_concert_sections": {"Verse": list(CHORDS_DB)},
            "_ami_send_gen_music_practice": 0,
        }
        out1, _, _ = self._submit(ss, instrument="Bass", key="C")
        self.assertTrue(out1 and not out1.get("duplicate"))
        ss["display_key"] = "Eb"
        out2, _, _ = self._submit(ss, instrument="Bass", key="Eb")
        self.assertTrue(out2 and not out2.get("duplicate"))
        ss["level"] = "Advanced"
        out3, _, _ = self._submit(ss, instrument="Bass", key="Eb", level="Advanced")
        self.assertTrue(out3 and not out3.get("duplicate"))


if __name__ == "__main__":
    unittest.main()
