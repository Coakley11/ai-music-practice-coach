"""One song end = one "ended" = one advance of the Karaoke Set.

Measured on f7419c6f (390 px, isolated data, Karaoke Set, Lead Sheet off): Blackbird ended -> the set moved on to
Trial Song, and 3.0 s later a second "ended" (transport playing) moved it on again, to Jazz tune - Trial Song was
skipped. Two senders reported the same end: the follow-along player (which since 2026-11-20 is mounted in Voice with
the singing panel, whatever the Lead Sheet switch says) through __backingReportKaraokeEnded, and the card's own
audio poll, which still reported whenever the Lead Sheet was off. The stale re-key fixed in 71e21577 had masked the
second report by stopping the transport.
"""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
CARD = (ROOT / "backing_transport_component" / "index.html").read_text(encoding="utf-8")


class OneSender(unittest.TestCase):
    def test_in_voice_the_card_poll_never_reports_a_karaoke_end(self) -> None:
        i = APP.index("def render_backing_card_transport_control(")
        body = APP[i:APP.index("_now_singing = \"\"", i)]
        self.assertIn("report_ended = not (\n                km.is_voice_mode(st.session_state)\n"
                      "                or bool(st.session_state.get(\"backing_lead_sheet_open\"))\n            )", body)
        self.assertNotIn('report_ended = not bool(st.session_state.get("backing_lead_sheet_open"))', body)

    def test_each_end_report_names_its_sender(self) -> None:
        self.assertIn('send("ended", { via: "sheet" });', CARD)
        self.assertIn('anyEnded()) send("ended", { via: "card" });', CARD)
        self.assertNotIn('send("ended");', CARD)

    def test_the_server_trace_records_the_sender(self) -> None:
        i = APP.index('elif _card_action == "ended":')
        self.assertIn('"via": str((st.session_state.get("backing_card_transport") or {}).get("via") or "")', APP[i:i + 1800])


if __name__ == "__main__":
    unittest.main()
