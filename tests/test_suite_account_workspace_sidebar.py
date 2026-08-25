"""Account & Workspace sidebar consolidation — nest Command Center + Saved Sessions."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from suite_account_settings import (
    account_workspace_expander_label,
    render_account_workspace_access,
)
from suite_app_shell import render_suite_sidebar_account_shell
from suite_command_center_link import command_center_url, render_command_center_sidebar_link
from suite_user_persistence import render_reset_controls


class _FakeExpander:
    def __init__(self, label: str, *, expanded: bool = False, key: str | None = None):
        self.label = label
        self.expanded = expanded
        self.key = key

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class _FakeSidebar:
    def __init__(self, parent: "_FakeSt"):
        self.parent = parent

    def expander(self, label: str, expanded: bool = False, key: str | None = None):
        self.parent.expanders.append({"label": label, "expanded": expanded, "key": key, "where": "sidebar"})
        return _FakeExpander(label, expanded=expanded, key=key)

    def link_button(self, label: str, url: str, use_container_width: bool = False):
        self.parent.link_buttons.append({"label": label, "url": url, "where": "sidebar"})

    def divider(self):
        self.parent.dividers.append("sidebar")

    def caption(self, text: str):
        self.parent.captions.append(text)

    def markdown(self, *args, **kwargs):
        self.parent.markdowns.append(args[0] if args else "")

    def button(self, *args, **kwargs):
        self.parent.buttons.append({"args": args, "kwargs": kwargs, "where": "sidebar"})
        return False

    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass

    def columns(self, *args, **kwargs):
        return [_FakeSidebar(self.parent), _FakeSidebar(self.parent)]


class _FakeSt:
    def __init__(self):
        self.session_state: dict = {}
        self.sidebar = _FakeSidebar(self)
        self.expanders: list[dict] = []
        self.link_buttons: list[dict] = []
        self.buttons: list[dict] = []
        self.markdowns: list = []
        self.captions: list = []
        self.dividers: list = []

    def expander(self, label: str, expanded: bool = False, key: str | None = None):
        self.expanders.append({"label": label, "expanded": expanded, "key": key, "where": "main"})
        return _FakeExpander(label, expanded=expanded, key=key)

    def link_button(self, label: str, url: str, use_container_width: bool = False):
        self.link_buttons.append({"label": label, "url": url, "where": "nested"})

    def markdown(self, *args, **kwargs):
        self.markdowns.append(args[0] if args else "")

    def caption(self, *args, **kwargs):
        self.captions.append(args[0] if args else "")

    def button(self, *args, **kwargs):
        label = args[0] if args else kwargs.get("label")
        self.buttons.append({"label": label, "kwargs": kwargs, "where": "nested"})
        return False

    def columns(self, *args, **kwargs):
        return [self, self]

    def warning(self, *args, **kwargs):
        pass

    def info(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass

    def rerun(self):
        pass


class TestAccountWorkspaceSidebarConsolidation(unittest.TestCase):
    def test_expander_label_is_compact_account_workspace(self) -> None:
        self.assertEqual(
            account_workspace_expander_label({"active_workspace_label": "Daniel"}),
            "Account & Workspace",
        )

    def test_shell_nests_utilities_without_top_level_command_center(self) -> None:
        st = _FakeSt()
        reset_calls: list = []

        def _on_reset(_st):
            reset_calls.append(1)

        with patch("suite_workspace.bootstrap_suite_workspace"), patch(
            "suite_workspace.can_show_developer_tools", return_value=False
        ), patch(
            "suite_account_settings.init_suite_workspace"
        ), patch(
            "suite_account_settings.build_account_settings_context",
            return_value={
                "active_workspace_label": "Daniel",
                "email_display": "user@example.com",
            },
        ), patch(
            "suite_auth.is_auth_enabled", return_value=True
        ), patch(
            "suite_auth.is_authenticated", return_value=True
        ), patch(
            "suite_auth.current_auth_email", return_value="user@example.com"
        ), patch(
            "suite_command_center_link.command_center_url",
            return_value="https://example.test/cc",
        ):
            render_suite_sidebar_account_shell(
                st,
                nest_account_utilities=True,
                saved_session_on_reset=_on_reset,
                saved_session_app_id="music",
            )

        top_labels = [e["label"] for e in st.expanders if e.get("where") == "sidebar"]
        self.assertEqual(top_labels.count("Account & Workspace"), 1)
        self.assertNotIn("Saved Sessions", top_labels)
        self.assertNotIn("Saved session", top_labels)
        self.assertFalse(any(b.get("where") == "sidebar" for b in st.link_buttons))

        nested_md = " ".join(str(m) for m in st.markdowns)
        self.assertIn("Command Center", nested_md)
        self.assertIn("Saved Sessions", nested_md)
        self.assertTrue(any(b.get("where") == "nested" for b in st.link_buttons))
        self.assertTrue(
            any(str(b.get("label") or "") == "Log out" for b in st.buttons),
        )
        self.assertTrue(
            any(str(b.get("label") or "") == "Reset to default" for b in st.buttons),
        )
        # Unique logout key
        logout_keys = [
            b["kwargs"].get("key")
            for b in st.buttons
            if str(b.get("label") or "") == "Log out"
        ]
        self.assertEqual(logout_keys, ["suite_account_workspace_logout_btn"])

    def test_nested_command_center_uses_canonical_url_helper(self) -> None:
        st = _FakeSt()
        with patch(
            "suite_command_center_link.command_center_url",
            return_value="https://example.test/cc?suite_workspace=daniel",
        ) as mock_url, patch(
            "suite_workspace.get_active_workspace_id", return_value="daniel"
        ):
            render_command_center_sidebar_link(
                st,
                label="Command Center",
                show_divider=False,
                use_sidebar=False,
            )
        mock_url.assert_called()
        self.assertEqual(st.link_buttons[0]["label"], "Command Center")
        self.assertIn("example.test/cc", st.link_buttons[0]["url"])

    def test_nested_saved_sessions_reuses_reset_controls(self) -> None:
        st = _FakeSt()
        called = {"n": 0}

        def _on_reset(_st):
            called["n"] += 1

        render_reset_controls(
            st,
            "music",
            on_reset=_on_reset,
            nested=True,
            label="Reset to default",
        )
        self.assertIn("**Saved Sessions**", st.markdowns)
        self.assertTrue(
            any(
                b["kwargs"].get("key") == "suite_reset_btn::music"
                for b in st.buttons
            )
        )
        # Nested must not create a top-level sidebar expander
        self.assertFalse(any(e.get("where") == "sidebar" for e in st.expanders))

    def test_legacy_unested_shell_still_renders_top_level_command_center(self) -> None:
        st = _FakeSt()
        with patch("suite_workspace.bootstrap_suite_workspace"), patch(
            "suite_workspace.can_show_developer_tools", return_value=False
        ), patch("suite_account_settings.render_account_workspace_access"), patch(
            "suite_command_center_link.command_center_url",
            return_value="https://example.test/cc",
        ), patch(
            "suite_workspace.get_active_workspace_id", return_value="daniel"
        ):
            render_suite_sidebar_account_shell(
                st,
                nest_account_utilities=False,
                show_command_center_link=True,
            )
        self.assertTrue(any(b.get("where") == "sidebar" for b in st.link_buttons))

    def test_command_center_url_helper_unchanged(self) -> None:
        with patch(
            "suite_workspace.resolve_workspace_id", return_value="daniel"
        ), patch(
            "suite_workspace.append_suite_workspace_param",
            side_effect=lambda base, workspace_id="": f"{base}?ws={workspace_id}",
        ):
            url = command_center_url(workspace_id="daniel")
        self.assertIn("daniel", url)

    def test_music_sidebar_layout_marker_drops_separate_utility_sections(self) -> None:
        from music_sidebar_layout import MUSIC_SIDEBAR_SECTION_ORDER

        self.assertIn("account_workspace", MUSIC_SIDEBAR_SECTION_ORDER)
        self.assertNotIn("command_center", MUSIC_SIDEBAR_SECTION_ORDER)
        self.assertNotIn("saved_session", MUSIC_SIDEBAR_SECTION_ORDER)


class TestAccountWorkspaceDoesNotTouchStudioNav(unittest.TestCase):
    def test_access_render_does_not_mutate_studio_page(self) -> None:
        st = _FakeSt()
        st.session_state["studio_page"] = "composer"
        with patch("suite_account_settings.init_suite_workspace"), patch(
            "suite_account_settings.build_account_settings_context",
            return_value={"active_workspace_label": "Daniel", "email_display": ""},
        ), patch(
            "suite_workspace.can_show_developer_tools", return_value=False
        ), patch(
            "suite_auth.is_auth_enabled", return_value=False
        ), patch(
            "suite_command_center_link.command_center_url",
            return_value="https://example.test/cc",
        ):
            render_account_workspace_access(
                st,
                sidebar=True,
                include_command_center=True,
                saved_session_on_reset=lambda _s: None,
            )
        self.assertEqual(st.session_state["studio_page"], "composer")


if __name__ == "__main__":
    unittest.main()
