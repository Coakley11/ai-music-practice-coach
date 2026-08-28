"""Visible-UI contracts for Creative Backing Stabilization render tests.

These checks operate on rendered text (main pane, sidebar, banners), not
helper return values. They must fail on the mixed states from live QA.
"""

from __future__ import annotations

import re


def low(text: str) -> str:
    return (text or "").lower().replace("♯", "#").replace("♭", "b")


def _has(text: str, *needles: str) -> bool:
    blob = low(text)
    return any(low(n) in blob for n in needles if n)


def trial_preview_shows_shape_practice_key(text: str) -> bool:
    """Trial Custom preview must not show Shape's B minor Practice Key."""
    blob = low(text)
    if "trial song" not in blob:
        return False
    return bool(
        re.search(
            r"practice\s*/\s*concert\s*key\s+(?:<strong>)?b\s*minor",
            blob,
        )
        or re.search(r"original key\s+d\s+major.{0,80}practice\s*/\s*concert\s*key\s+b\s*minor", blob, re.S)
    )


def catalog_shape_backing_banner(text: str) -> bool:
    blob = low(text)
    return "backing source: catalog song" in blob and "shape of you" in blob


def return_to_song_catalog_visible(text: str) -> bool:
    return "return to song catalog" in low(text)


def trial_identity_with_shape_original(text: str) -> bool:
    blob = low(text)
    if "trial song" not in blob:
        return False
    return bool(
        re.search(r"original key[:\s]+b\s*m\b", blob)
        or re.search(r"song original key[:\s]+b\s*m\b", blob)
    )


def mixed_state_failures(
    *,
    body: str = "",
    main: str = "",
    sidebar: str = "",
    surface: str = "",
) -> list[str]:
    """Return human-readable failures for mixed identity/key/return states.

    ``surface`` is a hint: custom_page, custom_backing, songs, mission, sbi.
    """
    errors: list[str] = []
    main_text = main or body
    side_text = sidebar or ""
    all_text = "\n".join(part for part in (body, main, sidebar) if part)
    hint = (surface or "").strip().lower()

    if hint in {"custom_page", "custom_finish", "custom_return"}:
        if trial_preview_shows_shape_practice_key(main_text) or trial_preview_shows_shape_practice_key(
            all_text
        ):
            errors.append("Trial Custom page shows Practice / Concert Key B minor")
        if trial_identity_with_shape_original(main_text):
            errors.append("Trial title + Shape/Bm original key on Custom page")

    if hint in {"custom_backing", "backing"}:
        # Catalog Shape backing is allowed when Trial is not Set as Active.
        # Fail only on split-brain / broken return.
        if _has(side_text, "Trial Song") and catalog_shape_backing_banner(main_text):
            if not _has(side_text, "Shape of You"):
                errors.append("Trial sidebar + Shape Catalog backing card")
        if _has(side_text, "D major") and catalog_shape_backing_banner(main_text):
            errors.append("Trial/D projection leaked into Catalog backing sidebar")
        if catalog_shape_backing_banner(main_text) and return_to_song_catalog_visible(all_text):
            if "return to custom page" not in low(all_text):
                errors.append("Catalog backing from Custom page missing Return to Custom Page")
        if _has(main_text, "Trial Song") and _has(main_text, "B minor") and catalog_shape_backing_banner(
            main_text
        ):
            errors.append("Trial identity mixed with Shape Bm backing keys")
        if _has(all_text, "Trial Song") and return_to_song_catalog_visible(all_text):
            if "return to custom page" not in low(all_text):
                errors.append("Custom PK / Trial identity + Catalog return route")

    if hint in {"songs", "picker"}:
        if _has(main_text, "Trial Song") and not _has(main_text, "Shape of You"):
            # Library list may mention Trial; fail only when Shape is absent as owner.
            if not _has(side_text, "Shape of You"):
                errors.append("Songs surface lost Shape of You after Custom save")
        if _has(main_text, "Practice / Concert Key D major") and _has(main_text, "Shape of You"):
            if "d minor" not in low(main_text):
                errors.append("Custom save wrote Trial D into Shape Songs card")

    if hint in {"mission", "mission_return"}:
        if re.search(r"selected mission chord:\s*d#\s*m(?:inor)?", low(main_text)) and _has(
            main_text, "Practice Key"
        ):
            # Song tonic replacing the selected Mission chord after transpose/return.
            if not _has(main_text, "G#m", "Abm", "G# minor", "Ab minor"):
                errors.append("Mission Practice Key replaced the selected Mission chord")

    return errors


def finished_main_has_songs_and_practice(button_labels: list[str]) -> bool:
    labels = " ".join(button_labels or [])
    return bool(re.search(r"Songs", labels)) and bool(re.search(r"Practice", labels))


def backing_must_be_trial_custom(text: str) -> list[str]:
    """Legacy helper — Trial Custom backing when Trial *is* Global Active."""
    errors: list[str] = []
    blob = low(text)
    if catalog_shape_backing_banner(text):
        errors.append("catalog Shape backing banner")
    if return_to_song_catalog_visible(text):
        errors.append("Return to Song Catalog")
    if "trial song" not in blob:
        errors.append("missing Trial Song")
    if "custom" not in blob:
        errors.append("missing Custom source")
    if "return to custom page" not in blob and "return to custom" not in blob:
        errors.append("missing Return to Custom Page")
    return errors


def catalog_backing_from_custom_page_coherent(
    *,
    main: str = "",
    sidebar: str = "",
    body: str = "",
) -> list[str]:
    """Trial not active: Catalog Shape backing + matching sidebar + Return to Custom."""
    errors: list[str] = []
    main_text = main or body
    side_text = sidebar or ""
    all_text = "\n".join(part for part in (body, main, sidebar) if part)
    if not catalog_shape_backing_banner(main_text) and not catalog_shape_backing_banner(all_text):
        errors.append("expected Catalog Shape backing while Trial is not Global Active")
    if "return to custom page" not in low(all_text):
        errors.append("missing Return to Custom Page")
    if return_to_song_catalog_visible(all_text) and "return to custom page" not in low(all_text):
        errors.append("Return to Song Catalog without Custom-page return")
    if _has(side_text, "Trial Song") and not _has(side_text, "Shape of You"):
        errors.append("Trial sidebar on Catalog backing")
    if _has(side_text, "D major") or re.search(r"sidebar_pk\s+d\b", low(side_text)):
        errors.append("Trial D leaked into Catalog backing sidebar")
    if _has(main_text, "Trial Song") and catalog_shape_backing_banner(main_text):
        errors.append("Trial title on Catalog Shape backing card")
    return errors
