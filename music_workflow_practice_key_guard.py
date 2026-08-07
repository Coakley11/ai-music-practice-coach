"""Practice-key mutation invariant — parent key changes only via explicit key edit."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

EXPLICIT_PRACTICE_KEY_MUTATION_SOURCES = frozenset(
    {
        "sidebar_song_improv",
        "song_practice_key_sidebar",
        "on_sidebar_practice_concert_key_change",
        "practice_key_change",
        "song_practice_key_edit",
        "consume_pending_song_practice_key_edit",
    }
)


@dataclass(frozen=True)
class PracticeKeySnapshot:
    practice_tonic: str
    practice_mode: str
    token: str
    display_key: str
    concert_key: str

    @classmethod
    def capture(cls, session: dict[str, Any]) -> PracticeKeySnapshot:
        pt, pm, token = "", "", ""
        try:
            from music_workflow_song_practice import resolve_song_practice_key_token, song_practice_blob

            blob = song_practice_blob(session)
            if blob is not None:
                pt = str(blob.keys.practice_tonic or "C")
                pm = str(blob.keys.practice_mode or "major")
            token = resolve_song_practice_key_token(session) or str(session.get("display_key") or "C")
        except ImportError:
            token = str(session.get("display_key") or session.get("concert_key") or "C")
        return cls(
            practice_tonic=pt,
            practice_mode=pm,
            token=token,
            display_key=str(session.get("display_key") or ""),
            concert_key=str(session.get("concert_key") or ""),
        )

    def unchanged_vs(self, other: PracticeKeySnapshot) -> bool:
        return (
            self.practice_tonic.upper() == other.practice_tonic.upper()
            and self.practice_mode.lower() == other.practice_mode.lower()
            and self.token == other.token
        )


def assert_practice_key_unchanged(
    session: dict[str, Any],
    before: PracticeKeySnapshot,
    *,
    action: str,
) -> None:
    after = PracticeKeySnapshot.capture(session)
    if before.unchanged_vs(after):
        return
    raise AssertionError(
        f"practice key mutated by {action!r}: before={before.token!r} after={after.token!r} "
        f"(tonic {before.practice_tonic!r}/{before.practice_mode!r} -> "
        f"{after.practice_tonic!r}/{after.practice_mode!r})"
    )


__all__ = [
    "EXPLICIT_PRACTICE_KEY_MUTATION_SOURCES",
    "PracticeKeySnapshot",
    "assert_practice_key_unchanged",
]
