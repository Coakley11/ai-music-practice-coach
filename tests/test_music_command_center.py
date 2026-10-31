"""Music Command Center — resume payloads, workspace isolation, restore."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from music_command_center import (
    build_continue_card,
    build_workstream_card,
    build_workstream_cards,
    filter_continue_cards_for_workspace,
    upsert_music_continue_card,
)
from music_resume_payload import (
    apply_music_resume_payload,
    build_music_resume_payload,
    continue_card_subtitle,
    continue_card_title,
    decode_payload_b64,
    encode_payload_b64,
    filter_payloads_for_workspace,
    legacy_resume_key_for_payload,
    payload_workspace_matches,
    resume_key_for_payload,
)
from suite_deep_links import build_music_continue_url, build_music_workstream_url


def _practice_session(*, workspace_id: str = "daniel") -> dict:
    return {
        "_suite_active_workspace_id": workspace_id,
        "studio_page": "practice",
        "active_catalog_pick_key": "Pop|Shape of You — Ed Sheeran",
        "song": "Shape of You",
        "artist": "Ed Sheeran",
        "instrument": "Tenor Sax",
        "display_key": "B minor",
        "bpm": 90,
        "practice_focus_section": "Verse",
        "selected_song": {"title": "Shape of You", "artist": "Ed Sheeran", "pick_key": "Pop|Shape of You — Ed Sheeran"},
    }


def _backing_session(*, workspace_id: str = "daniel") -> dict:
    base = _practice_session(workspace_id=workspace_id)
    base.update(
        {
            "studio_page": "backing",
            "backing_track_scope": "Selected sections",
            "backing_track_multi_sections": ["Verse", "Chorus"],
            "backing_track_bpm": 92,
            "backing_groove_style": "Funk",
            "backing_track_loops": 3,
        }
    )
    return base


class TestMusicResumePayload(unittest.TestCase):
    def test_practice_payload_captures_task_state(self) -> None:
        payload = build_music_resume_payload(_practice_session())
        self.assertEqual(payload["resume_kind"], "practice")
        self.assertEqual(payload["song"], "Shape of You")
        self.assertEqual(payload["instrument"], "Tenor Sax")
        self.assertEqual(payload["display_key"], "B minor")
        self.assertEqual(payload["bpm"], 90)
        self.assertEqual(payload["workspace_id"], "daniel")

    def test_practice_continue_card_copy(self) -> None:
        payload = build_music_resume_payload(_practice_session())
        title = continue_card_title(payload)
        self.assertEqual(title, "Continue Shape of You — Practice")
        sub = continue_card_subtitle(payload)
        self.assertIn("Tenor Sax", sub)
        self.assertIn("B minor", sub)
        self.assertIn("90 BPM", sub)
        # The producer encodes the concert-pitch semantic explicitly.
        self.assertEqual(payload["key_kind"], "concert")
        self.assertIn("Concert B minor", sub)

    def test_backing_payload_scope_and_sections(self) -> None:
        payload = build_music_resume_payload(_backing_session())
        self.assertEqual(payload["resume_kind"], "backing")
        self.assertEqual(payload["backing_track_scope"], "Selected sections")
        self.assertEqual(payload["backing_track_multi_sections"], ["Verse", "Chorus"])
        title = continue_card_title(payload)
        self.assertTrue(title.endswith("— Backing"))
        self.assertNotIn("Verse", title)
        self.assertIn("Verse", continue_card_subtitle(payload))
        self.assertEqual(continue_card_subtitle(payload).count("Full song"), 0)

    def test_payload_round_trip_b64(self) -> None:
        payload = build_music_resume_payload(_backing_session(workspace_id="coakley11"))
        encoded = encode_payload_b64(payload)
        decoded = decode_payload_b64(encoded)
        self.assertEqual(decoded.get("workspace_id"), "coakley11")
        self.assertEqual(decoded.get("resume_kind"), "backing")

    def test_workspace_isolation_filter(self) -> None:
        daniel = build_music_resume_payload(_practice_session(workspace_id="daniel"))
        coakley = build_music_resume_payload(_practice_session(workspace_id="coakley11"))
        scoped = filter_payloads_for_workspace([daniel, coakley], "coakley11")
        self.assertEqual(len(scoped), 1)
        self.assertEqual(scoped[0]["workspace_id"], "coakley11")

    def test_apply_rejects_foreign_workspace(self) -> None:
        payload = build_music_resume_payload(_practice_session(workspace_id="daniel"))
        session = {"_suite_active_workspace_id": "coakley11", "studio_page": "picker"}
        ok = apply_music_resume_payload(session, payload)
        self.assertFalse(ok)
        self.assertNotEqual(session.get("active_catalog_pick_key"), payload["pick_key"])

    def test_apply_restores_practice_state(self) -> None:
        payload = build_music_resume_payload(_practice_session(workspace_id="coakley11"))
        session: dict = {"_suite_active_workspace_id": "coakley11"}
        ok = apply_music_resume_payload(session, payload)
        self.assertTrue(ok)
        self.assertEqual(session.get("active_catalog_pick_key"), payload["pick_key"])
        self.assertEqual(session.get("instrument"), "Tenor Sax")
        self.assertEqual(session.get("practice_focus_section"), "Verse")
        self.assertEqual(session.get("studio_page"), "practice")

    def test_apply_restores_backing_filters(self) -> None:
        payload = build_music_resume_payload(_backing_session(workspace_id="daniel"))
        session: dict = {"_suite_active_workspace_id": "daniel"}
        apply_music_resume_payload(session, payload)
        self.assertEqual(session.get("studio_page"), "backing")
        self.assertEqual(session.get("backing_track_scope"), "Selected sections")
        self.assertEqual(session.get("backing_track_multi_sections"), ["Verse", "Chorus"])
        self.assertIn("Funk", str(session.get("backing_groove_style") or ""))


class TestMusicCommandCenterCards(unittest.TestCase):
    def test_continue_card_has_action_url_with_payload(self) -> None:
        payload = build_music_resume_payload(_practice_session(workspace_id="coakley11"))
        card = build_continue_card(payload)
        self.assertEqual(card["card_type"], "continue")
        self.assertEqual(card["workspace_id"], "coakley11")
        self.assertIn("suite_resume_payload=", card["action_url"])
        self.assertIn("suite_workspace=coakley11", card["action_url"])
        self.assertEqual(card["resume_key"], legacy_resume_key_for_payload(payload))

    def test_workstream_url_does_not_force_song(self) -> None:
        url = build_music_workstream_url("practice", workspace_id="coakley11")
        self.assertIn("suite_entry_mode=workstream", url)
        self.assertIn("suite_page=practice", url)
        self.assertIn("suite_workspace=coakley11", url)
        self.assertNotIn("suite_pick_key", url)
        self.assertNotIn("suite_resume_payload", url)

    def test_continue_url_includes_task_restore(self) -> None:
        payload = build_music_resume_payload(_backing_session())
        url = build_music_continue_url(payload)
        self.assertIn("suite_entry_mode=continue", url)
        self.assertIn("suite_backing_scope=Selected+sections", url)
        self.assertIn("suite_backing_sections=Verse%7CChorus", url)

    def test_filter_continue_cards_workspace(self) -> None:
        daniel_card = build_continue_card(build_music_resume_payload(_practice_session(workspace_id="daniel")))
        coakley_card = build_continue_card(build_music_resume_payload(_practice_session(workspace_id="coakley11")))
        scoped = filter_continue_cards_for_workspace([daniel_card, coakley_card], "coakley11")
        self.assertEqual(len(scoped), 1)
        self.assertEqual(scoped[0]["workspace_id"], "coakley11")

    def test_workstream_cards_cover_music_areas(self) -> None:
        cards = build_workstream_cards(workspace_id="daniel")
        kinds = {c["workstream_kind"] for c in cards}
        self.assertIn("song_practice", kinds)
        self.assertIn("backing", kinds)
        self.assertIn("creative", kinds)
        self.assertIn("multitrack", kinds)
        self.assertIn("tone", kinds)
        self.assertIn("upload", kinds)
        for card in cards:
            self.assertEqual(card["card_type"], "workstream")
            self.assertNotIn("suite_pick_key", card["action_url"])

    def test_upsert_uses_scoped_storage_app(self) -> None:
        payload = build_music_resume_payload(_practice_session(workspace_id="coakley11"))
        calls: list[tuple] = []

        def _fake_upsert(app, item_key, **kwargs):
            calls.append((app, item_key, kwargs))
            return {"write_mode": "upsert"}

        with patch("suite_storage_supabase.upsert_resume_item", side_effect=_fake_upsert):
            ok = upsert_music_continue_card(payload)
        self.assertTrue(ok)
        self.assertEqual(calls[0][0], "music__coakley11")
        self.assertTrue(str(calls[0][1]).startswith("music:") or str(calls[0][1]).startswith("song:"))


class TestSuiteResumeLaunchIntegration(unittest.TestCase):
    def test_workstream_entry_skips_song_restore(self) -> None:
        class _QP(dict):
            def get(self, key, default=None):
                return super().get(key, default)

        class _St(dict):
            session_state = property(lambda self: self)
            query_params = _QP(
                {
                    "suite_entry_mode": "workstream",
                    "suite_page": "backing",
                    "suite_workspace": "coakley11",
                }
            )

        st = _St()
        from suite_resume_launch import apply_suite_resume_launch

        self.assertTrue(apply_suite_resume_launch(st, "music"))
        self.assertEqual(st.get("studio_page"), "backing")
        self.assertNotIn("active_catalog_pick_key", st)

    def test_continue_payload_restore_via_query(self) -> None:
        payload = build_music_resume_payload(_practice_session(workspace_id="daniel"))
        encoded = encode_payload_b64(payload)

        class _QP(dict):
            def get(self, key, default=None):
                return super().get(key, default)

        class _St(dict):
            session_state = property(lambda self: self)
            query_params = _QP(
                {
                    "suite_entry_mode": "continue",
                    "suite_resume_payload": encoded,
                    "suite_workspace": "daniel",
                }
            )

        st = _St({"_suite_active_workspace_id": "daniel"})
        from suite_resume_launch import apply_suite_resume_launch

        with patch("music_resume_payload._resolve_workspace_id", return_value="daniel"):
            self.assertTrue(apply_suite_resume_launch(st, "music"))
        self.assertEqual(st.get("instrument"), "Tenor Sax")
        self.assertEqual(st.get("studio_page"), "practice")


if __name__ == "__main__":
    unittest.main()


class TestContinueCardHierarchy(unittest.TestCase):
    """Resource first, workflow second, setup metadata third; nothing invented."""

    def test_generated_contexts_do_not_invent_a_song(self) -> None:
        jam = {"resume_kind": "creative", "improv_entry_mode": "Jam Session Generator",
               "improv_style_key": "Bossa Nova", "workspace_id": "daniel"}
        self.assertEqual(continue_card_title(jam), "Continue Jam Session — Bossa Nova")
        style = {"resume_kind": "creative", "improv_entry_mode": "Style Jam Mode",
                 "improv_style_key": "Pop groove"}
        self.assertEqual(continue_card_title(style), "Continue Style Jam — Pop groove")

    def test_style_never_leads_when_a_song_exists_and_auto_is_dropped(self) -> None:
        p = {"resume_kind": "backing", "song": "Blue Bossa", "pick_key": "bb",
             "instrument": "Tenor Sax", "display_key": "Cm", "key_kind": "concert",
             "backing_track_bpm": 120, "backing_track_scope": "Full song",
             "style": "Auto", "mood": "Mellow", "backing_track_loops": 4}
        self.assertEqual(continue_card_title(p), "Continue Blue Bossa — Backing")
        self.assertEqual(continue_card_subtitle(p), "Catalog · Tenor Sax · Concert Cm · 120 BPM")

    def test_backing_without_song_uses_only_the_real_style(self) -> None:
        self.assertEqual(continue_card_title({"resume_kind": "backing", "style": "Jewish hora", "mood": "Mellow"}),
                         "Continue Backing Track — Jewish hora")
        self.assertEqual(continue_card_title({"resume_kind": "backing", "style": "Auto", "mood": "Mellow"}),
                         "Continue Backing Track")

    def test_upload_composition_custom_and_unknown_key_kind(self) -> None:
        self.assertEqual(continue_card_title({"resume_kind": "upload", "upload_label": "Hava Nagila"}),
                         "Continue Hava Nagila — Upload")
        comp = {"resume_kind": "practice", "studio_page": "composer", "song": "River Sketch",
                "pick_key": "composition::r1"}
        self.assertEqual(continue_card_title(comp), "Continue River Sketch — Composition")
        self.assertTrue(continue_card_subtitle(comp).startswith("Composition"))
        legacy = {"resume_kind": "practice", "song": "X", "pick_key": "custom::1", "display_key": "D"}
        self.assertEqual(continue_card_subtitle(legacy), "Custom · Practice Key: D")


class TestUploadIdentity(unittest.TestCase):
    def _upload_session(self, **extra) -> dict:
        s = _practice_session()
        s.update({"studio_page": "analysis", "last_analysis_source_label": "Friday Gig.wav", **extra})
        return s

    def test_upload_does_not_inherit_active_catalog_song(self) -> None:
        payload = build_music_resume_payload(self._upload_session(upload_catalog_active_recording_id="rec_42"))
        for field in ("song", "pick_key", "instrument", "display_key"):
            self.assertEqual(payload[field], "")
        self.assertNotIn("key_kind", payload)
        self.assertEqual((payload["source_type"], payload["source_id"], payload["upload_id"]),
                         ("upload", "rec_42", "rec_42"))
        self.assertEqual(continue_card_title(payload), "Continue Friday Gig.wav — Upload")
        self.assertEqual(continue_card_subtitle(payload), "Upload")
        self.assertEqual(resume_key_for_payload(payload), "music:upload:rec_42")

    def test_upload_without_stable_id_invents_no_identity(self) -> None:
        payload = build_music_resume_payload(self._upload_session())
        self.assertNotIn("upload_id", payload)
        self.assertNotIn("source_type", payload)
        self.assertEqual(payload["pick_key"], "")
        self.assertEqual(continue_card_subtitle(payload), "")
        self.assertNotIn("Catalog", continue_card_subtitle(payload))

    def test_backing_subtitle_omits_style_like_command_center(self) -> None:
        payload = build_music_resume_payload(_backing_session())
        self.assertNotIn("Funk", continue_card_subtitle(payload))
