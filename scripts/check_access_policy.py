"""Read-only: report whether the access policy is configured and well-formed. Prints counts only (no ids, no emails).

Run with the same environment/secrets as the app:  python scripts/check_access_policy.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import suite_access_policy as pol  # noqa: E402


def main() -> int:
    personal = pol.personal_accounts()
    admins = pol.admin_user_ids()
    print(f"SUITE_PERSONAL_ACCOUNTS: {len(personal)} valid entr{'y' if len(personal) == 1 else 'ies'}"
          f" -> workspaces {sorted(set(personal.values()))}")
    print(f"SUITE_ADMIN_USER_IDS: {len(admins)} valid auth user id(s)")
    problems = []
    if not personal:
        problems.append("no personal workspace is attached: the owners will get new, empty workspaces")
    if not admins:
        problems.append("nobody is admin")
    for p in problems:
        print("NOTE:", p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
