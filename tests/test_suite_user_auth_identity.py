"""Auth session must drive suite_user identity when Real Accounts are enabled."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from suite_user import get_external_user_id, get_user_email, reset_account_cache


def _coakley_session() -> dict:
    return {
        "_suite_auth_session": True,
        "_suite_auth_user_id": "uuid-coakley",
        "_suite_auth_user_email": "coakley11@aol.com",
        "_suite_auth_external_id": "coakley11",
    }


class TestSuiteUserAuthIdentity(unittest.TestCase):
    def setUp(self) -> None:
        reset_account_cache()

    def tearDown(self) -> None:
        reset_account_cache()

    def test_auth_session_overrides_secrets_external_id(self) -> None:
        session = _coakley_session()
        with patch("suite_user._authenticated_session_state", return_value=session), patch(
            "suite_auth.is_auth_enabled", return_value=True
        ), patch("suite_auth.is_authenticated", return_value=True):
            self.assertEqual(get_external_user_id(), "coakley11@aol.com")
            self.assertEqual(get_user_email(), "coakley11@aol.com")

    def test_secrets_used_when_auth_off(self) -> None:
        with patch("suite_user._authenticated_session_state", return_value=None), patch.dict(
            os.environ, {"SUITE_USER_ID": "daniel"}
        ):
            self.assertEqual(get_external_user_id(), "daniel")


if __name__ == "__main__":
    unittest.main()
